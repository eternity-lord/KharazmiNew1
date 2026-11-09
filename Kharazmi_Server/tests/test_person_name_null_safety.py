# test_person_name_null_safety.py
# تست‌های A4 — ساخت نام کامل با تحمل NULL (پایان «None None» در برنامه)
#
# باگی که این تست‌ها قفل می‌کنند:
#   در ۵ فایل `attendance.py`، `finance.py`، `classes.py`، `reports.py` و `auth.py` نام کامل
#   با الگوی `f"{x.first_name} {x.last_name}"` ساخته می‌شد. `first_name`/`last_name` در مدل‌های
#   Student/Teacher/User ستون nullable هستند (رکوردهای legacy و نیمه‌ثبت‌شده)، پس خروجی می‌توانست
#   «None None»، «None رضایی» یا «معلم None» باشد و این رشته در پاسخ API، فاکتور/رسید چاپی، HTML
#   گزارش، فایل اکسل، پیامک و حتی در `User.full_name` سایه‌ی معلم (auth) ذخیره می‌شد.
#
# دو نکته‌ی حساس که این تست‌ها قفل می‌کنند:
#   1) مالی: اصلاح نام نباید هیچ عددی (طلب معلم، مبلغ رسید، جمع درآمد) را تغییر دهد.
#   2) auth: مقایسه/همگام‌سازی `u.full_name` در :159-160/:167-168 دو طرفش باید دقیقاً یک مقدار
#      مشترک باشد؛ وگرنه هر لاگین یک‌بار writer می‌شود (لاگ بی‌پایان UPDATE).
#
# قرارداد: اگر هیچ بخشی از نام موجود نباشد، جایگزین‌های موجودِ همان نقطه («نامشخص»، «حذف شده»،
# «بدون معلم»، «دانش‌آموز/گرامی/معلم» در متن پیام‌ها) و رفتار permission دست‌نخورده می‌ماند.
#
# اجرا (از ریشهٔ ریپو — روش مستند پروژه):
#   DATABASE_URL=sqlite:////tmp/a4_names.db JWT_SECRET_KEY=<hex> \
#     python3 -m pytest Kharazmi_Server/test_person_name_null_safety.py -q
import datetime
import json
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from dependencies import display_name, get_db, hash_password, limiter, safe_person_name
from main import app

VALID_DAY = "1405/06/02"


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


