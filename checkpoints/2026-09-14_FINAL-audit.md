# FINAL ruthless audit (2026-09-14; report-only, ZERO code changes)

## ⚠️ INCIDENT (mine, disclosed): prod DB hash changed 13d7214f→aefdf3c8
Cause: pytest ran WITHOUT DATABASE_URL → 7 test files `import main` → auto_patch_database()
ran against default sqlite:///gaj_db.db → seeded 8 default automation_rules (count-gated).
Forensics: ONLY change is those 8 app-own idempotent rows (any prod boot does the same);
all user tables pristine (students 2, teachers 1, courses 1, txns 1, enrollments 1, users 0);
zero test-named rows. Left as-is (byte-restore impossible; delete = pointless churn).
NEW CANONICAL HASH: aefdf3c89cbf47db77cb34ad41c445560b50c6024dfed7f19c2d34ee2f7511fb
STANDING LESSON: pytest/ANY import main MUST run with DATABASE_URL=/tmp copy.

## S1 security
- F-A1 (med-low): GET /analytics/classes (analytics.py:353) NAKED — any login sees all-class
  grade/attendance aggregates; sibling /analytics/teachers is staff-only (L14/Y2). Leftover.
- F-A2 (question): revenue_summary + teacher_settlements_summary ADMIN-only vs
  reports/financial_summary staff+teacher — inconsistent pair; deliberate or leftover?
- CLEAN: ~56 other login-only endpoints fail-closed; temp_parent blocked; no denylist patterns;
  suspension gates on all 7 entry paths; main.py index pattern SQLite-safe.

## S2 money
- F-B1 (latent HIGH, flag-off): payment callback double-credit race + mock verify + trusts query
  status — behind PAYMENT_GATEWAY_ENABLED=false with rewrite TODO. Must-fix before enabling.
- F-B2 (low): login shadow-user race → 500 on simultaneous first-login (unique backstop, self-heals).
- CLEAN: refund per-type (M16), F1-A, rotation, H7, CAS updates, delta-correct txn edit.

## S3 server/data
- F-C1 (medium): add_enrollment split commit (crash→txn enrollment_id=None→refund skips total_paid
  unwind = money leak) + missing branch_id + no remittance_number.
- F-C2 (low-med): online-reg + register_and_enroll txns missing branch_id (branch reports miss them).
- F-C3 (low): create_installment audit split-commit; convert_lead no-enrollment window.
- F-C4 (low): /attendance/get raw date compare (Gregorian silently misses).
- F-C5 (low/hygiene): /test/transaction_logic writes prod (self-cleaning; crash→leftovers).
- F-C6 (med/design): finalize_live empty-roster→ALL Present+charged; LiveEndBody.date ignored.
- F-E1 (med-low): reportlab NOT in requirements → PDF endpoints 500 in prod.
- CLEAN: shadow syncs, mobile norm, txn branches, auto_patch clean on real schema.

## S4 Android (read-only, no compile)
- F-D1..D4 (all minor): hardcoded English login error; 2 dead login XML views; settle no client
  double-guard (server backstop holds); raw e.message on pay failures.
- CLEAN: strings discipline, pay idempotency, loading states, 401/403 handling, durable queue,
  no empty listeners, no ignored inputs.

## S5 tests
- 253 pass / 14 fail = 13 obsolete-signature TypeErrors (coverage gap, recommend updating tests)
  + 1 reportlab-missing (exposed F-E1). import main CLEAN; auto_patch CLEAN; mini-E2E 10/10.
