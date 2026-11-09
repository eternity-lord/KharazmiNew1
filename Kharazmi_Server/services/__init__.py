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

ماژول‌ها:
    branch_scope     — دامنهٔ شعبهٔ مؤثرِ کاربر (branch isolation)، قاعده‌ای عرضی
    class_archive    — گزارش فقط‌خواندنیِ کلاس‌های حذف‌شده + منبعِ بازیابی (provenance)
    class_lifecycle  — اسنپ‌شات/اجرای حذف کلاس و ثبت تصمیم در ActivityLog
    debtor_report    — منبع یگانهٔ «ردیف بدهکار» (لیست، نمای گروهی، پیامک، CSV/Excel)
    live_session     — آجرهای جلسهٔ زنده (تسخیر اتمیک، upsert حضور، گاردها، استثنا)
    scheduling       — پارسِ بازهٔ ساعت، تداخل روزهای هفته، یافتن کلاس‌های متعارض
"""