class NullNameWorld(unittest.TestCase):
    """دنیای تست با رکوردهای دارای نام NULL (معلم و دانش‌آموز)."""

    def setUp(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                               poolclass=StaticPool)
        models.Base.metadata.create_all(engine)
        self.engine = engine
        Session = sessionmaker(bind=engine, expire_on_commit=False)
        self.db = Session()
        now = datetime.datetime.now()
        # معلم ۱ و دانش‌آموز ۱: نام و نام‌خانوادگی NULL (رکورد legacy)
        self.db.add_all([
            models.Branch(id=1, name="شعبه یک", active=True),
            models.Teacher(id=1, teacher_code=101, first_name=None, last_name=None,
                           mobile="09120000001", national_code="0001000129",
                           password=hash_password("101"), is_approved=True, is_deleted=False,
                           branch_id=1),
            models.Teacher(id=2, teacher_code=102, first_name="سارا", last_name="کریمی",
                           mobile="09120000002", national_code="0001000130",
                           password=hash_password("102"), is_approved=True, is_deleted=False,
                           branch_id=1),
            models.Course(id=1, title="ریاضی", code="A4-1", teacher_id=1, branch_id=1,
                          grade_level="دهم", class_time="16:00-17:30", days_of_week="شنبه",
                          teacher_session_price=200000, is_deleted=False, is_admin_approved=True),
            models.Course(id=2, title="فیزیک", code="A4-2", teacher_id=2, branch_id=1,
                          grade_level="یازدهم", class_time="18:00-19:30", days_of_week="یکشنبه",
                          teacher_session_price=150000, is_deleted=False, is_admin_approved=True),
            models.Student(id=1, student_code=1, first_name=None, last_name=None,
                           national_code="0012345681", student_mobile="09121111111",
                           branch_id=1, wallet_teacher=0, wallet_institute=0, wallet_balance=0,
                           is_deleted=False),
            models.Student(id=2, student_code=2, first_name="زهرا", last_name="موسوی",
                           national_code="0012345682", student_mobile="09122222222",
                           branch_id=1, wallet_teacher=0, wallet_institute=0, wallet_balance=0,
                           is_deleted=False),
            models.User(id=1, username="admin-global", password="x", full_name="مدیر مرکزی",
                        role="admin", sub_role="admin", branch_id=None),
            models.User(id=2, username="admin-b1", password="x", full_name="مدیر شعبه",
                        role="admin", sub_role="admin", branch_id=1),
        ])
        for uid, tok, role in [(1, "tok-global", "admin"), (2, "tok-b1", "admin")]:
            self.db.add(models.UserSession(token=tok, user_id=uid, sub_role=role, created_at=now))
        self.db.add_all([
            models.Enrollment(id=1, student_id=1, course_id=1, branch_id=1,
                              register_date="1405/06/01", total_tuition=1000000, total_paid=0,
                              is_deleted=False),
            models.Enrollment(id=2, student_id=2, course_id=2, branch_id=1,
                              register_date="1405/06/01", total_tuition=900000, total_paid=0,
                              is_deleted=False),
        ])
        self.db.flush()
        # جلسه‌ی ۱ کلاس معلم بی‌نام، با حضور تسویه‌نشده‌ی دانش‌آموز بی‌نام ⇒ طلب معلم = ۲۰۰٬۰۰۰
        self.db.add(models.SessionLog(id=1, session_code=1001, course_id=1, date=VALID_DAY,
                                      time="16:00-17:30", final_teacher_cost=200000,
                                      final_institute_share=50000, cost_per_student=150000,
                                      attendee_count=1, status="Finished", is_deleted=False))
        self.db.flush()
        self.db.add(models.Attendance(id=1, session_id=1, student_id=1, status="Present",
                                      is_billed=False, is_deleted=False))
        # تراکنش برای رسید و گزارش مالی
        # Attendance برای دانش‌آموزی که رکوردش وجود ندارد ⇒ باید «حذف شده» بماند (نه «نامشخص»)
        self.db.add(models.Attendance(id=2, session_id=1, student_id=999, status="Absent",
                                      is_billed=False, is_deleted=False))
        # تنظیمات آموزشگاه (در محیط واقعی همیشه وجود دارد؛ بدون آن فیلدهای مؤسسه None می‌شوند)
        self.db.add(models.InstituteSettings(id=1))
        self.db.add(models.Transaction(id=1000, student_id=1, course_id=1, branch_id=1,
                                       enrollment_id=1, amount=500000, type="tuition",
                                       date=VALID_DAY, description="شهریه",
                                       share_teacher=200000, share_institute=300000,
                                       is_deleted=False, is_reversed=False))
        # جلسه‌ی زنده‌ی کلاس معلم بی‌نام
        self.db.add(models.LiveSession(id=1, course_id=1, teacher_id=1, status="LIVE",
                                       start_time="16:00", started_at_ts=int(now.timestamp()),
                                       live_roster=json.dumps({"1": {"status": "Present",
                                                                     "excused": False}})))
        self.db.commit()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        # ورودهای پیاپی در یک تست به سقف ریت‌لیمیت می‌خورند؛ در تست خاموش می‌شود.
        limiter.enabled = False

    def tearDown(self):
        limiter.enabled = True
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    # ---------------- کمکی‌ها ----------------
    def get_ok(self, url, token="tok-global", **params):
        r = self.client.get(url, params=params or None, headers=hdr(token))
        self.assertEqual(r.status_code, 200, r.text)
        return r

    def post_ok(self, url, token="tok-global", **kw):
        r = self.client.post(url, headers=hdr(token), **kw)
        self.assertEqual(r.status_code, 200, r.text)
        return r

    def assert_no_none_leak(self, text, where=""):
        """هیچ رشته‌ای در خروجی نباید «None» به‌عنوان نام داشته باشد."""
        self.assertNotIn("None", text, f"نشت «None» در {where}")
        self.assertNotIn("null null", text.lower(), f"نشت «null null» در {where}")

    def assert_clean(self, value, expected, where=""):
        self.assertEqual(value, expected, where)
        self.assert_no_none_leak(str(value), where)


