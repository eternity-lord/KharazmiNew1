# EditTeacherActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/EditTeacherActivity.kt:13`
- layout و محل bind:
  - `R.layout.activity_edit_teacher` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/EditTeacherActivity.kt:32`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_dit_teacher.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 36 | `id نامشخص` | `Toast.makeText(this, getString(R.string.etchr_sid_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 37 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 44 | `id نامشخص` | `btnSave.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 93 | `id نامشخص` | `Toast.makeText(this@EditTeacherActivity, getString(R.string.etchr_load_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 114 | `id نامشخص` | `Toast.makeText(this, getString(R.string.etchr_name_req), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 118 | `id نامشخص` | `Toast.makeText(this, getString(R.string.etchr_family_req), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 124 | `id نامشخص` | `Toast.makeText(this, getString(R.string.common_national_invalid), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 129 | `id نامشخص` | `Toast.makeText(this, getString(R.string.etchr_mobile_bad), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 133 | `id نامشخص` | `Toast.makeText(this, getString(R.string.etchr_card_bad), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 163 | `id نامشخص` | `Toast.makeText(this@EditTeacherActivity, getString(R.string.common_ok_msg, response.message), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 169 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 180 | `id نامشخص` | `.setPositiveButton(getString(R.string.common_understood), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 181 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 183 | `id نامشخص` | `Toast.makeText(this@EditTeacherActivity, getString(R.string.etchr_edit_error), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 72 | `val profile = api.getTeacherProfile(teacherId)` | `GET teachers/{id}` |
| 161 | `val response = api.updateTeacher(teacherId, data)` | `PUT teachers/update/{id}` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 77 | `etFirstName.setText(profile.first_name ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 78 | `etLastName.setText(profile.last_name ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 79 | `etFatherName.setText(profile.father_name ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 80 | `etNationalCode.setText(profile.national_code ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 81 | `etBirthDate.setText(profile.birth_date ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 82 | `etMobile.setText(profile.mobile ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 83 | `etHomePhone.setText(profile.home_phone ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 84 | `etMaritalStatus.setText(profile.marital_status ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 85 | `etGender.setText(profile.gender ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 86 | `etEmploymentType.setText(profile.employment_type ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 87 | `etCardNumber.setText(profile.card_number ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
