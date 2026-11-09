# چک‌پوینت ممیزی: طراحی امن restore برای کلاس‌های آرشیوشده

- **عنوان:** امکان‌سنجی محصولی/داده‌ای restore کلاس حذف‌شده — ممیزی صرف (بدون کدنویسی، بدون migration، بدون تغییر داده)
- **تاریخ:** 2026-09-20
- **Branch:** `arena/01a0bf8d-kharazmiapp` (تنها branch کاری)
- **HEAD در زمان ممیزی:** `b1679025cec18fac3fba7aef68d26680d5f04f3b`
- **ابزار اثبات:** probe بیرون‌ریپو `/home/user/probe_restore_audit.py` روی DB موقت SQLite (DB واقعی `gaj_db.db` با md5 `f048f8d118b33c4eaa944490594121d7` دست‌نخورده)
- **قانون رعایت‌شده:** هیچ endpoint، migration، تغییر داده، احیای enrollment/transaction انجام نشد. هیچ چیزی از snapshot حدس زده نشد.

---

## ۰) خلاصه‌ی مدیریتی

| پرسش | پاسخ کوتاه |
|---|---|
| restore کامل (داده‌ای) امن است؟ | ❌ **نه، با وضعیت فعلی نه.** سه شکاف بنیادی دارد (بدون دفتر کل، بدون شناسه‌ها، بستانکاری برگشت‌ناپذیر). |
| restore فقط metadata ممکن است؟ | ✅ **بله** — امروز و با یک تغییر کوچک، اثر مالی صفر. |
| نیاز به تصمیم محصولی؟ | ✅ **بله، ۵ تصمیم** (بخش ۱۰). |
| آیا `deleted_at` لازم است؟ | برای خودِ restore نه؛ برای policy/UX/مسیر سوم حذف بله (بخش ۵). |

**یافته‌ی جانبی مهم (باگ واقعی موجود):** مسیر حذف `DELETE /admin/reject_class/{course_id}` کلاس را آرشیو می‌کند ولی جلساتش را آرشیو **نمی‌کند** و هیچ `ClassDeletionRequest` نمی‌سازد؛ نتیجه: **طلب معلم از یک کلاس حذف‌شده هنوز باز می‌ماند** (اثبات عددی در بخش ۴). این باگ امروز در محصول وجود دارد و مستقل از restore باید تعیین تکلیف شود.

---

## ۱) مسیر فعلی archive/delete — سه مسیر متفاوت با معانی متفاوت

| مسیر | endpoint | گارد | اثر |
|---|---|---|---|
| ۱. حذف مستقیم ادمین | `DELETE /classes/{course_id}?forgive_session_charges=true` | `check_admin_access` (فقط admin) | `_apply_class_deletion` + ثبت `ClassDeletionRequest(status="approved")` با snapshot |
| ۲. تأیید درخواست | `POST /classes/deletion_requests/{id}/approve` | admin | همان `_apply_class_deletion` با `forgive` درخواست |
| ۳. رد کلاس تازه‌ساخته | `DELETE /admin/reject_class/{course_id}` | admin | `perform_delete_enrollment` برای همه‌ی ثبت‌نام‌ها + `Course.is_deleted=True` — **بدون آرشیو جلسات، بدون snapshot، بدون رکورد حذف** |

درخواست‌دهی (بدون اثر): `POST /classes/{course_id}/request_delete` (teacher فقط کلاس خودش / secretary) → `status="pending"` → approve/reject. لیست: `GET /classes/deletion_requests` (admin).

### `_apply_class_deletion` دقیقاً چه می‌کند (classes.py:975-987)
1. `Course.is_deleted = True`
2. برای هر ثبت‌نام فعال → `perform_delete_enrollment(en, db, forgive_session_charges)`
3. اگر `forgive_session_charges=True` → `SessionLog.is_deleted = True` برای **همه‌ی جلسات کلاس** (bulk update)

