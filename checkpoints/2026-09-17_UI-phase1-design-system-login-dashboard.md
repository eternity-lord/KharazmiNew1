# CHK 2026-09-17 — UI/UX Phase 1: Design System + Login + Main Dashboard

برنچ: `arena/01a0aac2-kharazmiapp` | ریپو: `eternity-lord/KharazmiApp`
نوع تسک: **فقط visual/UI refactor** — صفر تغییر در منطق برنامه (هیچ فایل Kotlin/Java/Python تغییر نکرد).

---

## ۱) وضعیت ابتدای کار (dump دستورات درخواستی)

```
$ git status --short      → (خالی) — درخت تمیز
$ git log -1 --oneline    → f1c4efc FIX: رفع F-R1 ... + F-R2 ... + رگرسیون تستی
$ git branch --show-current → arena/01a0aac2-kharazmiapp
$ git ls-remote origin arena/01a0aac2-kharazmiapp → f1c4efc9a914ecfa7051e734c24526406e811b54  (هم‌گام ✅)
```

## ۲) baseline اندروید: **اجرا نشد — دلیل دقیق محیطی**

| دستور درخواستی | نتیجه واقعی |
|---|---|
| `cd KharazmiAdmin && ./gradlew :app:assembleDebug` | `Permission denied` (بیت اجرا ندارد، exit 126)؛ بعد از `bash gradlew` → خطای JDK |
| `bash ./gradlew :app:assembleDebug` | `ERROR: JAVA_HOME is not set and no 'java' command could be found in your PATH.` |
| `./gradlew :app:test` | هرگز اجرا نمی‌شود — همان خطای بالا قبل از هر تَسکی رخ می‌دهد |
| `./gradlew :app:lint` | همان |

دلایل قطعی (همه در همین سندباکس اندازه‌گیری شد):

1. **هیچ JDK نصب نیست:** `java: command not found`، `/usr/lib/jvm` وجود ندارد، `find` برای `javac`/`java` چیزی نیافت. نصب هم ممکن نیست: `sudo -n true` کار می‌کند ولی مخزن دبیان مسدود است (`http://deb.debian.org/debian/ → 000`).
2. **Android SDK نصب نیست:** `ANDROID_HOME` و `ANDROID_SDK_ROOT` خالی‌اند و `sdkmanager` وجود ندارد (`compileSdk = 34`, `minSdk = 24`, `targetSdk = 34`).
3. **شبکه به مخازن لازم بسته است:** `dl.google.com → 000`، `repo1.maven.org → 000`، `services.gradle.org → 000`.
   پس دانلود `gradle-8.13-bin.zip` (طبق `gradle-wrapper.properties`)، Android SDK و وابستگی‌های Maven/AndroidX هم ناممکن است. (فقط `pypi.org` باز است.)

**پس هیچ عدد build/test/lint جعل نشده و هیچ ادعایی دربارهٔ سبز بودن کامپایل وجود ندارد.** به‌جای آن، اعتبارسنجی استاتیک معادل انجام شد (بخش ۶).

### ۲-الف) دو خطای **از قبل موجود** در resource linking (کشف‌شده به‌صورت استاتیک، مستقل از تغییرات این تسک)

| مورد | شرح | تصمیم |
|---|---|---|
| `@font/vazirmatn_regular` | `res/font/app_font.xml` به این فونت ارجاع می‌دهد ولی هیچ فایل فونتی در ریپو نیست (`git ls-files res/font/` فقط `app_font.xml`؛ هیچ `.ttf/.otf` نه الان و نه در کل تاریخچه) ⇒ aapt2 در هر محیطی خطا می‌دهد | **تغییر نداد** — چون رفع آن یعنی جایگزینی فونت و طبق الزام تسک «font فعلی app_font حفظ شود». نیاز به افزودن `res/font/vazirmatn_regular.ttf` توسط توسعه‌دهنده |
| `@color/gold_bg_subtle` | `res/layout/item_dunning_draft.xml` دو بار این رنگ را ارجاع می‌داد ولی در هیچ `values*/colors.xml` تعریف نشده بود ⇒ خطای resource linking | **رفع شد** (افزودن رنگ در `colors.xml` مجاز و در دامنهٔ تسک بود): `<color name="gold_bg_subtle">#1A1E26</color>` |

> نتیجهٔ صریح: حتی با یک محیط سالم، `:app:assembleDebug` تا وقتی فایل فونت اضافه نشود با شکست resource linking متوقف می‌شود. این موضوع **قبل از این تسک** هم وجود داشته است.

