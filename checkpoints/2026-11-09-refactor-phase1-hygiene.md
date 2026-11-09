# ۲۰۲۶-۱۱-۰۹ — ریفکتور کامل پروژه: نقشهٔ راه + گزارش فاز ۱ (بهداشت ریپو)

## صورت مسئله

کاربر درخواست «ریفکتور کامل» روی کل پروژه داد (~۵۴ هزار خط پایتون + ~۲۵ هزار خط کاتلین).
چنین درخواستی بدون قاب‌بندی، هم‌ارز «بازنویسی بی‌حساب» است و می‌تواند سامانهٔ در حال
استفادهٔ آموزشگاه را بشکند. پس پیش از دست‌زدن به کد، چهار تصمیم با کاربر گرفته شد:

| تصمیم | انتخاب کاربر | پیامد اجرایی |
| --- | --- | --- |
| دامنه | هر دو بخش، **فازبندی‌شده — اول بک‌اند** | فازهای ۱ تا ۳ روی `Kharazmi_Server`، فاز ۴ روی `KharazmiAdmin` |
| ریسک | **کاملاً رفتار‌حفظ** | endpointها، schema دیتابیس و شکل پاسخ JSON هیچ تغییری نمی‌کنند؛ معیار پذیرش هر فاز: سبز ماندن کل سوئیت |
| اولویت | **هر سه، به ترتیب**: پاک‌سازی ← typing/lint ← شکستن ماژول‌های غول‌پیکر | ترتیب فازها همین شد |
| آرشیو zip | حذف | در فاز ۱ حذف شد (محتوایش در PR #1 extract و نسخه‌بندی شده) |

## تور ایمنی (پیش از هر تغییر اندازه‌گیری شد)

```
DATABASE_URL=sqlite:////tmp/kharazmi_base.db JWT_SECRET_KEY=... \
  python -m pytest Kharazmi_Server/tests -q
→ 1279 passed, 86 warnings in 139.90s
→ md5 دیتابیس واقعی (gaj_db.db) پیش و پس از اجرا یکسان
```

این عدد **مبنای مقایسهٔ همهٔ فازهاست**: هر فاز باید همان ۱۲۷۹ را پاس کند (یا تعدادش را
با دلیل مستند بالا ببرد)، و md5 دیتابیس واقعی نباید عوض شود.

## نقشهٔ راه

| فاز | محتوا | وضعیت |
| --- | --- | --- |
| **P1** | بهداشت ریپو: حذف آرشیو و اسکریپت‌های مرده، سامان‌دهی اسکریپت‌های عملیاتی، پیکربندی ruff/mypy، `.gitignore` | ✅ انجام شد (همین سند) |
| **P2** | lint/type: مهاجرت `dict()` → `model_dump()` و `declarative_base()` (warningها ۸۶ ← ۲) + اصلاح‌های امن راف: یافته‌ها ۲۵۱۹ ← ۱۱۵۷ ← **۲۵۱** | ✅ انجام شد — PR #4 و `2026-11-09-refactor-phase2c-dead-code-and-schema-dedupe.md` |
| **P2b** | **احیای سوئیت `tests/route_audit`** (۱۶۷ تست قرمز به‌دلیل پوسیدگی زمانی) + افزودنش به CI به‌عنوان job جدا | ✅ انجام شد — `2026-11-09-route-audit-clock-rot-fix.md` |
| **P3** | شکستن ماژول‌های غول‌پیکر: `routers/admin.py` (۲۹۹۳ خط)، `routers/finance.py` (۲۸۲۲)، `attendance.py` (۱۵۶۱)، `classes.py` (۱۵۶۰) ← استخراج لایهٔ service، با **نگه‌داشتن دکوریتورهای route در همان فایل روتر** | ⏳ |
| **P4** | اپ اندروید: Activityهای غول‌پیکر (`StudentProfileActivity` ۱۲۶۴، `InvoiceActivity` ۱۲۴۸، `AttendanceActivity` ۱۰۱۲، `ClassDetailActivity` ۹۴۸)، حذف duplication، جدا کردن لایهٔ داده از UI | ⏳ |
| **P5** | سفت‌کردن تدریجی mypy + افزودن job لینتر به CI (فقط وقتی شمار خطاها به صفر رسید) | ⏳ |

## فاز ۱ — چه شد و چرا

### ۱) حذف آرشیو zip
`KharazmiApp-arena-01a10aa8-kharazmiapp.zip` (۲٫۶MB) حذف شد: محتوایش در PR #1 به‌صورت
سورس نسخه‌بندی شده و خودِ آرشیو فقط تاریخچهٔ git را سنگین می‌کرد (از تاریخچه قابل بازیابی است).

### ۲) حذف ۹ اسکریپت مردهٔ **خطرناک**
این فایل‌ها هیچ ارجاعی در کل ریپو نداشتند (کد، تست، CI، مستندات، اپ اندروید) و همه‌شان
مستقیم به دیتابیس واقعی وصل می‌شدند:

```
check_courses.py  check_parents.py  check_pricing_table.py  check_teacher_pass.py
check_teachers.py  check_users.py  insert_fresh_token.py  create_distinct_teacher.py
update_parent_mobile.py
```

> **چرا حذف، نه جابه‌جایی:** همه‌شان `DATABASE_URL = "sqlite:///gaj_db.db"` را **هاردکد**
> کرده بودند؛ یعنی هر اجرای تصادفی‌شان روی دیتابیس واقعی آموزشگاه می‌نشست — نقض مستقیم
> «قانون طلایی» ریپو (دیتابیس واقعی هرگز دست‌کاری نمی‌شود). `insert_fresh_token.py` و
> `update_parent_mobile.py` علاوه بر آن write هم می‌کردند. نگه‌داشتنشان ریسک بود، نه دارایی.

### ۳) سامان‌دهی ۹ اسکریپت عملیاتی در `Kharazmi_Server/scripts/`
ابزارهای مفید ولی یک‌بارمصرف از ریشهٔ سرور (جایی که باید فقط ماژول‌های برنامه باشند) به
`scripts/` منتقل شدند — همان پوشه‌ای که از قبل ۱۲ اسکریپت عملیاتی داشت:

```
run_sec1_auth_curl_tests.py     run_sec3_class_lifecycle_tests.py
run_sec4_communication_tests.py run_sec10_network_isolation_tests.py
scan_modules_security.py        scan_security_group2.py
verify_analytics_consistency_test.py   run_financial_audit.py
backfill_normalize_mobiles.py
```

چون این اسکریپت‌ها با `__file__` مسیر bootstrap می‌ساختند، جابه‌جایی بدون اصلاح، import
ماژول‌های سرور را می‌شکست. برای هر کدام همان قرارداد موجودِ پوشه اعمال شد:

```python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

و در `backfill_normalize_mobiles.py` هر سه مسیر (`sys.path`، `.env`، `mobile_backfill_report.txt`)
به `SERVER_DIR` گره خورد تا **دقیقاً** مثل قبل رفتار کند (گزارس همان‌جا نوشته می‌شود).

`backfill_branch_ids.py` عمداً در ریشهٔ سرور **باقی ماند**: `tests/test_branch_resolution.py`
آن را به‌عنوان ماژول import می‌کند (`from backfill_branch_ids import collect_plan, apply_plan`)؛
یعنی عملاً کتابخانهٔ تست‌شده است، نه اسکریپت یک‌بارمصرف.

هر چهار اسکریپتِ منتقل‌شده‌ای که ماژول سرور import می‌کنند، از ریشهٔ ریپو و بدون `PYTHONPATH`
اجرا و smoke-test شدند (scan/verify/backfill سبز؛ `run_financial_audit.py` همان خطای **از قبل
موجود** را داد — با اجرای نسخهٔ اصلی از git هم دقیقاً همان خطا reproduce شد، پس اثر
جابه‌جایی نیست).

### ۴) پیکربندی ابزار کیفیت (`pyproject.toml` در ریشه)
تا امروز هیچ lint/type-check پیکربندی‌شده‌ای وجود نداشت. ruff و mypy با پیکربندی **متناسب با
این کدبیس** اضافه شدند. سه `ignore` دلیل رفتاری دارند و باید در بازبینی‌ها محترم بمانند:

- **`E712` خاموش** — `Column == True` در SQLAlchemy عبارت SQL می‌سازد؛ «اصلاح» پیشنهادی
  راف (`if Column:`) **معنای کوئری را عوض می‌کند**. ۵۰۹ مورد از این جنس در کد هست.
- **`RUF001/002/003` خاموش** — نویسهٔ فارسی/عربی زبان محصول است (پیام کاربر، متن گزارش)،
  نه نویسهٔ مبهم. بدون این ignore، ~۲۲۵۰ خطای کاذب ساخته می‌شد.
- **`B008` با `extend-immutable-calls`** — الگوی `Depends()`/`Query()` در مقدار پیش‌فرض،
  استاندارد FastAPI است؛ قاعده باز ماند، فقط فراخوانی‌های مجاز فهرست شدند.

`known-first-party` در isort هم لازم است چون تست‌ها/روتروها ماژول‌های سرور را با نام کوتاه
import می‌کنند (`import models`) و conftest پوشهٔ سرور را به `sys.path` می‌دهد.

### ۵) `Kharazmi_Server/requirements-dev.txt` و `.gitignore` ریشه
وابستگی توسعه از runtime جدا شد (راف/mypy با نسخهٔ pin تا قواعد lint بین توسعه‌دهنده و CI
یکسان بماند). `.venv/`، `.ruff_cache/`، `.mypy_cache/`، artefacts پوشش تست و قفل‌های
SQLite هم ignore شدند — خودِ `gaj_db.db` عمداً ردیابی‌شده می‌ماند.

## خط مبنا (برای مقایسهٔ فازهای بعد)

| سنجه | مقدار در پایان فاز ۱ |
| --- | --- |
| تست‌ها | **1279 passed** (~۱۴۰ ثانیه) + md5 دیتابیس واقعی دست‌نخورده |
| ruff (با پیکربندی جدید) | **2519 خطا** — بزرگ‌ترین‌ها: `W293` ۶۰۱، `F401` ۵۴۸، `UP045` ۵۲۷، `UP006` ۱۸۴، `I001` ۱۶۶، `F811` ۶۳، `F841` ۳۲، `B905` ۲۷، `E722` ۱۰، `B023` ۲ |
| mypy (پیکربندی تدریجی) | **750 خطا در ۳۲ فایل** |
| warningهای pytest | ۸۶ — تقریباً همه `PydanticDeprecatedSince20` برای `.dict()` |

> `B023` (function-uses-loop-variable) فقط ۲ مورد است ولی **کلاس باگ واقعی** است (closure
> داخل حلقه)؛ در فاز ۲ دستی بررسی می‌شود، نه با autofix.

## قیدهایی که فازهای بعد باید رعایت کنند (از دل تست‌ها بیرون کشیده شد)

سوئیت این پروژه چند **تست ساختاری** دارد که متن/AST فایل‌های سرور را می‌خوانند؛ یعنی
«هر فایلی را می‌شود جابه‌جا کرد» غلط است:

1. `tests/test_suite_cwd_independence.py` — وجود `pytest.ini` ریشه با `testpaths` شامل
   `Kharazmi_Server` و `KharazmiAdmin` را الزام می‌کند؛ و فایل‌های
   `routers/{audit,dashboard,dunning,finance}.py` باید **سرِ همان مسیر** وجود داشته باشند.
   همچنین هیچ تستی نباید مسیر نسبیِ وابسته به cwd داشته باشد.
2. `tests/test_storage_paths.py` — همهٔ `*.py`های `Kharazmi_Server/` و `Kharazmi_Server/routers/`
   را اسکن می‌کند: هیچ مسیر مطلق ماشینی (`/home/user` و…) جز در `storage.py` مجاز نیست و
   الگوی `os.path.join("uploads/…")` نباید برگردد. ⇒ ماژول‌های جدید هم باید از
   `storage.storage_path()/storage_dir()` استفاده کنند.
3. `test_audit.py`، `test_dashboard.py`، `test_dashboard_performance.py`، `test_exports.py`،
   `test_group4_display_fixes.py`، `test_android_resources_static.py` — **متنِ** چند روتر را
   می‌خوانند و روی الگوهای خاص assert می‌کنند (مثلاً نبودِ `except: pass`، استفاده از
   `joinedload` برای N+1، اعتبارسنجی مرکزی قسط، SQL count در داشبورد). ⇒ در فاز ۳،
   دکوریتورهای route و این الگوها باید در همان فایل روتر بمانند؛ فقط **منطق** به لایهٔ
   service منتقل می‌شود، و پیش از هر جابه‌جایی، assertهای متنیِ همان فایل چک می‌شود.
4. `main.py` چند نام را عمداً re-export می‌کند (`resolve_existing`, `auto_patch_database`,
   `serve_upload`) و تست‌ها به‌صورت `main.resolve_existing` صدا می‌زنند ⇒ حذف import
   «بی‌استفاده» از `main.py` رفتار را می‌شکند (per-file-ignore گذاشته شد).
5. `docs/app-map/server-routes.csv` منبع حقیقتِ تست‌های `tests/route_audit/` است
   (`route_registry.py` همین CSV را می‌خواند). ⇒ اگر روزی مسیر/متد endpointی عوض شود،
   این CSV و مستندات route باید با `scripts/generate_route_audit_docs.py` بازتولید شوند.
   در ریفکتور رفتار‌حفظ، هیچ routeای عوض نمی‌شود، پس CSV دست‌نخورده می‌ماند.

## مشکلات از قبل موجودی که در مسیر پیدا شد (اثر ریفکتور نیست)

### الف) سوئیت `tests/route_audit` «پوسیدگی زمانی» داشت — ۱۶۷ تست قرمز  ✅ **تعمیر شد**

> **به‌روزرسانی (همان روز، commit بعدی):** ریشه‌یابی قطعی + تعمیر انجام شد و سوئیت حالا
> **۲۴۹ پاس / ۰ قرمز** است؛ به CI هم به‌عنوان job جدا اضافه شد. گزارش کامل:
> `checkpoints/2026-11-09-route-audit-clock-rot-fix.md`. تحلیل زیر به‌عنوان سندِ تشخیص
> نگه داشته شده است.

این سوئیت (۲۴۹ تست) نه در CI است و نه در `testpaths` فایل `pytest.ini`، پس سال‌هاست دیده
نمی‌شود. اجرایش روی شاخهٔ کاری و روی `origin/main` دست‌نخورده **دقیقاً یکسان** است:

```
tests/route_audit → 167 failed, 82 passed   (هر دو: پیش و پس از تغییرات فاز ۱)
```

ریشهٔ مشکل با قطعیت پیدا شد:

1. `tests/route_audit/clock.py` ساعت را روی `FIXED_NOW = 2026-09-28` فریز می‌کند و
   `seed.py` همهٔ رکوردها (از جمله `UserSession.created_at`) را با همان تاریخ می‌سازد.
2. `TestClient(audit_app)` در fixture، رویداد startup را اجرا می‌کند ⇒
   `main.auto_patch_database` این بلوک را می‌زند:
   `expiry_limit = datetime.datetime.utcnow() - timedelta(days=30)` و سشن‌های قدیمی‌تر را
   **حذف** می‌کند (`SESSION_EXPIRY_DAYS = 30` در `dependencies.py`).
3. خروجی گرفتن تست‌ها همین را تأیید می‌کند: `🧹 Auto-cleanup: Removed 5 expired user sessions.`
   ⇒ بعد از آن هر مسیر احراز هویت‌شده `401 «نشست نامعتبر یا منقضی شده است»` می‌دهد
   (`dependencies.py:991`).

یعنی فریزِ ساعت تا مسیر startupِ `main` نفوذ نمی‌کند و تاریخِ **واقعی** ملاک پاک‌سازی است.
نتیجه: تا ۲۰۲۶-۱۰-۲۸ (۳۰ روز پس از تاریخ seed) سوئیت سبز بوده و از آن تاریخ به بعد
خودبه‌خود قرمز شده — snapshot ریپو مال ۲۰۲۶-۱۰-۰۷ است، یعنی وقتی بسته می‌شد سبز بوده.

> **چرا مهم است:** این ۲۴۹ تست، بزرگ‌ترین تور ایمنیِ route-level ریپو هستند (هر route با
> oracle و seed قطعی). برای ریفکتور رفتار‌حفظ، احیایشان ارزش بالایی دارد ⇒ **آیتم P2**.
> مسیر درستِ تعمیر، fixture/seed است (قطعی‌کردن زمان)، **نه** دست‌زدن به assertها.

### ب) `scripts/run_financial_audit.py` با `HTTPException: 403` می‌شکند
از `routers/attendance.py:_verify_live_course_teacher`. با نسخهٔ اصلیِ پیش از جابه‌جایی هم
reproduce شد ⇒ باگ قدیمیِ خودِ اسکریپت است (فراخوانی مستقیم تابع endpoint بدون authorization
درست). در فاز ۲ تعیین تکلیف می‌شود: تعمیر یا حذف.

### پ) `.dict()` در Pydantic v2 — منبع ۸۶ warning
`routers/teachers.py:86,558` و `routers/students.py:757` ⇒ در فاز ۲ به `model_dump()` مهاجرت
می‌کند (رفتار یکسان، فقط API داخلی Pydantic).

### ت) `models.py:37` — `declarative_base()` از `sqlalchemy.ext.declarative`
`MovedIn20Warning` می‌دهد؛ شکل درست در SQLAlchemy 2.0: `from sqlalchemy.orm import declarative_base`.
در فاز ۲ اصلاح می‌شود (رفتار یکسان).


## دستورهای بازتولید

```bash
python3 -m venv .venv
.venv/bin/pip install -r Kharazmi_Server/requirements.txt -r Kharazmi_Server/requirements-dev.txt

# سوئیت کامل (با DB موقت) + گارد دیتابیس واقعی
DATABASE_URL=sqlite:////tmp/kharazmi.db JWT_SECRET_KEY=dev-secret \
  .venv/bin/python -m pytest Kharazmi_Server/tests -q
md5sum Kharazmi_Server/gaj_db.db   # پیش و پس از اجرا باید یکسان باشد

.venv/bin/ruff check .
.venv/bin/mypy
```
