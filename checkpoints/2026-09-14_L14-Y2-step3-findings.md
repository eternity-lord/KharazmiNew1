# L14/Y2 step-3 findings — immediate fix (2026-09-14, no compile/run)

## F1: broadcast (messages.py:241) — chose (الف) new permission
- dependencies.py:613 (secretary) + :625 (teacher): added "messages.broadcast". admin via "*".
- messages.py:247: broadcast dep messages.send → messages.broadcast. Other 3 messages.send
  endpoints (create/send/delete DMs) untouched → student DMs keep working.
- Why (a): declarative RBAC, single source of truth, auto fail-closed for unknown roles
  (ROLE_PERMISSIONS.get→[]→403); risk ≈ one dict + one dep string.
- App already gates broadcast UI to admin/teacher (MessageActivity:136) → zero legit breakage.
  Secretary allowed server-side (harmless superset). Note: teacher→everyone allowed per spec.

## F2: homework parent/child (homework.py:293) — explicit staff elif (:307-309)
- else-pass ("assumed admin") → elif sub_role not in (admin,secretary) → 403.
- Reachable roles were admin/student/parent (secretary+teacher lack homework.read at dep);
  student was the hole. Unknown roles now 403 too.
- App: HomeworkActivity:221-222 parent→parent/child, else→student/list → students never
  call this legitimately → zero breakage.

## Traces
- Broadcast: admin/secretary/teacher → pass; student/parent → 403 at dep; temp_parent → 403.
  Teacher+class target still owner-checked (:275 branch).
- Homework: parent own-child → pass; admin → pass; student A + B's id → 403 «مجاز به مشاهده
  تکالیف این دانش‌آموز نیستید». CLOSED.

## Verify: ast.parse ×3 (static) + grep.
