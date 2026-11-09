# Refactor Phase 3b — بدنهٔ handlerها به لایهٔ سرویس (پوستهٔ HTTP)

تاریخ: ۲۰۲۶-۱۱-۰۹ · شاخه: `arena/69c814fd-kharazminew1` · نقطهٔ شروع: `5a7484b` (بعد از P3a)

P3a آجرهای **مشترک** را از روترها بیرون کشید. P3b یک قدم جلوتر می‌رود و **بدنهٔ خودِ
handlerها** را به `services/` می‌برد؛ روتر فقط «پوستهٔ HTTP» نگه می‌دارد: decorator + امضا +
docstring + یک `return` که آرگومان‌ها را به تابع سرویس می‌دهد.

## عدد‌های این فاز

| مورد | قبل | بعد |
| --- | --- | --- |
| `routers/admin.py` | 2565 خط | **1914** (−651) |
| `routers/attendance.py` | 1461 خط | **1003** (−458) |
| `routers/classes.py` | 1362 خط | **946** (−416) |
| جمعِ سه روتر | 5388 | **3863** (−1525) |
| `services/` | 6 ماژول / 1108 خط | **11 ماژول / 2891 خط** |
| handlerِ پوسته‌شده | 0 | **9** (+۱ هلپر خالص منتقل شد) |
| خطِ بدنهٔ منتقل‌شده | — | **1542** (+20 هلپر) |

`routers/finance.py` (2655 خط) در این batch دست‌نخورده ماند — دلیلش در «باقی‌ماندهٔ P3b» آمده.

## چه چیزی منتقل شد

| handler (روت) | روتر | ماژول سرویس | خط بدنه |
| --- | --- | --- | --- |
| `submit_session_and_calculate` (`POST /attendance/submit_session`) | attendance | `session_submission.py` | 243 |
| `edit_past_session` (`PUT /attendance/session/{session_code}`) | attendance | `session_submission.py` | 228 |
| `get_student_full_profile` (`GET /admin/students/{id}/full_profile`) | admin | `student_profile.py` | 179 |
| `delete_transaction` (`DELETE /admin/transactions/{id}`) | admin | `transaction_admin.py` | 149 |
| `update_transaction` (`PUT /admin/transactions/{id}`) | admin | `transaction_admin.py` | 168 |
| `test_transaction_logic` (`POST /test/transaction_logic`) | admin | `transaction_admin.py` | 152 |
| `get_all_classes` (`GET /classes/list`) | classes | `class_reports.py` | 146 |
| `get_class_full_report` (`GET /classes/{id}/full_report`) | classes | `class_reports.py` | 152 |
| `add_enrollment` (`POST /enrollments/add`) | classes | `enrollment.py` | 125 |
| `_split_amount_integer` (هلپر خالص، بدون route) | admin | `transaction_admin.py` | 20 |

## چرا handler در روتر *می‌ماند* و فقط واگذار می‌کند

۱. **امضا قرارداد OpenAPI است.** annotationها + `Depends`/`Header` همان چیزی است که FastAPI
   از آن schema می‌سازد. پوسته‌ها امضای قبلی را **کپیِ بایت‌به‌بایت** نگه داشته‌اند، برای همین
   خروجی OpenAPI بدون یک خط اختلاف مانده.

۲. **این توابع قراردادِ فرا-HTTP دارند.** نمونه‌های واقعی از خودِ ریپو:

   * `tests/test_priority2_financial.py:278` → `admin.delete_transaction(transaction.id, db=ledger.db, _="admin")`
     (آرگومان **پوزیشنال**)
   * `tests/test_branch_resolution.py:21` → `from routers.classes import add_enrollment, create_class`
   * `tests/test_admin.py:16` / `test_classes.py` / `test_per_class_debt_isolation.py` → import مستقیم
     `get_student_full_profile`، `get_all_classes`، `get_class_full_report`
   * `scripts/run_financial_audit.py:111,121` → `from routers.attendance import submit_session_and_calculate`
     و فراخوانی `(data_s1, db, "admin")`
   * `finalize_live_session` (کلاس زنده) → `submit_session_and_calculate(data=data, db=db, _system_caller="live_system")`

   اگر تابع سرویس جای handler در route ثبت می‌شد، همهٔ این مسیرها می‌شکستند.

۳. **docstring بخشی از پاسخ مستندات است.** FastAPI docstring را به‌عنوان `description` در
   OpenAPI منتشر می‌کند؛ برای همین docstring در پوسته می‌ماند و به سرویس منتقل نمی‌شود
   (`restore_deleted_class` در batch بعدی همین حالت را دارد).

شکلِ نتیجه (نمونهٔ واقعی از `routers/attendance.py`):

