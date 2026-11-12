# فاز P4d (برش ۱) — بیرون کشیدنِ قراردادهای Retrofit از god-fileهای اندروید

**شاخه:** `arena/37e7066f-kharazminew1` (از `05e9ed9` = ادغامِ PR #14)
**دامنهٔ تغییر:** فقط Kotlin (۷۳ فایل) + یک یادداشتِ تاریخ‌دار در `docs/app-map/00-overview.md` + همین checkpoint. هیچ تستی، هیچ فایلی در `Kharazmi_Server/`، هیچ منبعی در `res/` و هیچ workflow ای تغییر نکرد.

---

## ۱) چرا این برش، و چرا اولِ کار

هدفِ P4d شکستنِ god-Activityهاست. پیش از دست بردن به منطقِ ۶۱ تابعیِ یک Activity، این برش **کم‌خطرترین و پُرارزش‌ترین** قدم را برمی‌دارد: جدا کردنِ «قراردادِ داده» (اینترفیسِ Retrofit) از «منطقِ صفحه».

دلیلِ انتخابِ این برش به‌عنوانِ نخستین گام:

1. **ریپو از قبل این قرارداد را دارد** و فقط ناقص اجرا شده بود: `LiveApi.kt`، `TodaySummaryApi.kt`، `ApiInterfaces.kt`، `ReportExporter.kt` فایل‌های اختصاصیِ API هستند، ولی از **۶۰ اینترفیسِ `*Api`** در اپ، **۴۴ تا داخلِ ۳۷ فایلِ `*Activity.kt`** اعلام شده بودند. پس این کار «اختراعِ معماریِ تازه» نیست، «تکمیلِ معماریِ موجود» است.
2. **FQCN عوض نمی‌شود.** اینترفیس‌ها از قبل top-level و هم‌بسته (same package `com.example.kharazmiadmin`) بودند؛ جابه‌جایی‌شان به فایلِ هم‌بستهٔ دیگر یعنی `com.example.kharazmiadmin.ProfileApi` قبل و بعد **دقیقاً یک نامِ بایت‌کدی** است. نتیجه: هیچ call site ای، هیچ `AndroidManifest.xml` ای، هیچ قاعدهٔ ProGuard/R8 ای و هیچ import ای در بقیهٔ اپ تغییر نمی‌کند. این همان چیزی است که ریسکِ «بدونِ JVM/Gradle/kotlinc محلی» را قابلِ قبول می‌کند.
3. **اوراکلِ مستندات مقاومت می‌کند.** `scripts/validate_app_map.py::compare_retrofit_map()` فقط `Counter((method, path))` را مقایسه می‌کند، نه محلِ اعلام را؛ پس جابه‌جایی برای آن نامرئی است (و در عمل ثابت شد: خروجی‌اش بایت‌به‌بایت یکسان ماند).

## ۲) آنچه انجام شد

- **۳۸ اینترفیس** از ۳۵ فایلِ `*Activity.kt` به ۳۸ فایلِ اختصاصیِ `<Name>Api.kt` منتقل شد (نامِ فایل == نامِ اینترفیس؛ اثبات شد: ۰ ناهمخوانی).
- هر فایلِ جدید: `package` + import‌های **دقیقاً لازم** + یک کامنتِ فارسیِ منشأ + خودِ بلوک، **کلمه‌به‌کلمه** بدونِ تغییر.
- **۴۶۳ خط** از فایل‌های Activity کم شد؛ مجموعِ آن ۳۵ فایل از `15458` به `14995` رسید.
- بزرگ‌ترین اثر: `StudentProfileActivity.kt` از **۱۲۶۴ → ۱۱۸۶** (−۷۸، چون `ProfileApi` با ۱۹ endpoint و ۷۵ خط بیرون رفت). بقیهٔ چشم‌گیرها: `ReportActivity.kt` ۶۶۶→۶۳۵، `ClassDetailActivity.kt` ۹۴۸→۹۲۶، `MessageActivity.kt` ۳۹۶→۳۷۷، `HomeworkActivity.kt` ۴۳۷→۴۲۱.
- شمارِ فایل‌های `.kt` اپ: **۸۱ → ۱۲۳**؛ مجموعِ خطوط **۲۳۹۳۳ → ۲۴۲۸۴** (رشدِ خالص فقط سربارِ `package`/import/کامنتِ ۳۸ فایلِ جدید است، نه منطقِ تازه).
- بزرگ‌ترین فایل‌های باقی‌مانده: `InvoiceActivity.kt` ۱۲۳۶، `StudentProfileActivity.kt` ۱۱۸۶، `AppModels.kt` ۱۰۳۹، `AttendanceActivity.kt` ۹۹۸، `ClassDetailActivity.kt` ۹۲۶. **یعنی بدنهٔ اصلیِ god-fileها هنوز سرِ جایش است** و به برش‌های بعدی نیاز دارد (بخش ۷).

## ۳) شش اینترفیسی که عمداً جابه‌جا **نشدند**

تست‌ها متنِ سورسِ Kotlin را به **فایلِ میزبان** پین کرده‌اند. معیارِ «پینِ سخت» را دقیق تعریف کردم: بلوکی پین است که **حذفش از فایل باعث شود یک لیترال/regexِ asserted دیگر در آن فایل پیدا نشود**. (صرفِ «لیترال داخلِ بلوک هست» کافی نیست — با آن معیارِ سست ۱۲ اینترفیس پین به‌نظر می‌رسیدند در حالی که ۶ تای‌شان لیترال را جایِ دیگریِ همان فایل هم دارند.) `assertNotIn`/`assertNotRegex` هرگز پین نیستند، چون بیرون بردنِ متن فقط به آن‌ها کمک می‌کند.

| اینترفیس | فایلِ میزبان | پین‌کننده |
|---|---|---|
| `DeletedClassesApi` | `MainActivity.kt` | `test_android_resources_static.py:837` → `_kotlin_function_body(self.main, "interface DeletedClassesApi")` |
| `AuthApi` | `LoginActivity.kt` | `test_e2e_auth_session_flow.py:423-424` → `assertRegex(login_api, r'@POST\("auth/logout"\)')` و `r'@Query\("device_token"\)'` |
| `ClassDetailApi` | `ClassDetailActivity.kt` | `test_group4_display_fixes.py:17c` → `assertIn('@GET("classes/{id}/students_full")', src)` |
| `ClassSetupNetworkApi` | `ClassSetupActivity.kt` | `test_group5_behavior.py:23b` → `@POST("enrollments/add")`، `@POST("enrollments/add_bulk")`، `BulkEnrollmentResponse` |
| `TeacherPanelApi` | `TeacherDashboardActivity.kt` | `test_group6_behavior.py` → `teacher_id` |
| `AdminSessionHistoryApi` | `AdminSessionHistoryActivity.kt` | `test_group7_reports_admin.py` → `reason` |

`AdminSessionHistoryApi` و `TeacherPanelApi` را لیترال‌های کوتاهِ عمومی (`reason`، `teacher_id`) پین کرده‌اند؛ یعنی پینِ **محافظه‌کارانه**. ارزشِ جابه‌جایی‌شان از ریسکِ شکستنِ تست کمتر بود، پس ماندند.

## ۴) باگی که همین معیار لو داد (و درسِ آن)

نخستین اجرا **۴۳** اینترفیس را جابه‌جا کرد و سه تست شکست:

```
FAILED test_e2e_auth_session_flow.py::…::test_9_android_client_registers_device_token_and_logs_out_device
FAILED test_group4_display_fixes.py::…::test_17c_the_admin_class_detail_uses_the_real_students_endpoint
FAILED test_group5_behavior.py::…::test_23b_single_endpoint_remains_and_bulk_endpoint_is_declared
```

**علت:** نقشهٔ پینِ بازسازیِ قبلی فقط `_kotlin_function_body`/`_kotlin_declaration` را در **یک** فایلِ تست (`test_android_resources_static.py`) می‌دید. ولی سه فایلِ تستِ دیگر با شکل‌های متفاوتی همان کار را می‌کنند: `kt("ClassDetailActivity.kt")` + `assertIn`، و `texts.get("LoginActivity.kt", "")` + `assertRegex`.

**درسی که ثبت می‌شود:** قیدِ `keep_verbatim` فقط به helperهای یک فایل محدود نیست. پیش از هر جابه‌جاییِ متنِ Kotlin، باید **کلِ کورپسِ تست** با AST پویش شود (`assertIn`/`assertNotIn`/`assertRegex`/`assertNotRegex`/`assertEqual`/`x in y` + helperهای فایل‌خوان)، و معیارِ پین هم «شبیه‌سازیِ خودِ تست» باشد نه «حضورِ لیترال در بلوک». ابزارِ این کار: `/tmp/pinmap2.py` (۱۲ فایلِ تستِ پین‌کننده، ۳۶ فایلِ `.kt` مرجع، ۶ پینِ سخت از ۴۴ نامزد).

## ۵) راستی‌آزمایی — چون محلی هیچ کامپایلری نیست

هر ۶ بررسیِ ساختاریِ `/tmp/verify_p4d.py` سبز (exit=0):

1. **دامنه:** ۳۵ `.kt` ویرایش‌شده، ۳۸ `.kt` جدید، **۰** تغییرِ غیرِ Kotlin در کد (فقط docs/checkpoint).
2. **تمامیتِ خطوط:** از ۴۶۳ خطِ حذف‌شده، **۰** خط گم شد — یعنی هر خطِ برداشته‌شده کلمه‌به‌کلمه در یکی از فایل‌های جدید بازتولید شده.
3. **حلِ نوع (اوراکلِ تفاضلی):** برای هر ۳۵ فایلِ ویرایش‌شده، مجموعهٔ «توکن‌های با حرفِ بزرگِ حل‌نشده» در برابرِ HEAD مقایسه شد: **۰** فایل توکنِ تازه‌ای اضافه کرد. برای هر ۳۸ فایلِ جدید: **۰** توکنِ حل‌نشده. scope هر فایل = importهای خودش (با **بازکردنِ star import**) ∪ ۴۰۳ نامِ top-levelِ هم‌بسته (از `find_dead_kotlin.py`) ∪ نام‌های اعلام‌شده در همان فایل ∪ builtinهای Kotlin ∪ پارامترهای جنریک.
4. **ساختار:** هر ۳۸ فایلِ جدید دقیقاً `package` + یک اینترفیسِ top-level دارد.
5. **نام‌های top-levelِ کلِ ریپو:** `399 → 399`؛ **gone=[]، born=[]، duplicated=[]**. این مهم‌ترین قیدِ کامپایل است: نامِ تکراریِ top-level در Kotlin یعنی `Duplicate JVM class name`، و نامِ گم‌شده یعنی call siteِ شکسته.
6. **پین‌های سخت:** هر ۶ لیترالِ پین‌کننده هنوز در فایلِ میزبانشان هستند.

دروازه‌های ریپو (همه مطابقِ بیس‌لاین):

| دروازه | نتیجه |
|---|---|
| `pytest Kharazmi_Server/tests` | **1279 passed** |
| `pytest tests/route_audit` (پروسهٔ جدا، DB جدا) | **249 passed** |
| `scripts/validate_app_map.py` | خروجیِ JSON **بایت‌به‌بایت یکسان با HEAD** (`170/162/extra 8/missing 0/android_only 0`) |
| `find_dead_kotlin.py` | همان **۸ نمادِ DEFER** / ۱۰۴ خط (`RemittancePrintApi` حالا در `RemittancePrintApi.kt:11-17` گزارش می‌شود) |
| `find_dead_resources.py` | **۰ منبعِ مرده** / ۱۸۴۲ تعریف |
| `gaj_db.db` md5 | `f048f8d118b33c4eaa944490594121d7` (بدونِ تغییر) |
| `test_android_resources_static.py` | **دست‌نخورده** (`git diff --stat` = ۰ خط) |

**اثباتِ نهاییِ کامپایل فقط CI است** (`:app:assembleDebug` + `:app:testDebugUnitTest` + `:app:lintDebug`)، چون این sandbox نه JVM دارد نه Gradle و نه دسترسی به Maven Central/`dl.google.com`.

## ۶) سه باگِ ابزار و یک باگِ واقعیِ ریپو که سرِ راه پیدا شدند

**الف — باگِ واقعیِ خودِ استخراج‌گر (اگر می‌ماند، CI قرمز می‌شد):** سه فایلِ مبدأ importِ **کامنت‌دار** دارند، مثلاً
`import android.widget.TextView // FIX: Bug 22 - resolve the grade form header type.`
چون خط با نقطه تمام می‌شود، `rsplit(".", 1)[-1]` رشتهٔ **تهی** می‌داد و `re.search(re.escape(""))` همه‌جا match می‌کند ⇒ آن import بی‌قیدوشرط به فایلِ جدید منتقل می‌شد (`GradeApi.kt` یک `TextView` بی‌ربط گرفته بود). جهتش امن بود (هیچ importِ لازم نمی‌افتاد) ولی خروجی کثیف می‌شد. اصلاح: بریدنِ کامنتِ دنباله‌دار + `assert` روی معتبر بودنِ نامِ ساده.

**ب — star import.** ۵ فایلِ مبدأ `import retrofit2.http.*` دارند و چون `*` داخلِ بلوکِ اینترفیس نمی‌آید، نخستین نسخه آن را منتقل نکرد ⇒ `CalendarApi`/`CrmNetworkApi`/`ExamNetworkApi`/`HomeworkNetworkApi`/`MessageApi` **کامپایل نمی‌شدند**. اصلاح: جدولِ «چه بستهٔ star چه نام‌هایی می‌دهد» و انتقالِ star **فقط** وقتی واقعاً لازم باشد.

**ج — سه باگ در خودِ راستی‌آزماها** (یادآوریِ درسِ قدیمی: «ابزارِ راستی‌آزمایی می‌تواند خودِ مصنوعِ باگ‌دار باشد»):
- `git diff` فایل‌های **untracked** را نشان نمی‌دهد ⇒ نخستین گزارش «۴۳۸ خط گم شد» کاملاً کاذب بود.
- اوراکلِ تفاضلی star import را به `"*"` تجزیه می‌کرد و باز نمی‌کرد ⇒ ۵ فایلِ سالم را «حل‌نشده» گزارش داد.
- آشکارسازِ «importِ بلااستفاده» extension functionها را نمی‌دید (چون همیشه با نقطه صدا زده می‌شوند: `lifecycleScope.launch`) ⇒ ۱۹۰ مثبتِ کاذب. **نتیجهٔ عملی:** به آن اعتماد نکردم و هیچ import ای را از Activityها پاک نکردم (بخش ۷).

**د — یک باگِ از قبل موجود در ریپو (برای فازِ رفعِ باگ):** `scripts/validate_app_map.py` **در HEAD هم exit=1 می‌دهد**: `retrofit_declarations_source=170` در برابر `retrofit_declarations_map=162`، یعنی **۸ endpoint** در سورسِ اندروید هست که در `android-api-calls.csv` ثبت نشده (`attendance/{course_id}/start_live`، `attendance/{session_id}/live_status`، `attendance/{session_id}/end_live`، `attendance/{session_id}/cancel_live`، `attendance/live/current`، `admin/live_sessions`، `admin/live_sessions/{session_id}/roster`، `auth/device_token`). این اسکریپت در **هیچ workflow ای اجرا نمی‌شود** (`grep` در `.github/workflows/` = خالی)، پس CI را قرمز نمی‌کند — ولی اوراکلی که همیشه exit=1 می‌دهد هرگز نمی‌تواند به CI اضافه شود. **کارِ من نیست** (خروجی‌اش قبل و بعدِ تغییرم یکسان است) و به فهرستِ فازِ رفعِ باگ منتقل شد.

## ۷) آنچه این برش عمداً انجام **نداد**

1. **بدنهٔ Activityها دست‌نخورده است.** هیچ تابعی از هیچ کلاسی بیرون نرفت. بدنهٔ اصلیِ god-fileها (`StudentProfileActivity` با ۶۱ تابع، `InvoiceActivity` ۱۲۳۶ خط) هنوز سرجایشان است. دلیل: بیرون بردنِ منطق زیرِ قیدِ `keep_verbatim` یعنی نگه‌داشتنِ **تابعِ نازکِ واگذارکننده با همان امضایِ دقیق** در Activity، که باید تک‌تک و با اثبات انجام شود — نه دسته‌جمعی.
2. **import‌های بلااستفادهٔ Activityها پاک نشد.** بعد از بیرون رفتنِ اینترفیس‌ها، مثلاً `retrofit2.http.Body` در `AddClassActivity.kt` بلااستفاده است. در Kotlin این **خطا نیست** (حتی warning کامپایلر هم نیست) و هیچ lint id ای برایش وجود ندارد؛ و آشکارسازِ محلیِ من برای extension functionها قابلِ اعتماد نبود (بند ج). پاک‌کردنشان با یک آشکارسازِ غیرقابلِ اعتماد = ریسکِ قرمز کردنِ CI به‌ازایِ سودِ صفر.
3. **`docs/app-map/*.md` و `android-api-calls.csv` بازنویسی نشدند.** آن‌ها snapshotِ تاریخ‌دارِ `2026-09-28` با لینکِ commitِ هر فاز هستند و خودِ `validate_app_map.py:8` می‌گوید «`docs/app-map` inputs remain untouched as historical map artifacts». بازنویسیِ ۱۱۵ ردیفِ `file:line` جعلِ سندِ تاریخی بود. به‌جایش **یک یادداشتِ تاریخ‌دار** به `00-overview.md` اضافه شد که می‌گوید کدام ستون‌ها هنوز معتبرند و کدام‌ها محلِ اعلامِ اینترفیس را نشان نمی‌دهند.
4. **هیچ تستی تغییر نکرد** — تست‌ها اوراکل‌اند، نه مانعِ ریفکتور.
5. **`AuditTrailActivity.kt` (۷۰۳ خط، صفر پین) و `TeacherProfileActivity.kt` (۸۰۳ خط) هنوز تجزیه نشده‌اند** — بهترین نامزدهای برشِ بعدی.

## ۸) بدهی‌های بازِ قبلی (بدونِ تغییر)

- **۹۱ موردِ `paddingVertical`/`paddingHorizontal` در ۳۴ فایلِ layout** که lint آن‌ها را `NewApi` نمی‌زند (فقط ۱۴ موردِ داخلِ `values*` را می‌زد که در فازِ قبل اصلاح شد). **[بسته شد ۲۰۲۶-۱۱-۱۲ / P4d-6: باگ نیستند — aapt2 در `ResourceFileFlattener` بازنویسی‌شان می‌کند و lint عمداً benign می‌داندشان؛ `checkpoints/2026-11-12-investigate-phase4d6-padding-attrs-aapt2-desugar.md`.]**
- **۱۴۸ `StringFormatMatches`** (همهٔ Errorهای باقی‌ماندهٔ lint) — triaged out؛ فرمت‌ها درست کار می‌کنند.
- **گیتِ warningهای کامپایلرِ Kotlin** (`w:`) هنوز ساخته نشده.
- **بدهیِ `./gradlew wrapper`:** jar فعلی با jar رسمیِ `gradle/gradle@v8.13.0` تفاوتِ container دارد (۴۲۶۱۳ در برابر ۴۳۷۰۵ بایت، sha256 متفاوت، ۳۲/۳۳ CRC یکسان)؛ تا وقتی کاربر `./gradlew wrapper` را اجرا نکند، `validate-wrappers: false` + `gradle-version: 8.13` + گامِ Guard در `android.yml` لازم‌اند.

## ۹) گامِ بعد

1. **برش ۲:** تجزیهٔ `AuditTrailActivity.kt` (۷۰۳ خط، **صفر پینِ تست**، در هیچ تستی نامش نیامده) — امن‌ترین god-module برای ساختنِ الگویِ «repository + تابعِ نازکِ واگذارکننده».
2. **برش ۳:** `StudentProfileActivity.kt` — پُرارزش‌ترین (۱۱۸۶ خط، ۶۱ تابع، و `RetrofitClient.getInstance(this).create(ProfileApi::class.java)` در **۹ نقطه** تکرار شده که باید پشتِ یک repository برود).
3. هر برش با همین الگو: استخراج پشتِ تابعِ نازکِ واگذارکننده ⇒ `keep_verbatim` برقرار ⇒ اوراکلِ تفاضلی + هر ۶ بررسیِ ساختاری + همهٔ دروازه‌ها ⇒ CI سبز.
