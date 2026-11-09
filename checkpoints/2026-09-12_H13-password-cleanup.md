# Checkpoint — H13 hardcoded-postgres-password cleanup

Date: 2026-09-12. 2 ops, anchors asserted. No compile/run.

## Step 1 — default changed (no blocker found)
- models.py:32 → :32-33: default `postgresql://postgres:13809054@localhost/gaj_db`
  replaced with `sqlite:///gaj_db.db` + FIX H13 comment. Semantics identical to
  active .env (same relative string, real boot CWD=Kharazmi_Server).
- Blocker analysis (done BEFORE changing): zero postgres-only SQL in prod code
  (no psycopg2 import, no ILIKE/ON CONFLICT/JSONB); get_next_sequence_value uses
  portable update().returning() (SQLite 3.35+); models alter-code is
  try/except-tolerant; prior permitted boot test ran the full patcher on sqlite.
  Postgres REMAINS usable via DATABASE_URL env (psycopg2-binary installed) —
  only the default changed.

## Step 2 — rotation reminder (human action, cannot do myself)
- .env DATABASE_URL = sqlite:///gaj_db.db → the postgres default was dormant,
  but IF a postgres server with password 13809054 exists anywhere, that
  password is compromised (lived in source + exports) and must be rotated on
  the server ASAP + all backups/exports treated as exposed. Needs direct DB
  access — operator task.

## Step 3 — sweep + cleanup
- scripts/backup_db.py:44 comment contained the REAL password → sanitized to
  username:password@host/database placeholder (matches :27 style). Tool reads
  URL from env (good) and is pg-only by design.
- .env.example: checked — placeholder only, no real secret; LEFT as-is.
- Verify: `grep -rn 13809054` over workspace + checkpoints = EMPTY.
- Adjacent (not fixed): backup_db.py refuses non-postgres URLs, so with today's
  sqlite .env the backup tool is non-functional — needs a sqlite path if backups
  matter (future task if ordered).
