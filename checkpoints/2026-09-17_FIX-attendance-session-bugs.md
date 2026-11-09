# FIX F-S1 + F-S3 + F-S4 + F-S2 — چهار باگ ثبت جلسه/حضور-غیاب (۲۰۲۶-۰۹-۱۷)

برنچ: `arena/01a0aac2-kharazmiapp` | ریپو: `eternity-lord/KharazmiApp`
پیش‌نیاز: ممیزی `checkpoints/2026-09-17_ATTENDANCE-SESSIONS-audit.md` (کامیت `46e8e00`) که این چهار باگ را
با تست‌های failing بازتولید کرده بود (فایل `Kharazmi_Server/test_attendance_sessions_audit.py`).

## ۰) محیط
سندباکس این تسک سالم بود: `HEAD=46e8e00` مطابق ریموت، درخت تمیز، وابستگی‌ها نصب، `.env` سندباکس موجود
(`DATABASE_URL=sqlite:////tmp/attendance_audit.db`, `PAYMENT_GATEWAY_ENABLED=false`, gitignored).
هیچ تست/سروری روی `Kharazmi_Server/gaj_db.db` اجرا نشد؛ همه‌ی اجراها روی کپی‌های `/tmp`.

## ۱) baseline (قبل از هر تغییر)
| دستور | نتیجه |
|---|---|
| `python -m compileall Kharazmi_Server` | exit 0 |
| `pytest -q Kharazmi_Server/test_attendance_sessions_audit.py` | **59 passed / 8 failed** (7.13s) |
| `pytest -q Kharazmi_Server` | **558 passed / 8 failed** (51.15s) |

۸ شکست = دقیقاً چهار یافته (F-S1، F-S2، F-S3 و F-S4 با ۵ پارامتر ورودی).

### خروجی failing-first هر یافته (قبل از fix)
- **F-S1:** `F-S1: جلسه با دانش‌آموز حذف‌شده نباید هیچ نوشتنی داشته باشد؛ attendee_count=1 final_teacher_cost=60 attendance_rows=0 charge_rows=0`
- **F-S2:** `F-S2: با حذف جلسه، سابقه‌ی حضور فیزیکی پاک شد (ردیف‌های باقی‌مانده: 0) و هیچ فلگ آرشیوی هم وجود ندارد`
- **F-S3:** `assert 1 == 0` روی `COUNT(SessionLog)` (درخواست `items=[]` جلسه ساخت) و سپس `409` برای ثبت واقعی همان (کلاس، تاریخ)
- **F-S4:** `DID NOT RAISE HTTPException` برای ۵ ورودی نامعتبر (`banana`، `present`، `PRESENT`، `حاضر`، خالی)

## ۲) یافته‌ها و علت ریشه‌ای
| ID | Sev | محل | علت ریشه‌ای |
|---|---|---|---|
| F-S1 | High | `attendance.py:423,449-459,496-498` (+ مسیر ویرایش `863/913`)؛ `dependencies.py:395` | فقط «معلق» چک می‌شد؛ دانش‌آموز آرشیوشده در شمارش حاضرین/سهم‌ها حاضر حساب می‌شد ولی حلقه‌ی شارژ ردش می‌کرد ⇒ SessionLog با هزینه‌ی معلم بدون وصول |
| F-S2 | Medium | `dependencies.py:359`؛ کالرها `attendance.py:887,1040` | `reverse_session_financial_impacts` ردیف‌های `attendances` را **فیزیکی** حذف می‌کرد (خلاف الگوی نرم بقیه‌ی حذف‌های پروژه) |
| F-S3 | Medium | `schemas.py:141`؛ `attendance.py:406,449` | `items=[]` مجاز بود ⇒ SessionLog خالی ساخته می‌شد و (کلاس، تاریخ) برای ثبت واقعیِ بعدی قفل می‌شد (۴۰۹) |
| F-S4 | Medium | `schemas.py:135`؛ `attendance.py:508-516` | وضعیت آزاد بود؛ مقدار ناشناخته بی‌صدا ذخیره می‌شد و `should_charge=False` ⇒ درآمد جلسه صفر، بدون هیچ خطا |
| O-S1 | Low | `teachers.py:805-810` | پیام «قبلاً تسویه شده است» برای جلسه‌ی بدون فعالیت (رفتار درست، پیام گمراه‌کننده) — خارج از scope fix، فقط تست پوشش |
| **O-S2** | **High** | `attendance.py:796` | **کشف حین fix:** سطر مرده‌ی `present_count.float()` در `get_student_attendance_history` همیشه `AttributeError` می‌داد ⇒ هر کلاس با ≥۱ جلسه این endpoint را **۵۰۰** می‌کرد (سطر بعدی همان محاسبه‌ی درست را داشت) |

