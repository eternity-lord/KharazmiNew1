# Checkpoint — B1 money-in: conditional UPDATE (H8 pattern) — 2026-09-12

Task: Batch 1 of the with_for_update fix plan — both money-IN paths converted from
pessimistic-lock + Python read-modify-write to H8-P4 conditional UPDATE + rowcount check.
Report only, no compile/run. All edits in `routers/finance.py` (Kharazmi_Server).

## Step 1 — submit_payment (def ~:166)
- :170-172 — Student read WITHOUT with_for_update (validation/branch only) + FIX B1 comment.
- :190 — linked_enrollment read, lock removed (explicit enrollment_id path).
- :199 — linked_enrollment read, lock removed (auto single-enrollment path).
- :205-208 — current_w_t/current_w_i REMOVED → add_teacher/add_institute = 0 accumulators.
- :239-241 — "both" branch: only sets shares (add_*), no wallet write.
- :281 — "teacher" branch: add_teacher = data.amount.
- :300 — "institute" branch: add_institute = data.amount.
- :318-320 — else (legacy unknown wallet): no-op, no in-branch sync (components untouched → total untouched).
- :337-353 — atomic Student UPDATE (COALESCE+add on both wallets, synchronize_session=False);
  wallet_rows != 1 → rollback + 404 (existence only). Runs only if add_* nonzero.
- :355-371 — Transaction linking UNCHANGED + atomic total_paid UPDATE
  (WHERE id AND is_deleted=False); paid_rows != 1 → rollback + 409 «ثبت‌نام هم‌زمان حذف شد».
- :373-377 — order: raw UPDATEs → db.refresh(st) (:376) → st.sync_wallet_balance() (only if UPDATE ran).
- :380-382 — final_w_t/final_w_i read from the REFRESHED object for the response.
- Untouched: Bug9 branch logic, Bug22/Bug10 validations, receipt creation, installment auto-allocation block.

## Step 2 — pay_installment_manually (def ~:1185)
- :1194-1195 — inst read WITHOUT lock (early 404/400-paid/400-amount checks KEPT as fast path).
- :1203-1204 — enroll read WITHOUT lock; :1206-1207 — student read WITHOUT lock.
- :1219 — inst_amount frozen at validation time.
- :1221-1233 — atomic CLAIM: SET is_paid=True, paid_at WHERE id AND is_paid=False AND is_deleted=False;
  claimed_rows != 1 → rollback + SAME 400 «این قسط قبلاً تسویه شده است» (idempotency preserved, no new error).
- :1235-1246 — atomic wallet_institute += inst_amount (COALESCE); wallet_rows != 1 → rollback + 404.
- :1248-1259 — atomic total_paid += inst_amount (WHERE id AND is_deleted=False); paid_rows != 1 → rollback + 409.
- :1261-1263 — db.refresh(student) → student.sync_wallet_balance() (bulk skips before_update listener).
- :1265-1280 — fresh deposit Transaction built ONLY after all three UPDATEs (sequence consumed after gates);
  construction lines byte-identical (read only unchanged fields id/amount/due_date). flush + ActivityLog + commit unchanged.

## Step 3 — lock/RMW sweep (verified by grep)
- Remaining `.with_for_update()` calls (7, ALL B2/B3, untouched): :699/:737/:777 callback,
  :961/:1002/:1028 refund, :1129 update_installment. (Note :1168/:1301/:1310/:1588 lock-free reads are
  pre-existing: delete_installment, remind, invoice — never had locks.)
- Zero RMW leftovers in both B1 functions: no current_w_*, no st.wallet_* assignments,
  no linked_enrollment.total_paid =, no inst.is_paid =, no student.wallet_institute =, no enroll.total_paid =.
- No import changes (func, HTTPException already imported).

## Judgments (deviations from the literal sketch, all preserving old behavior)
1. COALESCE(col,0)+amt instead of plain col+amt — columns are NULLABLE (models.py:128-129,226) and old
   code did None→0; without COALESCE a NULL wallet would swallow the payment (NULL+X=NULL).
2. Enrollment-mid-delete → 409 (task said «clear error», code was mine; H8-consistent concurrent-modification).
3. Claim-miss → SAME 400 (per instruction; theoretically conflates concurrent-pay with concurrent-delete —
   negligible window, no re-read, as ordered).
4. else-branch skips sync too (old code synced a possibly-stale object; skipping is strictly safer).
5. submit_payment's auto-allocation-to-old-installments block left untouched (out of B1 scope).

## Step 4 — race traces (delivered in report)
- submit_payment A(+30k)/B(+20k) concurrent → 150k exact, both receipts succeed (no loss, no false conflict).
- submit_payment vs mid-flight enrollment delete → rowcount 0 → full rollback + 409, no partial wallet credit.
- pay_installment double-click → winner claims + 1 receipt; loser rowcount 0 → same 400, no receipt consumed.
- pay_installment two DIFFERENT installments concurrently → both succeed, wallet/total exact (no over-serialization).

## Next
B2 (money-out: refund :961/:1002/:1028 + reverse_session + update_transaction :873-adjacent) and
B3 (deletes + submit-guard) NOT started — awaiting user order. Standing rule: checkpoint after every task.
