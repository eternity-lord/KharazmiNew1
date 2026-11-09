# FIX F-T1 + F-T2 — اعتبارسنجی مرکزی اقساط شهریه (۲۰۲۶-۰۹-۱۷)

برنچ: `arena/01a0aac2-kharazmiapp` | ریپو: `eternity-lord/KharazmiApp`
پیش‌نیاز: ممیزی `checkpoints/2026-09-17_TUITION-INSTALLMENTS-audit.md` (کامیت `145dedf`) که این دو باگ را مستند کرد.

## ۰) یادآوری محیط (سندباکس ریست شده بود)
سندباکس بین تسک‌ها ریست شده بود: `HEAD` روی `2b5ea9f` (عقب‌تر)، درخت dirty (۱۱ فایل M)،
وابستگی‌ها نصب نبود و `.env` وجود نداشت ⇒ همه‌ی تست‌ها با `RuntimeError: JWT_SECRET...` می‌مردند. ریکاوری:
```bash
git fetch origin '+refs/heads/arena/01a0aac2-kharazmiapp:refs/remotes/origin/...'
# تأیید شد هر ۱۱ فایل M روی دیسک عیناً برابر محتوای کامیت ریموت است (sha256) ⇒ هیچ کاری گم نشده
git reset --hard origin/arena/01a0aac2-kharazmiapp     # → 145dedf
python3 -m pip install --user -r Kharazmi_Server/requirements.txt pytest
# ساخت Kharazmi_Server/.env سندباکس (gitignore شده) با DATABASE_URL=sqlite:////tmp/tuition_audit.db
```
`.env` صرفاً سندباکس است، `git check-ignore` تأیید کرد (در کامیت نمی‌آید) و DB آن در `/tmp` است.

## ۱) baseline (قبل از تغییر، روی `145dedf`)
| دستور | نتیجه |
|---|---|
| `python -m compileall Kharazmi_Server` | exit 0 |
| `pytest -q Kharazmi_Server/test_tuition_installments_audit.py` | **41 passed / 2 failed** (F-T1, F-T2) |
| `pytest -q Kharazmi_Server` | **459 passed / 2 failed** / 38.6s |

## ۲) شرح F-T1 (قبل از fix)
مسیر «ثبت‌نام همراه اقساط» (`schemas.InstallmentCreate` + `routers/classes.py:421` و `routers/students.py:170`)
هیچ اعتبارسنجی‌ای نداشت: `amount=-5`، `amount=0`، `due_date="bad-date"`، `due_date="1405/13/45"` همه ذخیره می‌شدند،
در حالی که اندپوینت مستقل `POST /finance/installments` همان ورودی‌ها را رد می‌کرد ⇒ سیاست ناهمگون و ردیف مالی نامعتبر.
قسط با مبلغ ≤۰ بعداً از مسیر وصول هم قابل تسویه نبود (`finance.py:1815` ⇒ ۴۰۰) و قسط با تاریخ بی‌قالب هرگز معوقه نمی‌شد.

## ۳) شرح F-T2 (قبل از fix)
اعتبارسنجی `due_date` در `InstallmentCreateRequest`/`InstallmentUpdateRequest` فقط regex شکل بود
(`^\d{4}/(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])$`) ⇒ روز ۳۱ برای ماه‌های ۳۰روزه (۷..۱۲) و ۳۰ اسفند سال غیرکبیسه
می‌پذیرفت: `1405/07/31` و `1405/12/30` جدا شدند ولی `parse_project_date` بعداً `None` می‌داد ⇒ وضعیت همیشه
«در انتظار»، بدون معوقه‌شدن در داشبورد (مقایسه‌ی رشته‌ای) و بدون ورود به dunning.

## ۴) راه‌حل: یک اعتبارسنجی مرکزی، مصرف‌شده در همه‌ی مسیرها
`Kharazmi_Server/validation.py` (همان ماژول اعتبارسنجی مشترک پروژه) — سه تابع جدید:
- `validate_installment_amount(value) -> int` — فقط عدد صحیح **مثبت**؛ `100.5`/`"100.5"`/`nan`/`inf`/`True` رد می‌شوند
  (اعشار هرگز truncate نمی‌شود)؛ سازگاری با ورودی‌های صحیح‌مقدار قبلی (`100.0`، `"100"`) حفظ شد.
