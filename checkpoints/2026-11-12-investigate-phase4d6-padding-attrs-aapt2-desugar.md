# P4d-6 — بررسیِ معوقِ PR #14: آن ۹۱ موردِ `paddingVertical/Horizontal` در layoutها **باگ نیستند**

این برش هیچ کدِ اجرایی‌ای را تغییر نمی‌دهد. کارش سه چیز است: بستنِ یک پرسشِ بازِ
مستندشده، تصحیحِ یک ادعایِ **غلط** که در checkpointِ برشِ قبلی نوشته بودم، و گذاشتنِ یک
tripwire در CI تا اگر روزی این کلاسِ باگ واقعاً برگشت، مکانِ دقیقش منتشر شود.

## ۱) پرسشِ معوق

PR #14 (`fix-android-error-severity-lint-backlog`) چهارده خطایِ `NewApi` را در
`values/ds_styles.xml`، `values/themes.xml` و `values-night/themes.xml` اصلاح کرد و بعد
صریحاً نوشت:

> «همان دو صفت **۹۱ بار دیگر در ۳۴ فایلِ layout** آمده‌اند و `tools:targetApi` هم ندارند،
> ولی lint آن‌ها را `NewApi` **نمی‌گیرد**… اینکه آیا این نقطهٔ کورِ lint است یا دلیلِ دیگری
> دارد، بررسیِ جدا می‌خواهد؛ ویرایشِ سرسریِ ۳۴ فایل در این فاز توجیه نداشت.»

و در بندِ «گامِ بعد» همان doc، این بررسی به‌عنوانِ **آیتمِ ۲** باز مانده بود. دو docِ دیگرِ
همین فاز هم آن را به‌عنوانِ بدهیِ باز تکرار کرده بودند. پس پرسش این بود: **نقطهٔ کورِ lint
است یا دلیلِ دیگری دارد؟**

## ۲) ادعایِ غلطی که خودم نوشته بودم

در `checkpoints/2026-11-12-fix-phase4d5-jalali-roundtrip-guard.md` §۷ نوشته بودم:

> «`minSdk = 24` ولی `android:paddingVertical/Horizontal` نیاز به **API 26** دارد ⇒
> **۱۰۵ رخداد در ۳۷ فایلِ layout** رویِ دستگاه‌هایِ ۲۴–۲۵ بی‌صدا نادیده گرفته می‌شوند
> (باگِ بصریِ واقعی، نه فقط نویزِ lint).»

دو خطا در همین دو جمله:

1. **۳۷ فایل، layout نیستند.** آن ۳۷ فایل = **۳۴ layout + ۳ فایلِ values** است
   (`values/themes.xml`، `values/ds_styles.xml`، `values-night/themes.xml`). شمارِ کلِ
   ۱۰۵ رخدادِ خام هم با عددِ PR #14 نمی‌خواند: `۱۰۵ − ۹۱ = ۱۴`، و ۱۴ دقیقاً همان
   `۹ paddingVertical + ۵ paddingHorizontal` است که PR #14 از `values*` برداشت. یعنی
   grepِ من رویِ **کلِ** `res/` زده شده بود و من آن را «layout» نامیدم.
2. **«باگِ بصریِ واقعی» برایِ layoutها نادرست است** — بندِ بعد.

اگر این ادعا بدونِ بررسی باور می‌شد، نتیجه‌اش ویرایشِ ۳۴ فایل و ~۹۱ جایگزینی بود که
**هیچ نقصی را برنمی‌داشت** — دقیقاً همان کاری که PR #14 به‌درستی از آن پرهیز کرده بود.

## ۳) پاسخ با سه منبعِ دستِ‌اول

**الف) خودِ lint این چهار صفت را عمداً «benign» می‌داند.** کامیتِ AOSP با شناسهٔ
`139515660` در `platform/tools/base` (عنوان: «marginHorizontal is flagged as
UnusedAttribute») دقیقاً همین فهرست را اضافه می‌کند:

```kotlin
// The following attributes are benign because aapt2 will rewrite them
// into the safe alternatives; e.g. paddingHorizontal gets rewritten as
// paddingLeft and paddingRight; this is done in aapt2's
// ResourceFileFlattener::ResourceFileFlattener
"paddingHorizontal",
"paddingVertical",
"layout_marginHorizontal",
"layout_marginVertical" -> true
```

و متنِ خودِ کامیت: «AAPT will rewrite {margin,padding}{Horizontal,Vertical} into the
corresponding left/right attributes **such that they work correctly on older platforms**;
no need to flag as unused on older platforms.»
منبع: `https://android.googlesource.com/platform/tools/base/+/06d37c21031d973dc8f6cc768dcf15d0147db26c%5E!/`

