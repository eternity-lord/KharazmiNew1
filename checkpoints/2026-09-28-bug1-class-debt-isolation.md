# Bug 1 — جداسازی بدهی بین کلاس‌های یک دانش‌آموز

## دامنه
فقط باگ نشت بدهی/پرداخت بین دو enrollment بررسی و اصلاح شد. مسیرهای نوشتن wallet در `attendance.py` و مسیرهای ثبت پرداخت/settlement دست‌کاری نشدند.

## ریشه و اصلاح
- `Student.wallet_teacher` و `Student.wallet_institute` کیف کلی دانش‌آموز هستند و دیگر منبع اعداد بدهی کلاس در endpointهای کلاس نیستند.
- `calculate_enrollment_debt_breakdown` اکنون پرداخت را با `enrollment_id` واقعی یا fallback legacy دقیقِ `student_id + course_id` می‌خواند.
- تراکنش عمومیِ بدون `course_id` و `enrollment_id` به هیچ کلاس تخصیص داده نمی‌شود.
- `target_wallet == "both"` با `share_teacher` و `share_institute` در breakdown کلاس شمرده می‌شود.
- `Enrollment.total_paid` برای داده‌های legacy بدون رسید، و رسید legacy برای داده‌های متقابلاً ناقص، بدون دوباره‌شماری reconcile می‌شوند.
- لیست کلاس‌ها، جزئیات کلاس، full report، `students_full` و Excel از breakdown همان enrollment استفاده می‌کنند؛ کلیدهای قبلی حفظ شده‌اند و `wallet_*` در ردیف `students_full` همچنان کیف کلی است.
- پروفایل دانش‌آموز ادمین در `teachers_financial` از همان breakdown استفاده می‌کند و پرداخت‌های `both` را تفکیک می‌کند.
- `finance.py`: شاخهٔ class در `search_advanced` قبلاً wallet کلی و `calculate_student_debt` را در هر ردیف کلاس تکرار می‌کرد؛ اصلاح شد. `student_class_status` نیز قبلاً `due_to_*` را مستقیماً از wallet کلی می‌ساخت؛ اکنون breakdown همان enrollment را مصرف می‌کند. فاکتور `/finance/invoice/{enrollment_id}` و ردیف‌های per-enrollment داشبورد مالی نیز به breakdown وصل شدند. در گزارش teacher grouping نیز بدهی wallet legacy دیگر به تنها کلاس نسبت داده نمی‌شود و در `unassigned_debt` می‌ماند؛ walletهای top-level آن گزارش همچنان صراحتاً student-global هستند.
- `teachers.py`: endpoint `/teachers/{teacher_id}/classes` از قبل در commit `346e1fbb` به breakdown per-enrollment منتقل شده بود؛ کامنت ناسازگار اصلاح و regression واقعی برای بنر معلم اضافه شد.
- `ClassDetailActivity.kt` برای جمع پرداختِ کلاس به `paid_teacher`/`paid_institute` per-enrollment متصل شد، نه wallet کلی. Android compile عمداً اجرا نشد.

## دو تست قرمز CI و بررسی پدر باگ ۱
دو تست قرمز دقیقاً این‌ها بودند:

1. `TestItem11TeacherDashboardInvoiceButton.test_11a_fast_invoice_card_is_role_gated_and_hidden`
   - پیام خطا: `AssertionError: Regex didn't match ...`
   - پیام سفارشی: `باید شاخهٔ «غیر ادمین» داشته باشد`
   - علت: تست فقط دنبال `subRole != "admin"` بود، درحالی‌که کد رفتار درست را با `isAdminUser = subRole == "admin" && userRole != "teacher"` پیاده کرده است.

2. `TestItem11TeacherDashboardInvoiceButton.test_11b_the_invoice_shortcut_only_stays_for_admin`
   - پیام خطا: `ValueError: substring not found`
   - عبارت پیدا نشده: `subRole != "admin"`
   - پیام قراردادی تست: `ثبت listener باید داخل شاخهٔ ادمین باشد، نه قبل از گارد نقش`

