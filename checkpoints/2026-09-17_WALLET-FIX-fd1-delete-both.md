# فیکس F-D1 — حذف رسید legacy با `target_wallet="both"` — 2026-09-17

## درخواست کاربر
تنها باگ باقی‌مانده: `delete_transaction` برای رسیدهای `target_wallet="both"` اثر مالی کیف را
برنمی‌گرداند. با failing-test-first، سناریوهای خواسته‌شده (اصلی + الف…ح)، هم‌راستایی با
`refund_transaction`، نگه‌داشتن integerها و بدون تغییر کد خارج از موضوع.

## baseline (قبل از تغییر)
```
pytest -q Kharazmi_Server/test_wallet_finance_audit.py   → 68 passed
pytest -q Kharazmi_Server                                → 407 passed
```
سپس ۱۱ تست F-D1 به‌صورت failing-first نوشته و اجرا شد:
```
pytest -q ... -k "delete or refund_after or refund_of_soft"  → 8 failed / 7 passed
```
(۸ شکست = بازتولید دقیق باگ روی سناریوی اصلی، سهم نامساوی، مبلغ فرد، بعد از ویرایش، حذف تکراری،
استرداد بعد از حذف، هم‌راستایی با refund و fallback بدون سهم.)

## فایل‌های تغییرکرده
| فایل | تغییر |
|---|---|
| `Kharazmi_Server/routers/admin.py` | +۱۵/−۱ — تنها کد تولیدی (شاخه‌ی `both` در `delete_transaction`) |
| `Kharazmi_Server/test_wallet_finance_audit.py` | ۶۸ → ۷۹ تست (+۱۱ رگرسیون F-D1) |
| `checkpoints/2026-09-17_WALLET-FIX-fd1-delete-both.md` | همین سند |

## شرح دقیق fix
پیش‌تر در `delete_transaction` شاخه‌ی `deposit` فقط `teacher`/`institute` را می‌شناخت و برای `both`
با کامنت «هدف نامشخص» **هیچ دلتایی** اعمال نمی‌شد؛ در نتیجه با حذف یک رسید legacy، مبلغ شارژ‌شده‌ی
کیف‌ها باقی می‌ماند (واگرایی دفتر/کیف) — در حالی که مسیر `refund_transaction` همین رسیدها را
درست برمی‌گرداند.

اکنون شاخه‌ی `elif trans.target_wallet == "both"` اضافه شده که **عیناً همان اعداد مسیر refund** را
اعمال می‌کند (هم‌راستایی کامل، بدون منطق موازی):
```
share_teacher   = int(trans.share_teacher or 0)
share_institute = int(trans.share_institute or 0)
if share_teacher + share_institute != t_amount:      # ← همان شرط refund_transaction
    share_teacher   = t_amount // 2                  # ← همان fallback مستند پروژه
    share_institute = t_amount - share_teacher       #   (باقیمانده به آموزشگاه)
d_teacher  = -share_teacher
d_institute = -share_institute
```
نکات:
- **بدون تغییر سیاست حذف:** پروژه hard-delete می‌کند (تصمیم H11) و این تابع همان مسیر را دارد
  (claim اتمیک `is_deleted` برای mutual exclusion → `db.delete` + commit). هیچ ردیف `reversal`
  جدیدی ساخته نمی‌شود (طبق policy فعلی لازم نیست).
- **integer-only:** مقادیر از ستون‌های BigInteger می‌آیند و `int(...)` هم برای داده‌ی قدیمی محافظه‌کارانه است.
- **بدون تأثیر روی سایر مسیرها:** `teacher`/`institute`/`session_charge`/`tuition`/`enrollment_payment`
  و حالت `target_wallet=None` دست‌نخورده‌اند (کامنت قبلی فقط به None اشاره‌اش اصلاح شد).
- **جای helper:** این شاخه عمداً از `_split_amount_integer` استفاده نمی‌کند و همان فرمول refund را
  تکرار می‌کند تا برای مبلغ منفیِ legacy هم **بیت‌به‌بیت** با refund یکسان باشد (`//` پایتون).

