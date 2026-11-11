# فاز P4b — پاک‌سازیِ کدِ مردهٔ Kotlin (نماد‌به‌نماد) و آبشارِ منابعِ یتیم

تاریخ: ۲۰۲۶-۱۱-۱۱ · نقطهٔ شروع: `03319b9` (= `main` پس از PR #11)
نوع: **پاک‌سازیِ رفتارمحافظ** — صفر تغییرِ رفتاری، فقط حذفِ کدی که هیچ ارجاعی ندارد.

---

## ۱) چرا این فاز سخت‌تر از P4a بود

در P4a (منابع) یک اوراکلِ بیرونی داشتیم: AAPT2. اگر منبعِ زنده‌ای را حذف می‌کردیم، CI با
خطایِ صریح می‌شکست. برای Kotlin هیچ اوراکلِ محلی نداریم: محیطِ کاریِ ما نه JVM دارد، نه
Gradle، نه `kotlinc`، و نه مسیری به Maven Central یا `dl.google.com`. **تنها داور، کامپایلرِ
CI است.** پس هر حذف باید *پیش از* push با شمارشِ ارجاع اثبات شود، نه با حدس.

معیارِ سادهٔ «تعریفی که از فایلِ دیگری ارجاع نشده» را پیش‌تر آزمودیم و **نامعتبر** بود:
۲۰۴ مورد داد که تقریباً همه مثبتِ کاذب بودند، چون

* اینترفیس‌های Retrofit درونِ همان فایلِ خودشان با `retrofit.create(XApi::class.java)` مصرف می‌شوند؛
* data classهای Gson فقط به‌شکلِ نوعِ بازگشتی در همان اینترفیس ظاهر می‌شوند؛
* کلاس‌های تست را JUnit با reflection می‌سازد، پس شمارشِ ارجاع همیشه «مرده» می‌گویدشان.

پس ابزار باید **سطحِ نماد** باشد: همهٔ ارجاع‌ها در کلِ پیکره، منهای سایت‌های تعریف.

## ۲) ابزارِ جدید: `KharazmiAdmin/find_dead_kotlin.py`

پیکرهٔ ارجاع: هر `.kt`/`.java` در `main` + `test` + `androidTest`، هر `res/**.xml`، و
`AndroidManifest.xml` — به هر دو شکلِ نامِ ساده و FQCN (`com.example.kharazmiadmin.X`).

قاعده‌هایی که از اشتباه‌های واقعیِ همین فاز بیرون آمده‌اند:

| قاعده | چرا |
|---|---|
| فقط تعریف‌های **ستونِ صفر** (`class`/`object`/`interface`/`fun`/`val`/`var`) | اعضای کلاس عمداً بیرونِ دامنه‌اند: Gson با reflection پرشان می‌کند و ۲۸۶ `override fun` با قراردادِ فریم‌ورک صدا زده می‌شوند، نه با نام. |
| `test`/`androidTest` از **تعریف‌ها** حذف، ولی در **ارجاع‌ها** باقی | نمادی که فقط تست مصرفش می‌کند زنده است؛ ولی کلاسِ تست خودش هرگز «زنده» شمرده نمی‌شود. |
| بازهٔ تعریف با شمردنِ **هم پرانتز و هم آکولاد** | `data class X(...)` چندخطی با فقط `{}` یک‌خطی گزارش می‌شد و بی‌اهمیت به نظر می‌رسید. |
| `_strip_comments` باید **تعدادِ خطوط را دقیقاً حفظ کند** | بازه از `text[:m.start()].count("\n")` می‌آید؛ یک خطِ جابه‌جا = حذفِ خطِ اشتباه. (باگِ واقعی: الگوی `^\s*//.*$` که `\s` newline را هم می‌خورد ⇒ به `[ \t]*//[^\n]*` اصلاح شد و با assert ثابت شد ۱۰۵۵ = ۱۰۵۵.) |
| XML **بدونِ** strip کامنت | ارجاعِ کامنت‌شده در XML هنوز باید شمرده شود تا حذفِ ناامن پیشنهاد نشود. |
| نام‌های `android:name` در Manifest (۷۳ مورد) هرگز مرده نیستند | Activity/Service/Receiver را فریم‌ورک با نام می‌سازد. |
| سایت‌های `Class.forName`/`getDeclaredMethod`/`getMethod`/`getIdentifier` چاپ می‌شوند | تحلیلِ نام‌محور در مجاورتِ این‌ها ناامن است؛ در این اپ **۱ مورد** است (`ShareConfigActivity.kt`، روی `id` نه نامِ کلاس). |

خروجیِ پایه: ۸۷ فایلِ تعریف، ۱۹۳ XML، **۴۱۷ نمادِ سطحِ بالا** ⇒ **۱۹ نمادِ مرده / ۴۱۱ خط**.

## ۳) چه حذف شد (۱۴ نماد، ۳۸۰ خط)

| فایل | تغییر | نمادها |
|---|---|---|
| `GoldAnimations.kt` | **حذفِ کاملِ فایل** (−۳۱۸) | `object GoldAnimations` با ۱۳ تابع، همه بی‌ارجاع |
| `DashboardResponse.kt` | **حذفِ کاملِ فایل** (−۲۲) | `DashboardResponse`، سپس تراگذرا `TransactionInfo` و `CourseInfo` |
| `AppModels.kt` | −۱۶ خط (۱۰۵۵ → ۱۰۳۹) | `SearchItem`، `ClassItem`، `ClassItemFull`، `SubmitResponse`، `AttendanceLogRequest`، `AttendanceRecord`، `AttendanceSubmitItem` (تراگذرا)، `AttendanceSubmitData`، `AttResponse`، `BulkSmsRequest` |
| `res/drawable/bg_otp_box{,_filled,_error}.xml` | −۲۴ خط | آبشارِ منابع: این سه **فقط** از `GoldAnimations.kt` ارجاع می‌شدند |

حذف در ۳ دور تا نقطهٔ ثابت: دورِ ۱ ⇒ ۱۱ نماد، دورِ ۲ ⇒ ۳ نمادِ تراگذرا
(`AttendanceSubmitItem`, `CourseInfo`, `TransactionInfo`)، دورِ ۳ ⇒ خالی.
شمارِ نمادهای سطحِ بالا ۴۱۷ → **۴۰۳**، فایل‌های Kotlin/Java ۸۷ → **۸۵**، XML ۱۹۳ → **۱۹۰**.

خانوادهٔ `Attendance*` مرده بود چون خانوادهٔ زندهٔ `Session*` جایش را گرفته است:
`AttendanceActivity.kt` در خط‌های ۳۶، ۴۴، ۲۶۴، ۶۳۰، ۶۳۵، ۶۴۷ از
`SessionSubmitData`/`SessionItem`/`SessionResponse` استفاده می‌کند و اینترفیسِ زندهٔ
`AttendanceSubmitApi.submitSession(@Body data: SessionSubmitData)` هیچ‌کدام از انواعِ حذف‌شده را نمی‌خواهد.

## ۴) چه حذف **نشد** و چرا (مجموعهٔ DEFER — ۸ نماد، ۱۰۴ خط)

این‌ها از نظرِ شمارشِ ارجاع مرده‌اند، ولی یک **قراردادِ بیرون از کد** آن‌ها را نگه داشته است.
حذفشان دروازه‌های مستندسازی/CI را می‌شکست، پس با دلیل ثبت می‌شوند نه با حدس:

* `RemittancePrintApi` (۷ خط، `InvoiceActivity.kt`) — دو endpoint واقعیِ Retrofit
  (`POST /finance/receipt/print`، `POST /finance/receipt/pdf`) که در
  `docs/app-map/android-api-calls.csv:75-76` فهرست شده‌اند و `scripts/validate_app_map.py`
  آن‌ها را با سورس تطبیق می‌دهد. حذف = شکستنِ آن گیت.
* `MainActivityRefactored` + ۴ تابعِ Compose آن (`AdminDashboardScreen`, `QuickActionsGrid`,
  `SkeletonDashboardLoading`, `EmptyDashboardState`) — در `docs/app-map/navigation.md:57`،
  `phase-c-screens.md:6` و `screens/MainActivityRefactored.md` مستند شده‌اند. این یک خوشهٔ
  مردهٔ بسته است (`MainUseCase` صفر ارجاع؛ `MainViewModel` فقط از همین stub؛ `MainRepository`
  فقط از `MainUseCase`) و تصمیم دربارهٔ مهاجرتِ Compose یک تصمیمِ محصولی است، نه پاک‌سازی.
* `InvoiceSubmitData` و `StudentRegisterData` — در `docs/app-map/mismatches.md:106-107` به‌عنوانِ
  عدم‌تطابقِ شناخته‌شدهٔ payload ثبت شده‌اند؛ حذفشان سندِ زنده را بی‌مرجع می‌کرد.

## ۵) اثبات‌ها (پیش از push، چون بعد از push داور CI است)

1. **شمارشِ ارجاع:** هر ۱۴ نام با `grep -rnw` در `app/src` فقط در سایتِ تعریفِ خودش دیده می‌شد.
2. **صفر ارجاعِ باقی‌مانده پس از حذف:** پویشِ کلِ مخزن برای هر ۱۷ نام (۱۴ نماد + ۳ drawable)
   ⇒ صفر مورد در `.kt`/`.java`/`.xml`.
3. **تلهٔ هم‌نامیِ دوزبانه:** `AttendanceSubmitData`، `AttendanceLogRequest` و `BulkSmsRequest`
   در `Kharazmi_Server/schemas.py` هم وجود دارند (کلاسِ پایتونیکِ سمتِ سرور) و ۶ فایلِ تستِ
   پایتون به *همان* نسخهٔ سرور ارجاع می‌دهند. نسخهٔ Kotlin جدا و بی‌مصرف بود.
   همهٔ برخوردهای باقی‌مانده سمتِ سرور یا در `docs/` هستند، نه اپ.
4. **تستِ محافظِ متنی دست‌نخورده:** `test_android_resources_static.py` (974 خط،
   `keep_verbatim`) هیچ‌کدام از نام‌های حذف‌شده را پین نکرده؛ تنها نزدیک‌ترین مورد
   `:915` است که `data class ClassListItem(` و `data class TeacherClassItem(` را می‌خواهد —
   هر دو سرجایشان‌اند (`AppModels.kt` و `TeacherDashboardActivity.kt`).
   `git diff` روی `Kharazmi_Server/tests/` **خالی** است.
5. **اوراکلِ app-map:** `scripts/validate_app_map.py` پیش و پس از حذف اجرا شد و هر **۱۸ کلیدِ**
   خروجی **یکسان** بودند (`retrofit_source_map_missing=0`, `retrofit_source_map_exact`,
   `android_only_routes=0`, `server_map_exact=true`, `server_runtime_count=221`).
   دو لیستِ غیرخالی (`retrofit_source_map_extra=8`, `server_only_routes=64`) در HEAD بکر هم
   دقیقاً همین بودند ⇒ محصولِ این تغییر نیستند. مقایسه با `git worktree add --detach` روی HEAD انجام شد.
6. **منابع:** آنالیزرِ P4a پیش از حذفِ Kotlin **۰ مرده** می‌داد؛ پس از آن ۳ ⇒ علت‌یابی شد که
   تنها ارجاع‌کننده‌شان `GoldAnimations.kt:175,192,205,207` بوده؛ پس از حذفِ آن سه، دوباره **۰**.
   رنگ‌هایی که آن drawableها مصرف می‌کردند زنده ماندند (`gold_bg_elevated_2` ۷ ارجاع،
   `gold_primary` ۷۶، `status_danger` ۲۶).

## ۶) دو حادثهٔ ابزارِ یک‌بارمصرف (و چه سخت‌گیری‌ای جایش نشست)

هر دو در اسکریپتِ حذفِ `/tmp` رخ داد، نه در ابزارِ commit‌شده؛ هر دو با `git checkout` به حالتِ
سالم برگشتند و پیش از ادامه diff-stat گرفته شد. ثبت می‌شوند چون درسِ ابزارسازی‌اند:

* **آف‌بای‌وان:** بازه‌های آنالیزر **۰-پایه** هستند ولی حذف‌کننده `enumerate(lines, start=1)`
  داشت ⇒ خطِ *بالای* هر تعریف حذف می‌شد، تعریف سرِ جایش می‌ماند، حلقهٔ «تا نقطهٔ ثابت»
  ۵ دور تکرار می‌کرد و ۶۰ خطِ زندهٔ `AppModels.kt` را خورد.
  اصلاح: `enumerate` ۰-پایه + **دو assert** در هر حذف — یکی `name in raw_lines[start]`
  (بازه واقعاً روی تعریف است) و یکی پویشِ پس از نوشتن که نام دیگر در فایل نیست.
  افزون بر آن: اگر دوری هیچ تغییری ندهد، اسکریپت `ABORT` می‌کند تا هرگز بی‌صدا حلقه نزند.
  با همین assert بود که باگِ بعدی لو رفت.
* **جابه‌جاییِ خطوط از `_strip_comments`:** assertِ بالا روی `AttendanceLogRequest` شکست
  (خطِ ۳۴۰ `BulkEnrollmentResponse` بود) ⇒ ریشه، بلعیدنِ newline توسط `^\s*//` بود. در خودِ
  ابزارِ commit‌شده اصلاح شد (بندِ ۲).
* **امضای اشتباهِ API:** `find_dead_resources.collect_references()` یک **تاپلِ** `(refs, dynamic)`
  برمی‌گرداند؛ پاس‌دادنِ تاپل به `is_referenced` ⇒ عضویت همیشه False ⇒ **همهٔ ۱۸۴۳ منبع مرده
  دیده شدند** و حذف‌کننده کلِ `res/` را پاک کرد. با `git checkout -- .../res/` بازگشت
  (۱۹۲ فایل سالم شد) و این بار برای فقط ۳ فایل، حذفِ دستیِ کمینه انجام شد، نه حذف‌کنندهٔ عمومی.

درسِ کلی برای ادامهٔ P4: **هرگز** یک حذف‌کنندهٔ عمومی را بدونِ assertِ «نام واقعاً روی آن خط است»
و بدونِ مقایسهٔ diff-stat قبل/بعد اجرا نکن؛ و API یک ماژول را پیش از صدا زدن بخوان، نه حدس.

## ۷) دروازهٔ کامل (همه مطابقِ baseline)

| بررسی | انتظار | نتیجه |
|---|---|---|
| `pytest Kharazmi_Server/tests` | 1279 passed | **1279 passed** (۱۲۶٫۳ ثانیه) |
| `pytest tests/route_audit` (پروسهٔ جدا) | 249 passed | **249 passed** (۲۴٫۴ ثانیه) |
| md5 دیتابیسِ واقعیِ آموزشگاه | `f048f8d118b33c4eaa944490594121d7` | **مطابق** |
| `ruff check .` | 251 | **251** |
| `ruff --select F821` | 1 | **1** (`routers/exams.py:379`) |
| `mypy Kharazmi_Server` | 726 خطا / ۴۴ فایل | **726 / 44** |
| `validate_app_map.py` | ۱۸ کلید یکسان | **۰ تفاوت** |
| `find_dead_kotlin.py` | فقط ۸ DEFER | **۸ نماد، ۱۰۴ خط** |
| `find_dead_resources.py` | ۰ | **۰** |

`assembleDebug` و `testDebugUnitTest` روی CI قاضیِ نهاییِ Kotlin‌اند.

## ۸) گامِ بعد

1. **P4c — lint/typing اندروید:** گرفتنِ baseline از `lint`/خطاهای کامپایلر و گیتِ
   «بدتر نشود» (نه صفرکردنِ یک‌باره)، همان الگویی که برای ruff/mypy در P5 لازم است.
2. **P4d — خدا‌Activityها به لایهٔ service/repository:** با نگه‌داشتنِ یک تابعِ نازکِ
   delegate در Activity تا متنِ محافظت‌شدهٔ تست‌ها (`keep_verbatim`) سرجایش بماند.
3. گسترشِ الگوی تستِ JVM روی منطقِ خالص (`CachePolicy.kt`, `InputValidation.kt`,
   `DebouncedRequest.kt`, `JalaliUtils.kt`, `EnrollmentLabels.kt`, …).
4. بدهیِ باز از P4-prep: اجرای `./gradlew wrapper` در `KharazmiAdmin/` تا بتوان
   `validate-wrappers: false` + `gradle-version` + Guard step را از workflow برداشت.
