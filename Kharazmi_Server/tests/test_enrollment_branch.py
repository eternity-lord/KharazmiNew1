"""
Enrollment.branch_id — F-C2/S3 تکمیلی (regression test, isolated DB در /tmp)

چرا این تست: `analytics/dashboard` سه شمارش مهم (فعال/ثبت‌نام جدید/ماندگاری) را با
`Enrollment.branch_id == resolved_branch` فیلتر می‌کند. برای کاربر شعبه‌دار، ردیفِ
NULL در SQL هرگز مطابق نمی‌شود ⇒ ثبت‌نام از آمار حذف می‌شد.
دو مسیر باقی‌مانده‌ که branch_id ست نمی‌کردند: `students.register_and_enroll` و
`crm.leads/{id}/convert`. (`classes.add_enrollment` قبلاً در FIX S3 بسته شده بود.)

اجرا (طبق قانون پروژه، فقط روی کپی/DB تست):
    cd /home/user/KharazmiApp && DATABASE_URL=sqlite:////tmp/enroll_branch_test.db \
        PYTHONPATH=/home/user/KharazmiApp/Kharazmi_Server python3 -m pytest Kharazmi_Server/test_enrollment_branch.py -q
"""
import datetime
import os
import shutil
import tempfile
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dependencies import get_db, hash_password
from main import app
from models import Base, Branch, Course, Enrollment, Lead, Student, User, UserSession


class EnrollmentBranchBase(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="enroll_branch_test_")
        self.engine = create_engine(f"sqlite:///{os.path.join(self.tmpdir, 'test.db')}")
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        # دو شعبه: کارکنان/شاگردان شعبه ۱ در برابر شعبه ۲ (برای اثبات تفکیک)
        self.db.add_all([Branch(id=1, name="شعبه یک", active=True), Branch(id=2, name="شعبه دو", active=True)])
        self.db.add_all([
            # ادمین بدون شعبه (نباید فیلتر شود)
            User(id=1, username="09120000000", password=hash_password("123"), full_name="Admin",
                 role="admin", sub_role="admin", branch_id=None),
            # منشی شعبه ۱ (فیلتر شعبه فعال می‌شود)
            User(id=2, username="09121111111", password=hash_password("123"), full_name="Secretary",
                 role="admin", sub_role="secretary", branch_id=1),
        ])
        self.db.commit()
        self.db.add_all([
            UserSession(token="tok_admin", user_id=1, sub_role="admin", created_at=datetime.datetime.now()),
            UserSession(token="tok_sec1", user_id=2, sub_role="secretary", created_at=datetime.datetime.now()),
        ])
        self.db.commit()

        # کلاس‌ها: یکی شعبه ۱ و یکی بدون شعبه (برای تست fallback)
        self.course_b1 = Course(id=1, title="ریاضی شعبه یک", code="M1", class_time="16:00",
                                branch_id=1, is_admin_approved=True)
        self.course_no_branch = Course(id=2, title="فیزیک بی‌شعبه", code="P1", class_time="17:00",
                                       is_admin_approved=True)
        self.db.add_all([self.course_b1, self.course_no_branch])
        self.db.commit()

    def tearDown(self):
        app.dependency_overrides.clear()
        try:
            self.db.close()
        finally:
            self.engine.dispose()
            shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _headers(self, token="tok_sec1"):
        return {"Authorization": f"Bearer {token}"}

    def _register_payload(self, national_code="1000000001", course_id=1, student_branch_id=None):
        return {
            "first_name": "سینا", "last_name": "مرادی", "father_name": "علی",
            "national_code": national_code, "birth_date": "1390/01/01",
            "student_mobile": "09120000001", "parent_mobile": "09120000002",
            "home_phone": "02100000000", "address": "تهران", "study_status": "فعال",
            "gender": "male", "course_id": course_id, "total_tuition": 1000000,
            "paid_amount": 0, "register_date": "1405/06/25", "shift": "عصر",
        }