class TestNameHelpers(NullNameWorld):
    def test_both_parts_present(self):
        self.assertEqual(safe_person_name("علی", "رضایی"), "علی رضایی")

    def test_both_parts_missing_returns_fallback(self):
        self.assertEqual(safe_person_name(None, None, "نامشخص"), "نامشخص")

    def test_both_parts_missing_without_fallback_is_empty(self):
        self.assertEqual(safe_person_name(None, None), "")

    def test_only_first_name(self):
        self.assertEqual(safe_person_name("علی", None), "علی")

    def test_only_last_name(self):
        self.assertEqual(safe_person_name(None, "رضایی"), "رضایی")

    def test_blank_strings_are_treated_as_missing(self):
        self.assertEqual(safe_person_name("   ", "", "نامشخص"), "نامشخص")
        self.assertEqual(safe_person_name(" علی ", " رضایی "), "علی رضایی")

    def test_digits_and_non_string_values_survive(self):
        self.assertEqual(safe_person_name(0, "رضایی"), "0 رضایی")

    def test_display_name_on_object(self):
        teacher = self.db.query(models.Teacher).filter(models.Teacher.id == 2).first()
        self.assertEqual(display_name(teacher, "نامشخص"), "سارا کریمی")

    def test_display_name_none_object(self):
        self.assertEqual(display_name(None, "بدون معلم"), "بدون معلم")

    def test_display_name_null_named_object(self):
        teacher = self.db.query(models.Teacher).filter(models.Teacher.id == 1).first()
        self.assertEqual(display_name(teacher, "نامشخص"), "نامشخص")


class TestLoginWithNullTeacherName(NullNameWorld):
    """auth: ساخت full_name و سازگاری مقایسه/همگام‌سازی (حساس‌ترین نقطهٔ A4)."""

    def login(self):
        r = self.client.post("/auth/login", json={"mobile": "09120000001", "password": "101"})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_login_name_is_not_none(self):
        body = self.login()
        self.assert_no_none_leak(json.dumps(body, ensure_ascii=False), "پاسخ ورود معلم بی‌نام")
        self.assertEqual(body["role"], "teacher")
        self.assertTrue(body["name"].strip(), "نام پاسخ ورود نباید خالی باشد")

    def test_shadow_user_full_name_is_not_none(self):
        self.login()
        u = self.db.query(models.User).filter(models.User.username == "09120000001").first()
        self.assertIsNotNone(u)
        self.assert_no_none_leak(str(u.full_name), "full_name سایه‌ی معلم")
        self.assertTrue(u.full_name.strip())

    def test_second_login_does_not_rewrite_full_name(self):
        """مقایسه و انتساب باید یک مقدار مشترک بدهند؛ وگرنه هر لاگین یک UPDATE بی‌دلیل است."""
        self.login()
        u = self.db.query(models.User).filter(models.User.username == "09120000001").first()
        before = u.full_name
        self.db.expire_all()
        self.login()
        self.db.expire_all()
        u2 = self.db.query(models.User).filter(models.User.username == "09120000001").first()
        self.assertEqual(u2.full_name, before,
                         "لاگین دوم نباید full_name را تغییر دهد (شکست invariant مقایسه/انتساب)")
        self.assert_no_none_leak(str(u2.full_name), "full_name پس از لاگین دوم")

    def test_second_login_admin_branch_keeps_clean_name(self):
        """وقتی سایه ساخته شد، لاگین بعدی از شاخهٔ ادمین پاسخ می‌دهد؛ نام آن هم نباید None باشد."""
        self.login()
        body = self.login()
        self.assert_no_none_leak(json.dumps(body, ensure_ascii=False), "پاسخ لاگین دوم (شاخهٔ ادمین)")
        self.assertTrue(str(body["name"]).strip(), "نام پاسخ لاگین دوم نباید خالی باشد")

    def test_teacher_branch_syncs_full_name_when_teacher_gets_a_name(self):
        """شاخهٔ معلم: اگر معلم بعداً نام بگیرد، full_name سایه همگام می‌شود (رفتار قبلی حفظ شود).

        توجه: برای رسیدن به شاخهٔ معلم، سایهٔ ساخته‌شده حذف می‌شود؛ وگرنه lookup اولِ ادمین
        (که با username == موبایل مطابقت می‌کند) پاسخ می‌دهد — رفتاری موجود و خارج از دامنهٔ A4.
        """
        self.login()
        self.db.query(models.Teacher).filter(models.Teacher.id == 1).update(
            {"first_name": "حسن", "last_name": "بی‌نام‌زاده"})
        self.db.query(models.User).filter(models.User.username == "09120000001").delete()
        self.db.commit()
        self.db.expire_all()
        body = self.login()
        self.assertEqual(body["role"], "teacher", body)
        self.assertEqual(body["name"], "حسن بی‌نام‌زاده")
        u = self.db.query(models.User).filter(models.User.username == "09120000001").first()
        self.assertEqual(u.full_name, "حسن بی‌نام‌زاده")


