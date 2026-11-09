"""ساخت نخستین کاربر مدیر — اجرای تعاملی روی دیتابیس هدف (FIX O-16).

نسخهٔ قبلی این اسکریپت عملاً خراب بود:
  * رمز ثابت `"123"` را **plaintext** ذخیره می‌کرد؛ `verify_password` هش می‌خواهد ⇒
    مدیر ساخته‌شده هرگز نمی‌توانست وارد شود.
  * چک تکراری روی نام کاربری `"admin"` بود، ولی کاربر با نام کاربری `"09120000000"`
    ساخته می‌شد ⇒ اجرای دوباره، IntegrityError/رکورد تکراری می‌داد.
  * `sub_role` ست نمی‌شد (سیاست A1) و موبایل نرمال‌سازی نمی‌شد.

این نسخه:
  * موبایل/نام/رمز را از ترمینال می‌گیرد (`getpass`، رمز دو بار، حداقل ۸ نویسه)،
  * موبایل را با `normalize_mobile` استاندارد می‌کند و همان را `username` می‌گذارد،
  * رمز را با `hash_password` هش می‌کند (هرگز plaintext)،
  * `role="admin"` و `sub_role="admin"` می‌گذارد و `branch_id=None` (دسترسی سراسری)،
  * idempotent است: اگر کاربری با همان نام کاربری باشد، هیچ رکورد/رمزی تغییر نمی‌کند،
  * قبل از هر نوشتن، **دیتابیس هدف** را چاپ و تأیید می‌گیرد (جلوگیری از اجرای ناخواسته روی DB واقعی).

اجرا:
    python scripts/create_admin.py                                  # دیتابیس پیش‌فرض پروژه
    DATABASE_URL=sqlite:////tmp/x.db python scripts/create_admin.py  # دیتابیس آزمایشی
"""
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import models  # noqa: E402
from dependencies import hash_password, normalize_mobile  # noqa: E402
from models import SessionLocal, User  # noqa: E402

MIN_PASSWORD_LEN = 8


def main() -> int:
    print(f"دیتابیس هدف: {models.DATABASE_URL}")
    if input("ادامه؟ [y/N] ").strip().lower() not in ("y", "yes", "بله", "ب"):
        print("لغو شد؛ هیچ تغییری انجام نشد.")
        return 1

    mobile = normalize_mobile(input("شماره موبایل مدیر (مثلاً 09120000000): "))
    if not mobile:
        print("✗ شماره موبایل معتبر نیست (باید ۱۰ یا ۱۱ رقم و با 09 شروع شود).")
        return 2

    full_name = input("نام و نام خانوادگی مدیر: ").strip() or "مدیر سیستم"

    password = getpass.getpass(f"رمز عبور (حداقل {MIN_PASSWORD_LEN} نویسه): ")
    if len(password) < MIN_PASSWORD_LEN:
        print(f"✗ رمز باید حداقل {MIN_PASSWORD_LEN} نویسه باشد.")
        return 2
    if password != getpass.getpass("تکرار رمز عبور: "):
        print("✗ دو رمز یکسان نیستند.")
        return 2

    models.Base.metadata.create_all(bind=models.engine)
    db = SessionLocal()
    try:
        # idempotent: کلید هویت، همان چیزی است که ساخته می‌شود (نام کاربری نرمال‌شده).
        existing = db.query(User).filter(User.username == mobile).first()
        if existing is not None:
            print(f"⚠️ کاربری با نام کاربری {mobile} از قبل وجود دارد (نقش: {existing.role})."
                  " هیچ رکورد/رمزی تغییر نکرد.")
            return 3

        db.add(User(
            username=mobile,
            password=hash_password(password),  # هش — هرگز plaintext
            full_name=full_name,
            role="admin",
            sub_role="admin",
            branch_id=None,  # مدیر کل: دسترسی سراسری (بدون قید شعبه)
        ))
        db.commit()
        print(f"✅ مدیر ساخته شد — نام کاربری: {mobile} (نقش: admin/admin، بدون شعبه)")
        print("   رمز فقط به‌صورت هش ذخیره شد.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
