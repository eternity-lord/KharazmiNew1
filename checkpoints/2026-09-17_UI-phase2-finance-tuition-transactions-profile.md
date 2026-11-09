# CHK 2026-09-17 — UI/UX Phase 2: مالی / شهریه / اقساط / تراکنش‌ها / پروفایل دانش‌آموز

برنچ: `arena/01a0aac2-kharazmiapp` | ریپو: `eternity-lord/KharazmiApp`
نوع تسک: **فقط visual/UI refactor** — صفر تغییر در منطق برنامه.

---

## ۱) وضعیت ابتدای کار

```
$ git status --porcelain        → (خالی) — درخت تمیز
$ git log -1 --oneline          → 30916bf UI/UX Phase 1: Design System + Login + Main Dashboard
$ git branch --show-current     → arena/01a0aac2-kharazmiapp
$ git ls-remote origin arena/01a0aac2-kharazmiapp
                                → 30916bf4744377b90b30c6663cb045666e8ed4a2  (هم‌گام ✅)
$ sha256sum Kharazmi_Server/gaj_db.db
                                → f0e55fe7c5130ec17e39e73036e2291794c3c335f67d852c37599a6c0f99ec79 (ثابت، دست‌نخورده)
```

## ۲) baseline اندروید — **اجرا نشد، دلیل دقیق محیطی (بدون جعل نتیجه)**

| دستور درخواستی | خروجی واقعی |
|---|---|
| `cd KharazmiAdmin && ./gradlew :app:assembleDebug` | `/bin/bash: ./gradlew: Permission denied` — `exit=126` |
| `bash ./gradlew :app:assembleDebug` | `ERROR: JAVA_HOME is not set and no 'java' command could be found in your PATH.` |
| `bash ./gradlew :app:test` | همان خطای JAVA_HOME |
| `bash ./gradlew :app:lint` | همان خطای JAVA_HOME |

ابزار محیط (اندازه‌گیری‌شده): `java: command not found`، `JAVA_HOME`/`ANDROID_HOME`/`ANDROID_SDK_ROOT` خالی، `/usr/lib/jvm` وجود ندارد،
`sdkmanager`/`aapt2` وجود ندارد، `gradle-8.13-bin.zip` دانلود‌شدنی نیست (`services.gradle.org → 000`, `dl.google.com → 000`, `repo1.maven.org → 000`؛ فقط `pypi.org → 200`).
`gradlew` هم بیت اجرا ندارد (`-rw-r--r--`) و **chmod نشد** (قید تسک).
معادل استاتیک (بخش ۶) اجرا شد.

## ۳) دامنه — چه چیزی تغییر کرد و چه چیزی نه

**فقط منابع XML:** `res/layout/*` (۷ فایل)، `res/values/{strings,colors,dimens}.xml`، `res/color/*` (۳ selector)، `res/drawable/*` (۸ آیکون).

| untouched (صفر تغییر) | اثبات |
|---|---|
| هیچ فایل Python | `git status --porcelain | grep '\.py$'` → خالی |
| هیچ فایل Kotlin/Java | `git status --porcelain | grep '\.kt$\|\.java$'` → خالی |
| `ApiInterfaces.kt`, `AppModels.kt`, `RetrofitClient.kt` | در diff نیستند |
| `StudentProfileActivity.kt`, `InvoiceActivity.kt`, `TransactionManageActivity.kt`, `ReportActivity.kt` | در diff نیستند (۱۱۸۱/۹۰۲/۲۶۰/۴۳۱ خط، بیت‌تغییر) |
| endpoint/درخواست/response | حتی یک رشته‌ی URL یا DTO اضافه/کم نشد |
| فرمول بدهی/اعتبار/پرداخت/refund/قسط | هیچ‌کدام لمس نشد |
| نقش/permission | `currentUserRole` و شاخه‌های GONE/GONE دست‌نخورده |
| Intent extra / نام Activity | دست‌نخورده |
| `AndroidManifest.xml` / `styles`/`themes` | دست‌نخورده (تم‌های روشن/تیره بدون تغییر) |

## ۴) فایل‌های تغییر‌یافته

