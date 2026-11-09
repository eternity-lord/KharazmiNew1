# فاز دیباگ — سناریوی end-to-end #۵: اعلان‌ها و Push

- **تاریخ:** ۲۰۲۶-۰۹-۲۱ · **Branch:** `arena/01a0bf8d-kharazmiapp`
- **Base HEAD:** `69d366c` (سناریوی ۴)
- **فایل تست:** `Kharazmi_Server/tests/test_e2e_notifications_push.py` (۱۰ تست)
- **قاعدهٔ فاز:** صفر تغییر در کد برنامه.

## ۱) زنجیرهٔ سنجیده‌شده

| مرحله | اندروید | سرور | دیتابیس |
|---|---|---|---|
| لیست اعلان | `ApiInterfaces.kt:46-47` → `GET notifications` | 200 (فقط خودِ کاربر + نقش کانونیکال) | `notifications` |
| شمارش نخوانده | `ApiInterfaces.kt` → `GET notifications/unread_count` | `{unread, total}` | — |
| خوانده‌شده | `POST notifications/{id}/read` | 200 برای خودی، **۴۰۴** برای اعلان دیگران | `notifications.is_read` |
| همه خوانده | `POST notifications/read_all` | 200 (فقط ردیف‌های خودِ کاربر) | — |
| رویداد غیبت | ثبت جلسه (سناریو ۲) | اعلان `attendance` برای ولی + پیامک | `notifications` + `sms_logs` |
| رویداد تکلیف/آزمون/نمره | سناریو ۳ | اعلان `homework`/`exam`/`grade` | `notifications` |
| یادآوری قسط | `finance/installments/{id}/remind` | اعلان + پیامک | `notifications` + `sms_logs` |
| لایهٔ Push | — (کلاینت FCM در اپ نیست) | `NotificationService → deliver_push → FCM` | `device_tokens` (پاک‌سازی توکن نامعتبر) |

## ۲) نتیجهٔ تست‌ها

| سنجش | نتیجه |
|---|---|
| فایل سناریوی ۵ | ✅ **10 passed** |
| یافتهٔ جدید (باگ) | ❌ **صفر** — این سناریو کاملاً سالم است |

## ۳) رفتارهای تأییدشدهٔ درست

- **جداسازی صندوق اعلان:** هر کاربر فقط اعلان‌های `recipient_user_id` خودش با نقش خودش را می‌بیند؛
  بدون توکن ⇒ ۴۰۱؛ اعلان کاربر دیگر ⇒ ۴۰۴ (بدون نشت وجود رکورد) ✅
- `unread_count` با لیست می‌خواند؛ رکورد legacy با `is_read=NULL` هم «نخوانده» حساب می‌شود ✅
- `read`/`read_all` فقط ردیف‌های خودی را تغییر می‌دهند؛ خواندن دوباره بی‌خطر ✅
- **ضد تکرار:** متن/عنوان یکسان در ۱۰ ثانیه ⇒ یک اعلان (dedup) ✅
- اعلان‌های `attendance/installment/payment` پیامک هم در `sms_logs` می‌سازند ✅
- **لایهٔ Push:**
  - بدون `FCM_SERVER_KEY` ⇒ `skipped_reason=fcm_not_configured`، صفر درخواست شبکه، توکن‌ها دست‌نخورده ✅
  - با کلید تنظیم‌شده ⇒ اعلان به لایهٔ Push می‌رسد؛ توکنِ `NotRegistered` از `device_tokens` پاک می‌شود ✅
  - شکست شبکه (`RuntimeError`) ⇒ اعلان درون‌برنامه‌ای باز هم ذخیره می‌شود؛ خطا به کاربر منتقل نمی‌شود ✅

## ۴) نکتهٔ مهم این سناریو (تکرار یافتهٔ سناریوی ۱)

کل زنجیرهٔ Push سمت **سرور** آماده و درست است، اما سمت **اندروید** هیچ کلاینت FCM/GMS وجود ندارد
(grep در کل `.kt` + `build.gradle.kts`: صفر ارجاع `firebase`/`device_token`/`gms`).
⇒ `device_tokens` در عمل همیشه خالی می‌ماند (شاهد مستقل: سنجش B5 روی دیتابیس واقعی = ۰ ردیف)
و اعلان‌ها فقط درون‌برنامه‌ای می‌مانند. این یافته در سناریوی ۱ ثبت شده و اینجا فقط تأیید شد.

## ۵) Commit و Push

- **Commit message:** `test: add end-to-end notification and push delivery coverage`
- **سناریوی بعدی:** #۶ گزارش‌ها و خروجی‌ها (Excel/PDF، صورت مالی، بدهکاران، لاگ ممیزی)
