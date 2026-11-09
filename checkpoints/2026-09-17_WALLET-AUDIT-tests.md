# ممیزی کیف پول / پرداخت داخلی / refund / سازگاری موجودی — 2026-09-17

## درخواست کاربر
«فقط منطق کیف پول، پرداخت داخلی، refund و سازگاری موجودی را تست کن» — با قوانین کسب‌وکار:
`wallet_teacher`/`wallet_institute` **مثبت = اعتبار**، **منفی = بدهی دانش‌آموز**، **صفر = تسویه**؛
و invariant همیشگی `wallet_balance == wallet_teacher + wallet_institute`.
محدودیت صریح: فقط تست نوشتن/اجرا؛ **کد اصلی تغییر نکند**؛ به `gaj_db.db` واقعی دست نزن؛
SQLite موقت/in-memory؛ پرداخت آنلاین/CORS/Android/دسترسی نقش‌ها خارج از scope.

## خروجی: `Kharazmi_Server/test_wallet_finance_audit.py` (جدید، ۹۷۱ خط، ۴۹ تست)
هیچ فایل غیرتستی تغییر نکرد — `git status` فقط همین فایل را نشان می‌دهد.

### دستور اجرا (کانونیکال این تسک)
```
cd /home/user/KharazmiApp
DATABASE_URL=sqlite:////tmp/wallet_audit.db \
PYTHONPATH=/home/user/KharazmiApp/Kharazmi_Server \
python3 -m pytest Kharazmi_Server/test_wallet_finance_audit.py -q
```

### نتیجه‌ی اجرا
```
49 items — 46 passed / 3 failed (سه fail عمدی/یافته‌محور) — 0 skip   [4.66s]
سوئیت کامل: 388 items — 385 passed / 3 failed (همان سه یافته)      [33.4s]
۳ فایل مالی موجود: 172 passed (baseline دست‌نخورده)
```
سه تست fail از ابتدا با نام `test_finding_*` نوشته شده‌اند تا **نقص اسناد شود**، نه اینکه
رگرسیون پنهان بماند. اگر روزی فیکس شوند سبز/XPASS می‌شوند.

### نگاشت ۱۴ سناریوی درخواستی → تست‌ها
| # | سناریو | تست |
|---|---|---|
| ۱ | موجودی صفر اولیه | `test_s01_initial_wallets_are_zero` |
| ۲ | شارژ جلسه ۱۰۰ ⇒ ‎-۱۰۰ | `test_s02_session_charge_100_makes_minus_100` |
| ۳ | پرداخت ۴۰ ⇒ بدهی ۶۰ | `test_s03_payment_40_moves_debt_from_100_to_60` |
| ۴ | پرداخت ۶۰ ⇒ صفر (تسویه) | `test_s04_payment_60_settles_total_balance_to_zero`, `test_s04b_settling_both_wallets_to_exactly_zero` |
| ۵ | پرداخت ۱۰۰ بعد از تسویه ⇒ +۱۰۰ | `test_s05_payment_after_settlement_goes_positive` |
| ۶ | refund ⇒ بازگشت به صفر | `test_s06_refund_returns_balance_to_zero` |
| ۷ | فقط teacher | `test_s07_teacher_only_payment_touches_only_teacher_wallet` |
| ۸ | فقط institute | `test_s08_institute_only_payment_touches_only_institute_wallet` |
| ۹ | both (جمع سهم‌ها = مبلغ) | `test_s09_split_payment_shares_sum_exactly_to_amount[100/101/999/1001]`, `test_s09b_explicit_split_is_not_reinterpreted` |
| ۱۰ | مبلغ صفر/منفی/نامعتبر قبل از هر نوشتن رد شود | `test_s10_invalid_amounts_rejected_before_any_write[7 case]`, `test_s10b_*`, `test_s10c_schema_level` |
| ۱۱ | refund تکراری بی‌اثر | `test_s11_duplicate_refund_is_rejected_and_changes_nothing`, `test_s11b_refund_of_session_charge_is_rejected` |
| ۱۲ | deleted/reversed در موجودی فعال و درآمد نباشند | `test_s12a..s12d` |
| ۱۳ | invariant بعد از هر سناریو | `assert_wallet_invariant` داخل همه‌ی helperها (هر pay/refund/submit خودکار چک می‌کند) + `test_s13_full_walk_invariant_every_step` |
| ۱۴ | هم‌زمانی/bulk و lost update | `test_s14a..s14d`, `test_concurrent_double_refund_applies_exactly_once` |

