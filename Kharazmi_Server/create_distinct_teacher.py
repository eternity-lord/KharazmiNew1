from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import models
from models import Teacher, User, SessionLocal, engine
from dependencies import hash_password

db = SessionLocal()

try:
    # Check if exists
    existing = db.query(Teacher).filter(Teacher.mobile == "09123333333").first()
    if not existing:
        new_t = Teacher(
            id=3,
            teacher_code=103,
            first_name="استاد",
            last_name="محمدی",
            mobile="09123333333",
            password=hash_password("123"),
            is_approved=True,
            wallet_balance=0,
            branch_id=1
        )
        db.add(new_t)
        db.commit()
        print("✅ Distinct teacher created successfully!")
    else:
        print("Teacher already exists.")
except Exception as e:
    print("Error:", e)
finally:
    db.close()
