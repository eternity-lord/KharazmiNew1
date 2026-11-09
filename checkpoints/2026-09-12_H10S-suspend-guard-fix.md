# Checkpoint — H10-S suspend-toggle guard fix (C1-class)

Date: 2026-09-12. 5 ops (1 import + 4 guard swaps, single-line defs, no line
shifts). No compile/run.

## Step 1 — the 5 endpoints, confirmed
- suspend_teacher admin.py:238 — WAS check_user_login → FIXED.
- toggle_suspend_student admin.py:1053 — WAS check_user_login → FIXED.
- suspend_bulk_classes admin.py:1267 — ALREADY check_admin_access, NO change.
- suspend_class classes.py:301 — WAS check_user_login → FIXED.
- suspend_class_admin classes.py:318 — WAS check_user_login → FIXED (despite
  "مخصوص ادمین" docstring).

## Step 2 — guard decision: check_admin_or_secretary_access (dual, C1 pattern)
- Reversible toggle (one click undo) ≠ deletes/approvals.
- Operational: secretary handles debt-driven suspensions daily; already trusted
  with enrollments/installments/teacher-updates (C1 dual family).
- Tiering stays principled: single-item = dual, bulk (higher blast radius +
  True-only one-way) = admin-only. No existing guard loosened.
- Both class endpoints got the SAME guard: identical mutation ⇒ divergent
  guards would be theater (effective guard = weakest). Docstring intent noted;
  recommend deprecating one duplicate later (not done).
- admin.py:19 import extended (dual guard was missing there); classes.py
  already imported it. Marker: FIX H10-S.

## Step 3 — sweep: same-disease, LIST ONLY (not fixed)
- admin.py:216 approve_teacher — is_approved=True under check_user_login. HIGH:
  any logged-in user (even student) can approve any teacher → login enabled.
  Inconsistent pair: reject_teacher :226 is admin-only.
- admin.py:528 approve_class — is_admin_approved=True under check_user_login.
  Same inconsistent pair (reject_class :275 admin-only). Bonus: no 404
  (`c` may be None → 500).
- Verified CORRECT (no action): reject_teacher :226, delete_teacher :252,
  reject_class :275, delete_transaction :732, delete_student :1031,
  suspend_bulk :1267, suspend_branch (branches.py:97), delete_enrollment
  (classes.py:442), delete_class_endpoint, approve/reject_class_deletion,
  delete_installment (dual, C1-correct), delete_session_endpoint (admin),
  delete_homework (require_permission), delete_own_message (permission +
  ownership), _apply_class_deletion (helper; callers admin-guarded).
- Boundary: keyword sweep of lifecycle endpoints; full audit of all 106
  check_user_login sites (mostly reads) out of quick-sweep scope.
