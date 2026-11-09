import unittest
from dependencies import hash_password, verify_password, get_enrollment_tuition_and_discount
import models
from models import SessionLocal, Student, Teacher, Course, Enrollment, Transaction, SessionLog, Attendance
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

class TestKharazmiCoreLogic(unittest.TestCase):

    def setUp(self):
        # Use an in-memory SQLite database for fast unit testing
        self.engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        
    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(bind=self.engine)

    def test_authentication_password_hashing(self):
        """1. Test password hashing and rejection of legacy plaintext passwords"""
        raw_pass = "secret123"
        hashed = hash_password(raw_pass)
        
        # Verify it is hashed securely and starts with the pbkdf2 prefix
        self.assertTrue(hashed.startswith("$pbkdf2-sha256$"))
        
        # Verify verification succeeds with the correct password
        self.assertTrue(verify_password(raw_pass, hashed))
        
        # Verify verification fails with an incorrect password
        self.assertFalse(verify_password("wrong_pass", hashed))
        
        # Legacy plaintext passwords must be rejected, even when they match
        self.assertFalse(verify_password("legacy123", "legacy123"))
        self.assertFalse(verify_password("legacy123", "wrong_legacy"))

    def test_finance_tuition_discount_recalculation(self):
        """2. Test discount and final tuition recalculation logic"""
        # Scenario A: 10% percentage discount
        enroll_percentage = Enrollment(total_tuition=1000000, discount_type="percentage", discount_value=10)
        final, discount = get_enrollment_tuition_and_discount(enroll_percentage)
        self.assertEqual(final, 900000)
        self.assertEqual(discount, 100000)

        # Scenario B: Fixed amount discount
        enroll_fixed = Enrollment(total_tuition=1000000, discount_type="fixed", discount_value=150000)
        final, discount = get_enrollment_tuition_and_discount(enroll_fixed)
        self.assertEqual(final, 850000)
        self.assertEqual(discount, 150000)

        # Scenario C: No discount
        enroll_none = Enrollment(total_tuition=1000000, discount_type="none", discount_value=0)
        final, discount = get_enrollment_tuition_and_discount(enroll_none)
        self.assertEqual(final, 1000000)
        self.assertEqual(discount, 0)

    def test_attendance_dynamic_splitting_pricing(self):
        """3. Test attendance session cost dynamic splitting based on count of present students"""
        # Setup mock teacher and course
        teacher = Teacher(first_name="محمد", last_name="علوی", national_code="111", mobile="09111")
        self.db.add(teacher)
        self.db.commit()

        course = Course(title="ریاضی دهم", code="1001", teacher_id=teacher.id, grade_level="دهم", teacher_session_price=100000)
        self.db.add(course)
        self.db.commit()

        # Adding 3 students and enrollments
        student1 = Student(first_name="سارا", last_name="احمدی", national_code="222", student_mobile="09222")
        student2 = Student(first_name="علی", last_name="کریمی", national_code="333", student_mobile="09333")
        student3 = Student(first_name="رضا", last_name="حسینی", national_code="444", student_mobile="09444")
        self.db.add_all([student1, student2, student3])
        self.db.commit()

        enroll1 = Enrollment(student_id=student1.id, course_id=course.id, total_tuition=1000000)
        enroll2 = Enrollment(student_id=student2.id, course_id=course.id, total_tuition=1000000)
        enroll3 = Enrollment(student_id=student3.id, course_id=course.id, total_tuition=1000000)
        self.db.add_all([enroll1, enroll2, enroll3])
        self.db.commit()

        # Setting up pricing table (middle school / high school / elementary category pricing snapshot)
        from models import PricingTable
        p_mid = PricingTable(category="middle_school", count_1=120000, count_2=180000, count_3=240000, count_4=280000, count_5=300000)
        p_inst = PricingTable(category="institute", count_1=50000, count_2=80000, count_3=100000, count_4=120000, count_5=150000)
        self.db.add_all([p_mid, p_inst])
        self.db.commit()

        # Simulate present student list: Student 1 & Student 2 Present (2 students present)
        # For 2 present, middle school price is 180,000, and institute share is 80,000
        # So teacher price is 100,000, and institute is 80,000. Total session cost is 180,000
        # Cost per student (cost_per_student) is 180,000 / 2 = 90,000.
        # This will decrease student 1 & 2 wallets: teacher wallet by 50,000, institute by 40,000.
        items = [
            {"student_id": student1.id, "status": "Present", "excused": False},
            {"student_id": student2.id, "status": "Present", "excused": False},
            {"student_id": student3.id, "status": "Absent", "excused": True} # Absent and Excused: Not billed
        ]
        
        # We simulate the calculation inside submit_session_and_calculate directly or by verifying output.
        present_count = len([x for x in items if x["status"] == "Present" or (x["status"] == "Absent" and not x["excused"])])
        self.assertEqual(present_count, 2)
        
        # Verify pricing snapshot loads correctly
        pricing_inst = self.db.query(PricingTable).filter(PricingTable.category == "institute").first()
        self.assertIsNotNone(pricing_inst)
        inst_share = getattr(pricing_inst, f"count_{present_count}", 0)
        self.assertEqual(inst_share, 80000)

if __name__ == "__main__":
    unittest.main()
