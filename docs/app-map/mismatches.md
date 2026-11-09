# فاز D — جفت‌کردن و ناهماهنگی‌ها

این سند فقط اختلاف‌های قابل مشاهده از source را ثبت می‌کند؛ هیچ‌کدام در این فاز fix نشده‌اند.

## 1. تماس اپ بدون route سرور

مقایسه بر اساس method و path نرمال‌شدهٔ `{id}`/`{student_id}` انجام شد؛ declaration پویا `GET dynamic (@Url/نامشخص)` در `ReportExporter.kt:27` route ثابت نیست و پیش از تفاضل به‌عنوان مورد runtime کنار گذاشته شد. نتیجه: **0 تماس Retrofit با route مفقود**. دو موردی که ابتدا در مقایسهٔ خام ظاهر می‌شدند، پس از اعمال prefix ثبت‌شده در `Kharazmi_Server/main.py:710` و `Kharazmi_Server/main.py:713` با route واقعی جفت شدند:

- `AuditApi.getSuspiciousPatterns`: `ApiInterfaces.kt:126` ↔ `/audit/suspicious_patterns` در `routers/audit.py:87` و prefix در `main.py:710`.
- `AdminCommandCenterApi.getKpis`: `ApiInterfaces.kt:153` ↔ `/dashboard/kpis` در `routers/dashboard.py:56` و prefix در `main.py:713`.

## 2. routeهای سرور بدون فراخوانی Retrofit مستقیم

تعداد: **72 route pair**. این فهرست از تفاضل method/path نرمال‌شدهٔ `server-routes.csv` و `android-api-calls.csv` ساخته شده است. نبودن declaration در Retrofit به‌تنهایی dead code نیست؛ ستون آخر فقط طبقه‌ای را ثبت می‌کند که از مسیر/handler قابل اثبات است.

