# نوبت ۶-الف — باگ بحرانی کشف‌شده توسط CI: مسیر ذخیره‌سازی فایل‌ها (آپلودها)

- **تاریخ:** ۲۰۲۶-۰۹-۲۱ (پیدا شده در جریان نوبت ۶ / B2)
- **Branch:** `arena/01a0bf8d-kharazmiapp`
- **Base HEAD:** `338199973cd9f1ce2715c26a70c1965d17221fe9`
- **چگونه پیدا شد:** اولین اجرای واقعی CI (نوبت B2) در ۳۰ ثانیه و **در گام «اجرای کل سوئیت»** شکست خورد، در حالی که همان سوئیت روی ماشین محلی سبز بود. لاگ گیت‌هاب از این محیط قابل دریافت نبود، پس علت ریشه‌ای با «بازسازی محیط CI» و ممیزی مسیرهای فایل پیدا شد.

---

## ۱) مشکل و ریشه (باگ واقعی در کد production، نه فقط تست)

سه روتر مسیر **مطلقِ ماشین توسعه‌دهنده** را هاردکد کرده بودند و همان‌جا در زمان import پوشه می‌ساختند:

```python
# routers/homework.py
UPLOAD_DIR = "/home/user/uploads/homework"      # آپلود تکالیف
os.makedirs(UPLOAD_DIR, exist_ok=True)
# routers/exams.py
PDF_DIR    = "/home/user/uploads/report_cards"  # کارنامه PDF
os.makedirs(PDF_DIR, exist_ok=True)
# routers/messages.py
UPLOAD_DIR = "/home/user/uploads/messages"      # پیوست پیام‌رسان
os.makedirs(UPLOAD_DIR, exist_ok=True)
```

و مسیر پروفایل/لوگو **نسبت به پوشهٔ اجرا** ساخته می‌شد:

```python
filepath = os.path.join("uploads/profiles", unique_filename)   # students.py / teachers.py / admin.py
os.makedirs("uploads/profiles", exist_ok=True)                 # main.py
path = os.path.join("uploads/profiles", safe)                  # main.py → سرو فایل
```

### این باگ در آموزشگاه چه مشکلی ایجاد می‌کرد؟

| سناریو | پیامد واقعی |
|---|---|
| سرور آموزشگاه با کاربر دیگری اجرا شود (مثلاً `www-data` یا هر کاربری که `/home/user` را ندارد — تقریباً همهٔ سرورها) | **برنامه بالا نمی‌آید** (`PermissionError` در زمان import) ⇒ آپلود تکالیف، صدور کارنامه و پیوست پیام‌رسان کاملاً از کار می‌افتد؛ کاربر خطای ۵۰۰ می‌بیند |
| حتی اگر بالا بیاید و `/home/user` قابل ساخت باشد | فایل‌های کاربران **بیرون از پروژه/بکاپ** ذخیره می‌شوند ⇒ با بازگردانی بکاپ سرور، تکالیف و کارنامه‌های دانش‌آموزان گم می‌شوند |
| اجرای سرور از پوشهٔ متفاوت (مثلاً `systemd WorkingDirectory=/`) | عکس پروفایل/لوگو در جای دیگری نوشته می‌شود و اندپوینت سرو فایل آن را پیدا نمی‌کند ⇒ **عکس‌ها ۴۰۴ می‌شوند** (سابقهٔ تصویری پرسنل/دانش‌آموز ظاهراً ناپدید می‌شود) |
| استقرار چند-نمونه‌ای (docker/CI) | ناسازگاری مسیرها: فایل‌های یک نوع در `/home/user/uploads`، نوع دیگر در `<cwd>/uploads` |

برای آموزشگاه یعنی: **ریسک گم‌شدن سابقهٔ تکالیف/کارنامه (اصل ۱ سند تصمیم‌ها) و از کار افتادن کامل سه سرویس اصلی** در صورت جابه‌جایی سرور.

---

## ۲) رفتار قبل و بعد

