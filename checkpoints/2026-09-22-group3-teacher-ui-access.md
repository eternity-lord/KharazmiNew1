# گروه ۳ — دسترسی نادرست معلم در اپ ادمین (آیتم‌های ۱۰ تا ۱۵): فقط UI، endpointها دست‌نخورده

- **تاریخ:** ۲۰۲۶-۰۹-۲۲ · **Branch:** `arena/01a0c867-kharazmiapp` · **زبان:** فارسی
- **Base HEAD:** `9a36c13` (پایان گروه ۲) · **Tip بعد از این گروه:** `f0ca350` (+ همین سند)
- **کامیت‌ها:** `7409ca7` (آیتم ۱۰) · `23743cb` (آیتم ۱۱) · `3ed515f` (آیتم ۱۲) · `4837847` (آیتم ۱۳) · `d4d7c7a` (آیتم ۱۵) · `f0ca350` (آیتم ۱۴)
- **وضعیت:** هر مورد با تست قرمز → فیکس حداقلی → سبز · **سوئیت کامل ۱۱۴۸ passed** · ۲۲ تست ایستای جدید گروه ۳
- **md5 مبنای `gaj_db.db`:** `f048f8d118b33c4eaa944490594121d7` — قبل از کار، بعد از هر کامیت و بعد از هر سوئیت کامل **یکسان** (دست‌نخورده ✅)
- **قانون گروه (دستور کارفرما):** فقط UI · هیچ endpoint/سروری تغییر نکرد · با **همان چک نقش موجود** در Activityها (`UserCreds` → `USER_SUB_ROLE`) · الگوی جدید نساختیم · اندروید **کامپایل نشد** (در این سندباکس Gradle/JDK/SDK نیست).

---

## ۰) چرا تست‌ها «ایستا» هستند (و چه چیزی را قفل می‌کنند)

طبق قانون پروژه در این سندباکس اندروید هرگز کامپایل نمی‌شود ⇒ قرارداد UI با همان الگوی
موجودِ خودِ پروژه قفل شد:

- الگو: `test_class_restore_metadata.py::test_13` و `test_android_resources_static.py` (اسکن متن `res/` و سورس کاتلین).
- فایل جدید: `Kharazmi_Server/tests/test_group3_teacher_ui_access.py` — ۲۲ تست.
- هر تست **دو طرف** قرارداد را قفل می‌کند: (الف) چه چیزی باید برای معلم پنهان/حذف شود،
  (ب) چه چیزی باید در مسیر ادمین/منشی **سر جایش بماند** (تا رگرسیون «دکمه در پنل ادمین هم غیب شد» دیده شود).
- ابزارهای کمکی تست: `kt()` / `layout()` / `kt_strings()` / `strip_comments()` / `function_body()`
  (بدنهٔ یک تابع کاتلین تا تابع هم‌سطح بعدی) ⇒ گاردها به «همان تابعِ مسیرِ معلم» نگاه می‌کنند، نه کل فایل.
- به‌علاوه برای هر فایل کاتلینِ دست‌خورده: balansing `{}`/`()` با مقایسه نسبت به HEAD، و برای layout تغییر‌یافته `xml.etree.ElementTree.parse`.

**اصل فیکس‌ها در همهٔ آیتم‌ها:** وقتی ویجتی برای معلم پنهان می‌شود، **listener هم برایش ثبت نمی‌شود**
(ویجت پنهانِ کلیک‌پذیر = راه فرار). استثنا: مواردی که رفتار قبلی ادمین/منشی را عوض می‌کرد (مثلاً منشی و «حذف کامل دانش‌آموز» که از قبل همین‌طور بود).

**چک نقش پایه که در همهٔ آیتم‌ها استفاده شد (الگوی غالب پروژه، مثل `ClassDetailActivity:334`):**

```kotlin
val credsPrefs = getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
val subRole = credsPrefs.getString("USER_SUB_ROLE", "admin") ?: "admin"
```

✅ نکتهٔ حیاتی که قبل از آیتم ۱۴ راستی‌آزمایی شد: سرور در لاگین معلم **`"sub_role": "teacher"`**
برمی‌گرداند (`Kharazmi_Server/routers/auth.py:190-196`، با کامنت FIX O-01). اگر این فیلد نبود،
اپ برای معلم `USER_SUB_ROLE="admin"` ذخیره می‌کرد و هیچ‌کدام از گاردهای این گروه کار نمی‌کرد.

