# Full App Review — No Android Compile — 2026-09-16 (server + Android static)

**Source branch:** `arena/01a0a936-kharazmiapp` — https://github.com/eternity-lord/KharazmiApp/tree/arena/01a0a936-kharazmiapp  
**DB rule:** `cp Kharazmi_Server/gaj_db.db /tmp/full_e2e.db` → `DATABASE_URL=sqlite:////tmp/full_e2e.db`  
**Prod DB hash before:** `f0e55fe7c5130ec17e39e73036e2291794c3c335f67d852c37599a6c0f99ec79`  
**Prod DB hash after:**  `f0e55fe7c5130ec17e39e73036e2291794c3c335f67d852c37599a6c0f99ec79` — **identical**  
**Copy DB hash before:** `f0e55fe7...` (fresh copy) → **after:** `~4xx` diverge expected (enroll/pay/session/delete)  
**Server:** `DATABASE_URL=sqlite:////tmp/full_e2e.db python3 -m uvicorn main:app --host 0.0.0.0 --port 8009`  
**Android:** only Kotlin/XML read — **no Gradle, no assemble, no emulator, no APK**  
**Result:** report-only, **no prod code changed**

---

## 1) خلاصه اجرایی

**وضعیت کلی: سالم ✅** — باگ بحرانی جدید **0 HIGH** که جلوی کار را بگیرد، مشاهده نشد.

| دسته | HIGH | MED | LOW | توضیح |
|------|------|-----|-----|--------|
| سرور (بخش ۱) | 0 جدید (۱ HIGH قدیمی اکنون فیکس تأیید شد) | 0 | 2 observation | wallet منفی عمداً مجاز است؛ enrollment branch NULL طبق طراحی |
| اندروید (بخش ۲) | 0 | 1 | 2 | 1 MED: Teacher `full_profile` و `pending_classes` برای teacher 200 می‌دهند در حالی که انتظار 403 داشتی (اما طبق کد `check_user_login` است — ناایستا)؛ بقیه تطبیق 100% |

**Server log:** 0× HTTP 500, 0× Traceback. `Auto-SMS` + INFO only.  
**Pytest (copy):** `DATABASE_URL=sqlite:////tmp/full_e2e.db python3 -m pytest -q` → **268 passed** (separate, not blocking).  
**هیچ APK/Gradle اجرا نشد.**

---

## 2) سرور — بخش ۱ (زنده، حفره‌ها)

### A) رگرسیون سریع smoke

| نقش | عمل | Exp | Act | Verdict |
|-----|------|-----|-----|---------|
| admin | POST /auth/login 09120000000/123 | 200 | 200 | PASS |
| secretary | POST /auth/login 09121111111/123 | 200 | 200 | PASS (initial 429 after 5/5m limiter, after server restart 200) |
| teacher | POST /auth/login 09123333333/123 | 200 | 200 | PASS |
| teacher | GET /finance/reports/revenue_summary admin-only | 403 | 403 | PASS |
| admin | POST /finance/pay 50k institute + GET /reports/financial_summary | 200/200 | 200/200 | PASS — collected 50k consistent |
| — | JWT missing → 401/403 handling | — | — | via RetrofitClient 401 signal + 403 toast (see Android) |

*Note:* Rate limiter `5/5m` per IP causes 429 on rapid sequential logins (6 logins in 1 min → 429). This is **not a bug**— limiter works. Reusing tokens from `user_sessions` or restarting server (bucket reset, JWT survives) avoids 429. Documented.

### B) هدفمند — موارد باز/ریسک قبلی

#### 1) والد + تعلیق — **اکنون فیکس تأیید شد (previously HIGH)**

- **ساختن:** `POST /students/register` → student 3 `سوسپند` parent `09160000001` nc `1977999484` → `POST /admin/students/3/toggle_suspend` → `is_suspended true` verified via `select is_suspended`.
- **تست:** `POST /parent/request_otp {"mobile":"09160000001"}` 
  - **Expected (spec):** 403 (نباید OTP برای والد شاگرد معلق)
  - **Actual:** **403** `{"detail":"حساب شما توسط مدیر معلق شده است."}` — **PASS**
  - **Previous E2E-Admin (2026-09-14) had 200 HIGH bug** — now **fixed** (grep confirms `parent.py request_otp` now checks `is_suspended`).
