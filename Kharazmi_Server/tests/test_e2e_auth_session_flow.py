# test_e2e_auth_session_flow.py
# ═══════════════════════════════════════════════════════════════════════════════
# سناریوی end-to-end #۱ (فاز دیباگ): «ورود → نشست → /auth/me → توکن دستگاه → خروج»
# سبک این تست‌ها: هر تست دقیقاً همان درخواستی را می‌فرستد که **اپ اندروید** می‌فرستد
# (مسیر/متد/هدر/بدنه از کد Kotlin کپی شده)، بعد پاسخ سرور و **ذخیره‌شدن در دیتابیس**
# سنجیده می‌شود. یعنی: «از سمت اندروید این‌طور شد، سرور این‌طور پاسخ داد، در DB این‌طور ذخیره شد».
#
# مرجع سمت اندروید (خوانده‌شده از همین ریپو):
#   • ورود مدیر/معلم        → KharazmiAdmin/.../LoginActivity.kt:32-34  (POST auth/login)
#                            AppModels.kt:16-22 (LoginRequest/LoginResponse)
#   • استفادهٔ اپ از پاسخ   → LoginActivity.kt:254-280 (token/role/sub_role/branch_id + TEACHER_ID)
#   • پروفایل کاربر        → MainActivity.kt:53-62 (GET auth/me → MeResponse{user_id,name,role,permissions})
#   • پورتال دانش‌آموز       → StudentPortalActivity.kt:35-41 (POST auth/student/request_otp و auth/student/login)
#   • خروج                  → SettingsActivity.kt / AuthApi: POST auth/logout + device_token query
#   • توکن دستگاه/Push      → PushTokenRegistration.kt: FCM token → POST auth/device_token (تست ۹ قرارداد را قفل می‌کند)
#
# مرجع سمت سرور: routers/auth.py (login:23 · logout:364 · me:389 · request_otp:455 ·
#                                 student/login:525 · device_token:593)
#
# اجرا (از ریشهٔ ریپو):
#   DATABASE_URL=sqlite:////tmp/e2e_auth.db JWT_SECRET_KEY=<hex> \
#     python3 -m pytest Kharazmi_Server/tests/test_e2e_auth_session_flow.py -q
#
# تست‌ها روی SQLite درون‌حافظه‌ای اجرا می‌شوند؛ Firebase/SMS/network واقعی و Android Gradle/device build در این suite اجرا نمی‌شوند.
# source-contract بخش Android فقط wiring و API shape را نگه می‌دارد؛ token generation/delivery نیازمند device QA است.
import datetime
import os
import re
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from dependencies import get_db, hash_password, limiter, verify_password
from main import app

SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(SERVER_DIR)
ANDROID_JAVA_DIR = os.path.join(REPO_ROOT, "KharazmiAdmin", "app", "src", "main", "java")

ADMIN_MOBILE = "09120000001"
ADMIN_PASS = "admin-pass-123"
TEACHER_MOBILE = "09120000002"
TEACHER_PASS = "teacher-pass-123"
STUDENT_MOBILE = "09120000003"


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


