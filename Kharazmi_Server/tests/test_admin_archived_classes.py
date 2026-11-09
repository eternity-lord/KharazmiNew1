# test_admin_archived_classes.py
# Regression tests for «کلاس‌های حذف‌شده / آرشیو ادمین»:
#   GET  /admin/deleted_classes           (لیست آرشیو: اطلاعات کامل + branch isolation + جست‌وجو)
#   GET  /admin/deleted_classes/{id}      (جزئیات کنترول‌شده‌ی کلاس آرشیوشده)
#   POST /admin/deleted_classes/{id}/restore = restore عملیاتی کامل با گزینهٔ مالی؛ جزئیات آن
#        در test_class_restore_metadata.py است و این فایل فقط یکپارچگی route/آرشیو را می‌سنجد.
# و تعامل آن با DELETE /classes/{id} (جریان واقعی حذف) و GET /classes/list (لیست عادی).
#
# اجرا (روی DB کپی — نه DB واقعی، مطابق قاعده‌ی پروژه):
#   DATABASE_URL=sqlite:////tmp/archived_classes_test.db \
#   JWT_SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))") \
#   python3 -m pytest test_admin_archived_classes.py -q
import datetime
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models import (
    Base, Branch, ClassDeletionRequest, Course, Enrollment, SessionLog, Student,
    Teacher, Transaction, User, UserSession,
)
from main import app
from dependencies import get_db