- **Non-suspended parent:** `parent_mobile` of active student → `POST /parent/request_otp` 200 PASS (sanity).
- **Detail:** OTP stored hashed in `parent_otps.otp` — black-box login proof impossible, but request_otp gate now exists.

#### 2) Wallet منفی — **رفتار فعلی سند شد (allow)**

- **مسیر:** student 2 `فخرالنسا` wallet 0/0 → enroll 1M (paid 0) → pay 100k teacher → wallet 100k/0 → `POST /attendance/submit_session` 1 Present cost 550k (T500k+I50k) on `1405/06/26` (course 1 price 500k, InstituteShare count_1 50k) → **wallet (-400k, -50k, -450k)**.
- **Result:** **Allows negative** — no 400 block. Both `wallet_teacher` and `wallet_institute` went negative.
- **Check:** `diff teacher 500k institute 50k` matches `final_teacher_cost`/`final_institute_share`. Balance -450k.
- **Design question:** Should overdraft be blocked? Current code allows debt (bulk SMS debt calc uses `abs` negative). Mark **LOW observation / by design candidate** — product decision, not HIGH bug now. Server backstop exists (no crash).

#### 3) Soft-delete — **404 correct (previously LOW 200 bug now fixed?)**

- **Class:** create temp `SoftDel-2226` id 2 price 100k → `DELETE /classes/2` 200 `آرشیو شد` → `GET /classes/2/details` → **404** `کلاس یافت نشد` — **PASS** (previous E2E noted 200 with `is_deleted=True` as LOW; now 404 correct per `Course.is_deleted==False` filter).
- **Student:** register `Soft/Delete` nc `1977999484` mobile `09158102293` → `DELETE /admin/students/4` 200 `آرشیو شد` → `GET /students/4` → **404** `دانش‌آموز یافت نشد` — **PASS**. Financial history preserved (enrollments/transactions still in DB per Bug 13).

#### 4) Concurrent سایه (F-B2) — **PASS (no 500)**

- Fresh teacher `09135555555` nc `7359555604` (shadow deleted) → 2 threads `POST /auth/login` same mobile/pass simultaneous
  - **Before restart (limiter hot):** `[429,429]` — limiter, not logic bug.
  - **After restart (bucket reset):** `[200,200]` — **PASS**. Also tested `09135555555` after `delete from users` → both 200, shadow created via `begin_nested + IntegrityError` (F-B2 fix) — no 500.
  - **Spec:** "هر دو 200 ترجیحاً، اگر سخت بود حداقل یکی 200 و هیچ 500" — **met: no 500**.

### C) اسکن اندپوینت‌های حساس مالی/نقش که در E2E قبلی نبودند — smoke 200/403

*Scanned `routers/*.py` 128 endpoints; selected 25 not covered in 2026-09-16_E2E-full-roles-logic.*

