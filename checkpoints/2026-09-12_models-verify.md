# models.py post-incident verification — 2026-09-12 (read-only, zero code changes)
- STEP1: ast.parse OK (892 lines).
- STEP2: 41 classes, no duplicate defs. Financial: Student 23 (wallet_teacher/institute/balance, is_deleted, version),
  Transaction 20 (+idempotency_key, is_deleted, is_reversed), SessionLog 16 (absent_penalty_*, is_penalty_settled),
  Installment 8 (paid_amount, is_paid, paid_at, is_deleted), Settlement 6. All 13 session markers present.
- STEP3: ix_transactions_student_date (L4) ✓; uq_session_course_date_active unique partial (is_deleted=FALSE) ✓;
  UniqueConstraint(session_id,student_id) name=uq_attendance_session_student (H6) ✓; idempotency_key unique ✓.
- STEP4: byte-reconcile 41325+385=41710 EXACT; 72 server files scanned, 0 dangling Model.attr refs, 0 syntax fails.
- Note: __pycache__ + /tmp snapshot are excluded paths and did not persist across turns, so the pyc cross-check
  could not run this turn; byte-reconciliation + inventory + ref-resolution is conclusive instead.
- VERDICT: models.py کامل و بدون آسیب باقیمانده تأیید شد.
