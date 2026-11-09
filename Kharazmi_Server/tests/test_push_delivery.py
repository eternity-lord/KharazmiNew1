# test_push_delivery.py
# تست‌های C2 — ارسال واقعی اعلان سیستمی (Push/FCM) با گارد محیطی
#
# باگی که این تست‌ها قفل می‌کنند:
#   در `dependencies.NotificationService.send_notification` یک حلقهٔ **خالی** بود:
#       device_tokens = db.query(DeviceToken).filter(...).all()
#       for token_record in device_tokens:
#           pass
#   ⇒ هیچ Push ای هرگز ارسال نمی‌شد. اعلان فقط در جدول ذخیره می‌شد و کاربری که اپ را باز
#   نمی‌کرد (آفلاین) از پرداخت فرزند، قسط معوق، غیبت و پیام‌ها بی‌خبر می‌ماند — یعنی مهم‌ترین
#   کارکرد اعلان در آموزشگاه (یادآوری بدهی و غیبت) عملاً غیرفعال بود.
#
# قرارداد C2:
#   • گارد محیطی: بدون `FCM_SERVER_KEY` هیچ درخواست شبکه‌ای زده نمی‌شود (فقط لاگ شفاف).
#   • با اعتبارنامه: توکن‌ها دسته‌ای (۱۰۰ تایی) ارسال می‌شوند.
#   • توکن نامعتبر (NotRegistered/InvalidRegistration/MismatchSenderId) از DB پاک می‌شود.
#   • شکست ارسال هرگز ثبت اعلان/تراکنش را نمی‌شکند.
#   • تست‌ها با sender تزریقی کار می‌کنند و **هیچ درخواست شبکه‌ای واقعی** نمی‌زنند.
#
# اجرا (از ریشهٔ ریپو):
#   DATABASE_URL=sqlite:////tmp/c2_push.db JWT_SECRET_KEY=<hex> \
#     python3 -m pytest Kharazmi_Server/test_push_delivery.py -q
import datetime
import os
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
import push_service
from dependencies import NotificationService
from push_service import PushResult, deliver_push


class PushWorld(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                               poolclass=StaticPool)
        models.Base.metadata.create_all(engine)
        self.engine = engine
        Session = sessionmaker(bind=engine, expire_on_commit=False)
        self.db = Session()
        self.db.add_all([
            models.User(id=1, username="student:1", password="x", full_name="شاگرد",
                        role="student", sub_role="student", branch_id=1),
            models.DeviceToken(id=1, user_id=1, role="student", token="tok-valid-1"),
            models.DeviceToken(id=2, user_id=1, role="student", token="tok-valid-2"),
            models.DeviceToken(id=3, user_id=1, role="student", token="tok-dead"),
        ])
        self.db.commit()
        self._prev_key = os.environ.pop(push_service.ENV_FCM_KEY, None)
        push_service.set_sender_override(None)
        self.calls = []

    def tearDown(self):
        push_service.set_sender_override(None)
        if self._prev_key is not None:
            os.environ[push_service.ENV_FCM_KEY] = self._prev_key
        else:
            os.environ.pop(push_service.ENV_FCM_KEY, None)
        self.db.close()
        self.engine.dispose()

    def tokens(self, only_valid=False):
        q = self.db.query(models.DeviceToken)
        if only_valid:
            q = q.filter(models.DeviceToken.token != "tok-dead")
        return q.all()

    def fake_sender(self, dead_tokens=("tok-dead",)):
        """sender تست: توکن‌های menیِ dead را NotRegistered برمی‌گرداند."""
        def _send(batch, title, body, data):
            self.calls.append({"tokens": list(batch), "title": title, "body": body, "data": data})
            results = []
            for token in batch:
                if token in dead_tokens:
                    results.append({"error": "NotRegistered"})
                else:
                    results.append({"message_id": f"m-{token}"})
            return {"multicast_id": 1, "success": len(batch) - len([t for t in batch if t in dead_tokens]),
                    "failure": len([t for t in batch if t in dead_tokens]), "results": results}
        return _send


