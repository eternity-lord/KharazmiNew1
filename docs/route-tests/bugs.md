# Bug registry — route/API response audit

**Scope:** confirmed issues are reproduced by regression tests, and fixes based on explicit product decisions are implemented and listed below. Every remaining open, reproducible issue has a strict `xfail`. Screen-unmapped response candidates or issues depending on an undecided contract remain in `questions.md`; no unresolved policy is inferred.

## Confirmed/reproducible open findings

| ID | Area / severity | Strict reproduction | Expected | Observed | User-visible consumer / evidence |
|---|---|---|---|---|---|












## Observations not promoted to confirmed bugs

- `Q-027` records dunning eligibility as an unresolved product rule, not a defect: `/dunning/drafts` excludes a deleted Student but includes a suspended one; direct `send_batch` logs selected installments for either state. The route has no SMS gateway effect; all tests inspect local `SmsLog`/`ActivityLog` rows. No xfail was manufactured without an agreed eligibility contract.

## Previously known issues now fixed in this checkout

| ID | Current status | Verification |
|---|---|---|
| O-19 / `RA-admin-19` | **Closed here; financial history is opt-in and fail-closed.** | Restore returns class/enrollments/sessions by default and exposes a financial-history checkbox for deletions with row-level provenance. Checked restore atomically reactivates deletion-scoped transactions/installments and reverses only recorded wallet credits; it rejects spent credits (409) and blocks finance for legacy deletions without provenance. Server/UI contract regressions cover success, no-finance restore, legacy data, wallet insufficiency and session conflict. Android build/device execution remains unrun by scope. |
| O-02 / `RA-auth-02` | **Client integration complete; Firebase project configuration/device check pending.** | Android obtains/refreshes FCM tokens, registers them through `POST /auth/device_token` after successful admin/teacher/student/parent login, and sends the current token on logout so the server removes that device registration. Source-contract regressions verify the wiring; real token generation/delivery is not claimed until the four Firebase client settings are supplied and a device test is run. |
| O-12 / `RA-exams-02` | **Closed here; not xfailed.** | `/exams/student/list` filters `Exam.status == "published"`; the audit seed's pending exam is omitted and the route regression passes. |
| `RA-finance-02` | **Closed here; not xfailed.** | Parent handler forwards the authenticated `_role` into the child dashboard helper; valid parent now gets HTTP 200 and the seeded wallet balance. |
| `RA-homework-01` | **Closed here; not xfailed.** | Parent homework JSON now includes each task's `max_score`; the graded-item regression checks its value and the `HomeworkItem` Kotlin contract. |
| `RA-ai-01` | **Closed here; not xfailed.** | `/ai/chat` trims both before use and after appending so every role's conversation history remains at most 15 message entries; 20-turn regression ends at exactly 15. |
| `RA-audit_trail-01` | **Closed here; not xfailed.** | Range validation rejects equality at an exclusive date-only end boundary; both reversed ISO and Jalali date-only inputs return 400. |
| `RA-attendance-01/02/03`, `RA-teachers-01` | **Closed here; not xfailed.** | All four live/today-summary response paths coerce stored epoch values to JSON integers; fractional seed values now satisfy the Android `Long` contract. |
| `RA-crm-01` | **Closed here; not xfailed.** | Required lead name/mobile/course, provided notes, lead-note content, online-registration names, identity and mobile fields trim whitespace and reject empty values before writes. Empty/whitespace tests pass with exact DB snapshots unchanged. |
| `RA-crm-02` | **Server-side integrity fix complete; UI follow-up pending.** | A supplied nonexistent `course_id` now returns a clear 404 before student/lead/sequence writes; test passes. The current Android CRM conversion caller sends no course ID, so a course picker has not yet been wired. |
| `RA-crm-03` | **Server overflow fix complete; confirmation UI pending.** | `paid_amount` is bounded to the signed 64-bit database range, so `2**63` returns 422 before any write rather than SQLite 500. The route has no current Android caller, and no product-defined confirmation threshold/client exists in this checkout. |
| `RA-automation-02` | **Closed here; not xfailed.** | Rule create/update text now trims and rejects blank names; empty and whitespace create inputs return validation errors without writes. |
| `RA-automation-01` | **API confirmation contract implemented; UI follow-up pending.** | Create and update return a structured `unknown_action` error with `can_continue=true`; the rule changes only when the caller resubmits with `confirm_unknown_action=true`. No Android Automation screen/API caller exists in this checkout. |
| `RA-automation-03` | **Relationship-access defect closed; date-format question remains.** | Inactivity trigger now reads the existing `Attendance.session` relationship; deterministic Gregorian fixture produces one notification/log. Mixed Jalali/Gregorian date parsing remains unresolved under Q-018 and was not guessed. |
| `RA-branches-02` | **Closed here; not xfailed.** | Update now detects serials owned by other resources before writes and returns a clear 400; a concurrent unique-constraint race is rolled back and mapped to 409. |
| `RA-branches-01` | **Closed here; not xfailed.** | Booking conflict rejection was removed per product decision; identical booking requests each persist a new `ResourceBooking` row and return success. |
| `RA-messages-01` | **Closed here; not xfailed.** | Sender exclusion now compares `(user_id, role)` instead of numeric IDs alone; role-colliding student still receives the local Notification and mocked push. |
| `RA-messages-02` | **API integrity fix complete; UI prompt follow-up pending.** | Mismatched arrays return structured 422 `recipient_information_incomplete` / «اطلاعات را تکمیل کنید» before writes; a corrected request succeeds. Current Android screen has no conversation-create UI to display the prompt. |
| `RA-messages-03` | **Closed here; not xfailed.** | Only `everyone` and `class` are accepted. Unknown targets and the unsupported `role` target return HTTP 400 before writes; regression tests assert no database changes. No broadcast target/type was added. |
| O-14 / `RA-parent-01` | **Closed here; not xfailed.** | `ParentExamItem.max_score` is `Float`; the normal test `test_O14_parent_exam_decimal_max_score_is_not_parsed_as_Int` verifies 12.5 without `int-parse`. Android compilation/device execution remains outside this audit. |
| `RA-sweep-01` | Fixed before this audit; normal assertion | Bulk approve response contains non-null `message`; regression pins the specific key. |
| `RA-sweep-02` | Fixed before this audit; normal assertion | Student exam items contain explicit `description` and `due_date`; regression pins those fields. |
| `RA-sweep-03` | Earlier missing `description`/`due_date` issue fixed; normal assertion | Parent homework response contains both fields. A separate graded-state `max_score` omission is recorded as `RA-homework-01`, not mislabeled as the old fix. |
| `RA-sweep-04` | Earlier `students_preview` missing-list issue fixed; normal assertion | Incomplete-class response contains `students_preview: []`. Five other fields of the shared model remain an unresolved Q-006 contract question, not this fixed bug. |
| `RA-admin-01` | Fixed in the current server checkout; normal tests | Dashboard resolves a transaction's student from `Transaction.student_id` when `enrollment_id` is absent. See `test_audit_admin.py` and the admin report. |

