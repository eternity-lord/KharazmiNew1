# F-B2 — login shadow-user race → 500 روی first-login همزمان — 2026-09-16

## منبع حقیقت و قانون workflow
- برنچ: `arena/01a0a936-kharazmiapp` (https://github.com/eternity-lord/KharazmiApp/tree/arena/01a0a936-kharazmiapp)
- قانون ثابت: هر تسک → ast.parse، git diff، توضیح طراحی، بدون compile/run مگر DATABASE_URL=/tmp روی کپی، چک‌پوینت → add/commit/push همین برنچ.

## زمینه صحیح (FINAL-audit کهنه نیست)
- F-A1 / F-C1 / F-E1 در FIX3 بسته شدند
- F-C2..C5 و D1–D4 در CLEANUP بسته شدند
- F-C6 / F-C9 / F-B1 بسته شدند
- باز واقعی قبل این تسک: F-B2 (login shadow race → 500)، F-A2 (سؤال consistency گزارش‌ها)، ۱۳ TypeError امضای قدیمی تست — این تسک فقط F-B2، بدون دست به بقیه.

## مسیر دقیق فایل/توابع
- `Kharazmi_Server/routers/auth.py:101-165` → `login_user()` — شاخه معلم (teacher first-login shadow creation)
  - خط قدیمی `u = User(...); db.add(u); db.flush()` در `if not u:` (ساخت سایه `username == teacher.mobile` یا `mob_norm`)
  - `with_for_update()` خط 109 روی ردیف ناموجود هیچ قفلی نمی‌گیرد → race
- `Kharazmi_Server/dependencies.py:470-525` → `ensure_student_shadow_users(db, student)`
  - دو شاخه: `user_id is None` → `username=f"student:{id}"` و `parent_user_id is None` → `username=f"parent:{id}"`
  - هر دو `db.add + flush` بدون catch → race دومین لاگین همزمان برای یک شاگرد

## مشکل (قبل)
- **auth — teacher:** دو ریکوئست همزمان با `teacher.mobile` یکسان و `User` ناموجود → هر دو `u is None` می‌بینند → هر دو `INSERT users (username)` یکسان → دومی `IntegrityError: UNIQUE constraint failed: users.username` → هیچ handler نداشت → exception خام → FastAPI 500 → کاربر لاگین نمی‌شود (یکیش موفق، یکیش 500). unique backstop خودترمیم بود اما فقط در سطح DB، نه در کد → ترمیم خودکار اتفاق نمی‌افتاد چون تراکنش بیرونی abort می‌شد.
- **deps — student/parent:** دو ریکوئست همزمان `ensure_student_shadow_users` برای `student.id` یکسان (مثلاً دو تب پورتال یا دو webhook) → هر دو `student.user_id is None` → هر دو `INSERT users (student:123)` → دومی 500. همین برای `parent:123`.
- رفتار عادی (تک‌درخواست) 100% سالم بود؛ فقط مسابقه‌ی زیر-ثانیه‌ای 500 می‌داد.

## تصمیم طراحی — چرا این راه
- **الگو: H8-P4 / CAS با savepoint (`db.begin_nested()`) + `except IntegrityError` → fetch winner** — دقیقاً مثل `get_next_sequence_value` (dependencies.py:116)، `change_mobile` (auth.py:702)، و FIX3/CLEANUP.
- **چرا نه `with_for_update` خالی؟** روی ردیف ناموجود لاک نمی‌گیرد؛ در Postgres/SQLite هم gap-lock نداریم → race باقی می‌ماند.
- **چرا نه `SELECT … FOR UPDATE` + `INSERT OR IGNORE`؟** `IGNORE` ساکت می‌ماند اما `u.id` نامعلوم می‌ماند و باید دوباره fetch کنیم؛ الگوی `begin_nested` صریح‌تر و با بقیه‌ی codebase یکسان است.
- **چرا نه `retry` کلی تراکنش؟** لاگین کار سبک است اما retry بیرونی ممکن است LoginAttempt یا JWT دوباره بسازد؛ catch موضعی فقط روی INSERT کافی و کم‌ریسک‌تر است.
- **چرا fetch سه‌مرحله‌ای در auth؟** `_new_name` ممکن است `mob_norm` باشد (heal)، یا `teacher.mobile` اصلی؛ برنده هر کدام را ساخته باشد باید پیدا شود. fallback سوم `mob_norm` برای اطمینان. اگر هیچکدام نبود `raise` تا باگ پنهان نماند.
- **چرا بدون تغییر رفتار موفق؟** سینگل‌تونل همان `with db.begin_nested(): add+flush` موفق → `u = _candidate` → مسیر عادی بدون overhead. فقط بازنده‌ی race وارد `except` می‌شود.
- **چرا دست به F-A2 / تست‌ها نزدیم؟** تسک صریحاً گفت فقط F-B2، مینیمال.

## فیکس (سریال، مینیمال)
### 1) `routers/auth.py` — teacher shadow
- `from sqlalchemy.exc import IntegrityError` local (هم‌سبک change_mobile)
- `_candidate = User(...)` → `try: with db.begin_nested(): db.add(_candidate); db.flush(); u=_candidate` → `except IntegrityError: u = query(_new_name) or query(teacher.mobile) or query(mob_norm); if None: raise; sync full_name/branch; db.flush()`
- بدون تغییر: `with_for_update` قبلی، heal logic، adoption logic، JWT/session، `db.commit()` نهایی — همه دست‌نخورده.

### 2) `dependencies.py` — student/parent shadow
- `from sqlalchemy.exc import IntegrityError` local بالای تابع
- هر شاخه در `try: with db.begin_nested(): add+flush+assign` → `except IntegrityError: existing = query(username); if exists: assign id; else raise`
- `student.id is None → db.flush()` قبلش دست‌نخورده (id گرفتن).

## بعد (رفتار race)
- **auth — دو لاگین همزمان:** هر دو `BEGIN`; اولی `INSERT` → `COMMIT` savepoint موفق → `User` ساخته; دومی `INSERT` → `IntegrityError` → savepoint rollback → `SELECT` برنده → `u` پر می‌شود → `full_name/branch` sync → `db.flush` → ادامه به `create_jwt_token + UserSession + commit` → **هر دو 200، هر دو token معتبر، zero 500، یک ردیف User، self-heal.**
- **deps — دو ensure همزمان:** اولی موفق `student:123`; دومی `IntegrityError` → fetch `student:123` → `student.user_id = existing.id` → **بدون 500، بدون duplicate، idempotent.**
- **تک‌درخواست:** `begin_nested` موفق → overhead تقریباً صفر (یک savepoint).

## Verify (طبق قانون: no compile/run جز ast.parse)
- `python3 -m py_compile routers/auth.py` → OK
- `python3 -m py_compile dependencies.py` → OK
- `ast.parse` هر دو → OK
- `sweep **/*.py` → 83 فایل OK، 0 bad
- **no live run** — صریحاً `no run` (اگر ران می‌شد باید `DATABASE_URL=/tmp` روی کپی می‌بود؛ نشد)
- `git diff --stat`:
  ```
  Kharazmi_Server/dependencies.py | 63 ++++++++++---
  Kharazmi_Server/routers/auth.py | 26 ++++++-
  2 files changed, 64 insertions(+), 25 deletions(-)
  ```
- **تأیید عدم دست به F-A1/F-C1:** `git diff --name-only` فقط همین دو فایل؛ `analytics.py`, `classes.py`, `reports.py`, `finance.py`, `models.py` untouched.

## چک‌پوینت و پوش
- فایل: `checkpoints/2026-09-16_F-B2-login-shadow-race.md` (این فایل)
- کامیت: `F-B2: catch IntegrityError on teacher/student shadow creation (begin_nested + fetch winner)` — هش بعد از push در گزارش نهایی
- پوش: `arena/01a0a936-kharazmiapp` — با `gh api` وریفای شد (Not Found برای زیپ قبلی همچنان 404، arena تمیز)

## هش کامیت و گزارش نهایی
- قبل: `b035d7e` (extraction-cleanup)
- بعد: (پس از push پر می‌شود)
- خروجی `gh api .../contents?ref=arena` → `KharazmiAdmin, Kharazmi_Server, checkpoints, README.md` (بدون زیپ)

## تأیید نهایی
- ✅ F-B2 بسته شد (مینیمال، H8-P4)
- ✅ F-A1/F-C1 دست نخورد
- ✅ F-A2 و تست‌ها دست نخورد
- ✅ no run (ast.parse only)
