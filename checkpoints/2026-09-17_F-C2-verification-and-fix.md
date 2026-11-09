# راستی‌آزمایی فهرست Issues (F-A1…F-E1 + Payment) + تکمیل فیکس F-C2 — 2026-09-17

## درخواست کاربر
یک متن تحلیلی بیرونی (نقشه‌ی «هر Issue روی کدام بخش عملی برنامه اثر می‌گذارد») ارائه شد و پرسید:
**«ببین این مشکلات واقعین یا نه؟ واقعا همچین چیزی هست؟»**
⇒ تسک: راستی‌آزمایی کد-به-کد در HEAD فعلی، با شاهد file:line و وضعیت واقعی هر مورد.

## خلاصه‌ی حکم (سرشماری)
- **۱۱ مورد از ۱۲ مورد، «واقعی بودند و در نشست‌های قبلی همین پروژه بسته شده‌اند»** — با شاهد کد.
- **۱ مورد عمدی است** (F-A2: admin-only ماندن گزارش‌های مالی — تصمیم مستند؛ بازکردن به staff نشت بین‌شعبه‌ای/PII می‌ساخت).
- **۱ مورد واقعاً باز بود** (تکمیلِ ناقص F-C2) که در همین تسک بسته شد (پایین).

## جدول راستی‌آزمایی (شاهد = کد فعلی، نه متن قبلی)

| Issue | ادعا در متن | حکم در کد فعلی | شاهد |
|---|---|---|---|
| **F-A1** | دسترسی analytics | ✅ واقعی بود → بسته (FIX3) | `analytics.py:361` گارد `check_admin_or_secretary_access` (خواهرِ teachers هم‌گارد) |
| **F-A2** | Authorization گزارش مالی | ✅ **عمدی (تصمیم A)** — کد عوض نشد | `finance.py` revenue/settlements با `check_admin_access`؛ سند: `2026-09-16_F-A2-reports-access-consistency.md` |
| **F-B2** | login shadow race | ✅ واقعی بود (500 همزمان) → بسته | `auth.py:142` `with db.begin_nested()` + `:146` `except IntegrityError`؛ `dependencies.py:486` |
| **F-C1** | Split commit در add_enrollment | ✅ واقعی بود → بسته | `classes.py:359-464` فقط **۱** `db.commit()` (خط ۴۵۷) + `flush()` ۴۱۷؛ `enrollment_id/branch_id/target_wallet/remittance` از ساخت |
| **F-C2** | branch_id ناقص | ⚠️ **نیمه‌باز بود** → **در همین تسک تکمیل شد** | دو مسیر باقی‌مانده پیدا و فیکس شد (پایین) |
| **F-C3** | Split commitهای دیگر | ✅ واقعی بود → بسته | `finance.py:1636-1686` فقط ۱ commit (۱۶۸۲)؛ `crm.convert_lead` flush + تک‌کامیت |
| **F-C4** | مقایسه تاریخ attendance | ✅ واقعی بود → بسته | `attendance.py:346-353` نرمال‌سازی `parse_project_date/jalali_date_string` |
| **F-C5** | Test endpoint روی DB واقعی | ✅ واقعی بود → بسته | `admin.py:1094-1101` گارد `ENV=production → 404` + `check_admin_access` |
| **F-C6** | finalize با راستر خالی | ✅ واقعی بود (شارژ کل کلاس!) → بسته | `attendance.py:112-114` حذف fallback «همه حاضر» + claim اتمیک `:58` |
| **F-C9** | ورکر روی کلاس معلق (اضافه) | ✅ واقعی بود → بسته | `main.py:554-580` بستن مستقیم LIVE→ENDED بدون submit |
| **F-E1** | reportlab نصب نبود | ✅ واقعی بود → بسته | `requirements.txt:13` |
| **Payment callback** | idempotency/race | ✅ واقعی بود → بسته (F-B1)؛ درگاه واقعی هنوز خاموش | `finance.py:738` فلگ، `:942-947` تسخیر اتمیک PENDING→VERIFYING؛ `payment_gateways.py:81` گارد پروداکشن |
| **H16 (اضافه)** | IDOR پرینت/PDF | ✅ بسته | `finance.py:562/605/2196` +`reports.py:555/739` + `exams.py:378` + `analytics.py:527` — همه گارد مالکیت/نقش دارند |

> نکته‌ی مهم: جدولِ کاربر «F-A2» را در ردیف دسترسی «🟠» زده بود؛ در کد فعلی این مورد **باگ نیست** بلکه
> انتخاب امن‌تر است: اگر مثل `financial_summary` به secretary/teacher باز شود، revenue همه‌ی شعبه‌ها
> و `card_number` معلمان نشت می‌کند (گزینه‌های B/C در چک‌پوینت F-A2 تحلیل و رد شده‌اند).

