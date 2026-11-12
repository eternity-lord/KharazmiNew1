# فاز P4d (برش ۲) — تجزیهٔ `AuditTrailActivity` به لایه‌های برچسب، CSV و داده

**شاخه:** `arena/37e7066f-kharazminew1` · commit `7f95b8c` (پس از `f973505` = ادغامِ PR #15)
**دامنهٔ تغییر:** ۴ فایلِ Kotlin (۱ ویرایش + ۳ تازه) + همین checkpoint. هیچ تستی، هیچ فایلِ سروری، هیچ منبعی در `res/` و هیچ workflow ای تغییر نکرد.

---

## ۱) چرا این فایل، و چرا امن‌ترین نامزد بود

`AuditTrailActivity.kt` با ۷۰۳ خط ششمین فایلِ بزرگِ اپ بود، ولی یک ویژگیِ تصمیم‌ساز داشت: **صفر پینِ تست**. این را از روی حافظه نپذیرفتم؛ با پویشِ ASTِ **کلِ کورپسِ تست (۱۳۳ فایل)** ثابت شد:

- هیچ فایلی در `Kharazmi_Server/tests` یا `tests/` نامِ `AuditTrailActivity.kt` را نمی‌آورد.
- هفت فایلی که `AuditTrail` را ذکر می‌کنند همه سمتِ **سرور** هستند (Python) و هیچ‌کدام Kotlin نمی‌خوانند.

پس تنها اوراکل‌های این برش «کامپایل» و «حفظِ رفتار» بودند — یعنی دقیقاً همان چیزی که CI و اوراکل‌های مکانیکیِ زیر می‌سنجند. این همان الگویی است که برای برش‌های بعدی (که پین دارند) سخت‌تر می‌شود، پس ارزش داشت اول روی حالتِ بدونِ پین اثبات شود.

## ۲) چه ساخته شد

| فایل | خط | نقش |
|---|---:|---|
| `AuditTrailActivity.kt` | **۷۰۳ → ۵۰۲** (−۲۰۱، −۲۹٪) | فقط UI، ناوبری و lifecycle |
| `AuditTrailLabels.kt` | ۱۸۷ (تازه) | لایهٔ نمایشِ **خالص**: برچسب‌ها، fallbackهای نام/کاربر، پارسِ رنگ، قالب‌بندیِ مقدار، خلاصه و متنِ دیف |
| `AuditTrailCsv.kt` | ۶۱ (تازه) | متنِ CSV، مهارِ فرمول‌اینجکشن (`= + - @`)، BOM و ساختِ فایل |
| `AuditTrailRepository.kt` | ۶۵ (تازه) | `AuditTrailFilter` + واکشیِ صفحه‌ای + جمع‌آوریِ چندصفحه‌ایِ خروجی + تنها نقطهٔ `RetrofitClient.create` |

- **۱۶ تابع** منتقل شدند؛ **۸ عضوِ واگذارکنندهٔ نازک** با **دقیقاً همان امضایِ قبلی** در Activity ماندند (`displayActionLabel`، `entityRefsLine`، `displayDiff`، `displayActor`، `parseColor`، `actionIcon`، `entityLabel`، `errorMessage`) ⇒ **هیچ call site ای عوض نشد**، از جمله داخلِ `inner class AuditLogAdapter` و `showDiffDialog`.
- قراردادِ `context` به‌عنوانِ **پارامترِ اول** دقیقاً الگویِ موجودِ همین بسته است (`EnrollmentLabels`، `ReportHints`) — اختراعِ قراردادِ تازه نکردم.
- `showDiffDialog` از **۵۰ → ۱۷ خط**: ساختِ متن خالص است و به `AuditTrailLabels.diffDialogMessage` رفت؛ خودِ `AlertDialog` و ناوبری ماندند چون به lifecycle و `Intent` نیاز دارند.
- دو واگراییِ واقعی هم از بین رفت: هر دو نقطهٔ فراخوانی (`loadLogs` و `exportFilteredLogs`) همان **هشت آرگومانِ نام‌دار** را دستی و جدا می‌ساختند؛ حالا یک `AuditTrailFilter` مشترک است، یعنی دیگر *نمی‌توانند* ناخواسته از هم واگرا شوند. عددِ `limit = 200` هم که لیترالِ بی‌نام بود به `EXPORT_PAGE_SIZE = 200` تبدیل شد (همان مقدار، حالا نام‌دار).

## ۳) اثباتِ حفظِ رفتار — چون محلی هیچ کامپایلری نیست

دو اوراکلِ تازه ساختم که دقیقاً همین نوعِ تغییر را می‌سنجند:

1. **بازگشتِ معکوس (round-trip):** برای هر ۱۶ تابعِ منتقل‌شده، وارونِ تبدیل‌ها (حذفِ `context: Context, ` از امضا، `context.getString` ← `getString`، `(context, ` ← `(`، حذفِ پیشوندِ `AuditTrailLabels.`، `fun` ← `private fun`) روی متنِ **فایلِ جدید** اعمال شد و نتیجه با بازهٔ **اصلیِ HEAD** مقایسه شد: **۱۶ از ۱۶ کلمه‌به‌کلمه یکسان**. یعنی هیچ بدنه‌ای حینِ جابه‌جایی تغییر نکرده جز آنچه خودِ تبدیل تعریف می‌کند.
2. **اوراکلِ arity:** برای هر ۶۷ نقطهٔ فراخوانی در ۴ فایل، شمارِ آرگومان‌ها (با عبورِ رشته‌آگاه از `()`/`{}`/`[]` و شمارشِ آرگومان‌های نام‌دار) با `required ≤ n ≤ total`ِ اعلام مقایسه شد: **۰ ناهمخوانی**. این همان چیزی است که «فراموش شدنِ یک `context`» را می‌گیرد.
3. **اعضای تکراری:** در هر ۴ فایل، **۰ امضایِ تکراری** (۲۸ عضو در Activity، ۱۴ در Labels، ۴ در Csv، ۲ در Repository).
4. **نام‌های top-levelِ کلِ ریپو:** `۳۹۹ → ۴۰۳`؛ born دقیقاً همان ۴ نامِ موردِ انتظار (`AuditTrailCsv`، `AuditTrailFilter`، `AuditTrailLabels`، `AuditTrailRepository`)، **gone=[] و duplicated=[]**.
5. **اوراکلِ تفاضلیِ حلِ نوع:** در Activity **۰ توکنِ تازهٔ حل‌نشده** در برابرِ HEAD، و در هر سه فایلِ تازه **۰ توکنِ حل‌نشده**.

## ۴) دو باگ که **فقط** بازبینیِ چشمی و بررسیِ تکراری‌ها گرفتند

- **`errorMessage` دو بار اعلام شده بود** (یک بار از جایگزینیِ بازهٔ خودش در خطِ ۳۰۵، یک بار داخلِ بلوکِ واگذارکننده‌ها در خطِ ۳۸۷) ⇒ `Duplicate JVM class method` و CI قرمز. علت: نامش هم در `DECL_CTX` بود هم جداگانه جایگزین می‌شد. **درس: اوراکلِ arity نقطهٔ *فراخوانی* را می‌سنجد، نه اعلامِ تکراری را** — پس بررسیِ «عضوِ تکراری» به مجموعهٔ راستی‌آزمایی اضافه و دائمی شد.
- **دو مصنوعِ خودِ راستی‌آزما** (نه کد): بازه‌یابِ عضوها در تورفتگیِ **صفر** متوقف نمی‌شد (آخرین عضوِ `object` براکتِ بسته‌شدنِ خودِ object را هم می‌بلعید ⇒ گزارشِ کاذبِ «diffSummaryFor یک `}` اضافه دارد»)، و اوراکلِ نوع **رشته‌ها** را به‌عنوانِ ارجاعِ نوع می‌خواند (`putExtra("STUDENT_ID", …)` ⇒ `STUDENT_ID` حل‌نشده!) در حالی که `Charsets`/`System` هم در Kotlin بدونِ import در دسترس‌اند. هر دو اصلاح شدند تا اوراکل **بدونِ توضیح و استثنا** exit=0 بدهد — سبزی که نیاز به توجیه داشته باشد، سبز نیست.

## ۵) دروازه‌ها (همه مطابقِ بیس‌لاین)

| دروازه | نتیجه |
|---|---|
| CI `android` (شاملِ `:app:compileDebugKotlin` + `assembleDebug` + `testDebugUnitTest`) | run `43060286040` → **success** |
| CI `tests` | run `43060286105` → **success** |
| گیتِ lint | `lint gate OK - 1360 issues / no regression` · `baseline=1360 now=1360 (+0)` · **new 0 / worse 0 / improved 0 / gone 0** |
| `pytest Kharazmi_Server/tests` | **1279 passed** |
| `pytest tests/route_audit` | **249 passed** |
| `scripts/validate_app_map.py` | خروجیِ JSON **بایت‌به‌بایت یکسان با HEAD** |
| `find_dead_kotlin.py` | **۸ نماد / ۱۰۴ خط** (دقیقاً همان DEFERها) |
| `find_dead_resources.py` | **۰ مرده / ۱۸۴۲ تعریف** |
| `gaj_db.db` md5 | `f048f8d118b33c4eaa944490594121d7` (بدونِ تغییر) |
| `test_android_resources_static.py` و کلِ `Kharazmi_Server/tests/` | **دست‌نخورده** |

## ۶) دو یافتهٔ جانبی

1. **`hasActiveFilters()` مرده بود و حذف شد** — یک عضوِ `private` با **صفر** نقطهٔ فراخوانی در کلِ ریپو. نکتهٔ مهم‌تر از خودِ حذف: `find_dead_kotlin.py` **نمی‌تواند** این را ببیند، چون فقط اعلام‌های **سطحِ بالا** (تورفتگیِ صفر) را پویش می‌کند. یعنی یک دستهٔ کامل از کدِ مرده (اعضای privateِ کلاس‌ها) خارج از دیدِ آن ابزار است. گسترشِ آن به «اعضای private با صفر فراخوانی در همان فایل» یک قاعدهٔ **صدا**ست (private را فقط هم‌فایلی‌ها می‌توانند صدا کنند) و نامزدِ خوبی برای برشِ بعدیِ فازِ کدِ مرده است.
2. **`AuditTrailApi.exportLogsCsv` دست‌نخورده ماند** با اینکه مصرف نمی‌شود: در `checkpoints/2026-09-16_Financial-Audit-Trail.md:71` و `:165` صریحاً مستند شده که «اضافه شد ولی مصرف نمی‌شود و **کار نمی‌کند** (سرور CSV نمی‌دهد)» و در `docs/app-map/android-api-calls.csv:19` هم ثبت است. حذفش تصمیمِ دیگری است (روی اوراکلِ app-map هم اثر دارد: `170 → 169`)، پس به فهرستِ فازِ رفعِ باگ سپرده شد.

## ۷) وضعیتِ god-fileها بعد از دو برش

`AuditTrailActivity` دیگر جزو ۸ فایلِ بزرگ نیست. رتبهٔ فعلی:

```
1236  InvoiceActivity.kt        1186  StudentProfileActivity.kt   1039  AppModels.kt
 998  AttendanceActivity.kt      926  ClassDetailActivity.kt       790  TeacherProfileActivity.kt
 775  MainActivity.kt            636  ClassSetupActivity.kt
```

## ۸) گامِ بعد — برش ۳ (اندازه‌گیری شد)

`StudentProfileActivity.kt` (۱۱۸۶ خط، ۶۱ تابع، ۱ پینِ کل‌فایلی: `enrollmentLabel(`). الگویِ همان برش ۲، با دو تفاوت:

- **پین دارد** ⇒ هر تابعِ پین‌شده باید امضایِ دقیقش در همان فایل بماند (قاعدهٔ `_kotlin_function_body` که در نبودِ امضا رشتهٔ تهی می‌دهد و `assertIn` روی تهی شکست می‌خورد).
- **تکرارِ `RetrofitClient.getInstance(this).create(...)`**: در کلِ اپ **۲۷ نقطه**؛ `StudentProfileActivity` ۶ نقطه در یک خط (و بیشتر اگر فراخوانی‌های دوخطی باشند)، `TeacherProfileActivity` ۴، `PendingClassesActivity` ۳، `ClassManagementActivity` ۳ ⇒ هرکدام باید پشتِ یک `from(context)` مثلِ `AuditTrailRepository` بروند.

## ۹) بدهی‌های بازِ قبلی (بدونِ تغییر)

~~۹۱ موردِ `paddingVertical`/`paddingHorizontal` در ۳۴ layout که lint آن‌ها را `NewApi` نمی‌زند~~ (بسته شد ۲۰۲۶-۱۱-۱۲ / P4d-6: باگ نیستند — aapt2 بازنویسی می‌کند و lint عمداً benign می‌داندشان؛ `checkpoints/2026-11-12-investigate-phase4d6-padding-attrs-aapt2-desugar.md`) · ۱۴۸ `StringFormatMatches` (تنها Errorهای باقی‌ماندهٔ lint، triaged out) · گیتِ warningهای کامپایلرِ Kotlin ساخته نشده · `validate_app_map.py` در HEAD هم exit=1 می‌دهد (۸ endpointِ ثبت‌نشده) و در هیچ workflow ای نیست · بدهیِ `./gradlew wrapper` (تا اجرا نشود، `validate-wrappers: false` + `gradle-version: 8.13` + گامِ Guard لازم‌اند).
