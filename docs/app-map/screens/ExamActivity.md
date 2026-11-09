# ExamActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ExamActivity.kt:88`
- layout و محل bind:
  - `R.layout.activity_exam_list` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ExamActivity.kt:118`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_xam_list.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 163 | `id نامشخص` | `btnViewReportCard.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 175 | `id نامشخص` | `Toast.makeText(this@ExamActivity, getString(R.string.exam_empty), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 181 | `id نامشخص` | `Toast.makeText(this@ExamActivity, getString(R.string.exam_joined), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 189 | `id نامشخص` | `Toast.makeText(this@ExamActivity, getString(R.string.exam_list_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 199 | `id نامشخص` | `.setPositiveButton(getString(R.string.exam_start_btn)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 202 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 203 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 224 | `id نامشخص` | `Toast.makeText(this@ExamActivity, getString(R.string.exam_start_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 272 | `id نامشخص` | `btnSubmit.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 299 | `id نامشخص` | `Toast.makeText(this, getString(R.string.exam_submitting), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 309 | `id نامشخص` | `.setPositiveButton(getString(R.string.common_understood)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 314 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 320 | `id نامشخص` | `Toast.makeText(this@ExamActivity, getString(R.string.exam_submit_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 330 | `id نامشخص` | `Toast.makeText(this, getString(R.string.exam_sid_bad), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 334 | `id نامشخص` | `Toast.makeText(this, getString(R.string.exam_report_loading), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 346 | `id نامشخص` | `Toast.makeText(this@ExamActivity, getString(R.string.exam_report_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 399 | `tvDebtInstitute` | `cardPdf.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 403 | `id نامشخص` | `dialog.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 413 | `id نامشخص` | `Toast.makeText(this, getString(R.string.exam_pdf_downloading), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 418 | `id نامشخص` | `startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 172 | `val list = api.getExams()` | `GET exams/student/list` |
| 210 | `val res = api.startAttempt(examId)` | `POST exams/attempts/{exam_id}/start` |
| 304 | `val res = api.submitAttempt(activeAttemptId, req)` | `POST exams/attempts/{attempt_id}/submit` |
| 338 | `val card = api.getReportCard(targetId)` | `GET students/{id}/report_card` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 177 | `rvExams.adapter = HomeworkAdapter(list) { exam ->` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 237 | `tvQuestionNumber.text = getString(R.string.exam_q_number, currentQuestionIndex + 1, activeQuestions.size)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 238 | `tvQuestionText.text = q.question_text` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 247 | `rbOption1.text = q.options[0]` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 248 | `rbOption2.text = q.options[1]` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 257 | `rbOption3.text = q.options[2]` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 258 | `rbOption4.text = q.options[3]` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 268 | `etAnswerText.text = null` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 271 | `btnSubmit.text = if (currentQuestionIndex == activeQuestions.size - 1) getString(R.string.exam_finish_btn) else getString(R.string.exam_next_btn)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 366 | `tvName.text = card.student_name` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 367 | `tvPhone.text = getString(R.string.exam_card_row, card.national_code, card.overall_average)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 383 | `tvContent.text = builder.toString()` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 393 | `tvTotalDebt.text = getString(R.string.exam_pdf_hint)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
