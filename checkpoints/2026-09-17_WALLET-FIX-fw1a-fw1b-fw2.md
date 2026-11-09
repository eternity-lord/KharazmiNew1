# فیکس سه باگ ممیزی کیف پول (F-W1a / F-W1b / F-W2) — 2026-09-17

## درخواست کاربر
سه باگ قطعی‌شده‌ی ممیزی کیف پول باید fix شوند (همین سه‌تا و نه بیشتر):
۱) **F-W1a** ویرایش `session_charge` نباید اعشاری بنویسد (integer + جمع دقیق سهم‌ها + باقیمانده‌ی قطعی + invariant).
۲) **F-W1b** همان ویرایش باید `share_teacher`/`share_institute` را هم اصلاح کند و گزارش `financial_calculations` سهم جدید را نشان دهد.
۳) **F-W2** ویرایش رسید legacy `target_wallet="both"` باید delta واقعی (`new − old`) را با نسبت قبلی (یا fallback مستند) تقسیم کند.
+ تست‌های رگرسیون، تست refund/delete/گزارش‌ها، تست عدم‌ذخیره‌ی float، invariant پس از ویرایش، اجرای compileall/audit/suite،
و گزارش `git diff`/`git status` قبل از commit. دست‌زدن به `gaj_db.db` ممنوع؛ commit/push فقط روی برنچ arena.

## baseline (قبل از تغییر — الزام تسک)
```
pytest -q Kharazmi_Server/test_wallet_finance_audit.py   →  3 failed / 46 passed (همان سه تست یافته‌محور)
```

## فایل‌های تغییرکرده
| فایل | تغییر |
|---|---|
| `Kharazmi_Server/routers/admin.py` | +۷۰/−۲۵ (تنها کد تولیدی تغییرکرده) |
| `Kharazmi_Server/test_wallet_finance_audit.py` | ۴۹ → ۶۸ تست (+۱۹ رگرسیون جدید) |

## شرح فیکس

### ۱) helper مشترک `_split_amount_integer` (بالای `update_transaction`)
تقسیم قطعیِ یک مبلغ بین دو سهم با **جمع دقیقاً برابر مبلغ** و **بدون هیچ اعشار**:
```
part_a = sign * (|amount| * |share_a| // total)          # total = |share_a| + |share_b|
part_b = amount - part_a                                  # باقیمانده (در قدرمطلق) → سهم دوم
```
- **قاعده‌ی باقیمانده (قطعی و مستند):** باقیمانده در قدرمطلق همیشه به سهم دوم (آموزشگاه) می‌رسد —
  همان قراردادی که خودِ پروژه در `submit_payment` (Bug 10: `amt_teacher = amount // 2` و
  `amt_institute = amount - amt_teacher`) و در مسیر `refund` رسیدهای `both` دارد.
- **fallback مستند:** اگر هر دو سهم صفر/غایب باشند ⇒ ۱:۱ (نصف-نصف) با همان قاعده‌ی باقیمانده.
- محاسبه روی قدرمطلق انجام می‌شود تا در جهت منفی هم «باقیمانده به آموزشگاه» صادق باشد
  (کفِ `//` برای اعداد منفی، باقیمانده را به سهم اول می‌داد).

### ۲) F-W1a — پایان پول اعشاری در ویرایش `session_charge`
پیش‌تر: `teacher_ratio = abs(share_teacher)/total_share` (خط ۹۹۰) و `teacher_diff = diff * teacher_ratio` (خط ۹۹۷)
⇒ نوشتن `-60.6/-40.4` روی ستون BigInteger.
اکنون: سهم‌های جدید = تقسیم صحیحِ `|new_amount|` با نسبت قبلی؛ `d_teacher = prior_teacher − new_teacher` و
`d_institute = prior_institute − new_institute`. نتیجه: هم دلتاها صحیح‌اند، هم جمعشان دقیقاً برابر تغییر مبلغ،
هم کیف دقیقاً هم‌راستای سهم ذخیره‌شده. تست‌شده روی مبلغ‌های بدتقسیم `-1, -7, -101, -103, -999, -1001, -1500`.

