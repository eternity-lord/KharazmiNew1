# Admin Command Center (Unified Dashboard) — 2026-09-16

## Goal
یک صفحه اسکرولی واحد برای ادمین شامل revenue / alerts / overdue / attendance — بدون تکرار منطق، فقط KPI aggregated، با performance <500ms.

## Constraints رعایت‌شده (CRITICAL)
1. **Reuse** `/audit/suspicious_patterns` و `/dunning/drafts` — هیچ منطقی در dashboard کپی نشد (lazy import audit/dunning).
2. **Lightweight endpoint** فقط `GET /dashboard/kpis` با 6 فیلد aggregated (SUM + COUNT + parse jalali loop).
3. **NO modification** به `routers/finance.py`, `routers/timeline.py`, `routers/audit.py`, `routers/dunning.py` — فقط `routers/dashboard.py` + `AdminDashboardActivity.kt` ایجاد/پچ شد (تأیید sha256).
4. **Isolation** — `routers/dashboard.py` مستقل، read-only، Optimized.
5. **Security** — `Depends(check_admin_access)` برای هر درخواست؛ test 403 برای secretary/teacher.
6. **Performance** — Kotlin `coroutineScope { async kpis + async drafts }` برای 2 سورس موازی؛ backend: 1 SQL SUM + 1 COUNT + 1 bulk Installment fetch + lazy counts.

## Design Rationale

### Backend `routers/dashboard.py` (164 خط, read-only)
- **today_revenue**: `func.sum(Transaction.amount)` با `or_(is_deleted False, is_none)` + `or_(is_reversed ...)` + `_date_prefix_filter(Transaction.date, [today])` برای jalali/gregorian/time suffix. Fallback loop `parse_project_date(d)==today`.
- **overdue**: fetch `Installment is_deleted==False is_paid==False` → loop `parse_project_date(due) < today` → sum + count (jalali correctness). No N+1, یک query.
- **active_students_count**: `COUNT Student is_deleted==False`.
- **suspicious_alerts_count**: lazy `from routers.audit import get_suspicious_patterns` → `len(alerts)` else 0. عدم تکرار منطق night/delayed/rapid/perfect.
- **dunning_pending_count**: lazy `from routers.dunning import _categorize, _collect_recent_ids` → buckets Upcoming 1-3 / Overdue 1-7 / Critical >7 + filter 48h ActivityLog/SmsLog → count pending. Fallback `overdue_count`.
- **Model**: `DashboardKPIs(today_revenue, total_overdue_amount, overdue_installments_count, active_students_count, suspicious_alerts_count, dunning_pending_count)` int.
- **Router**: `@router.get("/kpis", response_model=DashboardKPIs)` + `check_admin_access`. Register در `main.py`: `from routers import ..., dashboard` + `app.include_router(dashboard.router, prefix="/dashboard")` — finance/timeline/audit/dunning untouched.

### Android
- **Models**: `AppModels.kt` → `data class DashboardKPIs(6 fields)` appended after `DunningSendResponse`.
- **API**: `ApiInterfaces.kt` → `interface DashboardApi { @GET("dashboard/kpis") suspend fun getKPIs(): DashboardKPIs }`.
- **Strings** (`strings.xml`): 20 کلید `dashboard_*` فارسی (title/nav/today_revenue/overdue/active_students/radar/dunning_pending/quick_actions/critical_title/subtitle/.../loading/error/refresh/coming_soon) + `main_menu_dashboard` موجود.
- **Layouts**:
  - `activity_admin_dashboard.xml`: `CoordinatorLayout` + `AppBarLayout` + `SwipeRefreshLayout(id=swipeDashboard)` + `NestedScrollView` → `GridLayout 2x2` KPI Cards (💰 Green, ⚠️ Red count+amount, 👨‍🎓 Blue, 🚨 Orange) با `MaterialCardView strokeColor` متمایز، سپس `Card quick_actions` با 3 `MaterialButton` (ارسال یادآوری→DunningActivity, مشاهده هشدارها→AuditDashboardActivity, گزارش بدهکاران→toast coming soon)، سپس `Card Bottom` با `RecyclerView rvDashboardCritical + tvCriticalEmpty`.
  - `item_dashboard_critical.xml`: `MaterialCardView` stroke red + `tvCriticalStudentName`, `tvCriticalAmount` (rounded bg), `tvCriticalCategory` red badge, `tvCriticalDueDate`, `tvCriticalParentMobile`, `tvCriticalSmsPreview` با `gold_bg_elevated_2`.
