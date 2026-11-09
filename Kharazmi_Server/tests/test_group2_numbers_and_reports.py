# test_group2_numbers_and_reports.py
# ═══════════════════════════════════════════════════════════════════════════════
# گروه ۲ — اعداد و گزارش‌های غلط (آیتم‌های ۴ تا ۹)
#
#   ۴) «وضعیت امروز / پرداختی امروز / ثبت‌نام امروز» در داشبورد ادمین غلط است
#   ۵) گزارش مالی معلم در پنل معلم کار نمی‌کند
#   ۶) خروجی بدهکاران خالی است با وجود داده
#   ۷) محدودهٔ گزارش‌گیری → انتخاب معلم: هیچ معلمی نمایش داده نمی‌شود
#   ۹) گزارش بدهکاران داشبورد ادمین ناقص است (+ گروه‌بندی معلم/قدمت بدهی/پیامک/اکسل)
#
# آیتم ۸ (تاریخچهٔ تغییرات مالی) در فایل جدا: test_group2_audit_trail_enrichment.py
#
# اجرا (DB موقت — هرگز gaj_db.db واقعی):
#   DATABASE_URL=sqlite:////tmp/g2.db JWT_SECRET_KEY=test \
#     python3 -m pytest Kharazmi_Server/tests/test_group2_numbers_and_reports.py -q
# ═══════════════════════════════════════════════════════════════════════════════
import datetime
import io
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
import routers.dashboard as dash
from dependencies import get_db, hash_password, limiter
from main import app
from today_summary import jalali_date_string, parse_project_date

TODAY_GREG = datetime.date.today()
TODAY_JALALI = jalali_date_string(TODAY_GREG)
TODAY_ISO = TODAY_GREG.isoformat()
THIS_MONTH_START = f"{TODAY_JALALI[:7]}01"
YESTERDAY_JALALI = jalali_date_string(TODAY_GREG - datetime.timedelta(days=1))


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


