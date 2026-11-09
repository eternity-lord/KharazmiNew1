# CHK 2026-09-20 — FIX: تکمیل بخش کلاس‌های حذف‌شده / آرشیو ادمین

برنچ: `arena/01a0bf8d-kharazmiapp` | نوع تسک: **قابلیت‌های missing آرشیو + branch isolation** —
صفر hard delete، صفر دست‌خوردگی رفتار endpointهای غیرمرتبط، صفر تغییر در CRM/student search/invoice/
attendance/teacher approval/notification، صفر تغییر در `gaj_db.db`/`.env`.

## ۱) مشخصات

| مورد | مقدار |
|---|---|
| تاریخ | ۲۰۲۶-۰۹-۲۰ |
| برنچ | `arena/01a0bf8d-kharazmiapp` |
| HEAD پایه | `ec9cbc716d601fe95d9f9b2043baf2e1ab89e6e8` |
| دامنه‌ی تغییر | `routers/admin.py` (آرشیو) + مدل/دیالوگ Android + تست جدید |

## ۲) root cause — چرا آرشیو اطلاعات و امکانات کمی داشت؟

1. **endpoint ناقص:** `GET /admin/deleted_classes` (admin.py:1491) فقط ۶ فیلد برمی‌گرداند
   (`id/title/code/teacher_name/grade_level/bg_color`) — بدون شعبه، تعداد دانش‌آموز، تعداد جلسه،
   تراکنش، تاریخ حذف و بدون ترتیب قطعی (`.all()` بدون `order_by`).
2. **بدون branch isolation:** تابع با `check_admin_access` فقط نقش را چک می‌کرد؛ ادمینِ شعبه‌دار
   آرشیو **همه‌ی شعبه‌ها** را می‌دید (نشت بین‌شعبه‌ای). پروژه الگوی آماده دارد
   (`get_user_branch_filter` در `routers/analytics.py` که crm/exports هم استفاده می‌کنند).
3. **خطر null («None None»/«null»):** `t_name = f"{teacher.first_name} {teacher.last_name}"` برای نام
   NULL نتیجه‌ی «None None» می‌داد و `title/code/grade_level` هم می‌توانند NULL باشند.
4. **نبود جزئیات:** هیچ endpoint برای دیدن مشخصات یک کلاس آرشیوشده نبود.
5. **نبود جست‌وجو/فیلتر** در آرشیو.
6. **تاریخ حذف در مدل نیست:** `Course` ستون `deleted_at` **ندارد**. اما هر دو مسیر حذف
   (حذف مستقیم ادمین در `classes.py:861` و تایید درخواست در `classes.py:1073`) یک ردیف
   `ClassDeletionRequest` با `status="approved"` و `decided_at` ثبت می‌کنند ⇒ تاریخ حذف **قابل استخراج**
   است (بدون حدس‌زدن). کلاس‌های legacy که پیش از این جدول حذف شده‌اند تاریخ ندارند → مقدار خالی
   (هیچ تاریخی جعل نمی‌شود).
7. **restore وجود ندارد** — `grep restore` در `routers/*.py` و `dependencies.py` ⇒ صفر نتیجه
   و در `app.openapi()["paths"]` هیچ مسیر restore نیست. همچنین `_apply_class_deletion` ثبت‌نام‌ها را
   آرشیو و در حالت `forgive_session_charges=True` اثرات مالی جلسات را برمی‌گرداند (`perform_delete_enrollment`)
   که بازگشت‌پذیرِ مطمئن نیست ⇒ **طبق قانون تسک، restore حدس زده نشد؛ فقط گزارش شد.**
8. **سمت اپ:** `DeletedClassesApi` پاسخ آرشیو را با مدل اشتباه `PendingClassItem` پارس می‌کرد
   (فیلدهای `teacher_price/days/time/base_institute_share` در پاسخ آرشیو وجود ندارند و
   `title/code/teacher_name` می‌توانند null باشند) و دیالوگ فقط `setItems` ساده با title/code بود.

**پوشش تستی قبلی:** هیچ تستی برای `deleted_classes` وجود نداشت (`grep` صفر نتیجه).

