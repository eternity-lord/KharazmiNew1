# AdminDashboardActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/AdminDashboardActivity.kt:33`
- layout و محل bind:
  - `R.layout.activity_admin_dashboard` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/AdminDashboardActivity.kt:73`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_dmin_dashboard.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 125 | `id نامشخص` | `btnRefresh.setOnClickListener { loadDashboard() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 126 | `id نامشخص` | `btnBack.setOnClickListener { finish() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 130 | `id نامشخص` | `btnDunning.setOnClickListener {` | Intent → DunningActivity |
| 131 | `id نامشخص` | `startActivity(Intent(this, DunningActivity::class.java))` | Intent → DunningActivity |
| 133 | `id نامشخص` | `btnAudit.setOnClickListener {` | Intent → DunningActivity, AuditDashboardActivity |
| 134 | `id نامشخص` | `startActivity(Intent(this, AuditDashboardActivity::class.java))` | Intent → AuditDashboardActivity |
| 136 | `id نامشخص` | `btnDebtors.setOnClickListener {` | Intent → AuditDashboardActivity |
| 139 | `id نامشخص` | `startActivity(Intent(this, DebtorsActivity::class.java))` | Intent → DebtorsActivity |
| 143 | `btnDashboardAuditTrail` | `findViewById<MaterialButton>(R.id.btnDashboardAuditTrail)?.setOnClickListener {` | Intent → AuditTrailActivity |
| 144 | `btnDashboardAuditTrail` | `startActivity(Intent(this, AuditTrailActivity::class.java))` | Intent → AuditTrailActivity |
| 148 | `id نامشخص` | `btnExportDebtors.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 151 | `id نامشخص` | `btnExportOverdue.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 154 | `id نامشخص` | `btnExportAlerts.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 159 | `cardKpiRevenue` | `findViewById<View>(R.id.cardKpiRevenue)?.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 160 | `cardKpiOverdue, cardKpiRevenue` | `Toast.makeText(this, getString(R.string.dashboard_today_revenue), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 162 | `cardKpiOverdue` | `findViewById<View>(R.id.cardKpiOverdue)?.setOnClickListener {` | Intent → DunningActivity |
| 163 | `cardKpiOverdue, cardKpiStudents` | `startActivity(Intent(this, DunningActivity::class.java))` | Intent → DunningActivity |
| 165 | `cardKpiStudents` | `findViewById<View>(R.id.cardKpiStudents)?.setOnClickListener {` | Intent → DunningActivity, PersonListActivity |
| 166 | `cardKpiAlerts, cardKpiStudents` | `startActivity(Intent(this, PersonListActivity::class.java).apply { putExtra("MODE", "STUDENT") })` | Intent → PersonListActivity |
| 168 | `cardKpiAlerts` | `findViewById<View>(R.id.cardKpiAlerts)?.setOnClickListener {` | Intent → PersonListActivity, AuditDashboardActivity |
| 169 | `cardKpiAlerts` | `startActivity(Intent(this, AuditDashboardActivity::class.java))` | Intent → AuditDashboardActivity |
| 203 | `id نامشخص` | `Toast.makeText(this, getString(R.string.export_started), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 215 | `id نامشخص` | `Toast.makeText(this@AdminDashboardActivity, message, Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 244 | `id نامشخص` | `).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 257 | `id نامشخص` | `Toast.makeText(this@AdminDashboardActivity, message, Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 285 | `id نامشخص` | `startActivity(viewIntent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 292 | `id نامشخص` | `startActivity(Intent.createChooser(sendIntent, getString(R.string.export_share_title)))` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 299 | `id نامشخص` | `).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 344 | `id نامشخص` | `Toast.makeText(this@AdminDashboardActivity, msg, Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 438 | `id نامشخص` | `holder.card.setOnClickListener {` | Intent → DunningActivity |
| 440 | `id نامشخص` | `startActivity(Intent(this@AdminDashboardActivity, DunningActivity::class.java))` | Intent → DunningActivity |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 149 | `downloadExport("debtors.csv") { exportApi.exportDebtors() }` | `GET exports/debtors` |
| 152 | `downloadExport("overdue_installments.csv") { exportApi.exportOverdueInstallments() }` | `GET exports/overdue_installments` |
| 155 | `downloadExport("audit_alerts.csv") { exportApi.exportAuditAlerts() }` | `GET exports/audit_alerts` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 108 | `tvTitle.text = getString(R.string.dashboard_title)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 177 | `tvEmpty.text = getString(R.string.dashboard_loading)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 340 | `tvEmpty.text = msg` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 342 | `tvCriticalEmpty.text = msg` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 351 | `tvKpiRevenueValue.text = formatAmount(kpis.todayRevenue)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 352 | `tvKpiRevenueSub.text = getString(R.string.dashboard_today_revenue_sub)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 354 | `tvKpiOverdueAmount.text = formatAmount(kpis.totalOverdueAmount)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 361 | `tvKpiOverdueSub.text = overdueSub + dunningInfo` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 363 | `tvKpiStudentsValue.text = formatNumber(kpis.activeStudentsCount.toLong())` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 364 | `tvKpiStudentsSub.text = getString(R.string.dashboard_students_sub)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 366 | `tvKpiAlertsValue.text = kpis.suspiciousAlertsCount.toString()` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 368 | `tvKpiAlertsSub.text = if (kpis.dunningPendingCount > 0) {` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 377 | `tvCriticalEmpty.text = getString(R.string.dashboard_critical_empty)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 383 | `rvCritical.adapter = CriticalAdapter(list)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 425 | `holder.tvStudentName.text = item.studentName` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 426 | `holder.tvAmount.text = formatAmount(item.amount)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 427 | `holder.tvDueDate.text = "سررسید: ${item.dueDate}"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 428 | `holder.tvParentMobile.text = "📱 ${item.parentMobile}"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 429 | `holder.tvSmsPreview.text = item.suggestedMessage` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 433 | `holder.tvCategory.text = "🔴 $label"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
