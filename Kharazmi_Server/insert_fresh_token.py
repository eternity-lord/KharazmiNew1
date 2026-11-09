import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import models

DATABASE_URL = "sqlite:///gaj_db.db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
db = Session()

try:
    # Delete old session if exists
    db.execute(text("DELETE FROM user_sessions WHERE token = 'test_admin_token';"))
    
    # Insert new session with created_at set to current UTC time
    now_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(text(f"INSERT INTO user_sessions (token, user_id, sub_role, created_at) VALUES ('test_admin_token', 1, 'admin', '{now_str}');"))
    db.commit()
    print("✅ Fresh test token inserted successfully: 'test_admin_token'")
except Exception as e:
    print("Error:", e)
finally:
    db.close()
