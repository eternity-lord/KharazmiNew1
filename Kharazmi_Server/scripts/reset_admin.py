from sqlalchemy.orm import Session
import models
from models import User, SessionLocal, engine

# اتصال به دیتابیس
models.Base.metadata.create_all(bind=engine)
db = SessionLocal()

def force_reset_admin():
    target_mobile = "09219868213"
    
    # 1. اول چک میکنیم اگه مدیر قبلی هست، پاکش کنیم (که ارور تکراری نده)
    old_admin = db.query(User).filter(User.username == target_mobile).first()
    if old_admin:
        db.delete(old_admin)
        db.commit()
        print(f"♻️ اکانت قدیمی {target_mobile} حذف شد.")

    # 2. حالا یه مدیر جدید و تمیز میسازیم
    new_admin = User(
        username=target_mobile,
        password="admin",  # رمز عبور قطعی
        full_name="مدیر کل سیستم",
        role="admin"
    )
    db.add(new_admin)
    db.commit()
    
    print("------------------------------------------------")
    print("✅ مدیر جدید با موفقیت ساخته شد!")
    print(f"👤 نام کاربری: {target_mobile}")
    print(f"🔑 رمز عبور: 123")
    print("------------------------------------------------")

if __name__ == "__main__":
    try:
        force_reset_admin()
    except Exception as e:
        print(f"❌ خطا: {e}")
