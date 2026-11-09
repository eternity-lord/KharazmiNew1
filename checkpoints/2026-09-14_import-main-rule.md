# Standing rule: import-main check + full clean pass (2026-09-14)

## New standing rule (user-set)
After every multi-file change (esp. new imports): `ast.parse` + REAL `import main`
(no full server boot) to catch NameError/ImportError that ast.parse misses.
Always on a DB COPY via DATABASE_URL (import has side effects: auto_patch runs at
import time + Live worker thread starts).

## Full pass result: IMPORT CLEAN (first try, zero fixes needed)
- `import main` (18 routers + deps) on /tmp/import_check.db: no NameError/ImportError.
- Confirms the only two import gaps in project history were the L14 ones already fixed
  (reports.py:20, analytics.py:13 — sqlite-uq checkpoint).
- Original gaj_db.db re-verified untouched.
- Note: pip packages don't persist across turns → reinstall per turn when needed.
