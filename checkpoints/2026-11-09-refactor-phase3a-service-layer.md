# ۲۰۲۶-۱۱-۰۹ — ریفکتور فاز ۳a: تولد لایهٔ service و حذف وابستگیِ روتر→روتر

## خلاصهٔ عددی

| سنجه | قبل (پایان P2c) | بعد (P3a) |
| --- | --- | --- |
| `routers/admin.py` | 2990 خط | **2565** (−425) |
| `routers/finance.py` | 2839 خط | **2655** (−184) |
| `routers/classes.py` | 1539 خط | **1362** (−177) |
| `routers/attendance.py` | 1582 خط | **1461** (−121) |
| لایهٔ service | وجود نداشت | **`Kharazmi_Server/services/` — ۶ ماژول، ۱۱۰۸ خط** |
| وابستگیِ روتر→روتر برای این نام‌ها | ۸ import (در ۴ فایل) | **۰** |
| یافته‌های ruff | 251 | **251** (بدون تغییر) |
| خطاهای mypy | 727 / 32 فایل | **727 / 37 فایل** (۵ ماژولِ جدیدِ type-clean) |
| `Kharazmi_Server/tests` | 1279 passed | **1279 passed** |
| `tests/route_audit` | 249 passed | **249 passed** |
| `openapi.json` | — | **بایت‌به‌بایت یکسان** (۱۷۲۰۳ خط، diff = ۰) |
| ledger مسیرها (`server-routes-extracted.csv`) | — | یکسان **جز file:line** (۱۰۳/۲۲۱ جابه‌جا، ۰ تفاوت غیرخطی) |
| `validate_app_map.py` | — | `server_map_exact: true`, 221 route, 0 missing/stale |
| md5 `gaj_db.db` | — | بدون تغییر |

## ۱) چرا لایهٔ service و نه «پکیج‌کردنِ روترها»

یک راهِ بدیهی برای شکستنِ `admin.py` این بود که به‌جای فایل، پکیجِ `routers/admin/` بسازیم.
**ممکن نیست**: چند تستِ ساختاریِ این ریپو، خودِ *متنِ* فایل را با مسیر می‌خوانند —

```python
admin = read(os.path.join(ROOT, "routers", "admin.py"))      # test_group7_reports_admin.py
self.assertIn("check_scheduling_conflicts", admin)
attendance = py("routers/attendance.py")                      # test_group5_behavior.py
self.assertIn("LiveSession.course_id == identifier", attendance)
with open(_server_file("routers", "finance.py")) as f: ...    # test_audit.py
self.assertIn("from validation import", content)
```

پس فایل‌های روتر باید **همین‌نام و تک‌فایل** بمانند. راهِ درست — و همان چیزی که کاربر
خواست — جدا کردنِ *منطق دامنه* از *لایهٔ HTTP* است: handlerها (decorator + `Depends` +
احراز مجوز + شکل پاسخ) در روتر می‌مانند و منطق به `services/` می‌رود.

## ۲) شش ماژولِ service که ساخته شد

| ماژول | از | محتوا | خط |
| --- | --- | --- | --- |
| `services/class_archive.py` | `admin.py` | گزارش فقط‌خواندنیِ کلاس‌های حذف‌شده: متادیتای حذف، اسنپ‌شات مالی لحظهٔ حذف، تجمیع جلسات/حضور و غیاب، نرمال‌سازیِ «منبعِ بازیابی» با قاعدهٔ fail-closed برای legacy | 467 |
| `services/debtor_report.py` | `finance.py` | منبع یگانهٔ «ردیف بدهکار» + دسته‌های قدمت بدهی (`DEBT_AGE_BUCKETS`) | 201 |
| `services/live_session.py` | `attendance.py` | آجرهای جلسهٔ زنده: تسخیر اتمیک LIVE→FINALIZING، upsert ردیف حضور با قید یکتا، گارد مالکیت کلاس، تاریخ کانونیک، تشخیص جلسهٔ تکراری، `DuplicateSessionDate` | 171 |
| `services/class_lifecycle.py` | `classes.py` | اسنپ‌شات/اجرای حذف کلاس و ثبت تصمیم در `ActivityLog` | 147 |
| `services/scheduling.py` | `classes.py` | پارسِ بازهٔ ساعت، تداخل روزهای هفته (زوج/فرد)، یافتن کلاس‌های متعارض | 85 |
| `services/branch_scope.py` | `finance.py` | `get_user_branch_filter` — دامنهٔ شعبهٔ مؤثرِ کاربر (یک قاعدهٔ **عرضی**) | 37 |