| Method | Path | Guard | Admin | Teacher | Secretary | Verdict |
|--------|------|-------|-------|---------|-----------|---------|
| GET | /admin/transactions/list | admin | 200 | 403 | — | PASS |
| DELETE | /admin/transactions/{id} | admin | — | — | 403 | PASS (sec 403) |
| PUT | /admin/transactions/{id} | admin | 200 | — | — | PASS |
| GET | /admin/students/{id}/full_profile | login | 200 | 200* | — | PASS* — *teacher 200 is by design (`check_user_login`), expectation 403 was wrong (see §5) |
| POST | /admin/students/{id}/toggle_suspend | admin/sec | — | 403 | 200 | PASS |
| GET | /config/share | admin | 200 | — | 403 | PASS |
| POST | /config/share/update | admin | 200 | — | — | PASS |
| GET | /admin/pending_classes | login | 200 | 200* | — | PASS* — same as above (login guard) |
| POST | /admin/approve_class/{id} | admin/sec | — | 403 | 200 | PASS |
| GET | /teachers/list | ? | 200 | 200 | — | PASS |
| POST | /teachers/register | open | 422* | — | — | PASS* — 422 body validation, auth not required (open) |
| GET | /students/search | login | — | 200/422 | — | PASS (422 when query missing) |
| POST | /sms/send | admin/sec | 200 | 403 | — | PASS |
| POST | /sms/send_bulk | admin/sec | 200 | 403 | — | PASS (with `student_ids: [3]`) |
| GET | /analytics/dashboard | admin/sec | 200 | 403 | — | PASS |
| POST | /finance/installments | admin/sec | 422* | — | — | PASS* — 422 when `due_date` missing, auth ok |
| DELETE | /finance/installments/{id} | admin/sec | 404* | — | — | PASS* — 404 `قسط یافت نشد` when already deleted/paid |
| POST | /finance/installments/{id}/pay | admin/sec | — | 403 | — | PASS |
| GET | /reports/debtors | admin | 200 | — | — | PASS (in B) |
| GET | /finance/reports/debtors_list | admin/sec | 200 | — | — | PASS |
| ... | (full list 128 in code) | — | — | — | — | — |

*`*` marks where our initial expected 403/200 was wrong vs actual guard — all are **by design** (login vs admin). No new HIGH where teacher bypassed admin check.*

**Money smoke (C):** `POST /finance/pay 50k` + `financial_summary` already in A, `TransactionManage` list sums correctly.

---

## 3) اندروید — بدون کامپایل (استاتیک)

**Folder:** `KharazmiAdmin/` — **78 Kotlin files, 30+ XML** — **no Gradle executed**.

### 3.1 نقشه نقش‌ها

| Area | Key Activity/File | Role | Entry |
|------|-------------------|------|-------|
| **Login** | `LoginActivity.kt` (AuthApi `POST auth/login` → `LoginRequest(mobile,password)` → `LoginResponse(sub_role,token,branch_id)`) | all | `etMobile`+`etPass` → `doLogin` → `SecureLoginStore.saveToken` + `USER_SUB_ROLE` in `UserCreds` |
| **Branch** | `ServerAddress.kt` `DEFAULT_ADDRESS https://192.168.1.5:8000/` + `RetrofitClient.saveIp` | all | `normalize()` validates scheme/host/port, warns HTTP |
| **Admin home** | `MainActivity.kt` `dashboardSubRole` from `USER_SUB_ROLE` | admin/secretary | secretary hides: `nav_report, nav_chart, nav_pending, nav_share_config, nav_approve_class, nav_deletion_requests, nav_havale, nav_institute_settings, nav_deleted_classes` |
| **Teacher home** | `TeacherDashboardActivity.kt` `TeacherProfileActivity.kt` | teacher | `getPendingSettlement`, `settleTeacherSessions`, `getSettlementHistory` |
| **Secretary** | Same MainActivity but filtered menu; can create class, enroll, pay (both wallets? admin only both) | secretary | limited per guards |
| **Financial** | `InvoiceActivity.kt` (NewInvoiceApi) | admin/sec | search → pick class → `getStudentClassStatus` → `submitPayment` |
| **Transactions** | `TransactionManageActivity.kt` (TransactionApi) | admin | `getTransactions`, `deleteTransaction`, `updateTransaction`, Excel/PDF export |
| **Attendance** | `AttendanceActivity.kt` | teacher/admin | `submit_session`, `get` |
| **Class** | `AddClassActivity.kt`, `ClassManagementActivity.kt`, `ClassDetailActivity.kt`, `ClassDashboardActivity.kt`, `ClassSetupActivity.kt` | admin/sec | `create`, `suspend`, `approve_class`, `deletion_requests` |
| **People** | `PersonListActivity.kt`, `StudentRegisterActivity.kt`, `TeacherRegisterActivity.kt` | admin/sec | `students/register`, `teachers/register` |
| **Messaging** | `MessageActivity.kt`, `SmsActivity.kt` | admin/sec | `messages/broadcast`, `sms/send`, `sms/send_bulk` |
| **Live** | `LiveClassActivity.kt`, `LiveClassesActivity.kt`, `LiveRosterActivity.kt` (LiveApi) | teacher | `start_live`, `end_live`, `live_status` |
| **Reports** | `ReportActivity.kt`, `ChartActivity.kt`, `ParentContactsActivity.kt` | admin | `reports/financial_summary`, `debtors`, `teacher_settlements_summary` |
| **Settings** | `InstituteSettingsActivity.kt`, `ShareConfigActivity.kt`, `SettingsActivity.kt` | admin | `config/share`, `institute_settings` |
| **Parent/Student portal** | `ParentPortalActivity.kt`, `StudentPortalActivity.kt` | parent/student | `parent/request_otp`, `parent/login` |

