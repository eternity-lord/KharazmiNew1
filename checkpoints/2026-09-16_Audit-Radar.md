# Audit Radar — Fraud Detection System — 2026-09-16

**Branch:** `arena/01a0a936-kharazmiapp` — https://github.com/eternity-lord/KharazmiApp/tree/arena/01a0a936-kharazmiapp  
**Source:** Task Audit Radar (Isolated Read-Only Fraud Detection) — 2026-09-16 Tehran (Asia/Tehran)  
**Constraints CRITICAL:** Isolation + No Regression + Admin-only + Read-Only  
- `routers/finance.py`, `routers/classes.py`, `routers/students.py`, `routers/auth.py` **must NOT be modified**  
- All logic in new `routers/audit.py` with `Depends(check_admin_access)` (403 for teacher/secretary, 401 without token)  
- Read-only: no wallet/balance/data mutation, only SELECT and alert generation  

---

## 1) Summary

| Layer | Before | After |
|-------|--------|-------|
| **Backend** | No audit capability | `GET /audit/suspicious_patterns` → List[AuditAlert] read-only, 3 independent patterns |
| **Android** | No audit UI | `AuditDashboardActivity` + RecyclerView color-coded (high=red, medium=orange) + Refresh, admin-only entry points |
| **Security** | — | All audit endpoints gated by `check_admin_access`; audit logic in try/except per pattern, never fails whole endpoint |
| **Tests** | No audit tests | `test_audit.py` 7 tests: 403 non-admin, 200 admin, 3 pattern mocks, read-only wallets |

---

## 2) Changed Files (New + Modified)

| Path | Change | Rationale |
|------|--------|-----------|
| `Kharazmi_Server/routers/audit.py` | **NEW** 224 lines: `AuditAlert(BaseModel)` + `_parse_hour/_now_str` + `APIRouter()` + `GET /suspicious_patterns` | Isolation: single file, no import of finance/classes/students. `_parse_hour` handles `HH:MM`, range `08:00-10:00`, Persian digits. `_now_str` for `detected_at`. |
| `Kharazmi_Server/main.py` | 2 lines: `from routers import ..., audit` + `app.include_router(audit.router, prefix="/audit")` (636-637) | Registration: `APIRouter()` has no prefix → final `/audit/suspicious_patterns` (avoid double prefix). |
| `Kharazmi_Server/test_audit.py` | **NEW** 7 tests | Covers 403/401/200 + 3 pattern mocks + read-only wallet check, in-memory SQLite + `TestClient` + `dependency_overrides[get_db]` |
| `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/AppModels.kt` | +13 lines `data class AuditAlert(type,severity,title,description,entityId,entityName,detectedAt)` with `@SerializedName` | Mirror backend `AuditAlert` exactly; retrofit parsing requires same keys snake_case → camel. |
| `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ApiInterfaces.kt` | +8 lines `interface AuditApi { @GET("audit/suspicious_patterns") }` | Relative path without leading slash (same as other APIs like `admin/...`), admin token via `Authorization: Bearer` header already handled by `RetrofitClient` interceptor. |
| `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/AuditDashboardActivity.kt` | **NEW** `BaseActivity` + `lifecycleScope(Dispatchers.IO)` + `RecyclerView LinearLayoutManager` + color-code high/medium/low + `HttpException` 403/401 handling + empty state | Pattern from `NotificationCenterActivity` (Retrofit + coroutine) but minimal — no wallet logic, offline not needed. |
| `KharazmiAdmin/app/src/main/res/layout/activity_audit_dashboard.xml` | **NEW** AppBar + 2 `MaterialButton` (refresh/back) + `tvEmpty` + `RecyclerView` in `MaterialCardView` | Uses existing `Widget.Kharazmi.Card.Gold` + `Gold.*` colors; RTL `layoutDirection="rtl"` consistent. |
| `KharazmiAdmin/app/src/main/res/layout/item_audit_alert.xml` | **NEW** `MaterialCardView` + `tvType/tvSeverity/tvTitle/tvDesc/tvEntity/tvDetected` with `strokeWidth 2dp` | Severity badge + card stroke color updated per `severity` (high=red `#FFEBEE/#D32F2F`, medium=orange `#FFF3E0/#FF6F00`, low=green). No `@drawable/bg_badge_high` to avoid build failure (fixed to `@android:color/transparent`). |
| `KharazmiAdmin/app/src/main/res/menu/drawer_menu.xml` | +5 lines `<item android:id="@+id/nav_audit_radar" title="@string/nav_audit_radar">` | Drawer entry admin-only; hidden for `secretary`/`teacher` in `MainActivity.onCreate`. |
| `KharazmiAdmin/app/src/main/res/values/strings.xml` | +2 lines `main_menu_audit_radar` + `nav_audit_radar` | Persian strings via `strings.xml`, no hardcoded UI text. |
| `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/MainActivity.kt` | +36 lines: hide `nav_audit_radar` for secretary/teacher, ensure visible for admin, `setNavigationItemSelectedListener` add `nav_audit_radar` case with role check, `showManagementAccordionDialog` add option 8, `setupMenuClickListeners` add `menu_14_audit` visibility+click, `animateEntrance` include 2 new ids | Admin-only navigation triple: drawer + dialog + grid card `menu_14_audit`. `secretary` → `GONE`, `admin` → `VISIBLE`. Prevents teacher bypass. |
| `KharazmiAdmin/app/src/main/res/layout/activity_main.xml` | +39 lines `menu_14_audit` `MaterialCardView` with `ic_menu_search` @ `status_warning` | GridLayout `columnCount=3` already supports extra card (wraps to next row). Text `@string/nav_audit_radar` via strings.xml. |
| `KharazmiAdmin/app/src/main/AndroidManifest.xml` | +4 lines `<activity android:name=".AuditDashboardActivity">` | Registration required for `startActivity`. |
| `checkpoints/2026-09-16_Audit-Radar.md` | NEW | This checkpoint |