```
$ git diff --cached --stat      → 21 files changed, 1570 insertions(+), 1007 deletions(-)

 color/ds_button_danger_bg.xml        |   4 ±   (قرمز عمیق پرشده برای کنتراست)
 color/ds_switch_thumb.xml            |  10 +   (جدید)
 color/ds_switch_track.xml            |  10 +   (جدید)
 drawable/ic_ds_{wallet,receipt,payments,person,event,refund,edit,delete}_24.xml | 8×11 +  (جدید)
 layout/activity_student_profile.xml  | 601 ±
 layout/activity_invoice.xml          | 533 ±
 layout/activity_report.xml           | 586 ±
 layout/activity_transaction_manage.xml | 148 ±
 layout/item_installment.xml          | 146 ±
 layout/item_transaction_admin.xml    | 192 ±
 layout/item_report.xml               |  92 ±
 values/colors.xml                    |   3 +   (۲ توکن قرمز عمیق)
 values/dimens.xml                    |   2 +   (ds_toolbar_height=56dp)
 values/strings.xml                   | 162 ±   (۷۰ کلید جدید + ۳۶ بازنویسی نمایشی)
```

## ۵) طراحی هر صفحه (خلاصه)

| صفحه | طراحی جدید |
|---|---|
| **پروفایل دانش‌آموز** | هدر با آواتار ۹۶dp (کلیک‌پذیر = تغییر تصویر، کد خودش listener می‌گذارد)، نام/تلفن، ۶ تب حفظ‌شده با همان ترتیب و اندیس‌ها؛ کارت «وضعیت حساب دانش‌آموز» با `tvTotalDebt` درشت (متن/رنگ از کد: بدهی/تسویه/اعتبار) + دو ردیف جدا **سهم معلم** و **سهم آموزشگاه** با آیکون مجزا، یادداشت «مبلغ هیچ‌وقت با علامت منفی نشان داده نمی‌شود»؛ CTA طلایی صدور فیش؛ کارت محتوای تب‌ها؛ کارت اقساط + حالت خالی؛ کارت تعلیق با سوییچ روشن/خاموش متمایز؛ اکشن‌های ثانویه (پورتال/حذف) با تفکیک رنگ. همه‌چیز داخل `NestedScrollView`. |
| **صدور فیش** | نوار بالا تیره‌ـ‌طلایی؛ کارت «جست‌وجوی طرف حساب»؛ کارت خلاصه حساب با مبلغ کل درشت + تفکیک سهم معلم/آموزشگاه (رنگ مستقل: هشدار/اطلاع)؛ کارت اطلاعات پرداخت با رادیوهای ۴۸dp؛ یادداشت شفاف «خلاصه و رسید قبل از ثبت»؛ `btnSubmit` همان `GoldButton` (منطق loading دست‌نخورده) با ارتفاع ۴۸dp. |
| **مدیریت حواله‌ها** | نوار عنوان تیره، کارت‌های اکشن ثانویه (Excel/PDF)، یادداشت ایمنی، لیست، نوار «جمع کل» با مبلغ طلایی درشت؛ `cardReportFilter` عیناً حفظ شد (۰dp و GONE) فقط برای جلوگیری از NPE کد. |
| **گزارش‌گیری** | کارت «۱. محدوده گزارش» (آموزشگاه/معلم)، «۲. فیلتر بازه زمانی» (سال/ماه/معلم با آیکون راهنما)، CTA اصلی طلایی، کارت آمار ماهانه/سالانه با تفکیک رنگی درآمد/وصول‌نشده، کارت صورت‌حساب با جست‌وجو و نتیجه (پیش‌فرض GONE، کنترل با کد)، چاپ به‌عنوان اکشن ثانویه. |
| **کارت قسط** | ردیف عنوان کلاس + برچسب «مبلغ قسط» + مبلغ درشت؛ سررسید با آیکون تقویم تزئینی؛ وضعیت به‌صورت پیل رنگی (پرداخت‌شده/در انتظار/معوق) که رنگش را کد می‌دهد؛ ردیف تاریخ پرداخت (فقط پرداخت‌شده)؛ دو اکشن یادآوری/پرداخت با ارتفاع ۴۸dp و وزن برابر. |
| **کارت تراکنش (ادمین)** | مبلغ برجسته با رقم‌های هم‌عرض (`tnum`)، نام/بابت/تاریخ خوانا، سه اکشن مجزا: **چاپ** (خنثی) / **ویرایش** (قاب کهربایی هشدار) / **حذف** (قاب قرمز خطر) — همه ۴۸dp و هم‌عرض. |
| **ردیف گزارش** | چک‌باکس انتخابی (پیش‌فرض GONE، کنترل با کد) با هدف ۴۸dp، نام/توضیح دوسطری، مبلغ برجسته و تاریخ ثانویه. |

