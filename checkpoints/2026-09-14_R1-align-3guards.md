# R1-align: 3 SMS/class guard decisions (2026-09-14; copy-tested; hash-identical; /tmp cleaned)

## Changes (routers/admin.py)
1. send_bulk_sms (:1249): check_admin_access → check_admin_or_secretary_access + FIX (L14/R1-align) comment.
2. suspend_bulk_classes (:1287): UNTOUCHED guard + DELIBERATE (H10-S) comment (blast radius N, one-way True — do NOT align with bulk-sms).
3. get_sms_history (:178): check_admin_access → check_admin_or_secretary_access + FIX comment.

## Verify
ast.parse OK; real `import main` CLEAN; live secretary session: bulk→200 (1 sent), history→200 (2 items); zero Tracebacks.

## Self-report
Parallel edit_file ×2 on same file raced: history edit silently lost (reported success). Re-applied serially + grep-verified. LESSON: never parallel-edit the same file.
