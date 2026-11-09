# test_portal_real_activity.py
# تست‌های C6 — تکالیف/آزمون‌ها/جلسات پیش‌روی **واقعی** در پورتال دانش‌آموز و ولی
#
# باگی که این تست‌ها قفل می‌کنند (همان باگ در **هر دو** پورتال):
#   GET /students/my_profile   (پورتال دانش‌آموز)  routers/students.py
#   GET /parent/child_profile  (پورتال ولی)        routers/parent.py
#   این دو اندپوینت سه لیست را **قالب ثابت جعلی** برمی‌گرداندند (به‌ازای هر کلاس دانش‌آموز):
#     تکلیف : «تمرین‌ها و حل مسائل فصل ۲ کتاب <نام کلاس>» — سررسید ثابت «۱۴۰۵/۰۶/۰۵»
#     آزمون : «آزمون هماهنگ مستمر کلاسی <نام کلاس>»      — تاریخ ثابت «۱۴۰۵/۰۶/۱۰»
#     جلسه  : «شنبه و دوشنبه‌ها» ساعت «۱۶:۰۰ الی ۱۷:۳۰»  — بی‌ربط به برنامهٔ واقعی کلاس
#   ⇒ هر خانواده یک تکلیف و آزمون قلابی می‌دید که هیچ معلمی ثبت نکرده بود، و تکالیف/آزمون‌های
#   واقعی هرگز در پورتال دیده نمی‌شدند (والدین به کارِ ناموجود رسیدگی می‌کردند و از کار واقعی
#   فرزند بی‌خبر می‌ماندند). برنامهٔ هفتگیِ واقعی کلاس هم نمایش داده نمی‌شد.
#
# قرارداد جدید: خواندن از جدول‌های واقعی `homeworks` / `exams` / `courses` با فیلتر
# ثبت‌نامِ فعال همان دانش‌آموز (منبع مشترک `portal_data.build_portal_activity`).
# کلیدها و نوع مقادیر پاسخ **بدون تغییر** ماندند (کلاینت منتشرشده می‌شکند اگر عوض شوند).
#
# اجرا (از ریشهٔ ریپو):
#   DATABASE_URL=sqlite:////tmp/c6_activity.db JWT_SECRET_KEY=<hex> \
#     python3 -m pytest Kharazmi_Server/test_portal_real_activity.py -q
import datetime
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from dependencies import get_db
from main import app

FAKE_HOMEWORK_PREFIX = "تمرین‌ها و حل مسائل فصل ۲ کتاب"
FAKE_EXAM_PREFIX = "آزمون هماهنگ مستمر کلاسی"
FAKE_DUE_DATE = "۱۴۰۵/۰۶/۰۵"
FAKE_EXAM_DATE = "۱۴۰۵/۰۶/۱۰"
FAKE_SESSION_DATE = "شنبه و دوشنبه‌ها"
FAKE_SESSION_TIME = "ساعت ۱۶:۰۰ الی ۱۷:۳۰"


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


