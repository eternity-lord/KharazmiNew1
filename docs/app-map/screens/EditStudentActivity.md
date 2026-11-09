# EditStudentActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/EditStudentActivity.kt:28`
- layout و محل bind:
  - `R.layout.activity_edit_student` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/EditStudentActivity.kt:57`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_dit_student.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 61 | `id نامشخص` | `Toast.makeText(this, getString(R.string.estudent_sid_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 62 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 74 | `id نامشخص` | `etBirthDate.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 76 | `id نامشخص` | `.setPositiveButtonString(getString(R.string.common_ok))` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 77 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel))` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 95 | `id نامشخص` | `picker.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 99 | `id نامشخص` | `btnDialMobile1.setOnClickListener { makeCall(etStudentMobile.text.toString().trim()) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 100 | `id نامشخص` | `btnDialMobile2.setOnClickListener { makeCall(etParentMobile.text.toString().trim()) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 103 | `id نامشخص` | `btnSave.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 108 | `id نامشخص` | `btnCancel.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 249 | `id نامشخص` | `Toast.makeText(this@EditStudentActivity, getString(R.string.estudent_current_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 299 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_no), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 303 | `id نامشخص` | `.setPositiveButton(getString(R.string.common_yes)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 306 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 346 | `id نامشخص` | `Toast.makeText(this@EditStudentActivity, getString(R.string.estudent_update_error), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 374 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 376 | `id نامشخص` | `.setPositiveButton(getString(R.string.btn_dismiss)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 377 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 379 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 383 | `id نامشخص` | `Toast.makeText(this, getString(R.string.estudent_print_loading), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 411 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_no), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 412 | `id نامشخص` | `.setPositiveButton(getString(R.string.common_yes)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 415 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 428 | `id نامشخص` | `startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 429 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 436 | `id نامشخص` | `startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 440 | `id نامشخص` | `Toast.makeText(this, getString(R.string.estudent_no_call), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 152 | `val profile = api.getStudentProfile(studentId)` | `GET students/my_profile, GET students/{id}` |
| 155 | `val fullProfile = api.getFullStudentProfile(studentId)` | `GET admin/students/{id}/full_profile, GET admin/students/{id}/full_profile` |
| 333 | `api.updateStudent(studentId, data)` | `PUT students/update/{id}` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 90 | `etBirthDate.setText(date)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 159 | `etFirstName.setText(profile.first_name)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 160 | `etLastName.setText(profile.last_name)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 161 | `etFatherName.setText(profile.father_name ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 162 | `etNationalCode.setText(profile.national_code)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 163 | `etBirthDate.setText(profile.birth_date ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 164 | `etStudentMobile.setText(profile.student_mobile)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 165 | `etParentMobile.setText(profile.parent_mobile ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 173 | `tvOverallPaidInstitute.text = String.format(Locale("en", "US"), getString(R.string.common_toman_format), newPaid)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 174 | `tvOverallDebtInstitute.text = String.format(Locale("en", "US"), getString(R.string.common_toman_format), newDebt)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 404 | `webView.loadUrl(url, headers)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
