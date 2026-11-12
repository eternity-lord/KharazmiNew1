# گیتِ warningهای کامپایلرِ Kotlin — `KharazmiAdmin/kotlin_warning_gate.py`

## ۱) چرا

`app/build.gradle.kts` هیچ `allWarningsAsErrors` ندارد و تا امروز هیچ workflow ای خروجیِ
کامپایلر را نمی‌خواند ⇒ شمارِ warningها **ناشناخته** بود. این با lint فرق دارد: lint سبک و
بهترین‌روش را می‌سنجد (۱۳۶۰ مورد در `lint-baseline.json` با ۳۲ شناسه، که بخشِ بزرگش
`HardcodedText` است)، ولی کامپایلر چیزهایی اعلام می‌کند که می‌توانند **باگِ واقعی** باشند —
`Name shadowed`، `Casting 'x' to 'Y' will throw ClassCastException`، `Unreachable code`،
`Elvis operator (?:) always returns the left operand`، `Variable is never used`.

صفرکردنِ یک‌باره‌شان ریفکتور نیست و با رفتارمحافظ بودنِ این کار در تضاد است، پس همان الگویِ
`lint_gate.py` (فازِ P4c): **baseline را ثبت کن و فقط جلویِ بدتر شدن را بگیر.**

## ۲) دو تفاوتِ ماهوی با `lint_gate.py`

**الف) warningهای Kotlin شناسهٔ پایدار ندارند.** خروجیِ lint یک `id` دارد (`HardcodedText`)
ولی کامپایلر فقط متنِ پیام می‌دهد. پس شناسه از **قالبِ پیام** ساخته می‌شود: نام‌های داخلِ
نقل‌قول/backtick ⇒ `'*'`، اعداد ⇒ `N`. نتیجه `Variable '*' is never used`.

**ب) لاگِ Gradle باید خودش را ثابت کند.** گزارشِ lint یک XMLِ ساخت‌یافته است که یا هست یا
نیست؛ ولی لاگِ کامپایل یک فایلِ متنی است که اگر build زود بشکند **کوتاه** است و warningِ
کمتری دارد — و شمردنِ آن به‌معنایِ «بهبود» اشتباه می‌شود. پس `read_log()` شاهد می‌خواهد:
`:app:compile*Kotlin` یا `BUILD SUCCESSFUL`؛ وگرنه `LogUnavailable` ⇒ exit=2. وجودِ
`BUILD FAILED` هم exit=2 است چون موجودی ناقص است. این همان قاعدهٔ «خواندنِ ناموفق هرگز صفر
گزارش نشود» است که در این پروژه بارها پرهزینه بوده.

## ۳) باگی که تست‌ها لو دادند: سوراخ‌هایِ بی‌نقل‌قول

نسخهٔ اول فقط نام‌های **نقل‌قولی** را نرمال می‌کرد. تستِ
`test_gate_fails_when_an_existing_kind_grows` قرمز شد و علتش آموزنده بود:

```
::error title=kotlin warning gate::new warning kinds (not present in the baseline): Name shadowed: row x1
```

یعنی `Name shadowed: item` و `Name shadowed: row` دو **شناسهٔ جدا** بودند، چون Kotlin در این
خانواده نام را بی‌نقل‌قول می‌گذارد. دو پیامد:

1. **انفجارِ baseline** — به ازایِ هر متغیرِ سایه‌زده یک شناسه؛ چند صد شناسه در یک
   annotationِ ۴KB نمی‌جاود و کانالِ انتقالِ baseline (که تنها کانالِ ممکن است) بسته می‌شد.
2. **شکستِ کاذب** — تغییرِ نامِ یک متغیر در یک ریفکتورِ کاملاً بی‌خطر، گیت را با «قالبِ
   جدید» می‌شکست. گیتی که با نویزِ بی‌خطر قرمز شود، خیلی زود نادیده گرفته می‌شود.

