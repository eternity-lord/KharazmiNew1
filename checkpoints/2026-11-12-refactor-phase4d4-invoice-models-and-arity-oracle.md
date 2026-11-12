# P4d slice 4 — بیرون‌کشیدنِ مدل‌های فیش از `InvoiceActivity` + رفعِ نقطهٔ کورِ trailing-lambda در اوراکلِ arity

تاریخ: ۲۰۲۶-۱۱-۱۲ · شاخه: `arena/0fd4f09a-kharazminew1` · پایه: `a81f5cb`

این اسلایس دو تغییرِ **مستقل** دارد که ترتیبِ کشفشان هم آموزنده است: نخست یک نقص در
ابزارِ سنجش پیدا شد، و همان نقص نشان داد که تا پیش از رفعش، ریفکتورِ هدفِ این اسلایس
با دو شکستِ شبح‌وار دیده می‌شد.

---

## ۱) رفعِ نقطهٔ کورِ اوراکلِ `--arity`: فراخوانیِ با trailing lambda

### مشکل
`verify_kotlin_refactor.py` سایتِ فراخوانی را با `(?<![\w.])(\w+)\(` پیدا می‌کرد و
شمارِ آرگومان‌ها را از داخلِ پرانتز می‌گرفت. دو شکلِ رایجِ Kotlin نادیده گرفته می‌شدند:

| شکل | مثالِ واقعی در این مخزن | رفتارِ اوراکلِ قدیم |
|---|---|---|
| `f(a, b) { … }` | `showEnrollmentPickerDialog(name, active) { en -> … }` | ۲ آرگومان می‌شمرد در حالی که lambda سومی است ⇒ **مثبتِ کاذبِ ناهمخوانی** |
| `f { … }` | `ensureEnrollmentForSubmit { ok -> … }` | **هرگز دیده نمی‌شد** ⇒ تابعِ زنده «صفر فراخوانی» یعنی به‌ظاهر «مرده» |

شکلِ دوم خطرناک‌تر بود: در تحلیلِ مقدماتیِ همین اسلایس، `ensureEnrollmentForSubmit`
(۳۳ خط، منطقِ حلِ `enrollment_id` پیش از submit) با «فراخوانی=۰» گزارش شد و یک قدم
مانده بود به‌عنوانِ کدِ مرده حذف شود. فراخوانیِ واقعی‌اش با trailing lambda در فایل هست.

### راه‌حل
- `count_args` حالا `(شمارِ آرگومان‌ها, جایِ «)»)` برمی‌گرداند تا بتوان دید آیا
  بلافاصله بعدِ پرانتز یک `{` آمده (آن lambda یک آرگومانِ آخرِ واقعی است).
- `check_arity` یک **گذرِ دوم** برایِ شکلِ بدونِ پرانتز (`name { … }`) دارد.
- تشخیصِ «خودِ اعلام است نه فراخوانی» به یک `resolve()` مشترک منتقل شد تا هر دو گذر
  یک قضاوت کنند. این مهم است، چون در `private fun showEnrollmentPickerDialog(…,
  onPicked: (…) -> Unit) {` آن `{` **بدنهٔ تابع** است نه trailing lambda، و گذرِ دوم
  بدونِ این محافظ خودِ اعلام را فراخوانیِ یک‌آرگومانی می‌دید.

### شاهدِ A/B (نه استدلال، اندازه‌گیری)
اوراکلِ قدیم با `git stash` برگردانده شد و هر دو نسخه رویِ **یک ورودیِ یکسان**
(هر ۱۲۸ فایلِ `.kt` پکیج) اجرا شدند:

```
OLD oracle: 18 شکست      NEW oracle: 13 شکست
▶ رگرسیون از این تغییر: ۰
▶ رفع‌شده: ۵
   - AdminDashboardActivity.kt:148/151/154 downloadExport(1) ولی اعلام req=2 total=2
   - InvoiceActivity.kt:300 showEnrollmentPickerDialog(2) ولی اعلام req=3 total=3
   - InvoiceActivity.kt:701 showEnrollmentPickerDialog(2) ولی اعلام req=3 total=3
```

