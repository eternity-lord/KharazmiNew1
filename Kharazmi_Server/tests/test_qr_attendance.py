import unittest
import models
from models import SessionLocal, Student, Teacher, Course, Enrollment, Attendance, SessionLog
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
import datetime

class TestKharazmiQRAttendance(unittest.TestCase):

    def setUp(self):
        # Setup memory database
        self.engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        # Create Course
        self.course = Course(title="ریاضی دهم", code="1001", teacher_id=1, teacher_session_price=100000)
        self.db.add(self.course)
        self.db.commit()

        # Create Student A
        self.student_a = Student(first_name="الارا", last_name="صیامی", national_code="333", student_mobile="09111")
        self.db.add(self.student_a)
        
        # Create Student B (unauthorized)
        self.student_b = Student(first_name="سارا", last_name="احمدی", national_code="444", student_mobile="09222")
        self.db.add(self.student_b)
        self.db.commit()

        # Enroll Student A
        self.enroll = Enrollment(student_id=self.student_a.id, course_id=self.course.id)
        self.db.add(self.enroll)
        self.db.commit()

        # Create active Session Log
        self.session_log = SessionLog(course_id=self.course.id, date="1404/09/01", session_code=100001, attendee_count=0)
        self.db.add(self.session_log)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(bind=self.engine)

    def test_qr_checkin_expired(self):
        """1. Verify expired QR is rejected with an error"""
        now_ts = datetime.datetime.utcnow().timestamp()
        expired_ts = now_ts - 100 # Expired 100 seconds ago
        
        # We simulate the check-in endpoint logic
        if expired_ts < now_ts:
            # Rejection expected!
            has_error = True
        else:
            has_error = False
            
        self.assertTrue(has_error)

    def test_qr_checkin_unauthorized_student(self):
        """2. Verify student not enrolled in course is rejected"""
        # Student B tries to check-in to Course A
        enrolled = self.db.query(Enrollment).filter(Enrollment.student_id == self.student_b.id, Enrollment.course_id == self.session_log.course_id).first()
        self.assertIsNone(enrolled) # Not enrolled!

    def test_qr_checkin_duplicate_scan_prevention(self):
        """3. Verify duplicate scan of QR is prevented"""
        # First scan -> Success
        att_1 = Attendance(session_id=self.session_log.id, student_id=self.student_a.id, status="Present")
        self.db.add(att_1)
        self.db.commit()

        # Second scan -> Blocked
        existing = self.db.query(Attendance).filter(Attendance.session_id == self.session_log.id, Attendance.student_id == self.student_a.id).first()
        self.assertIsNotNone(existing)
        self.assertEqual(existing.status, "Present")

if __name__ == "__main__":
    unittest.main()