class PortalActivityWorld(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                               poolclass=StaticPool)
        models.Base.metadata.create_all(engine)
        self.engine = engine
        Session = sessionmaker(bind=engine, expire_on_commit=False)
        self.db = Session()
        now = datetime.datetime.now()
        self.db.add_all([
            models.Branch(id=1, name="شعبه یک", active=True),
            models.User(id=10, username="student:1", password="x", full_name="شاگرد یک",
                        role="student", sub_role="student", branch_id=1),
            models.User(id=20, username="parent:1", password="x", full_name="ولی یک",
                        role="parent", sub_role="parent", branch_id=1),
            models.User(id=11, username="student:2", password="x", full_name="شاگرد دو",
                        role="student", sub_role="student", branch_id=1),
            models.Teacher(id=1, first_name="مریم", last_name="معلم", mobile="09120000041",
                           national_code="0012345621", password="x", is_approved=True,
                           is_deleted=False, branch_id=1),
            models.Student(id=1, student_code=1, first_name="علی", last_name="تست",
                           national_code="0012345622", student_mobile="09121111111",
                           branch_id=1, wallet_teacher=0, wallet_institute=0, wallet_balance=0,
                           is_deleted=False, user_id=10, parent_user_id=20),
            models.Student(id=2, student_code=2, first_name="زهرا", last_name="تست",
                           national_code="0012345623", student_mobile="09122222222",
                           branch_id=1, wallet_teacher=0, wallet_institute=0, wallet_balance=0,
                           is_deleted=False, user_id=11, parent_user_id=None),
        ])
        self.db.add_all([
            models.UserSession(token="tok-stud-1", user_id=10, sub_role="student", created_at=now),
            models.UserSession(token="tok-parent-1", user_id=20, sub_role="parent", created_at=now),
            models.UserSession(token="tok-stud-2", user_id=11, sub_role="student", created_at=now),
        ])

        # کلاس ۱: برنامهٔ واقعی دارد (شنبه/دوشنبه ۱۷:۳۰)
        self.course_1 = models.Course(id=1, title="ریاضی دهم", code="500001", teacher_id=1,
                                      branch_id=1, is_deleted=False, is_admin_approved=True,
                                      days_of_week="شنبه و دوشنبه", class_time="17:30",
                                      teacher_session_price=100000)
        # کلاس ۲: کلاس دیگری که دانش‌آموز ۱ در آن ثبت‌نام ندارد (نباید نشت کند)
        self.course_2 = models.Course(id=2, title="فیزیک یازدهم", code="500002", teacher_id=1,
                                      branch_id=1, is_deleted=False, is_admin_approved=True,
                                      days_of_week="یکشنبه", class_time="16:00",
                                      teacher_session_price=100000)
        # کلاس ۳: تعلیق‌شده (در «جلسات پیش‌رو» نیاید)
        self.course_suspended = models.Course(id=3, title="شیمی", code="500003", teacher_id=1,
                                              branch_id=1, is_deleted=False, is_suspended=True,
                                              is_admin_approved=True, days_of_week="سه‌شنبه",
                                              class_time="15:00", teacher_session_price=100000)
        # کلاس ۴: آرشیوشده (نه تکلیف نه جلسه)
        self.course_deleted = models.Course(id=4, title="زیست حذف‌شده", code="500004", teacher_id=1,
                                            branch_id=1, is_deleted=True, is_admin_approved=True,
                                            days_of_week="چهارشنبه", class_time="14:00",
                                            teacher_session_price=100000)
        # کلاس ۵: legacy بدون نام و بدون برنامه (نباید "None" یا زمان جعلی بدهد)
        self.course_legacy = models.Course(id=5, title=None, code="500005", teacher_id=1,
                                           branch_id=1, is_deleted=False, is_admin_approved=True,
                                           days_of_week=None, class_time=None,
                                           teacher_session_price=100000)
        self.db.add_all([self.course_1, self.course_2, self.course_suspended,
                         self.course_deleted, self.course_legacy])

        self.db.add_all([
            models.Enrollment(id=1, student_id=1, course_id=1, branch_id=1, register_date="1405/06/01",
                              shift="عصر", total_tuition=1000000, total_paid=0, is_deleted=False),
            models.Enrollment(id=4, student_id=1, course_id=4, branch_id=1, register_date="1405/06/01",
                              shift="عصر", total_tuition=1000000, total_paid=0, is_deleted=False),
            models.Enrollment(id=5, student_id=1, course_id=5, branch_id=1, register_date="1405/06/01",
                              shift="عصر", total_tuition=1000000, total_paid=0, is_deleted=False),
            # ثبت‌نام حذف‌شدهٔ کلاس ۲ ⇒ کلاس نباید در پورتال بیاید
            models.Enrollment(id=2, student_id=1, course_id=2, branch_id=1, register_date="1405/06/01",
                              shift="عصر", total_tuition=1000000, total_paid=0, is_deleted=True),
            models.Enrollment(id=3, student_id=2, course_id=2, branch_id=1, register_date="1405/06/01",
                              shift="عصر", total_tuition=1000000, total_paid=0, is_deleted=False),
        ])

        # تکالیف/آزمون‌های واقعی (کلاس ۱ برای دانش‌آموز ۱)
        self.hw_real = models.Homework(id=1, course_id=1, teacher_id=1,
                                       title="صفحه ۲۵ تا ۳۰ کتاب", description="تمرین‌های فصل سوم",
                                       due_date="1405/06/12", max_score=20.0, status="pending")
        self.hw_deleted_course = models.Homework(id=2, course_id=4, teacher_id=1,
                                                title="تکلیف کلاس حذف‌شده",
                                                due_date="1405/06/13", max_score=20.0, status="pending")
        self.hw_other_student = models.Homework(id=3, course_id=2, teacher_id=1,
                                               title="تکلیف کلاس دیگر",
                                               due_date="1405/06/14", max_score=20.0, status="pending")
        self.exam_real = models.Exam(id=1, course_id=1, teacher_id=1, title="آزمون فصل سوم",
                                     date="1405/06/20", duration=60, max_score=20.0, status="published")
        self.exam_float = models.Exam(id=2, course_id=1, teacher_id=1, title="آزمون مستمر شفاهی",
                                      date="1405/06/25", duration=30, max_score=18.5, status="published")
        self.exam_other = models.Exam(id=3, course_id=2, teacher_id=1, title="آزمون کلاس دیگر",
                                      date="1405/06/22", duration=60, max_score=20.0, status="published")
        self.db.add_all([self.hw_real, self.hw_deleted_course, self.hw_other_student,
                         self.exam_real, self.exam_float, self.exam_other])
        self.db.commit()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    # ---------------- کمکی ----------------
    def student_profile(self, tok="tok-stud-1"):
        resp = self.client.get("/students/my_profile", headers=hdr(tok))
        self.assertEqual(resp.status_code, 200, resp.text[:200])
        return resp.json()

    def parent_profile(self, tok="tok-parent-1"):
        resp = self.client.get("/parent/child_profile", headers=hdr(tok))
        self.assertEqual(resp.status_code, 200, resp.text[:200])
        return resp.json()

    def both(self):
        return [("student", self.student_profile()), ("parent", self.parent_profile())]


