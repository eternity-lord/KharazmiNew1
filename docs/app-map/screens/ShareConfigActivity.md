# ShareConfigActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ShareConfigActivity.kt:31`
- layout و محل bind:
  - `R.layout.activity_share_config` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ShareConfigActivity.kt:38`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_hare_config.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 46 | `btnSaveShare` | `findViewById<Button>(R.id.btnSaveShare).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 84 | `id نامشخص` | `Toast.makeText(this@ShareConfigActivity, getString(R.string.shcfg_load_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 109 | `id نامشخص` | `Toast.makeText(this@ShareConfigActivity, getString(R.string.common_ok_msg, res.message), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 110 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 116 | `id نامشخص` | `Toast.makeText(this@ShareConfigActivity, getString(R.string.shcfg_save_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 61 | `val data = api.getShares()` | `GET config/share` |
| 107 | `val res = api.updateShares(data)` | `POST config/share/update` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 64 | `etList[0].setText(data.count_1.toString())` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 65 | `etList[1].setText(data.count_2.toString())` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 66 | `etList[2].setText(data.count_3.toString())` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 67 | `etList[3].setText(data.count_4.toString())` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 68 | `etList[4].setText(data.count_5.toString())` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 69 | `etList[5].setText(data.count_6.toString())` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 70 | `etList[6].setText(data.count_7.toString())` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 71 | `etList[7].setText(data.count_8.toString())` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 72 | `etList[8].setText(data.count_9.toString())` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 73 | `etList[9].setText(data.count_10.toString())` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 74 | `etList[10].setText(data.count_11.toString())` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 75 | `etList[11].setText(data.count_12.toString())` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 76 | `etList[12].setText(data.count_13.toString())` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 77 | `etList[13].setText(data.count_14.toString())` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 78 | `etList[14].setText(data.count_15.toString())` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
