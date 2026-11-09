# فاز P3c — کشتنِ وابستگیِ روتر→روتر، دو de-duplication، و پوسته‌کردنِ پنج handlerِ آخر

تاریخ: ۲۰۲۶-۱۱-۰۹ · شاخه: `arena/80cb3294-kharazminew1` · نقطهٔ شروع: `0930543` (PR #8)
نوع: **رفتارمحافظِ محض** — هیچ قابلیت، مسیر، پاسخ JSON یا متنِ خطایی تغییر نکرد.

فازِ قبل (`phase3b2`) لایهٔ سرویس را ساخت و ۱۳ handler را پوسته کرد. اما سه چیز باقی مانده بود که
خودِ آن لایه را زیر سؤال می‌برد: لایهٔ سرویس **از روترها import می‌کرد**، دو هلپرِ پرکاربرد دو نسخه
داشتند، و پنج handlerِ بالای ۹۰ خط هنوز وسط روتر بودند. این فاز هر سه را بست.

---

## ۱) وابستگیِ روتر→روتر (مشکلِ اصلی)

دو هلپر که بیشترین استفاده را در کل ریپو داشتند، از **داخل بدنهٔ توابع** و به‌صورت lazy از روترهای
دیگر گرفته می‌شدند:

| نام | مبدأ (غلط) | تعداد سایتِ تنبل |
|---|---|---|
| `get_logged_in_teacher` | `routers/reports.py:573` | **۳۴ سایت در ۱۴ فایل** |
| `get_user_branch_filter` | `routers/analytics.py:18` | ۷ سایت در ۷ فایل |
| `_get_admin_username`, `_jalali_now_str` | `routers/dunning.py` | در `routers/finance.py` |

نکتهٔ مهم: سه تا از این importهای تنبل را **خودِ P3b به داخل لایهٔ سرویس کشیده بود** —
`services/class_reports.py:192`، `services/class_restore.py:60` و `services/live_session.py:57`
از روتر import می‌کردند، که خلافِ صریحِ قراردادِ همان پکیج است. یعنی ریفکتورِ قبلی، بی‌آنکه
بفهمد، یک نقضِ لایه تولید کرده بود.

**کاری که شد:** دو هلپرِ هویت (`get_logged_in_teacher` ۲۹ خط، `_get_admin_username` ۱۶ خط) به
`dependencies.py` منتقل شدند — دقیقاً کنار `get_session_from_token`، چون کارشان «resolve هویتِ
فراخوان از روی توکن» است و این ماژول از قبل `Teacher`، `User`، `UserSession` و `Session` را
import داشت ⇒ **صفر importِ جدید**. سپس هر ۴۲ خطِ importِ تنبل با importِ سطحِ ماژول جایگزین شد.

اثباتِ معادل بودن، فقط با چشم نبود:

```
reports.get_logged_in_teacher is dependencies.get_logged_in_teacher  ->  True
```

`routers/reports.py` هنوز خودش در خط ~۶۵۰ مصرف‌کننده است، پس بازصادرت می‌کند (و `noqa` لازم
نشد؛ F401 آن را نمی‌اندازد). `tests/test_reports.py:28` هم که از `routers.reports` می‌گیرد، دست‌نخورده کار می‌کند.

**importهای روتر→روتری که عمداً باقی ماندند** (هر سه مستند، هر سه دلیلِ تستی دارند):

- `main.py:643` → `routers.attendance` — worker پایانِ خودکارِ کلاس زنده؛ `finalize_live_session`
  عمداً در روتر می‌ماند چون خودش endpoint است.
- `routers/dashboard.py:125,135` → `routers.audit` / `routers.dunning` — هر دو تابع مقصد توسط
  `test_dashboard_performance.py:208-216` و `test_audit.py:283-291` با **source-text guard**
  محافظت می‌شوند. جابه‌جایی‌شان تغییرِ تست است، نه ریفکتور.
- `routers/exports.py:235` → `routers.audit.get_suspicious_patterns` — همان قید.

نتیجه: لایهٔ `services/` حالا **صفر** عبارتِ `from routers.* import` دارد (دو موردی که با grep
دیده می‌شوند متنِ تاریخیِ داخل docstring هستند، نه کد — با AST بررسی شد).

---

## ۲) دو de-duplication، هر دو با اثباتِ مکانیکی

### `get_user_branch_filter` — کپیِ بایت‌به‌بایت در analytics

`routers/analytics.py:18` نسخهٔ خودش را داشت که با نسخهٔ `services/branch_scope.py` (که P3a ساخته
بود) **بایت‌به‌بایت یکسان** بود. این یک قاعدهٔ امنیتیِ branch isolation است، پس دو کپی بودنش یعنی
یک روز یکی اصلاح می‌شود و دیگری نه. با یک اسکریپتِ AST+`difflib` اثبات شد که یکسان‌اند
(`byte-identical: True`)، بعد کپیِ analytics حذف شد و از لایهٔ سرویس import می‌شود.

### `_jalali_now_str` — دو نسخه در payments و dunning

هم‌ارزی‌شان پیش از ادغام **با اجرا** اثبات شد نه با خواندن: زیر یک ساعتِ منجمدِ یکسان، هر دو
دقیقاً `'1405-08-18 14:07'` برگرداندند. منبعِ یگانهٔ فعلی `services/jalali_time.py` است.
docstring همان ماژول هم اثباتِ هم‌ارزی را ثبت کرده و هم توضیح می‌دهد چرا ساعتِ منجمدِ
`tests/route_audit/clock.py:71` هنوز روی آن اثر می‌گذارد (چون `clock.py` همهٔ ماژول‌هایی را که
`__file__`شان زیر ریشهٔ سرور است freeze می‌کند، پس ماژولِ جدید خودبه‌خود پوشش دارد).

### `_now_str` — **ادغام نشد، و این درست است**

`routers/audit.py:82` و `services/live_session.py:35` هر دو `_now_str` نام داشتند و در نگاه اول
«تکراری» به نظر می‌رسیدند. ولی قالبشان فرق دارد:

| محل | قالب | چرا |
|---|---|---|
| `routers/audit.py` | `%Y-%m-%d %H:%M:%S` | ستون‌های زمانیِ ممیزی/لاگ |
| `services/live_session.py` | `%Y-%m-%d %H:%M` | `LiveSession.start_time`/`end_time` با همان قالبِ UI |

ادغامشان timestampهای ذخیره‌شده را **بی‌صدا** تغییر می‌داد و هیچ تستی هم آن را نمی‌گرفت. پس به‌جای
ادغام، نامِ audit شد `_now_str_with_seconds` و یک توضیحِ سرِ تابع نوشته شد که چرا این دو نباید
«de-duplicate» شوند. تنها مصرف‌کننده‌اش `audit.py:103` است.

---

## ۳) پنج handlerِ آخر (۵۰۷ خط بدنه)

| handler | روتر | بدنه | مقصد |
|---|---|---|---|
| `search_finance_advanced` | finance | ۱۰۶ | `services/finance_reports.py` (**جدید**) |
| `get_student_financial_dashboard` | finance | ۱۰۴ | `services/finance_reports.py` |
| `get_class_students_full` | classes | ۱۰۵ | `services/class_reports.py` |
| `get_class_students_excel` | classes | ۱۰۵ | `services/class_reports.py` |
| `get_deleted_classes` | admin | ۸۷ | `services/class_archive.py` |

`finance_reports.py` جدا از `payments.py` ساخته شد چون آن ماژول مسیرِ **نوشتن** و جابه‌جایی پول است
(کال‌بک درگاه، ثبت پرداخت، بازگشت رسید) و این مسیرِ **خواندن** و گزارش.

`get_deleted_classes` **docstring داشت** ⇒ docstring در پوسته ماند (FastAPI آن را `description`
می‌کند و OpenAPI عوض می‌شد). به همین دلیل هم در `services/class_archive.py` نیاز به ۷ نامِ
محلیِ همان ماژول داشت که با علامتِ «provided» منتقل شد — وگرنه ابزار یک **خود‌importی** می‌ساخت.
درایور بعد از هر انتقال assert می‌کند که ماژولِ مقصد `from <خودش> import` نداشته باشد.

**`pay_installment_manually` منتقل نشد** و نمی‌شود: `test_tuition_installments_audit.py:684` نام
`ActivityLog` را روی فضایِ همان ماژولِ روتر `monkeypatch` می‌کند. اگر بدنه به لایهٔ سرویس برود،
آن patch بی‌اثر می‌شود و تستِ rollback **سبزِ کاذب** می‌دهد. تنها استثنای مستندِ این قاعده است.

---

## ۴) راستی‌آزمایی: بایت‌به‌بایت، مکانیکی، با ابزارِ کامیت‌شده

ابزارها این بار در ریپو commit شدند تا بین نشست‌ها گم نشوند (سه بار `/tmp` از دست رفته بود):

- `Kharazmi_Server/scripts/refactor_move_body.py` — cutter (decorator/امضا/docstring را verbatim
  نگه می‌دارد، aliasها را حفظ می‌کند، روی نامِ router-local متوقف می‌شود؛ `find_assign_text` اضافه شد)
- `Kharazmi_Server/scripts/refactor_verify_move.py` — **دروازهٔ اثبات**: بدنهٔ هر تابعِ منتقل‌شده و
  همچنین decorator/امضا/docstring/پارامترهای هر پوسته و فراخوانیِ forwarding را با یک refِ گیت
  بایت‌به‌بایت مقایسه می‌کند؛ در صورتِ هر مشکل exit 1.

**خودآزمونِ ابزار:** روی انتقال‌های ادغام‌شدهٔ P3b batch 2 با `--base 6e6147e` ⇒ **۹/۹ بایت‌به‌بایت، exit 0**.

**نتیجهٔ این فاز:**

- در برابر `HEAD` (یعنی `4ef4cf3`، پیش از انتقالِ پنج handler): **۵/۵ بایت‌به‌بایت**.
- در برابر `origin/main` (`0930543`): دو بدنه کاملاً یکسان؛ سه بدنهٔ دیگر **هر کدام دقیقاً یک خط**
  فرق دارند — همان خطِ importِ تنبلِ روتر→روتر که در کامیتِ اول از درونِ بدنه حذف شد. یک بررسیِ
  `difflib`ِ خط‌به‌خط نشان داد تعدادِ تفاوت‌های **توجیه‌نشده = ۰**.
- سه انتقالِ مستقیم (`get_logged_in_teacher`، `_get_admin_username`، `_jalali_now_str`) در برابر
  `0930543` همگی `[OK]`.

---

## ۵) گیت‌ها (پس از هر دو کامیت، روی درختِ نهایی)

```
1279 passed, 2 warnings in 123.44s     # suite 1: Kharazmi_Server/tests
249 passed, 2 warnings in 22.36s       # suite 2: tests/route_audit (فرآیندِ جدا)
Kharazmi_Server/gaj_db.db: OK          # md5 دیتابیسِ واقعی تغییر نکرد
Found 251 errors                       # ruff == baseline
routers/exams.py:379:48: F821          # == baseline 1 (از قبل موجود؛ `'x' in locals()`)
Found 726 errors in 44 files           # mypy — یکی کمتر از 727 (تعریفِ تکراری حذف شد)
OpenAPI: 0 differences (17203 lines)   # اوراکل از یک worktreeِ HEAD ساخته شد
```

دفترِ مسیرها (`docs/app-map/server-routes-extracted.csv`) بازتولید شد:
**۲۲۱ مسیر، بدون افزودن/حذف**؛ در هفت فیلدِ `handler`، `input`،
`response_keys_or_schema`، `db_reads_detected`، `db_writes_detected`، `columns_referenced` و
`side_effects_detected` ⇒ **۰ اختلاف**؛ تنها `file:line` حرکت کرد (۱۷۱ مورد، و **هیچ‌کدام فایلشان
عوض نشد**). `scripts/validate_app_map.py` ⇒ `server_map_exact: true`.

---

## ۶) اثرِ تجمعیِ فاز ۳ روی اندازهٔ روترها

| فایل | پیش از فاز ۳ | پس از P3a | پس از P3b | **پس از P3c** |
|---|---|---|---|---|
| `routers/admin.py` | ۲۹۹۰ | ۲۵۶۵ | ۱۵۹۰ | **۱۵۰۳** |
| `routers/finance.py` | ۲۸۳۹ | ۲۶۵۵ | ۱۶۰۶ | **۱۴۰۵** |
| `routers/classes.py` | ۱۵۳۹ | ۱۳۶۲ | ۹۴۶ | **۷۳۸** |
| `routers/attendance.py` | ۱۵۸۲ | ۱۴۶۱ | ۱۰۰۳ | **۹۹۹** |
| `routers/reports.py` | — | — | ۱۳۷۸ | **۱۳۶۰** |
| `routers/analytics.py` | — | — | ۶۱۲ | **۵۹۳** |
| `dependencies.py` | — | — | ۱۲۲۴ | **۱۲۶۳** (+۳۹: دو هلپرِ هویت) |

چهار روترِ بزرگ: **۸۹۵۰ → ۴۶۴۵ خط** (−۴۳۰۵). لایهٔ `services/`: از **۰ → ۵۱۱۱ خط در ۱۶ فایل**
(۱۵ ماژول + `__init__.py`). مجموعِ handlerهای پوسته‌شده در فاز ۳: **۳۰** (۱۲ در P3a، ۱۳ در P3b، ۵ در P3c).

---

## ۷) درس‌هایی که باید به فازهای بعد برود

1. **ملاکِ بازصادرت:** سؤال این نیست که «آیا نام در متنِ روتر هست؟» بلکه «آیا مصرف‌کننده‌ای در روتر
   *مانده*؟». دو بار (P3a: `import time as time_module`، P3b: `PAYMENT_GATEWAY_ENABLED`) همین اشتباه
   باعث F821 شد. بازصادرت را **بی‌قید** بگذار و بگذار F401 آن را بیندازد.
2. **بعد از هر انتقال** `ruff --select F821` و `--statistics` در برابر baseline. نه `import main`، نه
   اوراکلِ OpenAPI و نه هیچ‌کدام از دو سوئیت این کلاس از خطا را نمی‌گیرند.
3. **ابزارِ انتقال برای ماژولِ مقصد هم `provided` می‌خواهد:** وقتی مقصد همان ماژولی است که نام‌های
   محلی‌اش لازم‌اند (مثل `get_deleted_classes` → `class_archive`)، بدون علامت‌گذاری، خود‌importی ساخته
   می‌شود. دو بار این نشست همین اتّفاق افتاد (`dependencies.py:1093` و `:1150`) و هر دو حذف شدند.
4. **`dependencies.py` importهای وسط‌فایل دارد** (خطوط ~۷۵۵، ~۱۰۱۸) ⇒ `merge_imports` در جاهای عجیب
   درج می‌کند و توابع به EOF می‌افتند. بعد از هر انتقال به این فایل، محلِ تابع را بازبینی کن
   (این بار `relocate()` نوشته شد تا تابع را کنار `get_session_from_token` بگذارد).
5. **«تکراری» را با اجرا اثبات کن، نه با خواندن.** `_jalali_now_str` واقعاً همسان بود؛ `_now_str`
   در نگاه اول همسان بود ولی نبود. تفاوتِ یک ثانیه در قالب، یک باگِ خاموشِ داده‌ای است.
6. **دو سوئیت هرگز در یک فرآیند دَویده نشوند** (`models.py` کشِ `engine`/`SessionLocal` دارد؛
   ترکیبی ⇒ `UNIQUE constraint failed: branches.id`). در CI هم دو job جدا هستند.

---

## ۸) قدمِ بعد

فاز **P4**: اپلیکیشنِ اندروید (`KharazmiAdmin/`، ۹۲ فایل `.kt`، ۲۴۸۹۳ خط). اهدافِ بزرگ:
`StudentProfileActivity` ۱۲۶۴، `InvoiceActivity` ۱۲۴۸، `AttendanceActivity` ۱۰۱۲،
`ClassDetailActivity` ۹۴۸ خط.

سپس **P5**: گیتِ lint/type در CI — که امروز به‌خاطر baselineهای ۲۵۱ (ruff) و ۷۲۶ (mypy) مسدود است.
مسیرش: یا صفرکردنِ آن دو عدد، یا اضافه‌کردنِ گیت به‌صورتِ «بدتر نشود» (`--exit-zero` + مقایسهٔ شمار).
