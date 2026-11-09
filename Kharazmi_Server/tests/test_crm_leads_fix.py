"""
FIX(crm) — لیست/ایجاد/تبدیل سرنخ‌ها: null-safety، اعتبارسنجی branch، کد ملی یکتا و atomic convert

مشکلات اثبات‌شده (regression test این فیکس):
  1) created_at=NULL (legacy) ⇒ AttributeError ⇒ 500 روی کل لیست
  2) name/mobile/interested_course/source/status NULL ⇒ response model 500 می‌شد
  3) branch_id نامعتبر در create ⇒ IntegrityError خام 500 (و `or 1` حدسی)
  4) national_code تصادفی در convert ⇒ collision با unique ⇒ 500 خام
  5) convert بدون mobile ⇒ Student ناقص با موبایل خالی
  6) خطای وسط convert باید atomic باشد (rollback کامل؛ Lead نیمه‌تبدیل نماند)

اجرا:
    cd /home/user/KharazmiApp && export JWT_SECRET_KEY=test \
        && python3 -m pytest Kharazmi_Server/test_crm_leads_fix.py -q
"""
import datetime
import re
import unittest
from unittest import mock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from dependencies import get_db, hash_password
from main import app
from models import Base, Branch, Course, Enrollment, Lead, Student, User, UserSession


class CrmLeadsFixBase(unittest.TestCase):

    def setUp(self):
        # دیتابیس موقت ایزوله (in-memory) — الگوی تست‌های موجود پروژه
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

        # شعبه‌ها: ۱ و  فعال، ۳ غیرفعال (999 اصلاً وجود ندارد)
        self.db.add_all([
            Branch(id=1, name="شعبه یک", active=True),
            Branch(id=2, name="شعبه دو", active=True),
            Branch(id=3, name="شعبه تعطیل", active=False),
        ])
        self.db.commit()

        # کاربران: منشی شعبه ۱ (isolation) + ادمین مرکزی بدون شعبه (branch ارسالی)
        self.db.add_all([
            User(id=1, username="09120000000", password=hash_password("123"), full_name="GlobalAdmin",
                 role="admin", sub_role="admin", branch_id=None),
            User(id=2, username="09121111111", password=hash_password("123"), full_name="Secretary1",
                 role="admin", sub_role="secretary", branch_id=1),
        ])
        self.db.commit()
        self.db.add_all([
            UserSession(token="tok_admin_global", user_id=1, sub_role="admin", created_at=datetime.datetime.now()),
            UserSession(token="tok_sec1", user_id=2, sub_role="secretary", created_at=datetime.datetime.now()),
        ])
        self.db.commit()

        # یک کلاس فعال (برای convert با course_id)
        self.course = Course(id=1, title="ریاضی کنکور", code="M1", class_time="16:00",
                             branch_id=1, is_admin_approved=True)
        self.db.add(self.course)
        self.db.commit()

    def tearDown(self):
        app.dependency_overrides.clear()
        try:
            self.db.close()
        finally:
            Base.metadata.drop_all(bind=self.engine)
            self.engine.dispose()

    # ---------- helpers ----------

    def _h(self, token="tok_sec1"):
        return {"Authorization": f"Bearer {token}"}

    def _add_lead(self, mobile="09123456789", created_at="SET", **kw):
        """created_at='SET' (default) یک datetime می‌گیرد؛ created_at=None → INSERT خام با NULL
        واقعی (default ORMِ created_at روی مقدار None هم اجرا می‌شود و NULL legacy را نمی‌سازد)."""
        if created_at is None:
            from sqlalchemy import text
            self.db.execute(text(
                "INSERT INTO crm_leads (name, mobile, interested_course, source, status, created_at, branch_id) "
                "VALUES (:name, :mobile, :ic, :src, :st, NULL, :br)"
            ), {
                "name": kw.get("name", "آرش توست"), "mobile": mobile,
                "ic": kw.get("interested_course", "ریاضی"), "src": kw.get("source", "Web"),
                "st": kw.get("status", "NEW"), "br": kw.get("branch_id", 1),
            })
            self.db.commit()
            self.db.expire_all()
            return self.db.query(Lead).filter(Lead.mobile == mobile).order_by(Lead.id.desc()).first()
        lead = Lead(
            name=kw.get("name", "آرش توست"),
            mobile=mobile,
            interested_course=kw.get("interested_course", "ریاضی"),
            source=kw.get("source", "Web"),
            status=kw.get("status", "NEW"),
            created_at=datetime.datetime(2026, 9, 1) if created_at == "SET" else created_at,
            branch_id=kw.get("branch_id", 1),
        )
        self.db.add(lead)
        self.db.commit()
        self.db.expire_all()
        return self.db.query(Lead).filter(Lead.id == lead.id).first()

    def _add_student(self, national_code, mobile):
        st = Student(
            first_name="قدیمی", last_name="تست", father_name="تست",
            national_code=national_code, birth_date="1390/01/01",
            student_mobile=mobile, parent_mobile="09120000000",
            home_phone="0211", address="تهران", study_status="فعال",
            gender="male", branch_id=1,
        )
        self.db.add(st)
        self.db.commit()
        self.db.expire_all()
        return self.db.query(Student).filter(Student.national_code == national_code).first()

    def _create_lead(self, token="tok_sec1", branch_id=None, mobile="09121110000", name="نرگس فرهادی"):
        payload = {"name": name, "mobile": mobile, "interested_course": "شیمی"}
        if branch_id is not None:
            payload["branch_id"] = branch_id
        return self.client.post("/crm/leads/create", json=payload, headers=self._h(token))

    def _convert(self, lead_id, token="tok_sec1", course_id=None):
        url = f"/crm/leads/{lead_id}/convert"
        if course_id is not None:
            url += f"?course_id={course_id}"
        return self.client.post(url, headers=self._h(token))

    def _leads_in_db(self):
        self.db.expire_all()
        return self.db.query(Lead).all()

    def _students_in_db(self):
        self.db.expire_all()
        return self.db.query(Student).all()


