import datetime
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models import Base, Branch, Course, Enrollment, Student, Teacher, User, UserSession, SequenceCounter
from routers.classes import (
    create_class,
    get_all_classes,
    get_class_details,
    suspend_class,
    add_enrollment,
    delete_class_endpoint,
    request_class_deletion,
    approve_class_deletion,
    list_class_deletion_requests,
    DeletionRequestCreate,
)
from schemas import CourseCreate, EnrollmentCreate


class TestClassesRouter(unittest.TestCase):
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
        # Seed sequence counter high to avoid collision with manual course code
        self.db.add(SequenceCounter(name="class", current_value=300000))

        self.admin = User(
            username="admin",
            password="x",
            full_name="مدیر",
            role="admin",
            sub_role="admin",
            branch_id=1,
        )
        self.teacher_user = User(
            username="09120000001",
            password="x",
            full_name="معلم الف",
            role="teacher",
            sub_role="teacher",
        )
        self.other_teacher_user = User(
            username="09120000002",
            password="x",
            full_name="معلم ب",
            role="teacher",
            sub_role="teacher",
        )
        self.db.add_all([self.admin, self.teacher_user, self.other_teacher_user])
        self.db.flush()

        self.teacher_a = Teacher(
            first_name="مریم",
            last_name="الف",
            mobile="09120000001",
            national_code="0012345678",
            is_approved=True,
            teacher_code=101,
        )
        self.teacher_b = Teacher(
            first_name="سارا",
            last_name="ب",
            mobile="09120000002",
            national_code="0012345679",
            is_approved=True,
            teacher_code=102,
        )
        self.student = Student(
            first_name="علی",
            last_name="دانش‌آموز",
            national_code="0012345680",
            student_mobile="09121111111",
            wallet_teacher=0,
            wallet_institute=0,
            wallet_balance=0,
        )
        self.db.add_all([self.teacher_a, self.teacher_b, self.student])
        self.db.flush()

        self.db.add_all(
            [
                UserSession(
                    token="admin-token",
                    user_id=self.admin.id,
                    sub_role="admin",
                    created_at=datetime.datetime.now(),
                ),
                UserSession(
                    token="teacher-a-token",
                    user_id=self.teacher_user.id,
                    sub_role="teacher",
                    created_at=datetime.datetime.now(),
                ),
                UserSession(
                    token="teacher-b-token",
                    user_id=self.other_teacher_user.id,
                    sub_role="teacher",
                    created_at=datetime.datetime.now(),
                ),
            ]
        )
        self.db.commit()

        # Create a class for teacher A with manual code not colliding with sequence
        self.course = Course(
            title="ریاضی",
            code="200001",
            teacher_id=self.teacher_a.id,
            is_admin_approved=True,
            is_deleted=False,
            is_suspended=False,
            days_of_week="شنبه",
            class_time="16:00-17:30",
            grade_level="دهم",
            teacher_session_price=100000,
        )
        self.db.add(self.course)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_create_class_and_conflict_detection(self):
        new_course_data = CourseCreate(
            title="فیزیک",
            code="tmp",
            teacher_id=self.teacher_a.id,
            education_type="کنکور",
            grade_level="دهم",
            gender_type="مختلط",
            class_time="18:00-19:30",
            days_of_week="یکشنبه",
            teacher_session_price=100000,
        )
        result = create_class(course=new_course_data, override=False, db=self.db, authorization="Bearer admin-token", sub_role="admin")
        self.assertEqual(result["status"], "success")
        self.assertIn("code", result)

        conflict_data = CourseCreate(
            title="شیمی",
            code="tmp2",
            teacher_id=self.teacher_a.id,
            education_type="کنکور",
            grade_level="دهم",
            gender_type="مختلط",
            class_time="16:00-17:00",
            days_of_week="شنبه",
            teacher_session_price=100000,
        )
        result_conflict = create_class(course=conflict_data, override=False, db=self.db, authorization="Bearer admin-token", sub_role="admin")
        self.assertEqual(result_conflict["status"], "warning")
        self.assertIn("تداخل", result_conflict["message"])

    def test_get_all_classes_and_details(self):
        classes = get_all_classes(db=self.db, _="admin")
        self.assertTrue(len(classes) >= 1)
        # Find our course
        found = [c for c in classes if c["id"] == self.course.id]
        self.assertTrue(len(found) == 1)

        details = get_class_details(course_id=self.course.id, db=self.db, authorization="Bearer admin-token", sub_role="admin")
        self.assertEqual(details["course_info"].id, self.course.id)
        self.assertEqual(details["students"], [])

    def test_add_enrollment_and_duplicate_prevention(self):
        enroll_data = EnrollmentCreate(
            student_id=self.student.id,
            course_id=self.course.id,
            register_date="1405/06/01",
            shift="عصر",
            total_tuition=1000000,
            paid_amount=0,
            payment_method="نقد",
            receiver="مدیر",
        )
        result = add_enrollment(data=enroll_data, db=self.db, sub_role="admin")
        self.assertIn("enrollment_id", result)

        with self.assertRaises(HTTPException) as e:
            add_enrollment(data=enroll_data, db=self.db, sub_role="admin")
        self.assertEqual(e.exception.status_code, 400)

    def test_suspend_toggle(self):
        result = suspend_class(course_id=self.course.id, db=self.db, _="admin")
        self.assertTrue(result["is_suspended"])

        result2 = suspend_class(course_id=self.course.id, db=self.db, _="admin")
        self.assertFalse(result2["is_suspended"])

    def test_delete_class_idor_teacher_cannot_delete_others(self):
        # Ensure no debt and enrollment exists
        self.student.wallet_teacher = 0
        self.student.wallet_institute = 0
        self.db.commit()

        if not self.db.query(Enrollment).filter(Enrollment.course_id == self.course.id, Enrollment.student_id == self.student.id).first():
            self.db.add(
                Enrollment(
                    student_id=self.student.id,
                    course_id=self.course.id,
                    register_date="1405/06/01",
                    shift="عصر",
                    total_tuition=1000000,
                    # FIX: Bug 16 - a no-debt fixture must pay tuition, not merely zero wallets.
                    total_paid=1000000,
                )
            )
            self.db.commit()

        # Teacher A can request deletion of own class -> pending (not applied yet)
        result = request_class_deletion(
            course_id=self.course.id,
            data=DeletionRequestCreate(forgive_session_charges=True),
            authorization="Bearer teacher-a-token",
            db=self.db,
            sub_role="teacher",
        )
        self.assertEqual(result["status"], "pending")
        self.assertFalse(self.db.query(Course).filter(Course.id == self.course.id).first().is_deleted)

        # Admin approves -> class deleted
        approved = approve_class_deletion(request_id=result["request_id"], db=self.db, _="admin")
        self.assertIn("تایید", approved["message"])
        self.assertTrue(self.db.query(Course).filter(Course.id == self.course.id).first().is_deleted)

        self.course.is_deleted = False
        self.db.commit()

        # Teacher B cannot request for A's class -> IDOR
        with self.assertRaises(HTTPException) as e:
            request_class_deletion(
                course_id=self.course.id,
                data=DeletionRequestCreate(forgive_session_charges=True),
                authorization="Bearer teacher-b-token",
                db=self.db,
                sub_role="teacher",
            )
        self.assertEqual(e.exception.status_code, 403)

    def test_delete_class_with_debt_requires_admin_approval(self):
        # Create enrollment linking debt student to course
        self.db.query(Enrollment).filter(Enrollment.course_id == self.course.id).delete()
        self.db.commit()
        self.db.add(
            Enrollment(
                student_id=self.student.id,
                course_id=self.course.id,
                register_date="1405/06/01",
                shift="عصر",
                total_tuition=1000000,
                total_paid=0,
            )
        )
        self.student.wallet_teacher = -500000
        self.student.wallet_institute = 0
        self.student.wallet_balance = -500000
        self.db.commit()

        # Teacher CAN request even with debt (request_free) -> pending, debt visible in snapshot
        result = request_class_deletion(
            course_id=self.course.id,
            data=DeletionRequestCreate(forgive_session_charges=False),
            authorization="Bearer teacher-a-token",
            db=self.db,
            sub_role="teacher",
        )
        self.assertEqual(result["status"], "pending")
        pending_list = list_class_deletion_requests(status="pending", db=self.db, _="admin")
        self.assertEqual(len(pending_list), 1)
        self.assertGreater(pending_list[0]["snapshot"]["totals"]["total_debt"], 0)
        self.assertFalse(self.db.query(Course).filter(Course.id == self.course.id).first().is_deleted)

        # Admin direct delete still works immediately
        result = delete_class_endpoint(course_id=self.course.id, db=self.db, _="admin")
        self.assertIn("حذف", result["message"])

        # Approving the now-stale request closes it instead of double-applying
        with self.assertRaises(HTTPException) as e:
            approve_class_deletion(request_id=pending_list[0]["request_id"], db=self.db, _="admin")
        self.assertEqual(e.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
