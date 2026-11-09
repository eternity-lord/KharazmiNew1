import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

import models
from models import Student, Course, Enrollment, Transaction, UserSession, User
from routers.ai import chat_with_ai_assistant, AIChatRequest


class TestKharazmiAIAssistant(unittest.TestCase):

    def setUp(self):
        # Fresh in-memory DB for secure AI tool execution testing
        self.engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        # Seed data
        self.student = Student(
            id=10,
            first_name="فرهاد",
            last_name="شیری",
            national_code="1010101010",
            student_code=100010,
            wallet_teacher=-100000,
            wallet_institute=-150000,
            wallet_balance=-250000
        )
        self.db.add(self.student)
        self.db.commit()

        # FIX (audit-v2/test-triage): کاربران واقعی + لینک user_id (قبلاً سشن‌ها معلق بودند).
        self.db.add_all([
            User(id=10, username="student:10", role="student", sub_role="student"),
            User(id=99, username="student:99", role="student", sub_role="student"),
            Student(id=99, first_name="دیگر", last_name="شاگرد", national_code="9999999999", user_id=99),
        ])
        self.student.user_id = 10
        self.db.commit()

        # Seed active sessions
        self.admin_session = UserSession(token="tok_admin", user_id=1, sub_role="admin")
        self.student_session = UserSession(token="tok_student", user_id=10, sub_role="student")
        self.other_student_session = UserSession(token="tok_other", user_id=99, sub_role="student")
        self.db.add_all([self.admin_session, self.student_session, self.other_student_session])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(bind=self.engine)

    def test_admin_ai_success_flow_and_kpis(self):
        """1. Verify that admin chat correctly calls financial tools and proposes confirmatory actions"""
        # Admin query about revenue
        req = AIChatRequest(message="چرا این ماه درآمد ما کم شده؟")
        
        # Invoke chat endpoint as Admin
        res = chat_with_ai_assistant(req, self.db, "Bearer tok_admin", "admin")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["role"], "admin")
        self.assertIn("درآمد وصول‌شده", res["response"])
        
        # Verify it proposes a confirmatory action instead of executing automatically (Human-in-the-loop)
        self.assertEqual(res["suggested_action"], "SEND_DEBT_REMINDERS")

    def test_student_ai_self_query_success(self):
        """2. Verify that student chat successfully retrieves their own data and gives study advice"""
        req = AIChatRequest(message="لطفاً برای آزمون به من برنامه بده", student_id=10)
        
        res = chat_with_ai_assistant(req, self.db, "Bearer tok_student", "student")
        self.assertEqual(res["status"], "success")
        self.assertIn("میانگین نمرات", res["response"])

    def test_student_parent_idor_prevention(self):
        """3. Verify strict IDOR blocks on student/parent sessions querying other users' details"""
        # Student 99 tries to query Student 10's financial/academic data
        req = AIChatRequest(message="وضعیت من چطوره؟", student_id=10)
        
        with self.assertRaises(HTTPException) as ctx:
            chat_with_ai_assistant(req, self.db, "Bearer tok_other", "student")
            
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("IDOR", ctx.exception.detail)


if __name__ == "__main__":
    unittest.main()
