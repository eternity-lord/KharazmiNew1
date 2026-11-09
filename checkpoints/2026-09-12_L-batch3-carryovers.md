# Checkpoint — L بچ ۳ + دو یافته‌ی بچ ۲ (carryover-1/2، L1-server، L4، L12)

Date: 2026-09-12. Asserted + read-back per step. No compile/run.

## قدم ۱ — یافته‌ی ۱: حلقه‌ی آنلاین با M13 هماهنگ شد (finance.py:812/:832-844)
- حلقه‌ی وریفای آنلاین همان انباشت تجمعی paid_amount + is_paid فقط در پوشش
  کامل (الگوی M13 مسیر دستی). مسیر تک‌قسطی هدفمند هم‌جوار (:812) هم
  paid_amount=مبلغ کامل گرفت (تسویه‌ی هدفمند = پوشش کامل) تا invariant تغییری
  M13 در هر ۴ مسیر تسویه برقرار باشد (دستی/عمومی/آنلاین-حلقه/آنلاین-تکی).

## قدم ۲ — یافته‌ی ۲: گارد PricingTable خالی (financial_calculations.py:266-272)
- نبودن ردیف تعرفه برای category (وقتی نرخ کلاس هم صفر/None است) ← 500 صریح
  با پیام «جدول تعرفه را ثبت کنید» — آینه‌ی گارد InstituteShare (فلسفه‌ی H5).
  دیگر T_total=0 ساکت (جلسه‌ی مجانی) نداریم.

## قدم ۳ — L1 بخش سرور: ماسک PII (attendance.py:476/478)
- پروژه هیچ logging infra ندارد (صفر import لاگینگ؛ فقط print خام) پس به‌جای
  معرفی لاگر تک‌افتاده، student_id از هر دو پیام حذف شد (ماسک حداقلی سازگار
  با سبک کدبیس). بخش اپ (۳۱ printStackTrace) دست‌نخورده ماند.

## قدم ۴ — L4: ایندکس مرکب تراکنش (models.py:245 + main.py:303-308)
- `__table_args__` با Index("ix_transactions_student_date"، ‏student_id/date)
  به سبک SessionLog + مایگریشن CREATE INDEX IF NOT EXISTS به الگوی Bug 17
  (هر دو دیتابیس، idempotent). DB تازه از create_all می‌گیرد، قدیمی از پچر.

## قدم ۵ — L12: هشدار خطای واقعی (main.py:121-125)
- column_exists حالا اکسپشن را با نام جدول/ستون print می‌کند و بعد False
  برمی‌گرداند — رفتار fallback (خودترمیمی) نگه داشته شد ولی دیگر بی‌صدا نیست.
