# Checkpoint — H14 implementation (tunnel-aware key + per-mobile throttle)

Date: 2026-09-12. 8 ops, 4 files, anchors asserted + visual read-back. No compile/run.

## Step 1 — tunnel_aware_key (dependencies.py:442-461)
- _TRUSTED_PROXY_IPS from env TRUSTED_PROXY_IPS (default "127.0.0.1,::1"); os
  already imported (:11). tunnel_aware_key: TCP-truth direct IP; if loopback →
  CF-Connecting-IP else XFF-last; else direct. Limiter rebuilt with it (:461).
  Applies to all 7 existing @limiter.limit sites with zero per-site change.

## Step 2 — LoginAttempt + login_user throttle
- models.py:484-490: LoginAttempt(id, mobile ix, attempted_at ix, ip nullable).
  One-row-per-fail (no upsert races); ip = forensics only, throttle key = mobile.
- auth.py login_user: pre-check :26-35 (5 fails/5min → 429); record on BOTH
  wrong-password 400s (:62-63 admin, :70-71 teacher, immediate commit like OTP
  pattern); clear on BOTH successes (:49 admin, :113 teacher, piggybacked on
  existing commit). Lazy model import (in-file precedent). datetime already imported.
- Design calls: 404-unknown-mobile NOT recorded (no garbage rows, no lockout
  amplification); 403-approval NOT recorded (not a credential failure); strip()
  on throttle key. KNOWN trade-off: attacker knowing victim mobile can cause
  5-min lockout (self-recovering; standard per-account-throttle cost).
- Registers (students.py:30, teachers.py:31): IP-limiter only, zero ParentOTP/
  LoginAttempt interplay (grep empty) → no conflict, NO changes made there.

## Step 3 — migration
- New table → main.py:65 create_all at import (established pattern for new
  tables; no ALTER needed). Bounded growth: purge >24h rows in auto_patch
  (main.py:312-322, next to session cleanup, same try/commit/rollback shape).

## Step 4 — trace (manual, no run)
- Tunnel: A (mobile M_A, real 1.2.3.4) fails pw 5×; B (M_B, 5.6.7.8) logs in OK.
- IP layer: A's bucket="1.2.3.4" (CF header, loopback-trusted) hits 5/5min → A
  429s at decorator; B's bucket="5.6.7.8" untouched ✓ (OLD code: shared
  127.0.0.1 bucket → B locked too ✗).
- Mobile layer: 5 LoginAttempt(M_A) rows → A's 6th attempt (even correct pw)
  429s in-function; M_B has 0 rows → B passes ✓. Success clears M_A rows.
- Layer order: slowapi 429 (decorator) precedes in-function 429; both agree.