| موضوع | قبل | بعد |
|---|---|---|
| ریشهٔ فایل‌ها | سه مسیر مختلف: `/home/user/uploads/…` و `<cwd>/uploads/…` | **یک ریشهٔ واحد:** `Kharazmi_Server/uploads/` |
| جابه‌جایی ریشه (دیسک دادهٔ جدا) | ممکن نبود (هاردکد) | با متغیر محیطی `KHARAZMI_UPLOAD_ROOT` |
| وابستگی به پوشهٔ اجرا | ✅ داشت (پروفایل/لوگو) | ❌ ندارد (مسیر مطلق از محل `storage.py`) |
| رفتار روی سرور بدون `/home/user` | crash در import | کار می‌کند |
| فایل‌های قدیمی | — | همچنان **خوانده/سرو** می‌شوند (سازگاری عقب‌رو: ریشهٔ فعلی → `<repo>/uploads` → `<cwd>/uploads` → `/home/user/uploads`) |
| گیت | پوشهٔ uploads ردیابی‌نشده | `Kharazmi_Server/.gitignore` پوشهٔ زمان‌اجرا را نادیده می‌گیرد |

**ماژول جدید** `Kharazmi_Server/storage.py`:

```python
BASE_DIR = os.path.dirname(os.path.abspath(__file__))       # همیشه، مستقل از cwd
DEFAULT_UPLOAD_ROOT = os.path.join(BASE_DIR, "uploads")
def upload_root()      # KHARAZMI_UPLOAD_ROOT یا پیش‌فرض پروژه
def storage_dir(*p)    # ساخت پوشه + مسیر مطلق (برای نوشتن)
def storage_path(*p)   # مسیر مطلق بدون ساخت (برای خواندن/حذف)
def legacy_upload_roots() / resolve_existing(*p)  # سازگاری عقب‌رو (فقط خواندن/حذف)
```

---

## ۳) فایل‌های تغییرکرده

| فایل | تغییر |
|---|---|
| `Kharazmi_Server/storage.py` | **جدید** — ریشهٔ واحد + سازگاری عقب‌رو |
| `Kharazmi_Server/routers/homework.py` | مسیر آپلود تکلیف → `storage_dir("homework")` (resolve در زمان نوشتن) |
| `Kharazmi_Server/routers/exams.py` | مسیر کارنامه PDF → `storage_dir("report_cards")` |
| `Kharazmi_Server/routers/messages.py` | مسیر پیوست‌ها → `storage_dir("messages")` |
| `Kharazmi_Server/routers/students.py` | نوشتن عکس پروفایل → `storage_dir("profiles")` + حذف فایل قبلی با `resolve_existing` |
| `Kharazmi_Server/routers/teachers.py` | همان، برای معلم |
| `Kharazmi_Server/routers/admin.py` | همان، برای لوگوی آموزشگاه |
| `Kharazmi_Server/main.py` | ساخت پوشهٔ پروفایل + سرو `/uploads/{file}` (با fallback مسیر قدیمی) |
| `Kharazmi_Server/.gitignore` | + `uploads/` (دادهٔ زمان اجرا) |
| `Kharazmi_Server/test_storage_paths.py` | **جدید** — ۱۳ تست |

**بدون تغییر:** منطق مالی، permissionها، اسکیمای دیتابیس، قرارداد پاسخ‌ها، کد اندروید.

---

## ۴) تست‌ها

| سنجش | نتیجه |
|---|---|
| تست جدید `test_storage_paths.py` (۱۳ تست) | ✅ **13 passed** |
| **pre-fix proof** (worktree روی `3381999` + ماژول storage + تست) | ❌ **5 failed / 8 passed** — شامل «مسیر ماشینی در کد»، «نوشتن نسبی به cwd»، و «فایل در ریشهٔ تعیین‌شدهٔ تست ذخیره نشد» |
| کل سوئیت از ریشهٔ ریپو | ✅ **903 passed** |
| کل سوئیت از داخل `Kharazmi_Server/` | ✅ **903 passed** (گارد B1) |
| md5 دیتابیس واقعی | `f048f8d118b33c4eaa944490594121d7` — **بی‌تغییر** |
| اجرای واقعی CI روی گیت‌هاب پس از push | در گزارش نهایی اعلام می‌شود |

