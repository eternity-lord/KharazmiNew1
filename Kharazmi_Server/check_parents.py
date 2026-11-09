from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import models

DATABASE_URL = "sqlite:///gaj_db.db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
db = Session()

try:
    cursor_s = db.execute(text("SELECT id, first_name, last_name, student_mobile, parent_mobile FROM students;"))
    print("Students in DB:")
    for r in cursor_s.fetchall():
        print(r)
except Exception as e:
    print("Error:", e)
finally:
    db.close()
