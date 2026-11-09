# گروه ۴ — نمایش خراب

## وضعیت این تحویل: آیتم‌های ۱۷ تا ۲۱ تمام شد

- **آیتم‌ها:** ۱۷ `[پنل ادمین]` · ۱۸ `[پنل معلم]` · ۱۹ `[پنل معلم]` · ۲۰ `[پنل معلم]` · ۲۱ `[پنل ادمین]`
- **تاریخ:** ۲۰۲۶-۰۹-۲۲
- **برنچ کاری جلسه:** `arena/01a0c9b8-kharazmiapp`
- **محدوده:** فقط UI پنل مشخص‌شده و endpoint لازم برای تأمین عددهای پنل معلم؛ مسیرهای پنل مقابل دست‌نخورده ماندند.

> نکتهٔ محیطی: سندهای قبلی گروه ۳ نام برنچ `arena/01a0c867-kharazmiapp` را ثبت کرده‌اند، اما checkout این جلسه طبق قفل Arena روی `arena/01a0c9b8-kharazmiapp` است و تغییر برنچ انجام نشد.

---

## ۱) بازتولید قرمز و لاگ endpoint واقعی

فایل واقعی `Kharazmi_Server/gaj_db.db` فقط برای خواندن بررسی شد و قبل/بعد md5 آن
`f048f8d118b33c4eaa944490594121d7` بود. تست endpoint روی کپی زیر انجام شد:

```text
/tmp/group4_item17.db
```

دادهٔ واقعی کپی‌شده حداقل یک کلاس فعال و یک enrollment فعال داشت:

```text
course_id=1, title=ریاضی کنکور, code=3406, active_students=1
```

مسیر واقعی `/classes/{id}/students_full` با همان route و serialization سرور پاسخ غیرخالی داد:

```text
GET /classes/1/students_full -> 200
course_info.id=1, title=ریاضی کنکور, code=3406
students.length=1
student_id=1, student_name=الارا صیامی, enrollment_id=1
```

دو مسیر مرتبط نیز داده داشتند:

```text
GET /classes/1/details     -> 200, students.length=1
GET /classes/1/full_report -> 200, total_students=1, students.length=1
```

به‌دلیل اینکه DB واقعیِ موجود برای تست انتشار‌یافته کاربر/`user_sessions` ندارد، احراز هویت
زنده با token واقعی ممکن نبود؛ برای بررسی handler واقعی فقط dependency احراز هویت در
`TestClient` به `admin` override شد. درخواست بدون session نیز عمداً بررسی شد و پاسخ مورد
انتظار `401` داد. هیچ داده‌ای در DB واقعی نوشته نشد.

### تست قرمز

تست جدید:

```text
Kharazmi_Server/tests/test_group4_display_fixes.py
```

قبل از فیکس:

```text
1 failed, 2 passed
```

تست شکست‌خورده ثابت کرد مشکل از endpoint خالی نیست، بلکه قرارداد نمایش `RecyclerView`
در `ClassDetailActivity.updateUI` شکسته است.

---

## ۲) ریشهٔ باگ

در `ClassDetailActivity.onCreate`، همان `RecyclerView` متصل به adapter با این خط مخفی می‌شد:

```kotlin
rvStudents.visibility = View.GONE
```

اما در شاخهٔ تب «لیست دانش‌آموزان» (`updateUI(1)`) فقط container نمایش داده می‌شد:

```kotlin
tabContainer.visibility = View.VISIBLE
```

و خود `rvStudents` دوباره `VISIBLE` نمی‌شد. در نتیجه endpoint پاسخ دارای دانش‌آموز بود،
adapter هم داده می‌گرفت، اما ویجت binding‌شده تمام مدت `GONE` می‌ماند و کاربر لیست را
خالی می‌دید.

---

## ۳) فیکس حداقلی آیتم ۱۷ و ۱۸

در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ClassDetailActivity.kt`
داخل شاخهٔ تب دانش‌آموزان این خط اضافه شد:

```kotlin
rvStudents.visibility = View.VISIBLE
```

`TeacherDashboardActivity` برای کلاس تأییدشده به همین `ClassDetailActivity` می‌رود؛
مسیر پنل معلم جداگانه تأیید شد و endpoint مشترک `/classes/{id}/students_full`
برای session واقعی معلم پاسخ `200` و لیست غیرخالی داد.

---

## ۴) آیتم ۱۹ — نام و تم بنر کلاس در پنل معلم

لاگ واقعی endpoint معلم روی کپی DB:

```text
GET /teachers/1/classes (real teacher session) -> 200
[{"id":1,"title":"ریاضی کنکور","code":"3406",
  "grade_level":"کنکور","bg_color":"#FFFFFF", ...}]
