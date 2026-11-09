# test_e2e_notifications_push.py
# ═══════════════════════════════════════════════════════════════════════════════
# سناریوی end-to-end #۵: «اعلان‌ها و Push»
#
# مسیر اپ (KharazmiAdmin): ApiInterfaces.kt:46-56
#     GET  notifications            → لیست اعلان‌های کاربر جاری
#     POST notifications/{id}/read  → خوانده‌شده
#     POST notifications/read_all   → همه خوانده شوند
# رویدادهای تولیدکنندهٔ اعلان (از سناریوهای ۲–۴):
#     غیبت شاگرد (attendance/submit_session) · تکلیف/آزمون (homework, exams)
#     نمره (grade) · یادآوری قسط (finance/installments/{id}/remind)
# لایهٔ ارسال سیستمی (Push): NotificationService → push_service.deliver_push → FCM
#
# ⚠ فاز دیباگ: صفر تغییر در کد برنامه.
import datetime
import os
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from dependencies import NotificationService, get_db, hash_password, limiter
from main import app

SERVER_DIR_TOKEN = "tok-admin"


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


class NotificationWorld(unittest.TestCase):
    def setUp(self):
        self._limiter = limiter.enabled
        limiter.enabled = False
        self._fcm = os.environ.pop("FCM_SERVER_KEY", None)
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                               poolclass=StaticPool)
        models.Base.metadata.create_all(engine)
        self.engine = engine
        self.db = sessionmaker(bind=engine, expire_on_commit=False)()
        now = datetime.datetime.now()

        self.db.add(models.Branch(id=1, name="شعبه مرکزی", active=True))
        self.db.add_all([
            models.User(id=101, username="09120000101", password=hash_password("a"), full_name="مدیر",
                        role="admin", sub_role="admin", branch_id=1),
            models.User(id=102, username="09120000102", password=hash_password("b"), full_name="منشی",
                        role="secretary", sub_role="secretary", branch_id=1),
            models.User(id=201, username="student:41", password="x", full_name="علی تست",
                        role="student", sub_role="student", branch_id=1),
            models.User(id=202, username="parent:41", password="x", full_name="ولی علی",
                        role="parent", sub_role="parent", branch_id=1),
            models.User(id=203, username="student:43", password="x", full_name="حسن تست",
                        role="student", sub_role="student", branch_id=1),
        ])
        self.db.add(models.Teacher(id=51, first_name="مریم", last_name="معلم", mobile="09120000103",
                                   national_code="0012348001", password=hash_password("t"),
                                   is_approved=True, is_deleted=False, branch_id=1))
        self.db.add(models.Student(id=41, student_code=41, first_name="علی", last_name="تست",
                                   national_code="0012348002", student_mobile="09120000104",
                                   parent_mobile="09120000105", branch_id=1,
                                   wallet_teacher=0, wallet_institute=0, wallet_balance=0,
                                   user_id=201, parent_user_id=202, is_deleted=False))
        self.db.add(models.Course(id=71, title="ریاضی دهم", code="700001", teacher_id=51, branch_id=1,
                                  is_deleted=False, grade_level="دهم", days_of_week="شنبه",
                                  class_time="17:30", teacher_session_price=100000))
        self.db.add(models.Enrollment(id=1, student_id=41, course_id=71, branch_id=1,
                                      register_date="1405/06/01", shift="عصر",
                                      total_tuition=1000000, total_paid=0, is_deleted=False))
        self.db.add_all([
            models.UserSession(token="tok-admin", user_id=101, sub_role="admin", created_at=now),
            models.UserSession(token="tok-secretary", user_id=102, sub_role="secretary", created_at=now),
            models.UserSession(token="tok-teacher", user_id=51, teacher_id=51, sub_role="teacher",
                               created_at=now),
            models.UserSession(token="tok-student", user_id=201, sub_role="student", created_at=now),
            models.UserSession(token="tok-parent", user_id=202, sub_role="parent", created_at=now),
        ])
        self.db.commit()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        limiter.enabled = self._limiter
        if self._fcm:
            os.environ["FCM_SERVER_KEY"] = self._fcm
        self.db.close()
        self.engine.dispose()

    def notify(self, **kw):
        kw.setdefault("recipient_user_id", 201)
        kw.setdefault("recipient_role", "student")
        kw.setdefault("type", "general")
        kw.setdefault("title", "عنوان")
        kw.setdefault("body", "متن پیام")
        return NotificationService.send_notification(db=self.db, **kw)


