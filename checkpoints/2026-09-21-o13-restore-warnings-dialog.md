# O-13 — هشدارهای «بازیابی کلاس» به مدیر نشان داده نمی‌شد

- **تاریخ:** ۲۰۲۶-۰۹-۲۱ · **Branch:** `arena/01a0bf8d-kharazmiapp` · **موج:** ۳ (مورد ۱۴)
- **Base HEAD:** `081f29d` (O-17) · **دسته:** اندروید (پنل ادمین) · **شدت:** کم

## ریشه
سرور در بازیابی «فقط متادیتا»ی کلاس آرشیوشده، فیلد `warnings` را برمی‌گرداند
(`routers/admin.py:1924-1964`) و همان را تست `test_12b` قفل کرده است؛ اما اپ ادمین
(`MainActivity.restoreArchivedClass`) فقط `message` را Toast می‌کرد و `warnings` را **کامل نادیده
می‌گرفت** — حتی در مدل پاسخ `ClassRestoreResponse` هم فیلدی برایش وجود نداشت. یعنی مدیر کلاس را
بازیابی می‌کرد و نمی‌فهمید «معلم این کلاس آرشیو شده است؛ کلاس بدون معلم فعال برمی‌گردد» یا
«این کلاس معلم ثبت‌شده ندارد».

## فیکس
| فایل | تغییر |
|---|---|
| `KharazmiAdmin/.../AppModels.kt` | `ClassRestoreResponse`: فیلد `@SerializedName("warnings") val warnings: List<String>? = null` (nullable + default ⇒ سازگار با سرور قدیمی) |
| `KharazmiAdmin/.../MainActivity.kt` | در مسیر موفق بازیابی: اگر `warnings` غیرخالی بود، یک `AlertDialog` ساده با عنوان جدید و فهرست گلوله‌ای هشدارها نشان داده می‌شود؛ در غیر این صورت همان Toast موفقیت قبلی (رفتار بدون هشدار دست‌نخورده) |
| `KharazmiAdmin/.../values/strings.xml` | `main_trash_restore_warnings_title` = «کلاس بازیابی شد — نکته‌های مهم» (دکمهٔ «باشه» از `common_ok` موجود) |
| `Kharazmi_Server/tests/test_class_restore_metadata.py` | تست `test_13_android_client_surfaces_restore_warnings` — گارد static روی سورس کاتلین |

⚠️ کد Kotlin/XML در سندباکس **کامپایل نشد** (JDK/Gradle موجود نیست)؛ `strings.xml` با
`xml.dom.minidom.parse` معتبرسازی شد و گارد متنی، قرارداد را قفل می‌کند.

## تست
- **قرمز اول (کد بدون فیکس):** `test_13` ⇒
  `AssertionError: Regex didn't match: '@SerializedName\("warnings"\)\s*val\s+warnings\s*:\s*List<String>\?\s*=\s*null'`
  (و با برگشت‌ندادن مدل هم assertion مربوط به `AlertDialog` در `MainActivity` قرمز بود).
- پس از فیکس: `tests/test_class_restore_metadata.py` ⇒ **15 passed** · کل سوئیت ⇒ **1063 passed**
  · md5 `gaj_db.db` بی‌تغییر.
- گارد هر دو سر زنجیره را می‌سنجد: مدل پاسخ `warnings` را از JSON می‌گیرد **و** مسیر بازیابی آن را در
  `AlertDialog` نشان می‌دهد (نه فقط Toast).

## Commit / Push
- پیام: `feat: show class-restore warnings to the admin (O-13)`
