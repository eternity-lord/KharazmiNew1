# SettingsActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/SettingsActivity.kt:41`
- layout و محل bind:
  - `R.layout.activity_settings` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/SettingsActivity.kt:45`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_ettings.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 53 | `id نامشخص` | `btnTeacherCredentials.setOnClickListener {` | Intent → TeacherCredentialsActivity |
| 54 | `id نامشخص` | `startActivity(Intent(this, TeacherCredentialsActivity::class.java))` | Intent → TeacherCredentialsActivity |
| 61 | `btnChangePass` | `findViewById<TextView>(R.id.btnChangePass).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 66 | `btnChangeMobile` | `findViewById<TextView>(R.id.btnChangeMobile).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 71 | `btnAbout` | `findViewById<TextView>(R.id.btnAbout).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 75 | `id نامشخص` | `.setPositiveButton(getString(R.string.common_ok), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 76 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 80 | `btnLogout` | `findViewById<TextView>(R.id.btnLogout).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 84 | `id نامشخص` | `.setPositiveButton(getString(R.string.common_yes)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 100 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_no), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 101 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 106 | `tvAppVersion` | `findViewById<TextView>(R.id.tvAppVersion).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 110 | `id نامشخص` | `Toast.makeText(this, getString(R.string.set_dev_on), Toast.LENGTH_SHORT).show()` | Intent → DesignSystemActivity |
| 111 | `id نامشخص` | `startActivity(Intent(this, DesignSystemActivity::class.java))` | Intent → DesignSystemActivity |
| 113 | `id نامشخص` | `Toast.makeText(this, getString(R.string.set_dev_clicks, 5 - devClickCount), Toast.LENGTH_SHORT).show()` | Intent → DesignSystemActivity |
| 133 | `id نامشخص` | `.setPositiveButton(getString(R.string.set_pwd_btn)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 141 | `id نامشخص` | `Toast.makeText(this, getString(R.string.set_fill_all), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 144 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 145 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 161 | `id نامشخص` | `Toast.makeText(this@SettingsActivity, getString(R.string.common_ok_msg, response.message), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 167 | `id نامشخص` | `Toast.makeText(this@SettingsActivity, getString(R.string.set_pwd_wrong), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 183 | `id نامشخص` | `.setPositiveButton(getString(R.string.set_mobile_btn)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 191 | `id نامشخص` | `Toast.makeText(this, getString(R.string.set_fill_all), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 194 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 195 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 210 | `id نامشخص` | `Toast.makeText(this@SettingsActivity, getString(R.string.common_ok_msg, response.message), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 221 | `id نامشخص` | `startActivity(intent)` | Intent → LoginActivity |
| 222 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 229 | `id نامشخص` | `Toast.makeText(this@SettingsActivity, getString(R.string.set_mobile_dup), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 231 | `id نامشخص` | `Toast.makeText(this@SettingsActivity, getString(R.string.set_server_error), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 158 | `val response = api.changePassword(req)` | `POST auth/change-password` |
| 207 | `val response = api.changeMobile(req)` | `POST auth/change-mobile` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| — | assignment نمایشی با الگوهای scan پیدا نشد | نامشخص |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
