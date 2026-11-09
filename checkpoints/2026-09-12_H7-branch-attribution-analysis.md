# Checkpoint — H7 analysis: session_charge branch attribution — 2026-09-12

Task: READ-ONLY 5-step analysis (no code changes, no compile/run). Question: session_charge
Transactions built in attendance.py lack branch_id (unlike Bug-9-fixed deposits), breaking
branch P&L. Work with TODAY's code (post H2/H3/H5/H6).

## Step 1 — reference pattern (finance.py, Bug 9)
- get_user_branch_filter (finance.py:~40-56): authorization → session → (student/parent: passthrough
  param) else user's branch_id; no-auth → param; exceptions → param.
- submit_payment :176-180: `payment_branch = st.branch_id if st.branch_id is not None else
  get_user_branch_filter(...)`; None → 400 «شعبه پرداخت مشخص نیست...».
- `branch_id=payment_branch` on receipts: :249/:265 (both-split), :287/:306/:325 (single/legacy).
- pay_installment_manually :1256-1257 (same chain) + :1314 receipt. Money follows the STUDENT.

## Step 2 — attendance.py today: branch NEVER set
- "branch_id" occurs ZERO times in all of routers/attendance.py.
- Submit site (~:479-492, in submit_session_and_calculate :329): Transaction(student/course/session/
  amount/"System"/date/session_charge/shares/description) — no branch_id → NULL (Transaction.branch_id
  nullable, models.py:243).
- Edit site (~:788-800+, in edit_past_session :666): identical shape, no branch_id.
- compute_session_shares lives in financial_calculations.py:187 (pure dict computation); BOTH creations
  are outside it, in the two attendance loops (only 2 `type="session_charge"` sites file-wide).

## Step 3 — can one class span branches? YES, nothing prevents it
- branch_id = independent nullable FK on Student(:118)/Course(:174)/Enrollment(:219)/Transaction(:243)
  (+User/Teacher/Room/Resource/Lead).
- NO enforcement: classes.py contains ZERO "branch" (add_enrollment :339 sets/checks nothing);
  students.py + teachers.py contain ZERO "branch" (registration never assigns branch).
- Seeds/tests use branch_id=1 everywhere (single-branch FIXTURES — proves nothing about prod).
- Convention evidence: shadow Users inherit student.branch_id (dependencies.py:449/461).
- Split-brain attribution today: attendance COUNTS → Course.branch_id (analytics.py:207-208); MONEY →
  Transaction.branch_id (financial_calculations.py:55/76/96, reports.py:218). Bug-9 deposits sit in
  student.branch ⇒ charges must too, or branch P&L mismatches by construction.
- Extra find: main.py:164-170 startup migration backfills ALL NULL branch_id → 1 (incl. transactions)
  ⇒ bug partially masked (NULLs become 1) while MISATTRIBUTING every non-1 branch. Also masks on restart only.

## Step 4 — recommendation: (b) per-student, NOT (a) course-wide
- (b): `charge_branch = st.branch_id or course.branch_id` (+400 if both None, Bug-9-style never-unassigned);
  `branch_id=charge_branch` in both Transaction(...) sites. ~4-6 lines total (2×2 sites), NO signature change
  (neither endpoint takes authorization/branch_id today — and course is a better fallback than the clicking
  user for SYSTEM charges), NO new imports, ZERO extra queries (`st` already loaded per item in both loops).
- (a) rejected: misattributes cross-branch students (re-creates the H7 mismatch against their Bug-9 deposits);
  Course.branch_id nullable too (needs fallback anyway); saves only ~2 lines.
- P&L symmetry argument is decisive: same student's deposit is in student.branch ⇒ its charge must be too.

## Step 5 — old data (mention only, H4-in-C3-like, NO action)
- Pre-fix charges carry NULL (or startup-backfilled WRONG 1). Proper fix = targeted backfill script resolving
  each session_charge → student (→ course fallback) branch; precedent shape: scripts/backfill_link_orphan_deposits.py.
  Out of scope for the code fix; needs its own order (and prod backup).
