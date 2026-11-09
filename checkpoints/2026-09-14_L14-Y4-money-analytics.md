# L14 batch Y4 — 10 money/analytics endpoints (2026-09-14, no compile/run) — L14 CLOSED

## Step 1 — overlap resolved (user's list included already-fixed items)
- reports:507/550/731 = Y1-done (guards :513/:559/:743, verified present). classes:281/468/681 =
  Y3-done (:285/:481/:701, verified present). NOT re-touched.
- True Y4 (10): finance:46/:637/:2099 (was 2098) + reports:59/:411 + analytics:153/:394/:527
  (were 391/524) + automation:118/:126.

## Step 2 — classification & decisions
- PER-STUDENT → check_student_access: finance:637 class-status (:653; teacher-own needed for
  invoices — verify_financial_idor would wrongly 403 teachers).
- PER-TEACHER-filtered: finance:46 searchAdvanced (:53+; staff full, teacher own-courses/students
  only — InvoiceActivity teacher flow; student/parent 403). reports:411 (:421 gate; teacher
  self-forcing code below kept — ReportActivity:178 teacher flow).
- AGGREGATE staff-only: reports:59 chart-data (:65), analytics:153 (:160), :394 excel (:399),
  :527 pdf (:532). Zero/finance-staff callers (ChartActivity admin-only in app; analytics zero callers).
- CONFIG admin-only: automation:118 (:120), :126 (:131) — symmetric with admin-only writes.

## Step 3 — the two known sloppinesses
- finance:2099 (:2120): «ادمین و منشی» comment now ENFORCED via dep swap.
- analytics:153/:394/:527: all three staff-only; internal _="admin" direct calls bypass deps
  (unaffected) — the missing role check on :153 is now the dep itself.

## Step 4 — final bypass sweep: clean (get_logged_in_teacher None-return ✓, automation writes
admin-only ✓, finance:1382 chain previously verified, reports:162 admin-shares ✓). No new findings.

## Step 5 — traces
- :46: staff full; teacher filtered (own only); student search «...» → 403.
- :637: staff pass; owner-teacher pass; self/own-parent pass; other student → 403 helper.
- :2099: staff pass; teacher/student/parent → 403 dep. Debtors+PII CLOSED.
- :59/:153/:394/:527: staff pass; all others → 403 dep.
- :411: staff pass (either user_type); teacher → forced self; student/parent → 403 gate.
- :118/:126: admin pass; secretary/teacher/student/parent → 403 dep.
- Legit preserved: teacher invoicing (search+status own) ✓, ReportActivity teacher summary ✓,
  ChartActivity (admin) ✓.

## Verify: ast.parse ×4 (static) + grep.
## L14 FINAL: 42/42 closed (R1:4 + Y1:10 + Y2:8 + Y3:10 + Y4:10) + 2 bonus step-3 findings (broadcast, homework).
