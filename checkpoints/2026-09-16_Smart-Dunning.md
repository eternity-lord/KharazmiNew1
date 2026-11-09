# Smart Auto-Dunning (Human-in-the-Loop) - 2026-09-16

**Branch:** `arena/01a0a936-kharazmiapp`
**Task:** Implement **Smart Auto-Dunning (Human-in-the-Loop Reminder System)** - Draft only, Admin-only, Idempotency 48h via ActivityLog/SmsLog
**Constraints CRITICAL:** NO Auto-Send (only drafts), Idempotency 48h (ActivityLog/SmsLog reminder), Isolation (new router `dunning.py` DO NOT modify `finance.py`/`timeline.py`), Security Admin only (`check_admin_access`), Buckets Upcoming 1-3d / Overdue 1-7d / Critical >7d

---

## 1. Backend - `Kharazmi_Server/routers/dunning.py` (New, Isolated, Optimized)

**Isolation:** New file only (324 lines). `finance.py` / `timeline.py` / `audit.py` untouched - verified via `git diff HEAD --` empty + `sha256sum finance.py` identical (`fca8c7aff4037cc21e3c8dc1e6b9ad765c7a697c04d3092a71118fb28f0e1d53` head vs working). No modifications to any financial logic, no new columns.

**Security:** Both endpoints require `_: str = Depends(check_admin_access)` (Admin only). Non-admin (secretary/teacher/parent/student) => 403, missing/invalid token => 401. Admin username for `ActivityLog` is resolved via `get_session_from_token(db, token) -> User.username` (same pattern as `finance.py:994`).

**Buckets - Parse Jalali via Central Converter:**

```python
from today_summary import parse_project_date, jalali_date_string

today = datetime.datetime.now().date()
def _categorize(due_date_str, today):
    d = parse_project_date(due_date_str)  # Jalali 1405/06/15 -> Gregorian 2026-09-06
    if not d: return None, None
    diff = (d - today).days  # due - today
    if 1 <= diff <=3:      return "upcoming", diff      # 1-3 days future
    elif -7 <= diff <= -1: return "overdue", diff       # 1-7 days past
    elif diff < -7:        return "critical", diff      # >7 days past
    else:                  return None, diff              # far future >3 or today (0) -> ignore
```

Test: today 2026-09-16, due 1405/06/27 (+2) => diff 2 => upcoming, due 1405/06/23 (-2) => overdue, due 1405/06/15 (-10) => critical, due 1405/07/04 (+10) far-future ignored, due today (0) ignored - matches spec 3 buckets.

**N+1 Fix - Single Query with `joinedload` (no per-row query):**

```python
# One query for all unpaid installments + student/course via joinedload (no N+1)
installments = (
    db.query(Installment)
    .join(Enrollment, Installment.enrollment_id == Enrollment.id)
    .join(Student, Enrollment.student_id == Student.id)
    .options(
        joinedload(Installment.enrollment).joinedload(Enrollment.student),  # parent_mobile + student_name loaded
        joinedload(Installment.enrollment).joinedload(Enrollment.course),   # future course preview if needed
    )
    .filter(
        Installment.is_deleted==False, Installment.is_paid==False,
        Enrollment.is_deleted==False, Student.is_deleted==False,
    )
    .all()  # candidates then categorized in Python (oldest critical first via diff sort)
)
# Loop uses inst.enrollment.student.parent_mobile / first_name directly - 0 extra queries
```

Without `joinedload`, each draft would issue `N` queries for `Student` + `Course` (N up to 100) -> 200 queries. With `joinedload`, exactly **1 query** for drafts (+ 2 for idempotency check). Verified via test: drafts call emitted 3 SQL statements total (installments + ActivityLog + SmsLog), vs 100+ without.

**Idempotency 48h - `ActivityLog` OR `SmsLog`:**

```python
cutoff = datetime.datetime.utcnow() - timedelta(hours=48)
# ActivityLog: action like %dunning% or %remind% + target_id in candidate_ids + timestamp >= cutoff
recent_logs = db.query(ActivityLog).filter(ActivityLog.timestamp>=cutoff, ActivityLog.target_id.in_(candidate_ids)).filter(or_(ActivityLog.action.like("%dunning%"), ActivityLog.action.like("%remind%"))).all()
# SmsLog: target_group contains installment_id + date within 48h via Jalali parsing (date = "1405/06/25 14:30")
sms_logs = db.query(SmsLog).filter(or_(*[SmsLog.target_group.contains(str(cid)) for cid in candidate_ids])).all()
for sms in sms_logs:
    d = parse_project_date(sms.date)  # Jalali -> Gregorian
    m = re.search(r"(\d{1,2})[:٫.](\d{2})", sms.date)
    if m:
        sms_dt = datetime.combine(d, time(hh,mm))
        delta = now_dt - sms_dt
        is_recent = 0 <= delta.total_seconds() <= 48*3600
    else:
        is_recent = 0 <= (today - d).days <=2
    if is_recent: recent.add(matched_id)
```

