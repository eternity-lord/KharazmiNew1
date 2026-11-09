# Issue #7 closeout — ledger for targeted-online + manual settle (2026-09-12, no compile/run)
- T finance.py:~898-922: targeted branch converted RMW→optimistic cond-UPDATE (3 tries, refresh, paid-predicate) + ledger(new_trans.id → target, full−already); rowcount-0 → money stays general credit, NO 409 (verified gateway money), no ledger; never clamps paid_amount down (micro-delta vs old unconditional set). Residual NOTE removed.
- M1 :1549: freeze _man_pre (pre-claim coverage) next to inst_amount (deterministic: autoflush off, no flush between validation and freeze).
- M2 :1613-1616: ledger(new_trans.id → installment_id, full−pre) after receipt flush; normal case pre=0 → full amount as specified.
- Refund compat: both receipts type=deposit (M16-refundable); alloc reader has no type gate → same reversal path; restores exact pre-state (paid/flag/paid_at).
- Verified: ast.parse OK; NOTE gone; 4/4 writer sites now covered (submit, online-fallback, online-targeted, manual).
- Pre-existing, NOT touched (need own decision): (1) manual settle total_paid += FULL even over partial pre-cover (double-count suspect); (2) manual claim lacks paid-predicate (concurrent auto-cover lost-update); (3) targeted branch has no installment-ownership check (cross-student intent possible at initiate).
