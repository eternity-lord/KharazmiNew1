import datetime
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from dependencies import check_admin_access
from models import Base, Branch, Lead, Student, User, UserSession
from routers.analytics import get_enrollment_funnel
from routers.crm import LeadCreateRequest, convert_lead_to_student, create_crm_lead


class TestEnrollmentFunnel(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        self.db.add_all(
            [
                Branch(id=1, name="مرکزی", active=True),
                Branch(id=2, name="شعبه دوم", active=True),
            ]
        )
        admin = User(
            username="admin2",
            password="x",
            full_name="مدیر شعبه دوم",
            role="admin",
            sub_role="admin",
            branch_id=2,
        )
        secretary = User(
            username="sec2",
            password="x",
            full_name="منشی شعبه دوم",
            role="admin",
            sub_role="secretary",
            branch_id=2,
        )
        self.db.add_all([admin, secretary])
        self.db.flush()
        self.db.add_all(
            [
                UserSession(
                    token="admin-token",
                    user_id=admin.id,
                    sub_role="admin",
                    created_at=datetime.datetime.now(),
                ),
                UserSession(
                    token="secretary-token",
                    user_id=secretary.id,
                    sub_role="secretary",
                    created_at=datetime.datetime.now(),
                ),
            ]
        )

        converted_student_1 = Student(
            first_name="ثبت",
            last_name="شده یک",
            national_code="0012345701",
            student_mobile="09120000101",
            branch_id=2,
        )
        converted_student_2 = Student(
            first_name="ثبت",
            last_name="شده دو",
            national_code="0012345702",
            student_mobile="09120000102",
            branch_id=2,
        )
        self.db.add_all([converted_student_1, converted_student_2])
        self.db.flush()

        self.db.add_all(
            [
                Lead(
                    name="سرنخ تبدیل‌شده",
                    mobile="09120000101",
                    interested_course="ریاضی",
                    status="REGISTERED",
                    branch_id=2,
                    created_at=datetime.datetime(2026, 8, 5, 8, 0),
                    converted_at=datetime.datetime(2026, 8, 7, 8, 0),
                    converted_student_id=converted_student_1.id,
                ),
                Lead(
                    name="سرنخ بدون زمان تاریخی",
                    mobile="09120000102",
                    interested_course="فیزیک",
                    status="REGISTERED",
                    branch_id=2,
                    created_at=datetime.datetime(2026, 8, 10, 9, 0),
                    converted_at=None,
                    converted_student_id=converted_student_2.id,
                ),
                Lead(
                    name="سرنخ باز",
                    mobile="09120000103",
                    interested_course="شیمی",
                    status="NEW",
                    branch_id=2,
                    created_at=datetime.datetime(2026, 8, 20, 12, 0),
                ),
                Lead(
                    name="شعبه دیگر",
                    mobile="09120000104",
                    interested_course="زیست",
                    status="REGISTERED",
                    branch_id=1,
                    created_at=datetime.datetime(2026, 8, 15, 12, 0),
                    converted_at=datetime.datetime(2026, 8, 16, 12, 0),
                    converted_student_id=converted_student_1.id,
                ),
                Lead(
                    name="خارج بازه",
                    mobile="09120000105",
                    interested_course="ادبیات",
                    status="NEW",
                    branch_id=2,
                    created_at=datetime.datetime(2026, 7, 31, 23, 59),
                ),
            ]
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_branch_scoped_funnel_and_average(self):
        # The logged-in admin belongs to branch 2, so get_user_branch_filter
        # must override even a requested branch 1.
        result = get_enrollment_funnel(
            start_date="2026/08/01",
            end_date="2026/08/31",
            branch_id=1,
            authorization="Bearer admin-token",
            db=self.db,
            _="admin",
        )
        self.assertEqual(result["branch_id"], 2)
        self.assertEqual(result["total_leads"], 3)
        self.assertEqual(result["converted_leads"], 2)
        self.assertEqual(result["conversion_rate"], 66.67)
        self.assertEqual(result["average_conversion_hours"], 48.0)
        self.assertEqual(result["average_conversion_days"], 2.0)
        self.assertEqual(result["timed_conversions"], 1)

    def test_jalali_range_is_accepted_and_empty_rate_is_zero(self):
        result = get_enrollment_funnel(
            start_date="1405/07/01",
            end_date="1405/07/02",
            branch_id=2,
            authorization="Bearer admin-token",
            db=self.db,
            _="admin",
        )
        self.assertEqual(result["total_leads"], 0)
        self.assertEqual(result["converted_leads"], 0)
        self.assertEqual(result["conversion_rate"], 0.0)
        self.assertEqual(result["average_conversion_hours"], 0.0)

    def test_invalid_range_is_rejected(self):
        with self.assertRaises(HTTPException) as error:
            get_enrollment_funnel(
                start_date="2026/08/31",
                end_date="2026/08/01",
                branch_id=2,
                authorization="Bearer admin-token",
                db=self.db,
                _="admin",
            )
        self.assertEqual(error.exception.status_code, 400)

    def test_new_lead_inherits_logged_in_users_branch(self):
        created = create_crm_lead(
            req=LeadCreateRequest(
                name="سرنخ شعبه‌ای",
                mobile="09120000888",
                interested_course="ریاضی",
                branch_id=1,
            ),
            authorization="Bearer admin-token",
            db=self.db,
            role="admin",
            _login_role="admin",
        )
        lead = self.db.query(Lead).filter(Lead.id == created.id).first()
        self.assertEqual(lead.branch_id, 2)

    def test_convert_endpoint_records_funnel_metadata_without_changing_result(self):
        lead = Lead(
            name="تبدیل جدید",
            mobile="09120000999",
            interested_course="ریاضی",
            status="NEW",
            branch_id=2,
            created_at=datetime.datetime.now() - datetime.timedelta(hours=3),
        )
        self.db.add(lead)
        self.db.commit()

        response = convert_lead_to_student(
            id=lead.id,
            course_id=None,
            db=self.db,
            role="admin",
            _login_role="admin",
        )
        self.db.refresh(lead)
        student = self.db.query(Student).filter(Student.id == response["student_id"]).first()

        self.assertEqual(lead.status, "REGISTERED")
        self.assertIsNotNone(lead.converted_at)
        self.assertEqual(lead.converted_student_id, student.id)
        self.assertEqual(student.branch_id, 2)

    def test_secretary_is_rejected_by_existing_admin_dependency(self):
        with self.assertRaises(HTTPException) as error:
            check_admin_access("Bearer secretary-token", self.db)
        self.assertEqual(error.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