| method | route | handler و مرجع دقیق | طبقهٔ قابل اثبات |
|---|---|---|---|
| GET | `/admin/live_sessions` | `Kharazmi_Server/routers/attendance.py:1434` (routers.attendance.get_admin_live_sessions) | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| GET | `/admin/live_sessions/{session_id}/roster` | `Kharazmi_Server/routers/attendance.py:1492` (routers.attendance.get_admin_live_session_roster) | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| GET | `/admin/pricing_table` | `Kharazmi_Server/routers/admin.py:2044` (routers.admin.get_pricing_table) | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| PUT | `/admin/pricing_table` | `Kharazmi_Server/routers/admin.py:2050` (routers.admin.update_pricing_table) | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| GET | `/admin/transactions/list/excel` | `Kharazmi_Server/routers/admin.py:793` (routers.admin.get_transactions_excel) | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| POST | `/ai/chat` | `Kharazmi_Server/routers/ai.py:153` (routers.ai.chat_with_ai_assistant) | ابزار داخلی AI؛ declaration مستقیم ندارد |
| GET | `/analytics/classes` | `Kharazmi_Server/routers/analytics.py:355` (routers.analytics.get_classes_performance_analytics) | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| GET | `/analytics/dashboard` | `Kharazmi_Server/routers/analytics.py:152` (routers.analytics.get_analytics_dashboard) | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| GET | `/analytics/export/excel` | `Kharazmi_Server/routers/analytics.py:396` (routers.analytics.export_analytics_excel) | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| GET | `/analytics/export/pdf` | `Kharazmi_Server/routers/analytics.py:529` (routers.analytics.export_analytics_pdf) | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| GET | `/analytics/teachers` | `Kharazmi_Server/routers/analytics.py:294` (routers.analytics.get_teachers_performance_analytics) | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| POST | `/attendance/get` | `Kharazmi_Server/routers/attendance.py:585` (routers.attendance.get_class_attendance) | attendance/live؛ مسیر یا client متفاوت/قدیمی |
| GET | `/attendance/live/current` | `Kharazmi_Server/routers/attendance.py:551` (routers.attendance.get_current_live_session) | attendance/live؛ مسیر یا client متفاوت/قدیمی |
| POST | `/attendance/qr_check-in` | `Kharazmi_Server/routers/attendance.py:1353` (routers.attendance.qr_student_check_in) | attendance/live؛ مسیر یا client متفاوت/قدیمی |
| DELETE | `/attendance/session/{session_code}` | `Kharazmi_Server/routers/attendance.py:1288` (routers.attendance.delete_session_endpoint) | attendance/live؛ مسیر یا client متفاوت/قدیمی |
| POST | `/attendance/{course_id}/start_live` | `Kharazmi_Server/routers/attendance.py:313` (routers.attendance.start_live_session) | attendance/live؛ مسیر یا client متفاوت/قدیمی |
| POST | `/attendance/{session_id}/cancel_live` | `Kharazmi_Server/routers/attendance.py:449` (routers.attendance.cancel_live_session) | attendance/live؛ مسیر یا client متفاوت/قدیمی |
| POST | `/attendance/{session_id}/end_live` | `Kharazmi_Server/routers/attendance.py:369` (routers.attendance.end_live_session) | attendance/live؛ مسیر یا client متفاوت/قدیمی |
| POST | `/attendance/{session_id}/live_status` | `Kharazmi_Server/routers/attendance.py:509` (routers.attendance.save_live_status) | attendance/live؛ مسیر یا client متفاوت/قدیمی |
| POST | `/auth/device_token` | `Kharazmi_Server/routers/auth.py:597` (routers.auth.register_device_token) | background/device integration؛ declaration مستقیم ندارد |
| GET | `/automation/logs` | `Kharazmi_Server/routers/automation.py:125` (routers.automation.get_automation_logs) | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| GET | `/automation/rules` | `Kharazmi_Server/routers/automation.py:117` (routers.automation.get_automation_rules) | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| POST | `/automation/rules` | `Kharazmi_Server/routers/automation.py:66` (routers.automation.create_automation_rule) | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| PUT | `/automation/rules/{rule_id}` | `Kharazmi_Server/routers/automation.py:93` (routers.automation.update_automation_rule) | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| POST | `/automation/run_rules` | `Kharazmi_Server/routers/automation.py:143` (routers.automation.run_automation_engine) | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| GET | `/branches` | `Kharazmi_Server/routers/branches.py:113` (routers.branches.list_branches) | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| POST | `/branches` | `Kharazmi_Server/routers/branches.py:52` (routers.branches.create_branch) | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| PUT | `/branches/{branch_id}` | `Kharazmi_Server/routers/branches.py:75` (routers.branches.update_branch) | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| POST | `/branches/{branch_id}/suspend` | `Kharazmi_Server/routers/branches.py:96` (routers.branches.suspend_branch) | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| GET | `/classes/pending_approval` | `Kharazmi_Server/routers/classes.py:1304` (routers.classes.pending_classes_for_admin) | admin/export؛ declaration مستقیم ندارد |
| GET | `/classes/{class_id}/students_full/excel` | `Kharazmi_Server/routers/classes.py:710` (routers.classes.get_class_students_excel) | admin/export؛ declaration مستقیم ندارد |
| POST | `/crm/register_online` | `Kharazmi_Server/routers/crm.py:253` (routers.crm.public_online_registration) | وب/پرتال؛ caller Android مستقیم ندارد |
| GET | `/dashboard/branch_stats` | `Kharazmi_Server/routers/branches.py:229` (routers.branches.get_branch_stats) | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| GET | `/dashboard/push_status` | `Kharazmi_Server/routers/dashboard.py:157` (routers.dashboard.get_push_status) | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| GET | `/dashboard/stats` | `Kharazmi_Server/routers/admin.py:51` (routers.admin.get_dashboard_stats) | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| POST | `/exams/create` | `Kharazmi_Server/routers/exams.py:45` (routers.exams.create_exam) | جریان learner؛ caller مستقیم در Android admin پیدا نشد |
| POST | `/exams/{id}/questions` | `Kharazmi_Server/routers/exams.py:95` (routers.exams.add_exam_question) | جریان learner؛ caller مستقیم در Android admin پیدا نشد |
| POST | `/finance/debtors/remind` | `Kharazmi_Server/routers/finance.py:2576` (routers.finance.remind_debtors) | مالی/درگاه/legacy؛ مسیر مستقیم فعلی متفاوت است |
| GET | `/finance/installments` | `Kharazmi_Server/routers/finance.py:1588` (routers.finance.get_all_installments) | مدیریت قسط؛ UI فعلی declaration مستقیم ندارد |
| DELETE | `/finance/installments/{installment_id}` | `Kharazmi_Server/routers/finance.py:1764` (routers.finance.delete_installment) | مدیریت قسط؛ UI فعلی declaration مستقیم ندارد |
| PUT | `/finance/installments/{installment_id}` | `Kharazmi_Server/routers/finance.py:1698` (routers.finance.update_installment) | مدیریت قسط؛ UI فعلی declaration مستقیم ندارد |
| GET | `/finance/invoice/{enrollment_id}` | `Kharazmi_Server/routers/finance.py:2264` (routers.finance.get_invoice_details) | caller مستقیم در Retrofit پیدا نشد؛ علت نامشخص |
| GET | `/finance/mock_payment_page` | `Kharazmi_Server/routers/finance.py:1355` (routers.finance.mock_payment_page) | مالی/درگاه/legacy؛ مسیر مستقیم فعلی متفاوت است |
| GET | `/finance/parent/dashboard` | `Kharazmi_Server/routers/finance.py:2189` (routers.finance.get_parent_financial_dashboard) | وب/پرتال؛ caller Android مستقیم ندارد |
| GET | `/finance/payment/callback` | `Kharazmi_Server/routers/finance.py:879` (routers.finance.payment_callback) | مالی/درگاه/legacy؛ مسیر مستقیم فعلی متفاوت است |
| POST | `/finance/payment/initiate` | `Kharazmi_Server/routers/finance.py:799` (routers.finance.initiate_online_payment) | مالی/درگاه/legacy؛ مسیر مستقیم فعلی متفاوت است |
| GET | `/finance/reports/debtors_list` | `Kharazmi_Server/routers/finance.py:2486` (routers.finance.get_debtors_list) | گزارش/خروجی داخلی؛ declaration مستقیم ندارد |
| GET | `/finance/reports/revenue_summary` | `Kharazmi_Server/routers/finance.py:2654` (routers.finance.get_revenue_summary) | گزارش/خروجی داخلی؛ declaration مستقیم ندارد |
| GET | `/finance/reports/teacher_settlements_summary` | `Kharazmi_Server/routers/finance.py:2709` (routers.finance.get_teacher_settlements_summary) | گزارش/خروجی داخلی؛ declaration مستقیم ندارد |
| GET | `/finance/student/{student_id}/payments` | `Kharazmi_Server/routers/finance.py:2021` (routers.finance.get_student_online_payments) | مالی/درگاه/legacy؛ مسیر مستقیم فعلی متفاوت است |
| GET | `/finance/student/{student_id}/transactions` | `Kharazmi_Server/routers/finance.py:2047` (routers.finance.get_student_physical_transactions) | مالی/درگاه/legacy؛ مسیر مستقیم فعلی متفاوت است |
| POST | `/finance/transaction/{transaction_id}/refund` | `Kharazmi_Server/routers/finance.py:1394` (routers.finance.refund_transaction) | مالی/درگاه/legacy؛ مسیر مستقیم فعلی متفاوت است |
| POST | `/homework/submissions/{homework_id}/submit` | `Kharazmi_Server/routers/homework.py:186` (routers.homework.submit_homework_file) | جریان learner؛ caller مستقیم در Android admin پیدا نشد |
| DELETE | `/messages/{id}` | `Kharazmi_Server/routers/messages.py:221` (routers.messages.delete_own_message) | پیام‌رسان؛ delete مستقیم در UI پیدا نشد |
| GET | `/parent/portal` | `Kharazmi_Server/routers/parent.py:448` (routers.parent.get_parent_portal_page) | وب/پرتال؛ caller Android مستقیم ندارد |
| GET | `/reports/debtors` | `Kharazmi_Server/routers/reports.py:446` (routers.reports.get_debtors_report) | گزارش/خروجی داخلی؛ declaration مستقیم ندارد |
| GET | `/reports/debtors/excel` | `Kharazmi_Server/routers/reports.py:477` (routers.reports.get_debtors_excel) | گزارش/خروجی داخلی؛ declaration مستقیم ندارد |
| GET | `/reports/financial` | `Kharazmi_Server/routers/reports.py:314` (routers.reports.get_financial_report) | گزارش/خروجی داخلی؛ declaration مستقیم ندارد |
| GET | `/reports/student_profile/print` | `Kharazmi_Server/routers/reports.py:1067` (routers.reports.print_student_profile) | گزارش/خروجی داخلی؛ declaration مستقیم ندارد |
| GET | `/reports/student_statement/print` | `Kharazmi_Server/routers/reports.py:883` (routers.reports.print_student_statement) | گزارش/خروجی داخلی؛ declaration مستقیم ندارد |
| GET | `/resources` | `Kharazmi_Server/routers/branches.py:171` (routers.branches.list_resources) | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| POST | `/resources` | `Kharazmi_Server/routers/branches.py:125` (routers.branches.create_resource) | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| POST | `/resources/bookings` | `Kharazmi_Server/routers/branches.py:183` (routers.branches.book_resource) | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| PUT | `/resources/{id}` | `Kharazmi_Server/routers/branches.py:149` (routers.branches.update_resource) | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| POST | `/sms/send_bulk` | `Kharazmi_Server/routers/admin.py:1495` (routers.admin.send_bulk_sms) | پیامک؛ bulk route با UI ارسال معمولی متفاوت است |
| POST | `/students/register` | `Kharazmi_Server/routers/students.py:40` (routers.students.register_student) | مسیر students قدیمی/موازی؛ UI مسیر دیگری دارد |
| GET | `/students/search` | `Kharazmi_Server/routers/students.py:264` (routers.students.search_students) | مسیر students قدیمی/موازی؛ UI مسیر دیگری دارد |
| GET | `/students/{student_id}/report_card/pdf` | `Kharazmi_Server/routers/exams.py:383` (routers.exams.export_report_card_pdf) | PDF با URL runtime؛ declaration Retrofit ندارد |
| GET | `/teachers/list/excel` | `Kharazmi_Server/routers/teachers.py:668` (routers.teachers.get_teachers_excel) | گزارش/خروجی داخلی؛ declaration مستقیم ندارد |
| GET | `/test/debt_calculation` | `Kharazmi_Server/routers/admin.py:98` (routers.admin.test_debt_calculation) | diagnostic/test route |
| POST | `/test/transaction_logic` | `Kharazmi_Server/routers/admin.py:1338` (routers.admin.test_transaction_logic) | diagnostic/test route |
| GET | `/uploads/{filename}` | `Kharazmi_Server/main.py:94` (main.serve_upload) | فایل/URL runtime؛ Retrofit JSON نیست |


