# Checkpoint — H10 implementation (suspension gates)

Date: 2026-09-12. 12 ops, 5 files, all anchors asserted (count/shape), visual
read-back of all 12 sites. No compile/run.

## Step 1 — login gates (routers/auth.py) + parent display (routers/parent.py)
- A1 login_user teacher: :62-64, after is_approved 403 (:58-61), before shadow
  creation → 403 "حساب شما توسط مدیر معلق شده است. لطفاً با آموزشگاه تماس بگیرید".
- A2 request_student_otp: :361-363, after 404, before rate-limit/OTP → same 403
  (saves SMS cost).
- A3 student_login: :456-458, after :447-449 lookup/404, before H2 shadow →
  same 403.
- P1 child_profile info dict: :368-369 `"is_suspended": bool(student.is_suspended)`
  (display only; parent login NOT gated, per decision).

## Step 2 — write gates
- C1 add_enrollment student: classes.py:344-346 → 403 student-suspended.
- C2 add_enrollment course filter: classes.py:347-348 extended with
  `Course.is_deleted == False` → deleted course now hits existing 404 (was
  unchecked; DECISION: 404 not 403 — "suspended" message would be wrong for
  deleted rows; codebase-idiomatic).
- C3 add_enrollment course: classes.py:351-353 → 403 class-suspended.
- T1 submit: attendance.py:343-345, after course 404, before Bug-17 dup check →
  403 (no session/wallet effects on frozen class).
- T2 edit: attendance.py:696-698, after course 404, before settled-409 → 403.
  (2nd of 2 `session.course_id` lookups; get_session_details untouched.)
- T3 live start ONLY: attendance.py:153-155, between course 404 and owner-verify
  (404 → frozen → ownership). end_live/save_live calls deliberately ungated
  (closing/reporting an already-running session must keep working).
- T4 qr check-in: attendance.py:897-899, after `student_id = own.id` → 403.
  (Student-only per order; no course gate added to QR.)
- D1 validate_session_items_membership: dependencies.py:388-401, after membership
  422 → 422 same-format with suspended id list. Covers submit (:355 caller) +
  edit (:710 caller) at once. (Student already top-imported in dependencies.)

## Step 3 — caveat (report-only, as ordered)
Gates cover NEW logins/operations only; already-valid sessions stay usable until
expiry. Instant cut-off = future step at guard layer (check_user_login/
get_current_user + per-actor resolution; teachers_active kill-switch precedent).

## Errors & dead ends
- Attempt 1 aborted at A3: shape guard used 4-space `    raise` prefix vs actual
  8-space `        raise` (inside if-block). Nothing written (save after all ops).
- Attempt 2: 9/9 through T2 saved (auth/parent/classes), then T3 anchor
  `_verify_live_course_teacher(...)` count=3 (start/end/save call sites) —
  attendance.py NOT saved. Fixed by anchoring on bare-`course_id` course query
  (unique to start_live; end/save use live.course_id) + asserting the verify
  call 4 lines below. Reran attendance (T1-T4) + dependencies (D1): 5/5 OK.
