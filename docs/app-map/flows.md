# فاز E — جریان‌های اصلی برنامه

هر ردیف یک جریان قابل‌ردیابی از trigger تا API، transformation و نتیجهٔ UI است. هر ادعای source به `file:line` اشاره دارد؛ هرجا source caller یا نتیجهٔ runtime را ثابت نمی‌کند، «نامشخص» نوشته شده است. این سند تست اجرایی نیست و Android compile در این کار اجرا نشده است.

## خلاصهٔ جریان‌ها

| ID | جریان | نقطه شروع | API/route اصلی | پایان قابل مشاهده |
|---|---|---|---|---|
| F01 | ورود و انتخاب portal | `LoginActivity.kt:92-121` | `POST /auth/login` — `Kharazmi_Server/routers/auth.py:23` | Intentهای نقش‌محور در `LoginActivity.kt:279-283` و portalها |
| F02 | ثبت دانش‌آموز و enrollment | `StudentRegisterActivity.kt:94-111` | `GET /classes/list` — `Kharazmi_Server/routers/classes.py:150`؛ `POST /students/register_and_enroll` — `Kharazmi_Server/routers/students.py:83` | پیام موفقیت و finish در `StudentRegisterActivity.kt:471-486` |
| F03 | ساخت کلاس | `AddClassActivity.kt:62-179` | `GET /teachers/list` — `Kharazmi_Server/routers/teachers.py:103`؛ `POST /classes/create` — `Kharazmi_Server/routers/classes.py:83` | پیام/بازگشت به صفحه قبل در `AddClassActivity.kt:162-186` |
| F04 | مدیریت/تعلیق کلاس | `ClassManagementActivity.kt:114-353` | `GET /classes/list` — `Kharazmi_Server/routers/classes.py:150`؛ `POST /admin/classes/suspend_bulk` — `Kharazmi_Server/routers/admin.py:1534`؛ `POST /admin/classes/{course_id}/suspend_s` — `Kharazmi_Server/routers/classes.py:370` | refresh/list در `ClassManagementActivity.kt:114-142,353-386` |
| F05 | صدور حواله و پرداخت | `InvoiceActivity.kt:452-643` | `GET /finance/search_advanced` — `Kharazmi_Server/routers/finance.py:49`؛ `GET /finance/student_class_status` — `Kharazmi_Server/routers/finance.py:656`؛ `POST /finance/pay` — `Kharazmi_Server/routers/finance.py:224` | receipt/duplicate/error و چاپ client-side در `InvoiceActivity.kt:650-806,809-960` |
| F06 | مشاهده پروفایل و مالی دانش‌آموز | `StudentProfileActivity.kt:335-439` | `GET /admin/students/{id}/full_profile` — `Kharazmi_Server/routers/admin.py:407`؛ `GET /students/{student_id}/grades` — `Kharazmi_Server/routers/students.py:401` | profile، financial rows و action فیش در `StudentProfileActivity.kt:439-527` |
| F07 | قسط: ساخت، پرداخت و reminder | `StudentProfileActivity.kt:952-1070,1184` | `GET /students/{student_id}/installments` — `Kharazmi_Server/routers/students.py:868`؛ `POST /finance/installments` — `Kharazmi_Server/routers/finance.py:1646`؛ `POST /finance/installments/{installment_id}/pay` — `Kharazmi_Server/routers/finance.py:1809`؛ `POST /finance/installments/{installment_id}/remind` — `Kharazmi_Server/routers/finance.py:1960` | list/status/toast در `StudentProfileActivity.kt:952-1070,1184-1210` |
| F08 | حضور و غیاب کلاس | `AttendanceActivity.kt:539,603-634` | `GET /classes/list` — `Kharazmi_Server/routers/classes.py:150`؛ `GET /attendance/session/{session_code}` — `Kharazmi_Server/routers/attendance.py:1003`؛ `PUT /attendance/session/{session_code}` — `Kharazmi_Server/routers/attendance.py:1051`؛ `POST /attendance/submit_session` — `Kharazmi_Server/routers/attendance.py:631` | کلاس/جلسه/صف آفلاین در `AttendanceActivity.kt:414-492,603-684`؛ routeهای دیگر attendance که caller مستقیم ندارند در `mismatches.md` «نامشخص/غیرمستقیم» هستند |
| F09 | نمره و پروفایل آموزشی | `SubmitGradeActivity.kt:93` و `StudentProfileActivity.kt:536` | `POST /grades/submit` — `Kharazmi_Server/routers/students.py:338`؛ `GET /students/{student_id}/grades` — `Kharazmi_Server/routers/students.py:401` | grade list/average در `StudentProfileActivity.kt:536-575` |
| F10 | گزارش مالی و statement | `ReportActivity.kt:334-530` | `GET /reports/financial_summary` — `Kharazmi_Server/routers/reports.py:611`؛ `GET /reports/student_statement` — `Kharazmi_Server/routers/reports.py:744`؛ `GET /finance/search_advanced` — `Kharazmi_Server/routers/finance.py:49` | نمایش پرداخت/بدهی در `ReportActivity.kt:513-530` |
| F11 | داشبورد KPI و export | `AdminDashboardActivity.kt:310-369` | `GET /dashboard/kpis` — `Kharazmi_Server/routers/dashboard.py:56`؛ exportهای `AdminDashboardActivity.kt:149-155` | KPI cards و download toast در `AdminDashboardActivity.kt:321-369,203-215` |
| F12 | دَنینگ، audit و بدهکاران | `DunningActivity.kt:70-194`، `AuditDashboardActivity.kt:73` و `DebtorsActivity.kt:116` | `GET /dunning/drafts` — `Kharazmi_Server/routers/dunning.py:184`؛ `POST /dunning/send_batch` — `Kharazmi_Server/routers/dunning.py:256`؛ `GET /audit/suspicious_patterns` — `Kharazmi_Server/routers/audit.py:87`؛ `GET /finance/reports/debtors_grouped` — `Kharazmi_Server/routers/finance.py:2500` | پیام batch و navigation از `AdminDashboardActivity.kt:130-169` |