رفع: `_BARE_HOLE_RULES` (خانواده‌هایِ صریح: `Type mismatch: inferred type is X but Y was
expected`، `Name shadowed: X`، `expected type X`، `is not a subtype of X`، `Inferred type for
the parameter X`) به‌علاوهٔ `_TRAILING_IDENT_RE` به‌عنوانِ قاعدهٔ عمومیِ پشتیبان برایِ
خانواده‌هایِ ناشناخته (کلِ پیام به «سرآغاز: یک شناسه» ختم شود).

مرزِ مهم: **بیش‌ازحد یکی‌کردن هم ممنوع است.** `Variable '*' is never used` و
`Parameter '*' is never used` باید جدا بمانند، و `Name shadowed: *` با
`Variable 'item' is never used` یکی نیست. هر دو جهت در
`test_kind_of_collapses_bare_identifier_holes_so_renames_do_not_churn_the_gate` پین شده‌اند.

ریسکِ باقی‌ماندهٔ قاعدهٔ پشتیبان (یکی‌شدنِ دو پیامِ واقعاً متفاوت که به یک دنبالهٔ
تک‌شناسه ختم شوند) **fail-loud** است نه fail-silent: چون «قالبِ جدید» شکست است، خانوادهٔ
پوشش‌داده‌نشده خودش را با شکستِ پرسروصدا نشان می‌دهد و با افزودنِ یک قاعده به فهرست رفع
می‌شود.

## ۴) قاعدهٔ تصمیم و کدهای خروج

pass ⟺ هیچ **قالبِ جدیدی** نباشد **و** شمارِ هیچ قالبی از baseline بیشتر نشود **و** مجموع
از مجموعِ baseline بیشتر نشود. بهبود مجاز و گزارش‌شدنی است و annotationِ
«baseline can be refreshed» می‌گیرد تا دستاورد با `--write-baseline` قفل شود و بعداً بی‌صدا
پس نرود. نبودنِ baseline هم **شکست** است (وضعیتِ ناشناخته ≠ پاس).

`0` پاس · `1` گیت رد شد / baseline نیست · `2` لاگ ناخوانا، خالی، `BUILD FAILED`، یا بدونِ
شاهدِ اجرایِ taskِ کامپایل.

محدودیتِ صادقانه (همان‌که در `lint_gate.py` مستند است): اگر در یک قالب یک warning رفع شود و
هم‌زمان یک warningِ جدید از همان قالب بیاید، شمارِ کل تغییر نمی‌کند و گیت آن را نمی‌بیند
(netting-out). بهایِ فشرده‌بودنِ baseline است؛ هر قالبِ **جدید** حتی با یک مورد هم شکست است.

## ۵) چرا این گام فعلاً گزارش‌دهی است نه enforcing

موجودیِ واقعی فقط با JVM/Gradle تولید می‌شود و در محیطِ کاریِ ما هیچ‌کدام نیست، پس baseline
باید از CI بیاید. artifact قابلِ دانلود نیست (هاست بسته) و `output.summary` از API خالی
برمی‌گردد ⇒ تنها کانالِ قابلِ اتکا **annotation** است که از `api.github.com` خوانده می‌شود.
پس گامِ CI فعلاً `--table --emit-baseline` می‌دهد؛ `--emit-baseline` خودِ JSON را قطعه‌بندی‌شده
(سقفِ ۳۹۰۰ کاراکتر، چون GitHub فیلدِ `message` را روی ۴۰۹۶ می‌بُرد — عددی که در اجرایِ
`43042529340` اندازه‌گیری شد) چاپ می‌کند. مرحلهٔ بعد: خواندنِ آن annotation، commitِ
`KharazmiAdmin/kotlin-warnings-baseline.json`، و تبدیلِ گام به `--check`. این دقیقاً همان
دو‌مرحله‌ای است که فازِ P4c برای lint طی کرد.

گام عمداً **پس از** گامِ کامپایل و **پیش از** `Run JVM unit tests` نشست، چون ورودی‌اش
`/tmp/gradle-assemble.log` است که همان گامِ کامپایل با `tee` می‌نویسد. ترتیب با
`yaml.safe_load` تأیید شد و `android.yml` حالا ۱۳ گام دارد.