class TestNotificationInbox(NotificationWorld):
    def test_1_absence_creates_parent_notification_and_sms_row(self):
        """> زنجیرهٔ واقعی: ثبت جلسه با غیبت ⇒ اعلان ولی + پیامک."""
        self.db.add(models.InstituteShare(id=1, count_1=50000))
        self.db.commit()
        resp = self.client.post("/attendance/submit_session",
                                json={"course_id": 71, "date": "1405/06/30",
                                      "items": [{"student_id": 41, "status": "Absent", "excused": False}]},
                                headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        notes = self.db.query(models.Notification).filter(
            models.Notification.recipient_user_id == 202,
            models.Notification.recipient_role == "parent").all()
        self.assertEqual(len(notes), 1, "ولی باید اعلان غیبت بگیرد")
        self.assertEqual(notes[0].type, "attendance")
        sms = self.db.query(models.SmsLog).filter(models.SmsLog.message_text.like("%غیبت%")).first()
        self.assertIsNotNone(sms, "اعلان‌های attendance باید پیامک هم ثبت کنند")

    def test_2_inbox_is_scoped_to_the_current_user_and_role(self):
        self.notify(title="اعلان شاگرد ۴۱")
        self.notify(recipient_user_id=203, recipient_role="student", title="اعلان شاگرد ۴۳")
        self.notify(recipient_user_id=101, recipient_role="admin", title="اعلان مدیر")

        student_inbox = self.client.get("/notifications", headers=hdr("tok-student"))
        self.assertEqual(student_inbox.status_code, 200, student_inbox.text)
        titles = [n["title"] for n in student_inbox.json()]
        self.assertEqual(titles, ["اعلان شاگرد ۴۱"], "شاگرد فقط اعلان خودش را می‌بیند")

        admin_inbox = self.client.get("/notifications", headers=hdr("tok-admin"))
        self.assertEqual([n["title"] for n in admin_inbox.json()], ["اعلان مدیر"])

        self.assertEqual(self.client.get("/notifications").status_code, 401,
                         "بدون توکن ⇒ ۴۰۱")

    def test_3_unread_count_matches_inbox(self):
        self.notify(title="الف")
        self.notify(title="ب")
        n = self.notify(title="ج")
        n.is_read = True
        self.db.commit()
        resp = self.client.get("/notifications/unread_count", headers=hdr("tok-student"))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json(), {"unread": 2, "total": 3})

    def test_4_mark_read_is_scoped_and_idempotent(self):
        mine = self.notify(title="مال من")
        theirs = self.notify(recipient_user_id=203, recipient_role="student", title="مال دیگری")

        first = self.client.post(f"/notifications/{mine.id}/read", headers=hdr("tok-student"))
        self.assertEqual(first.status_code, 200, first.text)
        self.db.refresh(mine)
        self.assertTrue(bool(mine.is_read))

        again = self.client.post(f"/notifications/{mine.id}/read", headers=hdr("tok-student"))
        self.assertEqual(again.status_code, 200, "خواندن دوباره باید بی‌خطر باشد")

        steal = self.client.post(f"/notifications/{theirs.id}/read", headers=hdr("tok-student"))
        self.assertEqual(steal.status_code, 404, "اعلان کاربر دیگر اصلاً دیده/تغییر نمی‌شود")
        self.db.refresh(theirs)
        self.assertFalse(bool(theirs.is_read))

    def test_5_read_all_only_touches_own_role_rows(self):
        self.notify(title="۱")
        self.notify(title="۲")
        other = self.notify(recipient_user_id=203, recipient_role="student", title="دیگری")
        resp = self.client.post("/notifications/read_all", headers=hdr("tok-student"))
        self.assertEqual(resp.status_code, 200, resp.text)
        mine = self.db.query(models.Notification).filter(
            models.Notification.recipient_user_id == 201).all()
        self.assertTrue(all(bool(n.is_read) for n in mine))
        self.db.refresh(other)
        self.assertFalse(bool(other.is_read), "اعلان کاربر دیگر خوانده نمی‌شود")

    def test_6_duplicate_notification_within_10s_is_deduplicated(self):
        first = self.notify(title="تکرار", body="همان متن")
        second = self.notify(title="تکرار", body="همان متن")
        self.assertEqual(first.id, second.id, "متن یکسان در ۱۰ ثانیه ⇒ یک اعلان")
        self.assertEqual(self.db.query(models.Notification).count(), 1)


