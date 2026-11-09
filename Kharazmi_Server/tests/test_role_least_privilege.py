# test_role_least_privilege.py
# تست‌های A1 — «کمترین سطح دسترسی» برای نقش کاربران
#
# باگی که این تست‌ها قفل می‌کنند:
#   پیش‌تر هر کاربری که `sub_role` نداشت (رکورد legacy پیش از افزوده‌شدن ستون، یا هر ردیفی
#   که نقشش ثبت نشده) در گاردهای امنیتی **ادمین** فرض می‌شد:
#       sub_role = user.sub_role if user.sub_role else "admin"
#   پیامد: سایهٔ معلم/شاگرد/ولیِ قدیمی می‌توانست به تمام اندپوینت‌های ادمین (مالی، حذف،
#   تنظیمات) دسترسی بگیرد — و حتی از مسیر ورود، توکن با نقش «admin» می‌گرفت.
#   همچنین migration قدیمی همهٔ ردیف‌ها را «admin» می‌کرد (DEFAULT 'admin' + UPDATE بی‌قید).
#
# سیاست جدید (fail-closed): sub_role ست‌شده ⇒ همان؛ در غیر این‌صورت از `role` استفاده
# می‌شود و فقط `role` خالی/«admin» ⇒ ادمین (سازگاری با ادمین‌های legacy).
#
# اجرا (از ریشهٔ ریپو — طبق روش مستند پروژه):
#   DATABASE_URL=sqlite:////tmp/role_lp.db JWT_SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))") \
#     python3 -m pytest Kharazmi_Server/test_role_least_privilege.py -q
import datetime
import sqlite3
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from dependencies import get_db, resolve_effective_sub_role
from main import app


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


class TestEffectiveSubRole(unittest.TestCase):
    """لایهٔ منطقی: resolve_effective_sub_role باید fail-closed باشد."""

    def _user(self, role, sub_role):
        return models.User(username="u", password="x", full_name="ت", role=role, sub_role=sub_role)

    def test_explicit_sub_role_wins(self):
        self.assertEqual(resolve_effective_sub_role(self._user("admin", "secretary")), "secretary")
        self.assertEqual(resolve_effective_sub_role(self._user("teacher", "teacher")), "teacher")
        self.assertEqual(resolve_effective_sub_role(self._user(None, "temp_parent:۳")), "temp_parent:۳")

    def test_missing_sub_role_uses_role_column(self):
        # هستهٔ فیکس: سایهٔ بی‌نقش دیگر ادمین نیست
        self.assertEqual(resolve_effective_sub_role(self._user("teacher", None)), "teacher")
        self.assertEqual(resolve_effective_sub_role(self._user("student", None)), "student")
        self.assertEqual(resolve_effective_sub_role(self._user("parent", None)), "parent")
        self.assertEqual(resolve_effective_sub_role(self._user("secretary", None)), "secretary")

    def test_empty_and_whitespace_behave_like_missing(self):
        self.assertEqual(resolve_effective_sub_role(self._user("student", "")), "student")
        self.assertEqual(resolve_effective_sub_role(self._user("student", "   ")), "student")

    def test_legacy_admin_stays_admin(self):
        # سازگاری به‌عقب: ردیف‌های legacy ادمین که فقط role=admin دارند (یا role خالی)
        self.assertEqual(resolve_effective_sub_role(self._user("admin", None)), "admin")
        self.assertEqual(resolve_effective_sub_role(self._user(None, None)), "admin")
        self.assertEqual(resolve_effective_sub_role(self._user("", "")), "admin")

    def test_unknown_role_does_not_become_admin(self):
        self.assertEqual(resolve_effective_sub_role(self._user("مهمان", None)), "مهمان")


