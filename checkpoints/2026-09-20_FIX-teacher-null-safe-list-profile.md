# CHK 2026-09-20 — FIX: null-safe کردن داده‌های مربی (لیست، پروفایل، تسویه‌ی معلق)

برنچ: `arena/01a0bf8d-kharazmiapp` | نوع تسک: **null-safety داده‌ی legacy** — صفر تغییر منطق مالی،
صفر تغییر permission/نقش‌ها، صفر تغییر نام کلیدها یا مسیرها (قرارداد API دست‌نخورده: فقط به‌جای `NULL` مقدار امن).

> **یادداشت ساختار (audit-history):** این checkpoint توسط task اول ثبت شد و SHA آن **قبل از قانون
> «checkpoint داخل همان commit کد»** ساخته شده است؛ بنابراین در commit جداگانه‌ی `8f48590` نشسته و
> commit کد آن `c5462c0` است. از task دوم به بعد، checkpoint و کد **در یک commit** قرار می‌گیرند و طبق
> قانون جدید، فیلد SHA داخل checkpoint نمی‌نویسد («در گزارش نهایی پس از commit ثبت می‌شود»).
> پایه‌ی هر دو commit: `0133d80`.

---

## ۱) وضعیت پایه (ثبت اولیه قبل از تغییر)

| مورد | مقدار |
|---|---|
| `git status --short` | خالی (پاک) |
| برنچ | `arena/01a0bf8d-kharazmiapp` |
| HEAD پایه | `0133d806cf57392d01020abb82e7ebc4cbc2eecc` |
| برنچ کاری هدف (سایر نشست‌ها) | `arena/01a0b352-kharazmiapp` = همان `0133d80` (درخت یکسان) |

## ۲) مشکل و root cause (با probe مستقل قبل از فیکس اثبات شد)

اسکریپت probe خارج از ریپو (`/home/user/probe_teacher_nulls.py`) روی درخت `0133d80` اجرا شد؛ نتایج واقعی:

| # | نقطه | شکست واقعی (قبل از فیکس) |
|---|---|---|
| ۱ | `GET /admin/teachers/{id}/credentials` | `ValidationError: national_code/mobile Input should be a valid string` → **500** |
| ۲ | `GET /teachers/list/excel` | `TypeError: sequence item 0: expected str instance, NoneType found` → **500** |
| ۳ | `GET /teachers/{id}/pending_settlement` (کلاس دارد، جلسه ندارد) | `teacher_name: "None None"` (ناهم‌خوانی دو مسیر خروج زودهنگام) |
| ۴ | `GET /teachers/{id}` (پروفایل خام) | نشت `null` در `first_name/last_name/national_code/mobile` به مدل **non-null** اپ (`TeacherRawProfile`) |
| ۵ | `GET /teachers/pending` | `mobile: null` در پاسخ برای معلم بدون موبایل |

**root cause:** ستون‌های `Teacher.first_name/last_name/national_code/mobile` در `models.py` بدون
`nullable=False` تعریف شده‌اند و رکوردهای legacy با `NULL` پر شده‌اند؛ کد مسیر مربی در چند نقطه
این `NULL`ها را خام مصرف می‌کرد (f-string، `join`، `response_model` با فیلد `str` اجباری، مدل کاتلین غیر-null).

**قبلاً-فیکس‌شده‌ها (تغییر duplicate انجام نشد):** `admin/teachers/search` و
`teachers/{id}/full_profile` از قبل null-safe بودند و تست‌های موجودشان پاس می‌شد؛ دست نخوردند.

## ۳) رفتار قبل → بعد

| نقطه | قبل | بعد |
|---|---|---|
| `teachers/{id}/credentials` با نام/کد ملی/موبایل NULL | 500 (`ValidationError`) | 200 — `name="نامشخص"`، `national_code=""`، `mobile=""` |
| `teachers/list/excel` با عنوان کلاس NULL | 500 (`TypeError`) | 200 — فایل xlsx با «کلاس بدون عنوان» و نام امن |
| `teachers/{id}/pending_settlement` (بدون جلسه) | `"None None"` | `"نامشخص"` (هم‌خوان با مسیر اول) |
| `teachers/{id}` با فیلدهای NULL | نشت `null` | رشته‌ی خالی؛ **`id` و بقیه‌ی کلیدها بدون تغییر** |
| `teachers/pending` با موبایل NULL | `mobile: null` | `mobile: null` (قرارداد Optional حفظ شد) + مدل اپ null-safe |
| لیست مختلط سالم+ناقص | یک رکورد ناقص لیست را می‌شکست | همه‌ی رکوردها با **`id` واقعی** برمی‌گردند |

## ۴) فایل‌های تغییرکرده (۱۰ فایل — commit `c5462c0`، +۲۴۲/−۴۰)

**Backend**
- `Kharazmi_Server/routers/teachers.py` — پروفایل خام (۴ فیلد امن)، مسیر دوم `pending_settlement`، `list/excel` (join عنوان + نام)
- `Kharazmi_Server/routers/admin.py` — `credentials` (رفع 500) + دو `target_name` لاگ (`reset_password` / `update_credentials`)
- `Kharazmi_Server/test_teacher_null_data.py` — ۸ تست جدید

**Android (مدل/ادپتر/اکتیویتی همان مسیر)**
- `AppModels.kt` (`TeacherRawProfile`, `TeacherSimple`)
- `EditTeacherActivity.kt` (fallback چهار فیلد)
- `AddClassActivity.kt` (`TeacherSimple` + تطبیق نام)
- `ReportActivity.kt` (`TeacherItem` + فیلتر معلم)
- `PendingTeachersActivity.kt` (`TeacherPending` + adapter)
- `TeacherCredentialsActivity.kt` (model + نمایش + `CredentialsSearchAdapter`)
- `res/values/strings.xml` — رشته‌ی جدید `common_person_unknown`

