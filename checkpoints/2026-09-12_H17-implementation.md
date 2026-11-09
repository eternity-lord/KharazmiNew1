# Checkpoint — H17 implementation (parent endpoints via get_session_from_token)

Date: 2026-09-12. 2 ops, anchors asserted + visual read-back. No compile/run.

## A. child_profile (parent.py:238-241)
- Manual `query(UserSession).filter(token, sub_role=="parent")` replaced with
  lazy `from dependencies import get_session_from_token` (file convention) +
  `session, _ = get_session_from_token(db, token)` +
  `if not session or session.sub_role != "parent": 401` (same message).
- Downstream untouched: `get_session_parent(db, session)` (:246) receives the
  same UserSession ORM object (same var name) — resolver path verified (H17
  analysis step 2). Effect: 7-day JWT exp + signature now enforced; expired
  parent tokens 401 instead of serving until startup purge.

## B. select_child (parent.py:187-190)
- Manual `.like("temp_parent:%")` query replaced with
  `temp_session, _ = get_session_from_token(db, req.temp_token)` +
  `if not temp_session or not (temp_session.sub_role or "").startswith("temp_parent:"): 401`
  (same message). Downstream split/len/mobile/IDOR/new-session/delete-temp all
  untouched. Effect: temp JWT 7-day exp now enforced.
- user_id=-1 verified harmless: temp_session used ONLY for sub_role reads
  (prefix check, mobile split) + final db.delete; user_id never read in the
  function (only user_id refs are student.parent_user_id for the NEW session).
