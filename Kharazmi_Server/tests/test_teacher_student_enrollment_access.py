# test_teacher_student_enrollment_access.py
# معلم پس از ساخت کلاس باید بتواند برای کلاسِ خودش دانش‌آموز ثبت‌نام کند و دانش‌آموز جدید بسازد.
#
# وضعیت قبلی (باگ گزارش‌شده): هر دو مسیر «افزودن دانش‌آموز به کلاس» و «ثبت‌نام دانش‌آموز جدید»
# با `check_admin_or_secretary_access` محافظت می‌شدند ⇒ معلم ۴۰۳ «شما دسترسی لازم…» می‌گرفت و
# کلاس تازه‌ساخته‌شده‌اش عملاً خالی می‌ماند.
#
# سیاست فیکس (حداقلی و امن):
#   • معلم مجاز است، **فقط** برای کلاس‌های خودش (Course.teacher_id == پروندهٔ معلمِ همان سشن).
#   • کلاس معلم دیگر ⇒ ۴۰۳ و هیچ نوشتنی.
#   • شعبهٔ ثبت‌نام/شاگرد همان سیاست مرکزی resolve_creation_branch (شعبهٔ خودِ معلم).
#   • منطق مالی دست‌نخورده: همان Enrollment/Installment/Transaction و همان کیف‌ها.
#   • ادمین/منشی مثل قبل؛ شاگرد/ولی همچنان ۴۰۳.
#
# اجرا (روی DB موقت — نه DB واقعی):
#   DATABASE_URL=sqlite:////tmp/teacher_enroll.db python3 -m pytest Kharazmi_Server/tests/test_teacher_student_enrollment_access.py -q
import datetime
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from dependencies import get_db, hash_password, limiter
from main import app


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


