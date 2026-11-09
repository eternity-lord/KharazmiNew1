# test_class_restore_metadata.py
# تست‌های سازگاری و branch/permission برای بازیابی کلاس آرشیوشده:
#   POST /admin/deleted_classes/{course_id}/restore
#   • mode=metadata_only رفتار قدیمی را حفظ می‌کند؛ mode=full تاریخچهٔ عملیاتی را هم برمی‌گرداند.
#   • مالی با include_financial_history صریحاً انتخاب می‌شود؛ restore مالی فقط با provenance معتبر.
#   • وضعیت مالیِ خاموش دست‌نخورده می‌ماند؛ ثبت ClassRestoreLog و ActivityLog حفظ می‌شود.
#   • فقط ادمین + branch isolation؛ 400 ورودی نامعتبر، 404 ناموجود/شعبهٔ دیگر، 409 تعارض/کلاس فعال.
#
# اجرا (روی DB موقت — نه DB واقعی):
#   DATABASE_URL=sqlite:////tmp/restore_metadata_test.db \
#   JWT_SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))") \
#   python3 -m pytest Kharazmi_Server/test_class_restore_metadata.py -q
import datetime
import json
import os
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models import (
    Base, Branch, ClassDeletionRequest, ClassRestoreLog, Course, Enrollment, SessionLog,
    Student, Teacher, Transaction, User, UserSession,
)
from main import app
from dependencies import get_db


