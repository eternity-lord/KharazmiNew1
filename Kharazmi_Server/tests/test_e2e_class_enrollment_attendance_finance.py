# test_e2e_class_enrollment_attendance_finance.py
# ═══════════════════════════════════════════════════════════════════════════════
# سناریوی end-to-end #۲: «کلاس → ثبت‌نام → حضور و غیاب → اثر مالی»
#
# همان کاری که ادمین در اپ انجام می‌دهد، مرحله‌به‌مرحله:
#   ۱) AddClassActivity      → POST classes/create            (ساخت کلاس)
#   ۲) ClassSetupActivity    → POST enrollments/add           (ثبت‌نام + شهریه/پیش‌پرداخت)
#   ۳) AttendanceActivity    → POST attendance/submit_session (ثبت جلسه و حضور/غیاب)
#   ۴) و بعد: اثر روی کیف پول شاگرد، بدهی، تراکنش‌ها و طلب معلم.
#
# مرجع سمت اندروید: AddClassActivity.kt:21-24 · ClassSetupActivity.kt:40-46 ·
#                   AttendanceActivity.kt:35-41 · StudentProfileActivity.kt:86 (طلب معلم)
# مرجع سمت سرور:    routers/classes.py:77 (create) و :373 (enrollments/add) ·
#                   routers/attendance.py:442 (submit_session)
#
# اجرا (از ریشهٔ ریپو):
#   DATABASE_URL=sqlite:////tmp/e2e_class.db JWT_SECRET_KEY=<hex> \
#     python3 -m pytest Kharazmi_Server/tests/test_e2e_class_enrollment_attendance_finance.py -q
#
# ⚠ فاز دیباگ: هیچ کد برنامه‌ای تغییر نمی‌کند؛ فقط سنجش رفتار + مستندسازی باگ.
import datetime
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from dependencies import get_db, hash_password, limiter
from main import app

ADMIN_MOBILE = "09120000011"
JALALI_TODAY = "1405/06/30"


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


class ClassFlowWorld(unittest.TestCase):
    def setUp(self):
        self._limiter = limiter.enabled
        limiter.enabled = False
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                               poolclass=StaticPool)
        models.Base.metadata.create_all(engine)
        self.engine = engine
        self.db = sessionmaker(bind=engine, expire_on_commit=False)()

        self.db.add(models.Branch(id=1, name="شعبه مرکزی", active=True))
        self.admin = models.User(id=101, username=ADMIN_MOBILE, password=hash_password("admin-pass"),
                                 full_name="مدیر کل", role="admin", sub_role="admin", branch_id=1)
        self.teacher = models.Teacher(id=51, first_name="مریم", last_name="تست", mobile="09120000012",
                                      national_code="0012345901", password=hash_password("t-pass"),
                                      is_approved=True, is_deleted=False, is_suspended=False, branch_id=1)
        self.student = models.Student(id=41, student_code=41, first_name="علی", last_name="تست",
                                      national_code="0012345902", student_mobile="09120000013",
                                      branch_id=1, wallet_teacher=0, wallet_institute=0,
                                      wallet_balance=0, is_deleted=False, is_suspended=False)
        self.db.add_all([self.admin, self.teacher, self.student])
        self.db.commit()

        self.db.add(models.UserSession(token="tok-admin", user_id=101, sub_role="admin",
                                       created_at=datetime.datetime.now()))
        # تعرفهٔ سهم آموزشگاه: بدون این ردیف، ثبت جلسه با «۵۰۰» رد می‌شود (یافتهٔ همین نوبت).
        self.db.add(models.InstituteShare(id=1, count_1=50000, count_2=80000, count_3=100000))
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
    def create_class(self, title="ریاضی دهم", days="شنبه", time="17:30", price=150000, token="tok-admin"):
        payload = {
            "title": title, "code": "999", "teacher_id": self.teacher.id,
            "education_type": "عادی", "grade_level": "دهم", "gender_type": "مختلط",
            "class_type": "خصوصی", "days_of_week": days, "class_time": time,
            "teacher_session_price": price, "branch_id": 1,
        }
        return self.client.post("/classes/create", json=payload, headers=hdr(token))

    def enroll(self, course_id, student_id=None, tuition=1000000, paid=400000, token="tok-admin"):
        payload = {
            "student_id": student_id or self.student.id, "course_id": course_id,
            "register_date": "1405/06/01", "shift": "عصر", "total_tuition": tuition,
            "paid_amount": paid, "payment_method": "کارت", "receiver": "مدیر",
        }
        return self.client.post("/enrollments/add", json=payload, headers=hdr(token))

    def submit_session(self, course_id, statuses, date=JALALI_TODAY, token="tok-admin"):
        items = [{"student_id": sid, "status": st, "excused": False} for sid, st in statuses]
        return self.client.post("/attendance/submit_session",
                                json={"course_id": course_id, "date": date, "items": items},
                                headers=hdr(token))

    def wallet_of(self, student_id=41):
        row = self.db.query(models.Student).filter(models.Student.id == student_id).first()
        self.db.refresh(row)
        return row


