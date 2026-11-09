# چک‌پوینت: بررسی دقیق پنج failure قدیمی تست‌ها (audit / dashboard / dashboard-performance)

- **عنوان:** Root-cause analysis پنج failure گزارش‌شده‌ی موجود در suite — بدون تغییر کد production
- **تاریخ:** 2026-09-20
- **Branch:** `arena/01a0bf8d-kharazmiapp` (تنها branch کاری)
- **Base HEAD:** `b676ff6cffc1839be32de66b01105369ac73d6bd` — `fix: include undated sessions in teacher settlements`
- **HEAD قبل از تسک‌های اخیر (مرجع مقایسه):** `0133d806cf57392d01020abb82e7ebc4cbc2eecc`
- **نوع این چک‌پوینت:** ممیزی صرف (audit) — **هیچ خطی از کد production و هیچ تستی تغییر نکرد**
- **محیط:** Python 3.11.2 · pytest 9.1.1 · venv: `/home/user/.venv` · DB تست: SQLite موقت در `/tmp`

---

## ۰) خلاصه‌ی یک‌خطی

هر پنج failure **یک ریشه‌ی مشترک** دارند: آن تست‌ها فایل سورس را با **مسیر نسبی از ریشهٔ ریپو** می‌خوانند (`open("Kharazmi_Server/routers/...")`)، پس فقط وقتی شکست می‌خورند که pytest از **داخل پوشهٔ `Kharazmi_Server`** اجرا شود. با اجرای استاندارد پروژه (از ریشهٔ ریپو) **کل suite سبز است: 801 passed / 0 failed**.

📌 **هیچ‌کدام bug واقعی production نیستند، تست‌ها outdated نیستند، fixture/seed نادرست نیست.** نوع مشکل: **محیط اجرا (cwd)**.

اثبات نهایی (روی همین HEAD `b676ff6`):

| دستور اجرا | نتیجه |
|---|---|
| از **ریشهٔ ریپو**: `pytest Kharazmi_Server -q` | ✅ **801 passed / 0 failed** |
| از **داخل** `Kharazmi_Server`: `pytest -q` | ❌ **5 failed / 796 passed** |

---

## ۱) جدول پنج failure — دقیقاً همان‌ها که گزارش شده بود

| # | تست | خط `open()` | خطا |
|---|---|---|---|
| 1 | `test_audit.py::TestAuditRadar::test_no_silent_except_pass` | `test_audit.py:256` | `FileNotFoundError: 'Kharazmi_Server/routers/audit.py'` |
| 2 | `test_audit.py::TestAuditRadar::test_joinedload_used_for_nplus1` | `test_audit.py:263` | `FileNotFoundError: 'Kharazmi_Server/routers/audit.py'` |
| 3 | `test_audit.py::TestAuditRadar::test_finance_uses_central_installment_validation` | `test_audit.py:273` | `FileNotFoundError: 'Kharazmi_Server/routers/finance.py'` |
| 4 | `test_dashboard.py::TestDashboardKPIs::test_dashboard_isolated_no_finance_touch` | `test_dashboard.py:190` | `FileNotFoundError: 'Kharazmi_Server/routers/dashboard.py'` |
| 5 | `test_dashboard_performance.py::TestDashboardPerformance::test_uses_count_queries_not_all` | `test_dashboard_performance.py:159` (+ `:183`، `:187`) | `FileNotFoundError: 'Kharazmi_Server/routers/dashboard.py'` |

---

## ۲) Root-cause analysis هر failure به‌صورت جداگانه

### Failure ۱ — `test_no_silent_except_pass`

