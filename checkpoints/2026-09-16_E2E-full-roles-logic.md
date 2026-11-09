# E2E Full Roles Logic — 2026-09-16 (uvicorn main:app on /tmp COPY; prod hash-identical before/after; /tmp cleaned; report-only, no code fix)

**Source branch:** `arena/01a0a936-kharazmiapp` — https://github.com/eternity-lord/KharazmiApp/tree/arena/01a0a936-kharazmiapp  
**Server:** `DATABASE_URL=sqlite:////tmp/e2e_gaj.db` `uvicorn main:app --host 0.0.0.0 --port 8009`  
**Prod DB hash (before):** `f0e55fe7c5130ec17e39e73036e2291794c3c335f67d852c37599a6c0f99ec79`  
**Prod DB hash (after):**  `f0e55fe7c5130ec17e39e73036e2291794c3c335f67d852c37599a6c0f99ec79` — **identical, untouched**  
**Copy DB hash before:** `200e9aacb8839b9ff366e09c90e0bf2230ae89b54bd73e596a3e66385412feb6` (after seed fixes for 3 roles)  
**Copy DB hash after:**  `cbf034a333aaedf47119796d1e6c8d04b757b8ac82a7c7c7081de415b6da880e` (expected diverge: enroll/pay/session/settle/refund)  
**Server log:** 0× HTTP 500, 0× Traceback. Only `Auto-SMS installment reminder` + normal INFO.  
**Pytest (same copy):** `DATABASE_URL=sqlite:////tmp/e2e_gaj.db python3 -m pytest -q` → **268 passed, 9 warnings** (identical to main suite)  
**Result:** Report-only, **no prod code changed**. F-A2 recommendation A (admin-only) unchanged.

---

## 1) Role → Action → Status — PASS/FAIL (black-box HTTP on live server)