---

## ۱) آیتم ۱۰ — «ثبت مجدد برای دانش‌آموز دیگر» در پاپ‌آپ تسویهٔ معلم

**مسیر (طبق توضیح کارفرما):** پروفایل عملکرد معلم → تب تسویه‌حساب → «تسویه و ثبت پرداخت» → پاپ‌آپ موفقیت.

### ریشه (قبل از فیکس)
`TeacherProfileActivity.performSettlement()` همان لی‌اوت مشترک `dialog_remittance_success` را
inflate می‌کند و فقط `btnPrintRemittance` و `btnSaveAsPdf` را `GONE` می‌کرد ⇒ دکمهٔ
«ثبت مجدد برای دانش‌آموز دیگر» در پاپ‌آپ تسویهٔ **معلم** نمایان می‌ماند (و چون آنجا listener
ندارد، کلیکش هیچ کاری نمی‌کرد = دکمهٔ مرده).
الگوی درستِ موجود در همین پروژه: `AttendanceActivity:813` همین دکمه را `GONE` می‌کند.

### فیکس (۱ خط، همان الگو)
`TeacherProfileActivity.kt` (داخل `performSettlement`، کنار دو `GONE` قبلی):

```kotlin
dialogView.findViewById<com.google.android.material.button.MaterialButton>(R.id.btnRegisterAgain).visibility = View.GONE
```

**دست‌نخورده:** مسیر ثبت حوالهٔ دانش‌آموز — `InvoiceActivity:774` همان دکمه را فعال نگه می‌دارد
(«ثبت مجدد برای دانش‌آموز دیگر» آنجا معنادار است). تست `10c` دقیقاً همین را قفل می‌کند.

### تست‌ها (۴ مورد، همه ایستا)
`10a` متنِ خودِ دکمه در `dialog_remittance_success.xml` همان است که کارفرما دیده · `10b` در
`performSettlement` دکمه `GONE` می‌شود · `10c` در `InvoiceActivity` فعال می‌ماند (رگرسیون ادمین) ·
`10d` الگوی `AttendanceActivity` هم سر جایش است.

---

## ۲) آیتم ۱۱ — حذف «ثبت حواله» از داشبورد معلم

### ریشه
`TeacherDashboardActivity` کارت `cardFastInvoice` را **بدون هیچ چک نقشی** به `InvoiceActivity`
وصل می‌کرد، در حالی که این صفحه فقط پنل معلم است:
`LoginActivity:283` تنها وقتی `response.role == "teacher"` باشد اینجا می‌آید و
`EditStudentActivity.returnToDashboard` هم فقط برای `userRole == "teacher"`.
`fetchPermissionsAndSyncUI()` هم فقط permissionها را می‌گیرد و هیچ UI را گیت نمی‌کرد.

### فیکس
کارت برای غیر ادمین `GONE` و listener **فقط در شاخهٔ ادمین** ثبت می‌شود:

```kotlin
if (subRole != "admin") {
    cardFastInvoice.visibility = android.view.View.GONE
} else {
    cardFastInvoice.setOnClickListener { startActivity(Intent(this, InvoiceActivity::class.java)) }
}
```

`isAdminUser = subRole == "admin"` هم به‌عنوان فیلد Activity اضافه شد (آیتم ۱۲ از همان استفاده می‌کند).
بقیهٔ میان‌برهای پنل معلم (ثبت دانش‌آموز، ثبت کلاس، حضور و غیاب، کلاس‌های ناقص، گزارشات) دست‌نخورده.

### تست‌ها
`11a` چک نقش + `GONE` · `11b` listener پشت گارد نقش (نه قبلش) · `11c` پنج میان‌بر دیگر پنل معلم سالم.

---

## ۳) آیتم ۱۲ — مخفی‌شدن «تعلیق» و «ثبت حواله» روی بنر کلاس‌ها در پنل معلم

### ریشه
`item_class_row.xml` دو دکمهٔ `btnSuspend` («تعلیق») و `btnRegisterInvoice` («ثبت حواله») را
**بدون `android:visibility`** دارد ⇒ پیش‌فرض نمایان. این layout **مشترک** است:

