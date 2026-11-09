from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import models

DATABASE_URL = "sqlite:///gaj_db.db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
db = Session()

try:
    db.execute(text("UPDATE students SET parent_mobile = '09120000003' WHERE id = 1;"))
    db.commit()
    print("✅ Student 1 parent mobile set to 09120000003 successfully!")
except Exception as e:
    print("Error:", e)
finally:
    db.close()
