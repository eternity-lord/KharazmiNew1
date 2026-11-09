import datetime
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models import Base, Branch, Course, Enrollment, Student, Teacher, User, UserSession, SessionLog, Attendance, Settlement, SequenceCounter
from routers.teachers import (
    get_all_teachers,
    get_teacher_full_profile,
    get_teacher_profile,
    update_teacher,
    get_pending_settlement,
    get_settlement_history,
)
from schemas import TeacherUpdate


class TestTeachersRouter(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        self.db.add(Branch(id=1, name="مرکزی", active=True))
        self.db.add(SequenceCounter(name="teacher", current_value=101))

        self.admin = User(username="admin", password="x", full_name="مدیر", role="admin", sub_role="admin", branch_id=1)
        self.teacher_user_a = User(username="09120000001", password="x", full_name="معلم الف", role="teacher", sub_role="teacher")
        self.teacher_user_b = User(username="09120000002", password="x", full_name="معلم ب", role="teacher", sub_role="teacher")
        self.db.add_all([self.admin, self.teacher_user_a, self.teacher_user_b])
        self.db.flush()

        self.teacher_a = Teacher(first_name="مریم", last_name="الف", mobile="09120000001", national_code="0012345678", is_approved=True, teacher_code=101)
        self.teacher_b = Teacher(first_name="سارا", last_name="ب", mobile="09120000002", national_code="0012345679", is_approved=False, teacher_code=102)
        self.student = Student(first_name="علی", last_name="دانش‌آموز", national_code="0012345680", student_mobile="09121111111", wallet_teacher=0, wallet_institute=0, wallet_balance=0)
        self.db.add_all([self.teacher_a, self.teacher_b, self.student])
        self.db.flush()

        self.course_a = Course(title="ریاضی", code="200001", teacher_id=self.teacher_a.id, is_admin_approved=True, is_deleted=False, grade_level="دهم", class_time="16:00-17:30", days_of_week="شنبه", teacher_session_price=100000)
        self.db.add(self.course_a)
        self.db.flush()

        self.enrollment = Enrollment(student_id=self.student.id, course_id=self.course_a.id, register_date="1405/06/01", shift="عصر", total_tuition=1000000, total_paid=0)
        self.db.add(self.enrollment)
        self.db.flush()

        self.session_log = SessionLog(course_id=self.course_a.id, date="1405/06/02", time="16:00", final_teacher_cost=100000, final_institute_share=50000, cost_per_student=150000, attendee_count=1, status="Finished")
        self.db.add(self.session_log)
        self.db.flush()

        self.attendance = Attendance(session_id=self.session_log.id, student_id=self.student.id, status="Present", is_billed=False, excused=False)
        self.db.add(self.attendance)

        self.settlement = Settlement(teacher_id=self.teacher_a.id, total_amount=500000, session_count=2, settled_at=datetime.datetime.now(), settled_by_user_id=self.admin.id)
        self.db.add(self.settlement)

        self.db.add_all([
            UserSession(token="admin-token", user_id=self.admin.id, sub_role="admin", created_at=datetime.datetime.now()),
            UserSession(token="teacher-a-token", user_id=self.teacher_user_a.id, sub_role="teacher", created_at=datetime.datetime.now()),
            UserSession(token="teacher-b-token", user_id=self.teacher_user_b.id, sub_role="teacher", created_at=datetime.datetime.now()),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_list_teachers(self):
        teachers = get_all_teachers(db=self.db, authorization="Bearer admin-token", sub_role="admin", skip=0, limit=None)
        self.assertTrue(len(teachers) >= 2)

    def test_full_profile_idor(self):
        # Teacher A can view own full profile
        full = get_teacher_full_profile(id=self.teacher_a.id, authorization="Bearer teacher-a-token", db=self.db, sub_role="teacher")
        self.assertEqual(full.info.name, "مریم الف")
        self.assertIsNone(full.collaboration_summary)  # teacher should not see collaboration

        # Teacher B cannot view Teacher A's profile
        with self.assertRaises(HTTPException) as e:
            get_teacher_full_profile(id=self.teacher_a.id, authorization="Bearer teacher-b-token", db=self.db, sub_role="teacher")
        self.assertEqual(e.exception.status_code, 403)

        # Admin can view any and sees collaboration_summary
        full_admin = get_teacher_full_profile(id=self.teacher_a.id, authorization="Bearer admin-token", db=self.db, sub_role="admin")
        self.assertIsNotNone(full_admin.collaboration_summary)
        self.assertEqual(full_admin.total_students, 1)

    def test_get_teacher_profile(self):
        profile = get_teacher_profile(teacher_id=self.teacher_a.id, db=self.db, authorization="Bearer admin-token", sub_role="admin")
        self.assertEqual(profile["first_name"], "مریم")

        with self.assertRaises(HTTPException) as e:
            get_teacher_profile(teacher_id=9999, db=self.db, authorization="Bearer admin-token", sub_role="admin")
        self.assertEqual(e.exception.status_code, 404)

    def test_update_teacher_and_optimistic_locking(self):
        # Teacher B is not approved, so teacher role can still update (approved teachers blocked)
        # Admin can update
        data = TeacherUpdate(first_name="سارا_جدید", version=1)
        result = update_teacher(teacher_id=self.teacher_b.id, data=data, db=self.db, current_username_or_role="admin")
        self.assertIn("موفقیت", result["message"])
        self.db.refresh(self.teacher_b)
        self.assertEqual(self.teacher_b.first_name, "سارا_جدید")
        self.assertEqual(self.teacher_b.version, 2)

        # Old version should 409
        data_old = TeacherUpdate(first_name="سارا", version=1)
        with self.assertRaises(HTTPException) as e:
            update_teacher(teacher_id=self.teacher_b.id, data=data_old, db=self.db, current_username_or_role="admin")
        self.assertEqual(e.exception.status_code, 409)

        # Approved teacher cannot update self (403)
        data_approved = TeacherUpdate(first_name="مریم_جدید", version=1)
        with self.assertRaises(HTTPException) as e:
            update_teacher(teacher_id=self.teacher_a.id, data=data_approved, db=self.db, current_username_or_role="teacher")
        self.assertEqual(e.exception.status_code, 403)

    def test_pending_settlement_and_history(self):
        pending = get_pending_settlement(teacher_id=self.teacher_a.id, db=self.db, authorization="Bearer admin-token", sub_role="admin")
        self.assertEqual(pending["total_amount"], 100000)
        self.assertEqual(pending["session_count"], 1)

        history = get_settlement_history(teacher_id=self.teacher_a.id, db=self.db, authorization="Bearer admin-token", sub_role="admin")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["total_amount"], 500000)

    def test_pending_settlement_teacher_with_no_class(self):
        pending = get_pending_settlement(teacher_id=self.teacher_b.id, db=self.db, authorization="Bearer admin-token", sub_role="admin")
        self.assertEqual(pending["total_amount"], 0)
        self.assertEqual(pending["session_count"], 0)


if __name__ == "__main__":
    unittest.main()
