# LiveClassesActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/LiveClassesActivity.kt:25`
- layout و محل bind:
  - `R.layout.activity_live_classes` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/LiveClassesActivity.kt:46`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_ive_classes.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 82 | `id نامشخص` | `startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 132 | `id نامشخص` | `holder.itemView.setOnClickListener { onClick(item) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 74 | `val list = api.getLiveSessions()` | `نامشخص در declarationهای Retrofit` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 78 | `rv.adapter = LiveClassesAdapter(list) { item ->` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 86 | `findViewById<TextView>(R.id.tvLiveClassesTitle).text =` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 95 | `tvEmpty.text = getString(R.string.lclss_poll_error)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 126 | `holder.title.text = holder.itemView.context.getString(R.string.lclss_class_row, item.classTitle, item.courseCode)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 127 | `holder.teacher.text = holder.itemView.context.getString(R.string.lclss_teacher_row, item.teacherName)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 128 | `holder.elapsed.text = holder.itemView.context.getString(R.string.lclss_elapsed, item.elapsedMinutes)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 129 | `holder.present.text = holder.itemView.context.getString(R.string.lclss_present, item.present)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 130 | `holder.absent.text = holder.itemView.context.getString(R.string.lclss_absent, item.absent)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 131 | `holder.undetermined.text = holder.itemView.context.getString(R.string.lclss_undet, item.undetermined)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
