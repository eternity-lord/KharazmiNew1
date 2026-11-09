# PendingClassDetailActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/PendingClassDetailActivity.kt:16`
- layout و محل bind:
  - `R.layout.activity_pending_class_detail` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/PendingClassDetailActivity.kt:28`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_ending_class_detail.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 49 | `btnConfirmClass` | `findViewById<View>(R.id.btnConfirmClass).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 62 | `id نامشخص` | `Toast.makeText(this@PendingClassDetailActivity, getString(R.string.pclsdet_no_student), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 80 | `id نامشخص` | `Toast.makeText(this@PendingClassDetailActivity, getString(R.string.common_ok_msg, res.message), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 86 | `id نامشخص` | `.setPositiveButton(getString(R.string.pclsdet_understood)) { _, _ -> finish() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 87 | `id نامشخص` | `.setOnCancelListener { finish() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 88 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 90 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 97 | `id نامشخص` | `Toast.makeText(this@PendingClassDetailActivity, getString(R.string.pclsdet_op_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| — | فراخوانی `api.method` پیدا نشد | — |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 35 | `findViewById<TextView>(R.id.tvHeaderTitle).text = getString(R.string.pclsdet_header, title)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 37 | `findViewById<TextView>(R.id.tvTeacherAsk).text = String.format("%,d", teacherPrice)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 38 | `findViewById<TextView>(R.id.tvInstShare).text = String.format("%,d", instituteShare)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 39 | `findViewById<TextView>(R.id.tvFinalCost).text = getString(R.string.common_toman_format, teacherPrice + instituteShare)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 64 | `rv.adapter = PendingStudentAdapter(response.students)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 112 | `holder.tvName.text = "${position + 1}. ${list[position].student_name}"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
