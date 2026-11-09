import unittest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

import models
from models import AutomationRule, AutomationLog, Student, Course, Enrollment, Attendance, SessionLog, Grade, Lead, Transaction, Installment
from routers.automation import run_automation_engine
from routers.analytics import get_analytics_dashboard, export_analytics_excel, export_analytics_pdf


class TestKharazmiAutomationAnalytics(unittest.TestCase):

    def setUp(self):
        # Fresh in-memory database for automation rules and analytics
        self.engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        # Seed default automation rules
        self.rule_low_attendance = AutomationRule(
            id=1,
            name="Attendance < 80%",
            condition_type="attendance_low",
            threshold=80.0,
            action_type="parent_notification",
            active=True
        )
        self.rule_high_absence = AutomationRule(
            id=2,
            name="Absence >= 2",
            condition_type="absence_high",
            threshold=2.0,
            action_type="parent_alert",
            active=True
        )
        self.rule_overdue_installment = AutomationRule(
            id=4,
            name="Overdue installment",
            condition_type="installment_overdue",
            threshold=0.0,
            action_type="parent_notification",
            active=True
        )
        self.db.add_all([self.rule_low_attendance, self.rule_high_absence, self.rule_overdue_installment])
        self.db.commit()

        # Seed mock student
        self.student = Student(
            id=1,
            first_name="فریدون",
            last_name="مشیری",
            national_code="1111111111",
            parent_mobile="09121111111",
            wallet_teacher=-200000,
            wallet_institute=-150000,
            wallet_balance=-350000
        )
        self.db.add(self.student)
        self.db.commit()

        # Seed course
        self.course = Course(
            id=1,
            title="ادبیات عمومی",
            code="LIT101"
        )
        self.db.add(self.course)
        self.db.commit()

        # Seed enrollment
        self.enrollment = Enrollment(
            id=1,
            student_id=self.student.id,
            course_id=self.course.id,
            register_date=(datetime.date.today() - datetime.timedelta(days=15)).strftime("%Y/%m/%d"),
            total_tuition=500000
        )
        self.db.add(self.enrollment)
        self.db.commit()

        # Seed sessions with relative Gregorian dates to ensure they fall within filters
        today_dt = datetime.date.today()
        date1 = (today_dt - datetime.timedelta(days=15)).strftime("%Y/%m/%d")
        date2 = (today_dt - datetime.timedelta(days=10)).strftime("%Y/%m/%d")
        date3 = (today_dt - datetime.timedelta(days=5)).strftime("%Y/%m/%d")

        self.session1 = SessionLog(id=1, course_id=self.course.id, date=date1, time="08:00")
        self.session2 = SessionLog(id=2, course_id=self.course.id, date=date2, time="08:00")
        self.session3 = SessionLog(id=3, course_id=self.course.id, date=date3, time="08:00")
        self.db.add_all([self.session1, self.session2, self.session3])
        self.db.commit()

        # Seed attendance: Student missed 2 out of 3 sessions (66.6% absence rate, 33.3% attendance rate)
        self.att1 = Attendance(id=1, session_id=self.session1.id, student_id=self.student.id, status="Present")
        self.att2 = Attendance(id=2, session_id=self.session2.id, student_id=self.student.id, status="Absent", excused=False)
        self.att3 = Attendance(id=3, session_id=self.session3.id, student_id=self.student.id, status="Absent", excused=False)
        self.db.add_all([self.att1, self.att2, self.att3])
        self.db.commit()

        # Seed unpaid installment overdue
        self.installment = Installment(
            enrollment_id=self.enrollment.id,
            amount=100000,
            due_date=(datetime.date.today() - datetime.timedelta(days=2)).strftime("%Y/%m/%d"),  # Overdue
            is_paid=False
        )
        self.db.add(self.installment)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(bind=self.engine)

    def test_automation_low_attendance_triggering(self):
        """1. Verify that automation detects low attendance and records logs/triggers alerts"""
        # Run rules manually on our in-memory DB
        res = run_automation_engine(self.db, _="admin")
        self.assertEqual(res["status"], "success")

        # In our seed, Student missed 2/3 sessions (attendance = 33.3%, which is < 80%).
        # Therefore, "attendance_low" and "absence_high" should both trigger!
        # Check logs are generated
        logs = self.db.query(AutomationLog).all()
        self.assertGreaterEqual(len(logs), 2)

        # Check notification is created for parent
        notifs = self.db.query(models.Notification).filter(models.Notification.recipient_role == "parent").all()
        self.assertGreaterEqual(len(notifs), 2)
        self.assertIn("حضور و غیاب", notifs[0].title)

    def test_automation_installment_overdue_triggering(self):
        """2. Verify that unpaid overdue installments trigger automation notifications"""
        res = run_automation_engine(self.db, _="admin")
        self.assertEqual(res["status"], "success")

        # Check logs for the installment rule (Rule ID 4 or condition type installment_overdue)
        overdue_log = self.db.query(AutomationLog).filter(AutomationLog.details.like("%Installment %")).first()
        self.assertIsNotNone(overdue_log)
        self.assertIn("overdue", overdue_log.details)

    def test_analytics_aggregations(self):
        """3. Verify optimized databaseaggregations of analytics dashboard"""
        # Call dashboard stats for this Term (includes 1405 dates)
        stats = get_analytics_dashboard(time_filter="Term", db=self.db, _="admin")
        
        # Student 1 is active (has enrollment)
        self.assertEqual(stats["active_students"], 1)
        # Attendance rate should be exactly 33.3%
        self.assertEqual(stats["attendance_rate"], 33.3)
        # FIX: Bug 16 - tuition is 500,000 and total_paid is zero, regardless of wallet deficits.
        self.assertEqual(stats["outstanding_debt"], 500000)

    def test_analytics_exports(self):
        """4. Verify that Excel and PDF analytics exports run without throwing exceptions"""
        # Excel Export test
        xlsx_res = export_analytics_excel(time_filter="Month", db=self.db, _="admin")
        self.assertIsNotNone(xlsx_res)

        # PDF Export test
        pdf_res = export_analytics_pdf(time_filter="Month", db=self.db, _="admin")
        self.assertIsNotNone(pdf_res)


if __name__ == "__main__":
    unittest.main()
