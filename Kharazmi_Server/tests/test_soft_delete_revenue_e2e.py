import unittest
import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from models import Base, User, UserSession, Student, Course, Enrollment, Transaction, Branch
from main import app
from dependencies import get_db, hash_password


class TestSoftDeleteRevenueE2E(unittest.TestCase):

    def setUp(self):
        # Isolated in-memory SQLite DB
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

        # Seed Branch & Users
        self.branch = Branch(id=1, name="شعبه مرکزی", active=True)
        self.admin_user = User(id=1, username="admin_saas", password=hash_password("123"), role="admin", sub_role="admin", full_name="Admin SaaS")
        self.db.add_all([self.branch, self.admin_user])
        self.db.commit()

        self.admin_session = UserSession(token="tok_saas_admin", user_id=1, sub_role="admin", created_at=datetime.datetime.now())
        self.db.add(self.admin_session)
        self.db.commit()

        # Seed Student, Course & Enrollment
        self.student = Student(id=1, student_code=100001, first_name="آرش", last_name="کمالی", national_code="111", student_mobile="09120000002", parent_mobile="09120000003", wallet_balance=0, wallet_teacher=0, wallet_institute=0, branch_id=1)
        self.course = Course(id=1, title="شیمی دهم", code="CH10", teacher_id=1, branch_id=1, is_deleted=False, is_suspended=False)
        self.db.add_all([self.student, self.course])
        self.db.commit()

        self.enrollment = Enrollment(id=1, student_id=1, course_id=1, register_date="1405/01/01", branch_id=1)
        self.db.add(self.enrollment)
        self.db.commit()

        # Create two transactions
        self.trans1 = Transaction(
            id=1,
            student_id=1,
            course_id=1,
            enrollment_id=1,
            amount=500000,
            payment_method="نقدی",
            date=datetime.date.today().strftime("%Y/%m/%d"),
            type="deposit",
            target_wallet="institute",
            branch_id=1,
            is_deleted=False
        )
        self.trans2 = Transaction(
            id=2,
            student_id=1,
            course_id=1,
            enrollment_id=1,
            amount=300000,
            payment_method="نقدی",
            date=datetime.date.today().strftime("%Y/%m/%d"),
            type="deposit",
            target_wallet="institute",
            branch_id=1,
            is_deleted=False
        )
        self.db.add_all([self.trans1, self.trans2])
        self.db.commit()

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_soft_delete_ignored_by_both_reports_and_analytics_e2e(self):
        headers = {"Authorization": "Bearer tok_saas_admin"}
        from today_summary import gregorian_to_jalali  # FIX (audit-v2/test-triage): پارام شمسی (میلادی بازه‌ی ناممکن/ناهماهنگ می‌ساخت).
        year, month, _ = gregorian_to_jalali(datetime.date.today())

        res_reports_init = self.client.get(f"/reports/financial_summary?user_type=institute&year={year}&month={month}&branch_id=1", headers=headers)
        self.assertEqual(res_reports_init.status_code, 200)
        reports_init_revenue = res_reports_init.json()["monthly"]["collected"]
        self.assertEqual(reports_init_revenue, 800000)

        res_analytics_init = self.client.get("/analytics/dashboard?time_filter=Month&branch_id=1", headers=headers)
        self.assertEqual(res_analytics_init.status_code, 200)
        analytics_init_revenue = res_analytics_init.json()["total_turnover"]
        self.assertEqual(analytics_init_revenue, 800000)

        target_trans = self.db.query(Transaction).filter(Transaction.id == 2).first()
        target_trans.is_deleted = True
        self.db.commit()

        res_reports_final = self.client.get(f"/reports/financial_summary?user_type=institute&year={year}&month={month}&branch_id=1", headers=headers)
        self.assertEqual(res_reports_final.status_code, 200)
        reports_final_revenue = res_reports_final.json()["monthly"]["collected"]

        res_analytics_final = self.client.get("/analytics/dashboard?time_filter=Month&branch_id=1", headers=headers)
        self.assertEqual(res_analytics_final.status_code, 200)
        analytics_final_revenue = res_analytics_final.json()["total_turnover"]

        self.assertEqual(reports_final_revenue, 500000)
        self.assertEqual(analytics_final_revenue, 500000)
        self.assertEqual(reports_final_revenue, analytics_final_revenue)


if __name__ == "__main__":
    unittest.main()
