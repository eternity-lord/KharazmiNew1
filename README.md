# KharazmiApp

سامانهٔ مدیریت آموزشگاه خوارزمی — دو بخش مستقل:

- **`Kharazmi_Server/`** — بک‌اند (FastAPI + SQLAlchemy). حضور و غیاب، شهریه و اقساط، کیف پول معلم/آموزشگاه، گزارش‌های مالی و چاپی، اعلان‌ها و پورتال شاگرد/ولی.
- **`KharazmiAdmin/`** — اپ اندروید ادمین/معلم (Kotlin).

> **قانون طلایی این مخزن:** دیتابیس واقعی آموزشگاه (`Kharazmi_Server/gaj_db.db`) هرگز در تست‌ها دست‌کاری نمی‌شود؛ همهٔ تست‌ها روی یک DB موقت اجرا می‌شوند. (این موضوع در CI هم به‌صورت خودکار با مقایسهٔ md5 فایل بررسی می‌شود.)

---

## Running tests

> **ساختار تست‌ها:** همهٔ تست‌های پایتونی در پوشهٔ `Kharazmi_Server/tests/` قرار دارند
> (فایل‌های `test_*.py`). `Kharazmi_Server/tests/conftest.py` مسیر ماژول‌های سرور را در
> `sys.path` تثبیت می‌کند تا اجرای تست‌ها از **هر پوشه‌ای** کار کند.

### پیش‌نیاز

- Python 3.11
- یک محیط مجازی + وابستگی‌ها:

```bash
python3 -m venv .venv
.venv/bin/pip install -r Kharazmi_Server/requirements.txt pytest
```

### اجرای کل سوئیت (روش استاندارد پروژه)

دو متغیر محیطی لازم است: `DATABASE_URL` (روی یک **DB موقت**، نه دیتابیس واقعی) و `JWT_SECRET_KEY`.

```bash
# از ریشهٔ ریپو (روش مستند پروژه)
DATABASE_URL=sqlite:////tmp/kharazmi_test.db \
JWT_SECRET_KEY=test-secret-not-production \
python3 -m pytest Kharazmi_Server/tests -q
```

سوئیت **مستقل از پوشهٔ اجرا** است؛ هر یک از این دو هم کار می‌کند:

```bash
# از ریشه — کشف تست‌ها از pytest.ini (testpaths = Kharazmi_Server/tests)
pytest -q

# از داخل خود پوشهٔ سرور
cd Kharazmi_Server && pytest tests -q
```

### اجرای یک فایل یا یک تست

```bash
python3 -m pytest Kharazmi_Server/tests/test_reports.py -q
python3 -m pytest "Kharazmi_Server/tests/test_reports.py::TestReports::test_student_statement" -q
```

### نکته‌ها

- **`DATABASE_URL` را حتماً موقت بگیرید** (`/tmp/...`). بدون آن، `from main import app` روی دیتابیس پیش‌فرض پروژه کار می‌کند.
- `JWT_SECRET_KEY` در تست‌ها می‌تواند هر مقدار تستی باشد؛ **هرگز** مقدار واقعی محیط تولید را در ترمینال/فایل تست نگذارید.
- تست‌های مربوط به ریت‌لیمیت در چند فایل به‌صورت داخلی `limiter.enabled = False` می‌کنند (الگوی موجود پروژه).
- `pytest.ini` در ریشه، مسیر کشف تست‌ها (`Kharazmi_Server/tests`) را تثبیت می‌کند و درخت اندروید (`KharazmiAdmin/`) و مستندات (`checkpoints/`) را از کشف تست بیرون می‌گذارد.

### سوئیت دوم: `tests/route_audit` (۲۴۹ تستِ route-level)

این سوئیت **هر route** اپ را با دیتابیسِ seed‌شدهٔ قطعی و oracle محاسباتی بررسی می‌کند
(مقادیر پولی، نقش‌ها، شکل JSON، سازگاری با DTOهای اندروید). عمداً در `testpaths` فایل
`pytest.ini` نیست و باید **در فرایند جدا** اجرا شود:

```bash
DATABASE_URL=sqlite:////tmp/kharazmi_route_audit.db \
JWT_SECRET_KEY=test-secret-not-production \
python3 -m pytest tests/route_audit -q
```

> ⚠️ **دو سوئیت را در یک فرایند اجرا نکنید.** `models.py` در اولین import، `engine` را از
> `DATABASE_URL` می‌سازد و در `sys.modules` کش می‌شود؛ بعدتر که conftestِ route_audit
> متغیر را به DB موقتِ خودش تغییر می‌دهد، seed روی همان engine قدیمی می‌نویسد. نتیجهٔ
> اندازه‌گیری‌شده: `1326 passed, 202 errors` با `UNIQUE constraint failed: branches.id`.
> در CI هم این دو، **دو job جدا** هستند.
>
> سابقه: این سوئیت به‌دلیل «پوسیدگی زمانیِ» seed (تاریخ ثابت `2026-09-28` در برابر
> پاک‌سازی سشنِ ۳۰ روزه با ساعت واقعی در `import main`) از ۲۰۲۶-۱۰-۲۸ به بعد بی‌سروصدا
> قرمز شده بود؛ ریشه‌یابی و تعمیرش در
> `checkpoints/2026-11-09-route-audit-clock-rot-fix.md` مستند است.

### lint و type-check

پیکربندی راف و mypy در `pyproject.toml` ریشه است (وابستگی‌ها در
`Kharazmi_Server/requirements-dev.txt`):

```bash
.venv/bin/pip install -r Kharazmi_Server/requirements.txt -r Kharazmi_Server/requirements-dev.txt
.venv/bin/ruff check .            # گزارش lint
.venv/bin/ruff check . --fix      # اصلاح خودکارِ امن
.venv/bin/mypy                    # بررسی تایپ (پیکربندی تدریجی)
```

> چند `ignore` در پیکربندی **بار رفتاری** دارند و نباید «تمیزکاری» شوند: `E712`
> (در SQLAlchemy عبارت `Col == True` کوئری SQL می‌سازد)، `RUF001/002/003` (متن فارسی
> زبان محصول است) و `B008` (الگوی `Depends()` با `extend-immutable-calls` قانونی شده).
> دلیل کامل در `checkpoints/2026-11-09-refactor-phase1-hygiene.md`.

### CI (گیت‌هاب اکشنز)

workflow `.github/workflows/tests.yml` در هر push روی شاخه‌های کاری این موارد را اجرا می‌کند:

1. کل سوئیت از **ریشهٔ ریپو** با DB موقت،
2. گارد مستقل‌بودن از پوشهٔ اجرا (اجرا از داخل `Kharazmi_Server/`),
3. گارد یکپارچگی: md5 فایل `Kharazmi_Server/gaj_db.db` قبل و بعد از تست‌ها باید یکی باشد (در غیر این‌صورت CI شکست می‌خورد).
4. job جدا برای سوئیت `tests/route_audit` (۲۴۹ تست route-level) با همان گارد md5.

> تست‌های اندروید در CI اجرا نمی‌شوند (نیازمند JDK/SDK و Gradle است)؛ تغییرات سمت اندروید باید دستی بررسی/بیلد شوند.