## 3. اختلاف فیلد/نوع بین Kotlin و پاسخ سرور

| شدت | اختلاف قابل مشاهده | مرجع اپ | مرجع سرور | اثر |
|---|---|---|---|---|
| کم | مدل محلی `ClassStudentData` در `ClassDetailActivity` فقط `name/mobile/paid/debt` دارد و metadata/فیلدهای مالی اضافهٔ پاسخ `/classes/{id}/students_full` را مدل نمی‌کند. | `ClassDetailActivity.kt:40-42` و مدل کامل همان فایل: `ClassDetailActivity.kt:78-101` | ساخت ردیف کامل: `routers/classes.py:850-910` | Gson فیلدهای اضافه را نادیده می‌گیرد؛ نمایش metadata در این صفحه از مدل محلی قابل دسترسی نیست. |
| کم | `SearchStudentItem` در `ReportActivity` فقط فیلدهای پایه را می‌گیرد، درحالی‌که `/finance/search_advanced` `AdvancedSearchItem` با debt fields و nested students برمی‌گرداند. | `ReportActivity.kt:87-96,131-133` | `finance.py:49-180` | برای search گزارش، فیلدهای اضافه استفاده نمی‌شوند؛ mismatch مصرفی/مدل است نه route. |
| کم | `StudentClassStatus` و چند مدل مالی Kotlin مبالغ را `Long` می‌گیرند، درحالی‌که `FinanceSubmitData` در schema سرور `int` است. | `ApiInterfaces.kt:29-44`, `AppModels.kt:440-458` | `schemas.py:416-426` و handlerهای `finance.py:656-691,2248-2315` | JSON integer به Long قابل تبدیل است؛ اختلاف wire-type بالقوه، نه failure فعلی. |
| متوسط | پاسخ full profile می‌تواند ردیف unassigned با `course_title=null`/`teacher_name=null` بدهد؛ مدل قدیمی/مصرف‌کننده‌هایی که این دو را non-null می‌گرفتند باید nullable باشند. | مدل اصلاح‌شده `AppModels.kt:500-513` و نمایش `EditStudentActivity.kt:205-233` | `admin.py:510-523`, `reports.py:828-855`, `finance.py:2380-2420` | در HEAD فعلی مدل profile nullable شده؛ این مورد به‌عنوان قرارداد حساس ثبت می‌شود تا مدل دیگری دوباره non-null نشود. |
| نامشخص | `@Url` در `ReportExporter` path runtime دارد و از declaration ثابت قابل مقایسه نیست. | `ReportExporter.kt:24-29,107-130` | route باید از caller `endpointUrl` و `server-routes.csv` تطبیق داده شود | بدون مقدار runtime نمی‌توان یک path یکتا نوشت. |

