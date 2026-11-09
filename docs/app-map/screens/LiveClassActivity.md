# LiveClassActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/LiveClassActivity.kt:31`
- layout و محل bind:
  - `R.layout.activity_live_class` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/LiveClassActivity.kt:73`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_ive_class.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 93 | `tvLiveTitle` | `btnStartLive.setOnClickListener { startLive() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 94 | `tvLiveTitle` | `btnEndLive.setOnClickListener { promptEndLive() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 95 | `id نامشخص` | `btnCancelLive.setOnClickListener { promptCancelLive() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 148 | `id نامشخص` | `Toast.makeText(this@LiveClassActivity, getString(R.string.lcls_start_error, e.message), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 168 | `id نامشخص` | `Toast.makeText(this@LiveClassActivity, getString(R.string.lcls_none), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 169 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 176 | `id نامشخص` | `Toast.makeText(this@LiveClassActivity, getString(R.string.lcls_fetch_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 177 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 207 | `id نامشخص` | `Toast.makeText(this@LiveClassActivity, getString(R.string.lcls_list_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 273 | `id نامشخص` | `.setPositiveButton(getString(R.string.lcls_cancel_button)) { _, _ -> cancelLive() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 274 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_no), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 276 | `id نامشخص` | `dialog.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 295 | `id نامشخص` | `Toast.makeText(this@LiveClassActivity, response.message.ifEmpty { getString(R.string.lcls_cancel_done) }, Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 296 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 304 | `id نامشخص` | `Toast.makeText(this@LiveClassActivity, getString(R.string.lcls_cancel_error, e.message), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 314 | `id نامشخص` | `.setPositiveButton(getString(R.string.common_yes)) { _, _ -> endLive() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 315 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_no), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 317 | `id نامشخص` | `dialog.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 347 | `id نامشخص` | `).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 348 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 357 | `id نامشخص` | `).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 358 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 365 | `id نامشخص` | `Toast.makeText(this@LiveClassActivity, getString(R.string.lcls_end_error, e.message), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 397 | `id نامشخص` | `holder.name.setOnClickListener {` | Intent → StudentProfileActivity |
| 400 | `id نامشخص` | `holder.itemView.context.startActivity(intent)` | Intent → StudentProfileActivity |
| 403 | `id نامشخص` | `holder.rg.setOnCheckedChangeListener(null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 404 | `id نامشخص` | `holder.rgExcused.setOnCheckedChangeListener(null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 416 | `rbLivePresent` | `holder.rg.setOnCheckedChangeListener { _, checkedId ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 433 | `rbLiveExcused` | `holder.rgExcused.setOnCheckedChangeListener { _, checkedId ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 137 | `val response = api.startLive(courseId)` | `نامشخص در declarationهای Retrofit` |
| 158 | `val cur = api.getCurrentLive()` | `نامشخص در declarationهای Retrofit` |
| 254 | `api.saveLiveStatus(liveSessionId, payload)` | `نامشخص در declarationهای Retrofit` |
| 291 | `api.cancelLive(liveSessionId)` | `نامشخص در declarationهای Retrofit` |
| 334 | `api.saveLiveStatus(liveSessionId, finalPayload)` | `نامشخص در declarationهای Retrofit` |
| 335 | `api.endLive(liveSessionId, LiveEndPayload())` | `نامشخص در declarationهای Retrofit` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 92 | `findViewById<TextView>(R.id.tvLiveTitle).text = getString(R.string.lcls_title, classTitle)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 117 | `tvLiveIndicator.text = getString(R.string.lcls_not_started)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 118 | `tvStartedAt.text = getString(R.string.lcls_not_started_hint)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 165 | `findViewById<TextView>(R.id.tvLiveTitle).text = getString(R.string.lcls_title_fallback, classTitle.ifEmpty { cur.courseCode })` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 195 | `rv.adapter = LiveStudentAdapter(` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 217 | `tvLiveIndicator.text = getString(R.string.lcls_live_row, mins)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 218 | `tvStartedAt.text = getString(R.string.lcls_started, elapsedToHm(startedAtTs))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 395 | `holder.name.text = item.student_name` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
