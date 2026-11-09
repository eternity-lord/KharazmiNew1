# SubmitGradeActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/SubmitGradeActivity.kt:25`
- layout و محل bind:
  - `R.layout.activity_submit_grade` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/SubmitGradeActivity.kt:29`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_ubmit_grade.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 36 | `id نامشخص` | `Toast.makeText(this, getString(R.string.sgrade_incomplete), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 37 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 49 | `btnSubmitGradeFinal, etExamTitle, etScore` | `findViewById<Button>(R.id.btnSubmitGradeFinal).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 56 | `id نامشخص` | `Toast.makeText(this, getString(R.string.sgrade_required), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 57 | `id نامشخص` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 65 | `etScore` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 95 | `id نامشخص` | `Toast.makeText(this@SubmitGradeActivity, getString(R.string.common_ok_msg, res.message), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 100 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 106 | `btnSubmitGradeFinal` | `Toast.makeText(this@SubmitGradeActivity, getString(R.string.sgrade_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 93 | `val res = api.submitGrade(data)` | `POST grades/submit` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 43 | `tvHeader.text = getString(R.string.sgrade_header, studentName)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