class TestRealHomeworkExamsAndSessions(PortalActivityWorld):
    # ------------------------------------------------------------------
    # ۱) هیچ داده‌ی جعلی
    # ------------------------------------------------------------------
    def test_1_no_fake_rows_in_either_portal(self):
        for who, body in self.both():
            for item in body["homework"]:
                self.assertNotIn(FAKE_HOMEWORK_PREFIX, item["title"], who)
                self.assertNotEqual(item["due_date"], FAKE_DUE_DATE, who)
            for item in body["exams"]:
                self.assertNotIn(FAKE_EXAM_PREFIX, item["title"], who)
                self.assertNotEqual(item["date"], FAKE_EXAM_DATE, who)
            for item in body["upcoming_sessions"]:
                self.assertNotEqual(item["date"], FAKE_SESSION_DATE, who)
                self.assertNotEqual(item["time"], FAKE_SESSION_TIME, who)

    def test_2_real_homework_is_shown(self):
        for who, body in self.both():
            titles = [h["title"] for h in body["homework"]]
            self.assertEqual(titles, ["صفحه ۲۵ تا ۳۰ کتاب"], who)
            row = body["homework"][0]
            self.assertEqual(row["course_title"], "ریاضی دهم", who)
            self.assertEqual(row["due_date"], "1405/06/12", who)
            self.assertEqual(row["status"], "در انتظار تحویل", who)

    def test_3_real_exams_are_shown(self):
        for who, body in self.both():
            titles = sorted(e["title"] for e in body["exams"])
            self.assertEqual(titles, ["آزمون فصل سوم", "آزمون مستمر شفاهی"], who)
            by_title = {e["title"]: e for e in body["exams"]}
            self.assertEqual(by_title["آزمون فصل سوم"]["date"], "1405/06/20", who)
            self.assertEqual(by_title["آزمون فصل سوم"]["course_title"], "ریاضی دهم", who)

    def test_4_max_score_is_always_int(self):
        """قرارداد کلاینت (ParentExamItem.max_score: Int) — عدد اعشاری باعث خطای Gson می‌شود."""
        for who, body in self.both():
            for item in body["exams"]:
                self.assertIsInstance(item["max_score"], int, f"{who}: {item['max_score']!r}")
            by_title = {e["title"]: e for e in body["exams"]}
            self.assertEqual(by_title["آزمون فصل سوم"]["max_score"], 20)
            self.assertEqual(by_title["آزمون مستمر شفاهی"]["max_score"], 19, "۱۸.۵ ⇒ ۱۹ (گرد شده)")

    def test_5_real_weekly_schedule_is_shown(self):
        for who, body in self.both():
            rows = {r["course_title"]: r for r in body["upcoming_sessions"]}
            self.assertIn("ریاضی دهم", rows, who)
            self.assertEqual(rows["ریاضی دهم"]["date"], "شنبه و دوشنبه", who)
            self.assertEqual(rows["ریاضی دهم"]["time"], "17:30", who)

    # ------------------------------------------------------------------
    # ۲) عدم نشت بین دانش‌آموز/کلاس‌ها
    # ------------------------------------------------------------------
    def test_6_no_leak_from_other_courses_or_students(self):
        for who, body in self.both():
            hw_titles = [h["title"] for h in body["homework"]]
            exam_titles = [e["title"] for e in body["exams"]]
            self.assertNotIn("تکلیف کلاس دیگر", hw_titles, who)          # کلاس بدون ثبت‌نام فعال
            self.assertNotIn("تکلیف کلاس حذف‌شده", hw_titles, who)        # کلاس آرشیوشده
            self.assertNotIn("آزمون کلاس دیگر", exam_titles, who)
            self.assertNotIn("شیمی", [r["course_title"] for r in body["upcoming_sessions"]], who)
            self.assertNotIn("زیست حذف‌شده", [r["course_title"] for r in body["upcoming_sessions"]], who)

    def test_7_student_two_does_not_see_student_one_data(self):
        body = self.client.get("/students/my_profile", headers=hdr("tok-stud-2")).json()
        self.assertEqual([h["title"] for h in body["homework"]], ["تکلیف کلاس دیگر"])
        self.assertEqual([e["title"] for e in body["exams"]], ["آزمون کلاس دیگر"])
        # کلاس ۱ (ثبت‌نام دانش‌آموز ۱) نباید در برنامهٔ هفتگی دانش‌آموز ۲ باشد
        self.assertNotIn("ریاضی دهم", [r["course_title"] for r in body["upcoming_sessions"]])

    # ------------------------------------------------------------------
    # ۳) وضعیت هر دانش‌آموز جدا محاسبه می‌شود (نه فقط وضعیت کلاس)
    # ------------------------------------------------------------------
    def test_8_per_student_submission_status(self):
        self.assertEqual(self.student_profile()["homework"][0]["status"], "در انتظار تحویل")
        self.db.add(models.HomeworkSubmission(id=1, homework_id=1, student_id=1,
                                              file_path="/uploads/hw/ali.pdf", status="graded",
                                              score=19.5, submitted_at=datetime.datetime(2026, 9, 20)))
        self.db.commit()
        self.assertEqual(self.student_profile()["homework"][0]["status"], "تصحیح شده")
        self.assertEqual(self.parent_profile()["homework"][0]["status"], "تصحیح شده")
        # دانش‌آموز دیگر همان تکلیف را تحویل نداده ⇒ وضعیت خودش (pending) + کد ناشناخته عیناً
        self.db.query(models.HomeworkSubmission).filter(models.HomeworkSubmission.id == 1).update(
            {"status": "معلوم نیست"})
        self.db.commit()
        self.assertEqual(self.student_profile()["homework"][0]["status"], "معلوم نیست")

    # ------------------------------------------------------------------
    # ۴) کلاس legacy بدون نام/برنامه: نه «None»، نه زمان جعلی
    # ------------------------------------------------------------------
    def test_9_legacy_course_is_null_safe(self):
        for who, body in self.both():
            self.assertNotIn("None", str(body["homework"]), who)
            self.assertNotIn("None", str(body["exams"]), who)
            # کلاس بدون روز/ساعت در «جلسات پیش‌رو» نمی‌آید (به‌جای زمان ساختگی)
            self.assertNotIn("کلاس بدون نام", [r["course_title"] for r in body["upcoming_sessions"]], who)

    # ------------------------------------------------------------------
    # ۵) کلاس بدون هیچ تکلیف/آزمون ⇒ لیست خالی (نه ردیف جعلی)
    # ------------------------------------------------------------------
    def test_10_empty_when_nothing_registered(self):
        self.db.query(models.Homework).delete()
        self.db.query(models.Exam).delete()
        self.db.commit()
        for who, body in self.both():
            self.assertEqual(body["homework"], [], who)
            self.assertEqual(body["exams"], [], who)

    def test_11_no_enrollments_means_empty_lists(self):
        self.db.query(models.Enrollment).delete()
        self.db.commit()
        for who, body in self.both():
            self.assertEqual(body["homework"], [], who)
            self.assertEqual(body["exams"], [], who)
            self.assertEqual(body["upcoming_sessions"], [], who)

    # ------------------------------------------------------------------
    # ۶) قرارداد پاسخ: همان کلیدها و همان انواع (کلاینت منتشرشده نشکند)
    # ------------------------------------------------------------------
    def test_12_response_keys_unchanged(self):
        for who, body in self.both():
            self.assertEqual(set(body.keys()),
                             {"info", "classes", "wallet", "grades", "averages", "attendance",
                              "installments", "homework", "exams", "upcoming_sessions",
                              "notifications"}, who)
            for item in body["homework"]:
                self.assertEqual(set(item.keys()), {"course_title", "title", "due_date", "status"}, who)
                for value in item.values():
                    self.assertIsInstance(value, str, who)
            for item in body["exams"]:
                self.assertEqual(set(item.keys()), {"course_title", "title", "date", "max_score"}, who)
                self.assertIsInstance(item["max_score"], int, who)
            for item in body["upcoming_sessions"]:
                self.assertEqual(set(item.keys()), {"course_title", "date", "time"}, who)
                for value in item.values():
                    self.assertIsInstance(value, str, who)

    # ------------------------------------------------------------------
    # ۷) ترتیب قطعی + سقف لیست
    # ------------------------------------------------------------------
    def test_13_order_and_limit(self):
        for i in range(60):
            self.db.add(models.Homework(id=100 + i, course_id=1, teacher_id=1,
                                        title=f"تکلیف شماره {i}", due_date=f"1405/07/{i:02d}",
                                        max_score=20.0, status="pending"))
            self.db.add(models.Exam(id=100 + i, course_id=1, teacher_id=1,
                                    title=f"آزمون شماره {i}", date=f"1405/07/{i:02d}",
                                    duration=60, max_score=20.0, status="published"))
        self.db.commit()
        for who, body in self.both():
            self.assertEqual(len(body["homework"]), 50, who)   # سقف PORTAL_ITEMS_LIMIT
            self.assertEqual(len(body["exams"]), 50, who)
            # تازه‌ترین رکورد (بزرگ‌ترین id) اول می‌آید و ترتیب پایدار است
            self.assertEqual(body["homework"][0]["title"], "تکلیف شماره 59", who)
            self.assertEqual(body["exams"][0]["title"], "آزمون شماره 59", who)
            self.assertEqual(body["homework"][1]["title"], "تکلیف شماره 58", who)

    def test_14_helper_level_direct_call(self):
        """شاخهٔ دفاعی: بدون ثبت‌نام، helper مستقیم لیست خالی می‌دهد (بدون استثنا)."""
        import portal_data
        from models import Student

        student = self.db.query(Student).filter(Student.id == 1).first()
        self.db.query(models.Enrollment).delete()
        self.db.commit()
        self.assertEqual(portal_data.build_portal_homework(self.db, student), [])
        self.assertEqual(portal_data.build_portal_exams(self.db, student), [])
        self.assertEqual(portal_data.build_portal_upcoming_sessions(self.db, student), [])
        self.assertEqual(portal_data.build_portal_activity(self.db, student),
                         {"homework": [], "exams": [], "upcoming_sessions": []})


if __name__ == "__main__":
    unittest.main()
