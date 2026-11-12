# فاز P4d — برش ۳: هلپرهای خالصِ `StudentProfileActivity` و کدِ مردهٔ جایگزین‌شده

تاریخ: ۲۰۲۶-۱۱-۱۲ · شاخه: `arena/2c0a45b4-kharazminew1` · نقطهٔ شروع: `9ca64f7` (main پس از برش ۲)

## ۱. آنچه انجام شد

`StudentProfileActivity.kt` دومین ماژولِ بزرگِ اپ بود (**۱۱۸۶ خط**، ۴۲ عضو). در این برش
۷۳ خط از آن بیرون برده یا حذف شد:

| فایل | پیش | پس | تغییر |
|---|---:|---:|---|
| `StudentProfileActivity.kt` | ۱۱۸۶ | **۱۱۱۳** | −۷۳ (−۶٫۲٪) |
| `StudentProfileFormat.kt` (جدید) | — | ۴۴ | `object`: `formatCurrency` · `normalizePersianDigits` · `isValidJalaliDate` |
| `StudentProfileErrors.kt` (جدید) | — | ۲۵ | `object`: `extractServerDetail` |
| `res/values/strings.xml` | ۱۵۳۱ | ۱۵۲۳ | −۸ رشتهٔ یتیم |
| اعضای Activity | ۴۲ | **۳۵** | ۴ منتقل + ۳ حذف |

دو تغییرِ مستقل:

**الف) استخراجِ چهار هلپرِ خالص.** هر چهار تابع نه `Context` می‌خواهند نه `View`، پس بدونِ
Activity قابلِ تست‌اند. بدنه‌ها **کلمه‌به‌کلمه** منتقل شدند (تنها `private` برداشته شد چون
عضوِ `object` شده‌اند) و round-trip با assert اثبات شد (۴/۴). برخلافِ برش ۲، اینجا
« delegator نازک» نگذاشتیم: هیچ تستی این امضاها را پین نکرده بود (پایین‌تر اثبات شده)، پس
۸ جایِ فراخوانی مستقیم با prefix شیء نوشته شدند تا indirectionِ بی‌فایده نماند:
`formatCurrency` ۱ (داخلِ template در `showFinancial`)، `normalizePersianDigits` ۲،
`isValidJalaliDate` ۱، `extractServerDetail` ۴. شمارِ هر کدام پیش از جایگزینی assert شد.

**ب) حذفِ سه عضوِ مردهٔ جایگزین‌شده.** `buildTotalStatus` (۱۰ خط)، `buildWalletStatus` (۱۰)
و `colorForBalance` (۵) **صفر فراخوانی** در کلِ مخزن داشتند — فقط خطِ اعلامِ خودشان. دلیلِ
مرده بودنشان هم پیدا شد: `showFinancial` امروز همان کار را با
`EnrollmentLabels.debtTeacherLine(this, …)` و `EnrollmentLabels.debtInstituteLine(this, …)`
انجام می‌دهد، یعنی این سه باقی‌ماندهٔ یک جایگزینیِ قدیمی‌اند. با حذفِ آنها، هشت رشتهٔ
`R.string.profile_*` که **فقط** داخلِ همان سه تابع ارجاع می‌شدند یتیم شدند و حذف گردیدند
(`profile_debt_total`, `profile_credit_total`, `profile_settled_total`, `profile_debt_reg`,
`profile_ower`, `profile_creditor`, `profile_settled`, `profile_debt_short`). هیچ‌کدام پینِ
تستی نداشتند و هیچ `values-*` موازی‌ای هم وجود ندارد (فقط `values/strings.xml`)، پس
`MissingTranslation` یا lint-idِ تازه‌ای ساخته نشد.

دو importِ `java.util.Locale` و `kotlin.math.abs` پس از این تغییر واقعاً بی‌استفاده شدند
(شمارِ رخدادِ bare هر دو = ۰، با حذفِ استفادهٔ fully-qualified از شمارش) و برداشته شدند.

## ۲. دیوارِ پین: چرا لایهٔ شبکهٔ این صفحه بیرون نرفت

نقشهٔ پین (با دانه‌بندیِ member روی کورپسِ ۱۳ فایلِ تست) نشان داد از ۴۲ عضو، **۶ عضو
پینِ سخت** دارند و ۳۶ عضو آزادند:

