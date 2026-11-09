# گروه ۱ — سه باگ بلاکر: ۴۰۹ پایان کلاس زنده · شهریهٔ صفر · کلاس رد‌شده در صف تأیید

- **تاریخ:** ۲۰۲۶-۰۹-۲۲ · **Branch:** `arena/01a0c867-kharazmiapp` · **زبان:** فارسی
- **Base HEAD:** `c394baa` (راستی‌آزمایی برنچ + CI سبز) · **Tip بعد از این گروه:** `8a603c3`
- **کامیت‌ها:** `e9e61ac` (آیتم ۱) · `c1148fd` (آیتم ۲) · `8a603c3` (آیتم ۳)
- **وضعیت:** هر سه مورد با تست قرمز بازتولید، با فیکس حداقلی سبز شد · **سوئیت کامل ۱۰۸۸ passed** · CI ✅
- **صاحب پروژه تست دستی کامل کرده بود**؛ این گروه همان سه بلاکر گزارش‌شده است.

---

## ۱) راستی‌آزمایی‌های پیش از شروع (چهار مرحلهٔ درخواستی)

| مرحله | نتیجه |
|---|---|
| ساختار `Kharazmi_Server` | ✅ کامل: `main.py` · `models.py` · `schemas.py` · `dependencies.py` · `financial_calculations.py` · `today_summary.py` · `portal_data.py` · `push_service.py` · `storage.py` · `validation.py` · **۲۵ router** · **۶۶ فایل تست در `tests/`** · ۱۱ اسکریپت در `scripts/` |
| ساختار `KharazmiAdmin/app/src` | ✅ کامل: ۷۴ فایل Kotlin در `main/java/…` (+ پوشهٔ `ui`) · `res/layout` ۹۶ · `drawable` ۷۱ · `color` ۱۶ · `anim` ۱۳ · `values` ۶ · `font` ۲ · `androidTest` و `test` موجود |
| خواندن چک‌پوینت‌های آخر | ✅ `2026-09-21-teacher-enrollment-and-layout-crash-fixes.md` · `tests-directory-reorg.md` · `portal-real-activity.md` · `consolidated-report-and-stability-plan.md` · `final-report.md` · `final-phase-report.md` + `README.md` |
| **md5 مبنای `gaj_db.db`** | **`f048f8d118b33c4eaa944490594121d7`** — قبل از کار، بعد از هر سه کامیت و بعد از سوئیت کامل **یکسان** (دست‌نخورده ✅) |

قواعد رعایت‌شده در این گروه: `edit_file` سریال (یکی‌یکی) · تست فقط روی DB موقت `/tmp` و کپی `/tmp/impchk_g1` ·
بعد از تغییر چندفایلی `ast.parse` + `import main` واقعی روی کپی · **اندروید کامپایل نشد** (فقط اعتبارسنجی ایستا:
XML well-formed، بدون کلید string تکراری، وجود هر `R.string.*` استفاده‌شده) · هر مورد = قرمز → فیکس → سبز → سوئیت کامل → کامیت جدا.

---

## ۲) آیتم ۱ — خطای ۴۰۹ روی «پایان کلاس زنده»

### ریشه (قبل از هر فیکسی، با تست قرمز گرفته شد)
خروجی واقعی تست:
```
AssertionError: 409 == 409 : پایان کلاس زنده نباید ۴۰۹ بدهد:
{"detail":"جلسه این کلاس در این تاریخ قبلاً ثبت شده است"}
```
زنجیرهٔ فراخوانی: `POST /attendance/{id}/end_live` → `finalize_live_session` →
`submit_session_and_calculate` → گارد یکتایی `(course_id, date)` در `attendance.py:477` ⇒ **۴۰۹**.

**پاسخ صریح به سؤال صاحب پروژه:** خیر — این مسیر به قفل optimistic-lock پروفایل گیر **نکرده** است.
آن قفل‌ها در `teachers.py:478` و `students.py:805` هستند و فقط `PUT` پروفایل را می‌گیرند
(«تغییر هم‌زمان… صفحه را رفرش کنید»). ۴۰۹ اینجا **گارد «جلسهٔ تکراری در این تاریخ»** است.

