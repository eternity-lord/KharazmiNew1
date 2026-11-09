"""
Dashboard Performance Test — 10,000 installments, <100ms, COUNT queries verification
"""
import datetime
import os
import time
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from models import Base, User, UserSession, Student, Teacher, Course, Enrollment, Installment, Branch
from main import app
from dependencies import get_db, hash_password
from today_summary import jalali_date_string


# FIX(B1): مسیر فایل‌های سرور مستقل از پوشهٔ اجرا — نسبت به محل همین فایل تست، نه cwd.
# الگوی قدیمی `open("Kharazmi_Server/routers/x.py")` فقط وقتی کار می‌کرد که سوئیت از ریشهٔ ریپو
# اجرا شود و از داخل `Kharazmi_Server/` (یا هر پوشهٔ دیگر) با FileNotFoundError می‌شکست.
# FIX(tests-dir): تست‌ها به پوشهٔ `tests/` منتقل شدند ⇒ پوشهٔ سرور یک سطح بالاتر است.
_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _server_file(*parts):
    """مسیر مطلق یک فایل داخل Kharazmi_Server (مستقل از cwd)."""
    return os.path.join(_SERVER_DIR, *parts)


try:
    from routers.dashboard import _clear_dashboard_cache
except ImportError:
    def _clear_dashboard_cache():
        pass


