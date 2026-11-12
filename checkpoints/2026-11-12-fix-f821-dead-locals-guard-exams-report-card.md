# رفعِ F821 — گاردِ مردهٔ `in locals()` در کارنامهٔ دانش‌آموز + قفلِ رگرسیوندش

## ۱) باگ

`ruff check --select F821` رویِ کلِ ریپو **دقیقاً یک** خطا می‌داد:

```
F821 Undefined name `attendance_percentage`
  --> Kharazmi_Server/routers/exams.py:379:48
```

خطِ ۳۷۹، داخلِ `get_student_report_card` (شروع از ۳۳۳)، در حلقهٔ ساختِ `courses_details`:

```python
"attendance_percentage": round(attendance_percentage, 1) if 'attendance_percentage' in locals() else round(attendance_pct, 1),
```

نیتِ نویسنده روشن است: «اگر `attendance_percentage` حساب شده بود از آن استفاده کن، وگرنه
`attendance_pct`». ولی آن نام **هرگز در این تابع assign نمی‌شود** — دو رخدادِ دیگرش در
کلِ فایل یکی خودِ همین خط است و دیگری خطِ ۴۳۳ که `course['attendance_percentage']`
یعنی **کلیدِ dict** است نه متغیر.

## ۲) چرا `NameError` نمی‌داد (و چرا هیچ تستی گرفتارش نشد)

در Python محلی‌بودنِ یک نام **در زمانِ کامپایل** از رویِ assignها در همان تابع تعیین
می‌شود. چون `attendance_percentage` هیچ‌جا در `get_student_report_card` assign نمی‌شود،
بارگذاری‌اش `LOAD_GLOBAL` کامپایل می‌شود و در نتیجه `'attendance_percentage' in locals()`
که frameِ **محلیِ** تابع را می‌کاود **همیشه False** است. پس:

* شاخهٔ اول هرگز ارزیابی نمی‌شود ⇒ `NameError` رخ نمی‌دهد (اتفاقاً به‌خاطرِ همان گارد).
* شاخهٔ اول **کدِ مرده** است ⇒ خروجی همیشه `round(attendance_pct, 1)` بود.

یعنی رفتارِ observable درست بود و به همین دلیل هیچ تستی شکست نمی‌خورد؛ نقص از جنسِ
«کدِ مرده + نیتِ گمراه‌کننده» بود. خطرِ واقعی‌اش آینده است: این الگو خواننده را
قانع می‌کند که یک fallback دو‌شاخه وجود دارد، درحالی‌که یک شاخهٔ همیشه‌رو دارد. و اگر
روزی کسی واقعاً `attendance_percentage` را در همان تابع assign کند، رفتارِ endpoint
**بی‌صدا** عوض می‌شود.

## ۳) اندازه‌گیری پیش از رفع (نه حدس)

| پرسش | پاسخِ اندازه‌گیری‌شده |
|---|---|
| چند F821 در ریپو؟ | `ruff check --select F821 .` ⇒ **۱** (همین خط) |
| این الگو چند جایِ سرور هست؟ | `grep -rn "in locals()" Kharazmi_Server/` ⇒ **۱ فایل، ۱ خط** |
| `attendance_pct` موقعِ استفاده bind است؟ | خطِ ۳۶۶، **بی‌قیدِ شرط** در همان بدنهٔ `if en.course:` و پیش از ۳۷۹ ⇒ بله |
| `attendance_percentage` جایِ دیگر assign می‌شود؟ | در کلِ فایل فقط ۳۷۹ (خودِ گارد) و ۴۳۳ (کلیدِ dict) ⇒ **نه** |
| تستی این خط را پین کرده؟ | `grep -rn "attendance_percentage\|in locals()" Kharazmi_Server/tests/ tests/` (به‌جز `sweep/`) ⇒ **خالی** |
| شکلِ پاسخ عوض می‌شود؟ | **نه** — کلیدِ `"attendance_percentage"` و مقدارش (همان `round(attendance_pct, 1)`) دست‌نخورده می‌ماند؛ snapshotهای `tests/route_audit/sweep/contract-report.json` که این کلید را دارند معتبر می‌مانند |
| `test_audit_exams.py` چه می‌سنجد؟ | ۴۲ خط، فقط فهرستِ دو مسیرِ report_card ⇒ بی‌تأثیر |

