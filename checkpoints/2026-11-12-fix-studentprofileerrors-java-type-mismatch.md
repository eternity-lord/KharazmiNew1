# حذفِ تنها هشدارِ «Java type mismatch» پروژه و قفلِ دوبارهٔ baseline رویِ ۴۴/۲

تاریخ: ۲۰۲۶-۱۱-۱۲ · شاخه: `arena/c7e2f9a4-kharazminew1` · PR #27 · پایه: `6cd67b9`
commitها: `728720e` (وصلهٔ Kotlin) و `f96707a` (baselineِ برداشت‌شده از CI + شاهدِ به‌روز)

---

## ۱) خلاصهٔ یک‌خطی

تنها هشدارِ ناهمخوانیِ نوعِ کلِ پروژه — `StudentProfileErrors.kt:20:73` — با جایگزینیِ
`optString("message", null)` به `optString("message", "")` حذف شد، بدونِ هیچ تغییرِ
رفتاری؛ سپس baselineِ گیتِ هشدارهایِ Kotlin از ۴۵/۳ به **۴۴/۲** تنگ شد تا بازگشتِ
همان هشدار از این پس CI را قرمز کند.

## ۲) عیب

```kotlin
val d = obj.optString("detail", "")
if (d.isNotBlank()) d else obj.optString("message", null)?.takeIf { it.isNotBlank() }
```

`JSONObject.optString(String, String)` یک متدِ **Java** است و پارامترِ دومش `String`
اعلام شده، نه `String?`. ستونِ ۷۳ دقیقاً همان `null` است:

```
w: …/StudentProfileErrors.kt:20:73 Java type mismatch: inferred type is
   'kotlin.Nothing?', but 'kotlin.String' was expected
```

## ۳) چرا این هشدار پرسیگنال‌ترین یافتهٔ گیت بود

