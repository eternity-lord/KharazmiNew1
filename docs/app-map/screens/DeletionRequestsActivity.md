# DeletionRequestsActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/DeletionRequestsActivity.kt:72`
- layout و محل bind:
  - `R.layout.activity_deletion_requests` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/DeletionRequestsActivity.kt:80`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_eletion_requests.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 102 | `id نامشخص` | `Toast.makeText(this@DeletionRequestsActivity, getString(R.string.delreq_empty), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 115 | `id نامشخص` | `Toast.makeText(this@DeletionRequestsActivity, getString(R.string.common_list_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 125 | `id نامشخص` | `.setPositiveButton(getString(R.string.delreq_ok_yes)) { _, _ -> decide(id, true) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 126 | `id نامشخص` | `.setNegativeButton(getString(R.string.action_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 127 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 134 | `id نامشخص` | `.setPositiveButton(getString(R.string.delreq_no_yes)) { _, _ -> decide(id, false) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 135 | `id نامشخص` | `.setNegativeButton(getString(R.string.action_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 136 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 145 | `id نامشخص` | `Toast.makeText(this@DeletionRequestsActivity, getString(R.string.common_ok_msg, res.message), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 152 | `id نامشخص` | `Toast.makeText(this@DeletionRequestsActivity, getString(R.string.delreq_op_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 179 | `id نامشخص` | `.setPositiveButton(getString(R.string.btn_dismiss), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 180 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 226 | `id نامشخص` | `holder.btnApprove.setOnClickListener { onApprove(item.request_id) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 227 | `id نامشخص` | `holder.btnReject.setOnClickListener { onReject(item.request_id) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 228 | `id نامشخص` | `holder.itemView.setOnClickListener { onDetail(item) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 98 | `val list = api.getRequests("pending")` | `GET classes/deletion_requests` |
| 143 | `val res = if (approve) api.approve(id) else api.reject(id, DeletionRejectRequest(null))` | `POST classes/deletion_requests/{id}/approve` |
| 143 | `val res = if (approve) api.approve(id) else api.reject(id, DeletionRejectRequest(null))` | `POST classes/deletion_requests/{id}/reject` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 104 | `rv.adapter = DeletionRequestAdapter(` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 216 | `holder.title.text = item.course_title ?: holder.itemView.context.getString(R.string.delreq_row_title, item.course_id)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 217 | `holder.code.text = holder.itemView.context.getString(R.string.delreq_row_code, item.request_id, item.created_at ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 223 | `holder.teacher.text = holder.itemView.context.getString(R.string.delreq_row_requester, item.requester_name ?: "-", roleFa)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 224 | `holder.price.text = holder.itemView.context.getString(R.string.delreq_row_debt, String.format("%,d", t?.total_debt ?: 0))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 225 | `holder.schedule.text = holder.itemView.context.getString(R.string.delreq_row_stats, t?.students ?: 0, item.snapshot?.sessions_total ?: 0, if (item.forgive_session_charges) holder.itemView.context.getString(R.string.common_yes) else holder.itemView.context.getString(R.string.common_no))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