| مصرف‌کننده | رفتار قبلی |
|---|---|
| `ClassManagementActivity` (ادمین) | مدیریت می‌کرد: `btnSuspend.visibility = if (isAdminUser) VISIBLE else GONE` + listener ثبت حواله |
| `TeacherClassAdapter` داخل `TeacherDashboardActivity` (پنل معلم) | **هرگز به آن‌ها دست نمی‌زد** ⇒ دو دکمهٔ نمایانِ کاملاً بی‌عملکرد روی هر بنر کلاس معلم |

### فیکس (سمت آداپتر معلم؛ layout مشترک دست نخورد)
آداپتر پرچم نقش را می‌گیرد و با **همان اصطلاح موجود** هر دو دکمه را گیت می‌کند:

```kotlin
holder.btnSuspend.visibility = if (isAdminUser) android.view.View.VISIBLE else android.view.View.GONE
holder.btnRegisterInvoice.visibility = if (isAdminUser) android.view.View.VISIBLE else android.view.View.GONE
```

⚠️ **نکتهٔ زبانی (چون کامپایل ممکن نیست، دستی رعایت شد):** در Kotlin، lambda انتهایی به
**آخرین پارامترِ اعلام‌شده** وصل می‌شود. اگر `isAdminUser` را بعد از `onClick` می‌گذاشتم،
فراخوانِ `TeacherClassAdapter(list, isAdminUser = isAdminUser) { … }` خطای نوع می‌داد ⇒
`isAdminUser` عمداً **قبل از** `onClick` اعلام شده و تست `12b` همین ترتیب را قفل می‌کند.

### تست‌ها
`12a` هر دو دکمه در `onBindViewHolder` با گارد `isAdminUser` · `12b` پرچم از Activity به آداپتر
می‌رسد + ترتیب پارامترها · `12c` layout مشترک و گارد/listener سمت ادمین دست‌نخورده.

---

## ۴) آیتم ۱۳ — صفحهٔ کلاس در پنل معلم: «امور مدیریتی» مخفی، فقط اصلاح اطلاعات + حذف کلاس

### ریشه
`ClassDetailActivity` (از بنر کلاسِ تأییدشدهٔ داشبورد معلم باز می‌شود) بخش
«امور مدیریتی و تنظیمات دوره» را با سه دکمه و **بدون هیچ چک نقشی** نشان می‌داد:

| دکمه | endpoint | برای معلم |
|---|---|---|
| `btnEditClassInfoAction` (۳) اصلاح اطلاعات کلاس | `PUT classes/update_info/{id}` | ✅ می‌ماند |
| `btnSuspendAction` (۴) تعلیق کلاس | `POST classes/{id}/suspend` — **یک‌سره مدیریتی** | ❌ پنهان شد |
| `btnDeleteClassAction` (۵) حذف کلاس | برای غیر ادمین از قبل `POST classes/{id}/request_delete` | ✅ می‌ماند |

تنها کار ادمینیِ این بخش «تعلیق» بود؛ «حذف» از قبل نقش‌آگاه است
(`showDeleteClassDialog:334` همان `USER_SUB_ROLE` را می‌خواند و برای غیر ادمین «درخواست حذف» می‌فرستد).

### فیکس
```kotlin
if (subRole == "admin") {
    btnSuspendAction.setOnClickListener { suspendClass() }
} else {
    btnSuspendAction.visibility = View.GONE
}
```

### تست‌ها
`13a` چک نقش + `GONE` + listener فقط در شاخهٔ ادمین · `13b` «اصلاح اطلاعات» و «حذف کلاس» هرگز
برای معلم پنهان نشوند · `13c` مسیر «درخواست حذف» برای غیر ادمین سالم · `13d` layout و
سیم‌کشی endpointها دست‌نخورده (دقیقاً یک فراخوانی `suspendClass()` از دکمه).

### ⚠️ سؤال باز (در بخش ۸)
عنوانِ خودِ بخش هنوز «امور مدیریتی و تنظیمات دوره» است (در layout **id ندارد** و پنهان‌کردنش
نیاز به افزودن id داشت). چون دو دکمهٔ باقی‌مانده زیر همین عنوان می‌نشینند، عنوان را دست نزدم.

---

## ۵) آیتم ۱۵ — پاپ‌آپ نهایی ثبت کلاس: «رفتن به کلاس‌های منتظر تایید» حذف

