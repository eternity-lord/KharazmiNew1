# test_storage_paths.py
# تست‌های باگ «مسیر ذخیره‌سازی فایل» — کشف‌شده توسط CI (نوبت ۶ / B2)
#
# باگی که این تست‌ها قفل می‌کنند:
#   ۱) سه روتر مسیر مطلقِ ماشین توسعه‌دهنده را هاردکد کرده بودند:
#        homework.py : "/home/user/uploads/homework"
#        exams.py    : "/home/user/uploads/report_cards"
#        messages.py : "/home/user/uploads/messages"
#      و هر سه در **زمان import** `os.makedirs` می‌زدند. روی هر ماشینی که `/home/user` ندارد
#      (سرور آموزشگاه با کاربر دیگر، docker، GitHub Actions) برنامه با PermissionError بالا نمی‌آید
#      ⇒ آپلود تکلیف، کارنامه و پیوست پیام‌رسان کاملاً از کار می‌افتد.
#   ۲) مسیر پروفایل/لوگو **نسبت به پوشهٔ اجرا** بود: os.path.join("uploads/profiles", …)
#      ⇒ فایل‌ها بسته به پوشهٔ اجرای سرور در دو جای مختلف ذخیره می‌شدند و بعد از تغییر پوشهٔ اجرا
#      با ۴۰۴ «فایل یافت نشد» روبه‌رو می‌شدند (و بیرون از بکاپ پروژه می‌ماندند).
#
# قرارداد جدید: یک ریشهٔ واحد `Kharazmi_Server/uploads/` (یا `KHARAZMI_UPLOAD_ROOT`)،
# و مسیرهای قدیمی فقط برای خواندن/حذف بررسی می‌شوند تا سابقه گم نشود.
#
# اجرا (از ریشهٔ ریپو):
#   DATABASE_URL=sqlite:////tmp/storage.db JWT_SECRET_KEY=<hex> \
#     python3 -m pytest Kharazmi_Server/test_storage_paths.py -q
import ast
import datetime
import os
import shutil
import tempfile
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
import storage
from dependencies import get_db, hash_password
from main import app

# FIX(tests-dir): این فایل در tests/ است؛ کد سرور یک سطح بالاتر قرار دارد.
SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEARCH_DIRS = (SERVER_DIR, os.path.join(SERVER_DIR, "routers"))
# مسیرهای مطلقِ ماشینی که نباید در کد باشند (فقط storage.py به‌عنوان سازگاری عقب‌رو مجاز است)
FORBIDDEN_ABSOLUTE_PREFIXES = ("/home/user", "/root/", "/Users/", "/var/www", "C:\\")
# storage.py: تک‌جایی که مسیر قدیمی برای سازگاری عقب‌رو مجاز است
# test_storage_paths.py: همین فایل گارد (الگوها و مسیرهای نمونه در خودش تعریف شده‌اند)
LEGACY_EXEMPT_FILES = {"storage.py", os.path.basename(__file__)}


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


def iter_source_files():
    for base in SEARCH_DIRS:
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            if name.endswith(".py"):
                yield os.path.join(base, name)


def string_literals(path):
    """همهٔ رشته‌های ثابتِ کد (بدون کامنت‌ها) با شمارهٔ خط."""
    tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.lineno, node.value


class TestNoMachineSpecificPaths(unittest.TestCase):
    def test_no_hardcoded_machine_paths_outside_storage_module(self):
        """هیچ ماژولی جز storage.py نباید مسیر مطلق ماشینی داشته باشد."""
        offenders = []
        for path in iter_source_files():
            if os.path.basename(path) in LEGACY_EXEMPT_FILES:
                continue
            for lineno, value in string_literals(path):
                if value.startswith(FORBIDDEN_ABSOLUTE_PREFIXES):
                    offenders.append(f"{os.path.basename(path)}:{lineno} → {value}")
        self.assertEqual(offenders, [],
                         "مسیر مطلق ماشینی در کد پیدا شد (روی سرور دیگر باعث crash در import می‌شود):\n"
                         + "\n".join(offenders))

    def test_storage_module_uses_legacy_path_only_for_reads(self):
        """مسیر قدیمی در storage.py فقط در فهرست سازگاری عقب‌رو مجاز است، نه برای نوشتن."""
        source = open(os.path.join(SERVER_DIR, "storage.py"), encoding="utf-8").read()
        self.assertIn("/home/user/uploads", source)
        # فقط در تابع legacy_upload_roots به‌عنوان ریشهٔ قدیمی
        body = source.split("def legacy_upload_roots")[1].split("def resolve_existing")[0]
        self.assertIn("/home/user/uploads", body)
        # و هیچ makedirs/نوشتنی روی مسیر قدیمی نباید باشد
        self.assertNotIn("makedirs", body)

    def test_no_cwd_relative_upload_writes(self):
        """الگوی قدیمی os.path.join("uploads/", …) / makedirs("uploads/…") نباید برگردد."""
        offenders = []
        guard_file = os.path.basename(__file__)
        for path in iter_source_files():
            if os.path.basename(path) == guard_file:
                continue  # خودِ همین گارد، الگوها را به‌عنوان رشته در خود دارد
            for lineno, line in enumerate(open(path, encoding="utf-8"), start=1):
                stripped = line.split("#", 1)[0]
                if "os.path.join(\"uploads" in stripped or "os.path.join('uploads" in stripped:
                    offenders.append(f"{os.path.basename(path)}:{lineno}")
                if "makedirs(\"uploads" in stripped or "makedirs('uploads" in stripped:
                    offenders.append(f"{os.path.basename(path)}:{lineno}")
        self.assertEqual(offenders, [], f"مسیر نسبی به cwd برگشته است: {offenders}")


