# تسک جدید — رفع کرش «Chip does not support multi-line text» در صفحهٔ مدیریت کلاس‌ها

- **تاریخ:** ۲۰۲۶-۰۹-۲۹ · **Branch:** `arena/01a0ec4f-kharazmiapp` (شاخهٔ کاری جدید این نشست) · **زبان:** فارسی
- **Base HEAD:** `2bb1c48` (fix: allow Persian action labels to wrap) · **کامیت فیکس:** `58ce896`
- **وضعیت:** فیکس شد + گارد ایستا اضافه شد + کل سوئیت سبز + CI سبز (`36544939571`). کامپایل اندروید در این محیط ممکن نیست ⇒ تأیید نهایی روی دستگاه کاربر.

---

## ۱) گزارش باگ (لاگ ارسالی کاربر)

```
java.lang.UnsupportedOperationException: Chip does not support multi-line text
    at com.google.android.material.chip.Chip.setMaxLines(Chip.java:699)
    at android.widget.TextView.<init>(TextView.java:1390)
    at android.widget.CheckBox.<init>(CheckBox.java:71)
    at com.google.android.material.chip.Chip.<init>(Chip.java:207)
  ⇒ android.view.InflateException: Binary XML file line #123 in
     com.example.kharazmiadmin:layout/item_class_row
    at ClassManagementActivity$ClassAdapter.onCreateViewHolder(ClassManagementActivity.kt:244)
```

یعنی هنگام ساخت هر آیتم لیست در صفحهٔ **«مدیریت کلاس‌ها»**، inflate فایل `item_class_row.xml` می‌ترکید و صفحه کرش می‌کرد.

## ۲) ریشهٔ دقیق (پس از خواندن کد)

| حلقهٔ زنجیره | فایل / مورد |
|---|---|
| چیپ‌های سه‌گانهٔ ردیف کلاس (`chipGradeLevel` / `chipGender` / `chipSessionCount`) | `res/layout/item_class_row.xml:116،125،134` |
| هر سه با `style="@style/GajChipStyle"` | `res/values/themes.xml:182` و `res/values-night/themes.xml:163` |
| خودِ `GajChipStyle` دو مورد چندخطی داشت | `<item name="android:singleLine">false</item>` و `<item name="android:maxLines">2</item>` |
| منطق خودِ Chip | Chip این چهار متد را قفل کرده: `setSingleLine(false)` · `setLines(>1)` · `setMinLines(>1)` · `setMaxLines(>1)` ⇒ `UnsupportedOperationException` از داخل سازندهٔ `TextView` (چون Chip از `CheckBox`/`Button` ارث می‌برد) |

⇒ مقدار چندخطی از **زنجیرهٔ style** به سازندهٔ Chip می‌رسد و inflate همان لحظه می‌ترکد.
**مهم:** `aapt2` این را خطای build نمی‌بیند (خطای زمان اجراست)، پس هیچ build/CI ای آن را نمی‌گیرد.

### دو مورد مشابه که پیدا شد ولی کاربر هنوز به آن‌ها نخورده بود (کرش نهفته)
| استایل چیپ | مصرف‌کننده | وضعیت قبل |
|---|---|---|
| `Widget.Kharazmi.DS.Chip` (`values/ds_styles.xml:240`) | `activity_design_system.xml` (۴ چیپ) | همان `singleLine=false` + `maxLines=2` ⇒ با باز شدن صفحهٔ Design System هم کرش می‌کرد |
| `Widget.Kharazmi.DS.Chip.Tag` (`values/ds_styles.xml:256`) | همان فایل | همان مشکل |

### چه چیزی *مشکل نبود* (و عمداً دست‌نخورده ماند)
- استایل‌های **دکمهٔ** Material (`Widget.Kharazmi.Button*`) که `maxLines=2` دارند — دکمه چندخطی را پشتیبانی می‌کند و این همان درخواست قبلی کاربر است («برچسب‌های فارسی بشکنند»). **هیچ تغییری نکرد.**
- `android:maxLines` داخل `TextAppearance.Kharazmi.DS.Money / KpiValue` — یک آیتم بی‌اثر است (styleable مربوط به TextAppearance این attribute را نمی‌خواند). فعلاً رها شد؛ بی‌خطر.
- هیچ کدی در Kotlin مقدار `maxLines`/`singleLine` روی چیپ ست نمی‌کند (grep کامل: صفر مورد) ⇒ ریشه صرفاً XML بود.

## ۳) فیکس انجام‌شده (حداقلی — فقط attribute، بدون تغییر ساختار/منطق)

| فایل | تغییر |
|---|---|
| `res/values/themes.xml` (خط ~۱۸۹) | `GajChipStyle`: حذف `singleLine=false` و `maxLines=2` ⇒ جایش `<item name="android:singleLine">true</item>` و `<item name="android:maxLines">1</item>` + کامنت توضیحی |
| `res/values-night/themes.xml` (خط ~۱۷۰) | همان تغییر برای حالت شب (چون `values-night` تعریف جدا دارد و کرش در شب هم رخ می‌داد) |
| `res/values/ds_styles.xml` (خطوط ~۲۴۸ و ~۲۶۵) | همان تغییر برای `Widget.Kharazmi.DS.Chip` و `Widget.Kharazmi.DS.Chip.Tag` (رفع کرش نهفتهٔ صفحهٔ Design System) |