### ریشه
مسیر: پنل معلم → بنر کلاسِ در انتظار تأیید (یا «کلاس‌های ناقص») → `ClassSetupActivity` →
«ثبت نهایی و اتمام کلاس» → `showClassSummaryPage()` → بعد از «ارسال برای تأیید»، دیالوگِ
`csetup_sent_msg` **سه** دکمه داشت؛ دکمهٔ میانی «رفتن به کلاس‌های منتظر تایید»
(`csetup_sent_go`) → `PendingClassesActivity` = **صفِ تأیید ادمین** (رد/تایید کلاس‌ها) که معلم کارِ آن‌جا ندارد.

### فیکس
دیالوگ برای همه ساخته می‌شود؛ فقط دکمهٔ میانی داخل گارد ادمین است:

```kotlin
val sentDialogBuilder = AlertDialog.Builder(this@ClassSetupActivity)
    .setTitle(getString(R.string.csetup_sent_title))
    .setMessage(getString(R.string.csetup_sent_msg))
    .setPositiveButton(getString(R.string.common_ok)) { _, _ -> finish() }
    .setCancelable(false)

if (subRole == "admin") {
    sentDialogBuilder.setNeutralButton(getString(R.string.csetup_sent_go)) { _, _ -> /* PendingClassesActivity */ }
}
sentDialogBuilder.show()
```

چک نقش، همان الگوی موجودِ خودِ همین فایل است (در آداپتر دانش‌آموزانش برای **منشی** دکمهٔ حذف را `GONE` می‌کند).
پیام «به مدیر اطلاع بده تا تایید کند» و دکمهٔ «باشه» برای معلم می‌ماند ⇒ فقط میان‌بُر ادمینی حذف شد.

### تست‌ها
`15a` دکمهٔ میانی و `PendingClassesActivity` فقط پشت گارد ادمین · `15b` عنوان/پیام/«باشه» بیرون
گارد و دیالوگ همچنان `show()` می‌شود · `15c` رشته‌ها و گاردِ منشی دست‌نخورده.

---

## ۶) آیتم ۱۴ — داخل کلاس در پنل معلم: همهٔ قسمت‌های ادمین مخفی (پروفایل دانش‌آموز خواندنی)

### مسیر (کارفرما تأیید کرد)
پنل معلم → بنر کلاس → «۱) ثبت حضور و غیاب» (`AttendanceActivity`) → **نام دانش‌آموز** در لیست
حضور و غیاب (`AttendanceActivity:934`) → `StudentProfileActivity`.
همین صفحه از `ClassSetupActivity:505` (راه‌اندازی کلاس)، `LiveRosterActivity:160` و
`LiveClassActivity:287` (کلاس زنده) هم باز می‌شود.

### ریشه
تنها چک نقشِ `StudentProfileActivity` این بود: `if (subRole == "secretary")` → فقط «حذف کامل
دانش‌آموز» `GONE`. یعنی **معلم** همهٔ این‌ها را فعال می‌دید:

| ویجت | متن روی صفحه | endpoint |
|---|---|---|
| `btnIssueInvoice` | «صدور فیش و ثبت حواله» | → `InvoiceActivity` (وصول پول) |
| `switchSuspend` | «تعلیق دانش‌آموز (غیرفعال موقت)» | `POST admin/students/{id}/toggle_suspend` |
| `btnDeleteStudent` | «حذف کامل دانش‌آموز» | `DELETE admin/students/{id}` |
| `btnAddInstallment` | «➕ افزودن قسط جدید» | ساخت قسط |
| `btnInstallmentPay` / `btnInstallmentRemind` | «پرداخت» / «یادآوری» روی هر قسط | پرداخت قسط + SMS |
| `btnSendPortalLink` | «ارسال لینک پورتال به اولیا» | `sendPortalLink` |
| `fabEditProfile` + `imgProfile` | ویرایش پروفایل / تغییر عکس | `EditStudentActivity` + آپلود |

### فیکس (طبق انتخاب کارفرما: «همهٔ موارد مدیریتی»)
برای `USER_SUB_ROLE == "teacher"`:

1. هر شش ویجت بالا `View.GONE` — **کلِ کارت تعلیق** (نه فقط کلید) با افزودن
   `android:id="@+id/cardSuspendStudent"` به layout، تا عنوان و توضیحش هم نماند.
