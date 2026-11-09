"""
Audit Radar - Fraud Detection System tests (Optimized)
Isolated read-only tests - does not modify finance/classes/students/auth routers
Covers: 403/200, 3 patterns, N+1 fix, midnight crossover, rapid <1h + 30d via ActivityLog, no silent pass
"""
import datetime
import os
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from models import Base, User, UserSession, Student, Teacher, Course, SessionLog, Attendance, Transaction, Branch, ActivityLog
from main import app
from dependencies import get_db, hash_password


# FIX(B1): مسیر فایل‌های سرور مستقل از پوشهٔ اجرا — نسبت به محل همین فایل تست، نه cwd.
# الگوی قدیمی `open("Kharazmi_Server/routers/x.py")` فقط وقتی کار می‌کرد که سوئیت از ریشهٔ ریپو
# اجرا شود و از داخل `Kharazmi_Server/` (یا هر پوشهٔ دیگر) با FileNotFoundError می‌شکست.
# FIX(tests-dir): تست‌ها به پوشهٔ `tests/` منتقل شدند ⇒ پوشهٔ سرور یک سطح بالاتر است.
_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _server_file(*parts):
    """مسیر مطلق یک فایل داخل Kharazmi_Server (مستقل از cwd)."""
    return os.path.join(_SERVER_DIR, *parts)



