# TeacherRegisterActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/TeacherRegisterActivity.kt:31`
- layout و محل bind:
  - `R.layout.activity_teacher_register` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/TeacherRegisterActivity.kt:58`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_eacher_register.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 66 | `id نامشخص` | `etBirthDate.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 68 | `id نامشخص` | `.setPositiveButtonString(getString(R.string.common_ok))` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 69 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel))` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 88 | `id نامشخص` | `picker.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 92 | `id نامشخص` | `btnNext.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 118 | `id نامشخص` | `btnPrevious.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 224 | `id نامشخص` | `Toast.makeText(this, getString(R.string.treg_mobile_req), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 228 | `id نامشخص` | `Toast.makeText(this, getString(R.string.treg_mobile_bad), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 232 | `id نامشخص` | `Toast.makeText(this, getString(R.string.treg_marital_req), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 236 | `id نامشخص` | `Toast.makeText(this, getString(R.string.treg_gender_req), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 276 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_no), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 277 | `id نامشخص` | `.setPositiveButton(getString(R.string.common_yes)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 280 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 340 | `id نامشخص` | `.setPositiveButton(getString(R.string.btn_dismiss)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 341 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 343 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 351 | `id نامشخص` | `Toast.makeText(this@TeacherRegisterActivity, getString(R.string.common_submit_dup), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 314 | `val response = api.registerTeacher(data)` | `POST teachers/register` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 82 | `etBirthDate.setText(date)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 149 | `acGender.setText("آقا", false)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 153 | `acMarital.setText("متاهل", false)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 157 | `acEmployment.setText("رسمی", false)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 171 | `btnNext.text = getString(R.string.treg_submit)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 173 | `btnNext.text = getString(R.string.common_next)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 304 | `btnNext.text = getString(R.string.common_sending)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 354 | `btnNext.text = getString(R.string.treg_submit)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
