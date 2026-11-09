# O-05 — «چاپ حواله» همیشه ۵۰۰ می‌داد (`time` ایمپورت نشده)

- **تاریخ:** ۲۰۲۶-۰۹-۲۱ · **Branch:** `arena/01a0bf8d-kharazmiapp` · **موج:** ۱
- **Base HEAD:** `d15b8c7c5631841a73515fc0864e44ba53bb7bcf`
- **دسته:** باگ سرور (خطای برنامه‌نویسی) · **شدت:** بالا

## بازتولید (قرمز اول)
تست سناریو ۴ (`tests/test_e2e_finance_installments_invoice.py::test_12`) از «قفلِ باگ» به انتظار
رفتار درست تغییر کرد (۲۰۰ + `print_job_id`) و **قرمز شد** — یعنی باگ واقعاً وجود داشت.

## ریشه
`routers/finance.py:602` → `int(time.time())` در حالی که `time` در بالای فایل import نشده بود
(فقط `io, uuid, os, datetime, html`) ⇒ `NameError` ⇒ **HTTP 500** در هر فراخوانی.

## فیکس (حداقلی)
افزودن یک خط `import time` به بلوک importهای `routers/finance.py`.

## تست
- `test_12` بازنویسی‌شده به `test_12_receipt_print_endpoint_returns_print_job`:
  ۲۰۰ + `status="success"` + `print_job_id` با پیشوند `PRINT_` + وجود `receipt_data` + سالاری مسیر pdf.
- فایل سناریو ۴: **12 passed** · کل سوئیت: **1038 passed** · md5 دیتابیس واقعی بی‌تغییر.
- `ast.parse` روی فایل تغییریافته: سالم.

## Commit / Push
- پیام: `fix: restore receipt printing by importing time (O-05)`
- SHA در گزارش پایانی ثبت می‌شود.
