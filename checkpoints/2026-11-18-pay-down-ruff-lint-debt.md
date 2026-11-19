# ۲۰۲۶-۱۱-۱۸ — پرداختِ بدهیِ lintِ پایتون (۲۵۰ → ۸۷)

برشِ پیش (PR #29، در `main` با merge commit ‏`548b5be211b8`) نقطهٔ کورِ محیطیِ گیتِ
کیفیت را بست. آن حصار فقط **بدتر نشدن** را تضمین می‌کند؛ یعنی عددِ ۲۵۰ خطایِ ruff و
۷۲۵ خطایِ mypy را منجمد می‌کند ولی هیچ‌کس را وادار به پرداختنش نمی‌کند. این برش
همان بدهیِ ruff را می‌پردازد — با witness رفتار، نه با `--fix` کور.

---

## ۱) چرا این برش لازم بود

گیتِ کیفیت از برشِ PR #28 وجود دارد و کارش را درست انجام می‌دهد: یک commit نمی‌تواند
بی‌صدا ده‌ها خطایِ تازه اضافه کند. ولی «بدتر نشود» یک خاصیتِ ناخواسته هم دارد — عددِ
بالا را **قانونی** می‌کند. `baseline` همان ۲۵۰ را ثبت کرده بود و تا ابد همان‌جا
می‌ماند، مگر اینکه کسی جدا بپردازد.

خطرِ واقعی در سه شناسه بود که اصلاً ظاهری نیستند:

- **B905 (‏۲۷ مورد)** — ‏`zip()` بدونِ `strict=`. در پایتونِ ۳.۱۰+ این یک تصمیمِ
  پنهان است: اگر دو دنباله هم‌اندازه نباشند، بی‌صدا کوتاه‌ترین را می‌گیرد. یعنی یک
  سطرِ داده یا بی‌صدا **گم** می‌شود یا بی‌صدا `None` می‌گیرد.
- **F841 (‏۳۱ مورد)** — انتسابِ مرده. بیشترش بی‌ضرر است، ولی چند مورد یا فراخوانیِ
  دارایِ side-effect بودند (حذفِ خط ⇒ حذفِ کارِ واقعی) یا **باگِ واقعیِ دامنه**
  (یک نام خوانده می‌شود که هرگز انتساب نگرفته).
- **E722 (‏۱۰ مورد)** — ‏`except:` برهنه، که `KeyboardInterrupt` و `SystemExit` را هم
  می‌بلعد. در مسیرِ dunning و timeline یعنی Ctrl-C روی اسکریپتِ یادآوری هم بلعیده
  می‌شد.

پس این برش «آرایشِ عدد» نیست: سه دسته از این‌ها **درست‌بودنِ رفتار** را لمس می‌کنند.

---

## ۲) چه پاک شد

`ruff 0.17.4` رویِ کلِ ریپو، پیش و پس (همان فرمانی که گیت اجرا می‌کند):

| | پیش | پس | Δ |
| --- | --- | --- | --- |
| خطایِ ruff | ۲۵۰ | **۸۷** | −۱۶۳ |
| شناسهٔ متفاوت | ۲۷ | **۱۱** | −۱۶ |
| خطایِ mypy | ۷۲۵ | **۷۱۹** | −۶ |
| جمعِ گیت | ۹۷۵ | **۸۰۶** | −۱۶۹ |

تفکیک بر حسبِ شناسه (۱۶ شناسه کاملاً ناپدید شد):

| شناسه | پیش | پس | یادداشت |
| --- | --- | --- | --- |
| E701 | ۵۷ | ۳ | چند عبارت رویِ یک خط (`:`) — باقی‌مانده در پوشهٔ ممنوعه |
| B905 | ۲۷ | **۰** | `zip(..., strict=…)` — همه |
| F841 | ۳۱ | ۸ | انتسابِ مرده — همه در ناحیهٔ مجاز |
| E702 | ۲۳ | ۷ | چند عبارت رویِ یک خط (`;`) — باقی‌مانده در پوشهٔ ممنوعه |
| E722 | ۱۰ | **۰** | ‏`except:` → `except Exception:` |
| B007 | ۶ | ۱ | متغیرِ بی‌استفادهٔ حلقه → پیشوندِ `_` |
| SIM102 | ۱۱ | ۶ | ‏`if` تودرتو — ۶ مورد مانده عمدی است (بندِ ۶) |
| RUF013 | ۳ | **۰** | پارامترِ `= None` بدونِ `Optional` |
| SIM103 | ۳ | **۰** | ‏`if …: return False / return True` |
| C401 | ۲ | **۰** | ‏`set(gen)` → comprehension |
| E731 | ۲ | **۰** | ‏`lambda` انتسابی → `def` |
| RUF021 | ۲ | **۰** | اولویتِ `and`/`or` بدونِ پرانتز |
| SIM108 | ۴ | ۲ | ‏`if/else` → ternary (۲ مانده در پوشهٔ ممنوعه) |
| C416 / RET501 / RET503 / RUF019 / RUF046 / SIM110 / SIM300 / UP035 / W292 | ۱ | **۰** | هر کدام یک مورد |

بر حسبِ ناحیه:

| ناحیه | پیش | پس |
| --- | --- | --- |
| A — ‏`tests/route_audit/` | ۱۰۰ | **۰** |
| B — ‏`Kharazmi_Server/` (بیرونِ tests) | ۷۸ | ۱۸ |
| C — ‏`Kharazmi_Server/tests/` (**ممنوعه**) | ۶۹ | ۶۹ (دست‌نخورده) |
| D — ‏`scripts/` ریشه | ۳ | **۰** |

`mypy` هم شش خطا کم شد، بدونِ اینکه مستقیماً سراغش بروم — اثرِ جانبیِ پاک‌سازیِ
ruff بود: ‏`assignment` ۲۰۶→۲۰۳، ‏`arg-type` ۲۳۹→۲۳۷، ‏`union-attr` ۵۹→۵۸. آن یک
موردِ `union-attr` دقیقاً همان `session.user_id` است که در بندِ ۴ توضیح داده شده.

`scripts/python-quality-baseline.json` با `--write-baseline` تازه شد:
fingerprint ‏`427444bccb` → **`59a6c3279a`**. گیت روی baselineِ تازه
`delta +0` و exit 0 می‌دهد.

---

## ۳) سه رگرسیون که خودِ حصارها گرفتند

ارزشِ این بخش از عددها بیشتر است: هر سه خطایِ زیر را **من** در میانهٔ کار ساختم و
هر سه را یک شاهد گرفت، نه تستِ رفتار.

### ۳٫۱) ‏`--fix` کور رویِ W293 دو فایلِ تولید را خراب کرد

نخستین پاسِ قالب‌بندی «خطِ خالیِ دارایِ فضایِ سفید را پاک کن» را رویِ همهٔ W293ها
اجرا کرد. ولی ۱۲ موردِ این ریپو درونِ **رشتهٔ سه‌نقلوییِ قالبِ HTML** است (صفحهٔ
`routers/parent.py` و `routers/reports.py`) — یعنی آن فضایِ سفید بخشی از متنِ
خروجیِ کاربر است، نه بدهیِ قالب‌بندی.

آنچه نجات داد: یک manifest از `sha256(ast.dump(ast.parse(src)))` برایِ **همهٔ ۲۲۵
فایلِ پایتونِ ریپو**، پیش از هر ویرایش. پس از پاس، دو فایل درختِ عوض‌شده داشتند ⇒
خودکار برگردانده شدند. شاهدِ نهایی همان پاس: ‏۲۲۵ فایل، ۹ فایل با تغییرِ بایت،
**صفر** درختِ عوض‌شده.

این ناوردایی حالا به‌شکلِ تست قفل شده است (بندِ ۵).

### ۳٫۲) تطبیقِ «سوزنِ متنی» یک F821 زنده ساخت

‏`routers/audit.py` **دو** خطِ بایت‌یکسان داشت:

```python
txn_map = {t.id: t for t in deleted_txns}
```

یکی در `get_suspicious_patterns` (که بعداً **خوانده** می‌شود) و یکی در
`count_suspicious_patterns` (که هرگز خوانده نمی‌شود). fixerِ من با شمارشِ «دقیقاً یک
تطبیق» کار می‌کرد؛ پس از حذفِ اولی، assert ثانیه‌ها بعد **پاس** شد و دومی — همان که
زنده بود — حذف شد. نتیجه یک `NameError` در زمانِ اجرا.

آنچه نجات داد: دو شاهد که هیچ‌کدام تستِ رفتار نبودند:

```
ruff check . --select F821,F822,F823     # ← تنها چیزی که گرفت
git diff -U0                              # ← دیدنِ آنچه واقعاً حذف شده
```

گیت‌هایِ ۱۲۷۹ و ۳۳۸ **این را نگرفتند**: هر دو در همان وضعیت سبز شدند، چون هیچ تستی
آن شاخهٔ خاصِ `audit.py` را با دادهٔ لازم صدا نمی‌زند.

درسِ ثبت‌شده: حذفِ انتسابِ «مرده» باید با **شمارشِ خوانده‌ها در هر تابع به‌شکلِ
جدا** تصمیم گرفته شود، و `--select F821,F822,F823` باید پس از هر ویرایش اجرا شود.
فایل با `git checkout --` برگردانده و کار با روشِ درست تکرار شد.

### ۳٫۳) شمارهٔ خطِ کهنه، و یک `assert` که کارش را کرد

یک پاسِ دیگر با شمارهٔ خطِ یک اجرایِ ruffِ **قدیمی‌تر** کار می‌کرد. پاسِ مرحلهٔ ۱ یک
خط را در `routers/dunning.py:143` شکسته بود، پس هدفِ F841 از ۳۷۲ به ۳۷۱ رفته بود.
نتیجه: `AssertionError` در `dunning.py:372` — **پیش از هر نوشتن**.

و یک موردِ دیگر: `services/transaction_admin.py` سه خطِ یکسان داشت؛ `assert` با پیامِ
«۳ تطبیق، انتظار ۱» اجرا را متوقف کرد. وسوسه این است که چنین assertی را «سهل» کرد
(حذفِ همهٔ تطبیق‌ها)؛ آن دقیقاً همان کاری است که در ۳٫۲ فاجعه ساخت.

---

## ۴) تصمیم‌هایی که رفتار را عوض می‌کنند

این‌ها تنها مواردی هستند که «پاک‌سازیِ lint» در آن‌ها **معنا** دارد. بقیهٔ ۱۴۵ مورد
هم‌ارزِ نحوی‌اند.

### ۴٫۱) ‏`B905`: کدام `strict`؟

‏`strict=True` در ۲۶ مورد و `strict=False` در **یک** مورد. معیار: آیا هم‌اندازه بودنِ
دو دنباله در آن نقطه **قابلِ اثبات** است؟

- `tests/route_audit/**` — هفت کپیِ `_restore_tables` ‏`key` را از `key_indexes`
  (به طولِ `len(primary_keys)`) و `row` را از `dict(zip(column_names, row))` رویِ همان
  جدول می‌سازند ⇒ هم‌اندازه به‌طورِ ساختمانی.
- ‏`scripts/generate_route_audit_docs.py:139` زیرِ
  `if len(route_parts) != len(literal_parts): return False` است ⇒ اثبات‌شده.
- ‏`tests/route_audit/test_audit_timeline.py:530,550` ‏`range(20, 0, -1)` را با یک
  `expected_days` بیست‌عضوی zip می‌کند ⇒ اثبات‌شده.
- **تنها استثنا:** ‏`push_service.py:155` ‏`zip(batch, per_token)` داخلِ تابعی است که
  قراردادش «هرگز caller را نشکن» است (`except` پهن، `result.errors`،
  `logger.warning`). آنجا `strict=True` یک استثنایِ تازه به مسیرِ push اضافه می‌کرد ⇒
  `strict=False` یعنی رفتارِ پیشین عیناً حفظ شود.

شاهد: ‏`ast.dump` یک کپیِ عمیق، پس از پاک‌کردنِ همهٔ keywordهایِ `strict=`، با
`ast.dump` پیش از ویرایش مقایسه شد ⇒ تنها تفاوتِ مجاز همان keyword است.

### ۴٫۲) ‏`F841`: سه دسته، سه تصمیم

**(الف) فراخوانی دارایِ side-effect — انتساب حذف، فراخوانی ماند:**

| محل | خط |
| --- | --- |
| ‏`routers/homework.py` | ‏`validate_file(file)` (اعتبارسنجی باید اجرا شود) |
| ‏`services/session_submission.py` ×۲ | ‏`_upsert_attendance_row(...)` (نوشتنِ سطرِ حضور) |
| ‏`scripts/run_financial_audit.py` ×۴ | ‏`res_s1/res_s2/res_s3/res_settle` (خودِ ممیزی) |

هر کدام یک کامنتِ توضیحی گرفت که چرا نتیجه دور ریخته می‌شود. برایِ
`_upsert_attendance_row` تأیید شد `\batt\b` در هیچ‌جایِ دیگرِ فایل نمی‌آید.

**(ب) انتسابِ مردهٔ واقعاً مرده — کلِ خط حذف شد:**
‏`routers/reports.py` ‏`month_prefix/year_prefix`، ‏`routers/dunning.py`
‏`today_jalali`، ‏`routers/parent.py` و `routers/students.py` ‏`w_t/w_i`،
‏`services/transaction_admin.py` ‏`final_w_t/final_w_i` (سه بلوک — pyflakes فقط
**آخرین** انتسابِ مردهٔ هر دامنه را گزارش می‌کند، پس fixer باید حلقهٔ
fixpoint باشد و هر دور ruff را دوباره اجرا کند)، ‏`scripts/run_sec1_auth_curl_tests.py`
‏`sec_token` (باقی‌ماندهٔ سناریویی که هرگز نوشته نشد — کلِ ۸۲ خطِ فایل خوانده شد)،
‏`scripts/validate_app_map.py` ‏`out = []`، و سه مورد در ناحیهٔ A
(‏`log_ids`، ‏`old_active`، ‏`old_mobile`؛ پوششِ تست دست‌نخورده — `finally` همان
جدول‌ها را برمی‌گرداند).

**(ج) یک مورد که یک باگِ واقعی بود:** ‏`routers/calendar.py`
‏`user_id = session.user_id`. حذفِ این انتساب رفتار را **بهتر** می‌کند: اگر `session`
هیچ `user_id` نداشته باشد، پیش‌تر یک `AttributeError` ⇒ ۵۰۰ بود؛ حالا همان مسیری
می‌رود که `check_user_login` (‏`dependencies.py:376-396`) از قبل برایش ۴۰۱
می‌فرستد. این تنها `union-attr` است که در mypy هم کم شد.

**(د) یک مورد که باگ **نیست** و دستِ محتوا نخورد:** ‏`today_summary.py` در
حلقهٔ `for course, teacher in …` از `course` استفاده نمی‌کند، ولی `Course` برایِ join
به `Teacher` لازم است و **جایِ چندگانه‌اش** معنا دارد. پس فقط نام عوض شد
(‏`_course`)، نه ساختار.

### ۴٫۳) ‏`E722`: تنگ‌کردنِ عمدی

ده مورد در `routers/dunning.py` (۱۲۹، ۱۴۹، ۳۵۵) و `routers/timeline.py` (۲۹، ۷۷،
۸۰، ۲۱۱، ۲۳۱، ۲۷۵، ۲۹۱) به `except Exception:` تبدیل شد. این **یک تغییرِ رفتاریِ
عمدی** است: از این پس `KeyboardInterrupt` و `SystemExit` به بیرون منتشر می‌شوند.
هر دو مسیر یا اسکریپتِ زمان‌بندی‌شده است یا حلقهٔ پردازشِ دسته‌ای؛ بلعیدنِ Ctrl-C در
آن‌ها باگ است، نه محافظت.

### ۴٫۴) ‏`UP035` در `main.py`: چرا حذفِ کلِ import امن بود

‏`main.py` در `per-file-ignores` یک استثنا برایِ F401 دارد، چون عمداً
`resolve_existing` و `auto_patch_database` را re-export می‌کند و تست‌ها
`main.resolve_existing` را صدا می‌زنند. پس حذفِ بی‌ملاحظهٔ importها می‌توانست رفتار را
بشکند. قبل از دست‌زدن، دو جست‌وجو انجام شد:

```
grep -rn "from main import"            → همه فقط `app` (۴۷ مورد)
grep -rnE "main\.(List|Optional|Union)" → هیچ
```

و `List`/`Optional`/`Union` هر سه **فقط** در همان خطِ import آمده بودند ⇒ کلِ خطِ
`from typing import …` حذف شد. استثناهایِ F401 سرِ جایِ خودشان ماندند.

### ۴٫۵) یک `SIM114` که خودِ fixer ساخت

‏`--fix --unsafe-fixes` رویِ SIM102 دو شاخهٔ هم‌بدن در
`services/session_submission.py:448` ساخت:

```python
if item.status in ["Present", "Late"]:
    should_charge = True
elif item.status == "Absent" and course.rule_calc_absent and not excused_val:
    should_charge = True
```

که خودش یک خطایِ تازه (SIM114) است. ادغام شد:

```python
if item.status in ["Present", "Late"] or (
    item.status == "Absent" and course.rule_calc_absent and not excused_val
):
    should_charge = True
```

درس: پس از هر پاسِ خودکار، **هیستوگرامِ شناسه‌ها** را پیش و پس مقایسه کن، نه فقط
جمع را. جمع از ۶۰ به ۳۶ افتاده بود و همه خوشحال بودند؛ یک شناسهٔ تازه زیرِ آن
پنهان بود.

---

## ۵) شاهدِ تازه: هر W293ِ باقی‌مانده محتوایِ رشته است

‏`tests/route_audit/test_python_quality_gate.py` یک تست گرفت
(‏`test_every_whitespace_only_line_lives_inside_a_multiline_string`) که با
`tokenize` دامنهٔ همهٔ رشته‌هایِ چندخطیِ ریپو را می‌گیرد و می‌آزماید **هیچ** خطِ
غیرتهیِ کاملاً فضایِ سفید بیرونِ آن دامنه‌ها نیست.

اندازه‌گیریِ واقعی: ‏۲۲۵ فایلِ پایتون، ۱۲ خطِ فضایِ سفید — هر ۱۲ داخلِ رشته،
**صفر** در کد.

دو نکتهٔ طراحی:

- شاهد عمداً **همهٔ** ‏`*.py` ریپو را می‌بیند، نه فقط آن‌چه lint می‌شود. پوشهٔ
  ‏`checkpoints/`، ‏`docs/` و درختِ اندروید از lint بیرون‌اند
  (‏`extend-exclude`) ولی این ناوردایی برایِ آن‌ها هم می‌ارزد.
- فایلِ **پارس‌نشدنی** هم رد می‌شود، نه اینکه بی‌صدا بگذرد — همان قاعدهٔ سراسریِ
  گیت‌هایِ این ریپو («خواندنِ ناموفق هرگز پاک گزارش نمی‌شود»).

اثباتِ دندان (نه حدس): یک فایلِ کاوشگرِ موقت با یک خطِ `"   "` در کد ساخته شد ⇒ شاهد
قرمز شد و همان فایل و شمارهٔ خط را نام برد:

```
AssertionError: … [('scripts/_w293_tooth_probe.py', 2, "'   '")]
```

کاوشگر پاک شد ⇒ شاهد دوباره سبز. هیچ ردی از کاوشگر در `git status` نماند.

---

## ۶) چیزی که عمداً تغییر نکرد

| مورد | شمار | چرا |
| --- | --- | --- |
| ‏`Kharazmi_Server/tests/` | ۶۹ | بیرونِ دامنهٔ این برش. پس از هر پاس تأیید شد که `git status` هیچ فایلی از آن پوشه را نشان نمی‌دهد |
| W293 | ۱۲ | محتوایِ رشتهٔ قالبِ HTML است (بندِ ۳٫۱). پاک‌کردنش صفحهٔ رندرشده را عوض می‌کند |
| SIM102 | ۶ | پنج مورد در `routers/audit.py` و یکی در `routers/dunning.py`. بدنهٔ هر کدام **کامنتِ فارسیِ توضیحی** دارد که با ادغامِ `if`ها یا گم می‌شود یا بی‌معنا می‌شود؛ خودِ ruff هم برایِ همین fix نمی‌دهد |
| mypy | ۷۱۹ | بدهیِ نوع‌نویسی یک برشِ جداست. این برش فقط شش مورد را به‌شکلِ اثرِ جانبی کم کرد |
| درختِ اندروید (‏`.kt`) | — | هیچ ابزارِ Kotlin/Android در این محیط نیست (`java`، `javac`، `gradle`، `kotlinc` همه غایب). ریفکتورِ `AttendanceActivity.kt` بدونِ کامپایل‌کنندهٔ محلی **قابلِ تأیید نیست** و عمداً انجام نشد |

---

## ۷) باتریِ پذیرش

همه با روالِ همان گام‌هایِ CI (نه یک اجرایِ دلخواهِ محلی):

| بررسی | نتیجه |
| --- | --- |
| ‏`pytest Kharazmi_Server/tests -q` (گامِ CI) | **۱۲۷۹ passed** در ۱۰۶٫۶ ثانیه |
| اجرایِ سوئیت از **داخلِ** پوشهٔ سرور (گاردِ B1) | **۳۱ passed** |
| ‏`scripts/validate_app_map.py --gate` | **OK** — ‏`android_only_routes: 0`، ‏`server_map_exact: true`، ‏`server_runtime_count: 221`، exit 0 |
| ‏`scripts/python_quality_gate.py --table --check` | exit **0**، ‏`806 = baseline 806 \| delta +0`، ‏`environment: 13 required distributions installed` |
| ‏`pytest tests/route_audit -q` | **۳۳۸ passed** (۳۳۷ + شاهدِ تازه) |
| ‏`test_python_quality_gate.py` به‌تنهایی | **۵۳ passed** (۵۲ + ۱) |
| ‏`ruff --select F821,F822,F823` | **All checks passed!** |
| گاردِ md5 دیتابیسِ واقعی | پیش = پس = ‏`f048f8d118b33c4eaa944490594121d7` ⇒ دست‌نخورده |
| ممیزیِ املایی (‏۵۶۸ فایلِ کد) | ‏`bad: none` |
| شاهدِ بدهیِ خودساخته | صفر خطِ فقط-فضایِ-سفیدِ افزوده، صفر کامنتِ ستونِ صفرِ افزوده |

دربارهٔ `--gate` قراردادِ مسیر: این گام عمداً اجرا شد چون اصلاحِ RUF013 در
`routers/reports.py` **امضایِ پارامترِ یک مسیرِ FastAPI** را عوض کرد
(‏`start_date: str = None` → `str | None = None`) و annotation دقیقاً همان چیزی است
که سطحِ OpenAPI از آن ساخته می‌شود. ‏`server_runtime_count: 221` و
`server_map_exact: true` تأیید می‌کنند که سطحِ زنده تکان نخورده است.

---

## ۸) بدهیِ باقی‌مانده

- ‏**۶۹ خطایِ ruff در `Kharazmi_Server/tests/`**: ‏C408 ۲۷، UP031 ۸، F841 ۸،
  RUF015 ۸، E702 ۷، SIM115 ۵، E701 ۳، SIM108 ۲، B007 ۱.
- ‏**۷۱۹ خطایِ mypy** (‏`arg-type` ۲۳۷، ‏`assignment` ۲۰۳، ‏`var-annotated` ۷۲،
  ‏`union-attr` ۵۸، ‏`misc` ۵۴، ‏`valid-type` ۴۳، …؛ پرحجم‌ترین فایل‌ها
  ‏`routers/admin.py` ۹۹ و `models.py` ۸۸).
- ‏**۶ ‏SIM102** با کامنتِ فارسی (بندِ ۶).
- ‏**۷ کپیِ `_restore_tables`** در `tests/route_audit/` (‏`test_audit_automation.py`،
  ‏`branches`، ‏`calendar`، ‏`crm`، ‏`dunning`، ‏`messages`، ‏`timeline`).
  در این برش فقط `strict=` داخلشان اصلاح شد؛ یکی‌کردنشان کاری جداست.
- ‏**ریفکتورِ Kotlin** — ۱۰ فایل بالایِ ۶۰۰ خط؛ بهترین هدف `AttendanceActivity.kt`
  (‏۹۹۸ خط، ≈۱۴۲ خطِ خوشهٔ شبکه/صف آزاد). بدونِ ابزارِ محلی انجام‌نشدنی است.
- بدهی‌هایِ منجمدِ پیشین: ‏`./gradlew wrapper`، هشدارهایِ Node-20 برایِ
  ‏`setup-java@v4` و `actions/*@v4`، کامنتِ کهنهٔ
  ‏`Kharazmi_Server/tests/test_e2e_finance_installments_invoice.py:12`، نبودِ
  annotation موفقیتِ «gate OK».

---

## ۹) فهرستِ تغییرات

‏۴۲ فایل، همه در ناحیهٔ مجاز:

- ‏`scripts/python-quality-baseline.json` — fingerprint ‏`59a6c3279a`،
  ruff ‏۸۷/۱۱، mypy ‏۷۱۹/۱۴، combined ‏۸۰۶.
- ‏`tests/route_audit/test_python_quality_gate.py` — شاهدِ تازهٔ W293
  (‏۵۲ → ۵۳ تست) + ‏`import io` و `import tokenize`.
- ناحیهٔ B (‏`Kharazmi_Server/`): ‏`main.py`، ‏`dependencies.py`، ‏`portal_data.py`،
  ‏`push_service.py`، ‏`today_summary.py`،
  ‏`routers/{audit, audit_trail, calendar, dunning, homework, parent, reports,
  students, teachers, timeline}.py`،
  ‏`scripts/{run_financial_audit, run_sec1_auth_curl_tests,
  verify_analytics_consistency_test}.py`،
  ‏`services/{class_restore, debtor_report, scheduling, session_submission,
  transaction_admin}.py`.
- ناحیهٔ A (‏`tests/route_audit/`): ‏`kotlin_contract.py`،
  ‏`sweep/{common, run_contract, run_sweep}.py`، و
  ‏`test_audit_{admin, audit_trail, automation, branches, calendar, crm, dunning,
  finance, messages, serve_upload, timeline}.py`.
- ناحیهٔ D (‏`scripts/` ریشه): ‏`generate_route_audit_docs.py`، ‏`validate_app_map.py`.
- همین سند.