class TestPushDelivery(NotificationWorld):
    def test_7_without_fcm_key_push_is_skipped_and_tokens_kept(self):
        """گارد محیطی C2: بدون `FCM_SERVER_KEY` هیچ ارسال شبکه‌ای و هیچ حذف توکنی نداریم."""
        self.db.add(models.DeviceToken(id=1, user_id=201, role="student", token="dev-a"))
        self.db.commit()
        from push_service import deliver_push, fcm_configured
        self.assertFalse(fcm_configured())
        result = deliver_push(self.db, self.db.query(models.DeviceToken).all(),
                              title="t", body="b", sender=lambda *a: {"success": 1})
        self.assertTrue(result.skipped)
        self.assertEqual(result.skipped_reason, "fcm_not_configured")
        self.assertEqual(result.attempted, 0, "بدون اعتبارنامه، حتی با sender تزریقی ارسال نمی‌شود")
        self.assertEqual(self.db.query(models.DeviceToken).count(), 1)

    def test_8_notification_flow_reaches_push_layer_when_configured(self):
        """با تنظیم کلید محیطی، اعلان به لایهٔ Push می‌رسد و توکن نامعتبر پاک می‌شود."""
        import push_service
        os.environ["FCM_SERVER_KEY"] = "test-key"
        sent = {}

        def fake_sender(tokens, title, body, data):
            sent["tokens"] = list(tokens)
            sent["title"] = title
            return {"results": [{"error": "NotRegistered"}, {}]}

        push_service.set_sender_override(fake_sender)
        self.db.add_all([
            models.DeviceToken(id=1, user_id=201, role="student", token="bad-token"),
            models.DeviceToken(id=2, user_id=201, role="student", token="good-token"),
        ])
        self.db.commit()
        try:
            self.notify(title="اعلان با پوش", body="متن")
        finally:
            push_service.set_sender_override(None)

        self.assertEqual(sorted(sent["tokens"]), ["bad-token", "good-token"])
        self.assertEqual(sent["title"], "اعلان با پوش")
        remaining = [t.token for t in self.db.query(models.DeviceToken).all()]
        self.assertEqual(remaining, ["good-token"],
                         "توکن NotRegistered باید از دیتابیس پاک شود (خدمات FCM استاندارد)")
        note = self.db.query(models.Notification).first()
        self.assertIsNotNone(note, "اعلان درون‌برنامه‌ای حتی با شکست Push ثبت می‌شود")

    def test_9_push_failure_never_breaks_notification_save(self):
        import push_service
        os.environ["FCM_SERVER_KEY"] = "test-key"

        def exploding_sender(tokens, title, body, data):
            raise RuntimeError("شبکه قطع است")

        push_service.set_sender_override(exploding_sender)
        self.db.add(models.DeviceToken(id=9, user_id=201, role="student", token="dev-x"))
        self.db.commit()
        try:
            note = self.notify(title="با خطای شبکه", body="متن")
        finally:
            push_service.set_sender_override(None)
        self.assertIsNotNone(note.id, "اعلان باید ذخیره شود حتی وقتی Push می‌شکند")
        self.assertEqual(self.db.query(models.DeviceToken).count(), 1)

    def test_10_reminder_and_payment_notifications_write_sms_logs(self):
        inst = self.client.post("/finance/installments",
                                json={"enrollment_id": 1, "amount": 300000, "due_date": "1405/07/15"},
                                headers=hdr("tok-admin")).json()
        self.assertEqual(self.client.post(f"/finance/installments/{inst['installment_id']}/remind",
                                          headers=hdr("tok-admin")).status_code, 200)
        types = {n.type for n in self.db.query(models.Notification).all()}
        self.assertTrue(types & {"installment", "payment", "general"}, types)
        self.assertGreaterEqual(self.db.query(models.SmsLog).count(), 1,
                                "یادآوری مالی باید پیامک هم بسازد")

    def test_11_push_status_endpoint_tells_admin_whether_push_can_work(self):
        """O-15: مدیر باید از خود API بفهمد «چرا Push نمی‌رسد» — بدون دست‌زدن به کلید.

        قرارداد `GET /dashboard/push_status` (ادمین‌فقط):
            {"fcm_configured": bool, "device_token_count": int}
        نکتهٔ امنیتی: خودِ کلید FCM هرگز در پاسخ نمی‌آید؛ فقط «تنظیم است / نیست».
        """
        self.db.add_all([
            models.DeviceToken(id=1, user_id=201, role="student", token="dev-1"),
            models.DeviceToken(id=2, user_id=51, role="teacher", token="dev-2"),
        ])
        self.db.commit()

        # ۱) بدون اعتبارنامه: باید صریحاً False بدهد و تعداد واقعی توکن‌های ثبت‌شده را بگوید
        resp = self.client.get("/dashboard/push_status", headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json(), {"fcm_configured": False, "device_token_count": 2})

        # ۲) با اعتبارنامه: فقط «تنظیم است» گزارش می‌شود و کلید لو نمی‌رود
        secret = "AAA:super-secret-fcm-key"
        os.environ["FCM_SERVER_KEY"] = secret
        try:
            configured = self.client.get("/dashboard/push_status", headers=hdr("tok-admin"))
        finally:
            os.environ.pop("FCM_SERVER_KEY", None)
        self.assertEqual(configured.status_code, 200, configured.text)
        self.assertTrue(configured.json()["fcm_configured"])
        self.assertNotIn(secret, configured.text, "کلید FCM نباید در پاسخ بیاید")

        # ۳) ادمین‌فقط: منشی/معلم/شاگرد ⇒ ۴۰۳ · بدون توکن ⇒ ۴۰۱
        # نکته: ۴۰۳ برای نقش غیرادمین با سشن معتبر (منشی/شاگرد) و ۴۰۱ وقتی سشن/کاربر معتبر نیست
        # (در این دنیای آزمایشی سشن معلم به کاربر بدون رکورد User وصل است ⇒ بی‌اعتبار).
        for tok in ("tok-secretary", "tok-teacher", "tok-student"):
            status = self.client.get("/dashboard/push_status", headers=hdr(tok)).status_code
            self.assertIn(status, (401, 403), f"{tok} نباید وضعیت Push را ببیند (status={status})")
        self.assertEqual(self.client.get("/dashboard/push_status").status_code, 401)



if __name__ == "__main__":
    unittest.main()
