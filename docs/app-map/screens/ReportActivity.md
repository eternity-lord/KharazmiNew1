# ReportActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ReportActivity.kt:142`
- layout و محل bind:
  - `R.layout.activity_report` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ReportActivity.kt:193`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_eport.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 256 | `rbScopeTeacher` | `rgReportScope.setOnCheckedChangeListener { _, checkedId ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 268 | `id نامشخص` | `btnFetchFinancialSummary.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 272 | `id نامشخص` | `btnExportFinancial.setOnClickListener { exportFinancialReport() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 275 | `id نامشخص` | `btnSearchStudentStatement.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 280 | `id نامشخص` | `btnPrintStatement.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 283 | `id نامشخص` | `} ?: Toast.makeText(this, getString(R.string.rpt_no_student), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 345 | `id نامشخص` | `acTeacherFilter.setOnClickListener { acTeacherFilter.showDropDown() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 347 | `id نامشخص` | `acTeacherFilter.setOnItemClickListener { _, _, position, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 362 | `id نامشخص` | `Toast.makeText(this@ReportActivity, getString(R.string.rpt_tutors_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 382 | `id نامشخص` | `onStart = { Toast.makeText(this, "در حال ساخت خروجی Excel…", Toast.LENGTH_SHORT).show() },` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 383 | `id نامشخص` | `onComplete = { Toast.makeText(this, "خروجی Excel آماده و قابل اشتراک‌گذاری شد", Toast.LENGTH_LONG).show() },` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 384 | `id نامشخص` | `onError = { error -> Toast.makeText(this, "خروجی Excel ناموفق بود: $error", Toast.LENGTH_LONG).show() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 402 | `id نامشخص` | `Toast.makeText(this, getString(R.string.rpt_pick_tutor), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 453 | `id نامشخص` | `Toast.makeText(this@ReportActivity, getString(R.string.rpt_calc_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 462 | `id نامشخص` | `Toast.makeText(this, getString(R.string.rpt_enter_name), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 476 | `id نامشخص` | `Toast.makeText(this@ReportActivity, getString(R.string.rpt_student_nf), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 490 | `id نامشخص` | `Toast.makeText(this@ReportActivity, getString(R.string.rpt_search_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 500 | `id نامشخص` | `.setItems(names) { _, which ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 505 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 506 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 519 | `id نامشخص` | `tvStatementStudentName.setOnClickListener {` | Intent → StudentProfileActivity |
| 520 | `id نامشخص` | `startActivity(Intent(this@ReportActivity, StudentProfileActivity::class.java).apply {` | Intent → StudentProfileActivity |
| 533 | `id نامشخص` | `tvStatementTeacher.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 535 | `id نامشخص` | `if (teacherRows.isEmpty()) return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 541 | `id نامشخص` | `.setItems(labels) { _, which ->` | Intent → TeacherProfileActivity |
| 543 | `id نامشخص` | `startActivity(Intent(this@ReportActivity, TeacherProfileActivity::class.java).apply {` | Intent → TeacherProfileActivity |
| 548 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 549 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 558 | `id نامشخص` | `btnStatementPay.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 563 | `id نامشخص` | `Toast.makeText(this@ReportActivity, "برای پرداخت، کلاس فعالی وجود ندارد", Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 564 | `id نامشخص` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 572 | `id نامشخص` | `Toast.makeText(this@ReportActivity, "برای بدهی بدون کلاس امکان ثبت پرداخت کلاس‌محور وجود ندارد", Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 575 | `id نامشخص` | `startActivity(Intent(this@ReportActivity, InvoiceActivity::class.java).apply {` | Intent → InvoiceActivity |
| 592 | `id نامشخص` | `.setItems(labels) { _, which -> openSelected(teacherRows[which]) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 593 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 594 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 602 | `id نامشخص` | `Toast.makeText(this@ReportActivity, getString(R.string.rpt_stmt_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 609 | `id نامشخص` | `Toast.makeText(this, getString(R.string.rpt_rendering), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 334 | `val list = api.getTeachersList()` | `GET teachers/list` |
| 410 | `val summary = api.getFinancialSummary(` | `GET reports/financial_summary` |
| 471 | `val results = api.searchAdvanced(query)` | `GET finance/search_advanced, GET finance/search_advanced` |
| 513 | `val stmt = api.getStudentStatement(studentId)` | `GET reports/student_statement` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 326 | `acYearFilter.setText(jy.toString(), false)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 327 | `acMonthFilter.setText(String.format(java.util.Locale.US, "%02d", jm), false)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 355 | `else if (selectedTeacherId == null) acTeacherFilter.setText("", false)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 418 | `tvMonthlyTitle.text = getString(R.string.rpt_monthly_title, yearStr, monthStr)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 419 | `tvMonthlyTotal.text = getString(R.string.common_toman_format, summary.monthly.total)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 420 | `tvMonthlyCollected.text = getString(R.string.common_toman_format, summary.monthly.collected)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 421 | `tvMonthlyUncollected.text = getString(R.string.common_toman_format, summary.monthly.uncollected)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 428 | `warning.text = getString(` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 441 | `tvYearlyTitle.text = getString(R.string.rpt_yearly_title, yearStr)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 442 | `tvYearlyTotal.text = getString(R.string.common_toman_format, summary.yearly.total)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 443 | `tvYearlyCollected.text = getString(R.string.common_toman_format, summary.yearly.collected)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 444 | `tvYearlyUncollected.text = getString(R.string.common_toman_format, summary.yearly.uncollected)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 517 | `tvStatementStudentName.text = getString(R.string.rpt_stmt_name, stmt.student_name)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 518 | `tvStatementStudentCode.text = getString(R.string.rpt_stmt_code, stmt.student_code)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 524 | `tvStatementPaid.text = getString(R.string.common_toman_format, stmt.total_paid_institute)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 525 | `tvStatementDebt.text = getString(R.string.common_toman_format, stmt.total_debt_institute)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 531 | `tvStatementTeacher.text = if (teacherLines.isNotBlank()) teacherLines else` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 551 | `tvStatementNextDue.text = stmt.next_installment?.let {` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 554 | `tvStatementTimeline.text = stmt.payment_timeline.joinToString("\n") {` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 631 | `webView.loadUrl(url, headers)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
