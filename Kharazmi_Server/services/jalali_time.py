"""منبعِ یگانهٔ «الان، به شمسی» — `_jalali_now_str`.

پیش از این فاز، این تابع در **سه جا** بود:
  * `services/payments.py` (که خودش در P3b از `routers/finance.py` آمده بود)،
  * `routers/dunning.py:39` — نسخهٔ مستقلِ همسان،
  * و `routers/finance.py` با یک importِ تنبلِ **روتر→روتر** از دنینگ آن را می‌گرفت:
        from routers.dunning import _get_admin_username, _jalali_now_str

هر دو نسخه یک عبارت را محاسبه می‌کردند:
`jalali_date_string(_now.date()) + _now.strftime(" %H:%M")`.
پیش از ادغام، هم‌ارزی‌شان به‌صورت **اجراشدنی** اثبات شد (نه فقط با خواندنِ کد): زیرِ یک
ساعتِ فریز‌شدهٔ یکسان، هر دو دقیقاً `'1405-08-18 14:07'` برگرداندند.

نکتهٔ مهم برای سوئیت `tests/route_audit`: آن سوئیت `datetime` را در فضایِ هر ماژولِ سرور
فریز می‌کند (`clock.py:freeze_loaded_server_modules`) و این ماژول هم چون زیرِ ریشهٔ سرور
است و هنگامِ `import main` بار می‌شود، خودکار فریز می‌شود؛ پس مقدارِ برگشتی زیرِ تست
دقیقاً مثل قبل است.

تابع **بایت‌به‌بایت** از `services/payments.py` منتقل شده (حتی importِ تنبلِ
`jalali_date_string` داخلش، که الگوی مستندِ همین ریپو است).
"""
import datetime


def _jalali_now_str() -> str:
    """FIX L7: paid_at شمسی (هماهنگ با due_date و Transaction.date) + ساعت سرور."""
    from today_summary import jalali_date_string  # lazy، مثل H3-B3 همین فایل
    _now = datetime.datetime.now()
    return jalali_date_string(_now.date()) + _now.strftime(" %H:%M")