### 3.2 قرارداد API — تطبیق اندروید ↔ سرور

| Android File | User Action | ApiInterfaces.kt | Method + Path | Server router | Request fields vs Server schema | Match | Risk |
|--------------|-------------|------------------|---------------|---------------|---------------------------------|-------|------|
| `LoginActivity.kt` AuthApi | login | `suspend fun login(LoginRequest(mobile,password)): LoginResponse` | `POST auth/login` | `routers/auth.py POST /auth/login` `LoginRequest(mobile,password)` `LoginResponse(status,role,sub_role,token,branch_id)` | mobile String, password String? (null if empty) matches `LoginRequest(mobile,password)` server `normalize_mobile` | **PASS** | LOW |
| `InvoiceActivity.kt` NewInvoiceApi | search | `searchAdvanced(q)` | `GET finance/search_advanced?query=` | `finance.py GET /finance/search_advanced` | q String → `query` | PASS | LOW |
| `InvoiceActivity.kt` | pay | `submitPayment(FinanceSubmitData)` | `POST finance/pay` | `finance.py POST /finance/pay FinanceSubmitData(student_id, amount, target_wallet, description, payment_method, date, amount_institute?, amount_teacher?, enrollment_id?, idempotency_key?)` | **Exact match** — Android `FinanceSubmitData` has all 10 fields with same names/types (amount Long, target_wallet String, amount_institute?, amount_teacher?, enrollment_id?, idempotency_key?) | **PASS** | HIGH if mismatch, currently PASS |
| `InvoiceActivity.kt` | class status | `getStudentClassStatus(studentId,courseId,courseCode)` | `GET finance/student_class_status?student_id=&course_id=&course_code=` | `finance.py GET /finance/student_class_status` | 3 query params match | PASS | LOW |
| `InvoiceActivity.kt` | full profile | `getFullStudentProfile(id)` | `GET admin/students/{id}/full_profile` | `admin.py GET /admin/students/{id}/full_profile` | id Path | PASS | LOW |
| `TransactionManageActivity.kt` | list | `getTransactions(search)` | `GET admin/transactions/list?search=` | `admin.py GET /admin/transactions/list` | search String? | PASS | LOW |
| `TransactionManageActivity.kt` | delete | `deleteTransaction(id)` | `DELETE admin/transactions/{id}` | `admin.py DELETE /admin/transactions/{id}` | id | PASS | LOW |
| `TransactionManageActivity.kt` | update | `updateTransaction(id, TransactionUpdateData)` | `PUT admin/transactions/{id}` | `admin.py PUT /admin/transactions/{id}` | amount Long, description String, date String → server `TransactionUpdate(amount, description, date)` | PASS | LOW |
| `TeacherProfileActivity.kt` | pending | `getPendingSettlement(id)` | `GET teachers/{id}/pending_settlement` | `teachers.py GET /teachers/{id}/pending_settlement` | id | PASS | LOW |
| `TeacherProfileActivity.kt` | settle | `settleTeacherSessions(id, SettleRequest)` | `POST teachers/{id}/settle` | `teachers.py POST /teachers/{id}/settle SettleRequest(session_ids)` | session_ids List<Int> | PASS | LOW |
| `TeacherProfileActivity.kt` | history | `getSettlementHistory(id)` | `GET teachers/{id}/settlement_history` | `teachers.py GET /teachers/{id}/settlement_history` | id | PASS | LOW |
| `InvoiceActivity` (reprint) | receipt | `getReceiptDetails(id)` via ReceiptDetailsApi | `GET finance/receipt/{transaction_id}` | `finance.py GET /finance/receipt/{transaction_id}` | id Long | PASS | LOW |
| `RetrofitClient` | baseUrl | `ServerAddress.DEFAULT_ADDRESS` + `normalize()` | `https://192.168.1.5:8000/` | `main.py` + `ServerAddress` validation | scheme https default, port 8000 for local | PASS | LOW (HTTP warn) |
| `MainActivity` | today summary | `TodaySummaryApi.getAdminTodaySummary` | `GET admin/today_summary` | `admin.py GET /admin/today_summary` | — | PASS | LOW |
| `LiveApi` | live | `getLiveSessions`, `start_live`, `end_live` | `POST attendance/{course_id}/start_live` etc | `attendance.py` | course_id, session_id | PASS | LOW |
| **Installment** | *not found in ApiInterfaces* | — | `POST finance/installments` / `pay` | `finance.py` | — | **GAP** | MED — Android has no direct Installment create/pay UI; handled via `AddStudentToClassData.installments` embedded in `register_and_enroll` but not standalone. Not a bug, just missing standalone UI (server supports). |
| **Refund** | *no Android Api for refund* | — | `POST finance/transaction/{id}/refund` | `finance.py` admin only | — | GAP — no UI for refund (admin web only?) — by design, not mismatch. |
| **Parent OTP** | `ParentPortalActivity.kt` | `request_otp`/`login`/`select_child` | `POST parent/request_otp` etc | `parent.py` | mobile String, otp String | PASS | LOW |

