"""
FIX(invoice) — فیشِ دانش‌آموز چندکلاسه: enrollmentهای واقعی در پروفایل + رفتار کنترل‌شده /finance/pay

ریشه‌ی مشکل: صدور فیش از پروفایل فقط «نام نمایشی کلاس اول» را می‌فرستاد؛ InvoiceActivity هیچ
course_id/enrollment_id نداشت و برای شاگرد چندکلاسه `enrollment_id=null` به سرور می‌رسید و
/finance/pay با 400 «چند ثبت‌نام فعال» می‌پرد.

فیکس (این تست regression آن را نگه می‌دارد):
  1) GET /admin/students/{id}/full_profile فهرست `enrollments` با شناسه‌های واقعی
     (enrollment_id, course_id, title, code, branch_id) برمی‌گرداند — کلاینت با آن‌ها
     enrollment درست را انتخاب/می‌فرستد (سازگاری با عقب: `classes` نمایشی هم می‌ماند).
  2) /finance/pay: guard چندثبت‌نامی دست‌نخورده می‌ماند (حدس‌زدن ممنوع)؛ enrollment ارسال‌شده
     باید متعلق به همان شاگرد باشد و حذف‌شده نباشد؛ تک‌ثبت‌نامی خودکار وصل می‌شود؛ تراکنش
     در DB به همان enrollment (و course) لینک می‌شود؛ idempotency/retry و تفکیک شعبه حفظ است.

اجرا:
    cd /home/user/KharazmiApp && export JWT_SECRET_KEY=test \
        && python3 -m pytest Kharazmi_Server/test_invoice_enrollment.py -q
"""
import datetime
import os
import shutil
import tempfile
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dependencies import get_db, hash_password
from main import app
from models import Base, Branch, Course, Enrollment, Student, Transaction, User, UserSession


class InvoiceEnrollmentBase(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="invoice_enroll_test_")
        self.engine = create_engine(f"sqlite:///{os.path.join(self.tmpdir, 'test.db')}")
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        # دو شعبه فعال + کاربران: ادمین بدون شعبه، منشی شعبه ۱ و ۲ (برای تفکیک شعبه)
        self.db.add_all([Branch(id=1, name="شعبه یک", active=True), Branch(id=2, name="شعبه دو", active=True)])
        self.db.add_all([
            User(id=1, username="09120000000", password=hash_password("123"), full_name="Admin",
                 role="admin", sub_role="admin", branch_id=None),
            User(id=2, username="09121111111", password=hash_password("123"), full_name="Secretary1",
                 role="admin", sub_role="secretary", branch_id=1),
            User(id=3, username="09122222222", password=hash_password("123"), full_name="Secretary2",
                 role="admin", sub_role="secretary", branch_id=2),
        ])
        self.db.commit()
        self.db.add_all([
            UserSession(token="tok_admin", user_id=1, sub_role="admin", created_at=datetime.datetime.now()),
            UserSession(token="tok_sec1", user_id=2, sub_role="secretary", created_at=datetime.datetime.now()),
            UserSession(token="tok_sec2", user_id=3, sub_role="secretary", created_at=datetime.datetime.now()),
        ])
        self.db.commit()

        # کلاس‌ها: دو کلاس شعبه ۱ (برای شاگرد چندکلاسه) + یک کلاس شعبه ۲
        self.course_a = Course(id=1, title="ریاضی پایه", code="MA", class_time="16:00",
                               branch_id=1, is_admin_approved=True)
        self.course_b = Course(id=2, title="ریاضی پیشرفته", code="MB", class_time="18:00",
                               branch_id=1, is_admin_approved=True)
        self.course_c = Course(id=3, title="فیزیک شعبه دو", code="PC", class_time="19:00",
                               branch_id=2, is_admin_approved=True)
        self.db.add_all([self.course_a, self.course_b, self.course_c])
        self.db.commit()

    def tearDown(self):
        app.dependency_overrides.clear()
        try:
            self.db.close()
        finally:
            self.engine.dispose()
            shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ---------- helpers ----------

    def _headers(self, token="tok_admin"):
        return {"Authorization": f"Bearer {token}"}

    def _register_student(self, national_code, mobile="09120000001", branch_id=1):
        # مستقیم در DB — مسیر public /students/register محدودیت 5/hour دارد (تست‌ها هم‌سطل
        # 127.0.0.1 می‌شوند) و این تست به shadow-user آن وابسته نیست.
        st = Student(
            first_name="سینا", last_name="مرادی", father_name="علی",
            national_code=national_code, birth_date="1390/01/01",
            student_mobile=mobile, parent_mobile="09120000002",
            home_phone="02100000000", address="تهران", study_status="فعال",
            gender="male", branch_id=branch_id,
        )
        self.db.add(st)
        self.db.commit()
        self.db.expire_all()
        student = self.db.query(Student).filter(Student.national_code == national_code).first()
        self.assertIsNotNone(student, "شاگرد ثبت‌شده باید در DB باشد")
        return student

    def _enroll(self, student_id, course_id):
        payload = {
            "student_id": student_id, "course_id": course_id,
            "register_date": "1405/06/01", "shift": "عصر",
            "total_tuition": 1000000, "paid_amount": 0,
            "payment_method": "نقدی", "receiver": "آموزشگاه",
        }
        res = self.client.post("/enrollments/add", json=payload, headers=self._headers("tok_sec1"))
        self.assertEqual(res.status_code, 200, res.text)
        self.db.expire_all()
        return self.db.query(Enrollment).filter(
            Enrollment.student_id == student_id, Enrollment.course_id == course_id,
            Enrollment.is_deleted == False,
        ).first()

    def _pay(self, student_id, amount=500000, enrollment_id=None, idempotency_key=None, token="tok_sec1"):
        payload = {
            "student_id": student_id, "amount": amount, "target_wallet": "institute",
            "description": "آزمون فیش", "payment_method": "نقدی", "date": "1405/06/25",
            "enrollment_id": enrollment_id, "idempotency_key": idempotency_key,
        }
        return self.client.post("/finance/pay", json=payload, headers=self._headers(token))

    def _profile(self, student_id, token="tok_admin"):
        return self.client.get(f"/admin/students/{student_id}/full_profile", headers=self._headers(token))

    def _transactions_of(self, student_id, enrollment_id=None):
        q = self.db.query(Transaction).filter(Transaction.student_id == student_id)
        if enrollment_id is not None:
            q = q.filter(Transaction.enrollment_id == enrollment_id)
        return q.all()