| عضو | لیترال‌های پین‌کننده | تست |
|---|---|---|
| `fetchFullData` | ۶ لیترالِ Glide/آپلود (`"uploads/profiles/" + `, `GlideUrl(`, `SecureLoginStore.getToken`, `.addHeader("Authorization", …)`, `.load(glideUrl)`, `.error(android.R.drawable.sym_def_app_icon)`) | `test_audit_serve_upload.py` |
| `fetchTimeline` | `api.getTimeline(studentId)`, `timelineAdapter?.update(list)` | `test_audit_timeline.py` |
| `initViews` | ۵ regex (UserCreds/USER_SUB_ROLE/`isTeacherUser = …`/`if (subRole == "secretary")`/`btnDeleteStudent…GONE`) | `test_group3_teacher_ui_access.py` |
| `showFinancial` | `contract_only`, `debtTeacherLine(`, `debtInstituteLine(` | `test_android_resources_static.py` |
| `showCreateInstallmentDialog` | `JalaliUtils.todayJalaliString()` | `test_android_resources_static.py` |
| `onResume` | `override fun onResume()` | `test_android_resources_static.py` |

معنایِ دقیقِ «پینِ سخت»: تست `_kotlin_source("StudentProfileActivity.kt")` را می‌خواند و
`assertIn` را روی **متنِ کلِ فایل** می‌زند؛ ابزار شبیه‌سازی می‌کند که «اگر این بلوک از فایل
بیرون برود، آیا لیترال هنوز در فایل می‌ماند؟». اگر نه ⇒ پینِ سخت.

نتیجهٔ معماری: **لایهٔ شبکهٔ این صفحه با تست‌های بک‌اند به همین فایل پین شده است.** چون
`KHarazmi_Server/tests/` بنا بر تصمیمِ پروژه دست‌نخورده می‌ماند، ساختنِ
`StudentProfileRepository` (برخلافِ برش ۲ که `AuditTrailRepository` ممکن بود) اینجا بدونِ
شکستنِ تست ممکن نیست. هر هشت جایِ `RetrofitClient.getInstance(…).create(…)` داخلِ همین
توابعِ پین‌شده‌اند؛ سودِ انتزاعِ آنها ~۱۰ خط بود و ریسکش شکستنِ پین‌ها ⇒ **عمداً انجام نشد**
و به‌عنوانِ بدهیِ معماریِ مستند باقی می‌ماند.

هر ۷ کاندیدای این برش (۴ هلپرِ زنده + ۳ تابعِ مرده) پیش از دست‌زدن بررسی شدند:
**هیچ پینِ سخت یا نرمی نداشتند**، و هیچ تستی `_kotlin_function_body` را روی آنها صدا نمی‌زند
(تنها `initViews` در `test_group3_teacher_ui_access.py:332,363` استخراجِ بدنه می‌شود که
دست‌نخورده ماند). پس از ویرایش هم، نقشهٔ پین **دقیقاً همان ۲۴ سخت / ۱۲۷ نرم / ۱۴ منفی**
را داد ⇒ هیچ پینی نشکست.

## ۳. باگِ پیدا‌شده (عمداً اصلاح نشد): `isValidJalaliDate` همیشه `false` می‌دهد

هنگامِ استخراجِ کلمه‌به‌کلمه، یک باگِ از پیش موجود و **کاربر-محور** پیدا شد. الگویِ regex
در منبع بیش از حد escape شده است — ۱۲ backslash در آن خط (۴ تا برای هر `\d`):

```
val re = Regex("^\\\\d{4}/\\\\d{2}/\\\\d{2}$")
```

در Kotlin `\\\\` به **دو** backslash در رشتهٔ زمانِ اجرا تبدیل می‌شود، پس الگویِ واقعی
`^\\d{4}/\\d{2}/\\d{2}$` است و در regex یعنی «یک backslashِ واقعی، سپس حرفِ d چهار بار».
سنجشِ عددی:

| الگو | `1405/06/04` | `\dddd/\dd/\dd` |
|---|---|---|
| همان که در منبع است | `False` | `True` |
| شکلِ درست (`\\d` ⇒ `\d`) | `True` | `False` |

اثر: در `showCreateInstallmentDialog`، `if (!StudentProfileFormat.isValidJalaliDate(normalizedDue))`
با خطایِ `installment_error_due` و `return@setOnClickListener` بیرون می‌پرد ⇒ **ثبتِ قسط برای
هر تاریخِ معتبری هم رد می‌شود**. نکتهٔ تکمیلی: `JalaliUtils.parseProjectDate` خودش
`DATE_RE` و `normalizeDigits` و اعتبارسنجیِ `isLenient = false` دارد، پس این گاردِ محلی هم
اشتباه است هم زائد.

