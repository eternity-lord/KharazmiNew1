# test_teacher_approval_requests.py
# Regression tests for «درخواست‌های تایید معلم» (ثبت توسط ادمین → صف pending → approve/reject).
#
# ریشه‌ی باگی که این تست‌ها قفل می‌کنند: مسیر GET /teachers/pending توسط
# GET /teachers/{teacher_id} (که زودتر ثبت شده بود) سایه می‌شد ⇒ پاسخ 422
# («Input should be a valid integer ... input: pending») و صف هرگز بارگذاری نمی‌شد.
# تست ۱ دقیقاً همین را در سطح HTTP قفل می‌کند تا اگر ترتیب include دوباره خراب شد، تست بشکند.
#
# اجرا (DB موقت، نه DB واقعی):
#   DATABASE_URL=sqlite:////tmp/teacher_approval_test.db \
#   JWT_SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))") \
#   python3 -m pytest test_teacher_approval_requests.py -q
import datetime
import unittest

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models import Base, Branch, Course, Teacher, User, UserSession
from main import app
from dependencies import get_db, limiter
from routers.admin import approve_teacher, get_pending_teachers, reject_teacher


def valid_national_code(prefix8: str) -> str:
    """ساخت کد ملی با رقم کنترل معتبر (همان الگوریتم پروژه) برای تست‌های ثبت‌نام."""
    total = sum(int(ch) * (10 - i) for i, ch in enumerate(prefix8))
    rem = total % 11
    return prefix8 + str(rem if rem < 2 else 11 - rem)


REGISTER_PAYLOAD = {
    "first_name": "رضا", "last_name": "محمدی", "father_name": "علی",
    "national_code": valid_national_code("001234567"), "birth_date": "1365/01/01",
    "mobile": "09121234567", "password": "hidden_auto_assigned", "home_phone": "",
    "card_number": "6037991234567890", "marital_status": "مجرد", "gender": "آقا",
    "employment_type": "تمام وقت", "profile_image": None,
}


