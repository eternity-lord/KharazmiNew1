import datetime
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models import Base, Branch, Course, Enrollment, Student, Teacher, User, UserSession, Transaction, SessionLog, Attendance, InstituteSettings
from routers.reports import (
    get_chart_data,
    get_financial_report,
    get_debtors_report,
    get_financial_summary,
    get_student_statement,
    get_logged_in_teacher,
)


class TestReportsRouter(unittest.TestCase):
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
        self.db.add(InstituteSettings(name="آموزشگاه تست", address="تهران", phone="021", card_number="6037997979797979"))

        self.admin = User(username="admin", password="x", full_name="مدیر", role="admin", sub_role="admin", branch_id=1)
        self.secretary = User(username="sec", password="x", full_name="منشی", role="admin", sub_role="secretary", branch_id=1)
        self.teacher_user = User(username="09120000001", password="x", full_name="معلم", role="teacher", sub_role="teacher")
        self.db.add_all([self.admin, self.secretary, self.teacher_user])
        self.db.flush()

        self.teacher = Teacher(first_name="مریم", last_name="معلم", mobile="09120000001", national_code="0012345678", is_approved=True, teacher_code=101)
        self.student_debtor = Student(first_name="علی", last_name="بدهکار", national_code="0012345680", student_mobile="09121111111", wallet_teacher=-500000, wallet_institute=-200000, wallet_balance=-700000, branch_id=1)
        self.student_ok = Student(first_name="رضا", last_name="خوب", national_code="0012345681", student_mobile="09122222222", wallet_teacher=100000, wallet_institute=0, wallet_balance=100000, branch_id=1)
        self.db.add_all([self.teacher, self.student_debtor, self.student_ok])
        self.db.flush()

        self.course = Course(title="ریاضی", code="200001", teacher_id=self.teacher.id, is_admin_approved=True, is_deleted=False, grade_level="دهم", class_time="16:00", days_of_week="شنبه", teacher_session_price=100000)
        self.db.add(self.course)
        self.db.flush()

        self.enrollment = Enrollment(student_id=self.student_debtor.id, course_id=self.course.id, register_date="1405/06/01", shift="عصر", total_tuition=1000000, total_paid=300000)
        self.db.add(self.enrollment)

        self.transaction = Transaction(student_id=self.student_debtor.id, course_id=self.course.id, enrollment_id=self.enrollment.id, amount=300000, payment_method="نقد", date="1405/06/01", receiver="مدیر", description="شهریه", type="tuition", target_wallet="institute", share_teacher=100000, share_institute=200000, branch_id=1)
        self.db.add(self.transaction)

        self.session_log = SessionLog(course_id=self.course.id, date="1405/06/02", time="16:00", final_teacher_cost=100000, final_institute_share=50000, cost_per_student=150000, attendee_count=1, status="Finished")
        self.db.add(self.session_log)
        self.db.flush()

        self.attendance = Attendance(session_id=self.session_log.id, student_id=self.student_debtor.id, status="Present", is_billed=False)
        self.db.add(self.attendance)

        self.db.add_all([
            UserSession(token="admin-token", user_id=self.admin.id, sub_role="admin", created_at=datetime.datetime.now()),
            UserSession(token="sec-token", user_id=self.secretary.id, sub_role="secretary", created_at=datetime.datetime.now()),
            UserSession(token="teacher-token", user_id=self.teacher_user.id, sub_role="teacher", created_at=datetime.datetime.now()),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_chart_data(self):
        result = get_chart_data(authorization="Bearer admin-token", db=self.db, _="admin")
        self.assertIn("income_chart", result)
        self.assertIn("student_chart", result)
        self.assertIn("attendance_trend", result)
        # attendance_trend should have at least one entry
        self.assertTrue(len(result["attendance_trend"]) >= 1)

    def test_financial_report_admin_only(self):
        # Admin can access
        report = get_financial_report(authorization="Bearer admin-token", db=self.db, _="admin")
        self.assertTrue(len(report) >= 1)
        self.assertEqual(report[0]["amount"], 300000)

        # Secretary should be blocked by check_admin_access dependency (tested separately)
        from dependencies import check_admin_access
        with self.assertRaises(HTTPException) as e:
            check_admin_access("Bearer sec-token", self.db)
        self.assertEqual(e.exception.status_code, 403)

    def test_debtors_report(self):
        debtors = get_debtors_report(authorization="Bearer admin-token", db=self.db, _="admin")
        self.assertTrue(len(debtors) >= 1)
        self.assertTrue(any(d["student_id"] == self.student_debtor.id for d in debtors))
        # Non-debtor should not appear
        self.assertFalse(any(d["student_id"] == self.student_ok.id for d in debtors))

    def test_financial_summary_teacher_restriction(self):
        # Teacher can only see own summary, forced to teacher type
        result_teacher = get_financial_summary(user_type="teacher", teacher_id=self.teacher.id, authorization="Bearer teacher-token", db=self.db, sub_role="teacher")
        self.assertEqual(result_teacher["user_type"], "teacher")
        self.assertEqual(result_teacher["teacher_id"], self.teacher.id)

        # Teacher trying to see institute summary should still be forced to teacher (logic in function)
        result_forced = get_financial_summary(user_type="institute", authorization="Bearer teacher-token", db=self.db, sub_role="teacher")
        self.assertEqual(result_forced["user_type"], "teacher")

        # Admin can see institute summary
        result_admin = get_financial_summary(user_type="institute", authorization="Bearer admin-token", db=self.db, sub_role="admin")
        self.assertEqual(result_admin["user_type"], "institute")
        self.assertIn("monthly", result_admin)

    def test_student_statement(self):
        statement = get_student_statement(student_id=self.student_debtor.id, db=self.db, authorization="Bearer admin-token", role="admin")
        self.assertEqual(statement["student_id"], self.student_debtor.id)
        self.assertIn("total_paid_institute", statement)
        self.assertIn("total_debt_institute", statement)

        with self.assertRaises(HTTPException) as e:
            get_student_statement(student_id=9999, db=self.db, authorization="Bearer admin-token", role="admin")
        self.assertEqual(e.exception.status_code, 404)

    def test_get_logged_in_teacher(self):
        teacher = get_logged_in_teacher(self.db, "Bearer teacher-token")
        self.assertIsNotNone(teacher)
        self.assertEqual(teacher.id, self.teacher.id)

        # Colliding IDs in separate tables must not turn an admin into a teacher
        self.assertEqual(self.admin.id, self.teacher.id)
        teacher_none = get_logged_in_teacher(self.db, "Bearer admin-token")
        self.assertIsNone(teacher_none)

    def test_get_logged_in_teacher_secretary_id_collision(self):
        colliding_teacher = Teacher(id=self.secretary.id, mobile="09120000002")
        self.db.add(colliding_teacher)
        self.db.commit()

        self.assertIsNone(get_logged_in_teacher(self.db, "Bearer sec-token"))
        summary = get_financial_summary(
            user_type="institute", authorization="Bearer sec-token",
            db=self.db, sub_role="secretary",
        )
        self.assertEqual(summary["user_type"], "institute")

    def test_get_logged_in_teacher_direct_session_mapping(self):
        session = self.db.query(UserSession).filter(UserSession.token == "teacher-token").first()
        session.teacher_id = self.teacher.id
        self.teacher.mobile = "09120000009"
        self.db.commit()

        # Explicit mapping must still work after the teacher's mobile changes
        teacher = get_logged_in_teacher(self.db, "Bearer teacher-token")
        self.assertIsNotNone(teacher)
        self.assertEqual(teacher.id, self.teacher.id)

    def test_get_logged_in_teacher_legacy_id_fallback(self):
        legacy_teacher = Teacher(id=self.teacher_user.id, mobile="09120000003")
        self.db.add(legacy_teacher)
        self.db.commit()

        # Mobile mapping takes priority over an incidental ID collision
        teacher = get_logged_in_teacher(self.db, "Bearer teacher-token")
        self.assertIsNotNone(teacher)
        self.assertEqual(teacher.id, self.teacher.id)

        # A verified teacher user may use the legacy ID when mobile mapping is absent
        self.teacher_user.username = "legacy-teacher"
        self.db.commit()
        teacher = get_logged_in_teacher(self.db, "Bearer teacher-token")
        self.assertIsNotNone(teacher)
        self.assertEqual(teacher.id, legacy_teacher.id)

        # Session sub_role alone must not enable fallback for a non-teacher User
        self.teacher_user.role = "admin"
        self.db.commit()
        self.assertIsNone(get_logged_in_teacher(self.db, "Bearer teacher-token"))

    def test_get_logged_in_teacher_missing_user_id_collision(self):
        self.assertEqual(self.admin.id, self.teacher.id)
        self.db.delete(self.admin)
        self.db.commit()

        # An orphaned session cannot identify a teacher by a coincident ID
        self.assertIsNone(get_logged_in_teacher(self.db, "Bearer admin-token"))


if __name__ == "__main__":
    unittest.main()
