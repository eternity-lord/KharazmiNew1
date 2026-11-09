# F-A2 — گزارش‌ها: ناهم‌سازی دسترسی revenue/settlements vs financial_summary — فاز ۱ تحلیل (بدون کد) — 2026-09-16

## منبع حقیقت و قانون workflow
- برنچ: `arena/01a0a936-kharazmiapp` (https://github.com/eternity-lord/KharazmiApp/tree/arena/01a0a936-kharazmiapp)
- قانون: ast.parse روی فایل تغییرکرده (فاز ۱ کد نخورده → N/A)، git diff، توضیح طراحی داخل چک‌پوینت، ران فقط با DATABASE_URL=/tmp روی کپی DB، چک‌پوینت → add/commit/push همین برنچ.

## زمینه
- F-B2 و 13 TypeError بسته شدند (268 pass, `5b25e02`)
- FINAL-audit S1 — سؤال F-A2: `GET /finance/reports/revenue_summary` + `GET /finance/reports/teacher_settlements_summary` → ADMIN-only، در مقابل `GET /reports/financial_summary` → staff+teacher (admin/secretary/teacher). عمدی یا leftover؟

## فاز ۱ — مسیر دقیق هر سه اندپوینت (وابسته‌ها)

| # | متد + مسیر | فایل:خط | تابع | Dependency گارد | نقش‌های مجاز (فعلی) |
|---|------------|----------|-------|----------------|---------------------|
| 1 | `GET /finance/reports/revenue_summary` | `Kharazmi_Server/routers/finance.py:2340-2392` | `get_revenue_summary(db, _: check_admin_access)` | `check_admin_access` → `sub_role == "admin"` فقط | **admin فقط** (secretary 403, teacher 403, student/parent 401→403) |
| 2 | `GET /finance/reports/teacher_settlements_summary` | `Kharazmi_Server/routers/finance.py:2394-2445` | `get_teacher_settlements_summary(db, _: check_admin_access)` | `check_admin_access` → `sub_role == "admin"` فقط | **admin فقط** |
| 3 | `GET /reports/financial_summary` | `Kharazmi_Server/routers/reports.py:410-485` | `get_financial_summary(user_type, teacher_id, year, month, branch_id, authorization, db, sub_role: check_user_login)` | `check_user_login` → هر login معتبر، سپس `if sub_role not in ("admin","secretary","teacher"): 403` | **admin, secretary, teacher** (student/parent 403، temp_parent 403) |

### جزئیات گارد

- `check_admin_access` (`dependencies.py:125-145`): 401 اگر توکن نباشد/بد باشد، سپس `User` lookup، سپس `sub_role != "admin"` → 403. سخت‌گیرترین.
- `check_admin_or_secretary_access` (در جاهای دیگر): `sub_role in ("admin","secretary")` — **این دو endpoint از آن استفاده نمی‌کنند**، عمداً admin-only هستند.
- `check_user_login` (`dependencies.py:190-210`): 401 اگر توکن نباشد/بد باشد، سپس `User` lookup، سپس فقط اگر `teacher` و `teachers_active == False` → 403 (تعلیق کلی معلمان). سپس `financial_summary` خودش `if sub_role not in ("admin","secretary","teacher"): 403` را می‌زند؛ یعنی `student/parent` حتی با توکن معتبر 403.

## چه نقشی چه داده‌ای می‌بیند

### 1) `revenue_summary` (ADMIN-only)
- **ورودی:** هیچ پارامتری جز `db` (نه `branch_id`، نه `authorization`).
- **خروجی:**
  ```
  {
    revenue_by_wallet: { teacher_wallet: {cash, card, online, total}, institute_wallet: {...} },
    totals: { total_revenue, refund_count, refund_total_amount }
  }
  ```
- **حساسیت:** مجموع گردش مالی کل مؤسسه به تفکیک کیف پول (معلم/آموزشگاه) و روش پرداخت (نقدی/کارت/online) + تعداد/مبلغ استرداد. بدون PII مستقیم (نه mobile، نه card)، اما **مجموع مالی کل** — حساس برای نشت رقابتی.
- **شعبه:** **بدون branch isolation** — `db.query(Transaction).filter(is_deleted==False, is_reversed==False, type=="deposit")` روی کل DB، بدون `branch_id` فیلتر. در استقرار تک‌شعبه مشکلی نیست؛ در چندشعبه، admin همه شعبه‌ها را می‌بیند (برای admin درست است). اگر به secretary شعبه‌محور باز شود، نشت بین‌شعبه‌ای می‌دهد مگر branch filter اضافه شود.
- **چه کسی محروم:** `secretary` (منشی) — در حالی که `secretary` در `ROLE_PERMISSIONS` تقریباً همه چیز `admin` را دارد جز `settings` و `teacher.create` و ... ولی اینجا 403 می‌گیرد.

### 2) `teacher_settlements_summary` (ADMIN-only)
- **ورودی:** هیچ پارامتر (نه branch، نه teacher_id).
- **خروجی:** آرایه برای **همه معلمان** (`Teacher.all()`):
  ```
  [{ teacher_id, teacher_name, mobile, card_number, session_count, wallet_balance, pending_total_amount, settled_total_amount, earned_total_amount, last_settled_at }, ...]
  ```
- **حساسیت:** **بسیار حساس — PII + مالی**:
  - `mobile` (شماره موبایل معلم — قابل سوءاستفاده برای اسپم/فیشینگ)
  - `card_number` (شماره کارت بانکی — PII مالی سطح بالا، حتی اگر `"---"` fallback داشته باشد)
  - `pending/settled/earned` (طلب فعلی، تسویه‌شده، جمع — اطلاعات حقوق)
  - `session_count` + `last_settled_at`
  - برای **همه** معلمان، یک‌جا.
- **شعبه:** **بدون branch isolation** — `Teacher.all()` + `Course.filter(teacher_id)` بدون فیلتر branch. در چندشعبه، admin همه معلمان همه شعبه‌ها را می‌بیند.
- **چه کسی محروم:** `secretary` و `teacher` (teacher حتی طلب خودش را اینجا نمی‌بیند؛ باید از `get_pending_settlement` یا `financial_summary?user_type=teacher` ببیند).

### 3) `reports/financial_summary` (staff+teacher)
- **ورودی:** `user_type="institute"|"teacher"`, `teacher_id?`, `year?`, `month?`, `branch_id?`, `authorization` (Header), `db`, `sub_role`
- **گارد ثانویه داخل تابع:**
  1. `if sub_role not in ("admin","secretary","teacher"): 403` → student/parent حتی با توکن 403.
  2. `resolved_branch = get_user_branch_filter(db, authorization, branch_id)` → اگر کاربر `admin/secretary/teacher` شعبه داشته باشد، `branch_id` ورودی override می‌شود به شعبه خودش (isolation).
  3. `logged_teacher = get_logged_in_teacher(db, authorization)` → اگر معلم لاگین کرده باشد، **اجبار**: `user_type="teacher"` و `teacher_id = logged_teacher.id` (معلم نمی‌تواند `institute` ببیند، و نمی‌تواند `teacher_id` دیگری را ببیند).
- **خروجی (scoping دقیق):**
  - اگر `user_type=="institute"` (فقط admin/secretary می‌رسند اینجا، چون teacher强制 می‌شود به teacher):
    ```
    { user_type:"institute", year, month, monthly:{total, collected, uncollected}, yearly:{...} }
    ```
    - `total` = `calculate_institute_session_revenue(db, start_date, end_date, resolved_branch)` — مجموع جلسات برگزار‌شده در **شعبه‌ی resolved** (اگر `resolved_branch` داشته باشد فقط همان شعبه).
    - `collected` = واریزی‌های همان شعبه/بازه.
  - اگر `user_type=="teacher"` (admin/secretary می‌توانند هر `teacher_id` را بپرسند؛ teacher فقط خودش):
    ```
    { user_type:"teacher", teacher_id, teacher_name, monthly:{...}, yearly:{...} }
    ```
    - محاسبه فقط روی `SessionLog` همان `teacher_id` (یا `logged_teacher.id` اگر teacher).
- **حساسیت:** **کم تا متوسط** — فقط **aggregate ماهانه/سالانه** (total/collected/uncollected) بدون PII (نه mobile، نه card)، بدون لیست تراکنش، بدون نام دانش‌آموز. `teacher_name` فقط وقتی `user_type==teacher`.
- **شعبه:** **با branch isolation کامل** — هم `resolved_branch` روی institute، هم `teacher_id` روی teacher. نشت بین‌شعبه‌ای ندارد.
- **چه کسی محروم:** `student/parent` 403 (درست)؛ `secretary` مجاز (branch خودش)؛ `teacher` فقط خودش.

## آیا نشت بین‌شعبه‌ای / داده حساس هست؟

| اندپوینت | نشت شعبه فعلی | داده حساس | برای نقش فعلی مشکل دارد؟ |
|-----------|---------------|-----------|---------------------------|
| `revenue_summary` | **بله بالقوه** — بدون branch filter، ولی چون فقط admin می‌بیند و admin سراسری است، **در تک‌شعبه فعلی مشکلی نیست**؛ در چندشعبه اگر به secretary باز شود بدون فیلتر، **بله نشت می‌دهد**. | مجموع مالی کل (بدون PII) — متوسط | نه برای admin-only؛ بله اگر به secretary بدون فیلتر باز شود |
| `teacher_settlements_summary` | **بله بالقوه** — بدون branch filter، ولی admin سراسری است؛ اگر به secretary/teacher باز شود بدون فیلتر، همه معلمان همه شعبه‌ها نشت می‌کند. | **PII بالا** (mobile + card_number) + حقوق برای **همه** | **بله اگر باز شود بدون محدودسازی** — حتی admin-only هم در چندشعبه ممکن است بخواهد per-branch |
| `financial_summary` | **نه** — `get_user_branch_filter` + teacher self-lock | aggregate بدون PII | **نه** — درست isolation شده |

## مقایسه با سایر گزارش‌ها (برای قضاوت leftover vs عمدی)

- `reports/financial_report`, `reports/debtors_report`, `analytics/*` معمولاً `check_admin_or_secretary_access` (staff) هستند — یعنی secretary معمولاً مالی می‌بیند.
- `finance` depositها هم `admin_or_secretary` هستند.
- پس اینکه `revenue_summary` فقط admin باشد، **غیرمعمول** است نسبت به خواهرانش؛ **ممکن است leftover** باشد از زمانی که `secretary` نقش جدید بود و کسی `finance/reports/*` را آپدیت نکرد.
- `teacher_settlements_summary` با PII کارت، **admin-only بودن منطقی‌تر** است (حتی secretary شاید نباید کارت همه را ببیند)؛ اما `secretary` در بسیاری سیستم‌ها حقوق می‌دهد و نیاز دارد.

## پیشنهاد واضح A/B/C

### A) عمدی بماند — **توصیه اصلی فاز ۱ (محافظه‌کارانه)**
- **معنا:** هیچ کد نزن؛ `revenue_summary` و `teacher_settlements` همان `check_admin_access` بمانند.
- **چرا:**
  - `revenue_summary`: مجموع کل گردش مالی — تصمیم مدیریتی که فقط admin ببیند، منطقی است؛ secretary از `financial_summary` (ماهانه institute) نیازش را می‌گیرد (همان total/collected ولی per-month با branch). نیازی به duplicate نیست.
  - `teacher_settlements_summary`: لیست همه معلمان با `mobile` و `card_number` — **PII سطح بالا**؛ باز کردن حتی برای `secretary` بدون audit یا masking ریسک دارد. Teacher هم از `get_pending_settlement(teacher_id=self)` و `financial_summary?user_type=teacher` طلب خودش را می‌بیند؛ نیازی به دیدن همه ندارد.
  - **بدون branch filter فعلی:** اگر باز کنیم بدون اضافه کردن `branch_id`، نشت بین‌شعبه‌ای قطعی است — پس بستن به admin امن‌تر است تا وقتی نیاز branch‌دار ثابت نشود.
  - **سازگاری با FINAL-audit:** S1 خودش آن را «سؤال» نامید نه «باگ». Zero کد، zero ریسک، و 268 تست دست‌نخورده می‌ماند.
- **هزینه:** `secretary` برای revenue کلی باید از admin بپرسد یا از `financial_summary` ماهانه استفاده کند — قابل قبول.

### B) teacher/secretary هم دسترسی محدود بگیرند — **اگر نیاز عملیاتی ثابت شود**
- **معنا:**
  - `revenue_summary`: گارد شود `check_admin_or_secretary_access` + اضافه کردن `branch_id? + authorization` و `resolved_branch` فیلتر روی همه `Transaction` کوئری‌ها (مثل `financial_summary`). `secretary` فقط شعبه خودش را ببیند؛ `teacher` همچنان 403 (نیازی ندارد).
  - `teacher_settlements_summary`: گارد شود `check_admin_or_secretary_access` برای secretary + `check_user_login` با شاخه‌بندی برای teacher:
    - `admin`: همه (مثل الان)
    - `secretary`: فقط معلمان `branch_id == resolved_branch` + **حذف یا mask `card_number`** (مثل `****1234`) تا PII کم شود
    - `teacher`: فقط ردیف خودش (`teacher_id == logged_teacher.id`)، بدون `mobile` دیگران، و `card_number` خودش (یا mask)
- **چه فیلدی محدود شود:** `mobile` و `card_number` برای secretary/teacher باید محدود/mask شود؛ `pending/settled` برای teacher فقط خودش.
- **چرا B منطقی است اگر:** آموزشگاه چندشعبه شود و secretary هر شعبه باید revenue شعبه خودش را ببیند، یا teacher بخواهد settlement خودش را در لیست ببیند بدون رفتن به endpoint جداگانه.
- **ریسک B:** نیاز به 2 فایل تغییر + تست جدید branch isolation؛ اگر mask نشود، PII نشت می‌کند.

### C) همه staff مثل `financial_summary` — **توصیه نمی‌شود**
- **معنا:** هر دو endpoint گارد شوند `check_user_login` + `if sub_role not in ("admin","secretary","teacher"):403` مثل `financial_summary`، بدون branch یا teacher self-filter اضافی.
- **چرا نه:**
  - `revenue_summary` بدون branch filter → secretary یک شعبه، revenue همه شعبه‌ها را می‌بیند — **نشت بین‌شعبه‌ای**.
  - `teacher_settlements_summary` بدون teacher self-filter → teacher همه معلمان (با mobile/card) را می‌بیند — **نشت PII بحرانی**.
  - این دقیقاً چیزی است که L14 تلاش کرد ببندد؛ C آن را برمی‌گرداند.

## توصیه نهایی فاز ۱
- **توصیه: A) عمدی بماند — کد نزن.**
- دلیل: امن‌ترین، بدون branch leak، بدون PII leak، بدون تغییر 268 تست، و با نیاز فعلی (secretary از `financial_summary` و teacher از `financial_summary/pending_settlement` کارش راه می‌افتد) همخوان است.
- **اگر بعداً نیاز B ثابت شد** (مثلاً مدیر گفت secretary باید revenue شعبه خودش را ببیند)، آنگاه با تسک جداگانه B را پیاده کن: `revenue_summary` → `admin_or_secretary + branch filter`، `teacher_settlements_summary` → `admin_or_secretary (branch) + teacher self (mask card)` — نه C.

## Verify فاز ۱
- `ast.parse` روی فایل‌های تغییرکرده: **N/A — هیچ کد تغییر نکرده** (فقط تحلیل)
- `git diff --stat` قبل کامیت چک‌پوینت: باید `0 files changed` جز خود چک‌پوینت باشد
- `pytest` با `DATABASE_URL=/tmp`: **نیازی نبود** (چون کد نخورده) — سوئیت قبلی `268 passed` دست‌نخورده می‌ماند
- `gh api` وریفای push: بعد از push چک می‌شود

## هش کامیت و گزارش نهایی
- قبل: `5b25e02` (tests align)
- بعد: (پس از push این چک‌پوینت)
- **فاز ۱ فقط، کد نخورده** — اگر کد زده می‌شد، diff خلاصه اینجا می‌آمد؛ چون نزدیم، صریح: **کد نخورده**
