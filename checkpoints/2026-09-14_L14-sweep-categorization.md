# L14 sweep + categorization (read-only, 2026-09-14)

## Step 1 — Fresh count
- 194 total endpoints. login-only (check_user_login|get_current_user, no strong dep): **93** (was 97).
- 13 no-auth endpoints: login/OTP/register/payment-callback/parent-portal — by design, OUT of L14
  (payment_callback already carries TODO(security) from audit-v2/#12).
- Of the 93: **51 already safe** (in-body guards from audits/H-fixes, or inherently safe) → **real L14 = 42**.

## Step 2 — Categorization
### RED (4) — unauthorized writes/side-effects
- branches.py:126 POST /resources (create equipment) / :149 PUT /resources/{id} / :182 POST /resources/bookings (squat/DoS)
- finance.py:1753 POST /finance/installments/{id}/remind — SENDS REAL SMS + SmsLog (top 🔴: cost + harassment)

### YELLOW (38) — sensitive reads, incl. 5 PARTIAL-guard traps (teacher-only checks, student/parent OPEN)
- admin: 46 dashboard(last txn+name) / 299* full_profile+txns / 460 share-config / 501 pending+prices / 1306 settings+CARD#s / 1442 student-PII-search / 1468 teacher-PII-search
- analytics: 153 revenue/debt / 293 per-teacher+wallet / 391 excel / 524 pdf (=153 data; direct-call _="admin" harmless — :153 itself has no role check, just unguarded)
- attendance: 326 any-class roster / 593 history+costs
- automation: 118 rules / 126 logs (low)
- classes: 128 catalog+rosters (low) / 281 tuition-debt / 468 mobiles+debt / 681 wallets+attendance
- finance: 46 fin-search / 637 wallet-status / 2098 debtors+PII (comment says "# ادمین و منشی" but unenforced!)
- reports: 59 income-charts (only shares gated) / 411 institute-or-any-teacher financials / 507+550 statements / 731 profile-print
- students: 206 FULL ROWS (worst read) / 218 id+name+code / 300 grades / 414* full-PII / 593 installments
- teachers: 200* classes+rosters / 271* incomplete / 311* full+PII+revenue / 384 PII+card / 630 pending-settlement / 882 settlement-history
(* = partial guard: teacher path checked, student/parent pass through!)

### GREEN (51) — verified guarded (verify_financial_idor / check_student_access / role+ownership / self-scoped)
auth all 8, attendance 11, finance 10, teachers 4 (72/121/169/504), students 3 (373/540/660), classes 3 (76/929/1093),
exams 2 (check_student_access), ai, calendar:154, branches:227, finance:1382/1971 + inherently-safe 7
(analytics:351 aggregates, branches:114/170, calendar:72/77, main:89 /uploads — uuid4 filenames = capability URLs).

## Step 3 — Batching (fix patterns per existing helpers)
- R1 (4): branches 126/149/182 → check_admin_or_secretary_access; finance:1753 → admin/secretary (+owner-teacher?).
- Y1 student-data (10): students 206/218/300/414/593 + admin 299/1442 + reports 507/550/731 → check_student_access (student/parent-self, teacher-own, staff-pass).
- Y2 teacher-data (8): teachers 200/271/311/384/630/882 + admin 1468 + analytics 293 → teacher-self (get_logged_in_teacher+id) + staff gate; students/parents 403 (or narrow catalog where legit).
- Y3 classes/ops (10): classes 128/281/468/681 + attendance 326/593 + admin 46/460/501/1306 → staff-only for admin/config; teacher-own-or-involved for class reports; students own-class-only where the app needs it.
- Y4 money/analytics (10): finance 46/637/2098 + reports 59/411 + analytics 153/391/524 + automation 118/126 → staff-only aggregates; per-student → verify_financial_idor (CAVEAT: it 403s teachers entirely — use check_student_access where teachers legitimately need access).
- Helpers exist: check_student_access (dependencies.py:406), verify_financial_idor (finance.py:723), get_logged_in_teacher (reports.py), check_admin_or_secretary_access.
