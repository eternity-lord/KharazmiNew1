# Issue #7 (refund↔installment) + #9 (cross-vs-per-enrollment) — DESIGN ANALYSIS (read-only, zero code changes)

## Evidence
- Coverage loop: finance.py:429-480 (cross-enrollment query :431-434, atomic since idempotency task).
- Debt core: financial_calculations.py:166-184 — enrollment: max(0,tuition-total_paid); student: SUM over priced enrollments (+wallet-negative legacy fallback only if NO priced enrollment).
- Debt consumers (~15, all through the 2 central fns): admin (:110,:154 debtors count,:344), ai (:248), analytics (:227), classes (:234,:490,:610,:701,:875), finance (:78,:123,:1678,:1911), parent (:344), reports (:271,:328).
- total_paid writers (all per-enrollment): submit, online-callback, refund (CASE floor 0), enrollment-create (classes.py:401), admin edit/delete (:780-945).
- Installment reads are display/scheduling only (analytics stats, automation reminders, calendar, installments API) — NO money math reads is_paid/paid_amount.
- Cross-enrollment basis exists in EXACTLY 2 loops: submit_payment (:431) + online-callback fallback (~:881). Online targeted branch (installment_id) already per-installment ✓. Online fallback loop still legacy non-atomic ORM (idempotency step-2 hardened submit only).
- No Transaction↔Installment link: Installment 8 cols (no txn ref), Transaction none; manual-settle links only via description TEXT (:1512); Payment HAS installment_id+enrollment_id (intent level) but resulting Transaction drops the installment part.

## Decision step2: OPTION A (per-enrollment coverage) — decisive
- Count: per-enrollment underlies everything; cross lives in 2 loops. A ≈ 10-line change in 2 loops; B = debt-core rewrite + consumer audit + changed debtor semantics (Σmax(0,) vs max(0,Σ) differ on overpayment) + STILL needs allocation for class-level views.
- Single-enrollment majority (auto-link rule) behaviorally unaffected by A; only the broken multi-enrollment case changes.
- Wallets neutral (student-level pots, not debt basis).
- A-scope: scope query to [linked.id] when linked (submit + online-fallback); unlinked payments keep cross-legacy (no attribution flow exists; residual accepted, out of scope); convert online-fallback loop to conditional-UPDATE with A (3rd site).
- Absurd state fixed: 10M linked to E1 settling E2's installments while E1 shows unpaid/zero-debt and E2 shows paid/10M-debt.

## Design step3 (#7): allocation LEDGER (junction), reject heuristic + single-FK
- Reject LIFO-heuristic: partials (M13), interleave (T1,T2 refund order), targeted/manual (wrong installment), legacy-cross — all break it; can't even split amounts.
- Reject single Transaction→Installment FK: auto-coverage is 1→N with partial amounts; doesn't fit.
- Ledger: TransactionInstallmentAllocation(transaction_id, installment_id, amount, created_at); 4 writer sites (submit loop, online fallback, online targeted, manual settle — row added after rowcount==1, same DB txn); refund reverses per-row (cond-UPDATE, floor 0, recompute is_paid/paid_at). Interleave/partial/concurrency-safe (H8-P4).
- Backfill: none — history has no allocations → old refunds behave as today (backward compatible). Migration: CREATE TABLE only. Do NOT promote description-text convention to a mechanism.
