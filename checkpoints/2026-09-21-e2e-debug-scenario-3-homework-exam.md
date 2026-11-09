# فاز دیباگ — سناریوی end-to-end #۳: تکالیف و آزمون‌ها (ثبت معلم → شاگرد → تصحیح → پورتال ولی)

- **تاریخ:** ۲۰۲۶-۰۹-۲۱ · **Branch:** `arena/01a0bf8d-kharazmiapp`
- **Base HEAD:** `84c5dd8` (سناریوی ۲)
- **فایل تست:** `Kharazmi_Server/tests/test_e2e_homework_exam_grading.py` (۱۲ تست)
- **قاعدهٔ فاز:** صفر تغییر در کد برنامه — فقط تست و گزارش.

## ۱) زنجیرهٔ سنجیده‌شده

| مرحله | از سمت اپ | سرور | دیتابیس |
|---|---|---|---|
| ثبت تکلیف | `HomeworkActivity.kt:74` → `POST /homework/create` | 200 + اعلان به دانش‌آموزان ثبت‌نام‌شده | `homeworks` (status=pending) + `notifications` (type=homework) |
| تحویل فایل | `HomeworkActivity.kt:59` → `POST /homework/submissions/{id}/submit` | 200 (یا 409 قبلاً تحویل شده) | `homework_submissions` (فایل زیر `uploads/homework/`) |
| تصحیح | `HomeworkActivity.kt:83` → `POST /homework/submissions/{id}/grade` | 200 | `homework_submissions.status=graded` + score/feedback |
| ثبت آزمون | `ExamActivity.kt:75/78` → `POST /exams/create` + `/exams/{id}/questions` | 200 + اعلان (type=exam) | `exams` + `exam_questions` |
| شرکت در آزمون | `ExamActivity.kt:81` → `POST /exams/attempts/{id}/start` و `/submit` | 200 | `exam_attempts` + `grades` (نمرهٔ خودکار) + اعلان type=grade |
| نمای ولی | `HomeworkActivity.kt:86` → `GET /homework/parent/child/{id}` | 200 فقط برای فرزند خودش (۴۰۳ برای دیگران) | — |
| پورتال شاگرد | `StudentPortalActivity.kt:41` → `GET /students/my_profile` | 200 | از `portal_data.py` |

## ۲) نتیجهٔ تست‌ها

| سنجش | نتیجه |
|---|---|
| فایل سناریوی ۳ | ✅ **12 passed** |
| کل سوئیت | ✅ **999 passed** (88.02s) |
| md5 دیتابیس واقعی | ✅ بدون تغییر `f048f8d118b33c4eaa944490594121d7` |

## ۳) 🐞 یافته‌ها

### یافتهٔ ۳-الف — دسترسی دانش‌آموزِ حذف‌شده از کلاس هنوز باز است — **بالا**

مسیر حذف: ادمین → `DELETE /enrollments/{id}` (`routers/classes.py:489`) → `perform_delete_enrollment`
(`dependencies.py:382`) ⇒ `Enrollment.is_deleted = True`.

اما هیچ‌کدام از مسیرهای زیر این پرچم را فیلتر نمی‌کنند:

| فایل:خط | نقش |
|---|---|
| `homework.py:94` | ارسال اعلان تکلیف |
| `homework.py:158` | لیست تکالیف دانش‌آموز |
| `homework.py:203` | مجوز تحویل فایل |
| `homework.py:315` | نمای تکالیف ولی |
| `exams.py:75` | ارسال اعلان آزمون |
| `exams.py:136` | لیست آزمون‌های دانش‌آموز |
| `exams.py:187` | مجوز شرکت در آزمون |

**اثر اثبات‌شده (تست ۱۱):** دانش‌آموزِ خارج‌شده از کلاس در اپش:
1. تکلیف کلاس را می‌بیند، 2. **فایل تحویل می‌دهد (۲۰۰)**, 3. **در آزمون شرکت می‌کند (۲۰۰)**.

در مقابل، `portal_data.py:59` (فیکس C6) درست فیلتر می‌کند و همان تکلیف/آزمون را در پورتال
نشان **نمی‌دهد** ⇒ ناسازگاری داخلی که خودش شاهد باگ است.
اوج ماجرا: تحویل تکلیف این دانش‌آموز توسط معلم تصحیح می‌شود و نمره ثبت می‌گردد.

### یافتهٔ ۳-ب — نشت اعلان تکلیف/آزمون به دانش‌آموزِ حذف‌شده (زیرشاخهٔ ۳-الف) — **متوسط**

`homework.py:94` و `exams.py:75` با `Enrollment.course_id == ...` **بدون** فیلتر آرشیو، برای همهٔ
ثبت‌نام‌های قدیمی اعلان می‌فرستند ⇒ اعلان‌های مزاحم برای خانواده‌ای که دیگر شاگرد کلاس نیست.
(تست‌های ۲ و ۸ این را مستند می‌کنند.)

## ۴) رفتارهای تأییدشدهٔ درست

- ثبت تکلیف: `homeworks` + اعلان به دانش‌آموزِ فعال (type=homework) ✅
- تحویل فایل: ذخیره‌سازی امن زیر `uploads/homework/` با نام sanitize‌شده ✅
- دیرکرد: مهلت گذشته ⇒ `status="late"` (فیکس H3-B3 با مقایسهٔ واقعی تاریخ شمسی) ✅
- تصحیح: `graded` + score + feedback؛ گارد مالکیت ⇒ معلم دیگر ۴۰۳ ✅
- IDOR ولی: ولیِ دانش‌آموز دیگر ۴۰۳؛ خودِ دانش‌آموز ۴۰۳ (رفع L14/Y2-F2) ✅
- آزمون: سوالات + `exam_attempts` + تصحیح خودکار فقط برای سوال عینی + سقف `min(score, exam.max_score)` ✅
- نمرهٔ آزمون با عنوان `آزمون آنلاین: ...` در `grades` + اعلان type=grade به شاگرد و ولی ✅
- پورتال: فقط داده‌های واقعی (C6) و `max_score` به‌صورت **int** با گردکردن نیم‌به‌بالا (۱۸.۵⇒۱۹) ✅

## ۵) Commit و Push

- **Commit message:** `test: add end-to-end homework, exam and grading coverage`
- **سناریوی بعدی:** #۴ مالی: قسط، کیف پول، فاکتور/چاپ، بدهکاران
