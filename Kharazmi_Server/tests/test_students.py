import datetime
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models import Base, Branch, Course, Enrollment, Student, Teacher, User, UserSession, Grade, Installment, SequenceCounter
from routers.students import (
    search_students,
    get_student_profile,
    update_student,
    get_student_grades,
    get_student_installments,
    get_student_my_profile,
)
from schemas import StudentUpdate


class TestStudentsRouter(unittest.TestCase):
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
        self.db.add(SequenceCounter(name="student", current_value=100001))

        self.admin = User(username="admin", password="x", full_name="مدیر", role="admin", sub_role="admin", branch_id=1)
        self.teacher_user_a = User(username="09120000001", password="x", full_name="معلم الف", role="teacher", sub_role="teacher")
        self.teacher_user_b = User(username="09120000002", password="x", full_name="معلم ب", role="teacher", sub_role="teacher")
        self.db.add_all([self.admin, self.teacher_user_a, self.teacher_user_b])
        self.db.flush()

        self.teacher_a = Teacher(first_name="مریم", last_name="الف", mobile="09120000001", national_code="0012345678", is_approved=True, teacher_code=101)
        self.teacher_b = Teacher(first_name="سارا", last_name="ب", mobile="09120000002", national_code="0012345679", is_approved=True, teacher_code=102)
        self.student = Student(first_name="علی", last_name="دانش‌آموز", national_code="0012345680", student_mobile="09121111111", parent_mobile="09122222222", wallet_teacher=0, wallet_institute=0, wallet_balance=0)
        self.unrelated_student = Student(first_name="رضا", last_name="نامرتبط", national_code="0012345681", student_mobile="09123333333", parent_mobile="09124444444")
        self.db.add_all([self.teacher_a, self.teacher_b, self.student, self.unrelated_student])
        self.db.flush()

        self.course_a = Course(title="ریاضی", code="200001", teacher_id=self.teacher_a.id, is_admin_approved=True, is_deleted=False, grade_level="دهم", class_time="16:00-17:30", days_of_week="شنبه", teacher_session_price=100000)
        self.db.add(self.course_a)
        self.db.flush()

        self.enrollment = Enrollment(student_id=self.student.id, course_id=self.course_a.id, register_date="1405/06/01", shift="عصر", total_tuition=1000000, total_paid=0)
        self.db.add(self.enrollment)
        self.db.flush()

        self.student_user = User(username=f"student:{self.student.id}", password="x", full_name="کاربر شاگرد", role="student", sub_role="student")
        self.db.add(self.student_user)
        self.db.flush()
        self.student.user_id = self.student_user.id
        self.db.add_all([
            UserSession(token="admin-token", user_id=self.admin.id, sub_role="admin", created_at=datetime.datetime.now()),
            UserSession(token="teacher-a-token", user_id=self.teacher_user_a.id, sub_role="teacher", created_at=datetime.datetime.now()),
            UserSession(token="teacher-b-token", user_id=self.teacher_user_b.id, sub_role="teacher", created_at=datetime.datetime.now()),
            UserSession(token="student-token", user_id=self.student_user.id, sub_role="student", created_at=datetime.datetime.now()),
        ])
        # Add grade and installment for student
        self.db.add(Grade(student_id=self.student.id, course_id=self.course_a.id, teacher_id=self.teacher_a.id, exam_title="میان ترم", score=18, max_score=20, date="1405/06/01", description="خوب"))
        self.db.add(Installment(enrollment_id=self.enrollment.id, amount=500000, due_date="1405/07/01", is_paid=False))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_search_students(self):
        results = search_students(query="دانش", db=self.db, sub_role="admin")
        self.assertTrue(any(r.id == self.student.id for r in results))

    def test_get_student_profile_idor(self):
        # Teacher A can view related student
        profile = get_student_profile(student_id=self.student.id, authorization="Bearer teacher-a-token", db=self.db, role="teacher")
        self.assertEqual(profile["id"], self.student.id)

        # Teacher B cannot view unrelated student
        with self.assertRaises(HTTPException) as e:
            get_student_profile(student_id=self.student.id, authorization="Bearer teacher-b-token", db=self.db, role="teacher")
        self.assertEqual(e.exception.status_code, 403)

        # Admin can view any
        profile_admin = get_student_profile(student_id=self.unrelated_student.id, authorization="Bearer admin-token", db=self.db, role="admin")
        self.assertEqual(profile_admin["id"], self.unrelated_student.id)

    def test_update_student_optimistic_locking(self):
        # First update with correct version
        data = StudentUpdate(first_name="علی‌رضا", version=1)
        result = update_student(student_id=self.student.id, data=data, db=self.db, _="admin")
        self.assertIn("موفقیت", result["message"])
        self.db.refresh(self.student)
        self.assertEqual(self.student.first_name, "علی‌رضا")
        self.assertEqual(self.student.version, 2)

        # Second update with old version should 409
        data_old = StudentUpdate(first_name="علی", version=1)
        with self.assertRaises(HTTPException) as e:
            update_student(student_id=self.student.id, data=data_old, db=self.db, _="admin")
        self.assertEqual(e.exception.status_code, 409)

    def test_get_student_grades_and_installments(self):
        grades = get_student_grades(student_id=self.student.id, db=self.db, authorization="Bearer admin-token", role="admin")
        self.assertIn("grades", grades)
        self.assertEqual(len(grades["grades"]), 1)
        self.assertIn("ریاضی", grades["averages"] or list(grades["grades"][0].values()))

        installments = get_student_installments(student_id=self.student.id, db=self.db, authorization="Bearer admin-token", role="admin")
        self.assertEqual(len(installments), 1)
        self.assertEqual(installments[0]["amount"], 500000)

    def test_student_my_profile_auth(self):
        # Student can view own profile via token
        profile = get_student_my_profile(authorization="Bearer student-token", db=self.db, _="student")
        self.assertIn("info", profile)
        self.assertEqual(profile["info"]["name"], "علی دانش‌آموز")

        # Invalid token should 401
        with self.assertRaises(HTTPException) as e:
            get_student_my_profile(authorization="Bearer invalid-token", db=self.db, _="student")
        self.assertEqual(e.exception.status_code, 401)

    def test_student_not_found(self):
        with self.assertRaises(HTTPException) as e:
            get_student_profile(student_id=9999, authorization="Bearer admin-token", db=self.db, role="admin")
        self.assertEqual(e.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