## ۵) تست‌ها و نتیجه

محیط: `/home/user/.venv` (خارج از ریپو) با `Kharazmi_Server/requirements.txt` +
`JWT_SECRET_KEY` موقت در **env همان فرمان** (نه فایل `.env`). `gaj_db.db` دست‌نخورده.

| اجرا | دستور (خلاصه) | نتیجه |
|---|---|---|
| تست‌های نفس این فیکس | `pytest test_teacher_null_data.py -q` | **19 passed** |
| regression مستقیم teacher | `pytest test_teachers.py test_teacher_null_data.py -q` | **25 passed** |
| زیرمجموعه‌ی مرتبط | `pytest test_teachers test_teacher_null_data test_admin test_permissions test_collaboration_summary test_communication_history test_exports -q` | **57 passed** |
| کل مجموعه | `pytest -q` | **731 passed**, 5 failed |
| ۵ خطای باقی‌مانده | `test_audit.py` (۳) + `test_dashboard.py`/`test_dashboard_performance.py` (۲) | **از قبل موجود** — با اجرای همان تست‌ها روی worktree موقت در `0133d80` تأیید شد (خارج از scope این task) |

**اثبات اعتبار خودِ تست‌های جدید (نه صرفاً سبز شدن):** همان فایل تست روی درخت **قبل از فیکس**
(worktree موقت detach روی `0133d80`) اجرا شد → **4 failed**:
`test_teacher_credentials_null_mobile_and_national_code`,
`test_teachers_excel_null_course_title_and_name`,
`test_teacher_profile_null_fields_do_not_leak_none`,
`test_pending_settlement_null_name_with_courses_but_no_sessions`
— و پس از فیکس همه پاس شدند.

پوشش موارد خواسته‌شده: mobile=NULL ✅ | national_code=NULL ✅ | نام ناقص ✅ | total_paid=NULL ✅ (تست قبلی
`test_full_profile_null_total_paid`) | course title=NULL ✅ | تاریخ/نام ناقص در تسویه‌ی معلق ✅ |
ترکیب رکورد سالم و ناقص ✅ | regression مستقیم teacher ✅

## ۶) Android build status

**build ادعا نمی‌شود.** در این محیط JDK نصب نیست (`java: command not found`) و Android SDK هم موجود نیست
(`ANDROID_HOME` تنظیم نشده) — بنابراین `gradlew` قابل اجرا نبود. فقط **static review** انجام شد:
تعادل براکت‌ها در ۶ فایل تغییرکرده، بازبینی همه‌ی محل‌های استفاده از فیلدهای null‌شده، تأیید ارجاع‌های
`R.string.common_person_unknown` (۵ مورد) و تأیید سابقه‌ی الگوی `${x ?: ""}` در همین پروژه
(`TeacherProfileActivity.kt:270`).

## ۷) محدودیت‌ها و ریسک‌های باقی‌مانده

1. **جلسه با `date=NULL`** در `pending_settlement` طبق منطق موجود فیلتر تاریخ کنار گذاشته می‌شود
   (بدون crash، ولی درخواست مالی نمایش داده نمی‌شود). عمداً تغییر نداد: تغییر semantics مالی خارج از
   scope null-safety است. در تست مستند شده.
2. **رفتار صورت‌حساب جلسه‌ی بی‌تاریخ** (`is_billed` / `is_penalty_settled`) در این task دست نخورد؛ اگر
   بخواهید طلب معلم برای این جلسات هم دیده شود، task جدا لازم است.
3. صحت نهایی **کامپایل Kotlin** فقط با build روی ماشین دارای JDK/SDK تأیید می‌شود.
4. فیکس‌های هم‌خانواده در `attendance.py` / `finance.py` / `classes.py` / `reports.py` / `auth.py`
   (الگوی `f"{teacher.first_name} {teacher.last_name}"`) طبق محدوده‌ی تسک **دست‌نخورده** — کاندید task بعدی.
5. `mobile` در پاسخ `/teachers/list` عمداً `Optional` ماند (تغییر آن قرارداد API را می‌شکست)؛ امن‌سازی
   در سمت اپ انجام شد.

## ۸) Commit / Push

| مورد | مقدار |
|---|---|
| commit کد (task اول) | `c5462c081d5d8c59eadc81ee4d10918fce297818` — `fix: make teacher data handling null-safe` |
| commit این checkpoint | `8f4859058af2dd8a4720726dc1c32a172a7e7966` — `docs(checkpoint): ثبت checkpoint فیکس null-safe داده‌های مربی` |
| **Commit SHA (این task)** | **در گزارش نهایی پس از commit ثبت می‌شود؛ SHA داخل همان commit قابل درج نیست** |
| push | ✅ `origin arena/01a0bf8d-kharazmiapp` (هر دو commit آپلود شده) |
| لینک commit کد | https://github.com/eternity-lord/KharazmiApp/commit/c5462c081d5d8c59eadc81ee4d10918fce297818 |
| لینک commit checkpoint | https://github.com/eternity-lord/KharazmiApp/commit/8f4859058af2dd8a4720726dc1c32a172a7e7966 |
| لینک branch | https://github.com/eternity-lord/KharazmiApp/tree/arena/01a0bf8d-kharazmiapp |
| ZIP دانلود (branch) | https://github.com/eternity-lord/KharazmiApp/archive/refs/heads/arena/01a0bf8d-kharazmiapp.zip |
| PR به برنچ کاری | https://github.com/eternity-lord/KharazmiApp/pull/1 (OPEN — بدون دستور کاربر merge/close نشد) |
