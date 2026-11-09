import datetime
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models
from models import (
    Attendance,
    Course,
    Enrollment,
    Installment,
    InstituteSettings,
    LiveSession,
    SessionLog,
    Student,
    Teacher,
    Transaction,
)
from today_summary import (
    build_admin_smart_alerts,
    build_admin_today_summary,
    build_teacher_today_summary,
    jalali_date_string,
    parse_project_date,
    parse_schedule_start,
    schedule_matches_date,
)


class TestTodaySummary(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        # Sunday, 23 August 2026, 10:30 local server time.
        self.now = datetime.datetime(2026, 8, 23, 10, 30)

        self.teacher = Teacher(
            first_name="مریم",
            last_name="احمدی",
            national_code="1000000001",
            mobile="09120000001",
            is_approved=True,
        )
        self.db.add(self.teacher)
        self.db.flush()

        self.started_course = Course(
            title="ریاضی",
            code="C-1",
            teacher_id=self.teacher.id,
            days_of_week="یکشنبه",
            class_time="09:00-10:30",
            is_admin_approved=True,
            is_suspended=False,
            is_deleted=False,
        )
        self.late_course = Course(
            title="فیزیک",
            code="C-2",
            teacher_id=self.teacher.id,
            days_of_week="فرد",
            class_time="۱۰:۰۰",
            is_admin_approved=True,
            is_suspended=False,
            is_deleted=False,
        )
        self.db.add_all([self.started_course, self.late_course])
        self.db.flush()

        self.student = Student(
            first_name="علی",
            last_name="رضایی",
            national_code="2000000002",
            student_mobile="09120000002",
        )
        self.db.add(self.student)
        self.db.flush()

        today = jalali_date_string(self.now.date())
        self.db.add(
            Enrollment(
                student_id=self.student.id,
                course_id=self.started_course.id,
                register_date=today,
                total_tuition=1_000_000,
                total_paid=250_000,
            )
        )
        self.db.add(
            Transaction(
                student_id=self.student.id,
                amount=250_000,
                date=f"{today} 10:00",
                type="deposit",
                is_deleted=False,
                is_reversed=False,
            )
        )
        self.db.add(
            LiveSession(
                course_id=self.started_course.id,
                teacher_id=self.teacher.id,
                status="LIVE",
                start_time="2026-08-23 09:05",
                started_at_ts=int(datetime.datetime(2026, 8, 23, 9, 5).timestamp()),
            )
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_schedule_parsing_and_day_aliases(self):
        self.assertTrue(schedule_matches_date("فرد", self.now.date()))
        self.assertTrue(schedule_matches_date("یکشنبه، سه‌شنبه", self.now.date()))
        self.assertFalse(
            schedule_matches_date("یکشنبه", datetime.date(2026, 8, 22))
        )  # شنبه نباید با زیررشته‌ی «یکشنبه» اشتباه شود
        self.assertEqual(parse_schedule_start("۱۶:۳۰ تا ۱۸:۰۰"), (16, 30))
        self.assertEqual(parse_project_date("1405/06/01"), self.now.date())
        self.assertEqual(parse_project_date("۱۴۰۵/۰۶/۰۱"), self.now.date())
        self.assertEqual(parse_project_date("2026-08-23 10:30"), self.now.date())
        self.assertIsNone(parse_project_date("1405/12/31"))

    def test_admin_and_secretary_summaries(self):
        admin = build_admin_today_summary(self.db, "admin", self.now)
        self.assertEqual(admin["scheduled_classes"], 2)
        self.assertEqual(admin["started_classes"], 1)
        self.assertEqual(admin["today_enrollments"], 1)
        self.assertEqual(admin["today_payments"], 250_000)
        self.assertEqual(len(admin["late_classes"]), 1)
        self.assertEqual(admin["late_classes"][0]["course_id"], self.late_course.id)
        self.assertEqual(admin["late_classes"][0]["minutes_late"], 30)

        with patch(
            "today_summary.build_admin_smart_alerts",
            side_effect=AssertionError("secretary must not execute financial alert queries"),
        ):
            secretary = build_admin_today_summary(self.db, "secretary", self.now)
        self.assertFalse(secretary["payment_visible"])
        self.assertIsNone(secretary["today_payments"])
        self.assertEqual(secretary["scheduled_classes"], 2)
        self.assertFalse(secretary["smart_alerts_visible"])
        self.assertIsNone(secretary["installment_alerts"])
        self.assertIsNone(secretary["teacher_settlement_alerts"])

    def test_admin_smart_financial_alerts_and_configurable_threshold(self):
        enrollment = self.db.query(Enrollment).first()
        today = self.now.date()
        self.db.add(
            InstituteSettings(teacher_settlement_alert_days=30)
        )
        self.db.add_all(
            [
                Installment(
                    enrollment_id=enrollment.id,
                    amount=100_000,
                    due_date=jalali_date_string(today),
                    is_paid=False,
                ),
                Installment(
                    enrollment_id=enrollment.id,
                    amount=200_000,
                    due_date=jalali_date_string(today - datetime.timedelta(days=5)),
                    is_paid=False,
                ),
                Installment(
                    enrollment_id=enrollment.id,
                    amount=300_000,
                    due_date=jalali_date_string(today + datetime.timedelta(days=1)),
                    is_paid=False,
                ),
                Installment(
                    enrollment_id=enrollment.id,
                    amount=400_000,
                    due_date=jalali_date_string(today - datetime.timedelta(days=10)),
                    is_paid=True,
                ),
            ]
        )

        old_session = SessionLog(
            course_id=self.started_course.id,
            date=jalali_date_string(today - datetime.timedelta(days=31)),
            final_teacher_cost=500_000,
        )
        boundary_session = SessionLog(
            course_id=self.started_course.id,
            date=jalali_date_string(today - datetime.timedelta(days=30)),
            final_teacher_cost=600_000,
        )
        self.db.add_all([old_session, boundary_session])
        self.db.flush()
        self.db.add_all(
            [
                Attendance(
                    session_id=old_session.id,
                    student_id=self.student.id,
                    status="Present",
                    is_billed=False,
                ),
                Attendance(
                    session_id=boundary_session.id,
                    student_id=self.student.id,
                    status="Present",
                    is_billed=False,
                ),
            ]
        )
        self.db.commit()

        alerts = build_admin_smart_alerts(self.db, self.now)
        self.assertEqual(alerts["installment_alerts"]["count"], 2)
        self.assertEqual(alerts["installment_alerts"]["total_amount"], 300_000)
        self.assertEqual(
            [item["days_overdue"] for item in alerts["installment_alerts"]["items"]],
            [5, 0],
        )
        self.assertEqual(alerts["teacher_settlement_alert_days"], 30)
        self.assertEqual(alerts["teacher_settlement_alerts"]["count"], 1)
        self.assertEqual(
            alerts["teacher_settlement_alerts"]["total_amount"], 500_000
        )
        self.assertEqual(
            alerts["teacher_settlement_alerts"]["items"][0]["oldest_days_unsettled"],
            31,
        )

        settings = self.db.query(InstituteSettings).first()
        settings.teacher_settlement_alert_days = 40
        self.db.commit()
        raised_threshold = build_admin_smart_alerts(self.db, self.now)
        self.assertEqual(raised_threshold["teacher_settlement_alerts"]["count"], 0)

    def test_teacher_live_and_week_summary(self):
        session = SessionLog(
            course_id=self.started_course.id,
            date=jalali_date_string(self.now.date()),
            final_teacher_cost=180_000,
        )
        self.db.add(session)
        self.db.flush()
        self.db.add(
            Attendance(
                session_id=session.id,
                student_id=self.student.id,
                status="Present",
                is_billed=False,
            )
        )
        self.db.commit()

        result = build_teacher_today_summary(self.db, self.teacher.id, self.now)
        self.assertEqual(result["live_class"]["class_name"], "ریاضی")
        self.assertEqual(result["live_class"]["elapsed_minutes"], 85)
        self.assertIsNone(result["next_class"])
        self.assertEqual(result["week_summary"]["sessions_taught"], 1)
        self.assertEqual(result["week_summary"]["unsettled_amount"], 180_000)

    def test_teacher_next_class_when_not_live(self):
        self.db.query(LiveSession).delete()
        self.late_course.class_time = "11:00"
        self.db.commit()

        result = build_teacher_today_summary(self.db, self.teacher.id, self.now)
        self.assertIsNone(result["live_class"])
        self.assertEqual(result["next_class"]["course_id"], self.late_course.id)
        self.assertEqual(result["next_class"]["minutes_until"], 30)


if __name__ == "__main__":
    unittest.main()