### `perform_delete_enrollment` (dependencies.py:312-395) دقیقاً چه می‌کند
1. `Enrollment.is_deleted = True` (claim اتمیک، idempotent)
2. تراکنش‌های وابسته (بر اساس `enrollment_id` یا `student_id+course_id`) را می‌گیرد:
   - `tuition` / `enrollment_payment` / `deposit` / `reversal` → **دست‌نخورده می‌مانند** (سیاست Bug 13: پول واقعی دریافت‌شده از بین نمی‌رود)
   - `session_charge` با `forgive=False` → **دست‌نخورده** (هزینه‌ی جلسات برگزارشده سر جایش می‌ماند)
   - بقیه → **آرشیو** (`is_deleted=True`) و اگر `session_charge` بود: **`Student.wallet_teacher += share_teacher` و `wallet_institute += share_institute`** و بعد `sync_wallet_balance()`
3. `Installment.is_deleted = True` (همه‌ی اقساط آن ثبت‌نام، bulk)
4. `Attendance` → **دست‌نخورده** (آرشیو نمی‌شود؛ فقط مسیر «برگشت جلسه» آن را آرشیو می‌کند)

### نکته‌ی کلیدی
حذف کلاس، **آرشیو نرم + جابه‌جایی پول** است؛ نه حذف. یعنی «restore» صرفاً flip کردن `is_deleted` نیست — باید حرکت پول را هم دقیقاً برگرداند، و امروز **هیچ رکوردی از آن حرکت پول به‌ازای هر ردیف وجود ندارد**.

---

## ۲) `is_deleted` و `deleted_at`

- `deleted_at` **در هیچ جدولی وجود ندارد** (grep سراسری: هیچ ستونی نیست؛ تنها استفاده‌ها در `routers/admin.py` و تست Task 2 است که **مشتق و محاسباتی** هستند).
- تاریخ حذف در نمای آرشیو از `ClassDeletionRequest.decided_at` (fallback: `created_at`) ساخته می‌شود — یعنی فقط برای مسیرهای ۱ و ۲ و فقط اگر رکورد وجود داشته باشد.
- کلاس‌های legacy و کلاس‌های مسیر ۳ ⇒ `deleted_at = ""` (بدون تاریخ). این رفتار الان در `GET /admin/deleted_classes` دیده می‌شود و تست Task 2 (`test_6_legacy_nulls_do_not_500`) آن را قفل کرده است.
- مدل‌های دخیل: `Course.is_deleted`, `Enrollment.is_deleted` (nullable=False, server_default FALSE), `SessionLog.is_deleted`, `Attendance.is_deleted`, `Transaction.is_deleted` (+ `is_reversed`), `Installment.is_deleted`, `Student.is_deleted`, `Teacher.is_deleted`.

### قیدهای دیتابیس مرتبط با restore
| جدول | قید | اثر روی restore |
|---|---|---|
| `session_logs` | ایندکس یکتای **partial** `(course_id, date) WHERE is_deleted = FALSE` | اگر روی کلاس حذف‌شده جلسه‌ی جدیدی با همان تاریخ ثبت شود، restore جلسه‌ی قدیم **IntegrityError** می‌دهد (اثبات‌شده) |
| `attendances` | یکتای **غیر partial** `(session_id, student_id)` | ردیف آرشیوشده جای خود را نگه می‌دارد ⇒ مسیر ویرایش باید revive کند (precedent موجود: `attendance.py:79` `row.is_deleted = False`) |
| `enrollments` | **هیچ قید یکتایی ندارد** | restore ثبت‌نام قید DB را نمی‌شکند (اما app-level چک `is_deleted == False` دارد) |
| `courses` | `code` یکتا | restore همان ردیف است ⇒ تضاد ندارد |

---

## ۳) `ClassDeletionRequest` و `snapshot_json` — چه چیزی *هست* و چه چیزی *نیست*

ساختار رکورد: `course_id`, `requested_by_role`, `requested_by_user_id`, `requested_by_teacher_id`, `forgive_session_charges`, `status` (pending/approved/rejected), `snapshot_json`, `admin_note`, `decided_by_user_id`, `created_at`, `decided_at`.

**محتوای واقعی snapshot (اثبات‌شده با probe):**

```
کلیدهای سطح بالا : course_id, course_title, course_code, sessions_total, students, totals
کلیدهای هر شاگرد : student_id, name, sessions_attended, tuition_final, total_paid, debt,
                   wallet_teacher, wallet_institute
totals           : {students, total_debt, total_paid, teacher_pending_this_class}
```

