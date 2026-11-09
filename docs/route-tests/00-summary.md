# خلاصهٔ ممیزی تست‌محور routeها و قرارداد Android

**Snapshot:** 2026-10-07 · **Branch:** `arena/01a10aa8-kharazmiapp` · **Application code:** شامل fixهای تأییدشدهٔ audit و تصمیم‌های صریح محصول است. این سند وضعیت آزمون‌های همین checkout را گزارش می‌کند؛ اجرای smoke روی هر route معادل deep audit همهٔ branchها نیست.

**پایگاه اصلی:** MD5 قبل و بعد از اجرای pytest و runnerهای ایزوله `f048f8d118b33c4eaa944490594121d7` است. همهٔ seedها در DB موقت ساخته شده‌اند؛ SMS/push/network واقعی فراخوانی نشده است.

## دامنه و مرحلهٔ صفر

- ورودی اصلی نگاشت، `docs/app-map/*` است و route path inventory آن حفظ شده است؛ metadata پنج route مربوط به حذف/تأیید حذف/جزئیات/بازیابی کلاس برای provenance و فیلدهای O-19 به‌روزرسانی شد. server map همچنان 221 route در 25 router دارد.
- مقایسهٔ Android جاری با نگاشت تاریخی در `android-api-current.csv` و `android-route-diff.md`: 170 declaration در Kotlin جاری، 162 در map تاریخی، 159 زوج یکتای method/path، 157 مسیر static یکتا، 1 `@Url` پویا، 64 server-only و 0 Android-only؛ route جدید `/auth/device_token` اکنون caller مستقیم دارد.
- این map، retrofit caller/screen، response data class/field، handler/source، ورودی OpenAPI، DB read/write استاتیک و side effect را کنار هم قرار می‌دهد. 25 ledger در `routes/*.md`، 221 route را پوشش می‌دهند.
- seed canonical پایدار و مستقل است: 30 دانش‌آموز، 7 کلاس، 7 enrollment، 6 transaction، 3 session، 4 attendance، 4 installment، 2 grade، 1 homework و 2 exam؛ timestamp/JWT/hash deterministic هستند. fixture حجیم مستقل 300 دانش‌آموز، 30 کلاس، 300 transaction و 300 session دارد.
- زمان seed روی `2026-09-28 09:00:00` freeze است. guard از اتصال به `Kharazmi_Server/gaj_db.db` جلوگیری می‌کند؛ فقط temporary DB استفاده می‌شود. `requests`, `urllib`, `socket` در pytest و runnerهای مستقل fail-closed هستند؛ subprocess regression در `test_sweep_network_guard.py` این مسدودسازی را بررسی می‌کند و worker زمان‌بندی‌شده نیز در test اجرا نمی‌شود.

## نتایج واقعی آخرین sweep / runnerها

| Probe | نتیجه |
|---|---|
| Route smoke | 221/221 route اجرا شد؛ status 500 = 0 |
| Status اصلی | `200:182`, `400:18`, `401:1`, `404:7`, `409:5`, `422:8`; هیچ 403 مشاهده نشد |
| Actor probe | admin=168، teacher=21، student=18، public=9، parent=5؛ این نقش‌ها probe هستند، نه اثبات کامل مجوز route |
| Invalid-input | 220/221 route هدف invalid-target دارند؛ statusها `422:146`, `200:71`, `400:3`, `404:1`; invalid status 500 = 0 |
| Empty probes | 11؛ null-list مشاهده‌شده = 0 |
| Non-JSON | 14 پاسخ در sweep؛ endpointهایی که HTML/file/empty response دارند باید با contract خودشان تفسیر شوند |
| Boundary | 4 route، 500=0؛ `Exam.max_score=12.5`, transaction=`2147483649`, empty string/null/list بررسی شد؛ 5 خام Gson-candidate، 0 مورد تأییدشده |
| Large | هر 8 check مربوط به limit/order/filter/count/debtors/session سبز؛ تمام statusها 200 |

