# O-04 — شاگردِ حذف‌شده از کلاس هنوز تکلیف می‌دید/تحویل می‌داد/آزمون می‌داد

- **تاریخ:** ۲۰۲۶-۰۹-۲۱ · **Branch:** `arena/01a0bf8d-kharazmiapp` · **موج:** ۱
- **Base HEAD:** `55089ab` (O-06)
- **دسته:** منطق کد/دسترسی · **شدت:** بالا

## بازتولید (قرمز اول)
سه تست «قفل‌کنندهٔ باگ» سناریو ۳ آگاهانه به انتظار رفتار درست تبدیل شدند ⇒ **هر سه قرمز**:

| تست جدید | انتظار درست | رفتار قبل از فیکس |
|---|---|---|
| `test_2_archived_enrollment_gets_no_homework_notification` | صفر اعلان برای ثبت‌نام آرشیوشده | ۱ اعلان (نشت) |
| `test_8_exam_notification_does_not_leak_to_archived_enrollment` | صفر اعلان آزمون | ۱ اعلان (نشت) |
| `test_11_removed_student_loses_homework_and_exam_access` | ۴۰۳ + لیست بدون تکلیف + کارنامهٔ خالی | ۲۰۰ و ساخت ردیف تحویل/تلاش آزمون |

## ریشه
هشت مسیر، فیلتر آرشیوِ ثبت‌نام را نداشتند (مسیر حذف: `classes.py:489` →
`perform_delete_enrollment` در `dependencies.py:382` که `is_deleted = True` می‌گذارد):

| فایل:خط | نقش |
|---|---|
| `homework.py:94` | ارسال اعلان تکلیف |
| `homework.py:158` | لیست تکالیف دانش‌آموز |
| `homework.py:203` | مجوز تحویل فایل |
| `homework.py:315` | نمای تکالیف ولی |
| `exams.py:75` | ارسال اعلان آزمون |
| `exams.py:136` | لیست آزمون‌های دانش‌آموز |
| `exams.py:187` | مجوز شرکت در آزمون |
| `exams.py:330` | کارنامهٔ شاگرد (اضافه بر فهرست قبلی — طبق دستور) |

## فیکس (حداقلی)
افزودن `Enrollment.is_deleted == False` به همان هشت کوئری، با کامنت `# O-04`؛ هیچ تغییر دیگری
در منطق انجام نشد (نه ۴۰۳ به ۴۰۴ عوض شد، نه پیام‌ها).

## تست
- سناریو ۳: **13 passed** (سه تست به‌روزشده + تست جدید رگرسیون `test_12_active_student_keeps_full_access`).
- کل سوئیت: **1039 passed** (+۱ تست جدید) · md5 دیتابیس واقعی بی‌تغییر.
- `ast.parse` + `from main import app` واقعی: سالم.

## Commit / Push
- پیام: `fix: hide homework, exams and notifications from archived enrollments (O-04)`
