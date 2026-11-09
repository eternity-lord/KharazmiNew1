# Backfill dry-run scripts ×3 (2026-09-14; --apply NEVER run)

## Scripts (H4/H20 pattern: argparse, SessionLocal, Persian report, exit 2 = needs review)
1. scripts/audit_is_billed_orphans.py — REPORT-ONLY (no --apply by design: real money).
   Orphan = billed Attendance on active session whose teacher has ZERO Settlement rows.
   + per-teacher billed-count vs sum(session_count) mismatch section.
2. scripts/backfill_session_charge_branch.py — dry-run default; --apply = NULL-only fill,
   only when sources agree (student-first H7, else class); branch=1-mismatches NEVER auto-touched.
3. scripts/audit_pseudo_jalali_dates.py — REPORT-ONLY (dates can't be auto-derived).
   Scope: transactions.date, session_logs.date, installments.due_date via parse_project_date.

## Validation (all on /tmp/backfill_current.db COPY; original gaj_db.db untouched, counts verified)
- Deps installed (dotenv+sqlalchemy); DATABASE_URL env override used.
- Current dev DB is schema-stale (no idempotency_key) → replayed server auto_patch column list
  on the COPY. NOTE: SQLite can't ADD UNIQUE columns — server's own idempotency_key patch fails
  the same way on old sqlite DBs (latent server issue, out of scope; added as plain VARCHAR on COPY).
- Empty-DB runs: all exit 0, sensible zeros.
- Synthetic proof (planted on COPY): billed att w/o settlement → flagged exit 2; NULL-branch
  charge → proposed 2 (student-first, disagreement flagged); branch=1 charge → suspect (≠1);
  '1404/13/45' → شبه‌شمسی flagged exit 2. Detection logic PROVEN.

## Ready for prod: run dry-run first; script 2 --apply only after reviewing NULL proposals.