```python
@router.post("/attendance/submit_session")
def submit_session_and_calculate(
    data: AttendanceSubmitData, db: Session = Depends(get_db), authorization: str | None = Header(None),
    sub_role: str = Depends(check_user_login), _system_caller: str | None = None
):
    # REFAC(P3b): بدنهٔ ۲۴۳ خطیِ دامنه ... به services/session_submission.py رفت.
    return session_submission.submit_session_and_calculate(
        data, db, authorization, sub_role, _system_caller
    )
```

## گیت‌های راستی‌آزمایی (همه اجرا شدند)

| گیت | نتیجه |
| --- | --- |
| مقایسهٔ **بایت‌به‌بایت** بدنهٔ هر ۹ تابع با `git HEAD` | ۹/۹ یکسان |
| مقایسهٔ decorator + امضا + docstring هر ۹ پوسته با `HEAD` | ۹/۹ یکسان |
| بررسیِ forward شدنِ **همهٔ** پارامترها به‌ترتیب در هر پوسته | ۹/۹ کامل |
| `inspect.signature` پوسته در برابر تابع سرویس | یکسان؛ هر سه سبک فراخوانی (پوزیشنال/کلیدواژه‌ای/HTTP) bind می‌شود |
| اوراکل OpenAPI (`/tmp/dump_openapi.py` در worktreeِ `origin/main` در برابر ریپو) | **۰ اختلاف** (17203 خط) |
| سوئیت ۱: `Kharazmi_Server/tests` | **1279 passed** |
| سوئیت ۲: `tests/route_audit` (پروسسِ جدا) | **249 passed** |
| گارد md5 دیتابیس واقعی institute | `gaj_db.db: OK` |
| `ruff check .` | **251** (= بیس‌لاین؛ صفر یافتهٔ جدید) |
| `ruff check . --select F821` | **1** — همان موردِ قدیمی `routers/exams.py:380` (`'x' in locals()`) |
| `mypy` | **727 خطا** (بدون تغییر) در ۴۲ فایل از ۵۱ فایلِ بررسی‌شده → ۵ ماژولِ جدید **صفر** خطای تایپ دارند |
| ledger مسیرها (`server-routes-extracted.csv`) | ۲۲۱ route؛ **یکسان جز `file:line`** (۷۷ مسیر فقط شمارهٔ خطشان جابه‌جا شد) |
| `scripts/validate_app_map.py` | `server_map_exact=true`، 221 runtime، 0 missing، 0 stale، 0 android-only |

### importهایی که ruff حذف کرد و راستی‌آزمایی شدند

`F401 --fix` بعد از انتقال، ۲۵ importِ بلااستفاده را از سه روتر حذف کرد. چون در P2c یک بار
`F401` یک fixture تست را حذف کرده بود، این‌بار **تک‌تکِ نام‌های حذف‌شده** در برابر کلِ
مصرف‌کننده‌ها (تست‌ها، `tests/route_audit`، اسکریپت‌ها، `main.py` و بقیهٔ روترها) چک شد که
کسی آن‌ها را از فضای روتر import نمی‌کند:

* `admin.py`: `calculate_enrollment_debt_breakdown`, `case`, `check_student_access`, `session_fields_for_client`
* `attendance.py`: `Transaction`, `compute_session_shares`, `validate_session_item_statuses`, `validate_session_items_membership`
* `classes.py`: `ClassReportInfo`, `ClassSessionHistory`, `ClassSessionStudent`, `ClassStudentData`,
  `FullClassReport`, `Installment`, `Transaction`, `normalize_installments`, `or_`, `resolve_session_teacher`

نتیجه: صفر مصرف‌کنندهٔ بیرونی → حذف امن. (`F821` هم همین را مستقل تأیید می‌کند.)

## دو تغییر غیر از «جابه‌جایی کد»

### ۱) `extract_server_routes.py` یاد گرفت پوسته را دنبال کند

ledger مسیرها یک استخراجِ **ایستای عمیق** است: از منبعِ هر endpoint کلیدهای پاسخ،
خواندن/نوشتن‌های ORM، ستون‌ها و side-effectها را بیرون می‌کشد. وقتی handler پوسته شد، آن
ستون‌ها برای ۹ مسیر `نامشخص` شدند — یعنی ledger اطلاعاتش را از دست می‌داد.

راه‌حل: تابع `_service_body_source()` اضافه شد. **فقط** وقتی بدنهٔ تابع (بدون docstring)
دقیقاً یک `return <ماژول>.<همان نام تابع>(...)` باشد و `<ماژول>` در فضای روتر یک ماژولِ
واقعی باشد، تحلیل روی تابعِ سرویس انجام می‌شود. ستون‌های `handler` و `file:line` عمداً به
روتر اشاره می‌کنند چون route همان‌جا ثبت شده است. نتیجه: ledger دقیقاً به اطلاعاتِ قبلی
برگشت (فقط شمارهٔ خط‌ها جابه‌جا شد).

