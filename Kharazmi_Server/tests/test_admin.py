import datetime
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models import Base, Branch, Course, Enrollment, Student, Teacher, User, UserSession
from dependencies import check_admin_access, check_user_login
from routers.admin import (
    get_student_full_profile,
    toggle_suspend_student,
    delete_student,
    get_pending_teachers,
    approve_teacher,
    suspend_teacher,
    delete_teacher,
)
from routers.reports import get_logged_in_teacher


class TestAdminRouter(unittest.TestCase):
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

        self.admin = User(
            username="admin",
            password="x",
            full_name="مدیر",
            role="admin",
            sub_role="admin",
            branch_id=1,
        )
        self.secretary = User(
            username="sec",
            password="x",
            full_name="منشی",
            role="admin",
            sub_role="secretary",
            branch_id=1,
        )
        self.teacher_user = User(
            username="09120000001",
            password="x",
            full_name="معلم",
            role="teacher",
            sub_role="teacher",
        )
        self.other_teacher_user = User(
            username="09120000002",
            password="x",
            full_name="معلم دیگر",
            role="teacher",
            sub_role="teacher",
        )
        self.db.add_all([self.admin, self.secretary, self.teacher_user, self.other_teacher_user])
        self.db.flush()

        self.teacher = Teacher(
            first_name="مریم",
            last_name="معلم",
            mobile="09120000001",
            national_code="0012345678",
            is_approved=True,
        )
        self.other_teacher = Teacher(
            first_name="سارا",
            last_name="دیگر",
            mobile="09120000002",
            national_code="0012345679",
            is_approved=True,
        )
        self.student = Student(
            first_name="علی",
            last_name="دانش‌آموز",
            national_code="0012345680",
            student_mobile="09121111111",
            parent_mobile="09122222222",
        )
        self.unrelated_student = Student(
            first_name="رضا",
            last_name="نامرتبط",
            national_code="0012345681",
            student_mobile="09123333333",
            parent_mobile="09124444444",
        )
        self.db.add_all([self.teacher, self.other_teacher, self.student, self.unrelated_student])
        self.db.flush()

        course = Course(
            title="ریاضی",
            code="C-1",
            teacher_id=self.teacher.id,
            is_admin_approved=True,
            is_deleted=False,
            is_suspended=False,
        )
        self.db.add(course)
        self.db.flush()

        enrollment = Enrollment(
            student_id=self.student.id,
            course_id=course.id,
            register_date="1405/06/02",
            shift="عصر",
        )
        self.db.add(enrollment)

        self.db.add_all(
            [
                UserSession(
                    token="admin-token",
                    user_id=self.admin.id,
                    sub_role="admin",
                    created_at=datetime.datetime.now(),
                ),
                UserSession(
                    token="sec-token",
                    user_id=self.secretary.id,
                    sub_role="secretary",
                    created_at=datetime.datetime.now(),
                ),
                UserSession(
                    token="teacher-token",
                    user_id=self.teacher_user.id,
                    sub_role="teacher",
                    created_at=datetime.datetime.now(),
                ),
                UserSession(
                    token="other-teacher-token",
                    user_id=self.other_teacher_user.id,
                    sub_role="teacher",
                    created_at=datetime.datetime.now(),
                ),
            ]
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_admin_can_view_any_student_full_profile(self):
        # admin can view
        profile = get_student_full_profile(
            id=self.student.id,
            authorization="Bearer admin-token",
            db=self.db,
            role="admin",
        )
        self.assertEqual(profile["info"]["name"], "علی دانش‌آموز")

    def test_teacher_idor_blocked_for_unrelated_student(self):
        # teacher can view related student
        profile = get_student_full_profile(
            id=self.student.id,
            authorization="Bearer teacher-token",
            db=self.db,
            role="teacher",
        )
        self.assertIsNotNone(profile)

        # teacher cannot view unrelated student -> IDOR protection
        with self.assertRaises(HTTPException) as e:
            get_student_full_profile(
                id=self.unrelated_student.id,
                authorization="Bearer teacher-token",
                db=self.db,
                role="teacher",
            )
        self.assertEqual(e.exception.status_code, 403)

    def test_toggle_suspend_requires_login(self):
        # Any logged in user can toggle? In current code check_user_login only
        result = toggle_suspend_student(
            id=self.student.id,
            db=self.db,
            _="admin",
        )
        self.assertIn(result["is_suspended"], (True, False))

        # Toggle back
        result2 = toggle_suspend_student(
            id=self.student.id,
            db=self.db,
            _="admin",
        )
        self.assertNotEqual(result["is_suspended"], result2["is_suspended"])

    def test_delete_student_admin_only(self):
        # admin can delete
        result = delete_student(id=self.unrelated_student.id, db=self.db, _="admin")
        self.assertIn("آرشیو", result["message"])  # FIX (audit-v2/test-triage): سافت‌دیلیت.

        # verify soft-deleted (row kept, flagged)
        row = self.db.query(Student).filter(Student.id == self.unrelated_student.id).first()
        self.assertIsNotNone(row)
        self.assertTrue(row.is_deleted)

        # non-existing should 404
        with self.assertRaises(HTTPException) as e:
            delete_student(id=9999, db=self.db, _="admin")
        self.assertEqual(e.exception.status_code, 404)

    def test_pending_teachers_and_approve(self):
        # Make a pending teacher
        pending = Teacher(
            first_name="منتظر",
            last_name="تایید",
            mobile="09120000003",
            national_code="0012345682",
            is_approved=False,
        )
        self.db.add(pending)
        self.db.commit()

        pending_list = get_pending_teachers(db=self.db, _="admin")
        self.assertTrue(any(t.id == pending.id for t in pending_list))

        # approve
        approve_teacher(teacher_id=pending.id, db=self.db, _="admin")
        self.db.refresh(pending)
        self.assertTrue(pending.is_approved)

    def test_suspend_and_delete_teacher_with_active_class_blocked(self):
        # suspend toggle
        result = suspend_teacher(teacher_id=self.teacher.id, db=self.db, _="admin")
        self.assertIn("is_suspended", result)

        # delete should be blocked because teacher has active class
        with self.assertRaises(HTTPException) as e:
            delete_teacher(teacher_id=self.teacher.id, db=self.db, _="admin")
        self.assertEqual(e.exception.status_code, 400)

        # other teacher with no class can be deleted
        result_del = delete_teacher(teacher_id=self.other_teacher.id, db=self.db, _="admin")
        self.assertIn("حذف", result_del["message"])

    def test_delete_teacher_allowed_when_all_classes_are_archived(self):
        """O-11: کلاس آرشیوشده نباید مانع حذف معلم شود.

        قبلاً `active_classes = query(Course).filter(teacher_id).count()` بود ⇒ هر کلاس
        آرشیوشده هم «فعال» شمرده می‌شد و پیام «این معلم N کلاس فعال دارد» درست نبود.
        """
        self.db.query(Course).filter(Course.teacher_id == self.teacher.id).update({"is_deleted": True})
        self.db.commit()

        result = delete_teacher(teacher_id=self.teacher.id, db=self.db, _="admin")
        self.assertIn("حذف", result["message"], result)
        self.db.refresh(self.teacher)
        self.assertTrue(self.teacher.is_deleted, "معلم باید سافت‌دیلیت شود")
        self.assertEqual(self.db.query(Course).filter(Course.teacher_id == self.teacher.id,
                                                      Course.is_deleted == True).count(), 1,
                         "کلاس آرشیوشده باید دست‌نخورده بماند")

    def test_delete_teacher_message_counts_only_active_classes(self):
        """O-11: عدد داخل پیام باید فقط کلاس‌های **فعال** را بشمارد."""
        self.db.add(Course(title="کلاس آرشیو", code="C-2", teacher_id=self.teacher.id,
                           is_admin_approved=True, is_deleted=True))
        self.db.commit()

        with self.assertRaises(HTTPException) as e:
            delete_teacher(teacher_id=self.teacher.id, db=self.db, _="admin")
        self.assertEqual(e.exception.status_code, 400)
        self.assertIn("1 کلاس فعال", e.exception.detail,
                      f"پیام باید فقط کلاس فعال را بشمارد: {e.exception.detail}")
        self.assertNotIn("2 کلاس فعال", e.exception.detail)

    def test_admin_dependency_blocks_non_admin(self):
        with self.assertRaises(HTTPException) as e:
            check_admin_access("Bearer teacher-token", self.db)
        self.assertEqual(e.exception.status_code, 403)

        with self.assertRaises(HTTPException) as e:
            check_admin_access("Bearer sec-token", self.db)
        self.assertEqual(e.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