- `validate_jalali_due_date(value) -> str` — قالب `yyyy/mm/dd` (**ASCII**) + وجود واقعی روز با `parse_project_date`
  (تقویم خود پروژه). قالب و پیام خطا از حذف regex قدیمی یکدست شد.
- `normalize_installment_fields` / `normalize_installments` — سنجش یک یا همه‌ی اقساط یک درخواست.

مصرف‌کننده‌ها (همه از همین توابع):
| مسیر | فایل | لایه |
|---|---|---|
| ثبت‌نام همراه اقساط | `schemas.InstallmentCreate` (استفاده در `EnrollmentCreate` و `StudentRegisterAndEnrollRequest`) | schema ⇒ **۴۲۲** |
| ساخت قسط مستقل + ویرایش قسط | `routers/finance.py` → `InstallmentCreateRequest` / `InstallmentUpdateRequest` | schema ⇒ **۴۲۲** |
| ثبت‌نام (endpoint) | `routers/classes.py::add_enrollment` | گارد پیش از نوشتن ⇒ **۴۰۰** |
| ثبت دانش‌آموز + ثبت‌نام | `routers/students.py::register_and_enroll_student` | گارد پیش از نوشتن ⇒ **۴۰۰** |

### چرا ۴۲۲ و چرا ۴۰۰ (تصمیم status code — بند ۷ درخواست)
- خطاهای Pydantic در مرز درخواست توسط FastAPI با **۴۲۲ Unprocessable Entity** برگردانده می‌شوند؛ چون قاعده در
  schema پیاده شده، **هر دو مسیر برای کلاینت HTTP دقیقاً ۴۲۲ می‌دهند** و پیام خطایشان هم یکی است (تست دارد).
- گاردهای داخل endpoint فقط برای فراخوان‌های داخلی/آینده‌ای هستند که schema را دور می‌زنند؛ status آن‌ها
  **۴۰۰** انتخاب شد چون همان الگوی موجود همین اندپوینت‌هاست: خطای تخفیف در `add_enrollment` ⇒ ۴۰۰، «شهریه باید مثبت
  باشد» در `register_and_enroll_student` ⇒ ۴۰۰ و «مبلغ قسط معتبر نیست» در `pay_installment_manually` ⇒ ۴۰۰.
  گاردها **پیش از هر نوشتنی** اجرا می‌شوند تا ثبت‌نام/قسط/تراکنش نیمه‌کاره ممکن نباشد.

## ۵) فایل‌های تغییرکرده (۷ فایل)
| فایل | تغییر |
|---|---|
| `Kharazmi_Server/validation.py` | +۷۰: اعتبارسنجی مرکزی قسط (مبلغ/تاریخ) |
| `Kharazmi_Server/schemas.py` | +۲۱/-۳: `InstallmentCreate` صاحب `gt=0` + دو validator مرکزی |
| `Kharazmi_Server/routers/finance.py` | +۳۲/-۶: حذف regex شکلی، validator مرکزی برای create/update خزانه‌ی قسط |
| `Kharazmi_Server/routers/classes.py` | +۲۱/-۵: سنجش مرکزی پیش از نوشتن + درج مقادیر سنجیده |
| `Kharazmi_Server/routers/students.py` | +۲۰/-۵: همان گارد در مسیر ثبت دانش‌آموز + ثبت‌نام |
| `Kharazmi_Server/test_tuition_installments_audit.py` | +۳۲۹/-۳۰: دو تست یافته‌محور ⇒ رگرسیون سبز + ۳۶ تست جدید |
| `Kharazmi_Server/test_audit.py` | +۱۶/-۶: گارد منقضی «finance.py دست نخورد» ⇒ invariant پایدار (توضیح پایین) |

`git diff --stat`: 451 insertion(+), 60 deletion(-) روی ۷ فایل.