class TestClassRestoreMetadata(unittest.TestCase):
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
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        self.db.add_all([Branch(id=1, name="شعبه مرکزی", active=True),
                         Branch(id=2, name="شعبه شمال", active=True)])
        self.db.flush()

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

        self.teacher = Teacher(first_name="مریم", last_name="تست", mobile="09120000031",
                               national_code="0012345611", password="x", is_approved=True,
                               is_deleted=False, branch_id=1)
        self.db.add(self.teacher)
        self.student = Student(first_name="علی", last_name="تست", national_code="0012345612",
                               student_mobile="09120000032", wallet_teacher=50000,
                               wallet_institute=30000, wallet_balance=200000)
        self.db.add(self.student)
        self.db.flush()

        # کلاس آرشیوشده در شعبه ۱ با تاریخچه‌ی آرشیوی (ثبت‌نام/جلسه/تراکنش)
        self.c_arch = Course(title="کلاس آرشیو", code="400001", teacher_id=self.teacher.id, branch_id=1,
                             is_deleted=True, is_admin_approved=True, grade_level="دهم",
                             class_time="16:00", days_of_week="شنبه", teacher_session_price=120000)
        # کلاس آرشیوشده در شعبه ۲ (برای تست دسترسی)
        self.c_arch_b2 = Course(title="کلاس شمال", code="400002", teacher_id=self.teacher.id, branch_id=2,
                                is_deleted=True, is_admin_approved=True, grade_level="یازدهم",
                                class_time="17:00", days_of_week="یکشنبه", teacher_session_price=120000)
        # کلاس فعال (restore نباید رویش اثر بگذارد)
        self.c_active = Course(title="کلاس فعال", code="400003", teacher_id=self.teacher.id, branch_id=1,
                               is_deleted=False, is_admin_approved=True, grade_level="دوازدهم",
                               class_time="18:00", days_of_week="دوشنبه", teacher_session_price=120000)
        self.db.add_all([self.c_arch, self.c_arch_b2, self.c_active])
        self.db.flush()

        self.en_arch = Enrollment(student_id=self.student.id, course_id=self.c_arch.id, branch_id=1,
                                  register_date="1405/06/01", shift="عصر", total_tuition=1200000,
                                  total_paid=400000, is_deleted=True)
        self.db.add(self.en_arch)
        self.db.add(SessionLog(course_id=self.c_arch.id, date="1405/06/02", time="16:00",
                               final_teacher_cost=120000, final_institute_share=60000,
                               cost_per_student=150000, attendee_count=1, status="Finished",
                               is_deleted=True))
        self.db.add(Transaction(student_id=self.student.id, course_id=self.c_arch.id, branch_id=1,
                                amount=400000, type="enrollment_payment", date="1405/06/01",
                                description="شهریه", is_deleted=False, is_reversed=False))
        self.db.add(ClassDeletionRequest(course_id=self.c_arch.id, requested_by_role="admin",
                                        status="approved", forgive_session_charges=True,
                                        decided_at=datetime.datetime(2026, 9, 19, 10, 0)))
        self.db.commit()

    def tearDown(self):
        app.dependency_overrides.pop(get_db, None)
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    # ------------------------------------------------------------------
    # ابزار کمکی
    # ------------------------------------------------------------------
    def _restore(self, course_id, token="tok-global", mode="metadata_only", reason="بازیابی آزمایشی"):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return self.client.post(f"/admin/deleted_classes/{course_id}/restore",
                                json={"mode": mode, "reason": reason}, headers=headers)

    def _financial_fingerprint(self):
        """اثر مالی صفر ⇒ این اثر انگشت باید قبل/بعد یکسان باشد."""
        student = self.db.query(Student).filter(Student.id == self.student.id).first()
        self.db.refresh(student)
        return {
            "wallet_teacher": student.wallet_teacher,
            "wallet_institute": student.wallet_institute,
            "wallet_balance": student.wallet_balance,
            "transactions_total": sum(t.amount or 0 for t in self.db.query(Transaction).all()),
            "sessions_active": self.db.query(SessionLog).filter(SessionLog.is_deleted == False).count(),  # noqa: E712
            "enrollments_active": self.db.query(Enrollment).filter(Enrollment.is_deleted == False).count(),  # noqa: E712
            "course_price": self.db.query(Course).filter(Course.id == self.c_arch.id).first().teacher_session_price,
        }

    def _rows(self):
        return (self.db.query(Enrollment).count(), self.db.query(SessionLog).count(),
                self.db.query(Transaction).count())

    # ------------------------------------------------------------------
    # ۱) دسترسی: فقط ادمین
    # ------------------------------------------------------------------
    def test_1_restore_requires_admin_role(self):
        self.assertEqual(self._restore(self.c_arch.id, token=None).status_code, 401)
        self.assertEqual(self._restore(self.c_arch.id, token="tok-invalid").status_code, 401)
        self.assertEqual(self._restore(self.c_arch.id, token="tok-secretary").status_code, 403)
        self.assertEqual(self._restore(self.c_arch.id, token="tok-teacher").status_code, 403)
        self.assertEqual(self._restore(self.c_arch.id, token="tok-student").status_code, 403)
        # هیچ‌کدام از تلاش‌های بالا نباید وضعیت را تغییر داده باشد
        self.assertTrue(self.db.query(Course).filter(Course.id == self.c_arch.id).first().is_deleted)

    def test_2_branch_isolation(self):
        # مثل نمای آرشیو: ردیف شعبه‌ی دیگر «ناموجود» است (بدون نشت وجود رکورد)
        self.assertEqual(self._restore(self.c_arch_b2.id, token="tok-branch").status_code, 404)
        self.assertTrue(self.db.query(Course).filter(Course.id == self.c_arch_b2.id).first().is_deleted,
                        "کلاس شعبه‌ی دیگر نباید بازیابی شده باشد")
        # ادمین شعبه‌دار کلاس شعبه‌ی خودش را می‌تواند بازیابی کند
        self.assertEqual(self._restore(self.c_arch.id, token="tok-branch").status_code, 200)
        # ادمین کل کلاس شعبه‌ی دیگر را هم می‌تواند
        self.assertEqual(self._restore(self.c_arch_b2.id, token="tok-global").status_code, 200)

    # ------------------------------------------------------------------
    # ۳) کدهای خطای قراردادی
    # ------------------------------------------------------------------
    def test_3_not_found_and_conflict(self):
        self.assertEqual(self._restore(999999).status_code, 404)                 # ناموجود
        self.assertEqual(self._restore(self.c_active.id).status_code, 409)       # از قبل فعال
        self.assertEqual(self._restore(self.c_arch.id).status_code, 200)
        # بار دوم (مثلاً دو ادمین هم‌زمان): 409 پیام دوستانه، بدون بازیابی دوباره
        self.assertEqual(self._restore(self.c_arch.id).status_code, 409)

    def test_4_invalid_mode_is_rejected(self):
        for bad in ("metadata", "", "METADATA_ONLY_FULL"):
            resp = self._restore(self.c_arch.id, mode=bad)
            self.assertIn(resp.status_code, (400, 422), f"mode نامعتبر ({bad!r}) نباید پذیرفته شود")
            self.assertTrue(self.db.query(Course).filter(Course.id == self.c_arch.id).first().is_deleted,
                            "mode نامعتبر نباید کلاس را بازیابی کند")
        # فقط full و metadata_only (سازگاری عقب‌رو) پشتیبانی می‌شوند.
        resp = self._restore(self.c_arch.id, mode="full_restore")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("full", resp.json()["detail"])

    def test_4b_full_mode_restores_operational_history_without_finance(self):
        resp = self._restore(self.c_arch.id, mode="full")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["mode"], "full")
        self.assertTrue(resp.json()["finances_untouched"])
        enrollment = self.db.query(Enrollment).filter(Enrollment.id == self.en_arch.id).first()
        session = self.db.query(SessionLog).filter(SessionLog.course_id == self.c_arch.id).first()
        self.db.refresh(enrollment)
        self.db.refresh(session)
        self.assertFalse(enrollment.is_deleted)
        self.assertFalse(session.is_deleted)

    # ------------------------------------------------------------------
    # ۵) رفتار موفق: کلاس برمی‌گردد، تاریخچه دست‌نخورده
    # ------------------------------------------------------------------
    def test_5_success_returns_class_metadata(self):
        resp = self._restore(self.c_arch.id)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["id"], self.c_arch.id)
        self.assertFalse(body["is_deleted"])
        self.assertEqual(body["mode"], "metadata_only")
        self.assertTrue(body["finances_untouched"])
        self.assertEqual(body["title"], "کلاس آرشیو")
        self.assertNotIn("None", body["title"])
        row = self.db.query(Course).filter(Course.id == self.c_arch.id).first()
        self.db.refresh(row)
        self.assertFalse(row.is_deleted)
        # در لیست آرشیو دیگر دیده نمی‌شود و در جزئیات آرشیو 404 می‌گیرد
        ids = [r["id"] for r in self.client.get("/admin/deleted_classes",
                                                headers={"Authorization": "Bearer tok-global"}).json()]
        self.assertNotIn(self.c_arch.id, ids)
        self.assertEqual(self.client.get(f"/admin/deleted_classes/{self.c_arch.id}",
                                         headers={"Authorization": "Bearer tok-global"}).status_code, 404)

    def test_6_zero_financial_effect(self):
        before = self._financial_fingerprint()
        rows_before = self._rows()
        self.assertEqual(self._restore(self.c_arch.id).status_code, 200)
        after = self._financial_fingerprint()
        self.assertEqual(before, after, "بازیابی متادیتا نباید هیچ عدد مالی را تغییر دهد")
        self.assertEqual(rows_before, self._rows(), "هیچ ردیفی نباید ساخته/حذف شود")

    def test_6b_institute_visible_numbers_unchanged(self):
        """عدد-بیتغییر بودن: گزارش‌هایی که آموزشگاه می‌بیند نباید تغییر کنند (شرط صریح کاربر)."""
        headers = {"Authorization": "Bearer tok-global"}
        endpoints = ["/finance/reports/teacher_settlements_summary", "/reports/debtors",
                     "/finance/reports/revenue_summary"]
        before = {}
        for url in endpoints:
            resp = self.client.get(url, headers=headers)
            self.assertEqual(resp.status_code, 200, f"{url} ⇒ {resp.status_code}")
            before[url] = resp.json()
        self.assertEqual(self._restore(self.c_arch.id).status_code, 200)
        for url in endpoints:
            resp = self.client.get(url, headers=headers)
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json(), before[url], f"بازیابی متادیتا نباید گزارش {url} را تغییر دهد")

    def test_7_archived_history_not_revived(self):
        self.assertEqual(self._restore(self.c_arch.id).status_code, 200)
        en = self.db.query(Enrollment).filter(Enrollment.id == self.en_arch.id).first()
        self.db.refresh(en)
        self.assertTrue(en.is_deleted, "ثبت‌نام آرشیوشده نباید زنده شود")
        self.assertEqual(en.total_paid, 400000, "مبلغ پرداخت‌شده نباید تغییر کند")
        sess = self.db.query(SessionLog).filter(SessionLog.course_id == self.c_arch.id).first()
        self.db.refresh(sess)
        self.assertTrue(sess.is_deleted, "جلسه‌ی آرشیوشده نباید زنده شود (طلب معلم باز نشود)")
        tx = self.db.query(Transaction).filter(Transaction.course_id == self.c_arch.id).first()
        self.db.refresh(tx)
        self.assertFalse(tx.is_deleted)
        self.assertFalse(bool(tx.is_reversed), "تراکنش واقعی نباید برگشت بخورد")

    def test_8_restored_class_visible_again(self):
        headers = {"Authorization": "Bearer tok-global"}
        # پیش از بازیابی: در لیست عادی کلاس‌ها نیست
        before_ids = [c["id"] for c in self.client.get("/classes/list", headers=headers).json()]
        self.assertNotIn(self.c_arch.id, before_ids)

        self.assertEqual(self._restore(self.c_arch.id).status_code, 200)

        resp = self.client.get("/admin/deleted_classes", headers=headers)
        self.assertNotIn(self.c_arch.id, [r["id"] for r in resp.json()])
        after_ids = [c["id"] for c in self.client.get("/classes/list", headers=headers).json()]
        self.assertIn(self.c_arch.id, after_ids, "کلاس بازیابی‌شده باید در /classes/list برگردد")
        # شمارش کلاس‌های فعال: باید شامل کلاس بازیابی‌شده باشد
        active_ids = [c.id for c in self.db.query(Course).filter(Course.is_deleted == False).all()]  # noqa: E712
        self.assertIn(self.c_arch.id, active_ids)

    # ------------------------------------------------------------------
    # ۹) رد پای حسابرسی (actor/reason/pre_state)
    # ------------------------------------------------------------------
    def test_9_audit_trail_written(self):
        self.assertEqual(self._restore(self.c_arch.id, reason="درخواست والدین").status_code, 200)
        log = self.db.query(ClassRestoreLog).filter(ClassRestoreLog.course_id == self.c_arch.id).first()
        self.assertIsNotNone(log, "رد پای بازیابی باید ثبت شود")
        self.assertEqual(log.mode, "metadata_only")
        self.assertEqual(log.reason, "درخواست والدین")
        self.assertEqual(log.actor_user_id, self.global_admin.id)
        self.assertEqual(log.actor_name, "مدیر کل")
        self.assertFalse(log.finance_touched)
        pre = json.loads(log.pre_state_json)
        self.assertTrue(pre["is_deleted"])
        self.assertEqual(pre["archived_enrollments"], 1)
        self.assertEqual(pre["archived_sessions"], 1)
        self.assertEqual(pre["wallet_debit"], 0)
        self.assertIsNotNone(log.restored_at)

    def test_10_reason_is_optional_but_never_faked(self):
        resp = self._restore(self.c_arch.id, reason=None)
        self.assertEqual(resp.status_code, 200)
        log = self.db.query(ClassRestoreLog).filter(ClassRestoreLog.course_id == self.c_arch.id).first()
        self.assertIsNone(log.reason, "نبود دلیل نباید با متن ساختگی پر شود")

    # ------------------------------------------------------------------
    # ۱۱) تعامل با حذف بعدی: آرشیو و بازیابی چندباره سالم بماند
    # ------------------------------------------------------------------
    def test_11_delete_after_restore_works(self):
        self.assertEqual(self._restore(self.c_arch.id).status_code, 200)
        headers = {"Authorization": "Bearer tok-global"}
        resp = self.client.delete(f"/classes/{self.c_arch.id}", headers=headers)
        self.assertIn(resp.status_code, (200, 204), f"حذف دوباره پس از بازیابی: {resp.status_code} {resp.text[:200]}")
        row = self.db.query(Course).filter(Course.id == self.c_arch.id).first()
        self.db.refresh(row)
        self.assertTrue(row.is_deleted, "کلاس پس از حذف دوباره باید آرشیو شود")
        self.assertEqual(self._restore(self.c_arch.id).status_code, 200, "بازیابی دوباره باید ممکن باشد")
        self.assertEqual(self.db.query(ClassRestoreLog).filter(
            ClassRestoreLog.course_id == self.c_arch.id).count(), 2, "هر بازیابی یک رکورد حسابرسی")

    def test_12b_warns_when_teacher_is_archived(self):
        """D5: بازیابی کلاسِ معلم‌آرشیوشده انجام می‌شود ولی ادمین هشدار می‌گیرد."""
        self.db.query(Teacher).filter(Teacher.id == self.teacher.id).update({"is_deleted": True})
        self.db.commit()
        body = self._restore(self.c_arch.id).json()
        self.assertTrue(body["teacher_archived"], "هشدار معلم آرشیوشده باید در پاسخ باشد")
        self.assertTrue(any("معلم" in w for w in body["warnings"]), body["warnings"])

        # کلاس دوم (شعبه ۲) با معلم سالم ⇒ بدون هشدار و بدون متن اضافه
        self.db.query(Teacher).filter(Teacher.id == self.teacher.id).update({"is_deleted": False})
        self.db.commit()
        resp2 = self._restore(self.c_arch_b2.id)
        self.assertEqual(resp2.status_code, 200)
        self.assertFalse(resp2.json()["teacher_archived"])
        self.assertEqual(resp2.json()["warnings"], [])

    def test_12_active_class_is_untouched(self):
        before = (self.c_active.is_deleted, self.c_active.title)
        before_finance = self._financial_fingerprint()
        self.assertEqual(self._restore(self.c_active.id).status_code, 409)
        row = self.db.query(Course).filter(Course.id == self.c_active.id).first()
        self.db.refresh(row)
        self.assertEqual((row.is_deleted, row.title), before)
        self.assertEqual(self._financial_fingerprint(), before_finance)
        self.assertEqual(self.db.query(ClassRestoreLog).count(), 0)

    # ------------------------------------------------------------------
    # O-13 — نمایش هشدارهای بازیابی در اپ ادمین (گارد static؛ اپ اندروید در سندباکس کامپایل نمی‌شود)
    # ------------------------------------------------------------------
    def test_13_android_client_surfaces_restore_warnings(self):
        """سرور `warnings` را برمی‌گرداند (test_12b)، ولی اپ ادمین فقط `message` را Toast می‌کرد
        ⇒ هشدار مهم (مثلاً «کلاس بدون معلم فعال برمی‌گردد») به مدیر نمی‌رسید.

        چون اپ اندروید در این سندباکس کامپایل/اجرا نمی‌شود، قرارداد با اسکن متنی کد کاتلین قفل
        می‌شود: مدل پاسخ باید `warnings` را بگیرد و مسیر بازیابی باید آن را در یک دیالوگ نشان دهد.
        """
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        java_dir = os.path.join(repo_root, "KharazmiAdmin", "app", "src", "main", "java",
                                "com", "example", "kharazmiadmin")
        self.assertTrue(os.path.isdir(java_dir), f"مسیر کد اندروید پیدا نشد: {java_dir}")

        with open(os.path.join(java_dir, "AppModels.kt"), encoding="utf-8") as handle:
            models_src = handle.read()
        # بازیابی از دیالوگ MainActivity به صفحهٔ جزئیات آرشیو منتقل شد (ArchivedClassDetailActivity)
        with open(os.path.join(java_dir, "ArchivedClassDetailActivity.kt"), encoding="utf-8") as handle:
            main_src = handle.read()

        # ۱) مدل پاسخ بازیابی، فیلد warnings را از JSON می‌گیرد (nullable/default ⇒ سازگار با سرور قدیمی)
        self.assertRegex(
            models_src,
            r'@SerializedName\("warnings"\)\s*val\s+warnings\s*:\s*List<String>\?\s*=\s*null',
            "ClassRestoreResponse باید فیلد warnings داشته باشد",
        )

        # ۲) مسیر بازیابی کلاس، warnings را می‌خواند و در دیالوگ به مدیر نشان می‌دهد
        restore_fn = main_src[main_src.index("private fun restoreArchivedClass") :]
        self.assertIn("warnings", restore_fn, "مسیر بازیابی باید warnings را بخواند")
        self.assertIn("AlertDialog", restore_fn,
                      "warnings باید در یک دیالوگ ساده نشان داده شود، نه فقط Toast پیام موفقیت")



if __name__ == "__main__":
    unittest.main()