۱۳ شکستِ باقی‌مانده نویزِ از‌پیش‌موجودِ اجرایِ **کلِ کورپس** است (این حالت هیچ‌وقت
گیتِ ما نبوده؛ گیت رویِ مجموعهٔ فایل‌هایِ تغییریافته اجرا می‌شود): اعلام‌های
چندخطی که `signature_table` فقط خطِ نخستشان را می‌خواند ⇒ `req=0 total=0`،
اورلودهای بین‌فایلی، و امضایِ تکراریِ adapterها (`onCreateViewHolder` در دو کلاسِ
مختلفِ یک فایل).

---

## ۲) چرا از `InvoiceActivity` فقط مدل‌ها بیرون رفتند

`InvoiceActivity.kt` با ۱۲۳۶ خط بزرگ‌ترین ماژولِ باقی‌مانده بود. انتظارِ اولیه
«شکستنِ گام‌به‌گام» بود، ولی دیوارِ پین و زبانِ Kotlin هر دو سقف گذاشتند:

- **۳۱ عضو، که ۱۵ تایِ آن‌ها پینِ سخت دارند** (۲۵ سطرِ assertion در کورپسِ ۱۳ فایلِ
  تست / ۳۷ فایلِ `.kt`). بخشی از این پین‌ها خودِ **متنِ امضا** هستند
  (`'private fun sendData('`، `'private fun renderClassStatus('`،
  `'private fun receiptHtmlExtraRows('`) و بخشی **literalهایِ سطحِ فایل**
  (`R.id.btnRegisterAgain` و `dialog_remittance_success` از
  `test_group3_teacher_ui_access.py:101-105`، `unpaid_session_items`، `delay(`،
  `clearByPrefix(this@InvoiceActivity, "class_report")` از
  `test_android_resources_static.py:612-614`). یعنی این اعضا نه‌تنها نمی‌توانند
  جابه‌جا شوند، **متن‌شان هم باید در همین فایل بماند** ⇒ delegatorِ نازک جواب نمی‌دهد.
- **همهٔ فیلدهایِ view از نوعِ `private lateinit var`** هستند. در Kotlin یک extension
  function در فایلِ دیگر به عضوِ `private` دسترسی ندارد، پس هیچ عضوِ UI-coupled بدونِ
  تغییرِ معماری (لایهٔ ViewModel یا internal‌کردنِ فیلدها) بیرون نمی‌رود. از ۱۶ عضوِ
  بدونِ پین، فقط `serverDetail` (۸ خط) و `setupApi` (۴ خط) خالص‌اند.

پس تنها انتقالِ امن، **۴ مدلِ سطحِ بالا** بود:

| مدل | مصرف‌کننده |
|---|---|
| `PrintReceiptRequest` | `InvoiceActivity`، `RemittancePrintApi` |
| `PrintReceiptResponse` | `RemittancePrintApi` |
| `PdfReceiptResponse` | `RemittancePrintApi` |
| `ReceiptDetailsResponse` | `InvoiceActivity` (`lastReceipt`)، `ReceiptDetailsApi` |

چون این مدل‌ها بینِ سه مصرف‌کننده مشترک‌اند، در فایلِ تازهٔ **`InvoiceModels.kt`**
گذاشته شدند (هم‌راستا با سابقِ `AppModels.kt`) نه کنارِ یکی از APIها — تا اگر روزی
`RemittancePrintApi` (که در فهرستِ ۸ نمادِ مردهٔ DEFER است) حذف شد، جایِ مدل‌ها
تکان نخورد.

### نتیجهٔ عددی
`InvoiceActivity.kt`: **۱۲۳۶ → ۱۱۸۶ خط** (−۵۰) = −۴۶ خطِ مدل‌ها و −۴ خطِ importِ مرده.
`InvoiceModels.kt`: ۶۱ خط (۱۵ خط توضیح + ۴۶ خطِ بدنهٔ عیناً منتقل‌شده).

