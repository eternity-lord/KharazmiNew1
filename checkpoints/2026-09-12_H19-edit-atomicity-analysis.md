# Checkpoint — H19 analysis: edit_past_session date-collision + atomicity

Date: 2026-09-12. READ-ONLY (no code changed). No compile/run.
Full live code: attendance.py:681-858 (verified verbatim this turn).

## Step 2 — date change: STILL OPEN
- data.date exists (schemas.py:125); session.date=data.date at :746, committed
  at :754 with NO try/except. Partial unique index uq_session_course_date_active
  (models.py:306-311) on (course_id,date) where active. NO Bug-17-style
  pre-check in edit (submit has one; edit doesn't).
- Collision → IntegrityError at :754 → uncaught → raw 500, AFTER reverse
  committed (:744→deps:360). Stranded + inconsistent: txns archived, wallets
  credited, Attendance deleted, while SessionLog keeps OLD date/amounts
  (the :754 txn rolled back) → display shows costs that no longer exist.

## Step 3 — NOT atomic: THREE separate commits
- #1 inside reverse (:744→deps:360): archive txns + credit wallets + DELETE
  all Attendance rows — COMMITTED.
- #2 at :754: date + snapshot fields — UNPROTECTED.
- #3 at :837: rebuild — IntegrityError→409 backstop, but rollback covers
  rebuild only; reverse stands.
- Post-reverse deterministic failures: (a) :754 date-collision 500;
  (b) :809-810 H7 branch 400 — the :806 comment ("همه‌چیز rollback می‌شود")
  is FACTUALLY WRONG (commit #1 stands); (c) :837 race-409 self-heals via
  the winning concurrent request (not stranded); (d) any unexpected
  exception :744-:837 → stranded.
- B2 atomic-claim made reverse IDEMPOTENT (no double-credit), NOT atomic
  with rebuild. Different problem; correctly solved, but not this one.

## Step 4 — proposals (not applied)
- F1: Bug-17-style date pre-check BEFORE reverse (right after settled block,
  honoring the 409-before-422 convention): active same-course+date session
  with id!=self → 409. + F1b: wrap :754 in try/except IntegrityError→409
  (same message) as race backstop, mirroring :836.
- F2: hoist H7 branch validation pre-reverse (after membership check): same
  condition (existing student + should_charge + no branch anywhere) → same
  400, before the point of no return. Keep in-loop check as zero-cost
  backstop; FIX the wrong :806 comment.
- F3 (optional/bigger): single-transaction (flush-only reverse). Shared with
  delete :872 + tests; needs care. Recommend F1+F2 now (all VALIDATABLE
  failures pre-reverse); residual = DB-crash-level only → document + defer.
- Already solved implicitly: settled-lock, C1/membership/shares pre-reverse,
  idempotent reverse, C2 backstop, H7 branch existence (just misplaced).