## F-C2 — تناقض واقعی که پیدا شد (و فیکس شد)
### شاهد مسئله
- `analytics/dashboard` سه شمارش را با شعبه فیلتر می‌کند: `analytics.py:177` (active) / `:185` (new regs) / `:193` (retention)
  با `Enrollment.branch_id == resolved_branch` — و `resolved_branch` برای کاربرِ شعبه‌دار مقدار می‌گیرد (`finance.get_user_branch_filter`).
- در SQL، `branch_id = 1` هیچ‌وقت ردیفِ `NULL` را برنمی‌گرداند ⇒ **ثبت‌نامِ بدون شعبه از آمار شعبه حذف می‌شد.**
- چهار مسیر ساخت `Enrollment` در کد وجود دارد؛ فیکس S3 قبلی فقط `classes.add_enrollment` را پوشانده بود:
  | مسیر | قبل |
  |---|---|
  | `classes.py` (add_enrollment) | ✅ داشت (FIX S3) |
  | `crm.py` ثبت‌نام آنلاین (خط ۱۹۹) | ✅ داشت |
  | `crm.py` `convert_lead` (خط ۲۶۸) | ❌ نداشت |
  | `students.py` `register_and_enroll` (خط ۱۴۹) | ❌ نداشت |
  ⇒ یعنی ادعای چک‌پوینت S3 که «Enrollment.branch_id هیچ‌جا خوانده نمی‌شود» **دیگر درست نبود**؛ analytics آن را می‌خواند.

### فیکس (هم‌منطق با Transaction و H7)
```python
# students.py:155  و  crm.py:274  (الگوی یکسان: شاگرد، وگرنه کلاس)
branch_id=<student>.branch_id if <student>.branch_id is not None else course.branch_id,
```
هر دو مسیر یک خط + کامنت توضیحی؛ هیچ فایل ممنوعه‌ای لمس نشد.

### تست — `test_enrollment_branch.py` (جدید، ۱۸۷ خط، ۶ تست، همه pass)
- ثبت‌نام از مسیر HTTP ⇒ `Enrollment.branch_id == 1` (شعبه‌ی کلاس/شاگرد).
- fallback: شاگرد بی‌شعبه + کلاس شعبه‌دار ⇒ شعبه‌ی کلاس.
- رگرسیون اصلی: منشی شعبه‌ی ۱ ⇒ `active_students ≥ 1` در `/analytics/dashboard`.
- **کنترل منفی:** همان ردیف را NULL کن ⇒ `active_students == 0` (اثبات اینکه قبل از فیکس از آمار حذف می‌شد).
- ادمین بدون شعبه ⇒ هیچ فیلتری (نه رگرسیون).
- تبدیل سرنخ (`/crm/leads/{id}/convert`) ⇒ Enrollment شعبه‌دار.

## وریفای
```
1) ast.parse(students.py, crm.py)                                     → OK
2) test_enrollment_branch.py                                          → 6 passed
3) سوئیت کامل از ریشه‌ی ریپو (روشی کانونیکال)                          → 339 passed / 0 failed (333+6)
4) لایو روی کپی /tmp/branch_live.db + uvicorn :8044 + توکن منشی شعبه:
   POST /students/register_and_enroll → HTTP 200، enrollment_id=2
   DB: enrollment.branch_id = 1   (student.branch_id = None → fallback کلاس)
5) ۶ فایل ممنوعه: finance/timeline/audit/dunning/dashboard/exports → دست‌نخورده
6) DB پروداکشن: f0e55fe7c5130ec17e39e73036e2291794c3c335f67d852c37599a6c0f99ec79 (بدون تغییر)
```

## نکات محیطی این تسک (برای نشست بعد)
- سندباکس بین نوبت‌ها ریست شد: `~/.local` (پکیج‌ها) و `.env` رفتند →
  `python3 -m pip install --user --break-system-packages -r requirements.txt` + ساخت دوباره‌ی `.env`.
- **`.git` محلی به کامیت قبل برگشته بود** (HEAD=`2b5ea9f` در حالی که ریموت `927dd14` را داشت)؛
  درخت کاری اما دقیقاً برابر ریموت بود (sha256 نمونه‌ای تأیید شد) ⇒ با بکاپ فایل‌های جدید،
  `git reset --hard origin/arena/01a0aac2-kharazmiapp` + بازگرداندن فایل‌ها انجام شد.
  **درس: اول هر تسک `git log -1` را چک کن و اگر عقب بود، از ریموت سینک کن.**
- نکته‌ی گارد F-C5 فقط برای `POST /test/transaction_logic` است؛ `GET /test/debt_calculation` خواندنی است.

## فایل‌های این تسک
```
M  Kharazmi_Server/routers/students.py   (+۱ خط branch_id + کامنت)
M  Kharazmi_Server/routers/crm.py        (+۱ خط branch_id + کامنت)
?? Kharazmi_Server/test_enrollment_branch.py  (جدید — ۶ تست)
?? checkpoints/2026-09-17_F-C2-verification-and-fix.md  (همین فایل)
```