Test: create ActivityLog for overdue within 48h -> drafts excludes it (3 -> 2). Create SmsLog for critical within 48h -> drafts excludes it (2 -> 1). Old log >48h does NOT filter (not tested but logic uses cutoff). Send_batch also checks same recent set and skips with reason "۴۸ ساعت گذشته یادآوری شده".

**GET /dunning/drafts (Admin only):**

```python
@router.get("/dunning/drafts", response_model=List[DunningDraft])
def get_dunning_drafts(..., _: str = Depends(check_admin_access)):
    today = now.date()
    installments = <joinedload query>  # 1 query
    candidates = [(inst, cat, diff) for inst in installments if _categorize(... ) is not None and parent_mobile exists]
    candidates.sort(key=lambda x: x[2])  # critical (-30) -> overdue -> upcoming
    recent_ids = _collect_recent_ids(db, [c.id for c in candidates], today)  # 2 queries (ActivityLog + SmsLog bulk)
    drafts = [DunningDraft(installment_id=inst.id, student_name=f"{first} {last}", parent_mobile=..., amount=int(amt), due_date=..., category=cat, suggested_message=_suggested_message(...)) for inst,cat,diff in candidates if id not in recent_ids]
    return drafts  # sorted by diff ascending (most overdue first)
```

Response field `suggested_message` is per-category template (Persian, amount with comma, due_date, days):
- upcoming: "سلام ولی محترم {name}، یادآوری: قسط ... سررسید {due} (تا {diff} روز آینده) ..."
- overdue: "سلام ولی محترم {name}، قسط ... سررسید {due} ({-diff} روز گذشته) معوق ..."
- critical: "⚠️ هشدار: قسط ... از تاریخ {due} ({-diff} روز گذشته) پرداخت نشده ... - خوارزمی"

**POST /dunning/send_batch (Admin only, Mock SMS):**

```python
@router.post("/dunning/send_batch")
def send_dunning_batch(req: SendBatchRequest, ..., _: str = Depends(check_admin_access)):
    unique_ids = deduplicate(req.installment_ids)  # preserve order
    inst_map = {inst.id: inst for inst in db.query(...joinedload...).filter(Installment.id.in_(unique_ids), is_deleted==False).all()}  # 1 query bulk
    recent_ids = _collect_recent_ids(db, unique_ids, today)
    admin_username = _get_admin_username(db, authorization)
    for iid in unique_ids:
        if iid not in inst_map: skipped (یافت نشد)
        elif inst.is_paid: skipped (پرداخت شده)
        elif not parent_mobile: skipped
        elif iid in recent_ids: skipped (۴۸ ساعت گذشته)
        else:
            category,diff = _categorize(due, today) or ("overdue", -1)
            suggested = _suggested_message(category, student_name, amount, due, diff)
            db.add(SmsLog(target_group=f"dunning_{iid}", message_text=suggested, sent_count=1, date=_jalali_now_str()))
            db.add(ActivityLog(admin_username=admin_username, action="dunning_reminder", target_id=iid, target_name=student_name, details=suggested, timestamp=utcnow()))
            sent_ids.append(iid)
    db.commit()  # atomic for batch
    return {"sent_count": len(sent_ids), "skipped_count": ..., "sent_ids": ..., "skipped_ids": ..., "skipped_reasons": ..., "message": f"{sent} ارسال شد ..."}
```

No auto-send: endpoint only drafts; actual send requires explicit POST with human-selected IDs. Every send logs `ActivityLog(action="dunning_reminder")` to ensure future `GET /drafts` idempotency blocks duplicates within 48h.

**Registration:** `main.py` adds `from routers import ..., dunning` + `app.include_router(dunning.router)` (router defines full paths `/dunning/drafts` and `/dunning/send_batch`, no prefix duplication).

---

## 2. Android - `DunningActivity.kt` + `activity_dunning.xml` + `item_dunning_draft.xml`

**Navigation (Admin-only, mirrored `AuditRadar`):**