class TestLeadsListNullSafety(CrmLeadsFixBase):

    def test_list_created_at_null_no_500(self):
        """created_at=NULL (legacy) → 200 و مقدار خالی کنترل‌شده (مقدار جعلی تولید نمی‌شود)."""
        self._add_lead(created_at=None)
        res = self.client.get("/crm/leads/list", headers=self._h())
        self.assertEqual(res.status_code, 200, res.text)
        rows = res.json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["created_at"], "", "created_at خالی باید '' کنترل‌شده برگردد، نه تاریخ جعلی")

    def test_list_nullable_fields_safe(self):
        """name/mobile/interested_course/source/status = NULL → fallback امن، بدون 500."""
        self._add_lead(name=None, mobile=None, interested_course=None, source=None, status=None)
        res = self.client.get("/crm/leads/list", headers=self._h())
        self.assertEqual(res.status_code, 200, res.text)
        row = res.json()[0]
        self.assertEqual(row["name"], "")
        self.assertEqual(row["mobile"], "")
        self.assertEqual(row["interested_course"], "")
        self.assertEqual(row["source"], "Web")
        self.assertEqual(row["status"], "NEW")

    def test_list_mixed_healthy_and_incomplete(self):
        """ترکیب رکورد سالم + ناقص → هر دو ردیف برگردانده می‌شوند (کل لیست نمی‌افتد)."""
        good = self._add_lead(mobile="09121111111", name="سالم‌پرو")
        self._add_lead(mobile=None, name=None, created_at=None, status=None, branch_id=2)
        res = self.client.get("/crm/leads/list", headers=self._h())
        self.assertEqual(res.status_code, 200, res.text)
        rows = res.json()
        self.assertEqual(len(rows), 2)
        by_id = {r["id"]: r for r in rows}
        self.assertEqual(by_id[good.id]["name"], "سالم‌پرو")
        self.assertEqual(by_id[good.id]["created_at"], "2026/09/01")
        bad = [r for r in rows if r["id"] != good.id][0]
        self.assertEqual(bad["created_at"], "")
        self.assertEqual(bad["status"], "NEW")