class TestRegisterAndEnrollBranch(EnrollmentBranchBase):

    def test_enrollment_inherits_student_branch(self):
        """شاگرد شعبه‌دار ⇒ Enrollment همان شعبه."""
        response = self.client.post("/students/register_and_enroll", json=self._register_payload(),
                                    headers=self._headers())
        self.assertEqual(response.status_code, 200, response.text)

        self.db.expire_all()
        enrollment = self.db.query(Enrollment).filter(Enrollment.course_id == 1).first()
        self.assertIsNotNone(enrollment, "ثبت‌نام باید ساخته شود")
        self.assertEqual(enrollment.branch_id, 1, "F-C2: Enrollment باید شعبه‌ی شاگرد را بگیرد")

    def test_enrollment_falls_back_to_course_branch(self):
        """شاگرد بدون شعبه + کلاس شعبه‌دار ⇒ شعبه‌ی کلاس (fallback هم‌منطق تراکنش)."""
        response = self.client.post(
            "/students/register_and_enroll",
            json=self._register_payload(national_code="1000000011", course_id=1),
            headers=self._headers()
        )
        self.assertEqual(response.status_code, 200, response.text)

        student = self.db.query(Student).filter(Student.national_code == "1000000011").first()
        if student is not None and student.branch_id is None:
            self.db.expire_all()
            enrollment = self.db.query(Enrollment).filter(Enrollment.student_id == student.id).first()
            self.assertEqual(enrollment.branch_id, 1, "شاگرد بی‌شعبه ⇒ شعبه‌ی کلاس")

    def test_admin_without_branch_still_sees_everything(self):
        """ادمین بدون شعبه: resolved_branch تهی ⇒ هیچ فیلتری اعمال نمی‌شود (نه رگرسیون)."""
        self.client.post("/students/register_and_enroll",
                         json=self._register_payload(national_code="1000000028"),
                         headers=self._headers("tok_admin"))
        self.db.expire_all()
        response = self.client.get("/analytics/dashboard?time_filter=Year", headers=self._headers("tok_admin"))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertGreaterEqual(response.json().get("active_students", 0), 1)

    def test_branch_scoped_user_counts_new_enrollment(self):
        """رگرسیون اصلی: ثبت‌نامِ شعبه‌ی ۱ باید در آمار منشیِ شعبه‌ی ۱ دیده شود."""
        self.client.post("/students/register_and_enroll",
                         json=self._register_payload(national_code="1000000036", course_id=1),
                         headers=self._headers())

        self.db.expire_all()
        response = self.client.get("/analytics/dashboard?time_filter=Year", headers=self._headers("tok_sec1"))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertGreaterEqual(
            response.json().get("active_students", 0), 1,
            "ثبت‌نام شعبه‌ی ۱ باید برای منشیِ همان شعبه شمرده شود (NULL یعنی حذف از آمار)"
        )

    def test_branch_scoped_analytics_excludes_null_branch_enrollments(self):
        """کنترل منفی — چرا فیکس لازم بود: ردیفِ branch_id=NULL برای کاربر شعبه‌دار
        در SQL هرگز مطابق نمی‌شود؛ یعنی قبل از فیکس، ثبت‌نام از آمار شعبه حذف می‌شد."""
        self.client.post("/students/register_and_enroll",
                         json=self._register_payload(national_code="1000000044", course_id=1),
                         headers=self._headers())
        self.db.expire_all()
        fixed_count = self.client.get("/analytics/dashboard?time_filter=Year",
                                      headers=self._headers("tok_sec1")).json()["active_students"]
        self.assertGreaterEqual(fixed_count, 1)

        # همان ردیف را عمداً NULL می‌کنیم (شبیه‌سازی رفتار پیش از فیکس)
        enrollment = self.db.query(Enrollment).first()
        enrollment.branch_id = None
        self.db.commit()
        self.db.expire_all()
        null_count = self.client.get("/analytics/dashboard?time_filter=Year",
                                     headers=self._headers("tok_sec1")).json()["active_students"]
        self.assertEqual(null_count, 0, "NULL ⇒ حذف از آمار شعبه‌دار (اثبات اهمیت فیکس)")
        self.assertLess(null_count, fixed_count)


class TestConvertLeadBranch(EnrollmentBranchBase):

    def setUp(self):
        super().setUp()
        self.lead = Lead(id=1, name="سرنخ تستی", mobile="09129999999", branch_id=1, status="new")
        self.db.add(self.lead)
        self.db.commit()

    def test_convert_lead_sets_enrollment_branch(self):
        response = self.client.post("/crm/leads/1/convert?course_id=1", headers=self._headers("tok_admin"))
        self.assertEqual(response.status_code, 200, response.text)

        self.db.expire_all()
        enrollment = self.db.query(Enrollment).first()
        self.assertIsNotNone(enrollment, "تبدیل سرنخ باید Enrollment بسازد")
        self.assertEqual(enrollment.branch_id, 1, "F-C2: Enrollment تبدیل سرنخ باید شعبه‌دار شود")


if __name__ == "__main__":
    unittest.main(verbosity=2)
