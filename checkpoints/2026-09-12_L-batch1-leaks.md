# Checkpoint — L بچ ۱: نشت اطلاعات و دسترسی (L3/L8/L14)

Date: 2026-09-12. Asserted + read-back per step. No compile/run.

## قدم ۱ — L3: حذف کد ملی از لیست پیش‌انتخاب (parent.py:183)
- اپ فقط id+name می‌خواهد (ParentSimpleStudentItem همین دو فیلد؛ انتخاب با id،
  نمایش name) و پورتال وب هم child.id/child.name؛ پس `({national_code})` از نام
  حذف شد. لبه: هم‌نام‌بودن دو فرزند (نادر) دیگر با کد ملی قابل‌تفکیک نیست.

## قدم ۲ — L8: پیجینیشن سازگار (teachers.py:71-101)
- هر دو کالر اپ آرایه‌ی خام می‌خواهند (AddClassApi.getTeachers: List،
  ReportNewApi.getTeachersList: List) پس پاسخ همچنان آرایه‌ی خام ماند (برش‌خورده).
- `skip=0` + `limit=None..200` اختیاری؛ پیش‌فرضِ بدون‌پارامتر = همه مثل قبل (بدون
  شکستن اپ قدیمی)؛ order_by(id) برای پیج پایدار. مهاجرت تدریجی: اپ بعداً limit
  بفرستد؛ آن‌وقت می‌توان دیفالت را هم محدود کرد (فعلاً عمداً نامحدود).

## قدم ۳ — L14: گارد teachers/list (teachers.py:82-93)
- موبایل در response_model هست (schemas.py:269) پس مشکل دسترسی بود: ادمین/منشی
  لیست کامل، معلم فقط خودش (get_logged_in_teacher، مقاوم به تغییر موبایل)،
  شاگرد/والد 403. C9 (حذف password/card/national_code) سر جاست.

## بقیه‌ی bareها (۹۷ مورد، فقط لیست — پروژه‌ی جدا، بدون فیکس)
admin.py :: get_admin_today_summary, get_dashboard_stats, send_sms,
  get_pending_teachers, get_student_full_profile, get_share_config,
  get_pending_classes, get_parent_contacts, get_institute_settings,
  search_admin_students, search_admin_teachers
ai.py :: chat_with_ai_assistant
analytics.py :: get_analytics_dashboard, get_teachers_performance_analytics,
  get_classes_performance_analytics, export_analytics_excel, export_analytics_pdf
attendance.py :: start_live_session, end_live_session, save_live_status,
  get_current_live_session, get_class_attendance, submit_session_and_calculate,
  get_history, get_student_attendance_history, get_session_details,
  edit_past_session, qr_student_check_in, get_admin_live_sessions,
  get_admin_live_session_roster
auth.py :: change_password, logout_user, get_me, register_device_token,
  get_notifications, mark_notification_read, mark_all_notifications_read,
  change_mobile
automation.py :: get_automation_rules, get_automation_logs
branches.py :: list_branches, create_resource, update_resource, list_resources,
  book_resource, get_branch_stats
calendar.py :: get_all_rooms, check_scheduling_conflicts, get_calendar_events
classes.py :: create_class, get_all_classes, get_class_details,
  get_class_full_report, get_class_students_full, request_class_deletion,
  update_class_info
crm.py :: create_crm_lead, get_crm_leads_list, add_lead_notes,
  convert_lead_to_student
exams.py :: get_student_report_card, export_report_card_pdf
finance.py :: search_finance_advanced, print_receipt, generate_pdf_receipt,
  get_student_class_status, initiate_online_payment, get_all_installments,
  send_installment_payment_reminder, get_student_online_payments,
  get_student_physical_transactions, get_student_financial_dashboard,
  get_parent_financial_dashboard, get_receipt_details, get_invoice_details,
  get_debtors_list
reports.py :: get_chart_data, get_financial_summary, get_student_statement,
  print_student_statement, print_student_profile
students.py :: search_students, search_students_simple, submit_grade,
  get_student_grades, get_student_communication_history, get_student_profile,
  get_student_installments, get_student_my_profile
teachers.py :: get_teacher_communication_history, get_teacher_today_summary,
  get_my_classes, get_teacher_incomplete_classes, get_teacher_full_profile,
  get_teacher_profile, get_pending_settlement, get_settlement_history
(توجه: get_all_teachers از این لیست خارج شد — همین بچ گارد گرفت.)