## ۳) راه‌حل اعمال‌شده (۱۴ فایل، +۶۰۳/−۱۰۶ خط)

### F-S1 — رد دانش‌آموز آرشیوشده، قبل از هر نوشتنی
- `dependencies.validate_session_items_membership`: بلوک جدید «archived» **دقیقاً هم‌الگو با بلوک معلق**:
  `Student.is_deleted == True` ⇒ `HTTPException(422, "این دانش‌آموزان حذف/آرشیو شده‌اند و نمی‌توانند در جلسه ثبت شوند: [...]")`.
  محل: بعد از چک عضویت و معلق بودن، **قبل از** هر `db.add`؛ پس هر دو مسیر `submit` و `edit` پوشش داده می‌شوند.
- مسیر جایگزین QR (`qr_student_check_in`): چک `own.is_deleted` ⇒ ۴۰۳ + محدودکردن عضویت به `Enrollment.is_deleted == False`
  (پیش‌تر ثبت‌نام آرشیوشده هم کافی بود).
- مسیر کلاس زنده (`finalize_live_session`): راستر UI ممکن است شاگرد آرشیوشده/معلق/غیرعضو داشته باشد؛
  به‌جای شکست کل بستن جلسه، ردیف نامواجد **فیلتر** می‌شود (هیچ ردیفی از او نوشته نمی‌شود) و `skipped_student_ids`
  در پاسخ برمی‌گردد. اصولاً هیچ مسیری با `student_id` آرشیوشده جلسه‌ی مالی نمی‌سازد.

### F-S3 — جلسه‌ی بی‌محتوا ممنوع
- `schemas.AttendanceSubmitData.items: List[AttendanceItem] = Field(min_length=1)` ⇒ مرز HTTP پاسخ ۴۲۲ pydantic
  (سازگار با سیاست پروژه برای ورودی نامعتبر: تاریخ بد/غیرعضو هم ۴۲۲).
- گارد داخل `submit_session_and_calculate` و `edit_past_session` برای فراخوان مستقیم تابعی (`if not data.items: 422`),
  **قبل از** ساخت `SessionLog` و گرفتن sequence ⇒ نه ردیف خالی می‌ماند، نه شمارنده مصرف می‌شود.
- **مسیر کلاس زنده (تصمیم آگاهانه):** `finalize_live_session` با راستر خالی، SessionLog نمی‌سازد؛
  کلاس زنده به‌صورت سالم `ENDED` می‌شود و پاسخ `session_id=None` + `skipped_student_ids` می‌دهد.
  این با سیاست جدید «جلسه‌ی بی‌ردیف = قفل‌نشدن تاریخ» هم‌راستاست و مسیر ثبت دستی بعدی همان تاریخ را نمی‌بندد.
  (گزینه‌ی جایگزین — حفظ رفتار قبلی F-C6(a) و ساخت SessionLog با صفر حاضر برای کلاس زنده — مستثناکردن صریح
  مسیر سیستمی لازم داشت؛ در بخش ۹ به‌عنوان گزینه‌ی قابل بازگشت ثبت شده است.)