**آنچه در snapshot نیست (همه با probe تأیید شد):** ❌ `enrollment_id` ❌ `session_id` ❌ شناسه/مبلغ تراکنش‌ها ❌ ردیف‌های Installment ❌ ردیف‌های Attendance ❌ **مبلغ بستانکاری کیف پول** ❌ دلیل/زمان آرشیو هر ردیف.

⇒ snapshot یک سند **بازبینی برای تصمیم ادمین** است (همانطور که در داک‌استرینگ آمده)، **نه سند بازسازی**. donc «restore از روی snapshot» غیرقابل اتکاست و طبق دستور شما انجام/فرض نشد.

---

## ۴) شواهد تجربی probe (خلاصه‌ی اعداد)

سناریو: ۴ کلاس همانند (هرکدام ۲ جلسه، ۲ ثبت‌نام، ۳ تراکنش، ۲ قسط، ۳ ردیف حضور)، هر جلسه `final_teacher_cost=100000`، هر ثبت‌نام `total_tuition=2,000,000` و `total_paid=500,000`.

| # | یافته | عدد/شاهد |
|---|---|---|
| A | حذف کلاس A (forgive=true) | `Course/Enrollment/SessionLog/Installment` همه `is_deleted=True` |
| B | **حضورها آرشیو نشدند** | `Attendance.is_deleted` هنوز `False` ⇒ عدم تقارن در حذف کلاس |
| C | تراکنش‌ها | `session_charge` آرشیو شد؛ `tuition` فعال ماند (سیاست Bug 13) |
| D | **بستانکاری کیف پول** | شاگرد ۱: `(0,0,0)` → `(100000, 50000, 150000)` |
| E | اثر روی بدهی | بدهی شاگرد ۱: `6,000,000` → `4,500,000` (Δ=۱٫۵M = کل بدهی همان کلاس) |
| F | اثر روی طلب معلم | `800,000` → `600,000` (Δ=۲۰۰k = ۲ جلسه) |
| G | **دفتر کل (ledger)** | `FinancialAuditLog`: ۲۰ رکورد، **توزیع action = {create: 20}** ⇒ **صفر رکورد update برای آرشیو انبوه**. هیچ نشانه‌ای که «کدام تراکنش/قسط با این حذف آرشیو شد» وجود ندارد |
| H | restore کامل ساده‌لوحانه (flip همه) | بدهی به `6,000,000` و طلب معلم به `800,000` **برگشت کامل** — ولی کیف پول هم `(100000,50000,150000)` باقی ماند ⇒ **Double-count: شاگرد هم اعتبار گرفت، هم هزینه‌ی جلسه‌ها زنده شد** |
| I | ابهام منبع آرشیو | یک جلسه با `reverse_session_financial_impacts` برگشت داده شد (سناریوی مستقل)؛ بعد کلاسش حذف شد؛ restore ساده‌لوحانه **تراکنش برگشت‌خورده را هم زنده کرد** (`is_deleted=False`) چون تفکیک منبع ممکن نیست |
| J | تضاد ایندکس یکتا | روی کلاس حذف‌شده جلسه‌ی جدید با همان تاریخ ثبت شد (گارد ساخت جلسه فقط `is_suspended` را چک می‌کند) → restore جلسات **`IntegrityError: UNIQUE constraint failed: session_logs.course_id, session_logs.date`** |
| K | مسیر سوم (`reject_class`) | جلسات آرشیو **نشدند**، `ClassDeletionRequest` **ساخته نشد** (`deleted_at=""` در آرشیو) و **طلب معلم از کلاس حذف‌شده هنوز باز ماند: سهم C = 200,000** |
| L | restore فقط metadata | کلاس در `/classes/list` و `/{id}/details` برمی‌گردد با **۰ شاگرد**؛ `pending` **دقیقاً بی‌تغییر** (`200000 → 200000`) ⇒ اثر مالی صفر |
| M | permission/branch (فعلی) | ادمینِ شعبه ۱ ⇒ فقط آرشیو شعبه ۱ (`ids=[2,3,4]`)؛ ادمین مرکزی ⇒ همه؛ بدون توکن ⇒ ۴۰۱ |

