# AttendanceActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/AttendanceActivity.kt:68`
- layout و محل bind:
  - `R.layout.activity_attendance` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/AttendanceActivity.kt:92`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_ttendance.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 128 | `btnFinishSession` | `findViewById<MaterialButton>(R.id.btnFinishSession).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 227 | `id نامشخص` | `Toast.makeText(this@AttendanceActivity, getString(R.string.attendance_queue_summary, parts.joinToString("؛ ")), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 309 | `id نامشخص` | `Toast.makeText(this, getString(R.string.attendance_offline_retry), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 321 | `id نامشخص` | `Toast.makeText(this@AttendanceActivity, getString(R.string.attendance_submit_ok), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 323 | `id نامشخص` | `Toast.makeText(this@AttendanceActivity, getString(R.string.attendance_submit_dup), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 325 | `id نامشخص` | `Toast.makeText(this@AttendanceActivity, getString(R.string.attendance_submit_netdown), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 329 | `id نامشخص` | `Toast.makeText(this@AttendanceActivity, getString(R.string.attendance_send_failed, err), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 387 | `id نامشخص` | `setOnClickListener { retryQueueItem(item.id) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 425 | `id نامشخص` | `Toast.makeText(this@AttendanceActivity, msg, Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 426 | `id نامشخص` | `if (!isFinishing) finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 437 | `id نامشخص` | `Toast.makeText(this@AttendanceActivity, getString(R.string.attendance_class_deleted), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 438 | `id نامشخص` | `if (!isFinishing) finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 465 | `id نامشخص` | `Toast.makeText(this@AttendanceActivity, msg, Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 466 | `id نامشخص` | `if (!isFinishing) finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 500 | `id نامشخص` | `Toast.makeText(this@AttendanceActivity, describeApiError(e), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 502 | `id نامشخص` | `if (e is HttpException && e.code() in setOf(401, 403, 404) && !isFinishing) finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 536 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 546 | `id نامشخص` | `Toast.makeText(this@AttendanceActivity, describeApiError(e), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 547 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 556 | `id نامشخص` | `Toast.makeText(this@AttendanceActivity, getString(R.string.attendance_classes_empty), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 557 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 567 | `tvPageTitle` | `.setItems(labels.toTypedArray()) { _, which ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 575 | `id نامشخص` | `.setNegativeButton(R.string.btn_dismiss) { _, _ -> if (!isFinishing) finish() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 576 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 580 | `id نامشخص` | `Toast.makeText(this@AttendanceActivity, getString(R.string.attendance_class_list_error), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 581 | `id نامشخص` | `if (!isFinishing) finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 594 | `id نامشخص` | `.setPositiveButton(getString(R.string.common_yes)) { _, _ -> submitSession() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 595 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_no), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 598 | `id نامشخص` | `dialog.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 620 | `id نامشخص` | `Toast.makeText(this, getString(R.string.attendance_offline_kept), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 684 | `id نامشخص` | `Toast.makeText(this@AttendanceActivity, userMessage, Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 817 | `btnPrintRemittance` | `btnPrint.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 826 | `btnSaveAsPdf` | `btnSavePdf.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 877 | `id نامشخص` | `Toast.makeText(this@AttendanceActivity, getString(R.string.attendance_pdf_saved, fileName), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 881 | `id نامشخص` | `Toast.makeText(this@AttendanceActivity, getString(R.string.attendance_pdf_error, e.message), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 888 | `btnClose` | `btnClose.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 890 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 893 | `id نامشخص` | `dialog.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 900 | `id نامشخص` | `Toast.makeText(this@AttendanceActivity, getString(R.string.attendance_receipt_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 901 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 933 | `id نامشخص` | `holder.name.setOnClickListener {` | Intent → StudentProfileActivity |
| 936 | `id نامشخص` | `holder.itemView.context.startActivity(intent)` | Intent → StudentProfileActivity |
| 939 | `id نامشخص` | `holder.rg.setOnCheckedChangeListener(null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 940 | `id نامشخص` | `holder.rgAbsenceType.setOnCheckedChangeListener(null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 964 | `rbPresent` | `holder.rg.setOnCheckedChangeListener { _, checkedId ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 983 | `rbExcused` | `holder.rgAbsenceType.setOnCheckedChangeListener { _, checkedId ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 539 | `classApi.getAllClasses()` | `GET classes/list` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 104 | `findViewById<TextView>(R.id.tvPageTitle).text = getString(R.string.attendance_edit_title_code, targetSessionCode)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 106 | `findViewById<TextView>(R.id.tvPageTitle).text = getString(R.string.attendance_title_class, className)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 107 | `findViewById<TextView>(R.id.etSessionDate).text = JalaliUtils.todayJalaliString() // FIX (audit-v2/#13): نمایش تاریخ شمسی امروز (قبلاً خالی بود)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 360 | `title.text = getString(R.string.attendance_queue_title, items.size)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 406 | `tvNetworkStatus.text = getString(R.string.attendance_net_online)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 409 | `tvNetworkStatus.text = getString(R.string.attendance_net_offline)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 455 | `findViewById<TextView>(R.id.tvPageTitle).text = getString(R.string.attendance_edit_loaded, details.session_code, details.class_title)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 456 | `findViewById<TextView>(R.id.etSessionDate).text = details.date // FIX (audit-v2/#13): نمایش تاریخ اصلی جلسه` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 457 | `rv.adapter = AttendanceAdapter(studentList, attendanceMap, excusedMap)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 492 | `rv.adapter = AttendanceAdapter(studentList, attendanceMap, excusedMap)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 569 | `findViewById<TextView>(R.id.tvPageTitle).text = getString(` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 808 | `dialogView.findViewById<TextView>(R.id.tvSuccessMessage).text =` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 816 | `btnPrint.text = getString(R.string.attendance_print_receipt)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 818 | `webView.loadDataWithBaseURL(null, htmlContent, "text/html", "UTF-8", null)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 825 | `btnSavePdf.text = getString(R.string.attendance_save_pdf)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 930 | `holder.name.text = item.student_name` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