### F-S4 — یک قرارداد واحد برای وضعیت حضور
- `validation.validate_attendance_status` + ثابت `ATTENDANCE_STATUSES = ("Present", "Late", "Absent")`:
  مقادیر از کلاینت رسمی استخراج شد (`AttendanceActivity.kt:449,487,845-847`, `LiveClassActivity.kt:284-297`,
  `LiveApi.kt:53`) و با همه‌ی فیلترهای سرور (`is_billed`, جریمه‌ی غیبت، گزارش‌ها) یکی است.
  **normalize انجام نمی‌شود** چون هیچ نسخه‌ی کوچک‌نویس/فارسی در قرارداد وجود ندارد؛ ورودی دیگر رد می‌شود.
- `schemas.AttendanceItem`: `@field_validator("status")` ⇒ ۴۲۲ در مرز HTTP.
- `dependencies.validate_session_item_statuses` (اعتبارسنج مرکزی) در `submit` و `edit` قبل از هر نوشتن ⇒ ۴۲۲
  برای فراخوان‌های مستقیم/داخلی.
- `save_live_status`: وضعیت نامعتبر وارد راستر نمی‌شود ⇒ ۴۲۲ (پیش‌تر بی‌صدا ذخیره و در finalize نادیده/خطا می‌شد).
- `finalize_live_session`: وضعیت غیرمجازِ نهفته در راستر legacy باعث ۵۰۰ نمی‌شود؛ ردیف skip و در `skipped_student_ids` گزارش می‌شود.

### F-S2 — آرشیو نرم ردیف حضور (به‌جای حذف فیزیکی)
- `models.Attendance.is_deleted = Column(Boolean, default=False, server_default=text("FALSE"), nullable=False)`.
  قید یکتای `uq_attendance_session_student` **partial نشد**: ردیف آرشیوشده سطرش را نگه می‌دارد و مسیر
  ثبت/ویرایش همان ردیف را **revive** می‌کند (`_upsert_attendance_row`)، پس روی دیتابیس‌های موجود هیچ مایگریشن قید لازم نیست.
- `main.auto_patch_database`: ردیف `("attendances","is_deleted","BOOLEAN DEFAULT FALSE","UPDATE attendances SET is_deleted = FALSE WHERE is_deleted IS NULL;")`
  ⇒ دیتابیس قدیمی خودکار وصله می‌شود و ردیف‌های موجود «فعال» می‌مانند (هیچ سابقه‌ای بی‌دلیل آرشیو نمی‌شود).
- `reverse_session_financial_impacts`: `DELETE` ⇒ `UPDATE attendances SET is_deleted=TRUE` (بدون شرط، پس اجرای دوباره idempotent است).
- فیلتر `is_deleted == False` در همه‌ی مصرف‌کننده‌های فعال:
  `attendance.py` (جزئیات جلسه، تاریخچه‌ی شاگرد، قفل تسویه در ویرایش/حذف، QR)،
  `teachers.py` (تسویه: ۳ نقطه)، `analytics.py` (نرخ حضور + ۴ نقطه)، `classes.py` (۶ نقطه)،
  `ai.py`، `automation.py` (۴ نقطه)، `exams.py`، `today_summary.py` (۲ نقطه).

### O-S2 — رفع کراش ۵۰۰ تاریخچه‌ی شاگرد (کشف حین fix، خارج از چهار یافته اما در همان تابع ویرایش‌شده)
سطر مرده‌ی `rate = (present_count.float() / ...)` حذف شد؛ سطر بعدی همان محاسبه‌ی صحیح را انجام می‌دهد.
این endpoint برای هر کلاس با ≥۱ جلسه ۵۰۰ می‌داد (اثبات با probe روی DB موقت: `AttributeError: 'int' object has no attribute 'float'`).

