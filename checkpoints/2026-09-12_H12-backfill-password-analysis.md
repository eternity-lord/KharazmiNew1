# Checkpoint — H12 backfill-password analysis (READ-ONLY, no code changed)

Date: 2026-09-12. Q: uncoded_teachers backfill sets password=str(sequential
code); C12 randomized only NEW registrations. Analyze + propose.

## Step 1 — today's block + order (main.py)
- Block :249-257: filter Teacher.teacher_code == None (ordered by id) →
  code=get_next_sequence_value(db,"teacher",101) → t.teacher_code=code AND
  t.password=str(code) ("هم‌راستاسازی پسورد و کد مربی") → commit + count-only
  print. NOTE: OVERWRITES any pre-existing legacy password.
- Hashing block :380-406 (plaintext→PBKDF2 for Users+Teachers). Order:
  backfill FIRST → str(code) gets HASHED at rest, but stays a sequential
  guessable secret (101,102,103...). user's premise CONFIRMED.
- Runs EVERY boot: auto_patch_database() at import (:414); per-row one-shot
  via the ==None filter (nothing ever resets teacher_code to None — grep empty).

## Step 2 — C12 pattern (routers/teachers.py:47-60)
- _READABLE_ALPHABET (58 chars, no 0/O/1/l/I) ×8 via secrets.choice →
  hash_password → returned ONCE as initial_password in register response.
  Register is PUBLIC self-service (5/hour limit): applicant learns own password
  from response — no admin relay needed. Backfill (boot-time, no request
  context) cannot copy this channel directly.

## Step 3 — lockout analysis
- No forced-change mechanism exists (grep empty). Nothing depends on
  password==code (only test comment test_auth.py:125; seeds use "123").
- Today a future uncoded teacher LOSES their working password to str(code) at
  next boot (lockout-by-migration; recovery = ask admin for code).
  Randomizing instead = same relay problem, but secure.
- Reality check: backfill almost surely ALREADY ran on real data (many boots
  since patcher existed) → remaining uncoded teachers ≈ none expected.

## Step 4 — RECOMMEND (b1): stop overwriting password; assign code only
- (a) randomize+relay needs a secure channel (console print is out; in-app
  notification persists plaintext in DB; file needs perms design) + admin toil
  — for an event that likely NEVER recurs. Bad economics.
- (b1): block's job is codes, not passwords. Assign code, preserve existing
  secret (hashing block still hashes it if plaintext). Kills BOTH harms
  (lockout-by-migration + manufactured guessables) with ZERO relay/logistics.
- Edge (honest): passwordless future row stays passwordless (today it'd get
  code-password). Remedy = existing reset endpoint ("teacher can't log in" is
  exactly its job). Not a regression worth keeping guessables for.
- CONCLUSION (explicit): NO block-fix reaches ALREADY-migrated teachers
  (password==code today; filter excludes them forever). Their remediation is
  OPERATIONAL: per-teacher reset via existing endpoint.
- Adjacent (future task if ordered): reset_teacher_password (admin.py:1516):
  random 100-999 with NO UNIQUE-collision check (→ possible 500) and still
  guessable-ish; natural upgrade = C12-style random + collision-safe code.
