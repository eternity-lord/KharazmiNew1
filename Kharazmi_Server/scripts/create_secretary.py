from sqlalchemy.orm import Session
import os
import sys

# Add parent directory to path so models can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import models
from models import User, SessionLocal, engine

# اتصال به دیتابیس
models.Base.metadata.create_all(bind=engine)
db = SessionLocal()

def create_test_secretary():
    # چک کنیم اگر از قبل وجود دارد نسازیم
    exists = db.query(User).filter(User.username == "09121111111").first()
    if exists:
        print("⚠️ کاربر منشی تستی با شماره 09121111111 از قبل وجود دارد.")
        return

    secretary = User(
        username="09121111111", # شماره موبایل منشی (نام کاربری)
        password="123",         # رمز عبور منشی
        full_name="منشی تستی سیستم",
        role="admin",           # نقش پایه ادمین است تا لاگین موفق باشد
        sub_role="secretary"    # سطح دسترسی محدودتر منشی
    )
    db.add(secretary)
    db.commit()
    print("✅ کاربر منشی تستی با موفقیت ساخته شد!")
    print("نام کاربری (موبایل): 09121111111")
    print("رمز عبور: 123")
    print("سطح دسترسی محدود: secretary")

if __name__ == "__main__":
    create_test_secretary()
