# test_e2e_homework_exam_grading.py
# ═══════════════════════════════════════════════════════════════════════════════
# سناریوی end-to-end #۳: «تکلیف/آزمون: ثبت معلم → دیدن دانش‌آموز → تحویل/تصحیح → پورتال ولی»
#
# همان جریان واقعی اپ:
#   معلم  : HomeworkActivity.kt:74  → POST homework/create            (ثبت تکلیف)
#           HomeworkActivity.kt:83  → POST homework/submissions/{id}/grade
#           ExamActivity.kt:75/78/81→ POST exams/create · exams/attempts/{id}/start · .../submit
#           SubmitGradeActivity.kt:21 → POST grades/submit
#   شاگرد : HomeworkActivity.kt:80  → GET  homework/student/list
#           HomeworkActivity.kt:59  → POST homework/submissions/{id}/submit (فایل)
#   ولی   : HomeworkActivity.kt:86  → GET  homework/parent/child/{student_id}
#   پورتال: StudentPortalActivity.kt:41 → GET students/my_profile (لیست تکالیف/آزمون‌ها)
#
# ⚠ فاز دیباگ: هیچ کد برنامه‌ای تغییر نمی‌کند؛ فقط سنجش + مستندسازی.
import datetime
import os
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from dependencies import get_db, hash_password, limiter
from main import app

SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


class HomeworkExamWorld(unittest.TestCase):
    def setUp(self):
        self._limiter = limiter.enabled
        limiter.enabled = False
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                               poolclass=StaticPool)
        models.Base.metadata.create_all(engine)
        self.engine = engine
        self.db = sessionmaker(bind=engine, expire_on_commit=False)()
        now = datetime.datetime.now()

        self.db.add(models.Branch(id=1, name="شعبه مرکزی", active=True))
        self.db.add(models.User(id=101, username="09120000021", password=hash_password("a"),
                                full_name="مدیر", role="admin", sub_role="admin", branch_id=1))
        self.teacher = models.Teacher(id=51, first_name="مریم", last_name="معلم", mobile="09120000022",
                                      national_code="0012346001", password=hash_password("t"),
                                      is_approved=True, is_deleted=False, branch_id=1)
        self.db.add(self.teacher)
        self.course = models.Course(id=71, title="ریاضی دهم", code="700001", teacher_id=51, branch_id=1,
                                    is_deleted=False, is_admin_approved=True, grade_level="دهم",
                                    days_of_week="شنبه", class_time="17:30", teacher_session_price=100000)
        self.db.add(self.course)

        # دانش‌آموز ۱ (فعال) + دانش‌آموز ۲ (ثبت‌نام آرشیوشده) — برای سنجش نشت اعلان
        self.db.add_all([
            models.User(id=201, username="student:41", password="x", full_name="علی تست",
                        role="student", sub_role="student", branch_id=1),
            models.User(id=202, username="parent:41", password="x", full_name="ولی علی",
                        role="parent", sub_role="parent", branch_id=1),
            models.User(id=203, username="student:42", password="x", full_name="زهرا تست",
                        role="student", sub_role="student", branch_id=1),
            models.User(id=204, username="parent:42", password="x", full_name="ولی زهرا",
                        role="parent", sub_role="parent", branch_id=1),
        ])
        self.db.add_all([
            models.Student(id=41, student_code=41, first_name="علی", last_name="تست",
                           national_code="0012346002", student_mobile="09120000023", branch_id=1,
                           wallet_teacher=0, wallet_institute=0, wallet_balance=0,
                           user_id=201, parent_user_id=202, is_deleted=False),
            models.Student(id=42, student_code=42, first_name="زهرا", last_name="تست",
                           national_code="0012346003", student_mobile="09120000024", branch_id=1,
                           wallet_teacher=0, wallet_institute=0, wallet_balance=0,
                           user_id=203, parent_user_id=204, is_deleted=False),
        ])
        self.db.add_all([
            models.Enrollment(id=1, student_id=41, course_id=71, branch_id=1, register_date="1405/06/01",
                              shift="عصر", total_tuition=1000000, total_paid=0, is_deleted=False),
            # ثبت‌نام آرشیوشده (دانش‌آموز از کلاس خارج شده)
            models.Enrollment(id=2, student_id=42, course_id=71, branch_id=1, register_date="1405/06/01",
                              shift="عصر", total_tuition=1000000, total_paid=0, is_deleted=True),
        ])
        self.db.add_all([
            models.UserSession(token="tok-teacher", user_id=51, teacher_id=51, sub_role="teacher",
                               created_at=now),
            models.UserSession(token="tok-admin", user_id=101, sub_role="admin", created_at=now),
            models.UserSession(token="tok-student", user_id=201, sub_role="student", created_at=now),
            models.UserSession(token="tok-student2", user_id=203, sub_role="student", created_at=now),
            models.UserSession(token="tok-parent", user_id=202, sub_role="parent", created_at=now),
            models.UserSession(token="tok-parent2", user_id=204, sub_role="parent", created_at=now),
        ])
        self.db.commit()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        limiter.enabled = self._limiter
        self.db.close()
        self.engine.dispose()

    # ---------------- کمکی ----------------
    def create_homework(self, title="صفحه ۲۵ تا ۳۰", token="tok-teacher", due_date="1405/11/29"):
        return self.client.post("/homework/create", json={
            "course_id": 71, "title": title, "description": "تمرین فصل ۳",
            "due_date": due_date, "max_score": 20.0}, headers=hdr(token))

    def notifications(self, user_id, role):
        return self.db.query(models.Notification).filter(
            models.Notification.recipient_user_id == user_id,
            models.Notification.recipient_role == role).all()

    def create_exam(self, token="tok-teacher"):
        return self.client.post("/exams/create", json={
            "course_id": 71, "title": "آزمون فصل ۳", "date": "1405/06/20",
            "duration": 60, "max_score": 20.0}, headers=hdr(token))


