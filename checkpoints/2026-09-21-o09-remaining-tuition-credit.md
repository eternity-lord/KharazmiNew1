# O-09 — «بدهی منفی» در فاکتور: نبودِ فیلد صریح «باقی‌ماندهٔ شهریه» و «اعتبار»

- **تاریخ:** ۲۰۲۶-۰۹-۲۱ · **Branch:** `arena/01a0bf8d-kharazmiapp` · **موج:** ۲ (مورد ۸)
- **Base HEAD:** `143f95d` (O-07) · **دسته:** مالی + کلاینت · **شدت:** متوسط

## ریشه
`GET /finance/student_class_status` فقط `due_to_teacher`/`due_to_institute` را می‌داد که قرارداد
کیف‌پولی دارند (`due = منهای کیف پول`). پس از پیش‌پرداخت جزئی، کیف مثبت می‌شد و «بدهی» **منفی**
گزارش می‌شد؛ اپ (`InvoiceActivity.kt:314-325`) همان را با علامت چاپ می‌کرد:
«سهم آموزشگاه (قابل پرداخت): - ۵۰۰٬۰۰۰» و مبلغ پیش‌فرض پرداخت هم از همان عدد علامت‌دار می‌آمد.

## اعداد قبل/بعد روی کپی `/tmp/wave2_o09.db` (کپی `gaj_db.db` با md5 یکسان)
| دادهٔ واقعی دیتابیس توسعه (۱ ثبت‌نام فعال) | شهریه | پرداختی لینک‌شده | before: `due_to_institute` | after: `remaining_tuition` | after: `credit_balance` |
|---|---:|---:|---:|---:|---:|
| enrollment #1 | 0 | 0 | **−2,000,000** | **0** | **0** |

(نکتهٔ داده‌ای: در این دیتابیس، رکورد legacy تراکنش کیف آموزشگاه را ۲٬۰۰۰٬۰۰۰ مثبت کرده ولی
شهریهٔ ثبت‌نام صفر است؛ `due_to_*` عدد کیف را نشان می‌دهد و `remaining_tuition` تعهد قراردادی را.
این تفاوت دقیقاً همان ابهامی است که O-09 رفع می‌کند — اپ حالا عدد قراردادی را نشان می‌دهد.)

سناریوی روشن‌تر (تست e2e): پیش‌پرداخت ۵۰۰٬۰۰۰ از شهریهٔ ۱٬۰۰۰٬۰۰۰
- **قبل:** تنها `due_to_institute = -500,000` ⇒ اپ: «… (قابل پرداخت): - ۵۰۰٬۰۰۰ تومان»
- **بعد:** `remaining_tuition = 500,000` و `credit_balance = 0` ⇒ مبلغ پیش‌فرض پرداخت = ۵۰۰٬۰۰۰

## فیکس
| فایل | تغییر |
|---|---|
| `routers/finance.py` (`student_class_status`) | `remaining_tuition = max(0, final - paid_total)` + `credit_balance = max(0, paid_total - final)` — **فیلدهای قبلی دست‌نخورده** |
| `routers/finance.py` (`get_invoice_details`) | همان دو فیلد به‌صورت افزودنی (`balance_due` قبلی حفظ شد) |
| `ApiInterfaces.kt` (`StudentClassStatus`) | `remaining_tuition: Long? = null` و `credit_balance: Long? = null` (nullable با پیش‌فرض ⇒ سازگاری با پاسخ قدیمی) |
| `InvoiceActivity.kt` | اعتبار در خط «شهریه» نمایش داده می‌شود (`invoice_total_and_credit`) و **مبلغ پیش‌فرض پرداخت** از `remaining_tuition` می‌آید (fallback به منطق قبلی اگر سرور نفرستد) |
| `strings.xml` | `invoice_total_and_credit` = «شهریه قراردادی کلاس: %1$s تومان — اعتبار: %2$s تومان» |

⚠️ کد Kotlin کامپایل نشده (در سندباکس JDK/Gradle نیست) — تغییرات static-review شده‌اند.

## تست
- **قرمز اول:** `test_11b_remaining_tuition_and_credit_are_sign_safe` ⇒ `KeyError: 'remaining_tuition'`.
- پس از فیکس: سناریو ۴: **13 passed** · کل سوئیت: **1052 passed** · md5 دیتابیس واقعی بی‌تغییر.
- قرارداد علامت‌دار `due_to_*` عمداً حفظ شد (تست `test_11` مثل قبل آن را می‌سنجد) تا مصرف‌کننده‌های فعلی نشکنند.

## Commit / Push
- پیام: `fix: expose non-negative remaining tuition and credit balance (O-09)`