## ۴) تست‌ها: ۶۷ ⇒ ۸۵ (+۱۸)
| یافته | تست‌های جدید (رگرسیون) |
|---|---|
| F-S1 | `test_s08b_fix_soft_deleted_student_is_rejected_before_any_write`, `test_s08c_fix_active_student_still_succeeds`, `test_s08d_fix_suspended_student_is_rejected_too`, `test_s08e_fix_deleted_student_is_rejected_in_edit_path_too`, `test_s08f_fix_deleted_student_is_rejected_in_qr_path`, `test_s08g_fix_qr_path_still_works_for_active_student_of_today` |
| F-S2 | `test_s19b_fix_attendance_history_is_archived_not_destroyed`, `test_s19d_fix_archived_attendance_is_invisible_to_active_reads_and_settlement`, `test_s19e_fix_new_session_on_the_same_date_still_works_after_soft_delete`, `test_fix_fs4_migration_autopatch_adds_is_deleted_to_legacy_attendances` |
| F-S3 | `test_fix_fs3_empty_attendee_list_is_rejected_and_does_not_lock_the_date`, `test_fix_fs3_edit_cannot_empty_the_session`, `test_fix_fs3_live_session_with_empty_roster_creates_no_session` |
| F-S4 | `test_fix_fs4_invalid_status_is_rejected_without_any_write` (۷ پارامتر), `test_fix_fs4_valid_statuses_are_accepted` (۳), `test_fix_fs4_late_is_charged_exactly_like_present`, `test_fix_fs4_edit_rejects_invalid_status_and_keeps_previous_state` |
| O-S2 | `test_fix_os2_student_history_with_active_sessions_does_not_crash` |

جایگزینی‌شده (تست‌های یافته‌محور که قبلاً عمداً قرمز بودند): `test_s08b_finding_*`، `test_s19b_finding_*`،
`test_s_ext_items_finding_*`، `test_s_ext_status_finding_*` و `test_s24f` (به `test_s24f_legacy_empty_session_has_nothing_to_settle`
تغییر نام یافت چون از F-S3 به بعد جلسه‌ی خالی از API ساخته نمی‌شود و سناریو فقط با ردیف legacy در DB معنا دارد).

## ۵) نتایج نهایی (پس از fix)
| دستور | نتیجه |
|---|---|
| `python -m compileall Kharazmi_Server` | exit 0 |
| `pytest -q Kharazmi_Server/test_attendance_sessions_audit.py -vv` | **85 passed** / 8.90s |
| `pytest -q Kharazmi_Server` | **584 passed / 0 failed** / 9 warnings / 51.76s |
| `pytest -q Kharazmi_Server/test_priority2_financial.py` | **85 passed** / 7.07s |
| `pytest -q ... -k s27` ×۳ اجرای متوالی | هر بار **2 passed** (بدون flake) |
| `import main` (کپی /tmp) | OK — 29 route |

هیچ تستی skip نشد. ۹ warning همه از نوع Deprecation/SAWarning موجود در پروژه است (بی‌ربط به این تغییر).

## ۶) status codeها
| سناریو | کد |
|---|---|
| دانش‌آموز آرشیوشده (ثبت/ویرایش) | ۴۲۲ |
| دانش‌آموز آرشیوشده در QR | ۴۰۳ |
| `items=[]` (submit/edit، مرز HTTP و فراخوان مستقیم) | ۴۲۲ |
| وضعیت نامعتبر (schema و گارد endpoint و `live_status`) | ۴۲۲ |
| تکراری (کلاس، تاریخ) | ۴۰۹ (بدون تغییر) |
| معلق/غیرعضو/تاریخ بد | ۴۲۲ (بدون تغییر) |
| رشد/خطای یکتایی backstop | ۴۰۹ (بدون تغییر) |
| QR: حضور قبلاً ثبت‌شده | ۴۰۰ (بدون تغییر) |
| کراش قبلی تاریخچه‌ی شاگرد | ۵۰۰ ⇒ حالا ۲۰۰ |

