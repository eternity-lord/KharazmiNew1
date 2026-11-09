# SmsActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/SmsActivity.kt:38`
- layout و محل bind:
  - `R.layout.activity_sms` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/SmsActivity.kt:45`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_ms.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 80 | `btnSendSms, etMessage` | `findViewById<Button>(R.id.btnSendSms).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 91 | `id نامشخص` | `Toast.makeText(this, getString(R.string.sms_write_msg), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 105 | `btnSendSms, etMessage` | `Toast.makeText(this@SmsActivity, getString(R.string.sms_sent, res.count), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 103 | `val res = api.sendSms(req)` | `POST sms/send` |
| 123 | `val list = api.getHistory()` | `GET admin/session_history, GET messages/conversations/{id}/history, POST attendance/get_history, GET sms/history` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 107 | `findViewById<TextInputEditText>(R.id.etMessage).text = null` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 125 | `rvHistory.adapter = SmsAdapter(list)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 155 | `holder.target.text = holder.itemView.context.getString(R.string.sms_to_row, targetFa)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 156 | `holder.msg.text = item.message_text` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 157 | `holder.date.text = item.date` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 158 | `holder.count.text = holder.itemView.context.getString(R.string.sms_count_row, item.sent_count)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
