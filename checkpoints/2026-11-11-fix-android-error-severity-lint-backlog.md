# فاز P4-bugfix — صفرکردنِ تمامِ ۲۵ مسئلهٔ Error-severity لینتِ اندروید

تاریخ: ۲۰۲۶-۱۱-۱۱ · نقطهٔ شروع: `7dc617b` (= `main` پس از PR #13)
نوع: **رفعِ باگ** — این فاز عمداً رفتارمحافظ *نیست*؛ کاربر صریحاً اجازهٔ فازِ رفعِ باگ داد.
هر چهار دسته از پیش موجود بودند و هیچ‌کدام در فازهای ریفکتور ساخته نشده بودند.

---

## ۱) صورتِ مسئله

فازِ P4c لینت را برای اولین بار روشن کرد و baseline را روی **۱۳۸۵ مسئله / ۳۶ شناسه**
منجمد کرد. از این‌ها **۱۷۳ مورد Error** بودند. گیت جلویِ *بدتر شدن* را می‌گیرد ولی انباشتهٔ
موجود را دست نمی‌زند؛ پس Errorها یک فهرستِ باگِ از‌پیش‌موجود بودند که نیاز به تصمیمِ جدا
داشتند. کاربر آن را تصویب کرد.

نتیجهٔ این فاز: **هر ۲۵ مسئلهٔ Errorِ غیرِ StringFormatMatches رفع شد** و
`1385 → 1360`، `36 → 32` شناسه، `Error: 173 → 148`.

## ۲) پیش‌نیاز: مکانِ دقیق، که در baseline نیست

baseline عمداً فقط **شمار** دارد (باید در یک annotation جا شود) و گزارشِ XML فقط روی رانرِ
CI تولید می‌شود. پس دو چیز اضافه شد تا مکان‌ها بیرون بیایند:

* `lint_gate.py --locations --ids A,B --max-per-id N`
* در workflow: stepِ «Publish lint locations» با دو منبعِ درخواست — ورودیِ
  `workflow_dispatch`، و فایلِ commit‌شدهٔ `KharazmiAdmin/lint-locations-request.txt`
  (خطِ ۱: شناسه‌ها با کاما؛ خطِ ۲: سقف برای هر شناسه).

دومین منبع عمداً اضافه شد چون `gh workflow run` با توکنِ این محیط
**HTTP 403 «Resource not accessible by integration»** می‌دهد (حقِ `actions:write` ندارد)، یعنی
مسیرِ dispatch از این‌جا بسته است. با فایلِ commit‌شده، هر تشخیصِ جدید بدونِ دست‌زدن به
workflow ممکن است. پس از پایانِ کار این فایل **حذف شد** — capability در workflow می‌ماند و
هر وقت لازم شد با یک خط commit برمی‌گردد.

سه نکتهٔ مهندسی که در همین مسیر لو رفت:

* شرطِ step عمداً `github.event_name == 'workflow_dispatch'` را هم داشت، چون در رویدادِ push
  مقدارِ `inputs` **null** است و در عبارت‌های GitHub `null != ''` **true** می‌شود. بدونِ این
  محافظ step در هر push با لیستِ خالی اجرا می‌شد و «لیستِ خالی» در این ابزار یعنی **همهٔ
  شناسه‌ها** ⇒ ۱۳۸۵ مکان در هر اجرا.
* ورودی‌ها از `env` پاس می‌شوند نه درون‌خطی در `run:`، تا تزریقِ دستور ممکن نباشد.
* با `set -u`، خواندنِ `$REQ_FILE` وقتی env آن را نرسانده باشد step را می‌کُشت ⇒
  `${REQ_FILE:-lint-locations-request.txt}`. این را با اجرای verbatimِ بلوکِ shellِ step
  بدونِ هیچ env پیدا کردم، که دقیقاً شکلِ یک رویدادِ push است.

## ۳) سقفِ واقعیِ کانالِ annotation: ۴۰۹۶ کاراکتر

اولین درخواستِ مکان‌ها (۵ شناسه × ۲۰) حدود ۹KB شد و GitHub آن را **دقیقاً روی ۴۰۹۶
کاراکتر** برید (`message_len=4096`، و `raw_message` خالی). چیزی که بریده شد دقیقاً همان
`NewApi` و `SuspiciousIndentation` بود که برایشان رفته بودیم — چون `StringFormatMatches`
با ۲۰ خطِ اول کلِ فضا را پر کرده بود.

این فقط «خروجیِ بلند زشت است» نبود. `--emit-baseline` هم `lint-baseline.json` را از **همین**
کانال منتشر می‌کند و payload فعلی ۳۲۲۴ بایت است؛ روزی که baseline از ۴KB بگذرد، annotation
یک JSONِ **ناقص** می‌داد و کسی که آن را commit می‌کرد baselineِ خراب داشت — یعنی گیت بی‌معنا
می‌شد در حالی که سبز به نظر می‌رسید.

راه‌حل: همهٔ هفت انتشارِ ابزار از یک `emit_annotation()` عبور می‌کنند که روی مرزِ خط در
۳۹۰۰ کاراکتر می‌شکند (۱۹۶ حاشیه برای عنوان و `(part i/n)`)، قطعه‌ها را شماره می‌زند، و اگر
بیش از `MAX_PARTS=8` لازم بود **صریحاً warning می‌دهد** به‌جایِ اینکه بی‌صدا بقیه را بیندازد.

آزموده شد، نه فرض:

| ورودی | انتظار | نتیجه |
|---|---|---|
| ۲۰ خط | ۱ قطعه، بازچسباندن بایت‌به‌بایت یکسان | ✅ |
| ۲۷٬۶۳۹ کاراکتر | ۸ قطعه، هرکدام ≤ ۴۰۹۶، بازچسباندن یکسان | ✅ |
| ۸۳٬۸۸۹ کاراکتر | ۸ قطعه + ۱ warning با نامِ سرریز | ✅ |
| JSONِ ۷٬۲۱۷ کاراکتری | ۲ قطعه که به آبجکتِ معتبرِ **یکسان** برمی‌گردد | ✅ |

## ۴) چه رفع شد

### ۴٫۱ `SuspiciousIndentation` (۸) — فقط تورفتگی، **صفر تغییرِ رفتار**
`AddClassActivity:185`، `AttendanceActivity:903`، `ClassDetailActivity:487`،
`ClassManagementActivity:360`، `InvoiceActivity:293` و `:1148`، `SessionHistoryActivity:61`،
`TeacherCredentialsActivity:147`. هر هشت یک شکلِ واحد بودند، از یک اصلاحِ قبلیِ «Bug 19»:

```kotlin
} catch (e: Exception) {
// FIX: Bug 19 - cancellation is not a network/UI error.
if (e is kotlinx.coroutines.CancellationException) throw e;
    withContext(Dispatchers.Main) { ... }        // ← تودرتو به نظر می‌رسد، ولی نیست
```

`if` بدونِ آکولاد در Kotlin **دقیقاً یک جمله** می‌گیرد، پس `throw e` کلِ بدنه است و خطِ
تورفتهٔ بعدی از اول جملهٔ جداگانهٔ داخلِ `catch` بوده. یعنی **رفتار درست بود** (لغو را
دوباره پرتاب کن، وگرنه خطا را گزارش کن) و فقط تورفتگی دربارهٔ ساختار دروغ می‌گفت — که
دقیقاً همان چیزی است که باعث می‌شود نفرِ بعدی خطِ دومی اضافه کند به گمانِ اینکه محافظت‌شده
است. اصلاح: هم‌ترازکردنِ کامنت و `if` با جملهٔ بعدیشان و حذفِ `;` اضافی. تعدادِ خط‌ها عوض
نشد.

**دامنه عمداً محدود ماند:** این الگو **۱۷۶ بار در ۳۷ فایل** هست، ولی lint فقط این ۸ را
گرفت — یعنی فقط جاهایی که خطِ بعدی **عمیق‌تر** از `if` تورفته است. فقط همان ۸ دست خورد؛
قالب‌بندیِ مجددِ هر ۱۷۶ مورد diff بزرگی بود بدونِ اینکه هیچ نقصی را بردارد.

### ۴٫۲ `NewApi` (۱۴) — باگِ واقعی روی API 24/25
`android:paddingVertical` (۹ مورد) و `android:paddingHorizontal` (۵ مورد) در
`values/ds_styles.xml`، `values/themes.xml` و `values-night/themes.xml` از API 26 هستند و
`minSdk = 24` ⇒ روی دستگاهِ قدیمی فریم‌ورک **بی‌صدا نادیده‌شان می‌گیرد** و padding اصلاً
اعمال نمی‌شود. جایگزینی با معادلِ همه‌نسخه‌ها:

* `paddingVertical` → `paddingTop` + `paddingBottom`
* `paddingHorizontal` → `paddingStart` + `paddingEnd` (RTL-امن؛ اپ فارسی و
  `android:supportsRtl="true"` است، و چون هر دو طرف یک مقدار می‌گیرند نتیجهٔ رندرشده روی
  API 26+ **دقیقاً** همانِ قبل است)

راستی‌آزمایی با diffِ شمارِ itemهای صفت‌ها در برابرِ HEAD در همان سه فایل:
`paddingVertical 9→0`، `paddingTop/Bottom 2→11` (هرکدام +9)، `paddingHorizontal 5→0`،
`paddingStart/End 2→7` (هرکدام +5)، و **صفر `<item>` تکراری در هر ۱۱ فایلِ values** —
item تکراری در استایل build را می‌شکند، پس این بررسی لازم بود نه تزئینی.

**خارج از دامنه، ولی گزارش‌شده:** همان دو صفت **۹۱ بار دیگر در ۳۴ فایلِ layout** آمده‌اند و
`tools:targetApi` هم ندارند، ولی lint آن‌ها را `NewApi` **نمی‌گیرد** و پس بخشی از انباشتهٔ
Error نیستند. اینکه آیا این نقطهٔ کورِ lint است یا دلیلِ دیگری دارد، بررسیِ جدا می‌خواهد؛
ویرایشِ سرسریِ ۳۴ فایل در این فاز توجیه نداشت. این تنها بدهیِ شناخته‌شدهٔ باقی‌مانده از
این فاز است.

> **به‌روزرسانیِ ۲۰۲۶-۱۱-۱۲ (برشِ P4d-6) — بررسی انجام شد؛ پاسخ «نه نقطهٔ کور، بلکه
> رفتارِ عمدیِ ابزار» است:** aapt2 در `ResourceFileFlattener` همین صفت‌ها را در فایل‌های
> layout به معادلِ همه‌نسخه‌ها بازنویسی می‌کند (`paddingHorizontal` → `paddingLeft` +
> `paddingRight`) و lint هم دقیقاً همین چهار صفت (`padding{Horizontal,Vertical}` و
> `layout_margin{Horizontal,Vertical}`) را عمداً «benign» می‌داند (AOSP commit `139515660`
> در `platform/tools/base`). آن بازنویسی فقط برایِ layout است نه `values/` — که دقیقاً
> توضیح می‌دهد چرا آن ۱۴ موردِ `values*` به‌عنوانِ `NewApi` گرفته شدند و این ۹۱ مورد نه.
> پس **باگ نیستند** و ویرایشِ ۳۴ فایل هیچ نقصی را برنمی‌داشت؛ و چون `paddingHorizontal`
> به `paddingLeft/Right` تجزیه می‌شود نه `paddingStart/End`، جایگزینیِ دستی حتی می‌توانست
> رفتار را عوض کند. شواهد، زنجیرهٔ استنتاجی برایِ `values*` (چون در آن پنجرهٔ زمانی
> checkoutِ sandbox خواندنی نبود) و tripwireِ CI: `checkpoints/2026-11-12-investigate-phase4d6-padding-attrs-aapt2-desugar.md`.

### ۴٫۳ `ResourceType` (۲) — عددِ خام به‌جایِ شناسهٔ منبع
`CachedApiCall.kt` اسکلتِ شیمر و بنرِ آفلاین را با idهای خامِ `887766` و `998877` می‌ساخت
(تخصیص در `:38` و `:70`، جست‌وجو در `:59` و `:99`). دو خطر: عددِ دلخواه می‌تواند با یک idِ
واقعیِ تولیدشده توسط AAPT **برخورد** کند که آن‌وقت `findViewById` ویویِ اشتباهی می‌دهد و
`hideShimmer`/`removeView` روی ویویِ دیگری اثر می‌گذارد؛ و چون در `R` دیده نمی‌شود، هیچ
ابزاری نمی‌تواند ارجاع‌هایش را پیدا کند (همان مشکلی که آنالیزرهای P4b با آن سروکار دارند).
`res/values/ids.xml` با `shimmer_overlay_host` و `offline_banner_host` اضافه شد و هر چهار
سایت به `R.id.*` رفت.

### ۴٫۴ `PermissionImpliesUnsupportedChromeOsHardware` (۱)
`android.permission.CAMERA` به Play می‌گوید اپ **حتماً** دوربین می‌خواهد و اپ از دستگاه‌های
فاقدِ دوربین فیلتر می‌شود. `<uses-feature android:name="android.hardware.camera"
android:required="false" />` اضافه شد.

## ۵) آنچه عمداً رفع **نشد**

`StringFormatMatches` با **۱۴۸ مورد** تنها Errorِ باقی‌مانده است. نمونه‌های بررسی‌شده همه یک
شکلِ بی‌ضرر دارند: `%s` که `int` یا `long` می‌گیرد (`getString(R.string.capi_days_ago, days)`)
و `String.format("%s", 42)` به‌درستی `"42"` می‌دهد. حجمش زیاد است و ارزشِ رفعِ یک‌باره ندارد؛
در baseline منجمد است و بدترشدنش CI را سرخ می‌کند.

همچنین `1212` Warning (بزرگ‌ترین‌ها: `HardcodedText` ۶۵۲، `DefaultLocale` ۱۰۵،
`SetTextI18n` ۶۸، `Overdraw` ۵۳، `RtlHardcoded` ۴۷) دست‌نخورده ماندند: هدفِ این فاز فقط
ردهٔ Error بود.

## ۶) راستی‌آزمایی

**محلی:** `1279 passed` (Kharazmi_Server/tests) · `249 passed` (tests/route_audit، پروسهٔ
جدا) · md5 دیتابیسِ واقعیِ آموزشگاه `f048f8d118b33c4eaa944490594121d7` بدونِ تغییر ·
ruff `251` · `ruff --select F821` `1` · mypy `726` خطا در `44` فایل ·
`validate_app_map.py` پاک (`retrofit_source_map_missing=[]`، `android_only_routes=0`،
`server_map_exact=true`، `server_runtime_count=221`، `server_map_stale=[]`) ·
`find_dead_kotlin.py` همان **۸ نمادِ DEFER** و `find_dead_resources.py` **۰** — با تعریف‌های
منبع `1840 → 1842` یعنی دقیقاً دو idِ جدید و صفر حذف.

**`test_android_resources_static.py` دست‌نخورده ماند** (`keep_verbatim`). تنها تستی که چیزی
از این ناحیه را پین کرده `assertIn("CancellationException", restore)` برای بدنهٔ
`restoreArchivedClass(` در `ArchivedClassDetailActivity.kt` است — که **جزوِ آن ۸ سایت نیست**
و متنش عوض نشد؛ ضمناً خودِ واژه در هر ۸ سایتِ اصلاح‌شده هم باقی است. هیچ تستی
`paddingVertical`/`paddingHorizontal` یا permission دوربینِ manifest را پین نکرده.

**CI (اجرای `43046008679`) — دو مسیرِ مستقل یکدیگر را تأیید کردند:**
1. `:app:assembleDebug` و `:app:testDebugUnitTest` سبز ⇒ تغییراتِ Kotlin و XML کامپایل و
   لینک می‌شوند (این داورِ واقعیِ `R.id.*` و ساختارِ استایل‌هاست).
2. annotationِ مکان‌ها: `ids requested but not present in this report: NewApi,
   PermissionImpliesUnsupportedChromeOsHardware, ResourceType, SuspiciousIndentation` و
   `locations listed: 0` — یعنی از مسیرِ جست‌وجوی مکان، نه شمارش، هر چهار شناسه ناپدیدند.
3. annotationِ گیت: `1385 → 1360 (-25)`، `36 → 32` شناسه، `gone ids: 4`، و مهم‌تر
   **`new ids: 0 | worse ids: 0`** ⇒ هیچ regression تازه‌ای ساخته نشده.
4. `Warning: 1212 → 1212` بدونِ تغییر ⇒ Errorها به Warning **تنزل** داده نشدند (یک راهِ
   تقلبِ ناخواسته در گیت‌های شمارشی دقیقاً همین است).

**قفل‌شدنِ دستاورد:** baselineِ تازه از annotationِ خودِ CI با پارسِ ماشینی ساخته شد
(نه بازنویسیِ دستیِ ۳۲ عدد)، با assertهایی که جمعِ شمارها = `total`، تعدادِ شناسه‌ها =
`distinct_ids`، جمعِ شدت‌ها = `total`، و **هیچ یک از ۳۲ شناسهٔ دست‌نخورده drift نداشته
باشد**. سپس round-trip: از همین baseline یک گزارشِ مصنوعیِ ۱۳۶۰-مسئله‌ای بازسازی شد و گیت
صفر تفاوت داد؛ و با افزودنِ یک `NewApi` به آن گزارش، گیت **exit 1** داد با
`NEW 1 Error NewApi`. یعنی بازگشتِ هر یک از این باگ‌ها از این پس CI را سرخ می‌کند.

یک نکتهٔ روشی: اسکریپتِ راستی‌آزماییِ همین baseline در اولین تلاش روی یک assertِ اشتباهِ
**خودش** مرد (`new["by_id"][k]` برای شناسه‌هایی که رفته بودند، به‌جای `old[...]`) و چون
نوشتنِ فایل بعد از assertها بود، چیزی نیمه‌کاره نوشته نشد. fail-closed بودنِ همان اسکریپتِ
یک‌بارمصرف هم تصادفی نبود.

## ۷) وضعیتِ انباشتهٔ lint پس از این فاز

`1360 مسئله / 32 شناسه · Error=148 (همه StringFormatMatches) · Warning=1212`

## ۸) گامِ بعد

1. **P4d — خدا‑Activityها به لایهٔ service/repository** با تابعِ نازکِ delegate در Activity تا
   متنِ محافظت‌شدهٔ تست‌ها سرجایش بماند. حالا که Errorهای لینت صفرِ واقعی شده‌اند، این کار
   روی درختِ امن‌تری انجام می‌شود — به‌ویژه چون ۸ موردِ `SuspiciousIndentation` دقیقاً همان
   الگویی بودند که جابه‌جایی‌شان در ریفکتور خطرناک بود.
2. ~~بررسیِ آن **۹۱ موردِ layout** از `paddingVertical/Horizontal` که lint نگرفت (بندِ ۴٫۲).~~
   **انجام شد (۲۰۲۶-۱۱-۱۲، برشِ P4d-6): نقطهٔ کور نیست — aapt2 بازنویسی‌شان می‌کند و
   lint عمداً benign می‌داندشان ⇒ باگ نیستند.** `checkpoints/2026-11-12-investigate-phase4d6-padding-attrs-aapt2-desugar.md`.
3. گیتِ warningهای کامپایلرِ Kotlin (خطوطِ `w:`) با همین الگوی «بدتر نشود».
4. بدهیِ باز از P4-prep: `./gradlew wrapper` تا بتوان `validate-wrappers: false` و Guard step
   را از workflow برداشت.
