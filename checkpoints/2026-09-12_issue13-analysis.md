# Issue #13 (dual-calendar session date) — ANALYSIS ONLY, zero code changes
## Step1 evidence
- AttendanceActivity.kt:491: `SimpleDateFormat("yyyy/MM/dd", Locale.US).format(Date())` (Gregorian today), used for BOTH submit and edit modes (:503-507).
- etSessionDate (layout :136, hint «تاریخ امروز», focusable=false) + etSessionTime (:158, hint «ساعت», editable): ZERO references in any .kt (repo-wide grep) → date renders empty-hint, time input discarded.
- SessionSubmitData(course_id, date, items) — NO time field (AppModels.kt:163) → time unsendable without API change.
- Server submit (attendance.py:353-430): NO date validation (no parse/format check; any string stored :416-418); Bug-17 pre-check (:371-376) + uq index compare RAW strings → "2026/09/12" vs "1405/06/21" = different days → double session + double charge. Single SessionLog creator (:416).
- Edit mode also sends today → server sets session.date=today (silent re-date of old sessions, or H19-F1 409 if today's session exists).
## Step2 intent verdict: HYBRID
- DATE field = designed DISPLAY-ONLY («تاریخ امروز» + focusable=false): intent IS always-today (consistent with one-session-per-day Bug-17/uq + card «تنظیمات زمان جلسه»).
- TIME field = unfinished leftover (editable, no picker, no API field, submit never sets start_time/end_time though columns exist).
## Step3 proposal (not implemented)
1. Canonical format = Jalali (matches H3/M27/L7 direction; Installment.due_date already «فرمت خورشیدی»).
2. Server: validate + NORMALIZE session date via H3 converter at submit (canonical compare → cross-client dedup works); reject garbage 422.
3. App submit: send tap-day in Jalali (existing JalaliUtils/getSimplePersianDate precedent) + DISPLAY it in etSessionDate (fulfills evident intent).
4. App edit: send back details.date (already in get_session_details response — zero API change) instead of today.
5. REMOVE etSessionTime (dead input discarding user data; live-time tracking = separate feature on start_time/end_time if ever needed).
6. Backdated entry (forgot Monday, submit Tuesday) stays unsupported — product call, not part of this fix.
