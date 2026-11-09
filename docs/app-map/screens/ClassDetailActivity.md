# ClassDetailActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ClassDetailActivity.kt:142`
- layout و محل bind:
  - `R.layout.activity_class_detail` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ClassDetailActivity.kt:168`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_lass_detail.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 150 | `id نامشخص` | `withContext(Dispatchers.Main) { Toast.makeText(this@ClassDetailActivity, "کلاس به‌روزرسانی شد", Toast.LENGTH_SHORT).show() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 153 | `id نامشخص` | `withContext(Dispatchers.Main) { Toast.makeText(this@ClassDetailActivity, "ویرایش کلاس انجام نشد", Toast.LENGTH_SHORT).show() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 187 | `btnGoToAttendance` | `findViewById<Button>(R.id.btnGoToAttendance).setOnClickListener {` | Intent → AttendanceActivity |
| 192 | `id نامشخص` | `startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 197 | `btnClassSetupAction` | `findViewById<Button>(R.id.btnClassSetupAction).setOnClickListener {` | Intent → ClassSetupActivity |
| 202 | `id نامشخص` | `startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 207 | `btnEditClassInfoAction` | `findViewById<Button>(R.id.btnEditClassInfoAction).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 222 | `btnSuspendAction` | `btnSuspendAction.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 230 | `btnDeleteClassAction` | `findViewById<Button>(R.id.btnDeleteClassAction).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 245 | `btnClassExportExcel` | `findViewById<Button>(R.id.btnClassExportExcel).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 251 | `id نامشخص` | `Toast.makeText(this, getString(R.string.cdetail_excel_downloading), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 254 | `id نامشخص` | `Toast.makeText(this, getString(R.string.cdetail_excel_done), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 257 | `id نامشخص` | `Toast.makeText(this, getString(R.string.cdetail_excel_error, errorMsg), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 263 | `btnClassExportPdf` | `findViewById<Button>(R.id.btnClassExportPdf).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 266 | `id نامشخص` | `Toast.makeText(this, getString(R.string.cdetail_students_not_loaded), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 267 | `id نامشخص` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 303 | `id نامشخص` | `.setPositiveButton(getString(R.string.cdetail_edit_save)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 309 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 310 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 326 | `id نامشخص` | `Toast.makeText(this@ClassDetailActivity, getString(R.string.common_ok_msg, response.message), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 334 | `id نامشخص` | `Toast.makeText(this@ClassDetailActivity, getString(R.string.cdetail_edit_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 350 | `id نامشخص` | `Toast.makeText(this@ClassDetailActivity, getString(R.string.common_ok_msg, response.message), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 358 | `id نامشخص` | `Toast.makeText(this@ClassDetailActivity, getString(R.string.cdetail_suspend_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 385 | `id نامشخص` | `.setPositiveButton(getString(R.string.common_delete_yes)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 388 | `id نامشخص` | `.setNegativeButton(getString(R.string.action_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 391 | `id نامشخص` | `dialog.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 410 | `id نامشخص` | `Toast.makeText(this@ClassDetailActivity, getString(R.string.common_ok_msg, message), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 417 | `id نامشخص` | `finish() // Close page after deletion` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 438 | `id نامشخص` | `.setPositiveButton(getString(R.string.common_understood), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 439 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 445 | `id نامشخص` | `Toast.makeText(this@ClassDetailActivity, getString(R.string.cdetail_net_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 570 | `id نامشخص` | `startActivity(intent)` | Intent → StudentProfileActivity |
| 594 | `id نامشخص` | `Toast.makeText(this@ClassDetailActivity, getString(R.string.cdetail_students_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 627 | `id نامشخص` | `Toast.makeText(this@ClassDetailActivity, getString(R.string.common_offline_empty), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 645 | `id نامشخص` | `Toast.makeText(this@ClassDetailActivity, getString(R.string.cdetail_students_empty), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 667 | `id نامشخص` | `.setPositiveButton(getString(R.string.btn_dismiss), null)` | Intent → SubmitGradeActivity |
| 674 | `id نامشخص` | `startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 677 | `id نامشخص` | `dialog.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 683 | `id نامشخص` | `Toast.makeText(this@ClassDetailActivity, getString(R.string.cdetail_att_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 805 | `id نامشخص` | `holder.itemView.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 810 | `id نامشخص` | `holder.tvStudentName.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 324 | `val response = api.updateClassInfo(classId, ClassUpdateInfo(newTitle))` | `PUT classes/update_info/{course_id}` |
| 348 | `val response = api.suspendClass(classId)` | `POST classes/{id}/suspend, POST classes/{course_id}/suspend` |
| 405 | `api.deleteClass(classId, forgive).message` | `DELETE classes/{course_id}` |
| 407 | `api.requestDeleteClass(classId, DeleteClassRequest(forgive)).message` | `POST classes/{course_id}/request_delete` |
| 465 | `networkCall = { api.getClassReport(classId) },` | `GET classes/{id}/full_report, GET classes/{id}/full_report` |
| 586 | `val response = api.getClassDetails(classId)` | `GET classes/{id}/details, GET classes/{id}/details` |
| 614 | `networkCall = { api.getClassStudentsFull(classId) },` | `GET classes/{id}/students_full` |
| 659 | `val response = api.getStudentAttendanceHistory(` | `POST attendance/student_history` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 180 | `rvStudents.adapter = studentAdapter` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 298 | `etInput.setText(reportData?.info?.title ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 468 | `findViewById<TextView>(R.id.tvPageTitle).text = getString(R.string.cdetail_page_title, data.info.title, data.info.code)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 477 | `tvContent.text = getString(R.string.common_offline_empty)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 530 | `tvContent.text = sb.toString()` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 561 | `tvContent.text = sb.toString()` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 755 | `holder.tvStudentName.text = holder.itemView.context.getString(R.string.cdetail_student_row, student.student_name, codeStr, dValDisp)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 757 | `holder.tvStudentName.text = "${student.student_name}$codeStr"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 761 | `holder.tvStudentMobile.text = holder.itemView.context.getString(R.string.common_mobile_row, fullStudent.mobile)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 764 | `holder.tvStudentPaid.text = holder.itemView.context.getString(R.string.cdetail_att_pct, String.format("%.1f", fullStudent.attendance_rate))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 771 | `holder.tvStudentDebt.text = holder.itemView.context.getString(R.string.cdetail_debt_total, String.format("%,d", totalDebt), breakdown)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 772 | `holder.tvStudentStatus.text = holder.itemView.context.getString(R.string.cdetail_unsettled)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 775 | `holder.tvStudentDebt.text = holder.itemView.context.getString(R.string.cdetail_no_debt)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 776 | `holder.tvStudentStatus.text = holder.itemView.context.getString(R.string.cdetail_settled)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 782 | `holder.tvStudentStatus.text = holder.itemView.context.getString(R.string.cdetail_susp)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 787 | `holder.tvStudentMobile.text = holder.itemView.context.getString(R.string.cdetail_sid_row, student.student_id)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 791 | `holder.tvStudentDebt.text = holder.itemView.context.getString(R.string.cdetail_debt_row, String.format("%,d", student.debt))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 792 | `holder.tvStudentStatus.text = holder.itemView.context.getString(R.string.cdetail_unsettled)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 795 | `holder.tvStudentDebt.text = holder.itemView.context.getString(R.string.cdetail_no_debt)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 796 | `holder.tvStudentStatus.text = holder.itemView.context.getString(R.string.cdetail_settled)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
