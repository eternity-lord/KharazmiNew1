# test_suite_cwd_independence.py
# تست‌های B1 — اجرای سوئیت نباید به پوشهٔ اجرا وابسته باشد
#
# باگی که این تست‌ها قفل می‌کنند:
#   ۷ فراخوانی `open("Kharazmi_Server/routers/x.py")` در test_audit.py، test_dashboard.py و
#   test_dashboard_performance.py مسیر را **نسبت به cwd** باز می‌کردند. اجرای سوئیت از ریشهٔ ریپو
#   سبز بود، ولی از داخل `Kharazmi_Server/` پنج تست با `FileNotFoundError` شکست می‌خوردند
#   (که در Task 6 به‌عنوان failureهای وابسته به cwd مستند شد) — یعنی «تست سبز» به مسیر اجرا
#   وابسته بود و همین می‌توانست رگرسیون‌ها را در CI بی‌سروصدا پنهان کند.
#
# فیکس B1: مسیرها با `_server_file(...)` (نسبت به `__file__`) باز می‌شوند و `pytest.ini` ریشه
# مسیر کشف تست‌ها را تثبیت می‌کند. این تست دو سطح را می‌سنجد:
#   1) ساختاری: نبود الگوی مسیرِ نسبی به Kharazmi_Server در فایل‌های تست + وجود pytest.ini.
#   2) رفتاری: اجرای واقعیِ ۵ تستِ قبلاً شکست‌خورده با cwd = `Kharazmi_Server/` در یک زیرفرایند.
#
# اجرا (از ریشهٔ ریپو):
#   DATABASE_URL=sqlite:////tmp/b1.db JWT_SECRET_KEY=<hex> \
#     python3 -m pytest Kharazmi_Server/tests/test_suite_cwd_independence.py -q
import io
import os
import subprocess
import sys
import tokenize
import unittest

# FIX(tests-dir): این فایل اکنون در `Kharazmi_Server/tests/` است ⇒
#   TESTS_DIR = پوشهٔ همین فایل | SERVER_DIR = یک سطح بالاتر | REPO_ROOT = دو سطح بالاتر
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.dirname(TESTS_DIR)
REPO_ROOT = os.path.dirname(SERVER_DIR)

# همان ۵ تستی که پیش از B1 از داخل Kharazmi_Server/ با FileNotFoundError می‌شکستند
PREVIOUSLY_CWD_DEPENDENT = [
    "test_audit.py::TestAuditRadar::test_no_silent_except_pass",
    "test_audit.py::TestAuditRadar::test_joinedload_used_for_nplus1",
    "test_audit.py::TestAuditRadar::test_finance_uses_central_installment_validation",
    "test_dashboard.py::TestDashboardKPIs::test_dashboard_isolated_no_finance_touch",
    "test_dashboard_performance.py::TestDashboardPerformance::test_uses_sql_counts_and_the_shared_revenue_definition",
]

# مسیر نسبیِ وابسته به cwd: open("Kharazmi_Server/...") یا Path('./Kharazmi_Server/...')
# سنجش روی «کد» انجام می‌شود (tokenize) تا کامنت‌های توضیحیِ همین فیکس، الگوی مخرب به حساب نیایند.
RELATIVE_SERVER_PREFIXES = ("./Kharazmi_Server/", "Kharazmi_Server/")
PATH_CALL_NAMES = {"open", "Path"}


def relative_server_path_lines(path):
    """شمارهٔ خطوطی که مسیر Kharazmi_Server را نسبت به cwd باز می‌کنند (فقط کد، بدون کامنت)."""
    hits = []
    with open(path, "rb") as handle:
        tokens = list(tokenize.tokenize(handle.readline))
    for index, token in enumerate(tokens):
        if token.type != tokenize.STRING:
            continue
        if not any(prefix in token.string for prefix in RELATIVE_SERVER_PREFIXES):
            continue
        # توکن قبلیِ معنادار باید '(' و قبل از آن نام open/Path باشد
        previous = [t for t in tokens[:index] if t.type not in (tokenize.NL, tokenize.NEWLINE,
                                                                tokenize.INDENT, tokenize.DEDENT,
                                                                tokenize.COMMENT)]
        if len(previous) >= 2 and previous[-1].string == "(" and previous[-2].string in PATH_CALL_NAMES:
            hits.append(token.start[0])
    return hits


