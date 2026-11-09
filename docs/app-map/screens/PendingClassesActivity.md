# PendingClassesActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/PendingClassesActivity.kt:38`
- layout و محل bind:
  - `R.layout.activity_pending_classes` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/PendingClassesActivity.kt:47`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_ending_classes.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 53 | `btnPendingBulkApprove, btnPendingRefresh` | `findViewById<Button>(R.id.btnPendingRefresh).setOnClickListener { fetchPending() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 54 | `btnPendingBulkApprove, btnPendingRefresh` | `findViewById<Button>(R.id.btnPendingBulkApprove).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 57 | `btnPendingBulkReject` | `findViewById<Button>(R.id.btnPendingBulkReject).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 114 | `id نامشخص` | `.setPositiveButton(getString(R.string.common_delete_yes)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 118 | `id نامشخص` | `.setNegativeButton(getString(R.string.action_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 119 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 161 | `id نامشخص` | `.setPositiveButton("ثبت رد") { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 165 | `id نامشخص` | `.setNegativeButton(getString(R.string.action_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 166 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 187 | `id نامشخص` | `private fun toast(message: String?) = Toast.makeText(this, message ?: "عملیات انجام شد", Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 216 | `id نامشخص` | `holder.check.setOnCheckedChangeListener(null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 218 | `id نامشخص` | `holder.check.setOnCheckedChangeListener { _, checked -> onSelectionChanged(item.id, checked) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 230 | `id نامشخص` | `holder.btnApprove.setOnClickListener { onApproveClick(item.id) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 231 | `id نامشخص` | `holder.btnReject.setOnClickListener { onRejectClick(item.id) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 70 | `val list = api.getPendingClasses()` | `GET admin/pending_classes, GET teachers/{teacher_id}/pending_classes` |
| 95 | `val response = api.approveClass(id)` | `POST admin/approve_class/{id}` |
| 125 | `val res = api.rejectClass(id, reason)` | `DELETE admin/reject_class/{id}` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 75 | `rv.adapter = PendingClassAdapter(` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 219 | `holder.title.text = item.title?.takeIf { it.isNotBlank() } ?: "کلاس بدون عنوان"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 220 | `holder.code.text = holder.itemView.context.getString(R.string.pcls_code_row, item.code ?: item.id.toString())` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 221 | `holder.teacher.text = holder.itemView.context.getString(R.string.pcls_teacher_row, item.teacher_name?.takeIf { it.isNotBlank() } ?: "نامشخص")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 222 | `holder.price.text = holder.itemView.context.getString(R.string.pcls_price_row, String.format("%,d", item.teacher_price ?: 0L))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 223 | `holder.schedule.text = holder.itemView.context.getString(R.string.pcls_sched_row, item.days ?: "روز نامشخص", item.time ?: "ساعت نامشخص")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 228 | `holder.issue.text = listOf(conflicts, rejection).filter { it.isNotBlank() }.joinToString("\n")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