2. هیچ listenerی برای آن‌ها ثبت نمی‌شود (`if (!isTeacherUser) { … }` — شامل FAB در `onCreate` و تغییر عکس).
3. در ردیف اقساط، `layoutInstallmentActions` (پرداخت/یادآوری) برای معلم `GONE`.
4. نمای خواندنی دست‌نخورده: تب‌ها (مشخصات/مالی/کارنامه/اقساط/ارتباطات/تایم‌لاین)، آمار بدهی، لیست اقساط.

**layout:** فقط افزودن یک `android:id` (+ توضیح) به `activity_student_profile.xml` — برای ادمین/منشی هیچ تغییری ایجاد نمی‌کند (`xml.etree` parse شد).

### 🔴 تصمیم دامنه (نیازمند تأیید کارفرما — بخش ۸)
گارد روی **`subRole == "teacher"`** است، نه `!= "admin"`:

- «منشی» در این اپ **نقش وصول پول** است؛ endpointهای مالی سرور `("admin","secretary")` را می‌پذیرند
  (مثلاً `routers/analytics.py:304`) و رفتار قبلی منشی در همین صفحه (فقط پنهان‌شدن «حذف کامل») عمداً حفظ شد.
- اگر گارد `!= "admin"` گذاشته می‌شد، منشی «صدور فیش و ثبت حواله» و «تعلیق» و «قسط» را از دست می‌داد = شکستن گردش‌کار روزانهٔ او.
- تغییرش **یک کلمه** است: `isTeacherUser = subRole != "admin"` (تست `14c` الان عمداً جلوی این تغییر را می‌گیرد تا تصادفی نباشد).

### تست‌ها
`14a` هر شش ویجت + id کارت تعلیق · `14b` همهٔ listenerهای ادمینی فقط داخل `if (!isTeacherUser)`
(شامل FAB در `onCreate`) · `14c` گارد منشی سالم + گارد معلم `!= "admin"` **نباشد** ·
`14d` پرداخت/یادآوری قسط برای معلم پنهان · `14e` اجزای خواندنی پنهان نشوند + مسیر ورود از
`AttendanceActivity`/`ClassSetupActivity` سر جایش بماند.

---

## ۷) راستی‌آزمایی

| بررسی | نتیجه |
|---|---|
| سوئیت کامل (`pytest Kharazmi_Server/tests`) روی کپی `/tmp/g3_full.db` | **۱۱۴۸ passed** (قبل از گروه ۳: ۱۱۲۶ ⇒ ۲۲ تست جدید) |
| md5 فایل واقعی `Kharazmi_Server/gaj_db.db` | `f048f8d118b33c4eaa944490594121d7` — **بدون تغییر** |
| `ast.parse(main.py)` | ok |
| balansing `{}`/`()` فایل‌های کاتلین دست‌خورده نسبت به HEAD | همه بدون تغییر (۰/۰) — `ClassDetailActivity` از قبل `parens=-5` داشت (متن فارسی)، HEAD و WORK یکسان |
| `xml.etree.ElementTree.parse` روی `activity_student_profile.xml` | ok |
| تغییر سمت سرور | **هیچ** (فقط `Kharazmi_Server/tests/…` اضافه شد) |
| کامپایل اندروید | طبق قانون انجام **نشد** (Gradle/JDK/SDK در سندباکس نیست) |

### فایل‌های دست‌خورده (۶ فایل کد + ۱ layout + ۱ تست)
```
KharazmiAdmin/.../TeacherProfileActivity.kt      (آیتم ۱۰)
KharazmiAdmin/.../TeacherDashboardActivity.kt    (آیتم‌های ۱۱ و ۱۲)
KharazmiAdmin/.../ClassDetailActivity.kt         (آیتم ۱۳)
KharazmiAdmin/.../ClassSetupActivity.kt          (آیتم ۱۵)
KharazmiAdmin/.../StudentProfileActivity.kt      (آیتم ۱۴)
KharazmiAdmin/.../res/layout/activity_student_profile.xml  (آیتم ۱۴ — فقط افزودن یک id)
Kharazmi_Server/tests/test_group3_teacher_ui_access.py     (۲۲ تست ایستا)
```

---

## ۸) سؤال‌های باز / تصمیم‌های کارفرما

1. **آیتم ۱۴ — دامنهٔ منشی:** الان معلم هیچ‌کدام را نمی‌بیند و **منشی مثل قبل** (حواله/تعلیق/قسط
   برایش باز، فقط «حذف کامل» پنهان). اگر می‌خواهید منشی هم نبیند ⇒ یک کلمه تغییر
   (`isTeacherUser = subRole != "admin"`) + به‌روزرسانی تست `14c`.
