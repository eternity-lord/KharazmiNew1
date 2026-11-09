# E2E secretary test (2026-09-14; COPY; hash-identical; /tmp cleaned; report-only, no fixes)

## Verdict: 39/40 PASS, zero Tracebacks
## ONE divergence: refund as secretary → 403 (code: check_admin_access, admin-only),
but scenario expected 200. DECISION NEEDED: is refund admin-only by design (scenario wrong)
or should secretary refund (code too strict)? Money logic itself verified identical via admin refund.

## Boundary confirmed
ALLOW (200): register teacher/student, approve_teacher, create/approve class, enroll,
pay (single+both, keyed), installments CRUD+pay (+409 semantics), suspend teacher/student/class,
suspended teacher login→403 + suspended OTP→403 (today's fixes hold), resources CRUD+book,
remind, broadcast, financial_summary, debtors, teacher-search with mobiles, teacher card.
DENY (403): reject_teacher, reject_class, pricing update, share update, bulk-sms (admin-only
per code — scenario listed it under ✅ but code is explicit; treat as boundary clarification).
REPORT-ONLY: over-cap approve by secretary → 200 WITH price_warning (no special secretary limit).

## Test bugs (mine, corrected): resource_id key (not id); teacher-search check arg order.