### درباره‌ی `test_audit.py` و قاعده‌ی «۶ فایل ممنوعه»
تست `test_finance_not_touched` یک گارد limited-scope از تسک ممیزی بود که با `git diff --name-only HEAD~1` چک می‌کرد
finance.py تغییر نکرده باشد. چون fix تأییدشده‌ی F-T2 **باید** در `finance.py` انجام شود، این گارد منقضی شد و با
`test_finance_uses_central_installment_validation` جایگزین شد: حالا asserts می‌کند finance.py اعتبارسنجی مرکزی را
import کرده، `validate_jalali_due_date` را به‌کار می‌برد و regex شکلی قدیمی (`Field(pattern=`) برنگشته است.
سایر فایل‌های حساس (timeline/audit/dunning/dashboard) دست‌نخورده‌اند (sha256 دیسک == HEAD).

## ۶) تست‌های اضافه/اصلاح‌شده (۳۸ تست جدید؛ فایل ممیزی: ۴۳ ⇒ ۸۱)
دو تست یافته‌محور قبلی **حذف نشدند** بلکه به رگرسیون سبز تبدیل شدند (منطقشان حالا در تست‌های `test_fix_t1_*`/`test_fix_t2_*`).
| تست | چه چیزی را قفل می‌کند |
|---|---|
| `test_fix_t1_invalid_installments_rejected_identically_on_both_paths` (۷ پارامتر) | ۷ payload نامعتبر (شامل amount=-5/0، bad-date، 1405/13/45، 100.5، 1405/07/31، 1405/12/30) در هر دو مسیر رد می‌شوند و هیچ ردیفی ساخته نمی‌شود |
| `test_fix_t1_error_messages_are_identical_on_both_paths` | پیام خطای دو مسیر عیناً یکی است ⇒ اعتبارسنجی مرکزی |
| `test_fix_t1_invalid_installment_writes_nothing_at_all` | نه ردیف قسط، نه ثبت‌نام نیمه‌کاره، نه `Transaction` ناقص، نه `Notification`/`SmsLog`، نه تغییر بدهی، نه draft یادآوری؛ گارد داخلی ⇒ ۴۰۰ |
| `test_fix_t1_amount_must_be_positive_integer_on_both_paths` (۱۰ پارامتر) | صفر/منفی/اعشاری/`nan`/`inf`/`True` در هر دو مسیر رد |
| `test_fix_t1_fractional_amount_is_not_silently_truncated` | ۱۰۰٫۵ هرگز ۱۰۰ نمی‌شود؛ سازگاری `100.0` و `"100"` |
| `test_fix_t1_valid_installments_still_saved_by_enrollment_path` | رگرسیون مثبت: اقساط معتبر با همان مبلغ/تاریخ ذخیره و بدهی درست |
| `test_fix_t1_central_validator_is_shared_by_every_creation_path` | منبع حقیقت واحد (مبلغ/تاریخ/مرز کبیسه) |
| `test_fix_t1_http_layer_returns_422_on_both_endpoints` | TestClient واقعی: `POST /finance/installments` و `POST /enrollments/add` ⇒ **۴۲۲** و DB دست‌نخورده |
| `test_fix_t2_calendar_valid_dates_are_still_accepted_everywhere` (۴ پارامتر) | 1405/01/31، 1405/06/31، 1405/07/30، 1405/12/29 در هر دو مسیر ذخیره می‌شوند |
| `test_fix_t2_calendar_invalid_dates_rejected_in_every_path` (۶ پارامتر) | 1405/07/31، 1405/12/30، 1405/13/01، 1405/00/01، 1405/01/00، bad-date در create مستقل، ثبت‌نام همراه اقساط و PUT رد + بدون ردیف/بدهی/draft |
| `test_fix_t2_leap_year_boundary_matches_project_calendar` (۶ پارامتر) | مرز کبیسه: 1403/12/30 و 1399/12/30 مجاز، 1404/12/30 و 1405/12/30 ممنوع — داور `parse_project_date` |
| `test_fix_t2_update_installment_rejects_bogus_due_date_without_touching_row` | PUT با تاریخ ناموجود ⇒ رد، ردیف دست‌نخورده؛ PUT معتبر کار می‌کند |
| رگرسیون‌های قبلی (۱۵۰ تا ۲۴) | پرداخت کامل، جزئی، چند جزئی FIFO، overpayment، enrollment حذف‌شده، rollback، هم‌زمانی — همه سبز ماندند |

