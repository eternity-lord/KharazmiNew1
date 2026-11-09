# test_class_deletion_paths_consistency.py
# تست‌های A2 — یکدستی سه مسیر حذف کلاس
#
# باگی که این تست‌ها قفل می‌کنند:
#   مسیر سومِ حذف کلاس (`DELETE /admin/reject_class/{course_id}` — همان دکمه‌ی «رد کلاس» در
#   اپ، صفحهٔ کلاس‌های در انتظار تایید) فقط ثبت‌نام‌ها را آرشیو می‌کرد و **جلسات را
#   دست‌نخورده می‌گذاشت** و هیچ رکورد حذفی هم نمی‌ساخت. نتیجه:
#     • طلب معلم از کلاسی که دیگر وجود ندارد در «طلب تسویه‌نشده» باز می‌ماند
#       (پرداخت برای کلاس ناموجود)،
#     • تاریخ و عامل حذف گم می‌شود (نمای آرشیو: deleted_at خالی).
#   حالا هر سه مسیر باید اثر یکسان بگذارند: آرشیو کلاس + ثبت‌نام‌ها + جلسات + رکورد حسابرسی.
#
# اجرا (از ریشهٔ ریپو — روش مستند پروژه):
#   DATABASE_URL=sqlite:////tmp/a2_paths.db JWT_SECRET_KEY=<hex> \
#     python3 -m pytest Kharazmi_Server/test_class_deletion_paths_consistency.py -q
import datetime
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from dependencies import get_db
from main import app


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


