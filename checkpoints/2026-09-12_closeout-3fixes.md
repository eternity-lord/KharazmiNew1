# Closeout 3 fixes (double-count, paid-predicate, targeted ownership) — 2026-09-12 (no compile/run)
- Manual claim finance.py:1570-1598: paid-predicate + 3-try refresh/recompute; settled→same 400; moved→retry; else 409. :1599-1603 marginal<=0 → honest 400 (rollback undoes flip).
- Marginal downstream: wallet :1610, total_paid :1623, receipt :1641, audit :1676, ledger :1652-1653 (unconditional, guarded >0). Claim still sets FULL paid_amount. Normal case (pre=0) byte-identical.
- Targeted :896-918 ownership gate (student + optional enrollment match; deleted owner → mismatch) → mismatch sets _use_fallback + ActivityLog targeted_installment_mismatch (:913); :942 else→if _use_fallback. Settled-target→nothing preserved; NO 400 (single-use gateway authority).
- Verified: ast.parse OK; all markers on disk.
- Follow-up (not done): validate installment ownership at initiate-time too (initiate currently 400-stub; gateway disabled + callback TODO).