class AuthFlowWorld(unittest.TestCase):
    """دنیای مشترک سناریو: مدیر + معلم تأییدشده + دانش‌آموز با موبایل معتبر (DB در حافظه)."""

    def setUp(self):
        # تست‌های auth به ریت‌لیمیت IP نیاز ندارند (مثل بقیهٔ سوئیت: خاموش می‌شود)؛
        # ولی throttle سطح موبایل (H14) که در DB ذخیره می‌شود عمداً روشن می‌ماند تا سنجیده شود.
        self._limiter_was_enabled = limiter.enabled
        limiter.enabled = False

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                               poolclass=StaticPool)
        models.Base.metadata.create_all(engine)
        self.engine = engine
        self.db = sessionmaker(bind=engine, expire_on_commit=False)()

        self.db.add(models.Branch(id=1, name="شعبه مرکزی", active=True))
        self.db.add(models.User(id=101, username=ADMIN_MOBILE, password=hash_password(ADMIN_PASS),
                                full_name="مدیر کل", role="admin", sub_role="admin", branch_id=None))
        self.teacher = models.Teacher(id=51, first_name="مریم", last_name="تست", mobile=TEACHER_MOBILE,
                                      national_code="0012345801", password=hash_password(TEACHER_PASS),
                                      is_approved=True, is_deleted=False, is_suspended=False, branch_id=1)
        self.db.add(self.teacher)
        self.db.add(models.Course(id=71, title="ریاضی دهم", code="600001", teacher_id=51, branch_id=1,
                                  is_deleted=False, is_admin_approved=True, days_of_week="شنبه",
                                  class_time="17:30", teacher_session_price=100000))
        self.student = models.Student(id=41, student_code=41, first_name="علی", last_name="تست",
                                      national_code="0012345802", student_mobile=STUDENT_MOBILE,
                                      branch_id=1, wallet_teacher=0, wallet_institute=0,
                                      wallet_balance=0, is_deleted=False, is_suspended=False)
        self.db.add(self.student)
        self.db.commit()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        limiter.enabled = self._limiter_was_enabled
        self.db.close()
        self.engine.dispose()

    # ---------------- ابزار کمکی ----------------
    def login(self, mobile, password):
        """همان درخواست اپ: LoginActivity.login(LoginRequest(mobile, password))."""
        return self.client.post("/auth/login", json={"mobile": mobile, "password": password})

    def sessions(self, user_id=None):
        q = self.db.query(models.UserSession)
        if user_id is not None:
            q = q.filter(models.UserSession.user_id == user_id)
        return q.all()

    def device_tokens(self, token=None):
        q = self.db.query(models.DeviceToken)
        if token is not None:
            q = q.filter(models.DeviceToken.token == token)
        return q.all()


class TestAdminLogin(AuthFlowWorld):
    # ------------------------------------------------------------------
    # ۱) ورود مدیر: قرارداد پاسخ + ذخیره‌ی نشست در DB
    # ------------------------------------------------------------------
    def test_1_admin_login_response_contract_and_session_row(self):
        resp = self.login(ADMIN_MOBILE, ADMIN_PASS)
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()

        # کلیدهایی که اپ می‌خواند (LoginResponse در AppModels.kt + LoginActivity.kt:254-280)
        for key in ("status", "role", "user_id", "name", "message", "token", "sub_role", "branch_id"):
            self.assertIn(key, body, f"کلید {key} در پاسخ ورود نیست")
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["role"], "admin")
        self.assertEqual(body["sub_role"], "admin")
        self.assertEqual(body["user_id"], 101)
        self.assertEqual(body["name"], "مدیر کل")
        self.assertEqual(body["branch_id"], None, "مدیر کل بدون شعبه است (دسترسی سراسری)")
        self.assertEqual(len(body["token"].split(".")), 3, "توکن باید JWT امضادار باشد")

        # دیتابیس: نشست با همان توکن ذخیره شده و نقش درست دارد
        rows = self.sessions(user_id=101)
        self.assertEqual(len(rows), 1, "هر ورود باید یک UserSession بسازد")
        self.assertEqual(rows[0].token, body["token"])
        self.assertEqual(rows[0].sub_role, "admin")

        # و همان توکن روی /auth/me کار می‌کند (اپ بعد از ورود همین را صدا می‌زند)
        me = self.client.get("/auth/me", headers=hdr(body["token"]))
        self.assertEqual(me.status_code, 200, me.text)
        self.assertEqual(me.json()["user_id"], 101)
        self.assertEqual(me.json()["role"], "admin")

    def test_2_wrong_password_is_logged_and_throttled_per_mobile(self):
        """ضدِ brute-force: هر تلاش ناموفق در DB ثبت و در پنجرهٔ ۵ دقیقه شمارش می‌شود."""
        for _ in range(5):
            self.assertEqual(self.login(ADMIN_MOBILE, "wrong-pass").status_code, 400)
        self.assertEqual(self.db.query(models.LoginAttempt).count(), 5, "تلاش‌های ناموفق باید ذخیره شوند")

        # ششمین تلاش — حتی با رمز درست — قفل می‌شود (H14)
        blocked = self.login(ADMIN_MOBILE, ADMIN_PASS)
        self.assertEqual(blocked.status_code, 429, blocked.text)
        self.assertEqual(len(self.sessions(user_id=101)), 0, "در حالت قفل نباید نشستی ساخته شود")

    def test_2b_successful_login_clears_failed_attempts(self):
        self.login(ADMIN_MOBILE, "bad")
        self.assertEqual(self.db.query(models.LoginAttempt).count(), 1)
        self.assertEqual(self.login(ADMIN_MOBILE, ADMIN_PASS).status_code, 200)
        self.assertEqual(self.db.query(models.LoginAttempt).count(), 0, "ورود موفق باید شمارنده را پاک کند")