class TestProfileEnrollments(InvoiceEnrollmentBase):

    def test_profile_lists_active_enrollments_with_real_ids(self):
        """۱: پروفایل، enrollmentهای فعال را با شناسه‌های واقعی می‌دهد (classes نمایشی هم می‌ماند)."""
        st = self._register_student("1000000011")
        en_a = self._enroll(st.id, self.course_a.id)
        en_b = self._enroll(st.id, self.course_b.id)

        res = self._profile(st.id)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertIn("enrollments", body, "کلید جدید enrollments باید در پروفایل باشد")
        got = {e["enrollment_id"]: e for e in body["enrollments"]}
        self.assertEqual(set(got), {en_a.id, en_b.id}, "دو enrollment فعال با شناسه واقعی")
        self.assertEqual(got[en_a.id]["course_id"], self.course_a.id)
        self.assertEqual(got[en_b.id]["course_id"], self.course_b.id)
        self.assertEqual(got[en_a.id]["title"], "ریاضی پایه")
        self.assertEqual(got[en_a.id]["code"], "MA")
        # سازگاری با عقب: classes نمایشی دست‌نخورده
        self.assertEqual(len(body["classes"]), 2)

    def test_profile_excludes_deleted_enrollments(self):
        """۲: enrollment حذف‌شده (آرشیو) در فهرست enrollments نمی‌آید."""
        st = self._register_student("1000000028")
        en_a = self._enroll(st.id, self.course_a.id)
        en_b = self._enroll(st.id, self.course_b.id)
        en_b.is_deleted = True
        self.db.commit()
        self.db.expire_all()

        res = self._profile(st.id)
        self.assertEqual(res.status_code, 200, res.text)
        ids = [e["enrollment_id"] for e in res.json()["enrollments"]]
        self.assertEqual(ids, [en_a.id], "فقط enrollment فعال می‌ماند")

    def test_profile_no_active_enrollment(self):
        """۳: شاگرد بدون enrollment فعال → فهرست خالی (فیش عمومی، مثل رفتار قبلی)."""
        st = self._register_student("1000000036")
        res = self._profile(st.id)
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["enrollments"], [])
        self.assertEqual(res.json()["classes"], [])


