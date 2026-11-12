# گیتِ قراردادِ مسیرهای اندروید↔سرور — `validate_app_map.py --gate` در CI

## ۱) چرا این برش

`scripts/validate_app_map.py` در HEAD **همیشه** با exit=1 بیرون می‌آمد و در هیچ workflow
هم نبود. اسکریپتی که همیشه قرمز است گیت نمی‌شود، و در نتیجه سیگنال‌هایِ واقعاً مفیدش
هیچ‌وقت **خودکار** اجرا نمی‌شدند:

* `android_only_routes == 0` — یعنی اندروید هرگز مسیری را صدا نزند که سرور ندارد.
  نقضِ این، کلاسِ **404 در زمانِ اجرا** است: اپِ منتشرشده رویِ گوشیِ معلم دکمه‌ای دارد
  که به endpointِ ناموجود می‌خورد. هیچ تستِ دیگری این را نمی‌گیرد، چون تست‌های
  route-audit سمتِ سرور را می‌سنجند نه اعلام‌های Retrofit را.
* `server_map_exact` — یعنی `docs/app-map/server-routes.csv` هنوز با سطحِ واقعیِ OpenAPI
  یکی باشد (نه routeِ غایب، نه routeِ کهنه).
* نبودِ «اعلامِ شبح» — مسیری که در نقشه هست ولی از سورسِ Kotlin ناپدید شده.

## ۲) اندازه‌گیری: exit=1 **عمدی** است، نه نقص

```
retrofit_declarations_source = 170      retrofit_declarations_map = 162
retrofit_source_map_exact    = False    retrofit_source_map_missing = []
retrofit_source_map_extra    = ۸ مورد:
    POST attendance/{course_id}/start_live      POST attendance/{session_id}/live_status
    POST attendance/{session_id}/end_live       POST attendance/{session_id}/cancel_live
    GET  attendance/live/current                GET  admin/live_sessions
    GET  admin/live_sessions/{session_id}/roster POST auth/device_token
android_only_routes = 0 · server_map_exact = True · server_runtime_count = 221
server_map_missing = [] · server_map_stale = []
```

سه شاهدِ مستقل که این دریفت **عمدی** است:

1. خودِ اسکریپت: «Keep the historical map mismatch visible even when overlays were
   written; `--write` does not rewrite the supplied phase-zero inputs» — و docstringش
   `docs/app-map` را «historical map artifacts» می‌نامد که «untouched» می‌مانند.
2. `tests/route_audit/test_phase_zero_map.py` شمارِ سورس را **۱۷۰ پین کرده** و صریحاً
   `POST auth/device_token` و هر ۷ مسیرِ `LiveApi` را به‌عنوانِ زیرمجموعهٔ لازم می‌خواهد.
   یعنی سورس درست است و CSVِ تاریخیِ ۱۶۲ تایی عمداً عقب نگه داشته شده.
3. شرطِ `retrofit_source_map_exact` در `map_current` تنها چیزی است که exit=1 را می‌سازد؛
   سه شرطِ دیگر همه برقرارند.

پس راهِ درست «اصلاحِ CSVِ تاریخی» نبود (ورودیِ منجمدِ فازِ صفر است و تست هم ۱۷۰ را
پین کرده)، و نه «بی‌خیال شدنِ اسکریپت». راهِ درست **جدا کردنِ دو پرسش** بود.

## ۳) تغییر

**الف) `evaluate_gate(report, saved_count, live_keys) -> list[str]`** — تابعِ **خالص**.
چرا خالص: تا بدونِ import کردنِ اپِ FastAPI (که spin-upِ DB یک‌بارمصرف دارد) قابلِ تست
باشد. سه ناوردا را برمی‌گرداند:

| ناوردا | پیامِ شکست |
|---|---|
| `android_only_routes == 0` | «the app calls route(s) the server does not expose (runtime 404): …» |
| `server_map_exact` + هم‌خوانیِ شمارِ live با CSV | «docs/app-map/server-routes.csv disagrees with the live OpenAPI surface» / «server route count drift» |
| `retrofit_source_map_missing == []` | «the historical map lists N declaration(s) that no longer exist in the Kotlin source» |