---

## ۵) پاسخ به ۱۰ پرسش خواسته‌شده

### ۱. restore کامل از نظر داده‌ای امن است یا نه؟
**نه — با وضعیت فعلی غیرامن است.** شش دلیل اثبات‌شده:
1. **بدون دفتر کل:** آرشیو انبوه (`Query.update`) در `FinancialAuditLog` ثبت نمی‌شود (شاهد G) ⇒ مجموعه‌ی دقیق ردیف‌های تعلق‌دار به این حذف قابل بازسازی نیست.
2. **snapshot شناسه ندارد** ⇒ مسیر بازسازی از سند وجود ندارد (بخش ۳).
3. **بستانکاری کیف پول برگشت‌ناپذیرِ امن نیست:** پول جابه‌جا شده و ممکن است خرج شده باشد؛ برگرداندنش بدون سند ⇒ یا کیف پول منفی، یا double-count (شاهد H).
4. **آرشیو چندمنبعی است:** ردیف آرشیوشده به‌خاطر «برگشت جلسه» از «حذف کلاس» تفکیک نمی‌شود (شاهد I).
5. **تضاد قید یکتا** روی جلسات ⇒ خطای ۵۰۰ در restore (شاهد J).
6. **عدم تقارن حذف:** Attendance آرشیو نمی‌شود، جلسات در مسیر سوم آرشیو نمی‌شوند (شواهد B و K) ⇒ حالت بازیابی‌شده ناسازگار می‌شود.

**نتیجه:** restore کامل نیازمند **تغییر سمت حذف** (ثبت دفتر کلّ + شناسه‌ها) است، نه فقط افزودن یک endpoint.

### ۲. restore فقط Course metadata ممکن است؟
**بله و امروز قابل پیاده‌سازی است.** با یک فیلد (`Course.is_deleted = False`) کلاس به لیست فعال برمی‌گردد؛ اثر مالی **صفر** (شاهد L: pending بی‌تغییر)؛ ثبت‌نام/جلسه/تراکنش‌ها آرشیو می‌مانند. پیامد محصولی: کلاس با **۰ شاگرد و ۰ جلسه‌ی فعال** بالا می‌آید و باید ادمین دوباره ثبت‌نام کند. این همان گزینه‌ی «کلاس را برگردان، سابقه را دست نزن» است.

### ۳. enrollmentهای قبلی باید چه وضعیتی داشته باشند؟
سه گزینه، به ترتیب ایمنی:
- **الف) آرشیوشده بمانند (پیشنهاد فاز ۱):** هیچ ریسک مالی ندارد.
- **ب) revive انتخابی (`is_deleted=False`):** فقط با این پیش‌شرط‌ها: (۱) بستانکاری کیف پولِ همان ثبت‌نام باید **معکوس (debit)** شود و مبلغش باید **سند داشته باشد** (امروز ندارد)؛ (۲) چک کفایت موجودی/یا سیاست «بدهی جدید»؛ (۳) جلوگیری از duplicate (چک app-level روی `is_deleted == False` هست). توجه: با revive، بدهی شاگرد **فوراً** برمی‌گردد (شاهد E به‌صورت معکوس).
- **ج) ثبت‌نام جدید (re-enroll):** تاریخچه دست‌نخورده؛ ادمین با تعرفه‌ی امروز ثبت‌نام می‌کند. برای «کلاس ادامه دارد» عملی‌ترین است.

### ۴. transaction و session تاریخی چه می‌شوند؟
- **Transaction:** وجه واقعی (`tuition/enrollment_payment/deposit/reversal`) هرگز آرشیو نمی‌شود ⇒ مسئله‌ای ندارد. `session_charge` (و تایپ‌های دیگر) آرشیو می‌شوند و همراه آن‌ها **کیف پول بستانکار** شده ⇒ restore فقط با دفتر کلّ + debit معکوس + بررسی کفایت موجودی امن است؛ در غیر این‌صورت **آن‌ها را دست نزنید**.
- **SessionLog:** با `forgive=true` آرشیو می‌شوند. restore آن‌ها: (۱) ممکن است قید یکتا را بشکند، (۲) **طلب معلم را دوباره باز می‌کند** ⇒ تصمیم محصولی لازم است: «آیا معلم برای کلاسی که شاگردانش بستانکار شدند دوباره تسویه می‌گیرد؟» (اگر بله ⇒ پرداخت دوباره؛ اگر نه ⇒ باید `is_billed`/`is_penalty_settled` مدیریت شود).
- **Attendance:** امروز در حذف کلاس دست‌نخورده می‌ماند ⇒ اگر جلسات برنگردند، ردیف‌های حضور «یتیم اما زنده» باقی می‌مانند (وضعیت موجود).

