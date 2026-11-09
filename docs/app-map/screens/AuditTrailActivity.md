# AuditTrailActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/AuditTrailActivity.kt:43`
- layout و محل bind:
  - `R.layout.activity_audit_trail` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/AuditTrailActivity.kt:78`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_udit_trail.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 138 | `id نامشخص` | `btnBack.setOnClickListener { finish() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 139 | `id نامشخص` | `btnRefresh.setOnClickListener { loadLogs(reset = true) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 140 | `id نامشخص` | `btnLoadMore.setOnClickListener { loadLogs(reset = false) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 142 | `id نامشخص` | `btnClearFilters.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 163 | `id نامشخص` | `btnFromDate.setOnClickListener { pickDate(isFrom = true) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 164 | `id نامشخص` | `btnToDate.setOnClickListener { pickDate(isFrom = false) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 166 | `id نامشخص` | `btnExport.setOnClickListener { exportFilteredLogs() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 183 | `id نامشخص` | `.setPositiveButtonString(getString(R.string.audit_trail_pick_ok))` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 184 | `id نامشخص` | `.setNegativeButton(getString(R.string.audit_trail_pick_cancel))` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 208 | `id نامشخص` | `picker.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 282 | `id نامشخص` | `Toast.makeText(this@AuditTrailActivity, message, Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 347 | `id نامشخص` | `getString(R.string.audit_trail_export_empty), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 362 | `id نامشخص` | `getString(R.string.audit_trail_export_saved, file.absolutePath), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 371 | `id نامشخص` | `getString(R.string.audit_trail_export_error, e.message ?: ""), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 418 | `id نامشخص` | `startActivity(viewIntent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 425 | `id نامشخص` | `startActivity(Intent.createChooser(sendIntent, getString(R.string.audit_trail_export_share)))` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 428 | `id نامشخص` | `Toast.makeText(this, getString(R.string.audit_trail_export_open_failed, file.absolutePath), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 591 | `id نامشخص` | `.setPositiveButton(getString(R.string.audit_trail_dialog_ok), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 597 | `id نامشخص` | `dialog.setNegativeButton(getString(R.string.audit_trail_dialog_open_statement)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 601 | `id نامشخص` | `dialog.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 607 | `id نامشخص` | `startActivity(Intent(this, ReportActivity::class.java))` | Intent → ReportActivity |
| 610 | `id نامشخص` | `startActivity(Intent(this, TransactionManageActivity::class.java))` | Intent → TransactionManageActivity |
| 624 | `id نامشخص` | `startActivity(intent)` | Intent → StudentProfileActivity |
| 627 | `id نامشخص` | `private fun toast(message: String) = Toast.makeText(this, message, Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 681 | `id نامشخص` | `holder.card.setOnClickListener { showDiffDialog(item) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 682 | `id نامشخص` | `holder.tvEntity.setOnClickListener { openEntity(item) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 685 | `id نامشخص` | `holder.tvRefs.setOnClickListener { openStudentStatement(item) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 687 | `id نامشخص` | `holder.tvRefs.setOnClickListener(null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 247 | `val response = api.getLogs(` | `GET audit-trail/logs` |
| 327 | `val response = api.getLogs(` | `GET audit-trail/logs` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 123 | `spEntityType.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, entityLabels)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 124 | `spAction.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, actionLabels)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 145 | `etEntityId.setText("")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 146 | `etSearch.setText("")   // FIX (گروه۲/آیتم۸): جست‌وجوی نام هم پاک می‌شود` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 212 | `btnFromDate.text = fromDate ?: getString(R.string.audit_trail_date_from)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 213 | `btnToDate.text = toDate ?: getString(R.string.audit_trail_date_to)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 242 | `btnLoadMore.text = getString(R.string.audit_trail_loading_more)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 261 | `btnLoadMore.text = getString(R.string.audit_trail_load_more)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 276 | `btnLoadMore.text = getString(R.string.audit_trail_load_more)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 279 | `tvEmpty.text = message` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 290 | `tvEmpty.text = getString(R.string.audit_trail_empty)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 293 | `tvSummary.text = getString(R.string.audit_trail_summary_empty)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 297 | `adapter = AuditLogAdapter(logs).also { rvLogs.adapter = it }` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 298 | `tvSummary.text = getString(R.string.audit_trail_summary, logs.size, totalCount, currentPage, maxOf(totalPages, 1))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 656 | `holder.tvIcon.text = actionIcon(item.action)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 657 | `holder.tvAction.text = displayActionLabel(item)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 658 | `holder.tvEntity.text = getString(` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 661 | `holder.tvMeta.text = getString(` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 670 | `holder.tvRefs.text = getString(R.string.audit_trail_refs_line, refs)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 672 | `holder.tvDiff.text = displayDiff(item)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 673 | `holder.tvIp.text = getString(R.string.audit_trail_item_ip, item.ipAddress ?: "—")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