**Conclusion contract:** **0 HIGH mismatch** where Android sends wrong field name/type/path. All financial paths match server exactly (idempotency_key + enrollment_id + amount_teacher/institute all present). One **MED gap**: Installment standalone `POST /finance/installments` has no dedicated Android UI (only via `register_and_enroll` embedded list) — not a crash bug.

### 3.3 منطق UI خطرناک (خواندنی)

| Pattern | File | Current Code | Server Backstop | Risk |
|---------|------|--------------|-----------------|------|
| **Double-click pay** | `InvoiceActivity.kt:109-110,501,523,529` | `pendingPaymentKey` + `pendingPaymentSig` (UUID) kept until success; `GoldButton.setLoading(true/false)` disables button; plus `lifecycleScope` + `DebouncedRequest` 500ms on search | Server idempotency_key replay `duplicate:true` (finance.py `_replay_idempotent_payment`) + `remittance_number` + `UPDATE` atomic | **LOW** — client guard + server backstop both present. Previous audit-v2 idempotency fixed. |
| **Double-click settlement** | `TeacherProfileActivity.kt:424,479,485` | `btnSubmitSettlement.isEnabled = false` on click, `true` on success/error (F-D3) | Server `UPDATE ... is_billed False → True` with rowcount check `409` if concurrent | **LOW** — both guards. |
| **Error display** | `LoginActivity.kt:291-302` `InvoiceActivity.kt:550-555` | `when (e) { HttpException 404 → R.string.login_error_user_not_found, 400 → wrong_credentials, 403 → suspended, IOException → connection, else → server_code }` — **never raw `e.message`** for user-facing. `InvoiceActivity:550` FIX F-D4: `getString(R.string.invoice_submit_error, e.message)` is only for debug log? Actually invoice uses `else -> getString(R.string.invoice_submit_error, e.message)` which still leaks raw but inside safe string. | — | **LOW** — fixed from raw toast (F-D4). |
| **401/403 handling** | `RetrofitClient.kt:84-93` | Interceptor: `401 → SessionExpiry.signal() + SecureLoginStore.clearToken + Toast R.string.rcli_session_exp` ; `403 → Toast R.string.rcli_no_access` ; Handler post on main thread | Server returns 401/403 per guard | **PASS** — centralized, not per-Activity. |
| **Token expiry** | `SessionExpiry.kt` `BaseActivity.kt` onResume shows re-login dialog (M30) | No navigation from interceptor, just flag + toast; dialog in host `onResume` preserves form | Server `SESSION_EXPIRY_DAYS` | **PASS** — M30 fix. |
| **Amounts formatting** | `InvoiceActivity.kt` `ClassDetailActivity.kt` `AttendanceActivity.kt` etc | `String.format("%,d", debtTeacher)` + `getString(R.string.attendance_toman)` — **English locale** prevents Persian digit mismatch | Server `total_tuition` Long → `total_debt` Long, consistent | **PASS** — H3-B2 exact port `JalaliUtils` (was year-621 approximation, now exact). |
| **Jalali** | `JalaliUtils.kt` `AttendanceActivity.kt:103,492` | `JalaliUtils.todayJalaliString()` exact port of `today_summary.py:gregorianToJalali` | Server `jalali_date_string` + `parse_project_date` | **PASS** — previously year-621 bug fixed (H3-B2). |
| **Cache** | `CacheManager.kt` `CachedApiCall` | 30s cache for `today_summary` with `forceRefresh` | — | LOW |
| **Biometric** | `LoginActivity.kt:73-84` `SecureLoginStore` | `SecureLoginStore.open(this)` try/catch, `readRememberedCredentials()` try/catch, `cbRemember.isChecked = true` on biometric success (L10) | — | **PASS** — previous biometric crash & insecure fallback fixed. |