### چطور در عمل رخ می‌داد
۱) معلم کلاس زنده را شروع می‌کند (`start_live`) · ۲) همان روز جلسه از مسیر دستی
(`AttendanceActivity` → `submit_session`) یا از کلاس زندهٔ دیگری که زودتر بسته شده ثبت می‌شود ·
۳) پایان کلاس زنده ⇒ ۴۰۹. **عوارض جانبی:** `end_live` استثنا را re-raise می‌کرد و وضعیت را به
`LIVE` برمی‌گرداند ⇒ جلسهٔ زنده در تایمر/لیست «کلاس زنده» معلم گیر می‌کرد و ورکر `auto-end`
هر ۶۰ ثانیه `claim → ۴۰۹ → rollback → LIVE` را تکرار می‌کرد (دقیقاً همان الگویی که F-C9 برای کلاس معلق حل کرد).

### فیکس حداقلی
| مورد | قبل | بعد |
|---|---|---|
| تشخیص | ۴۰۹ خام از submit | استثنای صریح `DuplicateSessionDate` + pre-check در `finalize` |
| مقایسهٔ تاریخ | `date_str` **میلادی** در برابر `SessionLog.date` **شمسیِ کانونیکال** ⇒ هرگز نمی‌خورد | نرمال‌سازی با همان مبدل مرکزی (`parse_project_date`/`jalali_date_string`) مثل submit |
| وضعیت جلسهٔ زنده | `LIVE` (گیرکرده) | `ENDED` + `end_time` |
| اثر مالی | — | **صفر**: هیچ SessionLog/تراکنش/شارژ دومی ساخته نمی‌شود؛ جلسهٔ موجود دست‌نخورده |
| پاسخ API | ۴۰۹ | ۲۰۰ با کلیدهای قبلی **به‌علاوهٔ** `duplicate_date` · `existing_session_id` · `existing_session_code` · `duplicate_date_str` (افزودنی ⇒ قرارداد نشکست) |
| ورکر auto-end | لوپ ۶۰ ثانیه‌ای | مستقیم `ENDED` با `ended_automatically=True` (هم‌الگو با F-C9) |
| اندروید | `Toast` «سهم معلم: ۰» (گمراه‌کننده) یا خطای خام | نمایش پیام سرور با `R.string.lcls_duplicate_msg` + فیلدهای اختیاریِ دارای پیش‌فرض در `LiveEndResponse` |

---

## ۳) آیتم ۲ — شهریهٔ پایه = ۰ در افزودن دانش‌آموز

### ریشه
`EnrollmentCreate.total_tuition = Field(gt=0)` (schemas.py:102) ⇒ ۴۲۲ با بدنهٔ خام pydantic:
```
{"detail":[{"type":"greater_than","loc":["body","total_tuition"],
            "msg":"Input should be greater than 0","input":0,"ctx":{"gt":0}}]}
```
یعنی دقیقاً همان «خطای عمومی» که صاحب پروژه گزارش کرد. **شاهد ناسازگاری داخلی:** مسیر
`register_and_enroll` (schemas.py:401) همین مقدار را `Optional[int] = 0` می‌پذیرد ⇒ دو مسیر
«افزودن دانش‌آموز» رفتار متفاوت داشتند.

### فیکس
| مورد | قبل | بعد |
|---|---|---|
| شهریهٔ ۰ (رایگان/معاف) | ۴۲۲ خام | **۲۰۰** + ردیف `Enrollment(total_tuition=0, total_paid=0)` |
| شهریهٔ منفی | ۴۲۲ خام انگلیسی | ۴۲۲ با پیام فارسی: «شهریهٔ ثبت‌نام نمی‌تواند منفی باشد؛ برای دانش‌آموز رایگان یا معاف عدد ۰ را وارد کنید» |
| محل پیام | `Field(gt=0)` | `field_validator(mode="before")` — عمداً before، چون محدودیت روی Field اول اجرا می‌شد و پیام فارسی هرگز دیده نمی‌شد |
| اثر مالی | — | **بدون تغییر**: پرداخت اولیهٔ صفر ⇒ هیچ تراکنشی ساخته نمی‌شود، کیف‌ها دست‌نخورده |
| تخفیف ثابت روی شهریهٔ صفر | ۴۰۰ | ۴۰۰ (بدون تغییر — `d_val > total_tuition`) |
| مسیر معلم (O-22) | ۴۲۲ | ۲۰۰ برای کلاس خودش |