- **فایل/کلاس:** `test_audit.py` / `TestAuditRadar`
- **خطا:** `FileNotFoundError: [Errno 2] No such file or directory: 'Kharazmi_Server/routers/audit.py'`
- **ماهیت تست:** تست ایستا (static) — هیچ درخواست HTTP و هیچ کوئری DB ندارد؛ فقط محتوای متنی `routers/audit.py` را می‌خواند و بررسی می‌کند `except Exception: pass` بی‌صدا وجود نداشته باشد و `logger.error`/`print` موجود باشد.
- **Root cause:** `open("Kharazmi_Server/routers/audit.py")` یک مسیر **نسبی** است که فقط وقتی درست resolve می‌شود که **cwd = ریشهٔ ریپو** باشد. اجرای pytest از داخل `Kharazmi_Server` ⇒ مسیر به `Kharazmi_Server/Kharazmi_Server/routers/audit.py` اشاره می‌کند ⇒ `FileNotFoundError`.
- **طبقه‌بندی:** ❌ bug تولید نیست · ❌ تست outdated نیست · ❌ fixture/seed نادرست نیست · ✅ **مشکل محیط/روش اجرا (cwd)**
- **اقدام:** هیچ تغییری در تست و کد — طبق قانون «اگر مشکل محیطی بود، کد production را تغییر نده و راه اجرای صحیح را مستند کن».
- **اجرای مجدد (از ریشهٔ ریپو):** ✅ `PASSED`

### Failure ۲ — `test_joinedload_used_for_nplus1`

- **فایل/کلاس:** `test_audit.py` / `TestAuditRadar`
- **خطا:** `FileNotFoundError: 'Kharazmi_Server/routers/audit.py'`
- **ماهیت تست:** تست ایستا — بررسی می‌کند در `routers/audit.py` از `joinedload` و به‌طور خاص `joinedload(SessionLog.course)` استفاده شده باشد (رفع N+1).
- **Root cause:** دقیقاً همان الگوی مسیر نسبی از ریشهٔ ریپو (`test_audit.py:263`).
- **طبقه‌بندی:** ✅ مشکل محیط/روش اجرا (cwd)
- **اقدام:** بدون تغییر.
- **اجرای مجدد:** ✅ `PASSED`

### Failure ۳ — `test_finance_uses_central_installment_validation`

- **فایل/کلاس:** `test_audit.py` / `TestAuditRadar`
- **خطا:** `FileNotFoundError: 'Kharazmi_Server/routers/finance.py'`
- **ماهیت تست:** تست ایستا — بررسی invariant: در `routers/finance.py` اعتبارسنجی سررسید قسط از قاعدهٔ مرکزی (`from validation import` و `validate_jalali_due_date`) بیاید و regex شکلیِ قدیمی (`Field(pattern=`) برنگردد. (این تست خودش در تاریخ ۲۰۲۶-۰۹-۱۷ به‌عنوان جانشینِ گارد قدیمی F-T2 به‌روزرسانی شده بود.)
- **Root cause:** همان الگوی مسیر نسبی (`test_audit.py:273`) — نه ناشی از تغییر `finance.py`.
- **طبقه‌بندی:** ✅ مشکل محیط/روش اجرا (cwd)
- **اقدام:** بدون تغییر.
- **اجرای مجدد:** ✅ `PASSED`

### Failure ۴ — `test_dashboard_isolated_no_finance_touch`

- **فایل/کلاس:** `test_dashboard.py` / `TestDashboardKPIs`
- **خطا:** `FileNotFoundError: 'Kharazmi_Server/routers/dashboard.py'`
- **ماهیت تست:** تست ایستا — بررسی می‌کند `routers/dashboard.py` شامل `check_admin_access` و `DashboardKPIs` باشد و `def create_transaction` (منطق نوشتن مالی) نداشته باشد ⇒ یعنی داشبورد فقط-خواندنی و مستقل از finance است.
- **Root cause:** همان الگوی مسیر نسبی (`test_dashboard.py:190`).
- **طبقه‌بندی:** ✅ مشکل محیط/روش اجرا (cwd)
- **اقدام:** بدون تغییر.
- **اجرای مجدد:** ✅ `PASSED`

