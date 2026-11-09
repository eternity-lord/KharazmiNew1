# Refactor Phase 3b — بخش دوم: payments و restore (پایانِ P3b)

تاریخ: ۲۰۲۶-۱۱-۰۹ · شاخه: `arena/cdb77c9d-kharazminew1` · نقطهٔ شروع: `6e6147e` (PR #7 = P3b بخش اول)

بخشِ اولِ P3b نُه handler را پوسته کرد. این بخش **باقی‌ماندهٔ فهرستِ هدف** را تمام می‌کند:
سه handlerِ بزرگِ مالی، `restore_deleted_class`، و هلپرهای خصوصی‌شان.

## عددهای این بخش

| مورد | قبل | بعد |
| --- | --- | --- |
| `routers/finance.py` | 2655 خط | **1606** (−1049) |
| `routers/admin.py` | 1914 خط | **1590** (−324) |
| `services/` | 11 ماژول / 2891 خط | **13 ماژول / 4449 خط** |
| handlerِ پوسته‌شده در این بخش | — | **4** (۱۳۰۰ خط بدنه) |
| انتقالِ مستقیم (هلپر/اسکیما/ثابت) | — | **7** (۷۴ خط) |

### جمعِ کلِ P3 (مرحلهٔ ۳ از نقشهٔ راه)

| فایل | پیش از P3a | پس از P3a | پس از P3b (هر دو بخش) |
| --- | --- | --- | --- |
| `routers/admin.py` | 2990 | 2565 | **1590** |
| `routers/finance.py` | 2839 | 2655 | **1606** |
| `routers/attendance.py` | 1582 | 1461 | **1003** |
| `routers/classes.py` | 1539 | 1362 | **946** |
| جمعِ چهار روتر | **8950** | 8043 | **5145** (−3805) |
| `services/` | 0 | 1108 | **4449** |

هیچ‌کدام از این چهار فایل دیگر «ماژول خدا» نیست؛ بزرگ‌ترین‌شان (`finance.py`) ۱۶۰۶ خط است و
تنها سه handlerِ بالای ۱۰۰ خط دارد.

## چه چیزی منتقل شد

| نام | نوع | مبدأ | مقصد | خط |
| --- | --- | --- | --- | --- |
| `payment_callback` (`GET /finance/payment/callback`) | handler (۲ decorator: `router.get` + `limiter.limit`) | finance | `services/payments.py` | 462 |
| `submit_payment` (`POST /finance/pay`) | handler | finance | `services/payments.py` | 335 |
| `refund_transaction` (`POST /finance/transaction/{id}/refund`) | handler | finance | `services/payments.py` | 182 |
| `restore_deleted_class` (`POST /admin/deleted_classes/{id}/restore`) | handler با docstring | admin | `services/class_restore.py` | 321 |
| `_jalali_now_str` | هلپر (۱۲ مصرفِ دیگر در finance) | finance | `services/payments.py` + **بازصادرات** | 5 |
| `_replay_idempotent_payment` | هلپرِ idempotency | finance | `services/payments.py` | 22 |
| `_callback_static_page` | صفحهٔ HTML (+۲ خط کامنتِ چسبیده) | finance | `services/payments.py` | 13 |
| `_callback_refresh_page` | صفحهٔ HTML | finance | `services/payments.py` | 14 |
| `_callback_processing_page` | صفحهٔ HTML | finance | `services/payments.py` | 14 |
| `PAYMENT_GATEWAY_ENABLED` | ثابتِ feature-flag (+۲ خط کامنت) | finance | `services/payments.py` + **بازصادرات** | 1 |
| `ClassRestoreRequest` | اسکیمای Pydantic | admin | **`schemas.py`** + بازصادرات | 5 |

`_replay_idempotent_payment` و سه صفحهٔ کال‌بک بازصادرت **نشدند**: تنها مصرف‌کننده‌شان همان
handlerهایی بودند که منتقل شدند، پس importِ موقتشان را `ruff --select F401 --fix` پاک کرد.

## سه نکتهٔ مهمِ این بخش

### ۱) گیتِ F821 برای دومین بار یک باگِ واقعی گرفت

`PAYMENT_GATEWAY_ENABLED` دو مصرف‌کننده داشت: `payment_callback` (که منتقل شد) و
`mock_payment_page` (که در روتر ماند). شرطِ درایورِ من برای افزودنِ بازصادرت، به‌جای بررسیِ
مصرف‌کننده‌ها، حضورِ *رشتهٔ* نام در فایل را چک می‌کرد و چون دو مصرفِ باقی‌مانده همان رشته را
داشتند، import **هرگز اضافه نشد**. نتیجه:

```
F821 Undefined name `PAYMENT_GATEWAY_ENABLED` --> Kharazmi_Server/routers/finance.py:547
```

`ruff check .` از ۲۵۱ به ۲۵۲ رفت و `--select F821` از ۱ به ۲. هیچ‌کدام از این‌ها توسط
«import main» یا اوراکل OpenAPI گرفته نمی‌شد (مسیر فقط وقتی اجرا می‌شود که فلگ روشن باشد و
`mock_payment_page` صدا زده شود) — یعنی دقیقاً همان کلاسی از باگ که در P3a هم با
`import time as time_module` رخ داد و فقط F821 گرفتش.

**قاعدهٔ قطعی‌شده: بعد از هر جابه‌جایی، `ruff check . --select F821` و مقایسهٔ rule-by-ruleٔ
`--statistics` با بیس‌لاین اجباری است؛ تستِ سبز کافی نیست.** (و برای ثابت‌ها/هلپرها، معیارِ
بازصادرت باید «آیا مصرف‌کننده‌ای در روتر مانده؟» باشد، نه «آیا رشتهٔ نام در فایل هست؟».)

### ۲) ۳۶ خط کامنتِ دوتایی پاک شد (۲۴ خطش از بخشِ اول بود)

قالبِ کامنتِ پوسته، پیشوندِ `    # ` را هم در الگو داشت و هم هنگامِ ساختنِ خطوط ⇒ خطوطِ
ادامه به `#     # …` تبدیل شده بودند. صرفاً ظاهری (کامنت است، نه کد) ولی در PRِ کیفیتِ کد
جای ماندن نداشت؛ با یک جایگزینیِ مکانیکی در هر چهار روتر اصلاح شد.

### ۳) `ClassRestoreRequest` به `schemas.py` رفت

این اسکیمای ۴ فیلدی داخل `routers/admin.py` تعریف شده بود، در حالی که از P2c قرار است
`schemas.py` منبعِ یگانهٔ اسکیم‌ها باشد. چون در **امضای** handler می‌آید، انتقالِ بدنه بدون
انتقالِ اسکیمای ممکن نبود (وگرنه سرویس مجبور می‌شد از روتر import کند = چرخه). نامِ کلاس
همان است، پس `$ref` در OpenAPI عوض نشد — اوراکل این را تأیید کرد (۰ اختلاف). `routers/admin.py`
آن را بازصادرات می‌کند چون امضای پوسته به آن اشاره دارد.

## گیت‌های راستی‌آزمایی

| گیت | نتیجه |
| --- | --- |
| بدنهٔ ۴ handler در برابر `git HEAD` | **بایت‌به‌بایت یکسان ۴/۴** |
| decorator + امضا + docstringِ ۴ پوسته | **بایت‌به‌بایت یکسان ۴/۴** (`payment_callback` هر دو decorator را دارد) |
| forward شدنِ همهٔ پارامترها به‌ترتیب | ۴/۴ |
| ۷ انتقالِ مستقیم (هلپر/اسکیما/ثابت) + کامنت‌های چسبیده | **بایت‌به‌بایت یکسان ۷/۷** |
| resolve شدنِ نام‌های بازصادرت‌شده در روتر مبدأ | `_jalali_now_str`، `PAYMENT_GATEWAY_ENABLED`، `ClassRestoreRequest` ✓ |
| اوراکل OpenAPI در برابر `origin/main` | **۰ اختلاف** (17203 خط) |
| سوئیت ۱ / سوئیت ۲ (پروسسِ جدا) | **1279 passed / 249 passed** |
| گارد md5 دیتابیس واقعی | `gaj_db.db: OK` |
| `ruff check .` | **251** (= بیس‌لاین) |
| `ruff --select F821` | **1** (فقط `routers/exams.py:380` قدیمی) |
| `mypy` | **727** (بدون تغییر) در ۴۳ فایل از ۵۳ ⇒ ۲ ماژول جدید type-clean |
| ledger مسیرها | ۲۲۱ route، **یکسان جز `file:line`** (۶۷ مسیر) |
| `scripts/validate_app_map.py` | `server_map_exact=true`، 0 missing / 0 stale / 0 android-only |
| گاردهای متنِ منبعِ `finance.py` | `from validation import` ✓، `validate_jalali_due_date` ✓، `Field(pattern=` ندارد ✓ |
| importهای حذف‌شده توسط F401 | finance: `IntegrityError`, `case`, `get_payment_gateway`, `os` · admin: `ClassRestoreLog`, `Installment` — **صفر مصرف‌کنندهٔ بیرونی** (برنامهٔ راستی‌آزمایی، همهٔ تست‌ها/اسکریپت‌ها/روترها/`main.py` را گشت) |

## چرا `pay_installment_manually` پوسته نشد

`tests/test_tuition_installments_audit.py:684` نام `ActivityLog` را روی فضای ماژولِ
`routers.finance` مانکی‌پچ می‌کند تا «خطا در آخرین قدمِ نوشتنِ ledger» را بسازد و rollback را
بسنجد. اگر بدنه به لایهٔ سرویس می‌رفت، `ActivityLog` در فضای ماژولِ سرویس resolve می‌شد و patch
**بی‌اثر** می‌گشت ⇒ تست سبزِ کاذب. این تنها `monkeypatch.setattr` روی فضای یک ماژولِ روتر در
کلِ دو سوئیت است و در `services/__init__.py` هم مستند شده.

## چه چیزی باقی مانده

| مورد | وضعیت |
| --- | --- |
| handlerهای ≥۱۰۰ خط | `pay_installment_manually` 147 (عمداً دست‌نخورده)، `search_finance_advanced` 114، `get_student_financial_dashboard` 110، `get_class_students_full` 107، `get_deleted_classes` 106، `get_class_students_excel` 106 — هیچ‌کدام «ماژول خدا» نمی‌سازند؛ انتهای P3b |
| لایهٔ **repository** | ساخته **نشد**. کوئری‌ها (`db.query(...)`) در لایهٔ سرویس‌اند. جداکردنِ واقعیِ data-access یعنی *بازنویسی* کوئری‌ها، که با قیدِ «رفتارمحافظ / بایت‌به‌بایت» سازگار نیست؛ باید تصمیمِ جداگانهٔ کاربر باشد |
| `_jalali_now_str` تکراری | `routers/dunning.py:39` نسخهٔ مستقلِ خودش را دارد (و `routers/audit.py:82` هم `_now_str`). نامزدِ de-duplication در یک فازِ جدا |
| `routers/finance.py:2493` | هنوز `from routers.dunning import _get_admin_username, _jalali_now_str` (lazy، داخل تابع) — تنها وابستگیِ باقی‌ماندهٔ روتر→روتر در این فایل |
| P4 | اپِ Android/Kotlin: `StudentProfileActivity` 1264، `InvoiceActivity` 1248، `AttendanceActivity` 1012، `ClassDetailActivity` 948 خط |
| P5 | گیتِ lint/type در CI (فعلاً ruff/mypy فقط گزارش‌اند، چون بیس‌لاین ۲۵۱/۷۲۷ خطا دارد) |

## بازتولیدِ راستی‌آزمایی

```bash
cd /home/user/KharazmiNew1
# اوراکل OpenAPI (درختِ کاری تمیز روی origin/main است، پس before = HEAD)
DATABASE_URL=sqlite:////tmp/oa0.db JWT_SECRET_KEY=ci-only .venv/bin/python /tmp/dump_openapi.py > /tmp/openapi_before.json
# ...بعد از تغییرات...
DATABASE_URL=sqlite:////tmp/oa1.db JWT_SECRET_KEY=ci-only .venv/bin/python /tmp/dump_openapi.py > /tmp/openapi_after.json
diff /tmp/openapi_before.json /tmp/openapi_after.json           # باید خالی باشد
# دو سوئیت (پروسسِ جدا) + گارد md5 + lint/type
DATABASE_URL=sqlite:////tmp/x1.db JWT_SECRET_KEY=test-secret-not-production \
  .venv/bin/python -m pytest Kharazmi_Server/tests -q -p no:randomly      # 1279 passed
DATABASE_URL=sqlite:////tmp/x2.db JWT_SECRET_KEY=test-secret-not-production \
  .venv/bin/python -m pytest tests/route_audit -q -p no:randomly          # 249 passed
md5sum -c /tmp/db_p3b2.txt                                                # gaj_db.db: OK
.venv/bin/ruff check .                                                    # Found 251 errors
.venv/bin/ruff check . --select F821                                      # فقط exams.py:380
.venv/bin/mypy                                                            # 727 errors in 43 files (checked 53)
# ledger
DATABASE_URL=sqlite:////tmp/rl.db JWT_SECRET_KEY=ci-only .venv/bin/python \
  Kharazmi_Server/scripts/extract_server_routes.py --output docs/app-map/server-routes-extracted.csv
DATABASE_URL=sqlite:////tmp/vam.db JWT_SECRET_KEY=ci-only .venv/bin/python scripts/validate_app_map.py
```
