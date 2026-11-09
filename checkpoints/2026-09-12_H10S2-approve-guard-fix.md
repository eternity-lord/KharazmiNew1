# Checkpoint — H10-S2 approve-guard fix + approve_class 404

Date: 2026-09-12. 3 ops, all in routers/admin.py, anchors asserted. No compile/run.

## Step 1 — approve_teacher admin.py:216
- Guard check_user_login → check_admin_or_secretary_access (dual, C1/H10-S
  pattern) + trailing FIX H10-S2 marker. Body untouched (already had 404
  "معلم یافت نشد").
- Asymmetry approve(dual) vs reject(admin-only :226) is PRINCIPLED, not a bug:
  approve = enabling action, instantly neutralizable by the SAME role via
  suspend_teacher (dual, H10-S); reject = destructive archival (is_deleted,
  kills livelihood, disrupts classes, no exposed undo) → admin-only stays.
  Rule: an action's guard need be only as strong as its undo's guard.
- Honest reservation (stated, not vetoed): approve_teacher is the closest to
  the identity family (credentials/password-delete all admin-only) and has no
  one-click unapprove; dual holds because (a) suspend-undo is dual+instant,
  (b) monetizing a bad approval needs admin-gated steps (settlement payout),
  (c) secretary trust already assumed by C1 (enrollments/installments/updates).

## Step 2 — approve_class admin.py:528
- Same dual guard swap + trailing marker.
- Bonus 404 fixed in same function: `if not c: → 404 "کلاس یافت نشد"` (message
  matches same-file neighbor reject_class :275; was None → AttributeError 500).

## Step 3 — rejects verified UNTOUCHED
- reject_teacher :226 and reject_class :275 still check_admin_access (shown in
  verify output). reject_class body confirms why: deletes class + rewrites
  every enrollment balance via perform_delete_enrollment — destructive,
  must NOT be downgraded to dual.