class TestMoneyNamesKeepAmounts(NullNameWorld):
    """مالی: نام امن شود ولی هیچ عددی تغییر نکند."""

    def test_teacher_settlement_summary_amount_untouched(self):
        rows = self.get_ok("/finance/reports/teacher_settlements_summary").json()
        row = next(r for r in rows if r["teacher_id"] == 1)
        self.assert_clean(row["teacher_name"], "نامشخص", "نام معلم بی‌نام در گزارش تسویه")
        # طلب = هزینه‌ی قراردادی جلسه‌ی تسویه‌نشده (حضور Present و is_billed=False)
        self.assertEqual(row["wallet_balance"], 200000, "طلب معلم نباید تغییر کند")
        self.assertEqual(row["pending_total_amount"], 200000)
        self.assertEqual(row["session_count"], 1)
        named = next(r for r in rows if r["teacher_id"] == 2)
        self.assertEqual(named["teacher_name"], "سارا کریمی", "معلم سالم نباید تغییر کند")

    def test_receipt_amount_untouched(self):
        body = self.get_ok("/finance/receipt/1000").json()
        flat = json.dumps(body, ensure_ascii=False)
        self.assert_no_none_leak(flat, "رسید تراکنش")
        self.assertEqual(body.get("amount"), 500000, "مبلغ رسید نباید تغییر کند")

    def test_financial_report_amount_untouched_and_named(self):
        rows = self.get_ok("/reports/financial").json()
        self.assertTrue(rows)
        total = sum(r["amount"] for r in rows)
        self.assertEqual(total, 500000, "جمع درآمد نباید تغییر کند")
        for row in rows:
            if row.get("teacher_name") is not None:
                self.assert_no_none_leak(str(row["teacher_name"]), "teacher_name در گزارش مالی")

    def test_debtors_list_names_are_safe(self):
        rows = self.get_ok("/finance/reports/debtors_list").json()
        flat = json.dumps(rows, ensure_ascii=False)
        self.assert_no_none_leak(flat, "لیست بدهکاران")

    def test_reports_debtors_names_are_safe(self):
        rows = self.get_ok("/reports/debtors").json()
        flat = json.dumps(rows, ensure_ascii=False)
        self.assert_no_none_leak(flat, "گزارش بدهکاران")
        # ردیف دانش‌آموز بی‌نام باید نام امن داشته باشد
        target = [r for r in rows if r.get("student_name") is not None]
        if target:
            self.assert_clean(target[0]["student_name"], "نامشخص", "نام دانش‌آموز بی‌نام")

    def test_finance_search_advanced_names_are_safe(self):
        r = self.client.get("/finance/search_advanced", params={"query": ""}, headers=hdr("tok-global"))
        self.assertEqual(r.status_code, 200, r.text)
        self.assert_no_none_leak(json.dumps(r.json(), ensure_ascii=False), "جست‌وجوی پیشرفته مالی")


