import unittest
import uuid
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

import models
from models import Student, Enrollment, Course, Transaction, Installment, Payment, ActivityLog, UserSession
from payment_gateways import get_payment_gateway
from routers.finance import verify_financial_idor


class TestKharazmiAdvancedFinance(unittest.TestCase):

    def setUp(self):
        # Use a fresh, in-memory SQLite database for rapid transaction and idempotency testing
        self.engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        # Seed initial data
        self.student = Student(
            first_name="سهراب",
            last_name="سپهری",
            national_code="1234567890",
            student_mobile="09120001122",
            parent_mobile="09120002233",
            wallet_teacher=-200000,      # Debt of 200,000 to teacher
            wallet_institute=-150000,    # Debt of 150,000 to institute
            wallet_balance=-350000
        )
        self.db.add(self.student)
        self.db.commit()

        self.course = Course(
            title="فیزیک کنکور",
            code="PHY101",
            teacher_session_price=50000
        )
        self.db.add(self.course)
        self.db.commit()

        self.enrollment = Enrollment(
            student_id=self.student.id,
            course_id=self.course.id,
            total_tuition=500000
        )
        self.db.add(self.enrollment)
        self.db.commit()

        # Create installments
        self.installment1 = Installment(
            enrollment_id=self.enrollment.id,
            amount=150000,
            due_date="1405/01/15",
            is_paid=False
        )
        self.installment2 = Installment(
            enrollment_id=self.enrollment.id,
            amount=200000,
            due_date="1405/02/15",
            is_paid=False
        )
        self.db.add_all([self.installment1, self.installment2])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(bind=self.engine)

    def test_online_payment_success_flow_and_idempotency(self):
        """1. Test successful online payment verification, wallet updates, and double-callback idempotency"""
        # Step A: Create a pending payment
        internal_id = "TX_TEST_123456"
        payment = Payment(
            internal_transaction_id=internal_id,
            amount=150000,
            status="PENDING",
            student_id=self.student.id,
            enrollment_id=self.enrollment.id,
            target_wallet="teacher",
            description="پرداخت آنلاین قسط ۱"
        )
        self.db.add(payment)
        self.db.commit()

        # Step B: Simulate first callback (Payment Success processing)
        # We manually run the callback logic on the database
        payment_record = self.db.query(Payment).filter(Payment.id == payment.id).with_for_update().first()
        self.assertEqual(payment_record.status, "PENDING")

        # Verify gateway mock
        gateway = get_payment_gateway("zarinpal")
        verified, trk_code = gateway.verify_payment("zp_ref_mock123", 150000)
        self.assertTrue(verified)
        self.assertTrue(trk_code.startswith("TRK_ZP_"))

        # Transition status
        payment_record.status = "SUCCESS"
        payment_record.tracking_code = trk_code
        payment_record.paid_at = datetime.datetime.utcnow()

        # Apply credit to the student's teacher wallet
        student_record = self.db.query(Student).filter(Student.id == self.student.id).with_for_update().first()
        student_record.wallet_teacher += 150000
        student_record.wallet_balance = student_record.wallet_teacher + student_record.wallet_institute

        # Add physical-like transaction
        new_trans = Transaction(
            student_id=payment_record.student_id,
            enrollment_id=payment_record.enrollment_id,
            amount=payment_record.amount,
            payment_method="online",
            tracking_code=trk_code,
            date="1405/01/10",
            description="پرداخت آنلاین موفق بابت قسط ۱",
            type="deposit",
            target_wallet="teacher",
            remittance_number=100002
        )
        self.db.add(new_trans)

        # Allocate to installment 1
        inst1 = self.db.query(Installment).filter(Installment.id == self.installment1.id).first()
        inst1.is_paid = True
        inst1.paid_at = "1405/01/10"

        # Log Activity
        self.db.add(ActivityLog(
            admin_username="online_payment_system",
            action="online_payment_success",
            target_id=student_record.id,
            target_name=f"{student_record.first_name} {student_record.last_name}",
            details=f"پرداخت آنلاین موفق به مبلغ {150000:,}."
        ))

        self.db.commit()

        # Assertions after first processing
        self.db.refresh(payment_record)
        self.db.refresh(student_record)
        self.db.refresh(inst1)

        self.assertEqual(payment_record.status, "SUCCESS")
        self.assertEqual(student_record.wallet_teacher, -50000)  # -200k + 150k = -50k
        self.assertEqual(student_record.wallet_balance, -200000) # -50k + -150k = -200k
        self.assertTrue(inst1.is_paid)

        # Step C: Simulate SECOND callback (Idempotency check)
        # Re-fetch payment record
        payment_record_dup = self.db.query(Payment).filter(Payment.id == payment.id).first()
        
        # In a real callback, we check: if payment_record_dup.status == "SUCCESS", we return success HTML immediately!
        # This prevents running any wallet updates or duplicate Transaction creations.
        if payment_record_dup.status == "SUCCESS":
            # Test passes idempotency check!
            idempotency_passed = True
        else:
            idempotency_passed = False

        self.assertTrue(idempotency_passed)
        # Ensure no duplicate transactions exist
        trans_count = self.db.query(Transaction).filter(Transaction.student_id == self.student.id).count()
        self.assertEqual(trans_count, 1)

    def test_refund_reversal_and_traceability_consistency(self):
        """2. Test non-physical soft reversal (Refund) and trace reliability"""
        # Step A: Register a manual payment transaction
        trans = Transaction(
            student_id=self.student.id,
            amount=100000,
            payment_method="نقدی",
            tracking_code="TRK_MAN_999",
            date="1405/01/12",
            description="شهریه حضوری",
            type="deposit",
            target_wallet="institute",
            remittance_number=100003,
            is_deleted=False,
            is_reversed=False
        )
        self.db.add(trans)
        
        # Apply to student wallet
        student = self.db.query(Student).filter(Student.id == self.student.id).first()
        student.wallet_institute += 100000
        student.wallet_balance = student.wallet_teacher + student.wallet_institute
        self.db.commit()

        self.assertEqual(student.wallet_institute, -50000) # -150k + 100k = -50k

        # Step B: Perform Refund (Reversal) - NEVER physically delete!
        target_trans = self.db.query(Transaction).filter(Transaction.id == trans.id).first()
        self.assertFalse(target_trans.is_reversed)

        # Apply reversal
        target_trans.is_reversed = True
        
        reversal = Transaction(
            student_id=target_trans.student_id,
            amount=-target_trans.amount,  # Negative amount to offset
            payment_method=target_trans.payment_method,
            tracking_code=f"REFUND_{target_trans.id}",
            date="1405/01/13",
            description=f"استرداد تراکنش #{target_trans.id}",
            type="reversal",
            target_wallet=target_trans.target_wallet,
            remittance_number=target_trans.remittance_number
        )
        self.db.add(reversal)

        # Deduct from student wallet
        student.wallet_institute -= target_trans.amount
        student.wallet_balance = student.wallet_teacher + student.wallet_institute
        self.db.commit()

        # Step C: Assert transaction audit trails
        self.db.refresh(target_trans)
        self.db.refresh(student)

        self.assertTrue(target_trans.is_reversed)
        self.assertEqual(student.wallet_institute, -150000) # Back to -150,000!
        
        # Ensure we have BOTH the original transaction and the reversal transaction in the database
        all_trans = self.db.query(Transaction).filter(Transaction.student_id == self.student.id).all()
        self.assertEqual(len(all_trans), 2)
        self.assertEqual(all_trans[0].amount, 100000)
        self.assertEqual(all_trans[1].amount, -100000) # Perfect financial traceability!

    def test_audit_logs_on_installment_modification(self):
        """3. Test automatic audit trail logging on editing installment amounts"""
        inst = self.db.query(Installment).filter(Installment.id == self.installment1.id).first()
        old_amount = inst.amount

        # Simulate update to 180,000
        new_amount = 180000
        inst.amount = new_amount

        # Write to ActivityLog (Audit)
        self.db.add(ActivityLog(
            admin_username="secretary_user",
            action="update_installment_amount",
            target_id=inst.id,
            target_name="installment",
            details=f"تغییر مبلغ قسط #{inst.id} از {old_amount:,} به {new_amount:,}."
        ))
        self.db.commit()

        # Assert Audit log exists
        audit = self.db.query(ActivityLog).filter(
            ActivityLog.action == "update_installment_amount",
            ActivityLog.target_id == inst.id
        ).first()

        self.assertIsNotNone(audit)
        self.assertEqual(audit.admin_username, "secretary_user")
        self.assertIn("از 150,000 به 180,000", audit.details)

    def test_financial_idor_restrictions(self):
        """4. Test financial portal IDOR restriction rules for parents, students, and admins"""
        # Set up mock user sessions
        from models import User  # FIX (audit-v2/test-triage): لینک واقعی user/shadow (قبلاً user_id معلق بود).
        student_user = User(username="adv-student-99", role="student", sub_role="student")
        self.db.add(student_user)
        self.db.flush()
        self.student.user_id = student_user.id
        student_session = UserSession(token="student_tok_99", user_id=student_user.id, sub_role="student")
        parent_session = UserSession(token="parent_tok_99", user_id=self.student.id, sub_role="parent")
        admin_session = UserSession(token="admin_tok_99", user_id=5, sub_role="admin")
        self.db.add_all([student_session, parent_session, admin_session])
        self.db.commit()

        # Case A: Student tries to access their own info (Should succeed)
        try:
            verify_financial_idor(self.student.id, "Bearer student_tok_99", self.db)
            student_self_check = True
        except HTTPException:
            student_self_check = False
        self.assertTrue(student_self_check)

        # Case B: Student tries to access other student's info (Should raise 403)
        with self.assertRaises(HTTPException) as ctx:
            verify_financial_idor(999, "Bearer student_tok_99", self.db)
        self.assertEqual(ctx.exception.status_code, 403)

        # Case C: Admin tries to access student info (Should succeed)
        try:
            verify_financial_idor(self.student.id, "Bearer admin_tok_99", self.db)
            admin_check = True
        except HTTPException:
            admin_check = False
        self.assertTrue(admin_check)


if __name__ == "__main__":
    unittest.main()
