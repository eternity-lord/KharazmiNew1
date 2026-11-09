# ۲۰۲۶-۱۱-۰۹ — ریفکتور فاز ۲c: کد مرده، سایه‌زدایی schemaها، و دامِ fixture در pytest

## خلاصهٔ عددی

| سنجه | آغاز فاز ۲c | پایان فاز ۲c |
| --- | --- | --- |
| یافته‌های ruff | 1157 | **251** |
| خطاهای mypy | 750 | **727** |
| کلاس schema تکراری در روترها | ۲۳ | **۰** |
| تست‌های سوئیت اصلی | 1279 passed | **1279 passed** |
| تست‌های route-audit | 249 passed | **249 passed** |
| سطح API (OpenAPI) | — | **بایت‌به‌بایت یکسان** (۱۷۲۰۳ خط، diff = ۰) |
| `gaj_db.db` | — | md5 دست‌نخورده |

## ۱) حذف ۶۱۷ import مرده + مرتب‌سازی ۱۶۴ بلوک import

`ruff --select F401,I001 --fix`. پیش از اعمال، سطح API از `origin/main` دست‌نخورده
(داخل worktree) استخراج و با بعد از آن مقایسه شد: **`openapi.json` بایت‌به‌بایت یکسان**.

### دامی که باز شد و تور ایمنی گرفتش 🎯
نخستین اجرا ۲۶ تست را **error** داد:

```
E  fixture 'ledger' not found
```

ریشه: الگوی استاندارد pytest این است که fixture از ماژولِ تستِ دیگری import شود
(`from test_priority2_financial import ledger`) و فقط به‌شکلِ **نامِ پارامترِ تابع تست**
مصرف شود. از دیدِ پایتون (و ruff) آن import «بی‌استفاده» است، ولی حذفش یعنی fixture از
namespace ماژول بیرون می‌رود و pytest دیگر پیدایش نمی‌کند.

اقدام:
1. تست‌ها به HEAD برگردانده شدند (nothing lost).
2. یک ممیزیِ خودکار نوشته شد: همهٔ نام‌های F401‌خورده در تست‌ها با «نام پارامترهای همان
   فایل» مقایسه شد ⇒ تنها **۲** مورد fixture-like پیدا شد.
3. روی همان یک موردِ واقعی `# noqa: F401` با دلیلِ فارسی گذاشته شد
   (`test_priority3_integrity.py:9`) و بقیه حذف شدند.
4. ممیزیِ دوم (محکم‌کاری): بعد از اعمال، هر importِ حذف‌شده با `@pytest.fixture`های
   ماژولِ مقصد و `conftest.py` مقایسه شد ⇒ **۰ fixture حذف‌شده**.
5. آن `noqa` هم باعث شد `F811` هجده‌بار روی همان فایل گزارش شود (پارامتر، نامِ import
   را در دامنهٔ تابع سایه می‌زند — بخشی از همان الگو) ⇒ `per-file-ignores` برای
   **همان یک فایل** با دلیل مستند.

> یک موردِ false-positive هم توسط ممیزی گرفته شد: `import models` داخل یک تابع در
> `tests/route_audit/test_audit_messages.py` که واقعاً مرده بود (نام `models` پارامترِ
> تابعِ **کمکیِ دیگری** در همان فایل است) ⇒ به‌جای noqa، حذف شد.

## ۲) سایه‌زدایی: ۲۳ کلاس schema تکراری در روترها ← ۰

مهم‌ترین یافتهٔ این فاز. پنج روتر، کلاس‌هایی هم‌نام با `schemas.py` را **دوباره به‌صورت
محلی** تعریف کرده بودند؛ تعریف محلی، import را سایه می‌زد (همان `F811`ها). یعنی
`from schemas import StudentCreate` در `auth.py` عملاً مرده بود و هر routeای که آن نام را
بخواهد، نسخهٔ محلیِ **متفاوت** را برمی‌داشت.

تحلیل با AST روی هر ۲۳ کلاس (مقایسهٔ bases + بدنه با نسخهٔ canonical، و شمارشِ
مصرف‌کننده‌ها میان همهٔ توابعِ دکوریت‌شده با `router.*`):

| دسته | تعداد | اقدام |
| --- | --- | --- |
| مرده — هیچ route یا کلاس دیگری مصرفش نمی‌کرد | ۱۷ | حذف |
| مردهٔ آبشاری — فقط توسط همان کلاس‌های مرده مصرف می‌شدند | ۴ (`AttendanceItem`, `TeacherProfileInfo`, `TeacherInfo`, `StudentProfileInfo`) | حذف |
| زنده ولی **بایت‌به‌بایت یکسان** با canonical | ۲ (`PersonListItem` در `admin.py` = `response_model` دو route جستجو، `PrintReceiptRequest` در `finance.py` = دو route چاپ رسید) | حذف کلاس محلی، استفاده از import |
| زنده و متفاوت | **۰** | — |