### ۵. آیا `deleted_at` لازم است؟
- **برای خود عملیات restore: نه.** `is_deleted` کافی است.
- **برای سیاست‌گذاری و UX: بله.** بدون آن: پنجره‌ی undo قابل تعریف نیست، ترتیب/گزارش دقیق نیست، و مسیر سوم (و کلاس‌های legacy) اصلاً تاریخ ندارند.
- **پیشنهاد (بدون اجرا در این تسک):** به‌جای افزودن ستون به همه‌ی جداول، **گسترش رکورد حذف** (یک جدول/رکورد حذف کلاس) با: `deleted_at`, `deleted_by_user_id`, `reason`, `forgive_session_charges` و آرایه‌ی شناسه‌های آرشیوشده + مبالغ بستانکاری. اگر ستون لازم شد، فقط `Course.deleted_at` برای نمای آرشیو کافی است (چون بقیه از رکورد حذف مشتق می‌شوند) — اما این یک تغییر schema و نیازمند تأیید جداگانه است.

### ۶. permission دقیق restore چیست؟
پیش‌نهاد منطبق با وضعیت فعلی پروژه:
- **فقط `check_admin_access`** (یعنی `sub_role == "admin"`؛ **منشی ۴۰۳** — چون مسیر خود حذف هم منشی را راه نمی‌دهد). اگر محصول بخواهد منشی هم بتواند، باید صریحاً از `check_admin_or_secretary_access` استفاده شود (تصمیم محصولی).
- **شعبه:** همان الگوی `get_user_branch_filter` (بخش ۷).
- **idempotency/وضعیت:** کلاسِ فعال ⇒ پاسخ کنترل‌شده (پیشنهاد ۴۰۹/۴۰۰ «کلاس فعال است»)، کلاس ناموجود/شعبه‌ی دیگر ⇒ **۴۰۴** (بدون نشت وجود رکورد — عین رفتار `GET /admin/deleted_classes/{id}`).
- **مسیر جدا:** وضعیت `ClassDeletionRequest` را دست نزنید (`pending/approved/rejected` معنیِ «تصمیم حذف» دارد)؛ restore یک رکورد/جدول جدا با actor و دلیل می‌خواهد.
- **گارد رگرسیون موجود:** `test_8_restore_not_offered_and_archive_is_read_only` در `test_admin_archived_classes.py` صریحاً چک می‌کند «هیچ مسیر restore در API نیست»؛ با افزودن restore این تست **باید** آگاهانه به‌روزرسانی شود (وگرنه عمداً می‌شکند) و باید permission/branch آن هم تست شود.

### ۷. branch isolation چگونه اعمال می‌شود؟
- در نمای آرشیو فعلی: `resolved_branch = get_user_branch_filter(db, authorization, branch_id)` → اگر کاربر `branch_id` دارد، **فقط شعبه‌ی خودش** (پارامتر ورودی نادیده گرفته می‌شود)؛ ادمین مرکزی (`branch_id IS NULL`) می‌تواند با پارامتر شعبه فیلتر کند.
- فیلتر روی `Course.branch_id` اعمال می‌شود؛ کلاس‌های `branch_id = NULL` (legacy/مرکزی) برای ادمینِ شعبه‌دار **دیده نمی‌شوند** ⇒ restore آن‌ها هم باید فقط برای ادمین مرکزی مجاز باشد (یا سیاست صریح شما).
- داده‌ی مرتبط: `Enrollment.branch_id` هم وجود دارد (می‌تواند با `Course.branch_id` متفاوت باشد) — برای restore، **ملاک همان `Course.branch_id`** باشد تا با نمای آرشیو یکدست بماند.

