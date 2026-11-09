# Checkpoint — H14 rate-limit-behind-tunnel analysis (READ-ONLY)

Date: 2026-09-12. Q: IP limiter shares one bucket behind Cloudflare Tunnel?

## Step 1 — current state (confirmed mechanism)
- dependencies.py:439-442: `Limiter(key_func=get_remote_address)` (=request.client.host).
  Handler wired main.py:18-23. 7 usages: login_user auth.py:24, request_student_otp
  :352, student_login :418, request_parent_otp parent.py:25, parent_login :100
  (all 5/5min) + register_student students.py:30, register_teacher teachers.py:31
  (5/hour).
- RunServer.bat: plain `uvicorn main:app --host 0.0.0.0 --port 8000` — NO
  --proxy-headers, no ProxyHeadersMiddleware/TrustedHost anywhere. Behind
  cloudflared-over-localhost, EVERY request.client.host = 127.0.0.1 → ONE shared
  bucket per endpoint. 5 failures by anyone ⇒ 429 for everyone. BUG CONFIRMED
  (code-level + documented uvicorn/slowapi semantics).

## Step 2 — headers (zero refs today; but receivable with zero deploy change)
- No X-Forwarded-*/CF-Connecting-IP/request.client refs anywhere in code.
- Deployment is DUAL (proven by PublicRouteIsolationMiddleware host check):
  direct LAN/localhost + cloudflared tunnel (.trycloudflare.com).
- cloudflared/edge sets CF-Connecting-IP (edge-OVERWRITTEN, true client) and
  APPENDS X-Forwarded-For; uvicorn passes all headers to request.headers
  regardless of --proxy-headers (flag only affects trusted client/scheme
  interpretation). So a custom key_func can read real IPs TODAY.
- Spoofing: direct clients can forge both headers ⇒ trust proxy headers ONLY
  when client.host ∈ loopback (proves tunnel hop). Prefer CF-Connecting-IP
  (unambiguous) over XFF-last (edge-appended). Direct-attacker XFF ignored.

## Step 3 — per-mobile: EXISTS for OTP, MISSING for password-login (critical gap)
- ParentOTP columns (attempts/is_locked/locked_until/created_at) + enforcement
  in both OTP-request endpoints (3-per-5min, lock check) and both OTP-login
  endpoints (attempt++ → 5-strike 15-min lock): auth.py:378-380,398-399,431,443-446;
  parent.py:51-53,68-69,112,128-131.
- login_user: NO per-mobile throttle — only the (broken-behind-tunnel) IP limiter.
  HIGHEST-RISK endpoint. Registers: same (no per-mobile/national-code throttle).
- No generic throttle table; SequenceCounter unsuitable (no windows, shared
  namespace). login_user needs NEW mechanism: attempts+locked_until on
  User/Teacher (ParentOTP mirror) OR dedicated LoginAttempt(mobile, window)
  table (cleaner, all roles). Do NOT reuse ParentOTP table (semantically OTP).

## Step 4 — proposed key_func (apply ALWAYS; self-scoping via loopback check)
- tunnel_aware_key: direct=get_remote_address (TCP truth); if direct in
  TRUSTED_PROXY_IPS (env, default 127.0.0.1,::1): return CF-Connecting-IP if
  present else XFF-last; else return direct. Direct traffic byte-identical to
  today; tunnel traffic gets real-IP buckets. If cloudflared moves off
  localhost, extend env — one line.
- Custom key_func SAFER than --proxy-headers here: that flag would let DIRECT
  clients poison request.client with forged XFF in this dual-mode deploy (and
  needs RunServer change). Residual: NAT-sharing coarseness → per-mobile (step 3)
  is the COMPLEMENT. Multi-worker note: slowapi default storage is in-memory;
  fine today (single process), needs redis if workers ever added.
