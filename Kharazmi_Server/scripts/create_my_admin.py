import os
import sys

# Add parent directory to path so models can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import models
from models import User, SessionLocal, engine

# اتصال به دیتابیس و ساخت جداول در صورت عدم وجود
models.Base.metadata.create_all(bind=engine)
db = SessionLocal()

def create_interactive_admin():
    print("==================================================")
    print("        KHARAZMI SYSTEM - CREATE ADMIN ACCOUNT")
    print("==================================================")
    print("\nلطفاً اطلاعات خود را برای ساخت حساب ادمین وارد کنید:\n")
    
    full_name = input("👤 نام و نام خانوادگی خودتان: ").strip()
    mobile = input("📱 شماره موبایل شما (نام کاربری): ").strip()
    password = input("🔑 رمز عبور انتخابی شما: ").strip()
    
    if not full_name or not mobile or not password:
        print("\n❌ خطا: تمام فیلدها الزامی هستند! دوباره تلاش کنید.")
        return
        
    # بررسی عدم تکراری بودن شماره موبایل در دیتابیس
    exists = db.query(User).filter(User.username == mobile).first()
    if exists:
        print(f"\n⚠️ هشدار: کاربری با شماره {mobile} از قبل در سیستم وجود دارد!")
        confirm = input("آیا می‌خواهید رمز عبور و نام او را بروزرسانی کنید؟ (y/n): ").strip().lower()
        if confirm == 'y':
            exists.full_name = full_name
            exists.password = password
            db.commit()
            print("\n✅ حساب کاربری با موفقیت بروزرسانی شد!")
        else:
            print("\n❌ عملیات لغو شد.")
        return

    # ساخت کاربر جدید با نقش ادمین
    new_admin = User(
        username=mobile,
        password=password,
        full_name=full_name,
        role="admin",
        sub_role="admin"
    )
    db.add(new_admin)
    db.commit()
    
    print("\n" + "🎉" * 20)
    print("✅ حساب ادمین اختصاصی شما با موفقیت ساخته شد!")
    print(f"👤 نام: {full_name}")
    print(f"📱 نام کاربری (موبایل): {mobile}")
    print(f"🔑 رمز عبور: {password}")
    print("🎉" * 20)

if __name__ == "__main__":
    try:
        create_interactive_admin()
    except KeyboardInterrupt:
        print("\n\n❌ عملیات لغو شد.")
    finally:
        db.close()