class TestClassCreation(ClassFlowWorld):
    def test_1_admin_creates_class_and_row_is_persisted(self):
        resp = self.create_class()
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["status"], "success")
        course = self.db.query(models.Course).filter(models.Course.id == body["id"]).first()
        self.assertIsNotNone(course)
        self.assertEqual(course.title, "ریاضی دهم")
        self.assertEqual(course.teacher_id, self.teacher.id)
        self.assertEqual(course.branch_id, 1, "کلاس باید شعبه داشته باشد (سیاست resolve_creation_branch)")
        self.assertEqual(course.code, body["code"])
        self.assertFalse(bool(course.is_deleted))

    def test_2_same_time_clash_returns_warning_without_creating_class(self):
        self.assertEqual(self.create_class().status_code, 200)
        clash = self.create_class(title="کلاس دوم", days="شنبه", time="18:00")
        self.assertEqual(clash.status_code, 200)
        self.assertEqual(clash.json()["status"], "warning", "تداخل زمانی باید هشدار بدهد، نه ثبت کورکورانه")
        self.assertEqual(self.db.query(models.Course).count(), 1, "در حالت هشدار نباید کلاس ساخته شود")


class TestEnrollment(ClassFlowWorld):
    def setUp(self):
        super().setUp()
        self.course_id = self.create_class().json()["id"]

    def test_3_enrollment_persists_with_payment_and_institute_wallet(self):
        resp = self.enroll(self.course_id)
        self.assertEqual(resp.status_code, 200, resp.text)
        enroll = self.db.query(models.Enrollment).filter(
            models.Enrollment.student_id == 41, models.Enrollment.course_id == self.course_id).first()
        self.assertIsNotNone(enroll, "ثبت‌نام باید در DB ذخیره شود")
        self.assertEqual(enroll.total_tuition, 1000000)
        self.assertEqual(enroll.total_paid, 400000)
        self.assertFalse(bool(enroll.is_deleted))

        tx = self.db.query(models.Transaction).filter(
            models.Transaction.student_id == 41,
            models.Transaction.type == "enrollment_payment").first()
        self.assertIsNotNone(tx, "پیش‌پرداخت ثبت‌نام باید تراکنش داشته باشد")
        self.assertEqual(tx.amount, 400000)
        self.assertEqual(tx.target_wallet, "institute")
        self.assertEqual(self.wallet_of().wallet_institute, 400000,
                         "پیش‌پرداخت باید به کیف پول مؤسسه برود (Bug 18)")
        self.assertEqual(self.wallet_of().wallet_balance, 400000)

    def test_4_duplicate_enrollment_is_rejected(self):
        self.assertEqual(self.enroll(self.course_id).status_code, 200)
        again = self.enroll(self.course_id)
        self.assertIn(again.status_code, (400, 409), again.text)
        self.assertEqual(self.db.query(models.Enrollment).filter(
            models.Enrollment.student_id == 41, models.Enrollment.is_deleted == False).count(), 1)  # noqa: E712