**چرا اصلاح نشد:** این برش یک بازسازیِ رفتار-حفظ است؛ اصلاحِ این الگو رفتار را عوض می‌کند
(مسیرِ موفقیتِ ثبتِ قسط را باز می‌کند) و تصمیمِ جداگانه‌ای است که باید با تستِ خودش بیاید.
متن در `StudentProfileFormat.kt` **بایت‌به‌بایت** همان چیزی است که در HEAD بود (با
`git show` مقایسه و اثبات شد). هیچ تستی این متن را پین نکرده، پس اصلاحش در یک برشِ مستقل
بدونِ دست‌زدن به `KHarazmi_Server/tests/` ممکن است. **منتظرِ تصمیمِ کاربر است.**

> **یادداشتِ ۲۰۲۶-۱۱-۱۲ (پس از ادغامِ برشِ ۳):** کاربر تصمیم گرفت و این باگ در یک
> تغییرِ مستقل اصلاح شد. متنِ بالا دست‌نخورده ماند چون وضعیتِ همان برش را روایت می‌کند.
> یک سطحِ escape برداشته شد (۱۲ → ۶ backslash در منبع) و شاهدِ تستیِ JVM اضافه شد:
> `KharazmiAdmin/app/src/test/java/com/example/kharazmiadmin/StudentProfileFormatTest.kt`
> که در CI با `:app:testDebugUnitTest` اجرا می‌شود.
>
> پیش از رفع، قالبِ درست تأیید شد تا «رفع» حدسی نباشد: `JalaliUtils.formatJalali` قالبِ
> `"%04d/%02d/%02d"` را می‌سازد (اسلش، صفر-پرشده، «server-safe») و
> `etDue.setText(JalaliUtils.todayJalaliString())` همان را در فیلدِ سررسید پیش‌پر می‌کند —
> یعنی برنامه مقدارِ پیش‌فرضِ خودش را هم رد می‌کرد. مهم‌ترین تستِ اضافه‌شده همین است:
> `acceptsTheDateTheAppPrefillsIntoTheDueField`، و چون قالبِ `%04d/%02d/%02d` همیشه با
> الگو می‌خواند، مستقل از تاریخِ اجراست.
>
> قراردادِ قالب **عمداً سخت‌گیرانه ماند**: جداکنندهٔ `-` و رقمِ تک‌رقمی رد می‌شوند، چون
> `formatJalali` همان قالبِ اسلش‌دار را server-safe می‌داند. پارسرِ عمومیِ
> `JalaliUtils.parseProjectDate` هر دو جداکننده را می‌پذیرد (برای خواندنِ دادهٔ
> ذخیره‌شده)، پس اگر روزی خواستیم ورودیِ کاربر هم `-` را بپذیرد، آن یک تصمیمِ محصولیِ
> جداست نه بخشیِ این رفع.
>
> یک نکتهٔ تستی که از خواندنِ `JalaliUtils` به دست آمد و دام بود: `jalaliToGregorian`
> فقط `require(jm in 1..12 && jd in 1..31)` دارد و سپس با حلقهٔ `while (gd > monthDays[gm])`
> **سرریز** می‌کند؛ پس برخلافِ شاخهٔ میلادی (`isLenient = false` + اجبارِ `time`)، تاریخِ
> ناممکنِ شمسی مثلِ `1404/07/31` را رد **نمی‌کند** و بی‌صدا به ماهِ بعد می‌برد. به همین
> دلیل در تست فقط ماهِ ناممکن (`1404/13/01`, `1404/00/01`) assert شد، نه روزِ ناممکن.
> این واگرایی بینِ دو شاخهٔ پارسر خودش یک بدهیِ ثبت‌شدنی است.

## ۴. اوراکلِ بازسازی: از `/tmp` به ابزارِ متعهد

اسکریپت‌های راستی‌آزماییِ برش‌های ۱ و ۲ در `/tmp` بودند و `/tmp` بین نوبت‌ها پاک شد؛ همهٔ
اوراکل‌های کالیبره‌شده از دست رفتند. بازسازی‌شدند و این‌بار به‌صورتِ یک ابزارِ stdlib-only
**متعهد** در `KharazmiAdmin/verify_kotlin_refactor.py` (کامیتِ `a7ae11b` + اصلاحاتِ این برش).
چهار باگِ واقعی در خودِ ابزار پیدا و رفع شد — هر سه تایِ اول «سبزِ کاذب» تولید می‌کردند:

1. **`members()` بدونِ `re.MULTILINE`**: الگویِ `^ {4}…fun (\w+)\(` با `finditer` روی کلِ متن
   فقط آغازِ رشته را می‌دید ⇒ همیشه فهرستِ تهی، و `except KeyError: continue` آن را
   **بی‌صدا** می‌بلعید. نتیجهٔ عملی: `member_blocks` برای فایلِ ۱۱۸۶ خطی **صفر** عضو
   می‌داد و نقشهٔ پین گزارش می‌کرد «صفر پینِ سخت» — یعنی دقیقاً مجوزِ شکستنِ تست‌ها.
   اکنون ۴۲ عضو را درست می‌شمارد و اگر عضوی پیدا شود ولی بازه‌ای ساخته نشود، `SystemExit`
   می‌دهد (fail-closed).