**UNTOUCHED (verified via `git diff --name-only`):** `routers/finance.py`, `routers/classes.py`, `routers/students.py`, `routers/auth.py`

```bash
git diff --name-only  # tracked modified
# KharazmiAdmin/app/src/main/AndroidManifest.xml
# KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ApiInterfaces.kt
# KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/AppModels.kt
# KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/MainActivity.kt
# KharazmiAdmin/app/src/main/res/layout/activity_main.xml
# KharazmiAdmin/app/src/main/res/menu/drawer_menu.xml
# KharazmiAdmin/app/src/main/res/values/strings.xml
# Kharazmi_Server/main.py
# (plus 5 untracked NEW files: AuditDashboardActivity.kt, activity_audit_dashboard.xml, item_audit_alert.xml, routers/audit.py, test_audit.py)

git diff --stat  # tracked
#  8 files changed, 107 insertions(+), 3 deletions(-)
```

---

## 3) Design Rationale

### 3.1 Why Isolated `routers/audit.py` + `APIRouter()` without prefix?

- **No regression risk:** Touching `finance.py`/`classes.py` could break 275 existing tests (especially `transaction` idempotency, `check_admin_access` assumptions). A new file guarantees zero side-effects; `git diff --name-only` proves isolation.
- **Double-prefix guard:** `main.py` already prefixes `include_router(..., prefix="/audit")`. If `audit.py` also declared `APIRouter(prefix="/audit")` final path would be `/audit/audit/suspicious_patterns` (404). Tests hitting `/audit/suspicious_patterns` validated single prefix is correct.
- **Alternative rejected:** Adding audit logic into `finance.py` as helper functions — rejected because finance is high-risk (wallet, idempotency, settlement).

### 3.2 Why `check_admin_access` (not `check_admin_or_secretary_access` or `check_user_login`)?

- **Requirement:** "All endpoints with `check_admin_access` (Admin only)". This is the strictest guard (checks `sub_role=="admin"`). `secretary` gets 403 (verified in `test_403_non_admin`). `teacher`/`parent`/`student` also 403. No token → 401 (same dependencies helper as other admin routes like `InstituteSettings`).
- **Security audit compliance:** `test_security_audit.py` whitelists only 12 public routes; every other route must have explicit dependency. Audit endpoint passes that audit (dependency inspected via `Depends` param).

### 3.3 Why 3 Independent try/except Blocks + `_parse_hour` Robustness?

- **Fault isolation:** Pattern A/B/C each wrapped in `try: ... except: pass`. If one pattern's query fails (e.g., missing column on older DB), others still return alerts. The endpoint never 500 due to audit logic.
- **Time parsing edge:** `SessionLog.time` can be `"16:00"`, `"08:00-10:00"`, `"۳۰ ۱۶:۰۰"` Persian, empty, or `None`. `_parse_hour` normalizes Persian/Arabic digits, extracts first token before `-`, ignores missing `:`, returns `None` safely. Delayed check only runs if both `course_hour` and `session_hour` parsed successfully — no false positives on malformed data.

### 3.4 Why Pattern B Assumes All `is_deleted=True` Are Rapid?

- **Schema limitation:** `Transaction` has `date` string (yyyy/MM/dd) but no `created_at`/`deleted_at` timestamps, no `ActivityLog` FK reliably linking deletions. Computing real time diff impossible without schema change (which would touch `models.py` and risk migration). Requirement says "Transaction is_deleted=True and diff creation-deletion <1h (fallback assumption)". Conservative fallback: mark all soft-deleted as `high` with description explaining fallback (auditor can refine later when `deleted_at` column added). Read-only — never updates `Transaction`.

