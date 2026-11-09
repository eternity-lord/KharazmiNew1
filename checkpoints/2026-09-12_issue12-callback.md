# Issue #12 — dormant callback cleanup (2026-09-12, no compile/run)
- Step1 shown: initiate :765-778 (400 + IDOR live; dead below deleted), callback :801-~1148 (flag-gate, idempotent SUCCESS early-return, verify→6 steps→commit→HTML, FAILED/cancel branches), mock gateway module (verify=True unless amount ends 99), zero app callers.
- Step2 DECISION: DELETE dead code (undefined payment/internal_id = rot, not skeleton) → rich rewrite TODO :779 (validations incl. M12/closeout-3/gateway-allowlist, PENDING row + branch capture, real gateway). 400 + IDOR byte-identical.
- Step3: wallet gate :840 (invalid → FAILED + ActivityLog + error HTML, no charge); downstream else → defensive 500 :881; branch H7-resolution + NULL-with-warning-log policy :895 (verified money never stranded over metadata; initiate must capture); receipt date :920 + SMS date :1050 → _jalali_now_str(); status-trust TODO expanded :798 (authority binding, real verify, never trust query status, single-use idempotency).
- Step4: live behavior unchanged — initiate 400/IDOR identical, flag-gate :806 first line untouched, zero app callers, gateway mock untouched, ast.parse OK.
- NOT touched (flagged): refund reversal's Gregorian date (live path, own scope); get_payment_gateway silent-zarinpal fallback (covered in TODO).

## Follow-up: refund reversal date (same day)
- finance.py:1240 reversal_trans.date: Gregorian strftime → _jalali_now_str() (:165, same-file L7 helper, also used in #12).
- One-line diff; amount/ledger/wallet/total_paid lines untouched. ast.parse green.
- Same-pattern siblings NOT touched (flagged): :1776 send_installment_payment_reminder (SmsLog? date), :1821-1822 get_student_online_payments display, :2227 get_teacher_settlements_summary display.

## Follow-up 2: three sibling flags (same day)
- Helper _jalali_dt_str (:171-175, mirrors _jalali_now_str for stored datetimes).
- :1782 reminder SmsLog → _jalali_now_str (visible via /sms/history → SmsActivity).
- :1827-1828 online-payments API → _jalali_dt_str (live IDOR end-user endpoint; no current app caller but user-facing surface, not internal log).
- :2233 settlements-summary API → _jalali_dt_str (live admin report endpoint).
- Residual Gregorian strftime in finance.py: ZERO. ast.parse green. Each fix = single value-swap; no surrounding logic touched.