و عمداً `retrofit_source_map_extra` را **چک نمی‌کند** — همان دریفتِ تاریخیِ بخشِ ۲.
اگر `live_keys is None` باشد (یعنی `--skip-server-import`) هم شکست می‌دهد: گیتِ
بی‌داده هرگز «سبز» نیست.

**ب) `--gate` در `main_cli`** — همان JSONِ همیشگی چاپ می‌شود (تا تشخیص از annotation
و لاگ خوانده شود)، بعد یا `::error title=route contract gate::…` برای هر ناوردا و
exit=1، یا `route contract gate: OK …` و exit=0. **رفتارِ پیش‌فرض دست‌نخورده ماند**:
بدونِ `--gate` همان exit=1 قبلی است، پس دریفتِ تاریخی همچنان دیده می‌شود.

**پ) گامِ CI** در jobِ `pytest` در `.github/workflows/tests.yml`:
`python scripts/validate_app_map.py --gate`، **پیش از** گامِ «Guard - real institute
database untouched» قرار گرفت تا همان گاردِ md5 این step را هم پوشش بدهد. هزینه‌اش
~۲ ثانیه است و نیاز به وابستگیِ تازه ندارد (اسکریپت فقط stdlib است و stepِ نصبِ CI
همان `requirements.txt pytest` را دارد). `live_server_routes()` اپ را با DB
یک‌بارمصرف import می‌کند، stdout/stderr را می‌بندد و threadِ «live-session-auto-ender»
را شروع نمی‌کند؛ هرگز `Kharazmi_Server/gaj_db.db` را باز نمی‌کند.

**ت) سه تستِ شاهد** در همان `test_phase_zero_map.py` — مرزِ دقیقِ گیت را قفل می‌کنند:

1. `test_gate_passes_when_only_the_historical_map_drifts` — دریفتِ فازِ صفر به‌تنهایی
   **نباید** بشکند، وگرنه گیت مثلِ قبل همیشه قرمز است. این مهم‌ترینِ سه تست است چون
   دقیقاً همان اشتباهی را می‌بندد که باعث شد اسکریپت سال‌ها گیت نشود.
2. `test_gate_fails_on_every_live_contract_violation` — هر چهار نقضِ زنده (مسیرِ
   فقط‌اندرویدی با ذکرِ «404» و نامِ مسیر، دریفتِ CSV، دریفتِ شمار، و نبودِ اسکنِ
   زنده) باید **دقیقاً یک** شکست با پیامِ تشخیصی بدهد.
3. `test_gate_fails_on_phantom_map_entries` — اعلامِ شبح باید گرفته شود.

## ۴) شواهد

| بررسی | نتیجه |
|---|---|
| `validate_app_map.py --gate` | **exit=0** · «route contract gate: OK - no Android-only route, server CSV matches the live OpenAPI surface (221 routes), no phantom map entry» |
| `validate_app_map.py` (پیش‌فرض) | **exit=1** — بدونِ تغییر، دریفتِ تاریخی همچنان دیده می‌شود |
| `pytest -q` (ریشه) | **1279 passed** in 114.13s · ۰ FAILED/ERROR |
| `pytest ./tests/route_audit -q` | 252 → **255 passed** (+۳ تستِ شاهد) |
| سوئیتِ cwd-independence از داخلِ `Kharazmi_Server` | **31 passed** |
| `test_phase_zero_map.py` به‌تنهایی | **5 passed** (۲ قبلی + ۳ تازه) |
| YAMLِ workflow | با `yaml.safe_load` تجزیه شد؛ گامِ تازه در jobِ `pytest` و پیش از گاردِ md5 |
| `ruff check .` | ۲۵۰ → **۲۵۰** (صفر یافتهٔ تازه) |
| ruffِ تک‌فایل: نسخهٔ HEAD در برابرِ نسخهٔ تازه | **۱ → ۱** ⇒ آن `F841` (`out = []` در `:281`، تابعِ `--write`) **پیش‌موجود** است، نه از این برش |
| `mypy Kharazmi_Server/` | **725 در ۴۴ فایل** (بی‌تغییر) |
| md5 دیتابیسِ واقعی | `f048f8d118b33c4eaa944490594121d7` · `git ls-files -d` = ۰ · `git diff --stat HEAD -- KHarazmi_Server/gaj_db.db` خالی · blobِ HEAD `ead925c9…` |
| `git ls-files -m` | فقط سه فایلِ همین برش |

