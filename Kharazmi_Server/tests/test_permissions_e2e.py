import unittest
import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from models import Base, User, UserSession, Student, Teacher, Course, Enrollment, Branch, ParentOTP
from main import app
from dependencies import get_db, hash_password


class TestKharazmiPermissionsE2E(unittest.TestCase):

    def setUp(self):
        # Isolated in-memory SQLite DB
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        # Seed branches
        self.db.add(Branch(id=1, name="مرکزی", active=True))
        self.db.commit()

        # Seed admin and secretary
        self.admin_user = User(id=1, username="09120000000", password=hash_password("123"), full_name="Admin", role="admin", sub_role="admin", branch_id=1)
        self.secretary_user = User(id=2, username="09121111111", password=hash_password("123"), full_name="Secretary", role="admin", sub_role="secretary", branch_id=1)
        self.db.add_all([self.admin_user, self.secretary_user])
        self.db.commit()

        # Seed students
        self.student1 = Student(id=1, first_name="الارا", last_name="صیامی", national_code="0000000001", student_mobile="09120000001", parent_mobile="09120000001")
        self.student2 = Student(id=2, first_name="سارا", last_name="احمدی", national_code="0000000002", student_mobile="09120000002", parent_mobile="09120000002")
        self.db.add_all([self.student1, self.student2])
        self.db.commit()

        # Seed teacher
        self.teacher = Teacher(id=1, first_name="امیر", last_name="احمدی", national_code="0001000128", mobile="09123333333", teacher_code=101, is_approved=True, password=hash_password("101"))
        self.teacher_user = User(id=3, username="09123333333", password=hash_password("101"), full_name="امیر احمدی", role="teacher", sub_role="teacher")
        self.db.add_all([self.teacher, self.teacher_user])
        self.db.commit()

        # Sessions
        self.admin_session = UserSession(token="tok_admin", user_id=1, sub_role="admin", created_at=datetime.datetime.now())
        self.secretary_session = UserSession(token="tok_secretary", user_id=2, sub_role="secretary", created_at=datetime.datetime.now())
        self.teacher_session = UserSession(token="tok_teacher", user_id=3, sub_role="teacher", created_at=datetime.datetime.now())
        self.temp_parent_session = UserSession(token="temp_tok", user_id=-1, sub_role="temp_parent:09120000001", created_at=datetime.datetime.now())
        self.db.add_all([self.admin_session, self.secretary_session, self.teacher_session, self.temp_parent_session])
        self.db.commit()

        # OTP for parent
        self.otp = ParentOTP(mobile="09120000001", otp="12345", created_at=datetime.datetime.utcnow(), expires_at=datetime.datetime(2030, 12, 31, 23, 59, 59), is_used=False)
        self.db.add(self.otp)
        self.db.commit()

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_permission_scenarios(self):
        # TEST 1: Admin login and access everything
        r_admin = self.client.post("/auth/login", json={"mobile": "09120000000", "password": "123"})
        self.assertEqual(r_admin.status_code, 200)
        admin_token = r_admin.json()["token"]
        headers_admin = {"Authorization": f"Bearer {admin_token}"}

        me_admin = self.client.get("/auth/me", headers=headers_admin)
        self.assertEqual(me_admin.status_code, 200)
        self.assertIn("*", me_admin.json()["permissions"])

        # TEST 2: Secretary cannot edit institute settings
        r_sec = self.client.post("/auth/login", json={"mobile": "09121111111", "password": "123"})
        self.assertEqual(r_sec.status_code, 200)
        sec_token = r_sec.json()["token"]
        headers_sec = {"Authorization": f"Bearer {sec_token}"}

        r_settings_put = self.client.put("/admin/institute_settings", json={
            "name": "آموزشگاه جدید", "address": "تهران", "phone": "021", "official_email": "a@a.com"
        }, headers=headers_sec)
        self.assertEqual(r_settings_put.status_code, 403)

        # TEST 3: Teacher access Student IDOR
        # Teacher tries to access Student 1 who is NOT enrolled in teacher's class -> 403
        r_student_profile = self.client.get("/admin/students/1/full_profile", headers={"Authorization": "Bearer tok_teacher"})
        self.assertEqual(r_student_profile.status_code, 403)

        # TEST 4: Parent Select Child IDOR
        # Parent with mobile 09120000001 tries to select student 2 (belongs to 09120000002) -> 403
        r_switch = self.client.post("/parent/select_child", json={"temp_token": "temp_tok", "student_id": 2})
        self.assertEqual(r_switch.status_code, 403)

        # Positive case: parent selects own child (student 1) -> success
        r_switch_ok = self.client.post("/parent/select_child", json={"temp_token": "temp_tok", "student_id": 1})
        # Might need fresh temp token because previous attempt didn't delete, but our temp token still exists
        # If first failure didn't delete token, second should succeed
        if r_switch_ok.status_code == 200:
            self.assertEqual(r_switch_ok.status_code, 200)
        else:
            # If token was consumed or blocked, recreate and try again
            self.db.add(UserSession(token="temp_tok2", user_id=-1, sub_role="temp_parent:09120000001", created_at=datetime.datetime.now()))
            self.db.commit()
            r_switch_ok2 = self.client.post("/parent/select_child", json={"temp_token": "temp_tok2", "student_id": 1})
            self.assertEqual(r_switch_ok2.status_code, 200)


if __name__ == "__main__":
    unittest.main()