## ۶) تست محافظتی — ۱۲ بند درخواستی + گاردهای اضافه

| # | بند | نتیجه |
|---|---|---|
| ۱ | هیچ فایل Python تغییر نکرده | ✅ هیچ |
| ۲ | لایه‌ی API/مدل‌ها/۴ Activity دست‌نخورده | ✅ هیچ (`git status` + `git diff`) |
| ۳ | همه‌ی `R.id`های استفاده‌شده در Kotlin موجود باشند | ✅ `StudentProfile 39/39`, `Invoice 34/34`, `TransactionManage 14/14`, `Report 26/26` (IDهای دیالوگ‌های همان Activity جدا محاسبه شد) |
| ۴ | همه‌ی View IDهای قبلی حفظ شده باشند | ✅ 102 شناسه: ۲۶→۲۶، ۲۸→۲۸، ۶→۶، ۳۰→۳۰، ۸→۸، ۷→۷، ۵→۵ — صفر حذف، صفر افزوده |
| ۵ | هیچ `@id` مرده‌ی **جدید** | ✅ هیچ. ۷ شناسه‌ی بی‌ارجاع قبلی (از HEAD) طبق قید «حذف نکردن ID موجود» نگه داشته شدند: `layoutDebtTeacher/Institute`، `cardFilters`، `cardMonthlySummary`، `cardStudentStatement`، `cbSelectReport`، `tvDesc` |
| ۶ | فونت روی متن‌ها از تم (`@font/app_font`) | ✅ از تم می‌آید (دست‌نخورده). ⚠️ `app_font.xml` به `@font/vazirmatn_regular` اشاره می‌کند که فایلش در ریپو نیست — **ایراد پیش‌موجود**، خارج از دامنه‌ی فاز ۲ و طبق قید فاز ۱ («app_font حفظ شود») تغییر نکرد |
| ۷ | همه‌ی کلیک‌پذیرها ≥48dp | ✅ صفر مورد؛ همه‌ی دکمه‌ها `@dimen/min_touch_target`، ردیف‌های رادیویی/سوییچ/چک‌باکس/آواتار (۹۶dp) هم ≥48 |
| ۸ | بدون `?attr/color*` و بدون رنگ hex | ✅ صفر hex و صفر `?attr` (سه `?attr/actionBarSize` با `@dimen/ds_toolbar_height` جایگزین شد) |
| ۹ | کنتراست در دو تم ≥4.5 | ✅ ۹۱ متن با ≥4.5:1، صفر خطا. اصلاح لازم: متن سفید روی `ds_danger` ۳٫۴۸ بود ⇒ توکن `ds_danger_deep` (#B03A33, ۶٫۰۰:۱) برای دکمه‌ی پرشده‌ی خطر اضافه شد؛ سوییچ: روشن ۳٫۲۳:۱ / خاموش ۷٫۵۰:۱ / غیرفعال ۵٫۳۳:۱ |
| ۱۰ | res well-formed و منابع resolvable | ✅ همه‌ی `res/**/*.xml` پارس می‌شوند؛ صفر ارجاع حل‌نشده در ۷ چیدمان و فایل‌های values |
| ۱۱ | حالت empty/loading/error | ⚠️ فقط با تغییر کد ممکن است: در `ReportActivity`/`TransactionManageActivity` حالت‌ها با `Toast` مدیریت می‌شوند و هیچ ویوی برای empty/error وجود ندارد؛ ساختن ویوی مرده = «UI توخالی» پس اضافه نشد (کارت‌های `tvInstallmentsEmpty`/`tvStudentCommunicationEmpty`/`tvStudentTimelineEmpty` که کد واقعاً آن‌ها را کنترل می‌کند بازطراحی و حفظ شدند) |
| ۱۲ | attributeهای منطقی/ورودی حفظ شده | ✅ `visibility/inputType/hint/checked/enabled/maxLength/imeOptions/endIconMode` صفر تفاوت با HEAD (`tilTeacherFilter.endIconMode=dropdown_menu` که بی‌سابقه بود، به آیکون تزئینی `startIconDrawable` تبدیل شد تا هیچ رفتار جدیدی اضافه نشود) |

گاردهای اضافه‌ی این تسک (قابل اجرا مجدد):

```
python3 /tmp/phase2_checks.py    # چک‌لیست ۱۲ماده‌ای (شکست: 0 | اخطار: 2)
python3 /tmp/xmlcompare.py       # مقایسه‌ی ساختاری با HEAD (OK ✅)
python3 /tmp/contrast.py         # کنتراست WCAG (۹۱ متن ≥4.5 | 0 خطا)
python3 /tmp/idcheck.py          # نگاشت ID↔نوع Kotlin (همه OK ✅)
python3 /tmp/phase2_guard.py     # شناسه/نوع/attribute حساس + حل منابع
```
سایر بررسی‌های استاتیک: کلاس همه‌ی ویوها سابقه‌ی استفاده در HEAD دارند (پس وابستگی‌شان موجود است)، ساختار والد/فرزند
(هر `TextInputLayout` دقیقاً ۱ فرزند، هر `MaterialCardView` ≤۱ فرزند، `TabLayout` با ۶ تب) سالم است،
و ۳۵ متن literal فارسی در چیدمان‌ها به منبع/جای‌نگهدار `@string/ds_value_placeholder` منتقل شد.

## ۷) متن‌های مالی — قید «منفی خام هرگز»

- Kotlin (دست‌نخورده) منفی را با کلیدهای `profile_debt_total` («بدهی باقی‌مانده: %1$s تومان»)، `profile_credit_total` («اعتبار دانش‌آموز: %1$s تومان»)، `profile_settled_total` («تسویه‌شده») و `profile_ower/creditor/settled` نگاشت می‌کند ⇒ **عدد منفی در XML/UI دیده نمی‌شود**.
- ۳۶ رشته‌ی نمایشی بازنویسی شد (حذف ایموجی/دابل‌کوتیشن سرگردان، شفاف‌سازی «باقی‌مانده/مانده سهم/وصول‌نشده»)، و بررسی خودکار تأیید کرد **هیچ placeholder (`%1$s`…) کم/زیاد نشده** و هیچ کلیدی حذف نشده است (۷۰ کلید جدید، ۰ حذف، ۰ تکراری، مجموع ۱۴۶۹ رشته).
- منفی خام فقط در یک مسیر دیده می‌شود که **خارج از این ۵ صفحه و خارج از دامنه‌ی تسک** است: اندپوینت قدیمی `GET /admin/students/{id}/full-profile` که تراکنش‌ها را به‌صورت رشته‌ی خام (`f"{t.date}: {t.amount:,} (...)"`) می‌سازد و محدود به ۵ ردیف است. برای رفع آن باید سرور (Python) تغییر کند که در این تسک ممنوع است.

## ۸) آنچه اجرا نشد / محدودیت‌ها (صریح)

- `assembleDebug` / `test` / `lint` → اجرا نشد (بخش ۲: نه JDK، نه SDK، نه شبکه). هیچ ادعای سبز بودن کامپایل وجود ندارد.
- تست روی دستگاه/emulator و بازبینی بصری واقعی → ممکن نبود؛ به‌جای آن ماکاپ HTML از روی همان توکن‌ها/رشته‌های ریپو ساخته شد: `design-preview/phase2.html` (خارج از ریپو نگه داشته می‌شود).
- اضافه‌کردن UI برای loading/empty/error در دو صفحه‌ی گزارش و تراکنش‌ها → نیازمند تغییر Kotlin (خارج از دامنه).
- «نوع» تراکنش در کارت‌های ادمین: مدل لیست سرور اصلاً `type` را برنمی‌گرداند ⇒ چیپ نوع اضافه نشد (وفادار به داده‌ی موجود).
- رنگ `#1565C0` که `ExamActivity` (کد، دست‌نخورده) روی `tvTotalDebt` در دیالوگ کارنامه ست می‌کند، روی سطح تیره ≈۳٫۰:۱ است (حد AA برای متن درشت) — این مسیر با کد کنترل می‌شود و در این تسک قابل اصلاح نبود.
- کارت `cardFinancialStatus` در دیالوگ `ExamActivity` به‌عنوان دکمه‌ی دانلود PDF بازاستفاده می‌شود؛ نوع (`MaterialCardView`)، شناسه و ساختارش حفظ شد و listener را خود کد می‌گذارد.

## ۹) بازتولید

```
git checkout arena/01a0aac2-kharazmiapp
git log -1 --oneline
cd KharazmiAdmin && bash ./gradlew :app:assembleDebug   # در این سندباکس: خطای JAVA_HOME
python3 /tmp/phase2_checks.py && python3 /tmp/xmlcompare.py && python3 /tmp/contrast.py && python3 /tmp/idcheck.py
```
