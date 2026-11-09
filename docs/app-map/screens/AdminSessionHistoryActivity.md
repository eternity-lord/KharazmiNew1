# AdminSessionHistoryActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/AdminSessionHistoryActivity.kt:56`
- layout و محل bind:
  - `R.layout.activity_admin_session_history` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/AdminSessionHistoryActivity.kt:62`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_dmin_session_history.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 67 | `btnExportSessions, btnFilterSessions` | `findViewById<Button>(R.id.btnExportSessions).setOnClickListener { loadHistory(export = true) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 68 | `btnExportSessions, btnFilterSessions` | `findViewById<Button>(R.id.btnFilterSessions).setOnClickListener { loadHistory() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 101 | `id نامشخص` | `onStart = { Toast.makeText(this@AdminSessionHistoryActivity, "در حال ساخت خروجی جلسه‌ها…", Toast.LENGTH_SHORT).show() },` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 102 | `id نامشخص` | `onComplete = { Toast.makeText(this@AdminSessionHistoryActivity, "خروجی جلسه‌ها آماده شد", Toast.LENGTH_LONG).show() },` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 103 | `id نامشخص` | `onError = { Toast.makeText(this@AdminSessionHistoryActivity, "خروجی جلسه‌ها ناموفق بود: $it", Toast.LENGTH_LONG).show() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 115 | `id نامشخص` | `Toast.makeText(this@AdminSessionHistoryActivity, "دریافت تاریخچه ناموفق بود", Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 123 | `id نامشخص` | `Toast.makeText(this, "این جلسه اثر مالی دارد و قابل بازگشایی نیست", Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 133 | `id نامشخص` | `withContext(Dispatchers.Main) { Toast.makeText(this@AdminSessionHistoryActivity, "بازگشایی انجام نشد", Toast.LENGTH_SHORT).show() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 167 | `id نامشخص` | `holder.reopen.setOnClickListener { onReopen(item) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| — | فراخوانی `api.method` پیدا نشد | — |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 66 | `rv.adapter = adapter` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 154 | `holder.title.text = "${item.course_title ?: "کلاس"} \| ${item.date ?: "تاریخ نامشخص"} ${item.time ?: ""}"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 155 | `holder.flags.text = "معلم: ${item.teacher_name ?: "بدون معلم"} \| حضور: ${item.attendance_count} \| " +` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 158 | `holder.financial.text = if (financial == null) "وضعیت مالی: نامشخص" else` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 161 | `holder.attendance.text = if (item.attendance.isEmpty()) "حضور و غیاب: ثبت نشده" else` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