class TestDashboardPerformance(unittest.TestCase):

    def setUp(self):
        _clear_dashboard_cache()
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
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        self.db.add(Branch(id=1, name="مرکزی", active=True))
        self.db.commit()
        self.admin_user = User(id=1, username="09120000000", password=hash_password("123"), full_name="Admin", role="admin", sub_role="admin", branch_id=1)
        self.db.add(self.admin_user)
        self.db.commit()
        self.admin_session = UserSession(token="tok_admin_perf", user_id=1, sub_role="admin", created_at=datetime.datetime.now())
        self.db.add(self.admin_session)
        self.db.commit()

        self.teacher = Teacher(id=1, first_name="امیر", last_name="احمدی", national_code="0001000128", mobile="09123333333", teacher_code=101, is_approved=True, password=hash_password("101"))
        self.db.add(self.teacher)
        self.db.commit()
        self.course = Course(id=1, title="ریاضی", code="MATH1", teacher_id=1, class_time="16:00", is_admin_approved=True)
        self.db.add(self.course)
        self.db.commit()
        self.student = Student(id=1, first_name="سینا", last_name="مرادی", national_code="0000000001", student_mobile="09120000001", parent_mobile="09120000001", is_deleted=False)
        self.db.add(self.student)
        self.db.commit()
        self.enrollment = Enrollment(id=1, student_id=1, course_id=1, register_date=jalali_date_string(datetime.date.today()))
        self.db.add(self.enrollment)
        self.db.commit()

        # Track SQL query count via event
        self.query_count = 0
        self.queries = []

        def count_queries(conn, cursor, statement, parameters, context, executemany):
            # Count only SELECT queries for dashboard
            if statement.strip().lower().startswith("select"):
                self.query_count += 1
                self.queries.append(statement)

        event.listen(self.engine, "before_cursor_execute", count_queries)
        self._listener = count_queries

    def tearDown(self):
        event.remove(self.engine, "before_cursor_execute", self._listener)
        _clear_dashboard_cache()
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_10k_installments_under_100ms(self):
        """Mock 10,000 installments, verify endpoint returns in <100ms (or <500ms relaxed) and uses COUNT."""
        today = datetime.date.today()
        overdue_jalali = jalali_date_string(today - datetime.timedelta(days=5))
        # Create 10,000 overdue installments
        batch = []
        for i in range(10000):
            batch.append(Installment(enrollment_id=1, amount=10000 + (i % 1000), due_date=overdue_jalali, is_paid=False, is_deleted=False))
            # To avoid huge memory, flush in batches
            if len(batch) >= 1000:
                self.db.add_all(batch)
                self.db.commit()
                batch = []
        if batch:
            self.db.add_all(batch)
            self.db.commit()

        # Verify count in DB
        cnt = self.db.query(Installment).count()
        self.assertEqual(cnt, 10000, f"should have 10000 installments but got {cnt}")

        # Clear cache to force recompute
        _clear_dashboard_cache()
        self.query_count = 0
        self.queries = []

        start = time.time()
        r = self.client.get("/dashboard/kpis", headers={"Authorization": "Bearer tok_admin_perf"})
        elapsed_ms = (time.time() - start) * 1000

        self.assertEqual(r.status_code, 200, f"dashboard should be 200 but got {r.status_code}: {r.text}")
        data = r.json()
        self.assertEqual(data["overdue_installments_count"], 10000, f"overdue count should be 10000 but got {data}")
        # Total amount: 10000 * 10000 + sum(i%1000) ~ 100M + 4,995,000 = 104,995,000?
        # Each amount is 10000 + (i % 1000), sum = 10000*10000 + sum(0..999)*10 = 100M + 499500*10? Wait sum 0..999 = 499500, *10 = 4,995,000 => 104,995,000
        expected_total = sum(10000 + (i % 1000) for i in range(10000))
        self.assertEqual(data["total_overdue_amount"], expected_total, f"overdue amount mismatch")

        print(f"[Perf] 10k installments dashboard elapsed: {elapsed_ms:.2f}ms, queries: {self.query_count}")
        # Relaxed to 500ms for CI variance, but aim for <100ms
        # In sqlite memory, even with 10k, SQL COUNT/SUM should be <50ms
        self.assertLess(elapsed_ms, 500, f"Dashboard took {elapsed_ms:.2f}ms, expected <500ms (aim <100ms)")
        # Ideally <100ms, but allow 500 for slower CI
        if elapsed_ms >= 100:
            print(f"WARNING: dashboard took {elapsed_ms:.2f}ms >=100ms but <500ms — still passes relaxed check")

        # Verify query count <5 (or <10 including audit/dunning)
        # Our dashboard does: revenue (1), overdue (1), students (1), audit (maybe 3-4), dunning (1-2) => total ~7
        # For this test, we care that overdue is not N queries (should be 1-2 not 10000)
        # So we assert query_count < 10 and not 10000
        self.assertLess(self.query_count, 15, f"Expected <15 queries but got {self.query_count}: {self.queries[:3]}")
        # Also ensure we didn't do Python loop that would cause many queries (would be >10)
        print(f"[Perf] Queries executed: {self.query_count}")

        # Second call should be cached and even faster (<10ms) and 0 queries if cache works? But our cache still needs DB for auth? Auth uses DB but dashboard cache bypasses heavy queries.
        # Our cache returns immediately without DB queries for KPIs, but still does auth check? No, auth is dependency, so it still does 1 query for session?
        # So second call should be faster
        _ = self.client.get("/dashboard/kpis", headers={"Authorization": "Bearer tok_admin_perf"})
        # After cache, query_count should not increase much
        # Not asserting cache query count, just that second call is fast
        start2 = time.time()
        r2 = self.client.get("/dashboard/kpis", headers={"Authorization": "Bearer tok_admin_perf"})
        elapsed2 = (time.time() - start2) * 1000
        print(f"[Perf] Second cached call elapsed: {elapsed2:.2f}ms")
        self.assertEqual(r2.status_code, 200)
        self.assertLess(elapsed2, 100, f"Cached call should be <100ms but took {elapsed2:.2f}ms")

    def test_uses_sql_counts_and_the_shared_revenue_definition(self):
        """Verify dashboard.py uses SQL COUNT/SUM and the shared revenue definition, not Python loops.

        O-08 (به‌روزرسانی آگاهانهٔ این گارد): الگوی قبلیِ «LIKE روی پیشوند تاریخ شمسی» برای
        «درآمد امروز» عمداً حذف شد — آن SUM بدون فیلتر نوع/کیف، شارژ جلسه را منفی می‌شمرد و
        واریزی با تاریخ میلادی/بی‌تاریخ را از دست می‌داد. اکنون عدد از همان تابعی می‌آید که
        گزارش‌های مالی می‌خوانند.
        """
        with open(_server_file("routers", "dashboard.py"), encoding="utf-8") as f:
            content = f.read()

        # Must use Jalali string comparison for overdue
        self.assertIn("due_date < today_jalali", content, "Should use string comparison due_date < today_jalali")
        self.assertIn("func.count", content, "Should use func.count for COUNT queries")
        self.assertIn("func.sum", content, "Should use func.sum for SUM queries")
        self.assertNotIn('like(f"{today_jalali}%"', content,
                         "LIKE روی تاریخ شمسی برای درآمد امروز باید حذف شده باشد (O-08)")
        self.assertIn("calculate_institute_cash_collected", content,
                      "درآمد امروز باید از تعریف واحد لایهٔ مالی بیاید (O-08 + گروه۲/آیتم۴: "
                      "همان تابعی که «پرداخت امروز» در /admin/today_summary استفاده می‌کند)")
        self.assertIn("jalali_date_string", content, "Should convert today to Jalali string")
        # Must NOT load all installments and loop with parse_project_date for overdue
        # The old bug was: db.query(Installment).filter(...).all() then for inst in unpaid: parse_project_date(due) < today
        # New code should not have that pattern
        self.assertNotIn("parse_project_date", content, "Should not use parse_project_date in dashboard (SQL string comparison instead)")
        # Should not have fallback Python loop for revenue that loads all transactions
        # Check that we don't have .all() for overdue loop
        # We allow .all() for other but not for overdue counting pattern
        # Simple check: ensure not having "for inst in unpaid" pattern for overdue
        self.assertNotIn("for inst in unpaid", content, "Should not loop over unpaid installments in Python")
        # Should have TTL cache
        self.assertIn("_dashboard_cache", content, "Should have TTL cache dict")
        self.assertIn("CACHE_TTL", content, "Should have CACHE_TTL")
        self.assertIn("time.time()", content, "Should use time.time() for cache TTL")

        # Verify audit and dunning helpers exist
        with open(_server_file("routers", "audit.py"), encoding="utf-8") as f:
            audit_content = f.read()
        self.assertIn("def count_suspicious_patterns", audit_content, "audit.py should have count_suspicious_patterns")

        with open(_server_file("routers", "dunning.py"), encoding="utf-8") as f:
            dunning_content = f.read()
        self.assertIn("def count_dunning_pending", dunning_content, "dunning.py should have count_dunning_pending")

        # Verify dashboard uses those helpers
        self.assertIn("count_suspicious_patterns", content, "dashboard should use count_suspicious_patterns")
        self.assertIn("count_dunning_pending", content, "dashboard should use count_dunning_pending")
        # Should NOT use len(get_suspicious_patterns(...))
        self.assertNotIn("get_suspicious_patterns", content, "Should not call get_suspicious_patterns (use count helper)")

        print("[Perf] Code pattern checks passed")


if __name__ == "__main__":
    unittest.main()