### ۳) F-W1b — سهم‌های جلسه با مبلغ هم‌راستا می‌شوند
همان شاخه، سه خط `trans.share_teacher/share_institute = new_*` را ست می‌کند ⇒
`share_teacher + share_institute == |amount|` و گزارش‌های `calculate_institute_session_revenue` /
`calculate_teacher_session_revenue` (که همین ستون‌ها را جمع می‌زنند) عدد جدید را نشان می‌دهند.
نمونه‌ی تست: شارژ ۱۰۰ (۶۰/۴۰) → ویرایش به ۱۳۰ ⇒ سهم‌ها `(78, 52)`، کیف `(-78, -52)`، گزارش آموزشگاه `52` (قبلاً ۴۰).

### ۴) F-W2 — دلتای واقعی برای رسید legacy `both`
پیش‌تر: شاخه‌ی `deposit` فقط `teacher`/`institute` را می‌شناخت و برای `both` هیچ دلتایی اعمال نمی‌شد.
اکنون:
- **سهم قبلی موجود:** `new_share = split(new_amount, prior_share)` و `d = new_share − prior_share`
  ⇒ برای ردیف سازگار، جمع دلتاها دقیقاً `delta = new − old`؛ ستون‌های سهم هم با مبلغ جدید هم‌راستا می‌شوند
  (مسیر `refund` دقیقاً `share_t + share_i == amount` را ملاک می‌گیرد).
- **سهم قبلی غایب:** `delta` طبق فرمول `new − old` نصف-نصف تقسیم می‌شود (باقیمانده به آموزشگاه) و سهم‌های
  ردیف هم ۵۰/۵۰ با مبلغ جدید ست می‌شوند.

### آنچه عمداً تغییر نکرد (محدوده‌ی تسک)
- شاخه‌ی `deposit` برای `target_wallet in (teacher, institute)`، شاخه‌های `tuition/enrollment_payment` و
  رفتار `delete_transaction` دست‌نخورده‌اند.
- ردیف legacy `session_charge` با **سهم صفر مطلق**: طبق رفتار قبلی دست‌نخورده می‌ماند (نه دلتا، نه پرکردن
  مصنوعی سهم) تا مسیر `delete` سهمی را برنگرداند که هرگز کسر نشده بود — تست اختصاصی دارد.
- ردیف legacy با سهم **ناسازگار** (مثلاً `share=(30,30)` برای مبلغ ۱۰۰) با ویرایش «درمان» می‌شود:
  سهم‌ها به نسبت قبلی با مبلغ هم‌راستا و کیف هم با همان سهم‌ها منطبق می‌شود (تست اختصاصی).

## تست‌های جدید (۱۹ تست / ۲۶ آیتم با پارامتری)
| تست | باگ | چه چیزی را قفل می‌کند |
|---|---|---|
| `test_fix_fw1a_session_charge_edit_keeps_money_integer` | F-W1a | نسخه‌ی سبزشده‌ی تست یافته‌محور قبلی (۱۰۱ ⇒ ۶۰/۴۱) |
| `test_fix_fw1a_no_float_for_any_awkward_charge_amount[-1…-1500]` (۷ مورد) | F-W1a | هیچ مبلغ بدتقسیمی اعشار تولید نمی‌کند (typeof SQLite == integer) |
| `test_fix_fw1a_no_float_when_charge_is_reduced_or_untouched` | F-W1a | کاهش شارژ و ویرایشِ بدون تغییر مبلغ |
| `test_fix_float_amount_input_never_reaches_money_columns` | F-W1a | ورودی اعشاری در `TransactionUpdate` به DB نمی‌رسد |
| `test_fix_fw1b_session_charge_edit_updates_shares_and_reports` | F-W1b | نسخه‌ی سبزشده (۱۳۰ ⇒ سهم ۷۸/۵۲ + گزارش ۵۲/۷۸) |
| `test_fix_fw1b_shares_stay_consistent_across_many_edits` | F-W1b | زنجیره‌ی ویرایش‌ها؛ سهم == مبلغ == گزارش در هر گام |
| `test_fix_fw1b_legacy_zero_share_charge_is_left_untouched` | F-W1b | محدودیت مستند (سهم صفر legacy) |
| `test_fix_fw1b_legacy_inconsistent_shares_are_healed` | F-W1b | هم‌راستاشدن ردیف ناسازگار (۳۰/۳۰ ⇒ ۵۰/۵۰) |
| `test_fix_fw2_legacy_both_receipt_edit_applies_real_delta` | F-W2 | نسخه‌ی سبزشده (۱۰۰→۲۰۰ با نسبت ۴۰:۶۰) |
| `test_fix_fw2_both_edit_fallback_is_half_split_with_remainder_to_institute` | F-W2 | fallback مستند سهم‌غایب (۱‏۰۱ ⇒ ۵۰/۵۱) |
| `test_fix_fw2_repeated_both_edits_split_delta_by_prior_ratio` | F-W2 | دو ویرایش پیاپی با نسبت جاری |
| `test_fix_fw2_negative_delta_stays_integer_and_coherent` | F-W2 | دلتای منفی ۱ واحدی + سازگاری کامل با refund |
| `test_fix_fw2_refund_after_edit_reverses_exactly_what_was_credited` | F-W2 | refund بعد از ویرایش ⇒ بازگشت دقیق به حالت پایه |
| `test_fix_fw1b_refund_and_reports_unaffected_for_normal_receipts` | رگرسیون | پرداخت/refund/گزارش‌های عادی دست‌نخورده |
| `test_fix_teacher_and_institute_edit_behavior_is_preserved` | رگرسیون | ویرایش رسید تک‌کیفی همان رفتار قبلی |
| `test_fix_delete_after_session_charge_edit_restores_wallets` | رگرسیون | delete بعد از ویرایش شارژ (سهم‌های جدید) |