## ۳) فایل‌های تغییرکرده (فقط UI/resource)

```
$ git diff --name-only | grep -E "\.(kt|java|py)$"   →  (خالی)
```

تغییرکرده‌ها:
- `KharazmiAdmin/app/src/main/AndroidManifest.xml` — فقط `android:windowSoftInputMode="adjustResize"` روی `LoginActivity` (نیاز الزام «کیبورد دکمه ورود را پنهان نکند»)
- `res/layout/activity_login.xml`, `res/layout/activity_main.xml`, `res/layout/activity_design_system.xml`, `res/layout/nav_header.xml`, `res/layout/dialog_ip_input.xml`, `res/layout/layout_empty.xml`
- `res/values/colors.xml`, `res/values/dimens.xml`, `res/values/strings.xml`
- جدید: `res/values/ds_styles.xml` + ۱۵ فایل `res/color/ds_*.xml` + ۱۶ فایل `res/drawable/` (شکل/رنگ‌حالت/آیکون‌های DS)

**عمداً تغییر نکرد:** `MainActivity.kt`, `LoginActivity.kt`, `DesignSystemActivity.kt`, `BaseActivity.kt`, `GoldButton.kt`, `AvatarHelper.kt`, `ApiInterfaces.kt`, `RetrofitClient.kt`, `AppModels.kt`, `ui_clickable_audit.py`، همهٔ فایل‌های پایتون سرور، `res/values/themes.xml` (نیازی به تغییر نداشت؛ تمام استایل‌های جدید در `ds_styles.xml` افزوده شدند) و هیچ استایل/رنگ legacy حذف نشد.

## ۴) Design System — چه ساخته شد

**توکن‌ها (`colors.xml`, `dimens.xml`) — جداکردن معنایی از تزئینی:**
- سطوح: `ds_bg_base` / `ds_bg_surface` / `ds_bg_surface_2` / `ds_bg_surface_3` / `ds_bg_surface_disabled` / `ds_border` / `ds_border_strong`
- اکسنت: `ds_accent` (طلایی)، `ds_accent_soft/strong`، `ds_on_accent`
- متن: `ds_text_primary/secondary/disabled` (+ `res/color/ds_text_secondary_state.xml` برای حالت disabled)
- معنایی: `ds_success|warning|danger|info` + `*_container` + `*_on_container`
- مالی: `ds_debt` / `ds_credit` (+ container) — در UI همیشه همراه متن/آیکون، نه فقط رنگ
- گروه‌های اولویت داشبورد: `ds_group_ops|tools|finance|academic|admin|critical`
- اندازه‌ها: spacing جدید (2/6/12/40/56dp)، `min_touch_target=48dp`، آیکون‌ها، شعاع‌ها (`corner_radius_xs`, `corner_radius_pill`)، ضخامت خط، فونت‌سایزهای `display|kpi_value|money|status|label|overline`، `dash_card_min_height`, `kpi_divider_height`, `pill_height`, `max_text_width`

**TextAppearanceهای استاندارد (`TextAppearance.Kharazmi.DS.*`):** `PageTitle`, `SectionTitle`, `Body`, `Caption`, `Money`, `Error`, `Status` + کمکی‌ها `Label`, `Overline`, `KpiValue` — همه با `@font/app_font` (بدون جایگزینی فونت).

**استایل‌ها:** `DS.Button.Primary/Secondary/Ghost/Danger`، `DS.Card/Surface2/Interactive/Status.{Success,Warning,Danger,Info}`، `DS.Input` و `DS.Input.Disabled`، `DS.Chip` و `DS.Chip.Tag`، `DS.Pill.{Success,Warning,Danger,Info,Neutral}`، `DS.Divider.Vertical`، `DS.SectionHeader`.

**Stateها (الزام ۷):** `res/color/ds_card_stroke*.xml` (default/focused/pressed/disabled برای پنج گروه)، `ds_input_stroke` (+ `boxStrokeErrorColor`)، `ds_chip_bg|text|stroke` (checked/selected/disabled)، `ds_button_danger_bg|text`، `bg_ds_ripple_borderless` (pressed برای کنترل‌های آیکونی).

**Lint/کیفیت:** `minHeight=48dp` روی دکمه‌ها/چک‌باکس/فیلدها/کارت‌های گرید؛ `ensureMinTouchTargetSize=true` برای چیپ‌ها؛ `contentDescription` برای آیکون‌های معنادار و `importantForAccessibility="no"` برای آیکون‌های تزئینی؛ RTL همه‌جا حفظ شد.

