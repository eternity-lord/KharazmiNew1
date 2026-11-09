# ParentContactsActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ParentContactsActivity.kt:30`
- layout و محل bind:
  - `R.layout.activity_parent_contacts` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ParentContactsActivity.kt:39`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_arent_contacts.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 89 | `id نامشخص` | `Toast.makeText(this@ParentContactsActivity, getString(R.string.pcon_empty), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 99 | `id نامشخص` | `Toast.makeText(this@ParentContactsActivity, getString(R.string.common_offline_empty), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 132 | `id نامشخص` | `holder.btnCallParent.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 136 | `id نامشخص` | `startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 138 | `id نامشخص` | `Toast.makeText(this@ParentContactsActivity, getString(R.string.pcon_no_phone), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 143 | `id نامشخص` | `holder.btnSmsParent.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 147 | `id نامشخص` | `startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 149 | `id نامشخص` | `Toast.makeText(this@ParentContactsActivity, getString(R.string.pcon_no_phone), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 154 | `id نامشخص` | `holder.itemView.setOnClickListener {` | Intent → StudentProfileActivity |
| 157 | `id نامشخص` | `startActivity(intent)` | Intent → StudentProfileActivity |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 86 | `networkCall = { api.getParentContacts(null, query.ifEmpty { null }) },` | `GET admin/parent_contacts` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 91 | `rv.adapter = ParentContactsAdapter(list)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 124 | `holder.tvStudentName.text = item.student_name` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 125 | `holder.tvParentPhone.text = getString(R.string.pcon_par_phone, item.parent_mobile.ifEmpty { getString(R.string.pcon_unset) })` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 126 | `holder.tvStudentPhone.text = getString(R.string.pcon_st_phone, item.student_mobile.ifEmpty { getString(R.string.pcon_unset) })` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 129 | `holder.tvClasses.text = getString(R.string.pcon_classes, classesText.ifEmpty { getString(R.string.pcon_unenrolled) })` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