2. **آیتم ۱۳ — عنوان بخش:** عنوان «امور مدیریتی و تنظیمات دوره» در صفحهٔ کلاس هنوز هست (بدون id در
   layout) و زیرش فقط «اصلاح اطلاعات» و «حذف کلاس» مانده. می‌خواهید برای معلم عنوانش عوض شود
   (مثلاً «تنظیمات دوره») یا کامل پنهان شود؟
3. **کد مرده پیدا شد (گزارش، بدون تغییر):**
   - `SessionHistoryActivity` («تاریخچه جلسات برگزار شده») فقط از `ClassDashboardActivity` باز می‌شود و
     `ClassDashboardActivity` **هیچ‌جای اپ فراخوانی نمی‌شود** ⇒ عملاً هر دو مرده‌اند. اگر «تاریخچهٔ جلسات»
     مدنظر کارفرما این صفحه بوده، باید اول مسیرش وصل شود (کار جدا).
   - تب «تاریخچه جلسات» در `ClassDetailActivity` فقط متن است (شماره/تاریخ/حاضر/غایب) و هیچ دکمه‌ای ندارد.
   - `ClassDetailActivity.openStudentProfile()` تعریف شده ولی هیچ‌جا صدا زده نمی‌شود (کلیک روی دانش‌آموز،
     دیالوگِ تاریخچهٔ حضور و غیاب را باز می‌کند).
4. **آیتم ۷ (گروه ۲)** همچنان **بازتولید‌نشده** است — منتظر لاگ/اسکرین‌شات دستگاه + نقش حساب کاربری.

---

## ۹) چک‌لیست تست دستی روی دستگاه (با حساب معلم وارد شوید)

| # | مسیر | انتظار |
|---|---|---|
| ۱۰ | پروفایل عملکرد معلم → تب تسویه‌حساب → «تسویه و ثبت پرداخت» | پاپ‌آپ موفقیت **بدون** «ثبت مجدد برای دانش‌آموز دیگر» |
| ۱۰-ب | (با ادمین) ثبت حوالهٔ دانش‌آموز در `InvoiceActivity` | دکمهٔ «ثبت مجدد برای دانش‌آموز دیگر» **سر جایش** |
| ۱۱ | داشبورد معلم | کارت «ثبت حواله» **نیست**؛ بقیهٔ میان‌برها هستند |
| ۱۲ | داشبورد معلم → بنر هر کلاس | «تعلیق» و «ثبت حواله» **نیستند** (جایشان خالی نمی‌ماند — `GONE`) |
| ۱۲-ب | (با ادمین) مدیریت کلاس‌ها | هر دو دکمه با رفتار قبلی فعال‌اند |
| ۱۳ | پنل معلم → بنر کلاس تأییدشده → صفحهٔ کلاس | «۴) تعلیق کلاس» **نیست**؛ «۳) اصلاح اطلاعات» و «۵) حذف کلاس» هستند (حذف = «درخواست حذف») |
| ۱۴ | پنل معلم → داخل کلاس → «ثبت حضور و غیاب» → نام دانش‌آموز | پروفایل دانش‌آموز **فقط خواندنی**: بدون حواله/تعلیق/حذف/افزودن قسط/پرداخت و یادآوری قسط/لینک پورتال/ویرایش |
| ۱۴-ب | (با ادمین و با منشی) همان پروفایل | برای ادمین همه‌چیز باز؛ برای منشی مثل قبل (فقط «حذف کامل» پنهان) |
| ۱۵ | پنل معلم → کلاس در انتظار تأیید → «ثبت نهایی و اتمام کلاس» → «ارسال برای تأیید» | دیالوگ با پیام و «باشه» — **بدون** «رفتن به کلاس‌های منتظر تایید» |
| ۱۵-ب | (با ادمین) همین مسیر | دکمهٔ «رفتن به کلاس‌های منتظر تایید» سر جایش |

> نکته: چون گاردها با `USER_SUB_ROLE` کار می‌کنند، بعد از هر **تغییر حساب** (خروج/ورود) تست کنید؛
> مقدار نقش در لاگین نوشته می‌شود (`LoginActivity` → `UserCreds`).

---

## ۱۰) سند تحویل برای جلسهٔ بعد (handoff) — وضعیت لحظهٔ پایان گروه ۳

