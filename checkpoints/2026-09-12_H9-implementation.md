# Checkpoint — H9 implementation (7 audit-identity fixes)

Date: 2026-09-12. No compile/run (text edits + grep/sed verification only).
Pattern: H8-P2 lazy get_session_from_token (teachers.py:742-752), adapted:
finance needs .username (one extra User query; User already top-imported in
both files), classes needs user_id. Fallback "unknown" (finance) / None
(classes, columns nullable = today's behavior).

## Step 1 — routers/finance.py (5 funcs, 9 replacements, all anchor-count==1)
- refund_transaction: sig :955 (auth added :958, trailing comment preserved);
  H9 block :1078-1093; admin_username=_audit_username :1095 (action transaction_refund).
- create_installment: sig :1149 (auth :1152); block :1171-1186; use :1188.
- update_installment: sig :1200 (auth :1204); block :1217-1232 (indent 12, inside
  amount-change guard); use :1234.
- delete_installment: sig :1257 (auth :1260); block :1268-1283; use :1285.
- pay_installment_manually: sig UNCHANGED :1297 (auth pre-existing :1302);
  block :1394-1409; use :1411.
Verify: admin_username="admin_portal" count 5→0; 5 inits + 5 uses; auth headers 11→15.

## Step 2 — routers/classes.py (3 funcs, 7 replacements, all anchor-count==1)
- delete_class_endpoint: sig :785 (auth :789); id-block :799-812;
  requested_by_role="admin" KEPT :815 + requested_by_user_id :816 +
  decided_by_user_id :821 (both were NULL).
- approve_class_deletion: sig+block :994-1007 (init :998); decided_by set at
  BOTH decision points — early-exit branch :1018 (commits before 400-raise) and
  main path :1024.
- reject_class_deletion: sig+block :1030-1043 (init :1034); decided_by :1052.
Verify: decided_by_user_id writes = 4 (delete+approve×2+reject); requested write = 1.

## Step 3 — identity-layer-only proof
Each change = (+1 sig param) + (lookup block with NEW locals only:
_parts/_token/_sess/_audit_user/_audit_username/_actor_user_id) + (audit-value
swap / added id kwarg). Untouched: all query filters, arithmetic, status flows,
commit/rollback/raise lines (approve-branch raise anchor ended before detail).
`_` shadowing audit: standalone `_` in all 8 touched ranges = only Depends
params (never body-read by convention) + own `_sess, _` unpacks; no post-block
read of `_` anywhere (same shape as accepted H8 precedent).

## Step 4 — intentionally untouched (verified present, count==1 each)
- routers/auth.py:593 admin_username=old_mobile (self-service + 403-guarded;
  only at-action identity handle — correct per analysis).
- routers/finance.py:814 admin_username="online_payment_system" (gateway
  callback, no logged-in user exists — correct per analysis).

## Errors & dead ends
First classes.py patch attempt aborted: delete-site anchor assumed 8/12 indent
(finance habit); actual is 4/8/4 → count=0 assertion fired, NOTHING written
(write happens after all reps pass). Reran classes-only with corrected indents:
7/7 OK. Naive `grep -c admin_portal` (=5) measures H9 comment mentions, not live
code — correct check is `admin_username="admin_portal"` (=0).