## Contract simulator candidates not counted as confirmed bugs

The fresh Kotlin/Gson report is intentionally a **candidate detector**, not a product-bug count. It reports `parse=0`, `npe=5`, and `silent_zero=7`; the raw candidates were reviewed against current Android call sites before registry classification.

- `GET /finance/student/{id}/dashboard`: `recent_transactions` omits fields required by the broad `TransactionFullItem` model; current `StudentProfileActivity.showCreateInstallmentDialog()` reads only enrollments. **Q-008**; not an xfail.
- `GET /students/my_profile`: `info.parent_mobile` is absent although a shared profile model declares it non-null; current `StudentPortalActivity` displays `name` and `national_code` only. **Q-007**; not an xfail.
- `GET /teachers/{id}/incomplete_classes`: `is_admin_approved`, `is_suspended`, and debt fields are absent from the response while the shared model has defaults. The current incomplete-class dialog reads only `id/title/code`. **Q-006**; not an xfail.
- `GET /homework/parent/child/{student_id}`: `max_score` becomes visible when an item has a score; a separate stateful test promotes that candidate to confirmed `RA-homework-01`.

## Latest isolated route sweep

- **221/221** routes executed in the 2026-10-07 isolated sweep; main-request **500 = 0**.
- **220** invalid-target probes; invalid-request **500 = 0**; **11** empty probes, null-list results = 0; **14** non-JSON responses.
- The current role/status probe has no 403 response; `GET /finance/parent/dashboard` now returns 200 for the valid parent session (`RA-finance-02` is closed).
- Latest full role/status/shape samples are in `tests/route_audit/sweep/report.json`; route-by-route caller/source/DB annotations are in `routes/*.md`. The Kotlin/Gson simulator now reports 170 declarations, 159 unique calls and 157 static routes; `parse=0`, `npe=5`, `silent_zero=7`.
