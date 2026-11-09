# Checkpoint — H7 implementation: per-student branch on session charges — 2026-09-12

Task: implement option (b) — charge_branch = st.branch_id or course.branch_id, Bug-9-style 400
if both None. Report only, no compile/run. No import/signature changes needed.

## Step 1 — submit_session_and_calculate (routers/attendance.py)
- :478-483 — branch resolution inserted after wallet mutation, before sync/Transaction:
  `charge_branch = st.branch_id if st.branch_id is not None else course.branch_id`;
  None → db.rollback() + 400 «شعبه این دانش‌آموز یا کلاس مشخص نیست؛ امکان ثبت شارژ مالی نیست».
  Single final commit ⇒ raise anywhere in loop = full rollback (mirrors existing mid-loop 422s + B1/B2/B3 gates).
- :492 — `branch_id=charge_branch` added as 2nd Transaction field (finance.py convention).

## Step 2 — edit_past_session (routers/attendance.py)
- :795-800 — identical block (12-space, true block level). :810 — identical branch_id field.
- Pre-existing 16-space tail (sync/NOTE/db.add) TOUCHED NOTHING — left byte-identical (see finding below).

## Step 3 — verification
- Insertion-only by construction (script asserted old anchors contained verbatim); post-grep: amount ×2,
  share_teacher ×2, payment_method "System" ×2, description ×2 — all intact. Only ADDED lines: 2×(6-line
  computation + 1 field) = 14 lines, zero modified lines.
- Cross-branch trace: student branch=2 in class branch=1 → st.branch_id (2, not None) wins → Transaction
  branch_id=2 (course's 1 unused) ⇒ branch-2 P&L symmetric with the student's Bug-9 deposits. Fallback:
  st None + course 1 → 1. Double-None → 400 + rollback pre-commit.
- No effect on amounts/shares/descriptions (untouched lines), no signature/import changes.

## CRITICAL PRE-EXISTING FINDING (NOT H7, NOT fixed — out of scope)
- edit_past_session charge tail (~:803+: 16-space `st.sync_wallet_balance()` + NOTE + db.add/Transaction
  after 12-space wallet lines) is an IndentationError by grammar (pure spaces per cat -A, no tabs; statement
  indented with no opener). Deduced-from-reading (no compile/run performed): routers/attendance.py cannot be
  imported ⇒ app cannot start while this stands. Present since ≤B3 reads (H5/H6-era + NOTE insertion), never
  caught under the no-compile rule. H7 lines avoid the area (correct 12-level). OFFERED: mechanical re-indent
  16→12 of that tail + verification — needs explicit order (touches the is_billed NOTE region).
