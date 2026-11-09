# LiveRosterActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/LiveRosterActivity.kt:28`
- layout و محل bind:
  - `R.layout.activity_live_roster` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/LiveRosterActivity.kt:52`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_ive_roster.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 101 | `id نامشخص` | `Toast.makeText(this@LiveRosterActivity, getString(R.string.lrost_live_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 152 | `id نامشخص` | `holder.btnCallStudent.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 155 | `id نامشخص` | `holder.btnCallParent.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 159 | `id نامشخص` | `holder.itemView.setOnClickListener {` | Intent → StudentProfileActivity |
| 162 | `id نامشخص` | `holder.itemView.context.startActivity(intent)` | Intent → StudentProfileActivity |
| 171 | `id نامشخص` | `view.context.startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 173 | `id نامشخص` | `Toast.makeText(view.context, view.context.getString(R.string.lrost_no_phone), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 88 | `val data = api.getLiveRoster(liveSessionId)` | `نامشخص در declarationهای Retrofit` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 64 | `tvClassInfo.text = getString(R.string.lrost_class_row, classTitle)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 90 | `tvClassInfo.text = getString(R.string.lrost_class_full, data.classTitle, data.teacherName)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 91 | `tvElapsed.text = getString(R.string.lrost_elapsed, data.elapsedMinutes)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 92 | `tvSummary.text = getString(R.string.lrost_summary, data.present, data.absent, data.undetermined)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 94 | `rv.adapter = LiveRosterAdapter(data.students)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 131 | `holder.name.text = item.studentName` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 136 | `holder.status.text = if (item.status == "Late") holder.itemView.context.getString(R.string.lrost_late) else holder.itemView.context.getString(R.string.lrost_present)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 140 | `holder.status.text = if (item.excused) holder.itemView.context.getString(R.string.lrost_excused) else holder.itemView.context.getString(R.string.lrost_absent)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 144 | `holder.status.text = holder.itemView.context.getString(R.string.lrost_unknown)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 149 | `holder.studentPhone.text = holder.itemView.context.getString(R.string.lrost_st_phone, item.studentMobile.ifEmpty { holder.itemView.context.getString(R.string.lrost_unset) })` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 150 | `holder.parentPhone.text = holder.itemView.context.getString(R.string.lrost_par_phone, item.parentMobile.ifEmpty { holder.itemView.context.getString(R.string.lrost_unset) })` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
