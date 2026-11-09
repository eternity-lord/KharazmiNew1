# test_group1_blockers.py
# ═══════════════════════════════════════════════════════════════════════════════
# گروه ۱ — سه باگ بلاکر گزارش‌شدهٔ صاحب پروژه (تست دستی کامل شده)
#
#   ۱) خطای ۴۰۹ هنگام «پایان کلاس زنده»
#   ۲) شهریهٔ پایه = ۰ در «افزودن دانش‌آموز» رد می‌شود (باید مجاز باشد: رایگان/معاف)
#   ۳) کلاسِ رد‌شده همچنان در «کلاس‌های منتظر تأیید» می‌ماند
#
# مسیرهای درگیر (سرور):
#   routers/attendance.py:212 start_live · :266 end_live · :100 finalize_live_session
#   routers/attendance.py:441 submit_session_and_calculate (گارد ۴۰۹ تکراری: :477)
#   schemas.py:102 EnrollmentCreate.total_tuition = Field(gt=0)
#   routers/classes.py:376 POST /enrollments/add
#   routers/admin.py:335 DELETE /admin/reject_class/{id} · :601 GET /admin/pending_classes
#   routers/teachers.py:303 GET /teachers/{id}/incomplete_classes
#
# مرجع سمت اندروید (بدون کامپایل — فقط خواندن):
#   LiveClassActivity.kt:220 endLive · TeacherDashboardActivity.kt:338 startLive
#   ClassSetupActivity.kt (افزودن دانش‌آموز) · PendingClassesActivity.kt (صف تأیید)
#
# اجرا (طبق قانون پروژه: DB موقت، هرگز gaj_db.db واقعی):
#   DATABASE_URL=sqlite:////tmp/g1.db JWT_SECRET_KEY=test \
#     python3 -m pytest Kharazmi_Server/tests/test_group1_blockers.py -q
# ═══════════════════════════════════════════════════════════════════════════════
import datetime
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from dependencies import get_db, hash_password, limiter
from main import app
from today_summary import jalali_date_string, parse_project_date

TODAY = jalali_date_string(parse_project_date(datetime.date.today().strftime("%Y/%m/%d")))


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


