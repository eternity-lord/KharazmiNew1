# پیشرفت ممیزی routeها

**شروع پروژهٔ ممیزی:** 2026-09-28 — **snapshot فعلی:** 2026-10-07 — **branch ثابت این نشست:** `arena/01a10aa8-kharazmiapp`. این snapshot شامل fixهای تأییدشدهٔ audit/تصمیم‌های explicit و regressionهایشان است.

## زیرساخت و مرحلهٔ صفر

- `docs/app-map/*` به‌عنوان ورودی اصلی و route path inventory حفظ شده است؛ پنج ردیف مربوط به مسیرهای حذف/تأیید/جزئیات/restore کلاس در `server-routes.csv` برای provenance و فیلدهای O-19 همگام شدند.
- بررسی map جاری: server inventory برابر 221/221 با routeهای runtime است؛ ورودی Retrofit تاریخی 162 declaration دارد، در برابر 170 declaration در Kotlin فعلی. مقایسهٔ جاری 159 زوج یکتای method/path، 157 route ثابت یکتا و 1 `@Url` پویا را نشان می‌دهد. 8 declaration جاری در map تاریخی نیستند (از جمله `/auth/device_token`); overlayهای `android-api-current.csv` و `android-route-diff.md` اختلاف را ثبت می‌کنند. 64 server-only و 0 Android-only route باقی است.
- seed canonical فقط DB موقت را می‌سازد؛ salted password hash، JWT، timestampهای ORM و داده‌های business ثابت‌اند. `test_seed_reproducibility.py` دو DB را با schema/row canonical digest مقایسه می‌کند.
- seed عادی 30 دانش‌آموز و seed حجیم 300 دانش‌آموز/30 کلاس دارد. role fixtures: admin, secretary, teacher, student, parent؛ شماره‌های دانش‌آموز/والد در seed با قالب 11 رقمی معتبرند.
- ساعت سرور در `clock.py` روی `2026-09-28 09:00:00` ثابت است. sweep، contract، boundary، large و pytest هرکدام DB موقت استفاده می‌کنند؛ `requests`, `urllib` و اتصال socket خروجی مسدود است (subprocess regression در `test_sweep_network_guard.py`)، FCM key خالی است و worker زنده برای runnerهای مستقل start نمی‌شود.
- oracle مالی مستقل، simulator Kotlin/Gson، route registry و 25 گزارش per-router موجودند. گزارش‌های per-router اکنون از ورودی map، caller فعلی Kotlin، actor probe، پاسخ/نمونه، static DB effects، sweep و test-reference استفاده می‌کنند؛ probe actor را به‌عنوان مجوز نهایی endpoint معرفی نمی‌کنند.

## routerها

۲۵ router دارای suite متمرکز/مقداری هستند، اما پوشش هنوز **partial** است و تمام branchهای 221 route این گروه deep نشده‌اند:

| router | routes | وضعیت فعلی |
|---|---:|---|
| ai | 1 | tool values برای admin/teacher/student/parent و no-write بررسی شد؛ `RA-ai-01` بسته است و history به حداکثر 15 پیام محدود می‌شود |
| audit | 1 | empty/read-only، early/delayed attendance، <30-day and <1h rapid-delete (exactly 1h rejected)، last-10 perfect-attendance transition؛ باگ باز تأیید نشد |
| audit_trail | 1 | Android response/display values، filters/search، ISO/Jalali bounds، pagination 205-row، orphan/deleted refs، rollback؛ `RA-audit_trail-01` بسته است و reversed date-only range با 400 رد می‌شود |
| auth | 12 | ورود موفق admin/secretary/teacher، me، تغییر رمز/موبایل، OTP، logout/device token و اعلان‌ها؛ Android FCM registration wiring بسته شد؛ project config/device run pending؛ invalid credential/abuse از scope امنیتی خارج است |
| finance | 26 | oracle مالی/پرداخت و invoice، retry/FIFO؛ `RA-finance-02` (دسترسی parent dashboard) در این checkout بسته است؛ side-effect/gateway و چند CRUD هنوز blocker دارند |
| attendance | 15 | read/history، live start/status/cancel، retry مالی، suspended guard و QR stale/same-day success با DB restore |
| classes | 21 | list/detail/debt/export و subset state/approval؛ create/bulk/delete/enrollment transitionها هنوز عمیق نیستند |
| admin | 41 | مقدار/KPI/state/export/guard، coverage مقداری پیشین؛ `RA-admin-01` فعلی سبز است |
| teachers | 18 | settlement/wallet slice، incomplete-class minimum fields؛ timestampهای live در JSON عدد integer/Long هستند (`RA-teachers-01` بسته) |
| students | 13 | profile/grade/access/version conflict؛ `parent_mobile` در StudentPortal فعلاً فقط Q-007 است |
| dashboard | 2 | KPI exact values و local push status؛ fixed clock overdue/dunning values asserted |
| dunning | 2 | due-bucket boundaries/order/messages، 48h ActivityLog/SmsLog idempotency، missing/deleted/paid/no-mobile/suspended, admin-only roles, exact local logs/retry و Kotlin/Gson DTO؛ Q-027 برای deleted/suspended direct-ID eligibility |
| messages | 7 | list/history role/order/filter, conversation create, send/retry, broadcast fanout, soft-delete, per-role pin، exact Notification/push spy و Kotlin/Gson DTO؛ latest suite **14 passed**; `RA-messages-01/02/03` بسته‌اند. API برای recipient arrays ناقص 422 می‌دهد، ولی Android prompt/continuation UI پیاده نشده. Q-028 حل شد؛ Q-029..Q-031 بازند |
| serve_upload | 1 | temp file bytes/MIME/length, five authenticated roles, auth/missing/path-validation responses, exact DB no-write; Glide screen source/Authorization header and placeholder |
| timeline | 1 | all four exact event DTOs, Persian/Gregorian timestamp normalization, empty/read-only, five-role access scopes, missing/deleted/suspended states, per-source 20, merged 50, Gson/Android display; Q-032..Q-034 keep visibility/order/format unconfirmed |
| reports | 9 | debtor/statement/chart subset و date/order assertions |
| analytics | 6 | filter/date/limit/funnel subset |
| exports | 3 | CSV header/rows subset؛ PDF/XLSX کامل هنوز مانع دارد |
| exams | 7 | list/attempt subset؛ O-12/`RA-exams-02` و O-14/`RA-parent-01` در این checkout fixed/سبز هستند |
| homework | 6 | scope/optional defaults؛ graded parent row اکنون `max_score` را برمی‌گرداند (`RA-homework-01` بسته) |
| parent | 5 | profile/portal values و role slice؛ OTP/select-child transitionها هنوز deep نشده‌اند |
| crm | 5 | create/list/notes/convert/online registration; exact row/response, 206-row/null-safe list, conversion/idempotency, independent finance oracle, audit/SMS/notification mock, rollback; `RA-crm-01/02/03` fixes complete; Q-010..Q-015 remain unresolved |
| automation | 5 | rule CRUD/list/log filtering, all eight trigger conditions, exact notification/SMS/log effects, retry/idempotency, no network/push; `RA-automation-01/02/03` fixes complete; action, threshold and date-format questions Q-016..Q-018 remain open |
| branches | 9 | branch/resource CRUD and filters, exact branch-stat financial/count oracle, booking tests; `RA-branches-01` closed per decision (duplicate bookings allowed), `RA-branches-02` closed (duplicate serial update returns clear error before writes); toggle/update/stat/resource-scope questions Q-019..Q-022 remain open |
| calendar | 4 | room CRUD/list and empty/full, teacher/room/student/resource conflict matrix, role-scoped exact calendar events, Kotlin/Gson contract; null-description candidate (Q-023), event/conflict/branch policies Q-024..Q-026 |

