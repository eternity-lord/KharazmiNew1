# F-B1 — بازنویسی کال‌بک پرداخت (ریس دابل‌کردیت + اعتماد به status + Mock) — 2026-09-16

## تصمیم‌های طراحی (به نفع برنامه و کاربر)
- ماشین‌حالت PENDING→VERIFYING→SUCCESS/FAILED (+CANCELLED) با UPDATE مشروط (H8-P4)؛ claim قبل از
  وریفای خارجی کامیت می‌شود؛ بازیابی تسخیر کهنه (۱۰ دقیقه) برای کرش بین وریفای و ثبت.
- verify-first رد شد: با وریفای تک‌مصرف واقعی، ریس «FAILEDنویسی بازنده بین وریفای و claim برنده» پولِ پرداخت‌شده را FAILED می‌کرد.
- authority باید دقیقاً با سطر ذخیره‌شده match شود (هر دو شاخه، حتی انصراف) — وگرنه 400 بدون تغییر حالت.
- status کوئری فقط راهنمای انصراف است (SUCCESS/OK موفق، بقیه CANCELLED مشروط از PENDING)؛ تنها منبع حقیقت کردیت = پاسخ وریفای.
- Mock ذاتاً قابل‌«فیکس» نیست (بدون merchant واقعی) → به‌جایش fail-loud ساختاری: فلگ پیش‌فرض خاموش + نگهبان ENV=production در کال‌بک و factory.
- initiate همان استاب 400 ماند (بازنویسی واقعی merchant می‌خواهد)؛ قراردادش با کال‌بک جدید در کامنت مستند شد.

## فیکس‌ها (سریال)
- `models.py`: ستون‌های `payments.gateway` + `payments.claimed_at`؛ کامنت status (+VERIFYING)؛ PG patch هر دو ستون.
- `main.py`: دو تاپل auto_patch (SQLite) + کامای گمشده‌ی تاپل قبلی (بدون آن auto_patch در بوت TypeError می‌داد — شکار شد قبل از بوت).
- `payment_gateways.py`: `IS_MOCK`؛ factory: RuntimeError در پروداکشن + ValueError برای نام ناشناخته (حذف fallback ساکت به زرین‌پال)؛ قرارداد وریفای واقعی (تک‌مصرف: «قبلاً وریفای‌شده»=موفق؛ خطای گذرا=exception نه False).
- `routers/finance.py` کال‌بک: ریت‌لیمیت 30/min (+`request`)؛ نگهبان پروداکشن؛ حذف with_for_update نمایشی؛
  بازپخش پایانی بدون وریفای مجدد (SUCCESS/REFUNDED صفحه موجود، FAILED/CANCELLED ایستا)؛ authority-match؛
  درگاه همان‌مسیر؛ تسخیر PENDING→VERIFYING + reclaim کهنه؛ پیش‌شرط‌ها (مبلغ/کیف/شاگرد→FAILED مشروط)؛
  SUCCESS مشروط + افزایش اتمیک کیف و total_paid (coalesce)؛ تلاش تخصیص ۳→۱۰ و اتمام=لاگ+ادامه (نه rollback+409)؛
  FAILED/CANCELLED مشروط؛ ۳ هلپر صفحه (static/refresh/processing)؛ فیکس f-string `{payment.id}`؛ TODOها به‌روز.

## راستی‌آزمایی (فقط /tmp کپی؛ PAYMENT_GATEWAY_ENABLED=true)
- AST+COMPILE OK؛ import main CLEAN؛ auto_patch هر دو ستون را روی کپی ساخت.
- لایو ۱۲/۱۲: T1 موفق کامل (کیف+رسید+تسویه قسط)؛ T2 بازپخش idempotent؛ T3 همزمانی (یکی موفق+یکی پردازش، دقیقاً یک کردیت)؛
  T4 وریفای-ناموفق→FAILED+بازپخش ایستا؛ T5 انصراف→CANCELLED (حتی بازپخش با SUCCESS)؛ T6 mismatch→۴۰۰+PENDING ماندگار؛
  T7 کیف نامعتبر→FAILED+لاگ+رندر درست شناسه؛ T8 reclaim کهنه→SUCCESS؛ T9 VERIFYING تازه→processing بدون تغییر؛
  T10 فلگ‌خاموش→۴۰۴؛ T11 پروداکشن→۵۰۰ بدون تغییر حالت؛ T12 factory (ValueError/RuntimeError). صفر Traceback.
- رگرسیون سوئیت: 255 پاس / ۱۳ فیل = دقیقاً همان TypeErrorهای منسوخ شناخته‌شده (نمونه چک شد)؛ صفر رگرسیون.
- teardown: هش f0e55fe7… پایدار؛ سرورها stop؛ /tmp پاک.

## باقی‌مانده‌ی واقعی (نیازمند ورودی بیرونی، نه کد)
- اتصال درگاه واقعی: merchant ID + بازنویسی initiate + جایگزینی verify Mock (قرارداد هر دو در کامنت‌ها).
- انقضای PENDINGهای رهاشده (cron/worker) — عمداً خارج از اسکوپ (بدون حجم، بی‌ضرر؛ بعد از اتصال واقعی).
