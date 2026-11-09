# SessionHistoryActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/SessionHistoryActivity.kt:35`
- layout و محل bind:
  - `R.layout.activity_session_history` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/SessionHistoryActivity.kt:39`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_ession_history.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 55 | `id نامشخص` | `if (list.isEmpty()) Toast.makeText(this@SessionHistoryActivity, getString(R.string.shist_empty), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 61 | `id نامشخص` | `withContext(Dispatchers.Main) { Toast.makeText(this@SessionHistoryActivity, getString(R.string.shist_error), Toast.LENGTH_SHORT).show() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 53 | `val list = api.getHistory(HistoryRequest(classId))` | `GET admin/session_history, GET messages/conversations/{id}/history, POST attendance/get_history, GET sms/history` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 56 | `rv.adapter = HistoryAdapter(list)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 85 | `holder.date.text = holder.itemView.context.getString(R.string.shist_date, item.date)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 86 | `holder.attendees.text = holder.itemView.context.getString(R.string.shist_att, item.attendees)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 87 | `holder.cost.text = holder.itemView.context.getString(R.string.shist_cost, String.format("%,d", item.cost_per_student))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 93 | `holder.tvTime.text = if (end.isNotEmpty()) holder.itemView.context.getString(R.string.shist_time_full, item.start_time, end) else holder.itemView.context.getString(R.string.shist_time_start, item.start_time)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 102 | `holder.tvStatus.text = holder.itemView.context.getString(R.string.shist_st_done)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 108 | `holder.tvStatus.text = holder.itemView.context.getString(R.string.shist_st_modified)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 114 | `holder.tvStatus.text = holder.itemView.context.getString(R.string.shist_st_deleted)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 120 | `holder.tvStatus.text = statusVal` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
