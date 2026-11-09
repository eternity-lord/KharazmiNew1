# test_class_details_null_data.py
# Regression tests for «خطا در دریافت لیست/اطلاعات کلاس»:
# GET /classes/{id}/details must stay controlled for -1/0/deleted/no-permission ids,
# and legacy NULL data (total_tuition / total_paid / student names / branch_id)
# must not cause 500s — without changing any stored amount.
import datetime
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models import Base, Branch, Course, Enrollment, Student, Teacher, User, UserSession
from routers.classes import get_class_details


class TestClassDetailsNullData(unittest.TestCase):
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

        self.admin = User(username="admin", password="x", full_name="مدیر", role="admin", sub_role="admin", branch_id=1)
        self.teacher_owner = Teacher(first_name="مریم", last_name="مالک", mobile="09120000001", national_code="0012345678", is_approved=True)
        self.teacher_other = Teacher(first_name="سارا", last_name="دیگر", mobile="09120000002", national_code="0012345679", is_approved=True)
        self.teacher_owner_user = User(username="09120000001", password="x", full_name="معلم مالک", role="teacher", sub_role="teacher")
        self.teacher_other_user = User(username="09120000002", password="x", full_name="معلم دیگر", role="teacher", sub_role="teacher")
        self.student_user = User(username="09120000003", password="x", full_name="شاگرد", role="student", sub_role="student")
        self.db.add_all([self.admin, self.teacher_owner, self.teacher_other, self.teacher_owner_user, self.teacher_other_user, self.student_user])
        self.db.flush()

        self.student = Student(first_name="علی", last_name="دانش‌آموز", national_code="0012345680", student_mobile="09121111111",
                               wallet_teacher=0, wallet_institute=0, wallet_balance=0)
        self.course = Course(title="ریاضی", code="200001", teacher_id=self.teacher_owner.id, is_admin_approved=True,
                             is_deleted=False, grade_level="دهم", class_time="16:00-17:30", days_of_week="شنبه",
                             teacher_session_price=100000, branch_id=1)
        self.db.add_all([self.student, self.course])
        self.db.flush()

        self.db.add_all([
            UserSession(token="admin-token", user_id=self.admin.id, sub_role="admin", created_at=datetime.datetime.now()),
            UserSession(token="owner-token", user_id=self.teacher_owner_user.id, sub_role="teacher", created_at=datetime.datetime.now()),
            UserSession(token="other-token", user_id=self.teacher_other_user.id, sub_role="teacher", created_at=datetime.datetime.now()),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _add_enrollment(self, student=None, course=None, total_tuition=1000000, total_paid=0, **kw):
        enrollment = Enrollment(student_id=(student or self.student).id, course_id=(course or self.course).id,
                                register_date="1405/06/01", shift="عصر",
                                total_tuition=total_tuition, total_paid=total_paid, **kw)
        self.db.add(enrollment)
        self.db.commit()
        return enrollment

    @staticmethod
    def _force_legacy_null(enrollment, field):
        """Column default=0 را دور می‌زنیم تا رکورد legacy واقعی (NULL) شبیه‌سازی شود."""
        from sqlalchemy import text
        session = enrollment._sa_instance_state.session
        session.execute(text(f"UPDATE enrollments SET {field} = NULL WHERE id = :id"), {"id": enrollment.id})
        session.commit()
        session.expire_all()

    # ------------------------------------------------------------------
    # 1. class_id معتبر و کلاس فعال → 200
    # ------------------------------------------------------------------
    def test_valid_class_returns_200(self):
        self._add_enrollment(total_paid=500000)
        result = get_class_details(course_id=self.course.id, db=self.db, authorization="Bearer admin-token", sub_role="admin")
        self.assertEqual(result["course_info"].id, self.course.id)
        self.assertEqual(len(result["students"]), 1)
        row = result["students"][0]
        self.assertEqual(row["student_name"], "علی دانش‌آموز")
        self.assertEqual(row["total_tuition"], 1000000)
        self.assertEqual(row["paid"], 500000)
        self.assertEqual(row["debt"], 500000)

    # ------------------------------------------------------------------
    # 2. class_id برابر -1 یا 0 → پاسخ کنترل‌شده (404 JSON، نه 500)
    # ------------------------------------------------------------------
    def test_class_id_minus_one_is_controlled_404(self):
        with self.assertRaises(HTTPException) as ctx:
            get_class_details(course_id=-1, db=self.db, authorization="Bearer admin-token", sub_role="admin")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_class_id_zero_is_controlled_404(self):
        with self.assertRaises(HTTPException) as ctx:
            get_class_details(course_id=0, db=self.db, authorization="Bearer admin-token", sub_role="admin")
        self.assertEqual(ctx.exception.status_code, 404)

    # ------------------------------------------------------------------
    # 3. کلاس حذف‌شده → 404 (بدون تغییر)
    # ------------------------------------------------------------------
    def test_deleted_class_still_404(self):
        self.course.is_deleted = True
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            get_class_details(course_id=self.course.id, db=self.db, authorization="Bearer admin-token", sub_role="admin")
        self.assertEqual(ctx.exception.status_code, 404)

    # ------------------------------------------------------------------
    # 4. معلم غیرمالک → 403 (بدون تغییر)
    # ------------------------------------------------------------------
    def test_non_owner_teacher_403(self):
        with self.assertRaises(HTTPException) as ctx:
            get_class_details(course_id=self.course.id, db=self.db, authorization="Bearer other-token", sub_role="teacher")
        self.assertEqual(ctx.exception.status_code, 403)

    def test_owner_teacher_200(self):
        self._add_enrollment()
        result = get_class_details(course_id=self.course.id, db=self.db, authorization="Bearer owner-token", sub_role="teacher")
        self.assertEqual(len(result["students"]), 1)

    # ------------------------------------------------------------------
    # 5. نقش غیرمجاز → 403 (بدون تغییر)
    # ------------------------------------------------------------------
    def test_unauthorized_role_403(self):
        with self.assertRaises(HTTPException) as ctx:
            get_class_details(course_id=self.course.id, db=self.db, authorization=None, sub_role="student")
        self.assertEqual(ctx.exception.status_code, 403)

    # ------------------------------------------------------------------
    # 6. enrollment با total_tuition=NULL → بدون 500 (مثل 0)
    # ------------------------------------------------------------------
    def test_null_total_tuition_no_500(self):
        enrollment = self._add_enrollment(total_tuition=None, total_paid=0)
        self._force_legacy_null(enrollment, "total_tuition")
        self.assertIsNone(self.db.get(Enrollment, enrollment.id).total_tuition)  # داده‌ی DB دست‌نخورده
        result = get_class_details(course_id=self.course.id, db=self.db, authorization="Bearer admin-token", sub_role="admin")
        row = result["students"][0]
        self.assertEqual(row["total_tuition"], 0)
        self.assertEqual(row["debt"], 0)

    def test_null_total_tuition_with_percentage_discount(self):
        # حتی با درصد تخفیف، total_tuition=NULL نباید crash کند.
        enrollment = self._add_enrollment(total_tuition=None, discount_type="percentage", discount_value=10)
        self._force_legacy_null(enrollment, "total_tuition")
        result = get_class_details(course_id=self.course.id, db=self.db, authorization="Bearer admin-token", sub_role="admin")
        self.assertEqual(result["students"][0]["total_tuition"], 0)

    # ------------------------------------------------------------------
    # 7. enrollment با total_paid=NULL → بدون 500 (مثل 0)
    # ------------------------------------------------------------------
    def test_null_total_paid_no_500(self):
        enrollment = self._add_enrollment(total_tuition=1000000, total_paid=None)
        self._force_legacy_null(enrollment, "total_paid")
        self.assertIsNone(self.db.get(Enrollment, enrollment.id).total_paid)  # داده‌ی DB دست‌نخورده
        result = get_class_details(course_id=self.course.id, db=self.db, authorization="Bearer admin-token", sub_role="admin")
        row = result["students"][0]
        self.assertEqual(row["paid"], 0)
        # Contractual enrollment debt remains visible even without a session charge.
        self.assertEqual(row["debt"], 1000000)

    def test_both_money_fields_null_no_500(self):
        enrollment = self._add_enrollment(total_tuition=None, total_paid=None)
        self._force_legacy_null(enrollment, "total_tuition")
        self._force_legacy_null(enrollment, "total_paid")
        result = get_class_details(course_id=self.course.id, db=self.db, authorization="Bearer admin-token", sub_role="admin")
        row = result["students"][0]
        self.assertEqual(row["total_tuition"], 0)
        self.assertEqual(row["paid"], 0)
        self.assertEqual(row["debt"], 0)

    # ------------------------------------------------------------------
    # 8. کلاس بدون دانش‌آموز → 200 با لیست خالی
    # ------------------------------------------------------------------
    def test_class_without_students_empty_list(self):
        result = get_class_details(course_id=self.course.id, db=self.db, authorization="Bearer admin-token", sub_role="admin")
        self.assertEqual(result["students"], [])

    # ------------------------------------------------------------------
    # 9. کلاس با branch_id=NULL → رفتار فعلی امن (200)
    # ------------------------------------------------------------------
    def test_class_null_branch_id_still_works(self):
        self.course.branch_id = None
        self.db.commit()
        result = get_class_details(course_id=self.course.id, db=self.db, authorization="Bearer admin-token", sub_role="admin")
        self.assertEqual(result["course_info"].id, self.course.id)

    # ------------------------------------------------------------------
    # 10. نام دانش‌آموز NULL → بدون 500، فال‌بک نمایشی امن
    # ------------------------------------------------------------------
    def test_null_student_names_no_500(self):
        self._add_enrollment()  # رکورد پایه برای شاگرد سالم
        anonymous = Student(first_name=None, last_name=None, national_code="0012345681", student_mobile="09121111112",
                            wallet_teacher=0, wallet_institute=0, wallet_balance=0)
        self.db.add(anonymous)
        self.db.commit()
        self._add_enrollment(student=anonymous)

        result = get_class_details(course_id=self.course.id, db=self.db, authorization="Bearer admin-token", sub_role="admin")
        names = {row["student_id"]: row["student_name"] for row in result["students"]}
        self.assertEqual(names[anonymous.id], "نامشخص")
        self.assertEqual(names[self.student.id], "علی دانش‌آموز")
        for name in names.values():
            self.assertNotIn("None", name)

    def test_one_null_name_does_not_break_other_rows(self):
        self._add_enrollment()  # رکورد پایه برای شاگرد سالم
        half = Student(first_name="زهرا", last_name=None, national_code="0012345682", student_mobile="09121111113",
                       wallet_teacher=0, wallet_institute=0, wallet_balance=0)
        self.db.add(half)
        self.db.commit()
        self._add_enrollment(student=half)

        result = get_class_details(course_id=self.course.id, db=self.db, authorization="Bearer admin-token", sub_role="admin")
        self.assertEqual(len(result["students"]), 2)
        names = {row["student_id"]: row["student_name"] for row in result["students"]}
        self.assertEqual(names[half.id], "زهرا")
        self.assertEqual(names[self.student.id], "علی دانش‌آموز")


if __name__ == "__main__":
    unittest.main()
