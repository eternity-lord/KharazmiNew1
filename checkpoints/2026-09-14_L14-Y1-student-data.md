# L14 batch Y1 — 10 student-data endpoints (2026-09-14, no compile/run)

## Step 1 — check_student_access (dependencies.py:406-443, now +else 440-443)
Roles: teacher → own students only (Enrollment+Course join); parent → own child only
(get_session_parent); student → self only (get_session_student); admin/secretary → pass.
FOUND + FIXED in step 1 review: unknown roles (incl. temp_parent:* pre-selection sessions
from parent.py:173) matched NO branch = full bypass. Added else → 403 unless admin/secretary.
Zero legit breakage: temp_parent has no child context to authorize; all 5 known roles unchanged.

## Step 2 — applied
Per-student via helper (7): students.py :300 grades (chk :308) / :414 profile TRAP-REWRITE (chk :424) /
:593 installments (chk :592); admin.py :299 full-profile TRAP-REWRITE (chk :301, was teacher-only too);
reports.py :507 statement (chk :514) / :550 print (chk :560) / :731 profile-print (chk :744).
Imports added: admin.py:20, reports.py:20 (students.py already had it).
DEVIATION (reported): 3 searches have NO student_id → helper inapplicable. Role-gated instead
(admin/secretary/teacher; student/parent 403): students.py :206/:218, admin.py :1442 (gates :207/:222/:1432).
Teacher allowed = legit need (ClassSetup search_simple, PersonList); staff-enumeration accepted trade-off.

## Step 3 — traces (all 10)
Per-student ×7: admin → pass; owner-teacher → enrollment-join pass; self/own-parent → id-match pass;
other student → 403 «...دانش‌آموز دیگری...»; stranger parent → 403 «...این فرزند...»; temp_parent → 403 (new else).
:414 specifically: student A GET /students/{B} → role=student, own.id=A ≠ B → 403. CLOSED.
Searches ×3: admin/secretary/teacher → pass; student/parent → 403 at gate line.
Legit flows preserved: ClassSetup teacher-search ✓, PersonList staff ✓, ReportActivity statements
(admin/secretary/owner-teacher/self) ✓, StudentProfileActivity grades (same) ✓, print WebViews ✓.

## Verify: ast.parse ×4 (static) + grep + re-read of both trap sites.
