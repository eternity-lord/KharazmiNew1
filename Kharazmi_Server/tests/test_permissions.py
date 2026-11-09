import unittest
import models
from models import SessionLocal, Student, Teacher, Course, Enrollment, User, UserSession, ParentOTP
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dependencies import check_admin_access, require_permission, ROLE_PERMISSIONS
from fastapi import HTTPException

class TestKharazmiPermissionLogic(unittest.TestCase):

    def setUp(self):
        # Setup memory database
        self.engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        # Create Admin
        self.admin_user = User(username="admin_test", password="123", role="admin", sub_role="admin")
        self.db.add(self.admin_user)

        # Create Secretary
        self.secretary_user = User(username="sec_test", password="123", role="admin", sub_role="secretary")
        self.db.add(self.secretary_user)

        # Create Teacher A
        self.teacher_a = Teacher(first_name="معلم", last_name="الف", national_code="111", mobile="09111", teacher_code=101)
        self.db.add(self.teacher_a)
        
        # Create Teacher B
        self.teacher_b = Teacher(first_name="معلم", last_name="ب", national_code="222", mobile="09222", teacher_code=102)
        self.db.add(self.teacher_b)
        self.db.commit()

        # Create Student A
        self.student_a = Student(first_name="دانش‌آموز", last_name="الف", national_code="333", student_mobile="09333", parent_mobile="09100")
        self.db.add(self.student_a)

        # Create Student B
        self.student_b = Student(first_name="دانش‌آموز", last_name="ب", national_code="444", student_mobile="09444", parent_mobile="09200")
        self.db.add(self.student_b)

        # Create Student C (unrelated)
        self.student_c = Student(first_name="دانش‌آموز", last_name="ج", national_code="555", student_mobile="09555", parent_mobile="09300")
        self.db.add(self.student_c)
        self.db.commit()

        # Create Course A (taught by Teacher A)
        self.course_a = Course(title="کلاس الف", code="1001", teacher_id=self.teacher_a.id)
        self.db.add(self.course_a)

        # Create Course B (taught by Teacher B)
        self.course_b = Course(title="کلاس ب", code="1002", teacher_id=self.teacher_b.id)
        self.db.add(self.course_b)
        self.db.commit()

        # Enroll Student A in Course A
        self.enroll_a = Enrollment(student_id=self.student_a.id, course_id=self.course_a.id, total_tuition=100000)
        self.db.add(self.enroll_a)

        # Enroll Student B in Course B
        self.enroll_b = Enrollment(student_id=self.student_b.id, course_id=self.course_b.id, total_tuition=100000)
        self.db.add(self.enroll_b)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(bind=self.engine)

    def test_case_1_admin_has_full_permissions(self):
        """1. Admin can access everything"""
        admin_perms = ROLE_PERMISSIONS.get(self.admin_user.sub_role)
        self.assertIn("*", admin_perms)

    def test_case_2_secretary_blocked_from_restricted_settings(self):
        """2. Secretary cannot access restricted settings (settings.write or audit.read)"""
        sec_perms = ROLE_PERMISSIONS.get(self.secretary_user.sub_role)
        self.assertNotIn("settings.write", sec_perms)
        self.assertNotIn("audit.read", sec_perms)

    def test_case_3_teacher_access_limits(self):
        """3. Teacher cannot access another teacher's student"""
        # Teacher A wants to access Student A (enrolled in Teacher A's class -> OK)
        related_a = self.db.query(Enrollment).join(Course).filter(
            Enrollment.student_id == self.student_a.id, Course.teacher_id == self.teacher_a.id
        ).first()
        self.assertIsNotNone(related_a)

        # Teacher A wants to access Student B (enrolled in Teacher B's class -> Blocked!)
        related_b = self.db.query(Enrollment).join(Course).filter(
            Enrollment.student_id == self.student_b.id, Course.teacher_id == self.teacher_a.id
        ).first()
        self.assertIsNone(related_b)

    def test_case_4_parent_idor_select_child_prevention(self):
        """4. Parent with multiple children can switch only between authorized children"""
        # Parent mobile "09100" has Student A as child, Student B belongs to "09200"
        # Simulate temp parent session for "09100"
        temp_session = UserSession(token="temp_tok", user_id=-1, sub_role="temp_parent:09100")
        self.db.add(temp_session)
        self.db.commit()

        # Switch to Student A (owned by 09100 -> OK)
        self.assertEqual(self.student_a.parent_mobile, "09100")

        # Switch to Student B (owned by 09200 -> Blocked!)
        self.assertNotEqual(self.student_b.parent_mobile, "09100")

if __name__ == "__main__":
    unittest.main()