2. **کورپسِ تست از `rglob`**: در همین sandbox لحظاتی `Kharazmi_Server` برای ابزار ناپدید شد
   و کورپس از ۱۳ فایلِ تست به ۴ سقوط کرد، بی‌آنکه چیزی اعلام شود. اکنون فهرست از
   **indexِ git** خوانده می‌شود (`git ls-files -- '*/test_*.py'`) و کامل بودنش با سه assert
   اثبات می‌گردد: حضورِ فایل‌های tracked روی دیسک، حضورِ
   `test_android_resources_static.py`، و دستِ‌کم ۱۰۰ فایلِ تست.
3. **دانه‌بندیِ `top`**: بلوکِ یک `class` یعنی کلِ فایل، پس هر لیترالی «پینِ سخت» می‌شود
   (۹ پینِ کاذب روی همین فایل دیده شد). پیش‌فرض روی `member` تنظیم شد و برای
   پین‌های سطحِ interface (`AuthApi` و…) پرچمِ `--granularity top` مانده است.
4. **`assertNotIn`ها دیده نمی‌شدند**: پینِ منفی فقط وقتی لیترال حاضر بود ثبت می‌شد، پس
   قیدِ واقعیِ `test_android_resources_static.py:738-739`
   (`assertNotIn("enrollmentLabel(", …)`) نامرئی بود. اکنون پین‌های منفی **همیشه** با
   وضعیتِ «حاضر/غایب» گزارش می‌شوند (۱۴ مورد برای همین فایل).

`BUILTIN` هم کامل شد (`IntArray`, `Regex`, `RESULT_OK` و…)؛ پیش از آن اوراکلِ نوع سه توکنِ
حل‌نشدهٔ کاذب می‌داد و «سبز» بودنش نیاز به توضیحِ زبانی داشت. مُدِ تازهٔ `--duplicates`
اضافه شد: همهٔ تعریف‌های هم‌نام در پکیجِ اپ را می‌یابد و بدنه‌ها را (کامنت/تورفتگی/فضا
نرمال‌شده) گروه‌بندی می‌کند تا «یکسان ⇒ یکسان‌سازی امن» از «متفاوت ⇒ هرگز یکی نکن»
(درسِ `_now_str_with_seconds` در برابرِ `_now_str` در بک‌اند) به‌طورِ مکانیکی جدا شود.
نتیجهٔ آن برای هر ۷ نامِ کاندید: **هر کدام دقیقاً یک تعریف در کلِ اپ** ⇒ هیچ بدنهٔ
تکراریِ بین‌فایلی وجود نداشت و سؤالِ یکسان‌سازی اصلاً پیش نیامد.

دو دامِ محیطی هم ثبت می‌شود چون دوباره هزینه‌زا شدند:

- **`pytest` با مسیرِ نسبیِ بی‌پیشوند در این sandbox صفر تست جمع می‌کند.**
  `pytest Kharazmi_Server/tests -q` ⇒ «no tests collected / file or directory not found»،
  در حالی که `pytest ./Kharazmi_Server/tests -q` و مسیرِ مطلق ⇒ **۱۲۷۹ تست**. این در
  همان shell‌ی رخ داد که `ls -d Kharazmi_Server/tests` موفق بود، پس مشکلِ فایل‌سیستم نیست.
  CI (`.github/workflows/tests.yml:64`) همان شکلِ بی‌پیشوند را می‌زند و سبز است ⇒ **CI
  متأثر نیست**؛ فقط فرمانِ گیتِ محلی باید `./` داشته باشد.
- **`Kharazmi_Server` بین فرمان‌ها واقعاً ناپدید/پدیدار می‌شد** (۳۰ پیاپی probe = غایب،
  سپس ۲۴۰/۲۴۰ = حاضر). راهکارِ مؤثر: خواندن با تلاشِ مجدد و، در صورتِ شکست، افتادن به
  object storeِ git (`git cat-file -p HEAD:<dir>` سپس blob). پروسهٔ پس‌زمینه‌ای که
  `.venv` را می‌سازد هم در یکی از همین پنجره‌ها مرد؛ بازسازی با **فهرستِ صریحِ پکیج‌ها**
  (نه `-r requirements.txt`) انجام شد تا به فایلِ ناپایدار وابسته نباشد.