class TestTeacherApprovalRequests(unittest.TestCase):
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
        try:
            limiter.reset()  # سقف ۵/ساعت ثبت‌نام نباید بین تست‌ها تداخل کند
        except Exception:
            limiter.enabled = False
        self.client = TestClient(app)

        self.db.add_all([
            Branch(id=1, name="شعبه مرکزی", active=True),
            Branch(id=2, name="شعبه شمال", active=True),
        ])
        self.db.flush()

        self.global_admin = User(username="gadmin", password="x", full_name="مدیر کل",
                                 role="admin", sub_role="admin", branch_id=None)
        self.branch_admin = User(username="badmin", password="x", full_name="مدیر مرکزی",
                                 role="admin", sub_role="admin", branch_id=1)
        self.branch2_admin = User(username="b2admin", password="x", full_name="مدیر شمال",
                                  role="admin", sub_role="admin", branch_id=2)
        self.secretary = User(username="secretary", password="x", full_name="منشی",
                              role="admin", sub_role="secretary", branch_id=1)
        self.teacher_user = User(username="teacheruser", password="x", full_name="معلم",
                                 role="teacher", sub_role="teacher", branch_id=1)
        self.student_user = User(username="studentuser", password="x", full_name="شاگرد",
                                 role="student", sub_role="student", branch_id=1)
        self.db.add_all([self.global_admin, self.branch_admin, self.branch2_admin,
                         self.secretary, self.teacher_user, self.student_user])
        self.db.flush()
        now = datetime.datetime.now()
        for token, user in (("tok-global", self.global_admin), ("tok-b1", self.branch_admin),
                            ("tok-b2", self.branch2_admin), ("tok-sec", self.secretary),
                            ("tok-teacher", self.teacher_user), ("tok-student", self.student_user)):
            self.db.add(UserSession(token=token, user_id=user.id, sub_role=user.sub_role, created_at=now))
        self.db.commit()

    def tearDown(self):
        app.dependency_overrides.pop(get_db, None)
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    # ------------------------------------------------------------------
    # ابزار کمکی
    # ------------------------------------------------------------------
    def _headers(self, token):
        return {"Authorization": f"Bearer {token}"} if token else {}

    def _pending(self, token="tok-global"):
        return self.client.get("/teachers/pending", headers=self._headers(token))

    def _register(self, token=None, **overrides):
        payload = dict(REGISTER_PAYLOAD)
        payload.update(overrides)
        return self.client.post("/teachers/register", json=payload, headers=self._headers(token))

    def _add_teacher(self, **kwargs):
        data = dict(first_name="مریم", last_name="تست", mobile="09120000001",
                    national_code=valid_national_code("001234568"), password="x",
                    is_approved=False, is_deleted=False, branch_id=None)
        data.update(kwargs)
        teacher = Teacher(**data)
        self.db.add(teacher)
        self.db.commit()
        return teacher

    # ------------------------------------------------------------------
    # ۱) (root cause) مسیر pending سایه نشده و به endpoint درست می‌رسد
    # ------------------------------------------------------------------
    def test_01_pending_route_not_shadowed_by_teacher_id(self):
        resp = self._pending("tok-global")
        self.assertEqual(resp.status_code, 200, resp.text)
        # اگر route دوباره سایه شود، خطای 422 با loc=["path","teacher_id"] برمی‌گردد.
        self.assertNotIn("teacher_id", resp.text)
        self.assertIsInstance(resp.json(), list)

    # ------------------------------------------------------------------
    # ۲) ثبت معلم توسط ادمین + وضعیت اولیه + id واقعی + نمایش در pending
    # ------------------------------------------------------------------
    def test_02_admin_registration_creates_pending_teacher_with_real_id(self):
        resp = self._register("tok-global")
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertIsInstance(body["id"], int)
        created = self.db.query(Teacher).filter(Teacher.id == body["id"]).first()
        self.assertIsNotNone(created)
        # ۳) وضعیت اولیه: در انتظار تایید، حذف‌نشده
        self.assertFalse(bool(created.is_approved))
        self.assertFalse(bool(created.is_deleted))

        rows = self._pending("tok-global").json()
        self.assertEqual([r["id"] for r in rows], [created.id])       # ۴) نمایش در صف
        self.assertEqual(rows[0]["first_name"], "رضا")
        self.assertEqual(rows[0]["mobile"], "09121234567")
        self.assertFalse(rows[0]["is_approved"])

    # ------------------------------------------------------------------
    # ۴) معلم تاییدشده در صف pending نیست
    # ------------------------------------------------------------------
    def test_04_approved_teacher_not_in_pending(self):
        approved = self._add_teacher(is_approved=True)
        pending = self._add_teacher(mobile="09120000002", national_code=valid_national_code("001234569"))
        ids = [r["id"] for r in self._pending("tok-global").json()]
        self.assertIn(pending.id, ids)
        self.assertNotIn(approved.id, ids)

    # ------------------------------------------------------------------
    # ۵ و ۶) approve موفق + خروج از صف
    # ------------------------------------------------------------------
    def test_05_06_approve_removes_from_pending(self):
        teacher = self._add_teacher()
        resp = self.client.post(f"/teachers/approve/{teacher.id}", headers=self._headers("tok-global"))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.db.refresh(teacher)
        self.assertTrue(bool(teacher.is_approved))
        self.assertEqual(self._pending("tok-global").json(), [])

    # ------------------------------------------------------------------
    # ۷) reject موفق + خروج از صف (soft-delete)
    # ------------------------------------------------------------------
    def test_07_reject_removes_from_pending(self):
        teacher = self._add_teacher()
        resp = self.client.request("DELETE", f"/teachers/reject/{teacher.id}",
                                   headers=self._headers("tok-global"))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.db.refresh(teacher)
        self.assertTrue(bool(teacher.is_deleted))          # آرشیو شده، نه حذف فیزیکی
        self.assertEqual(self._pending("tok-global").json(), [])
        # رکورد باقی است (تاریخچه و جلوگیری از ثبت تکراری با همان کد ملی)
        self.assertIsNotNone(self.db.query(Teacher).filter(Teacher.id == teacher.id).first())

    # ------------------------------------------------------------------
    # ۸) نقش غیرمجاز دسترسی ندارد
    # ------------------------------------------------------------------
    def test_08_unauthorized_roles_cannot_view_or_act(self):
        teacher = self._add_teacher()
        self.assertEqual(self._pending(None).status_code, 401)            # بدون توکن
        self.assertEqual(self._pending("tok-invalid").status_code, 401)   # توکن نامعتبر
        self.assertEqual(self._pending("tok-student").status_code, 403)   # شاگرد
        self.assertEqual(self._pending("tok-teacher").status_code, 403)   # معلم
        self.assertEqual(
            self.client.post(f"/teachers/approve/{teacher.id}", headers=self._headers("tok-teacher")).status_code,
            403,
        )
        self.assertEqual(
            self.client.request("DELETE", f"/teachers/reject/{teacher.id}",
                                headers=self._headers("tok-student")).status_code,
            403,
        )
        self.db.refresh(teacher)
        self.assertFalse(bool(teacher.is_approved))   # هیچ‌کدام اثر نگذاشتند
        self.assertFalse(bool(teacher.is_deleted))

    # ------------------------------------------------------------------
    # ۹) branch isolation: ادمین شعبه‌دار فقط شعبه‌ی خودش + بدون‌شعبه‌ها (و نه شعبه‌ی دیگر)
    # ------------------------------------------------------------------
    def test_09_branch_admin_isolation(self):
        own = self._add_teacher(branch_id=1, mobile="09120000003",
                                national_code=valid_national_code("001234570"))
        other = self._add_teacher(branch_id=2, mobile="09120000004",
                                  national_code=valid_national_code("001234571"), first_name="شمالی")
        unassigned = self._add_teacher(branch_id=None, mobile="09120000005",
                                       national_code=valid_national_code("001234572"), first_name="بدون‌شعبه")

        ids = [r["id"] for r in self._pending("tok-b1").json()]
        self.assertIn(own.id, ids)              # شعبه‌ی خودش
        self.assertIn(unassigned.id, ids)       # بدون انتساب (متعلق به هیچ شعبه‌ای نیست)
        self.assertNotIn(other.id, ids)         # 🔒 نشت بین‌شعبه‌ای ممنوع

        ids_b2 = [r["id"] for r in self._pending("tok-b2").json()]
        self.assertIn(other.id, ids_b2)
        self.assertNotIn(own.id, ids_b2)

        # نشت نام/موبایل شعبه‌ی دیگر در پاسخ شعبه‌ی اول دیده نمی‌شود
        self.assertNotIn("شمالی", self._pending("tok-b1").text)

    # ------------------------------------------------------------------
    # ۱۰) ادمین کل: همه‌ی شعبه‌ها (+ فیلتر صریح شعبه)
    # ------------------------------------------------------------------
    def test_10_global_admin_sees_all_branches(self):
        t1 = self._add_teacher(branch_id=1, mobile="09120000006", national_code=valid_national_code("001234573"))
        t2 = self._add_teacher(branch_id=2, mobile="09120000007", national_code=valid_national_code("001234574"))
        t3 = self._add_teacher(branch_id=None, mobile="09120000008", national_code=valid_national_code("001234575"))
        ids = [r["id"] for r in self._pending("tok-global").json()]
        self.assertEqual(sorted(ids), sorted([t1.id, t2.id, t3.id]))

        # منشی مجاز است ولی مثل هر کاربرِ شعبه‌دار، فقط دامنه‌ی خودش را می‌بیند
        # (شعبه‌ی ۱ + بدون‌شعبه‌ها)، نه شعبه‌ی ۲.
        self.assertEqual(sorted(r["id"] for r in self._pending("tok-sec").json()),
                         sorted([t1.id, t3.id]))

        # فیلتر صریح شعبه برای ادمین کل = دقیق (بدون رکوردهای بدون‌شعبه)
        resp = self.client.get("/teachers/pending", params={"branch_id": 2}, headers=self._headers("tok-global"))
        self.assertEqual([r["id"] for r in resp.json()], [t2.id])
        # فیلتر صریح شعبه‌ی دیگر برای ادمینِ شعبه‌دار بی‌اثر است (isolation با query دور زده نمی‌شود)
        resp = self.client.get("/teachers/pending", params={"branch_id": 2}, headers=self._headers("tok-b1"))
        self.assertEqual([r["id"] for r in resp.json()], [t1.id])

    # ------------------------------------------------------------------
    # ۱۱) branch_id=NULL بدون نشت: ثبت‌نام بدون هویت + چند شعبه → بدون شعبه و بی‌خطا
    # ------------------------------------------------------------------
    def test_11_unassigned_registration_has_no_branch_and_no_leak(self):
        resp = self._register()  # بدون توکن، دو شعبه‌ی فعال ⇒ تخمین ممنوع
        self.assertEqual(resp.status_code, 200, resp.text)
        created = self.db.query(Teacher).filter(Teacher.id == resp.json()["id"]).first()
        self.assertIsNone(created.branch_id)              # هیچ شعبه‌ای حدس زده نشد
        self.assertFalse(bool(created.is_approved))
        # رکورد بدون شعبه فقط به‌عنوان «بدون انتساب» دیده می‌شود، نه به نام یک شعبه‌ی خاص
        row = [r for r in self._pending("tok-b1").json() if r["id"] == created.id][0]
        self.assertIsNone(row["branch_id"])
        self.assertEqual(row["branch_name"], "")

    # ------------------------------------------------------------------
    # ۱۲) داده‌ی nullable بدون 500
    # ------------------------------------------------------------------
    def test_12_nullable_data_does_not_500(self):
        self._add_teacher(first_name=None, last_name=None, mobile=None,
                          national_code=None, branch_id=1)
        self._add_teacher(first_name="سالم", last_name="تست", mobile="09120000009",
                          national_code=valid_national_code("001234576"), branch_id=1)
        resp = self._pending("tok-global")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertNotIn("None", resp.text)
        rows = resp.json()
        self.assertEqual(len(rows), 2)
        legacy = [r for r in rows if r["first_name"] == ""][0]
        self.assertEqual(legacy["first_name"], "")
        self.assertEqual(legacy["last_name"], "")
        self.assertIsNone(legacy["mobile"])

    # ------------------------------------------------------------------
    # ۱۳) جلوگیری از duplicate
    # ------------------------------------------------------------------
    def test_13_duplicate_registration_prevented(self):
        first = self._register("tok-global")
        self.assertEqual(first.status_code, 200, first.text)
        again = self._register("tok-global")     # همان کد ملی و موبایل
        self.assertEqual(again.status_code, 400, again.text)
        # موبایل جدید ولی کد ملی تکراری
        dup_nc = self._register("tok-global", mobile="09129999999")
        self.assertEqual(dup_nc.status_code, 400, dup_nc.text)
        # کد ملی جدید ولی موبایل تکراری → 409
        dup_mobile = self._register("tok-global", national_code=valid_national_code("001234577"))
        self.assertEqual(dup_mobile.status_code, 409, dup_mobile.text)
        # فقط یک رکورد ساخته شد و فقط یک بار در صف است
        self.assertEqual(self.db.query(Teacher).count(), 1)
        self.assertEqual(len(self._pending("tok-global").json()), 1)

    # ------------------------------------------------------------------
    # ۱۴) لیست خالی
    # ------------------------------------------------------------------
    def test_14_empty_pending_list(self):
        resp = self._pending("tok-global")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    # ------------------------------------------------------------------
    # ۱۵) خطای کنترل‌شده برای معلم ناموجود
    # ------------------------------------------------------------------
    def test_15_unknown_teacher_controlled_error(self):
        self.assertEqual(
            self.client.post("/teachers/approve/999999", headers=self._headers("tok-global")).status_code, 404)
        self.assertEqual(
            self.client.request("DELETE", "/teachers/reject/999999",
                                headers=self._headers("tok-global")).status_code, 404)
        with self.assertRaises(HTTPException) as ctx:
            approve_teacher(teacher_id=999999, db=self.db, _="admin")
        self.assertEqual(ctx.exception.status_code, 404)

    # ------------------------------------------------------------------
    # ۱۶) حفظ id واقعی (سطح HTTP و تابع) + ۱۷) سازگاری API با اپ
    # ------------------------------------------------------------------
    def test_16_real_id_preserved_http_and_function_level(self):
        teacher = self._add_teacher(branch_id=None)
        rows = self._pending("tok-global").json()
        self.assertEqual(rows[0]["id"], teacher.id)
        direct = get_pending_teachers(db=self.db, _="admin")
        self.assertEqual([r.id for r in direct], [teacher.id])
        self.assertEqual(direct[0].id, teacher.id)

    def test_17_api_contract_compatible_with_android(self):
        teacher = self._add_teacher(branch_id=1)
        row = self._pending("tok-global").json()[0]
        # فیلدهای قبلی (اپ کنونی) باید سر جای خودشان باشند
        for key in ("id", "first_name", "last_name", "mobile", "teacher_code",
                    "profile_image", "is_approved", "is_suspended"):
            self.assertIn(key, row)
        # فیلدهای افزوده‌شده (اختیاری و سازگار با Gson اپ)
        self.assertIn("branch_id", row)
        self.assertIn("branch_name", row)
        self.assertEqual(row["branch_id"], 1)
        self.assertEqual(row["branch_name"], "شعبه مرکزی")
        self.assertEqual(row["id"], teacher.id)

    # ------------------------------------------------------------------
    # تکمیلی) ثبت با توکن ادمین شعبه‌دار → انتساب همان شعبه (بدون حدس)
    # ------------------------------------------------------------------
    def test_registration_assigns_callers_branch(self):
        resp = self._register("tok-b1")          # ادمین شعبه ۱
        self.assertEqual(resp.status_code, 200, resp.text)
        created = self.db.query(Teacher).filter(Teacher.id == resp.json()["id"]).first()
        self.assertEqual(created.branch_id, 1)
        # و همان ادمین شعبه رکورد را در صف خودش می‌بیند
        self.assertIn(created.id, [r["id"] for r in self._pending("tok-b1").json()])

    def test_registration_rejects_invalid_branch_id(self):
        # شعبه‌ی ناموجود → 400 از سیاست مرکزی (بدون رکورد ناقص)
        bad = self._register("tok-b1", branch_id=999, mobile="09120000011",
                             national_code=valid_national_code("001234578"))
        self.assertEqual(bad.status_code, 400, bad.text)
        # شعبه‌ی دیگر (شعبه ۲) توسط ادمین شعبه ۱ → 403
        cross = self._register("tok-b1", branch_id=2, mobile="09120000012",
                               national_code=valid_national_code("001234579"))
        self.assertEqual(cross.status_code, 403, cross.text)
        self.assertEqual(self.db.query(Teacher).count(), 0)

    def test_branch_admin_cannot_approve_other_branch(self):
        other = self._add_teacher(branch_id=2, mobile="09120000013",
                                  national_code=valid_national_code("001234580"))
        resp = self.client.post(f"/teachers/approve/{other.id}", headers=self._headers("tok-b1"))
        self.assertEqual(resp.status_code, 404)          # بدون نشت وجود رکورد
        self.db.refresh(other)
        self.assertFalse(bool(other.is_approved))
        # ادمین همان شعبه موفق است
        self.assertEqual(
            self.client.post(f"/teachers/approve/{other.id}", headers=self._headers("tok-b2")).status_code, 200)


if __name__ == "__main__":
    unittest.main()