class TestUploadRootResolution(unittest.TestCase):
    def tearDown(self):
        os.environ.pop(storage.UPLOAD_ROOT_ENV, None)

    def test_default_root_is_inside_project(self):
        os.environ.pop(storage.UPLOAD_ROOT_ENV, None)
        root = storage.upload_root()
        self.assertTrue(root.startswith(storage.BASE_DIR),
                        f"ریشهٔ پیش‌فرض باید داخل پروژه باشد، نه بیرون: {root}")
        self.assertTrue(os.path.isabs(root))

    def test_env_override_changes_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ[storage.UPLOAD_ROOT_ENV] = tmp
            self.assertEqual(os.path.realpath(storage.upload_root()), os.path.realpath(tmp))
            created = storage.storage_dir("homework")
            self.assertEqual(os.path.realpath(created), os.path.realpath(os.path.join(tmp, "homework")))
            self.assertTrue(os.path.isdir(created))
            self.assertTrue(os.path.isabs(storage.storage_path("report_cards", "x.pdf")))

    def test_storage_path_does_not_create_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ[storage.UPLOAD_ROOT_ENV] = tmp
            path = storage.storage_path("nothing", "here.pdf")
            self.assertFalse(os.path.exists(path), "storage_path فقط مسیر می‌سازد، نه پوشه")

    def test_resolve_existing_prefers_current_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ[storage.UPLOAD_ROOT_ENV] = tmp
            target = os.path.join(storage.storage_dir("profiles"), "a.png")
            open(target, "wb").write(b"x")
            self.assertEqual(storage.resolve_existing("profiles", "a.png"), target)
            self.assertIsNone(storage.resolve_existing("profiles", "missing.png"))

    def test_resolve_existing_falls_back_to_legacy_root(self):
        """فایل‌های نوشته‌شده با مسیرهای قدیمی باید همچنان پیدا شوند (سابقه گم نشود)."""
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as legacy:
            os.environ[storage.UPLOAD_ROOT_ENV] = tmp
            legacy_file = os.path.join(legacy, "profiles", "old.png")
            os.makedirs(os.path.dirname(legacy_file), exist_ok=True)
            open(legacy_file, "wb").write(b"old")
            original = storage.legacy_upload_roots
            storage.legacy_upload_roots = lambda: [legacy]
            try:
                self.assertEqual(storage.resolve_existing("profiles", "old.png"), legacy_file)
            finally:
                storage.legacy_upload_roots = original


