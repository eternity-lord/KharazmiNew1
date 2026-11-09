# Checkpoint — M بچ ۵ (آخر): شش مورد باقی‌مانده (M5/M7/M14/M18/M19/M28)

Date: 2026-09-12. Asserted + read-back per step. No compile/run.

## قدم ۱ — M5: کیف‌پول BigInteger (models.py:130-131 + main.py:268-285)
- Student.wallet_teacher/institute: Integer ← BigInteger (هم‌خوان با
  Transaction.amount و همه‌ی ستون‌های مالی که از قبل BigInteger بودند).
- مهاجرت auto_patch: فقط Postgres (چک information_schema + ALTER COLUMN TYPE
  BIGINT برای هر ستون غیر-bigint)؛ SQLite نوع را enforce نمی‌کند پس مدل کافی است.
  int→bigint تعریض بدون‌اتلاف است (بدون USING لازم) — دیتای موجود دست‌نخورده.
  بلوک self-contained با try/except+rollback مثل سیدهای مجاور؛ DB تازه (create_all)
  از قبل bigint است پس skip می‌شود.

## قدم ۲ — M7: تحلیل unique+nullable (بدون فیکس)
- username: فقط موبایل canonical (H20، نامعتبر←400) + نام‌های سیستمی student:/parent:
  هرگز ""/space/NULL. national_code: همه‌ی مسیرهای واقعی checksum دارند (ثبت/ویرایش
  معلم، ثبت دانش‌آموز، ثبت‌آنلاین) — "" غیرممکن؛ NULL چندتایی در PG/SQLite مجاز و سالم.
- تنها ""ی زنده: Teacher.mobile در ثبت معلم بدون موبایل (teachers.py:41-43 «else ""»).
  اثرش: معلم دومِ بدون موبایل 409 می‌گیرد (صریح، نه فساد ساکت) + ریس TOCTOU (دو ثبت
  همزمان ← IntegrityError 500). سوءاستفاده‌ی عملی/امنیتی نیست ← طبق دستور بدون فیکس.
- چرا فیکس یک‌خطی (None) نزدیم: پاسخ API موبایل را خام برمی‌گرداند و مدل‌های اپ
  (AppModels.kt) بعضاً `val mobile: String` غیرنال دارند — null فرستادن نیاز به ممیزی
  اپ دارد. فیکس آینده: None + گارد چک یکتایی + نال‌سیف اپ.
- یافته‌ی مجاور (خارج سؤال): کد موقت ملی «0000xxxxxx» در convert سرنخ (crm.py:175)
  چکسام‌نامعتبر در ستون unique می‌نشیند + ریسک تصادم ۱/۹۰۰هزار ← IntegrityError.

## قدم ۳ — M14: پایان اتمیک جلسه‌ی زنده (attendance.py:208-242)
- body.date مرده (pass) حذف شد؛ تاریخ از قبل هم از سرور بود (finalize از
  started_at_ts می‌سازد :~100) — حالا مستند و صریح؛ پارامتر body برای سازگاری ماند.
- فلیپ LIVE→ENDED با UPDATE مشروط + rowcount (الگوی H8-P4)؛ موازی ← همان 400 قبلی.
  احراز به قبل از claim منتقل شد (403 مقدم بر 400؛ غریبه نه وضعیت می‌بیند نه می‌بندد).
- db.refresh بعد از UPDATE خام (رفع stale) + revert به LIVE در except (تا retry ممکن
  شود؛ submit داخلی روی خطا rollback می‌کند پس مالیِ نصفه نمی‌ماند).
- تنها کالر finalize همین end_live است؛ readers دیگر (start-guard، لیست ادمین) با
  ENDED مشکلی ندارند.

## قدم ۴ — M18: خروج فقط دیوایس فعلی (auth.py:330/340-351)
- تشخیص فعلی: هیچ — کد قبلی همه‌ی DeviceTokenهای (user,role) را پاک می‌کرد و
  درخواست هیچ شناسه‌ی دیوایسی نداشت. DeviceToken فقط FCM token یکتا دارد.
- فیکس: پارامتر اختیاری device_token (backward-compatible)؛ اگر آمد فقط ردیف
  (token,user,role) پاک می‌شود (اسکوپ user/role جلوی پاک متقاطع را می‌گیرد)؛ اگر
  نیامد هیچ ردیفی پاک نمی‌شود چون دیوایس فعلی قابل‌شناسایی نیست. سشن مثل قبل باطل می‌شود.
- دامنه‌ی اثر: صفر کالر فعلی (اپ خروج را client-side می‌کند، پورتال localStorage را
  پاک می‌کند) — رفتار جدید فقط کالرهای آینده را لمس می‌کند. فالوآپ اپ: هنگام سیم‌کشی
  logout به سرور، FCM token را هم بفرستد (پیاده نشده).

## قدم ۵ — M19: get_me معلم با teacher_id (auth.py:376-388)
- الگوی H1/H8 (مثل get_logged_in_teacher): اول session.teacher_id مستقیم (مقاوم به
  تغییر موبایل — باگ واقعی: بعد از change_mobile، mobile==username هیچ‌چیز پیدا
  نمی‌کرد و نام معلم به «کاربر سیستم» می‌افتاد)، بعد fallback به mobile==username
  برای سشن‌های قدیمی بدون teacher_id.

## قدم ۶ — M28: کانتکست bcrypt ماژول (dependencies.py:658-729)
- _BCRYPT_CTX یک‌بار در سطح ماژول (فقط مسیر legacy $2b$/$2a$/$2y$؛ مسیر اصلی
  pbkdf2 از قبل handler مستقیم بود). ساخت داخل try با fallback None تا اگر bcrypt
  در دسترس نباشد import نشکند و verify همان False قبلی را بدهد. صفر temp_ctx ماند.
