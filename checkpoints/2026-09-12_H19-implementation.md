# Checkpoint — H19 implementation (F1 date pre-check + F1b backstop + F2 branch hoist)

Date: 2026-09-12. 4 ops in routers/attendance.py :: edit_past_session,
asserted + visual read-back. No compile/run.

## F1 (:712-722): date-clash pre-check, before reverse
After settled block, before C1 (honors 409-before-422 convention): active
SessionLog with same course_id + data.date + id != self → 409 with the EXACT
Bug-17 message ("جلسه این کلاس در این تاریخ قبلاً ثبت شده است", cf. submit
:352) — verbatim, not the order's paraphrase, per "same message" intent.
Deterministic date-collision 500: FIXED (request now side-effect-free).

## F1b (:779-786): commit #2 wrapped in try/except IntegrityError → 409
Same message, mirrors H6-C2 pattern. Honest scope: covers the concurrent-edit
race the pre-check can't see; converts raw 500 → clean 409, but in that
microsecond race reverse still stands (F3-deferred residual, noted in code).

## F2 (:733-745): branch pre-scan hoisted before reverse
After membership validation, before counts/shares: mirrors loop condition
exactly (chargeable + existing student + branchless anywhere incl. course
fallback) → same 400, before the point of no return. In-loop check (:840-843)
KEPT as backstop per order (mid-request branch-null race, however unlikely).

## Comment fix (:838-839)
Wrong :806 sentence ("همه‌چیز rollback می‌شود") replaced: in-loop = backstop
only, F2 = real guard, commit #1 (reverse) stands. Submit's identical sentence
deliberately UNTOUCHED — correct there (single transaction).

## Order verified: F1 :712 < F2 :733 < reverse :769
Both fail side-effect-free (nothing reversed yet), like submit. Post-reverse
deterministic failures: none left; residual = race/DB-crash class (F3 deferred).
