# سناریوی واقعی اسکرین‌شات #۸: دو کلاس جدا، یک معلم، یک دانش‌آموز.
# بدهی هر نما (لیست دانش‌آموزان، جزئیات، گزارش کلاس، بنر مدیریت کلاس و بنر پنل معلم) باید فقط مال
# «همان کلاس» باشد و جلسهٔ یک کلاس هرگز به کلاس دیگر نشت نکند؛ و اعداد یکسان فقط وقتی مجازند که هر
# دو کلاس واقعاً جلسهٔ شارژشدهٔ خودشان را داشته باشند (مثلاً حاضر در A و غایبِ جریمه‌شده در B).
# همهٔ مسیرها از طریق HTTP و endpointهای واقعی ساخته می‌شوند (نه درج مستقیم تراکنش).
from test_e2e_class_enrollment_attendance_finance import ClassFlowWorld, hdr


class TestTwoClassesSameTeacherAndStudent(ClassFlowWorld):
    def setUp(self):
        super().setUp()
        self.a = self.create_class(title="A", days="شنبه", time="17:30").json()["id"]
        self.b = self.create_class(title="B", days="یکشنبه", time="17:30").json()["id"]
        self.assertEqual(self.enroll(self.a, tuition=660000, paid=0).status_code, 200)
        self.assertEqual(self.enroll(self.b, tuition=660000, paid=0).status_code, 200)

    # ---- کمکی: همهٔ نماها برای یک کلاس ----
    def views(self, course_id):
        h = hdr("tok-admin")
        full = self.client.get(f"/classes/{course_id}/students_full", headers=h).json()["students"][0]
        det = self.client.get(f"/classes/{course_id}/details", headers=h).json()["students"][0]
        rep = self.client.get(f"/classes/{course_id}/full_report", headers=h)
        banner = next(r for r in self.client.get("/classes/list", headers=h).json() if r["id"] == course_id)
        teacher = next(r for r in self.client.get(f"/teachers/{self.teacher.id}/classes", headers=h).json()
                       if r["id"] == course_id)
        return {"full": full, "det": det, "rep": rep, "banner": banner, "teacher": teacher}

    def assert_all_views(self, course_id, debt_teacher, debt_institute):
        v = self.views(course_id)
        self.assertEqual((v["full"]["debt_teacher"], v["full"]["debt_institute"]), (debt_teacher, debt_institute))
        self.assertEqual((v["det"]["debt_teacher"], v["det"]["debt_institute"]), (debt_teacher, debt_institute))
        self.assertEqual((v["banner"]["debt_to_teacher"], v["banner"]["debt_to_institute"]), (debt_teacher, debt_institute))
        self.assertEqual((v["teacher"]["debt_to_teacher"], v["teacher"]["debt_to_institute"]), (debt_teacher, debt_institute))
        if v["rep"].status_code == 200:
            info = v["rep"].json()["info"]
            self.assertEqual((info["debt_to_teacher"], info["debt_to_institute"]), (debt_teacher, debt_institute))
        return v

    def test_1_session_in_a_never_leaks_into_b_on_any_view(self):
        self.assertEqual(self.submit_session(self.a, [(41, "Present")]).status_code, 200)
        va = self.assert_all_views(self.a, 150000, 50000)
        vb = self.assert_all_views(self.b, 0, 660000)
        self.assertEqual(va["full"]["attendance_rate"], 100.0)
        self.assertEqual(vb["full"]["total_sessions"], 0)
        self.assertEqual(vb["full"]["attendance_rate"], 0)
        self.assertTrue(vb["full"]["contract_only"], "B هنوز جلسه‌ای شارژ نشده ⇒ فقط شهریهٔ قراردادی")
        # فیلدهای جدید بنر: A بابت یک جلسه، B هیچ جلسهٔ شارژشده‌ای ندارد
        self.assertEqual((va["banner"]["unpaid_sessions"], va["banner"]["sessions_billed"]), (1, 1))
        self.assertEqual((vb["banner"]["unpaid_sessions"], vb["banner"]["sessions_billed"]), (0, 0))
        self.assertEqual((va["teacher"]["unpaid_sessions"], vb["teacher"]["sessions_billed"]), (1, 0))

    def test_2_equal_numbers_are_legitimate_only_when_each_class_has_its_own_charge(self):
        """همان چیزی که اسکرین‌شات می‌دهد: A حاضر (۱۰۰٪)، B غایب غیرموجه (۰٪) با جریمهٔ یک جلسه."""
        self.assertEqual(self.submit_session(self.a, [(41, "Present")]).status_code, 200)
        self.assertEqual(self.submit_session(self.b, [(41, "Absent")], date="1405/07/01").status_code, 200)
        va = self.assert_all_views(self.a, 150000, 50000)
        vb = self.assert_all_views(self.b, 150000, 50000)
        self.assertEqual(va["full"]["attendance_rate"], 100.0)
        self.assertEqual(vb["full"]["attendance_rate"], 0.0)
        self.assertEqual((vb["full"]["present_count"], vb["full"]["absent_count"], vb["full"]["total_sessions"]), (0, 1, 1))
        self.assertEqual(vb["banner"]["unpaid_sessions"], 1, "جریمهٔ غیبت هم یک جلسهٔ شارژشدهٔ همین کلاس است")

    def test_3_payment_or_session_delete_in_a_does_not_touch_b(self):
        self.assertEqual(self.submit_session(self.a, [(41, "Present")]).status_code, 200)
        self.assertEqual(self.submit_session(self.b, [(41, "Present")], date="1405/07/01").status_code, 200)
        before_b = self.views(self.b)["banner"]
        # حذف جلسهٔ A فقط A را عوض می‌کند
        import models
        code = self.db.query(models.SessionLog).filter_by(course_id=self.a).first().session_code
        resp = self.client.delete(f"/attendance/session/{code}", headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(self.views(self.a)["banner"]["sessions_billed"], 0, "جلسهٔ A باید واقعاً حذف شده باشد")
        after_b = self.views(self.b)["banner"]
        for key in ("debt_to_teacher", "debt_to_institute", "total_debt", "unpaid_sessions", "sessions_billed"):
            self.assertEqual(before_b[key], after_b[key], f"{key} کلاس B با تغییر A عوض شد")
