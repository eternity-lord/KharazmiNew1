# ۲۰۲۶-۱۱-۰۹ — احیای سوئیت `tests/route_audit` (پوسیدگی زمانیِ seed)

## خلاصهٔ یک‌خطی

`tests/route_audit` — ۲۴۹ تستِ route-level با oracle و seed قطعی — از **۱۶۷ قرمز / ۸۲ سبز**
به **۲۴۹ سبز / ۰ قرمز** رسید، بدون هیچ تغییری در کد برنامه و بدون دست‌زدن به یک assert.

## نشانه

اجرای سوئیت (بیرون از `testpaths` فایل `pytest.ini` و بیرون از CI، پس سال‌ها دیده نمی‌شد):

```
tests/route_audit → 167 failed, 82 passed
```

تقریباً همهٔ شکست‌ها یک شکل داشتند:

```
AssertionError: {"detail":"نشست نامعتبر یا منقضی شده است"}
assert 401 == 200
```

و در خروجی setup این خط دیده می‌شد:

```
🧹 Auto-cleanup: Removed 5 expired user sessions.
```

همین عدد ۵ سرنخ اصلی بود: seed دقیقاً **۵ سشن** می‌سازد (admin, secretary, teacher,
student, parent) ⇒ پس هر ۵ سشن احراز هویت حذف شده‌اند.

## ریشهٔ مشکل (با قطعیت)

سه واقعیت که کنار هم قرار گرفتند:

1. `tests/route_audit/seed.py` همهٔ رکوردها را با تاریخ ثابت
   `FIXED_NOW = 2026-09-28 09:00` می‌سازد (تا fixture بایت‌به‌بایت بازتولیدپذیر باشد)،
   از جمله `UserSession.created_at`.
2. `main.py` در **انتهای ماژول** (خط ۵۷۴) `auto_patch_database()` را صدا می‌زند — یعنی
   در لحظهٔ `import main`، نه در یک startup event. آن بلوک این را اجرا می‌کند:
   `expiry_limit = datetime.datetime.utcnow() - timedelta(days=30)` و سشن‌های قدیمی‌تر را
   **حذف** می‌کند (`SESSION_EXPIRY_DAYS = 30` در `dependencies.py`).
3. `clock.freeze_loaded_server_modules()` فقط ماژول‌های **از قبل import‌شده** را پچ می‌کند،
   و در fixture ترتیب این است: `audit_app` (یعنی `import main`) ← `frozen_server_clock`.
   ⇒ فریزِ ساعت **هرگز** به پاک‌سازیِ زمانِ import نمی‌رسد؛ آن با ساعت واقعی اجرا می‌شود.

نتیجهٔ زمانی: تا **۲۰۲۶-۱۰-۲۸** (سی روز پس از تاریخ seed) فاصلهٔ «اکنونِ واقعی» تا
`FIXED_NOW` زیر ۳۰ روز بود و پاک‌سازی چیزی حذف نمی‌کرد؛ از فردای آن روز، سوئیت **خودبه‌خود**
و بدون هیچ تغییر کدی قرمز شد. snapshot این ریپو مال ۲۰۲۶-۱۰-۰۷ است، یعنی هنگام بسته‌شدن
سبز بوده — یک «تستِ سبزِ مشروط به پنجرهٔ زمانی».

> توکن‌های seed مشکل نداشتند: `_stable_jwt()` عمداً `exp = issued + 10 سال` می‌گذارد
> («remains valid independently of wall time»). تنها چیزی که می‌شکست، **ردیفِ سشن** بود
> که پیش از رسیدنِ درخواست حذف شده بود.

## راه‌حلی که امتحان و رد شد (مهم برای آینده)

نخستین ایده: در fixture، ساعتِ stdlib را برای پنجرهٔ کوتاهِ import فریز کنیم
(`datetime.datetime = FrozenDateTime` تا `import main` با `FIXED_NOW` پاک‌سازی کند).
نتیجه: ۴۰۱ها رفتند (۱۶۷ ← ۵۳ قرمز) ولی **۴۰ خطای جدید** ساخته شد:

```
sqlalchemy.exc.StatementError: (builtins.TypeError) SQLite DateTime type only
accepts Python datetime and date objects as input.
```

علت: `bind_processor` نوع `DATETIME` در دیالکت SQLite، کلاس `datetime.datetime` را
**در نخستین اجرا cache می‌کند**. آن نخستین اجرا دقیقاً داخل همان پنجرهٔ فریز رخ می‌دهد
(اولین UPDATE در `auto_patch_database`) ⇒ کلاسِ cache‌شده `FrozenDateTime` می‌شود و پس از
پایان پنجره، هر مقدارِ datetime **واقعی** (مثل همان `2026-09-28 09:00` که seed ساخته)
در `isinstance(value, FrozenDateTime)` رد می‌شود. یعنی دست‌کاری سراسری ساعتِ stdlib،
لایهٔ ORM را مسموم می‌کند. ⇒ این مسیر بازگشت داده شد (`git checkout`).

