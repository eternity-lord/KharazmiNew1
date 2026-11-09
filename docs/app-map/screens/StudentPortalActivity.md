# StudentPortalActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/StudentPortalActivity.kt:45`
- layout و محل bind:
  - `R.layout.activity_student_portal` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/StudentPortalActivity.kt:75`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_tudent_portal.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 110 | `id نامشخص` | `btnRequestOtp.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 115 | `id نامشخص` | `Toast.makeText(this, getString(R.string.portal_mobile_invalid), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 119 | `id نامشخص` | `btnLoginPortal.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 124 | `id نامشخص` | `Toast.makeText(this, getString(R.string.portal_code_length), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 129 | `id نامشخص` | `btnViewClasses.setOnClickListener { showClassesDialog() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 130 | `id نامشخص` | `btnViewAttendance.setOnClickListener { showAttendanceDialog() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 131 | `id نامشخص` | `btnViewGrades.setOnClickListener { showGradesDialog() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 132 | `id نامشخص` | `btnViewHomework.setOnClickListener { showHomeworkDialog() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 133 | `id نامشخص` | `btnViewExams.setOnClickListener { showExamsDialog() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 134 | `id نامشخص` | `btnViewInstallments.setOnClickListener { showInstallmentsDialog() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 135 | `id نامشخص` | `btnViewNotifications.setOnClickListener { showNotificationsDialog() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 145 | `id نامشخص` | `Toast.makeText(this@StudentPortalActivity, getString(R.string.common_ok_msg, res.message), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 153 | `id نامشخص` | `Toast.makeText(this@StudentPortalActivity, getString(R.string.sportal_not_found), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 172 | `id نامشخص` | `Toast.makeText(this@StudentPortalActivity, getString(R.string.portal_code_wrong), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 183 | `id نامشخص` | `Toast.makeText(this, getString(R.string.common_session_save_fail), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 215 | `id نامشخص` | `Toast.makeText(this@StudentPortalActivity, getString(R.string.sportal_profile_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 230 | `id نامشخص` | `builder.setItems(list.toTypedArray(), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 232 | `id نامشخص` | `builder.setPositiveButton(getString(R.string.btn_dismiss), null).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 244 | `id نامشخص` | `builder.setItems(items, null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 246 | `id نامشخص` | `builder.setPositiveButton(getString(R.string.btn_dismiss), null).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 258 | `id نامشخص` | `builder.setItems(items, null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 260 | `id نامشخص` | `builder.setPositiveButton(getString(R.string.btn_dismiss), null).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 272 | `id نامشخص` | `builder.setItems(items, null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 274 | `id نامشخص` | `builder.setPositiveButton(getString(R.string.btn_dismiss), null).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 286 | `id نامشخص` | `builder.setItems(items, null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 288 | `id نامشخص` | `builder.setPositiveButton(getString(R.string.btn_dismiss), null).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 301 | `id نامشخص` | `builder.setItems(items, null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 303 | `id نامشخص` | `builder.setPositiveButton(getString(R.string.btn_dismiss), null).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 315 | `id نامشخص` | `builder.setItems(items, null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 317 | `id نامشخص` | `builder.setPositiveButton(getString(R.string.btn_dismiss), null).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 143 | `val res = api.requestOtp(StudentOtpRequest(mobile))` | `POST parent/request_otp, POST auth/student/request_otp` |
| 163 | `val res = api.studentLogin(StudentLoginRequest(studentMobile, otp))` | `POST auth/student/login` |
| 199 | `val profile = api.getStudentProfile()` | `GET students/my_profile, GET students/{id}` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 204 | `tvStudentName.text = getString(R.string.portal_person_name, profile.info.name)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 205 | `tvStudentCode.text = getString(R.string.portal_national, profile.info.national_code)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 208 | `tvWalletBalance.text = getString(R.string.portal_money, formatter.format(profile.wallet.balance))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 209 | `tvTotalDebt.text = getString(R.string.portal_money, formatter.format(profile.wallet.total_debt))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