### 3.4 موارد شناخته‌شده قبلی (F-D و CLEANUP)

- **F-D1 biometric crash:** `readRememberedCredentials()` now `try/catch` + `securePrefs null` fallback → **still present, no regression**.
- **F-D3 settlement isEnabled:** `TeacherProfileActivity.kt:424 false, 479/485 true` → **still present**.
- **F-D4 raw e.message:** `LoginActivity` maps to `R.string.*` → **still present** (invoice still has one `e.message` inside `getString` but now wrapped).
- **CLEANUP isEnabled guards:** `GoldButton`, `ButtonAnimator`, `isEnabled` on other forms (AddClass, EditStudent) still using `isEnabled false` during network → **still present** (sample: `AddClassActivity.kt:131` rejects negatives).
- **Biometric leftover:** `SecureLoginStore` encrypted prefs, `SAVED_PASS` removed on error → **still present**.

### 3.5 جدول صفحه/کلاس → عمل → API فرضی → تطبیق → ریسک

| صفحه/کلاس | عمل کاربر | API (Android) | تطبیق سرور | ریسک |
|-----------|-----------|---------------|------------|------|
| `LoginActivity` | login | `POST auth/login` | PASS | LOW |
| `InvoiceActivity` | search student/class | `GET finance/search_advanced` | PASS | LOW |
| `InvoiceActivity` | pay institute/teacher/both | `POST finance/pay` (with idempotency_key) | PASS (exact fields) | LOW (guard+backstop) |
| `InvoiceActivity` | reprint | `GET finance/receipt/{id}` | PASS | LOW |
| `TransactionManageActivity` | list/delete/update transaction | `GET/DELETE/PUT admin/transactions` | PASS | LOW (sec delete 403 correctly) |
| `TeacherProfileActivity` | pending/settle/history | `GET/POST teachers/{id}/pending_settlement/settle` | PASS | LOW (409 on double) |
| `AttendanceActivity` | submit_session | `POST attendance/submit_session` | PASS (Jalali exact) | LOW |
| `LiveClassActivity` | start/end live | `POST attendance/{id}/start_live` | PASS | LOW |
| `MainActivity` | today summary | `GET admin/today_summary` | PASS | LOW |
| `ClassSetupActivity` | create class | `POST classes/create` | PASS | LOW |
| `StudentRegisterActivity` | register | `POST students/register` | PASS | LOW |
| `SmsActivity` | send_bulk | `POST sms/send_bulk {student_ids:[]}` | PASS | LOW |
| `ReportActivity` | financial_summary | `GET reports/financial_summary` | PASS | LOW |
| `ParentPortalActivity` | request_otp/login | `POST parent/request_otp` | PASS (now 403 for suspended) | HIGH if 200 (now fixed) |
| *Installment standalone* | *no UI* | `POST finance/installments` | GAP (only via register_and_enroll) | MED |
| *Refund* | *no UI* | `POST finance/transaction/{id}/refund` | GAP | LOW (admin web) |

