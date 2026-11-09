from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import models

DATABASE_URL = "sqlite:///gaj_db.db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
db = Session()

try:
    cursor = db.execute(text("SELECT id, title, code, days_of_week, class_time, is_deleted FROM courses;"))
    print("Courses in DB:")
    for r in cursor.fetchall():
        print(r)
except Exception as e:
    print("Error:", e)
finally:
    db.close()
