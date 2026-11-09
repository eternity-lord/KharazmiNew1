# O-08 — «درآمد امروز» داشبورد: عدد بی‌معنا (جمع علامت‌دارِ همهٔ تراکنش‌ها با LIKE روی تاریخ شمسی)

- **تاریخ:** ۲۰۲۶-۰۹-۲۱ · **Branch:** `arena/01a0bf8d-kharazmiapp` · **موج:** ۲ (مورد ۶)
- **Base HEAD:** `3ce3095` (گروه auth) · **دسته:** مالی · **شدت:** بالا (KPI روی صفحهٔ اول پنل ادمین)

## ریشه
`routers/dashboard.py` → `_today_revenue_sql()` یک `SUM(amount)` بدون فیلتر نوع/کیف‌پول، فقط با
`Transaction.date.like(f"{today_jalali}%")` بود:
- شارژ جلسه (عدد **منفی**، ماهیتاً بدهی شاگرد) از وصولی کم می‌شد؛
- واریزی امروز با تاریخ **میلادی** یا تاریخ خالی («بی‌تاریخ») دیده نمی‌شد؛
- واریزی به کیف **معلم** جزو «درآمد آموزشگاه» شمرده می‌شد؛
- عدد با تعریف گزارش‌های مالی (`calculate_institute_collected_revenue`) نمی‌خواند.

## اعداد قبل/بعد روی کپی `/tmp/wave2_o08.db` (کپی `gaj_db.db` با md5 یکسان)
| سناریو | قبل (SQL LIKE) | بعد (تابع مرکزی) |
|---|---:|---:|
| کپی دست‌نخوردهٔ دیتابیس توسعه (۱ تراکنش legacy، تاریخ `1404/09/06`) | 0 | 0 |
| کپی + فعالیت امروز: ۵۰۰ک وصولی شمسی، **۷۰۰ک وصولی با تاریخ میلادی**، ۹۰۰ک سهم معلم، −۴۰۰ک شارژ جلسه، ۱۲۰ک بی‌تاریخ | **1,000,000** | **1,200,000** |

یعنی عدد قبلی هم ۹۰۰٬۰۰۰ تومان پولِ معلم را جزو درآمد مؤسسه می‌شمرد، هم ۴۰۰٬۰۰۰ تومان بدهی شاگرد را
از آن کم می‌کرد، و ۷۰۰٬۰۰۰ تومان وصولی واقعی را نمی‌دید. عدد جدید = ۵۰۰+۷۰۰ هزار تومان وصولی نقدی مؤسسه.

## فیکس
| فایل | تغییر |
|---|---|
| `routers/dashboard.py` | حذف کامل `_today_revenue_sql` و LIKE؛ `today_revenue = calculate_institute_collected_revenue(db, today_jalali, today_jalali)` داخل `try/except` (مثل بقیهٔ KPI‌ها: خطا ⇒ ۰ و لاگ، نه ۵۰۰) |
| `KharazmiAdmin/.../values/strings.xml` | `dashboard_today_revenue_sub`: «مجموع تراکنش‌های امروز» → **«وصولی نقدی امروز»** |

## تست
- **قرمز اول:** `test_14` سناریو ۶ (که رفتار غلط را قفل کرده بود) + تست جدید `test_14b` ⇒ ۲ FAILED.
- `test_14b_today_revenue_counts_only_cash_collected_today`: ۴ ردیف حاشیه‌ای (وصولی میلادیِ امروز /
  سهم معلم / شارژ جلسه / بی‌تاریخ) + سنجش هم‌ارزی با `calculate_institute_collected_revenue`
  + بی‌اثری حذف ردیف‌ها.
- گاردهای قدیمی که این باگ را قفل کرده بودند آگاهانه به‌روزرسانی شدند:
  `test_dashboard_performance.py::test_uses_sql_counts_and_the_shared_revenue_definition` (assertion
  ممنوعیت `like(f"{today_jalali}%")` + الزام تابع مرکزی)، `test_dashboard.py::test_kpi_today_revenue_is_cash_collected_for_the_institute`،
  و فهرست `PREVIOUSLY_CWD_DEPENDENT` در `test_suite_cwd_independence.py` (نام جدید).
- سناریو ۶: **18 passed** · کل سوئیت: **1044 passed** · md5 دیتابیس واقعی بی‌تغییر.

## Commit / Push
- پیام: `fix: make the dashboard today-revenue KPI use the shared cash-collection definition (O-08)`
