import sys
import os
import datetime
from sqlalchemy import create_engine, text, func
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import models
from models import Student, Teacher, Course, Enrollment, Transaction, SessionLog, Attendance, Installment, PricingTable, Branch, User, UserSession, Settlement, ActivityLog

def run_audit():
    # Use a fresh in-memory SQLite database to run E2E scenarios E2E and retrieve exact SELECT outputs
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    print("=========================================================================")
    print("📈 KHARAZMI FINANCIAL INTEGRITY & MATHEMATICAL AUDIT RUN")
    print("=========================================================================")

    # Seeding PricingTable
    p_elem = PricingTable(category="elementary", count_1=100000, count_2=160000, count_3=210000, count_4=240000, count_5=250000)
    p_mid = PricingTable(category="middle_school", count_1=120000, count_2=180000, count_3=240000, count_4=280000, count_5=300000)
    p_high = PricingTable(category="high_school", count_1=150000, count_2=240000, count_3=300000, count_4=360000, count_5=400000)
    p_inst = PricingTable(category="institute", count_1=50000, count_2=80000, count_3=100000, count_4=120000, count_5=150000)
    db.add_all([p_elem, p_mid, p_high, p_inst])
    db.commit()

    # Seeding Branch
    branch = Branch(id=1, name="شعبه مرکزی", active=True)
    db.add(branch)
    db.commit()

    # Seeding Admin and Teacher
    teacher_user = User(id=1, username="09120000001", password="123", role="teacher", sub_role="teacher")
    teacher = Teacher(id=1, teacher_code=101, first_name="امین", last_name="رضایی", mobile="09120000001", password="123", is_approved=True)
    admin_user = User(id=10, username="admin", password="123", role="admin", sub_role="admin")
    db.add_all([teacher_user, teacher, admin_user])
    db.commit()

    # --- STEP 1: Create a test class (High School category) ---
    course = Course(
        id=1,
        title="فیزیک دهم کنکور",
        code="PHY10",
        teacher_id=1,
        grade_level="دبیرستان",
        rule_prepay_teacher=False,
        rule_prepay_institute=False,
        rule_calc_absent=True,
        branch_id=1
    )
    db.add(course)
    db.commit()
    print("Step 1: Test course created with high_school category.")

    # --- STEP 2: Create 3 students ---
    student_a = Student(id=1, student_code=100001, first_name="آرش", last_name="کمالی", national_code="111", student_mobile="09120000002", parent_mobile="09120000003", wallet_balance=0, wallet_teacher=0, wallet_institute=0, branch_id=1)
    student_b = Student(id=2, student_code=100002, first_name="بهنام", last_name="راد", national_code="222", student_mobile="09120000004", parent_mobile="09120000005", wallet_balance=0, wallet_teacher=0, wallet_institute=0, branch_id=1)
    student_c = Student(id=3, student_code=100003, first_name="جمال", last_name="کریمی", national_code="333", student_mobile="09120000006", parent_mobile="09120000007", wallet_balance=0, wallet_teacher=0, wallet_institute=0, branch_id=1)
    db.add_all([student_a, student_b, student_c])
    db.commit()

    # Enrollments
    # Enrollment A: No discount
    enroll_a = Enrollment(id=1, student_id=1, course_id=1, register_date="1405/01/01", total_tuition=1000000, discount_type="none", discount_value=0, branch_id=1)
    # Enrollment B: 20% discount
    enroll_b = Enrollment(id=2, student_id=2, course_id=1, register_date="1405/01/01", total_tuition=1000000, discount_type="percentage", discount_value=20, branch_id=1)
    # Enrollment C: Fixed discount (100,000)
    enroll_c = Enrollment(id=3, student_id=3, course_id=1, register_date="1405/01/01", total_tuition=1000000, discount_type="fixed", discount_value=100000, branch_id=1)
    
    db.add_all([enroll_a, enroll_b, enroll_c])
    db.commit()

    # Verify calculated tuitions
    from dependencies import get_enrollment_tuition_and_discount
    tuition_a, _ = get_enrollment_tuition_and_discount(enroll_a)
    tuition_b, _ = get_enrollment_tuition_and_discount(enroll_b)
    tuition_c, _ = get_enrollment_tuition_and_discount(enroll_c)

    print(f"Step 2: Calculated tuitions:")
    print(f"  - Student A (No discount): Expected: 1,000,000 | Actual: {tuition_a:,}")
    print(f"  - Student B (20% discount): Expected: 800,000 | Actual: {tuition_b:,}")
    print(f"  - Student C (100k discount): Expected: 900,000 | Actual: {tuition_c:,}")

    # --- STEP 3: Session 1 (All 3 Present) ---
    # We will simulate the submit_session_and_calculate logic
    # Total cost for 3 present high_school: count_3 = 300,000
    # Institute share for 3 present: count_3 = 100,000
    # Teacher share: 300,000 - 100,000 = 200,000
    # Cost per student: 300,000 / 3 = 100,000
    # Teacher share per student: 200,000 / 3 = 66,666.6 -> rounded (66,667 / 66,667 / 66,666)
    # Institute share per student: 100,000 / 3 = 33,333.3 -> rounded (33,334 / 33,333 / 33,333)

    # Let's use the actual routing logic of submit_session_and_calculate to verify database execution
    from routers.attendance import submit_session_and_calculate, AttendanceSubmitData, AttendanceItem
    data_s1 = AttendanceSubmitData(
        course_id=1,
        date="1405/01/10",
        items=[
            AttendanceItem(student_id=1, status="Present"),
            AttendanceItem(student_id=2, status="Present"),
            AttendanceItem(student_id=3, status="Present")
        ]
    )
    res_s1 = submit_session_and_calculate(data_s1, db, "admin")
    db.commit()

    # Re-fetch wallets of students B and C
    db.refresh(student_a)
    db.refresh(student_b)
    db.refresh(student_c)

    print("Step 3: Session 1 completed (All 3 present). Wallets after deduction:")
    print(f"  - Student A wallet: {student_a.wallet_balance:,} (Teacher: {student_a.wallet_teacher:,}, Institute: {student_a.wallet_institute:,})")
    print(f"  - Student B wallet: {student_b.wallet_balance:,} (Teacher: {student_b.wallet_teacher:,}, Institute: {student_b.wallet_institute:,})")
    print(f"  - Student C wallet: {student_c.wallet_balance:,} (Teacher: {student_c.wallet_teacher:,}, Institute: {student_c.wallet_institute:,})")

    # --- STEP 4: Session 2 (A Absent Excused, B Absent Unexcused, C Present) ---
    # Total present: 1 (only C).
    # Since 1 present high_school: count_1 = 150,000.
    # Institute share: count_1 = 50,000.
    # Teacher share: 150,000 - 50,000 = 100,000.
    # Cost per student: 150,000 / 1 = 150,000.
    # Present student C is charged: Teacher=100,000, Institute=50,000 (Total = 150,000).
    # Absent Excused student A is NOT charged.
    # Absent Unexcused student B is charged the penalty rate (equal to base session rate): Teacher=100,000, Institute=50,000 (Total = 150,000).

    data_s2 = AttendanceSubmitData(
        course_id=1,
        date="1405/01/15",
        items=[
            AttendanceItem(student_id=1, status="Absent", excused=True),   # Excused (0 charge)
            AttendanceItem(student_id=2, status="Absent", excused=False),  # Unexcused (150,000 charge)
            AttendanceItem(student_id=3, status="Present")                  # Present (150,000 charge)
        ]
    )
    res_s2 = submit_session_and_calculate(data_s2, db, "admin")
    db.commit()

    db.refresh(student_a)
    db.refresh(student_b)
    db.refresh(student_c)

    print("Step 4: Session 2 completed. Wallets after deduction:")
    print(f"  - Student A (Excused):   {student_a.wallet_balance:,} (Teacher: {student_a.wallet_teacher:,}, Institute: {student_a.wallet_institute:,})")
    print(f"  - Student B (Unexcused): {student_b.wallet_balance:,} (Teacher: {student_b.wallet_teacher:,}, Institute: {student_b.wallet_institute:,})")
    print(f"  - Student C (Present):   {student_c.wallet_balance:,} (Teacher: {student_c.wallet_teacher:,}, Institute: {student_c.wallet_institute:,})")

    # --- STEP 5: Session 3 (0 present, Cancelled) ---
    data_s3 = AttendanceSubmitData(
        course_id=1,
        date="1405/01/20",
        items=[
            AttendanceItem(student_id=1, status="Absent", excused=True),
            AttendanceItem(student_id=2, status="Absent", excused=True),
            AttendanceItem(student_id=3, status="Absent", excused=True)
        ]
    )
    res_s3 = submit_session_and_calculate(data_s3, db, "admin")
    db.commit()

    db.refresh(student_a)
    db.refresh(student_b)
    db.refresh(student_c)

    print("Step 5: Session 3 completed (0 present). Wallets after deduction:")
    print(f"  - Student A wallet: {student_a.wallet_balance:,}")
    print(f"  - Student B wallet: {student_b.wallet_balance:,}")
    print(f"  - Student C wallet: {student_c.wallet_balance:,}")

    # --- STEP 6: Payments ---
    # Wallet balances are:
    # A: Teacher=-66,667, Institute=-33,334 (Total = -100,001)
    # B: Teacher=-166,667, Institute=-83,333 (Total = -250,000)
    # C: Teacher=-166,666, Institute=-83,333 (Total = -249,999)

    # Let's perform payments using submit_payment from routers/finance.py
    from routers.finance import submit_payment, FinanceSubmitData
    
    # 1. Student A pays exact debt (100,001)
    # We will pay to institute and teacher wallets
    submit_payment(FinanceSubmitData(student_id=1, amount=66667, target_wallet="teacher", description="تسویه", payment_method="نقدی", date="1405/01/22"), db, "admin")
    submit_payment(FinanceSubmitData(student_id=1, amount=33334, target_wallet="institute", description="تسویه", payment_method="نقدی", date="1405/01/22"), db, "admin")
    
    # 2. Student B pays half debt (125,000)
    submit_payment(FinanceSubmitData(student_id=2, amount=83333, target_wallet="teacher", description="تسویه نصف", payment_method="نقدی", date="1405/01/22"), db, "admin")
    submit_payment(FinanceSubmitData(student_id=2, amount=41667, target_wallet="institute", description="تسویه نصف", payment_method="نقدی", date="1405/01/22"), db, "admin")
    
    # 3. Student C pays more than debt (300,000)
    # Surplus: 300,000 - 249,999 = 50,001. Wallet should become +50,001 (credit / طلبکار)
    submit_payment(FinanceSubmitData(student_id=3, amount=200000, target_wallet="teacher", description="تسویه مازاد", payment_method="نقدی", date="1405/01/22"), db, "admin")
    submit_payment(FinanceSubmitData(student_id=3, amount=100000, target_wallet="institute", description="تسویه مازاد", payment_method="نقدی", date="1405/01/22"), db, "admin")
    
    db.commit()
    db.refresh(student_a)
    db.refresh(student_b)
    db.refresh(student_c)

    print("Step 6: Payments completed. Wallets after payment:")
    print(f"  - Student A wallet: {student_a.wallet_balance:,} (Teacher: {student_a.wallet_teacher:,}, Institute: {student_a.wallet_institute:,})")
    print(f"  - Student B wallet: {student_b.wallet_balance:,} (Teacher: {student_b.wallet_teacher:,}, Institute: {student_b.wallet_institute:,})")
    print(f"  - Student C wallet: {student_c.wallet_balance:,} (Teacher: {student_c.wallet_teacher:,}, Institute: {student_c.wallet_institute:,})")

    # --- STEP 7: Teacher Settlement ---
    # Let's count un-billed sessions and teacher share sum
    # Un-billed transactions of type "session_charge"
    unbilled_q = db.query(func.sum(Transaction.share_teacher)).filter(
        Transaction.type == "session_charge",
        Transaction.target_wallet == None, # session charges don't target wallet
        Transaction.is_deleted == False
    )
    unbilled_sum = unbilled_q.scalar() or 0
    print(f"Step 7: Pre-settlement un-billed teacher share sum: {unbilled_sum:,} Toman")

    # Execute settlement
    from routers.teachers import settle_teacher_sessions
    from schemas import SettleRequest
    
    # Get all unbilled session IDs
    sessions_db = db.query(SessionLog).all()
    session_ids = [s.id for s in sessions_db]
    
    settle_req = SettleRequest(session_ids=session_ids)
    res_settle = settle_teacher_sessions(teacher_id=1, req=settle_req, db=db, admin_sub_role="admin")
    db.commit()

    # Re-fetch settlements
    settlements = db.query(Settlement).filter(Settlement.teacher_id == 1).all()
    print(f"Step 7: Settlements count in DB: {len(settlements)}")
    for s in settlements:
        print(f"  - Settlement ID: {s.id} | Amount: {s.total_amount:,} | Session Count: {s.session_count}")

    # --- STEP 8: Delete Enrollment of Student A ---
    enroll_a_db = db.query(Enrollment).filter(Enrollment.id == 1).first()
    
    from dependencies import perform_delete_enrollment
    perform_delete_enrollment(enroll_a_db, db)
    db.commit()

    # تصمیم محصولی: تراکنش‌های وجه واقعی با همان لینک تاریخی فعال می‌مانند و اعتبار نزد شاگرد است
    trans_a = db.query(models.Transaction).filter(models.Transaction.student_id == 1).all()
    print(f"Step 8: Student A transactions count after enrollment deletion: {len(trans_a)}")
    for t in trans_a:
        print(f"  - Trans ID: {t.id} | Amount: {t.amount:,} | Enrollment ID: {t.enrollment_id} (انتظار: لینک تاریخی حفظ شده، فعال)")

    # --- STEP 9: Final Consistency Verification ---
    from routers.reports import get_financial_report
    from routers.analytics import get_analytics_dashboard

    # Reports legacy revenue:
    legacy_rev = get_financial_report(db=db, _="admin")
    
    # Analytics Dashboard revenue:
    analytics_dash = get_analytics_dashboard(db=db, _="admin")

    print("Step 9: Final Monthly Revenue:")
    print(f"  - Legacy Financial Reports Revenue sum: {sum(t['amount'] for t in legacy_rev):,}")
    print(f"  - Analytics Dashboard Revenue:           {analytics_dash['monthly_revenue']:,}")

if __name__ == "__main__":
    run_audit()