**هدف این بخش:** چت/جلسهٔ بعدی بدون کانتکست قبلی، فقط از روی همین فایل بتواند ادامه دهد.

### ۱۰-۱) وضعیت ریپو (راستی‌آزمایی‌شده در پایان کار)

| مورد | وضعیت |
|---|---|
| برنچ | `arena/01a0c867-kharazmiapp` (جلسه به همین برنچ قفل است؛ به برنچ دیگری push نکنید) |
| HEAD محلی | `0c44979` |
| tip ریموت (`git ls-remote origin refs/heads/arena/01a0c867-kharazmiapp`) | `0c44979` — **یکسان** |
| `git diff HEAD FETCH_HEAD` | خالی ⇒ همهٔ تغییرات push شده |
| `git status --porcelain -uall` | خالی ⇒ working tree **تمیز** (فایل untracked/تغییرنیافتهٔ جامانده نداریم) |
| `git stash list` | خالی |
| CI (`gh run list --branch arena/01a0c867-kharazmiapp`) | همهٔ کامیت‌های گروه ۳ **success** (workflow: `tests`) |
| md5 `Kharazmi_Server/gaj_db.db` | `f048f8d118b33c4eaa944490594121d7` — از اول برنامه تا الان **دست‌نخورده** |

> نکتهٔ فنی: `remote.origin.fetch` فقط `main` را track می‌کند، پس `git rev-parse origin/arena/...`
> خطا می‌دهد. برای مقایسه با ریموت از این دو استفاده کنید:
> `git fetch origin arena/01a0c867-kharazmiapp` و بعد `git rev-parse FETCH_HEAD` / `git ls-remote origin refs/heads/arena/01a0c867-kharazmiapp`.

### ۱۰-۲) زنجیرهٔ کامل کامیت‌ها (همه push شده)

```
31a1f40  گروه ۱ (آیتم‌های ۱-۳: خطای ۴۰۹ پایان کلاس زنده · base_tuition=0 · کلاس ردشده در فهرست در انتظار)
5c9396d  گروه ۲ / آیتم ۴      73279b8  گروه ۲ / آیتم ۵
9900510  گروه ۲ / آیتم ۶+۹    8aeb64a  گروه ۲ / آیتم ۸
66a14a8  گروه ۲ / تکمیل ۹     9a36c13  گزارش گروه ۲
7409ca7  گروه ۳ / آیتم ۱۰     23743cb  گروه ۳ / آیتم ۱۱
3ed515f  گروه ۳ / آیتم ۱۲     4837847  گروه ۳ / آیتم ۱۳
d4d7c7a  گروه ۳ / آیتم ۱۵     f0ca350  گروه ۳ / آیتم ۱۴
0c44979  گزارش گروه ۳ (همین فایل)  ← HEAD
```

گزارش‌ها: `checkpoints/2026-09-22-group1-blockers.md` · `…-group2-numbers-and-reports.md` · `…-group3-teacher-ui-access.md`

### ۱۰-۳) چه چیزی تمام شده و چه چیزی باز است

**تمام:** گروه ۱ (۱-۳) · گروه ۲ (۴-۶، ۸، ۹) · گروه ۳ (۱۰-۱۵) · سوئیت **۱۱۴۸ passed** (۲۲ تست ایستای گروه ۳ در `Kharazmi_Server/tests/test_group3_teacher_ui_access.py`).

**باز:**
1. **متن دقیق آیتم‌های گروه ۴، ۵ و ۶ در هیچ فایلی از ریپو ثبت نشده** ⇒ جلسهٔ بعد باید از کارفرما بخواهد لیست را دوباره بفرستد (حدس نزنید).
2. **آیتم ۷ گروه ۲ بازتولید نشد** — نیاز به لاگ/اسکرین‌شات دستگاه + نقش همان حساب (جزئیات در گزارش گروه ۲، بخش ۶).
3. دو تصمیم بازِ گروه ۲ (بخش ۸ همان گزارش): (الف) وصل‌کردن دکمهٔ پیامک بدهکاران به `POST /finance/debtors/remind`، (ب) ساخت صفحهٔ «گزارش بدهکاران» در اپ ادمین (الان `btnDebtors` فقط Toast «به‌زودی» می‌دهد).
4. دو سؤال بازِ گروه ۳ (بخش ۸ همین فایل): دامنهٔ منشی در آیتم ۱۴ · عنوان «امور مدیریتی و تنظیمات دوره» در آیتم ۱۳.
5. کد مرده: `ClassDashboardActivity` (هیچ‌جا فراخوانی نمی‌شود) ⇒ `SessionHistoryActivity` عملاً مرده · `ClassDetailActivity.openStudentProfile()` بی‌استفاده.
6. **آیتم ۲۳** (طبق دستور کارفرما): ویرایش/حذف تسویه فقط با **سند برگشتی (reversal)**؛ اول **نقشهٔ کتبی** بنویسید و اگر با `financial_calculations.py` تضاد داشت **توقف کنید و بپرسید**.

