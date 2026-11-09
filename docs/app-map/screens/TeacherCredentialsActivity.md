# TeacherCredentialsActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/TeacherCredentialsActivity.kt:63`
- layout و محل bind:
  - `R.layout.activity_teacher_credentials` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/TeacherCredentialsActivity.kt:82`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_eacher_credentials.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 88 | `id نامشخص` | `Toast.makeText(this, getString(R.string.tcred_no_access), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 89 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 181 | `id نامشخص` | `Toast.makeText(this@TeacherCredentialsActivity, getString(R.string.tcred_load_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 188 | `id نامشخص` | `btnSave.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 193 | `id نامشخص` | `Toast.makeText(this, getString(R.string.tcred_mobile_empty), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 194 | `id نامشخص` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 200 | `id نامشخص` | `.setPositiveButton(getString(R.string.common_yes)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 203 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 204 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 207 | `id نامشخص` | `btnReset.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 211 | `id نامشخص` | `.setPositiveButton(getString(R.string.tcred_pwd_yes)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 214 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 215 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 226 | `id نامشخص` | `Toast.makeText(this@TeacherCredentialsActivity, getString(R.string.common_ok_msg, res.message), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 233 | `id نامشخص` | `Toast.makeText(this@TeacherCredentialsActivity, getString(R.string.tcred_save_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 249 | `id نامشخص` | `.setPositiveButton(getString(R.string.common_understood), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 251 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 259 | `id نامشخص` | `Toast.makeText(this@TeacherCredentialsActivity, getString(R.string.tcred_pwd_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 294 | `id نامشخص` | `holder.itemView.setOnClickListener { onClick(item) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 133 | `val results = api.searchTeachers(s.toString())` | `GET admin/teachers/search` |
| 167 | `val creds = api.getCredentials(selectedTeacherId)` | `GET admin/teachers/{id}/credentials` |
| 224 | `val res = api.updateCredentials(selectedTeacherId, req)` | `PUT admin/teachers/{id}/credentials` |
| 243 | `val res = api.resetPassword(selectedTeacherId)` | `POST admin/teachers/{id}/credentials/reset_password` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 137 | `rvResults.adapter = CredentialsSearchAdapter(results) { item ->` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 159 | `etSearch.setText("")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 171 | `tvName.text = creds.name ?: getString(R.string.common_person_unknown)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 172 | `tvCode.text = getString(R.string.tcred_code_row, creds.teacher_code ?: getString(R.string.tcred_unset))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 173 | `etMobile.setText(creds.mobile ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 174 | `etCardNumber.setText(creds.card_number ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 175 | `tvCurrentPassword.text = creds.password` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 289 | `holder.title.text = ctx.getString(` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 293 | `holder.subtitle.text = ctx.getString(R.string.tcred_sub_row, item.national_code ?: "", item.mobile ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
