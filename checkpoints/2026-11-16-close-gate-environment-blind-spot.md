# ۲۰۲۶-۱۱-۱۶ — بستنِ نقطهٔ کورِ محیطیِ گیتِ کیفیتِ پایتون

برشِ پیش (PR #28، در `main` با merge commit ‏`f9469b0c711d`) حصارِ ruff و mypy را ساخت.
این برش یک **نقطهٔ کور** در همان حصار می‌بندد: گیت نمی‌فهمید محیطی که در آن اندازه
می‌گیرد کامل است یا نه، و در محیطِ ناقص **بهبودِ دروغین** گزارش می‌کرد.

---

## ۱) چرا این برش لازم بود

`pyproject.toml` برایِ mypy دو تنظیم دارد:

```toml
ignore_missing_imports = true
follow_imports = "silent"
```

یعنی یک بستهٔ نصب‌نشده **هیچ** خطایی تولید نمی‌کند و نوعش `Any` می‌شود. با `Any` شدنِ
fastapi و sqlalchemy و pydantic، صدها خطایِ `arg-type` و `assignment` بی‌صدا ناپدید
می‌شوند. اندازه‌گیریِ واقعی رویِ همین مخزن، با دو venv جدا:

| محیط | خطایِ mypy | شناسه | `checked_files` |
| --- | --- | --- | --- |
| کامل (`requirements.txt` + dev) | **۷۲۵** | ۱۴ | ۵۵ |
| فقط ruff+mypy+pytest | **۱۷۴** | ۹ | ۵۵ |

`arg-type` از ۲۳۹ به ۱۰ و `assignment` از ۲۰۶ به ۱۶ می‌افتد.

فاجعه این است که **هیچ شاهدِ درونیِ گیت این را نمی‌گرفت**:

- خروجیِ mypy در هر دو حالت کاملاً خوش‌قالب است؛
- خطِ خلاصهٔ «۱۷۴ errors» با شمارشِ تک‌تکِ خطاهایِ پارس‌شده یکی است؛
- `checked_files` همان ۵۵ می‌ماند؛
- هیچ‌یک از `MYPY_PARTIAL_MARKERS` («errors prevented further checking»، «Cannot read
  file») ظاهر نمی‌شود؛
- pinهایِ نسخه هم می‌خوانند (mypy 2.4.1 در هر دو محیط نصب است).

پس گیت `delta -551` را می‌خواند، «improvement» اعلام می‌کرد و با **exit 0** چراغِ سبز
می‌داد. بدترین شکلِ ممکن برایِ یک حصار: در محیطِ ناقص بی‌صدا باز می‌شود و به‌جایِ
قرمز شدن، تشویق می‌کند.

ریشهٔ مشکل: گیت از رویِ **stdoutِ خودِ mypy** دربارهٔ محیط قضاوت می‌کرد. با
`follow_imports = "silent"` آن stdout هیچ نشانی از محیط ندارد. راه‌حل باید یک
سنجشِ **مستقل از خروجیِ ابزار** باشد.

---

## ۲) چه ساخته شد

پنج تابعِ تازه در `scripts/python_quality_gate.py`:

| تابع | کار |
| --- | --- |
| `_norm_dist(name)` | نرمال‌سازیِ نامِ distribution طبقِ PEP 503 |
| `find_requirements(root)` | یافتنِ `requirements.txt` سرور بدونِ نوشتنِ نامِ پوشه |
| `parse_requirements(text)` | بیرون کشیدنِ نام‌ها از فایلِ requirements |
| `installed_distributions()` | نامِ نرمالِ همهٔ بسته‌هایِ نصب‌شده در همین مفسر |
| `probe_environment(root)` | `{required, missing, requirements}` |
| `_check_environment(stats, base)` | مقایسهٔ مجموعهٔ وابستگی با baseline |

و چهار اتصال:

1. `collect()` یک `env_prober` می‌گیرد، پروب را **پیش از** اجرایِ هر دو ابزار صدا
   می‌زند، و اگر `missing` ناتهی باشد `ToolUnavailable` می‌دهد ⇒ exit 2.
2. `stats` کلیدِ `environment` می‌گیرد.
3. `compact_table()` یک خطِ تازه چاپ می‌کند:
   `environment: 13 required distributions installed (declared by Kharazmi_Server/requirements.txt)`.
4. `baseline_payload()` کلیدِ `environment` را در JSON می‌گذارد و
   `check_against_baseline()` تغییرِ مجموعهٔ وابستگی را مثلِ تغییرِ نسخهٔ ابزار
   **ناشناخته** می‌شمارد.

`scripts/python_quality_gate.py`: ‏۶۲۷ → **۷۹۴ خط** / ۴۸۳۲۹ بایت.
`tests/route_audit/test_python_quality_gate.py`: ‏۴۳ → **۵۲ شاهد** (۷۶۰ خط / ۴۱۷۵۷ بایت).
`scripts/python-quality-baseline.json`: ‏۱۰۰ → **۱۲۴ خط** / ۴۵۶۷ بایت،
fingerprint ‏`e4f4e2f589` → **`427444bccb`**.

---

## ۳) تصمیم‌هایِ طراحی

### ۳-۱) سنجش با `importlib.metadata` در همان مفسر، نه با اجرایِ یک زیرفرآیند

`collect()` ‏mypy را با `[sys.executable, "-m", "mypy"]` اجرا می‌کند (خطوطِ ۳۲۵–۳۲۷
پیش از این برش). پس محیطِ **همین مفسر** دقیقاً همان چیزی است که mypy برایِ حلِ
importها می‌بیند. سنجشِ درون‌فرآیندی هم ارزانی است هم بی‌واسطه. اجرایِ یک
`pip list` در زیرفرآیند می‌توانست مفسرِ دیگری را بسنجد و همان توهم را بازتولید کند.

### ۳-۲) نامِ distribution مقایسه می‌شود، نه نامِ import — پس هیچ جدولِ نگاشتی لازم نیست

سه نام در این مخزن importِ متفاوتی دارند (`python-dotenv` ⇒ `dotenv`،
`psycopg2-binary` ⇒ `psycopg2`، `python-multipart` ⇒ `multipart`). ساختنِ جدولِ
نگاشتِ distribution→import گزینهٔ اولِ ذهنی بود. اندازه‌گیری شد که لازم نیست:
`importlib.metadata` همان نامی را می‌دهد که `requirements.txt` می‌نویسد، پس

```python
req = parse_requirements(...)          # 13 نام
inst = installed_distributions()       # 47 نام
[r for r in req if r not in inst]      # → []
```

**هر ۱۳ نام بدونِ یک استثنا خواندند.** یک جدولِ دستی هم ناقص می‌ماند هم با هر
وابستگیِ تازه کهنه می‌شد. شرطِ لازم فقط نرمال‌سازیِ PEP 503 است
(`Psycopg2_Binary` ⇒ `psycopg2-binary`)، چون `requirements.txt` و متادیتا ممکن است
جداکننده‌هایِ متفاوت بنویسند.

### ۳-۳) شمارهٔ نسخه عمداً دور ریخته می‌شود

pinهایِ این مخزن `>=` هستند (`fastapi>=0.100.0`)، یعنی نسخهٔ نصب‌شده شناور است و
مقایسهٔ شمارهٔ نسخه‌ها هر اجرایِ CI را بی‌دلیل قرمز می‌کرد. چیزی که باید یکی بماند
**مجموعهٔ** وابستگی‌هاست، چون نبودنِ یک بسته نوعش را `Any` می‌کند. تغییرِ خودِ
مجموعه هم separately در `_check_environment` گرفته می‌شود (بخشِ ۳-۶).

### ۳-۴) کشفِ مسیرِ `requirements.txt` بدونِ هیچ literal

نامِ پوشه در گیت نوشته **نشد**. این مخزن یک کلاسِ غلطِ تاریخی دارد که در آن حرفِ دومِ
نامِ پوشه‌ها گاهی بزرگ نوشته می‌شود و گاهی کوچک، و یک گاردِ سراسریِ املایی هم برایش
ساخته شده (ده لغزشِ ثبت‌شده، آخرینش در برشِ پیش داخلِ خودِ workflow). نوشتنِ نام در
یک فایلِ تازه دو خطر داشت: مصداقِ یازدهم شدن، و شکستنِ ویرایشِ بعدی به‌خاطرِ
یکی‌نبودنِ case. معیارِ انتخاب‌شده ساختاری است:

> تنها زیرپوشهٔ سطحِ اولی که `requirements.txt` دارد.

اندازه‌گیری شد که در این مخزن **دقیقاً یک** مصداق دارد و خودِ ریشه یکی ندارد. اگر
روزی صفر یا دو شود، `find_requirements` بلند شکست می‌خورد (نه حدسِ تصادفی).

### ۳-۵) محیطِ ناقص ⇒ exit 2، نه exit 1

این گیت سه وضعیت دارد: پاس (۰)، بدتر (۱)، **ناشناخته (۲)**. نبودنِ یک بسته «بدتر
شدنِ کد» نیست — اندازه‌گیری اصلاً معتبر نیست. اگر exit 1 می‌داد، یک نصبِ ناقص به
شکلِ یک رگرسیونِ کد گزارش می‌شد و توسعه‌دهنده را به دنبالِ تغییری می‌فرستاد که هرگز
اتفاق نیفتاده. exit 2 همان معنایی است که برایِ «نسخهٔ ابزار فرق کرد» و «خروجیِ mypy
نیمه‌کاره بود» به کار رفته است. پیام هم نامِ **تک‌تکِ** بسته‌هایِ غایب را می‌دهد، نه
فقط یک شمار — پیامِ «۲ بسته کم است» قابلِ اقدام نیست.

### ۳-۶) مجموعهٔ وابستگی هم بخشیِ baseline است

اگر `requirements.txt` از زمانِ اندازه‌گیریِ baseline عوض شده باشد، شمارِ فعلی با شمارِ
baseline هم‌سنخ نیست — حتی اگر هر دو محیط کامل باشند، چون یک بستهٔ تازه نوع‌هایِ
تازه‌ای را برایِ mypy قابلِ حل می‌کند و خطاها را جابه‌جا می‌کند. پس
`_check_environment` ‏exit 2 می‌دهد و از کاربر می‌خواهد `--write-baseline` بگیرد و JSON
تازه را commit کند. این دقیقاً همان الگویِ `_check_versions` است.

### ۳-۷) یک fail-openِ محدود و **صراحی‌شده**

baselineهایِ قدیمی‌تر که کلیدِ `environment` ندارند رد **نمی‌شوند**. اگر نبودِ کلید
exit 2 می‌داد، هر baselineِ ساخته‌شده پیش از این برش بلافاصله بی‌استفاده می‌شد و
ارتقا را پرهزینه می‌کرد. نبودِ کلید یعنی «مقایسه ممکن نیست» نه «محیط ناقص است» — و
سنجشِ کامل بودنِ محیط همچنان مستقل از baseline در `collect()` انجام می‌شود، پس حفره‌ای
باز نمی‌ماند. این انتخاب عمدی است و شاهدِ
`test_gate_accepts_a_baseline_without_an_environment_section` آن را قفل می‌کند تا
«ناخواسته fail-open شد» با «صراحی‌شده fail-open است» اشتباه نشود.

### ۳-۸) تزریقِ `env_prober` — این بار درسِ CI را **پیش‌دستانه** گرفتم

برشِ پیش باگِ پرهزینه‌ای داشت: `collect()` پیش از نگاه کردن به `runner` تزریقی،
`find_ruff()` واقعی را صدا می‌زد. نتیجه ۲۱ شاهدِ قرمز در jobِ ‏`route-audit` بود، در
حالی که همان suite در محیطِ توسعه سبز می‌ماند. یعنی تست‌ها به‌جایِ منطقِ گیت، محیطِ
نصب را می‌سنجیدند.

سنجشِ تازهٔ محیط **خودش یک وابستگیِ محیطی است**. اگر بدونِ نقطهٔ تزریق اضافه
می‌شد، هر شاهدی که runnerِ ساختگی تزریق می‌کند ناچار بود یک `requirements.txt` واقعی
رویِ دیسک و کلِ بسته‌هایِ نصب‌شده را هم داشته باشد — همان دام با یک بهانهٔ تازه. پس
`env_prober` هم‌زمان با خودِ سنجش اضافه شد و دو شاهد آن را قفل می‌کنند:

- `test_an_injected_env_prober_does_not_require_the_real_environment` ‏`probe_environment`
  را عمداً با `AssertionError` خراب می‌کند و assert می‌کند که با proberِ تزریقی کار
  ادامه دارد — الگویِ همان شاهدی که برایِ `ruff_resolver` نوشته شد.
- هر ۸ فراخوانیِ `collect()` در تست‌ها `env_prober=fake_env` می‌گیرند، از جمله دو
  شاهدی که `find_ruff` را monkeypatch می‌کنند (چون پروب الان **پیش از** ruff اجرا
  می‌شود، وگرنه با پیامِ غلط می‌شکستند).

### ۳-۹) چرا پروب پیش از اجرایِ ابزارها می‌آید

ترتیب عمدی است. در محیطِ ناقص خودِ اندازه‌گیری بی‌معناست، و پیامِ «محیط ناقص است،
این‌ها را نصب کن» از پیامِ «ruff پیدا نشد» بسیار قابلِ اقدام‌تر است. ضمناً در همان
محیط، mypy عملاً کارِ بی‌فایده می‌کرد.

---

## ۴) اثباتِ دندان (هر دو اندازه‌گیریِ واقعی، نه حدس)

**دندانِ اول — وابستگیِ غایب.** یک venv با ruff و mypy ولی بدونِ بسته‌هایِ سرور:

```
ruff: True  mypy: True  fastapi: False  sqlalchemy: False
gate exit = 2
::error title=python quality inventory unavailable::dependency environment incomplete:
  13 of 13 distributions declared by Kharazmi_Server/requirements.txt are not installed:
  fastapi, httpx, openpyxl, passlib, psycopg2-binary, pydantic, python-dotenv,
  python-multipart, reportlab, requests, slowapi, sqlalchemy, uvicorn. With
  ignore_missing_imports=true mypy types every unresolved import as Any, so hundreds of
  real errors vanish and this run would read as a huge improvement. The measurement is
  not comparable to the baseline — install the declared requirements and re-run.
```

همان سناریویی که پیش‌تر exit 0 با «بهبودِ ۵۵۱ واحدی» می‌داد، حالا exit 2 با تشخیصِ
علت می‌دهد.

**دندانِ دوم — تغییرِ مجموعهٔ وابستگی.** یک کپی از baseline با
`required − {pandas} + {httpx}`:

```
exit = 2
::error title=python quality gate::dependency set changed since the baseline was
  measured: added=['httpx'] removed=['pandas'] — mypy resolves different types now, so
  the counts are not comparable. Re-run with --write-baseline and commit the refreshed JSON.
```

و در وضعیتِ ناشناخته **هیچ خطِ delta چاپ نمی‌شود** (شاهد assert می‌کند).

**شاهدِ ساختگی‌بودنِ شکست.** `find_requirements` در سه حالت سنجیده شد: صفر مصداق ⇒
`ToolUnavailable`؛ دو مصداق ⇒ `ToolUnavailable`؛ یک مصداق ⇒ همان مسیر.
`parse_requirements` هم کامنت، خطِ خالی، `-r`، `--index-url`، extras و environment
marker را درست رد می‌کند و نامِ تکراری را یکی می‌شمارد.

---

## ۵) چیزی که عمداً تغییر نکرد

- **عددها دست‌نخورده‌اند:** ruff ‏۲۵۰ در ۲۷ شناسه و ۶۳ فایل، mypy ‏۷۲۵ در ۱۴ شناسه
  و ۴۴ فایل، `checked_files` ‏۵۵، combined ‏۹۷۵، `delta +0`، exit 0. این برش حصار
  گذاشت، نه بدهی رفع.
- fingerprint از `e4f4e2f589` به **`427444bccb`** تغییر کرد **فقط** به‌خاطرِ کلیدِ
  تازهٔ `environment` در payload. برابریِ fingerprintِ اجرایِ زنده با فایلِ رویِ دیسک
  اندازه‌گیری و تأیید شد.
- `.github/workflows/tests.yml` دست **نخورد**. گیت فقط در یک گام اجرا می‌شود
  (خطِ ۹۶، jobِ ‏`pytest`) و آن job عمداً هر دو فایلِ requirements را نصب می‌کند، پس
  پروب آنجا سبز است. jobِ ‏`route-audit` ‏ruff/mypy را نصب نمی‌کند و گیت را هم اجرا
  نمی‌کند — فقط شاهدِ ریپویِ واقعی در آن اجرا می‌شود، که `requirements.txt` را نصب
  دارد (بخشِ ۶).
- هیچ فایلی در `Kharazmi_Server/tests/` (پوشهٔ ممنوعه) ویرایش نشد.

---

## ۶) باتریِ پذیرش

| سنجش | نتیجه |
| --- | --- |
| `ruff check` رویِ دو فایلِ دست‌خورده | `All checks passed!` |
| `ruff check .` رویِ کلِ ریپو | `Found 250 errors.` (بدونِ تغییر — کدِ تازه صفر خطا اضافه کرد) |
| `python_quality_gate.py --table --check` در محیطِ کامل | exit 0، `ruff 250 + mypy 725`، `delta +0` |
| `pytest tests/route_audit/test_python_quality_gate.py -q` | **52 passed** |
| GATE B ‏`pytest tests/route_audit -q` در venv کامل | **337 passed** (پیش‌تر ۳۲۸) |
| GATE A ‏`pytest -q` در venv کامل | **1279 passed** (بدونِ تغییر) |
| GATE B در **venvِ شکلِ CI** (`ruff: False mypy: False yaml: False`، `fastapi/sqlalchemy/pydantic: True`) | **337 passed** در ۳۲ ثانیه |
| گیت در همان venvِ شکلِ CI | `ToolUnavailable: ruff executable not found` ⇒ exit 2 (انتظار: آن job گیت را اجرا نمی‌کند) |
| اسکنِ املایی رویِ ۵۶۸ فایلِ کد | `bad: none` |

آخرین ردیفِ جدولِ بالا مهم‌ترین است: همان شکلِ محیطی که در برشِ پیش ۲۱ شاهد را قرمز
کرد، حالا **۳۳۷ سبز** می‌دهد. و اینکه در آن محیط پیامِ شکستِ گیت «ruff پیدا نشد» است
و نه «محیط ناقص» خودش گواهی است که پروب با `requirements.txt` نصب‌شده به‌درستی رد
شده است.

---

## ۷) بدهیِ باقی‌مانده (صراحتاً رفع **نشد**)

- **۲۵۰ خطایِ ruff و ۷۲۵ خطایِ mypy همچنان منجمد‌اند، نه رفع‌شده.** این برش فقط
  کاری کرد که نتوان بی‌صدا از حصایشان عبور کرد.
- **netting-out**: یک شناسه که ۱۰ تا کم شود و یکی ۱۰ تا زیاد، `delta +0` می‌دهد.
  گاردِ «شناسهٔ تازه یا رشدکرده» بخشی از آن را می‌گیرد، نه همه را.
- پروب فقط `requirements.txt` سرور را می‌سنجد. اگر روزی وابستگیِ دیگری (مثلاً یک
  بستهٔ فقط برایِ اسکریپت‌ها) لازم شود، باید همان‌جا اعلام شود تا سنجیده شود.
- `requirements-dev.txt` عمداً **سنجیده نمی‌شود**: jobِ ‏`route-audit` آن را نصب
  نمی‌کند، و سنجیدنش همان job را قرمز می‌کرد. pinهایِ نسخهٔ ruff/mypy را شاهدِ
  `test_committed_baseline_agrees_with_the_pinned_tool_versions` جداگانه قفل می‌کند.
- هیچ‌کدام از گیت‌ها در حالتِ موفقیت annotationِ «gate OK» منتشر نمی‌کنند.
- بدهی‌هایِ برشِ پیش سرِ جایشان‌اند: `F841` از پیش موجود در
  `scripts/validate_app_map.py:281`، `find_dead_kotlin` ‏۸ نماد/۱۰۴ خط، بدهیِ
  `./gradlew wrapper`، کامنتِ کهنه در پوشهٔ ممنوعه، هشدارهایِ Node 20.

**پاسخِ «ریفکتور کامل انجام شد؟ باگ‌ها کامل تمام شد؟» همچنان NO است.**

---

## ۸) فهرستِ تغییرات

```
 scripts/python_quality_gate.py                     |  ۶۲۷ → ۷۹۴ خط (+۱۷۵/−۲)
 tests/route_audit/test_python_quality_gate.py      |  ۴۳ → ۵۲ شاهد (+۲۱۵/−۱۳)
 scripts/python-quality-baseline.json               |  کلیدِ environment (+۲۸/−۱)
 checkpoints/2026-11-16-close-gate-environment-blind-spot.md | تازه (همین سند)
 checkpoints/2026-11-14-add-python-quality-gate.md   | یک ارجاعِ رو‌به‌جلو در بخشِ بدهی
```

جمعاً ۳ فایلِ کد با ۴۰۳ درج و ۱۵ حذف، به‌علاوهٔ دو سند.

`git add` فقط با **مسیرهایِ صریح** انجام شد، هرگز `-A`. دلیلش همان قاعدهٔ برش‌های
پیش است: در این sandbox دیدِ زیردرخت‌ها ناپایدار است و یک `add -A` در لحظهٔ کوری
می‌تواند حذفِ صدها فایل را stage کند.

### قاعدهٔ تازه‌ای که این برش اضافه کرد

> هر وابستگیِ محیطی — ابزار، باینری، بسته، حتی یک فایل رویِ دیسک — باید نقطهٔ تزریقِ
> هم‌سطحِ خودش را داشته باشد، و هر سنجشِ محیطی باید **پیش از** کاری اجرا شود که
> نتیجه‌اش را بی‌معنا می‌کند. یک شاهدی که محیطِ واقعی را لازم دارد، شاهدِ منطق نیست؛
> شاهدِ ماشینِ توسعه‌دهنده است.
