# PersonListActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/PersonListActivity.kt:30`
- layout و محل bind:
  - `R.layout.activity_person_list` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/PersonListActivity.kt:42`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_erson_list.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 62 | `btnPersonExportExcel` | `findViewById<MaterialButton>(R.id.btnPersonExportExcel).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 68 | `id نامشخص` | `Toast.makeText(this, getString(R.string.plist_excel_start), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 71 | `id نامشخص` | `Toast.makeText(this, getString(R.string.plist_excel_done), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 74 | `id نامشخص` | `Toast.makeText(this, getString(R.string.plist_excel_error, errorMsg), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 80 | `btnPersonExportPdf` | `findViewById<MaterialButton>(R.id.btnPersonExportPdf).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 82 | `btnPersonExportPdf` | `Toast.makeText(this, getString(R.string.plist_print_empty), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 83 | `id نامشخص` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 152 | `id نامشخص` | `Toast.makeText(this@PersonListActivity, getString(R.string.plist_empty_row, roleText), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 166 | `id نامشخص` | `Toast.makeText(this@PersonListActivity, getString(R.string.common_offline_empty), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 196 | `id نامشخص` | `holder.itemView.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 201 | `id نامشخص` | `context.startActivity(intent)` | Intent → StudentProfileActivity, TeacherProfileActivity |
| 205 | `id نامشخص` | `context.startActivity(intent)` | Intent → TeacherProfileActivity |
| 249 | `id نامشخص` | `holder.btnCallTeacher.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 252 | `id نامشخص` | `holder.itemView.context.startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 254 | `id نامشخص` | `Toast.makeText(holder.itemView.context, holder.itemView.context.getString(R.string.plist_no_phone), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 258 | `id نامشخص` | `holder.btnViewProfile.setOnClickListener {` | Intent → TeacherProfileActivity |
| 261 | `id نامشخص` | `holder.itemView.context.startActivity(intent)` | Intent → TeacherProfileActivity |
| 264 | `id نامشخص` | `holder.btnViewClasses.setOnClickListener {` | Intent → TeacherProfileActivity |
| 267 | `id نامشخص` | `holder.itemView.context.startActivity(intent)` | Intent → TeacherProfileActivity |
| 270 | `id نامشخص` | `holder.itemView.setOnClickListener {` | Intent → TeacherProfileActivity |
| 273 | `id نامشخص` | `holder.itemView.context.startActivity(intent)` | Intent → TeacherProfileActivity |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 143 | `api.getStudents(query)` | `GET admin/students/search` |
| 145 | `api.getTeachers(query)` | `GET teachers/list, GET admin/teachers/search` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 48 | `findViewById<TextView>(R.id.tvHeaderTitle).text = title` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 155 | `rv.adapter = ImprovedTeacherAdapter(list)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 157 | `rv.adapter = PersonAdapter(list, mode)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 190 | `holder.tvName.text = item.name ?: ""` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 191 | `holder.tvCode.text = holder.itemView.context.getString(R.string.plist_code_mobile, item.national_code ?: "", item.mobile ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 237 | `holder.tvTeacherName.text = item.name ?: ""` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 238 | `holder.tvTeacherMobile.text = holder.itemView.context.getString(R.string.common_mobile_row, item.mobile ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 239 | `holder.tvNationalCode.text = holder.itemView.context.getString(R.string.plist_national_row, item.national_code ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 242 | `holder.tvTeacherStatus.text = holder.itemView.context.getString(R.string.tprof_suspended)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 245 | `holder.tvTeacherStatus.text = holder.itemView.context.getString(R.string.tprof_active)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
