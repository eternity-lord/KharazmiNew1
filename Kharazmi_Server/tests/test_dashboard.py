"""
Admin Command Center - Dashboard KPI tests (Lightweight, Isolated)
Covers: 401/403/200, 6 KPIs aggregated, jalali prefix, overdue parse, student count, reuse audit/dunning optional
Isolated: sqlite memory, no modification to finance/timeline/audit/dunning routers
"""
import datetime
import os
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from models import Base, User, UserSession, Student, Teacher, Course, Enrollment, Installment, Transaction, Branch, SessionLog, Attendance, ActivityLog
from main import app
from dependencies import get_db, hash_password
from today_summary import jalali_date_string, parse_project_date


# FIX(B1): مسیر فایل‌های سرور مستقل از پوشهٔ اجرا — نسبت به محل همین فایل تست، نه cwd.
# الگوی قدیمی `open("Kharazmi_Server/routers/x.py")` فقط وقتی کار می‌کرد که سوئیت از ریشهٔ ریپو
# اجرا شود و از داخل `Kharazmi_Server/` (یا هر پوشهٔ دیگر) با FileNotFoundError می‌شکست.
# FIX(tests-dir): تست‌ها به پوشهٔ `tests/` منتقل شدند ⇒ پوشهٔ سرور یک سطح بالاتر است.
_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _server_file(*parts):
    """مسیر مطلق یک فایل داخل Kharazmi_Server (مستقل از cwd)."""
    return os.path.join(_SERVER_DIR, *parts)

try:
    from routers.dashboard import _clear_dashboard_cache
    _HAS_CLEAR = True
except ImportError:
    _HAS_CLEAR = False
    def _clear_dashboard_cache():
        pass


