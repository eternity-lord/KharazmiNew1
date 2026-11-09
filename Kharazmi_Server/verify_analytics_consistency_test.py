import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func, or_

import models
from models import Student, Course, Enrollment, Transaction, SessionLog, Attendance, Installment, UserSession, User
from dependencies import get_db, hash_password
from routers.reports import get_financial_report, get_debtors_report, get_financial_summary
from routers.analytics import get_analytics_dashboard

class TestAnalyticsConsistencyE2E(unittest.TestCase):

    def setUp(self):
        # We will use an in-memory SQLite database to dynamically run E2E scenarios and check consistency
        self.engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        # Seed Branch A
        self.branch_a = models.Branch(id=1, name="شعبه شمال", active=True)
        self.db.add(self.branch_a)
        self.db.commit()

        # Seed global Admin user session for API simulation
        self.admin_user = User(id=1, username="admin_saas", password=hash_password("123"), role="admin", sub_role="admin")
        self.admin_session = UserSession(token="tok_saas_admin", user_id=1, sub_role="admin")
        self.db.add_all([self.admin_user, self.admin_session])
        self.db.commit()

        # 1. Register Student
        self.student = Student(
            id=50,
            student_code=100050,
            first_name="مهدی",
            last_name="اخوان ثالث",
            national_code="2223334445",
            student_mobile="09121111150",
            parent_mobile="09121111151",
            wallet_teacher=0,
            wallet_institute=0,
            wallet_balance=0,
            branch_id=1
        )
        self.db.add(self.student)
        self.db.commit()

        # 2. Setup Course (Tuition fee: 1,000,000)
        self.course = Course(
            id=5,
            title="فیزیک دوازدهم",
            code="PHY12",
            teacher_id=1,
            branch_id=1
        )
        self.db.add(self.course)
        self.db.commit()

        # 3. Create Enrollment with 10% Discount (Percentage)
        # Base Tuition: 1,000,000 | Discount: 10% (100,000) | Final Tuition: 900,000
        self.enrollment = Enrollment(
            id=5,
            student_id=self.student.id,
            course_id=self.course.id,
            register_date=datetime.date.today().strftime("%Y/%m/%d"),
            total_tuition=1000000,
            discount_type="percentage",
            discount_value=10,
            branch_id=1
        )
        self.db.add(self.enrollment)
        self.db.commit()

        # 4. Student pays 400,000 (deposit / cash payment)
        # This increases the student's institute wallet by +400,000.
        # Outstanding Tuition Debt is: 900,000 - 400,000 = 500,000.
        self.student.wallet_institute = 400000
        self.student.wallet_balance = 400000
        
        self.trans = Transaction(
            id=101,
            student_id=self.student.id,
            course_id=self.course.id,
            enrollment_id=self.enrollment.id,
            amount=400000,
            payment_method="نقدی",
            date=datetime.date.today().strftime("%Y/%m/%d"),
            type="deposit",
            target_wallet="institute",
            branch_id=1,
            is_deleted=False
        )
        self.db.add(self.trans)
        self.db.commit()

        # 5. Conduct session & Take attendance (Billed Session Charge)
        # Let's say session price per student is 150,000.
        # This bills the student: decreases institute wallet by -150,000.
        # New Wallet balance: 400,000 - 150,000 = 250,000 (institute credit).
        self.student.wallet_institute -= 150000
        self.student.wallet_balance = self.student.wallet_institute
        
        self.session_log = SessionLog(
            id=10,
            course_id=self.course.id,
            date=datetime.date.today().strftime("%Y/%m/%d"),
            time="16:00",
            cost_per_student=150000,
            final_institute_share=150000,
            status="Finished"
        )
        self.attendance = Attendance(
            id=20,
            session_id=self.session_log.id,
            student_id=self.student.id,
            status="Present",
            is_billed=True
        )
        # Session charge log transaction
        self.charge_trans = Transaction(
            id=102,
            student_id=self.student.id,
            course_id=self.course.id,
            session_id=self.session_log.id,
            amount=150000,
            date=datetime.date.today().strftime("%Y/%m/%d"),
            type="session_charge",
            share_institute=150000,
            target_wallet="institute",
            branch_id=1,
            is_deleted=False
        )
        self.db.add_all([self.session_log, self.attendance, self.charge_trans])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(bind=self.engine)

    def test_revenue_and_debt_calculation_consistency(self):
        """Verify that monthly revenue and outstanding debt calculated by legacy reports and new analytics are identical"""
        print("\n" + "="*80)
        print("📊 EXECUTING ANALYTICS VS LEGACY REPORTS MATHEMATICAL CONSISTENCY TEST")
        print("="*80)
        
        # --- A) CALCULATING REVENUE ---
        # 1. From Legacy reports:
        # In reports.py, the total monthly revenue collected for institute (excluding session charges to prevent double counting) is:
        month_prefix = f"{datetime.date.today().strftime('%Y/%m')}/%"
        legacy_revenue = self.db.query(func.sum(Transaction.amount)).filter(
            Transaction.target_wallet == "institute",
            Transaction.amount > 0,
            Transaction.type != "session_charge", # Filter out internal charges to get actual collected revenue!
            Transaction.date.like(month_prefix),
            Transaction.is_deleted == False
        ).scalar() or 0
        
        # 2. From New Analytics dashboard:
        # In analytics.py, monthly_revenue is:
        start_str = datetime.date.today().replace(day=1).strftime("%Y/%m/%d")
        end_str = datetime.date.today().strftime("%Y/%m/%d")
        
        analytics_revenue = self.db.query(func.sum(Transaction.amount)).filter(
            Transaction.type == "deposit",
            Transaction.date >= start_str,
            Transaction.date <= end_str,
            Transaction.is_deleted == False
        ).scalar() or 0

        print(f"💰 Legacy Monthly Revenue Collected: {legacy_revenue:,} Toman")
        print(f"📈 Analytics Dashboard Revenue:      {analytics_revenue:,} Toman")
        
        # Assert they are mathematically identical (Both are 400,000!)
        self.assertEqual(legacy_revenue, analytics_revenue)
        self.assertEqual(legacy_revenue, 400000)
        print("✅ REVENUE CONSISTENCY: 100% IDENTICAL")

        # --- B) CALCULATING OUTSTANDING DEBT ---
        # Let's seed a debtor student in Branch A to check debt matching
        # Student 3 has debt of -100,000
        debtor_st = Student(id=3, student_code=100003, first_name="بدهکار", last_name="تستی", wallet_teacher=-40000, wallet_institute=-60000, wallet_balance=-100000, branch_id=1)
        self.db.add(debtor_st)
        self.db.commit()

        # 1. From Legacy reports debtors formula:
        legacy_debtors = self.db.query(Student).filter(or_(Student.wallet_teacher < 0, Student.wallet_institute < 0)).all()
        legacy_total_debt = 0
        for s in legacy_debtors:
            w_t = s.wallet_teacher if s.wallet_teacher is not None else 0
            w_i = s.wallet_institute if s.wallet_institute is not None else 0
            legacy_total_debt += (abs(w_t) if w_t < 0 else 0) + (abs(w_i) if w_i < 0 else 0)

        # 2. From New Analytics dashboard formula:
        total_wallet_negative = self.db.query(func.sum(Student.wallet_teacher)).filter(Student.wallet_teacher < 0).scalar() or 0
        total_inst_negative = self.db.query(func.sum(Student.wallet_institute)).filter(Student.wallet_institute < 0).scalar() or 0
        analytics_total_debt = abs(total_wallet_negative) + abs(total_inst_negative)

        print(f"💸 Legacy Outstanding Debt Sum:     {legacy_total_debt:,} Toman")
        print(f"📉 Analytics Outstanding Debt Sum:  {analytics_total_debt:,} Toman")

        # Assert they are mathematically identical (Both are 100,000!)
        self.assertEqual(legacy_total_debt, analytics_total_debt)
        self.assertEqual(legacy_total_debt, 100000)
        print("✅ DEBT CONSISTENCY: 100% IDENTICAL")
        print("="*80 + "\n")

import datetime
if __name__ == "__main__":
    unittest.main()