class TestHomeworkFlow(HomeworkExamWorld):
    def test_1_teacher_creates_homework_and_active_students_are_notified(self):
        resp = self.create_homework()
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        hw = self.db.query(models.Homework).filter(models.Homework.id == body["id"]).first()
        self.assertIsNotNone(hw, "تکلیف باید در homeworks ذخیره شود")
        self.assertEqual(hw.title, "صفحه ۲۵ تا ۳۰")
        self.assertEqual(hw.teacher_id, 51)
        self.assertEqual(hw.status, "pending")

        notes = self.notifications(201, "student")
        self.assertEqual(len(notes), 1, "دانش‌آموزِ ثبت‌نام‌شده باید اعلان تکلیف بگیرد")
        self.assertEqual(notes[0].type, "homework")

    def test_2_archived_enrollment_gets_no_homework_notification(self):
        """O-04 (رفع‌شده): اعلان «تکلیف جدید» فقط برای ثبت‌نام‌های **فعال** ارسال می‌شود.

        پیش از فیکس، `routers/homework.py:94` همهٔ ردیف‌های ثبت‌نام (حتی آرشیوشده) را
        می‌گرفت ⇒ دانش‌آموزی که از کلاس خارج شده بود هم اعلان تکلیف می‌گرفت.
        """
        self.assertEqual(self.create_homework().status_code, 200)
        active = self.notifications(201, "student")
        self.assertEqual(len(active), 1, "شاگردِ فعال باید اعلان بگیرد (رگرسیون)")
        leaked = self.notifications(203, "student")
        self.assertEqual(leaked, [], "شاگردِ حذف‌شده نباید اعلان تکلیف بگیرد")

    def test_3_student_lists_homework_and_submits_file(self):
        hw_id = self.create_homework().json()["id"]
        listing = self.client.get("/homework/student/list", headers=hdr("tok-student"))
        self.assertEqual(listing.status_code, 200, listing.text)
        self.assertIn("صفحه ۲۵ تا ۳۰", [h["title"] for h in listing.json()])

        submit = self.client.post(f"/homework/submissions/{hw_id}/submit",
                                  files={"file": ("answers.pdf", b"%PDF-1.4 test", "application/pdf")},
                                  headers=hdr("tok-student"))
        self.assertEqual(submit.status_code, 200, submit.text)
        sub = self.db.query(models.HomeworkSubmission).filter(
            models.HomeworkSubmission.homework_id == hw_id,
            models.HomeworkSubmission.student_id == 41).first()
        self.assertIsNotNone(sub, "پاسخ تکلیف باید در homework_submissions ذخیره شود")
        self.assertEqual(sub.status, "submitted")
        self.assertIn("uploads", sub.file_path.replace("\\", "/"),
                      "فایل باید زیر پوشهٔ آپلودِ پروژه ذخیره شود (فیکس storage)")

    def test_3b_late_submission_is_marked_late(self):
        """مهلت گذشته ⇒ وضعیت پاسخ «late» می‌شود (فیکس H3-B3: مقایسهٔ واقعی تاریخ شمسی)."""
        hw_id = self.create_homework(title="تکلیف دیرشده", due_date="1405/01/01").json()["id"]
        resp = self.client.post(f"/homework/submissions/{hw_id}/submit",
                                files={"file": ("late.pdf", b"%PDF-1.4 x", "application/pdf")},
                                headers=hdr("tok-student"))
        self.assertEqual(resp.status_code, 200, resp.text)
        sub = self.db.query(models.HomeworkSubmission).filter(
            models.HomeworkSubmission.homework_id == hw_id).first()
        self.assertEqual(sub.status, "late", "تحویل بعد از مهلت باید late ثبت شود")

    def test_4_teacher_grades_and_status_is_visible_to_parent(self):
        hw_id = self.create_homework().json()["id"]
        self.client.post(f"/homework/submissions/{hw_id}/submit",
                         files={"file": ("a.pdf", b"%PDF-1.4 x", "application/pdf")},
                         headers=hdr("tok-student"))
        sub = self.db.query(models.HomeworkSubmission).filter(
            models.HomeworkSubmission.homework_id == hw_id).first()

        grade = self.client.post(f"/homework/submissions/{sub.id}/grade",
                                 json={"score": 18.5, "feedback": "خوب بود"}, headers=hdr("tok-teacher"))
        self.assertEqual(grade.status_code, 200, grade.text)
        self.db.refresh(sub)
        self.assertEqual(sub.status, "graded")
        self.assertEqual(sub.score, 18.5)
        self.assertEqual(sub.feedback, "خوب بود")

        parent_view = self.client.get("/homework/parent/child/41", headers=hdr("tok-parent"))
        self.assertEqual(parent_view.status_code, 200, parent_view.text)
        self.assertEqual(len(parent_view.json()), 1, "ولی باید تکلیف فرزندش را ببیند")

    def test_5_parent_idor_and_student_are_blocked(self):
        self.create_homework()
        # ولیِ دانش‌آموز دیگر ⇒ ۴۰۳ (حفاظت IDOR)
        other = self.client.get("/homework/parent/child/41", headers=hdr("tok-parent2"))
        self.assertEqual(other.status_code, 403, other.text)
        # خودِ دانش‌آموز نباید این مسیرِ خاص را ببیند
        student_call = self.client.get("/homework/parent/child/41", headers=hdr("tok-student"))
        self.assertEqual(student_call.status_code, 403, student_call.text)

    def test_6_homework_is_visible_in_student_portal(self):
        self.create_homework()
        profile = self.client.get("/students/my_profile", headers=hdr("tok-student"))
        self.assertEqual(profile.status_code, 200, profile.text)
        titles = [h["title"] for h in profile.json()["homework"]]
        self.assertIn("صفحه ۲۵ تا ۳۰", titles, "تکلیف واقعی باید در پورتال شاگرد دیده شود (زنجیرهٔ C6)")


