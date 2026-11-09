# test_portal_real_notifications.py
# تست‌های C1 — اعلان‌های واقعی در پورتال دانش‌آموز و ولی
#
# باگی که این تست‌ها قفل می‌کنند:
#   دو اندپوینت پورتال، لیست اعلان‌ها را **هاردکد** برگردانده بودند:
#     GET /students/my_profile   (پورتال دانش‌آموز)  routers/students.py
#     GET /parent/child_profile  (پورتال ولی)        routers/parent.py
#   یعنی هر دانش‌آموز/ولی — مستقل از واقعیت — دو پیام نمایشی می‌دید:
#     «اطلاعیه شروع ترم تحصیلی جدید» (تاریخ ثابت ۱۴۰۵/۰۶/۰۱)
#     «تعطیلی موقت به علت سرما» (تاریخ ثابت ۱۴۰۵/۰۶/۰۲)
#   و برعکسش مهم‌تر بود: اعلان‌های واقعیِ تولیدشده در سیستم (پرداخت فرزند، یادآوری قسط،
#   غیبت، آزمون، پیام‌ها) **هرگز** به پورتال نمی‌رسید. پیامد برای آموزشگاه: ولی‌ها
#   اطلاعیه‌های ساختگی می‌دیدند و از بدهی/غیبت/آزمون فرزندشان بی‌خبر می‌ماندند.
#
# قرارداد جدید: هر دو پورتال از جدول واقعی `notifications` می‌خوانند، با همان کلید
# (`recipient_user_id` در فضای User.id + `recipient_role` کانونیکال) که اندپوینت
# `/notifications` استفاده می‌کند ⇒ هیچ اعلانِ کاربر دیگری دیده نمی‌شود.
#
# اجرا (از ریشهٔ ریپو):
#   DATABASE_URL=sqlite:////tmp/c1_notif.db JWT_SECRET_KEY=<hex> \
#     python3 -m pytest Kharazmi_Server/test_portal_real_notifications.py -q
import datetime
import json
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from dependencies import get_db, hash_password
from main import app

FAKE_TITLES = ("اطلاعیه شروع ترم تحصیلی جدید", "تعطیلی موقت به علت سرما")


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


class PortalNotificationsWorld(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                               poolclass=StaticPool)
        models.Base.metadata.create_all(engine)
        self.engine = engine
        Session = sessionmaker(bind=engine, expire_on_commit=False)
        self.db = Session()
        now = datetime.datetime.now()
        self.db.add_all([
            models.Branch(id=1, name="شعبه یک", active=True),
            models.User(id=10, username="student:1", password="x", full_name="شاگرد یک",
                        role="student", sub_role="student", branch_id=1),
            models.User(id=20, username="parent:1", password="x", full_name="ولی یک",
                        role="parent", sub_role="parent", branch_id=1),
            models.User(id=11, username="student:2", password="x", full_name="شاگرد دو",
                        role="student", sub_role="student", branch_id=1),
            models.User(id=21, username="parent:2", password="x", full_name="ولی دو",
                        role="parent", sub_role="parent", branch_id=1),
            models.Student(id=1, student_code=1, first_name="علی", last_name="تست",
                           national_code="0012345701", student_mobile="09121111111",
                           branch_id=1, wallet_teacher=0, wallet_institute=0, wallet_balance=0,
                           is_deleted=False, user_id=10, parent_user_id=20),
            models.Student(id=2, student_code=2, first_name="زهرا", last_name="تست",
                           national_code="0012345702", student_mobile="09122222222",
                           branch_id=1, wallet_teacher=0, wallet_institute=0, wallet_balance=0,
                           is_deleted=False, user_id=11, parent_user_id=21),
        ])
        self.db.add_all([
            models.UserSession(token="tok-stud-1", user_id=10, sub_role="student", created_at=now),
            models.UserSession(token="tok-parent-1", user_id=20, sub_role="parent", created_at=now),
            models.UserSession(token="tok-stud-2", user_id=11, sub_role="student", created_at=now),
            models.UserSession(token="tok-parent-2", user_id=21, sub_role="parent", created_at=now),
        ])
        self.db.commit()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    # ---------------- کمکی ----------------
    def add_notification(self, nid, user_id, role, title, body, created_at=True, is_read=False):
        self.db.add(models.Notification(id=nid, recipient_user_id=user_id, recipient_role=role,
                                        type="payment", title=title, body=body,
                                        is_read=is_read,
                                        created_at=datetime.datetime(2026, 9, 21, 10, 30)))
        self.db.commit()
        if not created_at:
            # ستون default دارد؛ برای شبیه‌سازی رکورد legacy باید صریحاً NULL شود
            self.db.query(models.Notification).filter(models.Notification.id == nid).update(
                {"created_at": None})
            self.db.commit()

    def student_portal(self, token="tok-stud-1"):
        r = self.client.get("/students/my_profile", headers=hdr(token))
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def parent_portal(self, token="tok-parent-1"):
        r = self.client.get("/parent/child_profile", headers=hdr(token))
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    @staticmethod
    def titles(items):
        return [i["title"] for i in items]


