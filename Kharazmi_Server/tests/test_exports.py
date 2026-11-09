"""
Export to Excel/CSV — tests (isolated, sqlite in-memory)
پوشش: 401/403/200، BOM یونیکت، ساختار CSV، ستون‌ها، بدهی معلم/آموزشگاه، اقساط معوق
(جلالی/میلادی legacy/نامعتبر)، هشدارهای Audit، read-only بودن و مقاوم‌بودن به 10k ردیف.

اجرا (طبق قانون پروژه، همیشه روی کپی — نه DB واقعی):
    DATABASE_URL=sqlite:////tmp/exports_test.db python3 -m pytest test_exports.py -q
تست‌ها DB درون‌حافظه‌ای دارند و به DB واقعی دست نمی‌زنند.
"""
import csv
import datetime
import io
import os
import time
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models import (
    Base, User, UserSession, Student, Teacher, Course, Enrollment, Installment,
    Branch, SessionLog,
)
from main import app
from dependencies import get_db, hash_password
from today_summary import jalali_date_string


def _rows(csv_text):
    """CSV بدون BOM → لیست ردیف‌ها (csv.reader روی متن بدون BOM)."""
    reader = csv.reader(io.StringIO(csv_text.lstrip("\ufeff")))
    return list(reader)


class TestExportsCSV(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        # ⚠️ دقیقاً مثل get_db واقعی: سشن ته استریم بسته می‌شود (تست عمر سشن در StreamingResponse)
        def override_get_db():
            try:
                yield self.db
            finally:
                pass  # سشن مشترک تست را نمی‌بندیم؛ بستن واقعی در test_session_lifecycle_* شبیه‌سازی شده

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        self.db.add(Branch(id=1, name="مرکزی", active=True))
        self.db.commit()

        self.admin_user = User(id=1, username="09120000000", password=hash_password("123"), full_name="Admin", role="admin", sub_role="admin", branch_id=None)
        self.secretary_user = User(id=2, username="09121111111", password=hash_password("123"), full_name="Secretary", role="admin", sub_role="secretary", branch_id=None)
        self.teacher_user = User(id=3, username="09123333333", password=hash_password("101"), full_name="Teacher", role="teacher", sub_role="teacher", branch_id=None)
        self.db.add_all([self.admin_user, self.secretary_user, self.teacher_user])
        self.db.commit()

        self.db.add_all([
            UserSession(token="tok_admin", user_id=1, sub_role="admin", created_at=datetime.datetime.now()),
            UserSession(token="tok_secretary", user_id=2, sub_role="secretary", created_at=datetime.datetime.now()),
            UserSession(token="tok_teacher", user_id=3, sub_role="teacher", created_at=datetime.datetime.now()),
        ])
        self.db.commit()

        self.teacher = Teacher(id=1, first_name="امیر", last_name="احمدی", national_code="0001000128", mobile="09123333333", teacher_code=101, is_approved=True, password=hash_password("101"))
        self.db.add(self.teacher)
        self.db.commit()
        self.course = Course(id=1, title="ریاضی کنکور", code="MATH1", teacher_id=1, class_time="16:00", is_admin_approved=True)
        self.db.add(self.course)
        self.db.commit()

        # شاگرد بدهکار: شهریه ۱٬۰۰۰٬۰۰۰ پرداخت‌نشده + کیف معلم منفی ۵۰٬۰۰۰
        self.debtor = Student(id=1, first_name="سینا", last_name="مرادی", national_code="0000000001",
                              student_mobile="09120000001", parent_mobile="09120000001",
                              wallet_teacher=-50000, wallet_institute=0, is_deleted=False)
        # شاگرد بدون بدهی (باید از خروجی حذف شود)
        self.clear_student = Student(id=2, first_name="سارا", last_name="احمدی", national_code="0000000002",
                                     student_mobile="09120000002", parent_mobile="09120000002",
                                     wallet_teacher=10000, wallet_institute=0, is_deleted=False)
        self.db.add_all([self.debtor, self.clear_student])
        self.db.commit()

        self.enrollment = Enrollment(id=1, student_id=1, course_id=1,
                                     register_date=jalali_date_string(datetime.date.today()),
                                     total_tuition=1000000, total_paid=0, discount_type="none", discount_value=0)
        self.db.add(self.enrollment)
        self.db.commit()

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    # ---------- دسترسی‌ها ----------
    def test_401_no_token_all_endpoints(self):
        for path in ("/exports/debtors", "/exports/overdue_installments", "/exports/audit_alerts"):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 401, f"{path} باید 401 بدهد، داد {r.status_code}: {r.text}")

    def test_403_non_admin_all_endpoints(self):
        for path in ("/exports/debtors", "/exports/overdue_installments", "/exports/audit_alerts"):
            for role, token in (("secretary", "tok_secretary"), ("teacher", "tok_teacher")):
                r = self.client.get(path, headers={"Authorization": f"Bearer {token}"})
                self.assertEqual(r.status_code, 403, f"{path} برای {role} باید 403 بدهد، داد {r.status_code}: {r.text}")

    # ---------- بدهکاران ----------
    def test_debtors_csv_bom_headers_and_values(self):
        r = self.client.get("/exports/debtors", headers={"Authorization": "Bearer tok_admin"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("text/csv", r.headers["content-type"])
        self.assertIn('filename="debtors.csv"', r.headers["content-disposition"])
        self.assertTrue(r.content.decode("utf-8").startswith("\ufeff"), "CSV باید با BOM شروع شود")
        self.assertTrue(r.content.startswith(b"\xef\xbb\xbf"), "BOM باید بایت‌های EF BB BF باشد")

        rows = _rows(r.text)
        self.assertEqual(len(rows), 2, f"فقط یک بدهکار انتظار می‌رفت: {rows}")
        # FIX (گروه۲/آیتم۹): دو ستون پیگیری جدید («تاریخ آخرین پرداخت»، «قدمت بدهی (روز)»)
        # به انتهای هدر اضافه شده‌اند — ترتیب ستون‌های قبلی برای کلاینت منتشرشده دست‌نخورده است.
        self.assertEqual(rows[0], ["شناسه", "نام دانش‌آموز", "کد ملی", "موبایل ولی",
                                   "بدهی معلم", "بدهی آموزشگاه", "بدهی کل", "کلاس‌های فعال",
                                   "تاریخ آخرین پرداخت", "قدمت بدهی (روز)"])
        self.assertEqual(rows[1][0], "1")
        self.assertEqual(rows[1][1], "سینا مرادی")
        self.assertEqual(rows[1][2], "0000000001")
        self.assertEqual(rows[1][3], "09120000001")
        # CSV debt columns are enrollment-scoped; the negative legacy wallet is
        # not attributed to this class.
        self.assertEqual(rows[1][4], "0")
        self.assertEqual(rows[1][5], "1000000")
        self.assertEqual(rows[1][6], "1000000")    # بدهی شهریه
        self.assertEqual(rows[1][7], "ریاضی کنکور")
        # هیچ تراکنش پرداختی در فیکسچر نیست ⇒ ستون‌های جدید خالی/بی‌مقدار می‌آیند (نه crash)
        self.assertEqual(rows[1][8], "")
        self.assertEqual(rows[1][9], "")

    def test_debtors_excludes_zero_debt_student(self):
        r = self.client.get("/exports/debtors", headers={"Authorization": "Bearer tok_admin"})
        body = r.content.decode("utf-8")
        self.assertNotIn("سارا", body)

    def test_csv_formula_injection_hardened(self):
        self.debtor.first_name = "=SUM(A1:A2)"
        self.db.commit()
        r = self.client.get("/exports/debtors", headers={"Authorization": "Bearer tok_admin"})
        rows = _rows(r.text)
        self.assertTrue(rows[1][1].startswith("'=SUM"), f"سلول متنی خطرناک باید quote شود: {rows[1][1]}")

    # ---------- اقساط معوق ----------
    def _add_overdue_fixtures(self):
        today = datetime.date.today()
        rows = [
            Installment(id=1, enrollment_id=1, amount=100000, due_date=jalali_date_string(today - datetime.timedelta(days=5)), is_paid=False, is_deleted=False),
            Installment(id=2, enrollment_id=1, amount=200000, due_date=jalali_date_string(today - datetime.timedelta(days=10)), is_paid=False, is_deleted=False),
            Installment(id=3, enrollment_id=1, amount=300000, due_date=jalali_date_string(today - datetime.timedelta(days=3)), is_paid=True, is_deleted=False),   # پرداخت‌شده → خارج
            Installment(id=4, enrollment_id=1, amount=400000, due_date=jalali_date_string(today + datetime.timedelta(days=4)), is_paid=False, is_deleted=False),  # آینده → خارج
            Installment(id=5, enrollment_id=1, amount=500000, due_date=jalali_date_string(today - datetime.timedelta(days=2)), is_paid=False, is_deleted=True),   # حذف‌شده → خارج
            Installment(id=6, enrollment_id=1, amount=600000, due_date=jalali_date_string(today), is_paid=False, is_deleted=False),                                # سررسید امروز → خارج
            Installment(id=7, enrollment_id=1, amount=700000, due_date=(today - datetime.timedelta(days=4)).strftime("%Y/%m/%d"), is_paid=False, is_deleted=False),  # legacy میلادی → داخل
            Installment(id=8, enrollment_id=1, amount=800000, due_date="1405/13/45", is_paid=False, is_deleted=False),                                              # نامعتبر → خارج
        ]
        self.db.add_all(rows)
        self.db.commit()

    def test_overdue_installments_rows_and_status(self):
        self._add_overdue_fixtures()
        r = self.client.get("/exports/overdue_installments", headers={"Authorization": "Bearer tok_admin"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn('filename="overdue_installments.csv"', r.headers["content-disposition"])
        rows = _rows(r.text)
        self.assertEqual(rows[0], ["شناسه قسط", "نام دانش‌آموز", "موبایل ولی", "عنوان کلاس",
                                   "مبلغ", "سررسید", "روزهای تأخیر", "وضعیت"])
        ids = [row[0] for row in rows[1:]]
        self.assertEqual(sorted(ids), ["1", "2", "7"], f"فقط اقساط معوق معتبر باید باشند: {rows}")

        by_id = {row[0]: row for row in rows[1:]}
        self.assertEqual(by_id["1"][6], "5")
        self.assertEqual(by_id["1"][7], "معوق")
        self.assertEqual(by_id["2"][6], "10")
        self.assertEqual(by_id["2"][7], "بحرانی")
        self.assertEqual(by_id["1"][1], "سینا مرادی")
        self.assertEqual(by_id["1"][3], "ریاضی کنکور")
        self.assertEqual(by_id["7"][6], "4")  # تاریخ میلادی legacy درست پارس می‌شود

    def test_overdue_streams_and_handles_10k_rows(self):
        self._add_overdue_fixtures()
        today = datetime.date.today()
        payload = [
            Installment(enrollment_id=1, amount=1000 + i, due_date=jalali_date_string(today - datetime.timedelta(days=30)),
                        is_paid=False, is_deleted=False)
            for i in range(3000)
        ]
        self.db.add_all(payload)
        self.db.commit()

        started = time.time()
        r = self.client.get("/exports/overdue_installments", headers={"Authorization": "Bearer tok_admin"})
        elapsed = time.time() - started
        self.assertEqual(r.status_code, 200)
        rows = _rows(r.text)
        self.assertEqual(len(rows), 1 + 3003, f"سرستون + 3003 ردیف انتظار می‌رفت، شد {len(rows)}")
        self.assertLess(elapsed, 15.0, f"خروجی ۳هزار ردیفی نباید کند باشد: {elapsed:.2f}s")

    # ---------- هشدارهای Audit ----------
    def test_audit_alerts_csv(self):
        r = self.client.get("/exports/audit_alerts", headers={"Authorization": "Bearer tok_admin"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn('filename="audit_alerts.csv"', r.headers["content-disposition"])
        self.assertTrue(r.content.startswith(b"\xef\xbb\xbf"))
        rows = _rows(r.text)
        self.assertEqual(rows[0], ["نوع", "شدت", "عنوان", "توضیحات", "شناسه موجودیت", "نام موجودیت", "زمان تشخیص"])
        self.assertEqual(len(rows), 1, "بدون داده، فقط سرستون انتظار می‌رفت")

    def test_audit_alerts_detects_night_session(self):
        self.db.add(SessionLog(course_id=1, date=jalali_date_string(datetime.date.today()), time="02:30",
                               start_time="02:30", final_teacher_cost=0, final_institute_share=0,
                               cost_per_student=0, attendee_count=1, status="Finished"))
        self.db.commit()
        r = self.client.get("/exports/audit_alerts", headers={"Authorization": "Bearer tok_admin"})
        rows = _rows(r.text)
        self.assertGreaterEqual(len(rows), 2, f"جلسه‌ی ساعت ۲:۳۰ باید هشدار بدهد: {rows}")
        self.assertEqual(len(rows[1]), 7, "هر ردیف باید ۷ ستون داشته باشد")

    # ---------- Read-only & Isolation ----------
    def test_read_only_no_mutation(self):
        counts_before = (
            self.db.query(Student).count(),
            self.db.query(Installment).count(),
            self.db.query(Enrollment).count(),
        )
        wallets_before = (self.debtor.wallet_teacher, self.debtor.wallet_institute)

        for path in ("/exports/debtors", "/exports/overdue_installments", "/exports/audit_alerts"):
            self.assertEqual(self.client.get(path, headers={"Authorization": "Bearer tok_admin"}).status_code, 200)

        counts_after = (
            self.db.query(Student).count(),
            self.db.query(Installment).count(),
            self.db.query(Enrollment).count(),
        )
        self.db.refresh(self.debtor)
        self.assertEqual(counts_before, counts_after)
        self.assertEqual(wallets_before, (self.debtor.wallet_teacher, self.debtor.wallet_institute))

    def test_exports_module_has_no_write_calls(self):
        # مسیر مستقل از cwd — سوئیت از دو نقطه‌ی مختلف اجرا می‌شود (Kharazmi_Server/ و ریشه‌ی ریپو)
        # و بعضی تست‌های قدیمی (test_dashboard) عمداً از مسیر نسبی ریشه استفاده می‌کنند.
        # FIX(tests-dir): پوشهٔ سرور یک سطح بالاتر از پوشهٔ tests/ است.
        module_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                   "routers", "exports.py")
        with open(module_path, encoding="utf-8") as f:
            src = f.read()
        for forbidden in ("db.commit(", "db.add(", "db.add_all(", "db.delete(", "db.flush("):
            self.assertNotIn(forbidden, src, f"فایل exports نباید نوشتن داشته باشد: {forbidden}")
        self.assertIn("check_admin_access", src)
        self.assertNotIn("def submit", src)


class TestExportSessionLifecycle(unittest.TestCase):
    """اثبات اینکه استریم CSV با «سشن واقعیِ get_db» کار می‌کند:
    در پروداکشن، سشن در finally بسته می‌شود؛ اگر StreamingResponse بعد از teardown
    وابستگی اجرا شود، این تست با خطای session closed می‌افتد."""

    def setUp(self):
        import os
        import tempfile
        from models import Branch, User, UserSession, Student, Enrollment, Course, Teacher

        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.engine = create_engine(f"sqlite:///{self.db_path}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine)

        seed = Session()
        seed.add(Branch(id=1, name="مرکزی", active=True))
        seed.add(User(id=1, username="09120000000", password=hash_password("123"), full_name="Admin", role="admin", sub_role="admin"))
        seed.commit()
        seed.add(UserSession(token="tok_admin", user_id=1, sub_role="admin", created_at=datetime.datetime.now()))
        seed.add(Teacher(id=1, first_name="امیر", last_name="احمدی", national_code="0001000128", mobile="09123333333", teacher_code=101, is_approved=True, password=hash_password("101")))
        seed.add(Course(id=1, title="ریاضی کنکور", code="MATH1", teacher_id=1, is_admin_approved=True))
        seed.commit()
        seed.add(Student(id=1, first_name="سینا", last_name="مرادی", national_code="0000000001", student_mobile="09120000001", parent_mobile="09120000001", wallet_teacher=0, wallet_institute=0, is_deleted=False))
        seed.commit()
        seed.add(Enrollment(id=1, student_id=1, course_id=1, register_date=jalali_date_string(datetime.date.today()), total_tuition=500000, total_paid=0))
        seed.commit()
        seed.add(Installment(id=1, enrollment_id=1, amount=250000, due_date=jalali_date_string(datetime.date.today() - datetime.timedelta(days=9)), is_paid=False, is_deleted=False))
        seed.commit()
        seed.close()

        self._Session = Session

        def override_get_db():
            # عیناً مثل get_db واقعی: سشن پس از پاسخ بسته می‌شود
            db = self._Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        import os
        app.dependency_overrides.clear()
        self.engine.dispose()
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_streaming_works_with_closing_session(self):
        r = self.client.get("/exports/debtors", headers={"Authorization": "Bearer tok_admin"})
        self.assertEqual(r.status_code, 200, f"با سشن closing نباید خطا بدهد: {r.text[:400]}")
        rows = _rows(r.text)
        self.assertEqual(rows[1][6], "500000")

        r2 = self.client.get("/exports/overdue_installments", headers={"Authorization": "Bearer tok_admin"})
        self.assertEqual(r2.status_code, 200, f"overdue با سشن closing خطا داد: {r2.text[:400]}")
        rows2 = _rows(r2.text)
        self.assertEqual(len(rows2), 2)
        self.assertEqual(rows2[1][6], "9")
        self.assertEqual(rows2[1][7], "بحرانی")


if __name__ == "__main__":
    unittest.main()
