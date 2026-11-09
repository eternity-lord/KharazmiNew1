# نوبت ۱۲ت — سازمان‌دهی تست‌ها: انتقال کل سوئیت به `Kharazmi_Server/tests/`

- **تاریخ:** ۲۰۲۶-۰۹-۲۱
- **Branch:** `arena/01a0bf8d-kharazmiapp`
- **Base HEAD:** `6bead1c8be10ed907c4c178eada5d71508d2fae2` (انتشار گزارش پایانی)
- **درخواست کاربر:** «تست‌های پایتونی قبلی را بنداز توی پوشهٔ تست» — سپس ساخت تست‌های جدید در نوبت‌های بعد.
- **دامنه:** **صفر تغییر در کد برنامه** (سرور/اندروید). فقط جابه‌جایی فایل‌های تست + تثبیت importها + به‌روزرسانی ابزارها/مستندات اجرا.

---

## ۱) چه چیزی تغییر کرد

| قبل | بعد |
|---|---|
| ۵۵ فایل `Kharazmi_Server/test_*.py` کنار کد سرور | همه در `Kharazmi_Server/tests/test_*.py` |
| بدون conftest؛ import ماژول‌های سرور به مسیر فایل تست تکیه داشت | `Kharazmi_Server/tests/conftest.py` مسیر `Kharazmi_Server/` را در `sys.path` تثبیت می‌کند ⇒ اجرا از **هر پوشه‌ای** یکسان کار می‌کند |
| ۸ فایل مسیر فایل‌های سرور را «نسبت به محل خودشان» می‌ساختند | همان helperها یک سطح بالاتر (`parents[1]`)指向 می‌شوند ⇒ به فایل‌های واقعی سرور می‌رسند |
| `pytest.ini`: `testpaths = Kharazmi_Server` | `testpaths = Kharazmi_Server/tests` |
| CI: `pytest Kharazmi_Server` + اجرای فایل‌ها از داخل `Kharazmi_Server/` | CI: `pytest Kharazmi_Server/tests` + اجرای `tests/test_*.py` از داخل `Kharazmi_Server/` (قفل B1) |
| README مسیرهای قدیمی را مستند می‌کرد | README ساختار جدید + دستورهای به‌روز |

**فایل‌های نیازمند اصلاح مسیر (چون مسیر فایل‌های سرور را می‌ساختند):** `test_audit.py` · `test_dashboard.py` · `test_dashboard_performance.py` · `test_audit_trail.py` · `test_exports.py` · `test_storage_paths.py` · `test_security_audit.py` · `test_suite_cwd_independence.py` (این آخری خودش گاردِ cwd است: مسیر کشف فایل‌های تست و اجرای زیرفرایندی هم به‌روز شد).

**بدون تغییر:** هیچ فایل کد سرور (`Kharazmi_Server/*.py` و `routers/`) و هیچ فایل اندروید (`KharazmiAdmin/`) لمس نشد.

---

## ۲) نتیجهٔ اجراها (قبل از انتقال: ۹۶۶ passed)

| مسیر اجرا | نتیجه |
|---|---|
| از ریشهٔ ریپو، صریح: `pytest Kharazmi_Server/tests -q` | ✅ **966 passed** (۸۷.۷s) |
| از داخل `Kharazmi_Server/`: `pytest tests -q` | ✅ **966 passed** (۸۷.۵s) |
| از داخل `Kharazmi_Server/tests/`: ۸ فایل حساس به مسیر | ✅ **85 passed** (۲۰.۳s) |
| از ریشه، bare: `pytest -q` (کشف از `pytest.ini`) | ✅ **966 tests collected** |
| md5 دیتابیس واقعی | `f048f8d118b33c4eaa944490594121d7` — **بی‌تغییر** |

⇒ شمارش تست‌ها **دقیقاً برابر** قبل و بعد است؛ هیچ تستی جا نماند و هیچ تستی شکسته نشد.

---

## ۳) ریسک‌ها / نکات باقی‌مانده

1. **مسیرِ داخل خودِ فایل‌های تست در مستنداتشان:** بعضی فایل‌ها در کامنت سرصفحه دستور اجرا با مسیر قدیمی دارند (مثل `python3 -m pytest test_x.py -q` از داخل سرور). این‌ها فقط کامنت‌اند و اجرای تست تحت تأثیر نیست؛ در نوبت‌های بعدی (هنگام کار روی همان فایل‌ها) به‌روز می‌شوند تا تاریخچه دست‌کاری نشود.
2. **`git log --follow`** برای پیگیری تاریخچهٔ هر تست لازم است (فایل‌ها Rename شده‌اند).
3. **CI** به‌روزرسانی شد ولی تأیید سبز بودنش بعد از این push در گزارش اعلام می‌شود.
4. **تست‌های اندروید** همچنان در CI اجرا نمی‌شوند (نیاز به JDK/SDK/Gradle) — طبق محدودیت محیط.

---

## ۴) Commit و Push

- **Commit SHA:** در گزارش نهایی پس از commit ثبت می‌شود؛ SHA داخل همان commit قابل درج نیست.
- **Commit message:** `chore: move the python test suite into a dedicated tests directory`
- **Branch:** `arena/01a0bf8d-kharazmiapp`