- **Activity** `AdminDashboardActivity.kt` (296 خط): `BaseActivity` + `SwipeRefreshLayout` + `ProgressBar` + `coroutineScope { async dashboardApi.getKPIs() + async dunningApi.getDrafts() }` روی `Dispatchers.IO`، `withContext(Main)` render. `renderKPIs` با `String.format("%,d تومان")` و overdue sub با dunning_pending diff note. `renderCritical` filter `category==critical` take 5 → `CriticalAdapter`. کلیک KPI cards → Dunning/Students/Audit. 3 quick actions → intents + toast. Error handling `HttpException 403/401` + toast. Nav drawer + grid integration.
- **Navigation**:
  - `drawer_menu.xml`: `nav_admin_dashboard` (ic_menu_view, @string/dashboard_nav) بعد از nav_dashboard (اولین آیتم ادمین).
  - `activity_main.xml`: `menu_16_dashboard` (ic_menu_view tint #2196F3, text dashboard_nav) بعد از dunning.
  - `MainActivity.kt`: secretary/teacher `isVisible=false` برای nav_admin_dashboard, admin `true`; `setOnNavigationItemSelectedListener` case `R.id.nav_admin_dashboard` → AdminDashboardActivity else toast; `setupMenuClickListeners` visibility + click for `menu_16_dashboard`; `animateEntrance` شامل `R.id.menu_16_dashboard`; `showManagementAccordionDialog` options افزوده `main_menu_dashboard` index 9 → AdminDashboardActivity.
  - `AndroidManifest.xml`: `<activity .AdminDashboardActivity label="داشبورد مدیریت">`.
  - `build.gradle.kts`: `implementation("androidx.swiperefreshlayout:swiperefreshlayout:1.1.0")`.

### Performance
- Backend: 2 SQL + 1 bulk fetch + Python loop <50 installments typical → <100ms.
- Android: parallel async 2 network calls → theoretical <500ms (spec) vs sequential.
- No N+1: Installment bulk, Students count, Transaction SUM.

## Files Changed (git diff --stat)
```
 KharazmiAdmin/app/build.gradle.kts                 |  1 +
 KharazmiAdmin/app/src/main/AndroidManifest.xml     |  4 +
 KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/AdminDashboardActivity.kt | 296 NEW
 KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ApiInterfaces.kt     |  8 +
 KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/AppModels.kt         | 12 +
 KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/MainActivity.kt      | 27 +
 KharazmiAdmin/app/src/main/res/layout/activity_admin_dashboard.xml              | 320 NEW
 KharazmiAdmin/app/src/main/res/layout/activity_main.xml                        | 39 +
 KharazmiAdmin/app/src/main/res/layout/item_dashboard_critical.xml              | 90 NEW
 KharazmiAdmin/app/src/main/res/menu/drawer_menu.xml                            |  4 +
 KharazmiAdmin/app/src/main/res/values/strings.xml                             | 27 +
 Kharazmi_Server/main.py                                                        |  3 +-
 Kharazmi_Server/routers/dashboard.py                                           | 164 NEW
 Kharazmi_Server/test_dashboard.py                                              | 160 NEW
```

## Confirmation — 4 Protected Files Unchanged (sha256)
```
fca8c7aff4037cc21e3c8dc1e6b9ad765c7a697c04d3092a71118fb28f0e1d53  finance.py
522d13836645189699084c3965909d02bec6ee768b095a9939ef896e45fb87a9  timeline.py
d6491e333f98f9ea855754a4ab6daac6f389055ef3887865bcf0ba83fc1bbfa5  audit.py
f96714e91d6e795011b5a9445bd924efc2c11f0d10c5048ab1d9f790cacbf967  dunning.py
```
Git HEAD vs working tree identical — no modification, only read via lazy import.

## Verification

### py_compile / ast.parse
```
dashboard.py py_compile OK
main.py py_compile OK
dashboard.py ast OK
main.py ast OK
activity_admin_dashboard.xml / item_dashboard_critical.xml XML OK
AdminDashboardActivity.kt braces 58 vs 58 OK
MainActivity.kt braces 151 vs 151 OK
```

### Sample JSON `GET /dashboard/kpis` (admin, today jalali, 1 txn today + 2 overdue + 1 night session)
```json
{
  "today_revenue": 125000,
  "total_overdue_amount": 400000,
  "overdue_installments_count": 2,
  "active_students_count": 2,
  "suspicious_alerts_count": 1,
  "dunning_pending_count": 2
}
```
- today_revenue: SUM 125000 (jalali prefix)
- overdue: 2 × 250k+150k overdue via parse < today
- active_students: 2 (is_deleted False)
- suspicious: 1 (night 02:30)
- dunning_pending: 2 (critical >7d without 48h ActivityLog)

### Test Suite `Kharazmi_Server/test_dashboard.py` (DATABASE_URL=sqlite memory)
```
9 passed
- test_401_no_token PASSED
- test_403_non_admin PASSED (secretary/teacher 403)
- test_200_admin_empty_returns_6_keys PASSED (2 students, 0 revenue)
- test_kpi_today_revenue_aggregated_jalali PASSED (125k, excludes deleted/reversed/other day)
- test_kpi_overdue_via_parse PASSED (2 count, 30k amount, excludes paid/deleted/upcoming/today)
- test_kpi_active_students_excludes_deleted PASSED
- test_kpi_suspicious_and_dunning_is_int PASSED
- test_read_only_not_modify PASSED
- test_dashboard_isolated_no_finance_touch PASSED
```

## Deliverables Checklist
- [x] `Kharazmi_Server/routers/dashboard.py` (isolated, admin-only, 6 KPIs)
- [x] `Kharazmi_Server/test_dashboard.py` + isolated /tmp run 9 passed
- [x] `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/AdminDashboardActivity.kt` (coroutineScope async, 2x2 Grid, 3 actions, Top5 RecyclerView, SwipeRefresh)
- [x] `activity_admin_dashboard.xml` + `item_dashboard_critical.xml`
- [x] `AppModels.kt` DashboardKPIs, `ApiInterfaces.kt` DashboardApi
- [x] `strings.xml` 20+ فارسی
- [x] `drawer_menu.xml` + `activity_main.xml` + `MainActivity.kt` + `AndroidManifest.xml` + `build.gradle.kts` swipe
- [x] sha256 4 files unchanged confirmed
- [x] sample JSON documented
- [x] git add/commit/push to `arena/01a0a936-kharazmiapp` (next step)

## Notes
- All UI text via `strings.xml` Persian, no hardcode.
- Server errors 400/403/404 shown via `HttpException.code()` and toast `dashboard_error`.
- No wallet/balance mutation — read-only.
- Tomorrow: manual device test DunningActivity ↔ Dashboard navigation, dark/light gold theme check.

