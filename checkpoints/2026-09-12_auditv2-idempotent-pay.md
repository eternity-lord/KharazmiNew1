# Idempotent submit_payment + atomic coverage loop — 2026-09-12 (impl, no compile/run)

## Step1 server: key (column-on-Transaction design)
- schemas.py:323 FinanceSubmitData.idempotency_key Optional (old clients omit → current behavior).
- models.py:273 Transaction.idempotency_key unique+nullable. Existing DBs need:
  ALTER TABLE transactions ADD COLUMN idempotency_key VARCHAR;
  CREATE UNIQUE INDEX ix_transactions_idempotency ON transactions(idempotency_key);
- finance.py:172 _replay_idempotent_payment (read-only; 422 on key-reuse with different student/amount; balances read fresh, receipts identical, duplicate:true).
- finance.py:203 pre-check at top (fast replay, never 404s on validations).
- finance.py:378 stamp key on all receipts (both-split = 2 rows, 1 key).
- finance.py:483 commit wrapped: IntegrityError + key → rollback → replay winner; else re-raise (old behavior).

## Step2 server: atomic loop finance.py:~440-480
- Per-row: refresh → skip if paid/deleted → optimistic cond-UPDATE (id + is_paid==False + is_deleted==False + coalesce(paid_amount,0)==_already), M13-cumulative + L7-Jalali preserved, is_paid+paid_at flip in SAME update.
- remaining decremented ONLY on rowcount==1 → no lost update, no over-cover. 3 tries/row → else rollback+409.
- NULL paid_amount handled via coalesce on both sides.

## Step3 app
- AppModels.kt:314 request key (nullable), :322 response duplicate flag (Gson-safe default).
- InvoiceActivity.kt:28 UUID import; :109-110 pending key+sig fields; :497-501 key-gen with form-signature (same-form retry → same key; edited form → NEW key, prevents wrong-replay + 422-stuck); :512 passes key; :530-533 success retires key, duplicate→explanatory toast; failure keeps key.

## Step4 traces (by reading)
- Timeout-then-retry (same key): req1 commits (wallets/total_paid/installments once); req2 pre-check replays same receipt_ids + fresh balances, zero writes. Concurrent double-tap: loser hits UNIQUE → replays winner.
- Same key + different amount → 422 (key-reuse bug, not retry).
- No key (old client) → byte-identical old path, incl. old IntegrityError 500.
- Two cashiers same installment: loser row retries with fresh owed (no lost update); 3 collisions → 409 → client retries with same key.

## INCIDENT this turn (recovered, verify clean)
- Patch script bug: open(models.py,"w").write(p2) wrote the PATH into models.py (file briefly contained 1 line).
- No git; recovered intact 41,325B/890-line file from /tmp/arena-workspace/changes.zip (turn snapshot 20:20, pre-clobber), verified: Transaction :241 + L4/paid_amount/LoginAttempt/penalty markers + clean tail; restored + re-applied the 2-line column (:272-273).
- All other files written this turn re-verified by read-back (schemas/finance/AppModels/InvoiceActivity).

## Residuals
- Rotation during pending payment drops the key (old behavior for that edge; ViewModel would fix).
- classes.py:791 FinanceSubmitData = dead dup (shadows import, never annotated, no cross-imports) — untouched.