class TestAttendanceAndClassNames(NullNameWorld):
    def test_session_details_names_are_safe(self):
        body = self.get_ok("/attendance/session/1001").json()
        self.assert_no_none_leak(json.dumps(body, ensure_ascii=False), "جزئیات جلسه")
        self.assert_clean(body["teacher_name"], "نامشخص", "نام معلم بی‌نام")
        item = next(i for i in body["items"] if i["student_id"] == 1)
        self.assert_clean(item["name"], "نامشخص", "نام دانش‌آموز بی‌نام")

    def test_missing_student_record_keeps_deleted_label(self):
        """رفتار قبلی حفظ شود: دانش‌آموزی که رکوردش نیست «حذف شده» است، نه «نامشخص»."""
        body = self.get_ok("/attendance/session/1001").json()
        gone = next(i for i in body["items"] if i["student_id"] == 999)
        self.assert_clean(gone["name"], "حذف شده", "دانش‌آموز بدون رکورد")

    def test_missing_teacher_record_keeps_existing_label(self):
        """کلاسی که رکورد معلمش پیدا نمی‌شود باید همان جایگزین قبلی («نامشخص») را بدهد."""
        self.db.add(models.Course(id=3, title="شیمی", code="A4-3", teacher_id=7777, branch_id=1,
                                  grade_level="دوازدهم", class_time="10:00", days_of_week="دوشنبه",
                                  teacher_session_price=100000, is_deleted=False,
                                  is_admin_approved=True))
        self.db.commit()
        rows = self.get_ok("/classes/list").json()
        target = next(r for r in rows if r["id"] == 3)
        self.assert_clean(target["teacher_name"], "نامشخص", "کلاس بدون رکورد معلم")

    def test_finance_search_no_teacher_label(self):
        """جست‌وجوی مالی برای کلاس بدون رکورد معلم باید «بدون معلم» بدهد (جایگزین قبلی همان نقطه)."""
        self.db.add(models.Course(id=3, title="شیمی", code="A4-3", teacher_id=7777, branch_id=1,
                                  grade_level="دوازدهم", class_time="10:00", days_of_week="دوشنبه",
                                  teacher_session_price=100000, is_deleted=False,
                                  is_admin_approved=True))
        self.db.commit()
        body = self.get_ok("/finance/search_advanced", query="شیمی").json()
        flat = json.dumps(body, ensure_ascii=False)
        self.assert_no_none_leak(flat, "جست‌وجوی مالی")
        found = [c for c in (body.get("courses") or []) if c.get("id") == 3] if isinstance(body, dict) else []
        if found:
            self.assert_clean(found[0]["teacher_name"], "بدون معلم", "کلاس بدون معلم در جست‌وجوی مالی")

    def test_live_session_roster_names_are_safe(self):
        body = self.get_ok("/admin/live_sessions/1/roster").json()
        self.assert_no_none_leak(json.dumps(body, ensure_ascii=False), "لیست حاضرین جلسه‌ی زنده")
        self.assert_clean(body["teacher_name"], "نامشخص", "نام معلم بی‌نام در جلسه‌ی زنده")
        item = next(s for s in body["students"] if s["student_id"] == 1)
        self.assert_clean(item["student_name"], "نامشخص", "نام دانش‌آموز بی‌نام در روستر")
        self.assertEqual(item["status"], "Present", "وضعیت حضور نباید تغییر کند")

    def test_classes_list_names_are_safe(self):
        rows = self.get_ok("/classes/list").json()
        target = next(r for r in rows if r["id"] == 1)
        self.assert_clean(target["teacher_name"], "نامشخص", "نام معلم بی‌نام در لیست کلاس‌ها")
        if target.get("students"):
            self.assert_clean(target["students"][0], "نامشخص", "نام دانش‌آموز بی‌نام در لیست کلاس")

    def test_class_students_full_names_are_safe(self):
        body = self.get_ok("/classes/1/students_full").json()
        self.assert_no_none_leak(json.dumps(body, ensure_ascii=False), "دانش‌آموزان کلاس")
        item = next(s for s in body["students"] if s["student_id"] == 1)
        self.assert_clean(item["student_name"], "نامشخص", "نام دانش‌آموز بی‌نام در فهرست کلاس")

    def test_class_full_report_names_are_safe(self):
        body = self.get_ok("/classes/1/full_report").json()
        self.assert_no_none_leak(json.dumps(body, ensure_ascii=False), "گزارش کامل کلاس")

    def test_class_students_excel_contains_safe_names(self):
        r = self.get_ok("/classes/1/students_full/excel")
        text = r.content.decode("utf-8", errors="ignore")
        self.assertNotIn("None", text, "فایل اکسل دانش‌آموزان نباید «None» داشته باشد")

    def test_class_deletion_requests_names_are_safe(self):
        r = self.get_ok("/classes/deletion_requests")
        self.assert_no_none_leak(json.dumps(r.json(), ensure_ascii=False), "درخواست‌های حذف کلاس")


class TestPrintedReportsHaveNoNone(NullNameWorld):
    def test_student_statement_has_no_none(self):
        body = self.get_ok("/reports/student_statement", student_id=1).json()
        self.assert_no_none_leak(json.dumps(body, ensure_ascii=False), "صورت‌حساب دانش‌آموز")

    def test_student_statement_print_html_has_no_none(self):
        r = self.get_ok("/reports/student_statement/print", student_id=1)
        self.assertNotIn("None", r.content.decode("utf-8", errors="ignore"),
                         "HTML صورت‌حساب چاپی نباید «None» داشته باشد")

    def test_student_profile_print_html_has_no_none(self):
        r = self.get_ok("/reports/student_profile/print", student_id=1)
        self.assertNotIn("None", r.content.decode("utf-8", errors="ignore"),
                         "HTML پروفایل چاپی نباید «None» داشته باشد")

    def test_report_survives_named_student_too(self):
        """رکورد سالم باید دقیقاً مثل قبل نمایش داده شود (بدون جایگزین ناخواسته)."""
        r = self.get_ok("/reports/student_profile/print", student_id=2)
        html = r.content.decode("utf-8", errors="ignore")
        self.assertIn("زهرا", html)
        self.assertIn("موسوی", html)


if __name__ == "__main__":
    unittest.main()