### 3.5 Why Pattern C Checks `absent_count==0` + `total_att>0` + `len(last_sessions)==10`?

- **Avoid empty-course false positives:** Courses with no attendance data (new courses) would have `absent_count==0` trivially. `total_att>0` ensures at least some `Present` records exist.
- **Threshold 10:** Spec says "10 session last 0 absence had". We order `SessionLog.id desc limit 10` (most recent). If course has <10 sessions, skip — not enough evidence for "perfect attendance" collusion.
- **Status strict `"Absent"`:** Attendance statuses are `"Present"/"Absent"/"Late"` — we check strict `Absent` not `Late`/`Excused`. Medium severity (not high) because it could be genuinely good class.

### 3.6 Android: Why 3 Entry Points (Drawer + Dialog + Grid Card) All Role-Gated?

- **Coverage of "Admin Main Menu":** Spec: "Add a button to open this activity ONLY in the Admin Main Menu (not accessible to secretary/teacher)". `MainActivity`'s main menu is ambiguous — it includes both the 3-column grid and the accordion dialog from "بخش مدیریت". We covered all: `drawer_menu` (nav_view), `showManagementAccordionDialog` (option 8), and `menu_14_audit` grid card. Each checks `sub_role=="admin"` before `startActivity`; otherwise `common_no_access` toast + `GONE`. Ensures secretary/teacher cannot navigate even via deep-link attempt within app.
- **Grid card visibility `GONE` vs `INVISIBLE`:** `GONE` removes from GridLayout flow (no blank gap), `INVISIBLE` would leave placeholder. For secretary we use `GONE`.

### 3.7 Why `HttpException` Handling in `AuditDashboardActivity` Mirrors `NotificationCenter`?

- **Consistency:** `NotificationCenterActivity` already handles 401 (session expired dialog) and 403 via `RetrofitClient`. `AuditDashboardActivity` reuses same `lifecycleScope(Dispatchers.IO)` + `withContext(Dispatchers.Main)` pattern, plus `try/catch HttpException` branch to show `common_restricted` for 403. No custom auth logic needed.
- **Refresh button:** Requirement asks for `Refresh button` on layout — implemented as top `MaterialButton` alongside `Back`; both use `Widget.Kharazmi.Button.Gold.Outline` consistent with app style.

---

## 4) Key Code Excerpts

### 4.1 `routers/audit.py` (core)

```python
class AuditAlert(BaseModel):
    type: str
    severity: str  # high/medium/low
    title: str
    description: str
    entity_id: int
    entity_name: str
    detected_at: str

router = APIRouter()

@router.get("/suspicious_patterns", response_model=List[AuditAlert])
def get_suspicious_patterns(db: Session = Depends(get_db), _: str = Depends(check_admin_access)):
    alerts: List[AuditAlert] = []
    now_str = _now_str()
    # Pattern A: SessionLog.time 00-05 or delayed >5h after Course.class_time → high
    # Pattern B: Transaction is_deleted=True (assume rapid) → high
    # Pattern C: Course last 10 sessions absent==0 and total>0 → medium
    return alerts
```

### 4.2 `main.py` registration

```python
from routers import admin, classes, enrollment, finance, reports, settings, students, teachers, auth, audit
...
app.include_router(audit.router, prefix="/audit")
```

### 4.3 `AuditDashboardActivity.kt` (skeleton)

```kotlin
class AuditDashboardActivity : BaseActivity() {
    private lateinit var rvAlerts: RecyclerView
    private lateinit var tvEmpty: TextView
    private val adapter = AuditAdapter(emptyList())
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_audit_dashboard)
        rvAlerts = findViewById(R.id.rvAlerts); tvEmpty = findViewById(R.id.tvEmpty)
        rvAlerts.layoutManager = LinearLayoutManager(this); rvAlerts.adapter = adapter
        findViewById<View>(R.id.btnRefresh).setOnClickListener { fetchAlerts() }
        findViewById<View>(R.id.btnBack).setOnClickListener { finish() }
        fetchAlerts()
    }
    private fun fetchAlerts() {
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val api = RetrofitClient.getInstance(this@AuditDashboardActivity).create(AuditApi::class.java)
                val list = api.getSuspiciousPatterns()
                withContext(Dispatchers.Main) { adapter.update(list); tvEmpty.visibility = if(list.isEmpty()) View.VISIBLE else View.GONE }
            } catch (e: HttpException) { // 403/401 → Toast common_no_access
            } catch (e: Exception) { /* CancellationException rethrow */ }
        }
    }
}
```