---

## ۳) شواهدِ ایمنی (اندازه‌گیری، نه ادعا)

**اوراکل‌ها** رویِ مجموعهٔ تغییریافته:
```
[types]   InvoiceActivity.kt: حل‌نشده=2 تازه-دربرابر-HEAD=0 OK
[types]   InvoiceModels.kt: فایلِ تازه — 0 توکنِ حل‌نشده []
[arity]   37 نقطهٔ فراخوانی سنجیده شد، 0 ناهمخوانی
[members] InvoiceActivity.kt: 31 عضو، 31 امضایِ متمایز، تکراری=none
[names]   HEAD=406 now=406 born=[] gone=none dup=none
[pins]    InvoiceActivity.kt (granularity=member): سخت=25 نرم=155 منفی=14
```
سطرِ `[names]` مهم‌ترین شاهدِ این اسلایس است: ۴ نامِ سطحِ بالا **جابه‌جا** شدند ولی
مجموعهٔ نام‌ها ۴۰۶ → ۴۰۶ ماند، هیچ نامِ تازه‌ای زاده نشد و **هیچ تکراری** پدید نیامد.

**چرا تستِ قراردادِ route_audit نمی‌شکند:**
`tests/route_audit/kotlin_contract.py::discover_models(root=ANDROID_SRC)` با
`root.rglob("*.kt")` اسکن می‌کند و کلیدِ خروجی‌اش **فقط نامِ کلاس** است
(`found[match.group(1)] = fields`)؛ مسیرِ فایل تنها در `KotlinField.source` نگه داشته
می‌شود و `test_infrastructure.py:71-77` فقط `issue.field`/`issue.kind` را می‌سنجد.
پس انتقالِ `ReceiptDetailsResponse` به فایلِ دیگر، کشفِ قرارداد را تغییر نمی‌دهد —
به شرطِ **move نه copy** (دو اعلامِ هم‌نام بی‌صدا باعثِ «برنده شدنِ» مسیرِ دوم در
`sorted(root.rglob(...))` می‌شد).

**گیت‌ها (همه رویِ درختِ نهایی):**
```
backend      1279 passed, 2 warnings in 133.32s
route_audit   249 passed, 2 warnings
find_dead_kotlin      بدونِ تغییر (همان ۸ نمادِ DEFER / ۱۰۴ خط)
find_dead_resources   جمعِ منابعِ مرده = 0
validate_app_map      server_map_exact=True · server_runtime_count=221 ·
                      android_only_routes=0  (exit=1 از پیش موجود، در هیچ workflow نیست)
gaj_db.db             md5 = f048f8d118b33c4eaa944490594121d7 (بی‌تغییر)
                      git hash-object = ead925c902fc44c451bbc6d9d884488df3bb4dfe = blobِ HEAD
android.yml           YAML سالم · ۱۲ گام · validate-wrappers: true · بدونِ gradle-version
```

---

## ۴) دام‌هایی که این اسلایس ساخت یا لو داد

1. **«فراخوانی=۰» در Kotlin هرگز به‌تنهایی یعنی «مرده».** شمارشِ `name\s*\(` شکلِ
   trailing lambda را نمی‌بیند. پیش ازِ هر حکمِ مرگ، `grep -n "NAME"` رویِ کلِ درخت
   (شاملِ `.xml` برایِ `android:onClick`) لازم است.
2. **`--pins --granularity top` مثبتِ کاذبِ انبوه می‌سازد** و دوباره تأیید شد: برایِ
   همین فایل، `top` **۱۹۸ پینِ سخت** گزارش کرد و هر literal را به **همهٔ** بلوک‌هایِ
   سطحِ بالا نسبت داد (حتی `'private fun sendData('` ← بلوکِ `PrintReceiptRequest`).
   دانه‌بندیِ معتبر فقط `member` است.
