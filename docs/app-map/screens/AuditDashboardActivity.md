# AuditDashboardActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/AuditDashboardActivity.kt:20`
- layout و محل bind:
  - `R.layout.activity_audit_dashboard` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/AuditDashboardActivity.kt:33`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_udit_dashboard.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 58 | `id نامشخص` | `btnRefresh.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 61 | `id نامشخص` | `btnBack.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 62 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 100 | `id نامشخص` | `Toast.makeText(this@AuditDashboardActivity, msg, Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 73 | `val list = api.getSuspiciousPatterns()` | `GET audit/suspicious_patterns` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 49 | `tvTitle.text = "Audit Radar — رادار تقلب"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 67 | `tvEmpty.text = "در حال بارگذاری..."` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 77 | `tvEmpty.text = "هیچ الگوی مشکوکی یافت نشد ✓"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 83 | `rvAlerts.adapter = AuditAlertAdapter(list)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 97 | `tvEmpty.text = msg` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 129 | `holder.tvType.text = item.type` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 130 | `holder.tvSeverity.text = item.severity.uppercase()` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 131 | `holder.tvTitle.text = item.title` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 132 | `holder.tvDesc.text = item.description` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 133 | `holder.tvEntity.text = "موجودیت: ${item.entityName} (#${item.entityId})"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 134 | `holder.tvDetected.text = "شناسایی: ${item.detectedAt}"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 156 | `holder.tvType.text = "$icon ${item.type}"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