class Group1World(unittest.TestCase):
    """دنیای مشترک: شعبه ۱ · ادمین · منشی · معلم مالک کلاس · یک دانش‌آموز · تعرفهٔ سهم."""

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
        self.db.add(models.User(id=101, username="09120000101", password=hash_password("a-pass"),
                                full_name="مدیر کل", role="admin", sub_role="admin", branch_id=1))
        self.db.add(models.User(id=102, username="09120000102", password=hash_password("s-pass"),
                                full_name="منشی", role="secretary", sub_role="secretary", branch_id=1))
        self.teacher = models.Teacher(id=51, first_name="مریم", last_name="احمدی",
                                      mobile="09120000103", national_code="0012345901",
                                      password=hash_password("t-pass"), is_approved=True,
                                      is_deleted=False, is_suspended=False, branch_id=1)
        self.db.add(self.teacher)
        self.db.add(models.User(id=103, username="09120000103", password=hash_password("t-pass"),
                                full_name="مریم احمدی", role="admin", sub_role="teacher", branch_id=1))
        self.student = models.Student(id=41, student_code=41, first_name="علی", last_name="رضایی",
                                      national_code="0012345902", student_mobile="09120000104",
                                      branch_id=1, wallet_teacher=0, wallet_institute=0,
                                      wallet_balance=0, is_deleted=False, is_suspended=False)
        self.student2 = models.Student(id=42, student_code=42, first_name="سارا", last_name="کریمی",
                                       national_code="0012345903", student_mobile="09120000105",
                                       branch_id=1, wallet_teacher=0, wallet_institute=0,
                                       wallet_balance=0, is_deleted=False, is_suspended=False)
        self.db.add_all([self.student, self.student2])
        # تعرفهٔ سهم آموزشگاه — بدون این ردیف ثبت جلسه ۵۰۰ می‌دهد (الگوی e2e سناریو ۲)
        self.db.add(models.InstituteShare(id=1, count_1=50000, count_2=80000, count_3=100000))
        self.db.add(models.UserSession(token="tok-admin", user_id=101, sub_role="admin", created_at=now))
        self.db.add(models.UserSession(token="tok-sec", user_id=102, sub_role="secretary", created_at=now))
        self.db.add(models.UserSession(token="tok-teacher", user_id=103, teacher_id=51,
                                       sub_role="teacher", created_at=now))
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
    def create_class(self, title="ریاضی دهم", days="شنبه", time="17:30", price=150000,
                     token="tok-admin", approve=True):
        resp = self.client.post("/classes/create", json={
            "title": title, "code": "0", "teacher_id": self.teacher.id,
            "education_type": "عادی", "grade_level": "دهم", "gender_type": "مختلط",
            "class_type": "خصوصی", "days_of_week": days, "class_time": time,
            "teacher_session_price": price, "branch_id": 1,
        }, headers=hdr(token))
        self.assertEqual(resp.status_code, 200, resp.text)
        course_id = resp.json()["id"]
        if approve:
            ap = self.client.post(f"/admin/approve_class/{course_id}", headers=hdr(token))
            self.assertEqual(ap.status_code, 200, ap.text)
        return course_id

    def enroll(self, course_id, student_id=41, tuition=1000000, paid=0, token="tok-admin"):
        return self.client.post("/enrollments/add", json={
            "student_id": student_id, "course_id": course_id, "register_date": "1405/06/01",
            "shift": "عصر", "total_tuition": tuition, "paid_amount": paid,
            "payment_method": "کارت", "receiver": "مدیر",
        }, headers=hdr(token))

    def submit_session(self, course_id, statuses, date=TODAY, token="tok-admin"):
        items = [{"student_id": sid, "status": st, "excused": False} for sid, st in statuses]
        return self.client.post("/attendance/submit_session",
                                json={"course_id": course_id, "date": date, "items": items},
                                headers=hdr(token))

    def start_live(self, course_id, token="tok-teacher"):
        return self.client.post(f"/attendance/{course_id}/start_live", headers=hdr(token))

    def save_live_status(self, live_id, items, token="tok-teacher"):
        return self.client.post(f"/attendance/{live_id}/live_status", json={"items": items},
                                headers=hdr(token))

    def end_live(self, live_id, token="tok-teacher"):
        return self.client.post(f"/attendance/{live_id}/end_live", json={}, headers=hdr(token))

    def live_row(self, live_id):
        row = self.db.query(models.LiveSession).filter(models.LiveSession.id == live_id).first()
        self.db.refresh(row)
        return row

    def sessions_of(self, course_id):
        return self.db.query(models.SessionLog).filter(
            models.SessionLog.course_id == course_id, models.SessionLog.is_deleted == False).all()