class TestGuardsFailClosed(unittest.TestCase):
    """لایهٔ HTTP: گاردها نباید به رکورد بی‌نقش دسترسی ادمین بدهند."""

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
            # کاربران legacy: sub_role ندارند (شبیه دیتابیس پیش از این ستون)
            models.User(id=1, username="09120000001", password="x", full_name="معلم قدیمی",
                        role="teacher", sub_role=None, branch_id=1),
            models.User(id=2, username="student:1", password="x", full_name="شاگرد قدیمی",
                        role="student", sub_role=None, branch_id=1),
            models.User(id=3, username="parent:1", password="x", full_name="ولی قدیمی",
                        role="parent", sub_role=None, branch_id=1),
            models.User(id=4, username="student:2", password="x", full_name="شاگرد خالی",
                        role="student", sub_role="   ", branch_id=1),
            # ادمین legacy (باید همچنان ادمین بماند)
            models.User(id=5, username="admin-legacy", password="x", full_name="مدیر قدیمی",
                        role="admin", sub_role=None, branch_id=None),
            models.User(id=6, username="no-role", password="x", full_name="بی‌نقش قدیمی",
                        role=None, sub_role=None, branch_id=None),
            # کاربران مدرن
            models.User(id=7, username="admin-now", password="x", full_name="مدیر امروز",
                        role="admin", sub_role="admin", branch_id=None),
            models.User(id=8, username="sec-now", password="x", full_name="منشی امروز",
                        role="admin", sub_role="secretary", branch_id=1),
        ])
        for uid, tok in [(1, "tok-legacy-teacher"), (2, "tok-legacy-student"), (3, "tok-legacy-parent"),
                         (4, "tok-blank-student"), (5, "tok-legacy-admin"), (6, "tok-no-role"),
                         (7, "tok-admin"), (8, "tok-secretary")]:
            self.db.add(models.UserSession(token=tok, user_id=uid, sub_role=None, created_at=now))
        self.db.commit()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    # --- گارد ادمین: /admin/deleted_classes (check_admin_access) ---
    def test_admin_endpoint_denies_legacy_non_admins(self):
        for tok in ("tok-legacy-teacher", "tok-legacy-student", "tok-legacy-parent", "tok-blank-student"):
            r = self.client.get("/admin/deleted_classes", headers=hdr(tok))
            self.assertEqual(r.status_code, 403, f"{tok} ⇒ {r.status_code} (نباید ادمین فرض شود)")

    def test_admin_endpoint_allows_admin_users(self):
        for tok in ("tok-legacy-admin", "tok-no-role", "tok-admin"):
            r = self.client.get("/admin/deleted_classes", headers=hdr(tok))
            self.assertEqual(r.status_code, 200, f"{tok} ⇒ {r.status_code}")

    def test_secretary_not_admin_but_allowed_on_staff_routes(self):
        # منشی: ادمین نیست
        self.assertEqual(self.client.get("/admin/deleted_classes", headers=hdr("tok-secretary")).status_code, 403)
        # ولی از گارد کارکنان (ادمین یا منشی) عبور می‌کند
        self.assertEqual(self.client.get("/reports/chart-data", headers=hdr("tok-secretary")).status_code, 200)

    def test_staff_route_denies_legacy_non_staff(self):
        # گارد check_admin_or_secretary_access نباید رکورد بی‌نقش را راه بدهد
        self.assertEqual(self.client.get("/reports/chart-data", headers=hdr("tok-legacy-student")).status_code, 403)
        self.assertEqual(self.client.get("/reports/chart-data", headers=hdr("tok-legacy-teacher")).status_code, 403)
        self.assertEqual(self.client.get("/reports/chart-data", headers=hdr("tok-legacy-parent")).status_code, 403)

    def test_staff_route_allows_admins(self):
        for tok in ("tok-legacy-admin", "tok-no-role", "tok-admin"):
            self.assertEqual(self.client.get("/reports/chart-data", headers=hdr(tok)).status_code, 200, tok)

    def test_no_token_still_401(self):
        self.assertEqual(self.client.get("/admin/deleted_classes").status_code, 401)
        self.assertEqual(self.client.get("/reports/chart-data").status_code, 401)