## ۴) رفع

```python
# پیش
"attendance_percentage": round(attendance_percentage, 1) if 'attendance_percentage' in locals() else round(attendance_pct, 1),
# پس (با کامنتِ چرایی، به سبکِ بقیهٔ `# FIX(...)`های ریپو)
"attendance_percentage": round(attendance_pct, 1),
```

رفتارنگه‌دار به‌معنایِ دقیق: شاخهٔ حذف‌شده هرگز اجرا نمی‌شد، پس مقدارِ برگشتی در هر
ورودی یکسان است. `Kharazmi_Server/routers/exams.py` از ۴۴۰ به ۴۴۵ خط (۵ خط کامنت).

## ۵) تستِ شاهد — `tests/route_audit/test_static_scope_guards.py` (جدید، ۳ تست)

چرا تستِ استاتیک و نه تستِ endpoint: نقص، «شاخهٔ مرده» است و با هیچ ورودی‌ای در
پاسخ دیده نمی‌شود؛ پس witness باید **خودِ الگو** را ببندد. فقط `ast` از کتابخانهٔ
استاندارد — عمداً به ruff وابسته نیست، چون نصبِ ابزارِ اضافی در jobِ route-audit تضمین
نیست.

آشکارساز: هر `Compare` به‌شکلِ `<str-const> in locals()` (یا شکلِ معکوس، و `not in`)
که رشته‌اش میانِ نام‌های **bindشده در همان scopeِ تابع** نباشد. تابع‌های تودرتو،
`Lambda` و `ClassDef` عمداً شمرده نمی‌شوند چون `locals()` در frameِ خودِ تابع ارزیابی
می‌شود؛ و `global`/`nonlocal` هم `locals()` را پر نمی‌کند.

سه تست، و دلیلِ هرکدام:

1. `test_scan_actually_sees_the_server_tree` — باید ≥۱۰۰ فایلِ `.py` ببیند و
   `routers/exams.py` در مجموعه باشد. **بدونِ این، «۰ یافته» می‌توانست از «۰ فایلِ
   دیده» بیاید**؛ این همان دامی است که در همین برش یک‌بار سراغم آمد (بندِ ۷).
   اندازهٔ واقعی: ۱۵۹ فایل.
2. `test_detector_is_not_vacuous` — رویِ سه نمونهٔ مصنوعی: گاردِ بد را **بگیرد**
   (`ghost`)، گاردِ سالم را نگیرد (`pct`)، و assign در تابعِ **تودرتو** را برایِ گاردِ
   تابعِ بیرونی معتبر نشمارد. اثباتِ غیرِتهی بودنِ تستِ سوم.
3. `test_no_dead_locals_guard_in_server` — جارویِ کلِ سرور؛ پیامِ شکست مکانِ دقیق
   (`file:line`، نامِ تابع، رشتهٔ پاییده‌شده) را فهرست می‌کند.

## ۶) شواهدِ گیت‌ها

| گیت | پیش | پس |
|---|---|---|
| `pytest -q` (ریشه، `testpaths = Kharazmi_Server/tests`) | 1279 | **1279 passed, 2 warnings in 115.99s** · ۰ سطرِ FAILED/ERROR |
| `pytest tests/route_audit -q` | 249 | **252 passed** (+۳ تستِ شاهد) |
| سوئیتِ سومِ CI (از داخلِ `Kharazmi_Server`؛ گاردِ cwd-independence) | — | **31 passed** |
| `ruff check .` (کلِ ریپو) | 251 | **250** (−۱) |
| `ruff check --select F821 .` | 1 | **0 — All checks passed!** |
| `mypy Kharazmi_Server/` | 726 / ۴۴ فایل | **725 / ۴۴ فایل** (−۱) |
| `find_dead_kotlin.py` | ۸ نماد / ۱۰۴ خط | **۸ / ۱۰۴** (بی‌تغییر) |
| `find_dead_resources.py` | ۰ | **جمعِ منابعِ مرده = ۰** |
| md5 دیتابیسِ واقعی | `f048f8d118b33c4eaa944490594121d7` | **همان** (پس از هر سه سوئیت) |
| `git ls-files -m` | — | فقط `Kharazmi_Server/routers/exams.py` |

`KHarazmi_Server/tests/` **دست‌نخورده** ماند (قانونِ پذیرش)؛ تستِ تازه در
`tests/route_audit/` اضافه شد که `testpaths` آن را جمع نمی‌کند، پس شمارِ سوئیتِ اصلی
(۱۲۷۹) تغییر نکرد و فقط سوئیتِ route-audit ۲۴۹→۲۵۲ شد. دو کامنتِ کهنهٔ «۲۴۹ تست
route-level» در `.github/workflows/tests.yml` (خط‌های ۱۱ و ۸۱) هم به ۲۵۲ به‌روز شد —
کامنت است نه assertion، ولی عددِ غلط در کامنت بعداً کسی را گمراه می‌کند.

## ۷) یافتهٔ روش‌کاری: آن «فایل‌سیستمِ خراب» بیشترش **غلطِ املاییِ مسیرِ من** بود

چندین ساعت از این نشست را با این باور کار کردم که `KHarazmi_Server` خواندنی نیست:
`pip install -r KHarazmi_Server/requirements.txt` با `ENOENT` (در ۳۰۰ تلاشِ پشت‌سرِ هم)،
`git show HEAD:KHarazmi_Server/...` ⇒ «does not exist in 'HEAD'»، `ruff check
KHarazmi_Server/` ⇒ «Failed to lint»، `test -d` ⇒ MISSING، و نتیجه‌گیریِ من که
«object store ناقص است و گیت‌های محلی اجراشدنی نیستند».

**علت واقعی: نامِ پوشه `Kharazmi_Server` با `h` کوچک است، و من `KHarazmi_Server` با
`H` بزرگ می‌نوشتم.** اثباتِ بایتی:

```
path bytes : b'Kharazmi_Server/routers/'   → char codes [75, 104, 97, ...]  = 'K','h'
my literal : b'KHarazmi_Server'            → char codes [75,  72, 97, ...]  = 'K','H'
startswith? False      find('KHarazmi') = -1      find('Server') = 9
```

همین یک حرف باعث شد: آن «نافه‌خواندنی بودنِ گاه‌به‌گاهِ `requirements-dev.txt`» که کلِ
نشستِ قبل را گرفته بود، «غایب بودنِ سرور از object store»، «اجرانشدنی بودنِ گیت‌های
محلی»، و یک برشِ کامل مستندسازیِ نادرست. به‌محضِ اصلاحِ املا، همه‌چیز در یک تلاش کار
کرد: `ls Kharazmi_Server` ⇒ ۲۳ ورودی، `tests/` ⇒ ۸۱ ورودی، `requirements.txt` ⇒
۱۳ خط/۲۲۹ بایت، venv در یک بار ساخته شد، و هر سه سوئیت سبز دویدند.

تأییدِ مستقل: خودِ CI در `.github/workflows/tests.yml:64` می‌نویسد
`python -m pytest Kharazmi_Server/tests -q` — املایِ درست از اول در ریپو بود.

**درس‌ها:**
1. پیش ازِ پذیرفتنِ «محیط/overlay خراب است»، **بایت‌هایِ مسیر** را با `git ls-tree`
   مقایسه کن (`python3 -c "print([ord(c) for c in p])"`). ارزان‌ترین آزمایش، همان
   اولین آزمایش است.
2. املایِ مسیرهایی که از یادداشت/حافظهٔ نشست می‌آیند **دادهٔ معتبر نیستند**؛ باید از
   خودِ درختِ git گرفته شوند. نامِ ریپو `KharazmiNew1` و پوشهٔ اندروید `KharazmiAdmin`
   هم `h` کوچک دارند — یعنی الگویِ نام‌گذاریِ پروژه از اول پیشِ چشمم بود.
3. `git ls-tree HEAD ""` (pathspec خالی) **هیچ** چاپ نمی‌کند؛ آن «۰ ورودی در ریشه» هم
   خطایِ من بود نه خرابیِ git.
4. همچنان ناپایداریِ **واقعیِ** فایل‌سیستم هم دیده شد و انکارش نمی‌کنم: در یک پنجرهٔ
   ~۱۰ دقیقه‌ای پس از تعویضِ شاخه، `ls res` پوشه‌ها را نشان می‌داد ولی `find` و
   `os.walk` هیچ فایلی نمی‌دیدند، و `shutil.copyfile` در `KHarazmiAdmin/` ۱۲۰ بار
   شکست خورد درحالی‌که `touch` همان‌جا موفق بود (احتمالاً همگام‌سازیِ ناتمامِ workspace
   پس از ساختِ cloneِ تازه). تفاوتِ کلیدی: آن ناپایداری **گذرا** بود و با پنجرهٔ
   خوانا آمد و رفت، ولی خطایِ املا **ماندگار** بود و هر بار همان‌جا شکست می‌داد.
   معیارِ تفکیک: ناپایداریِ گذرا باید در تلاش‌هایِ پیاپی **ناهمسان** باشد؛ شکستِ
   ۱۰۰٪ یکسان و تکرارپذیر رویِ یک مسیر، نشانهٔ اشتباهِ خودِ مسیر است.
5. شاهدم همین‌جا هم به کار آمد: اسکریپتی که از خواندنِ ناموفق نتیجهٔ «پاک است» گرفت
   را باطل کردم، و تستِ شاهدِ این برش هم دقیقاً برایِ جلوگیری از همان نوشته شد
   (`test_scan_actually_sees_the_server_tree`).

## ۸) بدهیِ باقی‌مانده

* `ruff` ۲۵۰ یافته (۳ مورد `--fix`پذیر) و `mypy` ۷۲۵ مسئله در ۴۴ فایل — هیچ‌کدام
  F821 نیستند؛ انباشتهٔ سبک/typing است و گیتِ «بدتر نشود» برایش ساخته نشده.
* گیتِ warningهای کامپایلرِ Kotlin (خطوطِ `w:`) — آیتمِ ۳ از «گامِ بعدِ» PR #14، هنوز
  ساخته نشده. گامِ کامپایل در CI همین حالا لاگ را نگه می‌دارد
  (`./gradlew … :app:assembleDebug 2>&1 | tee /tmp/gradle-assemble.log`)، پس فقط یک
  اسکریپتِ گیت و یک step می‌خواهد (Kotlin 2.0.21 ⇒ قالبِ `w: file:///…:L:C msg`).
