# گروه ۵ — کلاس زنده و افزودن دانش‌آموز

## وضعیت تحویل

- **آیتم‌ها:** ۲۲ `[پنل معلم، کلاس زنده]` و ۲۳ `[پنل معلم، افزودن دانش‌آموز به کلاس]`
- **تاریخ:** ۲۰۲۶-۰۹-۲۲
- **برنچ:** `arena/01a0c9b8-kharazmiapp`
- **commit نهایی:** تحویل مستقل با پیام `fix(group5): add live class controls and bulk enrollment`؛ شناسهٔ نهایی در `git log` ثبت است.
- **محدوده:** هر دو آیتم در یک batch؛ Android compile عمداً اجرا نشد.

## ۱) بازتولید قرمز پیش از فیکس

تست قراردادی جدید در فایل زیر قبل از تغییر کد اجرا شد:

```text
Kharazmi_Server/tests/test_group5_behavior.py
```

نتیجهٔ قبل از فیکس:

```text
8 failed
```

شکست‌ها دقیقاً قراردادهای موردنیاز را پوشش می‌دادند: شروع خودکار در داشبورد، نبودن دکمه‌های شروع/لغو، نبود endpoint لغو، نبود سطح انتخاب چندتایی، نبود API bulk، نبود مدل پاسخ خلاصه و نبود route bulk.

## ۲) آیتم ۲۲ — کلاس زندهٔ معلم

### رفتار پیاده‌شده

- `TeacherDashboardActivity` در مسیر انتخاب کلاس یا کلاس بعدی دیگر `start_live` را قبل از باز کردن صفحه صدا نمی‌زند؛ فقط `LiveClassActivity` را با `TARGET_COURSE_ID` باز می‌کند.
- `LiveClassActivity` با session موجود در حالت LIVE باز می‌شود، اما برای کلاس انتخاب‌شدهٔ بدون session در حالت «آمادهٔ شروع» می‌ماند و هیچ request شروعی هنگام `onCreate` ندارد.
- دکمهٔ `btnStartLive` شروع واقعی را با `POST /attendance/{course_id}/start_live` انجام می‌دهد؛ بعد از موفقیت، همان روستر، تایمر، snapshot حضور و دکمهٔ پایان قبلی فعال می‌شوند.
- دکمهٔ `btnEndLive` همچنان مسیر قبلی `end_live -> finalize_live_session -> submit_session_and_calculate` را برای ثبت حضور، شهریه و سهم‌ها اجرا می‌کند.
- دکمهٔ `btnCancelLive` کنار دکمهٔ محاسبه قرار گرفت و با تأیید کاربر endpoint مستقل لغو را صدا می‌زند؛ snapshot آخر را برای لغو ارسال نمی‌کند.
- endpoint جدید `POST /attendance/{session_id}/cancel_live` احراز مالکیت را قبل از تغییر انجام می‌دهد و فقط با update اتمیک `LIVE -> CANCELLED`، زمان پایان و roster را پاک می‌کند. این route هیچ `SessionLog`، `Attendance`، محاسبه شهریه یا `Transaction` نمی‌سازد و با auto-end/finalize تداخل ندارد.

### فایل‌های اصلی

```text
KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/LiveClassActivity.kt
KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/LiveApi.kt
KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/TeacherDashboardActivity.kt
KharazmiAdmin/app/src/main/res/layout/activity_live_class.xml
Kharazmi_Server/routers/attendance.py
```

## ۳) آیتم ۲۳ — افزودن چند دانش‌آموز

### رفتار پیاده‌شده