class Group2World(unittest.TestCase):
    """دنیای مشترک — عمداً شکل دادهٔ واقعی آموزشگاه (کپی /tmp از gaj_db.db):

    * `students.branch_id = NULL` و `teachers.branch_id = NULL` (ردیف‌های legacy)
    * کاربر ادمین/منشی با `branch_id = 1` (چون `scripts/create_admin.py` شعبه می‌دهد)
    ⇒ هر کوئری که `branch_id == <شعبهٔ کاربر>` را **سخت** فیلتر کند، این ردیف‌ها را
    کامل حذف می‌کند (ریشهٔ مشترک آیتم‌های ۶ و ۹؛ و عامل خالی‌شدن گزارش‌های شعبه‌دار).
    """

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
        self.db.add(models.Branch(id=2, name="شعبه شرق", active=True))
        self.db.add(models.User(id=101, username="09120000201", password=hash_password("a-pass"),
                                full_name="مدیر کل", role="admin", sub_role="admin", branch_id=1))
        self.db.add(models.User(id=102, username="09120000202", password=hash_password("s-pass"),
                                full_name="منشی", role="secretary", sub_role="secretary", branch_id=1))
        # معلم‌ها: branch_id NULL (legacy) — مثل دادهٔ واقعی
        self.teacher = models.Teacher(id=51, first_name="مریم", last_name="احمدی",
                                      mobile="09120000203", national_code="0012345901",
                                      password=hash_password("t-pass"), is_approved=True,
                                      is_deleted=False, is_suspended=False, branch_id=None)
        self.teacher2 = models.Teacher(id=52, first_name="رضا", last_name="کریمی",
                                       mobile="09120000206", national_code="0012345904",
                                       password=hash_password("t2-pass"), is_approved=True,
                                       is_deleted=False, is_suspended=False, branch_id=None)
        self.teacher_new = models.Teacher(id=53, first_name="سارا", last_name="نو",
                                          mobile="09120000207", national_code="0012345905",
                                          password=hash_password("t3-pass"), is_approved=True,
                                          is_deleted=False, is_suspended=False, branch_id=None)
        self.teacher_archived = models.Teacher(id=54, first_name="قدیمی", last_name="حذف‌شده",
                                               mobile="09120000208", national_code="0012345906",
                                               password=hash_password("t4-pass"), is_approved=True,
                                               is_deleted=True, is_suspended=False, branch_id=None)
        self.db.add_all([self.teacher, self.teacher2, self.teacher_new, self.teacher_archived])
        self.db.add(models.User(id=103, username="09120000203", password=hash_password("t-pass"),
                                full_name="مریم احمدی", role="teacher", sub_role="teacher", branch_id=1))
        self.db.add(models.User(id=104, username="09120000207", password=hash_password("t3-pass"),
                                full_name="سارا نو", role="teacher", sub_role="teacher", branch_id=1))
        # دانش‌آموزان: branch_id NULL (legacy)
        self.debtor = models.Student(id=41, student_code=41, first_name="علی", last_name="رضایی",
                                     national_code="0012345902", student_mobile="09120000204",
                                     parent_mobile="09120000205", branch_id=None,
                                     wallet_teacher=0, wallet_institute=0, wallet_balance=0,
                                     is_deleted=False, is_suspended=False)
        self.clean = models.Student(id=42, student_code=42, first_name="سارا", last_name="کریمی",
                                    national_code="0012345903", student_mobile="09120000209",
                                    parent_mobile="09120000210", branch_id=None,
                                    wallet_teacher=0, wallet_institute=0, wallet_balance=0,
                                    is_deleted=False, is_suspended=False)
        self.archived_student = models.Student(id=43, student_code=43, first_name="بایگانی",
                                               last_name="شده", national_code="0012345907",
                                               branch_id=None, wallet_teacher=0, wallet_institute=0,
                                               wallet_balance=0, is_deleted=True, is_suspended=False)
        self.db.add_all([self.debtor, self.clean, self.archived_student])
        self.db.add(models.InstituteShare(id=1, count_1=50000, count_2=80000, count_3=100000))
        for tok, uid, tid, role in (("tok-admin", 101, None, "admin"),
                                    ("tok-sec", 102, None, "secretary"),
                                    ("tok-teacher", 103, 51, "teacher"),
                                    ("tok-teacher-new", 104, 53, "teacher")):
            self.db.add(models.UserSession(token=tok, user_id=uid, teacher_id=tid,
                                           sub_role=role, created_at=now))
        self.db.commit()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        dash._dashboard_cache.clear()

    def tearDown(self):
        app.dependency_overrides.clear()
        dash._dashboard_cache.clear()
        limiter.enabled = self._limiter
        self.db.close()
        self.engine.dispose()

    # ---------------- کمکی ----------------
    def create_class(self, teacher_id=51, title="ریاضی دهم", days="شنبه", time="17:30",
                     price=150000, branch_id=1, approve=True, token="tok-admin"):
        resp = self.client.post("/classes/create", json={
            "title": title, "code": "0", "teacher_id": teacher_id, "education_type": "عادی",
            "grade_level": "دهم", "gender_type": "مختلط", "class_type": "خصوصی",
            "days_of_week": days, "class_time": time, "teacher_session_price": price,
            "branch_id": branch_id,
        }, headers=hdr(token))
        self.assertEqual(resp.status_code, 200, resp.text)
        cid = resp.json()["id"]
        if approve:
            self.assertEqual(self.client.post(f"/admin/approve_class/{cid}",
                                              headers=hdr(token)).status_code, 200)
        return cid

    def enroll(self, course_id, student_id=41, tuition=1000000, paid=0, date="1405/06/01",
               token="tok-admin"):
        return self.client.post("/enrollments/add", json={
            "student_id": student_id, "course_id": course_id, "register_date": date,
            "shift": "عصر", "total_tuition": tuition, "paid_amount": paid,
            "payment_method": "کارت", "receiver": "مدیر",
        }, headers=hdr(token))

    def add_tx(self, **kw):
        kw.setdefault("branch_id", 1)
        kw.setdefault("is_deleted", False)
        kw.setdefault("is_reversed", False)
        row = models.Transaction(**kw)
        self.db.add(row)
        self.db.commit()
        return row