## ۶) شواهد

| بررسی | نتیجه |
|---|---|
| سوئیتِ تازهٔ شاهد | **20 passed** در ۰٫۱۲s |
| GATE A (`pytest -q` ریشه) | **1279 passed** در 137.33s — بی‌تغییر، چون تست‌های تازه در `tests/route_audit` هستند و `testpaths` جمعشان نمی‌کند |
| GATE B (`pytest ./tests/route_audit`) | 255 → **275 passed** (+۲۰) |
| GATE C (سوئیتِ cwd از داخلِ `Kharazmi_Server`) | **31 passed** |
| `validate_app_map.py --gate` (برشِ قبلی، اکنون در main) | exit **0** — بی‌تغییر |
| `ruff check .` | **250** (بی‌تغییر؛ `KharazmiAdmin` در `extend-exclude` است) · `--select F821 .` ⇒ All checks passed |
| `mypy Kharazmi_Server/` | **725 در ۴۴ فایل** (۵۵ فایل بررسی شد) — بی‌تغییر |
| `find_dead_resources.py` | **جمعِ منابعِ مرده: 0** |
| `find_dead_kotlin.py` | 8 نمادِ فهرست‌شده — بی‌تغییر، چون این برش هیچ کدِ Kotlin اضافه یا حذف نمی‌کند |
| `lint-baseline.json` | **1360 / ۳۲ شناسه** بی‌تغییر |
| YAMLِ `android.yml` | تجزیه شد؛ ترتیب: کامپایل ← **گامِ تازه** ← JVM tests ← lint ← گیتِ lint |
| smokeِ CLI | `--table`→0 («2 in 2 kinds») · `--check` بدونِ baseline→1 · لاگِ غایب→2 · `--write-baseline`→0 · round-trip `--check`→0 |
| md5 دیتابیسِ واقعی | `f048f8d118b33c4eaa944490594121d7` بی‌تغییر · هیچ `gaj_db.db` سرگردانی در ریشه ساخته نشد |

نسخهٔ ابزارها با pinهایِ `requirements-dev.txt` یکی است (`ruff==0.17.4`، `mypy==2.4.1`)، پس
شمارِ خطاهایِ بالا با بیس‌لاین‌هایِ قبلی قابلِ مقایسه است؛ این پس از بازسازیِ `.venv` در
این session صریحاً بررسی شد.

گروه‌های تست: کنترلِ مثبتِ تجزیه (هر دو قالبِ `file:///` و مسیرِ مطلقِ ساده، حذفِ تکرارِ
دقیق، رد شدنِ `e:` و نویزِ Gradle، نرمال‌سازیِ مسیر به نسبیِ ریپو) · نرمال‌سازیِ شناسه
(سه تست: نقل‌قولی/عددی، بی‌نقل‌قول، و فرارِ annotation) · پنج تستِ fail-closed (لاگِ غایب، خالی، بی‌شاهدِ
کامپایل، `BUILD FAILED`، نبودِ baseline) · معنایِ گیت (پاسِ دقیق، قالبِ جدید، رشدِ قالبِ
موجود، بهبود با درخواستِ تازه‌سازیِ baseline، round-tripِ `--write-baseline`→`--check`) ·
کانالِ annotation (قطعه‌بندی زیرِ سقفِ اندازه‌گیری‌شده، عنوانِ بی‌کاما، تک‌قطعه بودنِ متنِ
کوتاه).

## ۷) دو نکتهٔ روش‌کار که در همین برش هزینه دادند

**الف) املایِ درستِ ریشهٔ اندروید `KharazmiAdmin` است** (h کوچک). `ls KHarazmiAdmin/*.py` سه
بار پشتِ سر هم `No such file or directory` داد درحالی‌که `git ls-files` همان ابزارها را
نشان می‌داد؛ بایت‌ها حکم کردند: `K-h-a-r-a-z-m-i-A-d-m-i-n`. دقیقاً هم‌خانواده با
`KHarazmi_Server` در برابرِ `Kharazmi_Server`. معیارِ عملی: خطایِ ۱۰۰٪ بازتولیدپذیر رویِ
یک مسیر یعنی **خودِ مسیر غلط است**، نه ناپایداریِ گذرا؛ راهِ تشخیص هم ریختنِ `ord()`/`repr`
هر دو طرف است نه حدس زدن.