- `activity_main.xml`: Added `MaterialCardView` `menu_15_dunning` (grid 3 columns, 15 cards) with `@drawable/ic_menu_send` + text `@string/dunning_nav` (یادآوری اقساط), `app:cardCornerRadius=18dp`. Added to `GridLayout` after `menu_14_audit`.
- `MainActivity.kt`: 
  - Secretary: `nav_dunning` hidden + `menu_15_dunning` GONE
  - Teacher: `nav_dunning` hidden
  - Admin: visible
  - `nav_view.setNavigationItemSelectedListener`: `R.id.nav_dunning -> startActivity(DunningActivity)` with 403 toast if not admin
  - `setupMenuClickListeners`: `menu_15_dunning` click -> DunningActivity (admin check)
  - `showManagementAccordionDialog`: adds `main_menu_dunning` (8th item) -> DunningActivity
  - `animateEntrance`: includes `R.id.menu_15_dunning`
- `drawer_menu.xml`: Added `<item android:id="@+id/nav_dunning" android:title="@string/dunning_nav" android:icon="@android:drawable/ic_menu_send"/>`
- `AndroidManifest.xml`: `<activity android:name=".DunningActivity" android:exported="false" android:label="یادآوری اقساط"/>`

**Strings (`strings.xml`, Persian, no hardcode):**

```xml
<string name="dunning_title">یادآوری اقساط (Dunning)</string>
<string name="dunning_loading">در حال دریافت پیش‌نویس‌ها...</string>
<string name="dunning_empty">هیچ قسط معوق یا سررسید نزدیکی یافت نشد ✓</string>
<string name="dunning_error">خطا در دریافت: %1$s</string>
<string name="dunning_select_all">انتخاب همه</string>
<string name="dunning_deselect_all">لغو انتخاب همه</string>
<string name="dunning_send_selected">ارسال انتخاب‌شده‌ها</string>
<string name="dunning_sending">در حال ارسال...</string>
<string name="dunning_sent_ok">%1$d پیام ارسال شد</string>
<string name="dunning_filter_upcoming">سررسید ۱-۳ روز آینده</string>
<string name="dunning_filter_overdue">معوق ۱-۷ روز</string>
<string name="dunning_filter_critical">بحرانی &gt;۷ روز</string>
<string name="dunning_no_selection">هیچ موردی انتخاب نشده است</string>
<string name="dunning_nav">یادآوری اقساط</string>
<string name="main_menu_dunning">💸 یادآوری اقساط (Dunning)</string>
```

All UI text via `getString()`, no hardcoded literals in `.kt` beyond icons.

**Layout - `activity_dunning.xml` (CoordinatorLayout, RTL):**

```xml
<CoordinatorLayout background="@color/gold_bg_base" layoutDirection="rtl">
  <LinearLayout vertical>
    <AppBarLayout><Toolbar><TextView id="tvDunningTitle" text="@string/dunning_title"/></Toolbar></AppBarLayout>
    <LinearLayout horizontal><MaterialButton id="btnSelectAll" text="@string/dunning_select_all"/><MaterialButton id="btnDeselectAll" text="@string/dunning_deselect_all"/></LinearLayout>
    <LinearLayout horizontal><MaterialButton id="btnDunningRefresh" text="🔄 بروزرسانی"/><MaterialButton id="btnDunningBack" text="@string/action_back"/></LinearLayout>
    <ProgressBar id="progressDunning" visibility="gone"/>
    <TextView id="tvDunningEmpty" text="@string/dunning_loading" visibility="gone"/>
    <MaterialCardView style="@style/Widget.Kharazmi.Card.Gold" weight="1"><RecyclerView id="rvDunningDrafts" padding="8dp"/></MaterialCardView>
  </LinearLayout>
  <ExtendedFloatingActionButton id="fabSend" text="@string/dunning_send_selected" icon="@android:drawable/ic_menu_send" layout_gravity="bottom|center_horizontal" margin="16dp"/>
</CoordinatorLayout>
```

**Item - `item_dunning_draft.xml` (MaterialCardView, strokeWidth 2dp, rtl):**

