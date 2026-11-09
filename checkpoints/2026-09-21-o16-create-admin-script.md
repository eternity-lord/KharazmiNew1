# O-16 — اسکریپت ساخت مدیر، مدیرِ غیرقابل‌ورود می‌ساخت و اجرای دوباره‌اش می‌شکست

- **تاریخ:** ۲۰۲۶-۰۹-۲۱ · **Branch:** `arena/01a0bf8d-kharazmiapp` · **موج:** ۳ (مورد ۱۱)
- **Base HEAD:** `fa8db9b` (O-10) · **دسته:** اسکریپت‌های عملیاتی/امنیت · **شدت:** بالا (بلاک راه‌اندازی)

## ریشه (وضعیت کد قدیمی که خوانده شد)
`scripts/create_admin.py` قبلاً این‌گونه بود: نام کاربری **هارد‌کد** `"09120000000"`، رمز **هارد‌کد**
`"123"` و به‌صورت **plaintext** ذخیره می‌شد، `role="admin"` بدون `sub_role`، بدون `branch_id`، و
گارد تکراری روی `username == "admin"` (نه روی همان نام کاربری‌ای که ساخته می‌شد). مواردی که واقعاً
مشاهده شد:
1. **رمز plaintext:** در `/tmp/o16_old2.db` مقدار ستون `password` دقیقاً `123` ذخیره شد. ورود
   اتفاقاً کار کرد چون auto-patch مرحلهٔ startup (`main.py:527-544`) رمزهای plaintext را هش می‌کند —
   یعنی درستیِ مدیر به یک وصلهٔ جانبی در زمان بالا آمدن سرور وابسته بود (بخار فایل بدون startup، یا
   کاربری که پس از backfill ساخته شود، plaintext می‌ماند).
2. **اجرای دوباره خراب بود:** گارد روی `"admin"` بود، ولی رکورد با `"09120000000"` ساخته می‌شد ⇒
   اجرای دوم `UNIQUE constraint failed: users.username` داد (و در نبود constraint، رکورد تکراری).
3. **`sub_role` ست نمی‌شد** ⇒ رکورد legacy (مغایر سیاست A1) و وابستگی به `resolve_effective_sub_role`.
4. **موبایل نرمال‌سازی نمی‌شد** و امکان انتخاب رمز/نام وجود نداشت.

خروجی واقعی اسکریپت قدیمی روی کپی آزمایشی:
```
✅ مدیر با موفقیت ساخته شد!      User: 09120000000 | Pass: 123
users[1].password = '123'        role='admin'  sub_role=None  branch_id=None
اجرای دوم ⇒ sqlalchemy.exc.IntegrityError: UNIQUE constraint failed: users.username
```

## فیکس
| فایل | تغییر |
|---|---|
| `scripts/create_admin.py` | بازنویسی کامل: چاپ دیتابیس هدف + تأیید تعاملی؛ `normalize_mobile` (شکل canonical `09xxxxxxxxx` = نام کاربری)؛ `getpass` دوبار با حداقل ۸ نویسه؛ `hash_password` (هرگز plaintext)؛ `role="admin"` + `sub_role="admin"`؛ `branch_id=None` (مدیر کل)؛ idempotent (وجود نام کاربری ⇒ خروج با کد ۳ و پیام صریح، **بدون تغییر رکورد/رمز**) |
| `tests/test_create_admin_script.py` (جدید) | ۶ تست subprocess روی دیتابیس `/tmp` تازه: ساخت هش‌شده + نقش/شعبه، **ورود واقعی** (`/auth/login` + `/auth/me`)، idempotency، رد رمز کوتاه/موبایل نامعتبر بدون نوشتن، نرمال‌سازی موبایل، لغو با پاسخ منفی |

قراردادهای دستی: کد خروج ۰ = ساخته شد · ۱ = لغو توسط کاربر · ۲ = ورودی نامعتبر · ۳ = از قبل وجود دارد.

## تست
- `Kharazmi_Server/tests/test_create_admin_script.py` ⇒ **6 passed** (شامل ورود واقعی مدیر ساخته‌شده).
- کل سوئیت: **1061 passed** · md5 `gaj_db.db` بی‌تغییر · `import main` واقعی روی کپی `/tmp` سالم.
- ⚠️ اسکریپت **روی دیتابیس واقعی اجرا نشد** (دستور صریح کاربر)؛ همهٔ تست‌ها روی `/tmp/*.db`.

## Commit / Push
- پیام: `fix: make the admin-creator script produce a real, loginable, idempotent admin (O-16)`