انتقال **بایت‌به‌بایت** و با اسکریپتِ AST انجام شد (بازهٔ دقیق هر تعریف + کامنت‌های
چسبیده به آن برداشته شد، importهای لازم از جدولِ import خودِ روتر مشتق شد) — نه کپیِ
دستی، تا خطای رونویسی صفر باشد.

## ۳) مهم‌ترین دستاورد معماری: حذف وابستگیِ روتر→روتر

پیش از این، شش روتر برای یک قاعدهٔ عمومی مجبور بودند از **روترِ مالی** import کنند:

```python
from routers.finance import get_user_branch_filter   # در admin, analytics, crm, exports, reports, students
from routers.finance import build_debtor_rows        # در exports, reports — با importِ lazy «برای فرار از چرخه»
from routers.classes import check_scheduling_conflicts          # در admin (دو بار)
from routers.classes import _apply_class_deletion, _build_class_deletion_snapshot   # در admin
```

هیچ‌کدام از این مصرف‌کننده‌ها با «مالی» یا «کلاس» کار ندارند؛ آن‌ها یک قاعدهٔ عرضی
(شعبهٔ کاربر) یا یک گزارشِ مشترک می‌خواستند. آن `# lazy: بدون چرخهٔ import`ها نشانهٔ
خودِ مشکل بودند: وابستگیِ روتر→روتر که برای دورزدنِ چرخه، import را به زمانِ اجرا
موکول می‌کرد. حالا هر ۸ مورد مستقیم از لایهٔ service خوانده می‌شوند:

```python
from services.branch_scope import get_user_branch_filter      # REFAC(P3a)
from services.debtor_report import build_debtor_rows
from services.scheduling import check_scheduling_conflicts
from services.class_lifecycle import _apply_class_deletion, _build_class_deletion_snapshot
```

و چون `services/*` به هیچ روتری وابسته نیست (تنها استثنا یک importِ lazyِ از‌قبل‌موجود
داخل `_verify_live_course_teacher` است)، چرخه‌ای هم وجود ندارد.

## ۴) سازگاری عقب‌رو: هیچ مسیرِ importی نشکست

روترِ مبدأ، نام‌های منتقل‌شده را import می‌کند (که هم مصرفِ داخلیِ خودش است و هم
**بازصادرات**). بنابراین همهٔ این‌ها دست‌نخورده کار می‌کنند:

```python
from routers.attendance import DuplicateSessionDate, _get_live_max_minutes, _now_str, \
    claim_live_session_for_finalize, finalize_live_session     # importِ lazy در main.py:643
attendance.finalize_live_session(db, live)                     # test_attendance_sessions_audit.py:1411
from routers.finance import build_debtor_rows, get_user_branch_filter, DEBT_AGE_BUCKETS
from routers.classes import check_scheduling_conflicts, _apply_class_deletion
```

## ۵) دو چیزی که عمداً در روتر ماند (و چرا)

`services/live_session.py` همهٔ آجرهای جلسهٔ زنده را گرفت **جز دو مورد**:

* **`finalize_live_session`** — محاسبهٔ مالی را به `submit_session_and_calculate`
  واگذار می‌کند که خودش یک **handler** در همان روتر است. انتقالش یا چرخهٔ import
  می‌ساخت یا وابستگیِ service→router (که خلافِ جهتِ درستِ لایه‌هاست). حلِ اصولی‌اش
  «معکوس‌کردنِ آن وابستگی» است: بدنهٔ آن handler به service برود تا هم route و هم
  `finalize_live_session` مصرف‌کنندهٔ service شوند ⇒ کارِ **P3b**.