class TestEnvironmentGuard(PushWorld):
    def test_not_configured_without_env_key(self):
        self.assertFalse(push_service.fcm_configured())

    def test_no_network_call_when_not_configured(self):
        """گارد محیطی: بدون اعتبارنامه نباید هیچ درخواستی زده شود — حتی با توکن موجود."""
        import push_service as ps

        def boom(*args, **kwargs):  # اگر قفل گارد باز شود، این تست شکست می‌خورد
            raise AssertionError("درخواست شبکه‌ای واقعی در حالت بدون اعتبارنامه زده شد!")

        original = ps.requests
        ps.requests = type("Stub", (), {"post": staticmethod(boom)})()
        try:
            result = deliver_push(self.db, self.tokens(), title="t", body="b")
        finally:
            ps.requests = original
        self.assertTrue(result.skipped)
        self.assertEqual(result.skipped_reason, "fcm_not_configured")
        self.assertEqual(result.sent, 0)
        self.assertEqual(self.db.query(models.DeviceToken).count(), 3, "بدون ارسال، توکنی پاک نمی‌شود")

    def test_no_tokens_means_no_work(self):
        result = deliver_push(self.db, [], title="t", body="b")
        self.assertTrue(result.skipped)
        self.assertEqual(result.skipped_reason, "no_device_tokens")

    def test_guard_allows_sending_when_key_present(self):
        os.environ[push_service.ENV_FCM_KEY] = "test-server-key"
        self.assertTrue(push_service.fcm_configured())
        result = deliver_push(self.db, self.tokens(), title="ت", body="م",
                              sender=self.fake_sender(dead_tokens=()))
        self.assertFalse(result.skipped)
        self.assertEqual(result.sent, 3)
        self.assertEqual(len(self.calls), 1)


class TestDelivery(PushWorld):
    def setUp(self):
        super().setUp()
        os.environ[push_service.ENV_FCM_KEY] = "test-server-key"

    def test_payload_contains_tokens_title_body_and_data(self):
        result = deliver_push(self.db, self.tokens(only_valid=True), title="⚠️ قسط معوق",
                              body="قسط فرزند شما سررسید شده است.", data={"type": "installment", "notification_id": 7},
                              sender=self.fake_sender())
        self.assertEqual(result.sent, 2)
        call = self.calls[0]
        self.assertEqual(sorted(call["tokens"]), ["tok-valid-1", "tok-valid-2"])
        self.assertEqual(call["title"], "⚠️ قسط معوق")
        self.assertIn("سررسید", call["body"])
        self.assertEqual(call["data"]["type"], "installment")

    def test_invalid_token_is_removed_from_db(self):
        result = deliver_push(self.db, self.tokens(), title="t", body="b", sender=self.fake_sender())
        self.assertEqual(result.attempted, 3)
        self.assertEqual(result.sent, 2)
        self.assertEqual(result.failed, 1)
        self.assertEqual(result.invalid_tokens, ["tok-dead"])
        remaining = [row.token for row in self.db.query(models.DeviceToken).all()]
        self.assertEqual(sorted(remaining), ["tok-valid-1", "tok-valid-2"])
        self.assertIsNone(self.db.query(models.DeviceToken).filter(models.DeviceToken.token == "tok-dead").first())

    def test_sender_exception_is_swallowed(self):
        def failing(batch, title, body, data):
            raise TimeoutError("network down")

        result = deliver_push(self.db, self.tokens(), title="t", body="b", sender=failing)
        self.assertEqual(result.failed, 3)
        self.assertEqual(result.sent, 0)
        self.assertTrue(result.errors)
        self.assertEqual(self.db.query(models.DeviceToken).count(), 3, "خطای شبکه نباید توکن پاک کند")

    def test_batching_over_100_tokens(self):
        self.db.query(models.DeviceToken).delete()
        for i in range(150):
            self.db.add(models.DeviceToken(id=100 + i, user_id=1, role="student", token=f"bulk-{i}"))
        self.db.commit()
        result = deliver_push(self.db, self.tokens(), title="t", body="b", sender=self.fake_sender(dead_tokens=()))
        self.assertEqual(result.sent, 150)
        self.assertEqual(len(self.calls), 2, "۱۵۰ توکن ⇒ دو دسته (۱۰۰ + ۵۰)")
        self.assertEqual([len(c["tokens"]) for c in self.calls], [100, 50])

    def test_malformed_response_counts_as_failure(self):
        result = deliver_push(self.db, self.tokens(only_valid=True), title="t", body="b",
                              sender=lambda batch, title, body, data: {})
        self.assertEqual(result.failed, 2)
        self.assertEqual(result.sent, 0)

    def test_result_object_shape(self):
        result = deliver_push(self.db, [], title="t", body="b")
        self.assertIsInstance(result, PushResult)
        self.assertTrue(result.skipped)