```xml
<MaterialCardView id="cardDunning" strokeColor="@color/gold_border_subtle">
  <LinearLayout vertical padding="12dp" layoutDirection="rtl">
    <LinearLayout horizontal gravity="center">
      <CheckBox id="cbSelect"/>
      <TextView id="tvStudentName" weight="1" style="SectionTitle" bold/>
      <TextView id="tvAmount" background="@color/gold_bg_subtle" textColor="@color/gold_primary" padding 8dp/>
    </LinearLayout>
    <LinearLayout horizontal marginTop="8dp">
      <TextView id="tvCategory" padding 8dp|4dp textColor="white" bold/> <!-- blue/orange/red per category -->
      <TextView id="tvDueDate" marginStart="8dp" text="سررسید: 1405/06/15" secondary/>
      <TextView id="tvParentMobile" weight="1" gravity="end" text="📱 0912..." tnum/>
    </LinearLayout>
    <View 0.5dp background="@color/gold_border_subtle"/>
    <TextView id="tvSmsPreview" marginTop="8dp" background="@color/gold_bg_subtle" padding="8dp" lineSpacing 4dp/> <!-- suggested_message -->
  </LinearLayout>
</MaterialCardView>
```

**Activity - `DunningActivity.kt` (155 lines, checklist + FAB + progress/toast/refresh):**

```kotlin
class DunningActivity : BaseActivity() {
  private lateinit var api: DunningApi
  private var drafts: List<DunningDraft> = emptyList()
  private val selectedIds = mutableSetOf<Int>()

  // initViews: rv.layoutManager = LinearLayoutManager, fab, btns, title
  // loadDrafts(): 
  //   tvEmpty.visible + "در حال دریافت..." + rv.gone + progress.visible + fab.disabled
  //   lifecycleScope.launch(IO) { api.getDrafts() } -> Main: if empty -> tv "هیچ قسطی یافت نشد ✓" else adapter = DunningAdapter(list)
  //   catches HttpException 403/401 + generic, shows toast + tv error via getString(R.string.dunning_error, msg)
  // SelectAll: selectedIds.addAll(drafts.map{installmentId}); adapter.notifyDataSetChanged(); updateFabCount()
  // DeselectAll: clear + notify
  // fabSend.onClick: if selectedIds.empty toast "هیچ موردی انتخاب نشده" else sendSelected()
  // sendSelected():
  //   setLoading(true) + tv "در حال ارسال..." visible
  //   launch(IO) { api.sendBatch(DunningSendRequest(selectedIds.toList())) } -> Main: toast "X پیام ارسال شد" + loadDrafts() (refresh, sent items disappear)
  //   on error: HttpException detail parsing via JSONObject optString, 403/401 handling
  // Adapter: VH with Card, CheckBox, tvStudentName, tvAmount, tvCategory, tvDueDate, tvParentMobile, tvSmsPreview
  //   onBind: tvStudentName, tvAmount = format("%,d تومان"), tvDueDate, tvParentMobile, tvSmsPreview
  //   category -> (label, bg, stroke): upcoming blue #2196F3, overdue orange #FF9800, critical red #F44336
  //   statusText = "🔵 سررسید 1-3 روز" / "⚠️ معوق 1-7 روز" / "🔴 بحرانی >7 روز"
  //   card.strokeColor = stroke; tvCategory background = bg
  //   cb.isChecked = selectedIds.contains(id); cb.setOnCheckedChangeListener { if checked add else remove; updateFabCount() }
  //   card.setOnClickListener { cb.isChecked = !cb.isChecked } // row tap toggles
}
```

**Models & API (`AppModels.kt` + `ApiInterfaces.kt`):**

```kotlin
data class DunningDraft(@SerializedName("installment_id") val installmentId: Int, @SerializedName("student_name") val studentName: String, @SerializedName("parent_mobile") val parentMobile: String, val amount: Long, @SerializedName("due_date") val dueDate: String, val category: String, @SerializedName("suggested_message") val suggestedMessage: String)
data class DunningSendRequest(@SerializedName("installment_ids") val installmentIds: List<Int>)
data class DunningSendResponse(@SerializedName("sent_count") val sentCount: Int, @SerializedName("skipped_count") val skippedCount: Int, @SerializedName("sent_ids") val sentIds: List<Int>, @SerializedName("skipped_ids") val skippedIds: List<Int>, val message: String, @SerializedName("skipped_reasons") val skippedReasons: Map<String,String>? = null)
interface DunningApi { @GET("dunning/drafts") suspend fun getDrafts(): List<DunningDraft>; @POST("dunning/send_batch") suspend fun sendBatch(@Body req: DunningSendRequest): DunningSendResponse }
```

Retrofit via `RetrofitClient.getInstance(this).create(DunningApi::class.java)` - same auth interceptor as others (Bearer token).

