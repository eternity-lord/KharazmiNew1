# InvoiceActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/InvoiceActivity.kt:86`
- layout و محل bind:
  - `R.layout.activity_invoice` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/InvoiceActivity.kt:121`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_nvoice.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 176 | `rbWalletBoth` | `rgWallet.setOnCheckedChangeListener { _, checkedId ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 263 | `id نامشخص` | `Toast.makeText(this@InvoiceActivity, getString(R.string.invoice_no_enrollment), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 270 | `id نامشخص` | `.setItems(classNames) { _, which ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 276 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 372 | `id نامشخص` | `Toast.makeText(this, getString(R.string.invoice_class_empty), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 385 | `id نامشخص` | `.setItems(names) { _, which ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 398 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 452 | `id نامشخص` | `btnSubmit.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 455 | `id نامشخص` | `Toast.makeText(this, getString(R.string.invoice_amount_empty), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 456 | `id نامشخص` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 489 | `id نامشخص` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 497 | `id نامشخص` | `Toast.makeText(this, getString(R.string.invoice_institute_missing), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 498 | `id نامشخص` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 504 | `id نامشخص` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 513 | `id نامشخص` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 522 | `id نامشخص` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 547 | `id نامشخص` | `.setPositiveButton(getString(R.string.invoice_confirm_yes)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 566 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 567 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 609 | `id نامشخص` | `.setItems(labels) { _, which -> onPicked(active[which]) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 610 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 611 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 650 | `id نامشخص` | `if (res.duplicate) Toast.makeText(this@InvoiceActivity, getString(R.string.invoice_duplicate), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 681 | `id نامشخص` | `Toast.makeText(this@InvoiceActivity, friendly, Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 692 | `id نامشخص` | `Toast.makeText(this, getString(R.string.invoice_receipt_invalid), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 717 | `id نامشخص` | `Toast.makeText(this@InvoiceActivity, msg, Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 749 | `btnPrintRemittance` | `btnPrint.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 763 | `btnSaveAsPdf` | `btnSavePdf.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 777 | `btnRegisterAgain` | `btnRegisterAgain.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 791 | `btnClose` | `btnClose.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 794 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 806 | `id نامشخص` | `dialog.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 956 | `id نامشخص` | `Toast.makeText(this@InvoiceActivity, getString(R.string.invoice_pdf_saved, fileName), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 960 | `id نامشخص` | `Toast.makeText(this@InvoiceActivity, getString(R.string.invoice_pdf_error, e.message), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1025 | `id نامشخص` | `holder.itemView.setOnClickListener { onClick(item) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 208 | `val results = api.searchAdvanced(s.toString())` | `GET finance/search_advanced, GET finance/search_advanced` |
| 248 | `val fullProfile = api.getFullStudentProfile(studentId)` | `GET admin/students/{id}/full_profile, GET admin/students/{id}/full_profile` |
| 305 | `val status = api.getStudentClassStatus(studentId, courseId, courseCode)` | `GET finance/student_class_status` |
| 357 | `val status = api.getStudentClassStatus(studentId, courseId, null)` | `GET finance/student_class_status` |
| 577 | `api.getFullStudentProfile(selectedStudentId).enrollments` | `GET admin/students/{id}/full_profile, GET admin/students/{id}/full_profile` |
| 643 | `val res = api.submitPayment(data)` | `POST finance/pay` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 164 | `tvDate.text = getString(R.string.invoice_date, currentPersianDate)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 212 | `rvResults.adapter = SearchAdapter(results) { item ->` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 233 | `etSearch.setText("")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 298 | `tvStName.text = studentName` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 299 | `tvStClass.text = className` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 322 | `tvDebt.text = if (credit > 0)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 327 | `tvUnpaid.text = getString(R.string.invoice_paid_teacher, formattedPaidTeacher)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 328 | `tvStClass.text = getString(R.string.invoice_paid_institute, className, formattedPaidInstitute)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 330 | `tvDebtTeacher.text = getString(R.string.invoice_due_teacher, signTeacher, formattedDueTeacher)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 331 | `tvDebtInstitute.text = getString(R.string.invoice_due_institute, signInstitute, formattedDueInstitute)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 342 | `etAmount.setText(if (defaultPay > 0) defaultPay.toString() else "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 407 | `tvStName.text = name` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 408 | `tvStClass.text = className` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 409 | `tvDebt.text = getString(R.string.invoice_debt_total, String.format("%,d", debt))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 411 | `tvDebtTeacher.text = getString(R.string.invoice_debt_teacher, String.format("%,d", debtTeacherVal))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 413 | `tvDebtInstitute.text = getString(R.string.invoice_debt_institute, String.format("%,d", debtInstituteVal))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 414 | `tvUnpaid.text = getString(R.string.invoice_unpaid, unpaid)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 416 | `etAmount.setText(if (debt > 0) debt.toString() else "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 418 | `etDesc.setText(defaultDesc)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 445 | `etSearch.setText(query)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 593 | `tvStClass.text = enrollmentLabel(en)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 702 | `tvStName.text = d.student_name ?: "-"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 703 | `tvStClass.text = d.course_name ?: "-"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 704 | `etAmount.setText((d.amount ?: 0).toString())` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 705 | `etDesc.setText(d.description ?: "-")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 706 | `tvDate.text = d.date ?: "-"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 746 | `tvMessage.text = getString(R.string.invoice_dialog_msg, message, receiptId)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 781 | `etSearch.setText("")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 785 | `etAmount.setText("")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 786 | `etDesc.setText("")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 798 | `etSearch.setText("")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 801 | `etAmount.setText("")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 802 | `etDesc.setText("")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 864 | `webView.loadDataWithBaseURL(null, htmlContent, "text/html", "UTF-8", null)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 1016 | `holder.title.text = "$icon ${item.title}"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 1024 | `holder.subtitle.text = "${item.subtitle} \| $extraInfo"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
