# ParentPortalActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ParentPortalActivity.kt:84`
- layout و محل bind:
  - `R.layout.activity_parent_portal` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ParentPortalActivity.kt:118`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_arent_portal.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 157 | `id نامشخص` | `btnRequestOtp.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 162 | `id نامشخص` | `Toast.makeText(this, getString(R.string.portal_mobile_invalid), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 166 | `id نامشخص` | `btnLoginPortal.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 171 | `id نامشخص` | `Toast.makeText(this, getString(R.string.portal_code_length), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 175 | `id نامشخص` | `btnSwitchChild.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 182 | `id نامشخص` | `btnViewClasses.setOnClickListener { showClassesDialog() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 183 | `id نامشخص` | `btnViewAttendance.setOnClickListener { showAttendanceDialog() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 184 | `id نامشخص` | `btnViewGrades.setOnClickListener { showGradesDialog() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 185 | `id نامشخص` | `btnViewHomework.setOnClickListener { showHomeworkDialog() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 186 | `id نامشخص` | `btnViewExams.setOnClickListener { showExamsDialog() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 187 | `id نامشخص` | `btnViewInstallments.setOnClickListener { showInstallmentsDialog() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 188 | `id نامشخص` | `btnViewNotifications.setOnClickListener { showNotificationsDialog() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 198 | `id نامشخص` | `Toast.makeText(this@ParentPortalActivity, getString(R.string.common_ok_msg, res.message), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 206 | `id نامشخص` | `Toast.makeText(this@ParentPortalActivity, getString(R.string.pportal_not_registered), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 234 | `id نامشخص` | `Toast.makeText(this@ParentPortalActivity, getString(R.string.portal_code_wrong), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 260 | `id نامشخص` | `Toast.makeText(this@ParentPortalActivity, getString(R.string.pportal_child_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 271 | `id نامشخص` | `Toast.makeText(this, getString(R.string.common_session_save_fail), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 304 | `id نامشخص` | `Toast.makeText(this@ParentPortalActivity, getString(R.string.pportal_balance_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 319 | `id نامشخص` | `builder.setItems(list.toTypedArray(), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 321 | `id نامشخص` | `builder.setPositiveButton(getString(R.string.btn_dismiss), null).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 333 | `id نامشخص` | `builder.setItems(items, null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 335 | `id نامشخص` | `builder.setPositiveButton(getString(R.string.btn_dismiss), null).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 347 | `id نامشخص` | `builder.setItems(items, null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 349 | `id نامشخص` | `builder.setPositiveButton(getString(R.string.btn_dismiss), null).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 361 | `id نامشخص` | `builder.setItems(items, null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 363 | `id نامشخص` | `builder.setPositiveButton(getString(R.string.btn_dismiss), null).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 375 | `id نامشخص` | `builder.setItems(items, null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 377 | `id نامشخص` | `builder.setPositiveButton(getString(R.string.btn_dismiss), null).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 390 | `id نامشخص` | `builder.setItems(items, null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 392 | `id نامشخص` | `builder.setPositiveButton(getString(R.string.btn_dismiss), null).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 404 | `id نامشخص` | `builder.setItems(items, null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 406 | `id نامشخص` | `builder.setPositiveButton(getString(R.string.btn_dismiss), null).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 433 | `id نامشخص` | `holder.itemView.setOnClickListener { onClick(item) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 196 | `val res = api.requestOtp(ParentOtpRequest(mobile))` | `POST parent/request_otp, POST auth/student/request_otp` |
| 216 | `val res = api.parentLogin(ParentLoginRequest(parentMobile, otp))` | `POST parent/login` |
| 251 | `val res = api.selectChild(ChildSelectRequest(tempToken, studentId))` | `POST parent/select_child` |
| 288 | `val profile = api.getChildProfile()` | `GET parent/child_profile` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 242 | `rvChildren.adapter = ChildrenAdapter(multipleChildrenList) { child ->` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 293 | `tvChildName.text = getString(R.string.portal_person_name, profile.info.name)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 294 | `tvChildCode.text = getString(R.string.portal_national, profile.info.national_code)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 297 | `tvWalletBalance.text = getString(R.string.portal_money, formatter.format(profile.wallet.balance))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 298 | `tvTotalDebt.text = getString(R.string.portal_money, formatter.format(profile.wallet.total_debt))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 431 | `holder.title.text = holder.itemView.context.getString(R.string.common_person_row, item.name)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 432 | `holder.subtitle.text = holder.itemView.context.getString(R.string.pportal_child_hint)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