**دست‌نخورده‌ها:** تمام layoutها، تمام Kotlin، رنگ/گردی گوشه/پدینگ/`minHeight`/هدف لمسی چیپ‌ها، استایل دکمه‌ها، ترتیب attributeها، تِم‌ها. مقدار جدید صریحاً همان پیش‌فرض کتابخانهٔ Material است (تک‌خطی)، پس **ظاهر چیپ‌ها عوض نمی‌شود** — فقط دیگر کرش نمی‌کند.

> نکتهٔ طراحی: چیپ‌های این اپ متن‌های کوتاه دارند (پایه دهم / ۱۲ جلسه / …). اگر روزی متن بلند لازم شد، راه درست `TextView` با پس‌زمینهٔ pill است، نه `Chip` (Chip ذاتاً تک‌خطی است).

## ۴) گارد جدید (تست قرمز → سبز)

فایل: `Kharazmi_Server/tests/test_android_resources_static.py` (گارد ۵ به هدر فایل هم اضافه شد)

اسکنر namespace-aware است و **زنجیرهٔ style + مقدارهای سطح تِم** را برای هر `Chip` در هر layout (هم `values` و هم `values-night`) تا ته دنبال می‌کند:

| تست | چه چیزی را قفل می‌کند |
|---|---|
| `test_5a_no_layout_chip_resolves_to_multi_line_text` | هیچ Chip ای در هیچ layout ای (مستقیم یا از طریق style/theme) چندخطی نباشد |
| `test_5b_reported_crash_file_still_has_chips_and_is_scanned` | فایلِ گزارش‌شدهٔ کاربر (`item_class_row.xml`) واقعاً ۳ چیپ دارد و اسکن می‌شود (گارد بی‌اثر/کهنه نشود) |
| `test_5c_theme_level_chip_attributes_are_safe` | در سطح `Theme.*` هیچ `maxLines/minLines/lines/singleLine=false` نباشد (این‌ها به همهٔ TextViewها از جمله Chip می‌رسند) |
| `test_5d_chip_styles_are_explicitly_single_line` | سه استایل چیپ صریحاً `singleLine=true` و `maxLines=1` داشته باشند (وابسته به پیش‌فرض کتابخانه نمانیم) |

**خروجی قرمز (قبل از فیکس):** `2 failed, 2 passed` — و دقیقاً همان چیزی که کاربر دیده بود بازتولید شد:
```
KharazmiAdmin/.../layout/item_class_row.xml:112 «chipGradeLevel» → android:singleLine=false از style «GajChipStyle» (values/themes.xml:182)
KharazmiAdmin/.../layout/item_class_row.xml:112 «chipGradeLevel» → android:maxLines=2       از style «GajChipStyle» (values/themes.xml:182)
… (همین برای chipGender و chipSessionCount — و در values-night هم همین‌ها)
KharazmiAdmin/.../layout/activity_design_system.xml:810/818/825/832 → از style «Widget.Kharazmi.DS.Chip(.Tag)»
```
**خروجی سبز (بعد از فیکس):** `10 passed`

## ۵) اعتبارسنجی

| بررسی | نتیجه |
|---|---|
| سوئیت کامل (قبل) | ۱۱۹۹ تست |
| سوئیت کامل (بعد) | **۱۲۰۳ passed** (۱۱۹۹ + ۴ گارد جدید) · ۱۳۳ ثانیه |
| `md5sum Kharazmi_Server/gaj_db.db` قبل/بعد | `f048f8d118b33c4eaa944490594121d7` — دست‌نخورده ✅ (قانون پروژه) |
| XML سالم در کل `res/` | ۲۱۵ فایل، **۰ فایل خراب** |
| باقی‌ماندهٔ attribute چندخطی روی چیپ در `res/` | **۰** (بقیهٔ موارد فقط روی دکمه/TextAppearance هستند و مشکل‌ساز نیستند) |
| تغییر در Kotlin / layout | **صفر** |
| CI | شاخهٔ `arena/01a0ec4f-kharazmiapp` به تریگر `push` در `.github/workflows/tests.yml` اضافه شد ⇒ رانِ `36544939571` **سبز** (https://github.com/eternity-lord/KharazmiApp/actions/runs/36544939571) |

دستور اجرای تست (مستند پروژه):
```bash
cd /home/user/KharazmiApp
env -u PYTHONPATH DATABASE_URL=sqlite:////tmp/<n>.db JWT_SECRET_KEY=<hex> \
  /home/user/.venv/bin/python -m pytest Kharazmi_Server/tests -q
```
> در این محیط `pytest` نصب نبود؛ یک venv موقت در `/home/user/.venv` ساخته و
> `Kharazmi_Server/requirements.txt` + `pytest` در آن نصب شد (خارج از ریپو، در snapshot نمی‌آید).

## ۶) چه چیزی تست نشده (محدودیت‌ها)
1. **کامپایل/اجرای اندروید انجام نشد** (Gradle/JDK/Android SDK در این محیط نیست) ⇒ تأیید نهایی نصب روی دستگاه کاربر.
2. تست‌ها ایستا هستند: مطابقت با کد واقعی Material فرض شده (`Chip` چهار متد بالا را قفل می‌کند) — همان چیزی که خودِ stacktrace کاربر تأیید می‌کند.
3. کرش در حالت شب (`values-night`) هم فیکس شد ولی روی دستگاه در دارک‌مود هم باید دیده شود.

## ۷) قدم بعدی
کاربر: صفحهٔ «مدیریت کلاس‌ها» را باز کنید (هم حالت روشن، هم دارک) — باید بدون کرش لیست کلاس‌ها با چیپ‌های «پایه/جلسه» نمایش داده شود. سپس صفحهٔ Design System (چیپ‌ها) هم چک شود.