## ۳) رفتار قبل → بعد

| مورد | قبل | بعد |
|---|---|---|
| فیلدهای لیست | ۶ فیلد (بدون شعبه/شمارش/تاریخ) | + `branch_id/branch_name`, `teacher_id`, `students_count`, `students_active_count`, `sessions_count`, `transactions_count`, `deleted_at`, `forgive_session_charges`, `is_suspended`, `days_of_week`, `class_time` (کلیدهای قبلی حفظ شد) |
| branch isolation | ندارد (نشت بین شعبه‌ها) | ادمین شعبه‌دار فقط شعبه‌ی خودش؛ ادمین کل (branch_id=NULL) همه |
| تاریخ حذف | نداشت | از آخرین `ClassDeletionRequest` تاییدشده (`decided_at or created_at`) با قالب `%Y/%m/%d %H:%M`؛ بدون رکورد → `""` |
| جست‌وجو | نداشت | `?query=` روی title/code/نام و نام‌خانوادگی معلم (branch-isolated) |
| ترتیب | نامشخص | قطعی: تازه‌ترین حذف اول، بعد id نزولی |
| کارایی | کوئری معلم در حلقه (N+1) | ۳ کوئری گروهی (`group_by`) + دو lookup دسته‌ای برای معلم/شعبه (بدون N+1) |
| جزئیات | نداشت | `GET /admin/deleted_classes/{id}` — فقط آرشیوشده، فقط همان شعبه، 404 برای فعال/ناموجود/شعبه‌ی دیگر (بدون نشت وجود رکورد)، خروجی dict تعریف‌شده |
| null/legacy | «None None» و احتمال «null» | رشته‌ی خالی/«نامشخص»؛ تست ۶ متن پاسخ را برای «None» اسکن می‌کند |
| سمت اپ | مدل اشتباه + نمایش ناقص | مدل درست `ArchivedClassItem`/`ArchivedClassDetail` + ردیف غنی (معلم/شعبه/دانش‌آموز/تاریخ) + دیالوگ جزئیات با کلیک، همه null-safe |

## ۴) فایل‌های تغییرکرده

| فایل | تغییر |
|---|---|
| `Kharazmi_Server/routers/admin.py` | بازنویسی `GET /admin/deleted_classes` + سه هلپر (`_archived_deletion_meta`، `_archived_class_aggregates`، `_fmt_datetime`/`_safe_person_name`) + endpoint جدید `GET /admin/deleted_classes/{course_id}` |
| `Kharazmi_Server/test_admin_archived_classes.py` | **جدید** — ۱۱ تست regression (موارد ۱ تا ۱۰ تسک + جست‌وجو) |
| `KharazmiAdmin/.../AppModels.kt` | مدل‌های `ArchivedClassItem` و `ArchivedClassDetail` (null-safe، `@SerializedName`) |
| `KharazmiAdmin/.../MainActivity.kt` | `DeletedClassesApi` (مدل درست + `query` + متد جزئیات) + ردیف‌های غنی + `showArchivedClassDetail` + import `retrofit2.http.Path` |
| `KharazmiAdmin/.../res/values/strings.xml` | +۱۲ رشته‌ی `main_trash_*` (ردیف غنی، بدون‌تاریخ، جزئیات، خطای جزئیات) |

## ۵) تست‌های اجراشده و نتیجه

همه‌ی اجراها با `DATABASE_URL=sqlite:////tmp/...` و `JWT_SECRET_KEY` موقت در env همان فرمان
(بدون ساخت/تغییر `.env`؛ `gaj_db.db` با md5 `f048f8d1…` **دست‌نخورده**).

