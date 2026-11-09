# Checkpoint — M30: دیالوگ ملایم انقضای نشست (جای پرتاب CLEAR_TASK)

Date: 2026-09-12. Asserted + read-back. No compile/run.

## قدم ۱ — اینترسپتور (RetrofitClient.kt ~:81-90)
- بلوک 401 دیگر navigate نمی‌کند: SessionExpiry.signal() + پاک توکن (مثل قبل)
  + Toast کوتاه. صفر CLEAR_TASK/startActivity در فایل ماند. بلوک 403 دست‌نخورده.

## قدم ۲ — BaseActivity (جدید + مهاجرت ۴۵ اکتیویتی)
- بیس مشترکی وجود نداشت (۴۵ فایل مستقیم از AppCompatActivity ارث می‌بردند) پس
  BaseActivity.kt ساخته شد و هر ۴۵ اکتیویتی (۴۴ پکیج اصلی + ui/MainActivityRefactored
  با import cross-package) به آن مهاجرت کردند؛ تنها مرجع AppCompatActivity خود
  BaseActivity است. importهای بلااستفاده حذف شد.
- onResume: اگر LoginActivity نیست + claim موفق ← AlertDialog «نشست شما منقضی شده
  است» + دکمه‌ی «ورود مجدد». غیرمدال/کنسل‌شدنی: با بک/تاچ بیرون به فرم برمی‌گردد
  (کپی/اسکرین‌شات) و در resume بعدی یادآوری می‌شود. onPause دیالوگ را می‌بندد
  (ضد Window-leak) ولی فلگ سیگنال می‌ماند.

## قدم ۳ — گارد یک‌بارمصرف (SessionExpiry.kt جدید)
- signal/claim/onDialogGone/reset همگی @Synchronized: claim فقط وقتی true می‌دهد
  که سیگنال هست و دیالوگی بالا نیست ← 401های موازی فقط یک دیالوگ. چرخش صفحه:
  dismiss خودکار + claim مجدد در resume جدید ← همان یک دیالوگ برمی‌گردد.

## قدم ۴ — دکمه‌ی «ورود مجدد» (BaseActivity.kt)
- reset کامل فلگ + Intent به LoginActivity با NEW_TASK|CLEAR_TASK (تنها نقطه‌ی خروج
  واقعی). چون فلگ ریست شده، onResume صفحه‌ی لاگین دیالوگی نمی‌سازد (گارد دوم:
  skip صریح LoginActivity).