class TestTeacherLogin(AuthFlowWorld):
    # ------------------------------------------------------------------
    # ۳) ورود معلم (بار اول): ساخت «کاربر سایه» + نشست با teacher_id درست
    # ------------------------------------------------------------------
    def test_3_teacher_first_login_creates_shadow_user_and_maps_teacher_id(self):
        self.assertEqual(self.db.query(models.User).filter(models.User.role == "teacher").count(), 0)
        resp = self.login(TEACHER_MOBILE, TEACHER_PASS)
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()

        self.assertEqual(body["role"], "teacher")
        self.assertEqual(body["name"], "مریم تست")
        # اپ این مقدار را به‌عنوان TEACHER_ID به TeacherDashboardActivity می‌دهد (LoginActivity.kt:279)
        self.assertEqual(body["user_id"], self.teacher.id,
                         "برای معلم، user_id پاسخِ ورود باید Teacher.id باشد (قرارداد اندروید)")

        shadow = self.db.query(models.User).filter(models.User.role == "teacher").all()
        self.assertEqual(len(shadow), 1, "بار اول باید یک کاربر سایه ساخته شود")
        self.assertEqual(shadow[0].username, TEACHER_MOBILE)
        self.assertEqual(shadow[0].full_name, "مریم تست")

        session = self.sessions(user_id=shadow[0].id)
        self.assertEqual(len(session), 1)
        self.assertEqual(session[0].teacher_id, self.teacher.id, "نگاشت session → Teacher.id باید ذخیره شود")

        # مسیرهای پنل معلم با همان شناسه‌ای که اپ گرفته کار می‌کنند
        classes = self.client.get(f"/teachers/{body['user_id']}/classes", headers=hdr(body["token"]))
        self.assertEqual(classes.status_code, 200, classes.text)

    # ------------------------------------------------------------------
    # ۴) ⚠️ باگ: ورود دوم معلم از «شاخهٔ ادمین» پاسخ می‌گیرد
    # ------------------------------------------------------------------
    def test_4_second_teacher_login_still_returns_teacher_role(self):
        """O-01 (رفع شد): ورود دومِ معلم هم باید مثل ورود اول پاسخ معلم بدهد.

        چرا: `POST /auth/login` اول روی `User.username` می‌گردد و چون سایهٔ معلم با
        `username == mobile` ساخته می‌شود، ورود دومِ همان معلم از شاخهٔ **ادمین** پاسخ می‌گرفت:
        `role="admin"` و `user_id = User.id سایه` (نه `Teacher.id`). پیامد در اپ
        (`LoginActivity.kt:273-280`): معلم به **پنل ادمین** می‌رفت و `TEACHER_ID` هم اشتباه می‌شد.
        """
        first = self.login(TEACHER_MOBILE, TEACHER_PASS).json()
        self.assertEqual(first["role"], "teacher")
        shadow = self.db.query(models.User).filter(models.User.role == "teacher").one()
        self.assertNotEqual(shadow.id, self.teacher.id, "شناسهٔ سایه و معلم معمولاً یکی نیست")

        second = self.login(TEACHER_MOBILE, TEACHER_PASS)
        self.assertEqual(second.status_code, 200, second.text)
        body = second.json()
        self.assertEqual(body["role"], "teacher", "ورود دوم نباید از شاخهٔ ادمین پاسخ بگیرد")
        self.assertEqual(body["sub_role"], "teacher")
        self.assertEqual(body["user_id"], self.teacher.id,
                         "user_id باید Teacher.id باشد، نه شناسهٔ سایه")
        self.assertEqual(body["name"], "مریم تست")

        # نشست ذخیره‌شده هم باید مثل شاخهٔ معلم باشد (teacher_id برای مسیرهای معلم)
        sessions = [row for row in self.sessions(user_id=shadow.id) if row.token == body["token"]]
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].sub_role, "teacher")
        self.assertEqual(sessions[0].teacher_id, self.teacher.id,
                         "سشن ورود معلم باید teacher_id داشته باشد (map پایدار معلم)")

        # در دسترس بودن مسیرهای معلم با توکن ورود دوم (چیزی که اپ اکنون می‌خواند)
        self.assertEqual(self.client.get(f"/teachers/{self.teacher.id}/classes",
                                        headers=hdr(body["token"])).status_code, 200)
        # و ارتقای دسترسی رخ نداده است
        self.assertEqual(self.client.get("/admin/deleted_classes",
                                         headers=hdr(body["token"])).status_code, 403)

    def test_4b_orphan_teacher_shadow_cannot_get_a_token(self):
        """O-21 (رفع شد): سایهٔ `User(role="teacher")` بدون `Teacher` فعال ⇒ هیچ توکنی صادر نمی‌شود.

        پیش از فیکس، lookupِ اول (شاخهٔ ادمین) سایه را پیدا می‌کرد و چون `Teacher` متناظری
        وجود نداشت، گیت‌های H10 (تأیید/تعلیق) **قابل اجرا نبودند** و بی‌عبور از هیچ گیتی
        توکن صادر می‌شد. حالا این مسیر به شاخهٔ معلم می‌رسد و بدون Teacher فعال «کاربری یافت نشد» می‌دهد.
        """
        from dependencies import hash_password as _hash
        self.db.add(models.User(id=150, username="09120000077", password=_hash("orphan-pass-123"),
                                full_name="معلم بی‌پرونده", role="teacher", sub_role="teacher"))
        self.db.add(models.Teacher(id=90, first_name="حذف‌شده", last_name="تست", mobile="09120000078",
                                   national_code="0012345899", password=_hash("deleted-pass-123"),
                                   is_approved=True, is_suspended=False, is_deleted=True, branch_id=1))
        self.db.add(models.User(id=151, username="09120000078", password=_hash("deleted-pass-123"),
                                full_name="حذف‌شده تست", role="teacher", sub_role="teacher"))
        self.db.commit()

        orphan = self.login("09120000077", "orphan-pass-123")
        self.assertIn(orphan.status_code, (403, 404), f"بدون Teacher فعال نباید توکن صادر شود: {orphan.text}")
        self.assertNotIn("token", orphan.json())

        deleted = self.login("09120000078", "deleted-pass-123")
        self.assertIn(deleted.status_code, (403, 404), f"معلم حذف‌شده نباید توکن بگیرد: {deleted.text}")
        self.assertNotIn("token", deleted.json())

        self.assertEqual(self.sessions(user_id=150), [], "سشن سایهٔ بی‌پرونده نباید ساخته شود")
        self.assertEqual(self.sessions(user_id=151), [], "سشن سایهٔ معلم حذف‌شده نباید ساخته شود")

    def test_4c_teacher_login_gates_still_apply_to_the_shadow(self):
        """رگرسیون O-01/O-21: گیت‌های H10 (تأییدنشده/معلق) روی سایهٔ معلم دست‌نخورده است."""
        self.teacher.is_approved = False
        self.db.commit()
        pending = self.login(TEACHER_MOBILE, TEACHER_PASS)
        self.assertEqual(pending.status_code, 403, pending.text)
        self.assertNotIn("token", pending.json())

        self.teacher.is_approved = True
        self.teacher.is_suspended = True
        self.db.commit()
        suspended = self.login(TEACHER_MOBILE, TEACHER_PASS)
        self.assertEqual(suspended.status_code, 403, suspended.text)
        self.assertNotIn("token", suspended.json())


