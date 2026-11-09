# Live bugs + stale tests — FULL GREEN (2026-09-12, pytest runs authorized)
## Step1 comma (main.py:260): added after M13 tuple. ast.parse green (note: bug was runtime, not syntax).
Runtime proof on COPY /tmp/patch_verify.db (real gaj_db.db UNTOUCHED): 4 backlogged columns applied
(absent_penalty_teacher/institute, paid_amount, is_penalty_settled), no exception, backfill CASEs ran clean.
Side-finding (NOT fixed, non-fatal): sequence-backfill queries transactions.idempotency_key which old DBs lack —
no patch entry for it; caught+warned. Real DB still missing the 4 cols → next server start auto-patches via :494.
## Step2 join (analytics.py:203): select_from(Attendance) + explicit ONs to SessionLog+Course; select/filter/branch identical.
Scope note: no is_deleted exclusion added (original unrecoverable; flagged, not changed).
## Step3: 10/11 green; exports=missing reportlab (installed; real dep absent from requirements.txt — env gap noted);
financial_reads last assert=Gregorian params vs Jalali-canonical endpoint (invalid 2026/09/31 → fail-closed 0) → moved to step4.
## Step4 (14 stale incl. reads): security dep-name x2; reads+softdelete Jalali params (gregorian_to_jalali, drift-proof);
refund/delete_enrollment refresh; legacy param dropped; admin soft-delete asserts (text+row-check); user/shadow links
(advanced, ai x2 incl. 2nd student for 403, students, three_critical + parent_session repoint). soft_delete: NO third bug.
Self-mistake fixed: parent_user referenced before definition → literal 12.
## Step5: 268 passed, 0 failed (13.4s). Baseline was 35 failed/269; count 269→268 = dropped legacy param case.