**کاتالوگ (`activity_design_system.xml` → کاتالوگ واقعی):** ۹ بخش — رنگ‌ها، تایپوگرافی، دکمه‌ها (شامل disabled/danger/ghost)، فیلدها (عادی/فوکوس/خطا/غیرفعال)، کارت‌ها (سطح۱، سطح۲، تعاملی، ۴ کارت وضعیت)، چیپ‌ها (انتخاب‌شده/غیرفعال/tag)، وضعیت‌ها (پیل رنگ+متن+آیکون، بدهی/اعتبار)، حالت خالی (include از `layout_empty`)، بارگذاری (ProgressBar + اسکلتون) و خطا (کارت خطر + CTA تلاش مجدد). شناسه‌های `imgAvatarSample1..3` برای `DesignSystemActivity.kt` دست‌نخورده‌اند.

## ۵) Login — بازطراحی بدون تغییر منطق

- ریشهٔ چیدمان `NestedScrollView` + `fillViewport` ⇒ در موبایل کوچک اسکرول می‌شود؛ به‌همراه `adjustResize` در Manifest، کیبورد دکمهٔ ورود را پنهان نمی‌کند.
- سلسله‌مراتب: تنظیمات سرور ← لوگو/برند ← کارت فرم (شماره موبایل، رمز، راهنما، دکمهٔ اصلی، remember-me) ← دو اکشن ثانویهٔ Outline ← لینک ثبت‌نام ← نسخه (Overline، پایین صفحه، کم‌اهمیت).
- دکمهٔ اصلی `GoldButton` با استایل Primary کاملاً از دکمه‌های Outline ثانویه متمایز است؛ **`setLoading()` روی همان `btnLogin` دست‌نخورده کار می‌کند** (نوع View تغییری نکرده: GoldButton).
- متن‌ها از `strings.xml` (شامل دو کلید جدیدِ «مقدار اصلی»: `ds_login_mobile_hint`=«شماره همراه»، `ds_login_password_note`=«(تنها برای معلمان دارای کلمه عبور)»)، `contentDescription` برای آیکون‌ها، حذف ایموجی از طراحی، حاشیه/فوکوس/خطای فیلد از `Widget.Kharazmi.DS.Input`.
- منطق Toast فعلی خطاها دست‌نخورده ماند (هیچ TextView خطای جدیدی ساخته نشد).

## ۶) Main Dashboard — بازطراحی بدون تغییر منطق

- سرصفحه: گرادیان تیره + خط موی طلایی (`bg_ds_header`) به‌جای نوار طلایی یکدست؛ `imgHeaderDashboardIcon` با آیکون داشبورد طلایی، ۴۸dp و `contentDescription`.
- KPIها کم‌تراکم‌تر با `KpiValue`/`Label` و جداکننده‌های نازک؛ `tvTodaySummaryTitle` همچنان clickable و آیکون رفرش جای نویسهٔ `↻`.
- هشدارها از KPI جدا شدند: کلاس دیرشروع (warning)، اقساط سررسیدشده (warning + آیکون خطر)، تسویهٔ معوق معلمان (info) — هر سه با رنگ + آیکون + متن و CTA «جزئیات».
- گرید: همان `dashboardGrid` سه‌ستونه، اما داخل `NestedScrollView` تا در نمایشگر کوچک بریده نشود؛ `rowWeight` به `minHeight` توکن‌دار تبدیل شد (داخل scroll معنا نداشت). **هیچ کارتی حذف نشد** و ۵ سرصفحهٔ گروهی داخل خود XML اضافه شد (عملیات روزمره/ابزار مدیریتی/مالی/آموزشی/مدیریت ارشد) با رنگ اولویت‌دار، نه همه طلایی.
- `nav_view` و `drawer_layout` و `appBarLayout` دست‌نخورده؛ سرصفحهٔ دراور (`nav_header`) به توکن‌های تیره/طلایی منتقل شد (رنگ‌های هاردکد `#E0E0E0`/`#D32F2F` حذف شدند).
- هیچ انیمیشن تازه‌ای اضافه نشد؛ `animateEntrance()` در MainActivity همان‌طور کار می‌کند.

## ۷) نتیجهٔ اعتبارسنجی استاتیک (جایگزین aapt2/lint در نبود SDK)