class TestMeEndpoint(AuthFlowWorld):
    # ------------------------------------------------------------------
    # ۵) /auth/me — همان چیزی که MainActivity/TeacherDashboard می‌خوانند
    # ------------------------------------------------------------------
    def test_5_me_contract_for_admin_teacher_and_student(self):
        admin_tok = self.login(ADMIN_MOBILE, ADMIN_PASS).json()["token"]
        body = self.client.get("/auth/me", headers=hdr(admin_tok)).json()
        self.assertEqual(set(body.keys()), {"user_id", "name", "role", "permissions"},
                         "قرارداد MeResponse در اپ فقط همین چهار کلید است")
        self.assertEqual(body["role"], "admin")
        self.assertIn("*", body["permissions"], "مدیر کل باید دسترسی سراسری داشته باشد")

        teacher_tok = self.login(TEACHER_MOBILE, TEACHER_PASS).json()["token"]
        tme = self.client.get("/auth/me", headers=hdr(teacher_tok)).json()
        self.assertEqual(tme["role"], "teacher")
        self.assertEqual(tme["user_id"], self.teacher.id,
                         "در /auth/me شناسهٔ معلم برمی‌گردد (با ترتیب id مخالفِ پاسخِ ورودِ دوم)")

        # بدون توکن/توکن غلط → 401 (و اپ با 401 توکن محلی را پاک می‌کند: RetrofitClient.kt:85-89)
        self.assertEqual(self.client.get("/auth/me").status_code, 401)
        self.assertEqual(self.client.get("/auth/me", headers=hdr("bogus")).status_code, 401)