class TestCreateLeadBranchValidation(CrmLeadsFixBase):

    def test_create_valid_branch(self):
        """branch معتبر (خودِ کاربر) → 200 و Lead به همان شعبه تعلق می‌گیرد."""
        res = self._create_lead()
        self.assertEqual(res.status_code, 200, res.text)
        lead = self.db.query(Lead).filter(Lead.id == res.json()["id"]).first()
        self.assertEqual(lead.branch_id, 1)
        # ادمین مرکزی هم با branch_id ارسالیِ معتبر
        res2 = self._create_lead(token="tok_admin_global", branch_id=2, mobile="09121112222")
        self.assertEqual(res2.status_code, 200, res2.text)
        self.db.expire_all()
        lead2 = self.db.query(Lead).filter(Lead.id == res2.json()["id"]).first()
        self.assertEqual(lead2.branch_id, 2)

    def test_create_nonexistent_branch_controlled_400(self):
        """branch ناموجود → 400 کنترل‌شده (نه 500 خام IntegrityError) و ردیفی ساخته نمی‌شود."""
        before = len(self._leads_in_db())
        res = self._create_lead(token="tok_admin_global", branch_id=999)
        self.assertEqual(res.status_code, 400, res.text)
        self.assertIn("شعبه", res.json()["detail"])
        self.assertEqual(len(self._leads_in_db()), before, "هیچ Lead نیمه‌کاره نباید بماند")

    def test_create_inactive_branch_controlled_400(self):
        """branch غیرفعال → 400 کنترل‌شده و ردیف ساخته نمی‌شود."""
        before = len(self._leads_in_db())
        res = self._create_lead(token="tok_admin_global", branch_id=3)
        self.assertEqual(res.status_code, 400, res.text)
        self.assertIn("شعبه", res.json()["detail"])
        self.assertEqual(len(self._leads_in_db()), before)

    def test_create_no_branch_global_admin_controlled_400(self):
        """ادمین بدون شعبه بدون branch_id → حدس‌زنیِ قبلی (`or 1`) دیگر نیست؛ 400 واضح."""
        res = self._create_lead(token="tok_admin_global")
        self.assertEqual(res.status_code, 400, res.text)
        self.assertEqual(len(self._leads_in_db()), 0)


