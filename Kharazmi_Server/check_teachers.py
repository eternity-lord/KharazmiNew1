from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import models

DATABASE_URL = "sqlite:///gaj_db.db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
db = Session()

try:
    cursor = db.execute(text("SELECT id, username, role, sub_role FROM users;"))
    print("Users in DB:")
    for r in cursor.fetchall():
        print(r)
        
    cursor_t = db.execute(text("SELECT id, teacher_code, first_name, last_name, mobile FROM teachers;"))
    print("\nTeachers in DB:")
    for r in cursor_t.fetchall():
        print(r)
except Exception as e:
    print("Error:", e)
finally:
    db.close()
