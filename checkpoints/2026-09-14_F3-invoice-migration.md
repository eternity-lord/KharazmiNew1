# F3: invoice+3 migration to check_student_access (2026-09-14; live 8/8; hash-identical; /tmp cleaned)

## Changes (routers/finance.py, 4 serial edits)
- invoice get_invoice_details (:2078): verify_financial_idor → check_student_access (pattern of :653).
- payments (:1837), transactions (:1863), dashboard (:1892): same migration.
Analysis: all three return same-sensitivity data as invoice/statement (amounts/status/tracking —
no PII, no cards); dashboard is exactly the "own-student financial status" view.
Left untouched DELIBERATELY: payment/initiate (:795), receipt/print+pdf (:574/:617) — teacher-blind by design.

## Verify
ast.parse OK; real `import main` CLEAN; live teacher session 8/8 (own→200, other-class→403
on all 4 endpoints); zero Tracebacks.
