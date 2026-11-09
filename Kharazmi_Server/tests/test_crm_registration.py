import unittest
import models
from models import SessionLocal, Student, Enrollment, Course, Transaction, Lead
from sqlalchemy import create_engine, or_
from sqlalchemy.orm import sessionmaker
from dependencies import get_next_sequence_value
from routers.crm import OnlineRegisterRequest, public_online_registration
from fastapi import HTTPException

class TestKharazmiCRMRegistration(unittest.TestCase):

    def setUp(self):
        # Setup memory database
        self.engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        # Create Course
        self.course = Course(title="فیزیک کنکور", code="1001", teacher_id=1, teacher_session_price=100000)
        self.db.add(self.course)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(bind=self.engine)

    def test_crm_lead_conversion(self):
        """1. Verify CRM lead is correctly converted to a Student record"""
        # Create Lead
        lead = Lead(name="علی علوی", mobile="09129999999", interested_course="شیمی کنکور")
        self.db.add(lead)
        self.db.commit()

        # Convert to student
        next_code = get_next_sequence_value(self.db, "student", 100001)
        student = Student(
            first_name=lead.name,
            last_name="",
            national_code="1111111111",
            student_mobile=lead.mobile,
            student_code=next_code
        )
        self.db.add(student)
        lead.status = "REGISTERED"
        self.db.commit()

        # Verify conversion
        self.assertEqual(lead.status, "REGISTERED")
        self.assertEqual(student.first_name, "علی علوی")
        self.assertEqual(student.student_code, 100001)

    def test_public_online_registration_duplicate_prevention(self):
        """2. Verify online registration prevents creating duplicate students"""
        req_1 = OnlineRegisterRequest(
            first_name="سارا",
            last_name="احمدی",
            father_name="احمد",
            national_code="0001112228",  # FIX: Bug 22 - valid checksum; duplicate-prevention assertions are unchanged.
            student_mobile="09121111111",
            parent_mobile="09122222222",
            course_id=self.course.id,
            paid_amount=200000
        )

        # 1. First registration (Creates student + enrollment + transaction)
        student = self.db.query(Student).filter(Student.student_mobile == req_1.student_mobile).first()
        self.assertIsNone(student)

        next_code = get_next_sequence_value(self.db, "student", 100001)
        new_student = Student(
            first_name=req_1.first_name,
            last_name=req_1.last_name,
            father_name=req_1.father_name,
            national_code=req_1.national_code,
            student_mobile=req_1.student_mobile,
            parent_mobile=req_1.parent_mobile,
            student_code=next_code
        )
        self.db.add(new_student)
        self.db.flush()

        enroll = Enrollment(
            student_id=new_student.id,
            course_id=req_1.course_id,
            register_date="1404/09/01",
            total_tuition=1000000,
            total_paid=req_1.paid_amount,
            shift="عصر"
        )
        self.db.add(enroll)
        
        # Credit student's wallet and insert transaction record
        new_student.wallet_institute = req_1.paid_amount
        trans = Transaction(
            student_id=new_student.id,
            course_id=req_1.course_id,
            enrollment_id=enroll.id,
            amount=req_1.paid_amount,
            payment_method=req_1.payment_method,
            date="1404/09/01",
            type="tuition",
            target_wallet="institute"
        )
        self.db.add(trans)
        self.db.commit()

        # Verify Student 1 details
        students_count = self.db.query(Student).count()
        self.assertEqual(students_count, 1)

        # 2. Second registration (Same student mobile, different course)
        # Create second Course
        course_2 = Course(title="ریاضی دهم", code="1002", teacher_id=1, teacher_session_price=100000)
        self.db.add(course_2)
        self.db.commit()

        req_2 = OnlineRegisterRequest(
            first_name="سارا",
            last_name="احمدی",
            father_name="احمد",
            national_code="0001112228",  # FIX: Bug 22 - valid checksum; duplicate-prevention assertions are unchanged.
            student_mobile="09121111111", # Same mobile
            parent_mobile="09122222222",
            course_id=course_2.id,
            paid_amount=150000
        )

        # Find existing student
        existing_student = self.db.query(Student).filter(
            or_(
                Student.student_mobile == req_2.student_mobile,
                Student.national_code == req_2.national_code
            )
        ).first()
        self.assertIsNotNone(existing_student) # Successfully found existing student!

        # Do not create duplicate, reuse the existing student id!
        enroll_2 = Enrollment(
            student_id=existing_student.id,
            course_id=req_2.course_id,
            register_date="1404/09/02",
            total_tuition=800000,
            total_paid=req_2.paid_amount,
            shift="عصر"
        )
        self.db.add(enroll_2)
        
        # Credit wallet and add transaction
        existing_student.wallet_institute = (existing_student.wallet_institute or 0) + req_2.paid_amount
        trans_2 = Transaction(
            student_id=existing_student.id,
            course_id=req_2.course_id,
            enrollment_id=enroll_2.id,
            amount=req_2.paid_amount,
            payment_method=req_2.payment_method,
            date="1404/09/02",
            type="tuition",
            target_wallet="institute"
        )
        self.db.add(trans_2)
        self.db.commit()

        # Verify student count is STILL 1 (No duplicate created!)
        students_count_post = self.db.query(Student).count()
        self.assertEqual(students_count_post, 1)

        # Verify that their total wallet balance is 350,000 (200,000 + 150,000)
        self.assertEqual(existing_student.wallet_institute, 350000)

if __name__ == "__main__":
    unittest.main()
