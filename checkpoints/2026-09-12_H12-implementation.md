# Checkpoint — H12 implementation (b1 backfill + reset upgrade)

Date: 2026-09-12. 7 ops, 2 files, anchors asserted + visual read-back. No compile/run.

## Step 1 — main.py backfill (b1)
- Deleted old :255 `t.password = str(code)` (ASCII-prefix match, unique).
  Block :249-256 now: code=get_next_sequence_value(db,"teacher",101) →
  t.teacher_code=code only → commit.
- Print new :256: "کدهای ترتیبی برای N معلم قدیمی صادر شد (پسوردها دست‌نخورده باقی ماندند)."
  (States non-touch explicitly so operators don't assume a reset.)

## Step 2 — reset_teacher_password (admin.py:1510-1557)
- Imports: `import secrets` (:11) + get_next_sequence_value added to :19
  top import (zero circular risk — line already imports from dependencies).
- Generation block :1516-1521: new_code=get_next_sequence_value(db,"teacher",101)
  (same counter as register + backfill → all three draw collision-free from one
  sequence; UNIQUE 500 risk gone) + new_password = C12 secrets 8-char readable.
- Hash :1527 hash_password(new_password); shadow-sync untouched (copies new hash).
- Response :1555 "new_password": new_password (plaintext once, C12-style, for
  admin-to-teacher relay).
- Details line UNCHANGED: logs old hash + new CODE only — new plaintext password
  does NOT leak into activity_logs. (old hash in log = pre-existing hygiene note,
  untouched.) `import random` (:1478) now unused — left, harmless.

## Step 3 — passwordless edge: fails closed, managed path exists
- Teacher.password = Column(String), nullable, NO default → None possible.
- verify_password (deps): `if not hashed_password: return False` → login gives
  clean 400 "رمز عبور اشتباه است" (no crash, no silent weirdness).
- Hashing block skips falsy passwords (same `if t.password and ...` guard).
- So a hypothetical passwordless future row: cannot log in (clear 400) → admin
  issues working password via reset_teacher_password (exactly its job). Before
  this fix such a row would have silently received a GUESSABLE password — the
  new behavior (explicit reset) is strictly better.