* **`_resolve_live_session_for_action`** — علاوه بر همان وابستگی، یک تستِ ساختاری
  دقیقاً این نام و عبارت `LiveSession.course_id == identifier` را در متنِ
  `routers/attendance.py` جست‌وجو می‌کند (`test_group5_behavior.py:97-98`).

به همین دلیل `attendance.py` فقط ۱۲۱ خط کوچک شد؛ سهمِ اصلیِ آن در P3b است.

## ۶) باگی که استخراجم ساخت و **تست‌ها ندیدند** — فقط ruff دید 🎯

اسکریپتِ استخراج، importها را از جدولِ نام‌های روتر مشتق می‌کرد. `routers/attendance.py`
یک importِ **با alias** داشت:

```python
import time as time_module          # در روتر
```

اسکریپت alias را دور انداخت و در service نوشت `import time`، در حالی که کدِ منتقل‌شده
`time_module.time()` را صدا می‌زد ⇒ `NameError` در زمانِ اجرا.

نکتهٔ ترسناک: **هر دو سوئیت سبز ماندند** (1279 + 249). دلیلش short-circuit بود:

```python
start_ts = float(started_at_ts or time_module.time())
```

در همهٔ تست‌ها `started_at_ts` مقدار داشت، پس `time_module.time()` **هرگز ارزیابی نشد**.
یعنی یک ردیفِ legacyِ بدون timestamp می‌توانست در پروداکشن ۵۰۰ بگیرد و هیچ تستی
نمی‌فهمید. آنچه گرفتش `ruff --select F821` بود:

```
services/live_session.py:104:39: F821 Undefined name `time_module`
```

**درسِ ثبت‌شده:** در هر انتقالِ کد، `F821` (نامِ تعریف‌نشده) باید به‌عنوان گارد اجرا شود؛
سبز بودنِ تست‌ها برای این دسته از باگ‌ها کافی نیست، چون مسیرهای short-circuit و
شاخه‌های کم‌داده در سوئیت پوشش ندارند. بعد از رفع، آن شاخه مستقیماً امتحان شد:

```
_live_canonical_date(1, None)      -> 1405-08-18   # قبلاً NameError می‌داد
_live_canonical_date(1, 0)         -> 1405-08-18
_live_canonical_date(1, 1700000000)-> 1402-08-23
```

یک تلهٔ دوم هم همین‌جا رفع شد: `services` باید در `pyproject.toml` زیرِ
`known-first-party` ثبت می‌شد، وگرنه isort آن را third-party فرض می‌کرد و importش را
وسطِ بلوکِ `fastapi`/`sqlalchemy` می‌برد — یعنی مرزِ لایه‌ها در خودِ کد ناپدید می‌شد.

## ۷) قیدهای تست‌های ساختاری که طراحی را شکل دادند

پیش از هر جابه‌جایی، همهٔ تست‌هایی که *متنِ* روترها را می‌خوانند ممیزی شدند و این
توکن‌ها به‌عنوان «باید در همان فایل بماند» ثبت شد (همه امروز هم برقرارند — با اسکریپت
بررسی شد: `classes.py missing tokens: NONE ✓`):

| فایل | توکن‌های اجباری |
| --- | --- |
| `admin.py` | `attendance_missing`, `started_late`, `auto_ended`, `/admin/session_history{,/{session_id}/reopen}`, `StreamingResponse`, `check_scheduling_conflicts`, `action="class_approve"`, `action="class_reject"`, `financial_status`, `charge_amount`, `billed_attendance_count` |
| `classes.py` | `/classes/pending_approval{,/bulk_approve,/bulk_reject}`, `/classes/update`, `check_scheduling_conflicts`, `ActivityLog`, `conflict_course_ids`, `PERSIAN_DAY_NAMES`, `display_name(`, `days_of_week`, `class_time`, `capacity`, `teacher_id`, `is_paused`, و بعد از `@router.post("/enrollments/add_bulk")`: `added_count`, `rejected_count`, `reason`, `add_enrollment(` |
| `attendance.py` | `@router.post("/attendance/{session_id}/cancel_live")` (و در بدنه‌اش `"CANCELLED"` باشد و `finalize_live_session` **نباشد**)، `_resolve_live_session_for_action`, `LiveSession.course_id == identifier` |
| `finance.py` | `from validation import` |

