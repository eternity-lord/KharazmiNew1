# اسکرین‌شات #۸: «آمار مالی ماهانه/سالانه» همیشه ۰. این تست‌ها (روی endpointهای واقعی):
#   ۱) اثبات می‌کنند اعداد total/collected/uncollected تغییر نکرده‌اند و در حالت عادی غیرصفرند؛
#   ۲) `diagnostics` جدید دلیل صفر بودن را می‌گوید: ماه بدون جلسه (+ آخرین جلسه)، و پیش‌پرداخت
#      ثبت‌نام که طبق تعریف قفل‌شدهٔ O-07/O-08 در «وصول‌شده» نمی‌آید ولی دیگر نامرئی نیست.
from test_e2e_class_enrollment_attendance_finance import ClassFlowWorld, hdr


class TestFinancialSummaryDiagnostics(ClassFlowWorld):
    def setUp(self):
        super().setUp()
        self.course = self.create_class(title="A").json()["id"]

    def summary(self, user_type="institute", year=1405, month=7):
        extra = f"&teacher_id={self.teacher.id}" if user_type == "teacher" else ""
        r = self.client.get(f"/reports/financial_summary?user_type={user_type}&year={year}&month={month}{extra}",
                            headers=hdr("tok-admin"))
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_1_numbers_unchanged_and_nonzero_when_a_session_is_in_the_month(self):
        self.assertEqual(self.enroll(self.course, tuition=660000, paid=0).status_code, 200)
        self.assertEqual(self.submit_session(self.course, [(41, "Present")], date="1405/07/07").status_code, 200)
        inst = self.summary("institute")
        self.assertEqual(inst["monthly"], {"total": 50000, "collected": 0, "uncollected": 50000})
        self.assertEqual(inst["yearly"]["total"], 50000)
        tea = self.summary("teacher")
        self.assertEqual(tea["monthly"]["total"], 150000)
        self.assertEqual(tea["yearly"]["total"], 150000)
        d = inst["diagnostics"]
        self.assertEqual((d["session_charges_total"], d["session_charges_in_period"], d["session_charges_undated"]), (1, 1, 0))
        self.assertEqual(d["last_session_charge_date"], "1405/07/07")
        self.assertEqual(tea["diagnostics"]["session_charges_in_period"], 1)

    def test_2_empty_month_explains_itself_with_last_session_date(self):
        self.assertEqual(self.enroll(self.course, tuition=660000, paid=0).status_code, 200)
        self.assertEqual(self.submit_session(self.course, [(41, "Present")], date="1405/06/20").status_code, 200)
        inst = self.summary("institute", month=7)
        self.assertEqual(inst["monthly"], {"total": 0, "collected": 0, "uncollected": 0})
        d = inst["diagnostics"]
        self.assertEqual((d["session_charges_total"], d["session_charges_in_period"]), (1, 0))
        self.assertEqual(d["last_session_charge_date"], "1405/06/20")
        # سال کامل همان جلسه را دارد
        self.assertEqual(inst["yearly"]["total"], 50000)

    def test_3_no_sessions_at_all(self):
        inst = self.summary("institute")
        d = inst["diagnostics"]
        self.assertEqual((d["session_charges_total"], d["session_charges_in_period"]), (0, 0))
        self.assertIsNone(d["last_session_charge_date"])

    def test_4_enrollment_prepayment_is_visible_but_not_added_to_collected(self):
        # پیش‌پرداخت با تاریخ ۱۴۰۵/۰۶/۰۱ (enroll() ثابت) ⇒ ماه ۶
        self.assertEqual(self.enroll(self.course, tuition=660000, paid=200000).status_code, 200)
        inst = self.summary("institute", month=6)
        self.assertEqual(inst["monthly"]["collected"], 0, "تعریف قفل‌شدهٔ O-07/O-08: فقط deposit")
        d = inst["diagnostics"]
        self.assertEqual((d["prepaid_count"], d["prepaid_amount"]), (1, 200000))
        tea = self.summary("teacher", month=6)
        self.assertEqual(tea["diagnostics"]["prepaid_amount"], 0, "پیش‌پرداخت ثبت‌نام مال کیف آموزشگاه است نه معلم")

    def test_5_teacher_without_classes_is_safe(self):
        import models
        other = models.Teacher(id=99, first_name="بی", last_name="کلاس", mobile="09120000099",
                               national_code="0012345999", is_approved=True, is_deleted=False, is_suspended=False, branch_id=1)
        self.db.add(other); self.db.commit()
        r = self.client.get("/reports/financial_summary?user_type=teacher&teacher_id=99&year=1405&month=7",
                            headers=hdr("tok-admin"))
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()["diagnostics"]
        self.assertEqual(d["session_charges_total"], 0)