class BaseDeletionWorld(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                               poolclass=StaticPool)
        models.Base.metadata.create_all(engine)
        self.engine = engine
        Session = sessionmaker(bind=engine, expire_on_commit=False)
        self.db = Session()
        now = datetime.datetime.now()
        self.db.add_all([
            models.Branch(id=1, name="شعبه", active=True),
            models.Teacher(id=1, first_name="معلم", last_name="الف", mobile="09120000001",
                           national_code="0012345678", password="x", is_approved=True, is_deleted=False),
            models.Student(id=1, student_code=1, first_name="شاگرد", last_name="یک",
                           national_code="0012345681", student_mobile="09121111111",
                           wallet_teacher=0, wallet_institute=0, wallet_balance=0, is_deleted=False),
            models.User(id=1, username="admin-1", password="x", full_name="مدیر مرکزی", role="admin",
                        sub_role="admin", branch_id=None),
            models.User(id=2, username="teacher-1", password="x", full_name="معلم", role="teacher",
                        sub_role="teacher", branch_id=None),
            models.User(id=3, username="sec-1", password="x", full_name="منشی", role="admin",
                        sub_role="secretary", branch_id=1),
        ])
        for uid, tok, role in [(1, "tok-admin", "admin"), (2, "tok-teacher", "teacher"),
                               (3, "tok-secretary", "secretary")]:
            self.db.add(models.UserSession(token=tok, user_id=uid, sub_role=role, created_at=now))
        self.db.commit()
        self.next_id = 100

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    # ---------- کارخانهٔ داده ----------
    def make_class(self, with_sessions=True, with_enrollment=True, approved=False):
        self.next_id += 1
        cid = self.next_id
        self.db.add(models.Course(id=cid, title=f"کلاس {cid}", code=f"A2-{cid}", teacher_id=1, branch_id=1,
                                  grade_level="دهم", class_time="16:00-17:30", days_of_week="شنبه",
                                  teacher_session_price=100000, is_deleted=False,
                                  is_admin_approved=approved, is_suspended=False))
        self.db.commit()
        if with_enrollment:
            self.db.add(models.Enrollment(id=cid * 10 + 1, student_id=1, course_id=cid, branch_id=1,
                                          register_date="1405/06/01", shift="عصر",
                                          total_tuition=2000000, total_paid=500000, is_deleted=False))
            self.db.add(models.Installment(id=cid * 10 + 1, enrollment_id=cid * 10 + 1, amount=700000,
                                           due_date="1405/07/01", is_paid=False, is_deleted=False))
            self.db.commit()
        if with_sessions:
            for i, day in enumerate(["1405/06/02", "1405/06/05"]):
                sid = cid * 10 + 2 + i
                self.db.add(models.SessionLog(id=sid, course_id=cid, date=day, time="16:00",
                                              final_teacher_cost=100000, final_institute_share=50000,
                                              cost_per_student=150000, attendee_count=1,
                                              status="Finished", is_deleted=False))
                self.db.add(models.Attendance(id=sid, session_id=sid, student_id=1, status="Present",
                                              is_billed=False, is_deleted=False))
                # هزینه‌ی جلسه با سهم معلم/آموزشگاه — همان ردیفی که هنگام ثبت جلسه ساخته می‌شود
                # و حذف کلاس آن را آرشیو و کیف پول شاگرد را بستانکار می‌کند.
                self.db.add(models.Transaction(id=cid * 100 + i, student_id=1, course_id=cid, branch_id=1,
                                               enrollment_id=cid * 10 + 1, session_id=sid,
                                               amount=150000, type="session_charge", date=day,
                                               description="هزینه جلسه", share_teacher=100000,
                                               share_institute=50000, is_deleted=False, is_reversed=False))
            self.db.add(models.Transaction(id=cid * 10 + 1, student_id=1, course_id=cid, branch_id=1,
                                           enrollment_id=cid * 10 + 1, amount=500000, type="tuition",
                                           date="1405/06/01", description="شهریه",
                                           is_deleted=False, is_reversed=False))
            self.db.commit()
        return cid

    # ---------- سنجه‌ها ----------
    def snapshot(self, cid):
        self.db.expire_all()
        course = self.db.query(models.Course).filter(models.Course.id == cid).first()
        enrollments = self.db.query(models.Enrollment).filter(models.Enrollment.course_id == cid).all()
        sessions = self.db.query(models.SessionLog).filter(models.SessionLog.course_id == cid).all()
        installments = self.db.query(models.Installment).filter(
            models.Installment.enrollment_id.in_([e.id for e in enrollments] or [0])).all()
        tuition = self.db.query(models.Transaction).filter(
            models.Transaction.course_id == cid, models.Transaction.type == "tuition").all()
        records = self.db.query(models.ClassDeletionRequest).filter(
            models.ClassDeletionRequest.course_id == cid).all()
        return {
            "course_deleted": bool(course.is_deleted) if course else None,
            "enrollments_deleted": all(bool(e.is_deleted) for e in enrollments) if enrollments else None,
            "sessions_deleted": all(bool(s.is_deleted) for s in sessions) if sessions else None,
            "sessions_count": len(sessions),
            "installments_deleted": all(bool(i.is_deleted) for i in installments) if installments else None,
            "tuition_preserved": all(not bool(t.is_deleted) for t in tuition) if tuition else None,
            "deletion_records": len(records),
            "record_status": records[0].status if records else None,
            "record_actor": records[0].decided_by_user_id if records else None,
            "record_has_snapshot": bool(records[0].snapshot_json) if records else False,
            "forgive_flag": records[0].forgive_session_charges if records else None,
        }

    def teacher_pending(self, token="tok-admin"):
        r = self.client.get("/teachers/1/pending_settlement", headers=hdr(token))
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def archived_ids(self, token="tok-admin"):
        r = self.client.get("/admin/deleted_classes", headers=hdr(token))
        self.assertEqual(r.status_code, 200, r.text)
        return [row["id"] for row in r.json()]


