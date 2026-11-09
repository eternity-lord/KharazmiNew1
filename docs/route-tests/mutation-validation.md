# اعتبارسنجی mutation منطق مالی و وضعیت

**تاریخ:** 2026-09-28 — **branch:** `arena/01a0c9b8-kharazmiapp`

این اجرا فقط برای سنجش قدرت تست‌های `tests/route_audit` انجام شد. هر mutation از checkout تمیز فعلی در یک کپی مستقل زیر `/tmp` ساخته شد؛ در هر کپی فقط همان تغییر عمدی اعمال شد و فقط دستور زیر اجرا شد:

```text
/tmp/route-audit-venv/bin/python -m pytest tests/route_audit -q
```

هیچ mutation، تغییر production یا دیتابیس اصلی روی branch ثبت نشده است. seed تست‌ها نیز فقط temporary DB می‌سازد؛ SMS، push و network واقعی استفاده نشدند.

## نتیجهٔ ۱۰ mutation مستقل

در ستون «تست قرمز» نام کامل nodeidهای قرمزِ همان اجرای مستقل آمده است. برای mutationهای M05 و M10 چند failure به‌دلیل اثر زنجیره‌ای روی fixture مشترک route-audit دیده شد؛ همهٔ آن‌ها عیناً از خروجی همان اجرای mutation ثبت شده‌اند.

| ID | mutation | محل mutation | نتیجه | تست قرمز / `none` |
|---|---|---|---|---|
| M01 | دوبرابرکردن سهم معلم در شارژ جلسه | `Kharazmi_Server/routers/attendance.py:793` | **گرفته شد** | `tests/route_audit/test_audit_attendance.py::test_session_charge_uses_the_declared_teacher_share_value` |
| M02 | حذف `is_deleted == False` از query بدهی enrollment | `Kharazmi_Server/financial_calculations.py:357` | **گرفته شد** | `tests/route_audit/test_audit_finance.py::test_invoice_ignores_archived_payment_rows_in_debt_oracle` |
| M03 | حذف `is_reversed == False` از جمع وصولی نقدی | `Kharazmi_Server/financial_calculations.py:71` | **گرفته شد** | `tests/route_audit/test_audit_dashboard.py::test_today_summary_excludes_reversed_institute_cash` |
| M04 | جابه‌جایی teacher/institute در breakdown بدهی | `Kharazmi_Server/financial_calculations.py:368` | **گرفته شد** | `tests/route_audit/test_audit_finance.py::test_invoice_and_class_status_agree` |
| M05 | حذف pre-check idempotency پرداخت | `Kharazmi_Server/routers/finance.py:230` | **گرفته شد** | `test_audit_finance.py::test_direct_payment_retry_is_idempotent_without_duplicate_transaction`; `test_audit_finance.py::test_installment_payment_is_atomic_and_updates_expected_rows`; `test_audit_finance.py::test_invoice_ignores_archived_payment_rows_in_debt_oracle`; `test_audit_finance.py::test_direct_payment_decrements_each_installment_cover_once`; `test_audit_parent.py::test_parent_child_profile_exact_values_and_no_real_sms`; `test_audit_reports.py::test_reports_debt_oracle_statement_scope_and_chart_shape`; `test_audit_students.py::test_student_profile_grade_oracle_access_and_optimistic_conflict`; `test_infrastructure.py::test_oracle_does_not_need_production_db` |
| M06 | حذف خطای 409 هنگام حذف جلسهٔ تسویه‌شده | `Kharazmi_Server/routers/attendance.py:1306` | **گرفته شد** | `tests/route_audit/test_audit_attendance.py::test_deleting_a_settled_session_is_a_conflict_without_side_effects` |
| M07 | تبدیل تخفیف fixed به محاسبهٔ درصدی | `Kharazmi_Server/dependencies.py:355` | **گرفته شد** | `tests/route_audit/test_audit_finance.py::test_invoice_applies_fixed_discount_as_a_fixed_amount` |
| M08 | حذف decrement پوشش قسط پس از پرداخت | `Kharazmi_Server/routers/finance.py:516` | **گرفته شد** | `tests/route_audit/test_audit_finance.py::test_direct_payment_decrements_each_installment_cover_once` |
| M09 | مثبت‌کردن payout تسویهٔ معلم به‌جای کسر از ledger | `Kharazmi_Server/routers/teachers.py:1015` | **گرفته شد** | `tests/route_audit/test_audit_teachers.py::test_teacher_settlement_retry_reversal_and_wallet_effect` |
| M10 | حذف scope `enrollment_id` و جایگزینی با scope دانش‌آموز | `Kharazmi_Server/financial_calculations.py:350` | **گرفته شد** | `test_audit_classes.py::test_class_list_details_and_students_have_values`; `test_audit_finance.py::test_student_dashboard_values_match_independent_oracle`; `test_audit_finance.py::test_invoice_and_class_status_agree`; `test_audit_finance.py::test_invoice_ignores_archived_payment_rows_in_debt_oracle`; `test_audit_reports.py::test_reports_debt_oracle_statement_scope_and_chart_shape` |

