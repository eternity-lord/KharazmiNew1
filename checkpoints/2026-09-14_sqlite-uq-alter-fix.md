# SQLite UNIQUE-inline ALTER fix (2026-09-14; test-run on COPY allowed & done)

## Step 1 — exact error (proven on scratch copy)
`ALTER TABLE transactions ADD COLUMN idempotency_key VARCHAR UNIQUE` →
`sqlite3.OperationalError: Cannot add a UNIQUE column`. SQLite forbids UNIQUE in ADD COLUMN
(it IS allowed in CREATE TABLE, which is why fresh create_all DBs never hit this).

## Step 2+3 — fixed 4 spots in main.py patches list (sweep found 3 more with same pattern)
- :235-237: teachers.teacher_code / students.student_code / session_logs.session_code:
  "INTEGER UNIQUE" → "INTEGER".
- :241-244: transactions.idempotency_key: "VARCHAR UNIQUE" → "VARCHAR" (+ comment).
- New block after L4 commit: 4× CREATE UNIQUE INDEX IF NOT EXISTS (uq_teachers_teacher_code,
  uq_students_student_code, uq_session_logs_session_code, uq_transactions_idempotency_key),
  Bug-17/H6 pattern, NULLs allowed on both engines. PG note: where inline-UNIQUE previously
  succeeded, the extra index is redundant-but-harmless.

## Step 4 — verified on fresh COPY (/tmp/uq_verify.db, lacked the column)
- `import main` + `auto_patch_database()`: no exception; log shows the ADD COLUMN;
  PRAGMA confirms column; sqlite_master confirms all 4 new uq_ indexes (+2 old).
- Second run: no-op, no error → idempotent. Original gaj_db.db verified untouched.

## BONUS (caught by this test): L14 NameError — reports.py:20 + analytics.py:13 were missing
check_admin_or_secretary_access imports (Y3/Y4 dep swaps used it) → server wouldn't boot.
Fixed both; full `import main` (all 18 routers) now passes.
## LESSON: never two parallel edit_file calls on the SAME file (second main.py edit was
silently lost by race; re-applied serially and grep-verified).