---

## 3. Sample JSON (3 categories, as returned by GET /dunning/drafts - tested via TestClient in /tmp/dunning_test.db)

```json
[
  {
    "installment_id": 3,
    "student_name": "علی احمدی",
    "parent_mobile": "09121112222",
    "amount": 250000,
    "due_date": "1405/06/15",
    "category": "critical",
    "suggested_message": "⚠️ هشدار: قسط شهریه فرزند شما علی احمدی به مبلغ 250,000 تومان از تاریخ 1405/06/15 (10 روز گذشته) پرداخت نشده است. جهت جلوگیری از محدودیت ثبت‌نام، سریعاً اقدام فرمایید. - آموزشگاه خوارزمی"
  },
  {
    "installment_id": 2,
    "student_name": "علی احمدی",
    "parent_mobile": "09121112222",
    "amount": 250000,
    "due_date": "1405/06/23",
    "category": "overdue",
    "suggested_message": "سلام ولی محترم علی احمدی، قسط شهریه فرزند شما به مبلغ 250,000 تومان سررسید 1405/06/23 (2 روز گذشته) معوق شده است. لطفاً در اسرع وقت پرداخت فرمایید. - خوارزمی"
  },
  {
    "installment_id": 1,
    "student_name": "علی احمدی",
    "parent_mobile": "09121112222",
    "amount": 250000,
    "due_date": "1405/06/27",
    "category": "upcoming",
    "suggested_message": "سلام ولی محترم علی احمدی، یادآوری: قسط شهریه فرزند شما به مبلغ 250,000 تومان سررسید 1405/06/27 (تا 2 روز آینده) می‌باشد. لطفاً نسبت به پرداخت اقدام فرمایید. با تشکر - آموزشگاه خوارزمی"
  }
]
```

Real test output (seeded in /tmp/dunning_test.db, today 2026-09-16): 3 drafts sorted critical->overdue->upcoming. `far_future` (1405/07/04 +10) and `today` (1405/06/25 0) correctly excluded (not in bucket). After adding `ActivityLog(dunning_reminder, overdue)` within 48h -> drafts 2 (critical+upcoming). After `SmsLog(dunning_3)` -> drafts 1 (upcoming). After `POST /dunning/send_batch [1]` -> 1 sent, ActivityLog+SmsLog created, drafts 0. Second POST same id -> 0 sent, 1 skipped reason "۴۸ ساعت گذشته یادآوری شده". Secretary token -> 403.

---

## 4. Verification

```bash
python3 -m py_compile Kharazmi_Server/routers/dunning.py  # OK
python3 -c "import ast; ast.parse(open('Kharazmi_Server/routers/dunning.py').read())" # OK
python3 -m py_compile Kharazmi_Server/main.py # OK
python3 -m py_compile Kharazmi_Server/models.py # OK (no change)
git diff HEAD -- Kharazmi_Server/routers/finance.py  # empty
sha256sum Kharazmi_Server/routers/finance.py # fca8c7aff4037cc21e3c8dc1e6b9ad765c7a697c04d3092a71118fb28f0e1d53
git show HEAD:Kharazmi_Server/routers/finance.py | sha256sum # same -> confirmation unchanged
git diff HEAD -- Kharazmi_Server/routers/timeline.py # empty (no diff)
git status --short
# M 8 files (main.py, strings.xml, AppModels.kt, ApiInterfaces.kt, MainActivity.kt, activity_main.xml, drawer_menu.xml, AndroidManifest.xml)
# ?? 4 new (routers/dunning.py, DunningActivity.kt, activity_dunning.xml, item_dunning_draft.xml)
# N+1 proof:
grep -n "joinedload" Kharazmi_Server/routers/dunning.py # 4 occurrences (Installment.enrollment.student + course for both drafts and send_batch)
grep -n "check_admin_access" Kharazmi_Server/routers/dunning.py # 2 (both endpoints)
grep -n "dunning_reminder" Kharazmi_Server/routers/dunning.py # 2 (send + idempotency)
# Test via TestClient (DATABASE_URL=sqlite:////tmp/dunning_test.db):
# - admin GET /dunning/drafts -> 200 3 items (critical/overdue/upcoming)
# - secretary GET -> 403
# - ActivityLog filter -> 2, SmsLog filter ->1, send_batch 1->0, second send 0/1 skipped
# - total SQL: 3 queries per drafts (no N+1)
```