class TestDashboardKPIs(unittest.TestCase):

    def setUp(self):
        if '_clear_dashboard_cache' in globals():
            try:
                _clear_dashboard_cache()
            except Exception:
                pass
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
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

        self.db.add(Branch(id=1, name="مرکزی", active=True))
        self.db.commit()

        self.admin_user = User(id=1, username="09120000000", password=hash_password("123"), full_name="Admin", role="admin", sub_role="admin", branch_id=1)
        self.secretary_user = User(id=2, username="09121111111", password=hash_password("123"), full_name="Secretary", role="admin", sub_role="secretary", branch_id=1)
        self.teacher_user = User(id=3, username="09123333333", password=hash_password("101"), full_name="Teacher", role="teacher", sub_role="teacher", branch_id=1)
        self.db.add_all([self.admin_user, self.secretary_user, self.teacher_user])
        self.db.commit()

        self.admin_session = UserSession(token="tok_admin", user_id=1, sub_role="admin", created_at=datetime.datetime.now())
        self.secretary_session = UserSession(token="tok_secretary", user_id=2, sub_role="secretary", created_at=datetime.datetime.now())
        self.teacher_session = UserSession(token="tok_teacher", user_id=3, sub_role="teacher", created_at=datetime.datetime.now())
        self.db.add_all([self.admin_session, self.secretary_session, self.teacher_session])
        self.db.commit()

        # Minimal teacher/course/enrollment for installments
        self.teacher = Teacher(id=1, first_name="امیر", last_name="احمدی", national_code="0001000128", mobile="09123333333", teacher_code=101, is_approved=True, password=hash_password("101"))
        self.db.add(self.teacher)
        self.db.commit()
        self.course = Course(id=1, title="ریاضی", code="MATH1", teacher_id=1, class_time="16:00", is_admin_approved=True)
        self.db.add(self.course)
        self.db.commit()
        self.student1 = Student(id=1, first_name="سینا", last_name="مرادی", national_code="0000000001", student_mobile="09120000001", parent_mobile="09120000001", is_deleted=False)
        self.student2 = Student(id=2, first_name="سارا", last_name="احمدی", national_code="0000000002", student_mobile="09120000002", parent_mobile="09120000002", is_deleted=False)
        self.db.add_all([self.student1, self.student2])
        self.db.commit()
        self.enrollment = Enrollment(id=1, student_id=1, course_id=1, register_date=jalali_date_string(datetime.date.today()))
        self.db.add(self.enrollment)
        self.db.commit()

    def tearDown(self):
        if '_clear_dashboard_cache' in globals():
            try:
                _clear_dashboard_cache()
            except Exception:
                pass
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_401_no_token(self):
        r = self.client.get("/dashboard/kpis")
        self.assertEqual(r.status_code, 401)

    def test_403_non_admin(self):
        # Secretary and teacher should be 403 (dashboard Admin-only)
        r = self.client.get("/dashboard/kpis", headers={"Authorization": "Bearer tok_secretary"})
        self.assertEqual(r.status_code, 403, f"secretary should be 403 but got {r.status_code}: {r.text}")
        r2 = self.client.get("/dashboard/kpis", headers={"Authorization": "Bearer tok_teacher"})
        self.assertEqual(r2.status_code, 403, f"teacher should be 403 but got {r2.status_code}: {r2.text}")

    def test_200_admin_empty_returns_6_keys(self):
        r = self.client.get("/dashboard/kpis", headers={"Authorization": "Bearer tok_admin"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        for key in ["today_revenue", "total_overdue_amount", "overdue_installments_count", "active_students_count", "suspicious_alerts_count", "dunning_pending_count"]:
            self.assertIn(key, data, f"missing key {key}")
            self.assertIsInstance(data[key], int)
        # With 2 active students
        self.assertEqual(data["active_students_count"], 2)
        self.assertEqual(data["today_revenue"], 0)
        self.assertEqual(data["overdue_installments_count"], 0)

    def test_kpi_today_revenue_is_cash_collected_for_the_institute(self):
        """O-08 (به‌روزرسانی آگاهانهٔ این گارد): «درآمد امروز» = وصولی نقدی امروزِ **آموزشگاه**.

        پیش‌تر این تست جمع همهٔ تراکنش‌های امروز (هر نوع/کیفی) را قفل می‌کرد؛ حالا فقط
        `deposit` به کیف آموزشگاه شمرده می‌شود — با هر قالب تاریخی (شمسی یا میلادی) —
        و شارژ جلسه/سهم معلم/ردیف‌های حذف‌شده یا برگشتی شمرده نمی‌شوند.
        """
        today_str = jalali_date_string(datetime.date.today())
        today_iso = datetime.date.today().isoformat()  # واریزیِ امروز با تاریخ میلادی (نقطهٔ کورِ LIKE قدیمی)
        t1 = Transaction(student_id=1, course_id=1, amount=50000, payment_method="cash", date=today_str,
                         description="pay1", type="deposit", target_wallet="institute", is_deleted=False, is_reversed=False)
        t2 = Transaction(student_id=1, course_id=1, amount=75000, payment_method="cash", date=today_str + " 12:30",
                         description="pay2", type="deposit", target_wallet="institute", is_deleted=False, is_reversed=False)
        t3 = Transaction(student_id=1, course_id=1, amount=100000, payment_method="cash", date=today_str,
                         description="deleted", type="deposit", target_wallet="institute", is_deleted=True, is_reversed=False)
        t4 = Transaction(student_id=1, course_id=1, amount=200000, payment_method="cash", date=today_str,
                         description="reversed", type="deposit", target_wallet="institute", is_deleted=False, is_reversed=True)
        # Different date should not count
        other = jalali_date_string(datetime.date.today() - datetime.timedelta(days=1))
        t5 = Transaction(student_id=1, course_id=1, amount=99999, payment_method="cash", date=other,
                         description="other day", type="deposit", target_wallet="institute", is_deleted=False, is_reversed=False)
        # پول معلم و بدهی شاگرد، هیچ‌کدام وصولی آموزشگاه نیستند
        t6 = Transaction(student_id=1, course_id=1, amount=90000, payment_method="cash", date=today_str,
                         description="teacher share", type="deposit", target_wallet="teacher", is_deleted=False, is_reversed=False)
        t7 = Transaction(student_id=1, course_id=1, amount=-200000, payment_method="System", date=today_str,
                         description="session charge", type="session_charge", share_teacher=150000,
                         share_institute=50000, is_deleted=False, is_reversed=False)
        t8 = Transaction(student_id=1, course_id=1, amount=30000, payment_method="cash", date=today_iso,
                         description="pay3 (Gregorian date)", type="deposit", target_wallet="institute",
                         is_deleted=False, is_reversed=False)
        self.db.add_all([t1, t2, t3, t4, t5, t6, t7, t8])
        self.db.commit()
        r = self.client.get("/dashboard/kpis", headers={"Authorization": "Bearer tok_admin"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["today_revenue"], 155000, f"expected 155000 but got {r.json()}")

    def test_kpi_overdue_via_parse(self):
        # Overdue installments: due_date < today, jalali
        today = datetime.date.today()
        overdue_str = jalali_date_string(today - datetime.timedelta(days=5))
        overdue_str2 = jalali_date_string(today - datetime.timedelta(days=10))
        upcoming_str = jalali_date_string(today + datetime.timedelta(days=2))
        today_str = jalali_date_string(today)
        # 2 overdue unpaid, 1 paid overdue (should not count), 1 upcoming unpaid, 1 overdue deleted
        i1 = Installment(enrollment_id=1, amount=10000, due_date=overdue_str, is_paid=False, is_deleted=False)
        i2 = Installment(enrollment_id=1, amount=20000, due_date=overdue_str2, is_paid=False, is_deleted=False)
        i3 = Installment(enrollment_id=1, amount=30000, due_date=overdue_str, is_paid=True, is_deleted=False)
        i4 = Installment(enrollment_id=1, amount=40000, due_date=upcoming_str, is_paid=False, is_deleted=False)
        i5 = Installment(enrollment_id=1, amount=50000, due_date=overdue_str, is_paid=False, is_deleted=True)
        i6 = Installment(enrollment_id=1, amount=15000, due_date=today_str, is_paid=False, is_deleted=False)  # due today not overdue
        self.db.add_all([i1, i2, i3, i4, i5, i6])
        self.db.commit()
        r = self.client.get("/dashboard/kpis", headers={"Authorization": "Bearer tok_admin"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["overdue_installments_count"], 2, f"overdue count wrong {data}")
        self.assertEqual(data["total_overdue_amount"], 30000, f"overdue amount wrong {data}")

    def test_kpi_active_students_excludes_deleted(self):
        # Add a deleted student
        s3 = Student(id=3, first_name="Deleted", last_name="One", national_code="0000000003", student_mobile="09120000003", parent_mobile="09120000003", is_deleted=True)
        self.db.add(s3)
        self.db.commit()
        r = self.client.get("/dashboard/kpis", headers={"Authorization": "Bearer tok_admin"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["active_students_count"], 2)

    def test_kpi_suspicious_and_dunning_is_int(self):
        # Even with suspicious patterns (night session), should be int
        # Create a suspicious night session to ensure audit count >=1 if reuse works
        sl = SessionLog(course_id=1, date=jalali_date_string(datetime.date.today()), time="02:30", start_time="02:30", final_teacher_cost=0, final_institute_share=0, cost_per_student=0, attendee_count=1, status="Finished")
        self.db.add(sl)
        self.db.commit()
        r = self.client.get("/dashboard/kpis", headers={"Authorization": "Bearer tok_admin"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIsInstance(data["suspicious_alerts_count"], int)
        self.assertIsInstance(data["dunning_pending_count"], int)
        # suspicious could be 0 or >=1 depending on lazy import; should not error
        self.assertGreaterEqual(data["suspicious_alerts_count"], 0)

    def test_read_only_not_modify(self):
        today_str = jalali_date_string(datetime.date.today())
        t = Transaction(student_id=1, course_id=1, amount=12345, payment_method="cash", date=today_str, description="ro", type="tuition", is_deleted=False, is_reversed=False)
        self.db.add(t)
        self.db.commit()
        count_before = self.db.query(Transaction).count()
        r = self.client.get("/dashboard/kpis", headers={"Authorization": "Bearer tok_admin"})
        self.assertEqual(r.status_code, 200)
        count_after = self.db.query(Transaction).count()
        self.assertEqual(count_before, count_after)

    def test_dashboard_isolated_no_finance_touch(self):
        with open(_server_file("routers", "dashboard.py"), encoding="utf-8") as f:
            c = f.read()
        self.assertIn("check_admin_access", c)
        self.assertIn("DashboardKPIs", c)
        # Ensure not importing finance write logic
        self.assertNotIn("def create_transaction", c)


if __name__ == "__main__":
    unittest.main()