### Failure ۵ — `test_uses_count_queries_not_all`

- **فایل/کلاس:** `test_dashboard_performance.py` / `TestDashboardPerformance`
- **خطا:** `FileNotFoundError: 'Kharazmi_Server/routers/dashboard.py'` (و در ادامه، در صورت عبور، `audit.py:183` و `dunning.py:187` هم مسیر نسبی دارند)
- **ماهیت تست:** تست ایستا-کارایی — بررسی می‌کند `routers/dashboard.py` از `func.count`/`func.sum`، مقایسهٔ رشته‌ای `due_date < today_jalali`، کش `_dashboard_cache`/`CACHE_TTL` استفاده کند و الگوی قدیمیِ پایتونی (`parse_project_date`، `for inst in unpaid`) برنگشته باشد؛ سپس `audit.py` (وجود `count_suspicious_patterns`) و `dunning.py` (وجود `count_dunning_pending`) را هم می‌خواند. این تست تنها تستی است که **۳ فایل** را باز می‌کند (۳ نقطهٔ شکست بالقوه).
- **Root cause:** همان الگوی مسیر نسبی (`test_dashboard_performance.py:159` و `:183` و `:187`) — اولین `open()` شکست می‌خورد.
- **طبقه‌بندی:** ✅ مشکل محیط/روش اجرا (cwd)
- **اقدام:** بدون تغییر.
- **اجرای مجدد:** ✅ `PASSED`

---

## ۳) بررسی fixture / seed / environment / database isolation (مرحله ۴)

- **این ۵ تست به هیچ fixture و هیچ داده‌ای وابسته نیستند:** شمارش ارجاع به `self.db` در بدنهٔ هر پنج تست = **صفر**. آن‌ها فقط فایل سورس را می‌خوانند. پس فرضیهٔ «fixture یا دادهٔ نادرست» منتفی است.
- **کلاس‌های میزبان** (`TestAuditRadar`، `TestDashboardKPIs`، `TestDashboardPerformance`) در `setUp` خود DB موقت SQLite + `StaticPool` + `dependency_overrides[get_db]` می‌سازند؛ این setup بی‌ربط به این ۵ تست است ولی برای بقیهٔ تست‌های همان فایل‌ها لازم است.
- **DB isolation:** برقرار است. کل فایل‌ها با `DATABASE_URL` موقت اجرا شدند و DB واقعی `gaj_db.db` دست‌نخورده ماند (md5 = `f048f8d118b33c4eaa944490594121d7`).
- **پیش‌نیاز محیط:** `import main` نیازمند `DATABASE_URL` و `JWT_SECRET_KEY` است؛ بدون آن‌ها collection شکست می‌خورد (درس ثابت‌شدهٔ قبلی پروژه). `PYTHONPATH` **لازم نیست** (pytest خودش پوشهٔ تست را به `sys.path` اضافه می‌کند — تست شد).
- **هیچ فایل تنظیماتی برای تست وجود ندارد:** نه `pytest.ini`، نه `conftest.py`، نه `pyproject.toml`/`tox.ini`، و نه `.github/workflows` (CI تعریف نشده). پس هیچ چیزی cwd را تثبیت نمی‌کند.

---

## ۴) مقایسه با HEAD قبل از تسک‌های اخیر (مرحله ۵)

در commit پایه `0133d80` (قبل از Taskهای ۱ تا ۵) با `git worktree` مجزا:

| حالت اجرا روی BASE `0133d80` | نتیجه |
|---|---|
| از داخل `Kharazmi_Server` | ❌ **همان‌ها 5 failed** |
| از ریشهٔ ریپو | ✅ **5 passed** |

جمع‌بندی مقایسه:

- همان ۵ تست، **با همان پیام خطا**، **قبل از تسک‌های ما هم** شکست می‌خوردند (فقط به‌خاطر cwd).
- none از تسک‌های ما به این فایل‌ها دست نزده: `git log 0133d80..HEAD -- test_audit.py test_dashboard.py test_dashboard_performance.py` **خالی** است.
- هیچ‌یک از فایل‌های production مرتبط (`routers/audit.py`، `routers/dashboard.py`، `routers/finance.py`) در بازهٔ تسک‌های ما تغییر نکرده: `git log 0133d80..HEAD -- <فایل>` برای هر سه **خالی**.
- پس failureها **نه ساخته‌ی تسک‌های ما هستند و نه رفع‌شده توسط آن‌ها** — رفتار قبل و بعد یکسان و کاملاً وابسته به cwd است.

---

## ۵) طبقه‌بندی نهایی (مرحله ۶ — پاسخ به پنج پرسش)

| پرسش | پاسخ |
|---|---|
| bug واقعی production است؟ | ❌ خیر — برای هر ۵ مورد |
| تست outdated است؟ | ❌ خیر — assertionها با کد فعلی می‌خوانند و با اجرای درست سبز می‌شوند |
| fixture یا داده نادرست است؟ | ❌ خیر — این ۵ تست صفر ارجاع به DB دارند |
| مشکل محیط یا dependency است؟ | ✅ **بله — وابستگی به cwd (مسیر نسبی از ریشهٔ ریپو)؛ محضِ روش اجرا** |
| رفتار عمداً تغییر کرده است؟ | ❌ خیر — کد تولیدی مرتبط در این بازه دست‌نخورده است |

---

## ۶) اقدام انجام‌شده

طبق قانون کاربر («اگر مشکل محیطی بود: کد production را تغییر نده، راه اجرای صحیح را مستند کن») و «تست outdated را بدون تحلیل تغییر نده»:

- ✅ **هیچ تغییری در کد production انجام نشد.**
- ✅ **هیچ تغییری در تست‌ها انجام نشد** (نه به‌روزرسانی، نه اصلاح مسیر، نه skip).
- ✅ فقط همین سند ممیزی (checkpoint) اضافه شد.
- ✅ روش اجرای صحیح مستند شد (بخش ۷).

> نکتهٔ مهم و صادقانه: در گزارش Taskهای قبلی، این پنج مورد به‌عنوان «۵ failure از قبل موجود» گزارش می‌شد؛ ممیزی امروز نشان داد آن‌ها **محصول روش اجرای خودم** (اجرا از داخل `Kharazmi_Server` به‌جای ریشهٔ ریپو) بودند، نه نقص پروژه. پروژه روی HEAD فعلی **کاملاً سبز** است: 801 passed / 0 failed.

---

## ۷) راه اجرای صحیح (روش مستند و تأییدشدهٔ پروژه)

مستندات خودِ پروژه در `checkpoints/` هم همین را می‌گویند، مثلاً:
`checkpoints/2026-09-16_Export-to-Excel.md:67` → «اجرا از **ریشهٔ ریپو**: `PYTHONPATH=Kharazmi_Server python3 -m pytest Kharazmi_Server` → **305 passed / 0 failed**».

**دستور استاندارد (تأییدشده روی همین HEAD):**

```bash
cd /home/user/KharazmiApp                    # ← ریشهٔ ریپو (مهم)
DATABASE_URL=sqlite:////tmp/kharazmi_test.db \
JWT_SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))") \
/home/user/.venv/bin/python -m pytest Kharazmi_Server -q
# نتیجه: 801 passed / 0 failed
```

- `PYTHONPATH` لازم **نیست** (تست شد).
- برای اجرای یک فایل/تست: `pytest Kharazmi_Server/test_audit.py -q` یا `pytest "Kharazmi_Server/test_audit.py::TestAuditRadar::test_no_silent_except_pass" -q`
- **الگوی غلط (باید اجتناب شود):** `cd Kharazmi_Server && pytest -q` ⇒ ۵ FileNotFoundError کاذب.