**ب) کارِ بی‌commit با تعویضِ branch از بین می‌رود.** این برش یک بار کامل ساخته و محلی
راستی‌آزمایی شد (۱۸ تست + همهٔ گیت‌ها)، ولی commit نشده بود چون دسترسیِ ریموتِ branchِ
قبلی بسته شده بود. با ساختِ branchِ تازه، working tree به `main` برگشت و **هر سه فایلِ
تازه ناپدید شدند** — `git status` خالی، `git stash list` خالی، `git fsck --lost-found` صفر
dangling blob، و هیچ کپی‌ای در `/home/user`. فایل‌هایِ untracked هیچ شیءِ git ندارند، پس
هیچ راهِ بازیابی‌ای وجود نداشت و کلِ برش از رویِ متنِ session بازسازی شد. `.venv` هم
از بین رفت (در فهرستِ snapshot نیست). قاعدهٔ تازه: **پیش از هر تعویضِ branch، حتی وقتی
ریموت بسته است، commitِ محلی بزن** — commitِ محلی رویِ branchِ قدیمی دستِ‌کم در
`git fsck`/reflog پیدا شدنی است، ولی untracked هرگز.

دو نکتهٔ ویرایشیِ کوچک‌تر: بازسازیِ دستیِ لنگرِ فارسی (کسره‌هایِ `ساختِ`/`قالبِ` جا
می‌افتند ⇒ `count=0`) — راهِ درست، یافتنِ لنگر با **توکنِ ASCII** و درجِ خطی؛ و `\u200c`ِ
دوبار escape‌شده در heredoc به بایت‌هایِ واقعیِ `\u200c` تبدیل می‌شود نه نیم‌فاصله.

## ۸) باگی که فقط CI لو داد: newlineِ خام در annotation

اجرایِ `43264977423` سبز شد و گامِ تازه هم `success` گرفت، ولی دو annotationِ آن این بود:

```
{"message_len":1,"msg":"{","raw":null,"title":"kotlin warning baseline JSON - commit as KharazmiAdmin/…"}
{"message_len":55,"msg":"Kotlin compiler warnings: 45 in 3 kinds across 10 files","raw":null,…}
```

یعنی GitHub متن را تا **نخستین LF خام** نگه داشته و بقیه را بی‌صدا دور ریخته بود: از JSONِ
baseline فقط `{` (یک کاراکتر!) و از جدول فقط خطِ نخست رسیده بود، با `raw_message` تهی.
علت: نسخهٔ اولِ `emit_annotation` در این اسکریپت `print(f"::{level} title=…::{part}")` را با
newlineِ **رمزنگشته** چاپ می‌کرد، درحالی‌که `lint_gate.py` از همان ابتدا `escape()` داشت
(`%`→`%25`، CR→`%0D`، LF→`%0A`) و شمارهٔ قطعه را در **عنوان** می‌گذاشت نه در پیام.

چرا این باگ جدی بود و نه آرایشی: annotation **تنها** کانالِ بیرون‌کشیدنِ داده از CI است
(artifact بسته است و `output.summary` از API خالی برمی‌گردد). پس این خطا بی‌صدا کلِ مرحلهٔ
enforcing را غیرممکن می‌کرد — baseline هرگز به ریپو نمی‌رسید. و **محلی دیده نمی‌شد**:
خروجیِ چاپ‌شده رویِ ترمینال کاملاً سالم به نظر می‌رسید؛ فقط یک مصرف‌کنندهٔ واقعی
(خودِ GitHub) تفاوت را می‌دید. این دقیقاً همان دلیلی است که این گام را «گزارش‌دهی» گذاشتیم
پیش از enforcing: مرحلهٔ گزارش‌دهی نه برایِ عدد، که برایِ آزمودنِ خودِ کانال هم لازم بود.