class TestExamFlow(HomeworkExamWorld):
    def test_7_exam_creation_attempt_and_automatic_grading(self):
        exam_resp = self.create_exam()
        self.assertEqual(exam_resp.status_code, 200, exam_resp.text)
        exam_id = exam_resp.json()["exam_id"]
        exam = self.db.query(models.Exam).filter(models.Exam.id == exam_id).first()
        self.assertIsNotNone(exam, "آزمون باید در exams ذخیره شود")
        self.assertEqual(exam.max_score, 20.0)

        q = self.client.post(f"/exams/{exam_id}/questions", json={
            "question_text": "۲+۲ چند است؟", "type": "multiple_choice", "options": "۳,۴,۵",
            "correct_answer": "۴", "score_weight": 12.0}, headers=hdr("tok-teacher"))
        self.assertEqual(q.status_code, 200, q.text)
        self.client.post(f"/exams/{exam_id}/questions", json={
            "question_text": "آسمان آبی است؟", "type": "true_false", "options": "بله,خیر",
            "correct_answer": "بله", "score_weight": 12.0}, headers=hdr("tok-teacher"))

        start = self.client.post(f"/exams/attempts/{exam_id}/start", headers=hdr("tok-student"))
        self.assertEqual(start.status_code, 200, start.text)
        attempt = self.db.query(models.ExamAttempt).filter(
            models.ExamAttempt.exam_id == exam_id, models.ExamAttempt.student_id == 41).first()
        self.assertIsNotNone(attempt, "شروع آزمون باید در exam_attempts ذخیره شود")

        questions = self.db.query(models.ExamQuestion).filter(
            models.ExamQuestion.exam_id == exam_id).order_by(models.ExamQuestion.id).all()
        answers = [{"question_id": questions[0].id, "answer_text": "۴"},
                   {"question_id": questions[1].id, "answer_text": "خیر"}]
        submit = self.client.post(f"/exams/attempts/{attempt.id}/submit", json={"answers": answers},
                                  headers=hdr("tok-student"))
        self.assertEqual(submit.status_code, 200, submit.text)

        self.db.refresh(attempt)
        self.assertEqual(attempt.score, 12.0, "فقط پاسخ درست امتیاز می‌گیرد")
        self.assertLessEqual(attempt.score, exam.max_score, "نمره هرگز از سقف آزمون بیشتر نمی‌شود")

        grade = self.db.query(models.Grade).filter(
            models.Grade.student_id == 41,
            models.Grade.exam_title == "آزمون آنلاین: آزمون فصل ۳").first()
        self.assertIsNotNone(grade, "نمرهٔ آزمون باید در grades ثبت شود")
        self.assertEqual(grade.score, 12.0)
        self.assertEqual(grade.max_score, 20.0)

        notes = self.notifications(201, "student")
        self.assertTrue(any(n.type == "grade" for n in notes),
                        "دانش‌آموز باید اعلان ثبت نمرهٔ آزمون بگیرد")
        self.assertTrue(any(n.type == "exam" for n in notes),
                        "اعلان «آزمون جدید» هم باید در زمان ساخت آزمون ارسال شده باشد")

    def test_8_exam_notification_does_not_leak_to_archived_enrollment(self):
        """O-04 (رفع‌شده): اعلان «آزمون جدید» هم فقط برای ثبت‌نام‌های فعال ارسال می‌شود."""
        self.assertEqual(self.create_exam().status_code, 200)
        self.assertEqual(len(self.notifications(201, "student")), 1, "شاگردِ فعال اعلان می‌گیرد")
        self.assertEqual(self.notifications(203, "student"), [],
                         "شاگردِ حذف‌شده نباید اعلان آزمون بگیرد")

    def test_9_exam_visible_in_student_portal_with_int_max_score(self):
        exam_id = self.create_exam().json()["exam_id"]
        self.db.query(models.Exam).filter(models.Exam.id == exam_id).update({"max_score": 18.5})
        self.db.commit()
        profile = self.client.get("/students/my_profile", headers=hdr("tok-student"))
        exams = [e for e in profile.json()["exams"] if e["title"] == "آزمون فصل ۳"]
        self.assertEqual(len(exams), 1, "آزمون واقعی باید در پورتال شاگرد دیده شود")
        self.assertIsInstance(exams[0]["max_score"], int, "قرارداد کلاینت: max_score عدد صحیح")
        self.assertEqual(exams[0]["max_score"], 19, "۱۸.۵ ⇒ ۱۹ (گردکردن نیم‌به‌بالا)")

    def test_10_teacher_cannot_grade_homework_of_another_teacher(self):
        """گارد مالکیت: تصحیح تکلیف کلاس معلم دیگر باید ۴۰۳ بدهد."""
        other_teacher = models.Teacher(id=52, first_name="سارا", last_name="دیگر", mobile="09120000025",
                                       national_code="0012346004", password=hash_password("t2"),
                                       is_approved=True, is_deleted=False, branch_id=1)
        self.db.add(other_teacher)
        self.db.add(models.UserSession(token="tok-teacher2", user_id=52, teacher_id=52,
                                       sub_role="teacher", created_at=datetime.datetime.now()))
        self.db.commit()
        hw_id = self.create_homework().json()["id"]
        self.client.post(f"/homework/submissions/{hw_id}/submit",
                         files={"file": ("a.pdf", b"%PDF-1.4 x", "application/pdf")},
                         headers=hdr("tok-student"))
        sub = self.db.query(models.HomeworkSubmission).filter(
            models.HomeworkSubmission.homework_id == hw_id).first()
        resp = self.client.post(f"/homework/submissions/{sub.id}/grade",
                                json={"score": 20, "feedback": "x"}, headers=hdr("tok-teacher2"))
        self.assertEqual(resp.status_code, 403, resp.text)


