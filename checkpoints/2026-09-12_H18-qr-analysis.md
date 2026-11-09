# Checkpoint — H18 analysis: QR check-in trust + indirect money effect

Date: 2026-09-12. READ-ONLY (no code changed). No compile/run.

## Step 1 — QR producer DOES NOT EXIST anywhere
- Android (KharazmiAdmin): zero QR code — no zxing/journeyapps dep, no
  scan/encode/display in any .kt (only false positive: "conflict checking"
  comment in CalendarActivity.kt:230). ParentPortalActivity: no scan.
- Server: `salt` occurs exactly ONCE in the codebase (attendance.py:883, the
  request-model field). No endpoint generates/returns QR payload; no table
  stores QR tokens; portal HTML has no QR refs.
- Workspace has only admin/teacher app + server; the scanning student app is
  absent entirely. token/salt are REQUIRED-but-ignored decoration.
- Exploit as reported: any authenticated student/parent POSTs arbitrary
  token/salt + future expires_at + guessed session_code (sequential from
  100001 via get_next_sequence_value, attendance.py:387) in an enrolled class
  → Present. Only real guards: login, enrolled (:908-910), suspension (H10).

## Step 2 — money effect: direct NO, indirect YES (conditional)
- Direct math (submit :365-374, edit :723+) reads ONLY teacher-submitted
  data.items → compute_session_shares. QR rows never enter directly. QR needs
  an EXISTING SessionLog (404 otherwise), so it only touches POST-charge
  sessions; live flow (finalize :58-104) builds items from teacher-saved
  live_roster JSON only.
- INDIRECT channel (real): QR flips/adds Present row → get_session_details
  (:656-666 serves status FROM Attendance rows) → AttendanceActivity.
  loadSessionDetailsForEdit (:410-435 prefills attendanceMap from rows) →
  teacher saves without noticing → Present enters data.items → counted in
  present_count → dilutes T_total split + charges wallets + Transactions.
  (Edit wipes all Attendance rows via reverse :356, but the INFLUENCE is
  baked into new items/charges.) Bounded by: needs teacher edit+save, and
  settled sessions are edit-locked (:702-711 is_billed→409).
- Discipline/stats effects are DIRECT + unconditional: student_history rate
  (:592-643), class reports (classes.py:503/:608), analytics.py, ai.py:221,
  and automation.py:167 — fake presence can SUPPRESS low-attendance warnings
  to parents. is_billed/final_teacher_cost untouched directly (as user noted).

## Step 3 — fix design (not applied)
- Recommended: server-truthful tokens. New table (session-bound
  token_hash + server expires_at ~10min); POST
  /attendance/session/{code}/qr_token (teacher/admin of course) → returns
  token for QR; qr_check-in verifies token row (exist/match/not-expired on
  SERVER clock), drops client expires_at/salt. Store hash, constant-time
  compare unnecessary with indexed equality; rate-limit per student.
- Effort: server ~half day (model+create_all, 1 new endpoint, check-in
  verify); teacher-app QR display ~half-to-full day (zxing dep + fetch +
  render dialog); STUDENT scan side BLOCKED — no student app in workspace,
  endpoint has no legitimate client today.
- Interim (no client exists to break — modulo any out-of-workspace app):
  restrict check-in to same-day sessions, or disable with 410 until the
  generate-token flow ships.