**درس ثبت‌شده:** در این ریپو ساعت را فقط در سطح «ماژولِ سرور» فریز کنید
(همان کاری که `freeze_loaded_server_modules` می‌کند)، هرگز در سطح `datetime` خودِ stdlib.

## راه‌حل پذیرفته‌شده

به‌جای جنگیدن با ساعت، **همان ردیف‌هایی که پاک‌سازی برده است برگردانده می‌شوند** — با همان
توکن قطعیِ manifest و همان `created_at = FIXED_NOW`:

```python
# tests/route_audit/seed.py
def restore_role_sessions(manifest) -> int:
    """idempotent: سشنی که توکنش هست دوباره ساخته نمی‌شود."""
```

- `user_id` و `sub_role` از payload خودِ JWT خوانده می‌شوند (نه از حدسِ نام نقش)، و
  `teacher_id=1 if sub_role == "teacher" else None` دقیقاً همان قاعدهٔ seed است.
- چون idempotent است، اگر روزی پاک‌سازیِ زمانِ import چیزی حذف نکند، تابع هیچ کاری نمی‌کند.
- `now = FIXED_NOW` در `seed_database` هم جای `dt.datetime(2026, 9, 28, 9, 0, 0)`
  hardcoded را گرفت ⇒ «اکنونِ» سوئیت فقط یک منبع حقیقت دارد (`clock.FIXED_NOW`).

فراخوانی‌ها:

| فایل | محل |
| --- | --- |
| `tests/route_audit/conftest.py` | fixture `audit_app`، بلافاصله پس از `import main` |
| `sweep/run_sweep.py` · `run_contract.py` · `run_boundary.py` · `run_large.py` | پس از `import main` و **پیش از** `baseline = db_path.read_bytes()` تا snapshotِ بازگردانیِ routeها هم سشن‌ها را داشته باشد |

`main.py` و `dependencies.py` **دست‌نخورده** ماندند: پاک‌سازی سشن منقضی در پروداکشن یک
رفتار درست و مطلوب است؛ مشکل از fixture بود که تاریخِ گذشتهٔ ثابت می‌سازد.

## راستی‌آزمایی

```
tests/route_audit        → 249 passed, 4 warnings in 26.17s   (پیش از تعمیر: 167 failed / 82 passed)
Kharazmi_Server/tests    → 1279 passed                        (بدون تغییر)
md5 Kharazmi_Server/gaj_db.db → پیش و پس از اجرا یکسان
```

آن ۱۳ شکستِ باقی‌ماندهٔ میانی (مثل `assert 11.5 == 18.5` یا `UNIQUE constraint failed:
session_logs.course_id, session_logs.date`) همگی **بالادستیِ همان ۴۰۱** بودند: وقتی
احراز هویت شکست می‌خورد، دادهٔ نیمه‌کارده در fixture می‌ماند و تستِ بعدی روی آن
می‌لغزد. با رفع ۴۰۱، همهٔ آن‌ها هم سبز شدند ⇒ هیچ assertی تضعیف یا حذف نشد.

## پیامد برای CI و بقیهٔ ریفکتور

- این ۲۴۹ تست حالا به تور ایمنیِ ریفکتور اضافه شدند (job جدا در
  `.github/workflows/tests.yml`).
- **چرا job جدا و نه یک اجرای pytest؟** چون دو سوئیت در یک فرایند همدیگر را خراب می‌کنند؛
  این ادعا اندازه‌گیری شد، نه حدس:

  ```
  pytest Kharazmi_Server/tests tests/route_audit     # یک فرایند
  → 1326 passed, 202 errors
     هر ۲۰۲ خطا یک شکل: sqlite3.IntegrityError: UNIQUE constraint failed: branches.id
  ```

  مکانیسم: `models.py` در **اولین import** خودش `engine`/`SessionLocal` را از
  `DATABASE_URL` می‌سازد و آن ماژول در `sys.modules` کش می‌شود. وقتی بعداً conftestِ
  route_audit مقدار `DATABASE_URL` را به فایلِ temp خودش تغییر می‌دهد و `seed_database()`
  را صدا می‌کند، seed روی همان engineِ **قدیمی** می‌نویسد — یعنی روی دیتابیسی که سوئیت اول
  پُر کرده ⇒ `branches.id = 1` با UNIQUE collision می‌شکند و کل fixtureها error می‌دهند.
  پس تفکیک فرایند (و job جدا در CI) **عمدی** است و باید بماند؛ این همان دلیلی است که
  `pytest.ini` فقط `Kharazmi_Server/tests` را در `testpaths` دارد.
- `scripts/seed_demo.py` (CLI عمومیِ seed) از `seed_database` استفاده می‌کند و رفتارِ
  پیش‌فرضش تغییر نکرد؛ `restore_role_sessions` فقط توسط fixtureها/runnerها صدا زده می‌شود.
