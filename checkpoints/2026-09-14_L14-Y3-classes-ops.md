# L14 batch Y3 — 10 classes/ops endpoints (2026-09-14, no compile/run)

## Step 1 — today's lines (pre-fix): classes 128/281/468/681, attendance 326/593, admin 46,
admin 460→449 (get_share_config), 501→490 (get_pending_classes), 1306→1295 (get_institute_settings).

## Step 2 — per-endpoint decisions (caller-verified)
- classes:128 /classes/list → STAFF-ONLY (dep swap :135). Catalog+debts; sole caller
  ClassManagementActivity←MainActivity (staff); no teacher/student need.
- classes:281/:468/:681 details/full_report/students_full → STAFF + OWNER-TEACHER (:285/:481/:701,
  +authorization; guard after 404 per H16). Callers: Attendance/Live/ClassDetail/ClassSetup (teacher receipts).
- attendance:326/:593 get/get_history → STAFF + OWNER-TEACHER (:331/:608; +course fetch, [] if missing).
  Zero callers; class-report pattern kept tight via ownership.
- admin:46 dashboard/stats → STAFF-ONLY (dep swap :46). Zero callers.
- admin:449 /config/share → ADMIN-ONLY (dep swap to check_admin_access). Symmetric with update (:462,
  admin-only); app hides nav_share_config from secretary; zero GET callers. (Stricter than batch spec.)
- admin:490 pending_classes → STAFF full + TEACHER OWN-ONLY filter (:491+). Teachers legitimately open
  PendingClassesActivity from ClassSetup:158 (status check); approve POST stays admin-only.
- admin:1295 institute_settings → STAFF full + TEACHER REDACTED (:1309+; 5 card_* fields → None).
  staff-only would BREAK teacher attendance receipts (AttendanceActivity:580) + teacher invoices
  (InvoiceActivity←TeacherDashboard). Student/parent 403 (no caller).

## Step 3 — bypass sweep (no new findings)
- Excel twin :568 already check_admin_or_secretary_access ✓; attendance:639 student_history
  (else→403) ✓; :710 session_details (!=teacher→403 + owner) ✓; qr :1050 self-scoped ✓;
  admin:34 today_summary staff ✓; classes:80/:937/:1108 fail-closed ✓.

## Step 4 — traces
- Staff-only ×3 (:128/:46): admin/secretary pass (dep); everyone else 403.
- Share (:449): admin pass; secretary/teacher/student/parent 403 (dep).
- Owner-teacher ×5 (:281/:468/:681/:326/:593): staff pass; owner-teacher id-match pass;
  other teacher 403; student/parent/unknown 403 («...این کلاس نیستید»).
- Pending (:490): staff full list; teacher own-submissions only; student/parent 403.
- Settings (:1295): staff full (cards); teacher same shape minus 5 card fields; student/parent 403.
- Legit preserved: teacher receipts/invoices ✓, ClassSetup status check ✓, ClassManagement ✓.

## Verify: ast.parse ×3 (static) + grep. Partial-apply incident: full_report anchor missed a
comment line → re-ran remaining 8 only after verifying first 2 landed (no double-apply).