این آمار از اجرای مجدد runnerها در 2026-10-07 است. `GET /finance/parent/dashboard` با parent session معتبر اکنون 200 می‌دهد (`RA-finance-02` بسته)؛ هیچ 403 در route smoke جدید ثبت نشد.

## Retrofit ↔ Kotlin/Gson simulator

اسکریپت شبیه‌ساز، declarationها و data classهای Kotlin فعلی را با payloadهای واقعی route مقایسه می‌کند؛ **Gradle/Gson runtime یا گوشی اجرا نشده است**.

```text
170 declarations; 159 unique calls; 157 unique static method/path routes
 dynamic=1; unmatched=0; route_non_success=29; successful_non_json=4
 empty_json_body=0; parse=0; npe=5; silent_zero=7
 missing_key=0; simulation_gap=0
```

این شمارنده‌ها candidate detector هستند، نه تعداد باگ قطعی. یافته‌های مصرف‌شده/نامطمئن در Q-006..Q-008 طبقه‌بندی شده‌اند: incomplete-class fields با caller مصرف‌کنندهٔ فقط `id/title/code`؛ نبود `parent_mobile` در screen دانش‌آموز؛ و فیلدهای اختیاری/غایب transaction که screen فعلی از آنها استفاده نمی‌کند. `RA-homework-01` برای `max_score` در حالت homework نمره‌دار در این checkout بسته و regression آن سبز است.

## پوشش رفتاری و مالی

