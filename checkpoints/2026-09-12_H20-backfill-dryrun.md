# Checkpoint — H20 backfill DRY-RUN (explicitly permitted; --apply NOT run)

Date: 2026-09-12. Deps installed (pip, non-persisting) to execute. No writes.

## Result: dev DB is clean — 0/0/0
- Scanned scope-rows: 5. Candidates: 0. Invalid: 0. Conflicts: 0.
- Teacher: 1 row (id=1, '09120000000' already canonical).
- Student: 2 rows (id=1 '09351111111', id=2 '09352222222', both canonical;
  parent_mobile None -> skipped as established-legit empty).
- User role=teacher: 0 rows (no shadows yet — lazy at first login).
- Lead: 0 rows.
- REVIEW divergent pairs: none. No-shadow teachers: [1] (expected; login
  recreates via L2 pair-consistent path). Cross-scope: none.
- Report artifact: Kharazmi_Server/mobile_backfill_report.txt.

## Interpretation
Seed/dev DB has no legacy formats (all seed values canonical), so this run
only proves the SCRIPT runs end-to-end (collect -> analyze -> report).
Real legacy data lives in production; the script + conflict/INVALID review
flow will matter at deploy time. ESC hatch stays until then.
--apply deliberately NOT executed (nothing to apply + no permission).