class TestUploadEndpointsUseCanonicalRoot(unittest.TestCase):
    def setUp(self):
        # ریشهٔ آپلود به یک پوشهٔ موقت منتقل می‌شود تا چیزی در پروژه نوشته نشود
        self.tmp_uploads = tempfile.mkdtemp(prefix="storage_test_")
        self._prev_env = os.environ.get(storage.UPLOAD_ROOT_ENV)
        os.environ[storage.UPLOAD_ROOT_ENV] = self.tmp_uploads

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                               poolclass=StaticPool)
        models.Base.metadata.create_all(engine)
        self.engine = engine
        Session = sessionmaker(bind=engine, expire_on_commit=False)
        self.db = Session()
        now = datetime.datetime.now()
        self.db.add_all([
            models.Branch(id=1, name="شعبه یک", active=True),
            models.Teacher(id=1, first_name="معلم", last_name="تست", mobile="09120000001",
                           national_code="0001000131", password=hash_password("x"),
                           is_approved=True, is_deleted=False, branch_id=1),
            models.Course(id=1, title="ریاضی", code="ST-1", teacher_id=1, branch_id=1,
                          grade_level="دهم", class_time="16:00", days_of_week="شنبه",
                          teacher_session_price=100000, is_deleted=False, is_admin_approved=True),
            # user_id = سایهٔ نقش student؛ get_session_student از همین FK استفاده می‌کند
            models.Student(id=1, student_code=1, first_name="علی", last_name="تست",
                           national_code="0012345691", student_mobile="09121111111",
                           branch_id=1, wallet_teacher=0, wallet_institute=0, wallet_balance=0,
                           is_deleted=False, user_id=2),
            models.Enrollment(id=1, student_id=1, course_id=1, branch_id=1,
                              register_date="1405/06/01", total_tuition=1000000, total_paid=0,
                              is_deleted=False),
            models.User(id=1, username="admin-global", password="x", full_name="مدیر",
                        role="admin", sub_role="admin", branch_id=None),
            models.User(id=2, username="student:1", password="x", full_name="شاگرد",
                        role="student", sub_role="student", branch_id=1),
        ])
        self.db.add_all([
            models.UserSession(token="tok-admin", user_id=1, sub_role="admin", created_at=now),
            models.UserSession(token="tok-student", user_id=2, sub_role="student", created_at=now),
        ])
        self.db.add(models.Homework(id=1, course_id=1, teacher_id=1, title="تمرین ۱",
                                    description="تست", due_date="1405/06/10", status="pending"))
        self.db.commit()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()
        if self._prev_env is None:
            os.environ.pop(storage.UPLOAD_ROOT_ENV, None)
        else:
            os.environ[storage.UPLOAD_ROOT_ENV] = self._prev_env
        shutil.rmtree(self.tmp_uploads, ignore_errors=True)

    def test_homework_upload_lands_in_canonical_root(self):
        files = {"file": ("hw.pdf", b"%PDF-1.4 test content", "application/pdf")}
        r = self.client.post("/homework/submissions/1/submit", files=files, headers=hdr("tok-student"))
        self.assertEqual(r.status_code, 200, r.text)
        stored = os.path.join(self.tmp_uploads, "homework")
        saved = os.listdir(stored)
        self.assertEqual(len(saved), 1, f"فایل تکلیف باید در ریشهٔ تعیین‌شده ذخیره شود: {saved}")
        self.assertTrue(os.path.getsize(os.path.join(stored, saved[0])) > 0)

    def test_profile_upload_lands_in_canonical_root(self):
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        r = self.client.post("/students/1/upload_photo",
                             files={"file": ("me.png", png, "image/png")}, headers=hdr("tok-admin"))
        self.assertEqual(r.status_code, 200, r.text)
        name = r.json()["profile_image"]
        expected = os.path.join(self.tmp_uploads, "profiles", name)
        self.assertTrue(os.path.isfile(expected), f"عکس پروفایل باید در {expected} باشد")

        # و همان فایل باید از مسیر سرو فایل قابل خواندن باشد (سازگاری نوشتن/خواندن)
        served = self.client.get(f"/uploads/{name}", headers=hdr("tok-admin"))
        self.assertEqual(served.status_code, 200, served.text)
        self.assertEqual(served.content, png)

    def test_served_file_falls_back_to_legacy_directory(self):
        """عکس‌های قدیمی که در مسیر قبلی (نسبت به cwd) مانده‌اند باید همچنان سرو شوند."""
        legacy = tempfile.mkdtemp(prefix="legacy_uploads_")
        try:
            os.makedirs(os.path.join(legacy, "profiles"), exist_ok=True)
            with open(os.path.join(legacy, "profiles", "legacy.png"), "wb") as handle:
                handle.write(b"\x89PNG\r\n\x1a\nlegacy")
            original = storage.legacy_upload_roots
            import main as main_module
            storage.legacy_upload_roots = lambda: [legacy]
            main_module.resolve_existing = lambda *parts: storage.resolve_existing(*parts)
            try:
                served = self.client.get("/uploads/legacy.png", headers=hdr("tok-admin"))
                self.assertEqual(served.status_code, 200, served.text)
                self.assertIn(b"legacy", served.content)
            finally:
                storage.legacy_upload_roots = original
        finally:
            shutil.rmtree(legacy, ignore_errors=True)

    def test_path_traversal_still_blocked(self):
        for bad in ("..%2Fetc%2Fpasswd", ".hidden", "a/b"):
            r = self.client.get(f"/uploads/{bad}", headers=hdr("tok-admin"))
            self.assertIn(r.status_code, (400, 404), f"{bad} → {r.status_code}")

    def test_no_file_written_inside_project_during_uploads(self):
        """قبل از فیکس، فایل‌ها بیرون از ریشهٔ پروژه/در مسیر ماشینی می‌رفتند."""
        project_uploads = os.path.join(SERVER_DIR, "uploads")
        before = set()
        if os.path.isdir(project_uploads):
            for root, _dirs, files in os.walk(project_uploads):
                before.update(os.path.join(root, f) for f in files)
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
        self.client.post("/students/1/upload_photo",
                         files={"file": ("me2.png", png, "image/png")}, headers=hdr("tok-admin"))
        after = set()
        if os.path.isdir(project_uploads):
            for root, _dirs, files in os.walk(project_uploads):
                after.update(os.path.join(root, f) for f in files)
        self.assertEqual(before, after, f"با override محیطی نباید فایلی در پروژه نوشته شود: {after - before}")


if __name__ == "__main__":
    unittest.main()
