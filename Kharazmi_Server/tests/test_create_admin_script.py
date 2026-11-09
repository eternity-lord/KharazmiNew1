# test_create_admin_script.py
# O-16: اسکریپت ساخت مدیر (`scripts/create_admin.py`) باید مدیرِ **قابل‌ورود** بسازد.
#
# باگ نسخهٔ قبلی: رمز ثابت «123» plaintext ذخیره می‌شد (verify_password هش می‌خواهد ⇒ ورود
# ناممکن)، چک تکراری روی «admin» بود ولی «09120000000» ساخته می‌شد (⇒ اجرای دوباره خراب)،
# sub_role ست نمی‌شد و موبایل نرمال نمی‌شد.
#
# اجرا (از ریشهٔ ریپو):
#   DATABASE_URL=sqlite:////tmp/e2e_create_admin.db JWT_SECRET_KEY=<hex> \
#     python3 -m pytest Kharazmi_Server/tests/test_create_admin_script.py -q
import os
import subprocess
import sys
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(SERVER_DIR)

MOBILE = "09120000077"
PASSWORD = "strong-pass-123"
FULL_NAME = "مدیر آزمایشی"


def _fresh_db_path(name):
    path = f"/tmp/{name}.db"
    if os.path.exists(path):
        os.remove(path)
    return path


class TestCreateAdminScript(unittest.TestCase):
    def setUp(self):
        self.db_path = _fresh_db_path("kharazmi_create_admin_test")
        self.env = dict(os.environ)
        self.env["DATABASE_URL"] = f"sqlite:///{self.db_path}"
        self.env.setdefault("JWT_SECRET_KEY", "create-admin-script-secret")
        self.env.pop("PYTHONPATH", None)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            path = self.db_path + suffix
            if os.path.exists(path):
                os.remove(path)

    def run_script(self, stdin_text):
        return subprocess.run(
            [sys.executable, os.path.join("scripts", "create_admin.py")],
            cwd=SERVER_DIR, env=self.env, input=stdin_text,
            capture_output=True, text=True, timeout=120,
        )

    def admin_rows(self):
        # اگر اسکریپت قبل از هر نوشتن برگشته باشد، فایل دیتابیس هم ساخته نشده است.
        if not os.path.exists(self.db_path):
            return []
        engine = create_engine(f"sqlite:///{self.db_path}")
        db = sessionmaker(bind=engine)()
        try:
            import models
            return db.query(models.User).filter(models.User.username == MOBILE).all()
        finally:
            db.close()
            engine.dispose()

    # ------------------------------------------------------------------
    def test_1_creates_hashed_admin_with_role_and_no_branch(self):
        result = self.run_script(f"y\n{MOBILE}\n{FULL_NAME}\n{PASSWORD}\n{PASSWORD}\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        rows = self.admin_rows()
        self.assertEqual(len(rows), 1, "باید دقیقاً یک مدیر ساخته شود")
        admin = rows[0]
        self.assertEqual(admin.role, "admin")
        self.assertEqual(admin.sub_role, "admin", "سیاست A1: sub_role باید صریح باشد")
        self.assertIsNone(admin.branch_id, "مدیر کل بدون شعبه است (دسترسی سراسری)")
        self.assertEqual(admin.full_name, FULL_NAME)

        # رمز هرگز plaintext ذخیره نمی‌شود و با هش تأیید می‌شود
        self.assertNotEqual(admin.password, PASSWORD)
        self.assertNotIn(PASSWORD, admin.password)
        from dependencies import verify_password
        self.assertTrue(verify_password(PASSWORD, admin.password),
                        "رمز ذخیره‌شده باید هشِ همین رمز باشد")

    def test_2_created_admin_can_actually_log_in_and_call_me(self):
        """سنجش واقعی قرارداد: login + /auth/me روی همان دیتابیس ساخته‌شده."""
        self.assertEqual(self.run_script(f"y\n{MOBILE}\n{FULL_NAME}\n{PASSWORD}\n{PASSWORD}\n").returncode, 0)
        probe = (
            "import os, sys; sys.path.insert(0, os.getcwd())\n"
            "from fastapi.testclient import TestClient\n"
            "from main import app\n"
            "c = TestClient(app)\n"
            f"r = c.post('/auth/login', json={{'mobile': '{MOBILE}', 'password': '{PASSWORD}'}})\n"
            "assert r.status_code == 200, r.text\n"
            "token = r.json()['token']\n"
            "assert r.json()['role'] == 'admin', r.text\n"
            "me = c.get('/auth/me', headers={'Authorization': f'Bearer {token}'})\n"
            "assert me.status_code == 200, me.text\n"
            "print('LOGIN_OK', me.json().get('role'))\n"
        )
        result = subprocess.run([sys.executable, "-c", probe], cwd=SERVER_DIR, env=self.env,
                                capture_output=True, text=True, timeout=180)
        self.assertIn("LOGIN_OK", result.stdout, result.stdout + result.stderr)

    def test_3_second_run_is_idempotent(self):
        first = self.run_script(f"y\n{MOBILE}\n{FULL_NAME}\n{PASSWORD}\n{PASSWORD}\n")
        self.assertEqual(first.returncode, 0, first.stdout)
        second = self.run_script(f"y\n{MOBILE}\n{FULL_NAME}\n{PASSWORD}\n{PASSWORD}\n")
        self.assertEqual(second.returncode, 3, second.stdout + second.stderr)
        self.assertIn("از قبل وجود دارد", second.stdout)
        self.assertEqual(len(self.admin_rows()), 1, "اجرای دوباره نباید رکورد تکراری بسازد")

    def test_4_rejects_short_password_and_bad_mobile_without_writing(self):
        short = self.run_script(f"y\n{MOBILE}\n{FULL_NAME}\n123\n123\n")
        self.assertEqual(short.returncode, 2, short.stdout + short.stderr)
        self.assertEqual(self.admin_rows(), [], "رمز کوتاه نباید کاربری بسازد")

        bad_mobile = self.run_script(f"y\n12345\n{FULL_NAME}\n{PASSWORD}\n{PASSWORD}\n")
        self.assertEqual(bad_mobile.returncode, 2, bad_mobile.stdout + bad_mobile.stderr)
        self.assertEqual(self.admin_rows(), [], "موبایل نامعتبر نباید کاربری بسازد")

    def test_5_mobile_is_normalized_before_saving(self):
        result = self.run_script(f"y\n+98 912 000 0077\n{FULL_NAME}\n{PASSWORD}\n{PASSWORD}\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rows = self.admin_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].username, MOBILE, "نام کاربری باید شکل canonical داشته باشد")

    def test_6_aborts_when_confirmation_is_declined(self):
        result = self.run_script(f"n\n")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(self.admin_rows(), [], "بدون تأیید نباید چیزی نوشته شود")


if __name__ == "__main__":
    unittest.main()