## نتایج اجرا (بعد از فیکس)
```
python3 -m compileall Kharazmi_Server                                              → exit 0
pytest -q Kharazmi_Server/test_wallet_finance_audit.py -vv                         → 68 passed / 0 failed / 0 skipped
۳ فایل مالی موجود (priority2 + advanced_finance + priority3)                       → 172 passed (baseline بدون تغییر)
pytest -q Kharazmi_Server                                                          → 407 passed / 0 failed / 0 skipped
import main روی کپی /tmp (قانون ایستاده‌ی پروژه)                                   → OK (29 route)
```
قبل از فیکس: ۳۸۸ آیتم (۳۸۵ pass + ۳ finding) — بعد از فیکس: ۴۰۷ آیتم، همه سبز.

## ایمنی
```
۶ فایل ممنوعه (finance/timeline/audit/dunning/dashboard/exports) → sha256 دیسک == HEAD ✅
gaj_db.db پروداکشن → f0e55fe7c5130ec17e39e73036e2291794c3c335f67d852c37599a6c0f99ec79 (بدون تغییر ✅)
همه‌ی اجراها روی کپی‌ها: /tmp/wallet_audit.db، /tmp/wallet_suite.db، /tmp/full_suite_wallet.db، /tmp/import_main_check.db
git status → فقط دو فایل: routers/admin.py + test_wallet_finance_audit.py
```

## محدودیت / ریسک باقی‌مانده
1. **`delete_transaction` برای رسید `both`** همچنان دلتایی اعمال نمی‌کند (همان کامنت «هدف نامشخص») —
   خارج از دامنه‌ی این سه باگ گفته‌شده ماند. ویرایش+حذفِ پیاپی یک رسید `both` می‌تواند اثر کیف را باقی بگذارد.
2. **کیف‌های از قبل اعشاری‌شده** (اگر داده‌ی تاریخی از باگ F-W1a داشته باشد) با این فیکس «پاک‌سازی سراسری»
   نمی‌شوند؛ فقط نوشتن‌های جدید صحیح‌اند. در داده‌ی فعلی صفر مورد وجود دارد (بررسی شد).
3. ردیف‌های legacy با سهم صفر مطلق عمداً دست‌نخورده می‌مانند (توضیح بالا) — یعنی در آن حالت خاص،
   `share_t + share_i` با مبلغ هم‌راستا نمی‌شود (اما کیف هم دست‌نخورده می‌ماند).
4. فیکس فقط روی مسیر **ویرایش ادمین** است؛ مسیرهای ساخت (attendance/submit_payment) از قبل صحیح بودند.
