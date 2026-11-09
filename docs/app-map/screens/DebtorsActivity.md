# DebtorsActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/DebtorsActivity.kt:75`
- layout و محل bind:
  - `R.layout.activity_debtors` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/DebtorsActivity.kt:89`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_ebtors.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 100 | `id نامشخص` | `startActivity(Intent(this, StudentProfileActivity::class.java).putExtra("STUDENT_ID", id))` | Intent → StudentProfileActivity |
| 104 | `id نامشخص` | `btnSearch.setOnClickListener { load() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 105 | `id نامشخص` | `btnRefresh.setOnClickListener { etSearch.setText(""); load() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 106 | `id نامشخص` | `btnExport.setOnClickListener { exportAllDebtors() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 130 | `id نامشخص` | `Toast.makeText(this@DebtorsActivity, tvEmpty.text, Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 142 | `id نامشخص` | `onStart = { Toast.makeText(this, "در حال ساخت خروجی بدهکاران…", Toast.LENGTH_SHORT).show() },` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 143 | `id نامشخص` | `onComplete = { Toast.makeText(this, "خروجی بدهکاران آماده شد", Toast.LENGTH_LONG).show() },` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 144 | `id نامشخص` | `onError = { Toast.makeText(this, "خروجی بدهکاران ناموفق بود: $it", Toast.LENGTH_LONG).show() },` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 175 | `id نامشخص` | `holder.text.setOnClickListener { onStudentClick(row.student_id) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 116 | `val result = api.getGrouped(search)` | `GET finance/reports/debtors_grouped` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 103 | `rvRows.adapter = adapter` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 105 | `btnRefresh.setOnClickListener { etSearch.setText(""); load() }` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 113 | `tvEmpty.text = "در حال دریافت گزارش بدهکاران…"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 118 | `tvSummary.text = "تعداد بدهکاران: ${result.debtors_count} \| کل بدهی: ${result.total_debt} تومان \| بدون انتساب معلم: ${result.unassigned_debt} تومان"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 119 | `tvBreakdown.text = result.by_age.orEmpty().joinToString(" \| ") { "${it.bucket}: ${it.debt} تومان (${it.students_count})" }` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 123 | `if (rows.isEmpty()) tvEmpty.text = "برای این جست‌وجو بدهکاری ثبت نشده است"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 128 | `tvEmpty.text = "دریافت گزارش بدهکاران ناموفق بود: ${error.message ?: "خطای سرور"}"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 169 | `holder.text.text = buildString {` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
