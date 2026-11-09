# Two small fixes (2026-09-13, no compile/run)

## Fix 1 — main.py:239-241: idempotency_key added to patches
- `("transactions", "idempotency_key", "VARCHAR UNIQUE", None)` + FIX comment.
- Matches model (models.py:273: nullable=True, unique=True) and patches-list precedent
  for UNIQUE columns (teacher_code/student_code/session_code inline UNIQUE).
- NOTE: models.py:272 comment prescribes a NAMED unique index (ix_transactions_idempotency);
  patches list has no index mechanism, so inline UNIQUE used instead — enforcement
  equivalent, index name differs (SQLite auto-index). No separate CREATE INDEX added.
- Placement: right after remittance_number (:238), same backfill concern area.
- Verified: grep + ast.parse (static only).

## Fix 2 — routers/exams.py:293-304: dual grade notification (exam → parent)
- Inserted after student send_notification (:285-292): `if st.parent_user_id is None:
  ensure_student_shadow_users(db, st)` then parent send (role="parent", type="grade").
- Mirrors students.py class-grade pattern (:281-291) incl. H2 shadow-user policy;
  title/body mirror the student message with فرزند شما + student name.
- Both helpers (ensure_student_shadow_users, NotificationService) already used/imported
  in this function — no new imports.
- Verified: re-read region + ast.parse (static only).
