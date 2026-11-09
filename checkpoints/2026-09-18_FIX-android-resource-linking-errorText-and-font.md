# CHK 2026-09-18 — FIX: خطای بیلد اندروید (`LinkApplicationAndroidResourcesTask` / `attribute errorText not found`)

برنچ: `arena/01a0aac2-kharazmiapp` | نوع تسک: **فقط رفع خطای بیلد (منابع)** — صفر تغییر منطق، صفر تغییر کد Kotlin/Java/Python.

---

## ۱) خطای گزارش‌شده‌ی کاربر (ورودی تسک)

```
failure occurred while executing com.android.build.gradle.internal.res.LinkApplicationAndroidResourcesTask$TaskAction
  > Android resource linking failed
    com.example.kharazmiadmin.app-main-46:/layout/activity_design_system.xml:586:
      error: attribute errorText (aka com.example.kharazmiadmin:errorText) not found.
    error: failed linking file resources.
```

## ۲) ریشه‌ی خطا (تأیید‌شده)

- فایل خطادار از **فاز ۱ UI** است: `activity_design_system.xml` (چیدمان کاتالوگ Design System)، نه صفحات فاز ۲.
- `app:errorText` **اصلاً وجود ندارد**؛ نه در Material 1.12.0 (فایل رسمی `textfield/res/values/attrs.xml`)، نه در AppCompat/AndroidX، نه در فریم‌ورک API 34، و نه در خود پروژه.
- Material برای «متن زیر فیلد» فقط این‌ها را دارد: `app:helperText`، `app:helperTextTextColor`، `app:helperTextTextAppearance`، `app:errorEnabled`، `app:errorTextAppearance`، `app:errorTextColor`، `app:boxStrokeErrorColor`.
- کد Kotlin روی این ویو هیچ کاری نمی‌کند (`DesignSystemActivity.kt` نه `setError` صدا می‌زند و نه به `TextInputLayout`ها دست می‌زند) ⇒ تغییر، **صرفاً نماست** و هیچ رفتاری را عوض نمی‌کند.

## ۳) فیکس (دقیقاً ۲ attribute → ۳ attribute)

```diff
                         android:hint="@string/ds_input_phone"
                         app:errorEnabled="true"
-                        app:errorText="@string/ds_input_error_text">
+                        app:boxStrokeColor="@color/ds_danger"
+                        app:helperText="@string/ds_input_error_text"
+                        app:helperTextTextColor="@color/ds_danger">
```

نتیجه‌ی بصری همان «فیلد دارای خطا» می‌ماند (قاب قرمز + متن قرمز زیر فیلد)، ولی این بار با attributeهای **موجود** و بدون هیچ منطق جدید.

## ۴) فیکس دوم (که بلافاصله بعد از فیکس اول بیلد را می‌شکست)

پیش از این، `res/font/app_font.xml` به `@font/vazirmatn_regular` ارجاع می‌داد که **هیچ فایل فونتی در مخزن نداشت**
(`find` روی کل ریپو: صفر فایل `.ttf/.otf`؛ در تاریخچه هم هرگز نبوده) ⇒ بعد از رفع `errorText`، خطای بعدی
`resource font/vazirmatn_regular not found` بود. چون اجرای بیلد در این سندباکس ممکن نیست (بخش ۶)، این مورد
استاتیک کشف و با افزودن منبع واقعی رفع شد:

| مورد | مقدار |
|---|---|
| فایل جدید | `KharazmiAdmin/app/src/main/res/font/vazirmatn_regular.ttf` (۱۲۲٫۷۵۲ بایت) |
| منبع | <https://github.com/rastikerdar/vazirmatn> → `fonts/ttf/Vazirmatn-Regular.ttf` |
| نسخه | Vazirmatn **33.003** (Family=`Vazirmatn`، Subfamily=`Regular`، sfnt=TrueType، ۱۵ جدول) |
| sha256 | `b69fd4c680b8f3f225feabcc655a2c585d97627b8f5f5c0f9985e894069f3a56` |
| مجوز | SIL OFL 1.1 — متن کامل، بیت‌به‌بیت مطابق فایل بالادست، در `THIRD_PARTY_NOTICES.md` |
| تطبیق با `app_font.xml` | `app:fontStyle="normal" app:fontWeight="400"` ⇒ فونت **استاتیک Regular** (سازگار با minSdk=24؛ برخلاف variable-font) |

`app_font.xml` و ارجاع‌های `@font/app_font` در تم‌ها **دست‌نخورده** ماندند (قید فاز ۱). اگر فایل فونت دیگری
مدنظر است، فقط همان مسیر را جایگزین کنید: `KharazmiAdmin/app/src/main/res/font/vazirmatn_regular.ttf`.

## ۵) اسکن استاتیک aapt2 (چون اجرای gradle ممکن نیست)

اسکریپت `/tmp/aapt2_preflight.py` (بازتولیدشدنی) کل `res/` + `AndroidManifest.xml` را در ۸ محور بررسی می‌کند:

| # | محور | اوورکل | نتیجه روی درخت فعلی |
|---|---|---|---|
| ۱ | XML خراب (well-formedness) | — | ✅ هیچ |
| ۲ | نام فایل نامعتبر (`[^a-z0-9_.]`) | قواعد aapt2 | ✅ هیچ |
| ۳ | **attribute ناموجود** (`app:`/`android:`) | ۲٬۶۵۳ اتربیوت Material 1.12.0 + AppCompat 1.7 + AndroidX + فریم‌ورک API 34 (AOSP) + shimmer + اتربیوت‌های خود پروژه + ۲۰۷ اتربیوت موجود در baseline | ✅ هیچ |
| ۴ | `item` ناموجود داخل style | همان اوورکل | ✅ هیچ |
| ۴-ب | `item`های پیشونددار (`android:`/`app:`) ناموجود | همان اوورکل | ✅ هیچ |
| ۵ | تعریف تکراری منبع در همان config | جمع‌آوری همه‌ی `values*` + پوشه‌های منبع | ✅ هیچ |
| ۶ | ارجاع به منبع ناموجود (`@drawable|color|dimen|string|style|font|...`) | نقشه‌ی کامل منابع تعریف‌شده | ✅ هیچ (قبلاً: `@font/vazirmatn_regular` → رفع شد) |
| ۷ | ارجاعات `AndroidManifest.xml` (`@mipmap/ic_launcher` و ...) | نقشه‌ی منابع | ✅ هیچ |
| ۸ | پوشه‌های منبع فایلی | — | `mipmap-anydpi-v26`=۲، `font`=۲، `xml`=۳ |

**اثبات «failing-first» اسکنر (مهم‌ترین شاهد):** روی همان فایلِ قبل از فیکس (`077ad74:activity_design_system.xml`)
اسکنر خروجی می‌دهد `(586, 'errorText')` و روی درخت بعد از فیکس `— هیچ ✅`. یعنی ابزار همان خطای واقعی aapt2 را
قبل از بیلد می‌گیرد (و ۶ کلاس خطای دیگر را هم پوشش می‌دهد).

## ۶) چرا در سندباکس بیلد نشد (بدون جعل نتیجه)

| ابزار | وضعیت واقعی |
|---|---|
| `java -version` | `command not found` — `JAVA_HOME` خالی، `/usr/lib/jvm` وجود ندارد |
| `ANDROID_HOME` / `ANDROID_SDK_ROOT` | خالی؛ `sdkmanager` نیست |
| `curl` به `services.gradle.org` / `dl.google.com` / `repo1.maven.org` | `000` (فقط `github.com`/`api.github.com`/`pypi` باز است) |
| `gradlew` | `-rw-r--r--` (بدون بیت اجرا؛ chmod نکردم) |

پس `assembleDebug` این‌بار هم اجرا نشد و **هیچ ادعایی دربارهٔ سبز بودن بیلد وجود ندارد**؛ اعتبارسنجی استاتیک بخش ۵
جای آن را می‌گیرد. **داور نهایی، بیلد خود شماست.**

## ۷) دامنه‌ی تغییر (اثبات «هیچ منطقی تغییر نکرد»)

```
$ git diff-tree -r --name-status 077ad74 <worktree-tree>
A  KharazmiAdmin/app/src/main/res/font/vazirmatn_regular.ttf
M  KharazmiAdmin/app/src/main/res/layout/activity_design_system.xml
A  THIRD_PARTY_NOTICES.md
$ git diff-tree -r --stat 077ad74 <worktree-tree>
 .../res/font/vazirmatn_regular.ttf                  | Bin 0 -> 122752 bytes
 .../res/layout/activity_design_system.xml           |   4 +-
 THIRD_PARTY_NOTICES.md                              | 120 +++++++++++++++++++++
 3 files changed, 123 insertions(+), 1 deletion(-)
$ git diff-tree -r --name-only 077ad74 <tree> | grep -E '\.(kt|java|py)$'   → خالی
```

هیچ فایل Kotlin/Java/Python، هیچ چیدمانی از فاز ۲، هیچ `strings.xml`/`colors.xml`/`dimens.xml` و هیچ
AndroidManifest‌ای در این فیکس تغییر نکرده است.

## ۸) یادداشت‌های صادقانه

- **آیکون لانچر:** `@mipmap/ic_launcher` و `ic_launcher_round` فقط در `mipmap-anydpi-v26` وجود دارند
  (adaptive icon). بیلد را نمی‌شکند (لینک می‌شود)، ولی روی **API 24/25** نسخه‌ی دیگری برای fallback وجود ندارد؛
  اگر پشتیبانی از API 24/25 مهم است، افزودن `mipmap-mdpi…xxxhdpi` لازم است. این وضعیت **پیش‌موجود** و خارج از دامنه‌ی این فیکس است.
- اگر بیلد شما خطای بعدی داد، **کل خروجی را بفرستید** (نه فقط خط آخر) تا همان کلاس خطا را در اسکنر ببندم؛
  اسکنر فعلی ۸ کلاس خطای resource-linking را پوشش می‌دهد و خروجی‌اش اکنون «۰ شکست» است.
- فاز ۲ UI (کامیت `077ad74`) در این فیکس دست‌نخورده است؛ فقط فایل کاتالوگ فاز ۱ + یک منبع فونت اضافه/اصلاح شد.

## ۹) بازتولید

```
git checkout arena/01a0aac2-kharazmiapp && git pull
cd KharazmiAdmin && ./gradlew :app:assembleDebug     # اکنون باید از مرحله‌ی resource linking رد شود
```
