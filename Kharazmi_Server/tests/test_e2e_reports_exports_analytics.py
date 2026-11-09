# test_e2e_reports_exports_analytics.py
# ═══════════════════════════════════════════════════════════════════════════════
# سناریوی end-to-end #۶: «گزارش‌ها، خروجی‌ها و تحلیل‌ها»
#
# مسیر اپ (KharazmiAdmin):
#   ChartActivity.kt:75   → GET reports/chart-data
#   ReportActivity.kt:70  → GET reports/financial_summary
#   ApiInterfaces.kt:134-142 → GET exports/debtors · exports/overdue_installments · exports/audit_alerts (ResponseBody)
#   ApiInterfaces.kt:123  → GET kpis
#   ApiInterfaces.kt:96   → GET suspicious_patterns · :150-164 → GET audit-trail/logs
#   ApiInterfaces.kt:112-115 → GET dunning/drafts · POST dunning/send_batch
#   ReportActivity        → GET reports/debtors · reports/debtors/excel · reports/student_statement(+print)
#
# ⚠ فاز دیباگ: صفر تغییر در کد برنامه.
import csv
import datetime
import io as _io
import os
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from dependencies import get_db, hash_password, limiter
from main import app


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


def jalali_today():
    try:
        from today_summary import jalali_date_string
        return jalali_date_string(datetime.date.today())
    except Exception:
        return "1405/06/30"


class ReportWorld(unittest.TestCase):
    def setUp(self):
        self._limiter = limiter.enabled
        limiter.enabled = False
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                               poolclass=StaticPool)
        models.Base.metadata.create_all(engine)
        self.engine = engine
        self.db = sessionmaker(bind=engine, expire_on_commit=False)()
        now = datetime.datetime.now()

        import routers.dashboard as dash
        dash._dashboard_cache.clear()

        self.db.add(models.Branch(id=1, name="شعبه مرکزی", active=True))
        self.db.add(models.InstituteSettings(id=1, name="آموزشگاه خوارزمی", card_number="۶۰۳۷-۱"))
        self.db.add_all([
            models.User(id=101, username="09120000111", password=hash_password("a"), full_name="مدیر",
                        role="admin", sub_role="admin", branch_id=1),
            models.User(id=102, username="09120000112", password=hash_password("b"), full_name="منشی",
                        role="secretary", sub_role="secretary", branch_id=1),
            models.User(id=201, username="student:41", password="x", full_name="علی تست",
                        role="student", sub_role="student", branch_id=1),
        ])
        self.db.add(models.Teacher(id=51, first_name="مریم", last_name="معلم", mobile="09120000113",
                                   national_code="0012349001", password=hash_password("t"),
                                   is_approved=True, is_deleted=False, branch_id=1))
        self.db.add_all([
            models.Student(id=41, student_code=41, first_name="علی", last_name="تست",
                           national_code="0012349002", student_mobile="09120000114",
                           parent_mobile="09120000117", branch_id=1,
                           wallet_teacher=-300000, wallet_institute=-700000, wallet_balance=-1000000,
                           user_id=201, is_deleted=False),
            models.Student(id=42, student_code=42, first_name="بی‌بدهی", last_name="تست",
                           national_code="0012349003", student_mobile="09120000115", branch_id=1,
                           wallet_teacher=0, wallet_institute=0, wallet_balance=0, is_deleted=False),
            # نامِ آغازشده با «=» برای سنجش محافظت از CSV-injection
            models.Student(id=43, student_code=43, first_name="=CMD", last_name="خطر",
                           national_code="0012349004", student_mobile="09120000116", branch_id=1,
                           wallet_teacher=0, wallet_institute=-500000, wallet_balance=-500000,
                           is_deleted=False),
        ])
        self.db.add(models.Course(id=71, title="ریاضی دهم", code="700001", teacher_id=51, branch_id=1,
                                  is_deleted=False, grade_level="دهم", days_of_week="شنبه",
                                  class_time="17:30", teacher_session_price=100000))
        self.db.add_all([
            models.Enrollment(id=1, student_id=41, course_id=71, branch_id=1, register_date="1405/06/01",
                              shift="عصر", total_tuition=1000000, total_paid=0, is_deleted=False),
            models.Enrollment(id=2, student_id=42, course_id=71, branch_id=1, register_date="1405/06/01",
                              shift="عصر", total_tuition=500000, total_paid=500000, is_deleted=False),
        ])
        today = jalali_today()
        self.db.add_all([
            # درآمد امروز (برای KPI)
            models.Transaction(id=901, student_id=41, enrollment_id=1, course_id=71, branch_id=1,
                               amount=500000, payment_method="کارت", date=today, type="deposit",
                               target_wallet="institute", receiver="مدیر", description="پرداخت"),
            # ردیف «بی‌تاریخ/بی‌روش» — فیکس A3: نباید گزارش‌ها را بشکند یا حذف شود
            models.Transaction(id=902, student_id=41, enrollment_id=1, course_id=71, branch_id=1,
                               amount=250000, payment_method=None, date="", type="deposit",
                               target_wallet="institute", description="پرداخت بی‌تاریخ"),
            # سهم معلم و آموزشگاه برای چارت سهم‌ها
            models.Transaction(id=903, student_id=41, course_id=71, branch_id=1, amount=-200000,
                               payment_method="System", date=today, type="session_charge",
                               share_teacher=150000, share_institute=50000,
                               description="هزینه جلسه"),
        ])
        self.db.add_all([
            models.Installment(id=1, enrollment_id=1, amount=300000, due_date="1400/01/01", is_paid=False),
            models.Installment(id=2, enrollment_id=1, amount=300000, due_date="1410/01/01", is_paid=False),
            models.Installment(id=3, enrollment_id=1, amount=300000, due_date="1400/01/01", is_paid=True),
        ])
        self.db.add_all([
            models.UserSession(token="tok-admin", user_id=101, sub_role="admin", created_at=now),
            models.UserSession(token="tok-secretary", user_id=102, sub_role="secretary", created_at=now),
            models.UserSession(token="tok-student", user_id=201, sub_role="student", created_at=now),
        ])
        self.db.commit()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        limiter.enabled = self._limiter
        import routers.dashboard as dash
        dash._dashboard_cache.clear()
        self.db.close()
        self.engine.dispose()

    def csv_rows(self, resp):
        text = resp.content.decode("utf-8-sig")
        return list(csv.reader(_io.StringIO(text)))