> برای routeهای attendance خارج از سه declaration بالا، caller مستقیم یا path ثابت در Android inventory پیدا نشد؛ آن موارد در `mismatches.md` با علت «attendance/live؛ مسیر یا client متفاوت/قدیمی» آمده‌اند. هیچ حدسی جایگزین نشده است.

## F01 — ورود

1. کاربر login را در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/LoginActivity.kt:92-103` trigger می‌کند.
2. declaration و call در `LoginActivity.kt:232` به `POST auth/login` وصل است؛ handler سرور `Kharazmi_Server/routers/auth.py:23` است.
3. مقصد بر اساس پاسخ/role در `LoginActivity.kt:279-283` تعیین می‌شود؛ مقصدهای parent/student نیز دکمه‌های مستقل در `LoginActivity.kt:105-111` دارند.
4. جزئیات token/access-control عمداً در scope این map نیست؛ صرفاً navigation ثبت شد.

## F02 — ثبت دانش‌آموز

1. انتخاب کلاس با `GET classes/list` در `StudentRegisterActivity.kt:246` انجام می‌شود.
2. payload ثبت/ثبت‌نام در `StudentRegisterActivity.kt:471` با `POST students/register_and_enroll` ارسال می‌شود؛ handler `Kharazmi_Server/routers/students.py:83` و schema `Kharazmi_Server/schemas.py:444-467` است.
3. موفقیت در `StudentRegisterActivity.kt:475-486` به toast و finish تبدیل می‌شود. اگر ثبت مستقیم legacy `/students/register` مدنظر باشد، caller در inventory پیدا نشده و در `mismatches.md` آمده است.

## F03 — ساخت کلاس

1. فرم و trigger در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/AddClassActivity.kt:62-179` است.
2. دریافت teacher در `AddClassActivity.kt:102` به declaration فاز B متصل است؛ handler دقیق route در `docs/app-map/server-routes.csv` ثبت شده و در این جریان به‌دلیل چند declaration هم‌نام «نامشخص» نگه داشته شده است.
3. create در `AddClassActivity.kt:162` به `POST /classes/create` و handler `Kharazmi_Server/routers/classes.py:83` وصل است.
4. نتیجهٔ موفق/خطا در `AddClassActivity.kt:178-186` به navigation/Toast ختم می‌شود.

## F04 — مدیریت کلاس

1. list در `ClassManagementActivity.kt:114` از `GET classes/list` می‌آید.
2. suspend bulk در `ClassManagementActivity.kt:196` به `POST /admin/classes/suspend_bulk` و `Kharazmi_Server/routers/admin.py:1534` وصل است.
3. suspend تکی در `ClassManagementActivity.kt:353` به `POST /admin/classes/{id}/suspend_s` و `Kharazmi_Server/routers/classes.py:370` وصل است.
4. refresh و خروجی لیست در `ClassManagementActivity.kt:114-142,353-386` دیده می‌شود؛ approve/reject مسیر جداگانه‌ای دارد و در این جریان فقط وقتی caller صریح در screen doc باشد قابل ادعاست.

## F05 — پرداخت و رسید

1. search در `InvoiceActivity.kt:208` از `GET finance/search_advanced` پاسخ `AdvancedSearchItem` می‌گیرد.
2. وضعیت enrollment در `InvoiceActivity.kt:305,357` از `GET finance/student_class_status` می‌آید؛ handler breakdown را در `Kharazmi_Server/routers/finance.py:676-699` برمی‌گرداند.
3. کاربر amount/wallet را در `InvoiceActivity.kt:452-561` تعیین می‌کند؛ `FinanceSubmitData` در `InvoiceActivity.kt:555-561` ساخته می‌شود.
4. ارسال در `InvoiceActivity.kt:643` به `POST /finance/pay` وصل است. validation، link enrollment، wallet و installment در `Kharazmi_Server/routers/finance.py:246-282,295-321,408-527` ثبت شده است.
5. duplicate/error و receipt در `InvoiceActivity.kt:650-806` و چاپ/PDF client-side در `InvoiceActivity.kt:809-960` تمام می‌شود.

## F06 — پروفایل و بدهی