دو موردِ ظریف:
* `check_scheduling_conflicts` با انتقال به service هم در `classes.py` و هم در `admin.py`
  دیده می‌شود (چون خطِ import خودش حاوی همان نام است) ⇒ گاردِ متنی برقرار می‌ماند.
* `test_tuition_installments_audit.py:684` روی `finance.ActivityLog` **monkeypatch**
  می‌گذارد و انتظار دارد مسیر پرداخت قسط `RuntimeError` بدهد. یعنی هر کدی که
  `ActivityLog` را در آن مسیر می‌سازد باید در زمانِ اجرا از فضای نامِ ماژولِ
  `routers.finance` خوانده شود ⇒ `pay_installment_manually` **نباید** از finance.py بیرون
  برود. این قید برای P3b ثبت شد.

## ۸) مرحلهٔ بعد (P3b) — شکستنِ بدنهٔ handlerها

چهار روتر هنوز بزرگ‌اند چون خودِ handlerها بزرگ‌اند. بزرگ‌ترین‌ها:

| handler | فایل | خط |
| --- | --- | --- |
| `payment_callback` | finance.py | 469 |
| `submit_payment` | finance.py | 339 |
| `restore_deleted_class` | admin.py | 334 |
| `submit_session_and_calculate` | attendance.py | 247 |
| `edit_past_session` | attendance.py | 235 |
| `refund_transaction` | finance.py | 188 |
| `get_student_full_profile` | admin.py | 180 |
| `update_transaction` | admin.py | 169 |
| `get_all_classes` | classes.py | 155 |
| `get_class_full_report` | classes.py | 153 |

نقشه: بدنهٔ هر کدام به تابعِ service برود و handler فقط «ورودی HTTP → فراخوانی service →
شکلِ پاسخ» شود. اولین هدف `submit_session_and_calculate` است، چون هم بزرگ است و هم
گرهِ `finalize_live_session` را باز می‌کند. قیدهای بالا (مخصوصاً monkeypatch روی
`finance.ActivityLog` و گاردهای متنی) در هر قدم رعایت می‌شوند.

## دستورهای بازتولیدِ راستی‌آزمایی

```bash
# سطح API باید بایت‌به‌بایت یکسان بماند
git worktree add --detach /tmp/baseN origin/main
(cd /tmp/baseN && DATABASE_URL=sqlite:////tmp/oa_b.db JWT_SECRET_KEY=x \
  /home/user/KharazmiNew1/.venv/bin/python /tmp/dump_openapi.py > /tmp/openapi_before.json)
DATABASE_URL=sqlite:////tmp/oa_a.db JWT_SECRET_KEY=x .venv/bin/python /tmp/dump_openapi.py > /tmp/openapi_after.json
diff /tmp/openapi_before.json /tmp/openapi_after.json          # ← باید خالی باشد

# گاردِ نامِ تعریف‌نشده (همین باگِ alias را گرفت؛ تست‌ها نمی‌گیرند)
.venv/bin/ruff check . --select F821        # ← فقط ۱ خطای از قبل موجود در routers/exams.py

# هر دو سوئیت (در دو فرایند جدا) + گارد دیتابیس واقعی
DATABASE_URL=sqlite:////tmp/a.db JWT_SECRET_KEY=x .venv/bin/python -m pytest Kharazmi_Server/tests -q
DATABASE_URL=sqlite:////tmp/b.db JWT_SECRET_KEY=x .venv/bin/python -m pytest tests/route_audit -q
md5sum Kharazmi_Server/gaj_db.db

# نقشهٔ مسیرها و ledger مشتق‌شده
.venv/bin/python scripts/validate_app_map.py
DATABASE_URL=sqlite:////tmp/e.db JWT_SECRET_KEY=x PYTHONPATH=Kharazmi_Server \
  .venv/bin/python Kharazmi_Server/scripts/extract_server_routes.py \
  --output docs/app-map/server-routes-extracted.csv
```