class TestDeviceTokenAndLogout(AuthFlowWorld):
    # ------------------------------------------------------------------
    # ۶) ثبت توکن دستگاه (پیش‌نیاز Push) — از سرور پاسخ می‌گیرد و در DB ذخیره می‌شود
    # ------------------------------------------------------------------
    def test_6_device_token_registration_is_persisted_and_scoped(self):
        tok = self.login(ADMIN_MOBILE, ADMIN_PASS).json()["token"]
        resp = self.client.post("/auth/device_token", json={"token": "fcm-device-aaa"}, headers=hdr(tok))
        self.assertEqual(resp.status_code, 200, resp.text)

        rows = self.device_tokens("fcm-device-aaa")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].user_id, 101)
        self.assertEqual(rows[0].role, "admin")

        # ثبت دوباره با همان کاربر ⇒ رکورد تکراری ساخته نمی‌شود (idempotent)
        self.assertEqual(self.client.post("/auth/device_token", json={"token": "fcm-device-aaa"},
                                          headers=hdr(tok)).status_code, 200)
        self.assertEqual(len(self.device_tokens("fcm-device-aaa")), 1)

        # کاربر دیگر نمی‌تواند همان توکن را تصاحب کند (گارد hijack در سرور)
        teacher_tok = self.login(TEACHER_MOBILE, TEACHER_PASS).json()["token"]
        hijack = self.client.post("/auth/device_token", json={"token": "fcm-device-aaa"},
                                  headers=hdr(teacher_tok))
        self.assertEqual(hijack.status_code, 403, hijack.text)
        self.assertEqual(self.device_tokens("fcm-device-aaa")[0].user_id, 101, "مالکیت نباید عوض شود")

    # ------------------------------------------------------------------
    # ۷) خروج: پارامتر query به‌نام device_token + باطل‌شدن نشست در DB
    # ------------------------------------------------------------------
    def test_7_logout_invalidates_session_and_only_own_device_token(self):
        tok = self.login(ADMIN_MOBILE, ADMIN_PASS).json()["token"]
        self.client.post("/auth/device_token", json={"token": "dev-mine"}, headers=hdr(tok))
        # توکن دستگاه یک کاربر دیگر (برای سنجش «فقط دیوایس خودم»)
        self.db.add(models.DeviceToken(id=900, user_id=51, role="teacher", token="dev-other"))
        self.db.commit()

        resp = self.client.post("/auth/logout", params={"device_token": "dev-mine"}, headers=hdr(tok))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(self.sessions(user_id=101), [], "نشست باید از DB حذف شود")
        self.assertEqual(self.device_tokens("dev-mine"), [], "توکن دیوایس خودم باید پاک شود")
        self.assertEqual(len(self.device_tokens("dev-other")), 1, "دیوایس کاربر دیگر نباید پاک شود")
        # توکن باطل‌شده دیگر کار نمی‌کند
        self.assertEqual(self.client.get("/auth/me", headers=hdr(tok)).status_code, 401)

    def test_7b_logout_without_device_token_keeps_push_token(self):
        tok = self.login(ADMIN_MOBILE, ADMIN_PASS).json()["token"]
        self.client.post("/auth/device_token", json={"token": "dev-keep"}, headers=hdr(tok))
        self.assertEqual(self.client.post("/auth/logout", headers=hdr(tok)).status_code, 200)
        self.assertEqual(self.sessions(user_id=101), [])
        self.assertEqual(len(self.device_tokens("dev-keep")), 1,
                         "بدون شناسهٔ دیوایس، توکن Push عمداً پاک نمی‌شود (M18)")