- تمام 25 router دارای testهای متمرکز هستند: ai, audit, audit_trail, auth, finance, attendance, classes, admin, teachers, students, dashboard, reports, analytics, exports, exams, homework, parent, crm, automation, branches, calendar, dunning, messages, serve_upload, timeline. پوشش این 221 route **partial** است و تمام transitionها/branchهایشان عمیق نشده‌اند.
- 151 route در test sourceها literal client request reference دارند؛ این شمارش، عمق assertion را ثابت نمی‌کند. 70 مسیر literal match ندارند. ledger هر route test-reference یا smoke-only را مشخص می‌کند.
- finance دارای oracle مستقل tuition/discount/payment/due، split wallet، FIFO installment allocation و receipt/reversal است. invariantهای retry شامل direct payment، installment payment، session charge و teacher settlement/reversal بررسی شده‌اند؛ `target_wallet=both`، معنای income، واحد مبلغ و بی‌تاریخی در questions ثبت‌اند. restore کلاس بر اساس Q-005 با checkbox اختیاری، provenance مالی و rollback اتمی پیاده‌سازی و تست شده است.
- AI route برای admin/teacher/student/parent با actor fixture درست، tool-data دقیق، response contract و نبود DB side effect بررسی شد. `RA-ai-01` بسته است؛ history بعد از append نیز به حداکثر 15 پیام محدود می‌شود.
- Audit route با seed خالی، خروجی read-only، early/delayed-session alerts، rapid-delete در پنجرهٔ 30 روز با حد <1h (رد دقیقاً 1h) و perfect-attendance روی ده session آخر؛ absent خارج از پنجره نادیده گرفته می‌شود بررسی شد؛ regressionهای read مسیر DB را تغییر ندادند.
- Audit-trail route با فیلتر/جست‌وجوی transaction و installment، خروجی دقیق Android DTO، تاریخ ISO/Jalali، صفحه‌بندی و ردیف‌های یتیم/soft-deleted بررسی شد. Rollback یک update مالی، هم مقدار تراکنش و هم لاگ ممیزی را برمی‌گرداند. `RA-audit_trail-01` بسته است؛ بازهٔ تاریخ-only وارونه در هر دو قالب ISO و Jalali با 400 رد می‌شود.
- Auth/notification routes با ورود مثبت admin/secretary/teacher، `me`، تغییر رمز و موبایل، OTP دانش‌آموز، session logout، token registration و inbox/unread/read transitions بررسی شدند؛ SMS فقط با SmsLog موقت mock شد. O-02 client wiring اکنون FCM token را پس از ورود/چرخش ثبت و هنگام logout همان device token را حذف می‌کند؛ Firebase project values و device runtime هنوز نیازمند تنظیم/آزمون‌اند. آزمون امنیتی (credential guessing، token forgery و auth bypass) خارج از scope است.
- suite رفتاری CRM در `tests/route_audit/test_audit_crm.py` هر پنج route را با DB موقت پوشش می‌دهد: create/list/notes/conversion و public online registration، exact Kotlin response contract، ترتیب/legacy-null/Gson list، duplicate/retry و row snapshots، independent finance oracle، `FinancialAuditLog`، wallet/enrollment invariants، SMS/notification mock و rollback. `RA-crm-01/02/03` در این checkout بسته‌اند؛ انتخاب tuition، branch ownership، class eligibility، nullable follow-up، empty-mobile و overpayment همچنان در Q-010..Q-015 باز است.
- Automation suite در `tests/route_audit/test_audit_automation.py` هر پنج server-only route را پوشش می‌دهد: rule create/update, logs filter/order/pagination, empty/no-active behavior و تمام هشت condition engine با side-effect rows، finance-safe snapshots، retry/idempotency و push/SMS isolation. `RA-automation-01/02/03` بسته‌اند؛ action matrix, threshold units و mixed-calendar semantics در Q-016..Q-018 همچنان بازند.
- Branch/resource suite در `tests/route_audit/test_audit_branches.py` هر نه route را تست می‌کند: branch/resource CRUD, filters, missing/duplicate inputs, toggle repeat, branch finance/count aggregates, booking time slots, exact DB snapshots. `RA-branches-01` بسته per decision است (رزرو تکراری مجاز) و `RA-branches-02` duplicate serial را پیش از write با خطای روشن رد می‌کند؛ suspend retry, nullable update, stats semantics و reservation scope در Q-019..Q-022 بازند.
- Calendar suite در `tests/route_audit/test_audit_calendar.py` هر چهار route و callerهای Android را با role-specific values، empty/full rooms، چهارنوع conflict، exact read/write snapshots و Kotlin/Gson source simulator می‌سنجد. سه behavioral cases پاس؛ nullable homework detail یک simulator candidate است، نه strict xfail/باگ تأییدشده (Q-023)؛ event visibility، conflict predicate و branch assignment در Q-024..Q-026 بازند.
- Dunning suite در `tests/route_audit/test_audit_dunning.py` هر دو route را با clock ثابت، مرزهای 48ساعته/روزهای سررسید، order/category/message exact، missing/deleted/paid/no-mobile/suspended cases، role guard، Kotlin/Gson DTO، no-write read، local SmsLog/ActivityLog، batch dedupe و retry پوشش می‌دهد؛ **6 passed**. direct batch برای Student حذف‌شده و suspended فعلاً log می‌سازد؛ eligibility مبهم در Q-027 است، نه xfail. SMS gateway واقعی فراخوانی نمی‌شود.
- Messages suite در `tests/route_audit/test_audit_messages.py` هر 7 route را با role-filtered empty/full conversation lists، history ordering/soft-delete, conversation creation, send/broadcast Notification rows, pinned preference, delete own-message, exact rollback, permission checks, push spy و Kotlin/Gson DTO می‌سنجد؛ آخرین اجرا **14 passed, 0 xfailed**. `RA-messages-01/02/03` بسته‌اند: recipient identity برابر `(user_id, role)` است؛ آرایه‌های ناقص 422 ساخت‌یافته و no-write دارند؛ و فقط `everyone`/`class` معتبرند. UI prompt مربوط به تکمیل recipient در Android هنوز پیاده نشده؛ fanout eligibility, retry semantics و suspended participants در Q-029..Q-031 بازند.
- `serve_upload` suite در `tests/route_audit/test_audit_serve_upload.py` فایل واقعی را فقط از temporary upload root برمی‌گرداند، همهٔ پنج نقش authenticated، exact bytes/MIME/length، 401/404 و filename validation را می‌سنجد و snapshot کامل DB را برای no-write مقایسه می‌کند؛ **11 passed**. سه Android screen از Glide با bearer token استفاده می‌کنند و source-contract test این display/header/error-placeholder flow را check می‌کند؛ Gradle/device اجرا نشده.
- Timeline suite در `tests/route_audit/test_audit_timeline.py` هر چهار type را با row-by-row payload/order, Persian/Gregorian normalized timestamps, amount/score color, due-today/overdue/paid installments, absent/present and soft-delete filters, empty/full, 20-per-source/50-global boundaries و full read-only snapshots بررسی می‌کند؛ **9 passed**. Admin/secretary/teacher/parent/student scope، 401/403/404/422، deleted/suspended state و `TimelineEvent` Gson + StudentProfile/TimelineAdapter display نیز چک می‌شوند. Soft-deleted attendance/deleted-session visibility، ID-vs-time limit و timestamp format در Q-032..Q-034 هستند؛ device/Gradle اجرا نشده، xfail/bug ادعایی ایجاد نشده.
- attendance: history/detail، snapshot هزینه، same-day QR check-in، stale QR، live start/status/cancel، conflict/retry و بی‌اثری مالی cancellation تست شده‌اند. مبلغ 260,000 در oracle جلسه با DB assert می‌شود.
- علاوه بر آن KPIهای dashboard، date/filter/order/limit subset، CSV، exam-attempt retry، homework scope، parent/child access و student optimistic version conflict آزمون شده‌اند.