3. **`(?<![\w.])` خودِ خطِ import را رد می‌کند** چون کاراکترِ پیش ازِ نماد `.` است؛
   با کسرِ «یکی برایِ خودِ import» به عددِ **−۱** رسیدم که بی‌معنا بود. برایِ سنجشِ
   مرگِ یک import باید **نشانِ مصرف** را شمرد (`@POST\b`) نه نامِ نماد را.
   نتیجهٔ درست: هر چهار `import retrofit2.http.{Body,POST,GET,Path}` در
   `InvoiceActivity.kt` **پیش ازِ این اسلایس** مرده بودند (ماندهٔ بیرون‌کشیدنِ
   interface‌ها به `ApiInterfaces.kt` در slice 1) و فقط `retrofit2.HttpException`
   با ۶ مصرف زنده است. هیچ تستی هم به `retrofit2.http` ارجاع نمی‌دهد، پس حذفشان
   در همین اسلایس انجام شد و اینجا مستند می‌شود (پاک‌سازیِ بی‌صدا نیست).
4. **`&&` بعدِ فرمانی که ممکن است غیرِصفر بدهد، بقیهٔ کار را بی‌صدا حذف می‌کند.**
   دو بار اتفاق افتاد: `ls -d "$A" && for …` کلِ گیتِ A را رد کرد، و
   `ls checkpoints/ | grep -c phase4d4` (صفر ⇒ exit 1) بقیهٔ رشتهٔ تشخیص‌ها را
   نگه داشت. جداکنندهٔ درست `;` است.
5. **flapِ فایل‌سیستم و اینکه چرا `os.path.isdir` راهِ چاره نیست.** پوشهٔ
   `KHarazmi_Server/tests` دقیقه‌ها برایِ `ls`، `pytest`، `md5sum` و Python ناپدید
   بود در حالی که `stat` آن را `directory 4096 bytes` گزارش می‌داد. دلیلِ پیامِ
   گمراه‌کنندهٔ pytest در سورسِ 9.2 پیدا شد (`_pytest/main.py:1174`): آرگومان از
   `absolutepath()` و `safe_exists()` رد می‌شود و `safe_exists` هر `OSError` را
   **بی‌صدا به `False`** ترجمه می‌کند. در همان لحظه‌ها `opendir` سالم بود و `stat`
   رویِ فایل‌هایِ داخلِ پوشه هم. حتی دیده شد که `[ -f FILE ]` موفق است و `md5sum`
   همان مسیر در همان ثانیه شکست می‌خورد ⇒ **دیدِ فایل‌سیستم بینِ فرآیندها یکسان
   نیست**؛ برایِ هر ادعا دو شاهدِ مستقل بگیر (اینجا `cat | md5sum` و
   `git hash-object` در برابرِ blobِ HEAD).
6. **`git ls-files` در بازهٔ flap صفر می‌دهد در حالی که `git ls-tree HEAD` کامل است**
   ⇒ از یک ابزارِ تنها نباید نتیجهٔ «فایل‌ها گم شدند» گرفت.
7. **xargs بدونِ `-r` با ورودیِ خالی، فرمان را یک‌بار بی‌آرگومان اجرا می‌کند.**
   وقتی `glob` در لحظهٔ flap هیچ فایلی ندید، فهرست خالی شد و
   `xargs -a list .venv/bin/python -m pytest -q` عملاً **بی‌آرگومان** دوید. نتیجه
   درست از آب درآمد (pytest از `testpaths` کلِ کورپس را جمع کرد) ولی این را
   **فرض نکردم**؛ با `--collect-only` اثبات شد: `1279 tests collected`،
   `rootdir: /home/user/KharazmiNew1`، `configfile: pytest.ini`،
   `testpaths: KHarazmi_Server/tests`، و صفر سطرِ error در لاگِ گیت.
   درس: اگر به فهرستِ فایل نیاز داری، `xargs -r` بگذار و پس ازِ ساختِ فهرست
   تعدادش را assert کن.
