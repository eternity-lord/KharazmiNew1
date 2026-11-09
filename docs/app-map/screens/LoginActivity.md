# LoginActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/LoginActivity.kt:42`
- layout و محل bind:
  - `R.layout.activity_login` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/LoginActivity.kt:64`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_ogin.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 81 | `id نامشخص` | `Toast.makeText(this, getString(R.string.login_secure_store_unavailable), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 92 | `id نامشخص` | `btnLogin.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 97 | `id نامشخص` | `Toast.makeText(this, getString(R.string.login_mobile_empty), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 98 | `id نامشخص` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 105 | `btnParentPortal` | `findViewById<Button>(R.id.btnParentPortal).setOnClickListener {` | Intent → ParentPortalActivity |
| 106 | `btnParentPortal` | `startActivity(Intent(this, ParentPortalActivity::class.java))` | Intent → ParentPortalActivity |
| 110 | `btnStudentPortal` | `findViewById<Button>(R.id.btnStudentPortal).setOnClickListener {` | Intent → StudentPortalActivity |
| 111 | `btnStudentPortal` | `startActivity(Intent(this, StudentPortalActivity::class.java))` | Intent → StudentPortalActivity |
| 115 | `id نامشخص` | `tvRegisterLink.setOnClickListener {` | Intent → TeacherRegisterActivity |
| 117 | `id نامشخص` | `startActivity(intent)` | Intent → TeacherRegisterActivity |
| 121 | `id نامشخص` | `btnSettings.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 138 | `id نامشخص` | `Toast.makeText(this@LoginActivity, getString(R.string.login_biometric_error, errString), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 154 | `id نامشخص` | `Toast.makeText(this@LoginActivity, getString(R.string.login_biometric_success), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 161 | `id نامشخص` | `Toast.makeText(this@LoginActivity, getString(R.string.login_biometric_failed), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 168 | `id نامشخص` | `.setNegativeButtonText(getString(R.string.login_biometric_use_password))` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 177 | `id نامشخص` | `Toast.makeText(this, getString(R.string.login_secure_read_failed), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 206 | `id نامشخص` | `.setPositiveButton(getString(R.string.action_save)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 212 | `id نامشخص` | `Toast.makeText(this, getString(R.string.login_server_saved), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 214 | `id نامشخص` | `Toast.makeText(this, getString(R.string.login_server_invalid), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 218 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 219 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 245 | `id نامشخص` | `if (!stored) Toast.makeText(this@LoginActivity, getString(R.string.login_quick_save_failed), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 249 | `id نامشخص` | `Toast.makeText(this@LoginActivity, getString(R.string.login_password_store_unavailable), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 261 | `id نامشخص` | `Toast.makeText(this@LoginActivity, getString(R.string.common_session_save_fail), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 276 | `id نامشخص` | `Toast.makeText(this@LoginActivity, getString(R.string.common_ok_msg, response.message), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 280 | `id نامشخص` | `startActivity(intent)` | Intent → MainActivity |
| 281 | `id نامشخص` | `finish()` | Intent → MainActivity, TeacherDashboardActivity |
| 286 | `id نامشخص` | `startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 287 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 312 | `id نامشخص` | `Toast.makeText(this@LoginActivity, msg, Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 232 | `val response = api.login(LoginRequest(mobile, if(pass.isEmpty()) null else pass))` | `POST auth/login` |
| 232 | `val response = api.login(LoginRequest(mobile, if(pass.isEmpty()) null else pass))` | `نامشخص در declarationهای Retrofit` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 150 | `etMobile.setText(savedMobile)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 151 | `etPass.setText(savedPass)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 199 | `etIp.setText(prefs.getString("SERVER_IP", ServerAddress.DEFAULT_ADDRESS))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