`test_tuition_installments_audit.py::test_s06a` (`paid_amount=-1` ⇒ ValidationError) **سبز ماند**.

---

## ۴) آیتم ۳ — کلاس رد‌شده در «کلاس‌های منتظر تأیید» می‌ماند

### ریشه
`DELETE /admin/reject_class/{id}` کلاس را آرشیو می‌کند (`_apply_class_deletion` ⇒ `is_deleted=True`،
classes.py:988) ولی `is_admin_approved` را `False` می‌گذارد؛ `GET /admin/pending_classes`
(admin.py:614) **فقط** `is_admin_approved == False` را فیلتر می‌کرد ⇒ ردیف آرشیوشده در صف می‌ماند.
**شاهد ناسازگاری داخلی:** نمای معلم (`teachers.py:321` → `incomplete_classes`) فیلتر
`is_deleted == False` را از قبل داشت. **بدتر:** `POST /admin/approve_class` روی کلاس آرشیوشده
۲۰۰ می‌داد ⇒ وضعیت ناسازگار «آرشیو + تأییدشده».

### فیکس (دو فیلتر، صفر تغییر در منطق مالی/حذف)
| کوئری | قبل | بعد |
|---|---|---|
| `GET /admin/pending_classes` (ادمین/منشی/معلم) | `is_admin_approved == False` | `+ is_deleted == False` |
| `POST /admin/approve_class/{id}` | کلاس آرشیوشده ⇒ ۲۰۰ | ⇒ **۴۰۴** (هم‌سیاست H10، هم‌سبک `reject_class` همسایه) |
| `GET /teachers/{id}/incomplete_classes` | از قبل درست | بدون تغییر |

`reject_class` دست‌نخورده ماند (idempotent بود و رکورد حسابرسی تکراری نمی‌سازد — با تست قفل شد).

---

## ۵) تست — چرخهٔ قرمز → سبز

فایل جدید: **`Kharazmi_Server/tests/test_group1_blockers.py`** (۳۳۷ سطر · ۱۱ تست) — دنیای درون‌حافظه‌ای:
شعبه ۱ · ادمین · منشی · معلم مالک · ۲ دانش‌آموز · ردیف `InstituteShare` · سه سشن توکن‌دار.

| # | سناریو | قبل از فیکس | بعد |
|---|---|---|---|
| 1a | شروع → پایان کلاس زنده (مسیر سالم): یک SessionLog + شارژ کیف | ✅ | ✅ (رگرسیون‌گیری) |
| 1b | جلسهٔ امروز قبلاً ثبت شده ⇒ پایان کلاس زنده | ❌ `409 == 409` | ✅ ۲۰۰ + `duplicate_date` + `ENDED` + صفر تراکنش دوم |
| 1c | پایانِ دوباره روی جلسهٔ بسته‌شده | ❌ | ✅ ۴۰۰ «از قبل بسته شده» |
| 2a | شهریهٔ ۰ ⇒ ثبت‌نام رایگان/معاف | ❌ ۴۲۲ خام | ✅ ۲۰۰ + `total_tuition=0` + صفر تراکنش |
| 2b | تخفیف ثابت روی شهریهٔ ۰ | ❌ | ✅ ۴۰۰ با پیام «تخفیف» |
| 2c | شهریهٔ منفی ⇒ پیام فارسی (نه `greater than`) | ❌ | ✅ |
| 2d | معلم، دانش‌آموز رایگان در کلاس خودش | ❌ | ✅ |
| 3a | رد کلاس ⇒ خروج از صف ادمین (و ماندن کلاس در انتظار دیگر) | ❌ `2 in [1, 2]` | ✅ |
| 3b | خروج از صف منشی + صف خود معلم + `incomplete_classes` | ❌ | ✅ |
| 3c | تأیید کلاس رد‌شده ⇒ رد (۴۰۴/۴۱۰) و آرشیو ماندن | ❌ ۲۰۰ «تایید شد» | ✅ ۴۰۴ |
| 3d | `reject` دوباره ⇒ idempotent + یک رکورد حسابرسی | ❌ | ✅ |