class TestRejectClassPathIsConsistent(BaseDeletionWorld):
    """مسیر سوم (reject_class) — هستهٔ فیکس A2."""

    def test_sessions_are_archived_so_teacher_pending_closes(self):
        cid = self.make_class()
        before = self.teacher_pending()
        self.assertGreaterEqual(before["total_amount"], 200000, before)  # ۲ جلسه × ۱۰۰٬۰۰۰

        r = self.client.delete(f"/admin/reject_class/{cid}", headers=hdr("tok-admin"))
        self.assertEqual(r.status_code, 200, r.text)

        snap = self.snapshot(cid)
        self.assertTrue(snap["course_deleted"])
        self.assertTrue(snap["sessions_deleted"],
                        "جلسات کلاس رد‌شده باید آرشیو شوند (قبلاً دست‌نخورده می‌ماندند)")
        self.assertTrue(snap["enrollments_deleted"])
        self.assertTrue(snap["installments_deleted"])
        self.assertTrue(snap["tuition_preserved"], "وجه واقعی دریافتی نباید آرشیو شود (سیاست Bug 13)")

        after = self.teacher_pending()
        self.assertEqual(after["total_amount"], before["total_amount"] - 200000,
                         "طلب معلم از کلاس حذف‌شده نباید باز بماند")
        # و کلاس حذف‌شده در هیچ‌کدام از ردیف‌های pending نباشد
        self.assertNotIn(cid, [row.get("course_id") for row in after["pending_sessions"]])

    def test_deletion_record_is_created_with_actor_and_snapshot(self):
        cid = self.make_class()
        r = self.client.delete(f"/admin/reject_class/{cid}", headers=hdr("tok-admin"))
        self.assertEqual(r.status_code, 200, r.text)
        snap = self.snapshot(cid)
        self.assertEqual(snap["deletion_records"], 1, "باید یک رکورد حذف ثبت شود")
        self.assertEqual(snap["record_status"], "approved")
        self.assertEqual(snap["record_actor"], 1, "عامل حذف باید کاربر واقعی درخواست باشد")
        self.assertTrue(snap["record_has_snapshot"], "snapshot باید ذخیره شود")
        self.assertTrue(snap["forgive_flag"])

    def test_archive_view_shows_deletion_date(self):
        cid = self.make_class()
        self.assertEqual(self.client.delete(f"/admin/reject_class/{cid}",
                                            headers=hdr("tok-admin")).status_code, 200)
        r = self.client.get("/admin/deleted_classes", headers=hdr("tok-admin"))
        row = [x for x in r.json() if x["id"] == cid]
        self.assertTrue(row, "کلاس باید در آرشیو دیده شود")
        self.assertNotEqual(row[0]["deleted_at"], "", "تاریخ حذف نباید خالی بماند")

    def test_repeat_call_is_idempotent_and_creates_no_duplicate_record(self):
        cid = self.make_class()
        self.assertEqual(self.client.delete(f"/admin/reject_class/{cid}",
                                            headers=hdr("tok-admin")).status_code, 200)
        self.assertEqual(self.client.delete(f"/admin/reject_class/{cid}",
                                            headers=hdr("tok-admin")).status_code, 200,
                         "فراخوانی دوباره باید مثل قبل ۲۰۰ بماند (سازگاری با اپ)")
        snap = self.snapshot(cid)
        self.assertEqual(snap["deletion_records"], 1, "نباید رکورد حذف تکراری ساخته شود")

    def test_returns_404_for_unknown_class(self):
        r = self.client.delete("/admin/reject_class/999999", headers=hdr("tok-admin"))
        self.assertEqual(r.status_code, 404)

    def test_permissions(self):
        cid = self.make_class()
        self.assertEqual(self.client.delete(f"/admin/reject_class/{cid}").status_code, 401)
        self.assertEqual(self.client.delete(f"/admin/reject_class/{cid}",
                                            headers=hdr("tok-teacher")).status_code, 403)
        self.assertEqual(self.client.delete(f"/admin/reject_class/{cid}",
                                            headers=hdr("tok-secretary")).status_code, 403)


class TestAllThreePathsAreEquivalent(BaseDeletionWorld):
    """سه مسیر حذف باید اثر یکسان بگذارند (هدف اصلی A2)."""

    def _expected_effects(self):
        return {
            "course_deleted": True,
            "enrollments_deleted": True,
            "sessions_deleted": True,
            "installments_deleted": True,
            "tuition_preserved": True,
            "deletion_records": 1,
            "record_status": "approved",
            "record_has_snapshot": True,
        }

    def _assert_effects(self, snap):
        for key, expected in self._expected_effects().items():
            self.assertEqual(snap[key], expected, f"{key}: {snap[key]} != {expected}")

    def test_path_1_admin_direct_delete(self):
        cid = self.make_class()
        r = self.client.delete(f"/classes/{cid}", params={"forgive_session_charges": "true"},
                               headers=hdr("tok-admin"))
        self.assertEqual(r.status_code, 200, r.text)
        self._assert_effects(self.snapshot(cid))

    def test_path_2_approved_deletion_request(self):
        cid = self.make_class()
        r = self.client.post(f"/classes/{cid}/request_delete",
                             json={"forgive_session_charges": True}, headers=hdr("tok-secretary"))
        self.assertEqual(r.status_code, 200, r.text)
        req_id = r.json()["request_id"]
        r = self.client.post(f"/classes/deletion_requests/{req_id}/approve", headers=hdr("tok-admin"))
        self.assertEqual(r.status_code, 200, r.text)
        self._assert_effects(self.snapshot(cid))

    def test_path_3_reject_class(self):
        cid = self.make_class()
        r = self.client.delete(f"/admin/reject_class/{cid}", headers=hdr("tok-admin"))
        self.assertEqual(r.status_code, 200, r.text)
        self._assert_effects(self.snapshot(cid))

    def test_all_paths_leave_same_teacher_pending(self):
        """هر سه مسیر باید کلاس را از طلب معلم خارج کنند (اثر مالی یکسان)."""
        results = []
        for deleter in (
            lambda cid: self.client.delete(f"/classes/{cid}", params={"forgive_session_charges": "true"},
                                           headers=hdr("tok-admin")),
            lambda cid: self.client.delete(f"/admin/reject_class/{cid}", headers=hdr("tok-admin")),
        ):
            base = self.teacher_pending()["total_amount"]
            cid = self.make_class()
            with_class = self.teacher_pending()["total_amount"]
            self.assertEqual(deleter(cid).status_code, 200)
            results.append((base, with_class, self.teacher_pending()["total_amount"]))
        for base, with_class, after in results:
            self.assertEqual(with_class - base, 200000)
            self.assertEqual(after, base, "پس از حذف، طلب باید به حالت پایه برگردد")