class TestFinancePayEnrollmentLinking(InvoiceEnrollmentBase):

    def test_pay_multi_with_valid_id_links_each_class(self):
        """۴: چندکلاسه + enrollment معتبر → تراکنش دقیقاً به همان enrollment و course لینک می‌شود (هر کلاس)."""
        st = self._register_student("1000000044")
        en_a = self._enroll(st.id, self.course_a.id)
        en_b = self._enroll(st.id, self.course_b.id)

        res1 = self._pay(st.id, amount=100000, enrollment_id=en_a.id)
        self.assertEqual(res1.status_code, 200, res1.text)
        res2 = self._pay(st.id, amount=200000, enrollment_id=en_b.id)
        self.assertEqual(res2.status_code, 200, res2.text)

        self.db.expire_all()
        t1 = self.db.query(Transaction).filter(Transaction.id == res1.json()["receipt_id"]).first()
        t2 = self.db.query(Transaction).filter(Transaction.id == res2.json()["receipt_id"]).first()
        self.assertEqual(t1.enrollment_id, en_a.id, "رسید اول باید به کلاس A وصل باشد")
        self.assertEqual(t1.course_id, self.course_a.id)
        self.assertEqual(t2.enrollment_id, en_b.id, "رسید دوم باید به کلاس B وصل باشد")
        self.assertEqual(t2.course_id, self.course_b.id)

    def test_pay_multi_empty_id_controlled_400(self):
        """۵: چندکلاسه + enrollment خالی → 400 کنترل‌شده (guard دست‌نخورده؛ سرور حدس نمی‌زند)."""
        st = self._register_student("1000000052")
        self._enroll(st.id, self.course_a.id)
        self._enroll(st.id, self.course_b.id)

        res = self._pay(st.id)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["detail"], "این دانش‌آموز چند ثبت‌نام فعال دارد، enrollment_id مشخص کنید")
        self.db.expire_all()
        self.assertEqual(self.db.query(Transaction).filter(Transaction.student_id == st.id).count(), 0)

    def test_pay_single_active_auto_links(self):
        """۶: تک‌کلاسه + enrollment خالی → خودکار به همان enrollment وصل می‌شود (قانون قدیمی)."""
        st = self._register_student("1000000060")
        en_a = self._enroll(st.id, self.course_a.id)

        res = self._pay(st.id)
        self.assertEqual(res.status_code, 200, res.text)
        self.db.expire_all()
        t = self.db.query(Transaction).filter(Transaction.id == res.json()["receipt_id"]).first()
        self.assertEqual(t.enrollment_id, en_a.id)
        self.assertEqual(t.course_id, self.course_a.id)

    def test_pay_no_active_enrollment_generic(self):
        """۷: بدون هیچ enrollment فعال → پرداخت عمومی (کیف پول شاگرد) بدون enrollment."""
        st = self._register_student("1000000079")
        res = self._pay(st.id)
        self.assertEqual(res.status_code, 200, res.text)
        self.db.expire_all()
        t = self.db.query(Transaction).filter(Transaction.id == res.json()["receipt_id"]).first()
        self.assertIsNone(t.enrollment_id, "پرداخت عمومی نباید enrollment داشته باشد")

    def test_pay_other_student_enrollment_rejected(self):
        """۸: enrollment متعلق به شاگرد دیگر → 400 (بدون نوشتن هیچ تراکنشی)."""
        st1 = self._register_student("1000000087", mobile="09120000005")
        st2 = self._register_student("1000000095", mobile="09120000006")
        en2 = self._enroll(st2.id, self.course_a.id)
        self._enroll(st1.id, self.course_a.id)
        self._enroll(st1.id, self.course_b.id)

        res = self._pay(st1.id, enrollment_id=en2.id)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["detail"], "این ثبت‌نام متعلق به این دانش‌آموز نیست")
        self.db.expire_all()
        self.assertEqual(self.db.query(Transaction).filter(Transaction.student_id == st1.id).count(), 0)

    def test_pay_deleted_enrollment_rejected(self):
        """۹: enrollment حذف‌شده (آرشیو) → 404، مثل ناموجود."""
        st = self._register_student("1000000109")
        en_a = self._enroll(st.id, self.course_a.id)
        self._enroll(st.id, self.course_b.id)
        en_a.is_deleted = True
        self.db.commit()
        self.db.expire_all()

        res = self._pay(st.id, enrollment_id=en_a.id)
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["detail"], "ثبت‌نام مورد نظر یافت نشد")
        self.db.expire_all()
        self.assertEqual(self.db.query(Transaction).filter(Transaction.student_id == st.id).count(), 0)

    def test_pay_branch_policy_preserved(self):
        """۱۰: تفکیک شعبه دست‌نخورده — رسید شعبه‌دار همیشه شعبه‌ی شاگرد را می‌گیرد (حتی با پرداخت منشی شعبه دیگر)؛
        شاگرد/کاربر بی‌شعبه → 400 «شعبه پرداخت مشخص نیست»."""
        st_b1 = self._register_student("1000000117", mobile="09120000008", branch_id=1)
        self._enroll(st_b1.id, self.course_a.id)
        res = self._pay(st_b1.id, token="tok_sec2")  # منشی شعبه ۲ پرداخت می‌کند
        self.assertEqual(res.status_code, 200, res.text)
        self.db.expire_all()
        t = self.db.query(Transaction).filter(Transaction.id == res.json()["receipt_id"]).first()
        self.assertEqual(t.branch_id, 1, "رسید شعبه‌دار به شعبه‌ی شاگرد می‌رسد، نه پرداخت‌کننده")

        # شاگرد بی‌شعبه مستقیم در DB (سیاست register هرگز بی‌شعبه نمی‌سازد؛ این رکورد legacy است)
        st_nb = Student(
            first_name="بی‌شعبه", last_name="تست", father_name="تست",
            national_code="1000000125", birth_date="1390/01/01",
            student_mobile="09120000099", parent_mobile="09120000098",
            home_phone="02100000001", address="تهران", study_status="فعال",
            gender="male", branch_id=None,
        )
        self.db.add(st_nb)
        self.db.commit()
        self.db.expire_all()
        # شاگرد بی‌شعبه + ادمین بی‌شعبه → شعبه پرداخت نامشخص → 400 کنترل‌شده (رفتار Bug-9، بدون تغییر)
        res2 = self._pay(st_nb.id, token="tok_admin")
        self.assertEqual(res2.status_code, 400)
        self.assertIn("شعبه", res2.json()["detail"])

    def test_retry_same_idempotency_key_replays(self):
        """۱۱: retry با همان idempotency_key → replay؛ تراکنش/کیف‌پول دوباره نوشته نمی‌شود."""
        st = self._register_student("1000000214")
        en_a = self._enroll(st.id, self.course_a.id)
        en_b = self._enroll(st.id, self.course_b.id)
        key = "invoice-test-key-0001"

        res1 = self._pay(st.id, amount=300000, enrollment_id=en_a.id, idempotency_key=key)
        self.assertEqual(res1.status_code, 200, res1.text)
        wallet_before = None
        self.db.expire_all()
        st_row = self.db.query(Student).filter(Student.id == st.id).first()
        wallet_before = (st_row.wallet_institute or 0)

        res2 = self._pay(st.id, amount=300000, enrollment_id=en_a.id, idempotency_key=key)
        self.assertEqual(res2.status_code, 200, res2.text)
        self.assertTrue(res2.json().get("duplicate"), "دومین فراخوان باید replay باشد")
        self.db.expire_all()
        st_row = self.db.query(Student).filter(Student.id == st.id).first()
        self.assertEqual(st_row.wallet_institute or 0, wallet_before, "کیف‌پول در replay دوباره شارژ نمی‌شود")
        ts = self._transactions_of(st.id, enrollment_id=en_a.id)
        self.assertEqual(len(ts), 1, "فقط یک تراکنش برای کلید تکراری")


if __name__ == "__main__":
    unittest.main(verbosity=2)
