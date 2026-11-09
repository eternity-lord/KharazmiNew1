# Test-call repair — caller-guard sig changes (2026-09-12, pytest RUN authorized as exception)
Baseline: 35 failed / 269. Final: 24 failed / 245 passed. TypeError count: 0.
## TypeError fixes (call-only, real seeded tokens, assertions untouched)
- test_classes.py:150 + :165 create_class → authorization="Bearer admin-token" (seeded :95-96), sub_role="admin".
- test_teachers.py:78 get_all_teachers → Bearer admin-token (seeded :66), sub_role="admin", skip=0, limit=None (L8 Query defaults aren't plain ints for direct calls).
- test_priority2:381 submit helper (feeds 7 tests) + :582 concurrent + :657 edit + :350 get_all_installments → Bearer p2-admin-token (seeded :61), sub_role="admin".
## Fixture completions (beyond calls, reported; no assertion/logic change)
- seed_finance += InstituteShare(count_1=30, count_2=60) — H5-canonical row, same values the tests were authored against (old PricingTable institute row). Unblocked 8 submit-path tests (500 tariff).
- refresh(transaction) (:394) + refresh(original) (:658) — B1/B2 bulk-update staleness (server proven correct via fresh-query asserts in sibling tests).
## Still failing (24, ALL pre-existing non-sig causes, untouched): join-to-SessionLog InvalidRequestError (automation x2, financial_reads, tuition x7, soft-delete-e2e?), legacy-wallet 400, refund assert, delete_enrollment assert, schema_upgrade missing col, admin msg-text, idor/ai/auth 401s, security-audit unprotected-routes, 3 critical-e2e scenarios, student_my_profile 404.
## Guards audit: all caller-guards short-circuit on sub_role admin/secretary without reading authorization; tokens passed are nevertheless REAL seeded sessions.
