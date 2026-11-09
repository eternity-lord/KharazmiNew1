# Checkpoint — ممیزی تازه‌ی کل پروژه (v2، بعد از همه‌ی فیکس‌ها)

Date: 2026-09-12. Read-only کامل؛ صفر تغییر کد؛ صفر کامپایل (اندروید فقط خوانده شد).

## روش
- سرور: ast.parse هر ۸۰ فایل (۰ خطا) + گرپ الگوهای قدیمی (with_for_update واقعی/کامنتی،
  mobile==، admin هاردکد، session.user_id، raw session lookup) + خواندن کامل ۱۲+ اندپوینت
  حساس + ردیابی ۵ مسیر پول + نمونه‌برداری ۱۷ write-login-only و ۵ خواندن IDOR.
- اندروید: کراس‌رفرنس ۶۳۷ id تعریف‌شده در ۸۵ لی‌آوت با ۵۹۰ id مصرف‌شده در ۷۳ فایل Kotlin +
  استخراج دقیق بدنه‌ی ۴۰ تابع mutating با brace-matching (نه regex سست) + چک caller برای
  دیالوگ + چک دکمه‌ی یتیم در ۱۵ لی‌آوت کلیدی + بایندینگ آداپترها.

## یافته‌های بحرانی/بالا (۹)
1. submit_grade بدون گارد caller (students.py:237) — هر لاگینی (شاگرد!) به هرکس نمره می‌دهد؛
   خواهرهایش (homework/exam) همه ownership چک می‌کنند.
2. submit_session/edit_session بدون caller (attendance.py:353/:704 — حتی پارام authorization
   ندارد) — شاگرد/ولی برای هر کلاس جلسه ثبت می‌کند و کیف‌ها شارژ می‌شوند.
3. update_class_info بدون گارد (classes.py:1070) — هر لاگینی هر کلاسی را rename + تغییر
   grade_level می‌کند (کامیت مستقیم).
4. get_parent_contacts (admin.py:537) — هر لاگینی موبایل همه‌ی شاگردان+والدین را می‌خواند (+ اوراکل کد ملی).
5. ترکیب blind-approve: create_class لاگین‌خالی (classes.py:76، قیمت دلخواه) + approve فقط
   فلیپ (admin.py:527) + اپ «۰» نشان می‌دهد (PendingClassDetail) + سهم سرور هاردکد ۰ (:521).
6. پرداخت بدون idempotency (finance.py:173؛ بدون کلید/یونیک) — retry بعد از timeout = پرداخت
   دوگانه (کیف+total_paid+اقساط)؛ installments هم read-modify-write است (:409-431).
7. استرداد اقساط را باز نمی‌کند (finance.py:988-1150) — پول برمی‌گردد ولی قسط paid می‌ماند.
8. حذف جلسه‌ی تسویه‌شده (attendance.py:919، بدون چک settled) — شارژها برمی‌گردد ولی payout
   معلم می‌ماند + Attendanceها (شامل billed) پاک می‌شود + دو کامیت غیراتمیک.
9. پوشش اقساط cross-enrollment در برابر بدهی per-enrollment (finance.py:393-431 در برابر
   financial_calculations.py:166-184) — قسط F با پول E تسویه می‌شود ولی بدهی F می‌ماند.

## متوسط (۶)
- send_sms لاگین‌خالی (admin.py:146): فعلاً فقط لاگ (اسپم/شمارش فیک)؛ با اتصال درگاه HIGH.
- IDOR خواندن‌ها: get_student_attendance_history (:614)، get_session_details (:667)،
  get_all_installments (finance.py:1158)، get_pending_teachers+mobile (admin.py:197).
- کال‌بک پرداخت خفته (finance.py:712): else ساکت M12-class، بدون branch، تاریخ میلادی،
  اعتماد به query؛ initiate مرده با NameError (:690). PaymentInitiateRequest.target_wallet
  بدون اعتبارسنجی (:656).
- تاریخ جلسه: بدون ولیدیشن سرور + اپ میلادی auto می‌فرستد و فیلدهای تاریخ UI را نادیده
  می‌گیرد (AttendanceActivity.kt:491؛ etSessionDate/Time در XML) — ستون دوقلمی + ریسک
  دابل‌شارژ cross-client.
- ویرایش جلسه دوکامیته (غیراتمیک، در کامنت کد اذعان شده) — پنجره‌ی کرش = جلسه‌ی خالی‌شده.
- نسخه‌ی خوش‌بینانه read-modify-write (students.py:511-513) + with_for_update بی‌اثر.

## پایین/بهداشت
- سرور: classes.py:935 resolver دستی (نه helper)؛ update_installment با with_for_update
  (:1255)؛ admin-username shadowing در لاگین؛ paid_at دومبنا؛ لی‌آوت‌های مرده (item_exam،
  item_dashboard_card، item_report، item_grade، layout_empty)؛ tvError/progressBar مرده در
  لاگین؛ tabSettlement id بلااستفاده (تب‌ها position-based و سالم‌اند).
- اندروید: tvStudents همیشه «در حال بارگذاری...» (item_class_row.xml:169)؛ loadStudents
  بی‌صدا fail می‌شود (PendingClassDetailActivity.kt:61-63)؛ toggleهای تعلیق بدون گارد
  (double-tap = تعلیق/رفع‌تعلیق پیاپی)؛ createHomework/createLead/createRoom/sendPortalLink/
  requestOtp بدون گارد (تکراری/هزینه پیامک)؛ approve/rejectها idempotent و بی‌خطر.
- تمیزها: سینتکس ۸۰/۸۰؛ H17/expiry (get_current_user متمرکز)؛ homework/exam گاردها؛
  رجیستر/لاگین/تسویه/فاکتور؛ بدون دکمه‌ی یتیم در ۱۵ لی‌آوت کلیدی؛ بدون listener خالی/TODO؛
  ShareConfig via getIdentifier؛ L9ها سر جا (باگ اسکریپت اول بود، با brace-matching تأیید شد).