### ۸. سناریوهای خطرناک
1. **Double-count کیف پول** (اثبات‌شده، شاهد H): شاگرد هم اعتبار می‌گیرد هم هزینه‌ی جلسه‌ها زنده می‌شود.
2. **احیای ردیف‌های بیگانه** (شاهد I): تراکنش‌های آرشیوشده به دلیل «برگشت جلسه» یا حذف دستی، با restore کلاس زنده می‌شوند.
3. **IntegrityError روی جلسات** (شاهد J) ⇒ ۵۰۰ و نیمه‌کاره ماندن تراکنش (در صورت نبود اتمیک بودن).
4. **پرداخت دوباره به معلم** در حالی که شاگردان بستانکار شده‌اند (باز شدن pending).
5. **معلم آرشیوشده:** حذف معلم وقتی هیچ کلاسی نداشته باشد ممکن است؛ بعداً restore کلاس با آن معلم ⇒ کلاس بدون معلم فعال. (نکته: `delete_teacher` فعلاً اگر معلم **هر** کلاسی — حتی آرشیوشده — داشته باشد، حذف را با ۴۰۰ رد می‌کند.)
6. **بازگشت کلاس بدون ظرفیت/تداخل:** زمان/روز کلاس ممکن است با کلاس جدیدِ همان معلم/اتاق تداخل داشته باشد؛ هیچ اعتبارسنجی تداخل در restore وجود ندارد.
7. **جهش گزارش‌های مالی:** با restore کامل، درآمد/شهریه/بدهی/آمار کلاس‌ها در گزارش‌ها (که همه `is_deleted == False` فیلتر می‌کنند) ناگهان تغییر می‌کند — اعم از `reports.py` (۸ نقطه)، `finance.py` (۶۹ ارجاع)، `analytics.py`، `dashboard.py`.
8. **کلاس بدون متادیتا** (مسیر ۳/legacy) ⇒ نمی‌دانیم با `forgive` حذف شده یا نه؛ restore کورکورانه خطرناک است.
9. **همزمانی:** حذف مجدد یا درخواست حذف باز، همراه restore ⇒ نیاز به قید وضعیت/idempotency.
10. **باور غلط «snapshot کافی است»** ⇒ ممنوع؛ snapshot فقط تجمیع است.

### ۹. پیشنهاد API و تست‌ها (فقط پیشنهاد — هیچ‌کدام ساخته نشد)

**فاز ۱ — restore متادیتا (امن، کم‌ریسک):**
```
POST /admin/deleted_classes/{course_id}/restore
  Body: { "mode": "metadata_only", "reason": "..." }   # mode اجباری، در فاز ۱ فقط metadata_only
  Permissions: check_admin_access + branch isolation (get_user_branch_filter)
  Responses: 200 (restored) | 400 (mode نامعتبر) | 404 (آرشیو نیست / شعبه‌ی دیگر) | 409 (کلاس فعال است)
  اثر: فقط Course.is_deleted=False ; ثبت رکورد restore با actor/reason ; منطق مشترک با حذف (helper مشترک)
```
پیشنهاد افزودن به `GET /admin/deleted_classes/{id}`: فیلدهای راهنما برای UI مثل `restore_mode_available: "metadata_only"` و `finance_side_effects: true/false`.

**فاز ۲ — restore کامل (فقط اگر محصول بخواهد):** نیازمند تغییر **سمت حذف** در یک تسک جدا:
1. جدول/رکورد «دفتر حذف کلاس» با آرایه‌ی شناسه‌های `enrollment_ids`, `session_ids`, `transaction_ids`, `installment_ids` + `wallet_credits` (per student/per wallet) + `deleted_at`, `deleted_by_user_id`, `reason`.
2. مسیر سوم حذف (`reject_class`) هم باید در همان دفتر ثبت کند (و اگر سیاستش عوض شد، جلسات را هم آرشیو کند).
3. restore در **یک تراکنش** با پیش‌شرط‌ها: کفایت/سیاست موجودی، عدم تضاد تاریخ جلسه، عدم تضاد `is_billed`، idempotency.
4. **`dry_run=true`** که فقط گزارش دهد «اگر restore شود چه چیزی و چه مبلغی برمی‌گردد» بدون هیچ نوشتن.
5. ردکردن restore در صورت نبود دفتر کل (کلاس‌های legacy/مسیر ۳) با پیام کنترل‌شده.