## ۷) مایگریشن + idempotency (اثبات عملی)
علاوه بر تست واحد (ساخت جدول legacy بدون ستون + ردیف نمونه + دو بار `auto_patch_database()` + بررسی
دست‌نخوردگی ردیف و یک‌تایی ستون)، یک اجرای end-to-end هم روی **کپی** DB واقعی انجام شد:
```bash
cp gaj_db.db /tmp/mig_check.db
sqlite3: ALTER TABLE attendances DROP COLUMN is_deleted
DATABASE_URL=sqlite:////tmp/mig_check.db python3 -c "import main; main.auto_patch_database(); main.auto_patch_database()"
→ 🔧 Auto-patching database: Adding 'is_deleted' to 'attendances' table...
→ ستون‌ها بعد از دو بار: [...] , is_deleted  (فقط یک بار)   |   ردیف‌های جعلی/گم‌شده: 0
```
(کپی واقعی صفر ردیف `attendances` دارد؛ حفظ «داده‌ی موجود» توسط همان تست واحد با ردیف legacy پوشش داده شده است.)

## ۸) ایمنی دیتابیس پروداکشن
`sha256sum Kharazmi_Server/gaj_db.db` = `f0e55fe7c5130ec17e39e73036e2291794c3c335f67d852c37599a6c0f99ec79`
— پیش و پس از تمام اجراها یکسان (بدون تغییر). همه‌ی تست‌ها/مایگریشن‌ها روی کپی‌های `/tmp` اجرا شدند.

## ۹) محدودیت‌ها و تصمیم‌های قابل بازگشت
- **SQLite vs PostgreSQL:** سناریوی race (`test_s27a/b`) فقط روی SQLite فایلی معنا دارد؛ SQLite قفل نوشتارِ
  سطح‌دیتابیس دارد و ترتیب واقعی تراکنش‌ها با Postgres (MVCC) یکی نیست. منطق اپلیکیشن (UPDATE مشروط H8-P4)
  و backstop یکتایی دیتابیس-آگنوستیک است؛ ولی اثبات race روی PG نیاز به اجرای واقعی روی PG دارد (خارج از این تسک).
- **partial index برای حضور:** عمداً ساخته نشد؛ در عوض upsert/revive. مزیت: هیچ DDL قید روی DB قدیمی لازم نیست؛
  هزینه: «یک ردیف به‌ازای هر جفت» همیشه برقرار است و سابقه‌ی آرشیوی همان ردیف است (نه ردیف دوم).
- **کلاس زنده با راستر خالی:** طبق بخش ۳ (F-S3) جلسه ساخته نمی‌شود. اگر محصول ترجیح دهد تاریخچه‌ی
  «کلاس زنده‌ی بدون حاضر» حفظ شود، بازگشت یک‌خطی است: ساخت `SessionLog` با صفر حاضر از یک مسیر سیستمی
  مستثنا (با پارامتر صریح) — آن‌گاه همان قفل‌شدن (کلاس، تاریخ) هم برمی‌گردد.
- **O-S1** (پیام تسویه) خارج از scope باقی ماند: رفتار درست است و فقط متن پیام گمراه‌کننده است.
- پرداخت آنلاین، اندروید، CORS و دسترسی نقش‌ها طبق scope تسک دست نخوردند.

## ۱۰) git
فایل‌های تغییرکرده (۱۴): `validation.py`, `dependencies.py`, `models.py`, `main.py`, `schemas.py`,
`routers/attendance.py`, `routers/teachers.py`, `routers/analytics.py`, `routers/classes.py`, `routers/ai.py`,
`routers/automation.py`, `routers/exams.py`, `today_summary.py`, `test_attendance_sessions_audit.py`
(به‌علاوه همین CHK). همه‌ی تست‌های قبلی سبز ماندند (۵۸۴ passed) ⇒ هیچ رگرسیون شناخته‌شده‌ای باقی نیست.
