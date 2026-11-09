# Server–Android API map revalidation

Generated from the current Kotlin Retrofit annotations and the current server route CSV; placeholders are normalized to `{}`.
The historical `docs/app-map/mismatches.md` includes seven routes that now have direct callers in `LiveApi.kt`; this overlay supersedes its old unmatched-route count.

Current classification: **221** server routes; **157** unique static Retrofit calls; **64** server-only routes; **1** dynamic `@Url`; Android-only static calls: **0**.

| method | route | handler/source | current category |
|---|---|---|---|
| DELETE | `attendance/session/{}` | `Kharazmi_Server/routers/attendance.py:1288` (routers.attendance.delete_session_endpoint)` | attendance/live؛ مسیر یا client متفاوت/قدیمی |
| DELETE | `finance/installments/{}` | `Kharazmi_Server/routers/finance.py:1764` (routers.finance.delete_installment)` | مدیریت قسط؛ UI فعلی declaration مستقیم ندارد |
| DELETE | `messages/{}` | `Kharazmi_Server/routers/messages.py:221` (routers.messages.delete_own_message)` | پیام‌رسان؛ delete مستقیم در UI پیدا نشد |
| GET | `admin/pricing_table` | `Kharazmi_Server/routers/admin.py:2044` (routers.admin.get_pricing_table)` | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| GET | `admin/transactions/list/excel` | `Kharazmi_Server/routers/admin.py:793` (routers.admin.get_transactions_excel)` | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| GET | `analytics/classes` | `Kharazmi_Server/routers/analytics.py:355` (routers.analytics.get_classes_performance_analytics)` | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| GET | `analytics/dashboard` | `Kharazmi_Server/routers/analytics.py:152` (routers.analytics.get_analytics_dashboard)` | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| GET | `analytics/export/excel` | `Kharazmi_Server/routers/analytics.py:396` (routers.analytics.export_analytics_excel)` | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| GET | `analytics/export/pdf` | `Kharazmi_Server/routers/analytics.py:529` (routers.analytics.export_analytics_pdf)` | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| GET | `analytics/teachers` | `Kharazmi_Server/routers/analytics.py:294` (routers.analytics.get_teachers_performance_analytics)` | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| GET | `automation/logs` | `Kharazmi_Server/routers/automation.py:125` (routers.automation.get_automation_logs)` | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| GET | `automation/rules` | `Kharazmi_Server/routers/automation.py:117` (routers.automation.get_automation_rules)` | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| GET | `branches` | `Kharazmi_Server/routers/branches.py:113` (routers.branches.list_branches)` | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| GET | `classes/pending_approval` | `Kharazmi_Server/routers/classes.py:1304` (routers.classes.pending_classes_for_admin)` | admin/export؛ declaration مستقیم ندارد |
| GET | `classes/{}/students_full/excel` | `Kharazmi_Server/routers/classes.py:710` (routers.classes.get_class_students_excel)` | admin/export؛ declaration مستقیم ندارد |
| GET | `dashboard/branch_stats` | `Kharazmi_Server/routers/branches.py:229` (routers.branches.get_branch_stats)` | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| GET | `dashboard/push_status` | `Kharazmi_Server/routers/dashboard.py:157` (routers.dashboard.get_push_status)` | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| GET | `dashboard/stats` | `Kharazmi_Server/routers/admin.py:51` (routers.admin.get_dashboard_stats)` | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| GET | `finance/installments` | `Kharazmi_Server/routers/finance.py:1588` (routers.finance.get_all_installments)` | مدیریت قسط؛ UI فعلی declaration مستقیم ندارد |
| GET | `finance/invoice/{}` | `Kharazmi_Server/routers/finance.py:2264` (routers.finance.get_invoice_details)` | caller مستقیم در Retrofit پیدا نشد؛ علت نامشخص |
| GET | `finance/mock_payment_page` | `Kharazmi_Server/routers/finance.py:1355` (routers.finance.mock_payment_page)` | مالی/درگاه/legacy؛ مسیر مستقیم فعلی متفاوت است |
| GET | `finance/parent/dashboard` | `Kharazmi_Server/routers/finance.py:2189` (routers.finance.get_parent_financial_dashboard)` | وب/پرتال؛ caller Android مستقیم ندارد |
| GET | `finance/payment/callback` | `Kharazmi_Server/routers/finance.py:879` (routers.finance.payment_callback)` | مالی/درگاه/legacy؛ مسیر مستقیم فعلی متفاوت است |
| GET | `finance/reports/debtors_list` | `Kharazmi_Server/routers/finance.py:2486` (routers.finance.get_debtors_list)` | گزارش/خروجی داخلی؛ declaration مستقیم ندارد |
| GET | `finance/reports/revenue_summary` | `Kharazmi_Server/routers/finance.py:2654` (routers.finance.get_revenue_summary)` | گزارش/خروجی داخلی؛ declaration مستقیم ندارد |
| GET | `finance/reports/teacher_settlements_summary` | `Kharazmi_Server/routers/finance.py:2709` (routers.finance.get_teacher_settlements_summary)` | گزارش/خروجی داخلی؛ declaration مستقیم ندارد |
| GET | `finance/student/{}/payments` | `Kharazmi_Server/routers/finance.py:2021` (routers.finance.get_student_online_payments)` | مالی/درگاه/legacy؛ مسیر مستقیم فعلی متفاوت است |
| GET | `finance/student/{}/transactions` | `Kharazmi_Server/routers/finance.py:2047` (routers.finance.get_student_physical_transactions)` | مالی/درگاه/legacy؛ مسیر مستقیم فعلی متفاوت است |
| GET | `parent/portal` | `Kharazmi_Server/routers/parent.py:448` (routers.parent.get_parent_portal_page)` | وب/پرتال؛ caller Android مستقیم ندارد |
| GET | `reports/debtors` | `Kharazmi_Server/routers/reports.py:446` (routers.reports.get_debtors_report)` | گزارش/خروجی داخلی؛ declaration مستقیم ندارد |
| GET | `reports/debtors/excel` | `Kharazmi_Server/routers/reports.py:477` (routers.reports.get_debtors_excel)` | گزارش/خروجی داخلی؛ declaration مستقیم ندارد |
| GET | `reports/financial` | `Kharazmi_Server/routers/reports.py:314` (routers.reports.get_financial_report)` | گزارش/خروجی داخلی؛ declaration مستقیم ندارد |
| GET | `reports/student_profile/print` | `Kharazmi_Server/routers/reports.py:1067` (routers.reports.print_student_profile)` | گزارش/خروجی داخلی؛ declaration مستقیم ندارد |
| GET | `reports/student_statement/print` | `Kharazmi_Server/routers/reports.py:883` (routers.reports.print_student_statement)` | گزارش/خروجی داخلی؛ declaration مستقیم ندارد |
| GET | `resources` | `Kharazmi_Server/routers/branches.py:171` (routers.branches.list_resources)` | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| GET | `students/search` | `Kharazmi_Server/routers/students.py:264` (routers.students.search_students)` | مسیر students قدیمی/موازی؛ UI مسیر دیگری دارد |
| GET | `students/{}/report_card/pdf` | `Kharazmi_Server/routers/exams.py:383` (routers.exams.export_report_card_pdf)` | PDF با URL runtime؛ declaration Retrofit ندارد |
| GET | `teachers/list/excel` | `Kharazmi_Server/routers/teachers.py:668` (routers.teachers.get_teachers_excel)` | گزارش/خروجی داخلی؛ declaration مستقیم ندارد |
| GET | `test/debt_calculation` | `Kharazmi_Server/routers/admin.py:98` (routers.admin.test_debt_calculation)` | diagnostic/test route |
| GET | `uploads/{}` | `Kharazmi_Server/main.py:94` (main.serve_upload)` | فایل/URL runtime؛ Retrofit JSON نیست |
| POST | `ai/chat` | `Kharazmi_Server/routers/ai.py:153` (routers.ai.chat_with_ai_assistant)` | ابزار داخلی AI؛ declaration مستقیم ندارد |
| POST | `attendance/get` | `Kharazmi_Server/routers/attendance.py:585` (routers.attendance.get_class_attendance)` | attendance/live؛ مسیر یا client متفاوت/قدیمی |
| POST | `attendance/qr_check-in` | `Kharazmi_Server/routers/attendance.py:1353` (routers.attendance.qr_student_check_in)` | attendance/live؛ مسیر یا client متفاوت/قدیمی |
| POST | `automation/rules` | `Kharazmi_Server/routers/automation.py:66` (routers.automation.create_automation_rule)` | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| POST | `automation/run_rules` | `Kharazmi_Server/routers/automation.py:143` (routers.automation.run_automation_engine)` | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| POST | `branches` | `Kharazmi_Server/routers/branches.py:52` (routers.branches.create_branch)` | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| POST | `branches/{}/suspend` | `Kharazmi_Server/routers/branches.py:96` (routers.branches.suspend_branch)` | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| POST | `crm/register_online` | `Kharazmi_Server/routers/crm.py:253` (routers.crm.public_online_registration)` | وب/پرتال؛ caller Android مستقیم ندارد |
| POST | `exams/create` | `Kharazmi_Server/routers/exams.py:45` (routers.exams.create_exam)` | جریان learner؛ caller مستقیم در Android admin پیدا نشد |
| POST | `exams/{}/questions` | `Kharazmi_Server/routers/exams.py:95` (routers.exams.add_exam_question)` | جریان learner؛ caller مستقیم در Android admin پیدا نشد |
| POST | `finance/debtors/remind` | `Kharazmi_Server/routers/finance.py:2576` (routers.finance.remind_debtors)` | مالی/درگاه/legacy؛ مسیر مستقیم فعلی متفاوت است |
| POST | `finance/payment/initiate` | `Kharazmi_Server/routers/finance.py:799` (routers.finance.initiate_online_payment)` | مالی/درگاه/legacy؛ مسیر مستقیم فعلی متفاوت است |
| POST | `finance/transaction/{}/refund` | `Kharazmi_Server/routers/finance.py:1394` (routers.finance.refund_transaction)` | مالی/درگاه/legacy؛ مسیر مستقیم فعلی متفاوت است |
| POST | `homework/submissions/{}/submit` | `Kharazmi_Server/routers/homework.py:186` (routers.homework.submit_homework_file)` | جریان learner؛ caller مستقیم در Android admin پیدا نشد |
| POST | `resources` | `Kharazmi_Server/routers/branches.py:125` (routers.branches.create_resource)` | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| POST | `resources/bookings` | `Kharazmi_Server/routers/branches.py:183` (routers.branches.book_resource)` | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| POST | `sms/send_bulk` | `Kharazmi_Server/routers/admin.py:1495` (routers.admin.send_bulk_sms)` | پیامک؛ bulk route با UI ارسال معمولی متفاوت است |
| POST | `students/register` | `Kharazmi_Server/routers/students.py:40` (routers.students.register_student)` | مسیر students قدیمی/موازی؛ UI مسیر دیگری دارد |
| POST | `test/transaction_logic` | `Kharazmi_Server/routers/admin.py:1338` (routers.admin.test_transaction_logic)` | diagnostic/test route |
| PUT | `admin/pricing_table` | `Kharazmi_Server/routers/admin.py:2050` (routers.admin.update_pricing_table)` | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| PUT | `automation/rules/{}` | `Kharazmi_Server/routers/automation.py:93` (routers.automation.update_automation_rule)` | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| PUT | `branches/{}` | `Kharazmi_Server/routers/branches.py:75` (routers.branches.update_branch)` | ابزار داخلی/admin؛ declaration مستقیم ندارد |
| PUT | `finance/installments/{}` | `Kharazmi_Server/routers/finance.py:1698` (routers.finance.update_installment)` | مدیریت قسط؛ UI فعلی declaration مستقیم ندارد |
| PUT | `resources/{}` | `Kharazmi_Server/routers/branches.py:149` (routers.branches.update_resource)` | ابزار داخلی/admin؛ declaration مستقیم ندارد |

## Retrofit dynamic URL

`DownloadApi.downloadFile(@Url url)` remains runtime-selected and is not counted as a fixed method/path pair. Source: `ReportExporter.kt` (see the current declaration inventory CSV).
