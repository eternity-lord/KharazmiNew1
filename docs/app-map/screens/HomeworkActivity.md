# HomeworkActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/HomeworkActivity.kt:90`
- layout و محل bind:
  - `R.layout.activity_homework_list` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/HomeworkActivity.kt:119`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_omework_list.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 170 | `id نامشخص` | `btnSubmit.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 176 | `id نامشخص` | `Toast.makeText(this, getString(R.string.hw_fill), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 177 | `id نامشخص` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 181 | `id نامشخص` | `Toast.makeText(this, getString(R.string.hw_class_bad), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 182 | `id نامشخص` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 188 | `id نامشخص` | `btnBack.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 200 | `id نامشخص` | `Toast.makeText(this@HomeworkActivity, getString(R.string.hw_created), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 210 | `id نامشخص` | `Toast.makeText(this@HomeworkActivity, getString(R.string.hw_create_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 238 | `id نامشخص` | `Toast.makeText(this@HomeworkActivity, getString(R.string.hw_load_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 261 | `id نامشخص` | `btnUpload.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 278 | `id نامشخص` | `Toast.makeText(this, getString(R.string.hw_file_loading), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 282 | `id نامشخص` | `Toast.makeText(this@HomeworkActivity, getString(R.string.hw_file_done), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 314 | `id نامشخص` | `.setPositiveButton(getString(R.string.hw_grade_btn)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 319 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 320 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 329 | `id نامشخص` | `Toast.makeText(this@HomeworkActivity, getString(R.string.hw_grade_done), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 337 | `id نامشخص` | `Toast.makeText(this@HomeworkActivity, getString(R.string.hw_grade_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 392 | `id نامشخص` | `holder.itemView.setOnClickListener { onClick(item) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 433 | `id نامشخص` | `holder.btnGrade.setOnClickListener { onGradeClick(item) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 198 | `val res = api.createHomework(req)` | `POST homework/create` |
| 221 | `"parent" -> api.getParentChildHomeworks(studentIdForParent)` | `GET homework/parent/child/{student_id}` |
| 222 | `else -> api.getStudentHomeworks()` | `GET homework/student/list` |
| 327 | `api.gradeSubmission(submissionId, GradeSubmissionRequest(score, feedback))` | `POST homework/submissions/{id}/grade` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 201 | `etTitle.text = null` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 202 | `etDesc.text = null` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 203 | `etDueDate.text = null` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 245 | `rvHomeworks.adapter = HomeworkAdapter(list) { hw ->` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 252 | `tvHwDetailTitle.text = hw.title` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 253 | `tvHwDetailDesc.text = hw.description` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 254 | `tvHwDetailDueDate.text = getString(R.string.hw_due_row, hw.due_date)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 294 | `rvSubmissions.adapter = SubmissionsAdapter(mockSubmissions) { sub ->` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 308 | `tvHeader.text = getString(R.string.hw_grade_for, sub.student_name)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 309 | `etScore.setText("20")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 365 | `holder.title.text = item.title` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 366 | `holder.course.text = item.course_title` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 367 | `holder.date.text = holder.itemView.context.getString(R.string.hw_due_short, item.due_date)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 370 | `holder.status.text = when (statusVal) {` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 379 | `holder.score.text = holder.itemView.context.getString(R.string.hw_score_row, item.score, item.max_score)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 386 | `holder.feedback.text = holder.itemView.context.getString(R.string.hw_feedback_row, item.feedback)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 417 | `holder.name.text = item.student_name` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 420 | `holder.status.text = when (statusVal) {` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 428 | `holder.details.text = holder.itemView.context.getString(R.string.hw_det_row, item.score, item.feedback ?: "---")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 430 | `holder.details.text = holder.itemView.context.getString(R.string.hw_det_wait)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
