# ClassDashboardActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ClassDashboardActivity.kt:13`
- layout و محل bind:
  - `R.layout.activity_class_dashboard` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ClassDashboardActivity.kt:21`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_lass_dashboard.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 31 | `id نامشخص` | `Toast.makeText(this, getString(R.string.common_class_activate), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 36 | `btnNewSession` | `findViewById<MaterialCardView>(R.id.btnNewSession).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 38 | `btnNewSession` | `Toast.makeText(this, getString(R.string.common_class_activate), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 39 | `id نامشخص` | `return@setOnClickListener` | Intent → AttendanceActivity |
| 46 | `id نامشخص` | `startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 50 | `btnSessionHistory` | `findViewById<MaterialCardView>(R.id.btnSessionHistory).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 52 | `btnSessionHistory` | `Toast.makeText(this, getString(R.string.common_class_activate), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 53 | `id نامشخص` | `return@setOnClickListener` | Intent → SessionHistoryActivity |
| 57 | `id نامشخص` | `startActivity(intent)` | Intent → SessionHistoryActivity |
| 61 | `btnStudentList` | `findViewById<MaterialCardView>(R.id.btnStudentList).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 63 | `btnStudentList` | `Toast.makeText(this, getString(R.string.common_class_activate), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 64 | `id نامشخص` | `return@setOnClickListener` | Intent → ClassSetupActivity |
| 69 | `id نامشخص` | `startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 73 | `btnFinancial` | `findViewById<MaterialCardView>(R.id.btnFinancial).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 75 | `btnFinancial` | `Toast.makeText(this, getString(R.string.common_class_activate), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 76 | `id نامشخص` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 78 | `id نامشخص` | `Toast.makeText(this, getString(R.string.cdash_fin_todo), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| — | فراخوانی `api.method` پیدا نشد | — |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 27 | `findViewById<TextView>(R.id.tvClassName).text = getString(R.string.cdash_mgmt_title, className)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