## 4. اختلاف بدنهٔ درخواست

| شدت | مورد | مرجع |
|---|---|---|
| کم | `InvoiceSubmitData` قدیمی در `AppModels.kt:214-223` `enrollment_id` ندارد، اما مسیر فعال حواله از `FinanceSubmitData` در `AppModels.kt:440-450` استفاده می‌کند. | مدل legacy در اپ؛ schema فعال `schemas.py:416-426` و handler `finance.py:224-456` | نامشخص بودن مصرف مستقیم مدل قدیمی؛ route فعال mismatch ندارد. |
| کم | `StudentRegisterData` و `StudentRegisterAndEnrollRequest` دو payload جدا با فیلدهای اجباری متفاوت دارند؛ route انتخاب‌شدهٔ Activity `students/register_and_enroll` است. | `StudentRegisterActivity.kt:35-39`, `AppModels.kt:600-617` | `routers/students.py` طبق `server-routes.csv` | مسیر legacy register بدون caller مستقیم است؛ نیاز به حذف/تغییر ندارد، فقط مستندسازی شد. |

## 5. نمایش نقش/تجربه

- مورد route-missing یا method/path اختلاف برای declarationهای Retrofit پیدا نشد.
- شرط‌های نقش در هر Activity در screen docs با `file:line` ثبت شده‌اند. بررسی امنیتی انجام نشده است؛ این بخش فقط نمایش و navigation را مقایسه می‌کند.
- `TeacherDashboardActivity` invoice guard به‌عنوان سابقهٔ pre-existing در کار قبلی ثبت شده، اما در این مرحله دوباره تغییر/تحلیل امنیتی انجام نشده است.

## 6. خلاصه شدت

| شدت | تعداد مورد ثبت‌شده در این سند |
|---|---:|
| زیاد | 0 |
| متوسط | 1 قرارداد nullable حساس |
| کم | 5 |
| نامشخص | 1 مورد runtime URL |

هیچ موردی در این فاز fix نشده است.
