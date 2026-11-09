"""Kharazmi Services Package — لایهٔ منطق دامنه (REFAC P3a).

قانون این لایه (چرا وجود دارد):
    روترها (`routers/*.py`) فقط **لایهٔ HTTP** باشند — decorator مسیر، `Depends`ها،
    احراز هویت/مجوز، و شکلِ پاسخ. منطق دامنه (کوئری‌ها، تجمیع‌ها، قواعد مالی و زمانی،
    چرخهٔ حذف/بازیابی) اینجا زندگی می‌کند.

پیش از این فاز، آن منطق وسط چهار فایلِ بزرگِ روتر پخش بود (`admin.py` ~۲۹۹۰ خط،
`finance.py` ~۲۸۳۹، `attendance.py` ~۱۵۸۲، `classes.py` ~۱۵۳۹) و برای استفادهٔ مشترک،
روترها مجبور بودند **از همدیگر** import کنند:

    from routers.finance import get_user_branch_filter   # در admin/analytics/crm/exports/reports/students
    from routers.finance import build_debtor_rows        # در exports/reports — lazy برای فرار از چرخه
    from routers.classes import check_scheduling_conflicts   # در admin

آن وابستگیِ روتر→روتر حالا از بین رفته: مصرف‌کننده‌ها مستقیم از این لایه import می‌کنند.

قراردادهای مهم:
  • ماژول‌های این پکیج **route ثبت نمی‌کنند** و `APIRouter` ندارند. تنها استثنا،
    `HTTPException` است که عمداً حفظ شده تا رفتار/پیام‌های خطای API بایت‌به‌بایت یکسان
    بماند (ریفکتورِ این فاز رفتارمحافظ است).
  • انتقال کد **بایت‌به‌بایت** انجام شده؛ هیچ منطقی بازنویسی نشده است.
  • روترِ مبدأ، نام‌های منتقل‌شده را import/re-export می‌کند تا همهٔ مسیرهای import
    قبلی (از جمله importهای lazy در `main.py` و تست‌ها) دست‌نخورده کار کنند.
  • نام‌گذاری با نام کوتاه (`from services.scheduling import ...`) است، چون conftest و
    bootstrap سرور پوشهٔ `Kharazmi_Server/` را روی `sys.path` می‌گذارند؛ به همین دلیل
    `services` در `pyproject.toml` زیرِ `known-first-party` ثبت شده است.

قاعدهٔ اضافه‌شده در P3b — «پوستهٔ HTTP»:
    P3a آجرهای *مشترک* را بیرون کشید؛ P3b **بدنهٔ خودِ handlerها** را هم به این لایه
    آورد. شکلِ کار این است:

        @router.post("/attendance/submit_session")          # ← decorator در روتر می‌ماند
        def submit_session_and_calculate(                   # ← نام و امضا در روتر می‌ماند
            data: AttendanceSubmitData, db: Session = Depends(get_db), ...
        ):
            # docstring هم در روتر می‌ماند ← FastAPI آن را description می‌کند
            return session_submission.submit_session_and_calculate(data, db, ...)

    چرا handler در روتر حذف نمی‌شود و فقط واگذار می‌کند؟
      ۱. امضای handler (annotationها + `Depends`/`Header`) **قرارداد OpenAPI** است؛ اگر
         تابع سرویس جای آن در route ثبت شود، باید تزریق‌ها را بازتعریف کرد و هیچ سودی ندارد.
      ۲. این handlerها قراردادِ فرا-HTTP دارند: ده‌ها تست و `scripts/run_financial_audit.py`
         آن‌ها را مستقیم از `routers.*` — گاهی با آرگومان **پوزیشنال** — صدا می‌زنند
         (مثلاً `admin.delete_transaction(transaction.id, db=..., _="admin")`) و
         `finalize_live_session` هم `submit_session_and_calculate` را با
         `_system_caller="live_system"` فراخوانی می‌کند.
    نتیجه: نام، ترتیب پارامترها و پاسخ JSON دقیقاً مثل قبل می‌ماند و بدنهٔ دامنه در این
    لایه است. تضمینِ این ادعا مکانیکی است: اسکریپتِ راستی‌آزمایی، بدنهٔ هر تابعِ منتقل‌شده
    و همچنین decorator/امضا/docstringِ هر پوسته را با `git HEAD` **بایت‌به‌بایت** مقایسه می‌کند.

    یک استثنای مستند: `pay_installment_manually` در `routers/finance.py` عمداً پوسته نشده،
    چون `test_tuition_installments_audit.py::test_s23b` نام `ActivityLog` را روی فضایِ
    همان ماژولِ روتر `monkeypatch` می‌کند تا «خطا در آخرین قدم» را شبیه‌سازی کند؛ اگر بدنه
    به این لایه می‌آمد، آن patch بی‌اثر می‌شد و تست **سبزِ کاذب** می‌داد (چیزی که دقیقاً
    برای سنجشِ rollback نوشته شده است).

ماژول‌ها:
    branch_scope        — دامنهٔ شعبهٔ مؤثرِ کاربر (branch isolation)، قاعده‌ای عرضی
    class_archive       — گزارش فقط‌خواندنیِ کلاس‌های حذف‌شده + منبعِ بازیابی (provenance)
    class_lifecycle     — اسنپ‌شات/اجرای حذف کلاس و ثبت تصمیم در ActivityLog
    class_reports       — فهرست کلاس‌ها + گزارش کامل یک کلاس (P3b)
    class_restore       — بازیابی کلاسِ حذف‌شده با opt-inِ مالی (P3b)
    debtor_report       — منبع یگانهٔ «ردیف بدهکار» (لیست، نمای گروهی، پیامک، CSV/Excel)
    enrollment          — ثبت‌نام دانش‌آموز در کلاس و اثرهای مالی‌اش (P3b)
    live_session        — آجرهای جلسهٔ زنده (تسخیر اتمیک، upsert حضور، گاردها، استثنا)
    payments            — کال‌بک درگاه، ثبت پرداخت، بازگشت رسید + هلپرهای خصوصی‌شان (P3b)
    session_submission  — ثبت جلسهٔ کلاسی + ویرایش جلسهٔ گذشته: سهم‌ها، شارژ، جریمه (P3b)
    student_profile     — پروفایل کامل یک دانش‌آموز برای صفحهٔ ادمین (P3b)
    transaction_admin   — حذف/ویرایش تراکنش از سمت ادمین + هلپرِ تقسیم مبلغ (P3b)
    scheduling          — پارسِ بازهٔ ساعت، تداخل روزهای هفته، یافتن کلاس‌های متعارض

چیزهایی که عمداً در روترها مانده‌اند:
    * `pay_installment_manually` (routers/finance.py) — به دلیل قیدِ monkeypatchِ بالا.
    * اسکیمای `ClassRestoreRequest` به `schemas.py` رفت (منبعِ یگانهٔ اسکیم‌ها از P2c) و
      `routers/admin.py` آن را بازصادرات می‌کند، چون امضای پوسته به آن اشاره دارد و
      FastAPI از همان امضا OpenAPI را می‌سازد.
    * `_jalali_now_str` و `PAYMENT_GATEWAY_ENABLED` در `services/payments.py` تعریف شده‌اند
      و `routers/finance.py` آن‌ها را بازصادرات می‌کند: بقیهٔ handlerهای همان فایل (از جمله
      `mock_payment_page`) هنوز مصرف‌کننده‌شان هستند. توجه: `routers/dunning.py` نسخهٔ
      **مستقلِ** خودش از `_jalali_now_str` را دارد (و `routers/audit.py` هم `_now_str` را)؛
      این تکرار عمداً دست‌نخورده ماند و یک نامزدِ جداگانه برای de-duplication است.
"""
