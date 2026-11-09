# test_archived_class_search_and_report.py
# «کلاس‌های حذفی (آرشیو ادمین)» — صفحهٔ جدید اپ:
#   GET /admin/deleted_classes            → جست‌وجو (نام کلاس / معلم / کد / بازهٔ تاریخ حذف) + تاریخ جلالی
#   GET /admin/deleted_classes/{id}       → گزارش کامل تاریخی: حضور/غیاب (موجه/غیرموجه)، شاگردان،
#                                           پرداخت‌شده و مانده‌ی زمان حذف
# همهٔ داده‌ها درون‌حافظه‌ای ساخته می‌شوند (نه DB واقعی) و به تاریخِ «امروز» وابسته نیستند.
import datetime
import json
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from dependencies import get_db
from main import app
from models import (
    Attendance, Base, Branch, ClassDeletionRequest, Course, Enrollment, SessionLog, Student,
    Teacher, Transaction, User, UserSession,
)

DELETED_A = datetime.datetime(2026, 9, 28, 7, 29)   # ۶ مهر ۱۴۰۵، دوشنبه
DELETED_B = datetime.datetime(2026, 8, 10, 15, 0)   # مرداد ۱۴۰۵


class TestArchivedClassSearchAndReport(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine)()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        db = self.db
        db.add(Branch(id=1, name="شعبه مرکزی", active=True))
        db.flush()
        admin = User(username="adm", password="x", full_name="مدیر", role="admin", sub_role="admin", branch_id=None)
        db.add(admin)
        db.flush()
        db.add(UserSession(token="tok", user_id=admin.id, sub_role="admin", created_at=datetime.datetime.now()))

        self.t_ali = Teacher(first_name="علی", last_name="احمدی", mobile="09120000031", national_code="0012345631",
                             password="x", is_approved=True, is_deleted=False, branch_id=1)
        self.t_sara = Teacher(first_name="سارا", last_name="کریمی", mobile="09120000032", national_code="0012345632",
                              password="x", is_approved=True, is_deleted=False, branch_id=1)
        db.add_all([self.t_ali, self.t_sara])
        db.flush()

        def mk_student(first, last, nat, code):
            s = Student(first_name=first, last_name=last, national_code=nat, student_mobile="0912" + nat[-7:],
                        wallet_teacher=0, wallet_institute=0, wallet_balance=0, student_code=code)
            db.add(s)
            return s

        self.s1 = mk_student("مرضیه", "ایرانی", "0012345641", 810001)
        self.s2 = mk_student("رضا", "موسوی", "0012345642", 810002)
        db.flush()

        # A: ریاضی — معلم علی احمدی — با اسنپ‌شات — حذف ۶ مهر
        self.c_a = Course(title="ریاضی", code="100001", teacher_id=self.t_ali.id, branch_id=1, is_deleted=True,
                          is_admin_approved=True, grade_level="دهم", class_time="16:00", days_of_week="شنبه",
                          teacher_session_price=600000)
        # B: فیزیک — معلم سارا کریمی — بدون اسنپ‌شات — حذف مرداد
        self.c_b = Course(title="فیزیک", code="200002", teacher_id=self.t_sara.id, branch_id=1, is_deleted=True,
                          is_admin_approved=True, grade_level="یازدهم", class_time="17:00", days_of_week="یکشنبه",
                          teacher_session_price=500000)
        # C: legacy بدون هیچ رکورد حذف (تاریخ ندارد)
        self.c_c = Course(title="شیمی", code="300003", teacher_id=self.t_ali.id, branch_id=1, is_deleted=True,
                          is_admin_approved=True, grade_level="دوازدهم", class_time="18:00", days_of_week="دوشنبه",
                          teacher_session_price=100000)
        # کلاس فعال — هرگز در آرشیو نمی‌آید
        self.c_live = Course(title="ریاضی فعال", code="100009", teacher_id=self.t_ali.id, branch_id=1, is_deleted=False,
                             is_admin_approved=True, grade_level="دهم", class_time="19:00", days_of_week="شنبه",
                             teacher_session_price=100000)
        db.add_all([self.c_a, self.c_b, self.c_c, self.c_live])
        db.flush()

        # --- کلاس A: دو شاگرد، سه جلسه (یکی جداگانه قبلاً برگشت خورده) ---
        self.e1 = Enrollment(student_id=self.s1.id, course_id=self.c_a.id, branch_id=1, register_date="1405/06/01",
                             shift="عصر", total_tuition=1000000, total_paid=400000, is_deleted=True)
        self.e2 = Enrollment(student_id=self.s2.id, course_id=self.c_a.id, branch_id=1, register_date="1405/06/01",
                             shift="عصر", total_tuition=800000, total_paid=800000, is_deleted=True)
        db.add_all([self.e1, self.e2])
        self.sess1 = SessionLog(course_id=self.c_a.id, date="1405/07/01", time="16:00", is_deleted=True)
        self.sess2 = SessionLog(course_id=self.c_a.id, date="1405/07/03", time="16:00", is_deleted=True)
        self.sess_reversed = SessionLog(course_id=self.c_a.id, date="1405/07/02", time="16:00", is_deleted=True)
        db.add_all([self.sess1, self.sess2, self.sess_reversed])
        db.flush()

        def att(sess, stu, status, excused=False, deleted=False):
            db.add(Attendance(session_id=sess.id, student_id=stu.id, status=status, excused=excused, is_deleted=deleted))

        att(self.sess1, self.s1, "Present")
        att(self.sess1, self.s2, "Absent", excused=True)
        att(self.sess2, self.s1, "Late")
        att(self.sess2, self.s2, "Absent", excused=False)
        att(self.sess_reversed, self.s1, "Present", deleted=True)     # جلسهٔ برگشت‌خورده: شمرده نمی‌شود
        att(self.sess_reversed, self.s2, "Absent", deleted=True)

        # هزینهٔ جلسه که با حذف کلاس ابطال شد (آرشیو) — حضور فعال دارد ⇒ «ابطال‌شده» حساب می‌شود
        db.add(Transaction(student_id=self.s1.id, course_id=self.c_a.id, session_id=self.sess1.id, branch_id=1,
                           amount=660000, type="session_charge", date="1405/07/01", description="جلسه",
                           share_teacher=600000, share_institute=60000, is_deleted=True, is_reversed=False))
        # همان‌طور که لحظهٔ حذف ثبت می‌شود: اسنپ‌شات با «مانده» عمداً متفاوت از محاسبهٔ فعلی
        snapshot = {"course_id": self.c_a.id, "students": [
            {"student_id": self.s1.id, "name": "مرضیه ایرانی", "tuition_final": 1000000, "total_paid": 400000, "debt": 600000},
            {"student_id": self.s2.id, "name": "رضا موسوی", "tuition_final": 800000, "total_paid": 800000, "debt": 0},
        ]}
        db.add(ClassDeletionRequest(course_id=self.c_a.id, requested_by_role="admin", status="approved",
                                    forgive_session_charges=True, decided_at=DELETED_A,
                                    snapshot_json=json.dumps(snapshot, ensure_ascii=False)))

        # --- کلاس B: یک شاگرد، بدون اسنپ‌شات، بدون ابطال هزینه ---
        self.e3 = Enrollment(student_id=self.s1.id, course_id=self.c_b.id, branch_id=1, register_date="1405/04/01",
                             shift="عصر", total_tuition=500000, total_paid=100000, is_deleted=True)
        db.add(self.e3)
        db.add(ClassDeletionRequest(course_id=self.c_b.id, requested_by_role="admin", status="approved",
                                    forgive_session_charges=False, decided_at=DELETED_B))
        db.commit()

    def tearDown(self):
        app.dependency_overrides.pop(get_db, None)
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    # ---- ابزار ----
    def _list(self, **params):
        r = self.client.get("/admin/deleted_classes", headers={"Authorization": "Bearer tok"}, params=params)
        return r

    def _ids(self, **params):
        r = self._list(**params)
        self.assertEqual(r.status_code, 200, r.text)
        return sorted(x["id"] for x in r.json())

    def _detail(self, cid):
        r = self.client.get(f"/admin/deleted_classes/{cid}", headers={"Authorization": "Bearer tok"})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    # ---------------- جست‌وجو ----------------
    def test_1_no_filter_lists_all_archived_but_never_live(self):
        self.assertEqual(self._ids(), sorted([self.c_a.id, self.c_b.id, self.c_c.id]))

    def test_2_filter_by_class_name_teacher_name_and_code(self):
        self.assertEqual(self._ids(title="ریاضی"), [self.c_a.id])          # کلاس فعال «ریاضی فعال» نیامد
        self.assertEqual(self._ids(teacher="کریمی"), [self.c_b.id])
        self.assertEqual(self._ids(teacher="علی احمدی"), sorted([self.c_a.id, self.c_c.id]))
        self.assertEqual(self._ids(teacher="احمدی علی"), sorted([self.c_a.id, self.c_c.id]), "ترتیب واژه‌ها نباید مهم باشد")
        self.assertEqual(self._ids(code="200002"), [self.c_b.id])
        self.assertEqual(self._ids(code="9999"), [])

    def test_3_filters_are_anded_and_free_text_matches_any_field(self):
        self.assertEqual(self._ids(title="ریاضی", teacher="کریمی"), [])
        self.assertEqual(self._ids(title="ریاضی", teacher="احمدی"), [self.c_a.id])
        self.assertEqual(self._ids(query="فیزیک"), [self.c_b.id])
        self.assertEqual(self._ids(query="سارا"), [self.c_b.id])
        self.assertEqual(self._ids(query="100001"), [self.c_a.id])

    def test_4_arabic_and_persian_letters_are_equivalent(self):
        self.assertEqual(self._ids(teacher="كريمي"), [self.c_b.id])   # ك/ي عربی

    def test_5_date_range_jalali_and_gregorian(self):
        self.assertEqual(self._ids(deleted_from="1405/07/01", deleted_to="1405/07/30"), [self.c_a.id])
        self.assertEqual(self._ids(deleted_from="2026-09-28", deleted_to="2026-09-28"), [self.c_a.id], "روز مرزی شامل است")
        self.assertEqual(self._ids(deleted_to="2026-08-31"), [self.c_b.id])
        self.assertEqual(self._ids(deleted_from="2026-08-01"), sorted([self.c_a.id, self.c_b.id]))
        self.assertEqual(self._ids(deleted_from="1405/09/01"), [], "بعد از هر حذفی ⇒ خالی")

    def test_6_undated_legacy_class_is_excluded_only_when_dates_are_filtered(self):
        self.assertIn(self.c_c.id, self._ids())
        self.assertNotIn(self.c_c.id, self._ids(deleted_from="2000-01-01"))

    def test_7_reversed_range_is_swapped_and_invalid_date_is_422(self):
        self.assertEqual(self._ids(deleted_from="1405/07/30", deleted_to="1405/07/01"), [self.c_a.id])
        self.assertEqual(self._list(deleted_from="not-a-date").status_code, 422)
        self.assertEqual(self._list(deleted_to="1405/13/45").status_code, 422)
        self.assertEqual(self._list(deleted_from="   ").status_code, 200, "خالی ⇒ بی‌فیلتر")

    def test_8_filters_combine_with_dates(self):
        self.assertEqual(self._ids(teacher="احمدی", deleted_from="1405/07/01"), [self.c_a.id])
        self.assertEqual(self._ids(teacher="کریمی", deleted_from="1405/07/01"), [])

    def test_9_list_rows_carry_jalali_date_and_weekday(self):
        rows = {x["id"]: x for x in self._list().json()}
        self.assertEqual(rows[self.c_a.id]["deleted_at_jalali"], "1405/07/06 07:29")
        self.assertEqual(rows[self.c_a.id]["deleted_weekday"], "دوشنبه")
        self.assertEqual(rows[self.c_a.id]["deleted_at"], "2026/09/28 07:29", "کلید قدیمی دست‌نخورده")
        self.assertEqual(rows[self.c_c.id]["deleted_at_jalali"], "")
        self.assertTrue(rows[self.c_a.id]["teacher_name"])

    def test_10_newest_deletion_first(self):
        ids = [x["id"] for x in self._list().json()]
        self.assertLess(ids.index(self.c_a.id), ids.index(self.c_b.id))

    # ---------------- گزارش جزئیات ----------------
    def test_11_attendance_totals_split_excused_and_unexcused(self):
        d = self._detail(self.c_a.id)
        at = d["attendance_totals"]
        self.assertEqual((at["present"], at["late"], at["absent"]), (2, 1, 2))
        self.assertEqual((at["absent_excused"], at["absent_unexcused"]), (1, 1))
        self.assertEqual(at["attendance_rate"], 50)
        self.assertEqual(d["sessions_held"], 2, "جلسهٔ برگشت‌خورده شمرده نمی‌شود")

    def test_12_per_student_rows_and_names(self):
        d = self._detail(self.c_a.id)
        by = {r["student_id"]: r for r in d["students"]}
        self.assertEqual(len(d["students"]), 2)
        m = by[self.s1.id]
        self.assertEqual(m["name"], "مرضیه ایرانی")
        self.assertEqual((m["present"], m["late"], m["absent"]), (2, 1, 0))
        self.assertEqual(m["attendance_rate"], 100)
        r = by[self.s2.id]
        self.assertEqual((r["present"], r["absent"], r["absent_excused"], r["absent_unexcused"]), (0, 2, 1, 1))
        self.assertEqual(r["attendance_rate"], 0)
        self.assertEqual(m["student_code"], 810001)

    def test_13_finance_paid_and_remaining_at_deletion_from_snapshot(self):
        d = self._detail(self.c_a.id)
        by = {r["student_id"]: r for r in d["students"]}
        m = by[self.s1.id]
        self.assertEqual((m["tuition"], m["paid"], m["tuition_debt"]), (1000000, 400000, 600000))
        self.assertEqual(m["finance_source"], "snapshot")
        self.assertEqual(by[self.s2.id]["debt_total"], 0)
        ft = d["finance_totals"]
        self.assertEqual((ft["tuition"], ft["paid"], ft["debt_total"], ft["debtors"]), (1800000, 1200000, 600000, 1))
        self.assertTrue(d["has_snapshot"])

    def test_14_snapshot_takes_precedence_over_current_computation(self):
        # اسنپ‌شات را «متفاوت» می‌کنیم؛ گزارش باید همان مقدار لحظهٔ حذف را نشان دهد
        row = self.db.query(ClassDeletionRequest).filter_by(course_id=self.c_a.id).first()
        data = json.loads(row.snapshot_json)
        data["students"][0]["debt"] = 123
        row.snapshot_json = json.dumps(data, ensure_ascii=False)
        self.db.commit()
        by = {r["student_id"]: r for r in self._detail(self.c_a.id)["students"]}
        self.assertEqual(by[self.s1.id]["tuition_debt"], 123)

    def test_15_forgiven_session_charges_are_reported(self):
        d = self._detail(self.c_a.id)
        m = {r["student_id"]: r for r in d["students"]}[self.s1.id]
        self.assertEqual((m["forgiven_teacher"], m["forgiven_institute"]), (600000, 60000))
        self.assertEqual(d["finance_totals"]["forgiven_total"], 660000)
        self.assertEqual(m["session_debt_teacher"] + m["session_debt_institute"], 0, "ابطال‌شده بدهی جلسه‌ای نیست")

    def test_16_class_without_snapshot_uses_ledger(self):
        d = self._detail(self.c_b.id)
        self.assertFalse(d["has_snapshot"])
        row = d["students"][0]
        self.assertEqual((row["tuition"], row["paid"], row["tuition_debt"]), (500000, 100000, 400000))
        self.assertEqual(row["finance_source"], "computed")
        self.assertEqual(d["sessions_held"], 0)
        self.assertEqual(d["attendance_totals"]["attendance_rate"], None)

    def test_17_sessions_history_has_weekday_and_counts(self):
        d = self._detail(self.c_a.id)
        hist = d["sessions_history"]
        self.assertEqual([h["date"] for h in hist], ["1405/07/01", "1405/07/03"])
        self.assertEqual(hist[0]["weekday"], "چهارشنبه")   # ۱ مهر ۱۴۰۵ = ۲۳ سپتامبر ۲۰۲۶
        self.assertEqual((hist[0]["present"], hist[0]["absent"], hist[0]["absent_excused"]), (1, 1, 1))
        self.assertEqual((hist[1]["present"], hist[1]["absent_unexcused"]), (1, 1))
        self.assertEqual(d["first_session_date"], "1405/07/01")
        self.assertEqual(d["last_session_date"], "1405/07/03")

    def test_18_detail_keeps_old_keys_and_is_read_only(self):
        before = (self.db.query(Enrollment).count(), self.db.query(Transaction).count(),
                  sum(s.wallet_teacher or 0 for s in self.db.query(Student)))
        d = self._detail(self.c_a.id)
        for key in ("students_count", "sessions_count", "transactions_count", "deleted_at", "forgive_session_charges"):
            self.assertIn(key, d)
        self.assertEqual(d["deleted_at_jalali"], "1405/07/06 07:29")
        after = (self.db.query(Enrollment).count(), self.db.query(Transaction).count(),
                 sum(s.wallet_teacher or 0 for s in self.db.query(Student)))
        self.assertEqual(before, after)

    def test_19_broken_snapshot_json_does_not_500(self):
        row = self.db.query(ClassDeletionRequest).filter_by(course_id=self.c_a.id).first()
        row.snapshot_json = "{not json"
        self.db.commit()
        d = self._detail(self.c_a.id)
        self.assertFalse(d["has_snapshot"])
        self.assertEqual(len(d["students"]), 2)

    def test_21_unforgiven_charges_remain_as_session_debt(self):
        """حذف بدون ابطال هزینه‌ها: چارج جلسه زنده می‌ماند ⇒ بدهی جلسه‌ای (معلم/آموزشگاه) گزارش می‌شود."""
        sess = SessionLog(course_id=self.c_b.id, date="1405/04/05", time="17:00", is_deleted=False)
        self.db.add(sess)
        self.db.flush()
        self.db.add(Attendance(session_id=sess.id, student_id=self.s1.id, status="Present", excused=False, is_deleted=False))
        self.db.add(Transaction(student_id=self.s1.id, course_id=self.c_b.id, session_id=sess.id, branch_id=1,
                                amount=350000, type="session_charge", date="1405/04/05", description="جلسه",
                                share_teacher=300000, share_institute=50000, is_deleted=False, is_reversed=False))
        self.db.commit()
        d = self._detail(self.c_b.id)
        row = d["students"][0]
        self.assertEqual(row["session_debt_teacher"] + row["session_debt_institute"] > 0, True)
        self.assertEqual(row["forgiven_teacher"] + row["forgiven_institute"], 0)
        self.assertEqual(d["finance_totals"]["forgiven_total"], 0)
        self.assertEqual(d["attendance_totals"]["present"], 1)
        self.assertEqual(d["sessions_held"], 1)

    def test_20_live_class_and_unknown_are_404_and_role_is_enforced(self):
        h = {"Authorization": "Bearer tok"}
        self.assertEqual(self.client.get(f"/admin/deleted_classes/{self.c_live.id}", headers=h).status_code, 404)
        self.assertEqual(self.client.get("/admin/deleted_classes/999999", headers=h).status_code, 404)
        self.assertEqual(self.client.get("/admin/deleted_classes").status_code, 401)


if __name__ == "__main__":
    unittest.main()
