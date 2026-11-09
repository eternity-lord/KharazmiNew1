# CalendarActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/CalendarActivity.kt:75`
- layout و محل bind:
  - `R.layout.activity_calendar` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/CalendarActivity.kt:96`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_alendar.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 137 | `id نامشخص` | `btnCheckConflicts.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 141 | `id نامشخص` | `btnManageRooms.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 146 | `id نامشخص` | `btnBack.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 150 | `id نامشخص` | `btnSubmitRoom.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 156 | `id نامشخص` | `Toast.makeText(this, getString(R.string.cal_fill), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 157 | `id نامشخص` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 171 | `id نامشخص` | `Toast.makeText(this@CalendarActivity, getString(R.string.cal_not_found), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 179 | `id نامشخص` | `Toast.makeText(this@CalendarActivity, getString(R.string.cal_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 197 | `id نامشخص` | `Toast.makeText(this@CalendarActivity, getString(R.string.cal_room_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 210 | `id نامشخص` | `Toast.makeText(this@CalendarActivity, getString(R.string.cal_room_done), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 220 | `id نامشخص` | `Toast.makeText(this@CalendarActivity, getString(R.string.cal_room_fail), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 261 | `id نامشخص` | `.setPositiveButton(getString(R.string.cal_conflict_check)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 267 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 268 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 293 | `id نامشخص` | `alertBuilder.setPositiveButton(getString(R.string.common_ok), null).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 299 | `id نامشخص` | `Toast.makeText(this@CalendarActivity, getString(R.string.cal_conflict_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 168 | `val list = api.getCalendarEvents()` | `GET calendar/events` |
| 189 | `val list = api.getRoomsList()` | `GET rooms/list` |
| 208 | `api.createRoom(req)` | `POST rooms/create` |
| 281 | `val res = api.checkConflicts(req)` | `POST calendar/check_conflicts` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 173 | `rvEvents.adapter = CalendarAdapter(list)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 191 | `rvRooms.adapter = RoomsAdapter(list)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 211 | `etRoomName.text = null` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 212 | `etRoomCapacity.text = null` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 213 | `etRoomLocation.text = null` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 251 | `acDay.setText("شنبه", false)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 254 | `etTime.setText("16:00")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 324 | `holder.title.text = item.title` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 325 | `holder.detail.text = item.detail` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 326 | `holder.schedule.text = holder.itemView.context.getString(R.string.cal_time_row, item.schedule)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 329 | `holder.type.text = when (typeVal) {` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 358 | `holder.name.text = holder.itemView.context.getString(R.string.cal_room_row, item.name)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 359 | `holder.capacity.text = holder.itemView.context.getString(R.string.cal_cap_row, item.capacity)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 360 | `holder.location.text = holder.itemView.context.getString(R.string.cal_loc_row, item.location)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