# ═══════════════════════════════════════════════════════════════════════════════
# آیتم ۱ — ۴۰۹ روی پایان کلاس زنده
# ═══════════════════════════════════════════════════════════════════════════════
class TestLiveEnd409(Group1World):
    """سناریوی واقعی: شروع کلاس → پایان کلاس.

    ریشه (قبل از فیکس): `end_live` → `finalize_live_session` → `submit_session_and_calculate`
    و گارد «جلسهٔ این کلاس در این تاریخ قبلاً ثبت شده است» (attendance.py:477) ⇒ ۴۰۹.
    این ۴۰۹ **قفل optimistic-lock پروفایل نیست** (آن یکی در teachers.py:478/students.py:805 است
    و فقط PUT پروفایل را می‌گیرد)؛ همان گارد یکتایی (course, date) جلسه است.
    """

    def setUp(self):
        super().setUp()
        self.course_id = self.create_class()
        self.assertEqual(self.enroll(self.course_id, 41, paid=400000).status_code, 200)

    def test_1a_normal_live_start_and_end_registers_and_charges(self):
        """مسیر سالم باید بدون تغییر بماند (رگرسیون‌گیری)."""
        st = self.start_live(self.course_id)
        self.assertEqual(st.status_code, 200, st.text)
        live_id = st.json()["live_session_id"]
        self.assertEqual(self.save_live_status(live_id, {"41": {"status": "Present", "excused": False}}).status_code, 200)
        end = self.end_live(live_id)
        self.assertEqual(end.status_code, 200, end.text)
        self.assertEqual(len(self.sessions_of(self.course_id)), 1, "یک جلسه ثبت می‌شود")
        self.assertEqual(self.live_row(live_id).status, "ENDED")
        self.db.refresh(self.student)
        self.assertLess(self.student.wallet_teacher, 0, "حاضر ⇒ شارژ کیف معلم")

    def test_1b_second_live_same_day_is_closed_not_409(self):
        """باگ گزارش‌شده: جلسهٔ امروز قبلاً ثبت شده ⇒ پایان کلاس زنده ۴۰۹ می‌دهد و جلسه LIVE می‌ماند."""
        # ۱) ثبت جلسهٔ امروز از مسیر دستی (AttendanceActivity)
        first = self.submit_session(self.course_id, [(41, "Present")], date=TODAY)
        self.assertEqual(first.status_code, 200, first.text)
        existing_code = first.json()["session_code"]

        # ۲) کلاس زندهٔ دوم در همان روز (auto-start از داشبورد/باز شدن صفحه)
        st = self.start_live(self.course_id)
        self.assertEqual(st.status_code, 200, st.text)
        live_id = st.json()["live_session_id"]
        self.save_live_status(live_id, {"41": {"status": "Present", "excused": False}})

        # ۳) پایان کلاس ⇒ رفتار مطلوب: بسته شدن جلسهٔ زنده + اشاره به جلسهٔ موجود، نه ۴۰۹
        end = self.end_live(live_id)
        self.assertNotEqual(end.status_code, 409,
                            f"پایان کلاس زنده نباید ۴۰۹ بدهد: {end.text}")
        self.assertEqual(end.status_code, 200, end.text)
        body = end.json()
        self.assertTrue(body.get("duplicate_date"), "پاسخ باید صریح بگوید جلسهٔ این تاریخ قبلاً ثبت شده")
        self.assertEqual(body.get("existing_session_code"), existing_code)
        self.assertIn("قبلاً ثبت شده", body.get("message", ""))

        # ۴) جلسهٔ زنده باید بسته شود (نه LIVE بماند، نه در FINALIZING قفل شود)
        self.assertEqual(self.live_row(live_id).status, "ENDED")
        # ۵) هیچ SessionLog دوم و هیچ شارژ مالی دومی ساخته نمی‌شود
        self.assertEqual(len(self.sessions_of(self.course_id)), 1)
        self.assertEqual(self.db.query(models.Transaction).filter(
            models.Transaction.type == "session_charge").count(), 1)

    def test_1c_repeated_end_after_duplicate_is_idempotent(self):
        """پایانِ دوباره روی جلسهٔ بسته‌شده باید همان پیام «قبلاً بسته شده» را بدهد (۴۰۰)."""
        self.submit_session(self.course_id, [(41, "Present")], date=TODAY)
        live_id = self.start_live(self.course_id).json()["live_session_id"]
        first_end = self.end_live(live_id)
        self.assertEqual(first_end.status_code, 200, first_end.text)
        again = self.end_live(live_id)
        self.assertEqual(again.status_code, 400, again.text)
        self.assertIn("از قبل بسته شده", again.json()["detail"])
        self.assertEqual(self.live_row(live_id).status, "ENDED")