رفع: افزودنِ `escape()` با همان قراردادِ `lint_gate.py` و گذاشتنِ `(part i/n)` در عنوان،
به‌علاوهٔ دو تستِ شاهد که دیگر نمی‌گذارند این به newlineِ خام برگردد:

* `test_multiline_messages_are_percent_encoded_so_github_keeps_them` — یک پیامِ سه‌خطی باید
  **دقیقاً یک خطِ فیزیکی** منتشر شود، بدونِ `\n` خام، با `%0A`، و محتوایِ رمزگشایی‌شده‌اش
  عینِ ورودی باشد (یعنی چیزی دور ریخته نشده).
* `test_escape_handles_percent_cr_and_lf` — ترتیبِ فرار مهم است: درصد **نخست** فرار می‌شود،
  وگرنه متنِ ازقبل دارایِ `%0A` دوپهلو می‌شد (`escape("%0A") == "%250A"`).
* تستِ قطعه‌بندی هم سخت‌تر شد: هر قطعه باید یک خطِ فیزیکیِ بی‌LF باشد و **بازچسباندنِ**
  قطعه‌ها عینِ ورودیِ ۱۲KB را بدهد.

دادهٔ باقی‌مانده از همان اجرایِ بریده: **۴۵ warning در ۳ قالب، در ۱۰ فایل** — یعنی موجودیِ
واقعی آن‌قدر فشرده است که در یک annotation جا می‌شود و دانه‌بندیِ قالبی درست انتخاب شده بود
(۳ قالب، نه ۴۵ موقعیت). جزئیاتِ هر قالب در اجرایِ بعدی، با `escape()` درست، به ریپو می‌رسد.

## ۹) بدهیِ باقی‌مانده

* **مرحلهٔ enforcing همین گیت**: خواندنِ annotationِ اجرایِ CI، commitِ
  `KharazmiAdmin/kotlin-warnings-baseline.json`، و تغییرِ گام به
  `python3 kotlin_warning_gate.py --log /tmp/gradle-assemble.log --check --baseline kotlin-warnings-baseline.json`.
  تا آن موقع وضعیتِ warningها «ثبت‌شده» است نه «قفل‌شده».
* `F841 out = []` در `scripts/validate_app_map.py:281` (تابعِ `--write`) — پیش‌موجود،
  ۱ مورد از ۲۵۰؛ ruff خودش «unsafe fix» می‌دهد و آزمودنِ `--write` یعنی نوشتنِ دو overlayِ
  tracked در `docs/route-tests/`.
* `ruff` ۲۵۰ یافته (۳ مورد `--fix`پذیر) و `mypy` ۷۲۵ مسئله در ۴۴ فایل. گیتِ «بدتر نشود»
  برایِ این دو ساخته نشده — الگویِ `lint_gate.py` و همین `kotlin_warning_gate.py` هر دو
  قابلِ کپی‌اند.
* ریفکتور: ۱۰ ماژولِ بالایِ ۶۰۰ خط. امن‌ترین هدفِ بزرگ بر پایهٔ چگالیِ پین
  `AttendanceActivity.kt` (۹۹۸ خط، ۶۸٫۱ پین بر هزار خط، ۱۷ پینِ سخت رویِ ۸ عضو از ۲۳ ⇒
  ۱۵ عضوِ آزاد)؛ خوشهٔ آزادِ صف/شبکه (`flushPendingQueue` ۳۵ + `retryQueueItem` ۳۸ +
  `refreshQueueCard` ۵۴ + `isNetworkAvailable` ۶ + `refreshNetworkStatus` ۹ ≈ ۱۴۲ خط)
  کاندیدِ استخراج است. بزرگ‌ترین عضو (`showAttendancePrintDialog`، ۲۱۴ خط با ۳ پینِ سخت)
  باید در فایل بماند.
* بدهیِ `./gradlew wrapper` از PR #19 (`validate-wrappers: false`).
* `Kharazmi_Server/tests/` در همهٔ این برش‌ها دست‌نخورده ماند (قانونِ پذیرش).