**پوشش مسیری اضافه‌شده:** پرداخت دستی قسط (`finance.pay_installment_manually`)، ویرایش و حذف
تراکنش توسط ادمین، برگشت جلسه (`dependencies.reverse_session_financial_impacts`)، جریمه‌ی غیبت
غیرموجه (`attendance`)، idempotency پرداخت، استرداد بعد از مصرف اعتبار، و بازنویسی مستقیم
`wallet_balance` (لیسنر Bug18).

## یافته‌ها (هر ۳ مورد در `routers/admin.py` — نقص کد تولیدی، فقط مستند شده)

### 🔴 F-W1a — ویرایش شارژ جلسه، پول اعشاری می‌نویسد
* **فایل/خط:** `Kharazmi_Server/routers/admin.py:990` (`teacher_ratio = abs(share_teacher) / total_share`)
  و `:997-998` (`teacher_diff = diff * teacher_ratio`) ⇒ نوشتن در ستون‌های BigInteger خط `:1019-1028`.
* **تست:** `test_finding_fw1a_session_charge_edit_writes_fractional_money` (خط ۹۴۹ فایل تست)
* **بازتولید:** شارژ جلسه ۱۰۰ (۶۰/۴۰) → ویرایش ادمین مبلغ به `-101`
* **expected:** کیف‌ها عدد صحیح تومان؛ **actual:** `teacher=-60.6 (float)، institute=-40.4 (float)، balance=-101`
* **شدت:** متوسط‌به‌بالا — invariant نمی‌شکند (balance از جمع همان دو مؤلفه ساخته می‌شود) ولی مقدار
  اعشاری در دیتابیس می‌نشیند و به فاکتور/گزارش/جمع‌های مالی نشت می‌کند.
* **قطعیت:** قطعی (deterministic؛ تقسیم float در پایتون).

### 🔴 F-W1b — ویرایش شارژ جلسه، `share_*` را به‌روز نمی‌کند ⇒ گزارش‌ها کهنه می‌مانند
* **فایل/خط:** همان شاخه‌ی `session_charge` در `admin.update_transaction` (`admin.py:985-1000`) —
  فقط `amount` عوض می‌شود، `share_teacher/share_institute` دست‌نخورده.
* **تست:** `test_finding_fw1b_session_charge_edit_leaves_shares_stale` (خط ۸۶۹)
* **بازتولید:** شارژ ۱۰۰ (۶۰/۴۰) → ویرایش به `-130`
* **expected:** جمع سهم‌ها = مبلغ شارژ و گزارش سهم آموزشگاه متناسب؛
  **actual:** `amount=-130` ولی `shares=(60,40)` ⇒ جمع سهم‌ها ۱۰۰؛ کیف‌ها درست مقیاس شدند
  (`-78/-52`) اما گزارش آموزشگاه **۴۰** ماند در حالی که عدد صحیح درست **۵۲** است.
* **شدت:** متوسط — ناسازگاری گزارش مالی با کیف/دفتر (مالیات، تسویه با معلم، داشبورد سهم‌ها).
* **قطعیت:** قطعی — تابع گزارش (`calculate_institute_session_revenue`) روی همین ستون‌ها جمع می‌زند.

### 🔴 F-W2 — ویرایش رسید قدیمی `both` هیچ دلتایی روی کیف اعمال نمی‌کند
* **فایل/خط:** `Kharazmi_Server/routers/admin.py:975-976` — در شاخه‌ی `deposit` فقط دو حالت
  `teacher`/`institute` هندل شده و برای `both` کامنت خودِ کد می‌گوید «هیچ تغییری اعمال نمی‌شود».
* **تست:** `test_finding_fw2_legacy_both_receipt_edit_does_not_adjust_wallets` (خط ۸۲۷)
* **بازتولید:** رسید `both` مبلغ ۱۰۰ با `share=(40,60)` و کیف‌های ۴۰/۶۰ → ویرایش مبلغ به ۲۰۰
* **expected:** ۱۰۰ به جمع کیف اضافه شود؛ **actual:** افزایش صفر (کیف همان ۴۰/۶۰ ماند).
* **ناسازگاری رفتاری:** دو مسیر دیگر همان رسید را می‌شناسند —
  `finance.refund_transaction` (`finance.py:1384`) سهم‌ها را برمی‌گرداند و
  `admin.delete_transaction` (`admin.py:845-870`) دلتای سهم‌دار می‌دهد ⇒ رفتار سه‌گانه‌ی ناسازگار.
* **شدت:** متوسط (دفتر/کیف‌پول از هم واگرا می‌شوند؛ عملیات بعدی مانند refund روی داده‌ی درست کار می‌کند
  ولی مبلغ ویرایش‌شده هیچ‌جا اعمال نشده است).
