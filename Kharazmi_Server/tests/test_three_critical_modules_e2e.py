import unittest
import os
import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from models import Base, User, UserSession, Student, Teacher, Course, Enrollment, Homework, HomeworkSubmission, Conversation, ConversationParticipant, Message, Exam, ExamQuestion, ExamAttempt, Grade
from main import app
from dependencies import get_db, hash_password


class TestThreeCriticalModulesE2E(unittest.TestCase):

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

        # Seed users
        self.teacher_user = User(id=1, username="09120000001", password=hash_password("123"), full_name="استاد رضایی", role="teacher", sub_role="teacher")
        self.teacher = Teacher(id=1, teacher_code=101, first_name="امین", last_name="رضایی", mobile="09120000001", password=hash_password("123"), is_approved=True, national_code="0000000001")
        self.student_user = User(id=2, username="student_test", password=hash_password("123"), full_name="آرش کمالی", role="student", sub_role="student")
        self.student = Student(id=2, student_code=100002, first_name="آرش", last_name="کمالی", student_mobile="09120000002", parent_mobile="09120000003", national_code="1112223334", user_id=self.student_user.id, parent_user_id=12)  # FIX (audit-v2/test-triage): لینک‌های shadow.
        self.parent_user = User(id=12, username="parent_test", password=hash_password("123"), full_name="ولی آرش", role="parent", sub_role="parent")
        self.admin_user = User(id=13, username="admin_test", password=hash_password("123"), full_name="مدیریت سیستم", role="admin", sub_role="admin")

        self.db.add_all([self.teacher_user, self.teacher, self.student_user, self.student, self.parent_user, self.admin_user])
        self.db.commit()

        # Create active session tokens
        self.teacher_session = UserSession(token="tok_teacher", user_id=self.teacher_user.id, sub_role="teacher", created_at=datetime.datetime.now())
        self.student_session = UserSession(token="tok_student", user_id=self.student_user.id, sub_role="student", created_at=datetime.datetime.now())
        self.parent_session = UserSession(token="tok_parent", user_id=self.parent_user.id, sub_role="parent", created_at=datetime.datetime.now())
        self.admin_session = UserSession(token="tok_admin", user_id=self.admin_user.id, sub_role="admin", created_at=datetime.datetime.now())

        self.db.add_all([self.teacher_session, self.student_session, self.parent_session, self.admin_session])
        self.db.commit()

        # Seed Course & Enrollment
        self.course = Course(id=1, title="ریاضی دهم", code="MATH10", teacher_id=self.teacher.id, branch_id=1, is_deleted=False, is_suspended=False)
        self.db.add(self.course)
        self.db.commit()

        self.enrollment = Enrollment(id=1, student_id=self.student.id, course_id=self.course.id, register_date="1405/01/01", branch_id=1)
        self.db.add(self.enrollment)
        self.db.commit()

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()
        # Clean up mock file if left
        if os.path.exists("mock_homework.pdf"):
            os.remove("mock_homework.pdf")

    def test_scenario_1_homework_lifecycle_e2e(self):
        hw_payload = {
            "course_id": self.course.id,
            "title": "حل تمرینات بخش ۲",
            "description": "سوالات ۱ تا ۵ صفحه ۳۰ کتاب درسی حل شود.",
            "due_date": "1405/01/20",
            "max_score": 20.0
        }
        res_create = self.client.post(
            "/homework/create",
            json=hw_payload,
            headers={"Authorization": "Bearer tok_teacher"}
        )
        self.assertEqual(res_create.status_code, 200)
        hw_id = res_create.json()["id"]

        with open("mock_homework.pdf", "wb") as f:
            f.write(b"%PDF-1.4 mock homework submission content")

        with open("mock_homework.pdf", "rb") as file_data:
            res_submit = self.client.post(
                f"/homework/submissions/{hw_id}/submit",
                files={"file": ("my_submission.pdf", file_data, "application/pdf")},
                headers={"Authorization": "Bearer tok_student"}
            )
        self.assertEqual(res_submit.status_code, 200)
        os.remove("mock_homework.pdf")

        submission = self.db.query(HomeworkSubmission).filter(HomeworkSubmission.homework_id == hw_id, HomeworkSubmission.student_id == self.student.id).first()
        self.assertIsNotNone(submission)

        grade_payload = {
            "score": 18.5,
            "feedback": "بسیار تمیز و خوش‌خط حل شده است."
        }
        res_grade = self.client.post(
            f"/homework/submissions/{submission.id}/grade",
            json=grade_payload,
            headers={"Authorization": "Bearer tok_teacher"}
        )
        self.assertEqual(res_grade.status_code, 200)

        res_parent = self.client.get(
            f"/homework/parent/child/{self.student.id}",
            headers={"Authorization": "Bearer tok_parent"}
        )
        self.assertEqual(res_parent.status_code, 200)
        self.assertEqual(res_parent.json()[0]["score"], 18.5)
        self.assertEqual(res_parent.json()[0]["status"], "graded")

    def test_scenario_2_messages_chat_e2e(self):
        conv_payload = {
            "title": "بررسی تراز مالی کلاس ریاضی",
            "type": "private",
            "participant_ids": [self.admin_user.id],
            "participant_roles": ["admin"]
        }
        res_create = self.client.post(
            "/messages/conversations/create",
            json=conv_payload,
            headers={"Authorization": "Bearer tok_teacher"}
        )
        self.assertEqual(res_create.status_code, 200)
        conv_id = res_create.json()["conversation_id"]

        msg_payload = {"body": "سلام مدیریت محترم، لطفا تراز مالی این ماه را بررسی کنید."}
        res_send = self.client.post(
            f"/messages/conversations/{conv_id}/send",
            json=msg_payload,
            headers={"Authorization": "Bearer tok_teacher"}
        )
        self.assertEqual(res_send.status_code, 200)

        res_history = self.client.get(
            f"/messages/conversations/{conv_id}/history",
            headers={"Authorization": "Bearer tok_admin"}
        )
        self.assertEqual(res_history.status_code, 200)
        self.assertEqual(res_history.json()[0]["body"], "سلام مدیریت محترم، لطفا تراز مالی این ماه را بررسی کنید.")

        res_clash = self.client.get(
            f"/messages/conversations/{conv_id}/history",
            headers={"Authorization": "Bearer tok_student"}
        )
        self.assertEqual(res_clash.status_code, 403)

    def test_scenario_3_exams_and_report_card_gpa_pdf_e2e(self):
        exam_payload = {
            "course_id": self.course.id,
            "title": "کوییز میان‌ترم ادبیات",
            "date": "1405/01/22",
            "duration": 30,
            "max_score": 2.0
        }
        res_create = self.client.post(
            "/exams/create",
            json=exam_payload,
            headers={"Authorization": "Bearer tok_teacher"}
        )
        self.assertEqual(res_create.status_code, 200)
        exam_id = res_create.json()["exam_id"]

        q1_payload = {
            "question_text": "پایتخت ایران کدام شهر است؟",
            "type": "multiple_choice",
            "options": "تهران,اصفهان,شیراز,تبریز",
            "correct_answer": "تهران",
            "score_weight": 1.0
        }
        q2_payload = {
            "question_text": "آیا زمین دور خورشید می‌چرخد؟",
            "type": "true_false",
            "correct_answer": "بله",
            "score_weight": 1.0
        }
        self.client.post(f"/exams/{exam_id}/questions", json=q1_payload, headers={"Authorization": "Bearer tok_teacher"})
        self.client.post(f"/exams/{exam_id}/questions", json=q2_payload, headers={"Authorization": "Bearer tok_teacher"})

        res_start = self.client.post(
            f"/exams/attempts/{exam_id}/start",
            headers={"Authorization": "Bearer tok_student"}
        )
        self.assertEqual(res_start.status_code, 200)
        attempt_id = res_start.json()["attempt_id"]
        q_ids = [q["id"] for q in res_start.json()["questions"]]

        submit_payload = {
            "answers": [
                {"question_id": q_ids[0], "answer_text": "تهران"},
                {"question_id": q_ids[1], "answer_text": "بله"}
            ]
        }
        res_submit = self.client.post(
            f"/exams/attempts/{attempt_id}/submit",
            json=submit_payload,
            headers={"Authorization": "Bearer tok_student"}
        )
        self.assertEqual(res_submit.status_code, 200)
        self.assertTrue(res_submit.json()["is_graded"])
        self.assertEqual(res_submit.json()["score"], 2.0)

        res_pdf = self.client.get(
            f"/students/{self.student.id}/report_card/pdf",
            headers={"Authorization": "Bearer tok_student"}
        )
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf.headers["content-type"], "application/pdf")


if __name__ == "__main__":
    unittest.main()