class TestConvertLead(CrmLeadsFixBase):

    def test_convert_valid_mobile(self):
        """mobile معتبر → Student معتبر + Lead دقیقاً REGISTERED + enrollment در همان کامیت."""
        lead = self._add_lead(mobile="09125556677")
        res = self._convert(lead.id, course_id=self.course.id)
        self.assertEqual(res.status_code, 200, res.text)
        student_id = res.json()["student_id"]

        self.db.expire_all()
        st = self.db.query(Student).filter(Student.id == student_id).first()
        self.assertIsNotNone(st, "Student باید ساخته شود")
        self.assertEqual(st.student_mobile, "09125556677")
        self.assertTrue(st.national_code.startswith("0000"), "کد ملی موقت همان فضای legacy 0000")
        self.assertRegex(st.national_code, r"^0000\d{6}$")

        lead = self.db.query(Lead).filter(Lead.id == lead.id).first()
        self.assertEqual(lead.status, "REGISTERED")
        self.assertEqual(lead.converted_student_id, student_id)
        self.assertIsNotNone(lead.converted_at)

        enroll = self.db.query(Enrollment).filter(Enrollment.student_id == student_id).first()
        self.assertIsNotNone(enroll, "ثبت‌نام باید در همان کامیت موفق ساخته شده باشد")

    def test_convert_empty_mobile_controlled_400(self):
        """mobile خالی/NULL → 400 واضح؛ Student ناقص ساخته نمی‌شود و Lead دست‌نخورده می‌ماند."""
        lead = self._add_lead(mobile=None)
        res = self._convert(lead.id)
        self.assertEqual(res.status_code, 400, res.text)
        self.assertIn("موبایل", res.json()["detail"])
        self.assertEqual(len(self._students_in_db()), 0, "بدون موبایل معتبر Student ساخته نمی‌شود")
        lead = self.db.query(Lead).filter(Lead.id == lead.id).first()
        self.assertEqual(lead.status, "NEW")
        self.assertIsNone(lead.converted_student_id)

    def test_convert_invalid_mobile_controlled_400(self):
        """mobile نامعتبر (فرمت غلط) → 400؛ Student ساخته نمی‌شود."""
        lead = self._add_lead(mobile="12345")
        res = self._convert(lead.id)
        self.assertEqual(res.status_code, 400, res.text)
        self.assertIn("موبایل", res.json()["detail"])
        self.assertEqual(len(self._students_in_db()), 0)

    def test_convert_duplicate_student_mobile_rejected(self):
        """رفتار قبلی حفظ: تکراری بودن موبایل با Student موجود → 400 و Lead دست‌نخورده."""
        self._add_student("1000000011", "09127778899")
        lead = self._add_lead(mobile="09127778899")
        res = self._convert(lead.id)
        self.assertEqual(res.status_code, 400, res.text)
        lead = self.db.query(Lead).filter(Lead.id == lead.id).first()
        self.assertEqual(lead.status, "NEW")

    def test_convert_double_convert_rejected(self):
        """idempotency: convert دومِ سرنخ تبدیل‌شده → 400 و Student تکراری ساخته نمی‌شود."""
        lead = self._add_lead(mobile="09123334455")
        res1 = self._convert(lead.id)
        self.assertEqual(res1.status_code, 200, res1.text)
        res2 = self._convert(lead.id)
        self.assertEqual(res2.status_code, 400, res2.text)
        self.assertIn("قبلاً", res2.json()["detail"])
        students = self.db.query(Student).filter(Student.student_mobile == "09123334455").all()
        self.assertEqual(len(students), 1, "تبدیل دوباره Student تکراری نمی‌سازد")

    def test_convert_mid_failure_full_rollback(self):
        """خطا در میانه convert (کرش موقع commit) → rollback کامل: Student/Lead هیچ تغییری نمی‌بیند."""
        lead = self._add_lead(mobile="09124445566")
        with mock.patch.object(type(self.db), "commit", side_effect=RuntimeError("simulated crash on commit")):
            res = self._convert(lead.id, course_id=self.course.id)
        self.assertEqual(res.status_code, 500, res.text)
        self.assertIn("هیچ داده‌ای ذخیره نشد", res.json()["detail"], "خطای کنترل‌شده، نه traceback خام")
        self.assertEqual(len(self._students_in_db()), 0, "Student نیمه‌کاره باقی نمی‌ماند")
        self.assertEqual(self.db.query(Enrollment).count(), 0, "Enrollment نیمه‌کاره باقی نمی‌ماند")
        lead = self.db.query(Lead).filter(Lead.id == lead.id).first()
        self.assertEqual(lead.status, "NEW", "Lead نباید REGISTEREDِ بدون Student بماند")
        self.assertIsNone(lead.converted_student_id)

    def test_nc_collision_retry_and_uniqueness(self):
        """collision قطعی: اولین کاندید (0000100000) توسط Student قدیمی گرفته است →
        convert باید کاندید بعدی را بگیرد؛ چند convert هم‌زمان کد یکتا می‌سازند."""
        blocked = self._add_student("0000100000", "09129990000")
        lead1 = self._add_lead(mobile="09126667788")
        res1 = self._convert(lead1.id)
        self.assertEqual(res1.status_code, 200, res1.text)
        st1 = self.db.query(Student).filter(Student.id == res1.json()["student_id"]).first()
        self.assertNotEqual(st1.national_code, "0000100000", "collision باید retry شود")
        self.assertEqual(st1.national_code, "0000100001", "اولین کاندید آزاد گرفته می‌شود")

        # یکتایی چندگانه: دو سرنخ دیگر → سه کد متمایز
        lead2 = self._add_lead(mobile="09126667799")
        lead3 = self._add_lead(mobile="09126668800")
        self.assertEqual(self._convert(lead2.id).status_code, 200)
        self.assertEqual(self._convert(lead3.id).status_code, 200)
        codes = [s.national_code for s in self._students_in_db() if s.id != blocked.id]
        self.assertEqual(len(codes), 3)
        self.assertEqual(len(set(codes)), 3, "کد ملی موقت هر Student باید یکتا باشد")

    def test_branch_isolation_preserved(self):
        """منشی شعبه ۱ حتی با branch_id=2، سرنخ را در شعبه‌ی خودش می‌سازد (isolation دست‌نخورده)."""
        res = self._create_lead(token="tok_sec1", branch_id=2, mobile="09129876543")
        self.assertEqual(res.status_code, 200, res.text)
        lead = self.db.query(Lead).filter(Lead.id == res.json()["id"]).first()
        self.assertEqual(lead.branch_id, 1, "isolation: شعبهٔ کاربر، نه branch_id ارسالی")


if __name__ == "__main__":
    unittest.main(verbosity=2)
