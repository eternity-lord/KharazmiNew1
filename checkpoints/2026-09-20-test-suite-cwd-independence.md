# نوبت ۵ — تصمیم B1: مستقل‌کردن سوئیت تست از پوشهٔ اجرا + `pytest.ini`

- **تاریخ:** ۲۰۲۶-۰۹-۲۱ (نوبت ۵ از برنامهٔ «۲۶ تصمیم باز»)
- **Branch:** `arena/01a0bf8d-kharazmiapp`
- **Base HEAD:** `acb8d7141da911f019a681b2e4771096003e2c6a` (پایان نوبت ۴ / A4)
- **سند نقشه:** `checkpoints/2026-09-20-open-decisions.md` — تصمیم B1
- **دامنه:** فقط فایل‌های تست + یک فایل کانفیگ جدید. **صفر تغییر در کد production** (نه سرور و نه اندروید).

---

## ۱) مشکل و ریشه

هفت فراخوانی در سه فایل تست، فایل‌های سرور را با **مسیر نسبی به cwd** باز می‌کردند:

```python
with open("Kharazmi_Server/routers/audit.py", encoding="utf-8") as f:   # test_audit.py ×3
with open("Kharazmi_Server/routers/dashboard.py", encoding="utf-8") as f:  # test_dashboard.py، test_dashboard_performance.py
with open("Kharazmi_Server/routers/audit.py", ...) / dunning.py            # test_dashboard_performance.py
```

| سی‌دی‌دبلیو | نتیجه |
|---|---|
| ریشهٔ ریپو (`/home/user/KharazmiApp`) | ✅ سبز |
| داخل `Kharazmi_Server/` | ❌ **۵ failure کاذب** با `FileNotFoundError` |

این دقیقاً همان ۵ failureای است که در Task 6 (checkpoint `2026-09-20-existing-test-failures.md`) به‌عنوان «مشکل پوشهٔ اجرا» مستند شد. ریسک واقعی: اگر CI یا هر کسی سوئیت را از داخل `Kharazmi_Server/` اجرا کند، یا این ۵ تست بی‌صدا «خراب» دیده می‌شوند و به بی‌اعتباری سوئیت می‌انجامد، یا بدتر: اگر کسی مسیر را «دور بزند» با `cd`، تست‌های محافظ (invariantهای code-inspection) عملاً بی‌اثر می‌شوند.

ضمناً هیچ فایل کانفیگ pytest در ریپو نبود؛ پس مسیر کشف تست‌ها هم برای ابزارها (IDE/CI) مبهم بود.

---

## ۲) رفتار قبل و بعد

| سناریو | قبل | بعد |
|---|---|---|
| اجرا از ریشهٔ ریپو | ✅ ۸۸۵ passed | ✅ **۸۹۰ passed** |
| اجرا از داخل `Kharazmi_Server/` | ❌ ۵ failure (`FileNotFoundError`) | ✅ **۸۹۰ passed** |
| `pytest -q` بدون آرگومان از ریشه | مجموعه مبهم (بدون کانفیگ) | ✅ کشف تثبیت‌شده: ۸۹۰ تست از `testpaths` |
| مسیر فایل‌های سرور در تست‌ها | وابسته به cwd | نسبت به `__file__` (مستقل از cwd) |

**الگوی جدید** (در هر سه فایل):

```python
_SERVER_DIR = os.path.dirname(os.path.abspath(__file__))

def _server_file(*parts):
    """مسیر مطلق یک فایل داخل Kharazmi_Server (مستقل از cwd)."""
    return os.path.join(_SERVER_DIR, *parts)
```

نکته: دو فایل قدیمی‌تر (`test_audit_trail.py`، `test_exports.py`) از قبل همین الگو را داشتند؛ B1 آن را به سه فایل باقی‌مانده تعمیم داد.

---

## ۳) فایل‌های تغییرکرده

| فایل | تغییر |
|---|---|
| `pytest.ini` (**جدید، ریشهٔ ریپو**) | `testpaths = Kharazmi_Server` + `norecursedirs` (بیرون‌ماندن `KharazmiAdmin`/`checkpoints`) + مستندسازی روش اجرا |
| `Kharazmi_Server/test_audit.py` | `import os` + helper `_server_file` + ۳ مسیر مطلق شد |
| `Kharazmi_Server/test_dashboard.py` | `import os` + helper + ۱ مسیر مطلق شد |
| `Kharazmi_Server/test_dashboard_performance.py` | `import os` + helper + ۳ مسیر مطلق شد |
| `Kharazmi_Server/test_suite_cwd_independence.py` (**جدید**) | ۶ تست رگرسیون B1 (ساختاری + رفتاری) |

**بدون تغییر:** کد production سرور، هر فایل Kotlin/XML اندروید، تست‌های دیگر، و معنای هیچ assertionای — فقط **مسیر باز کردن فایل** عوض شد. محتوای بررسی‌شده و همهٔ invariantها یکی‌اند.

---

## ۴) تست‌ها

```bash
# روش مستند پروژه (ریشهٔ ریپو)
DATABASE_URL=sqlite:////tmp/b1.db JWT_SECRET_KEY=<hex> python3 -m pytest Kharazmi_Server -q
```

