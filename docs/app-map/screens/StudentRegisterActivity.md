# StudentRegisterActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/StudentRegisterActivity.kt:42`
- layout و محل bind:
  - `R.layout.activity_student_register` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/StudentRegisterActivity.kt:86`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_tudent_register.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 94 | `id نامشخص` | `btnNext.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 111 | `id نامشخص` | `btnPrevious.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 205 | `id نامشخص` | `acRegDiscountType.setOnItemClickListener { _, _, _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 212 | `id نامشخص` | `etBirthDate.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 214 | `id نامشخص` | `.setPositiveButtonString(getString(R.string.common_ok))` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 215 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel))` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 233 | `id نامشخص` | `picker.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 256 | `id نامشخص` | `acChooseClass.setOnItemClickListener { parent, _, position, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 348 | `id نامشخص` | `if (!isValid) Toast.makeText(this, getString(R.string.sreg_fix_errors), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 475 | `id نامشخص` | `Toast.makeText(this@StudentRegisterActivity, getString(R.string.common_ok_msg, response.message), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 486 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 494 | `id نامشخص` | `Toast.makeText(this@StudentRegisterActivity, registrationError(e), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 246 | `activeClasses = api.getClassesList().filter { !it.is_suspended }` | `GET classes/list` |
| 471 | `val response = api.registerAndEnrollStudent(data)` | `POST students/register_and_enroll` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 159 | `acGender.setText("آقا", false) // مقدار پیش‌فرض` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 167 | `acStudyStatus.setText("در حال تحصیل", false) // مقدار پیش‌فرض` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 172 | `acRegDiscountType.setText("بدون تخفیف", false)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 190 | `tvRegFinalTuitionPreview.text = getString(R.string.sreg_tuition_preview, String.format(Locale("en", "US"), "%,d", finalTuition))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 228 | `etBirthDate.setText(date)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 254 | `acChooseClass.setText(getString(R.string.sreg_no_class), false)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 354 | `tvReviewName.text = getString(R.string.sreg_rev_name, etFirstName.text, etLastName.text)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 355 | `tvReviewFather.text = getString(R.string.sreg_rev_father, etFatherName.text)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 356 | `tvReviewCode.text = getString(R.string.sreg_rev_code, etNationalCode.text)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 357 | `tvReviewGender.text = getString(R.string.sreg_rev_gender, acGender.text)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 358 | `tvReviewStudyStatus.text = getString(R.string.sreg_rev_study, acStudyStatus.text)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 359 | `tvReviewBirth.text = getString(R.string.sreg_rev_birth, etBirthDate.text)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 360 | `tvReviewMobile.text = getString(R.string.sreg_rev_mobile, etStudentMobile.text)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 361 | `tvReviewParent.text = getString(R.string.sreg_rev_parent, etParentMobile.text)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 362 | `tvReviewDirectEnrollClass.text = getString(R.string.sreg_rev_class, acChooseClass.text)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 369 | `btnNext.text = getString(R.string.common_next)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 373 | `btnNext.text = getString(R.string.sreg_confirm)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 461 | `btnNext.text = getString(R.string.common_sending)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 497 | `btnNext.text = getString(R.string.btn_retry)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
