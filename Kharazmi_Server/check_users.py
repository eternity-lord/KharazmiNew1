from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import models

DATABASE_URL = "sqlite:///gaj_db.db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
db = Session()

try:
    cursor = db.execute(text("SELECT id, username, role, sub_role FROM users;"))
    rows = cursor.fetchall()
    print("Users list in DB:")
    for r in rows:
        print(r)
except Exception as e:
    print("Error:", e)
finally:
    db.close()
