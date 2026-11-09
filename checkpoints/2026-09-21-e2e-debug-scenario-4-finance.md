# فاز دیباگ — سناریوی end-to-end #۴: مالی (پرداخت، قسط، کیف پول، فاکتور و رسید)

- **تاریخ:** ۲۰۲۶-۰۹-۲۱ · **Branch:** `arena/01a0bf8d-kharazmiapp`
- **Base HEAD:** `12777b2` (سناریوی ۳)
- **فایل تست:** `Kharazmi_Server/tests/test_e2e_finance_installments_invoice.py` (۱۲ تست)
- **قاعدهٔ فاز:** صفر تغییر در کد برنامه — فقط تست و گزارش.

## ۱) زنجیرهٔ سنجیده‌شده

| مرحله | اندروید | سرور | دیتابیس |
|---|---|---|---|
| پرداخت حضوری | `ApiInterfaces.kt:39-40` → `POST finance/pay` | 200 + `receipt_id` + مانده‌های جدید | `transactions` (type=deposit، شعبهٔ شاگرد) + کیف پول اتمیک |
| ضد پرداخت تکراری | همان کلید `idempotency_key` در retry | بار دوم `duplicate=true` بدون نوشتن | فقط یک تراکنش با آن کلید |
| ساخت قسط | `ApiInterfaces.kt:52-53` → `POST finance/installments` | 200 + `installment_id` | `installments` |
| پرداخت قسط | `ApiInterfaces.kt:54-56` → `POST finance/installments/{id}/pay` | 200 «قسط تسویه و رسید پرداخت ثبت شد» | `installments.is_paid/paid_at` + تراکنش + کیف مؤسسه |
| یادآوری قسط | `POST finance/installments/{id}/remind` | 200 | `sms_logs` + اعلان ولی |
| داشبورد مالی | `ApiInterfaces.kt:58` → `GET finance/student/{id}/dashboard` | 200 | جمع کیف‌ها/پرداخت/بدهی از تراکنش‌ها |
| فاکتور | `InvoiceActivity.kt:57-82` → `GET finance/invoice/{enrollment_id}` | 200 با شهریه/تخفیف/اقساط | `enrollments` + `installments` |
| رسید | `GET finance/receipt/{tx}` · `POST finance/receipt/print` · `/pdf` | جزئیات 200 · **print 500 ❗** · pdf 200 | `transactions` |
| وضعیت مالی کلاس | `ApiInterfaces.kt:43-49` → `GET finance/student_class_status` | 200 (مبالغ علامت‌دار) | تراکنش‌های لینک‌شده به ثبت‌نام |

## ۲) نتیجهٔ تست‌ها

| سنجش | نتیجه |
|---|---|
| فایل سناریوی ۴ | ✅ **12 passed** |
| کل سوئیت | ⏳ در این مرحله اجرا نشد؛ اجرای تجمیعی پایان سناریوها: **1038 passed** (سناریوی ۶) |

> اصلاحیه (۲۰۲۶-۰۹-۲۱): در نسخهٔ اول این گزارش عدد «999 passed» برای سوئیت کامل نوشته شده بود؛
> آن عدد مربوط به *پایان سناریوی ۳* بود و در این مرحله سنجیده نشده بود. عدد نهایی تجمیعی پس از
> سناریوی ۶ ثبت شده است (1038 = 977 پایه + 10 سناریوی ۲ + 12 سناریوی ۳ + 12 سناریوی ۴ + 10 سناریوی ۵ + 17 سناریوی ۶).

## ۳) 🐞 یافته‌ها

### یافتهٔ ۴-الف — «چاپ حواله» همیشه ۵۰۰ می‌دهد (`time` ایمپورت نشده) — **بالا**

`routers/finance.py:602`:

```python
"print_job_id": f"PRINT_{transaction.id}_{int(time.time())}",
```

