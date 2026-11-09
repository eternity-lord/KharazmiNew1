# MessageActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/MessageActivity.kt:87`
- layout و محل bind:
  - `R.layout.activity_message_list` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/MessageActivity.kt:109`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_essage_list.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 149 | `id نامشخص` | `btnBack.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 154 | `id نامشخص` | `btnSend.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 161 | `id نامشخص` | `btnBroadcast.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 166 | `id نامشخص` | `Toast.makeText(this, getString(R.string.msg_empty), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 178 | `id نامشخص` | `Toast.makeText(this@MessageActivity, getString(R.string.msg_no_conv), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 191 | `id نامشخص` | `Toast.makeText(this@MessageActivity, getString(R.string.msg_inbox_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 210 | `id نامشخص` | `Toast.makeText(this@MessageActivity, getString(R.string.msg_pin_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 236 | `id نامشخص` | `Toast.makeText(this@MessageActivity, getString(R.string.msg_list_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 258 | `id نامشخص` | `Toast.makeText(this@MessageActivity, getString(R.string.msg_send_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 274 | `id نامشخص` | `Toast.makeText(this@MessageActivity, getString(R.string.msg_group_ok), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 283 | `id نامشخص` | `Toast.makeText(this@MessageActivity, getString(R.string.msg_group_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 331 | `id نامشخص` | `holder.itemView.setOnClickListener { onClick(item) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 332 | `id نامشخص` | `holder.itemView.setOnLongClickListener { onLongClick(item); true }` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 175 | `val list = api.getConversations()` | `GET messages/conversations` |
| 202 | `val res = api.setPin(conv.id, PinToggleRequest(!conv.is_pinned))` | `POST messages/conversations/{id}/pin` |
| 227 | `val msgs = api.getHistory(activeConversationId)` | `GET admin/session_history, GET messages/conversations/{id}/history, POST attendance/get_history, GET sms/history` |
| 248 | `api.sendMessage(activeConversationId, req)` | `POST messages/conversations/{id}/send` |
| 272 | `api.sendBroadcast(req)` | `POST messages/broadcast` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 185 | `rvConversations.adapter = convAdapter` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 219 | `findViewById<TextView>(R.id.tvMessageTitle).text = title` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 229 | `rvHistory.adapter = ChatAdapter(msgs, currentUserId, role)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 250 | `etCompose.text = null` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 275 | `etBroadcast.text = null` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 321 | `holder.title.text = item.title` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 322 | `holder.msg.text = item.last_message` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 323 | `holder.time.text = item.last_time` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 358 | `holder.text.text = item.body` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 359 | `holder.time.text = item.created_at` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