```

endpoint نام کلاس و `bg_color` را داشت، اما binding آداپتر به مقدار خام nullable متکی بود
و fallback/visibility صریح نداشت. در `TeacherClassAdapter`:

- نام کلاس با trim و fallback به کد کلاس bind می‌شود؛
- `tvClassTitle` و `tvClassCode` صریحاً visible می‌شوند؛
- `bg_color` روی `MaterialCardView` اعمال می‌شود و رنگ نامعتبر به سفید fallback می‌کند؛
- وضعیت در badge واقعی `tvStatus` و پایه در `tvTeacherName` نمایش داده می‌شود.

این تغییر فقط آداپتر پنل معلم است و مسیر ادمین را تغییر نمی‌دهد.

---

## ۵) آیتم ۲۰ — بدهی بنر کلاس در پنل معلم

قبل از فیکس، endpoint `/teachers/{teacher_id}/classes` فقط title/code/grade/status/
students_preview/bg_color را برمی‌گرداند و هیچ مقدار `total_debt` یا بدهی تفکیکی نداشت؛
درحالی‌که layout همان سه TextView مالی را داشت و آداپتر معلم آن‌ها را bind نمی‌کرد.

فیکس:

- endpoint معلم اکنون `total_debt`، `debt_to_teacher` و `debt_to_institute` را برمی‌گرداند؛
- بدهی کل با `calculate_enrollment_debt` و همان fallback endpoint ادمین محاسبه می‌شود؛
- سه مقدار در `TeacherClassAdapter` به TextViewهای مالی bind می‌شوند.

مقایسهٔ واقعی روی کپی DB با بدهی آزمایشی فقط در کپی:

```text
teacher endpoint: total_debt=900, debt_to_teacher=300, debt_to_institute=200
admin endpoint:   total_debt=900, debt_to_teacher=300, debt_to_institute=200
```

فایل واقعی DB در این probe تغییر نکرد.

---

## ۶) آیتم ۲۱ — حذف جنسیت مختلط از بنر مدیریت کلاس‌ها در پنل ادمین

`gender_type` در مدل/endpoint باقی ماند، اما چون سیستم جنسیت کلاس را ثبت نمی‌کند،
در `ClassManagementActivity.ClassAdapter.onBindViewHolder` فقط `chipGender` برای بنر
ادمین با `View.GONE` مخفی شد و متنش خالی شد.

`item_class_row.xml` و `TeacherClassAdapter` دست‌کاری نشدند؛ بنابراین این فیکس به پنل
معلم یا کامپوننت دیگر نشت نمی‌کند.

---

## ۷) راستی‌آزمایی بعد از فیکس‌های ۱۷ تا ۲۱

- تست قرمز باقی‌مانده‌ها قبل از فیکس: **۳ failed, 4 passed**
- تست گروه ۴: **۷ passed**
- تست گروه ۳ + گروه ۴: **۲۹ passed**
- `ast.parse` روی **۱۳۹ فایل Python**: موفق
- parse همهٔ XML منابع: موفق
- `import main` روی کپی `/tmp`: موفق
- شمارش دستی `{}`/`()`/`[]` برای فایل‌های Kotlin تغییر‌یافته: متعادل؛ اختلاف `ClassDetailActivity` همان `parens=-5` قبلی است
- سوئیت کامل روی کپی `/tmp`: **۱۱۵۵ passed, 74 warnings**
- md5 فایل واقعی قبل/بعد: یکسان و برابر با
  `f048f8d118b33c4eaa944490594121d7`
- کامپایل اندروید: طبق قانون پروژه انجام نشد
- `git diff --check`: موفق

---

## ۸) تغییرات این تحویل

```text
KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ClassDetailActivity.kt
KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/TeacherDashboardActivity.kt
KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ClassManagementActivity.kt
Kharazmi_Server/routers/teachers.py
Kharazmi_Server/tests/test_group4_display_fixes.py
checkpoints/2026-09-22-group4-display.md
```

## ۹) وضعیت گروه ۴

- [x] ۱۷ — پنل ادمین: لیست دانش‌آموزان کلاس
- [x] ۱۸ — پنل معلم: همان لیست، با تأیید جداگانهٔ مسیر پنل معلم
- [x] ۱۹ — پنل معلم: تم/اسم کلاس روی بنر
- [x] ۲۰ — پنل معلم: بدهی به معلم/بدهی کل روی بنر
- [x] ۲۱ — پنل ادمین: حذف متن جنسیت مختلط از بنر مدیریت کلاس‌ها

هر پنج آیتم گروه ۴ تمام شد و قبل از commit، سوئیت کامل روی کپی `/tmp` سبز شد.