گیتِ هشدارهایِ کامپایلر (PR #25) رویِ main ۴۵ هشدار در ۳ گونه شمارش کرد. ۴۴ تایِ آن‌ها
بدهیِ نوسازی‌اند و ماهیتاً یک‌دست:

| گونه | شمار | نمونه |
|---|---|---|
| `'*' is deprecated. Deprecated in Java` | ۴۰ | `MasterKey`، `EncryptedSharedPreferences`، `PersianCalendar`، `JsonParser` |
| `'*' is deprecated. … in favor of using the Activit#6b3040` | ۴ | `startActivityForResult` ⇒ Activity Result API |
| `Java type mismatch: inferred type is '*', but '*' was expected` | **۱** | `StudentProfileErrors.kt:20:73` |

یعنی ۴۴ مورد «امروز کار می‌کند، فردا باید مهاجرت کند» است، ولی موردِ ۴۵ام نشانهٔ یک
**نیتِ بیان‌نشده** در کد بود: نویسنده خواسته بگوید «اگر کلید نبود، هیچ»، و این خواسته
هم با امضایِ Java ناسازگار بود و هم بی‌اثر.

## ۴) هم‌ارزیِ رفتار (چرا این تغییر بی‌خطر است)

`optString(name, fallback)` مقدارِ `fallback` را **تنها** وقتی برمی‌گرداند که
`opt(name)` غایب باشد (یعنی Java-null). پس:

| حالتِ JSON | پیش از تغییر | پس از تغییر |
|---|---|---|
| کلید غایب | `fallback = null` → `null?.takeIf { … }` → `null` | `fallback = ""` → `"".takeIf { isNotBlank }` → `null` |
| مقدار = `null`ِ JSON | fallback خوانده نمی‌شود ⇒ نتیجهٔ `optString` | **دقیقاً همان** |
| رشتهٔ سفید | `takeIf` → `null` | **دقیقاً همان** |
| رشتهٔ ناتهی | خودِ رشته | **دقیقاً همان** |

تنها شاخه‌ای که fallback در آن مصرف می‌شود هم خروجیِ یکسان دارد (`null`)، و در سه شاخهٔ
دیگر fallback اصلاً خوانده نمی‌شود. ضمناً خطِ ۱۹ِ همان فایل برایِ `detail` از قبل
`optString("detail", "")` داشت ⇒ الگو یکدست شد.

فراخوانِ امنِ `?.` هم برداشته شد چون گیرنده دیگر عملاً ناتهی است. اگر نگاه داشته می‌شد،
هشدارِ «فراخوانِ امنِ بی‌ضرورت» جایِ هشدارِ قبلی را می‌گرفت و **گونهٔ تازه‌ای** به گیت
اضافه می‌کرد — یعنی اصلاحِ ناقص، گیت را قرمز می‌کرد.

کامنتِ ۶ خطیِ `FIX(kotlin-warning)` همین استدلال را سرِ همان خط ثبت می‌کند تا کسی بعداً
`null` را «برنگرداند». فایل ۲۵ → ۳۱ خط.

## ۵) دامنهٔ اثر و پین‌ها

۴ فراخوان در `StudentProfileActivity.kt` (خطوطِ ۸۷۸، ۹۱۱، ۱۰۰۱، ۱۰۲۷) که همه
به‌شکلِ `?: e.message ?: getString(R.string.common_unknown_error)` null-safe اند.
`--pins` برایِ این فایل: سخت=۰ نرم=۰ منفی=۰ («هیچ پینی ندارد») و هیچ تستی متنِ آن را
pin نکرده است ⇒ عضوِ `extractServerDetail` آزاد بود. `Kharazmi_Server/tests/` لمس نشد.

## ۶) شواهدِ اوراکل (`verify_kotlin_refactor.py`)

| پرچم | پیش | پس |
|---|---|---|
| `--spans` | ۱ عضو، ۱۳..۲۴ (۱۲ خط) | ۱ عضو، **۱۳..۳۰ (۱۸ خط)** |
| `--members` | ۱ عضو، ۱ امضا، تکراری=none | همان |
| `--types` | ۰ توکنِ حل‌نشده | همان |
| `--arity` | ۰ فراخوانی، ۰ ناهمخوانی | همان |
| `--names` | — | **HEAD=407 now=407 born=[] gone=none dup=none** |
| `--pins` (کورپس) | ۱۵ فایلِ تست و ۴۵ مرجع | همان، مجموعِ سخت **۲۱۸** |

دلتایِ نام‌هایِ سطحِ بالا **دقیقاً تهی** است — همان که برایِ یک اصلاحِ درونِ بدنه باید باشد.

## ۷) شواهدِ محلی

| گیت | نتیجه |
|---|---|
| GATE A (pytest کامل از ریشه) | **1279 passed** |
| GATE B (`tests/route_audit`) | **285 passed** |
| GATE C (cwd-independence از داخلِ `Kharazmi_Server`) | **31 passed** |
| suite گیتِ هشدارها | **25 passed** (و `--collect-only` هم 25) |
| گاردِ کورپسِ اوراکل | **5 passed** |
| ruff ریشه / `--select F821` | **250** (بدونِ تغییر) / **0** |
| ruff رویِ دو فایلِ ویرایش‌شده | **All checks passed** |
| mypy `Kharazmi_Server/` | **725 خطا در ۴۴ فایل** (بدونِ تغییر) |
| `validate_app_map.py --gate` / پیش‌فرض | **exit 0** / **exit 1** (هر دو مطابقِ انتظار) |
| `find_dead_kotlin.py` | **۸ نماد / ۱۰۴ خط** (بدونِ تغییر) |
| `find_dead_resources.py` | **0** |
| md5 `Kharazmi_Server/gaj_db.db` | `f048f8d118b33c4eaa944490594121d7` (دست‌نخورده) |

## ۸) شبیه‌سازیِ محلیِ گیت پیش از push — و یک انتظارِ غلط که اصلاح شد

چون در این سندباکس JVM/Gradle نیست، logِ سنتزی از **همان baselineِ committed**
بازسازی شد (۴۵ هشدار با همان توزیعِ `top_files`) و نخست با `kind_of` راستی‌آزمایی شد
که متنِ بازسازی‌شدهٔ پیام‌ها **دقیقاً** همان سه کلیدِ baseline را می‌سازد — از جمله
کلیدِ بریده‌شدهٔ `…in favor of using the Activit#6b3040` که تأیید کرد متنِ کامل
`Activity Result API` است. سپس سه سنجه:

1. baselineِ قدیم + logِ ۴۵ → `exit 0`، «now 45 in 3 kinds | baseline 45 in 3 kinds | delta +0»
2. baselineِ قدیم + logِ ۴۴ → **`exit 0`**، «now 44 in 2 kinds | baseline 45 in 3 kinds | **delta -1**» و دو `notice`
3. baselineِ **تازه** + logِ ۴۵ → **`exit 1`** با «new warning kinds … Java type mismatch … x1» و «total warnings increased: 44 -> 45»

سنجهٔ ۲ انتظارِ ثبت‌شده در حافظهٔ جلسه را **ابطال کرد**: گیت رویِ بهبود شکست نمی‌خورد
(فقط گونهٔ تازه یا رشد‌کرده شکست است)، بلکه پاس می‌شود و JSONِ آمادهٔ commit را در
`notice` منتشر می‌کند. سودِ این شبیه‌سازی: پیش از push معلوم شد که CI سبز می‌ماند و
قدمِ دوم یک «اصلاحِ شکست» نیست بلکه یک «قفلِ بهبود» است.

## ۹) شواهدِ CI — اجرایِ نخست (`43604395121` android، `43604395103` tests)

هر دو run با `exit 0`. گام‌هایِ Android همه `success` (۷ compile، ۸ گیتِ هشدارها،
۹ JVM unit tests، ۱۰ lint، ۱۱ گیتِ lint، ۱۲ locations) و گام‌هایِ ۱۳/۱۴ که
failure-only هستند `skipped`. هر دو jobِ tests هم `success`. صفر annotationِ
`error`/`failure`. این **شاهدِ کامپایلر** است: تغییر در Kotlin واقعی کامپایل شد و
JVM unit tests را پاس کرد.

annotationهایِ گیتِ هشدارها:

```
notice  Kotlin compiler warnings - 44 in 2 kinds
notice  kotlin warning baseline can be refreshed
        now 44 in 2 kinds | baseline 45 in 3 kinds | delta -1
        Java type mismatch: inferred type is '*', but '*' was expected 1->0
        kinds fully resolved: Java type mismatch: inferred type is '*', but '*' was expected
notice  kotlin warning baseline refreshed - commit as KharazmiAdmin/kotlin-warnings-baseline.json
notice  lint gate OK - 1360 issues / no regression   (baseline=1360 now=1360 (+0)، ۳۲ شناسه)
```

«kinds fully resolved» یعنی یک گونهٔ کامل از بین رفته — دقیقاً هدفِ این برش.

## ۱۰) قدمِ دوم: قفلِ baseline رویِ ۴۴/۲

JSONِ منتشرشده در `notice` **عیناً** (با `gh api … /annotations`، بدونِ بازنویسیِ دستی)
برداشت و commit شد؛ تنها فیلدِ metadata یعنی `source` به شمارهٔ همان اجرا ارجاع داده شد
(پیروی از قراردادِ پیشینِ فایل: «CI run 43268013140»). راستی‌آزماییِ برداشت: هر ۶ فیلدِ
محتوایی با شبیه‌سازیِ محلیِ §۸ برابر بود.

| | پیش | پس |
|---|---|---|
| `total` | ۴۵ | **۴۴** |
| `distinct_kinds` | ۳ | **۲** |
| `files_with_warnings` | ۱۰ | **۹** |
| گونهٔ حذف‌شده | — | `Java type mismatch: …` |
| فایلِ حذف‌شده از `top_files` | — | `StudentProfileErrors.kt` |

شاهدِ `test_committed_baseline_is_consistent_with_the_tool_and_the_ci_inventory`
به‌روز شد و **قفلِ چهارمی** گرفت: گونهٔ رفع‌شده باید بیرون مانده باشد و
`StudentProfileErrors.kt` نباید در `top_files` باشد. بازتولیدِ هر سه شناسه با `kind_of`
از پیامِ واقعیِ کامپایلر دست‌نخورده ماند (اگر روزی `MAX_KIND_LEN` یا تابعِ هش عوض شود،
همین تست قرمز می‌شود)، و `sum(top_files.values()) == total` هم اضافه شد.

سنجهٔ دندان‌داشتنِ گیت پس از قفل: logِ ۴۴ → `exit 0` و «delta +0» و «no change against
the baseline»؛ logِ ۴۵ → `exit 1` با locationsِ `StudentProfileErrors.kt:20:9`.

شواهدِ CI دوم (`43605479277` android، `43605479343` tests) — هر دو run با `exit 0`،
همهٔ گام‌هایِ Android و هر دو jobِ tests `success`، صفر annotationِ `error`/`failure`:

```
notice  Kotlin compiler warnings - 44 in 2 kinds
        Kotlin compiler warnings: 44 in 2 kinds across 9 files
           40  '*' is deprecated. Deprecated in Java
            4  '*' is deprecated. This method has been deprecated … Activit#6b3040
notice  lint gate OK - 1360 issues / no regression   (baseline=1360 now=1360 (+0)، ۳۲ شناسه)
```

و از هر عددی گویاتر: noticeِ «kotlin warning baseline can be refreshed» که در اجرایِ
نخست منتشر شده بود در اجرایِ دوم **دیگر منتشر نشد**. یعنی baseline با واقعیتِ کامپایلر
منطبق است (`delta +0`) و «قفل شدنِ بهبود» اثبات شد، نه فقط ادعا — اگر روزی آن هشدار
برگردد، همین گیت با «new warning kinds» و «total 44 -> 45» قرمز می‌شود (سنجهٔ ۳ در §۸).

## ۱۱) سه درسِ ابزاری از این برش

1. **انتظارِ ثبت‌شده را پیش از push بسنج.** حافظهٔ جلسه می‌گفت «گیت رویِ بهبود شکست
   می‌خورد»؛ شبیه‌سازیِ محلی نشان داد `exit 0` است. اگر بدونِ سنجش push کرده بودم،
   CIِ سبز را با شکستِ فرضی عوض می‌گرفتم و دنبالِ مشکلِ خیالی می‌رفتم.
2. **flapِ فایل‌سیستم تصادفیِ به‌ازای هر فراخوانی است، نه به‌ازای هر مسیر.** در یک
   فراخوانیِ واحد `ls -l KharazmiAdmin/*.py` و `open()` پایتون سالم بودند و `cat` و
   `python3 <path>` و `ls -ldi` شکست خوردند. راهکارِ مؤثر: `cd` به داخلِ پوشه و اجرایِ
   اسکریپت، همراه با retry (تا ۱۵ بار). و مهم‌تر: **هرگز** «صفر/پاک» را از یک خوانشِ
   شکسته نتیجه نگیر — در این برش دو بار «hard sum = 0» از فرمانِ ENOENT چاپ شد و هر دو
   بار سنجهٔ واقعی ۲۱۸ بود.
3. **assert نباید توضیحِ خودش را ببیند** (چهارمین رخدادِ این دام). کامنتِ جدیدِ Kotlin
   کلمهٔ `takeIf` و `?.` را نقل می‌کرد ⇒ `assert new.count("takeIf") == 1` شکست؛ و
   یک assertِ خود-شکست‌بر واژهٔ بیگانهٔ جاخوش‌کرده در کامنت را پنهان کرد. راهکار:
   شمارش‌ها را به خط‌هایِ کد مقید کن (`code_only()`: حذفِ خط‌هایِ `//`)، و توکن‌هایِ
   ممنوع را با `assert bad not in REPL` ساده و بدونِ خنثی‌سازی بسنج. ضمناً لنگرِ
   جایگزینی باید **با تورفتگی** باشد، وگرنه تورفتگی دو برابر می‌شود (۲۰ → ۴۰ فاصله)
   و assertِ عرضِ تورفتگی همان را می‌گیرد.

## ۱۲) بدهیِ باقی‌مانده

- ۴۴ هشدارِ نوسازیِ baselined که اکنون **قفل** شده‌اند (بدترشدنشان قرمز است):
  `EncryptedSharedPreferences`/`MasterKey` (۱۱ در `SecureLoginStore.kt`)،
  `PersianCalendar`/`PersianDatePickerDialog`، `JsonParser`، و ۴×
  `startActivityForResult` ⇒ Activity Result API.
- محدودیتِ صادقانهٔ گیت: **netting-out** — اگر یک هشدار از یک گونه حذف و یکی به همان
  گونه اضافه شود، `total` و `by_kind` تکان نمی‌خورند و گیت ساکت می‌ماند.
- ruff ۲۵۰ و mypy ۷۲۵/۴۴ هنوز گیتِ «بدتر-نشود» ندارند (الگویِ آماده:
  `lint_gate.py` و `kotlin_warning_gate.py`).
- `find_dead_kotlin` هنوز ۸ نماد / ۱۰۴ خطِ DEFER دارد.
- ۱۰ فایلِ `.kt` بالایِ ۶۰۰ خط؛ بهترین هدفِ اندازه-به-ریسک
  `AttendanceActivity.kt` (۹۹۸ خط، ۶۸٫۱ پین/kLOC، خوشهٔ ≈۱۴۲ خطیِ شبکه/صف).