### ۲) یک گاردِ «متنِ منبع» در تست، مسیرِ فایل را دنبالِ کد به‌روز کرد

`tests/test_android_resources_static.py:707` روی **متنِ** `routers/classes.py` دو لیترال را
چک می‌کند:

```python
routines = _read(os.path.join(SERVER_DIR, "routers", "classes.py"))
self.assertIn("PERSIAN_DAY_NAMES", routines, "روزِ هفته باید از تقویمِ مرکزیِ سرور بیاید")
self.assertIn("display_name(", routines, "نامِ حاضر/غایب باید از هلپرِ امنِ نام بیاید")
```

`PERSIAN_DAY_NAMES` یک importِ تنبل **داخل بدنهٔ** `get_class_full_report` بود که عیناً به
`services/class_reports.py` رفت، پس این گارد شکست. سه گزینه بود:

| گزینه | قضاوت |
| --- | --- |
| import مرده + `# noqa: F401` در روتر | رد — بدهی lint و یک وابستگیِ دروغین در کد production (دقیقاً چیزی که P3 می‌خواهد حذف کند) |
| منتقل نکردنِ `get_class_full_report` | رد — ۱۵۳ خط بدنهٔ دامنه در روتر می‌ماند بدون هیچ دلیلِ رفتاری |
| **گارد همان دو لیترال را روی مجموعِ روتر + ماژول سرویس بسنجد** | **پذیرفته شد** |

این **تنها** تغییرِ تست در کلِ P3b است: لیترال‌های موردِ ادعا دست‌نخورده‌اند و گارد
سخت‌گیرانه‌تر هم شده، چون حالا لایهٔ سرویس را هم پوشش می‌دهد.

درس: اسکنِ گاردها باید همهٔ الگوهای خواندنِ فایل را ببیند. اسکنِ اولِ من فقط `_server_file("routers", …)`
را گرفت و `_read(os.path.join(SERVER_DIR, "routers", …))` را از دست داد؛ فهرستِ نهاییِ
گاردها (پایین) با اسکنِ دوم به‌دست آمد.

## فهرستِ کاملِ گاردهای «متنِ منبع» روی فایل‌های پایتونِ سرور

این‌ها تست‌هایی هستند که به‌جای رفتار، **متنِ** یک فایل سرور را می‌خوانند؛ هر ریفکتوری که
فایلِ زیر را touched کند باید این لیترال‌ها را حفظ کند:

| فایل | لیترال‌ها | تست |
| --- | --- | --- |
| `routers/classes.py` | `PERSIAN_DAY_NAMES`، `display_name(` | `test_android_resources_static.py:707-708` (از P3b: روی روتر **+** `services/class_reports.py`) |
| `routers/finance.py` | `from validation import`، `validate_jalali_due_date`، **نباید** `Field(pattern=` | `test_audit.py:300-302` |
| `routers/audit.py` | `logger.error`، `print`، `joinedload`، `joinedload(SessionLog.course)`، `def count_suspicious_patterns`، `count_suspicious_patterns`؛ **نباید** `except Exception:\n        pass`، `get_suspicious_patterns` | `test_audit.py:283-291`، `test_dashboard_performance.py:208-218` |
| `routers/dashboard.py` | `check_admin_access`، `DashboardKPIs`، `due_date < today_jalali`، `func.count`، `func.sum`، `calculate_institute_cash_collected`، `jalali_date_string`، `_dashboard_cache`، `CACHE_TTL`، `time.time()`؛ **نباید** `def create_transaction`، `parse_project_date`، `for inst in unpaid`، `like(f"{today_jalali}%"` | `test_dashboard.py:237-240`، `test_dashboard_performance.py:182-203` |
| `routers/dunning.py` | `def count_dunning_pending`، `count_dunning_pending` | `test_dashboard_performance.py:212-216` |
| `schemas.py` | `class ClassSessionStudent(BaseModel):` + فیلدهای `ClassSessionHistory` | `test_android_resources_static.py:700-705` |
| `storage.py` | `/home/user/uploads` | `test_storage_paths.py:87` |

## قیدِ تازه کشف‌شده: `monkeypatch` روی فضای روتر

`tests/test_tuition_installments_audit.py:684`:

```python
monkeypatch.setattr(finance, "ActivityLog", BoomActivityLog)   # شبیه‌سازی خطا در آخرین قدم
with pytest.raises(RuntimeError):
    pay_installment_manually(world, installment_id)
```

