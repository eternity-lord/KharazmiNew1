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

### CI (گیت‌هاب اکشنز)

workflow `.github/workflows/tests.yml` در هر push روی شاخه‌های کاری این موارد را اجرا می‌کند:

1. کل سوئیت از **ریشهٔ ریپو** با DB موقت،
2. گارد مستقل‌بودن از پوشهٔ اجرا (اجرا از داخل `Kharazmi_Server/`),
3. گارد یکپارچگی: md5 فایل `Kharazmi_Server/gaj_db.db` قبل و بعد از تست‌ها باید یکی باشد (در غیر این‌صورت CI شکست می‌خورد).

> تست‌های اندروید در CI اجرا نمی‌شوند (نیازمند JDK/SDK و Gradle است)؛ تغییرات سمت اندروید باید دستی بررسی/بیلد شوند.