پس **هیچ routeای نسخهٔ متفاوتی را از دست نداد** — و این دقیقاً همان چیزی است که
`openapi.json` یکسان و هر دو سوئیت سبز تأییدش کردند.

### چرا این finding مهم است (تلهٔ اعتبارسنجی که خنثی شد)
نسخه‌های محلیِ مرده، ضعیف‌تر از canonical بودند. اگر روزی کسی آن‌ها را به routeای وصل
می‌کرد (یا به‌جای canonical وارد می‌کرد)، این اعتبارسنجی‌ها **بی‌صدا غیب می‌شدند**:

| کلاس محلیِ مرده | چه چیزی نداشت |
| --- | --- |
| `auth.py: StudentCreate` / `TeacherCreate` | base `NationalCodeRequest` (اعتبارسنجی کد ملی) + `branch_id` |
| `auth.py: GradeCreate` | `score: Field(ge=0, allow_inf_nan=False)`, `max_score: Field(gt=0)`, و `@model_validator` «نمره نمی‌تواند بیشتر از نمرهٔ کل باشد» |
| `auth.py: EnrollmentCreate` | `@field_validator('total_tuition')` (ردِ bool/رشته/منفی)، `installments` |
| `auth.py: CourseCreate` | `teacher_session_price: Field(ge=0)`, `capacity: Field(gt=0)` |
| `auth.py: FullStudentProfile` | `enrollments`, `wallet_total`, `wallet_teacher` |
| `admin.py: AttendanceItem` | فیلد `excused` و `@field_validator('status')` (وضعیت حضور و غیاب) |
| `admin.py: AttendanceSubmitData` | `items: Field(min_length=1)` ⇒ لیست خالی قبول می‌شد |
| `finance.py: TransactionTestData` | `amount: Field(gt=0)` |

حالا تک‌منبعِ حقیقت همان `schemas.py` است و این تله دیگر وجود ندارد.

## ۳) `F811`های باقی‌مانده: ۶ import دوباره در میانهٔ فایل

`import json` در `dependencies.py:1092`، `import io` در `admin.py:820`،
`from sqlalchemy import or_` در `admin.py:911`، `import models` در `finance.py:783`،
`import uuid` در `teachers.py:636` و `Course` در importِ محلیِ `main.py:642` — همگی
نام‌هایی بودند که در سطح ماژول از قبل import شده بودند. حذف‌شان رفتار را عوض نمی‌کند
(همان آبجکت، همان binding) و الگوی «import پراکنده در میانهٔ فایل» را کم می‌کند.

## ۴) `B023`: closure روی متغیر حلقه در `routers/admin.py`

`_same_transaction_value(field)` **داخل** حلقهٔ `for expected in transaction_rows` تعریف
می‌شد و `current`/`expected` را late-bind می‌کرد. چون بی‌درنگ در همان تکرار مصرف می‌شد
باگِ عملی نداشت، ولی تلهٔ کلاسیک closure-over-loop-variable بود (و هر تکرار یک تابع
تازه می‌ساخت). حالا یک بار بیرون حلقه تعریف می‌شود و مقادیر را صریح می‌گیرد
(`_same_transaction_value(field, current, expected)`) ⇒ رفتار یکسان، تله حذف.

## ۵) چهار تابع تست تکراری — یکی‌شان پوششِ واقعی را برگرداند

در `tests/test_roles_installment_notifications_audit.py` چهار نام تست **دو بار** تعریف
شده بود. در پایتون تعریف دوم جای اولی را می‌گیرد ⇒ آن چهار تست هیچ‌وقت اجرا نمی‌شدند.

| تست | دو کپی | اقدام |
| --- | --- | --- |
| `test_role_09b_student_and_parent_cannot_search_all_people` | یکسان | کپیِ مرده حذف شد |
| `test_role_07_parent_reads_only_own_child` | یکسان | کپیِ مرده حذف شد |
| `test_role_08_parent_cannot_read_other_child_by_id_swap` | یکسان | کپیِ مرده حذف شد |
| `test_role_09_student_reads_only_self` | **متفاوت** | کپیِ ضعیف‌تر (که اجرا می‌شد) حذف شد تا نسخهٔ قوی‌تر زنده شود |

