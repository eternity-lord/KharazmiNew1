# AddClassActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/AddClassActivity.kt:31`
- layout و محل bind:
  - `R.layout.activity_add_class` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/AddClassActivity.kt:42`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_dd_class.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 62 | `btnSubmitClass` | `findViewById<Button>(R.id.btnSubmitClass).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 80 | `btnColorPicker` | `btnColor.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 86 | `id نامشخص` | `.setItems(colors) { _, which ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 90 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 113 | `id نامشخص` | `acTeacher.setOnItemClickListener { _, _, position, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 130 | `id نامشخص` | `Toast.makeText(this, getString(R.string.aclass_fill_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 168 | `id نامشخص` | `.setPositiveButton(getString(R.string.invoice_confirm_yes)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 171 | `id نامشخص` | `.setNegativeButton(getString(R.string.action_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 172 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 178 | `id نامشخص` | `startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 179 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 186 | `id نامشخص` | `Toast.makeText(this@AddClassActivity, getString(R.string.aclass_submit_error), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 102 | `teachersList = api.getTeachers()` | `GET teachers/list, GET admin/teachers/search` |
| 162 | `val response = api.createClass(data, override)` | `POST classes/create` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 56 | `acTeacher.setText(autoTeacherName)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