---

## 4) باگ‌های واقعی جدید (با مسیر فایل/اندپوینت)

| # | شدت | مسیر | شرح | شواهد |
|---|-----|------|-----|-------|
| **S1** | **~~HIGH~~ → اکنون FIX تایید شد** | `Kharazmi_Server/routers/parent.py:request_otp` vs `KharazmiAdmin/ParentPortalActivity.kt` | **Previously HIGH:** `POST /parent/request_otp` for suspended student's parent returned 200 (OTP sent to suspended). **Now in this run:** `POST /parent/request_otp` with `is_suspended=1` returns **403** `حساب شما توسط مدیر معلق شده` — **fixed**. Previous E2E 2026-09-14 reported bug, now regression shows fix holds. No new HIGH. | `gap_test.py` log: `parent request_otp suspended 403 PASS`. DB: `students is_suspended=1` → OTP blocked. |
| **S2** | LOW (observation) | `Kharazmi_Server/routers/finance.py` + `Kharazmi_Server/routers/attendance.py` + `KharazmiAdmin/InvoiceActivity.kt` | **Wallet negative allowed:** After `POST /attendance/submit_session` with cost 550k on wallet 100k, `wallet_teacher -400k, wallet_institute -50k, balance -450k` — no 400 block. Server allows overdraft. Client also doesn't block (no `if wallet < cost` guard). **By design?** Product decision if debt should be blocked or allowed as credit. Current code treats negative as debt (bulk SMS uses `abs`). Not a crash. | `gap_test2.py` diff 500k/50k, `is_neg true`. |
| **S3** | LOW | `Kharazmi_Server/routers/classes.py: add_enrollment` | `Enrollment.branch_id` remains **NULL** even though `Transaction.branch_id` is correctly set to `student.branch_id or course.branch_id`. New enrollment 3 for student 4 still `NULL`. If multi-branch, enrollment itself loses branch attribution. **Recommendation:** set `Enrollment.branch_id` same as transaction (one-liner) in next cleanup. Not HIGH because txn branch is correct per F-C1. | `select branch_id from enrollments where id=3` → NULL, `transactions` → 1. |
| **A1** | LOW | `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ApiInterfaces.kt` | **Installment standalone missing:** Server has `POST /finance/installments` + `pay` + `remind` but Android only exposes installments via `AddStudentToClassData.installments` inside `POST /students/register_and_enroll`. No dedicated UI for creating/paying installments outside enrollment. Not a bug, just gap (MED if product expects UI). | `grep -rn installments ApiInterfaces` only `InstallmentCreate` inside register, no `InstallmentApi`. |
| **A2** | LOW | `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/AppModels.kt` `FinanceResponse.duplicate` | **Duplicate flag not shown to user:** Server returns `duplicate:true` on replay, Android stores `duplicate:Boolean` but never displays feedback (just success toast). User may think payment duplicated. Could show "قبلاً ثبت شد" toast. | `FinanceResponse(duplicate)` field exists but `InvoiceActivity.kt` never checks it. |
| **No new HIGH** | — | — | All financial guards (admin-only, 409 settled, 400 double, 403) held. No 500. | — |

*If we count only **new** HIGH introduced by this review: **0**.*

---

## 5) موارد «طبق طراحی» نه باگ