| اجرا | نتیجه |
|---|---|
| **۱)** ریشه + `pytest Kharazmi_Server -q` (روش مستند) | **890 passed** |
| **۲)** ریشه + bare `pytest --collect-only -q` (کشف از `pytest.ini`) | **890 tests collected** ✅ |
| **۳)** داخل `Kharazmi_Server/` + bare `pytest -q` (قبلاً ۵ failure) | **890 passed** ✅ |
| **۴)** داخل `Kharazmi_Server/` + `pytest test_audit.py -q` | **14 passed** |
| تست جدید `test_suite_cwd_independence.py` | **6 passed** |
| **اثبات pre-fix** (worktree روی `acb8d71` + فایل تست جدید) | **4 failed / 2 passed** — و در گزارش داخلی همان زیرفرایند: `5 failed` = دقیقاً ۵ failure مستندشدهٔ Task 6 |
| md5 دیتابیس واقعی `Kharazmi_Server/gaj_db.db` | `f048f8d118b33c4eaa944490594121d7` — **بی‌تغییر** |

**پوشش تست جدید:**
1. ساختاری: هیچ فایل تستی مسیر `Kharazmi_Server/...` را نسبت به cwd باز نمی‌کند — سنجش با `tokenize` روی **کد** (کامنت‌ها به حساب نمی‌آیند) تا خودِ مستندسازی فیکس، مثبت کاذب نسازد.
2. ساختاری: `pytest.ini` ریشه وجود دارد و `testpaths` را به `Kharazmi_Server` تثبیت کرده و درخت اندروید را بیرون نگه داشته است.
3. ساختاری: فایل‌های سرور مرجع (`routers/audit|dashboard|dunning|finance.py`) از مسیر مطلقِ helper واقعاً وجود دارند.
4. رفتاری: اجرای واقعیِ **همان ۵ تستِ قبلاً شکست‌خورده** در زیرفرایند با `cwd = Kharazmi_Server/` و انتظار `returncode == 0` و نبود `FileNotFoundError`.
5. رفتاری: همان تست با `cwd = ریشهٔ ریپو` و مسیر صریح فایل، سبز می‌ماند (هر دو نقطهٔ اجرا معتبر).

**بازگشت‌ناپذیری:** هیچ assertion یا رفتار تستی حذف/تضعیف نشد (مثلاً `test_no_silent_except_pass` هنوز همان محتوای `audit.py` را می‌سنجد)؛ فقط محل فایل با مسیر مطلق تعیین می‌شود.

---

## ۵) وضعیت build اندروید

**build واقعی انجام نشد و ادعا نمی‌شود** (JDK/SDK در محیط نیست). این نوبت **هیچ تغییری در سمت اندروید ندارد** — نه کد Kotlin، نه منابع XML. بنابراین ریسک بیلد اندروید صفر است و بررسی استاتیک پایتون (`ast.parse` روی فایل‌های تغییر‌یافته و تست جدید) سبز است.

---

## ۶) ریسک‌ها و محدودیت‌های باقی‌مانده

1. **`test_three_critical_modules_e2e.py` فایل موقت `mock_homework.pdf` را در پوشهٔ جاری می‌سازد** و در پایان پاک می‌کند (`os.remove`). این وابستگی به cwd **مضر نیست** (خودپاک‌شونده است و در اجرای ماتریس بالا هیچ فایل اضافه‌ای باقی نماند)، ولی اگر روزی جداسازی کامل لازم شد، کاندیدای `tmp_path` است. در دامنهٔ B1 دست نخورد.
2. **`pytest.ini` عمداً حداقلی است**: هیچ `addopts`، `filterwarnings` یا پلاگین اجباری اضافه نشد تا رفتار سوئیت در محیط‌های مختلف (CI نوبت B2) قابل پیش‌بینی بماند.
3. **اجرا از پوشه‌ای خارج از ریپو** (مثل `/tmp`) طبعاً `pytest.ini` را پیدا نمی‌کند — B1 تضمین را برای «هر پوشهٔ داخل ریپو» می‌دهد، همان چیزی که در سند نقشه مقصود بود.
4. **CI هنوز وجود ندارد** — این نوبت فقط پیش‌نیاز آن را (کانفیگ + تست‌های مستقل از cwd) آماده کرد؛ افزودن workflow در نوبت **B2** است تا اجرای خودکار رگرسیون‌ها بی‌سروصدا از دست نرود.
5. `warning`های موجود (`StarletteDeprecationWarning`, `MovedIn20Warning`, `crypt deprecated`) همان‌های قبل‌اند و در دامنهٔ B1 نیستند.

---

## ۷) Commit و Push

- **Commit SHA:** در گزارش نهایی پس از commit ثبت می‌شود؛ SHA داخل همان commit قابل درج نیست.
- **وضعیت Push:** در گزارش نهایی اعلام می‌شود.
- **Commit message:** `chore: make test suite independent of working directory`
- **Branch:** `arena/01a0bf8d-kharazmiapp` — PR/merge بدون دستور صریح ساخته نمی‌شود.
- **نوبت بعدی نقشه:** B2 — افزودن CI گیت‌هاب برای اجرای تست‌ها از ریشهٔ ریپو با DB موقت.