## ۷) نتیجه‌ی اجرا (after)
| دستور | before | after |
|---|---|---|
| `python -m compileall Kharazmi_Server` | exit 0 | **exit 0** |
| `pytest -q Kharazmi_Server/test_tuition_installments_audit.py -vv` | 41P / 2F | **81 passed / 0 failed / 0 skipped** |
| `pytest -q Kharazmi_Server` | 459P / 2F | **499 passed / 0 failed / 0 skipped** |
| `import main` واقعی روی DB موقت | OK (29 route) | **OK — 29 routes** |

## ۸) ایمنی دیتابیس
```
Kharazmi_Server/gaj_db.db → f0e55fe7c5130ec17e39e73036e2291794c3c335f67d852c37599a6c0f99ec79  (بدون تغییر ✅)
همه‌ی تست‌ها با DATABASE_URL=sqlite:////tmp/tuition_audit.db و /tmp/full_suite_tuition.db (کپی‌ها) اجرا شدند.
.env سندباکس gitignore شده و به /tmp اشاره می‌کند (در کامیت نیست).
```

## ۹) ریسک باقی‌مانده / نکات
1. **سخت‌گیری‌های عمدی نسبت به قبل** (همه در هر دو مسیر یکسان، تست‌شده):
   - ارقام فارسی/عربی در تاریخ و مبلغ دیگر پذیرفته نمی‌شوند (قبلاً `\d` در regex سالِ فارسی را می‌پذیرفت و
     ردیف با ارقام فارسی ذخیره می‌شد که مقایسه‌ی رشته‌ای سررسید را خراب می‌کرد).
   - فاصله/`\n` کنارِ مقدارها رد می‌شود (مسیر مستقل قبلاً هم رد می‌کرد).
   - `amount=True` دیگر به `1` تبدیل نمی‌شود.
   - `POST /students/register_and_enroll` حالا اقساط نامعتبر را **حتی وقتی `course_id=None`** رد می‌کند (قبلاً نادیده گرفته می‌شد).
2. `parse_project_date` برای سال ≥ ۱۷۰۰ آن را میلادی تفسیر می‌کند؛ پس `2500/01/01` اگرچه سال شمسی نیست، معتبر دانسته می‌شود.
   این رفتار **قبلی** پروژه است و در این fix تغییر نکرد (مستند شد، خارج از scope).
3. قالب `pattern` از OpenAPI این دو مدل حذف شد (به validator منتقل شد)؛ اعتبارسنجی و ۴۲۲ سرجایش است ولی ابزارهای
   تولید کلاینت دیگر hint الگو را نمی‌بینند.
4. تغییرات فقط روی `finance.py` از فهرست حساس قبلی اثر گذاشت (طبق دستور تسک) و سایر فایل‌های حساس دست‌نخورده‌اند.
5. سناریوی هم‌زمانی همچنان روی SQLite فایلی تست می‌شود (serialize در سطح فایل)؛ رفتار قفل سطری PostgreSQL بررسی نشد.

## ۱۰) دستورهای بازتولید
```bash
cd /home/user/KharazmiApp
python3 -m compileall Kharazmi_Server
cp Kharazmi_Server/gaj_db.db /tmp/tuition_audit.db && cp Kharazmi_Server/gaj_db.db /tmp/full_suite_tuition.db
DATABASE_URL=sqlite:////tmp/tuition_audit.db PYTHONPATH=/home/user/KharazmiApp/Kharazmi_Server \
  python3 -m pytest -q Kharazmi_Server/test_tuition_installments_audit.py -vv
DATABASE_URL=sqlite:////tmp/full_suite_tuition.db PYTHONPATH=/home/user/KharazmiApp/Kharazmi_Server \
  python3 -m pytest -q Kharazmi_Server
```