class TestStudentPortalNotifications(PortalNotificationsWorld):
    def test_fake_notices_are_gone(self):
        body = self.student_portal()
        for fake in FAKE_TITLES:
            self.assertNotIn(fake, self.titles(body["notifications"]),
                             "اعلان ساختگی قدیمی نباید برگردد")

    def test_no_notifications_is_empty_list(self):
        self.assertEqual(self.student_portal()["notifications"], [])

    def test_real_notification_is_returned(self):
        self.add_notification(1, 10, "student", "⚠️ غیبت ثبت شد",
                              "شما در جلسهٔ ریاضی غایب بودید.")
        items = self.student_portal()["notifications"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "⚠️ غیبت ثبت شد")
        self.assertEqual(items[0]["body"], "شما در جلسهٔ ریاضی غایب بودید.")
        self.assertEqual(items[0]["type"], "payment")
        self.assertFalse(items[0]["is_read"])
        self.assertNotIn("None", json.dumps(items, ensure_ascii=False))

    def test_other_student_notification_is_not_leaked(self):
        self.add_notification(2, 11, "student", "اعلان شاگرد دیگر", "محرمانه")
        items = self.student_portal("tok-stud-1")["notifications"]
        self.assertEqual(items, [], "اعلان شاگرد دیگر نباید به این پورتال نشت کند")
        other = self.student_portal("tok-stud-2")["notifications"]
        self.assertEqual(len(other), 1)

    def test_parent_role_notification_not_shown_to_student(self):
        self.add_notification(3, 10, "parent", "اعلان ولی", "فقط برای ولی")
        self.assertEqual(self.student_portal()["notifications"], [],
                         "اعلانِ نقش ولی نباید در پورتال شاگرد دیده شود")

    def test_newest_first(self):
        self.add_notification(4, 10, "student", "قدیمی", "ق")
        self.db.query(models.Notification).filter(models.Notification.id == 4).update(
            {"created_at": datetime.datetime(2026, 1, 1, 8, 0)})
        self.db.commit()
        self.add_notification(5, 10, "student", "جدید", "ج")
        titles = self.titles(self.student_portal()["notifications"])
        self.assertEqual(titles[0], "جدید")
        self.assertEqual(titles[1], "قدیمی")

    def test_legacy_row_without_created_at_does_not_crash(self):
        """رکورد legacy با created_at=NULL نباید کل پورتال را ۵۰۰ کند و date باید رشته باشد."""
        self.add_notification(6, 10, "student", "بدون تاریخ", "متن", created_at=False)
        items = self.student_portal()["notifications"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["date"], "")
        self.assertIsInstance(items[0]["date"], str)

    def test_date_is_jalali_string(self):
        self.add_notification(7, 10, "student", "با تاریخ", "متن")
        item = self.student_portal()["notifications"][0]
        # 2026-09-21 میلادی ⇒ 1405/06/30 شمسی (مبدل مرکزی پروژه)
        self.assertEqual(item["date"], "1405/06/30")

    def test_read_notification_is_flagged(self):
        self.add_notification(8, 10, "student", "خوانده‌شده", "متن", is_read=True)
        self.assertTrue(self.student_portal()["notifications"][0]["is_read"])

    def test_response_contract_unchanged(self):
        body = self.student_portal()
        self.assertEqual(set(body.keys()),
                         {"info", "classes", "wallet", "grades", "averages", "attendance",
                          "installments", "homework", "exams", "upcoming_sessions", "notifications"})
        self.assertEqual(body["notifications"], [])
        self.add_notification(9, 10, "student", "قرارداد", "متن")
        item = self.student_portal()["notifications"][0]
        self.assertTrue({"title", "body", "date"}.issubset(set(item.keys())),
                        "کلیدهای مورد استفادهٔ اپ (title/body/date) باید حفظ شوند")