| اجرا | دستور | نتیجه |
|---|---|---|
| تست‌های همین task | `pytest test_admin_archived_classes.py -q` | **11 passed** |
| اثبات ارزش regression (روی کد قبل از فیکس، worktree موقت detach) | همان فایل روی `HEAD` پیش از تغییر | **7 failed / 4 passed** — شکست‌ها: branch isolation (لیست و جزئیات)، متادیتای آرشیو، null/legacy، پاسخ جزئیات، جست‌وجو، متادیتای جریان حذف |
| suiteهای مرتبط | `test_admin_archived_classes + test_classes + test_admin + test_permissions + test_multi_branch + test_branch_resolution + test_exports + test_permissions_e2e` | **82 passed** |
| کل مجموعه | `pytest -q -p no:randomly` | **742 passed**, 5 failed |
| ۵ خطای باقی‌مانده | `test_audit.py` (۳) + `test_dashboard.py`/`test_dashboard_performance.py` (۲) | **از قبل موجود** — در task قبلی روی `0133d80` هم تکرار شد (خارج از scope) |

پوشش موارد خواسته‌شده: نقش مجاز (۱) ✅ | branch ادمین شعبه‌دار (۲) ✅ | عدم نشت (۳) ✅ |
عدم نمایش کلاس فعال (۴) ✅ | نمایش کلاس حذف‌شده (۵) ✅ | null/legacy بدون 500 (۶) ✅ |
جزئیات کنترول‌شده (۷) ✅ | restore = عدم وجود سیاست + read-only (۸) ✅ |
حفظ تاریخچه‌ی enrollment/transaction/session در حذف واقعی (۹) ✅ | عدم اختلاط لیست عادی و آرشیو (۱۰) ✅

## ۶) Android build status

**build ادعا نمی‌شود** — JDK و Android SDK در این محیط موجود نیستند (`java: command not found`،
`ANDROID_HOME` تنظیم نشده). بررسی انجام‌شده = static review: XML سالم (تجزیه‌ی strings.xml)،
تعادل براکت/پرانتز فایل‌های تغییریافته، تطبیق تعداد placeholderها با آرگومان‌های `getString`،
وجود همه‌ی resourceهای ارجاع‌شده (`common_yes/common_no/common_unknown_class/common_person_unknown/
btn_dismiss`) و تأیید اینکه `PendingClassItem` هنوز برای `PendingClassesActivity` دست‌نخورده است.

## ۷) محدودیت‌ها و ریسک‌های باقی‌مانده

1. **restore پیاده نشد** (سیاست فعلی پشتیبانی نمی‌کند). برای افزودن آن حداقل نیاز است:
   (الف) تصمیم محصولی درباره‌ی برگرداندن ثبت‌نام‌های آرشیوشده و اثرات مالی جلسات
   (`forgive_session_charges=True` برگشت‌پذیر مطمئن نیست)، (ب) ستون `deleted_at` (یا اتکای کامل به
   `ClassDeletionRequest`)، (ج) endpoint با همان branch isolation. پیشنهاد: task جدا با تصمیم صریح.
2. **کلاس‌های آرشیوشده‌ی بدون شعبه** (`branch_id IS NULL`) برای ادمین شعبه‌دار دیده نمی‌شوند (این عینِ
   isolation است) و فقط ادمین کل آن‌ها را می‌بیند — رفتار مستندشده، نه باگ.
3. **کلاس با `is_deleted=NULL`** (legacy) طبق سیاست موجود پروژه نه در آرشیو می‌آید و نه در لیست عادی
   (`== True` / `== False`). تغییر ندادم چون خارج از scope و نیازمند تصمیم داده‌ای است.
4. **تاریخ حذف** برای کلاس‌های حذف‌شده‌ی پیش از ایجاد `class_deletion_requests` خالی می‌ماند (عمدی؛
   هیچ تاریخی جعل نشد).
5. صحت نهایی **کامپایل Kotlin** فقط با build روی ماشین دارای JDK/SDK تأیید می‌شود.
6. `transactions_total` جمع **همه‌ی** تراکنش‌های تاریخی کلاس است (فعال و آرشیوشده) — معیار نمایش
   تاریخچه است، نه محاسبه‌ی مالی زنده.

## ۸) Commit / Push

| مورد | مقدار |
|---|---|
| Commit SHA | در گزارش نهایی اعلام می‌شود؛ داخل همان commit قابل درج نیست |
| push status | در گزارش نهایی اعلام می‌شود |
| دامنه‌ی stage | فقط همین ۵ فایل (۴ فایل تغییرکرده + تست جدید + همین checkpoint) |