**پوشش تست‌ها:** نبود مسیر مطلق ماشینی در همهٔ ماژول‌های سرور (اسکن AST، به‌جز `storage.py` که فقط سازگاری عقب‌رو دارد) · نبود الگوی نوشتن نسبی به cwd · پیش‌فرض ریشه داخل پروژه · اثر `KHARAZMI_UPLOAD_ROOT` · عدم ساخت پوشه در `storage_path` · ترجیح ریشهٔ فعلی و fallback به ریشهٔ قدیمی · **اندپوینت واقعی آپلود تکلیف** (فایل در ریشهٔ تعیین‌شده ذخیره می‌شود) · **اندپوینت واقعی عکس پروفایل** (+ سرو شدن همان فایل از `/uploads/{name}`) · سرو فایل قدیمی از مسیر قبلی · مسدودبودن path traversal · عدم نوشتن در پوشهٔ پروژه وقتی override تنظیم شده است.

---

## ۵) وضعیت build اندروید

**build واقعی انجام نشد و ادعا نمی‌شود** (JDK/SDK در محیط نیست). این نوبت صفر تغییر در سمت اندروید دارد.

> نکتهٔ جانبی (خارج از این commit): فایل کمکی `KharazmiAdmin/ui_clickable_audit.py:12` هم یک مسیر مطلق (`/home/user/KharazmiAdmin`) دارد. این یک **ابزار توسعه** است (نه کد اجرایی اپ) و در گزارش نهایی به‌عنوان «یافتهٔ باز» ثبت شد.

---

## ۶) ریسک‌ها و محدودیت‌های باقی‌مانده

1. **جابه‌جایی محل فایل‌ها در سرور واقعی:** از این پس فایل‌ها در `Kharazmi_Server/uploads/` نوشته می‌شوند. فایل‌های قبلی که در `<cwd>/uploads` یا `/home/user/uploads` هستند **خوانده می‌شوند** (fallback) ولی **منتقل نمی‌شوند**؛ برای انتقال قطعی باید دستی به ریشهٔ جدید کپی شوند (یا `KHARAZMI_UPLOAD_ROOT` روی مسیر قدیمی تنظیم شود).
2. **بدون migration/DB:** هیچ تغییری در دیتابیس انجام نشد؛ `profile_image`/`logo_path` فقط نام فایل را نگه می‌دارند (همان قرارداد قبلی).
3. **`messages.py`** مسیر پیوست را اصلاح‌شده دارد ولی خودِ ثابت `UPLOAD_DIR` در آن فایل جای دیگری استفاده نمی‌شود (باقی‌ماندهٔ کد قبلی) — دست‌نخورده ماند تا دامنهٔ تغییر کوچک بماند.
4. **ابزار `KharazmiAdmin/ui_clickable_audit.py`** همچنان مسیر مطلق دارد (انتظار می‌رود داخل همین commit اصلاح شود وگرنه به‌عنوان یافتهٔ باز در گزارش می‌آید).
5. **CI سبز شدن پس از این fix باید تأیید شود** — نتیجهٔ اجرای واقعی در گزارش نهایی می‌آید.

---

## ۷) Commit و Push

- **Commit SHA:** در گزارش نهایی پس از commit ثبت می‌شود؛ SHA داخل همان commit قابل درج نیست.
- **وضعیت Push:** در گزارش نهایی اعلام می‌شود.
- **Commit message:** `fix: store uploaded files under the project instead of a hardcoded path`
- **Branch:** `arena/01a0bf8d-kharazmiapp` — PR/merge بدون دستور صریح ساخته نمی‌شود.
- **نوبت بعدی نقشه:** C1 — اعلان واقعی پورتال شاگرد/ولی.