| بررسی | نتیجه |
|---|---|
| well-formed بودن همهٔ XMLهای `res/` | ✅ هیچ خطا (پس از رفع سه خطای کامنتی `--`) |
| حل‌شدن همهٔ `@type/name` در چیدمان‌های تغییرکرده/جدید | ✅ (به‌جز موارد کتابخانه‌ای Material و یک مورد فونتِ از قبل موجود که در بخش ۲-الف توضیح داده شد) |
| حل‌شدن همهٔ ارجاعات `R.*` در Kotlin | ✅ تنها مورد: `MainActivityRefactored.kt → R.drawable.layout_empty` که **داخل کامنت** است و از قبل وجود داشت |
| شناسه‌های تکراری داخل یک layout | ✅ هیچ‌کدام از ۶ چیدمان هدف شناسهٔ تکراری ندارند |
| شناسه‌های الزامی کاربر | ✅ Login: ۹/۹ — Main: ۴۱/۴۱ |
| گم‌شدن شناسه نسبت به HEAD | ✅ هیچ (`activity_login` 10→11، `activity_main` 41→42؛ فقط `dsRegisterRow` و `dsDashboardScroll` اضافه شده‌اند) |
| تغییر نوع کلاس View برای شناسه‌های موجود | ✅ هیچ (`btnLogin` هنوز `GoldButton`، `tvTodaySummaryTitle` هنوز `TextView`، `imgHeaderDashboardIcon` هنوز `ImageView`) |
| تفاوت attributeهای حساس (`hint/inputType/endIconMode/clickable/focusable/visibility/layout_gravity`) | ✅ فقط `txtLiveCount.maxLines: None→2` (جلوگیری از بریدگی متن؛ متن توسط کد ست می‌شود) |
| click targetها | ✅ همهٔ ۱۶ کارت منو `clickable/focusable=true` صریح، دکمه‌های هشدار MaterialButton، `tvTodaySummaryTitle` clickable، `layoutLateClassAlert` clickable، `btnParentPortal/btnStudentPortal/btnLogin/btnIpSettings/tvRegisterLink` موجود |
| attributeهای جدید `android:*` | `autofillHints`, `drawableEnd`, `drawableTint`, `importantForAccessibility`, `paddingStart/End`, `textDirection`, `importantForAutofill` — همه استاندارد (minSdk=24 سازگار) |
| attributeهای جدید `app:*` | `layout_columnSpan`, `layout_constraintVertical_bias`, `rippleColor`, `startIconContentDescription`, `endIconContentDescription`, `errorText`, `errorEnabled` — همه در Material 1.12 پشتیبانی می‌شوند |

## ۸) آنچه اجرا نشد (صریح)

- `:app:assembleDebug` / `:app:test` / `:app:lint` → **اجرا نشد** (بخش ۲).
- تست روی emulator/دستگاه (باز شدن Login، لمس دکمه‌ها، rotation) → **امکان‌پذیر نبود** (نه SDK، نه emulator، نه شبکه).
- هیچ endpoint/درخواست جدیدی اضافه نشد و هیچ business rule تغییر نکرد (diff فقط XML/values + یک attribute Manifest).


> **نکته مهم دربارهٔ تم:** `AndroidManifest` تم برنامه را `@style/Theme.GajAdmin` (پایه روشن) نگه داشته و
> `LoginActivity` هم در زمان اجرا همان را ست می‌کند. به همین دلیل **همهٔ رنگ‌های سطح/متن/مرز در چیدمان‌های
> جدید به‌صورت توکن صریح (نه `?attr/`) نوشته شده‌اند** تا ظاهر تیره‌ـ‌طلایی مستقل از تم پایه درست رندر شود.
> تم دست‌نخورده باقی ماند (الزام «theme فعلی را فقط به‌اندازهٔ compile تغییر بده»).

## ۹) پیشنهاد برای ادامهٔ فازبندی

- **فاز ۲ (پیشنهاد):** صفحه‌های آموزش/شهریه (لیست اقساط، صورتحساب، پرداخت) روی همین توکن‌ها — کارت‌های مالی با پیل بدهی/اعتبار و متن، نه فقط رنگ.
- **فاز ۳ (پیشنهاد):** پرسنل/معلمان و حضور و غیاب + صفحه‌های Settings/Dialog‌ها.
- **پیش‌نیاز اجرایی:** افزودن `res/font/vazirmatn_regular.ttf` به ریپو تا پروژه در هر محیطی قابل build شود؛ سپس اجرای واقعی `assembleDebug/test/lint` و بررسی بصری روی emulator.
