# Checkpoint — H9 audit-identity analysis (READ-ONLY, no code changed)

Date: 2026-09-12. Scope: every place an audit-identity param (ActivityLog.
admin_username or similar) is filled with a fixed string instead of the real
session user. Worked against TODAY's code (post H1/H8).

## Step 1 — exhaustive sweep (production code only)
ActivityLog creations: exactly 9 (grep `ActivityLog(` over routers/+main/+deps).
- routers/finance.py:814 payment_callback → "online_payment_system"
- routers/finance.py:1078 refund_transaction → "admin_portal"
- routers/finance.py:1154 create_installment → "admin_portal"
- routers/finance.py:1183 update_installment → "admin_portal"
- routers/finance.py:1217 delete_installment → "admin_portal"
- routers/finance.py:1327 pay_installment_manually → "admin_portal"
- routers/auth.py:593 change_mobile → old_mobile (data field)
- routers/admin.py:1537 reset_teacher_password → current_user.username (real)
- routers/admin.py:1588 update_teacher_credentials → current_user.username (real)
Similar params:
- routers/teachers.py:774 settled_by_user_id=settled_by (H8-P2, session user_id + fallback 1)
- routers/classes.py:801 requested_by_role="admin" in delete_class_endpoint (role-only, user_id NULL)
- routers/classes.py:924-926 requested_by_* = sub_role/current_user.id/teacher_id (real)
- approve_class_deletion :978 / reject_class_deletion :999: decided_by_user_id NEVER written (always NULL); decided_at IS set.
- Tests only (no fix): test_advanced_finance.py:132,243. Checked & out of scope:
  pinned_by (pin list), graded_by_teacher (bool), SmsLog/Notification (recipient not actor).

## Step 2 — verdicts
NEED FIX (human action, fixed string): finance 1078, 1154, 1183, 1217, 1327
(5x admin_portal); classes 801 (role-only + NULL user ids).
CORRECT AS-IS (true system actor): finance 814 payment_callback — gateway GET
callback, no auth possible, no logged-in user exists; student already in
target_id/target_name; also currently disabled behind PAYMENT_GATEWAY_ENABLED.
ALREADY CORRECT: admin 1537/1588 (Depends(get_current_user), object unmutated
before log); auth 593 old_mobile (self-service + 403-guarded ⇒ actor==target
enforced; user.username reassigned BEFORE log line on same identity-map
instance, so old_mobile is the only at-action identity handle); teachers 774
(H8-P2); classes 924-926 (authorization + direct get_current_user call).
BONUS GAP (missing, not hardcoded): decided_by_user_id never set by
approve :978-996 / reject :999-1012 — same H9 family, fix together.

## Step 3 — fix wiring per site (H8-P2 pattern, teachers.py:742-752)
finance.py idiom: zero get_current_user use; `_: str = Depends(check_...)` +
explicit `authorization` Header where needed. check_* (dependencies.py:143-200)
already 401-reject bad tokens via get_session_from_token (deps :84-111), so
inline lookup is guaranteed-valid in practice; H9 needs .username (one User
lookup more than H8's user_id). Header already imported in finance.py and
classes.py; only lazy get_session_from_token import to add.
- refund_transaction 955: has check_admin_access; ADD authorization Header.
- create_installment 1132: has check_admin_or_secretary_access; ADD authorization.
- update_installment 1166: same; ADD authorization.
- delete_installment 1206: same; ADD authorization.
- pay_installment_manually 1229: HAS authorization (:1235); NO signature change.
- delete_class_endpoint 785: has check_admin_access; ADD authorization; set
  requested_by_user_id + decided_by_user_id (both NULL today).
- approve_class_deletion 978 / reject 999: has check_admin_access; ADD
  authorization; set decided_by_user_id.
Proposed fallback shape (for the future fix task): H8-style try/except with
clearly-marked "unknown" fallback (should never trigger since Depends already
validated; guards logout-race None).