**ب) release notes خودِ AAPT2** (نسخهٔ ۲٫۱۶): «Versioning of XML files is more
intelligent, using a small set of rules to **degrade specific newer attributes to
backwards compatible versions** of them. Ex: `android:paddingHorizontal` degrades to
`android:paddingLeft` and `android:paddingRight`.»
منبع: `https://android.googlesource.com/platform/frameworks/base/+/master/tools/aapt2/readme.md`

**پ) تفکیکِ حیاتی: layout در برابرِ values.** همان desugar فقط برایِ **فایل‌های layout**
انجام می‌شود نه styleها — این دقیقاً همان چیزی است که تجربهٔ عملی هم تأیید می‌کند
(«AAPT2 supports desugaring backwards-translation for XML attribute
android:paddingHorizontal, but only for layout files, not styles»). و این دقیقاً همان
دلیلی است که lint آن ۱۴ موردِ `values*` را `NewApi` **گرفت** (و PR #14 اصلاحشان کرد)
ولی ۹۱ موردِ layout را **نگرفت**.

⇒ **نتیجه: نقطهٔ کور نیست؛ رفتارِ صحیح و عمدیِ ابزار است.** آن ۹۱ مورد باگ نیستند:
padding رویِ API 24–25 هم اعمال می‌شود. (و چون `paddingHorizontal` یک مقدار به هر دو طرف
می‌دهد، بازنویسی به `paddingLeft`+`paddingRight` هم از نظرِ RTL بی‌خطر است — هر دو طرف
همان مقدار را می‌گیرند.)

## ۴) اندازه‌گیریِ مستقیم — و مانعِ محیطی (صادقانه)

می‌خواستم انطباق‌های `values*` را خط‌به‌خط بخوانم تا ثابت کنم صفتِ زنده نیستند. **نتوانستم.**
checkoutِ این sandbox در این پنجرهٔ زمانی ناقص و ناسازگار بود:

```
git ls-tree HEAD                       → ۰ ورودی   (درختِ ریشه خواندنی نیست!)
git ls-tree HEAD KharazmiAdmin/app/src → ۰ ورودی
ls  KharazmiAdmin/app/src/main/res     → anim color drawable font layout …  (کار می‌کند)
find …/res -maxdepth 2 -name '*.xml'   → ۰ فایل    (در همان لحظه!)
ls  …/res/values                       → colors.xml dimens.xml ds_styles.xml …
test -d KHarazmi_Server                → وجود ندارد
.git                                   → ۲٫۷MB / ۹۴۲ آبجکت (shallow، فقط ۱ commit دیده می‌شود)
```

۳۳۰ تلاش با فاصلهٔ ۱ ثانیه رویِ **دو** کانالِ مستقل (`os.walk` رویِ دیسک و
`git ls-tree` + `git cat-file --batch`) همه خالی برگشتند. پس هیچ عددی از این مسیر
گزارش نمی‌کنم — **«۰ رخداد» اینجا یعنی «نخواندم»، نه «نیست»**. (یک بار در همین برش
اسکریپتم از رویِ خواندنِ ناموفق نتیجهٔ «پاک است» گرفت و من آن نتیجه را باطل کردم؛
درسش در بندِ ۶ آمده.)

## ۵) زنجیرهٔ استنتاجی برایِ `values*` (بدونِ نیاز به خواندنِ res)

چون اندازهٔ مستقیم ممکن نشد، از دو واقعیتِ **موفق خوانده‌شده** نتیجه گرفتم:

1. رویِ همین commit (`7ee8985`) گیتِ lint در CI اعلام کرد: `baseline=1360 now=1360 (+0)`،
   `distinct ids: baseline=32 now=32`، `new ids: 0`. در بیس‌لاینِ commit‌شده هم
   `NewApi` و `UnusedAttribute` **اصلاً حضور ندارند** و `per_severity` = `{Error: 148,
   Warning: 1212}` که تمامِ ۱۴۸ خطا از نوعِ `StringFormatMatches` است. گیتِ ما
   (`KharazmiAdmin/lint_gate.py`) **همهٔ** `<issue>`ها را می‌شمارد و هیچ فهرستِ
   سفیدی در کار نیست (`--ids` فقط نشرِ محل‌ها را محدود می‌کند)، و قاعده‌اش «شناسهٔ
   جدید = شکست» است.
2. خودِ PR #14 ثابت کرد که lint رخدادِ **واقعیِ** این صفت‌ها را در `values*` به‌عنوانِ
   `NewApi` می‌گیرد — آن ۱۴ مورد از دلِ انباشتهٔ Errorِ lint بیرون آمده بودند.

از ۱ و ۲: اگر در `values*` صفتِ زنده‌ای مانده بود، CI باید `NewApi` را به‌عنوانِ یک
**شناسهٔ جدید** گزارش می‌کرد و گیت می‌شکست. نگفت و نشکست ⇒ **صفتِ زنده‌ای در `values*`
نیست**. آن ۱۴ انطباقِ خام باید متنِ غیرِصفت باشند (محتمل‌ترین: کامنتِ مستندسازیِ همان
رفع). صورتِ دقیقِ آن متن را نخوانده‌ام و ادعا هم نمی‌کنم.

## ۶) شاهدِ تجربی از خودِ CI + tripwire دائمی

به‌جایِ تکیه بر استنتاج، از مکانیزمِ in-bandِ خودِ ریپو استفاده کردم: فایلِ
`KharazmiAdmin/lint-locations-request.txt` که گامِ «Publish lint locations for the
requested ids» در نبودِ inputِ `lint_ids` می‌خواندش (خطِ ۱ = شناسه‌ها، خطِ ۲ =
`--max-per-id`). محتوایش `NewApi,UnusedAttribute` است.

`lint_gate.py --locations` خروجی را هم print می‌کند و هم با `emit_annotation` به
annotation تبدیل می‌کند — و annotation تنها کانالی است که از `api.github.com` برایِ ما
خواندنی است (artifact و لاگِ خام بسته‌اند). اگر شناسه‌ها در گزارش نباشند، اسکریپت
می‌نویسد `ids requested but not present in this report: …` و **exit غیرِصفر نمی‌دهد**، پس
CI نمی‌شکند.

انتظار: annotation باید بگوید آن دو شناسه در گزارش نیستند ⇒ تأییدِ تجربیِ «هیچ رخدادِ
زنده‌ای هیچ‌جا». و بعد از این برش، فایل سرِ جایش می‌ماند به‌عنوانِ **tripwire**: اگر روزی
کسی `paddingVertical` واقعی را به یک style برگرداند، CI همان لحظه مکانِ `file:line` را
منتشر می‌کند. (گیتِ lint هم مستقل از این، `NewApi` را به‌عنوانِ شناسهٔ جدید می‌شکند.)

**نتیجهٔ واقعیِ اجرا — شاهدِ دریافت‌شده، نه پیش‌بینی.** اجرایِ CI شمارهٔ `43248926932`
رویِ commit `12dca7b` این annotation را منتشر کرد:

```
[notice] lint locations for NewApi UnusedAttribute ::
  ids requested but not present in this report: NewApi, UnusedAttribute
  locations listed: 0
```

یعنی در checkoutِ **سالمِ** CI، در کلِ ماژولِ app هیچ مسئلهٔ زندهٔ `NewApi` یا
`UnusedAttribute` وجود ندارد — نه در آن ۳۴ فایلِ layout و نه در `values*`. این همان حلقهٔ
تجربیِ ناقصِ بندِ ۵ است: چون PR #14 ثابت کرده بود lint رخدادِ واقعیِ این صفت‌ها را در
`values*` به‌عنوانِ `NewApi` می‌گیرد، صفر بودنِ هر دو شناسه در کلِ ماژول یعنی آن ۱۴
انطباقِ خام در `values*` **صفتِ زنده نیستند**. پس زنجیرهٔ استنتاجیِ بندِ ۵ با شاهدِ
مستقیم بسته شد و دیگر به خواندنِ `res/` در این sandboxِ خراب نیازی نیست.

از همان اجرا: گیتِ lint `total: baseline=1360 now=1360 (+0)` · `distinct ids: 32 → 32` ·
`new ids: 0 | worse ids: 0 | improved ids: 0 | gone ids: 0` · `per_severity: Error=148
(همه StringFormatMatches), Warning=1212` · `files with issues: 157` · هر دو شغلِ pytest
(`repo root + temp DB` و `route audit`) success · گامِ ۸ «Run JVM unit tests» success.

## ۷) تصحیحاتِ همین برش

| فایل | تغییر |
|---|---|
| `checkpoints/2026-11-12-fix-phase4d5-jalali-roundtrip-guard.md` §۷ | بندِ غلطِ «۱۰۵ رخداد در ۳۷ فایلِ layout… باگِ بصریِ واقعی» با صورتِ درست جایگزین شد |
| `checkpoints/2026-11-11-fix-android-error-severity-lint-backlog.md` §۴٫۲ | یادداشتِ «به‌روزرسانی: بررسی انجام شد» به بندِ «خارج از دامنه» افزوده شد (متنِ تاریخی دست‌نخورده) |
| همان doc §۸ آیتمِ ۲ | به‌عنوانِ انجام‌شده علامت خورد |
| `checkpoints/2026-11-11-refactor-phase4d-android-api-contract-extraction.md` §۸ | همان بندِ بدهی «بسته شد» خورد |
| `checkpoints/2026-11-11-refactor-phase4d2-audit-trail-layers.md` §۹ | همان بندِ بدهی «بسته شد» خورد |
| `KharazmiAdmin/lint-locations-request.txt` | **جدید** — tripwire/شاهدِ CI |

اصلِ «متنِ تاریخیِ checkpoint را بازنویسی نکن، حاشیه بزن» رعایت شد: فقط ادعایِ **برشِ
خودم** (که هنوز کسی رویش کار نکرده بود) جایگزین شد و سه docِ تاریخی یادداشتِ
به‌روزرسانی گرفتند.

## ۸) چرا هیچ ویرایشِ کدی نکردم

۹۱ جایگزینی در ۳۴ layout هیچ نقصی را برنمی‌داشت، diff بزرگی می‌ساخت، و ریسکِ واقعی هم
داشت: `paddingHorizontal` به `paddingLeft`+`paddingRight` تجزیه می‌شود درحالی‌که جایگزینیِ
دستیِ RTL-امن `paddingStart`+`paddingEnd` است — یعنی تغییرِ دستی می‌توانست **رفتار را عوض
کند** درحالی‌که aapt2 همان کارِ درست را بی‌خطر انجام می‌دهد. دست‌زدن به ۳۴ فایلِ UI بدونِ
هیچ نقصِ برداشته‌شده، خلافِ همان اصلی است که PR #14 رعایت کرد.

## ۹) بدهیِ باقی‌مانده (پس ازِ این تصحیح)

- ریفکتور: ۱۰ ماژول بالایِ ۶۰۰ خط (`InvoiceActivity` ۱۱۸۶، `StudentProfileActivity` ۱۱۱۳،
  `AppModels` ۱۰۳۹، …) با جمعِ ۲۴٬۴۰۱ خط. کوچک‌کردنِ دو تایِ بزرگ‌تر لایهٔ ViewModel
  می‌خواهد و به پین‌های کورپسِ تست می‌خورد (۱۵ عضو از ۳۱ عضوِ `InvoiceActivity` سخت
  پین‌شده‌اند).
- lint: ۱۳۶۰ مسئله / ۳۲ شناسه منجمد (`Error=148` همه `StringFormatMatches`).
- `find_dead_kotlin`: ۸ نماد / ۱۰۴ خط با برچسبِ DEFER (عمدی).
- `validate_app_map.py` با exit=1 (چهار مسیرِ live-session فقط در اندروید) و در هیچ workflow نیست.
- گیتِ warningهای کامپایلرِ Kotlin (`w:`) ساخته نشده. ریفکتورِ `./gradlew wrapper`
  (برایِ برداشتنِ `validate-wrappers: false`) — بدهیِ PR #19 که عمداً باز ماند.
- ruff ۲۵۱ یافته (از جمله `--select F821` = ۱ در `routers/exams.py:379:48`) و mypy ۷۲۶
  مسئله در ۴۴ فایل.
- ~~۹۱ موردِ `paddingVertical/Horizontal` در layoutها~~ — **با همین برش بسته شد: باگ نبودند.**

## ۱۰) یادداشتِ روش‌کار (برایِ برش‌های بعد)

در این sandbox خواندنِ فایل **می‌تواند** بی‌صدا شکست بخورد: `ls` موفق، `find`/`cat`/`open()`
با `ENOENT` در همان ثانیه؛ `git ls-tree` رویِ ریشه ۰ ورودی درحالی‌که `git status` درخت را
تمیز می‌بیند. پس هر اسکریپتِ اندازه‌گیری **باید شاهدِ مثبت** داشته باشد (مثلاً «باید
≥۱۰۰ فایلِ xml پیدا کنم و `values/themes.xml` باید `<resources` داشته باشد») و اگر شاهد
رد شد **هیچ عددی** گزارش نکند. صفرِ بی‌شاهد، خطرناک‌ترین خروجیِ ممکن است چون درست به
نظر می‌رسد.