class TestNoRelativeServerPaths(unittest.TestCase):
    def test_no_relative_kharazmi_server_paths_in_tests(self):
        offenders = []
        for name in sorted(os.listdir(TESTS_DIR)):
            if not (name.startswith("test_") and name.endswith(".py")):
                continue
            path = os.path.join(TESTS_DIR, name)
            offenders.extend(f"{name}:{lineno}" for lineno in relative_server_path_lines(path))
        self.assertEqual(offenders, [], f"مسیر وابسته به cwd در تست‌ها پیدا شد: {offenders}")

    def test_relative_and_absolute_helpers_agree(self):
        """هر دو سبکِ استخراج مسیر (نسبت به __file__) باید به یک فایل واقعی برسند."""
        for relative in ("routers/audit.py", "routers/dashboard.py", "routers/dunning.py",
                         "routers/finance.py"):
            absolute = os.path.join(SERVER_DIR, *relative.split("/"))
            self.assertTrue(os.path.isfile(absolute), f"فایل سرور پیدا نشد: {absolute}")


class TestPytestIniPinsDiscovery(unittest.TestCase):
    def test_root_pytest_ini_exists(self):
        ini = os.path.join(REPO_ROOT, "pytest.ini")
        self.assertTrue(os.path.isfile(ini),
                        "pytest.ini ریشه برای تثبیت مسیر کشف تست‌ها لازم است (تصمیم B1)")

    def test_root_pytest_ini_points_to_server_suite(self):
        with open(os.path.join(REPO_ROOT, "pytest.ini"), encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn("[pytest]", content)
        self.assertIn("testpaths", content)
        self.assertIn("Kharazmi_Server", content,
                      "testpaths باید مجموعهٔ تست‌های Kharazmi_Server را تثبیت کند")
        self.assertIn("KharazmiAdmin", content,
                      "درخت اندروید باید از کشف تست‌ها بیرون بماند")


class TestSuiteRunsFromServerDirectory(unittest.TestCase):
    """سنجش رفتاری: همان ۵ تست باید از داخل Kharazmi_Server/ هم سبز باشند."""

    def test_previously_failing_tests_pass_with_server_cwd(self):  # noqa: D401
        env = dict(os.environ)
        env.setdefault("JWT_SECRET_KEY", "b1-cwd-independence-secret")
        env.setdefault("DATABASE_URL", "sqlite:////tmp/b1_cwd_independence.db")
        env.pop("PYTHONPATH", None)  # مثل اجرای مستند پروژه: اتکا به مسیر خودِ تست
        result = subprocess.run(
            [sys.executable, "-m", "pytest", *[os.path.join("tests", node) for node in PREVIOUSLY_CWD_DEPENDENT],
             "-q", "-p", "no:randomly"],
            cwd=SERVER_DIR, env=env, capture_output=True, text=True, timeout=600,
        )
        tail = (result.stdout or "")[-1500:] + (result.stderr or "")[-500:]
        self.assertEqual(result.returncode, 0,
                         f"اجرای تست‌ها از داخل Kharazmi_Server/ شکست خورد:\n{tail}")
        self.assertNotIn("FileNotFoundError", result.stdout or "",
                         f"مسیر وابسته به cwd برگشته است:\n{tail}")

    def test_single_test_file_runs_from_repo_root(self):
        """از ریشه هم باید همان تست‌ها (با مسیر صریح) سبز بمانند."""
        env = dict(os.environ)
        env.setdefault("JWT_SECRET_KEY", "b1-cwd-independence-secret")
        env.setdefault("DATABASE_URL", "sqlite:////tmp/b1_cwd_root.db")
        env.pop("PYTHONPATH", None)
        result = subprocess.run(
            [sys.executable, "-m", "pytest",
             os.path.join(TESTS_DIR, "test_audit.py::TestAuditRadar::test_no_silent_except_pass"),
             "-q", "-p", "no:randomly"],
            cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=600,
        )
        self.assertEqual(result.returncode, 0,
                         (result.stdout or "")[-1200:] + (result.stderr or "")[-500:])


if __name__ == "__main__":
    unittest.main()