**جمع‌بندی mutation:** ۱۰ از ۱۰ گرفته شد؛ mutation فرارکرده (`escaped`) برابر **۰** است. بنابراین برای هیچ‌یک از ۱۰ mutation تست جبرانی لازم نماند؛ شش تست زیر برای mutationهایی که در اجرای اولیه escaped بودند اضافه شدند و سپس همان mutationها را قرمز کردند.

## تست‌های oracle اضافه‌شده

همهٔ این oracleها عدد مورد انتظار را مستقل از `financial_calculations` و helperهای محاسباتی production تعیین می‌کنند:

| commit مستقل | تست | mutation هدف |
|---|---|---|
| `6436838` | `test_audit_attendance.py:147` — `test_session_charge_uses_the_declared_teacher_share_value` | M01 |
| `2f93d35` | `test_audit_finance.py:185` — `test_invoice_ignores_archived_payment_rows_in_debt_oracle` | M02 |
| `e51cf4d` | `test_audit_dashboard.py:35` — `test_today_summary_excludes_reversed_institute_cash` | M03 |
| `52e51ab` | `test_audit_attendance.py:200` — `test_deleting_a_settled_session_is_a_conflict_without_side_effects` | M06 |
| `7729f10` | `test_audit_finance.py:210` — `test_invoice_applies_fixed_discount_as_a_fixed_amount` | M07 |
| `03255fc` | `test_audit_finance.py:224` — `test_direct_payment_decrements_each_installment_cover_once` | M08 |

برای جلوگیری از race مربوط به live auto-end در اجرای دیرهنگام suite، fixture موقت live نیز در commit `93b1e96` از timestamp فعلی seed می‌شود؛ این تغییر production نیست و در هیچ محاسبهٔ مالی دخالت ندارد.

## شمارش قبل و بعد

| شاخص | قبل | بعد |
|---|---:|---:|
| تست‌های evaluated (`passed + xfailed`) | 83 | 89 |
| passed | 80 | 86 |
| strict xfailed مجاز | 3 | 3 |
| warning | 4 | 4 |
| routeهای inventory | 221 | 221 |
| route دارای assertion مقداری | 70 | **72** |

شمارش route به‌صورت واقعی از inventory 221تایی و نقشهٔ assertion قبلی استخراج شد: `finance=11`، `attendance=10`، `classes=8` و admin/deep guard map برابر 41 (جمع قبلی 70). دو route جدیدِ دارای oracle مقداری عبارت‌اند از `POST /attendance/submit_session` و `DELETE /attendance/session/{session_code}`؛ finance و admin routes که تست جدیدشان اضافه شد، از قبل در مجموعهٔ routeهای asserted بودند. پس شمارش جدید `11 + 12 + 8 + 41 = 72 از 221` است.

CI پس از push نیز سبز شد: [run 36413712720](https://github.com/eternity-lord/KharazmiApp/actions/runs/36413712720)؛ root suite، cwd-independence و checksum guard همگی موفق بودند.

آخرین اجرای واقعی روی کد اصلی پس از همهٔ commitها:

```text
86 passed, 3 xfailed, 4 warnings in 4.92s
```

## checksum دیتابیس اصلی

خروجی عیناً از اجرای `md5sum` روی دیتابیس اصلی گرفته شده است؛ فایل اصلی تغییر نکرده است:

```text
f048f8d11833c4eaa944490594121d7  Kharazmi_Server/gaj_db.db
```
