import unittest
import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from models import Base, User, UserSession, Student, Teacher, Course, Enrollment, Room, Lead, Branch, Transaction
from main import app
from dependencies import get_db, hash_password


class TestBranchesCrmCalendarE2E(unittest.TestCase):

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

        # Override FastAPI dependency to use isolated DB
        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        # Seed two branches
        self.branch_a = Branch(id=1, name="شعبه الف (شمال)", active=True)
        self.branch_b = Branch(id=2, name="شعبه ب (جنوب)", active=True)
        self.db.add_all([self.branch_a, self.branch_b])
        self.db.commit()

        # Seed admin users for both branches
        self.admin_a_user = User(id=101, username="admin_a", password=hash_password("123"), role="admin", sub_role="admin", branch_id=1, full_name="Admin A")
        self.admin_b_user = User(id=102, username="admin_b", password=hash_password("123"), role="admin", sub_role="admin", branch_id=2, full_name="Admin B")
        self.secretary_user = User(id=103, username="secretary_test", password=hash_password("123"), role="admin", sub_role="secretary", branch_id=1, full_name="Secretary")
        self.db.add_all([self.admin_a_user, self.admin_b_user, self.secretary_user])
        self.db.commit()

        # Create active session tokens
        self.session_a = UserSession(token="tok_admin_a", user_id=101, sub_role="admin", created_at=datetime.datetime.now())
        self.session_b = UserSession(token="tok_admin_b", user_id=102, sub_role="admin", created_at=datetime.datetime.now())
        self.session_sec = UserSession(token="tok_secretary", user_id=103, sub_role="secretary", created_at=datetime.datetime.now())
        self.db.add_all([self.session_a, self.session_b, self.session_sec])
        self.db.commit()

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_scenario_1_room_clash_detection_e2e(self):
        """E2E Scenario 1: Create room, verify conflict check detects room clashing successfully"""
        room_payload = {
            "name": "اتاق ۱۰۱",
            "capacity": 20,
            "location": "طبقه اول",
            "branch_id": 1
        }
        res_room = self.client.post("/rooms/create", json=room_payload, headers={"Authorization": "Bearer tok_admin_a"})
        self.assertEqual(res_room.status_code, 200)
        room_id = res_room.json()["id"]

        course = Course(
            id=10,
            title="ریاضی کنکور",
            code="MATH99",
            teacher_id=1,
            room_id=room_id,
            days_of_week="شنبه",
            class_time="16:00",
            branch_id=1,
            is_deleted=False,
            is_suspended=False
        )
        self.db.add(course)
        self.db.commit()

        conflict_payload = {
            "teacher_id": 2,
            "room_id": room_id,
            "days_of_week": "شنبه",
            "class_time": "16:00",
            "student_ids": []
        }
        res_conflict = self.client.post(
            "/calendar/check_conflicts",
            json=conflict_payload,
            headers={"Authorization": "Bearer tok_admin_a"}
        )
        self.assertEqual(res_conflict.status_code, 200)
        self.assertTrue(res_conflict.json()["has_conflict"])
        self.assertIn("تداخل اتاق", res_conflict.json()["details"][0])

    def test_scenario_2_crm_lifecycle_and_secretary_conversion_e2e(self):
        """E2E Scenario 2: Secretary creates lead, updates notes, and converts lead to student successfully"""
        lead_payload = {
            "name": "علیرضا احمدی",
            "mobile": "09129998877",
            "interested_course": "فیزیک دهم",
            "source": "Instagram"
        }
        res_create = self.client.post(
            "/crm/leads/create",
            json=lead_payload,
            headers={"Authorization": "Bearer tok_secretary"}
        )
        self.assertEqual(res_create.status_code, 200)
        lead_id = res_create.json()["id"]

        note_payload = {
            "notes": "با ولی تماس گرفته شد و مشاوره اولیه داده شد.",
            "status": "CONSULTATION"
        }
        res_notes = self.client.post(
            f"/crm/leads/{lead_id}/notes",
            json=note_payload,
            headers={"Authorization": "Bearer tok_secretary"}
        )
        self.assertEqual(res_notes.status_code, 200)

        res_convert = self.client.post(
            f"/crm/leads/{lead_id}/convert",
            headers={"Authorization": "Bearer tok_secretary"}
        )
        self.assertEqual(res_convert.status_code, 200)
        student_id = res_convert.json()["student_id"]

        st = self.db.query(Student).filter(Student.id == student_id).first()
        self.assertIsNotNone(st)
        self.assertEqual(st.first_name, "علیرضا احمدی")
        self.assertEqual(st.student_mobile, "09129998877")

        lead = self.db.query(Lead).filter(Lead.id == lead_id).first()
        self.assertEqual(lead.status, "REGISTERED")

    def test_scenario_3_branch_statistics_idor_prevention_e2e(self):
        """E2E Scenario 3: Verify Branch A Admin can see Branch A stats, but is blocked from Branch B stats (IDOR)"""
        res_a = self.client.get(
            "/dashboard/branch_stats?branch_id=1",
            headers={"Authorization": "Bearer tok_admin_a"}
        )
        self.assertEqual(res_a.status_code, 200)
        self.assertEqual(res_a.json()["branch_name"], "شعبه الف (شمال)")

        res_b_fail = self.client.get(
            "/dashboard/branch_stats?branch_id=2",
            headers={"Authorization": "Bearer tok_admin_a"}
        )
        self.assertEqual(res_b_fail.status_code, 403)
        self.assertIn("Branch-Level IDOR Protection", res_b_fail.json()["detail"])


if __name__ == "__main__":
    unittest.main()