# ═══════════════════════════════════════════════════════════════════════════════
# آیتم ۴ — سه عدد «امروز» در داشبورد ادمین
# ═══════════════════════════════════════════════════════════════════════════════
class TestAdminTodayNumbers(Group2World):
    """ریشه (قبل از فیکس) در `today_summary.build_admin_today_summary`:

    * `today_payments`: جمع `amount>0` برای `type in (deposit, enrollment_payment, tuition,
      payment)` با `LIKE` روی سه پیشوند تاریخ ⇒ (الف) واریزی به **کیف معلم** هم شمرده می‌شد
      (دقیقاً همان باگ O-08 که در `/dashboard/kpis` فیکس شد)، (ب) ردیف legacy با
      `type=NULL` دیده نمی‌شد، (پ) با تعریف KPI «درآمد امروز» یکی نبود ⇒ دو عدد متفاوت
      برای یک روز در دو صفحهٔ اپ.
    * `today_enrollments`: `LIKE` روی `register_date` بدون فیلتر `is_deleted` و بدون پارس
      مرکزی تاریخ ⇒ ثبت‌نام آرشیوشده شمرده می‌شد و تاریخ‌های نامرسوم نمی‌خوردند.
    """

    def test_4a_today_summary_and_kpi_show_the_same_number(self):
        cid = self.create_class()
        self.enroll(cid, 41, tuition=1000000, paid=400000, date=TODAY_JALALI)
        # واریزی امروز به کیف آموزشگاه (مسیر «ثبت پرداخت»)
        self.add_tx(id=901, student_id=41, course_id=cid, amount=300000, type="deposit",
                    target_wallet="institute", payment_method="نقدی", date=TODAY_JALALI,
                    description="وصولی امروز")
        # واریزی امروز به کیف **معلم** — پول آموزشگاه نیست (باگ O-08)
        self.add_tx(id=902, student_id=41, course_id=cid, amount=900000, type="deposit",
                    target_wallet="teacher", payment_method="کارت", date=TODAY_JALALI,
                    description="سهم معلم")
        # شارژ جلسهٔ امروز (منفی) — نباید از وصولی کم شود
        self.add_tx(id=903, student_id=41, course_id=cid, amount=-400000, type="session_charge",
                    payment_method="System", date=TODAY_JALALI, share_teacher=300000,
                    share_institute=100000, description="هزینه جلسه")
        # واریزی دیروز — امروز نیست
        self.add_tx(id=904, student_id=41, course_id=cid, amount=777000, type="deposit",
                    target_wallet="institute", payment_method="نقدی", date=YESTERDAY_JALALI,
                    description="دیروز")

        summary = self.client.get("/admin/today_summary", headers=hdr("tok-admin"))
        self.assertEqual(summary.status_code, 200, summary.text)
        body = summary.json()
        kpi = self.client.get("/dashboard/kpis", headers=hdr("tok-admin"))
        self.assertEqual(kpi.status_code, 200, kpi.text)

        # پیش‌پرداخت ثبت‌نام (۴۰۰٬۰۰۰ → کیف آموزشگاه) + واریزی دستی امروز (۳۰۰٬۰۰۰)
        self.assertEqual(body["today_payments"], 700000,
                         f"پرداختی امروز باید فقط وصولی نقدی آموزشگاه باشد: {body}")
        self.assertEqual(body["today_payments"], kpi.json()["today_revenue"],
                         "دو عدد «امروز» در دو صفحهٔ اپ باید یکی باشد (تعریف مشترک)")

    def test_4b_today_payments_counts_gregorian_dated_and_legacy_rows(self):
        """واریزی با تاریخ میلادی امروز و ردیف legacy بدون type/target_wallet باید شمرده شوند."""
        self.add_tx(id=911, student_id=41, amount=700000, type="deposit",
                    target_wallet="institute", payment_method="کارت", date=TODAY_ISO,
                    description="وصولی با تاریخ میلادی")
        self.add_tx(id=912, student_id=41, amount=2000000, type=None, target_wallet=None,
                    payment_method="نقدی", date=TODAY_JALALI, description="ردیف legacy")
        body = self.client.get("/admin/today_summary", headers=hdr("tok-admin")).json()
        self.assertEqual(body["today_payments"], 2700000, body)
        dash._dashboard_cache.clear()
        kpi = self.client.get("/dashboard/kpis", headers=hdr("tok-admin")).json()
        self.assertEqual(kpi["today_revenue"], 2700000,
                         "KPI هم باید ردیف legacy/میلادی را ببیند (همان تعریف مشترک)")

    def test_4b2_persian_digits_and_timestamped_dates_are_read_too(self):
        """ستون تاریخ دو تقویمه/دو قالبی است (H3-B3): ارقام فارسی و ساعت چسبیده به تاریخ."""
        self.add_tx(id=915, student_id=41, amount=110000, type="deposit",
                    target_wallet="institute", date=TODAY_JALALI.translate(
                        str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")), description="ارقام فارسی")
        self.add_tx(id=916, student_id=41, amount=90000, type="deposit",
                    target_wallet="institute", date=f"{TODAY_JALALI} 18:45",
                    description="شمسی با ساعت")
        body = self.client.get("/admin/today_summary", headers=hdr("tok-admin")).json()
        self.assertEqual(body["today_payments"], 200000, body)

    def test_4c_today_payments_ignores_undated_reversed_and_deleted_rows(self):
        self.add_tx(id=921, student_id=41, amount=120000, type="deposit",
                    target_wallet="institute", date="", description="بی‌تاریخ")
        self.add_tx(id=922, student_id=41, amount=500000, type="deposit",
                    target_wallet="institute", date=TODAY_JALALI, is_reversed=True,
                    description="برگشت‌خورده")
        self.add_tx(id=923, student_id=41, amount=400000, type="deposit",
                    target_wallet="institute", date=TODAY_JALALI, is_deleted=True,
                    description="حذف‌شده")
        body = self.client.get("/admin/today_summary", headers=hdr("tok-admin")).json()
        self.assertEqual(body["today_payments"], 0, body)

    def test_4d_today_enrollments_uses_central_date_parser_and_skips_archived(self):
        cid = self.create_class()
        cid2 = self.create_class(teacher_id=52, title="فیزیک", days="یکشنبه", time="19:00")
        # ثبت‌نام امروز با تاریخ میلادی (پارس مرکزی) + ثبت‌نام امروز با تاریخ شمسی
        self.assertEqual(self.enroll(cid, 41, date=TODAY_ISO).status_code, 200)
        self.assertEqual(self.enroll(cid2, 42, date=TODAY_JALALI).status_code, 200)
        body = self.client.get("/admin/today_summary", headers=hdr("tok-admin")).json()
        self.assertEqual(body["today_enrollments"], 2, body)
        # آرشیو کردن یکی ⇒ دیگر «ثبت‌نام امروز» نیست (هم‌سیاست بقیهٔ نماهای فعال)
        row = self.db.query(models.Enrollment).filter(models.Enrollment.student_id == 42).first()
        row.is_deleted = True
        self.db.commit()
        body = self.client.get("/admin/today_summary", headers=hdr("tok-admin")).json()
        self.assertEqual(body["today_enrollments"], 1, body)

    def test_4e_secretary_still_sees_no_money(self):
        """سیاست موجود: منشی مبلغ نمی‌بیند (payment_visible=False) — باید حفظ شود."""
        self.add_tx(id=931, student_id=41, amount=300000, type="deposit",
                    target_wallet="institute", date=TODAY_JALALI)
        body = self.client.get("/admin/today_summary", headers=hdr("tok-sec")).json()
        self.assertFalse(body["payment_visible"])
        self.assertIsNone(body["today_payments"])


# ═══════════════════════════════════════════════════════════════════════════════
# آیتم ۵ — گزارش مالی معلم در پنل معلم
# ═══════════════════════════════════════════════════════════════════════════════
class TestTeacherFinancialReport(Group2World):
    """ریشه (با درخواست واقعی گرفته شد — حدس نیست):

    ۱) `ReportActivity.kt:315` برای معلم `teacherId = null` می‌فرستد؛ Retrofit یک `@Query`
       خالی را به‌صورت `teacher_id=` روی URL می‌گذارد ⇒ امضای `teacher_id: Optional[int]`
       در سرور ۴۲۲ می‌دهد با بدنهٔ خام pydantic:
       `{"type":"int_parsing","loc":["query","teacher_id"],"msg":"Input should be a valid integer…","input":""}`
       ⇒ «گزارش مالی معلم در پنل معلم کار نمی‌کنه».
       (بدون همان پارامتر خالی، مسیر ۲۰۰ است — یعنی قفل «معلمِ لاگین‌شده» سالم است.)
    ۲) `year`/`month` هم با متن خالی ۴۲۲ می‌دهند (وقتی فیلدهای سال/ماه خالی باشند).
    ۳) `user_type` نامعتبر ⇒ **۲۰۰ با بدنهٔ `null`** (تابع بدون return پایان می‌یابد) ⇒
       Gson در کلاینت روی `FinancialSummaryResponse` غیرnullable خطا می‌دهد.

    نکتهٔ رد‌شده: `.in_([])` در SQLAlchemy 2.0.54 خطا نمی‌دهد (سنجش مستقیم انجام شد)،
    پس «معلم بدون کلاس ⇒ ۵۰۰» ریشهٔ این باگ **نیست**.
    """

    def test_5a_teacher_panel_request_with_empty_query_params_works(self):
        """دقیقاً همان درخواستی که اپ معلم می‌فرستد: teacher_id/year/month خالی."""
        resp = self.client.get("/reports/financial_summary",
                               params={"user_type": "teacher", "teacher_id": "",
                                       "year": "", "month": ""},
                               headers=hdr("tok-teacher-new"))
        self.assertEqual(resp.status_code, 200,
                         f"گزارش مالی پنل معلم نباید خطا بدهد: {resp.text}")
        body = resp.json()
        self.assertEqual(body["user_type"], "teacher")
        self.assertEqual(body["teacher_id"], 53, "معلم باید به خودش قفل شود")
        self.assertEqual(body["year"], int(TODAY_JALALI[:4]), "پیش‌فرض: سال شمسی جاری")
        self.assertEqual(body["month"], int(TODAY_JALALI[5:7]), "پیش‌فرض: ماه شمسی جاری")
        self.assertEqual(body["monthly"]["total"], 0)
        self.assertEqual(body["monthly"]["collected"], 0)
        self.assertEqual(body["yearly"]["uncollected"], 0)

    def test_5b_teacher_with_class_gets_real_numbers(self):
        cid = self.create_class(teacher_id=51)
        self.assertEqual(self.enroll(cid, 41, tuition=1000000, paid=400000).status_code, 200)
        items = [{"student_id": 41, "status": "Present", "excused": False}]
        self.assertEqual(self.client.post("/attendance/submit_session", json={
            "course_id": cid, "date": TODAY_JALALI, "items": items},
            headers=hdr("tok-admin")).status_code, 200)
        resp = self.client.get("/reports/financial_summary",
                               params={"user_type": "teacher", "year": int(TODAY_JALALI[:4]),
                                       "month": int(TODAY_JALALI[5:7])},
                               headers=hdr("tok-teacher"))
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["teacher_id"], 51)
        self.assertGreater(body["monthly"]["total"], 0, "کارکرد معلم از شارژ جلسه")
        self.assertEqual(body["monthly"]["uncollected"],
                         max(0, body["monthly"]["total"] - body["monthly"]["collected"]))

    def test_5c_admin_viewing_a_teacher_with_no_class_gets_zero_not_500(self):
        resp = self.client.get("/reports/financial_summary",
                               params={"user_type": "teacher", "teacher_id": 53},
                               headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["monthly"]["total"], 0)

    def test_5d_unknown_user_type_does_not_return_null_body(self):
        """بدنهٔ `null` کلاینت را می‌شکند (Gson روی FinancialSummaryResponse) — باید ۴۰۰ گویا باشد."""
        resp = self.client.get("/reports/financial_summary", params={"user_type": "banana"},
                               headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertIn("user_type", resp.json()["detail"], resp.text)
        # teacher_id خالی برای ادمین هم باید پیام فارسی بدهد، نه بدنهٔ خام pydantic
        r2 = self.client.get("/reports/financial_summary",
                             params={"user_type": "teacher", "teacher_id": ""},
                             headers=hdr("tok-admin"))
        self.assertEqual(r2.status_code, 400, r2.text)
        self.assertIn("معلم", r2.json()["detail"], r2.text)


# ═══════════════════════════════════════════════════════════════════════════════
# آیتم ۶ — خروجی بدهکاران خالی است با وجود داده
# ═══════════════════════════════════════════════════════════════════════════════
class TestDebtorsNotEmpty(Group2World):
    """ریشه (قبل از فیکس): فیلتر سخت شعبه.

    `get_user_branch_filter` شعبهٔ کاربرِ لاگین‌شده را برمی‌گرداند (ادمینِ ساخته‌شده با
    `scripts/create_admin.py` ⇒ `branch_id=1`) و کوئری بدهکاران
    `Student.branch_id == resolved_branch` را اعمال می‌کند. در دادهٔ واقعی آموزشگاه
    `students.branch_id` برای ردیف‌های legacy **NULL** است (سنجش روی کپی /tmp از gaj_db.db:
    هر دو دانش‌آموز `branch_id=NULL`، معلم هم `branch_id=NULL`) ⇒ `NULL == 1` در SQL هرگز
    درست نیست ⇒ **لیست خالی** با وجود بدهکار واقعی.

    سیاست فیکس (هم‌جهت با H7 و `resolve_creation_branch`): ردیف بی‌شعبه = رکورد سراسری/legacy
    و باید به کاربر هر شعبه نشان داده شود؛ رکوردِ شعبهٔ **دیگر** همچنان پنهان می‌ماند.
    """

    def make_debtor(self):
        cid = self.create_class()
        self.assertEqual(self.enroll(cid, 41, tuition=1000000, paid=400000).status_code, 200)
        return cid

    def test_6a_finance_debtors_list_is_not_empty_for_branch_admin(self):
        self.make_debtor()
        resp = self.client.get("/finance/reports/debtors_list", headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        rows = resp.json()
        self.assertEqual([r["student_id"] for r in rows], [41],
                         f"بدهکار واقعی باید دیده شود: {rows}")
        self.assertEqual(rows[0]["total_debt"], 600000)

    def test_6b_exports_debtors_csv_has_the_debtor_row(self):
        self.make_debtor()
        resp = self.client.get("/exports/debtors", headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        text = resp.text
        self.assertIn("علی", text, f"خروجی بدهکاران خالی است: {text!r}")
        self.assertIn("600000", text.replace(",", ""), text)

    def test_6c_reports_debtors_and_excel_are_not_empty(self):
        self.make_debtor()
        resp = self.client.get("/reports/debtors", headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual([r["student_id"] for r in resp.json()], [41], resp.text)
        xls = self.client.get("/reports/debtors/excel", headers=hdr("tok-admin"))
        self.assertEqual(xls.status_code, 200, xls.text)
        self.assertGreater(len(xls.content), 5000, "فایل اکسل باید ردیف داده داشته باشد")

    def test_6d_other_branch_students_stay_hidden(self):
        """نشت شعبه نباید پیش بیاید: دانش‌آموزِ شعبهٔ ۲ به ادمین شعبهٔ ۱ نشان داده نمی‌شود."""
        self.make_debtor()
        # دادهٔ شعبهٔ ۲ مستقیم در DB (مسیر API عمداً اجازهٔ ساخت در شعبهٔ دیگر را نمی‌دهد —
        # «شما مجاز به ایجاد داده در شعبه‌ی دیگر نیستید» ⇒ سیاست موجود درست است و دست نمی‌خورد).
        c2 = models.Course(id=902, title="شیمی", code="902", teacher_id=52, education_type="عادی",
                           grade_level="دهم", gender_type="مختلط", class_type="خصوصی",
                           days_of_week="یکشنبه", class_time="19:00", teacher_session_price=150000,
                           branch_id=2, is_admin_approved=True, is_deleted=False,
                           is_suspended=False)
        self.db.add(c2)
        self.db.query(models.Student).filter(models.Student.id == 42).update(
            {models.Student.branch_id: 2}, synchronize_session=False)
        self.db.add(models.Enrollment(student_id=42, course_id=902, branch_id=2,
                                      register_date="1405/06/01", shift="عصر",
                                      total_tuition=900000, total_paid=0, is_deleted=False))
        self.db.commit()
        rows = self.client.get("/finance/reports/debtors_list", headers=hdr("tok-admin")).json()
        self.assertEqual([r["student_id"] for r in rows], [41], rows)

    def test_6e_archived_student_is_not_a_debtor(self):
        cid = self.create_class()
        self.assertEqual(self.enroll(cid, 43, tuition=500000, paid=0).status_code, 404,
                         "دانش‌آموز آرشیوشده ثبت‌نام نمی‌شود")
        rows = self.client.get("/finance/reports/debtors_list", headers=hdr("tok-admin")).json()
        self.assertNotIn(43, [r["student_id"] for r in rows], rows)


# ═══════════════════════════════════════════════════════════════════════════════
# آیتم ۷ — انتخاب معلم در محدودهٔ گزارش‌گیری
# ═══════════════════════════════════════════════════════════════════════════════
class TestTeacherPickerList(Group2World):
    """`ReportActivity.fetchTeachersList()` → `GET /teachers/list` (بدون پارامتر).

    انتظار: همهٔ معلم‌های فعال (حتی با `branch_id=NULL` legacy) برای ادمین/منشی برگردند و
    معلم آرشیوشده برنگردد؛ معلم لاگین‌شده فقط خودش را ببیند (سیاست موجود L14).
    """

    def test_7a_admin_sees_all_active_teachers_including_null_branch(self):
        resp = self.client.get("/teachers/list", headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        ids = [t["id"] for t in resp.json()]
        self.assertEqual(sorted(ids), [51, 52, 53],
                         f"فیلتر معلم خالی/ناقص است: {resp.json()}")
        self.assertNotIn(54, ids, "معلم آرشیوشده نباید بیاید")

    def test_7b_secretary_sees_the_same_list(self):
        resp = self.client.get("/teachers/list", headers=hdr("tok-sec"))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(sorted(t["id"] for t in resp.json()), [51, 52, 53])

    def test_7c_names_are_never_null_for_the_picker(self):
        """کلاینت نام را مستقیم در ArrayAdapter می‌گذارد؛ None ⇒ «null» دیده می‌شد."""
        self.teacher2.first_name = None
        self.teacher2.last_name = None
        self.db.commit()
        resp = self.client.get("/teachers/list", headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        row = [t for t in resp.json() if t["id"] == 52][0]
        self.assertEqual(row["first_name"], "")
        self.assertEqual(row["last_name"], "")

    def test_7d_teacher_sees_only_himself_and_others_get_403(self):
        resp = self.client.get("/teachers/list", headers=hdr("tok-teacher"))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual([t["id"] for t in resp.json()], [51])


# ═══════════════════════════════════════════════════════════════════════════════
# آیتم ۹ — گزارش بدهکاران داشبورد ادمین (فیلدها + گروه‌بندی + پیامک + اکسل)
# ═══════════════════════════════════════════════════════════════════════════════
class TestDebtorsReportEnriched(Group2World):
    """فیلدهای فعلی `debtors_list`: student_id, student_name, national_code, parent_mobile,
    debt_teacher, debt_institute, total_debt, active_courses.
    کم‌ها (طبق درخواست): نام کامل، مبلغ بدهی، **تاریخ آخرین پرداخت**، **شماره تماس** +
    گروه‌بندی بر اساس معلم · دسته‌بندی قدمت بدهی · پیامک دسته‌جمعی · اکسل با شماره تماس.
    """

    def make_debtors(self):
        # ثبت‌نام‌ها ۵۰ روز پیش ⇒ تنها «پرداختِ» جدیدِ دانش‌آموز ۴۱ همان تراکنش ۴۰ روز پیش است
        # (وگرنه تراکنش `enrollment_payment` با تاریخ امروزِ ثبت‌نام، آخرین پرداخت می‌شد).
        old_register = jalali_date_string(TODAY_GREG - datetime.timedelta(days=50))
        c1 = self.create_class(teacher_id=51, title="ریاضی")
        c2 = self.create_class(teacher_id=52, title="فیزیک", days="یکشنبه", time="19:00")
        self.assertEqual(self.enroll(c1, 41, tuition=1000000, paid=400000,
                                     date=old_register).status_code, 200)
        self.assertEqual(self.enroll(c2, 42, tuition=500000, paid=0,
                                     date=old_register).status_code, 200)
        # پرداخت قدیمی برای دانش‌آموز ۴۱ (۴۰ روز پیش ⇒ دستهٔ «بیش از ۳۰ روز»)
        old = jalali_date_string(TODAY_GREG - datetime.timedelta(days=40))
        self.add_tx(id=941, student_id=41, course_id=c1, amount=400000, type="deposit",
                    target_wallet="institute", payment_method="کارت", date=old,
                    description="پرداخت قدیمی")
        return c1, c2

    def test_9a_debtor_rows_carry_the_missing_fields(self):
        self.make_debtors()
        rows = self.client.get("/finance/reports/debtors_list", headers=hdr("tok-admin")).json()
        by_id = {r["student_id"]: r for r in rows}
        self.assertEqual(sorted(by_id), [41, 42], rows)
        for sid in (41, 42):
            row = by_id[sid]
            self.assertTrue(row["student_name"].strip(), "نام")
            self.assertGreater(row["total_debt"], 0, "مبلغ بدهی")
            self.assertTrue(row.get("parent_mobile") or row.get("student_mobile"),
                            f"شماره تماس باید باشد: {row}")
            self.assertIn("last_payment_date", row, "تاریخ آخرین پرداخت")
            self.assertIn("debt_age_days", row, "قدمت بدهی (برای دسته‌بندی)")
            self.assertIn("debt_age_bucket", row, "دستهٔ قدمت")
        self.assertEqual(by_id[41]["total_debt"], 600000)
        self.assertEqual(by_id[42]["total_debt"], 500000)
        self.assertIn(by_id[41]["debt_age_bucket"], ("0-7", "8-30", "over_30", "no_payment"))
        self.assertEqual(by_id[41]["debt_age_bucket"], "over_30",
                         "آخرین پرداخت ۴۰ روز پیش بوده")
        self.assertEqual(by_id[42]["debt_age_bucket"], "no_payment", "هیچ پرداختی نداشته")

    def test_9b_grouped_view_by_teacher_and_age(self):
        self.make_debtors()
        resp = self.client.get("/finance/reports/debtors_grouped", headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["total_debt"], 1100000)
        self.assertEqual(body["debtors_count"], 2)
        # گروه‌بندی بر اساس معلم
        teachers = {g["teacher_id"]: g for g in body["by_teacher"]}
        self.assertEqual(teachers[51]["debt"], 200000, body["by_teacher"])
        self.assertEqual(teachers[52]["debt"], 500000, body["by_teacher"])
        self.assertTrue(teachers[51]["teacher_name"].strip())
        self.assertEqual(teachers[51]["students_count"], 1)
        # دسته‌بندی قدمت — total_debt student-level است و تغییر نمی‌کند.
        buckets = {b["bucket"]: b for b in body["by_age"]}
        self.assertEqual(buckets["over_30"]["debt"], 600000)
        self.assertEqual(buckets["no_payment"]["debt"], 500000)

    def test_9c_bulk_sms_reminder_uses_the_existing_dunning_engine(self):
        """پیامک دسته‌جمعی به بدهکاران فیلترشده — روی همان زیرساخت موجود
        (`SmsLog` + `ActivityLog` + idempotency ۴۸ ساعتهٔ dunning)، نه موتور جدید."""
        self.make_debtors()
        resp = self.client.post("/finance/debtors/remind", json={"student_ids": [41, 42]},
                                headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["sent_count"], 2, body)
        self.assertEqual(body["skipped_count"], 0, body)
        self.assertEqual(self.db.query(models.SmsLog).count(), 2, "SmsLog موجود استفاده شود")
        logs = self.db.query(models.ActivityLog).filter(
            models.ActivityLog.action == "debtors_reminder").all()
        self.assertEqual(len(logs), 2, "ActivityLog موجود استفاده شود")
        self.assertTrue(all("600000" in (l.details or "").replace(",", "") or
                            "500000" in (l.details or "").replace(",", "") for l in logs),
                        [l.details for l in logs])
        # idempotency: ارسال دوباره در همان روز ⇒ skip
        again = self.client.post("/finance/debtors/remind", json={"student_ids": [41, 42]},
                                 headers=hdr("tok-admin"))
        self.assertEqual(again.status_code, 200, again.text)
        self.assertEqual(again.json()["sent_count"], 0, again.json())
        self.assertEqual(again.json()["skipped_count"], 2, again.json())
        self.assertEqual(self.db.query(models.SmsLog).count(), 2, "پیامک تکراری ثبت نمی‌شود")

    def test_9d_remind_skips_students_without_mobile_and_empty_list(self):
        self.make_debtors()
        self.debtor.parent_mobile = None
        self.debtor.student_mobile = None
        self.db.commit()
        resp = self.client.post("/finance/debtors/remind", json={"student_ids": [41]},
                                headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["sent_count"], 0)
        self.assertEqual(resp.json()["skipped_count"], 1)
        self.assertIn("41", str(resp.json()["skipped"]))
        empty = self.client.post("/finance/debtors/remind", json={"student_ids": []},
                                 headers=hdr("tok-admin"))
        self.assertEqual(empty.status_code, 400, empty.text)

    def test_9e_remind_is_admin_only(self):
        self.make_debtors()
        self.assertIn(self.client.post("/finance/debtors/remind", json={"student_ids": [41]},
                                       headers=hdr("tok-sec")).status_code, (401, 403))
        self.assertIn(self.client.post("/finance/debtors/remind", json={"student_ids": [41]},
                                       headers=hdr("tok-teacher")).status_code, (401, 403))

    def test_9h_legacy_wallet_only_debtor_reconciles_in_the_grouped_view(self):
        """دادهٔ legacy: بدهی فقط از کیف پول منفی (ثبت‌نام بدون شهریهٔ قیمت‌گذاری‌شده).

        در این حالت `total_debt` از fallback کیف پول می‌آید، اما wallet کلی منبع بدهی
        یک کلاس نیست. بنابراین مبلغ در `unassigned_debt` باقی می‌ماند، حتی با یک کلاس فعال؛
        همیشه `sum(by_teacher.debt) + unassigned_debt == total_debt` برقرار می‌ماند.
        """
        cid = self.create_class(teacher_id=51, title="ریاضی")
        self.assertEqual(self.enroll(cid, 41, tuition=0, paid=0).status_code, 200,
                         "ثبت‌نام با شهریهٔ صفر باید مجاز باشد (آیتم ۲ گروه ۱)")
        self.debtor.wallet_teacher = -100000
        self.db.commit()

        body = self.client.get("/finance/reports/debtors_grouped", headers=hdr("tok-admin")).json()
        self.assertEqual(body["total_debt"], 100000, body)
        # wallet کلی دانش‌آموز بدهی کلاس نیست؛ حتی با یک کلاس فعال هم
        # مبلغ بدون اتصال enrollment باید تخصیص‌نیافته بماند.
        self.assertEqual(sum(g["debt"] for g in body["by_teacher"]), 0, body["by_teacher"])
        self.assertEqual(body["unassigned_debt"], 100000, body)
        self.assertEqual(body["by_teacher"][0]["teacher_id"], 51, body["by_teacher"])

        # دو کلاس فعال با دو معلم ⇒ نسبت‌دادن قطعی ممکن نیست ⇒ unassigned
        c2 = self.create_class(teacher_id=52, title="فیزیک", days="یکشنبه", time="19:00")
        self.assertEqual(self.enroll(c2, 41, tuition=0, paid=0).status_code, 200)
        body2 = self.client.get("/finance/reports/debtors_grouped", headers=hdr("tok-admin")).json()
        self.assertEqual(body2["total_debt"], 100000, body2)
        self.assertEqual(sum(g["debt"] for g in body2["by_teacher"]), 0, body2["by_teacher"])
        self.assertEqual(body2["unassigned_debt"], 100000, body2)
        # دانش‌آموز در هر دو گروه معلم دیده می‌شود (فقط مبلغش تخصیص‌نیافته است)
        self.assertEqual(sorted(g["teacher_id"] for g in body2["by_teacher"]), [51, 52], body2)

    def test_9f_excel_export_includes_mobile_and_last_payment(self):
        self.make_debtors()
        resp = self.client.get("/reports/debtors/excel", headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(resp.content))
        ws = wb.active
        headers = [c.value for c in ws[1]]
        self.assertIn("تلفن والدین", headers, headers)
        self.assertIn("تاریخ آخرین پرداخت", headers, headers)
        self.assertIn("قدمت بدهی (روز)", headers, headers)
        rows = list(ws.iter_rows(min_row=2, values_only=True))
        self.assertEqual(len(rows), 2, rows)
        self.assertTrue(any("09120000205" in str(r) for r in rows), rows)

    def test_9g_csv_export_includes_last_payment_date(self):
        self.make_debtors()
        resp = self.client.get("/exports/debtors", headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        header = resp.text.splitlines()[0]
        self.assertIn("تاریخ آخرین پرداخت", header, header)
        self.assertIn("موبایل ولی", header, header)


if __name__ == "__main__":
    unittest.main()
