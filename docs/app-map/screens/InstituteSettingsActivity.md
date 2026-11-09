# InstituteSettingsActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/InstituteSettingsActivity.kt:37`
- layout و محل bind:
  - `R.layout.activity_institute_settings` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/InstituteSettingsActivity.kt:53`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_nstitute_settings.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 70 | `btnSave` | `imgLogo.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 74 | `id نامشخص` | `btnSave.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 133 | `id نامشخص` | `Toast.makeText(this@InstituteSettingsActivity, getString(R.string.iset_load_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 146 | `id نامشخص` | `Toast.makeText(this, getString(R.string.iset_fill), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 158 | `id نامشخص` | `).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 182 | `id نامشخص` | `Toast.makeText(this@InstituteSettingsActivity, getString(R.string.common_ok_msg, res.message), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 200 | `id نامشخص` | `Toast.makeText(this@InstituteSettingsActivity, getString(R.string.iset_save_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 213 | `id نامشخص` | `.setItems(options) { _, which ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 224 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 243 | `id نامشخص` | `Toast.makeText(this, getString(R.string.iset_no_camera), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 281 | `id نامشخص` | `Toast.makeText(this@InstituteSettingsActivity, getString(R.string.iset_img_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 302 | `id نامشخص` | `Toast.makeText(this@InstituteSettingsActivity, getString(R.string.iset_img_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 318 | `id نامشخص` | `Toast.makeText(this@InstituteSettingsActivity, getString(R.string.common_ok_msg, response.message), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 329 | `id نامشخص` | `Toast.makeText(this@InstituteSettingsActivity, getString(R.string.iset_upload_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 95 | `networkCall = { api.getSettings() },` | `GET admin/institute_settings, GET admin/institute_settings` |
| 180 | `val res = api.updateSettings(data)` | `PUT admin/institute_settings` |
| 316 | `val response = api.uploadLogo(body)` | `POST admin/institute_settings/upload_logo` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 98 | `etName.setText(data.name)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 99 | `etPhone.setText(data.phone)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 100 | `etEmail.setText(data.official_email ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 101 | `etAddress.setText(data.address)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 102 | `etLiveMaxMinutes.setText((data.liveSessionMaxMinutes ?: 180).toString())` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 103 | `etTeacherSettlementAlertDays.setText(` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 119 | `.load(glideUrl)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 174 | `btnSave.text = getString(R.string.iset_saving)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 192 | `btnSave.text = getString(R.string.iset_save)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 202 | `btnSave.text = getString(R.string.iset_save)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