class TestNotificationServiceIntegration(PushWorld):
    """اتصال واقعی: NotificationService.send_notification باید Push را تلاش کند (قبلاً حلقهٔ خالی)."""

    def test_push_attempted_when_configured(self):
        os.environ[push_service.ENV_FCM_KEY] = "test-server-key"
        push_service.set_sender_override(self.fake_sender(dead_tokens=()))
        notif = NotificationService.send_notification(
            db=self.db, recipient_user_id=1, recipient_role="student", type="installment",
            title="یادآوری قسط", body="متن پیام")
        self.assertIsNotNone(notif)
        self.assertEqual(len(self.calls), 1, "Push باید تلاش شود (حلقهٔ خالی قبلی اینجا بود)")
        self.assertEqual(self.calls[0]["title"], "یادآوری قسط")
        # اعلان در جدول ثبت شده و توکن‌های معتبر دست‌نخورده‌اند
        self.assertEqual(self.db.query(models.Notification).count(), 1)
        self.assertEqual(self.db.query(models.DeviceToken).count(), 3)

    def test_push_skipped_silently_without_credentials(self):
        push_service.set_sender_override(self.fake_sender(dead_tokens=()))
        notif = NotificationService.send_notification(
            db=self.db, recipient_user_id=1, recipient_role="student", type="payment",
            title="پرداخت", body="متن")
        self.assertIsNotNone(notif)
        self.assertEqual(self.calls, [], "بدون اعتبارنامه نباید ارسالی انجام شود")
        self.assertEqual(self.db.query(models.Notification).count(), 1, "ثبت اعلان باید بی‌تغییر باشد")

    def test_invalid_token_cleaned_during_notification(self):
        os.environ[push_service.ENV_FCM_KEY] = "test-server-key"
        push_service.set_sender_override(self.fake_sender(dead_tokens=("tok-dead",)))
        NotificationService.send_notification(
            db=self.db, recipient_user_id=1, recipient_role="student", type="attendance",
            title="غیبت", body="متن")
        remaining = sorted(row.token for row in self.db.query(models.DeviceToken).all())
        self.assertEqual(remaining, ["tok-valid-1", "tok-valid-2"])

    def test_notification_still_created_when_sender_explodes(self):
        os.environ[push_service.ENV_FCM_KEY] = "test-server-key"
        push_service.set_sender_override(lambda batch, title, body, data: (_ for _ in ()).throw(RuntimeError("boom")))
        notif = NotificationService.send_notification(
            db=self.db, recipient_user_id=1, recipient_role="student", type="payment",
            title="پرداخت", body="متن")
        self.assertIsNotNone(notif, "شکست Push نباید ثبت اعلان را بشکند")
        self.assertEqual(self.db.query(models.Notification).count(), 1)

    def test_no_push_for_user_without_device(self):
        os.environ[push_service.ENV_FCM_KEY] = "test-server-key"
        push_service.set_sender_override(self.fake_sender(dead_tokens=()))
        NotificationService.send_notification(
            db=self.db, recipient_user_id=999, recipient_role="teacher", type="payment",
            title="بی‌دستگاه", body="متن")
        self.assertEqual(self.calls, [])

    def test_sms_log_and_notification_unchanged(self):
        """رفتار موجود اعلان (ثبت رکورد + SmsLog) دست‌نخورده بماند."""
        push_service.set_sender_override(self.fake_sender(dead_tokens=()))
        before = self.db.query(models.SmsLog).count()
        NotificationService.send_notification(
            db=self.db, recipient_user_id=1, recipient_role="student", type="installment",
            title="قسط", body="متن")
        self.assertEqual(self.db.query(models.SmsLog).count(), before + 1)
        row = self.db.query(models.Notification).first()
        self.assertEqual(row.recipient_role, "student")
        self.assertEqual(row.type, "installment")
        self.assertIsNotNone(row.created_at)


if __name__ == "__main__":
    unittest.main()