* **قطعیت:** قطعی در سطح کد؛ **فعلاً نهفته** — `submit_payment` امروز رسید `both` نمی‌سازد
  (دو رسید جدا می‌سازد) و در کپی دیتابیس پروداکشن هم صفر ردیف `target_wallet='both'` وجود دارد
  (تنها ردیف: `target_wallet=None`). ریسک روی داده‌ی تاریخی نسخه‌های قدیمی.

## مواردی که طبق قانون کسب‌وکار **درست** کار می‌کنند (تأییدشده با تست)
1. **invariant** `balance == teacher + institute` در همه‌ی ۴۶ تست پاس، در هر گام، حتی وقتی کیف منفی می‌شود.
2. نشانه‌ها: منفی = بدهی، صفر = تسویه، مثبت = اعتبار — و **پرداخت فقط همان کیفی را شارژ می‌کند که هدف است**
   (پرداخت teacher هیچ اثری روی institute ندارد و برعکس).
3. تقسیم `both`: جمع سهم‌ها **دقیقاً** برابر مبلغ (تست‌شده روی ۱۰۰/۱۰۱/۹۹۹/۱۰۰۱ ⇒ باقیمانده به institute می‌رود).
4. مبلغ صفر/منفی/کیف نامعتبر **قبل از هر نوشتن** رد می‌شود؛ DB دست‌نخورده می‌ماند
   (ترتیب گاردها: Bug22 → M12 → M27 → شعبه → تقسیم).
5. `refund` تکراری ⇒ ۴۰۰ و بی‌اثر؛ refund شارژ جلسه ⇒ ۴۰۰؛ استرداد تسویه‌شده جزئی ⇒ کیف‌ها دست‌نخورده.
6. رسیدهای `is_deleted`/`is_reversed` نه در موجودی فعال و نه در درآمد (`calculate_*_revenue`) نمی‌آیند.
7. **هم‌زمانی:** ۱۰ پرداخت موازی ⇒ جمع دقیقاً N×amount (بدون lost update)؛ دو refund موازی روی یک رسید
   ⇒ دقیقاً یکی موفق (۲۰۰) و یکی ۴۰۰، کسر فقط یک‌بار.
8. **idempotency:** replay با همان کلید ⇒ `duplicate=True`، کیف فقط یک‌بار شارژ، رسید دوم ساخته نمی‌شود.
9. bulk UPDATE خام الگوی پروداکشن (admin/finance/dependencies) همه با `refresh` + `sync_wallet_balance`
   همراه‌اند ⇒ invariant حفظ می‌شود؛ و سشن دیگری با آبجکت کهنه نمی‌تواند کیف را به عقب برگرداند.
10. بازنویسی مستقیم و ناسازگار `wallet_balance` توسط کد بیرونی ⇒ لیسنر آن را به جمع دو مؤلفه برمی‌گرداند.

## وریفای
```
1) ۶ فایل ممنوعه (finance/timeline/audit/dunning/dashboard/exports):
   sha256 دیسک == sha256 HEAD برای هر ۶ ⇒ ✅ هیچ فایلی لمس نشد
2) git status → فقط ?? Kharazmi_Server/test_wallet_finance_audit.py (هیچ کد تولیدی تغییر نکرده)
3) DB پروداکشن: f0e55fe7c5130ec17e39e73036e2291794c3c335f67d852c37599a6c0f99ec79 (بدون تغییر ✅)
   همه‌ی اجراها روی کپی‌ها: /tmp/wallet_audit.db، /tmp/wallet_suite.db، /tmp/full_suite_wallet.db
4) ۳ فایل مالی موجود: 172 passed (بدون رگرسیون)
5) سوئیت کامل: 385 passed / 3 یافته‌ی عمدی / 0 skip
```

## جمع‌بندی برای کاربر
هیچ باگی در **هسته‌ی کیف پول / پرداخت / refund / invariant** پیدا نشد: هر ۴۶ تست رفتاری پاس شد و
سه یافته‌ی باقی‌مانده همه در **مسیر ویرایش ادمین روی تراکنش‌های خاص** (`routers/admin.py`) هستند،
نه در `finance.submit_payment`/`refund_transaction`. F-W1a اعشاری‌شدن پول، F-W1b کهنه‌ماندن سهم
جلسه در گزارش‌ها، و F-W2 بی‌اثر‌بودن ویرایش رسید قدیمی `both`. هر سه با تست مستند و قابل بازتولیدند
و **هیچ‌کدام رفع نشد** (طبق دستور تسک: فقط تست).