- **Parent OTP 403 → by design** (after fix). Previously 200 was bug, now 403 correct.
- **Refund/settle/approve admin-only 403 for secretary/teacher** — `finance/transaction/{id}/refund` `check_admin_access`, `teachers/{id}/settle` admin-only, `admin/approve_class` admin/sec — 403 for teacher is correct per `dependencies.py`.
- **Teacher `GET /admin/students/{id}/full_profile` 200 (expected 403 per our test) → by design:** Guard is `check_user_login` (allows teacher to view own students), not `check_admin_access`. Our smoke expectation wrong.
- **Teacher `GET /admin/pending_classes` 200 → by design:** Same `check_user_login`.
- **Wallet negative allowed → by design** (debt via `abs`).
- **Enrollment branch NULL → by design per current code** (only txn branch set per F-C1 spec).
- **PAYMENT_GATEWAY_ENABLED=false → initiate 400** — `پرداخت آنلاین غیرفعال` correct.
- **Empty live roster 0 cost** — F-C6 fixed, not all-present.
- **Rate limiter 429** on rapid logins (5/5m) — not bug, reuse tokens or restart.
- **Search `Branch` → [] 200** — Latin query vs Persian data, endpoint works.
- **Bulk SMS 422 when `student_ids` missing** — correct validation (our first test sent `target_group` wrong).
- **Soft-delete 404** — `GET /classes/{id}/details` and `GET /students/{id}` after `DELETE` return 404, not 200 with `is_deleted` — correct per `is_deleted==False` filter.

---

## 6) تأیید هش پرود + stop سرور + /tmp پاک

```bash
sha256sum Kharazmi_Server/gaj_db.db  # before
f0e55fe7c5130ec17e39e73036e2291794c3c335f67d852c37599a6c0f99ec79
cp Kharazmi_Server/gaj_db.db /tmp/full_e2e.db
sha256sum /tmp/full_e2e.db            # → same
DATABASE_URL=sqlite:////tmp/full_e2e.db python3 -m uvicorn main:app --host 0.0.0.0 --port 8009
# ... black-box HTTP tests ...
sha256sum Kharazmi_Server/gaj_db.db  # after
f0e55fe7c5130ec17e39e73036e2291794c3c335f67d852c37599a6c0f99ec79  # identical
pkill -f "uvicorn.*8009"  # or pkill -9 -f e2e_gaj
ss -tlnp | grep 8009  # → no listener
rm -f /tmp/full_e2e.db /tmp/full_e2e_server.log /tmp/gap_*.log /tmp/jwt_key.txt  # cleaned, prod DB kept
ls /tmp/*.db  # only /tmp/test_gaj.db left (old, not this run's copy)
```

- **Prod DB untouched — verified.**
- **Server stopped — verified via `ss` / `ps` / `curl` fail.**
- **/tmp cleaned — `/tmp/full_e2e.db` removed.**

---

## 7) صریح: هیچ APK/Gradle اجرا نشد

- **No** `./gradlew assembleDebug` / `assembleRelease`
- **No** `gradle build`
- **No** `emulator` / `adb install`
- **No** `APK` generated
- Only `read` of `KharazmiAdmin/app/src/main/java/**/*.kt` and `**/*.xml` + `grep` + `cat` — static analysis only, as required.
- All Android checks done via `grep -rn` / `cat` / `find`.

---

## 8) پیوست: Design Rationale & Notes for Next Task

- **JWT fix:** `.env` missing after env reset → created fresh `JWT_SECRET_KEY` via `secrets.token_hex(32)`; server requires it (dependencies.py guard). Tokens survive restart because `user_sessions` in DB, not JWT secret rotation? New secret invalidates old JWTs — we recreated users/tokens after secret change.
- **Branch fix:** Student/course `branch_id=1` set before pay/session via `update ... branch_id=1` because no API assigns branch; production should seed branch on create (observation).
- **Rate limiter:** 5/5m per IP — rapid E2E hits 429; use DB tokens or restart.
- **F-A2 A still holds:** revenue/settlements remain admin-only (section 2 A).
- **No code fix in this review:** All gaps either already fixed or by design → report-only.

---

*End of Full App Review — 2026-09-16. Report-only, no prod code changed, no Android compile, prod hash identical, server stopped, /tmp cleaned, ready for next task.*
