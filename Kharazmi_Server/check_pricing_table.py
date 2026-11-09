from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import models

DATABASE_URL = "sqlite:///gaj_db.db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
db = Session()

try:
    cursor = db.execute(text("SELECT * FROM pricing_table;"))
    rows = cursor.fetchall()
    print("Pricing Table contents:")
    for r in rows:
        print(r)
except Exception as e:
    print("Error querying pricing_table:", e)
finally:
    db.close()
