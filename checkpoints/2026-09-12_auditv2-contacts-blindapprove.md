# Contacts-guard + Blind-approve chain — 2026-09-12 (impl, no compile/run)

## 1) get_parent_contacts — admin.py:557
- `_: str = Depends(check_user_login)` → `Depends(check_admin_or_secretary_access)`.
- Compat PROVEN: sole launcher MainActivity (admin/secretary hub); teachers land on TeacherDashboard (no reference); nav_parents visible to both admin+secretary → zero legit break.
- Trace: student/parent/teacher 200+PII → 403; admin/secretary byte-identical 200.

## 2a) create_class — classes.py:76-87 (+import :25)
- Sig: `authorization: Optional[str] = Header(None), sub_role` (mid-line swap, Header/Optional pre-imported).
- Non-staff: get_logged_in_teacher (lazy, REF-B pattern); miss → 403; hit → `course.teacher_id = me.id`; price > MAX → 400.
- staff (admin/secretary): untouched path, any teacher_id/price (deliberate, approve warns instead).
- Trace: student/parent create → 403 (was: real unapproved row + consumed code); teacher-for-other → forced self; teacher 999M → 400.

## 2b) real base_institute_share — server admin.py:516-529 + app (150/32/37-39)
- Server: `_base_inst_share` = 0 if rule_prepay_institute else InstituteShare.count_1 (N=1 baseline, H5 mirror: same table, same getattr); missing row → 0 (submit still 500s separately).
- App: VH putExtra INSTITUTE_SHARE (:150); Detail reads (:32) + binds tvTeacherAsk/tvInstShare/tvFinalCost with %,d (:37-39). PendingClassItem.base_institute_share already existed (:111) — was just fed 0.
- Trace: approve screen shows e.g. 500,000 / 50,000 / 550,000 instead of ۰/۰/۰.

## 2c) approve warning (DECISION: non-blocking warn, implemented) — server admin.py:546-549 (+import :23), app AppModels:8 + Detail :8/:82-91
- Rationale: VIP-legit prices can exceed cap; 400 would break approve flow with no in-app remedy. Warning + visible amounts = informed consent.
- Server: `price_warning` key always present (None normally); set when price > MAX.
- App: SimpleResponse gains `price_warning: String? = null` (Gson-absent→null; sole approveClass caller is Detail :78); warning → AlertDialog, finish on ack/cancel; normal → toast+finish as before.

## Shared constant — financial_calculations.py:205
- MAX_TEACHER_SESSION_PRICE = 5_000_000. Grounding: unit is per-student (T_total = price × present); seed 500k → 10× catches fat-finger/abuse (999,999,999 × N students = billions/session), spares legit VIP.
- Used by classes.py (teacher hard-cap) + admin.py (approve soft-warn).

## Residuals (not implemented, out of scope)
- GET pending_classes itself still login-only (titles/prices to any login — low sensitivity).
- AddClassActivity teacher dropdown still lists other teachers (server now overrides to self — cosmetic; app could lock it).
- Staff-path typo'd teacher_id → orphan class ("نامشخص") — no existence-404 added.
