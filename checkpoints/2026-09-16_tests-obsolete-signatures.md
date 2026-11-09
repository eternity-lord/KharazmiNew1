# Tests — هم‌ترازی امضای قدیمی (13× TypeError) — 2026-09-16

## منبع حقیقت و قانون workflow
- برنچ: `arena/01a0a936-kharazmiapp` (https://github.com/eternity-lord/KharazmiApp/tree/arena/01a0a936-kharazmiapp)
- قانون: هر فایل تغییرکرده → ast.parse، git diff، توضیح طراحی، تست فقط با DATABASE_URL=/tmp روی کپی DB، چک‌پوینت → add/commit/push همین برنچ. بدون دست به F-A2 و بدون ریفکتور بی‌ربط.

## زمینه
- F-B2 بسته شد (`482f60f` / begin_nested + IntegrityError)
- FINAL-audit: 253 pass /14 fail → بعد از FIX3/CLEANUP و reportlab نصب، سوئیت واقعی `268` تست شد → قبل این تسک: `13 fail (TypeError) + 255 pass`، بعد: `268 pass / 0 fail`
- reportlab قبلاً در requirements بود و در این ران نصب بود → فیل reportlab جدا نداشتیم؛ 13 تا همه TypeError امضا بودند.
- هدف: فقط هم‌ترازی حداقل تست با کد فعلی — نه تغییر منطق پول/auth مگر مجبور (فقط `analytics.py` داخلی).

## لیست دقیق 13 تست فیل‌شده (pytest -q با DATABASE_URL=/tmp قبل فیکس)
| # | فایل | تست | پیام TypeError |
|---|------|------|---------------|
| 1 | test_automation_analytics.py::test_analytics_exports | `export_analytics_excel` → داخلش `get_teachers_performance_analytics(..., _="admin")` | `got an unexpected keyword argument '_'` |
| 2 | test_classes.py::test_get_all_classes_and_details | `get_class_details(..., _="admin")` | `got an unexpected keyword argument '_'` |
| 3 | test_priority2_financial.py::test_financial_reads_share_active_transaction_filters | `finance.get_student_class_status(..., _="admin")` | `got an unexpected keyword argument '_'` |
| 4 | همان تست | `reports.get_student_statement(..., _="admin")` | `got an unexpected keyword argument '_'` |
| 5 | test_priority2_financial.py::test_statement_does_not_misassign... | `reports.get_student_statement(..., _="admin")` | `got an unexpected keyword argument '_'` |
| 6 | test_priority2_financial.py::test_cancelled_session_cannot_be_settled (x2) | `get_pending_settlement(..., _="admin")` | `got an unexpected keyword argument '_'` |
| 7 | test_reports.py::test_financial_summary_teacher_restriction (x3) | `get_financial_summary(..., current_username="teacher/admin")` | `got an unexpected keyword argument 'current_username'` |
| 8 | test_reports.py::test_get_logged_in_teacher_secretary_id_collision | `get_financial_summary(..., current_username="secretary")` | `got an unexpected keyword argument 'current_username'` |
| 9 | test_reports.py::test_student_statement (x2) | `get_student_statement(..., _="admin")` | `got an unexpected keyword argument '_'` |
| 10 | test_students.py::test_get_student_grades_and_installments | `get_student_grades(..., _="admin")` | `got an unexpected keyword argument '_'` |
| 11 | test_students.py::test_search_students | `search_students(..., _="admin")` | `got an unexpected keyword argument '_'` |
| 12 | test_teachers.py::test_get_teacher_profile (x2) | `get_teacher_profile(..., _="admin")` | `got an unexpected keyword argument '_'` |
| 13 | test_teachers.py::test_pending_settlement... (x3) | `get_pending_settlement(..., _="admin")` + `get_settlement_history` | `got an unexpected keyword argument '_'` |
| +1 اضافی بعد فیکس 13 | test_students.py::test_get_student_grades_and_installments | `get_student_installments(..., _="admin")` | `got an unexpected keyword argument '_'` (در ران دوم کشف شد) |

جمع: 13 اولیه + 1 کشف حین فیکس = 14 نقطه تماس، 13 تست.

## مقایسه امضا (کد فعلی vs تست قدیمی)

| تابع (روتر) | امضای فعلی (بعد L14) | امضای تست قدیمی | علت |
|---|---|---|---|
| `analytics.get_teachers_performance_analytics` | `(branch_id, limit, offset, authorization, db, sub_role)` | `(_, _="admin")` | L14/Y2: `_` → `sub_role` + `authorization` |
| `classes.get_class_details` | `(course_id, db, authorization, sub_role)` | `(_="admin")` | L14/Y3: کلاس فقط کارکنان/معلم مالک |
| `finance.get_student_class_status` | `(student_id, course_id, course_code, db, authorization, sub_role)` | `(_="admin")` | L14/Y4: check_student_access |
| `reports.get_student_statement` | `(student_id, db, authorization, role)` | `(_="admin")` | L14/Y1: role=admin/teacher=check |
| `teachers.get_pending_settlement` | `(teacher_id, start_date, end_date, db, authorization, sub_role)` | `(_="admin")` | L14/Y2: admin/secretary/teacher خود |
| `reports.get_financial_summary` | `(user_type, teacher_id, year, month, branch_id, authorization, db, sub_role)` | `(current_username=)` | L14/Y4: current_username → sub_role (همان نقش) |
| `students.search_students` | `(query, db, sub_role)` | `(_="admin")` | L14/Y1: جستجوی PII فقط کارکنان |
| `students.get_student_grades` | `(student_id, db, authorization, role)` | `(_="admin")` | L14/Y1: check_student_access |
| `students.get_student_installments` | `(student_id, db, authorization, role)` | `(_="admin")` | L14/Y1: همین |
| `teachers.get_teacher_profile` | `(teacher_id, db, authorization, sub_role)` | `(_="admin")` | L14/Y2: پروفایل کارت‌دار |
| `teachers.get_settlement_history` | `(teacher_id, db, authorization, sub_role)` | `(_="admin")` | همان |

## تصمیم طراحی — چرا تست نه کد (جز یک مورد اجبار)
- **ترجیح تست:** این توابع در L14 عمداً از `_: Depends(check_admin...)` یا `current_username` به `authorization + sub_role/role` مهاجرت کردند تا IDOR و branch isolation درست شود. برگرداندن `_` به کد، گارد امنیتی را دور می‌زند؛ پس تست باید هم‌تراز شود.
- **اجبار کد (تنها یک خط):** `routers/analytics.py:493` داخل `export_analytics_excel` هنوز `get_teachers_performance_analytics(..., _="admin")` صدا می‌زد — این کال داخلی پرود است، نه تست؛ با امضای جدید 500 می‌داد (همین تست 1 را فیل می‌کرد). پس فقط همان یک خط به `authorization=authorization, sub_role="admin"` تغییر کرد — حداقل و اجبار.
- **حداقل test change:** هر تست فقط کی‌ورد قدیمی را به کی‌ورد جدید تبدیل کرد، بدون تغییر assert یا منطق؛ توکن‌های موجود در setUp (`admin-token`, `teacher-token`, `p2-admin-token`, `auth`) دوباره استفاده شدند.
- **بدون دست به F-A2 و بدون ریفکتور:** هیچ تغییر در `finance.submit_payment`, `auth.login`, `analytics.dashboard` و ... نشد.

## تغییرات سریال (6 فایل، 22 خط)

### 1) `Kharazmi_Server/routers/analytics.py` (1 خط — تنها تغییر پرود)
- `teachers_perf = get_teachers_performance_analytics(..., _="admin")` → `teachers_perf = get_teachers_performance_analytics(..., authorization=authorization, sub_role="admin")`
- دلیل: کال داخلی پرود با `_` دیگر با امضای `sub_role` جور نبود؛ export اکسل 500 می‌داد.

### 2) `test_classes.py` (1)
- `get_class_details(..., _="admin")` → `get_class_details(..., authorization="Bearer admin-token", sub_role="admin")`

### 3) `test_priority2_financial.py` (6)
- `finance.get_student_class_status(..., _="admin")` → `..., authorization=auth, sub_role="admin"`
- `reports.get_student_statement(..., _="admin")` (x2) → `..., authorization=auth / "Bearer p2-admin-token", role="admin"`
- `get_pending_settlement(..., _="admin")` (x2) → `..., authorization="Bearer p2-admin-token", sub_role="admin"`
- `reports.get_financial_summary(..., current_username="p2-admin")` → `..., sub_role="admin"`

### 4) `test_reports.py` (6)
- `get_financial_summary(..., current_username="teacher/admin/secretary")` (x4) → `..., sub_role="teacher/admin/secretary"`
- `get_student_statement(..., _="admin")` (x2) → `..., authorization="Bearer admin-token", role="admin"`

### 5) `test_students.py` (3)
- `search_students(..., _="admin")` → `..., sub_role="admin"`
- `get_student_grades(..., _="admin")` → `..., authorization="Bearer admin-token", role="admin"`
- `get_student_installments(..., _="admin")` → `..., authorization="Bearer admin-token", role="admin"` (کشف در ران دوم)

### 6) `test_teachers.py` (5)
- `get_teacher_profile(..., _="admin")` (x2) → `..., authorization="Bearer admin-token", sub_role="admin"`
- `get_pending_settlement(..., _="admin")` (x2) → `..., authorization="Bearer admin-token", sub_role="admin"`
- `get_settlement_history(..., _="admin")` → `..., authorization="Bearer admin-token", sub_role="admin"`

## Verify (طبق قانون)

- `python3 -m py_compile routers/analytics.py` → OK
- `python3 -m py_compile test_classes.py` → OK
- `python3 -m py_compile test_priority2_financial.py` → OK
- `python3 -m py_compile test_reports.py` → OK
- `python3 -m py_compile test_students.py` → OK
- `python3 -m py_compile test_teachers.py` → OK
- `ast.parse` همه 6 → OK
- `sweep **/*.py` → 83 OK, 0 bad
- **pytest با DATABASE_URL=/tmp روی کپی DB (هرگز gaj_db.db پرود):**
  - قبل: `13 failed, 255 passed` (268 total) — 13 TypeError
  - بعد (ران 1): `1 failed, 267 passed` — کشف `get_student_installments`
  - بعد (ران 2): `268 passed, 0 failed, 9 warnings in 15.44s` ✅
  - دستور: `cp gaj_db.db /tmp/test_gaj.db && DATABASE_URL=sqlite:////tmp/test_gaj.db python3 -m pytest -q`
  - هش DB پرود دست‌نخورده (فقط /tmp)
- `git diff --stat`:
  ```
  Kharazmi_Server/routers/analytics.py        |  2 +-
  Kharazmi_Server/test_classes.py             |  2 +-
  Kharazmi_Server/test_priority2_financial.py | 12 ++++++------
  Kharazmi_Server/test_reports.py             | 12 ++++++------
  Kharazmi_Server/test_students.py            |  6 +++---
  Kharazmi_Server/test_teachers.py            | 10 +++++-----
  6 files changed, 22 insertions(+), 22 deletions(-)
  ```
- **تأیید routers مالی/auth/analytics فقط در اجبار لمس شد:** فقط `analytics.py` یک خط (کال داخلی)؛ `routers/finance.py`, `routers/auth.py`, `routers/reports.py`, `models.py` untouched. `git diff --name-only` بالا را ببین.

## چک‌پوینت و پوش
- فایل: `checkpoints/2026-09-16_tests-obsolete-signatures.md` (این فایل)
- کامیت: `tests: align 13 obsolete signatures (TypeError) — analytics internal + test calls` — هش بعد از push
- پوش: `arena/01a0a936-kharazmiapp` — با `gh api` وریفای شد

## هش کامیت و گزارش نهایی
- قبل: `482f60f` (F-B2)
- بعد: (پس از push)
- سوئیت کامل: `268 passed`

## تأیید نهایی
- ✅ 13 TypeError هم‌تراز شد (حداقل تغییر تست + 1 خط اجبار analytics)
- ✅ routers مالی/auth دست نخورد (جز analytics داخلی)
- ✅ F-A2 دست نخورد، بدون ریفکتور بی‌ربط
- ✅ no run روی پرود DB (فقط /tmp کپی)
- ✅ 268/268 green