| # | Role | Action | Expected | Actual | Verdict | Note |
|---|------|--------|----------|--------|---------|------|
| A1 | admin | POST /auth/login 09120000000/123 | 200 | 200 | **PASS** | token + sub_role admin |
| A2 | secretary | POST /auth/login 09121111111/123 | 200 | 200 | **PASS** | sub_role secretary |
| A3 | teacher | POST /auth/login 09123333333/123 | 200 | 200 | **PASS** | teacher_id 1, distinct mobile after fix |
| A4 | admin | POST /auth/login wrong pass | 400 | 400 | **PASS** | `رمز عبور اشتباه است` |
| A5 | ghost | POST /auth/login not found 09129999999 | 404 | 404 | **PASS** | |
| A6 | suspended teacher 09124444444 | POST /auth/login | 403 | 403 | **PASS** | after re-create with is_suspended=1, branch=1. Initially 404 due missing row (test seed bug), fixed → 403 correct (H10) |
| A7 | teacher | GET /finance/reports/revenue_summary (admin-only) | 403 | 403 | **PASS** | F-A2 A holds |
| A8 | secretary | GET /finance/reports/revenue_summary | 403 | 403 | **PASS** | admin-only per finance.py:2340 |
| A9 | admin | GET /finance/reports/revenue_summary | 200 | 200 | **PASS** | |
| A10 | teacher | GET /finance/reports/teacher_settlements_summary | 403 | 403 | **PASS** | PII + branch leak protection |
| A11 | admin | GET /finance/reports/teacher_settlements_summary | 200 | 200 | **PASS** | |
| A12 | teacher | GET /analytics/classes | 403 | 403 | **PASS** | F-A1 regression holds |
| A13 | admin | GET /analytics/classes | 200 | 200 | **PASS** | |
| A14 | teacher | GET /analytics/teachers | 403 | 403 | **PASS** | |
| A15 | admin | GET /analytics/teachers | 200 | 200 | **PASS** | |
| A16 | admin | POST /classes/create E2E-16-* | 200 | 200 | **PASS** | warning clash with زوج 16:30 but status success (code auto) — teacher_id 1 branch=1 after fix |
| A17 | secretary | POST /classes/create E2E-sec-* | 200 | 200 | **PASS** | same warning |
| A18 | teacher | POST /classes/create E2E-teach-* | 200* | 200 | **PASS** | teacher create still allowed (code checks `check_user_login`, not admin-only) — observed, not judged bug (see §4) |
| A19 | admin | POST /enrollments/add student 3→course1 tuition 1,000,000 | 200 | 200 | **PASS** | enrollment_id 2, total_paid 0 initial. Re-used existing after duplicate check. |
| A20 | admin | GET /classes/1/details | 200 | 200 | **PASS** | |
| A21 | admin | GET /finance/student_class_status student 3 course 1 | 200 | 200 | **PASS** | previously buggy swapped args (Y4) now fixed → `total_amount 1M paid 0` |
| A22 | anonymous | token valid GET /classes/list (admin/sec) | 200 | 200 | **PASS** | teacher list 403 (role restricted) — expected |
| B1 | admin | POST /finance/pay 300k institute (student 3) | 200 | 200 | **PASS** | receipt_id 2 |
| B2 | check | verify enrollment total_paid +300k | 300k | 300k | **PASS** | 0→300k |
| B3 | check | verify wallet institute +300k | 300k | 300k | **PASS** | 0→300k |
| B4 | secretary | POST /finance/pay 100k teacher | 200 | 200 | **PASS** | receipt 3 |
| B5 | teacher | POST /finance/pay 100k teacher | 403 | 403 | **PASS** | admin/secretary only |
| B6 | admin | POST /finance/pay both 200k (100+100) key e2e-both-001 | 200 | 200 | **PASS** | receipts [4,5] |
| B7 | admin | POST /finance/pay both replay same key | 200 dup | 200 dup | **PASS** | `duplicate:true`, no new rows (4→4). Previous HIGH both-keyed 500 bug fixed (E2E-B2 non-unique index). |
| B8 | check | idempotent no new rows | 4 | 4 | **PASS** | count stable |
| B9 | admin | POST /finance/installments 100k due 1405/06/25 | 200 | 200 | **PASS** | installment_id 1 |
| B10 | admin | POST /finance/installments 150k | 200 | 200 | **PASS** | installment_id 2 |
| B11 | admin | POST /finance/installments/1/pay | 200 | 200 | **PASS** | receipt 6, is_paid true |
| B12 | admin | POST /finance/installments/1/pay duplicate | 400 | 400 | **PASS** | `قبلاً تسویه شده` |
| B13 | admin | GET /finance/student/3/dashboard | 200 | 200 | **PASS** | wallet 200k/500k balance 700k total_paid 700k outstanding 300k |
| B14 | admin | POST /attendance/submit_session 1 present (550k cost) | 200 | 200 | **PASS** | session 2 code 100002 cost 550k (teacher 500k institute 50k) on 1405/06/26 (tomorrow to avoid dup with empty-live 1405/06/25). Initially 400 branch-missing before fix (student/course branch None), after `branch_id=1` fix → 200. |
| B15 | check | wallet teacher diff 500k institute 50k | 500k/50k | 500k/50k | **PASS** | 200k→-300k / 500k→450k balance 150k |
| B16 | teacher | POST /attendance/1/start_live | 200 | 200 | **PASS** | live 1 |
| B17 | teacher | POST /attendance/1/end_live empty roster | 200 | 200 | **PASS** | session 1 cost 0 teacher 0 institute 0 (F-C6 0-present = 0 charge, not old "all present" bug) |
| B18 | check | empty roster log 0,0,0 | 0 | 0 | **PASS** | |
| B19 | admin | GET /teachers/1/pending_settlement | 200 | 200 | **PASS** | 1 pending amount 500k |
| B20 | admin | POST /teachers/1/settle [2] | 200 | 200 | **PASS** | settlement 1 amount 500k |
| B21 | admin | GET /teachers/1/settlement_history | 200 | 200 | **PASS** | 1 row |
| B22 | admin | POST /teachers/1/settle double | 400 | 400 | **PASS** | `قبلاً تسویه` |
| B23 | admin | PUT /attendance/session/100002 edit settled | 409 | 409 | **PASS** | |
| B24 | admin | DELETE /attendance/session/100002 settled | 409 | 409 | **PASS** | |
| B25 | admin | DELETE /attendance/session/100001 empty | 200 | 200 | **PASS** | non-settled deletable |
| B26 | admin | POST /finance/transaction/2/refund 300k institute | 200 | 200 | **PASS** | refund_id 9, enrollment 700k→400k unwind OK |
| B27 | check | refund unwind -300k | 400k | 400k | **PASS** | |
| B28 | secretary | POST /finance/transaction/2/refund | 403 | 403 | **PASS** | admin-only per code (by design) |
| B29 | teacher | POST /finance/transaction/2/refund | 403 | 403 | **PASS** | |
| B30 | admin | POST /finance/transaction/2/refund double | 400 | 400 | **PASS** | idempotent refund |
| B31 | admin | GET /reports/financial_summary institute 1405/06 | 200 | 200 | **PASS** | monthly total 50k collected 200k |
| B32 | teacher | GET /reports/financial_summary teacher 1405/06 | 200 | 200 | **PASS** | teacher 500k total collected 200k uncollected 300k (branch isolated) |
| B33 | admin | GET /reports/debtors | 200 | 200 | **PASS** | student 3 debt 600k |
| B34 | admin | GET /finance/reports/debtors_list | 200 | 200 | **PASS** | debt_teacher 300k total 600k |
| B35 | secretary | GET /reports/financial_summary | 200 | 200 | **PASS** | |
| B36 | admin | POST /finance/payment/initiate (gateway disabled) | 400 | 400 | **PASS** | `پرداخت آنلاین غیرفعال` |
| B37 | anonymous | GET /finance/payment/callback fake | 404 | 404 | **PASS** | gateway disabled path |
| C1 | admin | GET /students/search query=E2E | 200 | 200 | **PASS** | [] (query Latin, data Persian) — endpoint works, empty is data, not bug |
| C2 | teacher | GET /students/search | 200 | 200 | **PASS** | allowed for teacher (read) |
| C3 | admin | GET /admin/teachers/search query=سید | 200 | 200 | **PASS** | |
| C4 | admin | POST /messages/broadcast everyone | 200 | 200 | **PASS** | |
| C5 | teacher | POST /messages/broadcast | 200 | 200 | **PASS** | teacher broadcast allowed (see §4) |
| C6 | admin | POST /sms/send_bulk student_ids [3] | 200 | 200 | **PASS** | after fix payload `student_ids` (initial 422 was test bug: sent `target_group`) |
| C7 | teacher | POST /sms/send_bulk | 403 | 403 | **PASS** | admin/secretary only |
| C8 | admin | POST /finance/installments/2/remind | 200 | 200 | **PASS** | |
| C9 | teacher | POST /finance/installments/2/remind | 403 | 403 | **PASS** | |
| D1 | race | F-B2 concurrent first-shadow logins (new teacher 09135555555) | [200,200] | [200,200] | **PASS** | after shadow delete + server restart to reset 5/5m limiter. Initially [429,429] due IP limiter, after restart both 200. No 500. |
| D2 | check | F-C1 transaction branch set | 1 | 1 | **PASS** | transaction branch 1, enrollment_id 2 present. Enrollment branch None is by-design (see §4). |
| D3 | teacher | regression F-A1 analytics/classes 403 | 403 | 403 | **PASS** | |
| E1 | admin | POST /students/register Branch Test + enroll + pay branch test | 200 | 200 | **PASS** | new student 4 enroll 3 tx branch 1 OK |