این تست عمداً «شکست در آخرین قدمِ نوشتنِ ledger» را شبیه‌سازی می‌کند تا rollback سنجیده شود.
اگر بدنهٔ `pay_installment_manually` به لایهٔ سرویس برود، `ActivityLog` در فضای ماژولِ سرویس
resolve می‌شود و patch **بی‌اثر** می‌گردد → تست سبزِ کاذب می‌دهد (بدونِ `pytest.raises` شکست
می‌خورد، ولی اگر کسی بعداً assertها را شل کند، regressionِ rollback دیده نمی‌شود).

تصمیم: `pay_installment_manually` **پوسته نمی‌شود** و در `routers/finance.py` می‌ماند؛
این استثنا در docstringِ `services/__init__.py` هم مستند شده. (این تنها `monkeypatch.setattr`
روی فضای یک ماژولِ روتر در کلِ دو سوئیت است.)

## باقی‌ماندهٔ P3b (batch بعدی)

| handler | روتر | خط بدنه | مانع / کارِ لازم |
| --- | --- | --- | --- |
| `payment_callback` | finance | 453 | هلپرهای `_callback_static_page` (13)، `_callback_refresh_page` (14)، `_callback_processing_page` (14)، `_jalali_now_str` (5) و ثابت `PAYMENT_GATEWAY_ENABLED` باید همراهش بروند؛ `_jalali_now_str` ۱۲ مصرفِ دیگر در finance.py دارد ⇒ re-export لازم است. دو decorator دارد (`router.get` + `limiter.limit`) |
| `submit_payment` | finance | 334 | به `_jalali_now_str` و `_replay_idempotent_payment` (22) نیاز دارد |
| `refund_transaction` | finance | 180 | فقط `_jalali_now_str` |
| `restore_deleted_class` | admin | 321 | `ClassRestoreRequest` یک schema **محلی در روتر** است و در امضا می‌آید ⇒ اول باید به `schemas.py` (منبع یگانه از P2c) برود و از روتر re-export شود؛ docstring هم دارد که باید در پوسته بماند |
| `pay_installment_manually` | finance | 147 | **منتقل نمی‌شود** (قیدِ monkeypatchِ بالا) |

هیچ‌کدام از این نام‌ها مصرف‌کنندهٔ تست/اسکریپتِ بیرونی ندارند (بررسی شد)، پس انتقالِ هلپرهای
finance با یک re-export در `routers/finance.py` امن است.

## بازتولیدِ راستی‌آزمایی

```bash
cd /home/user/KharazmiNew1
# ۱) بدنه‌ها و پوسته‌ها بایت‌به‌بایت مثل HEAD باشند (اسکریپتِ راستی‌آزمایِ این فاز)
#    برای هر (روت، handler): بدنهٔ ماژول سرویس + decorator/امضا/docstring پوسته + forward کامل
# ۲) اوراکل OpenAPI
git worktree add --detach /tmp/base origin/main
cd /tmp/base && DATABASE_URL=sqlite:////tmp/oa1.db JWT_SECRET_KEY=ci-only \
  python /tmp/dump_openapi.py > /tmp/openapi_before.json; cd -
DATABASE_URL=sqlite:////tmp/oa2.db JWT_SECRET_KEY=ci-only \
  .venv/bin/python /tmp/dump_openapi.py > /tmp/openapi_after.json
diff /tmp/openapi_before.json /tmp/openapi_after.json     # باید خالی باشد (17203 خط)
git worktree remove /tmp/base --force && git worktree prune
# ۳) دو سوئیت (حتماً دو پروسسِ جدا) + گارد md5
DATABASE_URL=sqlite:////tmp/x1.db JWT_SECRET_KEY=test-secret-not-production \
  .venv/bin/python -m pytest Kharazmi_Server/tests -q -p no:randomly      # 1279 passed
DATABASE_URL=sqlite:////tmp/x2.db JWT_SECRET_KEY=test-secret-not-production \
  .venv/bin/python -m pytest tests/route_audit -q -p no:randomly          # 249 passed
md5sum -c /tmp/db_p3b.txt                                                 # gaj_db.db: OK
# ۴) lint / type / ledger
.venv/bin/ruff check .                                                    # Found 251 errors
.venv/bin/ruff check . --select F821                                      # فقط exams.py:380
.venv/bin/mypy                                                            # 727 errors in 42 files (checked 51)
DATABASE_URL=sqlite:////tmp/rl.db JWT_SECRET_KEY=ci-only .venv/bin/python \
  Kharazmi_Server/scripts/extract_server_routes.py --output docs/app-map/server-routes-extracted.csv
DATABASE_URL=sqlite:////tmp/vam.db JWT_SECRET_KEY=ci-only .venv/bin/python scripts/validate_app_map.py
```
