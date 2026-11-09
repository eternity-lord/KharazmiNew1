# Checkpoint — L-group status sweep (read-only)

Date: 2026-09-12. No code changes. No compile/run.

Verdicts: ❌10 = L1,L2,L3,L4,L5,L6,L7,L8,L10,L11,L12,L13 (12? recount below).
Recount: ❌ = L1,L2,L3,L4,L5,L6,L7,L8,L10,L11,L12,L13 (12 items);
⚠️ = L9,L14 (2 items); ✅ = L15 (1 item). Total 15.

- L1 ❌: 31 printStackTrace در اپ؛ پرینت فارسی با student_id در attendance.py:474/476 (+356/391).
- L2 ❌: باقیمانده همیشه به idxهای اول (financial_calculations.py:243/258).
- L3 ❌: parent.py:181 نام فرزندان با national_code (لیست پیش‌انتخاب؛ خود select_child پاک است).
- L4 ❌: Transaction فقط id/remittance ایندکس (models.py:243-256)؛ student_id/date بدون ایندکس.
- L5 ❌: ۶۹ فایل kt با فارسی هاردکد؛ strings.xml با ۲۰۰ رشته هست ولی حاشیه‌ای.
- L6 ❌: NewInvoiceApi دو نسخه‌ی زنده (ApiInterfaces.kt:35 برای InvoiceActivity؛ ui/MainRepository.kt:41 برای MainRepository).
- L7 ❌: paid_at میلادیِ now() با فرمت مشابه شمسی کنار due_date شمسی (finance.py:417 و ۴ جای دیگر)؛ H3 فقط خواندن را تبدیل کرد.
- L8 ❌: teachers/list با .all() بدون pagination (teachers.py:74).
- L9 ⚠️: لاگین/ثبت‌نام‌ها/پرداخت Invoice گارد دارند (loading/isEnabled) ولی دستی و per-screen؛ DebouncedRequest فقط در ۱ صفحه، GoldButton فقط ۴ لی‌آوت — تضمین سیستمی نیست.
- L10 ❌: بدون چک‌باکس (activity_login.xml)؛ هر لاگین موفق SAVED_PASS می‌نویسد (LoginActivity:~240).
- L11 ❌: فقط ۲ اندپوینت (students.py:447، teachers.py:392) و همان‌ها با حذف version از درخواست دور زده می‌شوند.
- L12 ❌: column_exists با except→False (main.py:121) patched را ساکت رد می‌کند؛ بقیه فقط print.
- L13 ❌: حدس substring سر جاست (financial_calculations.py:219-226)؛ «متوسطه» تنها ← سبد high_school.
- L14 ⚠️: نوشتن‌های مالی همه گارد نقش/IDOR دارند (۴۳+۱۸ دپ + verifyها) ولی ۱۰۰ اندپوینت bare مانده و خواندن‌های پهن مثل teachers/list (هر لاگینی، موبایل همه) بدون چک‌اند.
- L15 ✅: کدهای Integer UNIQUE + tracking رشته‌ای + ۳۱ مصرف sequence — درست و سالم.