- مسیر تکی `POST /enrollments/add` و تابع `addToClass` دست‌نخورده و فعال باقی ماندند؛ اگر فقط یک دانش‌آموز انتخاب شود، UI همان endpoint تکی را صدا می‌زند.
- دیالوگ جست‌وجوی فعلی، یک `LinearLayout` چندانتخابی دارد و نتایج جست‌وجو را به شکل `CheckBox` با نام و شناسه نمایش می‌دهد.
- برای دو یا چند انتخاب، UI از `POST /enrollments/add_bulk` استفاده می‌کند.
- schema ورودی bulk اطلاعات مشترک شهریه/تخفیف/اقساط را می‌گیرد. route برای هر شناسه یک `EnrollmentCreate` می‌سازد و خود تابع `add_enrollment` را صدا می‌زند؛ بنابراین ruleهای مالکیت معلم، دانش‌آموز معلق، کلاس معلق/آرشیوی، تکراری بودن، تخفیف و منطق مالی مسیر تکی reuse می‌شوند.
- پاسخ bulk شامل `added_count`، `rejected_count`، `added_student_ids` و `rejected[{student_id, reason}]` است و پیام خلاصهٔ فارسی `N اضافه شد، M رد شد` دارد. UI نیز دلیل هر رد را در Toast طولانی نشان می‌دهد.

### فایل‌های اصلی

```text
KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ClassSetupActivity.kt
KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/AppModels.kt
KharazmiAdmin/app/src/main/res/layout/dialog_search_student.xml
Kharazmi_Server/schemas.py
Kharazmi_Server/routers/classes.py
```

## ۴) راستی‌آزمایی قراردادی و endpoint واقعی

تست قراردادی بعد از فیکس:

```text
/tmp/kharazmi-g4-venv/bin/pytest -q Kharazmi_Server/tests/test_group5_behavior.py
8 passed
```

Probe bulk با `TestClient` و دیتابیس in-memory، در کنار مسیر تکی موجود:

```text
POST /enrollments/add_bulk [41, 999] -> 200
message: 1 اضافه شد، 1 رد شد
rejected[0].reason: دانش‌آموز یافت نشد
POST /enrollments/add_bulk [41] (duplicate) -> 200
message: 0 اضافه شد، 1 رد شد
POST /enrollments/add` برای کلاس معلم دیگر -> 403 (مسیر تکی بدون تغییر)
```

Probe endpoint لغو روی کپی واقعی DB در `/tmp` انجام شد؛ یک `LiveSession` فقط در کپی ساخته شد و بعد لغو شد:

```text
POST /attendance/{session_id}/cancel_live -> 200
status: CANCELLED, live_roster: {}
SessionLog/Attendance/Transaction قبل و بعد: یکسان
```

دوباره‌زدن لغو همان session نیز `400` «از قبل بسته یا لغو شده» برگرداند.

## ۵) syntax، import و سوئیت کامل

همهٔ آزمون‌های backend از checkout کپی‌شده در `/tmp` اجرا شدند تا DB واقعی فقط خواندنی بماند:

```text
ast.parse: routers/attendance.py, routers/classes.py, schemas.py, test_group5_behavior.py -> OK
import واقعی main روی /tmp/kharazmi-g5-import-final -> OK
pytest کامل از /tmp/kharazmi-g5-suite/Kharazmi_Server -> 1163 passed, 74 warnings
```

md5 دیتابیس واقعی در این batch:

```text
قبل:  f048f8d118b33c4eaa944490594121d7
بعد:  f048f8d118b33c4eaa944490594121d7
```

`git diff --check` نیز سبز است. هیچ Android compile اجرا نشد.

## ۶) وضعیت پذیرش

- [x] هر دو آیتم ۲۲ و ۲۳ در یک batch انجام شد.
- [x] بازتولید قرمز قبل از فیکس ثبت شد.
- [x] تست قراردادی هر دو آیتم سبز شد.
- [x] مسیر افزودن تکی با تست موجود و probe دوباره بررسی شد.
- [x] endpoint لغو بدون اثر مالی/حضور و غیاب probe شد.
- [x] `ast.parse` و import واقعی `main` روی کپی `/tmp` سبز شد.
- [x] سوئیت کامل: `1163 passed`.
- [x] DB واقعی read-only در وضعیت نهایی و md5 قبل/بعد یکسان است.
- [x] Android compile اجرا نشد.
- [ ] commit جداگانهٔ گروه ۵ و push به branch فعلی — گام پایانی.