## باگ‌ها و xfailها

آخرین اجرای کامل `PYTHONPATH=. /tmp/kharazmi-route-audit-venv/bin/pytest -q tests/route_audit --basetemp=/tmp/kharazmi-route-audit-final-o19-20261007` در 2026-10-07:

```text
249 passed, 0 xfailed, 4 warnings in 24.42s
```

هم‌زمانی O-19 در `Kharazmi_Server/tests`: **1279 passed, 87 warnings in 132.30s**؛ targeted restore/archive tests نیز **27 passed**. `Kharazmi_Server/gaj_db.db` قبل و بعد همان `f048f8d118b33c4eaa944490594121d7` بود؛ تست‌ها و runnerها از DBهای موقت استفاده کردند.

O-19 / `RA-admin-19` بسته است: کلاس و history عملیاتی به‌طور پیش‌فرض بازمی‌گردند؛ checkbox خاموش تراکنش‌ها، اقساط و wallet را دست‌نخورده می‌گذارد؛ checkbox روشن فقط اثرهای مالیِ دارای provenance همان حذف را اتمی برمی‌گرداند. اعتبار خرج‌شده یا حذف قدیمی بی‌provenance مالی با 409 و بدون تغییر رد می‌شود. Android source/contract wiring تست شده، اما full Android build و device QA اجرا نشده‌اند. O-02 Firebase runtime نیز تا دریافت تنظیمات پروژه و تست device تأیید نشده است؛ fixهای دیگر و reproductionها در `bugs.md` هستند.

## ناتمام‌ها و مراجع

- هیچ routerِ بدون suite متمرکز باقی نمانده و هر 221 route در inventory/ledger ثبت است؛ عمق branchها هنوز partial است و 70 route literal test-reference ندارند (جزئیات در ledger و `blockers.md`).
- 32 تصمیم محصول/contract همچنان باز است: Q-001..Q-004, Q-006..Q-027, Q-029..Q-034 در `questions.md`; Q-005 restore policy و Q-028 broadcast targets حل‌شده‌اند. تست‌ها rule مبهم دیگری را حدس نمی‌زنند.
- Android compile/runtime و device execution انجام نشده. Checklist دستی با seed values در `device-checklist.md` آمده است.
- شمارش و فایل‌های خام: `sweep/report.json`, `contract-report.json`, `boundary-report.json`, `large-report.json`; runnerهای مستقل در `tests/route_audit/sweep/`.
- تست کامل: `PYTHONPATH=. /tmp/kharazmi-route-audit-venv/bin/pytest -q tests/route_audit`.
