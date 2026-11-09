# Checkpoint — B3 deletes + submit-guard (AUDIT CLOSED) — 2026-09-12

Task: Batch 3 (final) — deletes + session-submit duplicate guard. Report only, no compile/run.

## Step 1 — perform_delete_enrollment (dependencies.py :234-~310)
- :239-247 — atomic enrollment CLAIM first (`SET is_deleted WHERE id AND not-deleted`, id only, no refresh);
  rowcount!=1 → silent early return (idempotent, as ordered).
- :248-260 — candidate discovery WITHOUT lock (same or/and filters); student pre-read REMOVED (rowcount replaces it).
- 4-way branch logic preserved exactly: real-money types stay ACTIVE (refund still possible later);
  session_charge + forgive=False stays; else per-row txn CLAIM (:270-278, skip-credit on rowcount-0).
- :280-298 — conditional wallet CREDIT (COALESCE+shares) only for claimed session_charges; missing student → silent skip.
- :300-305 — batched refresh+sync per affected student. Installments bulk block BYTE-IDENTICAL.
- Tail `enrollment.is_deleted = True` KEPT (in-session state sync for callers; DB already claimed).
- NO new commit. Callers verified (3 sites / 4 endpoint flows): admin.reject_class loop :282-284
  (single end-commit; already-deleted rows claim-0-skip like old return), classes.delete_enrollment :443-444
  (+commit), classes._apply_class_deletion :881-885 (forgive flag kept; both callers :797/:991 commit after).
  COUNT NOTE: task said "4 endpoints" — actual = 3 call sites covering 4 endpoint flows. Loser-of-race gets
  idempotent-success message (passed pre-check), per ordered silent-return.

## Step 2 — delete_transaction (routers/admin.py :732-867) — FILE CORRECTION: admin.py, NOT finance.py
- Full current code SHOWN to user BEFORE patching (in-chat display, verbatim).
- :739 — t_amount frozen. :741-751 — TRANSIENT atomic claim (conditional is_deleted UPDATE as pure
  mutual-exclusion gate); rowcount!=1 → rollback + SAME 404 «تراکنش یافت نشد» (mirrors sequential double-delete).
  Hard-delete semantics KEPT (user-confirmed: soft-vs-hard is separate H11 product decision, out of audit);
  claim flip invisible in final state (same txn hard-deletes the row); ORM db.delete lines kept (cascades intact —
  Transaction has no cascade children anyway: only student/course many-to-one).
- Path A exact-link (:753-770, CASE comment :758): atomic subtract WITH max(0,…) CASE + WITH is_deleted guard
  (mirrors old read+check). Path B legacy (:772-790, comment :782): atomic subtract WITH manual-floor-as-CASE
  but WITHOUT is_deleted guard — EXACT old behavior (old read had no deleted filter; mirror of B2 update path B;
  adding a guard would change reconciliation — flagged, trivial follow-up if wanted). BOTH branches converted,
  none forgotten. Rowcount-0 → silent skip both (old if-skip; enrollment-gone must not block the delete).
- :796/:802 — early-return db.delete+commit+messages KEPT. :806-809 — wallet_* locals → signed d_teacher/d_institute
  (wallet_balance local PROVEN dead again — same write-back pattern as update_transaction).
- Deposit → d_* = -t_amount (:~811-820); session_charge → abs(shares) credit-back, `!= 0` guards kept (:~822-832);
  tuition/enrollment/unknown/unknown-target → documented no-op `pass` (:834/:838, skeleton kept).
- :841-857 — ONE atomic wallet UPDATE (signed COALESCE+delta); rowcount!=1 → rollback+404. :858-862 — refresh+sync
  only if deltas nonzero. :865 — final db.delete AFTER all conditional UPDATEs (as ordered). commit+return kept.