---

## 5) Testing

### 5.1 `test_audit.py` — 7 tests (in-memory SQLite + TestClient)

| Test | Header | Expected | Pattern Mock |
|------|--------|----------|--------------|
| `test_403_non_admin_cannot_access_audit` | `tok_secretary` / `tok_teacher` / none | 403 / 403 / 401 | — |
| `test_200_admin_can_access_empty` | `tok_admin` | 200 list | — |
| `test_pattern_A_suspicious_attendance_night` | `tok_admin` | contains `suspicious_attendance` high with `"02:30"` in description | `SessionLog(time="02:30")` |
| `test_pattern_A_delayed_after_class_time` | `tok_admin` | `suspicious_attendance` with delay `اختلاف 7 ساعت` | `Course.class_time="16:00"` + `SessionLog(time="23:00")` diff 7 >5 |
| `test_pattern_B_rapid_deletion` | `tok_admin` | `rapid_deletion` high, wallet counts unchanged | `Transaction(is_deleted=True)` |
| `test_pattern_C_perfect_attendance` | `tok_admin` | `perfect_attendance` medium contains `"10"` + `"غیبت"` | 10 `SessionLog` + 10 `Attendance(Present)` |
| `test_read_only_wallet_not_modified` | `tok_admin` | wallets `wallet_teacher/institute/balance` unchanged after GET | mixed A+B data |

```bash
DATABASE_URL="sqlite:///:memory:" JWT_SECRET_KEY="test_secret..." python3 -m pytest Kharazmi_Server/test_audit.py -v
# 7 passed
```

### 5.2 Full suite on tmp copy (no prod mutation)

```bash
cp Kharazmi_Server/gaj_db.db /tmp/bugfix_test.db
DATABASE_URL="sqlite:////tmp/bugfix_test.db" JWT_SECRET_KEY="..." python3 -m pytest Kharazmi_Server/ -q
# 275 passed (268 existing + 7 audit) — confirms no regression
sha256sum Kharazmi_Server/gaj_db.db
# f0e55fe7c5130ec17e39e73036e2291794c3c335f67d852c37599a6c0f99ec79 (unchanged before/after)
```

### 5.3 Static checks

```bash
python3 -c "import ast; ast.parse(open('Kharazmi_Server/routers/audit.py').read())"  # OK
python3 -c "import ast; ast.parse(open('Kharazmi_Server/main.py').read())"        # OK
python3 -c "import ast; ast.parse(open('Kharazmi_Server/test_audit.py').read())"  # OK
python3 -m py_compile Kharazmi_Server/routers/audit.py  # OK
ET.parse(activity_audit_dashboard.xml)  # XML OK (all 6 XMLs OK)
```

---

## 6) Verification: No Regression & Isolation

```bash
# Confirm only intended files changed (tracked)
git diff --name-only
# KharazmiAdmin/app/src/main/AndroidManifest.xml
# KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ApiInterfaces.kt
# KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/AppModels.kt
# KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/MainActivity.kt
# KharazmiAdmin/app/src/main/res/layout/activity_main.xml
# KharazmiAdmin/app/src/main/res/menu/drawer_menu.xml
# KharazmiAdmin/app/src/main/res/values/strings.xml
# Kharazmi_Server/main.py
# New untracked: AuditDashboardActivity.kt, activity_audit_dashboard.xml, item_audit_alert.xml, routers/audit.py, test_audit.py
# Explicitly NOT in diff: routers/finance.py, routers/classes.py, routers/students.py, routers/auth.py
```

---

## 7) Deliverables Checklist

- [x] New files: `routers/audit.py`, `test_audit.py`, `AuditDashboardActivity.kt`, `activity_audit_dashboard.xml`, `item_audit_alert.xml`
- [x] Confirmation: `finance.py`/`classes.py`/`students.py`/`auth.py` untouched
- [x] Code for `routers/audit.py` and `AuditDashboardActivity.kt` included above (full files in workspace)
- [x] Router registered in `main.py` with `prefix="/audit"`
- [x] Android `AuditAlert` in `AppModels.kt`, `AuditApi` in `ApiInterfaces.kt`, navigation admin-only (drawer+dialog+grid)
- [x] Tests: 403 teacher/secretary, 200 admin, mock 3 patterns, read-only wallet check
- [x] All 275 tests passed on `/tmp` copy, prod hash unchanged
- [x] XML valid, py_compile OK, no Gradle build attempted (per A1 static-only rule)

---

**Next:** `git add` only changed + checkpoint → commit → push `arena/01a0a936-kharazmiapp` → verify `gh api branches` SHA matches.