---

## ۸) نتیجهٔ اجرای مجدد (خلاصهٔ شواهد)

| اجرا | نتیجه |
|---|---|
| هر ۵ تست، جداگانه، از ریشهٔ ریپو | ✅ **5 passed** |
| هر ۵ تست، جداگانه، از داخل `Kharazmi_Server` | ❌ **5 failed** (همان FileNotFoundErrorها) |
| کل `test_audit.py` از ریشه | ✅ 14 passed |
| کل `test_audit.py` از داخل `Kharazmi_Server` | ❌ 3 failed / 11 passed |
| کل `test_dashboard.py` از ریشه | ✅ 9 passed |
| کل `test_dashboard.py` از داخل `Kharazmi_Server` | ❌ 1 failed / 8 passed |
| کل `test_dashboard_performance.py` از ریشه | ✅ 2 passed |
| کل `test_dashboard_performance.py` از داخل `Kharazmi_Server` | ❌ 1 failed / 1 passed |
| **کل suite از ریشهٔ ریپو (ROOT)** | ✅ **801 passed / 0 failed** |
| کل suite از داخل `Kharazmi_Server` | ❌ 5 failed / 796 passed |
| مجموع تست‌های collect‌شده در هر دو حالت | ۸۰۱ (بدون گم‌شدن تست) |
| BASE `0133d80` — هر ۵ تست از داخل `Kharazmi_Server` | ❌ 5 failed (اثبات پیش‌موجود بودن) |
| BASE `0133d80` — هر ۵ تست از ریشه | ✅ 5 passed |

---

## ۹) ریسک‌ها و محدودیت‌های باقی‌مانده

1. **شکنندگی ذاتی (طراحی، نه failure فعلی):** این ۵ تست از نوع static-analysis هستند (خواندن متن سورس + `assertIn` روی رشته). با هر refactor بی‌خطر در `audit.py`/`dashboard.py`/`finance.py` ممکن است به‌اشتباه قرمز شوند. **تغییری داده نشد** (خارج از محدودهٔ این Task و نیازمند تصمیم شما).
2. **cwd-sensitive بودن:** چون `pytest.ini`/`conftest.py` وجود ندارد، هیچ چیز جلوی اجرای اشتباه از داخل `Kharazmi_Server` را نمی‌گیرد. **پیشنهاد اختیاری (نیازمند تأیید شما):** افزودن یک `pytest.ini` در ریشه + `conftest.py` که مسیرها را مطلق کند، یا اصلاح ۷ نقطهٔ `open()` به مسیر مطلق نسبت به فایل تست. **در این Task انجام نشد** چون قانون شما برای «مشکل محیطی» فقط مستندسازی است.
3. **نبود CI:** هیچ `.github/workflows` وجود ندارد؛ پس این نوع خطای cwd در CI گرفته نمی‌شود. پیشنهاد اختیاری: افزودن یک workflow که suite را از ریشهٔ ریپو اجرا کند.
4. **۱۷۶ فایل تست / ۸۰۱ تست** فقط با تنظیم `DATABASE_URL` و `JWT_SECRET_KEY` قابل اجرا هستند؛ بدون آن‌ها collection شکست می‌خورد (مستند شد).

---

## ۱۰) Commit و Push

- **Commit SHA:** در گزارش نهایی پس از commit ثبت می‌شود؛ SHA داخل همان commit قابل درج نیست.
- **وضعیت Push:** در گزارش نهایی اعلام می‌شود.
- **Commit message (audit-only، طبق دستور کاربر):** `chore: document existing test failures`
- **Branch:** `arena/01a0bf8d-kharazmiapp` (تنها branch کاری؛ PR/merge بدون دستور صریح ساخته نمی‌شود).
- **فایل‌های تغییرکرده در این commit:** فقط همین checkpoint — **صفر تغییر در کد production، صفر تغییر در تست‌ها**.