class TestLiveCancelAndIdentifierCompatibility(Group1World):
    """لغو live باید فقط وضعیت LiveSession را عوض کند؛ شناسه‌ی legacy هم امن resolve شود."""

    def setUp(self):
        super().setUp()
        self.course_id = self.create_class(title="کلاس زندهٔ لغوشدنی")
        self.assertEqual(self.enroll(self.course_id, 41, paid=0).status_code, 200)
        # عمداً id جلسهٔ زنده را از course_id جدا می‌کنیم تا fallback واقعاً تست شود.
        self.db.add(models.LiveSession(
            id=700, course_id=self.course_id, teacher_id=self.teacher.id,
            status="ENDED", ended_automatically=False, live_roster="{}",
        ))
        self.db.commit()

    def test_cancel_by_live_id_has_no_attendance_or_financial_effect_and_is_idempotent(self):
        started = self.start_live(self.course_id)
        self.assertEqual(started.status_code, 200, started.text)
        live_id = started.json()["live_session_id"]
        self.assertNotEqual(live_id, self.course_id)
        self.assertEqual(self.save_live_status(live_id, {"41": {"status": "Present"}}).status_code, 200)
        before = (self.student.wallet_teacher, self.student.wallet_institute, self.student.wallet_balance)

        cancelled = self.client.post(f"/attendance/{live_id}/cancel_live", headers=hdr("tok-teacher"))
        self.assertEqual(cancelled.status_code, 200, cancelled.text)
        self.assertEqual(cancelled.json()["status"], "CANCELLED")
        row = self.live_row(live_id)
        self.assertEqual(row.status, "CANCELLED")
        self.assertEqual(self.db.query(models.SessionLog).count(), 0)
        self.assertEqual(self.db.query(models.Attendance).count(), 0)
        self.assertEqual(self.db.query(models.Transaction).count(), 0)
        self.db.refresh(self.student)
        self.assertEqual(before, (self.student.wallet_teacher, self.student.wallet_institute, self.student.wallet_balance))

        again = self.client.post(f"/attendance/{live_id}/cancel_live", headers=hdr("tok-teacher"))
        self.assertEqual(again.status_code, 200, again.text)
        self.assertEqual(again.json()["status"], "CANCELLED")

    def test_legacy_course_id_path_resolves_same_live_session_for_end_and_finance(self):
        started = self.start_live(self.course_id)
        self.assertEqual(started.status_code, 200, started.text)
        live_id = started.json()["live_session_id"]
        self.assertEqual(self.save_live_status(self.course_id, {"41": {"status": "Present"}}).status_code, 200)

        ended = self.end_live(self.course_id)
        self.assertEqual(ended.status_code, 200, ended.text)
        self.assertEqual(ended.json()["live_session_id"], live_id)
        self.assertEqual(self.live_row(live_id).status, "ENDED")
        self.assertEqual(len(self.sessions_of(self.course_id)), 1)
        self.db.refresh(self.student)
        self.assertLess(self.student.wallet_teacher, 0)