class TestLoginRoleNotEscalated(unittest.TestCase):
    """مسیر ورود: سایهٔ معلمِ بدون sub_role نباید توکن «admin» بگیرد."""

    def setUp(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                               poolclass=StaticPool)
        models.Base.metadata.create_all(engine)
        self.engine = engine
        Session = sessionmaker(bind=engine, expire_on_commit=False)
        self.db = Session()
        from dependencies import hash_password
        self.db.add_all([
            models.Branch(id=1, name="شعبه", active=True),
            models.Teacher(id=1, first_name="معلم", last_name="قدیمی", mobile="09120000009",
                           national_code="0012345679", password=hash_password("secret123"),
                           is_approved=True, is_suspended=False, is_deleted=False, branch_id=1),
            # سایهٔ معلم legacy: role=teacher ولی sub_role خالی
            models.User(id=1, username="09120000009", password=hash_password("secret123"),
                        full_name="معلم قدیمی", role="teacher", sub_role=None, branch_id=1),
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

    def test_legacy_teacher_shadow_does_not_get_admin_token(self):
        r = self.client.post("/auth/login", json={"mobile": "09120000009", "password": "secret123"})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertNotEqual(body.get("sub_role"), "admin",
                            "سایهٔ معلمِ legacy نباید با نقش admin وارد شود")
        # توکن صادرشده هم در دیتابیس با همان نقش ثبت شده است
        sess = self.db.query(models.UserSession).filter(
            models.UserSession.user_id == 1).order_by(models.UserSession.id.desc()).first()
        self.assertIsNotNone(sess)
        self.assertNotEqual(sess.sub_role, "admin")


class TestMigrationBackfillIsRoleAware(unittest.TestCase):
    """migration واقعی (`auto_patch_database`) روی یک DB قدیمی: هیچ کاربری بی‌نقش ادمین نشود.

    این تست، تابع واقعی محصول را اجرا می‌کند (نه یک SQL کپی‌شده) روی یک دیتابیس SQLite موقت
    که جدول `users` آن **ستون sub_role ندارد** — دقیقاً وضعیت دیتابیس‌های قدیمی پیش از ارتقا.
    """

    def setUp(self):
        import os
        import tempfile
        self.db_path = os.path.join(tempfile.mkdtemp(prefix="a1_mig_"), "legacy.db")
        con = sqlite3.connect(self.db_path)
        con.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password TEXT, "
                    "full_name TEXT, role TEXT)")
        con.executemany("INSERT INTO users (id, username, password, full_name, role) VALUES (?,?,?,?,?)", [
            (1, "09120000001", "x", "معلم قدیمی", "teacher"),
            (2, "student:1", "x", "شاگرد قدیمی", "student"),
            (3, "parent:1", "x", "ولی قدیمی", "parent"),
            (4, "teacher:9", "x", "سایه معلم بدون role", None),
            (5, "admin-main", "x", "مدیر آموزشگاه", "admin"),
        ])
        con.commit()
        con.close()

    def _run_migration(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        import main as main_module
        engine = create_engine(f"sqlite:///{self.db_path}")
        original = models.SessionLocal
        models.SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        try:
            main_module.auto_patch_database()
        finally:
            models.SessionLocal = original
            engine.dispose()

    def _sub_roles(self):
        con = sqlite3.connect(self.db_path)
        try:
            rows = con.execute("SELECT username, sub_role FROM users").fetchall()
        finally:
            con.close()
        return dict(rows)

    def test_migration_creates_column_and_backfills_real_roles(self):
        self._run_migration()
        got = self._sub_roles()
        self.assertEqual(got["09120000001"], "teacher", "سایهٔ معلم legacy نباید ادمین شود")
        self.assertEqual(got["student:1"], "student")
        self.assertEqual(got["parent:1"], "parent")
        self.assertEqual(got["teacher:9"], "teacher")   # از پیشوند username
        self.assertEqual(got["admin-main"], "admin")    # ادمین واقعی ادمین می‌ماند

    def test_migration_promotes_nobody_unintentionally(self):
        self._run_migration()
        got = self._sub_roles()
        non_admins = {u: r for u, r in got.items() if u != "admin-main"}
        self.assertNotIn("admin", non_admins.values(),
                         f"هیچ کاربر غیرمدیری نباید در migration ادمین شود: {non_admins}")


if __name__ == "__main__":
    unittest.main()