* ریفکتور: ۱۰ ماژولِ بالایِ ۶۰۰ خط. چگالیِ پین (پین بر هزار خط) اندازه‌گیری شد تا
  هدفِ بعدی علمی انتخاب شود: `ClassDetailActivity` ۱۷۴٫۹ · `TeacherDashboardActivity`
  ۱۷۲٫۳ · `InvoiceActivity` ۱۵۱٫۸ · `ReportActivity` ۱۳۷٫۰ · `StudentProfileActivity`
  ۱۳۵٫۷ · `AttendanceActivity` **۶۸٫۱** · `TeacherProfileActivity` ۶۳٫۳ ·
  `MainActivity` **۴۶٫۵**. پس امن‌ترین هدفِ بزرگ `AttendanceActivity` (۹۹۸ خط،
  ۱۷ پینِ سخت رویِ ۸ عضو از ۲۳ عضو ⇒ ۱۵ عضوِ آزاد) است. مانعِ عملی‌اش این بود که
  بزرگ‌ترین عضویش `showAttendancePrintDialog` **۲۱۴ خط** است و ۳ پینِ سخت دارد
  (`'style'`، `'dialog_remittance_success'`، `'R.id.btnRegisterAgain'`) ⇒ باید در فایل
  بماند؛ خوشهٔ آزادِ صف/شبکه (`flushPendingQueue` ۳۵، `retryQueueItem` ۳۸،
  `refreshQueueCard` ۵۴، `isNetworkAvailable` ۶، `refreshNetworkStatus` ۹ ≈ ۱۴۲ خط)
  کاندیدِ استخراج است.
* `validate_app_map.py` با exit=1 (چهار مسیرِ live-session فقط در اندروید) و در هیچ
  workflow نیست · `find_dead_kotlin` ۸ نماد/۱۰۴ خط با برچسبِ DEFER · بدهیِ
  `./gradlew wrapper` از PR #19.