class TestParentPortalNotifications(PortalNotificationsWorld):
    def test_fake_notices_are_gone(self):
        body = self.parent_portal()
        for fake in FAKE_TITLES:
            self.assertNotIn(fake, self.titles(body["notifications"]))

    def test_no_notifications_is_empty_list(self):
        self.assertEqual(self.parent_portal()["notifications"], [])

    def test_real_parent_notification_is_returned(self):
        self.add_notification(10, 20, "parent", "✅ پرداخت آنلاین موفق فرزند",
                              "پرداخت ۵۰۰٬۰۰۰ تومان با موفقیت انجام شد.")
        items = self.parent_portal()["notifications"]
        self.assertEqual(len(items), 1)
        self.assertIn("پرداخت آنلاین", items[0]["title"])
        self.assertNotIn("None", json.dumps(items, ensure_ascii=False))

    def test_other_family_notification_is_not_leaked(self):
        self.add_notification(11, 21, "parent", "اعلان خانوادهٔ دیگر", "محرمانه")
        self.assertEqual(self.parent_portal("tok-parent-1")["notifications"], [])
        self.assertEqual(len(self.parent_portal("tok-parent-2")["notifications"]), 1)

    def test_student_role_notification_not_shown_to_parent(self):
        self.add_notification(12, 20, "student", "اعلان نقش شاگرد", "برای شاگرد")
        self.assertEqual(self.parent_portal()["notifications"], [],
                         "نقش باید دقیقاً parent باشد")

    def test_helper_is_defensive_when_parent_user_row_is_missing(self):
        """شاخهٔ دفاعی helper: دادهٔ ناسازگار (لینک ولی بدون رکورد کاربر) ⇒ لیست خالی، نه استثنا.

        توجه: از مسیر HTTP این حالت به ۴۰۴ «دانش‌آموز یافت نشد» می‌رسد (قرارداد موجود
        get_session_parent) — پس شاخهٔ دفاعی در سطح helper سنجیده می‌شود.
        """
        import routers.parent as parent_module
        student = self.db.query(models.Student).filter(models.Student.id == 1).first()
        self.db.query(models.User).filter(models.User.id == 20).delete()
        self.db.commit()
        student.parent_user_id = 20  # لینک فرزند→ولی هست، ولی رکورد کاربرش رفته
        self.assertEqual(parent_module._portal_notifications(self.db, student), [])
        self.assertEqual(parent_module._portal_notifications(self.db, None), [])

    def test_http_contract_for_broken_parent_link_is_404(self):
        """قرارداد موجود دست‌نخورده: نشستِ ولی بدون لینک فرزند ⇒ ۴۰۴ (نه ۵۰۰)."""
        self.db.query(models.Student).filter(models.Student.id == 1).update({"parent_user_id": None})
        self.db.commit()
        r = self.client.get("/parent/child_profile", headers=hdr("tok-parent-1"))
        self.assertEqual(r.status_code, 404)

    def test_newest_first_and_limit(self):
        for i in range(60):
            self.add_notification(100 + i, 20, "parent", f"اعلان {i}", "متن")
            self.db.query(models.Notification).filter(models.Notification.id == 100 + i).update(
                {"created_at": datetime.datetime(2026, 1, 1, 0, 0) + datetime.timedelta(minutes=i)})
        self.db.commit()
        items = self.parent_portal()["notifications"]
        self.assertEqual(len(items), 50, "سقف اعلان‌های پورتال ۵۰ است (جدیدترین‌ها)")
        self.assertEqual(items[0]["title"], "اعلان 59")

    def test_response_contract_unchanged(self):
        body = self.parent_portal()
        self.assertEqual(set(body.keys()),
                         {"info", "classes", "wallet", "grades", "averages", "attendance",
                          "installments", "homework", "exams", "upcoming_sessions", "notifications"})


if __name__ == "__main__":
    unittest.main()
