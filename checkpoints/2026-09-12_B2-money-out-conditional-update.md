# Checkpoint — B2 money-out: conditional UPDATE (H8 pattern) — 2026-09-12

Task: Batch 2 — all 3 money-OUT/reversal paths converted from pessimistic-lock +
Python RMW to H8-P4 conditional UPDATE + rowcount. Report only, no compile/run.

## Step 1 — refund_transaction (routers/finance.py, ~:954-1090)
- :5 — import: `case` added (SQLAlchemy 2.0 tuple syntax; portable SQLite+PG).
- :960-963 — trans read WITHOUT lock (R1 comment :961); 404 + is_reversed-400 fast-path KEPT (:967).
- :970 — t_amount frozen; :972-981 — atomic CLAIM (SET is_reversed WHERE id+not-reversed+not-deleted);
  rowcount!=1 → rollback + SAME 400 «قبلاً استرداد شده است (Idempotent Refund)».
- Remittance + reversal doc UNCHANGED (:983-1012, still after the claim → no sequence consumed on conflict).
- :1014-1015 — student read WITHOUT lock; :1017-1033 — sub_teacher/sub_institute accumulators
  (both-split math incl. share fallback kept byte-identical; else → documented no-op).
- :1035-1051 — atomic wallet SUBTRACT (COALESCE−sub); rowcount!=1 → rollback + 404.
- :1053-1057 — refresh (:1055) → sync (only if UPDATE ran; B1 rule).
- :1059-1076 — atomic total_paid SUBTRACT with max(0,…) preserved as SQL CASE (:1068);
  gate line byte-identical; rowcount-0 → SILENT skip (faithful: enrollment never pre-validated here,
  unlike submit→409; principled difference, deliberate).
- ActivityLog + commit + return UNCHANGED.

## Step 2 — reverse_session_financial_impacts (dependencies.py :278-323)
- :279-284 — candidate SELECT WITHOUT lock + lazy `func` import (file's lazy style).
- :285-313 — per-txn: atomic CLAIM (:289-295, is_deleted WHERE id+not-deleted+not-reversed;
  rowcount!=1 → continue/skip credit, idempotent); conditional wallet CREDIT (:296-313, COALESCE+shares;
  wallet rowcount-0 → silent skip, faithful to old `if student`); zero-share txns skip the UPDATE.
- :314-320 — ONE refresh+sync per affected student AFTER the loop (batched; :318 refresh).
- :322-323 — Attendance bulk delete BYTE-IDENTICAL (idempotent) + commit KEPT (callers rely on it).
- Callers verified compatible: edit path attendance.py:707-708 (validations pre-computed before reverse;
  session mutation + re-charge after — commit placement unchanged), delete path :826-827
  (reverse → is_deleted → commit), test double-call test_priority2_financial.py:391/:396 (2nd call no-ops).

## Step 3 — update_transaction (routers/admin.py :826-972)
- :5 — import: `case` added.
- Freeze/mutation/gates UNCHANGED (:835-841): old_amount frozen BEFORE trans mutation; all 3
  `diff = new_amount - old_amount` preserved (:850/:876/:901); UPDATE dicts never use trans.amount for math.
- Path A (:850-864): read+check KEPT; write → atomic UPDATE with CASE floor (:857), WHERE id+not-deleted;
  micro-window rowcount-0 → silent skip (old behavior).
- Path B (:876-884): read KEPT; write → atomic UPDATE with NO floor and NO is_deleted guard —
  EXACT old behavior (old read had no deleted filter; adding one would change product logic — out of scope).
- :889-890 — student read WITHOUT lock; early-returns KEPT.
- :895-901 — wallet_* locals → d_teacher/d_institute (wallet_balance local was PROVEN dead:
  old write-back :930-933 set only components + sync, discarding it).
- Deposit branches → d_* (:~903-910); session_charge ratio math KEPT, float deltas UNROUNDED (:~933-935);
  tuition/enrollment/typeless/unknown-target → documented no-op `pass` (:938/:942, skeleton kept for review).
- :945-961 — ONE atomic wallet UPDATE (signed diff, COALESCE); rowcount!=1 → rollback + 404.
- :963-968 — refresh (:966) → sync (:968) only if deltas nonzero (B1 rule). commit+return UNCHANGED.

## Step 4 — sweep (verified by grep)
- REMOVED (5 B2 sites): refund×3, reverse×1, update_transaction×1. Zero RMW leftovers in all 3 functions.
- REMAINING real `.with_for_update()` calls: finance.py :699/:737/:777 (callback, gateway-disabled-404,
  audited SAFE) + :1173 (update_installment, absolute-overwrite, audited SAFE); dependencies.py
  :239/:242/:254 (perform_delete_enrollment — B3 scope); admin.py ZERO.
- COUNT CORRECTION: task said "7 sites of this batch" — actual B2 scope (steps 1-3) is 5 lock sites.
  The other 4 (callback×3 + update_installment×1) were audited SAFE and in no fix batch; left untouched
  (no conversion prescribed; removing locks with no replacement = gratuitous churn in dead/safe code).
  Offered as trivial follow-up if user wants them deleted anyway.
- B3 delete_transaction RMW intact (:743/:756/:815); no other function touched. `case(` used once per
  file (refund :1068, update path A :857); no name collisions.

## Step 5 — race traces (in report)
- Refund double-click → winner claims + exactly 1 reversal; loser same-400, no sequence consumed.
- Concurrent over-refunds (700k pot, 500k+400k) → atomic CASE lands exactly 0 both orders (old: 200-300k overstatement).
- reverse_session concurrent double-call → each txn credited EXACTLY once (old: phantom double credit).
- update_transaction two admins, two txns, one student → both diffs land exactly (old: last-wins loss).
- HONEST CAVEAT: identical double-submit of one manual edit applies diff twice under both old and new
  (edits have no natural idempotency flag; dedup would need idempotency keys — not ordered, out of B2 scope).

## Next
B3 (deletes: perform_delete_enrollment :239/242/254, delete paths + attendance submit-guard :335) NOT
started — awaiting order. Standing rule: checkpoint after every task.