کپیِ قوی‌ترِ `test_role_09` چیزی است که کپیِ ضعیف‌تر نداشت: بررسی محتوای پاسخ
(فقط «کلاس الف» خودش، نه «کلاس ب» دانش‌آموز دیگر)، **بررسی IDOR**
(`/students/my_profile?student_id=102` نباید دامنه را عوض کند) و کنترل route shadowing.
اجرا شد و **پاس** داد ⇒ پوشش واقعیِ امنیتیِ این سناریو از هیچ به هست رسید، بدون اینکه
تستی ضعیف شود. (شمار تست‌های فایل همان ۳۶ ماند.)

## ۶) `E711` هم مثل `E712` خاموش شد — با دلیل

هر ۱۸ موردِ `E711` در کد، مقایسهٔ `== None` / `!= None` روی **ستونِ SQLAlchemy** بود
(`Student.branch_id == None` ⇒ `IS NULL` در SQL). پیشنهاد راف (`is None`) یک بولینِ
پایتون می‌سازد و کوئری را می‌شکند ⇒ قاعده در `pyproject.toml` با دلیل خاموش شد
(دقیقاً هم‌خانوادهٔ `E712` که در فاز ۱ خاموش شده بود).

## ۷) بازتولید artefact مشتق‌شده

`docs/app-map/server-routes-extracted.csv` (خروجی خام `extract_server_routes.py`) کهنه بود
— شمارهٔ خط‌هایش حتی با `origin/main` دست‌نخورده هم نمی‌خواند. بازتولید شد:

```
ledger identical apart from file:line → True
routes whose source line moved: 218 / 221     non-line differences: 0
```

و اعتبارسنجِ خودِ ریپو هم تأیید کرد:

```
scripts/validate_app_map.py → server_map_exact: true, server_runtime_count: 221,
                              server_map_missing: [], server_map_stale: [],
                              android_only_routes: 0
```

`docs/app-map/server-routes.csv` (نقشهٔ دستی و **oracle تست‌های route-audit**) دست‌نخورده
ماند: هیچ routeای تغییر نکرده، و ستون `file:line` آن سندِ تاریخیِ مرحلهٔ A است.

## ۸) چه چیزهایی عمداً باقی ماند (و چرا)

| قاعده | تعداد | چرا حالا نه |
| --- | --- | --- |
| `B905` (zip بدون strict) | ۲۷ | افزودن `strict=True` **تغییر رفتار** است (raise روی طول نابرابر) ⇒ باید موردی و با استدلال انجام شود، نه فله‌ای |
| `F841` (متغیر بی‌استفاده) | ۳۱ | اگر سمتِ راستِ انتساب side-effect داشته باشد (مثل `result = db.commit()`)، «اصلاح» خودکار رفتار را عوض می‌کند ⇒ بازبینی دستی در P3 |
| `E701`/`E702` (چند عبارت در یک خط) | ۸۰ | صرفاً قالب‌بندی؛ اصلاحش unsafe است و چند تست ساختاری **متنِ** روترها را می‌خوانند ⇒ با احتیاط و در P3 |
| `C408`, `UP031`, `RUF015`, `SIM*`, `E722`, `B007` | ~۶۰ | یا unsafe-fix یا نیازمند تصمیم رفتاری (مثلاً `except:` → `except Exception:` رفتار را برای `KeyboardInterrupt`/`SystemExit` عوض می‌کند) |

`mypy` هم از ۷۵۰ به ۷۲۷ رسید (اثرِ حذف کد مرده و مدرن‌شدن annotationها)؛ سفت‌کردنِ
تدریجی‌اش کارِ P3 است، هم‌زمان با شکستن ماژول‌های غول‌پیکر.

## دستورهای بازتولیدِ راستی‌آزمایی

```bash
# ۱) سطح API باید بایت‌به‌بایت یکسان بماند
DATABASE_URL=sqlite:////tmp/oa.db JWT_SECRET_KEY=x python /tmp/dump_openapi.py > /tmp/after.json
diff /tmp/before.json /tmp/after.json            # ← باید خالی باشد

# ۲) هر دو سوئیت (در دو فرایند جدا)
DATABASE_URL=sqlite:////tmp/a.db JWT_SECRET_KEY=x pytest Kharazmi_Server/tests -q
DATABASE_URL=sqlite:////tmp/b.db JWT_SECRET_KEY=x pytest tests/route_audit -q

# ۳) نقشهٔ route و گارد دیتابیس واقعی
python scripts/validate_app_map.py
md5sum Kharazmi_Server/gaj_db.db
```