class TeacherEnrollmentWorld(unittest.TestCase):
    def setUp(self):
        self._limiter = limiter.enabled
        limiter.enabled = False
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                               poolclass=StaticPool)
        models.Base.metadata.create_all(engine)
        self.engine = engine
        self.db = sessionmaker(bind=engine, expire_on_commit=False)()
        now = datetime.datetime.now()

        self.db.add(models.Branch(id=1, name="شعبه یک", active=True))
        # تعرفه لازم نیست: معلم نرخ جلسه روی کلاس دارد و شهریهٔ ثبت‌نام هم صریح داده می‌شود.
        self.db.add_all([
            models.User(id=101, username="09120001001", password=hash_password("a"), full_name="مدیر",
                        role="admin", sub_role="admin", branch_id=1),
            models.User(id=102, username="09120001002", password=hash_password("b"), full_name="منشی",
                        role="secretary", sub_role="secretary", branch_id=1),
            # معلم اول (مالک کلاس 71)
            models.User(id=51, username="09120001051", password=hash_password("t"), full_name="مریم معلم",
                        role="teacher", sub_role="teacher", branch_id=1),
            # معلم دوم (مالک کلاس 72)
            models.User(id=52, username="09120001052", password=hash_password("t"), full_name="سارا معلم",
                        role="teacher", sub_role="teacher", branch_id=1),
            models.User(id=201, username="student:41", password="x", full_name="علی تست",
                        role="student", sub_role="student", branch_id=1),
            models.User(id=202, username="parent:41", password="x", full_name="ولی علی",
                        role="parent", sub_role="parent", branch_id=1),
        ])
        self.db.add_all([
            models.Teacher(id=51, first_name="مریم", last_name="معلم", mobile="09120001051",
                           national_code="0012349001", password=hash_password("t"),
                           is_approved=True, is_deleted=False, branch_id=1),
            models.Teacher(id=52, first_name="سارا", last_name="معلم", mobile="09120001052",
                           national_code="0012349002", password=hash_password("t"),
                           is_approved=True, is_deleted=False, branch_id=1),
        ])
        self.db.add_all([
            models.Course(id=71, title="ریاضی معلم اول", code="710001", teacher_id=51, branch_id=1,
                          is_deleted=False, grade_level="دهم", teacher_session_price=100000),
            models.Course(id=72, title="فیزیک معلم دوم", code="720001", teacher_id=52, branch_id=1,
                          is_deleted=False, grade_level="دهم", teacher_session_price=100000),
            models.Course(id=73, title="کلاس آرشیوی معلم اول", code="730001", teacher_id=51,
                          branch_id=1, is_deleted=True, grade_level="دهم", teacher_session_price=100000),
        ])
        self.db.add(models.Student(id=41, student_code=41, first_name="علی", last_name="تست",
                                   national_code="0012349003", student_mobile="09120001061",
                                   parent_mobile="09120001062", branch_id=1, user_id=201,
                                   parent_user_id=202, is_deleted=False,
                                   wallet_teacher=0, wallet_institute=0, wallet_balance=0))
        self.db.add_all([
            models.UserSession(token="tok-admin", user_id=101, sub_role="admin", created_at=now),
            models.UserSession(token="tok-secretary", user_id=102, sub_role="secretary", created_at=now),
            models.UserSession(token="tok-teacher1", user_id=51, teacher_id=51, sub_role="teacher",
                               created_at=now),
            models.UserSession(token="tok-teacher2", user_id=52, teacher_id=52, sub_role="teacher",
                               created_at=now),
            models.UserSession(token="tok-student", user_id=201, sub_role="student", created_at=now),
            models.UserSession(token="tok-parent", user_id=202, sub_role="parent", created_at=now),
        ])
        self.db.commit()

        app.dependency_overrides[get_db] = lambda: (yield self.db)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close() if hasattr(self.client, "close") else None
        app.dependency_overrides.clear()
        limiter.enabled = self._limiter
        self.db.close()
        self.engine.dispose()

    # ── کمک‌تابع‌ها ─────────────────────────────────────────────────────
    def enroll_payload(self, course_id, student_id=41, paid=0):
        return {
            "student_id": student_id, "course_id": course_id, "register_date": "1405/06/30",
            "shift": "عصر", "total_tuition": 1_000_000, "paid_amount": paid,
            "payment_method": "cash", "receiver": "معلم",
        }

    def register_payload(self, course_id, national_code="0012349011", paid=0):
        return {
            "first_name": "زهرا", "last_name": "جدید", "father_name": "حسن", "national_code": national_code,
            "birth_date": "1390/01/01", "student_mobile": "09120001071", "parent_mobile": "09120001072",
            "home_phone": "02122334455", "address": "تهران", "study_status": "در حال تحصیل",
            "gender": "دختر", "course_id": course_id, "total_tuition": 1_000_000,
            "paid_amount": paid, "payment_method": "cash", "receiver": "معلم",
            "register_date": "1405/06/30", "shift": "عصر",
        }

    def enrollments(self):
        return self.db.query(models.Enrollment).all()

    # ── ۱) افزودن دانش‌آموز موجود به کلاسِ خودِ معلم ──────────────────────
    def test_1_teacher_can_add_existing_student_to_own_class(self):
        resp = self.client.post("/enrollments/add", json=self.enroll_payload(71),
                                headers=hdr("tok-teacher1"))
        self.assertEqual(resp.status_code, 200, resp.text)
        rows = self.enrollments()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].course_id, 71)
        self.assertEqual(rows[0].branch_id, 1, "شعبهٔ ثبت‌نام باید شعبهٔ معلم باشد")

    # ── ۲) معلم نمی‌تواند در کلاس معلم دیگر ثبت‌نام کند ────────────────────
    def test_2_teacher_cannot_enroll_into_another_teachers_class(self):
        resp = self.client.post("/enrollments/add", json=self.enroll_payload(72),
                                headers=hdr("tok-teacher1"))
        self.assertEqual(resp.status_code, 403, resp.text)
        self.assertEqual(self.enrollments(), [], "نباید رکوردی نوشته شود")

    # ── ۳) کلاس آرشیوشده همچنان ۴۰۴ (سیاست H10 دست‌نخورده) ────────────────
    def test_3_archived_own_class_is_still_404(self):
        resp = self.client.post("/enrollments/add", json=self.enroll_payload(73),
                                headers=hdr("tok-teacher1"))
        self.assertEqual(resp.status_code, 404, resp.text)
        self.assertEqual(self.enrollments(), [])

    # ── ۴) ثبت دانش‌آموز جدید توسط معلم برای کلاس خودش ─────────────────────
    def test_4_teacher_can_register_new_student_for_own_class(self):
        resp = self.client.post("/students/register_and_enroll", json=self.register_payload(71),
                                headers=hdr("tok-teacher1"))
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        student = self.db.query(models.Student).filter(models.Student.id == body["id"]).first()
        self.assertIsNotNone(student, "دانش‌آموز باید ساخته شده باشد")
        self.assertEqual(student.branch_id, 1)
        rows = self.enrollments()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].course_id, 71)

    # ── ۵) ثبت دانش‌آموز جدید برای کلاس معلم دیگر ⇒ ۴۰۳ بدون نوشتن ─────────
    def test_5_teacher_cannot_register_student_into_foreign_class(self):
        resp = self.client.post("/students/register_and_enroll", json=self.register_payload(72),
                                headers=hdr("tok-teacher1"))
        self.assertEqual(resp.status_code, 403, resp.text)
        self.assertEqual(self.db.query(models.Student).count(), 1, "فقط شاگردِ اولیه باید باشد")
        self.assertEqual(self.enrollments(), [])

    # ── ۶) نقش‌های دیگر دست‌نخورده ─────────────────────────────────────────
    def test_6_admin_and_secretary_and_student_roles_unchanged(self):
        admin = self.client.post("/enrollments/add", json=self.enroll_payload(72),
                                 headers=hdr("tok-admin"))
        self.assertEqual(admin.status_code, 200, admin.text)
        self.assertEqual(admin.json().get("enrollment_id") is not None, True)

        # ثبت‌نام دوبارهٔ همان شاگرد در همان کلاس ⇒ ۴۰۰ (بدون تغییر)
        dup = self.client.post("/enrollments/add", json=self.enroll_payload(72),
                               headers=hdr("tok-secretary"))
        self.assertEqual(dup.status_code, 400, dup.text)

        for tok in ("tok-student", "tok-parent"):
            denied = self.client.post("/enrollments/add", json=self.enroll_payload(71), headers=hdr(tok))
            self.assertEqual(denied.status_code, 403, f"{tok}: {denied.text}")
        self.assertEqual(self.client.post("/enrollments/add", json=self.enroll_payload(71)).status_code, 401)

    # ── ۷) بی‌اثری مالی: مسیر معلم و ادمین یک رفتار پولی دارند ─────────────
    def test_7_money_side_effects_are_identical_for_teacher_and_admin(self):
        """معلم با پرداخت اولیه: تراکنش/کیف‌ها باید **همان** قواعد مسیر ادمین را داشته باشند."""
        teacher_resp = self.client.post("/enrollments/add", json=self.enroll_payload(71, paid=400_000),
                                        headers=hdr("tok-teacher1"))
        self.assertEqual(teacher_resp.status_code, 200, teacher_resp.text)

        student = self.db.query(models.Student).filter(models.Student.id == 41).first()
        self.db.refresh(student)
        self.assertEqual(student.wallet_institute, 400_000, "پرداخت اولیه مثل قبل به کیف آموزشگاه می‌رود")
        self.assertEqual(student.wallet_balance, 400_000)

        txn = self.db.query(models.Transaction).all()
        self.assertEqual(len(txn), 1)
        self.assertEqual((txn[0].amount, txn[0].type, txn[0].target_wallet),
                         (400_000, "enrollment_payment", "institute"))
        self.assertEqual(txn[0].course_id, 71)

    # ── ۸) گیت تعلیق/غیرفعال‌بودن معلمان دست‌نخورده ────────────────────────
    def test_8_teacher_gate_still_applies_when_teachers_are_disabled(self):
        self.db.add(models.InstituteSettings(id=1, teachers_active=False))
        self.db.commit()
        resp = self.client.post("/enrollments/add", json=self.enroll_payload(71),
                                headers=hdr("tok-teacher1"))
        self.assertEqual(resp.status_code, 403, resp.text)
        self.assertIn("متوقف", resp.text)
        self.assertEqual(self.enrollments(), [])


if __name__ == "__main__":
    unittest.main()
