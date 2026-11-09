# PendingTeachersActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/PendingTeachersActivity.kt:54`
- layout و محل bind:
  - `R.layout.activity_pending_teachers` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/PendingTeachersActivity.kt:61`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_ending_teachers.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 85 | `id نامشخص` | `Toast.makeText(this@PendingTeachersActivity, getString(R.string.ptch_empty), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 100 | `id نامشخص` | `Toast.makeText(this@PendingTeachersActivity, getString(R.string.ptch_load_error), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 117 | `id نامشخص` | `Toast.makeText(this@PendingTeachersActivity, getString(R.string.common_ok_msg, res.message), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 128 | `id نامشخص` | `Toast.makeText(this@PendingTeachersActivity, getString(R.string.ptch_op_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 141 | `id نامشخص` | `Toast.makeText(this@PendingTeachersActivity, getString(R.string.common_deleted_msg, res.message), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 152 | `id نامشخص` | `Toast.makeText(this@PendingTeachersActivity, getString(R.string.ptch_del_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 206 | `id نامشخص` | `holder.btnApprove.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 211 | `id نامشخص` | `holder.btnReject.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 81 | `val list = api.getPendingTeachers()` | `GET teachers/pending` |
| 115 | `val res = api.approveTeacher(teacherId)` | `POST teachers/approve/{id}` |
| 139 | `val res = api.rejectTeacher(teacherId)` | `DELETE teachers/reject/{id}` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 88 | `rvPending.adapter = PendingAdapter(list,` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 101 | `rvPending.adapter = PendingAdapter(emptyList(),` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 187 | `holder.name.text = displayName` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 188 | `holder.mobile.text = item.mobile ?: ""` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 190 | `holder.branch.text = ctx.getString(` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