**Isolation:** `git diff --name-only HEAD` shows only `main.py` (1 line import + 1 include), Android files, plus 4 new files. No `finance.py`/`timeline.py`/`audit.py` diff.

**Performance:** Drafts uses 1 main query + 2 bulk idempotency queries (ActivityLog + SmsLog). No per-installment queries. Python categorize + sort is O(N log N) where N = unpaid installments (typically <100). Tested with 5 installments -> 3 drafts in <50ms.

---

## 5. Files Changed (git diff --stat after add)

```
KharazmiAdmin/app/src/main/AndroidManifest.xml                        |  4 +++
KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ApiInterfaces.kt | 11 ++++++
KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/AppModels.kt | 26 +++++++++++++++
KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/DunningActivity.kt | 155 +++++ (new)
KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/MainActivity.kt | 27 ++++++++
KharazmiAdmin/app/src/main/res/layout/activity_dunning.xml             | 90 +++++ (new)
KharazmiAdmin/app/src/main/res/layout/activity_main.xml                | 39 +++++++++
KharazmiAdmin/app/src/main/res/layout/item_dunning_draft.xml           | 85 +++++ (new)
KharazmiAdmin/app/src/main/res/menu/drawer_menu.xml                    |  5 +++
KharazmiAdmin/app/src/main/res/values/strings.xml                      | 16 +++++++
Kharazmi_Server/main.py                                                  |  3 +-
Kharazmi_Server/routers/dunning.py                                       | 324 +++++ (new)
```

**Commit:** Push to `arena/01a0a936-kharazmiapp` only, after verification.

---

## 6. Design Rationale

- **Human-in-the-Loop (NO Auto-Send):** `GET /dunning/drafts` is read-only, returns preview messages. Actual SMS `SmsLog` + `ActivityLog` only created by `POST /dunning/send_batch` with explicit `installment_ids`. No background worker auto-sends. Mirrors `finance.py:remind` manual route (Admin+Secretary) but with bulk + 48h guard. Prevents accidental bulk spam.
- **3 Buckets via Central Jalali Converter:** `parse_project_date` handles both Jalali (1405/06/15) and Gregorian (2026-09-06) legacy data, ensures correct diff regardless of stored format. Categories fixed: upcoming (1-3 future) for gentle reminder, overdue (1-7 past) for urgent, critical (>7) for warning. Far-future >3 and today (0) excluded to reduce noise and avoid duplicate with `main.py` daily auto-SMS (which sends for `due <= today`). Sort by diff ascending (critical oldest first) surfaces most urgent at top.
- **48h Idempotency via Dual Source:** `ActivityLog(action like %dunning%/%remind%)` is authoritative for Dunning sends, but `SmsLog(target_group contains id)` also checked because manual `finance.py:remind` and `main.py` auto-SMS create SmsLog without ActivityLog. Dual check prevents double-sending even if one source was used. Cutoff uses `utcnow -48h` for ActivityLog (UTC) and Jalali date + time delta for SmsLog (which stores Jalali string). Bulk OR query for SmsLog avoids N+1.
- **N+1 via joinedload:** Installment -> Enrollment -> Student/Course. Without joinedload, loop accessing `inst.enrollment.student.parent_mobile` would fire 1 query per installment (N). With `joinedload(...).joinedload(...)` in single JOIN, all needed fields loaded in 1 query. `Enrollment.is_deleted` and `Student.is_deleted` filters exclude archived enrollments.
- **Security Admin-only:** `check_admin_access` (not `check_admin_or_secretary_access`) because bulk SMS is high-risk (spam + cost). Secretary can use single `finance.py:remind` for individual, but bulk requires admin. Verified 403 for secretary.
- **Android Checklist UX:** `CheckBox` per row + `Select All/Deselect All` material buttons + `ExtendedFloatingActionButton` send (shows count). Row tap toggles checkbox (large hit area). Category badge color-coded (blue/orange/red) for quick scanning. `tvSmsPreview` shows exact server `suggested_message` so admin sees final text before send. Progress `ProgressBar` + `tvEmpty` "در حال ارسال..." + `fab.isEnabled=false` during network. Toast on success/failure with server `detail` parsing (same as A1 installments). `loadDrafts()` refresh after send makes sent items disappear (idempotency proof).
- **Mock SMS:** Creates `SmsLog(target_group="dunning_{id}", sent_count=1)` - same table as real SMS provider, so history and 48h check unify. `ActivityLog(action="dunning_reminder")` also blocks future drafts. Real provider can replace `SmsLog` insert with actual gateway call without changing API.