class TestStudentOtpFlow(AuthFlowWorld):
    # ------------------------------------------------------------------
    # ۸) پورتال دانش‌آموز: درخواست OTP → خواندن کد از پیامک → ورود
    # ------------------------------------------------------------------
    def test_8_student_otp_request_and_login(self):
        resp = self.client.post("/auth/student/request_otp", json={"mobile": STUDENT_MOBILE})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(set(resp.json().keys()), {"status", "message"},
                         "کد OTP عمداً در پاسخ HTTP برنمی‌گردد")

        otp_row = self.db.query(models.ParentOTP).order_by(models.ParentOTP.id.desc()).first()
        self.assertIsNotNone(otp_row)
        self.assertNotRegex(otp_row.otp, r"^\d{4,6}$", "کد OTP باید هش ذخیره شود، نه plaintext")
        sms = self.db.query(models.SmsLog).order_by(models.SmsLog.id.desc()).first()
        code = re.search(r"(\d{4,6})", sms.message_text or "")
        self.assertIsNotNone(code, "کد باید در متن پیامک (برای ارسال) باشد")

        # کد اشتباه → 400 و شمارش تلاش
        wrong = self.client.post("/auth/student/login", json={"mobile": STUDENT_MOBILE, "otp": "000000"})
        self.assertIn(wrong.status_code, (400, 429))
        self.db.refresh(otp_row)
        self.assertGreaterEqual(otp_row.attempts or 0, 1, "تلاش ناموفق باید در DB شمرده شود")

        # کد درست → توکن + نشست شاگرد (روی کاربر سایه)
        ok = self.client.post("/auth/student/login", json={"mobile": STUDENT_MOBILE, "otp": code.group(1)})
        self.assertEqual(ok.status_code, 200, ok.text)
        body = ok.json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["student_name"], "علی تست")
        self.assertEqual(len(body["token"].split(".")), 3)

        self.db.refresh(self.student)
        self.assertIsNotNone(self.student.user_id, "سایهٔ دانش‌آموز باید ساخته شده باشد")
        session = self.sessions(user_id=self.student.user_id)
        self.assertEqual(len(session), 1)
        self.assertEqual(session[0].sub_role, "student")

        # همان OTP یک‌بارمصرف است
        again = self.client.post("/auth/student/login", json={"mobile": STUDENT_MOBILE, "otp": code.group(1)})
        self.assertEqual(again.status_code, 400, "کد مصرف‌شده نباید دوباره کار کند")

        # و پورتال شاگرد با این توکن داده می‌دهد
        profile = self.client.get("/students/my_profile", headers=hdr(body["token"]))
        self.assertEqual(profile.status_code, 200, profile.text)


class TestAndroidClientGaps(AuthFlowWorld):
    # ------------------------------------------------------------------
    # ۹) قرارداد ثبت FCM: Android token را پس از login/rotation ثبت و هنگام logout لغو می‌کند.
    # ------------------------------------------------------------------
    def test_9_android_client_registers_device_token_and_logs_out_device(self):
        """Android FCM integration را با source-contract می‌سنجیم؛ Gradle/device اجرا نمی‌شود.

        Firebase project values از بیرون Git وارد BuildConfig می‌شوند. بدون پیکربندی FCM،
        login همچنان کار می‌کند و ثبت توکن به‌صورت best-effort رد می‌شود.
        """
        texts = {}
        kt_files = []
        for root, _dirs, files in os.walk(ANDROID_JAVA_DIR):
            kt_files.extend(os.path.join(root, f) for f in files if f.endswith(".kt"))
        self.assertGreater(len(kt_files), 20, f"مسیر کد اندروید پیدا نشد: {ANDROID_JAVA_DIR}")
        for path in kt_files:
            with open(path, encoding="utf-8") as handle:
                texts[os.path.basename(path)] = handle.read()

        settings = texts.get("SettingsActivity.kt", "")
        self.assertIn(".logout(PushTokenRegistration.currentToken", settings)
        self.assertIn("SecureLoginStore.clearToken", settings)
        login_api = texts.get("LoginActivity.kt", "")
        self.assertRegex(login_api, r'@POST\("auth/logout"\)')
        self.assertRegex(login_api, r'@Query\("device_token"\)')

        push = texts.get("PushTokenRegistration.kt", "")
        self.assertIn("FirebaseMessaging.getInstance(firebaseApp).token", push)
        self.assertIn('@POST("auth/device_token")', push)
        self.assertIn("DeviceTokenRequest(token)", push)
        self.assertIn("override fun onNewToken(token: String)", push)
        self.assertIn("PushTokenRegistration.onNewToken(applicationContext, token)", push)
        for filename in ("LoginActivity.kt", "StudentPortalActivity.kt", "ParentPortalActivity.kt"):
            self.assertIn("PushTokenRegistration.refreshAndRegister(applicationContext)", texts.get(filename, ""), filename)

        manifest_path = os.path.join(REPO_ROOT, "KharazmiAdmin", "app", "src", "main", "AndroidManifest.xml")
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = handle.read()
        self.assertIn('android:name=".PushMessagingService"', manifest)
        self.assertIn("com.google.firebase.MESSAGING_EVENT", manifest)

        gradle_path = os.path.join(REPO_ROOT, "KharazmiAdmin", "app", "build.gradle.kts")
        with open(gradle_path, encoding="utf-8") as handle:
            gradle = handle.read()
        self.assertIn("com.google.firebase:firebase-messaging", gradle)
        self.assertIn('"FIREBASE_API_KEY"', gradle)
        self.assertNotIn("FCM_SERVER_KEY", push, "FCM server credentials must remain server-side")

        paths = app.openapi()["paths"]
        for endpoint in ("/auth/device_token", "/auth/logout", "/auth/student/request_otp",
                         "/auth/student/login"):
            self.assertIn(endpoint, paths, f"اندپوینت {endpoint} روی سرور باید موجود باشد")


