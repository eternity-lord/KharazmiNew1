# فاز P4-prep و P4a — گیتِ CI اندروید، رفعِ «اپ هرگز build نمی‌شد»، و پاک‌سازیِ منابعِ مرده

تاریخ: ۲۰۲۶-۱۱-۱۰ · نقطهٔ شروع: `4ccc8aa` (= `main` پس از PR #10)
نوع: P4-prep یک **رفعِ باگ + زیرساختِ CI** بود؛ P4a یک **پاک‌سازیِ رفتارمحافظ**.

---

# بخشِ اول — P4-prep: گیتِ CI اندروید (PR #10، ادغام‌شده `4ccc8aa`)

## چرا

تا پیش از این، **هیچ workflow ای اپ اندروید را build نکرده بود**. تنها CI ریپو `tests.yml`
بود که pytest سمتِ سرور را می‌دواند. یعنی ۸۷ فایل Kotlin (۲۴٬۲۸۱ خط) بدونِ هیچ گیتِ
خودکاری تغییر می‌کردند و سؤالِ «آیا `main` امروز اصلاً کامپایل می‌شود؟» **بی‌پاسخ** بود.

این سؤال پیش‌شرطِ کلِ فاز P4 است: محیطِ کاریِ ما نه JVM دارد، نه Gradle، نه `kotlinc`، و
نه مسیری به Maven Central یا مخزنِ Google (هر دو timeout). پس هیچ تغییرِ Kotlin را نمی‌توان
محلی کامپایل یا تست کرد. ریفکتورِ «رفتارمحافظ» بدونِ baseline ای که کامپایل شود، ادعاییِ
غیرقابلِ راستی‌آزمایی است.

## چه چیزی اجرا می‌شود

| task | چرا |
|---|---|
| `:app:assembleDebug` | کامپایلِ Kotlin **+ لینکِ منابع با AAPT2** |
| `:app:testDebugUnitTest` | تست‌های واحدِ JVM: `CachePolicy`، `InputValidation`، `DebouncedRequest` |

`assemble` و نه فقط `compile`: چون قدمِ بعدیِ P4 حذفِ منابعِ مرده است و چیزی که
«drawableِ حذف‌شده هنوز جایی ارجاع شده» را می‌گیرد **لینکِ منابع** است، نه کامپایلرِ Kotlin.

عمداً اجرا **نمی‌شود**: `androidTest`/Espresso (امولاتور لازم دارد)، `lint` (هنوز baseline
ندارد)، `assembleRelease` (minify خاموش و امضای release در ریپو نیست).

## یافتهٔ ۱ — اپ هرگز build نمی‌شد

```
e: PushTokenRegistration.kt:32:31 Cannot access 'static fun getInstance(p0: FirebaseApp):
   FirebaseMessaging': it is package-private in 'com/google/firebase/messaging/FirebaseMessaging'.
> Task :app:compileDebugKotlin FAILED
```

`FirebaseMessaging.getInstance(FirebaseApp)` در firebase-messaging **package-private** است، پس
از پکیجِ اپ قابلِ صدا زدن نیست. این تنها خطای کامپایلِ ماژول بود ⇒ **اپ از روزی که آن خط
نوشته شد هرگز build نشده بود.**

رفعش مصالحه نیست، همان فراخوانی است: `firebaseAppOrNull()` در هر دو شاخه فقط اپِ **پیش‌فرض**
را برمی‌گرداند — یا آن را با نامِ `FirebaseApp.DEFAULT_APP_NAME` پیدا می‌کند (خط ۸۶) یا با
overload دو‌آرگومانیِ `FirebaseApp.initializeApp(context, options)` می‌سازد که `[DEFAULT]` را
ایجاد می‌کند (خط ۱۰۲). و `FirebaseMessaging.getInstance()` نمونهٔ همان اپِ پیش‌فرض است.
گاردِ `if (… == null) return` و `try/catch` دست‌نخورده ماندند ⇒ push همچنان best-effort است
و login هرگز بلاک نمی‌شود.

## یافتهٔ ۲ — چرا تست‌ها سبز بودند (و تنها ویرایشِ تستِ این فاز)

`tests/test_e2e_auth_session_flow.py:427` **دقیقاً همان خطِ کامپایل‌نشدنی را assert می‌کرد**:

```python
self.assertIn("FirebaseMessaging.getInstance(firebaseApp).token", push)
```

docstringِ خودِ تست دلیلش را می‌گوید: *«Gradle/device اجرا نمی‌شود»* — یعنی **قراردادِ متنی
جای buildِ واقعی را گرفته بود**. نتیجه: سوئیت سبز، اپ قرمز.

بدونِ تغییرِ این یک assertion هیچ راهی برای سبز کردنِ build نبود؛ زنده نگه‌داشتنِ متنِ قبلی در
کامنت صرفاً برای راضی کردنِ تست، **game کردنِ تست** بود نه رفعِ باگ. assertion حالا فراخوانیِ
درست را قفل می‌کند و **به‌علاوه** گاردِ رفتاریِ واقعی (`if (firebaseAppOrNull(appContext) == null)
return`) را — یعنی روی قراردادی که واقعاً مهم است قوی‌تر از قبل شده. هشت assertionِ دیگرِ همان
تست دست‌نخورده‌اند.

> این دومین source-text guard در این ریپو است که از کارافتاده نگه‌داشته می‌شود؛ اولی دلیلِ
> قرمز ماندنِ `tests/route_audit` برای ماه‌ها بود. **درس: قراردادِ متنی جانشینِ build نمی‌شود.**

## یافتهٔ ۳ — `gradle-wrapper.jar` اصیل نیست (زنجیرهٔ تأمین)

اولین اجرا در ۱۵ ثانیه شکست، پیش از آنکه Gradle شروع شود:

```
Error: At least one Gradle Wrapper Jar failed validation!
✗ Found unknown Gradle Wrapper JAR files:
  ccb27f2587513f0aac87b1587174aeaa167fe67643dea3fae4fce73d4d11594a
```

این فایل یک blobِ باینریِ اجراییِ commit‌شده است — دقیقاً همان برداری که یک PRِ خوش‌برخوردِ
«Update to Gradle x.y» برای حمله به زنجیرهٔ تأمین استفاده می‌کند. پس پیش از هر کاری در برابرِ
jar رسمیِ `gradle/gradle` tag `v8.13.0` کالبدشکافی شد:

- ۳۳ entry در هر دو، مجموعهٔ نام‌ها یکسان، **هیچ class یا بستهٔ ناشناس/اضافه‌ای نیست**
- **۳۲ از ۳۳ → CRC-32 یکسان**: بایت‌های decompressedِ همهٔ کلاس‌ها با Gradle 8.13 رسمی یکی است
- تنها تفاوت `META-INF/MANIFEST.MF` (۱۱۳ در برابر ۶۳ بایت): مالِ ما `Main-Class` دارد و کپیِ
  ریپو ندارد ⇒ jarِ ما flavorِ داخلِ **distribution** است (runnable)، که expected است نه دست‌کاری
- ظرفِ ZIP بازنویسی شده: timestamp رسمی `1980-01-01` (buildِ reproducible) ولی مالِ ما
  `2026-09-10` برای همهٔ entryها، و اندازهٔ فشرده ۴۲۶۱۳ در برابر ۴۳۷۰۵

**جمع‌بندی: کدِ داخلش Gradle 8.13ِ اصیل است، ولی آرشیو یک بار باز و دوباره فشرده شده** —
به‌احتمالِ زیاد همان چرخهٔ zip/unzip که کلِ ریپو از آن آمد. همین بایت‌ها و SHA-256 را عوض کرده.

راه‌حلِ دائمیِ خودِ Gradle (`./gradlew wrapper`) JVM و شبکه به services.gradle.org می‌خواهد که
این‌جا نیست. پس دو تصمیمِ محافظه‌کارانه:

1. **CI هرگز jarِ ریپو را اجرا نمی‌کند** — با `gradle-version: 8.13` اکشن خودش Gradle را
   دانلود و به PATH اضافه می‌کند و stepها `gradle` را صدا می‌زنند نه `./gradlew`.
2. `validate-wrappers: false` (چون نمی‌تواند این jar را تأیید کند) با یک **گیتِ باریک‌تر**
   جایگزین شد: SHA-256 پین شده و هر تغییرش hard fail است، به‌علاوهٔ مطابقتِ نسخهٔ wrapper با
   نسخهٔ CI تا این دو واگرا نشوند.

منطقِ آن Guard محلی در هر سه حالت آزمون شد: سالم ⇒ exit 0؛ یک بایتِ عوض‌شده ⇒ exit 1؛
واگراییِ نسخه (`8.14` در wrapper در برابر `8.13` در CI) ⇒ exit 1.

### 👈 کاری که نگهدارنده باید بکند
در `KharazmiAdmin/` یک بار `./gradlew wrapper` بزنید، سپس در `android.yml`:
`validate-wrappers: false` را بردارید، `gradle-version` را حذف کنید، step «Guard» را پاک کنید و
فراخوانی‌ها را به `./gradlew` برگردانید. همین دستورالعمل در پیامِ خطای خودِ Guard و سرِ workflow هست.

ضمناً `gradlew` با مودِ `100644` کامیت شده بود ⇒ در checkoutِ تازه اجرایی نیست
(`Permission denied` روی لینوکس/مک). شد `100755` با **همان blob hash** (`ef07e01…`) یعنی صفر تغییرِ محتوا.

## یافتهٔ ۴ — لاگ‌ها خواندنی نیستند

لاگِ خامِ job از `results-receiver.actions.githubusercontent.com` سرو می‌شود که از هر محیطی
قابلِ دسترسی نیست (در محیطِ این فاز کاملاً بسته است) و annotations API فقط
«Process completed with exit code 1» را می‌داد. پس stepهای build خروجی را `tee` می‌کنند
(با `pipefail` تا `tee` کدِ خروجِ Gradle را نپوشاند) و یک step با `if: failure()` خلاصهٔ
شکست را به‌صورتِ یک **annotationِ چندخطی** منتشر می‌کند که از `api.github.com` خواندنی است.
خطای FCM بالا دقیقاً از همین راه خوانده شد. فرارِ `%`/newline محلی با یک لاگِ ساختگی آزمون شد.

---

# بخشِ دوم — P4a: پاک‌سازیِ منابعِ مردهٔ اپ

## ابزار: `KharazmiAdmin/find_dead_resources.py`

تستِ `test_android_resources_static.py` جهتِ «ارجاع‌شده ⇒ تعریف‌شده» را می‌سنجد (منبعِ گم‌شده).
این ابزار جهتِ **عکس** را می‌سنجد: «تعریف‌شده ⇒ ارجاع‌شده»، یعنی وزنِ مرده. مکمل‌اند.

شکل‌های ارجاعی که می‌شناسد (و یک اسکنِ ساده از دست می‌دهد):
`@type/name`، `@+id/x`، `?attr/x`، namespaceهای `android:`/`tools:`/`app:`،
`parent="StyleName"` (**ارجاعِ بدونِ `@`**)، styleهای نقطه‌دار در Kotlin
(`R.style.Theme_Kharazmi` در برابر `@style/Theme.Kharazmi`)، `string-array` در برابر `R.array`،
ارثِ **ضمنیِ** styleهای نقطه‌دار (بدونِ `parent` صریح ⇒ والد = prefix)، و همهٔ پوشه‌های
`values*` شاملِ `values-night` و `values-v31`.

نوعِ `id` **هرگز** پیشنهادِ حذف نمی‌گیرد: تنها سایتِ `getIdentifier` در کلِ اپ
(`ShareConfigActivity.kt:38`) نامِ `et1…et15` را پویا می‌سازد و
`getIdentifier(name, "id", packageName)` صدا می‌کند ⇒ تحلیلِ نام‌محور برای `id` بی‌معناست.
برای بقیهٔ نوع‌ها همان سایت گزارش می‌شود تا اگر روزی `getIdentifier` برای نوعِ دیگری اضافه شد،
ابزار با صدای بلند هشدار بدهد.

## ⚠️ درسِ مهم: خودآزمون، یک فاجعه را گرفت

نسخهٔ اولِ ابزار ارجاع‌های XML را با الگوی `@type:name` می‌گشت — ولی سینتکسِ اندروید
**`@type/name` با اسلش** است. یعنی عملاً هیچ ارجاعِ XML ثبت نمی‌شد و ابزار **۷۷۱** منبع را
«مرده» اعلام می‌کرد. پیش از commit، خودآزمونِ «منابعی که می‌دانم استفاده می‌شوند باید در
فهرستِ مرده‌ها *نباشند*» اجرا شد و دو مثبتِ کاذب لو داد: `app_name` و `ic_launcher` — که هر دو
در `AndroidManifest.xml` ارجاع شده‌اند. پس از اصلاحِ الگو، ارجاع‌های متمایز از ۲۳۳۵ به ۲۹۰۱
رسید و کاندیداها از ۷۷۱ به **۳۱۰** افتاد.

> بدونِ آن خودآزمون، **۴۶۱ حذفِ اشتباه** انجام می‌شد که اپ را می‌شکست.
> قاعده: تحلیل‌گری که «حذف» پیشنهاد می‌دهد، اول باید روی نمونه‌هایِ **معلوم‌الزنده** آزمون شود.

## راستی‌آزماییِ مستقل، پیش از حذف

هر ۳۱۰ نام در **کلِ ریپو** (۸۴۵ فایل) grep شد؛ ۲۹ مورد جایی بیرون از محلِ تعریفشان پیدا شدند
و دستی بررسی شدند:

- **نامِ فیلدِ JSON، نه منبع**: `class_title`/`student_mobile`/`version`/`students_total`/
  `teachers_active` و مانندشان — در Kotlin به‌عنوانِ propertyهای data class (Gson با
  reflection پرشان می‌کند) و در تست‌های سرور به‌عنوانِ کلیدِ پاسخِ API
  (`row["class_title"]`، `{"version": 1}`). تقاطعِ صریح با ۱۳۶ فایلِ تست/اسکریپتِ Python
  فقط همین ۳ نام را داد و هر سه کلیدِ JSON بودند.
- **`@+id/nav_classes` در برابر `@string/nav_classes`**: آن دو در `drawer_menu.xml` فقط
  `@+id/` هستند ⇒ رشته‌های هم‌نام واقعاً مرده‌اند.
- **`bg_chat_sent`**: تنها در یک **کامنت** در `MessageActivity.kt:382` آمده
  («matching bg_chat_sent») ⇒ مرده. (آن کامنت حالا به منبعی اشاره می‌کند که نیست؛ عمداً
  دست‌نخورده ماند تا فایلِ Kotlin تغییر نکند.)
- **برخوردِ نامِ `gold_ripple`**: یک `drawable/gold_ripple.xml` (مرده) و یک
  `<color name="gold_ripple">` (زنده — `GoldButton.kt:58`، `rippleColor` در تم‌ها، `ds_ripple`).
  فقط فایلِ drawable حذف شد و بررسی شد که **صفر** ارجاعِ `@drawable/gold_ripple` باقی نمانده.
- **`Theme.Kharazmi.Gold`**: manifest به `…Gold.Launch` ارجاع می‌کند و زنجیرهٔ تم
  `.Launch → .Launch.Base → Theme.GajAdmin` است ⇒ خودِ `Theme.Kharazmi.Gold` در زنجیره نیست و مرده است.
- **ذکر در `checkpoints/` و `docs/`**: متنِ تاریخی، نه ارجاع.

## نتیجهٔ حذف

سه دور تا **نقطهٔ ثابت** (هر دور منابعی را مرده می‌کند که تنها ارجاع‌کننده‌شان در دورِ قبل حذف شده):

| دور | فایل | entry در values | نمونهٔ زنجیره |
|---|---|---|---|
| ۱ | ۲۸ | ۳۱۳ | — |
| ۲ | ۳ | ۶ | `Headline5` ← `layout/item_dashboard_card.xml` (حذف‌شده در دورِ ۱) |
| ۳ | ۰ | ۲ | `ShapeAppearance.Kharazmi.BottomSheet` ← `GajBottomSheetStyle` ← `Theme.Kharazmi.Gold` |
| **جمع** | **۳۱** | **۳۲۱** | تعریف‌ها: **۲۱۶۱ → ۱۸۴۳** |

ترکیبِ ۳۱ فایلِ حذف‌شده: ۱۵ drawable، ۷ anim، ۴ layout، ۳ drawable (دورِ ۲)، ۲ color-state-list.
ترکیبِ entryها: ۲۲۱ string، ۶۳ color، ۲۷ style، ۲ dimen.

هر ۳۱۸ نامِ حذف‌شده در درختِ **فعلی** دوباره grep شد (با lookaheadِ اصلاح‌شده تا
`Theme.Kharazmi.Gold` با `…Gold.Launch` اشتباه نشود): ۳۱۲ برخورد = تصادفِ متنیِ بی‌ضرر،
۳ برخورد = همان `gold_ripple` که بالا توضیح داده شد، و **صفر ارجاعِ واقعیِ منبع به منبعِ حذف‌شده**.
تحلیل‌گر در درختِ فعلی **۰ منبعِ مرده** گزارش می‌کند و همهٔ XMLها سالم parse می‌شوند.

## گیت‌ها

- `:app:assembleDebug` در CI ⇒ لینکِ منابع با AAPT2؛ اگر منبعِ هنوز‌ارجاع‌شده‌ای حذف شده باشد،
  build با نامِ دقیقِ همان منبع می‌شکند. این **حکمِ نهایی** است.
- سوئیتِ Python ⇒ هر `R.<type>.<name>` استفاده‌شده در Kotlin باید منبع داشته باشد
  (`test_android_resources_static.py`)، پس حذفِ بیش‌از‌حد در سمتِ Kotlin هم گرفته می‌شود.
- هیچ فایلِ Kotlin یا Pythonِ اپ/سرور تغییر نکرد؛ diff فقط زیر `res/` است.
