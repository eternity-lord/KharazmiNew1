# Checkpoint — H20 ESC + batch 3 (backfill script built, NOT run)

Date: 2026-09-12. Code ops asserted + read-back; script written, never executed.
No compile/run.

## Step 1 — ESC raw-fallback (marker H20-ESC, 10 sites, all removable post-backfill)
- login_user (auth.py:32-38 keys, :47 admin, :77-78 teacher): _login_keys =
  [canonical?, raw]; single IN query each.
- request_student_otp + student_login student lookups (auth.py:417/:516):
  IN ([mobile, _raw_mob]).
- student_login OTP selector (:491), parent_login candidates (:117) + latest
  (:137) + students (:149), request_parent_otp student_exists (:35): same.
- Throttle/rate VERIFIED untouched: H14 key + LoginAttempt reads/deletes,
  OTP recent_count/cooldown/lock/last_otp all canonical-only (grep-proof).
  Password/OTP remain the real gates; ESC only widens the selector.
- NOT touched (already dual/fallback): select_child exact-fallback,
  change_password/change_mobile OR-proofs, pair-consistent resolvers.

## Step 2 — backfill_normalize_mobiles.py (BUILT, NOT RUN — show + review first)
- Standalone script (not auto_patch: one-shot data migration, needs human
  review gate). DRY-RUN default; --apply writes. Report always written to
  mobile_backfill_report.txt.
- Skopes: Teacher.mobile, Student.student_mobile/parent_mobile,
  User.username role=teacher ONLY, Lead.mobile.
- Rules: "" skipped silently (legit); None -> INVALID (never touched);
  same-canonical within a UNIQUE scope (Teacher/Student-sm/Username) ->
  CONFLICT, all involved blocked, no auto-merge (already-canonical rows
  occupy values too); parent/Lead non-unique -> straight normalize;
  cross-scope same-canonical -> informational; teacher pair divergence
  after finals -> REVIEW + no-shadow list.
- Apply: per-row UPDATEs, single commit, counts printed.

## Step 3 — update_teacher shadow sync (teachers.py:447-459 + :~433 capture)
_old_mob captured pre-loop; after normalized overwrite, teacher-role shadow
(old-username lookup + teacher_id session fallback) renamed to canonical
with cross-User clash -> 409. Mirrors change_mobile/admin-creds. Pre-existing
divergence source closed going forward (old divergences surface in backfill
REVIEW section).