## سناریوهای تست‌شده (F-D1)
| # | سناریو | تست |
|---|---|---|
| اصلی | ۴۰/۶۰ از ۱۰۰ ⇒ هر دو کیف صفر + hard-delete + صفر ردیف reversal | `test_delete_both_receipt_returns_both_wallets_to_zero` |
| الف | سهم نامساوی ۳۰/۷۰ | `test_delete_both_receipt_unequal_shares` |
| ب | مبلغ فرد ۱۰۱ با سهم ۵۰/۵۱ | `test_delete_both_receipt_odd_amount` |
| ج | ویرایش ۱۰۰→۲۰۱ (سهم ۸۰/۱۲۱) سپس حذف | `test_delete_both_receipt_after_edit_reverses_final_amount` |
| د | حذف تکراری ⇒ ۴۰۴ و بی‌اثر | `test_delete_both_receipt_twice_is_rejected_and_idempotent` |
| هـ | رسید teacher-only / institute-only | `test_delete_teacher_only_and_institute_only_behaviour_preserved` |
| و | ردیف deleted / reversed ⇒ ۴۰۴ و بی‌اثر | `test_delete_never_touches_already_deleted_or_reversed_rows` |
| ح | استرداد بعد از حذف (hard-deleted) ⇒ ۴۰۴ | `test_refund_after_delete_is_rejected_and_changes_nothing` |
| ح (تکمیل) | استرداد ردیف soft-deleted ⇒ ۴۰۴ | `test_refund_of_soft_deleted_both_receipt_is_rejected` |
| هم‌راستایی | دو رسید یکسان: delete یکی و refund دیگری ⇒ همان مبالغ | `test_delete_both_matches_refund_for_identical_receipt` |
| fallback | رسید both بدون سهم (۵۰/۵۱ از ۱۰۱) | `test_delete_both_receipt_without_shares_uses_documented_fallback` |
| ز | invariant بعد از هر عملیات | `assert_wallet_invariant` داخل `delete_receipt`/`refund` + assertهای صریح هر تست |

## نتایج اجرا (بعد از فیکس)
```
python3 -m compileall Kharazmi_Server                                → exit 0
pytest -q Kharazmi_Server/test_wallet_finance_audit.py -vv           → 79 passed / 0 failed / 0 skipped
۳ فایل مالی موجود                                                     → 172 passed (بدون رگرسیون)
pytest -q Kharazmi_Server                                            → 418 passed / 0 failed / 0 skipped
import main روی کپی /tmp                                              → OK (29 route)
```

## بررسی invariant و refund/delete
- **invariant:** `wallet_balance == wallet_teacher + wallet_institute` بعد از هر حذف/استرداد/ویرایش
  در هر سه لایه بررسی می‌شود: helperهای تست (`wallets` + `assert_wallet_invariant`)، مسیر کد
  (`db.refresh` + `sync_wallet_balance` بعد از هر bulk update)، و لیسنر Bug18 مدل.
- **delete:** شاخه‌ی `both` حالا دقیقاً سهم‌های ذخیره‌شده (یا fallback مستند) را برمی‌گرداند؛ حذف
  تکراری/ردیف deleted یا reversed ⇒ ۴۰۴ بدون هیچ نوشتن.
- **refund:** رفتار قبلی دست‌نخورده و **عددی هم‌راستا** با delete (تست هم‌راستایی با دو ردیف یکسان).
  استرداد ردیف حذف‌شده یا soft-deleted ⇒ ۴۰۴ (چون lookup روی `is_deleted == False` است).
- **float:** `assert_wallet_money_integer` نوع واقعی SQLite (`typeof`) را در سناریوهای کلیدی چک می‌کند ⇒ integer.

## ایمنی
```
۶ فایل ممنوعه (finance/timeline/audit/dunning/dashboard/exports) → sha256 دیسک == HEAD ✅
gaj_db.db → f0e55fe7c5130ec17e39e73036e2291794c3c335f67d852c37599a6c0f99ec79 (بدون تغییر ✅)
همه‌ی اجراها روی کپی‌ها: /tmp/wallet_audit.db، /tmp/wallet_suite.db، /tmp/full_suite_wallet.db، /tmp/import_main_check.db
```

## محدودیت / ریسک باقی‌مانده
1. رسید legacy با `target_wallet=None` و سهم‌دار همچنان طبق رفتار مستند قبلی هیچ دلتایی نمی‌گیرد
   (خارج از دامنه‌ی این تسک؛ فقط `both` خواسته شده بود). اگر داده‌ی تاریخی چنین ردیفی داشته باشد،
   پیشنهاد: تسک جدا برای بررسی همان حالت (شمارش روی DB واقعی انجام نشده چون هدف `both` بود).
2. سیاست حذف همچنان hard-delete است (H11)؛ در نتیجه ردیابی «چه کسی حذف کرد» در سطح خود Transaction
   باقی نمی‌ماند (ActivityLog بیرونی خارج از دامنه).
3. ردیف‌های `both` با سهم ناسازگار (جمع سهم ≠ مبلغ) عمداً به fallback نصف-نصف می‌روند — همان رفتار
   refund؛ یعنی دقیقاً همان مبلغی برمی‌گردد که refund هم برمی‌گرداند (هم‌راستا، تست‌شده).