1. profile در `StudentProfileActivity.kt:335` از `GET admin/students/{id}/full_profile` دریافت می‌شود؛ endpoint `Kharazmi_Server/routers/admin.py:407` است.
2. server ردیف‌های active enrollment و `teachers_financial` را در `Kharazmi_Server/routers/admin.py:425-522` می‌سازد.
3. UI ردیف‌ها و انتخاب فیش را در `StudentProfileActivity.kt:439-527` نشان می‌دهد و grade را در `StudentProfileActivity.kt:536` می‌خواند.
4. اگر debt بدون enrollment وجود داشته باشد، server آن را در row unassigned نگه می‌دارد؛ در `mismatches.md` و `money-lineage.md` به‌عنوان قرارداد nullable ثبت شده است.

## F07 — اقساط

1. list اقساط در `StudentProfileActivity.kt:952` و create در `StudentProfileActivity.kt:1184` trigger می‌شوند.
2. pay/remind در `StudentProfileActivity.kt:1035,1070` declarationهای `InstallmentApi` در `ApiInterfaces.kt:101-115` را مصرف می‌کنند.
3. منطق FIFO و allocation در `Kharazmi_Server/routers/finance.py:455-527` است؛ وضعیت نمایش در `StudentProfileActivity.kt:952-1070` ثبت شده است.
4. route دقیق list/create/pay/remind و هر caller در CSV فاز A/B آمده است؛ هر موردی که declaration ثابت ندارد «نامشخص» است و route حدس زده نمی‌شود.

## F08 — حضور و غیاب

1. کلاس‌ها در `AttendanceActivity.kt:539` از `GET classes/list` گرفته می‌شوند.
2. آغاز/ثبت/تاریخچهٔ session به callerهای موجود در `AttendanceActivity.md` وابسته است؛ screen doc صریحاً موارد route نامشخص را علامت زده است.
3. بنابراین این سند ادعا نمی‌کند هر دکمه به یک endpoint منفرد متصل است؛ routeهای `attendance/*` بدون Retrofit direct در `mismatches.md` فهرست شده‌اند.

## F09 — نمره

1. submit در `SubmitGradeActivity.kt:93` به `POST grades/submit` و `Kharazmi_Server/routers/students.py:338` می‌رود.
2. profile grades در `StudentProfileActivity.kt:536` به `GET students/{id}/grades` و `Kharazmi_Server/routers/students.py:401` متصل است.
3. نمایش grades/averages از API response در screen doc و `StudentProfileActivity.kt:536-575` ثبت شده است؛ محاسبهٔ نمرهٔ جدید در Android ادعا نشده است.

## F10 — گزارش

1. teacher filter در `ReportActivity.kt:334`، financial summary در `ReportActivity.kt:410` و search در `ReportActivity.kt:471` اجرا می‌شوند.
2. statement در `ReportActivity.kt:513` به `GET reports/student_statement` و `Kharazmi_Server/routers/reports.py:744` متصل است.
3. مقادیر `total_paid_institute` و `total_debt_institute` در `ReportActivity.kt:524-525` render می‌شوند؛ اختلاف تعریف `total_paid_institute` با full profile در `findings.md:7` ثبت شده است.

## F11 — KPI/export

1. دریافت KPI در `AdminDashboardActivity.kt:310-321` و render در `AdminDashboardActivity.kt:350-369` است.
2. server route `/dashboard/kpis` در `Kharazmi_Server/routers/dashboard.py:56-85` محاسبهٔ today revenue و overdue را انجام می‌دهد.
3. export callbackها در `AdminDashboardActivity.kt:149-155` به `exports/*` declarationها وصل‌اند؛ نتیجهٔ download با toast در `AdminDashboardActivity.kt:203-215` گزارش می‌شود.

## F12 — دَنینگ و audit

1. draftها در `DunningActivity.kt:117` و ارسال batch در `DunningActivity.kt:162` انجام می‌شوند.
2. routeهای سرور به‌ترتیب `Kharazmi_Server/routers/dunning.py:184` و `Kharazmi_Server/routers/dunning.py:256` هستند.
3. navigation از dashboard به دَنینگ/audit/debtors در `AdminDashboardActivity.kt:130-169` صریح است؛ callerهای audit/debtors نیز در `AuditDashboardActivity.kt:73` و `DebtorsActivity.kt:116` ثبت شده‌اند.
4. وضعیت ارسال در `DunningActivity.kt:148-194` فقط به message/count UI تبدیل می‌شود؛ ارسال واقعی و side effect در source سرور ثبت شده است، نه حدس client.

## وضعیت تأیید

- routeها با extractor فاز A و تماس‌ها با inventory فاز B cross-reference شده‌اند.
- F05، F06، F09، F10 و F11 اتصال route/caller مشخص دارند.
- F03، F07 و F08 بخشی از مسیرهای runtime/چند declaration دارند؛ آن بخش‌ها **نامشخص** مانده‌اند و علت در همین سند درج شده است.
- هیچ تست اجرایی جدید و هیچ تغییر Kotlin/server موجود برای ساخت این flowها انجام نشد.