`KHarazmi_Server/tests/` طبقِ قانونِ پذیرش دست‌نخورده ماند؛ تست‌های تازه در
`tests/route_audit/` هستند که `testpaths` جمعشان نمی‌کند، پس ۱۲۷۹ تغییر نکرد.

## ۵) نکتهٔ روش‌کار: یک `md5sum` ناموفق را با سه شاهدِ دیگر پوشش بده

در میانهٔ راستی‌آزمایی، `md5sum KHarazmi_Server/gaj_db.db` یک بار `No such file or
directory` داد درحالی‌که `git status` هیچ حذفی نشان نمی‌داد. در تلاشِ دومِ همان حلقه
همان md5ِ بیس‌لاین برگشت. معیارِ عملیِ این برش: یک خواندنِ ناموفق **داده نیست**؛
یا حلقهٔ تلاش بزن و شاهدِ مثبت بگیر، یا سه شاهدِ مستقلِ دیگر (`git ls-files -d`،
`git diff --stat HEAD -- <path>`، `git rev-parse HEAD:<path>`).

## ۶) بدهیِ باقی‌مانده

* `F841 out = []` در `scripts/validate_app_map.py:281` (تابعِ `--write`) — پیش‌موجود،
  ۱ مورد از ۲۵۰. عمداً دست نخورد: ruff خودش «unsafe fix» می‌دهد و آزمودنِ `--write`
  یعنی نوشتنِ دو overlayِ tracked در `docs/route-tests/` که در این برش نویزِ بی‌مورد بود.
* `ruff` ۲۵۰ یافته (۳ مورد `--fix`پذیر) و `mypy` ۷۲۵ مسئله در ۴۴ فایل؛ هیچ‌کدام F821
  نیستند. گیتِ «بدتر نشود» برایِ این دو هنوز ساخته نشده — الگویِ `lint_gate.py` و همین
  `--gate` هر دو قابلِ کپی‌اند.
* گیتِ warningهای کامپایلرِ Kotlin (خطوطِ `w:`) — آیتمِ ۳ از «گامِ بعدِ» PR #14، هنوز
  ساخته نشده. گامِ کامپایلِ CI همین حالا لاگ را نگه می‌دارد
  (`:app:assembleDebug 2>&1 | tee /tmp/gradle-assemble.log`) و Kotlin 2.0.21 قالبِ
  `w: file:///…:L:C msg` می‌دهد، پس فقط یک اسکریپتِ گیت و یک step می‌خواهد.
* ریفکتور: ۱۰ ماژولِ بالایِ ۶۰۰ خط. امن‌ترین هدفِ بزرگ بر پایهٔ چگالیِ پین
  `AttendanceActivity.kt` است (۹۹۸ خط، ۶۸٫۱ پین بر هزار خط، ۱۷ پینِ سخت رویِ ۸ عضو
  از ۲۳ عضو ⇒ ۱۵ عضوِ آزاد)؛ مانعش اینکه بزرگ‌ترین عضویش `showAttendancePrintDialog`
  ۲۱۴ خط و ۳ پینِ سخت دارد و باید در فایل بماند. خوشهٔ آزادِ صف/شبکه
  (`flushPendingQueue` ۳۵ + `retryQueueItem` ۳۸ + `refreshQueueCard` ۵۴ +
  `isNetworkAvailable` ۶ + `refreshNetworkStatus` ۹ ≈ ۱۴۲ خط) کاندیدِ استخراج است.
* بدهیِ `./gradlew wrapper` از PR #19 (`validate-wrappers: false`).