class TestAuditRadar(unittest.TestCase):

    def setUp(self):
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

        self.teacher = Teacher(id=1, first_name="امیر", last_name="احمدی", national_code="0001000128", mobile="09123333333", teacher_code=101, is_approved=True, password=hash_password("101"))
        self.db.add(self.teacher)
        self.db.commit()

        self.student1 = Student(id=1, first_name="الارا", last_name="صیامی", national_code="0000000001", student_mobile="09120000001", parent_mobile="09120000001")
        self.student2 = Student(id=2, first_name="سارا", last_name="احمدی", national_code="0000000002", student_mobile="09120000002", parent_mobile="09120000002")
        self.db.add_all([self.student1, self.student2])
        self.db.commit()

        self.admin_session = UserSession(token="tok_admin", user_id=1, sub_role="admin", created_at=datetime.datetime.now())
        self.secretary_session = UserSession(token="tok_secretary", user_id=2, sub_role="secretary", created_at=datetime.datetime.now())
        self.teacher_session = UserSession(token="tok_teacher", user_id=3, sub_role="teacher", created_at=datetime.datetime.now())
        self.db.add_all([self.admin_session, self.secretary_session, self.teacher_session])
        self.db.commit()

        self.course = Course(id=1, title="ریاضی ۱۰", code="MATH10", teacher_id=1, class_time="16:00")
        self.db.add(self.course)
        self.db.commit()

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_403_non_admin_cannot_access_audit(self):
        r = self.client.get("/audit/suspicious_patterns", headers={"Authorization": "Bearer tok_secretary"})
        self.assertEqual(r.status_code, 403, f"secretary should be 403 but got {r.status_code}: {r.text}")
        r2 = self.client.get("/audit/suspicious_patterns", headers={"Authorization": "Bearer tok_teacher"})
        self.assertEqual(r2.status_code, 403, f"teacher should be 403 but got {r2.status_code}: {r2.text}")
        r3 = self.client.get("/audit/suspicious_patterns")
        self.assertEqual(r3.status_code, 401)

    def test_200_admin_can_access_empty(self):
        r = self.client.get("/audit/suspicious_patterns", headers={"Authorization": "Bearer tok_admin"})
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json(), list)

    def test_pattern_A_suspicious_attendance_night(self):
        sl = SessionLog(course_id=1, date="2026/01/01", time="02:30", start_time="02:30", final_teacher_cost=0, final_institute_share=0, cost_per_student=0, attendee_count=1, status="Finished")
        self.db.add(sl)
        self.db.commit()
        self.db.refresh(sl)
        r = self.client.get("/audit/suspicious_patterns", headers={"Authorization": "Bearer tok_admin"})
        self.assertEqual(r.status_code, 200)
        types = [a["type"] for a in r.json()]
        self.assertIn("suspicious_attendance", types, f"expected suspicious_attendance in {r.json()}")
        for a in r.json():
            if a["type"] == "suspicious_attendance":
                self.assertEqual(a["severity"], "high")
                self.assertIn("02:30", a["description"])
                break

    def test_pattern_A_delayed_after_class_time(self):
        # class 16:00, session 23:00 => circular diff 7 >5 => suspicious
        sl = SessionLog(course_id=1, date="2026/01/02", time="23:00", start_time="23:00", final_teacher_cost=0, final_institute_share=0, cost_per_student=0, attendee_count=1, status="Finished")
        self.db.add(sl)
        self.db.commit()
        r = self.client.get("/audit/suspicious_patterns", headers={"Authorization": "Bearer tok_admin"})
        self.assertEqual(r.status_code, 200)
        alerts = [a for a in r.json() if a["type"] == "suspicious_attendance"]
        self.assertTrue(len(alerts) >= 1)
        found = any("تأخیر" in a["description"] or "23:00" in a["description"] for a in alerts)
        self.assertTrue(found, f"expected delayed description in {alerts}")

    def test_pattern_A_midnight_crossover_not_flagged(self):
        # Bug before: abs(23-2)=21 >5 flagged as suspicious, but should NOT flag because circular diff 3
        # Create course with class_time 23:00 and session at 02:00 next day
        course2 = Course(id=2, title="فیزیک شب", code="PHYS23", teacher_id=1, class_time="23:00")
        self.db.add(course2)
        self.db.commit()
        sl = SessionLog(course_id=2, date="2026/01/03", time="02:00", start_time="02:00", final_teacher_cost=0, final_institute_share=0, cost_per_student=0, attendee_count=1, status="Finished")
        self.db.add(sl)
        self.db.commit()
        r = self.client.get("/audit/suspicious_patterns", headers={"Authorization": "Bearer tok_admin"})
        self.assertEqual(r.status_code, 200)
        alerts = [a for a in r.json() if a["type"] == "suspicious_attendance" and f"جلسه #{sl.id}" in a["description"]]
        # Should be empty because 23->02 circular diff 3 <=5 not suspicious, and time 02:00 is in 00-05 but that would be flagged as night
        # To test midnight logic specifically without night flag, use time 06:00 vs class 23:00? Let's use session 02:00 but course at 23:00
        # Since 02:00 is night (00-05), it WOULD be flagged as night suspicious anyway, so we need a non-night test for circular
        # Use class 22:00, session 01:00 -> session 01:00 night flagged, not good
        # Use class 23:00, session 01:00 with start_time 01:00 but time also 01:00 -> night flagged
        # So to isolate circular, we need session not in 00-05, e.g., class 23:00, session 02:30 is night, so we need different: class 23:00, session 06:00 (not night) circular diff min(7,17)=7 >5 should flag
        # Let's test class 23:00 session 06:00 => diff 7 -> should flag
        # But our current sl is 02:00 which is night, so we expect it to be flagged due to night, not circular. To test circular not flagged, we need non-night midnight crossover where diff small
        # Example class 23:00 session 01:00 night flagged, can't test
        # Better test: class 01:00 session 23:00 (session 23:00 not night, class 01:00) circular diff 2 => should NOT flag
        # Create course 01:00, session 23:00
        self.db.delete(sl)
        self.db.commit()
        course3 = Course(id=3, title="ریاضی بامداد", code="MATH01", teacher_id=1, class_time="01:00")
        self.db.add(course3)
        self.db.commit()
        sl2 = SessionLog(course_id=3, date="2026/01/04", time="23:00", start_time="23:00", final_teacher_cost=0, final_institute_share=0, cost_per_student=0, attendee_count=1, status="Finished")
        self.db.add(sl2)
        self.db.commit()
        r2 = self.client.get("/audit/suspicious_patterns", headers={"Authorization": "Bearer tok_admin"})
        self.assertEqual(r2.status_code, 200)
        alerts2 = [a for a in r2.json() if a["type"] == "suspicious_attendance" and f"جلسه #{sl2.id}" in a["description"]]
        # 01:00 vs 23:00 circular diff 2 <=5 => should NOT be flagged as delayed
        # Since 23:00 not in 00-05, only delayed check matters, and diff 2 not >5, so no alert for this session
        self.assertEqual(len(alerts2), 0, f"midnight crossover should not flag, but got {alerts2}")

    def test_pattern_B_rapid_deletion(self):
        # Rapid deletion must use ActivityLog within 30 days and <1h diff
        txn = Transaction(student_id=1, course_id=1, amount=50000, payment_method="cash", date="2026/01/01", description="test", type="tuition", is_deleted=True, is_reversed=False, share_teacher=0, share_institute=0)
        self.db.add(txn)
        self.db.commit()
        self.db.refresh(txn)
        # Create creation and deletion logs within 30 days and 30 min apart
        now = datetime.datetime.utcnow()
        creation = ActivityLog(admin_username="admin", action="online_payment_success", target_id=txn.id, target_name="transaction", details=f"ایجاد تراکنش #{txn.id} مبلغ {txn.amount}", timestamp=now - datetime.timedelta(minutes=30))
        deletion = ActivityLog(admin_username="admin", action="transaction_refund", target_id=txn.id, target_name="transaction", details=f"استرداد تراکنش #{txn.id}", timestamp=now)
        self.db.add_all([creation, deletion])
        self.db.commit()
        count_before = self.db.query(Transaction).filter(Transaction.is_deleted == True).count()
        r = self.client.get("/audit/suspicious_patterns", headers={"Authorization": "Bearer tok_admin"})
        self.assertEqual(r.status_code, 200)
        alerts = [a for a in r.json() if a["type"] == "rapid_deletion"]
        self.assertTrue(len(alerts) >= 1, f"expected rapid_deletion but got {r.json()}")
        self.assertEqual(alerts[0]["severity"], "high")
        self.assertIn(str(txn.id), alerts[0]["description"])
        count_after = self.db.query(Transaction).filter(Transaction.is_deleted == True).count()
        self.assertEqual(count_before, count_after)

    def test_pattern_B_not_rapid_when_over_1h(self):
        txn = Transaction(student_id=1, course_id=1, amount=60000, payment_method="cash", date="2026/01/02", description="test2", type="tuition", is_deleted=True, is_reversed=False)
        self.db.add(txn)
        self.db.commit()
        self.db.refresh(txn)
        now = datetime.datetime.utcnow()
        creation = ActivityLog(admin_username="admin", action="online_payment_success", target_id=txn.id, target_name="transaction", details=f"ایجاد تراکنش #{txn.id}", timestamp=now - datetime.timedelta(hours=2))
        deletion = ActivityLog(admin_username="admin", action="transaction_refund", target_id=txn.id, target_name="transaction", details=f"حذف تراکنش #{txn.id}", timestamp=now)
        self.db.add_all([creation, deletion])
        self.db.commit()
        r = self.client.get("/audit/suspicious_patterns", headers={"Authorization": "Bearer tok_admin"})
        self.assertEqual(r.status_code, 200)
        alerts = [a for a in r.json() if a["type"] == "rapid_deletion" and str(txn.id) in a["description"]]
        self.assertEqual(len(alerts), 0, f"over 1h should not flag rapid, but got {alerts}")

    def test_pattern_B_old_transaction_not_flagged(self):
        txn = Transaction(student_id=1, course_id=1, amount=70000, payment_method="cash", date="2025/01/01", description="old", type="tuition", is_deleted=True, is_reversed=False)
        self.db.add(txn)
        self.db.commit()
        self.db.refresh(txn)
        old = datetime.datetime.utcnow() - datetime.timedelta(days=40)
        creation = ActivityLog(admin_username="admin", action="online_payment_success", target_id=txn.id, target_name="transaction", details=f"ایجاد تراکنش #{txn.id}", timestamp=old)
        deletion = ActivityLog(admin_username="admin", action="transaction_refund", target_id=txn.id, target_name="transaction", details=f"حذف تراکنش #{txn.id}", timestamp=old + datetime.timedelta(minutes=30))
        self.db.add_all([creation, deletion])
        self.db.commit()
        r = self.client.get("/audit/suspicious_patterns", headers={"Authorization": "Bearer tok_admin"})
        self.assertEqual(r.status_code, 200)
        alerts = [a for a in r.json() if a["type"] == "rapid_deletion" and str(txn.id) in a["description"]]
        self.assertEqual(len(alerts), 0, f"old >30d should not flag, but got {alerts}")

    def test_pattern_B_no_activitylog_not_flagged_spam_fix(self):
        # Without ActivityLog, should NOT flag (fixes spam of all history)
        txn = Transaction(student_id=1, course_id=1, amount=80000, payment_method="cash", date="2026/01/03", description="no log", type="tuition", is_deleted=True, is_reversed=False)
        self.db.add(txn)
        self.db.commit()
        self.db.refresh(txn)
        r = self.client.get("/audit/suspicious_patterns", headers={"Authorization": "Bearer tok_admin"})
        self.assertEqual(r.status_code, 200)
        alerts = [a for a in r.json() if a["type"] == "rapid_deletion" and str(txn.id) in a["description"]]
        self.assertEqual(len(alerts), 0, f"without ActivityLog should not spam, but got {alerts}")

    def test_pattern_C_perfect_attendance(self):
        session_ids = []
        for i in range(10):
            sl = SessionLog(course_id=1, date=f"2026/01/{10+i:02d}", time="16:00", start_time="16:00", final_teacher_cost=10000, final_institute_share=5000, cost_per_student=15000, attendee_count=1, status="Finished")
            self.db.add(sl)
            self.db.flush()
            session_ids.append(sl.id)
        self.db.commit()
        for sid in session_ids:
            att = Attendance(session_id=sid, student_id=1, status="Present", is_billed=False, excused=False)
            self.db.add(att)
        self.db.commit()
        r = self.client.get("/audit/suspicious_patterns", headers={"Authorization": "Bearer tok_admin"})
        self.assertEqual(r.status_code, 200)
        alerts = [a for a in r.json() if a["type"] == "perfect_attendance"]
        self.assertTrue(len(alerts) >= 1, f"expected perfect_attendance but got {r.json()}")
        self.assertEqual(alerts[0]["severity"], "medium")
        self.assertIn("10", alerts[0]["description"])
        self.assertTrue("غیبت" in alerts[0]["description"])
        self.assertTrue("0 غیبت" in alerts[0]["description"] or "۰ غیبت" in alerts[0]["description"])

    def test_read_only_wallet_not_modified(self):
        s_before = self.db.query(Student).filter(Student.id == 1).first()
        wt_before = s_before.wallet_teacher
        wi_before = s_before.wallet_institute
        wb_before = s_before.wallet_balance
        sl = SessionLog(course_id=1, date="2026/01/05", time="03:00", final_teacher_cost=0, final_institute_share=0, cost_per_student=0, attendee_count=1, status="Finished")
        self.db.add(sl)
        # This txn without ActivityLog will NOT be flagged after fix, so read-only check still valid
        txn = Transaction(student_id=1, course_id=1, amount=10000, payment_method="cash", date="2026/01/05", description="test2", type="tuition", is_deleted=True, is_reversed=False)
        self.db.add(txn)
        self.db.commit()
        r = self.client.get("/audit/suspicious_patterns", headers={"Authorization": "Bearer tok_admin"})
        self.assertEqual(r.status_code, 200)
        self.db.refresh(s_before)
        s_after = self.db.query(Student).filter(Student.id == 1).first()
        self.assertEqual(wt_before, s_after.wallet_teacher)
        self.assertEqual(wi_before, s_after.wallet_institute)
        self.assertEqual(wb_before, s_after.wallet_balance)

    def test_no_silent_except_pass(self):
        with open(_server_file("routers", "audit.py"), encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("except Exception:\n        pass", content, "Silent except: pass still exists, should log")
        self.assertIn("logger.error", content, "Should log errors via logger.error")
        self.assertIn("print", content, "Should print/log errors")

    def test_joinedload_used_for_nplus1(self):
        with open(_server_file("routers", "audit.py"), encoding="utf-8") as f:
            content = f.read()
        self.assertIn("joinedload", content, "N+1 fix must use joinedload or selectinload")
        self.assertIn("joinedload(SessionLog.course)", content, "Should use joinedload(SessionLog.course)")

    def test_finance_uses_central_installment_validation(self):
        """FIX (F-T2، ۲۰۲۶-۰۹-۱۷): گارد قدیمیِ «finance.py نباید تغییر کند» محدودیت همان تسک ممیزی بود و با
        اصلاحِ تأییدشده‌ی F-T2 (که کدش در finance.py است) منقضی شد؛ به‌جای آن یک invariant پایدار
        بررسی می‌شود: اعتبارسنجی مبلغ/سررسید قسط در finance.py باید از قاعده‌ی مرکزی بیاید، نه regex شکلی.
        """
        with open(_server_file("routers", "finance.py"), encoding="utf-8") as f:
            content = f.read()
        self.assertIn("from validation import", content, "finance.py باید اعتبارسنجی مرکزی را import کند")
        self.assertIn("validate_jalali_due_date", content, "سررسید قسط باید با تقویم پروژه سنجیده شود")
        self.assertNotIn("Field(pattern=", content, "regex شکلیِ قدیمیِ سررسید نباید برگردد")


if __name__ == "__main__":
    unittest.main()