class TestPath3DoesNotBreakOtherBehavior(BaseDeletionWorld):
    """مسیر سوم نباید بقیهٔ رفتارها را بشکند."""

    def test_class_without_sessions_or_enrollments(self):
        cid = self.make_class(with_sessions=False, with_enrollment=False)
        r = self.client.delete(f"/admin/reject_class/{cid}", headers=hdr("tok-admin"))
        self.assertEqual(r.status_code, 200, r.text)
        snap = self.snapshot(cid)
        self.assertTrue(snap["course_deleted"])
        self.assertEqual(snap["deletion_records"], 1)

    def test_rejecting_pending_class_flow(self):
        """فلوی واقعی اپ: کلاس در انتظار تایید ⇒ رد."""
        cid = self.make_class(approved=False)
        r = self.client.delete(f"/admin/reject_class/{cid}", headers=hdr("tok-admin"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["message"], "کلاس رد و حذف شد و ترازهای مالی اصلاح گردید.",
                         "متن پاسخ باید برای اپ بدون تغییر بماند")
        self.assertIn(cid, self.archived_ids())
        # و از لیست فعال حذف شده باشد
        active = self.client.get("/classes/list", headers=hdr("tok-admin"))
        self.assertEqual(active.status_code, 200)
        self.assertNotIn(cid, [c.get("id") for c in active.json()])

    def test_wallet_credit_behavior_unchanged(self):
        """سیاست قدیمی این مسیر: بستانکار کردن کیف پول شاگرد (forgive=True) دست‌نخورده بماند.

        دو جلسه، هرکدام با سهم معلم ۱۰۰٬۰۰۰ و سهم آموزشگاه ۵۰٬۰۰۰ ⇒ مجموع ۳۰۰٬۰۰۰ به کیف پول
        شاگرد برمی‌گردد. این رفتار **قبل و بعد از فیکس A2 یکسان** است (فیکس فقط آرشیو جلسات و
        رکورد حسابرسی را اضافه کرد، نه حرکت پول).
        """
        cid = self.make_class()
        self.client.delete(f"/admin/reject_class/{cid}", headers=hdr("tok-admin"))
        self.db.expire_all()
        st = self.db.query(models.Student).filter(models.Student.id == 1).first()
        self.assertEqual(st.wallet_teacher, 200000, "بستانکاری کیف پول معلم طبق رفتار قبلی")
        self.assertEqual(st.wallet_institute, 100000)
        self.assertEqual(st.wallet_balance, 300000, "wallet_balance باید با جمع دو کیف هم‌سان باشد")
        # جمع بستانکاری باید دقیقاً معادل سهم تراکنش‌های آرشیوشده‌ی session_charge باشد
        archived = self.db.query(models.Transaction).filter(
            models.Transaction.course_id == cid,
            models.Transaction.type == "session_charge").all()
        self.assertTrue(all(t.is_deleted for t in archived), "هزینه‌ی جلسات باید آرشیو شود")
        self.assertEqual(sum(t.share_teacher or 0 for t in archived), st.wallet_teacher)


if __name__ == "__main__":
    unittest.main()