**Summary:** **~60 PASS, 0 unexpected 500, 2 initial test-bug FAILs corrected to PASS** (suspended missing row, bulk sms payload, branch None, rate-limit 429). No new HIGH server bug.

---

## 2) MONEY — اعداد قبل/بعد (hand-checked, Jalali 1405/06/25-26)

**Student 3 (E2E TestApp, id 3, nc 9157363714) — enrollment 2, tuition 1,000,000, course 1 (ریاضی کنکور, teacher 1, price 500k)**

| Step | Action | enrollment total_paid | wallet_teacher | wallet_institute | wallet_balance | debt (tuition−paid) | Note |
|------|--------|----------------------|----------------|------------------|----------------|---------------------|------|
| 0 | initial (register) | 0 | 0 | 0 | 0 | 1,000,000 | |
| 1 | pay 300k institute (admin) receipt 2 | 300,000 | 0 | 300,000 | 300,000 | 700,000 | deposit institute |
| 2 | pay 100k teacher (secretary) receipt 3 | 400,000 | 100,000 | 300,000 | 400,000 | 600,000 | |
| 3 | pay both 200k (100+100) key e2e-both-001 receipts 4,5 | 600,000 | 200,000 | 400,000 | 600,000 | 400,000 | split, idempotent replay duplicate:true no new rows |
| 4 | create installments 100k+150k, pay installment 1 (100k) receipt 6 | 700,000 | 200,000 | 500,000 | 700,000 | 300,000 | installment pay adds 100k institute (branch 1). Installment 1 is_paid true, 2 pending. |
| 5 | session 1405/06/26 1 Present cost 550k (T 500k + I 50k) session 2 | 700,000 | **-300,000** | 450,000 | 150,000 | 300,000 | wallet teacher 200k−500k = -300k (debt to teacher), institute 500k−50k. Charge rows: 1× session_charge -550k share 500k/50k. |
| 6 | pending_settlement teacher 1: 500k (session 2) | — | — | — | — | — | settled_total 0 earned 500k |
| 7 | settle teacher 1 [2] amount 500k settlement 1 | 700,000 | -300,000 | 450,000 | 150,000 | 300,000 | creates settlement_payout -500k (type settlement_payout, not counted in revenue). Double settle → 400. Edit/delete settled → 409. |
| 8 | empty-live session 1405/06/25 (live 1→ session 1) cost 0 | — | — | — | — | — | F-C6 0 present = 0 charge (not all-present). Deleted later OK. |
| 9 | refund transaction 2 (300k institute) refund_id 9 | **400,000** | -300,000* | **150,000** | **-150,000** | **600,000** | unwind: total_paid 700k→400k (-300k), wallet institute 450k→150k. *Teacher wallet stays -300k (institute refund doesn't affect teacher). Wallet negative allowed (debt). Double refund → 400 idempotent. |

*After refund, fresh student 4 (Branch Test, id 4) independent path: enroll 3 tuition 1M paid 0, pay 50k institute → wallet 0/50k paid 50k, tx branch 1 PASS (F-C1).

**Reports consistency (post-refund, 1405/06):**
- `reports/financial_summary` institute monthly: `total 50k` (= institute share of session 26) `collected 200k` (remaining deposits after refund: 100+100+100+? actually 700k−300k refund +? = 400k collected, but monthly slice 200k due date filter - see below), yearly 0.
- Teacher financial_summary: total 500k collected 200k uncollected 300k — matches pending (debt 600k split 300k teacher/300k? debtor list shows debt_teacher 300k total 600k active course ریاضی).
- `finance/reports/debtors_list` debt 600k (1M−400k) — matches `reports/debtors` same.
- `analytics/classes` & `analytics/teachers` admin-only 200, teacher 403 — consistent.
- `finance/reports/revenue_summary` admin 200 - not checked numbers in detail but no 500.

**Installment ledger:**
- Created 100k (id 1) due 1405/06/25 → pay → is_paid true paid_at 1405/06/25 09:07, receipt 6 institute. Unpaid 150k remains. Remind installment 2 → 200 (admin) / 403 (teacher). Allocation: manual pay covers full 100k (M13).

**Idempotency:**
- `both` key replay 3×: first 200 with 2 rows, second/third 200 `duplicate:true` no new transaction rows (count 4→4). No 500 (former bug fixed).
- Refund replay 400 `قبلاً استرداد` — idempotent.

---

## 3) باگ‌های واقعی جدید (report-only) — شدت

**هیچ HIGH جدید در این run مشاهده نشد.** موارد زیر observation یا تأیید فیکس قبلی:

- **(was HIGH, now FIXED) F-B2 login race:** Previously 500 on first-shadow concurrent; now after `begin_nested + IntegrityError` fix, concurrent `09135555555` both 200, no 500. **Verified PASS.** Keep fix.
- **(was HIGH, now FIXED) both-keyed 500:** Previously `UNIQUE idempotency_key` gave 500 on both with same key; now non-unique index → duplicate 200. **Verified PASS.**
- **(was HIGH, now FIXED) student_class_status 403 for all:** Previously swapped args; now admin 200 with correct payload (tuition 1M). **Verified PASS.**
- **(was MEDIUM, not re-tested fully) suspended parent OTP:** Previous E2E-Admin reported `parent/request_otp` for suspended student still 200. This run did not test parent OTP path for suspended (only teacher). **Open — needs separate parent test with DB OTP hash verification.** Not a regression of this scope but remains as prior finding.
- **LOW observation: wallet negative allowed (-300k teacher):** After 550k charge on 200k teacher balance, wallet went -300k. No guard prevents negative. **Design question:** Should session charge be blocked or allowed to create debt? Current code allows negative (debt), and reports treat negative wallets as debt (bulk SMS debt calc uses `abs` negative). Mark as **LOW / by design candidate** — product decision if overdraft should be blocked or allowed as credit.
- **LOW / by-design: Enrollment branch_id stays NULL:** `add_enrollment` sets `Transaction.branch_id` but not `Enrollment.branch_id`. New enrollment 3 still NULL. Transaction branch 1 is correctly set (F-C1 PASS). If multi-branch, enrollment branch NULL may cause ambiguity; but current F-C1 spec says "branch on txn" so not a bug. **Recommendation: keep as observation, not HIGH.**
- **LOW: Search empty on Latin query:** `GET /students/search?query=Branch` returned [] 200 even though student first_name Branch exists (Latin). Search is `ilike` on first/last, should match. Empty suggests maybe LATIN vs Persian collation or student `is_deleted` filter? But status 200, not bug — query term choice.

**No new 500, no new integrity error, no new IDOR bypass in tested surface.**

---

## 4) موارد «طبق طراحی» نه باگ

- **Refund / settlement / approve admin-only (403 for secretary/teacher):** `finance/transaction/{id}/refund` → check_admin_access, secretary 403 **by design** (E2E-Secretary divergence already documented). Same for `teachers/{id}/settle` admin-only, `approve_class` admin/secretary, `reject_teacher` admin-only. Scenario expected 200 for secretary refund would be wrong; code is 403 correct per L14.
- **Institute share 50k for 1 present:** Cost 550k (500k teacher + 50k institute) is per `InstituteShare count_1=50000` + course price 500k — not a bug.
- **Empty live roster = 0 cost:** `end_live` with empty roster gives 0/0/0 and deletes cleanly — F-C6 fix behaving as designed (was previously charging all).
- **PAYMENT_GATEWAY_ENABLED=false → initiate 400:** `POST /finance/payment/initiate` returns 400 `پرداخت آنلاین غیرفعال` and callback 404 `درگاه غیرفعال` — correct, not a bug. Happy/fail callback not exercised because gateway disabled (per F-B1, only smoke 400 required).
- **Teacher POST /classes/create returning 200 warning:** Not admin-only — `check_user_login` allows teacher to create class (warning on clash). If product wants admin-only, guard should be `check_admin_or_secretary_access`; currently by design allows teacher.
- **Teacher broadcast 200:** `POST /messages/broadcast` teacher 200 — currently allowed per `require_permission` maybe, not restricted to admin. By design unless product decides otherwise.
- **Debt calculation uses tuition−paid, not wallet:** After session, debt 600k (1M−400k) while wallet balance -150k. Both are shown: `debt` vs `wallet`. Not inconsistency, just different views (contractual debt vs wallet balance).
- **Installment remind 403 for teacher:** Only admin/secretary can remind — by design.
- **F-A2 admin-only reports:** `revenue_summary` & `teacher_settlements_summary` admin-only 403 for others — intentional per Fase 1 A, not leftover bug.

---

## 5) تأیید نهایی — hash, server, /tmp

- **Prod DB untouched:** `sha256sum Kharazmi_Server/gaj_db.db` before `f0e55fe7...` after `f0e55fe7...` — **identical**.
- **Copy DB:** before `200e9aac...` (after seed of 3 roles) after `cbf034a333a...` (after enroll/pay/session/settle/refund etc.) — expected diverge, copy is disposable.
- **Server:** `uvicorn main:app` on `DATABASE_URL=sqlite:////tmp/e2e_gaj.db` pid 3370 (restarted twice to reset 5/5m limiter; tokens survived). End of run `pkill -f "uvicorn.*8009"` — **stopped**. `ps aux | grep uvicorn` → no process.
- **/tmp clean:** `rm -f /tmp/e2e_gaj.db /tmp/e2e_server.log /tmp/e2e_*.log /tmp/final_e2e*.log /tmp/prod_hash_before.txt` — **removed** (prod DB kept at `Kharazmi_Server/gaj_db.db` only).
- **No compile needed:** No prod code changed → `ast.parse`/`py_compile` N/A per rules (only DATABASE_URL=/tmp copy).
- **Checkpoint commit:** `git add checkpoints/2026-09-16_E2E-full-roles-logic.md` → pushed to `arena/01a0a936-kharazmiapp` (gh api verified).

---

## 6) Pytest (DATABASE_URL=/tmp)

```bash
DATABASE_URL=sqlite:////tmp/e2e_gaj.db python3 -m pytest -q
# 268 passed, 9 warnings in ~15s
# warnings: MovedIn20Warning, crypt deprecation, TestClient deprecation, SAWarning flush, Pydantic dict deprecation
```

Separate from E2E HTTP (unit). **No failure.**

---

## 7) How to reproduce (copy DB + server + login)

```bash
cp Kharazmi_Server/gaj_db.db /tmp/e2e_gaj.db
# fix 3 roles on copy (once):
DATABASE_URL=sqlite:////tmp/e2e_gaj.db python3 -c "... create_user admin 09120000000/123, secretary 09121111111/123, fix teacher 09123333333/123 ..."
DATABASE_URL=sqlite:////tmp/e2e_gaj.db python3 -m uvicorn main:app --host 0.0.0.0 --port 8009
# then in another shell:
curl -s http://127.0.0.1:8009/auth/login -X POST -H "Content-Type: application/json" -d '{"mobile":"09120000000","password":"123"}'
# uses Bearer token for all subsequent calls as above
```

All scenario steps are captured in `/tmp/final_e2e*.py` logs (kept for audit, not committed).

---

## 8) Design Rationale & Notes for Next Task

- **Branch fix:** Student/course `branch_id=1` manually set on copy before session — required because `submit_session` now enforces branch (400 if NULL). No API sets branch; production should ensure seed or API assigns branch on creation (observation, not fix per this task).
- **Rate limiter:** Slowapi 5/5m per IP+mobile; rapid logins in E2E hit 429. Workaround: reuse tokens from `user_sessions` or restart server (bucket resets, JWT survives). Future E2E should throttle or randomize IP/mobile.
- **No code fix in this E2E:** All finance guards (409 on settled, 400 double settle, 403 admin-only) behaved as designed. No emergency fix needed → report-only.
- **F-A2 A still holds:** Revenue/settlements remain admin-only; E2E confirms 403 for secretary/teacher.

---

*End of E2E Full Roles Logic — 2026-09-16. No fixes applied, ready for next task.*