**تست‌های پیشنهادی (فاز ۱):** ۴۰۱ بدون توکن · ۴۰۳ برای معلم/منشی/شاگرد · ۴۰۴ برای کلاس فعال و شعبه‌ی دیگر · ۲۰۰ و بازگشت به `/classes/list` · **اثر مالی صفر** (pending/debt/wallet بی‌تغییر) · عدم احیای enrollment/session/transaction · idempotency (restore دوباره) · ثبت actor/reason · سازگاری با `test_8_restore_not_offered_and_archive_is_read_only` (به‌روزرسانی آگاهانه) · بدون تغییر در آرشیو.
**تست‌های پیشنهادی (فاز ۲):** double-count کیف پول · احیای ردیف بیگانه (reverse) · تضاد ایندکس یکتا · اتمیک بودن (rollback کامل در خطا) · dry-run بدون نوشتن · کلاس legacy بدون متادیتا.

### ۱۰. آیا نیاز به تصمیم محصولی کاربر وجود دارد؟
**بله — ۵ تصمیم صریح:**
1. **دامنه‌ی restore:** فقط متادیتا (پیشنهاد) یا کامل (نیازمند تسک فاز ۲ با تغییر سمت حذف)؟
2. **enrollmentها:** آرشیوشده بمانند، revive شوند، یا ثبت‌نام جدید؟
3. **پول:** آیا بستانکاری کیف پولِ ناشی از حذف باید در restore **پس گرفته شود**؟ اگر موجودی خرج شده باشد چه شود (بدهی جدید / رد restore / بستانکار institute)؟
4. **طلب معلم:** آیا معلم برای کلاس بازیابی‌شده دوباره قابل تسویه است؟ (اگر بله، سیاست پرداخت دوباره چیست؟)
5. **معلم/شعبه:** restore کلاس با معلم آرشیوشده یا `branch_id=NULL` مجاز است یا نه؟ و دسترسی منشی به restore؟
   **+ تصمیم فوری جدا:** باگ مسیر سوم حذف (طلب معلم از کلاس حذف‌شده باز می‌ماند) — تسک جداگانه بدهیم؟

---

## ۶) پیش‌قدم‌های پیشنهادی (ترتیب اجرا در تسک‌های بعدی)

1. **تصمیم‌های محصولی بخش ۱۰-۱ تا ۱۰-۵ را بگیرید** (بدون آن هر پیاده‌سازی، حدس است).
2. اگر «فاز ۱» تأیید شد: یک تسک کوچک = endpoint متادیتا + تست‌ها + به‌روزرسانی آگاهانه‌ی `test_8`.
3. **باگ مسیر سوم حذف** (طلب باز از کلاس حذف‌شده) را جدا و زودتر تعیین تکلیف کنید — این باگ امروز در محصول هست.
4. اگر «فاز ۲» خواسته شد: اول **دفتر کلّ حذف** در سمت حذف، بعد restore. بدون دفتر کل، restore کامل ممنوع بماند.

---

## ۷) وضعیت این تسک

- ✅ فقط ممیزی + اجرای probe روی DB موقت.
- ✅ صفر تغییر در کد production، صفر migration، صفر تغییر داده، صفر endpoint جدید.
- ✅ هیچ چیزی از snapshot حدس زده نشد و هیچ عملیات hard delete/restore خودکار اجرا نشد.
- ✅ DB واقعی `gaj_db.db` دست‌نخورده (md5 `f048f8d118b33c4eaa944490594121d7`).
- **Commit SHA:** در گزارش نهایی پس از commit ثبت می‌شود؛ SHA داخل همان commit قابل درج نیست.
- **وضعیت Push:** در گزارش نهایی اعلام می‌شود.
- **Commit message (طبق دستور):** `chore: document archived class restore design`
- **Branch:** `arena/01a0bf8d-kharazmiapp` — PR/merge بدون دستور صریح ساخته نمی‌شود.