class TestRemovedStudentAccess(HomeworkExamWorld):
    """دانش‌آموزی که ثبت‌نامش آرشیو شده (از کلاس حذف شده) هنوز چه دسترسی‌ای دارد؟

    مسیر حذف: ادمین → `DELETE /enrollments/{id}` (classes.py:489) → `perform_delete_enrollment`
    (dependencies.py:382) ⇒ `Enrollment.is_deleted = True`.
    """

    def test_11_removed_student_loses_homework_and_exam_access(self):
        """O-04 (رفع‌شده): دانش‌آموزی که ثبت‌نامش آرشیو شده، هیچ دسترسی‌ای به تکالیف/آزمون‌های
        آن کلاس ندارد و پورتال هم (که از قبل درست فیلتر می‌کرد) چیزی نشان نمی‌دهد.

        مسیر حذف: ادمین → `DELETE /enrollments/{id}` (classes.py:489) →
        `perform_delete_enrollment` (dependencies.py:382) ⇒ `Enrollment.is_deleted = True`.
        """
        hw = self.create_homework(title="تکلیف کلاسِ ترک‌شده").json()
        exam_id = self.create_exam().json()["exam_id"]
        self.client.post(f"/exams/{exam_id}/questions", json={
            "question_text": "۱+۱؟", "type": "multiple_choice", "options": "۱,۲",
            "correct_answer": "۲", "score_weight": 20.0}, headers=hdr("tok-teacher"))

        # ۱) لیست تکالیف: نباید تکلیف کلاسِ ترک‌شده را ببیند
        listing = self.client.get("/homework/student/list", headers=hdr("tok-student2"))
        self.assertEqual(listing.status_code, 200, listing.text)
        self.assertNotIn("تکلیف کلاسِ ترک‌شده", [h["title"] for h in listing.json()],
                         "شاگردِ حذف‌شده نباید تکلیف کلاس را ببیند")

        # ۲) تحویل فایل: باید ۴۰۳ بگیرد
        submit = self.client.post(f"/homework/submissions/{hw['id']}/submit",
                                  files={"file": ("x.pdf", b"%PDF-1.4 x", "application/pdf")},
                                  headers=hdr("tok-student2"))
        self.assertEqual(submit.status_code, 403, submit.text)
        self.assertIsNone(self.db.query(models.HomeworkSubmission).filter(
            models.HomeworkSubmission.homework_id == hw["id"],
            models.HomeworkSubmission.student_id == 42).first(),
            "هیچ ردیف تحویلی نباید ساخته شود")

        # ۳) شرکت در آزمون: باید ۴۰۳ بگیرد
        exam_start = self.client.post(f"/exams/attempts/{exam_id}/start", headers=hdr("tok-student2"))
        self.assertEqual(exam_start.status_code, 403, exam_start.text)
        self.assertIsNone(self.db.query(models.ExamAttempt).filter(
            models.ExamAttempt.exam_id == exam_id,
            models.ExamAttempt.student_id == 42).first(), "هیچ تلاش آزمونی ثبت نشود")

        # ۴) کارنامهٔ شاگرد (exams.py:330) هم نباید داده‌ای از کلاسِ ترک‌شده بدهد
        report_card = self.client.get("/students/42/report_card", headers=hdr("tok-admin"))
        self.assertEqual(report_card.status_code, 200, report_card.text)
        self.assertEqual(report_card.json().get("exams", []), [],
                         "کارنامه نباید آزمون کلاسِ ترک‌شده را نشان دهد")

        # ۵) پورتال (از قبل درست بود — شاهد ناسازگاری قبلی)
        portal = self.client.get("/students/my_profile", headers=hdr("tok-student2"))
        self.assertNotIn("تکلیف کلاسِ ترک‌شده", [h["title"] for h in portal.json()["homework"]])
        self.assertNotIn("آزمون فصل ۳", [e["title"] for e in portal.json()["exams"]])

    def test_12_active_student_keeps_full_access(self):
        """رگرسیون O-04: شاگردِ فعال همچنان تکلیف می‌بیند/تحویل می‌دهد و در آزمون شرکت می‌کند."""
        hw = self.create_homework().json()
        self.assertIn("صفحه ۲۵ تا ۳۰",
                      [h["title"] for h in self.client.get("/homework/student/list",
                                                           headers=hdr("tok-student")).json()])
        self.assertEqual(self.client.post(f"/homework/submissions/{hw['id']}/submit",
                                          files={"file": ("ok.pdf", b"%PDF-1.4 x", "application/pdf")},
                                          headers=hdr("tok-student")).status_code, 200)
        exam_id = self.create_exam().json()["exam_id"]
        self.assertEqual(self.client.post(f"/exams/attempts/{exam_id}/start",
                                          headers=hdr("tok-student")).status_code, 200)


if __name__ == "__main__":
    unittest.main()
