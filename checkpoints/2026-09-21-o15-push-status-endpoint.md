# O-15 — مدیر هیچ راهی نداشت بفهمد «چرا Push نمی‌رسد»

- **تاریخ:** ۲۰۲۶-۰۹-۲۱ · **Branch:** `arena/01a0bf8d-kharazmiapp` · **موج:** ۳ (مورد ۱۲)
- **Base HEAD:** `fa8db9b` (O-10) · **دسته:** اعلان‌ها/Push · **شدت:** کم (قابلیت تشخیص، نه خرابی داده)

## ریشه
لایهٔ Push دو پیش‌شرط دارد: (۱) اعتبارنامهٔ FCM روی سرور تنظیم شده باشد — گارد محیطی
`push_service.fcm_configured()` که فقط `FCM_SERVER_KEY` را می‌خواند؛ (۲) کاربری که باید اعلان بگیرد
دستگاهش با `POST /auth/device_token` ثبت شده باشد. هیچ‌کدام از این دو از بیرون قابل مشاهده نبود:
اپ اندروید نه Firebase دارد و نه توکن ثبت می‌کند (یافتهٔ سناریو ۱) و سرور هم هیچ endpoint وضعیتی نداشت.
نتیجه: اعلان درون‌برنامه‌ای کار می‌کرد و Push بی‌صدا شکست می‌خورد.

## فیکس
| فایل | تغییر |
|---|---|
| `routers/dashboard.py` | مدل پاسخ `PushStatus` + مسیر `GET /dashboard/push_status` با `Depends(check_admin_access)` (ادمین‌فقط)، فقط‌خواندنی و **بدون کش** (مقدار باید «همین حالا» را نشان دهد) |
| `Kharazmi_Server/tests/test_e2e_notifications_push.py` | تست `test_11` (قرمز اول ⇒ `404`) |

قرارداد پاسخ:
```json
{"fcm_configured": false, "device_token_count": 2}
```
- `fcm_configured`: از همان گارد محیطی `push_service.fcm_configured()` — **کلید خوانده/نوشته نمی‌شود و در پاسخ نمی‌آید**.
- `device_token_count`: `COUNT(*)` واقعی روی جدول `device_tokens`.
- ادمین‌فقط: با منشی/معلم/شاگرد ⇒ ۴۰۱/۴۰۳ · بدون توکن ⇒ ۴۰۱.

## تست
- **قرمز اول:** `test_11_push_status_...` ⇒ `404 Not Found` (مسیر وجود نداشت).
- پس از فیکس: سناریو ۵ (`test_e2e_notifications_push.py`) ⇒ **11 passed** · کل سوئیت ⇒ **1062 passed**.
- تست دو حالت را می‌سنجد: بدون توکن FCM (`fcm_configured=False` + شمارش واقعی) و با توکن
  (مقدار `True` **بدون** لو رفتن رشتهٔ کلید؛ assert عدم حضور راز در پاسخ).
- ⚠️ هیچ کلید FCM در محیط تنظیم/ذخیره شد (دستور صریح کاربر) و هیچ نوشتنی روی دیتابیس واقعی نبود.

## Commit / Push
- پیام: `feat: expose admin-only push status reporting (O-15)`