class TestAttendanceAndFinancialEffect(ClassFlowWorld):
    def setUp(self):
        super().setUp()
        self.course_id = self.create_class(price=150000).json()["id"]
        self.enroll(self.course_id)

    def test_5_session_submission_creates_rows_and_charges_student(self):
        before = self.wallet_of()
        before_balance = before.wallet_balance
        resp = self.submit_session(self.course_id, [(41, "Present")])
        self.assertEqual(resp.status_code, 200, resp.text)

        session = self.db.query(models.SessionLog).filter(
            models.SessionLog.course_id == self.course_id).first()
        self.assertIsNotNone(session, "جلسه باید در session_logs ذخیره شود")
        self.assertEqual(session.date, JALALI_TODAY)
        self.assertFalse(bool(session.is_deleted))

        att = self.db.query(models.Attendance).filter(
            models.Attendance.session_id == session.id,
            models.Attendance.student_id == 41).first()
        self.assertIsNotNone(att, "حضور/غیاب باید ثبت شود")
        self.assertEqual(att.status, "Present")

        tx = self.db.query(models.Transaction).filter(
            models.Transaction.student_id == 41,
            models.Transaction.type == "session_charge").first()
        self.assertIsNotNone(tx, "هزینهٔ جلسه باید تراکنش داشته باشد")
        self.assertEqual(tx.session_id, session.id, "تراکنش شارژ باید به همان جلسه وصل باشد")
        self.assertEqual(tx.share_teacher, 150000, "سهم معلم = نرخ جلسهٔ کلاس × تعداد حاضر")
        self.assertEqual(tx.share_institute, 50000, "سهم آموزشگاه از جدول InstituteShare.count_1")
        self.assertEqual(tx.amount, -200000, "مبلغ تراکنش شارژ منفی و برابر مجموع سهم‌هاست")
        self.assertLess(self.wallet_of().wallet_teacher, 0, "سهم معلم از کیف شاگرد کسر می‌شود ⇒ بدهی")

        after = self.wallet_of()
        self.assertLessEqual(after.wallet_teacher, before.wallet_teacher + 1e-6,
                             "هزینهٔ جلسه باید از کیف پول شاگرد کسر شود")
        self.assertEqual(after.wallet_balance,
                         (after.wallet_teacher or 0) + (after.wallet_institute or 0),
                         "wallet_balance باید همیشه جمع دو کیف باشد (sync_wallet_balance)")
        self.assertNotEqual(after.wallet_balance, before_balance, "اثر مالی جلسه باید دیده شود")

    def test_6_teacher_pending_settlement_reflects_the_session(self):
        pending_before = self.client.get(f"/teachers/{self.teacher.id}/pending_settlement",
                                         headers=hdr("tok-admin")).json()
        self.assertEqual(self.submit_session(self.course_id, [(41, "Present")]).status_code, 200)
        pending_after = self.client.get(f"/teachers/{self.teacher.id}/pending_settlement",
                                        headers=hdr("tok-admin")).json()
        self.assertNotEqual(pending_before, pending_after,
                            "ثبت جلسه باید در «طلب معلم» دیده شود (هم‌راستا با تسک ۵)")

    def test_7_duplicate_session_date_is_rejected_with_409(self):
        self.assertEqual(self.submit_session(self.course_id, [(41, "Present")]).status_code, 200)
        dup = self.submit_session(self.course_id, [(41, "Present")])
        self.assertEqual(dup.status_code, 409, dup.text)
        self.assertEqual(self.db.query(models.SessionLog).filter(
            models.SessionLog.course_id == self.course_id,
            models.SessionLog.is_deleted == False).count(), 1)  # noqa: E712

    def test_8a_missing_institute_share_is_a_clear_4xx(self):
        """O-06 (رفع‌شده): نبودِ تعرفهٔ سهم آموزشگاه ⇒ **۴۰۰** با همان پیام راهنما (نه ۵۰۰).

        فلسفهٔ H5 «خطای واضح به‌جای جلسهٔ مجانی ساکت» دست‌نخورده است؛ فقط کد وضعیت از
        «خطای سرور» به «خطای تنظیمات/درخواست» اصلاح شد تا ادمین‌ها راهنمای درست ببینند.
        """
        self.db.query(models.InstituteShare).delete()
        self.db.commit()
        resp = self.submit_session(self.course_id, [(41, "Present")], date="1405/07/05")
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertIn("تعرفه", resp.json()["detail"])
        self.assertEqual(self.db.query(models.SessionLog).count(), 0, "در این حالت جلسه‌ای ثبت نمی‌شود")

    def test_8b_class_without_session_price_needs_pricing_table(self):
        """کلاس بدون «نرخ هر جلسه» + نبود تعرفهٔ مقطعی ⇒ ۴۰۰ با پیام راهنما (O-06)."""
        plain = self.create_class(title="کلاس بدون نرخ", days="یکشنبه", time="10:00", price=0).json()["id"]
        self.enroll(plain)
        resp = self.submit_session(plain, [(41, "Present")], date="1405/07/06")
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertIn("تعرفه", resp.json()["detail"])

    def test_8_absent_student_is_not_charged_when_excused(self):
        excused = self.client.post("/attendance/submit_session",
                                   json={"course_id": self.course_id, "date": "1405/07/01",
                                         "items": [{"student_id": 41, "status": "Absent", "excused": True}]},
                                   headers=hdr("tok-admin"))
        self.assertEqual(excused.status_code, 200, excused.text)
        tx = self.db.query(models.Transaction).filter(
            models.Transaction.student_id == 41,
            models.Transaction.type == "session_charge").all()
        self.assertEqual(tx, [], "غیبت موجه نباید هزینهٔ جلسه بسازد")
        self.assertEqual(self.wallet_of().wallet_teacher, 0)


if __name__ == "__main__":
    unittest.main()
