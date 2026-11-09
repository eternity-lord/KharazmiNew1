# Checkpoint — H10 suspension-enforcement analysis (READ-ONLY, no code changed)

Date: 2026-09-12. Q: is_suspended (teacher/student) toggle+display only, never
checked at login; course.is_suspended same pattern on write paths?

## Step 1 — today's login code (verified vs current files)
- login_user auth.py:25; teacher branch ~:52-110. is_approved 403 at :58-61
  ("حساب شما هنوز توسط مدیر تایید نشده است"). NO is_suspended check anywhere
  in login_user. Password checked BEFORE approval (400 first).
- student_login auth.py:413-~470 (OTP-verify → student lookup :447 is_deleted
  only → H2 lazy shadow ensure_student_shadow_users → JWT student session).
  NO is_suspended/is_approved check. request_student_otp auth.py:350 (lookup
  :355) also unchecked → OTP (SMS) sent to suspended students today.
- Sweep proof: 50 non-test is_suspended refs = models(3)+migrations(5)+toggles
  (admin 244 teacher / admin 1059 student / classes 307+328 course / admin 1277
  bulk-True)+display (admin 209/422/1444/1470, teachers 80, classes 262/728/744,
  schemas×3, auth 626)+read-filters (calendar×4, branches 202, classes 85,
  today_summary×2, students search_simple 208). ZERO enforcement (no login/
  guard/write-path check).

## Step 2 — parent portal: separate path, same gap; OPINION: do NOT block
- Path: request_parent_otp parent.py:26 (lookup :31) → parent_login :101
  (students query :141, single-child session :143-162, multi temp+list :164-180)
  → parent_select_child :185 (lookup :196, IDOR guard :200). All filter
  is_deleted only; no suspension check.
- Portal is 100% READ-ONLY (5 endpoints: request_otp/login/select_child/
  child_profile GET/portal HTML). Suspension is typically debt-driven
  attendance freeze; parent must SEE debt + pay to resolve → blocking parent
  login creates resolution deadlock. RECOMMEND: no login block; surface
  is_suspended flag in child_profile payload (absent today — no parent.py in
  sweep) as banner. IF overridden: block points = single-child branch after
  :144 + children_list filter :173 + select_child after :196.

## Step 3 — course.is_suspended: read-filtered, write-OPEN
- Toggles: suspend_class classes.py:300, suspend_class_admin :319 (docstring:
  S-button), suspend_bulk_classes admin.py:1267 (True-only).
- Write paths with NO suspension (or even deletion) gate:
  - add_enrollment classes.py:339: student is_deleted-only (:341), course
    NO is_deleted + NO is_suspended (:344). → suspended students enrollable;
    enrollment into suspended/deleted class allowed.
  - submit_session_and_calculate attendance.py:329: course 404 :336-338, no
    suspension gate → sessions + wallet charges on frozen class.
  - edit_past_session :675: course 404 :686-688, no gate.
  - start_live_session :143: course 404 :149-151, no gate.
  - qr_student_check_in :876: no student/course suspension gate.
  - validate_session_items_membership deps:363 (called by submit :355 AND edit
    :710): membership-only → suspended students markable Present AND charged.

## Step 4 — fix proposal (exact points, 403s; order: after 404, before 409/422)
- Teacher: login_user after :58-61 block → 403 "حساب شما توسط مدیر معلق شده است. لطفاً با آموزشگاه تماس بگیرید".
- Student: student_login after :447 lookup (+ request_student_otp after :355,
  saves SMS) → same 403.
- Parent: no block (step 2); add flag to child_profile (display only).
- add_enrollment: after student 404 → 403 student-suspended; after course 404
  (:344-346) → 403 "این کلاس در حال حاضر معلق است و ثبت‌نام جدید در آن امکان‌پذیر نیست".
- submit :336-338 / edit :686-688 / live-start :149-151: after course 404 →
  403 "... معلق است و امکان ثبت/ویرایش جلسه/شروع جلسه‌ی زنده ... وجود ندارد".
  (Edit-blocking is the one debatable call: uniform-freeze recommended; allowing
  corrections to pre-suspension facts is the alternative.)
- Items: inside validate_session_items_membership (single chokepoint, both
  callers) → 422 with id list (matches existing 422 style): suspended students
  rejected from submit+edit at once.
- qr_student_check_in after own-resolution (:883-886) → 403 student-suspended
  (+ course gate for uniformity).
- Caveat: login-only gates leave EXISTING sessions valid until expiry. Guard-
  layer option exists (check_user_login/get_current_user already host the
  global teachers_active kill-switch precedent; per-actor would need
  get_logged_in_teacher / get_session_student/parent resolution per request).
  Recommend login gates now; guard layer as optional follow-up.
- Adjacent (NOT H10, one line each): suspend toggles use check_user_login, not
  admin guard (any logged-in role can suspend); course.is_deleted unchecked in
  add_enrollment/submit/edit/live; teachers.py:384 is_approved branch is dead
  (guard returns admin/secretary, never "teacher").