| مرحله | نتیجه |
|---|---|
| **قرمز** (قبل از فیکس) | `10 failed, 1 passed` — هر سه ریشه با پیام واقعی گزارش‌شده |
| **سبز** (بعد از فیکس) | `11 passed` (۳.۱s) |
| **سوئیت کامل** | **1088 passed** (۱۰۷۷ قبلی + ۱۱ جدید) در ۱۱۲s · `49 warnings` (همه از قبل: `PydanticDeprecatedSince20`) |
| CI (GitHub Actions) روی `8a603c3` | ✅ success — هر سه step: سوئیت از ریشه · گارد cwd-independence (B1) · گارد دست‌نخوردن DB |
| `ast.parse` روی ۴ فایل تغییریافتهٔ سرور | ✅ |
| `import main` واقعی روی کپی `/tmp/impchk_g1` | ✅ |
| `md5sum gaj_db.db` قبل/بعد | `f048f8d118b33c4eaa944490594121d7` (دست‌نخورده ✅) |

دستور اجرا:
```bash
DATABASE_URL=sqlite:////tmp/g1.db JWT_SECRET_KEY=test-secret-not-production \
  /home/user/.venv/bin/python -m pytest Kharazmi_Server/tests/test_group1_blockers.py -q -p no:randomly
```

### آمار تغییر
```
 Kharazmi_Server/routers/attendance.py              | +71/-3   (DuplicateSessionDate + pre-check + شاخهٔ end_live)
 Kharazmi_Server/main.py                            | +18/-1   (شاخهٔ ورکر auto-end)
 Kharazmi_Server/schemas.py                         | +20/-2   (total_tuition: صفر مجاز، منفی با پیام فارسی)
 Kharazmi_Server/routers/admin.py                   | +12/-2   (دو فیلتر is_deleted)
 Kharazmi_Server/tests/test_group1_blockers.py      | +337     (جدید، ۱۱ تست)
 KharazmiAdmin/…/AppModels.kt                       | +9/-1    (۴ فیلد اختیاری با پیش‌فرض)
 KharazmiAdmin/…/LiveClassActivity.kt               | +12      (نمایش پیام سرور)
 KharazmiAdmin/…/res/values/strings.xml             | +3       (lcls_duplicate_msg)
 8 files changed, 476 insertions(+), 6 deletions(-)
```

---

## ۶) چه چیزی تست نشد / محدودیت‌ها

1. **اندروید کامپایل نشد** (Gradle/JDK/SDK در محیط نیست — طبق قانون). تغییرات Kotlin فقط با
   الگوی موجود همان فایل‌ها نوشته شد و ایستا بررسی شد: XMLها well-formed، کلید string تکراری نداریم،
   هر `R.string.*` استفاده‌شده در `LiveClassActivity` وجود دارد. تأیید نهایی روی دستگاه صاحب پروژه.
2. رفتار ۴۰۹ در **کلاینت منتشرشدهٔ قدیمی** (بدون فیلدهای جدید): همچنان ۲۰۰ می‌گیرد و چون
   `details == null` است، `Toast` «سهم معلم: ۰» نشان می‌داد ⇒ با تغییر Kotlin همین پیام جایگزین شد؛
   برای build قدیمی هیچ کرشی رخ نمی‌دهد (فیلدها اختیاری‌اند).
3. `duplicate_date` فقط زمانی بسته می‌شود که SessionLog **فعال** (غیر آرشیو) در همان تاریخ باشد؛
   اگر جلسهٔ آن تاریخ قبلاً حذف نرم شده باشد، مسیر عادی finalize ثبت می‌کند (سیاست موجود دست‌نخورده).
4. هیچ نوشتنی روی DB واقعی آموزشگاه انجام نشد؛ همه‌چیز روی DB موقت و کپی `/tmp`.

## ۷) قدم بعدی

**گروه ۲ — اعداد و گزارش‌های غلط** (آیتم‌های ۴ تا ۹): یکدست‌سازی «وضعیت امروز» با
`today_summary.py` (همان تابع O-08) · گزارش مالی معلم · خروجی بدهکاران · فیلتر لیست معلم‌ها در
گزارش‌گیری · نام کلاس/شعبه در تاریخچهٔ تغییرات مالی (+ پیشنهادها) · گزارش بدهکاران داشبورد
(+ پیشنهادها: گروه‌بندی بر اساس معلم، دسته‌بندی قدمت بدهی، پیامک دسته‌جمعی از موتور موجود،
خروجی اکسل با شماره تماس). هر مورد با همان چرخهٔ قرمز → سبز و کامیت جدا.
