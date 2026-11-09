# Findings

این فایل فقط محل ثبت ناهماهنگی‌ها و باگ‌های منطقی مشاهده‌شده در زمان نقشه‌برداری است. طبق دامنهٔ کار، هیچ موردی در این فایل fix نمی‌شود.

| شدت | فایل:خط | شرح | وضعیت |
|---|---|---|---|
| متوسط | `Kharazmi_Server/routers/admin.py:524-566`؛ `Kharazmi_Server/routers/reports.py:756-764` | دو خروجی با نام/معنای نزدیک `total_paid_institute` یک تعریف ندارند: full profile سهم institute از رسیدهای `both` را با `share_institute` جمع می‌کند، اما statement فقط ردیف‌های `target_wallet == "institute"` را sum می‌کند و سهم split/both را کنار می‌گذارد. اثر دقیق برای دادهٔ دارای رسید both وابسته به مصرف endpoint است؛ تصمیم/اصلاح محصول در این فاز انجام نشد. | باز؛ فقط مستند شد |