# ═══════════════════════════════════════════════════════════════════════════════
# آیتم ۲ — شهریهٔ پایه = ۰ (دانش‌آموز رایگان/معاف)
# ═══════════════════════════════════════════════════════════════════════════════
class TestZeroTuitionEnrollment(Group1World):
    """ریشه (قبل از فیکس): `EnrollmentCreate.total_tuition = Field(gt=0)` در schemas.py:102 ⇒
    ۴۲۲ با بدنهٔ عمومی pydantic. شاهد ناسازگاری داخلی: مسیر `register_and_enroll`
    (schemas.py:401) همین مقدار را `Optional[int] = 0` می‌پذیرد ⇒ دو مسیر رفتار متفاوت دارند."""

    def setUp(self):
        super().setUp()
        self.course_id = self.create_class()

    def test_2a_zero_tuition_is_allowed(self):
        resp = self.enroll(self.course_id, 41, tuition=0, paid=0)
        self.assertEqual(resp.status_code, 200, f"شهریهٔ صفر (رایگان/معاف) باید مجاز باشد: {resp.text}")
        row = self.db.query(models.Enrollment).filter(
            models.Enrollment.student_id == 41, models.Enrollment.course_id == self.course_id,
            models.Enrollment.is_deleted == False).first()
        self.assertIsNotNone(row, "ثبت‌نام باید ذخیره شود")
        self.assertEqual(row.total_tuition, 0)
        self.assertEqual(row.total_paid, 0)
        # بدون پرداخت اولیه ⇒ هیچ تراکنشی ساخته نمی‌شود و کیف‌ها دست‌نخورده
        self.assertEqual(self.db.query(models.Transaction).filter(
            models.Transaction.student_id == 41).count(), 0)
        self.db.refresh(self.student)
        self.assertEqual(self.student.wallet_institute, 0)
        self.assertEqual(self.student.wallet_balance, 0)

    def test_2a_register_and_enroll_route_allows_zero_tuition(self):
        """رگرسیون مسیر ثبت دانش‌آموز از پنل معلم/ادمین؛ این مسیر قبلاً صفر را با 400 رد می‌کرد."""
        response = self.client.post("/students/register_and_enroll", json={
            "first_name": "رایگان", "last_name": "آزمایشی", "father_name": "پدر",
            "national_code": "1000000001", "birth_date": "1390/01/01",
            "student_mobile": "09121112223", "parent_mobile": "09123334445",
            "home_phone": "02100000000", "address": "تهران", "study_status": "فعال",
            "gender": "male", "course_id": self.course_id, "total_tuition": 0,
            "paid_amount": 0, "payment_method": "-", "receiver": "-",
            "discount_type": "none", "discount_value": 0,
        }, headers=hdr("tok-admin"))
        self.assertEqual(response.status_code, 200, response.text)
        row = self.db.query(models.Enrollment).filter(
            models.Enrollment.course_id == self.course_id,
            models.Enrollment.total_tuition == 0,
            models.Enrollment.is_deleted == False,
        ).first()
        self.assertIsNotNone(row)

    def test_2b_zero_tuition_with_zero_installment_and_discount_still_coherent(self):
        """تخفیف ثابت روی شهریهٔ صفر باید مثل قبل رد شود (پیام واضح، نه خطای عمومی)."""
        resp = self.client.post("/enrollments/add", json={
            "student_id": 41, "course_id": self.course_id, "register_date": "1405/06/01",
            "shift": "عصر", "total_tuition": 0, "paid_amount": 0, "payment_method": "کارت",
            "receiver": "مدیر", "discount_type": "fixed", "discount_value": 1000,
        }, headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertIn("تخفیف", resp.json()["detail"])

    def test_2c_negative_tuition_is_rejected_with_clear_message(self):
        """منفی همچنان نامعتبر است، ولی با پیام فارسی واضح — نه بدنهٔ عمومی pydantic."""
        resp = self.enroll(self.course_id, 41, tuition=-5000, paid=0)
        self.assertEqual(resp.status_code, 422, resp.text)
        text = resp.text
        self.assertIn("شهریه", text, f"پیام باید دلیل را به زبان کاربر بگوید: {text}")
        self.assertNotIn("greater than 0", text, "پیام خام انگلیسی pydantic نباید به کاربر برسد")

    def test_2d_teacher_can_enroll_free_student_in_own_class(self):
        """مسیر O-22 (معلم) هم با شهریهٔ صفر کار کند."""
        resp = self.enroll(self.course_id, 42, tuition=0, paid=0, token="tok-teacher")
        self.assertEqual(resp.status_code, 200, resp.text)


# ═══════════════════════════════════════════════════════════════════════════════
# آیتم ۳ — کلاس رد‌شده در صف «منتظر تأیید» می‌ماند
# ═══════════════════════════════════════════════════════════════════════════════
class TestRejectedClassLeavesPendingQueue(Group1World):
    """ریشه (قبل از فیکس): `reject_class` کلاس را آرشیو می‌کند (`is_deleted=True` در
    classes.py:988) ولی `GET /admin/pending_classes` (admin.py:614) فقط
    `is_admin_approved == False` را فیلتر می‌کند و `is_deleted` را نمی‌بیند ⇒ ردیف آرشیوشده
    در صف تأیید ادمین باقی می‌ماند. نمای معلم (`incomplete_classes`) این فیلتر را دارد."""

    def setUp(self):
        super().setUp()
        self.pending_id = self.create_class(title="کلاس در انتظار", approve=False)
        self.rejected_id = self.create_class(title="کلاس رد‌شده", days="یکشنبه",
                                             time="19:00", approve=False)

    def pending_ids(self, token="tok-admin"):
        resp = self.client.get("/admin/pending_classes", headers=hdr(token))
        self.assertEqual(resp.status_code, 200, resp.text)
        return [row["id"] for row in resp.json()]

    def test_3a_rejected_class_disappears_from_admin_pending_list(self):
        self.assertIn(self.rejected_id, self.pending_ids(), "پیش‌شرط: هر دو کلاس در صف‌اند")
        rej = self.client.delete(f"/admin/reject_class/{self.rejected_id}", headers=hdr("tok-admin"))
        self.assertEqual(rej.status_code, 200, rej.text)
        row = self.db.query(models.Course).filter(models.Course.id == self.rejected_id).first()
        self.db.refresh(row)
        self.assertTrue(bool(row.is_deleted), "رد کردن باید کلاس را آرشیو کند")

        left = self.pending_ids()
        self.assertNotIn(self.rejected_id, left, "کلاس رد‌شده نباید در صف تأیید ادمین بماند")
        self.assertIn(self.pending_id, left, "کلاس در انتظارِ دیگر باید سر جایش بماند")

    def test_3b_rejected_class_disappears_from_secretary_and_teacher_views(self):
        self.client.delete(f"/admin/reject_class/{self.rejected_id}", headers=hdr("tok-admin"))
        self.assertNotIn(self.rejected_id, self.pending_ids("tok-sec"), "نمای منشی")
        # صف تأیید از دید خودِ معلمِ مالک
        own = self.pending_ids("tok-teacher")
        self.assertNotIn(self.rejected_id, own, "نمای معلم")
        inc = self.client.get(f"/teachers/{self.teacher.id}/incomplete_classes", headers=hdr("tok-teacher"))
        self.assertEqual(inc.status_code, 200, inc.text)
        self.assertNotIn(self.rejected_id, [r["id"] for r in inc.json()], "لیست کلاس‌های ناقص معلم")

    def test_3c_rejected_class_cannot_be_approved_afterwards(self):
        """ردیف خارج‌شده از صف نباید با approve زنده شود (اگر شد، صریح گزارش می‌شود)."""
        self.client.delete(f"/admin/reject_class/{self.rejected_id}", headers=hdr("tok-admin"))
        ap = self.client.post(f"/admin/approve_class/{self.rejected_id}", headers=hdr("tok-admin"))
        self.assertIn(ap.status_code, (404, 410),
                      f"تأیید کلاس آرشیوشده باید رد شود، نه {ap.status_code}: {ap.text}")
        row = self.db.query(models.Course).filter(models.Course.id == self.rejected_id).first()
        self.db.refresh(row)
        self.assertTrue(bool(row.is_deleted), "کلاس باید آرشیوشده بماند")

    def test_3d_reject_is_idempotent(self):
        first = self.client.delete(f"/admin/reject_class/{self.rejected_id}", headers=hdr("tok-admin"))
        second = self.client.delete(f"/admin/reject_class/{self.rejected_id}", headers=hdr("tok-admin"))
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertNotIn(self.rejected_id, self.pending_ids())
        self.assertEqual(self.db.query(models.ClassDeletionRequest).filter(
            models.ClassDeletionRequest.course_id == self.rejected_id,
            models.ClassDeletionRequest.status == "approved").count(), 1,
            "رکورد حسابرسی تکراری ساخته نمی‌شود")


if __name__ == "__main__":
    unittest.main()