- Verified: zero RMW in scope; case( ×2 (A+B); db.delete ×3 kept; sync ×1.

## Step 3 — submit_session duplicate guard (routers/attendance.py) — PREMISE CORRECTION
- Task premise ("no UniqueConstraint on (course_id, date)") is FALSE: partial unique index
  uq_session_course_date_active exists (models.py:305-311, sqlite_where + postgresql_where).
  Primary race guard = that index (flush IntegrityError → same 409, pre-existing, kept).
- Still implemented the ordered COUNT as documented BACKSTOP (asymmetric safety: if prod DB drifted from
  models and lacks the index — plausible, no migrations seen — COUNT is the only guard; cost = 1 SELECT).
- :334-336 — :335 course lock REMOVED (read kept for 404+rules). :407-421 — post-flush COUNT gate
  (`.count()`, no new import; own row + committed dupe = 2 → rollback + SAME 409
  «جلسه این کلاس در این تاریخ قبلاً ثبت شده است»); placed right after flush, far before final commit (~:495)
  and before the money loop. Pre-check + flush-handler kept; 409 message ×3 verified identical.

## Step 4 — FINAL audit sweep (whole Kharazmi_Server, prod scope)
Remaining REAL `.with_for_update()` calls = exactly 8, ALL audited-SAFE, zero risk sites, nothing missed:
1-3. finance.py :699/:737/:777 — payment_callback (gateway-disabled-404; unreachable in prod).
4. finance.py :1173 — update_installment (absolute overwrite, no RMW).
5. auth.py :65 — rare-dup-User guard (SAFE per audit).
6. students.py :424 — version-guard GOOD pattern. 7. teachers.py :379 — version-guard GOOD pattern.
8. scripts/backfill_link_orphan_deposits.py :107 — serial CLI one-shot.
(Other grep hits are FIX B1/B2/B3/H8 comment mentions, not calls. Non-prod: test_advanced_finance.py :91/:106
use locks in test-only simulations — out of audit scope, untouched.)
USER'S "4 SAFE" FRAMING CORRECTED: 4 finance + 4 elsewhere = 8 total.

## Step 5 — race traces (in final report)
- perform double-delete → winner claims + exact single credit; loser silent no-op (old: phantom double credit).
- delete_transaction double-delete → winner deletes + exact single adjustment; loser same-404 (old: double subtract).
- submit double-submit → exactly one session; loser same-409 via index (PG) / flush-handler or COUNT (SQLite).

## Step 6 — AUDIT TOTALS (H8 + B1 + B2 + B3)
- Scope: 23 with_for_update code sites (25 grep − 2 comment lines). Fixed: ALL 15 real-risk sites —
  B1: 6 (submit_payment 3 + pay_installment 3); B2: 5 (refund 3 + reverse_session 1 + update_transaction 1);
  B3: 4 (perform_delete_enrollment 3 + submit-guard 1) + delete_transaction lockless RMW (transient-claim adaptation).
  H8 established the pattern (settle had no lock; fixed double-settle + strict-400 + payout + 409).
- Untouched by design: 8 SAFE (above) + delete hard-delete semantics (H11 product call).
- Checkpoints: (1) 2026-09-12_H8-with_for_update-audit.md, (2) 2026-09-12_B1-money-in-conditional-update.md,
  (3) 2026-09-12_B2-money-out-conditional-update.md, (4) 2026-09-12_B3-deletes-and-submit-guard.md.
- LEFTOVERS (not in audit scope, flagged, untouched): (a) submit charges-loop lockless wallet RMW
  (attendance.py ~:435-460 — concurrent submits, different dates, same student → lost update; needs own batch);
  (b) verify prod DB HAS uq_session_course_date_active; (c) final-commit 409 message conflates session-dup
  with attendance-dup on SQLite path (right code+rollback, wrong text); (d) H11 soft-vs-hard delete decision;
  (e) optional deletion of the 4 finance SAFE locks (offered B2, still open); (f) manual-edit double-submit
  applies twice (needs idempotency keys — B2 note).
