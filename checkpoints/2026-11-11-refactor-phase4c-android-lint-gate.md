# فاز P4c — روشن‌کردنِ lint اندروید و گیتِ «بدتر نشود»

تاریخ: ۲۰۲۶-۱۱-۱۱ · نقطهٔ شروع: `cb80984` (= `main` پس از PR #12)
نوع: **زیرساختِ گیت + ثبتِ baseline**. هیچ رفتارِ اپی تغییر نکرده؛ حتی یک مسئلهٔ lint هم
رفع نشده (رفعِ آن‌ها تغییرِ رفتار است و نیاز به تصمیمِ جدا دارد — بندِ ۸).

---

## ۱) چرا

تا این فاز، `lint` **هرگز** روی این اپ اجرا نشده بود: نه در هیچ workflow ای، و نه حتی به
شکلِ پیکربندی — هیچ بلوکِ `lint {}` در `app/build.gradle.kts` وجود نداشت. یعنی وضعیتِ
کیفیتِ ~۲۴ هزار خط Kotlin و ۱۹۰ فایلِ منبع کاملاً **ناشناخته** بود، همان‌طور که وضعیتِ
«آیا اصلاً build می‌شود؟» تا P4-prep ناشناخته بود.

پاسخِ اولین اجرا: **۱۳۸۵ مسئله در ۳۶ شناسه** (Error=۱۷۳، Warning=۱۲۱۲) پخش‌شده در
۱۶۱ فایل.

صفرکردنِ این انباشته در یک گام، «ریفکتورِ رفتارمحافظ» نیست — بازنویسی است. پس همان الگویی
که سمتِ سرور برای ruff (۲۵۱ خطا) و mypy (۷۲۶ خطا) لازم داریم این‌جا هم پیاده شد:
**baseline را ثبت کن و فقط جلویِ بدتر شدن را بگیر.**

## ۲) چه ساخته شد

| بخش | محتوا |
|---|---|
| `app/build.gradle.kts` | `lint { abortOnError = false; xmlReport = true; htmlReport = true }` |
| `.github/workflows/android.yml` | step «Run Android lint» (`:app:lintDebug`) + step «Gate lint against the committed baseline» |
| `KharazmiAdmin/lint_gate.py` | خودِ گیت: `--write-baseline` / `--check` / `--table` / `--emit-baseline` |
| `KharazmiAdmin/lint-baseline.json` | baseline ثبت‌شده (۳۲۲۴ بایت) |

`abortOnError = false` **عمدی** است: اگر lint خودش task را بشکند، job پیش از مقایسهٔ گزارش
با baseline می‌میرد و گیتِ ما تزئینی می‌شود. گزارش باید همیشه تولید شود؛ تصمیمِ رد/قبول با
اسکریپتِ گیت است، نه با lint.

قاعدهٔ گیت:
* هر شناسهٔ **جدید** ⇒ شکست (حتی با شمارِ ۱ — رایج‌ترین شکلِ regression همین است)؛
* **افزایشِ** شمارِ هر شناسه ⇒ شکست؛
* **کاهش** ⇒ قبول، به‌همراهِ یک annotation حاویِ JSONِ baselineِ تازه‌شده تا دستاورد قفل شود.

## ۳) baseline — کامل

`total=1385 · distinct_ids=36 · Error=173 · Warning=1212 · files_with_issues=161`

| شمار | شدت | شناسه | | شمار | شدت | شناسه |
|---:|---|---|---|---:|---|---|
| 652 | Warning | HardcodedText | | 8 | Warning | CutPasteId |
| 148 | **Error** | StringFormatMatches | | 8 | **Error** | SuspiciousIndentation |
| 105 | Warning | DefaultLocale | | 7 | Warning | DisableBaselineAlignment |
| 68 | Warning | SetTextI18n | | 7 | Warning | NewerVersionAvailable |
| 53 | Warning | Overdraw | | 5 | Warning | TextFields |
| 47 | Warning | RtlHardcoded | | 3 | Warning | ButtonStyle |
| 38 | Warning | UseCompoundDrawables | | 3 | Warning | KeyboardInaccessibleWidget |
| 37 | Warning | UseKtx | | 3 | Warning | SmallSp |
| 31 | Warning | UseCompatTextViewDrawableXml | | 3 | Warning | TooManyViews |
| 30 | Warning | ContentDescription | | 2 | Warning | AndroidGradlePluginVersion |
| 24 | Warning | UseTomlInstead | | 2 | Warning | MonochromeLauncherIcon |
| 23 | Warning | TypographyEllipsis | | 2 | **Error** | ResourceType |
| 18 | Warning | GradleDependency | | 2 | Warning | ScopedStorage |
| 17 | Warning | LabelFor | | 1 | Warning | ApplySharedPref |
| 14 | **Error** | NewApi | | 1 | Warning | ClickableViewAccessibility |
| 11 | Warning | NotifyDataSetChanged | | 1 | Warning | DiscouragedApi |
| 8 | Warning | Autofill | | 1 | Warning | OldTargetApi |
| | | | | 1 | **Error** | PermissionImpliesUnsupportedChromeOsHardware |
| | | | | 1 | Warning | UselessParent |

جمعِ ستونِ شمارها دقیقاً ۱۳۸۵ می‌شود — این یکی از assertهای ساختِ baseline بود (بندِ ۵).

## ۴) چرا از مکانیزمِ بومیِ AGP استفاده نشد (و کانال‌شناسیِ CI)

`lint { baseline = file("lint-baseline.xml") }` دانه‌بندیِ بهتری دارد (موقعیت‌به‌موقعیت)، ولی
فایلش را Gradle در CI می‌سازد و باید به ریپو برسد. در این محیط راهی نیست:

| کانال | وضعیت |
|---|---|
| `results-receiver.actions.githubusercontent.com` (لاگِ خام) | **بسته** (http=000) |
| `pipelines.actions.githubusercontent.com` (دانلودِ artifact) | **بسته** (http=000) — اندازه‌گیری‌شده در همین فاز |
| `output.summary` از check-runs API | **خالی** (length=0) — یعنی `$GITHUB_STEP_SUMMARY` به دستِ ما نمی‌رسد |
| `api.github.com/.../check-runs/<job>/annotations` | **باز** ✅ و تنها کانالِ قابلِ اتکا |

نتیجهٔ طراحی: baseline باید آن‌قدر فشرده باشد که در **یک annotation** جا شود ⇒
دانه‌بندیِ «شمار به تفکیکِ شناسه». به همان دلیل `category_of` و فهرستِ ۱۶۱ فایلی عمداً در
baseline نیامدند: گیت نمی‌خواندشان و هر تغییرِ نامِ فایل بی‌دلیل baseline را تکان می‌داد.

**محدودیتِ صادقانهٔ این دانه‌بندی:** اگر از یک شناسه یک مورد **رفع** و هم‌زمان یک مورد
**جدید** اضافه شود، شمار عوض نمی‌شود و این گیت آن را نمی‌بیند (netting-out). بهایِ
فشرده‌بودنِ baseline است. دو چیز ریسک را کم می‌کند: شناسهٔ جدید حتی با یک مورد هم شکست است،
و جدولِ کامل در هر اجرا منتشر می‌شود تا بازبینِ انسانی توزیع را ببیند.

## ۵) baseline با دست نوشته نشد

۳۶ عدد = ۳۶ فرصت برای شکستِ کاذبِ گیت، یا بدتر، **ردِ کاذبِ** آن. پس:

1. به `lint_gate.py` حالتِ `--emit-baseline` اضافه شد که خودِ JSON را داخلِ یک annotation
   منتشر می‌کند (تا تازه‌کردنِ baseline در آینده هم به JVM نیاز نداشته باشد).
2. فایلِ این فاز با **پارسِ ماشینیِ** annotationِ اجرای اکتشافی (`43037529996`) ساخته شد،
   با سه assert: جمعِ شمارها = `total` خودِ CI (۱۳۸۵)؛ تعدادِ شناسه‌ها = `distinct_ids` خودِ
   CI (۳۶)؛ جمعِ `per_severity` = همان total.
3. **round-trip:** از همین baseline یک گزارشِ XML مصنوعی به قالبِ AGP بازسازی شد
   (۱۳۸۵ `<issue>`) و گیت رویش اجرا شد ⇒ `new ids: 0 | worse ids: 0 | improved ids: 0`،
   exit=0. اگر پارس یا اعداد غلط بود، این round-trip تفاوت نشان می‌داد.

## ۶) خودآزماییِ گیت (پیش از push، چون محلی JVM/Gradle نیست)

با گزارش‌های مصنوعی به قالبِ واقعیِ AGP:

| حالت | انتظار | نتیجه |
|---|---|---|
| ساختِ baseline | نوشتنِ JSON + جدول | ✅ |
| گزارش = baseline | exit 0 | ✅ |
| شناسهٔ جدید + افزایشِ شمار + حذفِ یک شناسه | exit 1 با diff | ✅ |
| بهبود | exit 0 + annotationِ JSONِ تازه | ✅ |
| گزارش موجود نیست | exit **2** | ✅ |
| گزارش ۰ بایت | exit **2** | ✅ |
| XML ناشدنی | exit **2** | ✅ |
| ریشهٔ گزارش `<issues>` نیست | exit **2** | ✅ |
| `<issue>` بدونِ `id` | exit **2** | ✅ |
| baseline موجود نیست | exit **2** | ✅ |
| روی baselineِ واقعی: یک مورد اضافه | exit 1 | ✅ |
| روی baselineِ واقعی: شناسهٔ کاملاً جدید | exit 1 | ✅ |

اصلِ طراحی در همهٔ حالت‌های exit=2: **نبودنِ گزارش هرگز «صفر مسئله» تلقی نمی‌شود.** وگرنه
یک lintِ خراب تا ابد بی‌صدا گیت را رد می‌کند.

بلوکِ shellِ stepِ گیت هم از دلِ YAML بیرون کشیده شد و **verbatim** روی چهار شاخه آزموده شد:
گزارش هست/baseline نیست (فقط گزارش + `::warning::` صریحِ «هنوز enforcing نیست»)؛ هر دو هستند
و برابرند (قبول)؛ بدتر شده (exit 1)؛ گزارش نیست (exit 2).

## ۷) سه باگ که خودآزمایی لو داد

* `--table` مستقل کار نمی‌کرد چون گروهِ حالت‌ها `required=True` بود — یعنی **دقیقاً همان
  کانالی بسته بود که baseline از آن بیرون می‌آید**.
* `normalize_file()` مسیرِ `app/build/generated/x` را به `generated/x` خراب می‌کرد ⇒ baseline
  به مسیرِ رانر وابسته می‌شد.
* **کاما در عنوانِ workflow command:** بخشِ propertyها با کاما جدا می‌شود
  (`::notice title=X,file=Y::msg`)، پس عنوانِ «lint gate: 1385 issues, not worse than
  baseline» در CI به «lint gate: 1385 issues» کوتاه شد. این باگ فقط از **خواندنِ annotationِ
  واقعیِ CI** معلوم شد، نه از خودآزماییِ محلی. عنوان‌ها حالا بدونِ کاما هستند.

## ۸) آنچه این فاز عمداً انجام **نداد**

هیچ مسئلهٔ lint رفع نشد، چون رفعشان تغییرِ رفتار است. ولی شناسه‌های با شدتِ **Error** عملاً
یک فهرستِ باگِ از‌پیش‌موجودند و ارزشِ تصمیمِ جدا دارند:

* `NewApi` (۱۴) — فراخوانیِ API بالاتر از `minSdk = 24` بدونِ محافظ ⇒ **خطرِ crash روی
  دستگاه‌های قدیمی**. جدی‌ترین موردِ این فهرست.
* `SuspiciousIndentation` (۸) — تورفتگی‌ای که کد را داخلِ شاخه‌ای نشان می‌دهد که در آن نیست.
* `ResourceType` (۲) — id یک منبع با نوعِ اشتباه پاس داده شده.
* `StringFormatMatches` (۱۴۸) و `PermissionImpliesUnsupportedChromeOsHardware` (۱).

این‌ها اکنون **منجمد** شده‌اند: بیشتر شدنشان CI را سرخ می‌کند.

## ۹) دروازه‌ها

* **CI `android` روی کامیتِ baseline (`43038664214`): success** — و مهم‌تر، annotationِ خودِ
  گیت: `title=lint gate: 1385 issues` با `new ids: 0 | worse ids: 0 | improved ids: 0 |
  gone ids: 0`. یعنی گیت در حالتِ **enforcing** اجرا شد (warningِ «هنوز enforcing نیست»
  غایب بود) و صفر انحراف دید. `assembleDebug` و `testDebugUnitTest` هم سبز.
* **CI `tests` روی همان کامیت: success** (pytest + route audit + نگهبانِ دیتابیسِ واقعی).
* `ruff check .` = **۲۵۱** و `ruff --select F821` = **۱** — بدونِ تغییر، چون `KharazmiAdmin`
  در `extend-exclude` راف است. با این حال هر دو ابزارِ پایتونیِ این فاز
  (`lint_gate.py` و `find_dead_kotlin.py`) با ruff **پاک** شدند: ۲ مورد `W605`
  (escape نامعتبرِ `\s` در docstring — در ۳٫۱۲ به بعد SyntaxWarning) و ۲ مورد `SIM115`
  (بازکردنِ فایل بدونِ context manager در پویشِ ۸۷ فایلی) در `find_dead_kotlin.py` رفع شد و
  خروجیِ ابزار **دقیقاً** همان ماند (۸۵ فایل، ۱۹۰ XML، ۴۰۳ نماد، ۸ مرده/۱۰۴ خط؛
  منابع: ۰ مرده).
* `lint_gate.py` فقط stdlib است (argparse/json/os/sys/xml.etree) ⇒ روی رانر بدونِ نصبِ چیزی
  اجرا می‌شود.

## ۱۰) گامِ بعد — گزینه‌ها

1. **گیتِ warningهای کامپایلرِ Kotlin:** خطوطِ `w:` در `compileDebugKotlin` با همان الگوی
   «بدتر نشود». بدونِ وابستگیِ جدید، تقریباً رایگان.
2. **detekt/ktlint** برای سبکِ Kotlin — نیاز به افزونهٔ Gradle دارد (CI شبکه دارد، محلی نه).
3. **رفعِ باگ‌های Error-severityِ lint** (بندِ ۸) — به‌ویژه `NewApi`؛ **تغییرِ رفتار** است و
   باید جدا تصویب شود.
4. **P4d — خدا‑Activityها به لایهٔ service/repository** با نگه‌داشتنِ تابعِ نازکِ delegate در
   Activity تا متنِ محافظت‌شدهٔ تست‌ها (`keep_verbatim`) سرجایش بماند.
5. **P5 — گیتِ lint/type سمتِ سرور** (ruff ۲۵۱ / mypy ۷۲۶) با همین الگو؛ مزیتش این است که
   محلی قابلِ راستی‌آزمایی است و حلقهٔ بازخوردِ چندثانیه‌ای دارد، برخلافِ اندروید که هر تکرار
   یک رفت‌وبرگشتِ چنددقیقه‌ای با CI است.
6. بدهیِ باز از P4-prep: اجرای `./gradlew wrapper` در `KharazmiAdmin/` تا بتوان
   `validate-wrappers: false` + `gradle-version` + Guard step را از workflow برداشت.