اما در بالای `finance.py` هیچ `import time` وجود ندارد (فقط `io, uuid, os, datetime, html`).
⇒ هر فراخوانی `POST /finance/receipt/print` با `NameError: name 'time' is not defined` می‌شکند
و **HTTP 500** برمی‌گرداند. مسیر هم‌خانوادهٔ `/finance/receipt/pdf` سالم است.

**اثر واقعی:** دکمهٔ چاپ حواله در `InvoiceActivity` هیچ‌وقت کار نمی‌کند؛ کاربر فقط خطای سرور می‌بیند.
تست سند: `test_12_receipt_print_endpoint_crashes_with_500_bug` (print ⇒ 500، pdf ⇒ 200).

### یافتهٔ ۴-ب — «بدهی» منفی روی فاکتور بعد از پیش‌پرداخت جزئی — **متوسط (منطق مالی/نمایش)**

`GET /finance/student_class_status` سه عدد می‌دهد: `total_amount` (شهریهٔ نهایی)،
`paid_to_institute` (جمع پرداخت‌ها) و `due_to_institute = -wallet_institute`.

برای شاگردی که ۵۰۰٬۰۰۰ از ۱٬۰۰۰٬۰۰۰ را پرداخت کرده:

```
total_amount = 1,000,000        paid_to_institute = 500,000        due_to_institute = -500,000
```

اپ همین را با علامت چاپ می‌کند (`InvoiceActivity.kt:314-322`): «بدهی: **-۵۰۰٬۰۰۰**»، در حالی که
عددِ قابل‌فهم برای اپراتور «۵۰۰٬۰۰۰ بدهی» است (۵۰۰٬۰۰۰ مانده). یعنی **جهت علامت برعکسِ انتظارِ
اپراتور** است و «پیش‌پرداخت» شبیه «طلبکاری» نشان داده می‌شود. مبلغ پیش‌فرض فیلد پرداخت هم
با این قرارداد صفر می‌ماند (چون due>0 شرط است) و اپراتور باید دستی وارد کند.
تست سند: `test_11_student_class_status_matches_enrollment`.

## ۴) رفتارهای تأییدشدهٔ درست (اقتصاد برنامه سالم است)

- پرداخت: شعبهٔ شاگرد روی رسید (Bug 9)، تراکنش `deposit`، کیف پول و `wallet_balance` هم‌گام ✅
- **ضد پرداخت تکراری:** کلید idempotency بار دوم ⇒ `duplicate=true`، بدون تراکنش دوم و بدون شارژ دوباره ✅
- کلید تکراری با مبلغ متفاوت ⇒ **۴۲۲** (جلوگیری از سوءاستفادهٔ کلید) ✅
- پرداخت دو-کیفی (`both`) ⇒ تقسیم درست `amount_institute`/`amount_teacher` ✅
- رد پرداخت‌های نامعتبر: مبلغ صفر/منفی، کیف پول ناشناس، تاریخ آینده ⇒ ۴۰۰ و **بی‌اثر** روی کیف پول ✅
- قسط: ساخت ⇒ `installments`؛ پرداخت ⇒ `is_paid/paid_at` + کیف مؤسسه؛ پرداخت دوباره ⇒ ۴۰۰ ✅
- یادآوری قسط: پیامک در `sms_logs`؛ بدون موبایل ولی ⇒ ۴۰۰ (گارد ورودی) ✅
- داشبورد شاگرد: `total_paid`/`total_debt`/کیف‌ها با واقعیت تراکنش‌ها می‌خواند ✅
- فاکتور: `base_tuition/final_tuition/installments` درست ✅
- رسید: جزئیات کامل برای چاپ مجدد (`student_name`, `amount`, `tracking_code`, …) ✅

## ۵) Commit و Push

- **Commit message:** `test: add end-to-end finance, installment and receipt coverage`
- **سناریوی بعدی:** #۵ اعلان‌ها و Push (NotificationService + FCM)