class TestAdminArchivedClasses(unittest.TestCase):
    def setUp(self):
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
                pass  # سشن مشترک تست بسته نمی‌شود (الگوی test_exports.py)

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        self.db.add_all([
            Branch(id=1, name="شعبه مرکزی", active=True),
            Branch(id=2, name="شعبه شمال", active=True),
        ])
        self.db.flush()

        # نقش‌ها: ادمین کل (بدون شعبه)، ادمین شعبه‌دار (شعبه ۱)، منشی، معلم، شاگرد
        self.global_admin = User(username="gadmin", password="x", full_name="مدیر کل",
                                 role="admin", sub_role="admin", branch_id=None)
        self.branch_admin = User(username="badmin", password="x", full_name="مدیر شعبه",
                                 role="admin", sub_role="admin", branch_id=1)
        self.secretary = User(username="secretary", password="x", full_name="منشی",
                              role="admin", sub_role="secretary", branch_id=1)
        self.teacher_user = User(username="teacher", password="x", full_name="معلم",
                                 role="teacher", sub_role="teacher", branch_id=1)
        self.student_user = User(username="student", password="x", full_name="شاگرد",
                                 role="student", sub_role="student", branch_id=1)
        self.db.add_all([self.global_admin, self.branch_admin, self.secretary,
                         self.teacher_user, self.student_user])
        self.db.flush()
        now = datetime.datetime.now()
        for token, user in (("tok-global", self.global_admin), ("tok-branch", self.branch_admin),
                            ("tok-secretary", self.secretary), ("tok-teacher", self.teacher_user),
                            ("tok-student", self.student_user)):
            self.db.add(UserSession(token=token, user_id=user.id, sub_role=user.sub_role, created_at=now))

        # معلم رکورد legacy (نام NULL) + معلم سالم
        self.t_legacy = Teacher(first_name=None, last_name=None, mobile=None, national_code=None,
                                password="x", is_approved=True, is_deleted=False, branch_id=1)
        self.t_ok = Teacher(first_name="مریم", last_name="تست", mobile="09120000021",
                            national_code="0012345601", password="x", is_approved=True, is_deleted=False,
                            branch_id=2)
        self.db.add_all([self.t_legacy, self.t_ok])
        self.student = Student(first_name="علی", last_name="تست", national_code="0012345602",
                               student_mobile="09120000022", wallet_teacher=0, wallet_institute=0,
                               wallet_balance=0)
        self.db.add(self.student)
        self.db.flush()

        # کلاس آرشیوشده‌ی legacy در شعبه ۱ (title/code/grade همه NULL)
        self.c_arch_legacy = Course(title=None, code=None, teacher_id=self.t_legacy.id, branch_id=1,
                                    is_deleted=True, is_admin_approved=True, grade_level=None,
                                    class_time="16:00", days_of_week="شنبه", teacher_session_price=100000)
        # کلاس آرشیوشده در شعبه ۲
        self.c_arch_b2 = Course(title="کلاس شمال", code="300002", teacher_id=self.t_ok.id, branch_id=2,
                                is_deleted=True, is_admin_approved=True, grade_level="دهم",
                                class_time="17:00", days_of_week="یکشنبه", teacher_session_price=100000)
        # کلاس فعال در شعبه ۱ — نباید در آرشیو بیاید
        self.c_active = Course(title="کلاس فعال", code="300003", teacher_id=self.t_ok.id, branch_id=1,
                               is_deleted=False, is_admin_approved=True, grade_level="یازدهم",
                               class_time="18:00", days_of_week="دوشنبه", teacher_session_price=100000)
        # کلاس فعال برای تست جریان واقعی حذف
        self.c_to_delete = Course(title="کلاس برای حذف", code="300004", teacher_id=self.t_ok.id, branch_id=1,
                                  is_deleted=False, is_admin_approved=True, grade_level="دوازدهم",
                                  class_time="19:00", days_of_week="سه‌شنبه", teacher_session_price=100000)
        self.db.add_all([self.c_arch_legacy, self.c_arch_b2, self.c_active, self.c_to_delete])
        self.db.flush()

        # تاریخچه‌ی کلاس آرشیوشده‌ی legacy: ثبت‌نام/جلسه‌ی آرشیوشده + تراکنش فعال + رکورد حذف
        self.db.add(Enrollment(student_id=self.student.id, course_id=self.c_arch_legacy.id, branch_id=1,
                               register_date="1405/06/01", shift="عصر", total_tuition=1000000,
                               total_paid=0, is_deleted=True))
        self.db.add(SessionLog(course_id=self.c_arch_legacy.id, date="1405/06/02", time="16:00",
                               final_teacher_cost=100000, final_institute_share=50000,
                               cost_per_student=150000, attendee_count=1, status="Finished",
                               is_deleted=True))
        self.db.add(Transaction(student_id=self.student.id, course_id=self.c_arch_legacy.id, branch_id=1,
                                amount=250000, type="tuition", date="1405/06/01", description="شهریه",
                                is_deleted=False, is_reversed=False))
        self.db.add(ClassDeletionRequest(course_id=self.c_arch_legacy.id, requested_by_role="admin",
                                        status="approved", forgive_session_charges=True,
                                        decided_at=datetime.datetime(2026, 9, 20, 12, 30)))
        self.db.commit()

    def tearDown(self):
        app.dependency_overrides.pop(get_db, None)
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    # ------------------------------------------------------------------
    # ابزار کمکی
    # ------------------------------------------------------------------
    def _archive(self, token="tok-global", **params):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return self.client.get("/admin/deleted_classes", headers=headers, params=params)

    def _detail(self, course_id, token="tok-global"):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return self.client.get(f"/admin/deleted_classes/{course_id}", headers=headers)

    def _ids(self, response):
        return [row["id"] for row in response.json()]

    # ------------------------------------------------------------------
    # ۱) فقط نقش مجاز آرشیو را می‌بیند
    # ------------------------------------------------------------------
    def test_1_archive_requires_admin_role(self):
        self.assertEqual(self._archive(token=None).status_code, 401)                 # بدون توکن
        self.assertEqual(self._archive(token="tok-invalid").status_code, 401)        # توکن نامعتبر
        self.assertEqual(self._archive(token="tok-secretary").status_code, 403)      # منشی
        self.assertEqual(self._archive(token="tok-teacher").status_code, 403)        # معلم
        self.assertEqual(self._archive(token="tok-student").status_code, 403)        # شاگرد
        self.assertEqual(self._archive(token="tok-global").status_code, 200)         # ادمین
        self.assertEqual(self._archive(token="tok-branch").status_code, 200)         # ادمین شعبه‌دار

    # ------------------------------------------------------------------
    # ۲ و ۳) branch isolation — نشت بین شعبه‌ها ممنوع
    # ------------------------------------------------------------------
    def test_2_branch_admin_sees_only_own_branch(self):
        resp = self._archive(token="tok-branch")
        self.assertEqual(resp.status_code, 200)
        rows = resp.json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], self.c_arch_legacy.id)
        self.assertEqual(rows[0]["branch_id"], 1)
        self.assertEqual(rows[0]["branch_name"], "شعبه مرکزی")

    def test_3_no_cross_branch_leak(self):
        rows = self._archive(token="tok-branch").json()
        self.assertNotIn(self.c_arch_b2.id, [r["id"] for r in rows])          # لیست شعبه‌ی دیگر نشت نکند
        self.assertEqual(self._detail(self.c_arch_b2.id, token="tok-branch").status_code, 404)
        # ادمین کل هر دو شعبه را می‌بیند (سیاست فعلی: branch_id=NULL یعنی دسترسی سراسری)
        self.assertEqual(sorted(self._ids(self._archive(token="tok-global"))),
                         sorted([self.c_arch_legacy.id, self.c_arch_b2.id]))
        self.assertEqual(self._detail(self.c_arch_b2.id, token="tok-global").status_code, 200)

    # ------------------------------------------------------------------
    # ۴) کلاس فعال در آرشیو نمی‌آید
    # ------------------------------------------------------------------
    def test_4_active_class_not_in_archive(self):
        ids = self._ids(self._archive(token="tok-global"))
        self.assertNotIn(self.c_active.id, ids)
        self.assertNotIn(self.c_to_delete.id, ids)
        self.assertEqual(self._detail(self.c_active.id, token="tok-global").status_code, 404)

    # ------------------------------------------------------------------
    # ۵) کلاس حذف‌شده با متادیتای کامل در آرشیو می‌آید
    # ------------------------------------------------------------------
    def test_5_deleted_class_appears_with_metadata(self):
        rows = {r["id"]: r for r in self._archive(token="tok-global").json()}
        legacy = rows[self.c_arch_legacy.id]
        # //FIX(null-data): رکورد legacy با title/teacher NULL باید مقدار امن بدهد
        self.assertEqual(legacy["title"], "")
        self.assertEqual(legacy["code"], "")
        self.assertEqual(legacy["teacher_name"], "نامشخص")
        self.assertEqual(legacy["grade_level"], "")
        # فیلدهای تازه‌ی آرشیو
        self.assertEqual(legacy["branch_id"], 1)
        self.assertEqual(legacy["branch_name"], "شعبه مرکزی")
        self.assertEqual(legacy["students_count"], 1)          # شامل ثبت‌نام آرشیوشده (تاریخی)
        self.assertEqual(legacy["sessions_count"], 1)
        self.assertEqual(legacy["transactions_count"], 1)
        self.assertEqual(legacy["deleted_at"], "2026/09/20 12:30")   # از ClassDeletionRequest
        self.assertTrue(legacy["forgive_session_charges"])
        # کلاس بدون رکورد حذف نباید تاریخ حدسی بگیرد
        self.assertEqual(rows[self.c_arch_b2.id]["deleted_at"], "")

    # ------------------------------------------------------------------
    # ۶) داده‌ی null/legacy باعث 500 نشود
    # ------------------------------------------------------------------
    def test_6_legacy_nulls_do_not_500(self):
        resp = self._archive(token="tok-global")
        self.assertEqual(resp.status_code, 200)
        raw = resp.text
        self.assertNotIn("None", raw)          # نه «None» پایتونی و نه null خام در متن
        resp2 = self._detail(self.c_arch_legacy.id, token="tok-global")
        self.assertEqual(resp2.status_code, 200)
        self.assertNotIn("None", resp2.text)
        body = resp2.json()
        self.assertNotIn(None, [body["title"], body["code"], body["teacher_name"],
                                body["branch_name"], body["grade_level"]])
        self.assertEqual(body["teacher_name"], "نامشخص")

    # ------------------------------------------------------------------
    # ۷) جزئیات کلاس آرشیوشده: پاسخ کنترول‌شده
    # ------------------------------------------------------------------
    def test_7_archived_detail_controlled_response(self):
        resp = self._detail(self.c_arch_legacy.id, token="tok-global")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(
            set(body.keys()),
            {"id", "title", "code", "grade_level", "days_of_week", "class_time", "is_suspended",
             "bg_color", "teacher_id", "teacher_name", "branch_id", "branch_name", "students_count",
             "students_active_count", "archived_enrollments_count", "sessions_count",
             "archived_sessions_count", "transactions_count", "transactions_total", "deleted_at",
             "has_deletion_record", "financial_restore_available", "forgive_session_charges", "requested_by_role", "admin_note",
             # گزارش کامل تاریخی (صفحهٔ جزئیات آرشیو): تاریخ جلالی، حضور/غیاب، فهرست شاگردان، مالی
             "deleted_at_jalali", "deleted_weekday", "students", "attendance_totals", "finance_totals",
             "sessions_held", "sessions_history", "first_session_date", "last_session_date", "has_snapshot"},
        )
        self.assertEqual(body["students_count"], 1)
        self.assertEqual(body["archived_enrollments_count"], 1)
        self.assertEqual(body["students_active_count"], 0)
        self.assertEqual(body["sessions_count"], 1)
        self.assertEqual(body["archived_sessions_count"], 1)
        self.assertEqual(body["transactions_count"], 1)
        self.assertEqual(body["transactions_total"], 250000)
        self.assertTrue(body["has_deletion_record"])
        self.assertEqual(body["requested_by_role"], "admin")
        self.assertEqual(self._detail(999999, token="tok-global").status_code, 404)   # ناموجود
        self.assertEqual(self._detail(self.c_active.id, token="tok-global").status_code, 404)  # فعال

    # ------------------------------------------------------------------
    # ۸) restore از همان endpoint کنترل‌شده انجام می‌شود و خواندن آرشیو فقط‌خواندنی است
    # ------------------------------------------------------------------
    def test_8_restore_uses_single_endpoint_and_archive_is_read_only(self):
        # قرارداد بازیابی کامل/مالی در test_class_restore_metadata.py و route audit است:
        #   ۱) تنها مسیر restore مجاز = /admin/deleted_classes/{id}/restore؛
        #   ۲) خواندن آرشیو هیچ چیزی را تغییر نمی‌دهد،
        #   ۳) هیچ مسیر جایگزین/بدون احراز هویت برای restore اضافه نشده است.
        restore_paths = sorted(p for p in app.openapi()["paths"] if "restore" in p.lower())
        self.assertEqual(restore_paths, ["/admin/deleted_classes/{course_id}/restore"])
        restore_op = app.openapi()["paths"]["/admin/deleted_classes/{course_id}/restore"]
        self.assertIn("post", restore_op)
        # تاریخچهٔ عملیاتی/مالی از همان endpoint کنترل‌شده بازمی‌گردد، نه مسیر جداگانه.
        self.assertEqual([p for p in restore_paths if "enrollment" in p or "session" in p.lower()], [])
        # خواندن آرشیو نباید وضعیت را تغییر دهد
        before = (self.db.query(Course).filter(Course.is_deleted == True).count(),  # noqa: E712
                  self.db.query(Enrollment).filter(Enrollment.course_id == self.c_arch_legacy.id).count())
        self._archive(token="tok-global")
        self._detail(self.c_arch_legacy.id, token="tok-global")
        after = (self.db.query(Course).filter(Course.is_deleted == True).count(),  # noqa: E712
                 self.db.query(Enrollment).filter(Enrollment.course_id == self.c_arch_legacy.id).count())
        self.assertEqual(before, after)
        self.assertEqual(self._archive(token="tok-global").status_code, 200)

    # ------------------------------------------------------------------
    # ۹) حذف کلاس، تاریخچه‌ی enrollment/transaction/session را از بین نمی‌برد
    # ------------------------------------------------------------------
    def test_9_delete_preserves_history(self):
        en = Enrollment(student_id=self.student.id, course_id=self.c_to_delete.id, branch_id=1,
                        register_date="1405/06/03", shift="عصر", total_tuition=2000000,
                        total_paid=500000, is_deleted=False)
        self.db.add(en)
        self.db.flush()
        session_log = SessionLog(course_id=self.c_to_delete.id, date="1405/06/04", time="19:00",
                                 final_teacher_cost=120000, final_institute_share=80000,
                                 cost_per_student=200000, attendee_count=1, status="Finished",
                                 is_deleted=False)
        self.db.add(session_log)
        self.db.flush()
        self.db.add_all([
            Transaction(student_id=self.student.id, course_id=self.c_to_delete.id, branch_id=1,
                        amount=500000, type="tuition", date="1405/06/03", description="شهریه",
                        is_deleted=False, is_reversed=False),
            Transaction(student_id=self.student.id, course_id=self.c_to_delete.id, branch_id=1,
                        amount=200000, type="session_charge", session_id=session_log.id,
                        date="1405/06/04", description="هزینه جلسه",
                        is_deleted=False, is_reversed=False),
        ])
        self.db.commit()
        en_id, session_id = en.id, session_log.id

        resp = self.client.delete(f"/classes/{self.c_to_delete.id}",
                                  headers={"Authorization": "Bearer tok-global"})
        self.assertEqual(resp.status_code, 200, resp.text)

        # ردیف‌ها حذف فیزیکی نشده‌اند (فقط آرشیو شده‌اند)
        self.assertIsNotNone(self.db.query(Enrollment).filter(Enrollment.id == en_id).first())
        self.assertIsNotNone(self.db.query(SessionLog).filter(SessionLog.id == session_id).first())
        self.assertEqual(
            self.db.query(Transaction).filter(Transaction.course_id == self.c_to_delete.id).count(), 2)
        archived_en = self.db.query(Enrollment).filter(Enrollment.id == en_id).first()
        self.assertTrue(archived_en.is_deleted)
        # تراکنش شهریه (وجه واقعی) باید فعال بماند تا حسابرسی/استرداد ممکن بماند
        tuition = (self.db.query(Transaction)
                   .filter(Transaction.course_id == self.c_to_delete.id, Transaction.type == "tuition")
                   .first())
        self.assertFalse(tuition.is_deleted)
        # و کلاس حذف‌شده با تاریخِ واقعی حذف در آرشیو دیده می‌شود
        rows = {r["id"]: r for r in self._archive(token="tok-global").json()}
        self.assertIn(self.c_to_delete.id, rows)
        self.assertNotEqual(rows[self.c_to_delete.id]["deleted_at"], "")
        self.assertEqual(rows[self.c_to_delete.id]["students_count"], 1)

    # ------------------------------------------------------------------
    # ۱۰) لیست عادی و آرشیو با هم قاطی نمی‌شوند
    # ------------------------------------------------------------------
    def test_10_archive_not_mixed_with_active_list(self):
        headers = {"Authorization": "Bearer tok-global"}
        active = self.client.get("/classes/list", headers=headers)
        self.assertEqual(active.status_code, 200)
        active_ids = [row.get("id") if isinstance(row, dict) else row for row in active.json()]
        self.assertIn(self.c_active.id, active_ids)
        self.assertNotIn(self.c_arch_legacy.id, active_ids)
        self.assertNotIn(self.c_arch_b2.id, active_ids)

        archive_ids = self._ids(self._archive(token="tok-global"))
        self.assertNotIn(self.c_active.id, archive_ids)
        self.assertEqual(set(archive_ids) & set(active_ids), set())

    # ------------------------------------------------------------------
    # ۱۱) جست‌وجو در آرشیو (قابلیت تازه)
    # ------------------------------------------------------------------
    def test_11_archive_search(self):
        self.assertEqual(self._ids(self._archive(token="tok-global", query="شمال")), [self.c_arch_b2.id])
        self.assertEqual(self._ids(self._archive(token="tok-global", query="300002")), [self.c_arch_b2.id])
        self.assertEqual(self._ids(self._archive(token="tok-global", query="کلاس فعال")), [])
        # جست‌وجو هم باید branch-isolated بماند
        self.assertEqual(self._ids(self._archive(token="tok-branch", query="شمال")), [])


if __name__ == "__main__":
    unittest.main()
