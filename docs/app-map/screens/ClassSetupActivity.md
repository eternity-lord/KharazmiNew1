# ClassSetupActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ClassSetupActivity.kt:61`
- layout و محل bind:
  - `R.layout.activity_class_setup` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ClassSetupActivity.kt:78`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_lass_setup.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 93 | `btnAddStudent` | `findViewById<Button>(R.id.btnAddStudent).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 97 | `btnFinalizeClass` | `findViewById<Button>(R.id.btnFinalizeClass).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 109 | `id نامشخص` | `.setPositiveButton(getString(R.string.btn_dismiss), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 110 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 117 | `id نامشخص` | `.setPositiveButton(getString(R.string.common_yes)) { _, _ -> showClassSummaryPage() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 118 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_no), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 121 | `id نامشخص` | `confirmDialog.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 159 | `id نامشخص` | `.setPositiveButton(getString(R.string.csetup_sum_send)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 172 | `id نامشخص` | `.setPositiveButton(getString(R.string.common_ok)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 173 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 180 | `id نامشخص` | `startActivity(intent)` | Intent → PendingClassesActivity |
| 181 | `id نامشخص` | `finish()` | Intent → PendingClassesActivity |
| 185 | `id نامشخص` | `sentDialogBuilder.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 187 | `id نامشخص` | `.setNegativeButton(getString(R.string.csetup_sent_edit), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 190 | `id نامشخص` | `summaryDialog.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 199 | `id نامشخص` | `Toast.makeText(this@ClassSetupActivity, getString(R.string.csetup_sum_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 264 | `id نامشخص` | `acDiscountType.setOnItemClickListener { _, _, _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 288 | `id نامشخص` | `acSearch.setOnItemClickListener { _, _, position, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 290 | `id نامشخص` | `val item = searchResults.getOrNull(position) ?: return@setOnItemClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 300 | `id نامشخص` | `.setPositiveButton(getString(R.string.csetup_search_add)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 311 | `id نامشخص` | `Toast.makeText(this, getString(R.string.csetup_tuition_neg), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 312 | `id نامشخص` | `return@setPositiveButton` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 315 | `id نامشخص` | `Toast.makeText(this, getString(R.string.csetup_disc_range), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 316 | `id نامشخص` | `return@setPositiveButton` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 319 | `id نامشخص` | `Toast.makeText(this, getString(R.string.csetup_disc_over), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 320 | `id نامشخص` | `return@setPositiveButton` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 360 | `id نامشخص` | `selectedIds.isEmpty() -> Toast.makeText(this, getString(R.string.csetup_no_pick), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 365 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 366 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 399 | `id نامشخص` | `Toast.makeText(this@ClassSetupActivity, getString(R.string.csetup_search_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 428 | `id نامشخص` | `checkBox.setOnCheckedChangeListener { _, checked ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 472 | `id نامشخص` | `Toast.makeText(this@ClassSetupActivity, getString(R.string.common_class_activate), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 478 | `id نامشخص` | `Toast.makeText(this@ClassSetupActivity, getString(R.string.common_ok_msg, result.message), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 490 | `id نامشخص` | `Toast.makeText(this@ClassSetupActivity, enrollmentError(e, getString(R.string.csetup_add_error)), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 521 | `id نامشخص` | `Toast.makeText(this@ClassSetupActivity, getString(R.string.common_class_activate), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 533 | `id نامشخص` | `).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 541 | `id نامشخص` | `Toast.makeText(this@ClassSetupActivity, enrollmentError(e, getString(R.string.csetup_bulk_error)), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 568 | `id نامشخص` | `.setPositiveButton(getString(R.string.action_delete)) { _, _ -> removeStudentFromClass(item) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 569 | `id نامشخص` | `.setNegativeButton(getString(R.string.action_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 570 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 579 | `id نامشخص` | `Toast.makeText(this@ClassSetupActivity, getString(R.string.csetup_del_done, item.student_name), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 592 | `id نامشخص` | `Toast.makeText(this@ClassSetupActivity, getString(R.string.common_class_activate), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 594 | `id نامشخص` | `Toast.makeText(this@ClassSetupActivity, getString(R.string.csetup_del_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 623 | `id نامشخص` | `holder.tvName.setOnClickListener {` | Intent → StudentProfileActivity |
| 626 | `id نامشخص` | `holder.itemView.context.startActivity(intent)` | Intent → StudentProfileActivity |
| 636 | `id نامشخص` | `holder.btnRemove.setOnClickListener { onRemove(item) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 386 | `api.searchStudents(query)` | `GET students/search_simple` |
| 476 | `val result = api.addEnrollment(data)` | `POST enrollments/add` |
| 525 | `val result = api.addEnrollmentsBulk(data)` | `POST enrollments/add_bulk` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 83 | `findViewById<TextView>(R.id.tvHeaderTitle).text = getString(R.string.csetup_header, className)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 225 | `acDiscountType.setText("بدون تخفیف", false)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 233 | `tvFinalTuitionPreview.text = getString(R.string.csetup_preview_dash)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 248 | `tvFinalTuitionPreview.text = getString(R.string.sreg_tuition_preview, String.format(Locale("en", "US"), "%,d", finalTuition))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 292 | `tvInfo.text = "${item.name} (${item.id})"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 425 | `checkBox.text = "${student.name} (${student.id})"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 430 | `summary.text = getString(R.string.csetup_bulk_selected, selectedIds.size)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 434 | `summary.text = getString(R.string.csetup_bulk_selected, selectedIds.size)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 554 | `rv.adapter = ClassSetupStudentAdapter(details.students) { item -> promptRemoveStudent(item) }` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 620 | `holder.tvName.text = "${position + 1}. ${item.student_name}"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 621 | `holder.tvDebt.text = holder.itemView.context.getString(R.string.csetup_debt_row, String.format(Locale("en", "US"), "%,d", item.debt))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
