# باگ بیلد اندروید — کلید رشتهٔ تکراری `attendance_server_error` (`mergeDebugResources` FAILED)

- **تاریخ:** ۲۰۲۶-۰۹-۲۱ · **Branch:** `arena/01a0bf8d-kharazmiapp` · **نوع:** بلاکر build (aapt2/resource merger)
- **Base HEAD:** `d2095f9` · **دسته:** اندروید (منابع) + تست ایستا

## ریشه (خطای واقعی کاربر روی `gradle assembleDebug`)
```
ERROR: KharazmiAdmin/app/src/main/res/values/strings.xml: Resource and asset merger:
Found item String/attendance_server_error more than one time
Task :app:mergeDebugResources FAILED
```
در `res/values/strings.xml` نام `attendance_server_error` **دو بار** تعریف شده بود با شکل‌های متفاوت:
| تعریف | متن | placeholderها | مصرف‌کننده |
|---|---|---|---|
| ۱ (خط ۲۸۱) | «خطای سرور (%1$d): %2$s» | ۲ | `AttendanceActivity.kt:522` — `getString(…, e.code(), detail ?: "")` |
| ۲ (خط ۲۹۳) | «❌ خطای سرور (%1$d)؛ لطفاً دوباره تلاش کنید.» | ۱ | `AttendanceActivity.kt:676` — `getString(…, e.code())` |

هر دو مسیر لازم‌اند: یکی جزئیات سرور را نشان می‌دهد و دیگری پیام کوتاه «تلاش مجدد» در بازهٔ ۵۰۰..۵۹۹
هنگام ثبت جلسه. حذف هر کدام ⇒ `MissingFormatArgumentException` در زمان اجرا.

## فیکس (حداقلی و بدون لمس مسیر دیگر)
| فایل | تغییر |
|---|---|
| `res/values/strings.xml` | تعریف دوم به `attendance_server_error_retry` تغییر نام یافت (+ کامنت توضیحی با متن خطای aapt2) |
| `java/.../AttendanceActivity.kt` | **فقط** فراخوانی تک‌آرگومانی (بازهٔ ۵۰۰..۵۹۹) به کلید جدید؛ فراخوانی دوعملوندی خط ۵۲۲ دست‌نخورده |

## بررسی‌های ایستا روی کل `KharazmiAdmin/app/src/main` (چون Gradle/JDK در این محیط نیست)
| # | بررسی | نتیجه |
|---|---|---|
| الف | نام تکراری در `values*/strings.xml` (values, values-night, values-v31) | **قبل: ۱ مورد** (`attendance_server_error` در `values/strings.xml`) · **بعد: هیچ** |
| الف-ب | نام تکراری برای هر نوع منبع در **همهٔ** فایل‌های `res/**/*.xml` (string/color/dimen/style/id/item) | هیچ · هیچ XML خرابی هم نبود |
| ب | `R.string.X` استفاده‌شده در Kotlin ولی تعریف‌نشده | **۰ مورد** (۱۵۱۴ کلید تعریف‌شده، ۱۱۰۲ استفاده‌شده؛ ۴۱۲ کلید بی‌استفاده — طبیعی) |
| پ | تطبیق تعداد آرگومان `getString(...)` با placeholderها | **قبل: ۱ مغایرت واقعی** (همان کلید تکراری) · **بعد: ۰ از ۱۴۱۲ فراخوانی** |
| ت-۱ | هر `R.<نوع>.<نام>` در Kotlin ↔ منبع موجود | **۰ ارجاع نامعتبر** (۹۹ layout، ۹۰۹ id، ۱۴۱۹ string، ۲۲ color، …) |
| ت-۲ | نمادهای افزوده‌شدهٔ این شاخه (warnings/logout/remaining_tuition/credit_balance/undated_*) | تعریف و استفاده هر دو موجود ✓ |
| ت-۳ | importهای ناقص / نمادهای تعریف‌نشده در فایل‌های تغییریافته | هیچ (۱۵ فایل تغییر‌یافتهٔ Kotlin بررسی شد؛ `AlertDialog`/`Toast`/`withTimeoutOrNull`/`lifecycleScope` همه import شده‌اند) |
| ت-۴ | ارجاع‌های `@نوع/نام` داخل XMLها | ۳۱ مورد «نامعتبر» که **همه** به کتابخانه‌ها اشاره می‌کنند (Material/AppCompat: `Widget.MaterialComponents.*`، `appbar_scrolling_view_behavior`، `ThemeOverlay.AppCompat.Dark`) ⇒ مثبت کاذب، نه باگ |

**نکته‌های مثبت کاذب که در گزارش باقی می‌مانند (بدون تغییر کد):**
1. `String.format(Locale, getString(R.string.common_toman_format), value)` در `EditStudentActivity.kt:173-174`
   ⇒ `getString` عمداً بدون آرگومان است و `%,d` را `String.format` پر می‌کند (الگوی درست؛ در تست به‌عنوان
   حالت مجاز مدل شده است).
2. `isLast ||` عمداً حذف شد؟ خیر — موردی نبود؛ فقط همان دو مورد بالا.

## تست
- **کد جدید:** `Kharazmi_Server/tests/test_android_resources_static.py` (۶ تست، بدون نیاز به Gradle):
  ۱) تکرار رشته در `values*/strings.xml` · ۱ب) تکرار هر نوع منبع در همهٔ `res/**/*.xml` ·
  ۲) کلیدهای `R.string` تعریف‌نشده · ۳) تطبیق آرگومان/placeholder (با مدل‌سازی حالت `String.format`) ·
  ۴) لینک `R.*` ↔ منابع · ۵) گارد رگرسیون همان باگ (دو کلید متمایز + تفکیک فراخوانی‌ها)
- **قرمز اول (قبل از فیکس):** `2 failed, 3 passed` ⇒
  `test_1` («نام رشتهٔ تکراری… `['attendance_server_error']`») و `test_5` («`attendance_server_error_retry` تعریف نشده»).
- **پس از فیکس:** فایل تست ⇒ **6 passed** · **کل سوئیت ⇒ 1069 passed** (مبنا ۱۰۶۳).
- md5 `Kharazmi_Server/gaj_db.db` = `f048f8d118b33c4eaa944490594121d7` — **بی‌تغییر**.

## کامپایل‌نشده
⚠️ `gradle assembleDebug` در این سندباکس اجرا **نشد** (JDK/Gradle موجود نیست). اعتبارسنجی فقط ایستا بود:
`xml.etree` روی همهٔ منابع + تحلیل متنی Kotlin. تأیید نهایی build روی ماشین خودتان لازم است.

## Commit / Push
- پیام: `fix: give the attendance retry error its own string key (build fix)`
