# Audit (read-only): ClassDetail:289 hardcoded «دوازدهم» — 2026-09-13

## Verdict: REAL BUG (client-side root cause, server blindly persists)

## Client (ClassDetailActivity.kt)
- :261-279 `showEditClassInfoDialog()`: dialog has ONE EditText (title only).
  Comment at :193 says intent was «پایه و عنوان» but no grade picker was ever added.
- :281-300 `updateClassInfoOnServer(newTitle)`: :289 sends
  `ClassUpdateInfo(newTitle, "دوازدهم")` — grade hardcoded on EVERY call.
- Callers of PUT `classes/update_info/{course_id}`: exactly ONE in the whole app
  (grep: no other `updateClassInfo`/`ClassUpdateInfo` refs). No override path.

## Server (routers/classes.py:1080-1110)
- `ClassUpdateInfoModel`: both fields Optional.
- :1104-1105: `if data.grade_level is not None and ...strip(): course.grade_level = ...`
  → unconditional overwrite, no validation, no audit log, no history.
- :1105 is the ONLY `grade_level =` assignment post-creation in routers+models+schemas.
- Creation path (AddClass) sends the real user-picked grade → classes are born
  correct, then clobbered to دوازدهم on the FIRST title edit via this dialog.

## Relation to audit-v2 caller guard (#3, same endpoint)
- SEPARATE. The guard gates WHO (admin/secretary/owner-teacher; blocks students).
  It does not validate the grade VALUE. The bug rides the legitimate path the
  guard itself blesses («مسیر مشروع معلم»). Guard comment already foresaw a
  follow-up: teacher-driven grade changes need auditing (tariff impact).

## Blast radius (mechanism)
- Money: only when class has NO explicit `teacher_session_price` → fallback to
  PricingTable by category (financial_calculations.py:242-252). دوازدهم ⇒ high_school.
  Corruption elementary/middle → دوازدهم changes tariff; within high-school silent.
  Classes WITH a rate are financially immune (grade still wrong for display/filter).
- Non-money: grade filter (teachers.py:232-233), parent portal + reports display.
- No trail: endpoint writes no activity_logs → affected classes unknowable from logs;
  only title/grade mismatch heuristics.

## Exposure in current DB (read-only SELECT on /tmp COPY; original untouched)
- DB is dev/seed: exactly 1 course (id=1 «ریاضی کنکور», grade کنکور, price 500000).
- Zero classes with grade_level=دوازدهم → no evidence any class passed this path yet.
- Production exposure UNKNOWABLE from this DB.

## Fix options (NOT applied — awaiting user decision)
1. App: send current grade instead of hardcoded (needs grade in report response or
   omit field; server already treats None as "don't touch").
2. App+server: add real grade picker to the dialog (matches :193 intent).
3. Server hardening: reject grade_level values outside known list (defense in depth).