### ۱۰-۴) قواعد کاری کارفرما که در جلسهٔ بعد هم برقرار است

- پاسخ‌ها **فارسی**؛ گزارش بعد از پایان هر گروه با سوئیت سبز.
- **هرگز اندروید کامپایل نشود** مگر صریحاً بخواهد (در این سندباکس Gradle/JDK/SDK نیست)؛ تغییرات کاتلین باید **از الگوی موجودِ همان فایل** پیروی کند.
- تغییر گروه ۳‌گونه (UI): **فقط UI**، endpoint دست‌نخورده، با **همان چک نقش موجود** (`UserCreds` → `USER_SUB_ROLE`) و بدون ساختن الگوی جدید.
- تست‌های زنده فقط روی **کپی `/tmp` از `gaj_db.db`**؛ هرگز روی فایل واقعی؛ md5 قبل/بعد مقایسه شود (مبنا: `f048f8d118b33c4eaa944490594121d7`).
- `edit_file` **سریال** (یکی‌یکی). بعد از هر تغییر چندفایلی: `ast.parse` + `import main` واقعی روی کپی `/tmp`.
- هر آیتم: **تست قرمز → فیکس حداقلی → سبز → سوئیت کامل سبز → کامیت جدا → push فوری**.
- اگر چیزی با کد نمی‌خواند، **بگویید و حدس نزنید** (در گروه ۳ برای آیتم ۱۴ همین را کردیم و مسیر درست را از کارفرما پرسیدیم).
- موارد «(پیشنهاد من)» **فیچر** هستند و باید به زیرساخت موجود سوار شوند (SMS قسطی، `ActivityLog`، conflict-check بچ۲، خلاصهٔ همکاری معلم) — بازنویسی نکنید.
- ترتیب گروه‌ها ۱→۶ رعایت شود؛ اگر فیکسی طول کشید، تا همان‌جا فیکس + گزارش + push کنید و بعد سراغ بعدیِ **همان گروه** بروید.

### ۱۰-۵) دستور اجرای سوئیت و بازیابی محیط

```bash
# سوئیت کامل (همیشه روی کپی موقت از DB)
cd /home/user/KharazmiApp
rm -f /tmp/g3_full.db && cp Kharazmi_Server/gaj_db.db /tmp/g3_full.db
DATABASE_URL=sqlite:////tmp/g3_full.db JWT_SECRET_KEY=<hex> \
  /home/user/.venv/bin/python -m pytest Kharazmi_Server/tests -q -p no:randomly
# انتظار: 1148 passed (حدود ۱۰۰ ثانیه)
```

**اگر sandbox بازسازی شد** (git محلی و `.venv` می‌پرند ولی فایل‌های کاری و ریموت سالم می‌مانند):

```bash
cd /home/user/KharazmiApp
git ls-remote origin 'refs/heads/arena/*'          # tip ریموت باید 0c44979 باشد
git fetch origin arena/01a0c867-kharazmiapp
git reset --mixed FETCH_HEAD                       # تاریخ برمی‌گردد، working tree دست‌نخورده
# سپس .venv را با همان نسخه‌ها بسازید: fastapi 0.141.1 · sqlalchemy 2.0.54 · pydantic 2.13.5
#                                     pytest 9.1.1 · openpyxl 3.1.5 (Python 3.11.2)
# و سوئیت را اجرا کنید؛ هر کار push‌نشده را دوباره کامیت و push کنید.
```

`gh workflow run` در این محیط **HTTP 403** می‌دهد (تلاش نکنید)؛ ولی workflow `tests` روی هر push خودش اجرا می‌شود و با `gh run list --branch arena/01a0c867-kharazmiapp` دیده می‌شود.
