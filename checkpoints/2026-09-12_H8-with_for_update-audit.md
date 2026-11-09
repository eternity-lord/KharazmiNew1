# Checkpoint — H8 follow-up: with_for_update audit (2026-09-12)

## Task
Read-only audit of every `with_for_update()` use in Kharazmi_Server (SQLite no-op problem).
No code changed, no compile/run.

## Key finding
- Actual count: **23 code sites** (not 26 — the other 2 matches are comment mentions; tests excluded).
- SQLite ignores `FOR UPDATE` → all 23 locks are decorative. Real protection must be H8-style:
  conditional `UPDATE ... WHERE <expected state>` + `rowcount` check (or pure SQL arithmetic `SET x = x + :amt`).

## Verdict
- **REAL RISK (15 sites, 7 fix units):** dependencies.py:239/242/254 (delete_enrollment),
  dependencies.py:283 (reverse_session), attendance.py:335 (submit dup guard),
  finance.py:171/189/198 (submit_payment), finance.py:926/967/993 (refund),
  finance.py:1159/1168/1171 (pay_installment), admin.py:873 (update_transaction).
- **PRACTICALLY SAFE (8 sites):** auth.py:65 (rare duplicate-User, needs unique constraint not lock),
  finance.py:664/702/742 (gateway disabled → 404), finance.py:1094 (absolute overwrite, last-wins),
  students.py:424 + teachers.py:379 (optimistic `version` check is the real guard — GOOD pattern),
  scripts/backfill_link_orphan_deposits.py:107 (serial CLI, dry-run default, self-guarding re-run).
- Extra find: admin.py:~863 `enrollment.total_paid += diff` has NO lock at all (student-only lock at :873).

## Proposed batches (not started)
- B1: money-in (submit_payment + pay_installment) — highest traffic.
- B2: money-out/reversal (refund + reverse_session_financial_impacts + update_transaction).
- B3: delete paths + submit duplicate guard (perform_delete_enrollment + attendance:335 post-flush dup check).

## Standing rule (new)
After EVERY task, write a checkpoint file under /home/user/checkpoints/ (this is the first one).
