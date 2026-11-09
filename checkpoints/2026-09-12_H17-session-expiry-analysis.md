# Checkpoint — H17 analysis: manual UserSession queries vs get_session_from_token

Date: 2026-09-12. READ-ONLY (no code changed). No compile/run.

## Helper (dependencies.py:84-111)
get_session_from_token(db, token) -> (sess, payload):
- JWT path: verify HMAC + exp (7d, JWT_ACCESS_TOKEN_EXPIRE_DAYS :27); row must
  exist; 30d created_at purge (delete+commit). Missing row -> (None, payload).
- C7 no-fallback: JWT-shaped-but-bad/expired -> (None, None) outright.
- Opaque legacy path: row + 30d purge -> (sess, None).
Returns TUPLE; does NOT filter sub_role.

## Truly exposed (manual query = ONLY check, no check_user_login gate)
1. parent.py:237 child_profile: expired parent JWT (>7d) accepted until startup
   30d purge (main.py:304 runs at STARTUP only). REAL lifetime-extension gap.
2. parent.py:187 select_child: temp JWT exp ignored; temp rows linger until
   selected or startup purge. REAL (needs token string; narrower).

## Redundant-but-safe (gate check_user_login already enforces upstream)
attendance.py:892, auth.py:240/298/315, finance.py:616 (all 8 production
verify_financial_idor callers gated: 445/488/664/1495/1520/1548/1684/1734),
finance.py:1659, students.py:603, reports.py:155. Already-migrated:
reports.py:392. Non-auth: main.py:304 (startup purge), admin.py deletes/lookups,
dependencies.py:88/103 (inside helper), tests.

## Compatibility answers
- Q2: YES — helper returns the SAME UserSession ORM row object; unpack tuple,
  re-apply sub_role=="parent" manually (else non-parent tokens degrade to 404
  via resolver-None instead of clean 401).
- Q3: YES — works for temp sessions (token-only lookup; temp JWT carries own
  7d exp which becomes ENFORCED). Keep prefix check on returned sess;
  user_id=-1 harmless (helper never touches user_id). No separate logic needed.

## Fix proposal (not applied)
A. child_profile: `session, _ = get_session_from_token(db, token)` +
   `if not session or session.sub_role != "parent": 401`.
B. select_child: `temp_session, _ = get_session_from_token(db, req.temp_token)` +
   `if not temp_session or not (temp_session.sub_role or "").startswith("temp_parent:"): 401`.
C. Redundant sites: recommend NO touch (zero security delta, churn only).
Severity: lifetime-extension 7d->30d+, not bypass (exact-string match needed).