هیچ routerِ بدون suite متمرکز باقی نمانده است؛ هر 221 route در inventory/ledger ثبت است، اما 70 route literal test-reference ندارند و پوشش branchها همچنان **partial** است. ledgerها smoke-only gaps را نشان می‌دهند.

## آخرین اجراهای واقعی

```text
Route audit: PYTHONPATH=. /tmp/kharazmi-route-audit-venv/bin/pytest -q tests/route_audit --basetemp=/tmp/kharazmi-route-audit-final-o19-20261007
249 passed, 0 xfailed, 4 warnings in 24.42s (2026-10-07)
Server suite: DATABASE_URL=sqlite:////tmp/... pytest -q Kharazmi_Server/tests
1279 passed, 87 warnings in 132.30s; targeted archive/restore tests 27 passed
main DB MD5 before/after: f048f8d118b33c4eaa944490594121d7

Broad route sweep (2026-10-07): 221/221; main 500=0; 220 invalid-target probes; invalid 500=0
invalid observations: 422=146, 200=71, 400=3, 404=1
empty probes: 11; null-list observations=0; non-JSON responses=14
status: 200=182, 400=18, 401=1, 404=7, 409=5, 422=8; no 403
roles: admin=168, teacher=21, student=18, public=9, parent=5
contract: declarations=170, unique_calls=159, unique_static_routes=157,
          dynamic=1, unmatched=0, route_non_success=29, successful_non_json=4,
          empty_json_body=0, parse=0, NPE-candidates=5, silent-zero-candidates=7,
          missing_key=0, simulation_gap=0
boundary: 4 routes, 500=0, raw candidates=5, confirmed contract bugs=0 (Q-006)
large seed: 300 students/30 classes + 300 transaction/session rows; 8/8 checks pass, all statuses 200
Markdown generator: 25 ledgers; table-column and unwrapped-cell regression tests pass
```

هیچ strict xfail باقی نمانده؛ O-19 / `RA-admin-19` اکنون با restore عملیاتی، checkbox مالی opt-in و provenance fail-closed پیاده‌سازی و تست شده است. O-02 Android registration source/contract wiring بسته است؛ token generation واقعی به چهار Firebase client setting و device QA نیاز دارد. `RA-messages-01/02/03` و سایر fixهای تأییدشده در `bugs.md` بسته‌اند. contract simulator همچنان candidateهای خام Q-006..Q-008 را ثبت می‌کند؛ آن‌ها باگ تأییدشده نیستند. Full Android build و device execution اجرا نشده‌اند.

`docs/route-tests/routes/*.md` برای هر route: یک جملهٔ purpose/handler، actor و status probe، caller/screen جاری، ورودی و response schema، DB read/write statically extracted، side effect و test-reference یا smoke-only status دارد. 151 route test source literal request reference دارند؛ این شمارش به‌تنهایی عمق assertion را اثبات نمی‌کند. 70 مسیر literal match ندارند؛ ledger per-route قید هر مورد را نشان می‌دهد.

## دیتابیس اصلی و commit

در اجرای کامل 2026-10-06، `md5sum Kharazmi_Server/gaj_db.db` قبل و بعد از pytest برابر `f048f8d118b33c4eaa944490594121d7` ثبت شد؛ route tests از DB موقت استفاده کردند. این snapshot شامل زیرساخت deterministic seed، audit QR، socket blocking، oracle invoice، CRM، automation، branch/resource، calendar، dunning، messages، serve_upload و timeline audit/log/file/event assertions و ledgerهای جاری است. هر 25 router suite متمرکز دارند و تمام 221 route در inventory/ledger هستند؛ 70 route literal request-reference ندارند و branchها deep نشده‌اند. Fixهای پذیرفته‌شده در `bugs.md` ثبت شده‌اند؛ Android build/device و UI follow-upهای لازم انجام نشده‌اند.
