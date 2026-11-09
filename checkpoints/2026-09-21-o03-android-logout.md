# O-03 — دکمهٔ خروج اپ فقط پنجره را می‌بست؛ نشست سرور زنده می‌ماند

- **تاریخ:** ۲۰۲۶-۰۹-۲۱ · **Branch:** `arena/01a0bf8d-kharazmiapp` · **موج:** ۱
- **Base HEAD:** `61bcb70` (O-04) · **دسته:** کلاینت اندروید + قرارداد سرور · **شدت:** متوسط
- **⚠️ کد Kotlin کامپایل نشده** (در سندباکس java/kotlinc/gradle نصب نیست) — بازبینی static + تست گارد.

## بازتولید (قرمز اول)
گارد `test_9` سناریو ۱ عمداً «نبودِ» فراخوانی‌ها را قفل کرده بود ⇒ با افزودن کد، گارد شکست:

```
AssertionError: Lists differ: ['LoginActivity.kt ⇒ device_token', 'LoginActivity.kt ⇒ auth/logout'] != []
```

(این تست همان «سند زندهٔ» فاز دیباگ بود: سرور آماده، اپ وصل نبود.)

## ریشه و فیکس
- **سرور:** قرارداد کامل بود (`POST /auth/logout` بدون پارامتر هم نشست را باطل می‌کند —
  `test_7b`). نیازی به تغییر سرور نبود.
- **اپ:** `SettingsActivity.kt:79-88` فقط `finishAffinity()` داشت.

| فایل | تغییر |
|---|---|
| `LoginActivity.kt` (`AuthApi`) | `@POST("auth/logout") suspend fun logout()` (هدر `Authorization` را `RetrofitClient` خودکار می‌زند) |
| `SettingsActivity.kt` | در تأیید خروج: `withTimeoutOrNull(3000) { …logout() }` داخل `try/catch(ignored)` ← سپس `SecureLoginStore.clearToken(...)` ← `finishAffinity()` |

نکات عمدی:
- **خروج به شبکه وابسته نیست:** شکست/کندی logout (سقف ۳ ثانیه) مانع پاک‌شدن توکن و بستن اپ نمی‌شود.
- `clearToken` انتخاب شد نه `clear`؛ چون `clear()` فایل `SecureLoginCreds` را کامل حذف می‌کند
  (شامل رمزِ ذخیره‌شدهٔ «مرا به خاطر بسپار») در حالی که خروج فقط باید توکن نشست را پاک کند.
  اگر کاربر «مرا به خاطر بسپار» را زده باشد، رمز برای ورود بعدی می‌ماند — تصمیم ثبت‌شده در «تصمیم‌های من».
- بدون `device_token` صدا زده می‌شود (اپ Push ندارد) ⇒ توکن Push سرور عمداً دست‌نخورده می‌ماند.

## تست
- `test_9` بازنویسی شد به `test_9_android_client_logs_out_on_server_but_never_registers_device_token`:
  (۱) خروج سیم‌کشی شده، (۲) گارد Push همچنان برجاست (`device_token`/`firebase`/`gms.` ممنوع)،
  (۳) اندپوینت‌ها روی سرور موجودند.
- سناریو ۱: **11 passed** · کل سوئیت: **1039 passed** · md5 دیتابیس واقعی بی‌تغییر.
- «همان توکن پس از logout → 401» از قبل در `test_7` پوشش داده شده بود.

## Commit / Push
- پیام: `fix: send server logout and clear token when signing out (O-03)`
