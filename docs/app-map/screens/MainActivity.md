# MainActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/MainActivity.kt:75`
- layout و محل bind:
  - `R.layout.activity_main` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/MainActivity.kt:99`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_ain.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 159 | `tvTodaySummaryTitle` | `findViewById<TextView>(R.id.tvTodaySummaryTitle).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 164 | `imgHeaderDashboardIcon` | `findViewById<ImageView>(R.id.imgHeaderDashboardIcon).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 172 | `nav_approve_class, nav_dashboard, nav_deletion_requests, nav_share_config` | `R.id.nav_approve_class -> startActivity(Intent(this, PendingClassesActivity::class.java))` | Intent → PendingClassesActivity, DeletionRequestsActivity, ShareConfigActivity |
| 173 | `nav_approve_class, nav_dashboard, nav_deletion_requests, nav_pending, nav_share_config` | `R.id.nav_deletion_requests -> startActivity(Intent(this, DeletionRequestsActivity::class.java))` | Intent → PendingClassesActivity, DeletionRequestsActivity, ShareConfigActivity, PendingTeachersActivity |
| 174 | `nav_approve_class, nav_attendance, nav_deletion_requests, nav_pending, nav_share_config` | `R.id.nav_share_config -> startActivity(Intent(this, ShareConfigActivity::class.java))` | Intent → PendingClassesActivity, DeletionRequestsActivity, ShareConfigActivity, PendingTeachersActivity, AttendanceActivity |
| 175 | `nav_attendance, nav_deletion_requests, nav_pending, nav_report, nav_share_config` | `R.id.nav_pending -> startActivity(Intent(this, PendingTeachersActivity::class.java))` | Intent → DeletionRequestsActivity, ShareConfigActivity, PendingTeachersActivity, AttendanceActivity, ReportActivity |
| 176 | `nav_attendance, nav_chart, nav_pending, nav_report, nav_share_config` | `R.id.nav_attendance -> startActivity(Intent(this, AttendanceActivity::class.java))` | Intent → ShareConfigActivity, PendingTeachersActivity, AttendanceActivity, ReportActivity, ChartActivity |
| 177 | `nav_attendance, nav_chart, nav_pending, nav_report, nav_sms` | `R.id.nav_report -> startActivity(Intent(this, ReportActivity::class.java))` | Intent → PendingTeachersActivity, AttendanceActivity, ReportActivity, ChartActivity, SmsActivity |
| 178 | `nav_attendance, nav_chart, nav_report, nav_settings, nav_sms` | `R.id.nav_chart -> startActivity(Intent(this, ChartActivity::class.java))` | Intent → AttendanceActivity, ReportActivity, ChartActivity, SmsActivity, SettingsActivity |
| 179 | `nav_chart, nav_report, nav_settings, nav_sms` | `R.id.nav_sms -> startActivity(Intent(this, SmsActivity::class.java))` | Intent → ReportActivity, ChartActivity, SmsActivity, SettingsActivity |
| 180 | `nav_chart, nav_settings, nav_sms` | `R.id.nav_settings -> startActivity(Intent(this, SettingsActivity::class.java))` | Intent → ChartActivity, SmsActivity, SettingsActivity |
| 183 | `nav_deleted_classes, nav_institute_settings, nav_notifications` | `R.id.nav_notifications -> startActivity(Intent(this, NotificationCenterActivity::class.java))` | Intent → NotificationCenterActivity, InstituteSettingsActivity |
| 184 | `nav_audit_radar, nav_deleted_classes, nav_institute_settings, nav_notifications` | `R.id.nav_institute_settings -> startActivity(Intent(this, InstituteSettingsActivity::class.java))` | Intent → NotificationCenterActivity, InstituteSettingsActivity |
| 188 | `nav_audit_radar` | `Toast.makeText(this, getString(R.string.common_no_access), Toast.LENGTH_SHORT).show()` | Intent → AuditDashboardActivity |
| 190 | `id نامشخص` | `startActivity(Intent(this, AuditDashboardActivity::class.java))` | Intent → AuditDashboardActivity |
| 195 | `nav_dunning` | `Toast.makeText(this, getString(R.string.common_no_access), Toast.LENGTH_SHORT).show()` | Intent → DunningActivity |
| 197 | `id نامشخص` | `startActivity(Intent(this, DunningActivity::class.java))` | Intent → DunningActivity |
| 202 | `nav_admin_dashboard` | `Toast.makeText(this, getString(R.string.common_no_access), Toast.LENGTH_SHORT).show()` | Intent → AdminDashboardActivity |
| 204 | `id نامشخص` | `startActivity(Intent(this, AdminDashboardActivity::class.java))` | Intent → AdminDashboardActivity |
| 209 | `nav_classes, nav_havale` | `startActivity(intent)` | Intent → InvoiceActivity, ClassManagementActivity |
| 211 | `nav_classes, nav_parents, nav_register` | `R.id.nav_classes -> startActivity(Intent(this, ClassManagementActivity::class.java))` | Intent → ClassManagementActivity, ParentContactsActivity |
| 212 | `nav_classes, nav_parents, nav_register` | `R.id.nav_parents -> startActivity(Intent(this, ParentContactsActivity::class.java))` | Intent → ClassManagementActivity, ParentContactsActivity |
| 231 | `menu_1_dashboard` | `findViewById<View>(R.id.menu_1_dashboard).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 232 | `menu_1_dashboard` | `Toast.makeText(this, getString(R.string.main_already_home), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 236 | `menu_2_register` | `findViewById<View>(R.id.menu_2_register).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 241 | `menu_3_students` | `findViewById<View>(R.id.menu_3_students).setOnClickListener {` | Intent → PersonListActivity |
| 243 | `menu_3_students` | `startActivity(intent)` | Intent → PersonListActivity |
| 247 | `menu_4_teachers` | `findViewById<View>(R.id.menu_4_teachers).setOnClickListener {` | Intent → PersonListActivity |
| 249 | `menu_4_teachers` | `startActivity(intent)` | Intent → PersonListActivity |
| 253 | `menu_5_management` | `findViewById<View>(R.id.menu_5_management).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 258 | `menu_6_reports` | `findViewById<View>(R.id.menu_6_reports).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 260 | `menu_6_reports` | `Toast.makeText(this, getString(R.string.common_no_access), Toast.LENGTH_SHORT).show()` | Intent → ReportActivity |
| 262 | `id نامشخص` | `startActivity(Intent(this, ReportActivity::class.java))` | Intent → ReportActivity |
| 267 | `menu_7_sms` | `findViewById<View>(R.id.menu_7_sms).setOnClickListener {` | Intent → SmsActivity |
| 268 | `menu_7_sms` | `startActivity(Intent(this, SmsActivity::class.java))` | Intent → SmsActivity |
| 272 | `menu_8_settings` | `findViewById<View>(R.id.menu_8_settings).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 274 | `menu_8_settings` | `Toast.makeText(this, getString(R.string.common_no_access), Toast.LENGTH_SHORT).show()` | Intent → InstituteSettingsActivity |
| 276 | `id نامشخص` | `startActivity(Intent(this, InstituteSettingsActivity::class.java))` | Intent → InstituteSettingsActivity |
| 281 | `menu_9_quick_invoice` | `findViewById<View>(R.id.menu_9_quick_invoice).setOnClickListener {` | Intent → InvoiceActivity |
| 283 | `menu_9_quick_invoice` | `startActivity(intent)` | Intent → InvoiceActivity |
| 287 | `menu_10_statement` | `findViewById<View>(R.id.menu_10_statement).setOnClickListener {` | Intent → ReportActivity |
| 288 | `menu_10_statement` | `startActivity(Intent(this, ReportActivity::class.java))` | Intent → ReportActivity |
| 292 | `menu_11_grades` | `findViewById<View>(R.id.menu_11_grades).setOnClickListener {` | Intent → SubmitGradeActivity |
| 293 | `menu_11_grades` | `startActivity(Intent(this, SubmitGradeActivity::class.java))` | Intent → SubmitGradeActivity |
| 297 | `menu_12_sessions` | `findViewById<View>(R.id.menu_12_sessions).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 302 | `menu_13_live` | `findViewById<View>(R.id.menu_13_live).setOnClickListener {` | Intent → LiveClassesActivity |
| 303 | `menu_13_live` | `startActivity(Intent(this, LiveClassesActivity::class.java))` | Intent → LiveClassesActivity |
| 307 | `menu_14_audit` | `findViewById<View>(R.id.menu_14_audit)?.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 309 | `menu_14_audit` | `Toast.makeText(this, getString(R.string.common_no_access), Toast.LENGTH_SHORT).show()` | Intent → AuditDashboardActivity |
| 311 | `id نامشخص` | `startActivity(Intent(this, AuditDashboardActivity::class.java))` | Intent → AuditDashboardActivity |
| 315 | `menu_15_dunning` | `findViewById<View>(R.id.menu_15_dunning)?.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 317 | `menu_15_dunning` | `Toast.makeText(this, getString(R.string.common_no_access), Toast.LENGTH_SHORT).show()` | Intent → DunningActivity |
| 319 | `id نامشخص` | `startActivity(Intent(this, DunningActivity::class.java))` | Intent → DunningActivity |
| 323 | `menu_16_dashboard` | `findViewById<View>(R.id.menu_16_dashboard)?.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 325 | `menu_16_dashboard` | `Toast.makeText(this, getString(R.string.common_no_access), Toast.LENGTH_SHORT).show()` | Intent → AdminDashboardActivity |
| 327 | `id نامشخص` | `startActivity(Intent(this, AdminDashboardActivity::class.java))` | Intent → AdminDashboardActivity |
| 407 | `id نامشخص` | `lateContainer.setOnClickListener(null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 419 | `id نامشخص` | `lateContainer.setOnClickListener { showLateClassDetails() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 458 | `btnInstallmentAlerts` | `findViewById<View>(R.id.btnInstallmentAlerts).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 469 | `btnTeacherSettlementAlerts` | `findViewById<View>(R.id.btnTeacherSettlementAlerts).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 487 | `id نامشخص` | `.setItems(labels) { _, which -> openStudentInstallments(currentInstallmentAlerts[which]) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 488 | `id نامشخص` | `.setNegativeButton(getString(R.string.btn_dismiss), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 489 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 493 | `id نامشخص` | `startActivity(Intent(this, StudentProfileActivity::class.java).apply {` | Intent → StudentProfileActivity |
| 507 | `id نامشخص` | `.setItems(labels) { _, which ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 510 | `id نامشخص` | `.setNegativeButton(getString(R.string.btn_dismiss), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 511 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 515 | `id نامشخص` | `startActivity(Intent(this, TeacherProfileActivity::class.java).apply {` | Intent → TeacherProfileActivity |
| 533 | `id نامشخص` | `.setItems(labels) { _, which -> openClassDetails(currentLateClasses[which]) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 534 | `id نامشخص` | `.setNegativeButton(getString(R.string.btn_dismiss), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 535 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 543 | `id نامشخص` | `startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 572 | `id نامشخص` | `.setItems(options) { _, which ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 575 | `id نامشخص` | `0 -> startActivity(Intent(this, ClassManagementActivity::class.java))` | Intent → ClassManagementActivity, AddClassActivity |
| 576 | `id نامشخص` | `1 -> startActivity(Intent(this, AddClassActivity::class.java).apply { putExtra("IS_ADMIN_MODE", true) })` | Intent → ClassManagementActivity, AddClassActivity |
| 580 | `id نامشخص` | `0 -> startActivity(Intent(this, TransactionManageActivity::class.java))` | Intent → TransactionManageActivity, ShareConfigActivity, PendingTeachersActivity |
| 581 | `id نامشخص` | `1 -> startActivity(Intent(this, ShareConfigActivity::class.java))` | Intent → TransactionManageActivity, ShareConfigActivity, PendingTeachersActivity, ClassManagementActivity |
| 582 | `id نامشخص` | `2 -> startActivity(Intent(this, PendingTeachersActivity::class.java))` | Intent → TransactionManageActivity, ShareConfigActivity, PendingTeachersActivity, ClassManagementActivity, PendingClassesActivity |
| 583 | `id نامشخص` | `3 -> startActivity(Intent(this, ClassManagementActivity::class.java))` | Intent → ShareConfigActivity, PendingTeachersActivity, ClassManagementActivity, PendingClassesActivity |
| 584 | `id نامشخص` | `4 -> startActivity(Intent(this, PendingClassesActivity::class.java))` | Intent → PendingTeachersActivity, ClassManagementActivity, PendingClassesActivity, CrmLeadsActivity |
| 586 | `id نامشخص` | `6 -> startActivity(Intent(this, CrmLeadsActivity::class.java))` | Intent → PendingClassesActivity, CrmLeadsActivity, AuditDashboardActivity, DunningActivity |
| 587 | `id نامشخص` | `7 -> startActivity(Intent(this, AuditDashboardActivity::class.java))` | Intent → CrmLeadsActivity, AuditDashboardActivity, DunningActivity, AdminDashboardActivity |
| 588 | `id نامشخص` | `8 -> startActivity(Intent(this, DunningActivity::class.java))` | Intent → CrmLeadsActivity, AuditDashboardActivity, DunningActivity, AdminDashboardActivity |
| 589 | `id نامشخص` | `9 -> startActivity(Intent(this, AdminDashboardActivity::class.java))` | Intent → AuditDashboardActivity, DunningActivity, AdminDashboardActivity |
| 593 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 620 | `id نامشخص` | `.setItems(options) { _, which ->` | Intent → StudentRegisterActivity |
| 622 | `id نامشخص` | `0 -> startActivity(Intent(this, StudentRegisterActivity::class.java))` | Intent → StudentRegisterActivity, TeacherRegisterActivity |
| 623 | `id نامشخص` | `1 -> startActivity(Intent(this, TeacherRegisterActivity::class.java))` | Intent → StudentRegisterActivity, TeacherRegisterActivity |
| 626 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 640 | `id نامشخص` | `Toast.makeText(this@MainActivity, getString(R.string.main_trash_empty), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 662 | `id نامشخص` | `.setItems(labels, { _, which -> showArchivedClassDetail(list[which].id) })` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 663 | `id نامشخص` | `.setPositiveButton(getString(R.string.btn_dismiss), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 664 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 670 | `id نامشخص` | `Toast.makeText(this@MainActivity, getString(R.string.main_trash_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 709 | `id نامشخص` | `.setPositiveButton(getString(R.string.btn_dismiss), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 710 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 716 | `id نامشخص` | `Toast.makeText(this@MainActivity, getString(R.string.main_trash_detail_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 728 | `id نامشخص` | `.setPositiveButton(getString(R.string.main_trash_restore)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 731 | `id نامشخص` | `.setNegativeButton(getString(R.string.btn_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 732 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 750 | `id نامشخص` | `.setPositiveButton(R.string.common_ok, null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 751 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 755 | `id نامشخص` | `Toast.makeText(this@MainActivity, msg, Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 764 | `id نامشخص` | `Toast.makeText(this@MainActivity, getString(R.string.main_trash_restore_fail), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 779 | `id نامشخص` | `.setPositiveButton(getString(R.string.main_edit_session_go)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 787 | `id نامشخص` | `startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 789 | `id نامشخص` | `Toast.makeText(this, getString(R.string.main_session_invalid), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 792 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 793 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 338 | `val list = api.getLiveSessions()` | `نامشخص در declarationهای Retrofit` |
| 373 | `api.getAdminTodaySummary()` | `GET admin/today_summary` |
| 604 | `val settings = api.getSettings()` | `GET admin/institute_settings, GET admin/institute_settings` |
| 637 | `val list = api.getDeletedClasses()` | `GET admin/deleted_classes` |
| 684 | `val detail = api.getArchivedClassDetail(courseId)` | `GET admin/deleted_classes/{id}` |
| 741 | `val result = api.restoreArchivedClass(courseId, ClassRestoreRequest())` | `POST admin/deleted_classes/{id}/restore` |
| 902 | `val me = api.getMe()` | `GET auth/me, GET auth/me` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 92 | `tvHeaderLiveClock.text = timeStr` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 109 | `tvHeaderShamsiDate.text = getCurrentShamsiDate()` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 344 | `tvLiveCount.text = getString(R.string.main_live_count, count)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 347 | `tvLiveCount.text = getString(R.string.main_live)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 391 | `findViewById<TextView>(R.id.tvTodayClassesValue).text = summary.scheduledClasses.toString()` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 392 | `findViewById<TextView>(R.id.tvTodayClassesSub).text = getString(R.string.main_started, summary.startedClasses)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 393 | `findViewById<TextView>(R.id.tvTodayEnrollmentsValue).text = summary.todayEnrollments.toString()` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 396 | `paymentValue.text = if (summary.paymentVisible && summary.todayPayments != null) {` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 414 | `lateText.text = if (remaining > 0) {` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 455 | `findViewById<TextView>(R.id.tvInstallmentAlertSummary).text =` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 466 | `findViewById<TextView>(R.id.tvTeacherSettlementAlertSummary).text =` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 606 | `tvHeaderMainTitle.text = settings.name` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
