# L14 batch Y2 — 8 teacher-data endpoints (2026-09-14, no compile/run)

## Step 1 — no check_teacher_access helper exists → get_logged_in_teacher pattern (audit-v2)
Gate used: `sub_role not in (admin,secretary,teacher)` → 403, then teacher-self via
get_logged_in_teacher + id match (lazy import, circular-safe). Matches teachers.py:121 precedent.
CORRECTION: card number is at :384 (explicit card_number field), NOT :311 (:311 = mobile +
national_code + total_revenue + collaboration/settlement totals — still 🟡high). Both fully guarded.

## Step 2 — applied (8)
- teachers.py:200 (gate :210) / :271 (gate :280) / :311 (gate :323): completed half-guards
  (existing teacher-self checks kept, staff/teacher gate added above).
- teachers.py:384 (guard :394-400) / :630 (:655+) / :882 (:914+): full guards (+authorization param).
- admin.py:1468 search (gate :1461): staff+teacher (PersonList TEACHER mode reachable by teachers
  via MainActivity:185, no role gate → teacher allowed, same judgment as Y1).
- analytics.py:293 (gate :301): admin/secretary ONLY — zero callers anywhere (grep); teachers
  have today_summary (:169) for own stats.

## Step 3 — bypass sweep beyond check_student_access (REPORT ONLY, not fixed)
- NEW FINDING 1 (🔴-class): POST /messages/broadcast — require_permission("messages.send") held by
  student+parent too (ROLE_PERMISSIONS); everyone-branch = no role check, class-branch = teacher-only
  check → any STUDENT can broadcast announcements to everyone/any class (+notifications). Needs role design.
- NEW FINDING 2 (🟡): GET /homework/parent/child/{student_id} — require_permission("homework.read")
  held by students; in-body parent→own check, else→pass ("admin assumed") → student A reads B's homework.
- SAFE (verified fail-closed): ai.py tool chain (default [] + else 403); classes.py:929 request_delete
  (gate first); exams:130/hw:151 self-lists (non-student→401); auth/me (own data); teachers:413 (dep blocks).
- NOTE: sweep exposes a methodology blind spot — require_permission endpoints were assumed strong in L14
  but permission breadth (student-held) + missing in-body checks = same hole class. Recommend R2 batch.

## Step 4 — traces
Per-teacher ×6: admin/secretary → pass; self-teacher → id-match pass; other teacher → 403 «خودتان»;
student/parent/unknown → 403 at staff gate. Card (:384): student GET → 403 before any query. CLOSED.
Search (:1468): staff+teacher pass; student/parent 403. Analytics (:293): staff pass; teacher/student/parent 403.
Legit preserved: StudentProfileActivity teacher screens (staff/self) ✓, PersonList both modes (staff+teacher) ✓,
TeacherCredentials (staff) ✓, today_summary untouched ✓.

## Verify: ast.parse ×3 (static) + grep FIX lines.
