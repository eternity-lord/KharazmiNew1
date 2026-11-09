# ClassManagementActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ClassManagementActivity.kt:30`
- layout و محل bind:
  - `R.layout.activity_class_management` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ClassManagementActivity.kt:46`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_lass_management.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 66 | `id نامشخص` | `fabAddClass.setOnClickListener {` | Intent → AddClassActivity |
| 68 | `id نامشخص` | `startActivity(intent)` | Intent → AddClassActivity |
| 82 | `id نامشخص` | `btnBulkSuspend.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 84 | `id نامشخص` | `Toast.makeText(this, getString(R.string.cmgmt_no_access), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 85 | `id نامشخص` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 89 | `id نامشخص` | `Toast.makeText(this, getString(R.string.cmgmt_no_pick), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 90 | `id نامشخص` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 123 | `id نامشخص` | `Toast.makeText(this@ClassManagementActivity, getString(R.string.common_list_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 155 | `id نامشخص` | `withContext(Dispatchers.Main) { Toast.makeText(this@ClassManagementActivity, "ویرایش کلاس انجام نشد", Toast.LENGTH_SHORT).show() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 181 | `id نامشخص` | `.setPositiveButton(getString(R.string.cmgmt_bulk_yes)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 184 | `id نامشخص` | `.setNegativeButton(getString(R.string.action_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 185 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 198 | `id نامشخص` | `Toast.makeText(this@ClassManagementActivity, getString(R.string.common_ok_msg, res.message), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 206 | `id نامشخص` | `Toast.makeText(this@ClassManagementActivity, getString(R.string.cmgmt_bulk_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 242 | `id نامشخص` | `context.startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 277 | `id نامشخص` | `holder.cbSelectClass.setOnCheckedChangeListener(null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 279 | `id نامشخص` | `holder.cbSelectClass.setOnCheckedChangeListener { _, isChecked ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 304 | `id نامشخص` | `tv.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 321 | `id نامشخص` | `holder.tvTopStudents.setOnClickListener {` | Intent → ClassDetailActivity |
| 324 | `id نامشخص` | `holder.itemView.context.startActivity(intent)` | Intent → ClassDetailActivity |
| 347 | `id نامشخص` | `holder.btnSuspend.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 354 | `id نامشخص` | `Toast.makeText(holder.itemView.context, response.message, Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 359 | `id نامشخص` | `Toast.makeText(holder.itemView.context, getString(R.string.cmgmt_suspend_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 371 | `id نامشخص` | `holder.btnRegisterInvoice.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 378 | `id نامشخص` | `holder.itemView.context.startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 382 | `id نامشخص` | `holder.itemView.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 388 | `id نامشخص` | `holder.itemView.context.startActivity(intent)` | Intent → ClassDetailActivity |
| 393 | `id نامشخص` | `holder.itemView.setOnLongClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 114 | `fullClassList = api.getAllClasses()` | `GET classes/list` |
| 196 | `val res = api.suspendBulkClasses(BulkSuspendRequest(selectedClassIds.toList()))` | `POST admin/classes/suspend_bulk` |
| 196 | `val res = api.suspendBulkClasses(BulkSuspendRequest(selectedClassIds.toList()))` | `نامشخص در declarationهای Retrofit` |
| 353 | `val response = withContext(Dispatchers.IO) { api.suspendClassAdmin(item.id) }` | `POST admin/classes/{id}/suspend_s` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 117 | `rvClasses.adapter = adapter` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 252 | `holder.tvTitle.text = item.title` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 253 | `holder.tvCode.text = getString(R.string.cmgmt_code_row, item.code)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 254 | `holder.tvGradeLevel.text = item.grade_level` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 257 | `holder.tvGender.text = ""` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 259 | `holder.tvSessionCount.text = getString(R.string.cmgmt_sessions_row, item.session_count)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 285 | `btnBulkSuspend.text = getString(R.string.cmgmt_bulk_btn, selectedClassIds.size)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 293 | `holder.tvTeacher.text = getString(R.string.cmgmt_teacher_row, item.teacher_name ?: getString(R.string.cmgmt_unknown))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 299 | `tv.text = getString(R.string.common_bullet_row, name)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 311 | `tv.text = getString(R.string.cmgmt_no_students)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 320 | `holder.tvTopStudents.text = topStudentsText` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 330 | `holder.tvTotalDebt.text = String.format("%,d", item.total_debt)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 331 | `holder.tvTeacherDebt.text = String.format("%,d", item.debt_to_teacher)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 332 | `holder.tvInstituteDebt.text = String.format("%,d", item.debt_to_institute)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 340 | `holder.btnSuspend.text = getString(R.string.cmgmt_activate)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 344 | `holder.btnSuspend.text = getString(R.string.cmgmt_suspend)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 400 | `btnBulkSuspend.text = getString(R.string.cmgmt_bulk_btn_one)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
