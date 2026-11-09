# NotificationCenterActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/NotificationCenterActivity.kt:60`
- layout و محل bind:
  - `R.layout.activity_notification_list` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/NotificationCenterActivity.kt:75`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_otification_list.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 105 | `id نامشخص` | `btnMarkAll.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 109 | `id نامشخص` | `.setPositiveButton(getString(R.string.common_yes)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 112 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 113 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 116 | `id نامشخص` | `btnFilter.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 147 | `id نامشخص` | `Toast.makeText(this@NotificationCenterActivity, getString(R.string.notif_list_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 202 | `id نامشخص` | `Toast.makeText(this@NotificationCenterActivity, getString(R.string.notif_all_read), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 209 | `id نامشخص` | `Toast.makeText(this@NotificationCenterActivity, getString(R.string.notif_status_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 238 | `id نامشخص` | `.setPositiveButton(getString(R.string.common_understood), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 239 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 249 | `id نامشخص` | `.setItems(types) { _, which ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 254 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 290 | `id نامشخص` | `holder.itemView.setOnClickListener { onClick(item) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 125 | `val list = api.getNotifications()` | `GET notifications` |
| 128 | `api.getUnreadCount().unread ?: 0` | `GET notifications/unread_count` |
| 200 | `api.markAllRead()` | `POST notifications/read_all` |
| 223 | `api.markRead(item.id)` | `POST notifications/{id}/read` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 157 | `tvUnreadCount.text = getString(R.string.notif_unread_count, count)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 181 | `tvEmpty.text = if (allNotifications.isEmpty()) {` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 191 | `rv.adapter = NotificationAdapter(filtered) { notif ->` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 251 | `btnFilter.text = if (activeFilterType == null) getString(R.string.notif_filter_btn) else getString(R.string.notif_filter_on, types[which])` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 279 | `holder.title.text = item.title ?: ctx.getString(R.string.notif_untitled)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 280 | `holder.date.text = item.created_at ?: ""` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 281 | `holder.body.text = item.body ?: ""` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