class TestTeacherCredentialSync(AuthFlowWorld):
    # ------------------------------------------------------------------
    # ۱۰) O-20: رمزی که ادمین برای معلم می‌گذارد (`PUT /teachers/update/{id}`) باید سایه را هم
    #     به‌روز کند؛ وگرنه دو «رمز» متناقض در سیستم می‌ماند.
    # ------------------------------------------------------------------
    NEW_PASS = "new-teacher-pass-456"

    def test_10_admin_set_password_syncs_the_teacher_shadow(self):
        admin_tok = self.login(ADMIN_MOBILE, ADMIN_PASS).json()["token"]
        self.assertEqual(self.login(TEACHER_MOBILE, TEACHER_PASS).status_code, 200)  # ساخت سایه
        shadow = self.db.query(models.User).filter(models.User.role == "teacher").one()

        resp = self.client.put(f"/teachers/update/{self.teacher.id}",
                               json={"password": self.NEW_PASS, "version": 1}, headers=hdr(admin_tok))
        self.assertEqual(resp.status_code, 200, resp.text)

        # ۱) ورود با رمز جدید و رد رمز قدیمی (پس از O-01 مسیر ورود، Teacher.password را می‌سنجد)
        self.assertEqual(self.login(TEACHER_MOBILE, self.NEW_PASS).status_code, 200)
        self.assertEqual(self.login(TEACHER_MOBILE, TEACHER_PASS).status_code, 400,
                         "رمز قدیمی باید بی‌اعتبار شود")

        # ۲) هش سایه هم باید همگام شده باشد
        self.db.refresh(shadow)
        self.assertTrue(verify_password(self.NEW_PASS, shadow.password),
                        "هش سایه با رمز جدید همگام نشده است (O-20)")
        self.assertFalse(verify_password(TEACHER_PASS, shadow.password),
                         "رمز قدیمی نباید در سایه باقی بماند")

    def test_10b_change_mobile_accepts_the_password_set_by_admin(self):
        """اثر واقعی O-20 روی اپ: «تغییر شماره همراه» رمز را از **سایه** می‌سنجد."""
        admin_tok = self.login(ADMIN_MOBILE, ADMIN_PASS).json()["token"]
        self.login(TEACHER_MOBILE, TEACHER_PASS)
        self.assertEqual(self.client.put(f"/teachers/update/{self.teacher.id}",
                                         json={"password": self.NEW_PASS, "version": 1},
                                         headers=hdr(admin_tok)).status_code, 200)

        tok = self.login(TEACHER_MOBILE, self.NEW_PASS).json()["token"]
        resp = self.client.post("/auth/change-mobile", json={
            "current_mobile": TEACHER_MOBILE, "password": self.NEW_PASS, "new_mobile": "09120000099"
        }, headers=hdr(tok))
        self.assertEqual(resp.status_code, 200,
                         f"با رمز درستِ جدید باید کار کند (سایه همگام نشده؟): {resp.text}")


if __name__ == "__main__":
    unittest.main()
