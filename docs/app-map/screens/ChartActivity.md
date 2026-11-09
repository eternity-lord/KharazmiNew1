# ChartActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ChartActivity.kt:90`
- layout و محل bind:
  - `R.layout.activity_chart` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ChartActivity.kt:99`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_hart.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 122 | `btnFilterWeek` | `findViewById<Button>(R.id.btnFilterWeek).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 125 | `btnFilterMonth` | `findViewById<Button>(R.id.btnFilterMonth).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 128 | `btnFilterQuarter` | `findViewById<Button>(R.id.btnFilterQuarter).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 237 | `attendanceLineChart` | `Toast.makeText(this@ChartActivity, getString(R.string.chart_att_empty), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 246 | `sharesPieChart` | `Toast.makeText(this@ChartActivity, getString(R.string.chart_money_empty), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 253 | `id نامشخص` | `Toast.makeText(this@ChartActivity, getString(R.string.chart_stats_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 152 | `val funnel = api.getEnrollmentFunnel(startDate, endDate, branchId)` | `GET analytics/enrollment_funnel` |
| 225 | `val data = api.getChartData(queryClassId, startDate, endDate)` | `GET reports/chart-data` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 115 | `findViewById<TextView>(R.id.tvAttendanceChartTitle)?.text = getString(R.string.chart_att_title, className ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 148 | `findViewById<TextView>(R.id.tvFunnelAverage).text = getString(R.string.chart_funnel_loading)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 154 | `findViewById<TextView>(R.id.tvFunnelTotal).text =` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 156 | `findViewById<TextView>(R.id.tvFunnelConverted).text =` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 158 | `findViewById<TextView>(R.id.tvFunnelRate).text =` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 160 | `findViewById<TextView>(R.id.tvFunnelAverage).text =` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 175 | `findViewById<TextView>(R.id.tvFunnelAverage).text =` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