## ۵. راستی‌آزمایی

اوراکل‌ها (همه سبز، بدونِ توضیحِ استثنا):

| بررسی | نتیجه |
|---|---|
| round-trip کلمه‌به‌کلمه | **۴/۴** (بدنهٔ هر تابع عیناً در فایلِ مقصد) |
| `--types` / `--diff` | ۰ توکنِ حل‌نشده در هر سه فایل؛ **۰ تازه در برابرِ HEAD** |
| `--arity` | ۵۳ نقطهٔ فراخوانی سنجیده شد، **۰ ناهمخوانی** |
| `--members` | ۳۵/۳۵، ۳/۳، ۱/۱ امضایِ متمایز — **تکراری = none** |
| `--names` | `HEAD=403 → now=405`، born = `StudentProfileErrors`, `StudentProfileFormat`، **gone = none**، dup = none |
| `--pins` پس از ویرایش | **۲۴ سخت / ۱۲۷ نرم / ۱۴ منفی** — عیناً برابرِ پیش از ویرایش |

گیت‌ها:

| گیت | پیش | پس |
|---|---|---|
| `pytest ./Kharazmi_Server/tests` | ۱۲۷۹ passed | **۱۲۷۹ passed** (۱۱۱ ثانیه) |
| `pytest tests/route_audit` | ۲۴۹ passed | **۲۴۹ passed** |
| `find_dead_kotlin.py` | ۸ نماد / ۱۰۴ خط (DEFER) | **۸ / ۱۰۴** — بدونِ تغییر |
| `find_dead_resources.py` | ۰ مرده / ۱۸۴۲ تعریف | **۰ مرده / ۱۸۳۴ تعریف** (−۸ = همان رشته‌های حذف‌شده) |
| `validate_app_map.py` | exit 1، `server_map_exact=true`، extra = `attendance/live*` + `admin/live_sessions*` + … | **exit 1، بدونِ تغییر** (بدهیِ از پیش موجود) |
| `Kharazmi_Server/gaj_db.db` md5 | `f048f8d118b33c4eaa944490594121d7` | **بدونِ تغییر** |

دیفِ Activity **۸۱ خطِ حذف و ۸ خطِ اضافه** دارد و هیچ‌کدام از خطوطِ حذف‌شده شاملِ
`@GET|@POST|@PUT|@DELETE|@Path|@Body|.create(|RetrofitClient|interface` نیست ⇒ سطحِ
Retrofit دست‌نخورده ماند و بی‌تغییر بودنِ app-map از همین‌جا نتیجه می‌شود.

یک `gaj_db.db` **یتیم در ریشهٔ مخزن** توسط اجرای محلیِ `validate_app_map.py` ساخته شد
(untracked، و `.gitignore` هم نمی‌گیردش) و پیش از کامیت حذف گردید؛ پایگاهِ ردیابی‌شدهٔ
`Kharazmi_Server/gaj_db.db` دست‌نخورده است.

## ۶. وضعیتِ ماژول‌های بزرگ پس از این برش

`InvoiceActivity.kt` ۱۲۳۶ · **`StudentProfileActivity.kt` ۱۱۱۳** · `AppModels.kt` ۱۰۳۹ ·
`AttendanceActivity.kt` ۹۹۸ · `ClassDetailActivity.kt` ۹۲۶ · `TeacherProfileActivity.kt` ۷۹۰ ·
`MainActivity.kt` ۷۷۵. پکیجِ اپ: **۱۲۸ فایلِ `.kt`**.

بدهی‌های ثبت‌شده برای برش‌های بعد:

1. باگِ `isValidJalaliDate` (بندِ ۳) — منتظرِ تصمیم؛ یک برشِ رفتاریِ مستقل با تستِ خودش.
2. `StudentProfileRepository` به‌خاطرِ دیوارِ پین ممکن نیست (بندِ ۲)؛ برای صفحاتِ
   **بدونِ** پینِ شبکه — مثلِ `PendingClassesActivity` (۳ جایِ `create()`) و
   `ClassManagementActivity` (۳) — همچنان ممکن است و `TeacherProfileActivity` (۴) باید
   نخست نقشهٔ پین بگیرد.
3. اعضایِ privateِ مرده برای `find_dead_kotlin.py` نامرئی‌اند (فقط سطحِ بالا را می‌بیند).
   سه موردِ این برش دستی پیدا شدند؛ افزودنِ یک مُدِ «اعضایِ کلاس با صفر فراخوانی» به آن
   ابزار، باقیِ این دسته را در `InvoiceActivity` و `AttendanceActivity` روشن می‌کند.