8. **هر فراخوانیِ bash پوستهٔ تازه است؛ `export`ها نمی‌مانند.** یک
   `--collect-only` بدونِ `JWT_SECRET_KEY` اجرا کردم و «۷۰ خطایِ جمع‌آوری» گرفت.
   آن شاهدِ نامعتبر بود، نه نشانهٔ خرابیِ گیتِ A. محیطِ لازم:
   `JWT_SECRET_KEY` + `DATABASE_URL`.
9. **کامیتِ push‌نشده با تعویضِ شاخه از دست می‌رود؛ کامیتِ push‌شده نه.** پس ازِ
   بسته‌شدنِ دسترسیِ remote (چون PR #18 از شاخهٔ پیشین merge شده بود) و زدنِ
   Continue، نشست با یک **cloneِ تازه** از `a81f5cb` بالا آمد: `git reflog` فقط
   `clone` و `branch: Created from …` داشت، `git fsck --unreachable` خالی بود و هر
   سه کامیتِ محلی (`655b479`، `7678ec3`، `1f2ea02`) از آبجکت‌استور رفته بودند؛
   درختِ کار هم به حالتِ پیش ازِ اسلایس برگشت (jar = ۴۲۶۱۳ بایتِ قدیمی).
   **بازیابی:** آن یکی کامیت که push شده بود رویِ remote زنده بود —
   `git ls-remote origin` نشانش داد و
   `git fetch origin arena/5a940580-kharazminew1` + `git cherry-pick FETCH_HEAD`
   بدونِ هیچ تعارضی برگرداندش (شاخهٔ قدیمی را checkout نکردم؛ فقط آبجکتش را
   آوردم). دو کامیتِ دیگر از رویِ دستورِ مستندشان بازسازی شدند و همین A/B و
   اوراکل‌ها دوباره همان عددها را دادند.
   ⇒ **قاعدهٔ عملی: پیش ازِ هر تعویضِ شاخه، کار را push کن**؛ و اگر نشد،
   `git ls-remote` نخستین جایی است که باید نگاه کرد.

---

## ۵) بدهیِ باقی‌مانده (عمداً دست‌نخورده)

- `KHarazmi_Server/tests/test_e2e_finance_installments_invoice.py:12` یک **کامنتِ
  نگاشتِ خط‌شمار** دارد: `InvoiceActivity.kt:57-82 → GET finance/receipt/{transaction_id}`.
  پس ازِ انتقالِ مدل‌ها آن بازهٔ خطی کهنه است. چون `KHarazmi_Server/tests/` طبقِ
  قانونِ این فاز **دست‌نخورده** می‌ماند، کامنت اصلاح نشد و کهنه‌بودنش اینجا ثبت می‌شود.
- `InvoiceActivity.serverDetail` و `StudentProfileErrors.extractServerDetail` **عمداً
  یکی نشدند**: اولی فقط `HttpException` را می‌گیرد و فقط `detail` را برمی‌گرداند،
  دومی `Exception` را می‌گیرد و بعدِ `detail` به `message` هم می‌رسد. یکسان‌سازیِ
  این دو، رفتارِ نمایشِ خطا را در دو صفحه عوض می‌کرد (همان درسی که از
  `_now_str_with_seconds` در برابرِ `_now_str` گرفته شد).
- کوچک‌کردنِ بیشترِ `InvoiceActivity` (هنوز ۱۱۸۶ خط) به **لایهٔ ViewModel** نیاز
  دارد، نه به جابه‌جاییِ تابع: ۱۵ عضوِ پین‌شده و همهٔ فیلدهایِ `private lateinit var`
  راهِ انتقالِ بدونِ تغییرِ معماری را بسته‌اند.
- `ApiInterfaces.kt` ممکن است importهایِ مردهٔ مشابه داشته باشد؛ در این اسلایس
  بررسی نشد.