همین دو تست روی پدر اولین commit باگ ۱، یعنی `b6b2e83`، نیز اجرا شدند و نتیجه دقیقاً `2 failed, 1 passed, 19 deselected` بود. بنابراین این failureها از قبل قرمز بودند و با باگ ۱ ایجاد نشده بودند.

چرخهٔ قرمز → فیکس → سبز:
- قرمز فعلی و پدر: همان دو failure بالا.
- فیکس آگاهانه: تست‌های lock کننده به رفتار درست فعلی تغییر کردند: تشخیص `isAdminUser`، مخفی‌کردن کارت برای non-admin، و نصب listener فقط داخل شاخهٔ `else`.
- commit جدا: `91f1cfd test(group3): align teacher dashboard role guard`
- تست‌های گروه ۳: `22 passed`.

## مورد ۲۰ قبلی
بله، مورد ۲۰ («بدهی به معلم / بدهی کل غلط روی بنر کلاس در پنل معلم») همان ریشهٔ wallet کلی داشت و بسته شده است. اصلاح logic آن پیش‌تر در `346e1fbb` انجام شده بود و `/teachers/{teacher_id}/classes` اکنون برای هر enrollment از `calculate_enrollment_debt_breakdown` استفاده می‌کند؛ در این batch با سناریوی دوکلاسه و تست واقعی دوباره تأیید شد. بنابراین مورد ۲۰ جداگانه باز نمانده است.

## تست قرمز باگ ۱
روی copy موقت `/tmp/kharazmi-red` از HEAD قبلی با تست جدید:
- `5` تست: `3 failed, 2 passed`
- شکست‌ها نشت wallet در لیست کلاس، عدم احتساب legacy course payment و حذف سهم `both` در پروفایل admin را نشان دادند.

## تست سبز
- تست جدید isolation به‌همراه finance/class/teacher paths: سبز.
- suite مرتبط بعد از اصلاح finance و تست‌های group3: `233 passed`.
- کل suite محلی نهایی: `1190 passed, 76 warnings`.
- static AST parse برای فایل‌های تغییرکرده: موفق.
- import واقعی `main` با `DATABASE_URL=sqlite:////tmp/kharazmi-real-current.db`: موفق، `29` route.
- probe خواندنی روی copy واقعی: موفق؛ snapshot فعلی دانش‌آموز چندکلاسه نداشت، بنابراین enrollment چندکلاسهٔ واقعی برای probe وجود نداشت.

## DB و محیط واقعی
- md5 قبل از probe فایل اصلی `Kharazmi_Server/gaj_db.db`: `f048f8d118b33c4eaa944490594121d7`
- md5 فایل اصلی پس از probe: `f048f8d118b33c4eaa944490594121d7`
- probe فقط روی `/tmp/kharazmi-real-current.db` انجام شد؛ import main روی copy به‌علت auto-patch schema، md5 copy را از `f048f8d118b33c4eaa944490594121d7` به `d6a0a58bea98539e2094f642dab921cf` تغییر داد.

## Commit و CI
- commit اصلی فیکس: `376dcac fix per-class debt isolation`
- commit اصلاح تست‌های قفل‌کنندهٔ گروه ۳: `91f1cfd test(group3): align teacher dashboard role guard`
- commit فیکس finance/teacher follow-up: `8a44d5d fix finance views to use enrollment debt breakdown`
- commit تکمیل unassigned legacy debt در گزارش معلم: `067dc06 fix unassigned legacy debt in teacher reports`
- branch `arena/01a0c9b8-kharazmiapp` push شد.
- CI سبز روی آخرین کد: run `36382465452`
  - لینک: https://github.com/eternity-lord/KharazmiApp/actions/runs/36382465452
  - full suite، cwd-independence guard و md5 guard همگی موفق شدند.
- Android compile اجرا نشده است.
- working tree پس از آخرین commit کد پاک بود؛ تغییر بعدی این checkpoint صرفاً مستندسازی است.
