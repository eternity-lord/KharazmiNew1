# TeacherDashboardActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/TeacherDashboardActivity.kt:60`
- layout و محل bind:
  - `R.layout.activity_teacher_dashboard` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/TeacherDashboardActivity.kt:72`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_eacher_dashboard.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 84 | `btnLogout` | `findViewById<ImageView>(R.id.btnLogout).setOnClickListener { finish() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 87 | `btnRefresh` | `findViewById<ImageView>(R.id.btnRefresh).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 91 | `id نامشخص` | `Toast.makeText(this, getString(R.string.tdash_updated), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 95 | `cardRegisterStudent` | `findViewById<MaterialCardView>(R.id.cardRegisterStudent).setOnClickListener {` | Intent → StudentRegisterActivity |
| 96 | `cardRegisterStudent` | `startActivity(Intent(this, StudentRegisterActivity::class.java))` | Intent → StudentRegisterActivity |
| 100 | `cardRegisterClass` | `findViewById<MaterialCardView>(R.id.cardRegisterClass).setOnClickListener {` | Intent → AddClassActivity |
| 104 | `id نامشخص` | `startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 108 | `cardAttendance` | `findViewById<MaterialCardView>(R.id.cardAttendance).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 112 | `id نامشخص` | `.setItems(options) { _, which ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 114 | `id نامشخص` | `0 -> Toast.makeText(this, getString(R.string.tdash_pick_class), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 118 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 139 | `id نامشخص` | `cardFastInvoice.setOnClickListener {` | Intent → InvoiceActivity |
| 141 | `id نامشخص` | `startActivity(intent)` | Intent → InvoiceActivity |
| 147 | `cardPendingApproval` | `findViewById<MaterialCardView>(R.id.cardPendingApproval).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 153 | `cardIncompleteClasses` | `findViewById<MaterialCardView>(R.id.cardIncompleteClasses).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 158 | `cardReports` | `findViewById<MaterialCardView>(R.id.cardReports).setOnClickListener {` | Intent → ReportActivity |
| 160 | `cardReports` | `startActivity(intent)` | Intent → ReportActivity |
| 182 | `id نامشخص` | `.setItems(rows, null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 183 | `id نامشخص` | `.setPositiveButton(getString(R.string.common_ok), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 184 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 275 | `id نامشخص` | `actionButton.setOnClickListener { openTodayLiveClass(live) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 291 | `id نامشخص` | `actionButton.setOnClickListener { startUpcomingLiveClass(next) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 296 | `id نامشخص` | `actionButton.setOnClickListener(null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 307 | `id نامشخص` | `startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 315 | `id نامشخص` | `startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 331 | `cardStartLive` | `card.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 356 | `id نامشخص` | `startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 367 | `id نامشخص` | `Toast.makeText(this@TeacherDashboardActivity, getString(R.string.tdash_no_class), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 373 | `id نامشخص` | `.setItems(names) { _, which ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 377 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 383 | `id نامشخص` | `Toast.makeText(this@TeacherDashboardActivity, getString(R.string.tdash_class_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 394 | `id نامشخص` | `startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 404 | `id نامشخص` | `Toast.makeText(this@TeacherDashboardActivity, getString(R.string.tdash_no_partial), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 411 | `id نامشخص` | `.setItems(names) { _, which ->` | Intent → ClassSetupActivity |
| 416 | `id نامشخص` | `startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 418 | `id نامشخص` | `.setPositiveButton(getString(R.string.btn_dismiss), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 419 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 425 | `id نامشخص` | `Toast.makeText(this@TeacherDashboardActivity, getString(R.string.tdash_partial_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 440 | `id نامشخص` | `.setPositiveButton(getString(R.string.main_edit_session_go)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 448 | `id نامشخص` | `startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 450 | `id نامشخص` | `Toast.makeText(this, getString(R.string.main_session_invalid), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 453 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 454 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 468 | `id نامشخص` | `Toast.makeText(this@TeacherDashboardActivity, getString(R.string.common_class_activate), Toast.LENGTH_LONG).show()` | Intent → ClassDetailActivity |
| 474 | `id نامشخص` | `startActivity(intent)` | Intent → ClassSetupActivity |
| 480 | `id نامشخص` | `startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 617 | `id نامشخص` | `holder.itemView.setOnClickListener { onClick(item) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 191 | `val pending_classes = api.getPendingClasses(teacherId)` | `GET admin/pending_classes, GET teachers/{teacher_id}/pending_classes` |
| 363 | `val classes = api.getMyClasses(teacherId)` | `GET teachers/{id}/classes` |
| 401 | `val list = api.getTeacherIncompleteClasses(teacherId)` | `GET teachers/{id}/incomplete_classes` |
| 461 | `val list = api.getMyClasses(teacherId)` | `GET teachers/{id}/classes` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 77 | `findViewById<TextView>(R.id.tvWelcome).text = getString(R.string.tdash_welcome, teacherName)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 197 | `text.text = pending_classes.joinToString("\n") {` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 250 | `findViewById<TextView>(R.id.tvTeacherWeekSessions).text =` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 252 | `findViewById<TextView>(R.id.tvTeacherWeekUnsettled).text =` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 272 | `statusText.text = getString(R.string.tdash_live_now, live.className, live.elapsedMinutes)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 274 | `actionButton.text = getString(R.string.tdash_go_attendance)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 288 | `statusText.text = getString(R.string.tdash_next, next.className, next.scheduledTime)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 290 | `actionButton.text = getString(R.string.tdash_start_class)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 340 | `tvTitle.text = getString(R.string.tdash_banner_live, cur.classTitle.ifEmpty { getString(R.string.tdash_class_fallback) })` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 341 | `tvSub.text = getString(R.string.tdash_banner_back)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 343 | `tvTitle.text = getString(R.string.tdash_banner_start)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 344 | `tvSub.text = getString(R.string.tdash_banner_sub)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 466 | `rv.adapter = TeacherClassAdapter(list, isAdminUser = isAdminUser) { selectedClass ->` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 546 | `holder.title.text = classTitle.ifEmpty { classCode }` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 548 | `holder.code.text = holder.itemView.context.getString(R.string.tdash_code_row, classCode)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 567 | `holder.status.text = holder.itemView.context.getString(R.string.tdash_suspended)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 569 | `holder.sub.text = item.grade_level?.trim().orEmpty()` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 572 | `holder.status.text = holder.itemView.context.getString(R.string.tdash_active)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 574 | `holder.sub.text = item.grade_level?.trim().orEmpty()` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 577 | `holder.status.text = holder.itemView.context.getString(R.string.tdash_pending)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 579 | `holder.sub.text = item.grade_level?.trim().orEmpty()` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 585 | `holder.tvTotalDebt.text = String.format("%,d", item.total_debt)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 586 | `holder.tvTeacherDebt.text = String.format("%,d", item.debt_to_teacher)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 587 | `holder.tvInstituteDebt.text = String.format("%,d", item.debt_to_institute)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 602 | `tv.text = holder.itemView.context.getString(R.string.common_bullet_row, name)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 610 | `tv.text = holder.itemView.context.getString(R.string.tdash_no_students)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