class TestFinancialReports(ReportWorld):
    def test_1_financial_summary_uses_real_session_revenue(self):
        resp = self.client.get("/reports/financial_summary?user_type=institute", headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["user_type"], "institute")
        self.assertEqual(set(body["monthly"]) >= {"total", "collected", "uncollected"}, True, body)
        self.assertEqual(body["monthly"]["total"], 50000,
                         "درآمد مؤسسه از سهم جلسه می‌آید (InstituteShare.count_1) نه از کل پرداخت‌ها")
        self.assertEqual(body["monthly"]["collected"], 500000,
                         "وصول‌شدهٔ ماهانه = فقط ردیف‌های دارای تاریخ؛ پرداخت بی‌تاریخ (۲۵۰٬۰۰۰) "
                         "در این جمع نمی‌آید (در «صورت‌حساب شاگرد» می‌آید — تست ۴)")
        self.assertGreaterEqual(body["monthly"]["uncollected"], 0)

    def test_2_teacher_financial_summary_requires_teacher_id_and_valid_teacher(self):
        missing = self.client.get("/reports/financial_summary?user_type=teacher", headers=hdr("tok-admin"))
        self.assertEqual(missing.status_code, 400, missing.text)
        unknown = self.client.get("/reports/financial_summary?user_type=teacher&teacher_id=999",
                                  headers=hdr("tok-admin"))
        self.assertEqual(unknown.status_code, 404, unknown.text)
        ok = self.client.get("/reports/financial_summary?user_type=teacher&teacher_id=51",
                             headers=hdr("tok-admin"))
        self.assertEqual(ok.status_code, 200, ok.text)
        self.assertEqual(ok.json()["teacher_name"], "مریم معلم")

    def test_3_debtors_report_lists_only_real_debtors(self):
        resp = self.client.get("/reports/debtors", headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        rows = resp.json()
        ids = [r["student_id"] for r in rows]
        self.assertIn(41, ids, "شاگرد با شهریهٔ پرداخت‌نشده باید در لیست بدهکاران باشد")
        self.assertNotIn(42, ids, "شاگرد بی‌بدهی نباید در لیست باشد")
        debt41 = [r for r in rows if r["student_id"] == 41][0]
        self.assertEqual(debt41["amount"], 1000000, "بدهی = شهریهٔ ۱٬۰۰۰٬۰۰۰ − پرداخت‌شده ۰")
        self.assertEqual(debt41["student_name"], "علی تست")

    def test_4_undated_rows_do_not_break_reports_and_are_not_lost(self):
        """فیکس A3: ردیف مالی بدون تاریخ/بدون روش پرداخت نباید گزارش را ۵۰۰ کند یا حذف شود."""
        for url in ["/reports/financial_summary?user_type=institute", "/reports/debtors",
                    "/reports/chart-data", "/reports/student_statement?student_id=41"]:
            resp = self.client.get(url, headers=hdr("tok-admin"))
            self.assertEqual(resp.status_code, 200, f"{url} ⇒ {resp.status_code} {resp.text[:200]}")
        statement = self.client.get("/reports/student_statement?student_id=41",
                                    headers=hdr("tok-admin")).json()
        self.assertEqual(statement["total_paid_institute"], 750000,
                         "پرداختِ بی‌تاریخ هم باید در جمع وصول‌شده بیاید")

    def test_5_student_statement_and_print_carry_real_values(self):
        statement = self.client.get("/reports/student_statement?student_id=41",
                                    headers=hdr("tok-admin"))
        self.assertEqual(statement.status_code, 200, statement.text)
        body = statement.json()
        self.assertEqual(body["student_name"], "علی تست")
        self.assertEqual(body["institute_name"], "آموزشگاه خوارزمی")
        self.assertEqual(body["total_debt"], 1000000)
        self.assertEqual(body["total_debt_institute"], 700000, "بدهی کیف مؤسسه (wallet منفی)")

        printed = self.client.get("/reports/student_statement/print?student_id=41",
                                  headers=hdr("tok-admin"))
        self.assertEqual(printed.status_code, 200, printed.text)
        html = printed.text
        self.assertIn("علی تست", html)
        self.assertIn("آموزشگاه خوارزمی", html)
        self.assertNotIn("None", html, "مقدار None نباید در برگهٔ چاپی ظاهر شود")

    def test_6_student_profile_print_is_html_for_teacher_or_admin(self):
        resp = self.client.get("/reports/student_profile/print?student_id=41", headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertIn("text/html", resp.headers.get("content-type", ""))
        self.assertIn("علی", resp.text)


class TestExports(ReportWorld):
    def test_7_debtors_csv_has_bom_headers_rows_and_injection_guard(self):
        resp = self.client.get("/exports/debtors", headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertTrue(resp.content.startswith("\ufeff".encode("utf-8")),
                        "CSV باید BOM داشته باشد وگرنه اکسل متن فارسی را به‌هم‌ریخته نشان می‌دهد")
        self.assertIn("attachment", resp.headers.get("content-disposition", ""))
        rows = self.csv_rows(resp)
        header, body = rows[0], rows[1:]
        self.assertIn("نام", " ".join(header))
        names = [r[1] for r in body if len(r) > 1]
        self.assertTrue(any("علی تست" in n for n in names), rows)
        self.assertFalse(any(n.startswith("=") for n in names),
                         "سلول متنی که با = شروع شود باید بی‌اثر شده باشد (CSV injection)")

    def test_8_overdue_installments_export_includes_only_overdue_unpaid(self):
        resp = self.client.get("/exports/overdue_installments", headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        rows = self.csv_rows(resp)
        flat = " ".join(",".join(r) for r in rows)
        self.assertIn("300000", flat, "قسط سررسیدگذشتهٔ پرداخت‌نشده باید در خروجی باشد")
        self.assertIn("بحرانی", flat, "قسط بسیار معوق باید وضعیت «بحرانی» بگیرد")
        data_rows = [r for r in rows[1:] if any(c.strip() for c in r)]
        self.assertEqual(len(data_rows), 1, "فقط یک قسط معوق داریم (قسط پرداخت‌شده و آینده حذف شوند)")

    def test_9_audit_alerts_export_streams_csv_without_crash(self):
        resp = self.client.get("/exports/audit_alerts", headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertTrue(resp.content.startswith("\ufeff".encode("utf-8")))
        rows = self.csv_rows(resp)
        self.assertGreaterEqual(len(rows), 1, "دست‌کم سرستون‌ها باید بیایند")

    def test_10_debtors_excel_is_a_real_workbook(self):
        try:
            from openpyxl import load_workbook
        except ImportError:
            self.skipTest("openpyxl در محیط تست نیست")
        resp = self.client.get("/reports/debtors/excel", headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        wb = load_workbook(_io.BytesIO(resp.content))
        ws = wb.active
        self.assertTrue(ws.sheet_view.rightToLeft, "شیت باید راست‌به‌چپ باشد")
        headers = [c.value for c in ws[1]]
        self.assertIn("کل بدهی (تومان)", headers)
        self.assertGreaterEqual(ws.max_row, 2, "دست‌کم یک ردیف بدهکار باید باشد")

    def test_11_exports_follow_branch_filter(self):
        resp = self.client.get("/exports/debtors?branch_id=1", headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        other = self.client.get("/exports/debtors?branch_id=99", headers=hdr("tok-admin"))
        self.assertEqual(other.status_code, 200, other.text)
        self.assertEqual(len(self.csv_rows(other)), 1,
                         "شعبهٔ دیگر داده‌ای ندارد ⇒ فقط سرستون‌ها")


class TestAnalyticsAuditAndKpis(ReportWorld):
    def test_12_chart_data_income_chart_is_real_cash_collection(self):
        """O-07 (رفع شد): نمودار درآمد = وصولی نقدی واقعی در قلم‌های زمانی، نه تقسیم ساختگی.

        پیش‌تر `reports.py:127-133` میله‌ها را `[total//5, total//4, total//3, total//2, total]`
        می‌ساخت («درآمد هر روز هفته» بی‌ربط به داده) و «درآمد» را هم جمع علامت‌دارِ همهٔ
        تراکنش‌ها می‌گرفت (۵۰۰٬۰۰۰ + ۲۵۰٬۰۰۰ − ۲۰۰٬۰۰۰ = ۵۵۰٬۰۰۰).
        اکنون: برچسب‌ها قلم زمانی واقعی‌اند و عدد = وصولی نقدی مؤسسه.
        """
        chart = self.client.get("/reports/chart-data", headers=hdr("tok-admin")).json()["income_chart"]
        labels = [b["day"] for b in chart]
        dated = [b for b in chart if b["day"] != "بی‌تاریخ"]
        self.assertEqual(len(dated), 30, "بدون بازه، پیش‌فرض «۳۰ روز اخیر» است (مثل فیلتر ماه اخیر اپ)")
        self.assertEqual(dated[-1]["day"], jalali_today(), "آخرین قلم زمانی باید امروز باشد")
        self.assertEqual(dated[-1]["amount"], 500000, "امروز: فقط واریزی ۵۰۰٬۰۰۰ آموزشگاه")
        self.assertEqual(chart[-1], {"day": "بی‌تاریخ", "amount": 250000},
                         "واریزی بی‌تاریخ در قلم خودش دیده می‌شود (تصمیم E1) و شارژ منفی جلسه نمی‌آید")
        for bucket in chart:
            self.assertEqual(set(bucket), {"day", "amount"}, "قرارداد Kotlin دست‌نخورده")
        self.assertNotIn("شنبه", labels, "میله‌های ساختگی روزهای هفته حذف شده‌اند")

    def test_13_shares_chart_is_admin_only(self):
        admin = self.client.get("/reports/chart-data", headers=hdr("tok-admin")).json()
        self.assertIn("shares_chart", admin)
        self.assertEqual(admin["shares_chart"], {"teacher": 150000, "institute": 50000})
        sec = self.client.get("/reports/chart-data", headers=hdr("tok-secretary")).json()
        self.assertIn("shares_chart", sec)
        self.assertIsNone(sec["shares_chart"], "منشی نباید سهم معلم/آموزشگاه را ببیند (A1)")

    def test_14_kpis_are_consistent_with_database(self):
        # مسیر واقعی: روتر داشبورد با پیشوند /dashboard سوار شده (main.py:686) و
        # اپ هم همان را می‌خواند (ApiInterfaces.kt:122 → @GET("dashboard/kpis")).
        resp = self.client.get("/dashboard/kpis", headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(set(body), {"today_revenue", "total_overdue_amount",
                                     "overdue_installments_count", "active_students_count",
                                     "suspicious_alerts_count", "dunning_pending_count"})
        # O-08 (رفع شد): «درآمد امروز» = **وصولی نقدی امروز به حساب آموزشگاه**، دقیقاً همان
        # تعریف گزارش‌ها (`calculate_institute_collected_revenue`) ⇒ فقط ۵۰۰٬۰۰۰ (deposit به
        # کیف آموزشگاه با تاریخ امروز). شارژ جلسه (بدهی شاگرد) و واریزی بی‌تاریخ شمرده نمی‌شوند.
        self.assertEqual(body["today_revenue"], 500000,
                         "درآمد امروز باید فقط وصولی نقدی مؤسسه باشد")
        self.assertEqual(body["overdue_installments_count"], 1)
        self.assertEqual(body["total_overdue_amount"], 300000)
        self.assertEqual(body["active_students_count"], 3)

    def test_14b_today_revenue_counts_only_cash_collected_today(self):
        """O-08: معنای درست KPI «درآمد امروز» — سه سناریوی حاشیه‌ای.

        پیش از فیکس، این عدد «جمع علامت‌دارِ همهٔ تراکنش‌های امروز» بود (با LIKE روی تاریخ):
        شارژ جلسه از آن **کم** می‌شد، واریزیِ آموزشگاه با تاریخ میلادی **دیده نمی‌شد** و
        واریزی بی‌تاریخ هم از قلم می‌افتاد.
        """
        import routers.dashboard as dash
        today_iso = datetime.date.today().isoformat()          # «امروز» به تقویم میلادی
        self.db.add_all([
            # واریزی آموزشگاه با تاریخ میلادی (نقطهٔ کورِ LIKE روی تاریخ شمسی)
            models.Transaction(id=911, student_id=42, enrollment_id=2, course_id=71, branch_id=1,
                               amount=700000, payment_method="کارت", date=today_iso, type="deposit",
                               target_wallet="institute", description="وصولی میلادی امروز"),
            # واریزی امروز به کیف **معلم** — پول آموزشگاه نیست
            models.Transaction(id=912, student_id=42, enrollment_id=2, course_id=71, branch_id=1,
                               amount=900000, payment_method="کارت", date=jalali_today(), type="deposit",
                               target_wallet="teacher", description="سهم معلم"),
            # شارژ جلسهٔ امروز (بدهی شاگرد، عددِ منفی) — نباید از وصولی کم شود
            models.Transaction(id=913, student_id=42, enrollment_id=2, course_id=71, branch_id=1,
                               amount=-400000, payment_method="System", date=jalali_today(),
                               type="session_charge", share_teacher=300000, share_institute=100000,
                               description="هزینه جلسه امروز"),
            # واریزی بی‌تاریخ (فیکس A3: ردیف می‌ماند ولی وصولی امروز نیست)
            models.Transaction(id=914, student_id=42, enrollment_id=2, course_id=71, branch_id=1,
                               amount=120000, payment_method=None, date="", type="deposit",
                               target_wallet="institute", description="بی‌تاریخ"),
        ])
        self.db.commit()
        dash._dashboard_cache.clear()

        expected = 500000 + 700000  # deposit امروزِ آموزشگاه (شمسی + میلادی)
        body = self.client.get("/dashboard/kpis", headers=hdr("tok-admin")).json()
        self.assertEqual(body["today_revenue"], expected,
                         "فقط وصولی نقدی امروزِ آموزشگاه باید شمرده شود")

        # بی‌اثری: تعریف داشبورد و تعریف گزارش‌ها یکی است
        from financial_calculations import calculate_institute_collected_revenue
        self.assertEqual(body["today_revenue"],
                         calculate_institute_collected_revenue(self.db, jalali_today(), jalali_today()))

        # و شارژ جلسه/کیف معلم/بی‌تاریخ هیچ‌کدام عدد را تغییر ندادند:
        before = body["today_revenue"]
        self.db.query(models.Transaction).filter(models.Transaction.id.in_([912, 913, 914])).delete(
            synchronize_session=False)
        self.db.commit()
        dash._dashboard_cache.clear()
        self.assertEqual(self.client.get("/dashboard/kpis", headers=hdr("tok-admin")).json()["today_revenue"],
                         before, "حذف شارژ جلسه/سهم معلم/بی‌تاریخ نباید عدد را عوض کند")

    def test_14c_financial_summary_surfaces_undated_payments(self):
        """O-10: پول بی‌تاریخ در جمع‌های ماه/سال نمی‌آید (تصمیم E1) ولی باید **دیده** شود.

        ردیف بی‌تاریخ به هیچ بازه‌ای نسبت داده نمی‌شود؛ پس نه در جمع ماه و نه در جمع سال هست.
        بدون شمارنده، مدیر فکر می‌کند پولی گم شده است. برای همین `undated_count/undated_amount`
        اضافه شد (جمع‌های فعلی دست‌نخورده).
        """
        body = self.client.get("/reports/financial_summary?user_type=institute",
                               headers=hdr("tok-admin")).json()
        # دنیای این سناریو یک واریزی بی‌تاریخ ۲۵۰٬۰۰۰ تومانی به کیف آموزشگاه دارد (ردیف ۹۰۲)
        self.assertEqual(body["undated_count"], 1)
        self.assertEqual(body["undated_amount"], 250000)
        self.assertNotIn(250000, (body["monthly"]["collected"], body["yearly"]["collected"]),
                         "پول بی‌تاریخ نباید در جمع‌های بازه‌دار بیاید")

        # سهم معلم جدا شمرده می‌شود (کیف teacher، فقط ردیف‌های همان معلم)
        self.db.add(models.Transaction(id=905, student_id=41, course_id=71, branch_id=1, amount=40000,
                                       payment_method=None, date="", type="deposit",
                                       target_wallet="teacher", description="بی‌تاریخ معلم"))
        self.db.commit()
        teacher = self.client.get("/reports/financial_summary?user_type=teacher&teacher_id=51",
                                  headers=hdr("tok-admin")).json()
        self.assertEqual(teacher["undated_count"], 1)
        self.assertEqual(teacher["undated_amount"], 40000)
        self.assertEqual(teacher["monthly"]["collected"], 0,
                         "وصولی ماهانهٔ معلم دست‌نخورده است")

    def test_15_audit_trail_and_suspicious_patterns_are_admin_only(self):
        logs = self.client.get("/audit-trail/logs?entity_type=transaction&action=create",
                               headers=hdr("tok-admin"))
        self.assertEqual(logs.status_code, 200, logs.text)
        body = logs.json()
        self.assertIn("logs", body)
        self.assertEqual(body["total"], 3, "سه تراکنش seed شده باید در لاگ ممیزی create باشند")
        self.assertEqual(self.client.get("/audit-trail/logs?entity_type=transaction",
                                         headers=hdr("tok-secretary")).status_code, 403)
        self.assertEqual(self.client.get("/audit-trail/logs?entity_type=transaction",
                                         headers=hdr("tok-student")).status_code, 403)
        bad = self.client.get("/audit-trail/logs?entity_type=unknown", headers=hdr("tok-admin"))
        self.assertEqual(bad.status_code, 400)
        # مسیر واقعی: روتر audit با پیشوند /audit سوار شده (main.py:683) و اپ هم همین را می‌خواند
        alerts = self.client.get("/audit/suspicious_patterns", headers=hdr("tok-admin"))
        self.assertEqual(alerts.status_code, 200, alerts.text)
        self.assertEqual(
            self.client.get("/audit/suspicious_patterns", headers=hdr("tok-student")).status_code, 403)

    def test_16_dunning_drafts_and_batch_send(self):
        drafts = self.client.get("/dunning/drafts", headers=hdr("tok-admin"))
        self.assertEqual(drafts.status_code, 200, drafts.text)
        body = drafts.json()
        ids = [d["installment_id"] for d in body]
        self.assertIn(1, ids, "قسط معوق باید در پیش‌نویس‌های یادآوری باشد")
        self.assertNotIn(3, ids, "قسط پرداخت‌شده نباید پیش‌نویس داشته باشد")
        entry = [d for d in body if d["installment_id"] == 1][0]
        self.assertEqual(entry["category"], "critical", "بیش از ۷ روز تأخیر ⇒ دستهٔ بحرانی")
        self.assertTrue(entry["suggested_message"], "متن پیشنهادی یادآوری باید آماده باشد")

        batch = self.client.post("/dunning/send_batch", json={"installment_ids": [1]},
                                 headers=hdr("tok-admin"))
        self.assertEqual(batch.status_code, 200, batch.text)
        self.assertGreaterEqual(self.db.query(models.SmsLog).count(), 1)

        empty = self.client.post("/dunning/send_batch", json={"installment_ids": []},
                                 headers=hdr("tok-admin"))
        self.assertEqual(empty.status_code, 400)

    def test_17_students_and_teachers_cannot_read_institute_reports(self):
        for url in ["/reports/chart-data", "/reports/financial_summary?user_type=institute",
                    "/reports/debtors", "/dashboard/kpis"]:
            resp = self.client.get(url, headers=hdr("tok-student"))
            self.assertIn(resp.status_code, (401, 403), f"{url} ⇒ {resp.status_code}")


if __name__ == "__main__":
    unittest.main()
