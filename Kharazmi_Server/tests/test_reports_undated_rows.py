# test_reports_undated_rows.py
# تست‌های A3 — حذف نشدن بی‌صدای ردیف‌های بی‌تاریخ در گزارش‌های مالی
#
# باگی که این تست‌ها قفل می‌کنند:
#   در `routers/reports.py` (هم `get_chart_data` و هم `get_financial_report`) فیلتر تاریخ این‌طور بود:
#       def _in_range(value):
#           parsed = parse_project_date(value)
#           if parsed is None:
#               return False          # ← NULL و هر مقدار نامعتبر، بی‌صدا حذف می‌شد
#   و این حتی وقتی هیچ بازه‌ای درخواست نشده بود هم اجرا می‌شد. پیامد: جمع درآمد، روند حضور،
#   چارت سهم‌ها و گزارش مالی آموزشگاه **کمتر از واقع** نمایش داده می‌شد (همان باگ Task 5 در
#   طلب معلم که اینجا در گزارش‌های سطح آموزشگاه وجود داشت).
#
# سیاست جدید (مطابق تصمیم E1 سند نقشه): بازهٔ تاریخ فقط ردیف‌های دارای تاریخ معتبر را محدود
# می‌کند؛ ردیف بی‌تاریخ/نامعتبر حذف نمی‌شود و تاریخش در API کنترل‌شده `""` است (بدون null و
# بدون تاریخ جعلی) چون کلاینت اندروید مدل `String` غیر-null دارد.
#
# ⚠ به‌روزرسانی آگاهانه (O-07): «درآمد» نمودار از جمع علامت‌دار همهٔ تراکنش‌ها به **وصولی نقدی
# آموزشگاه** تغییر کرد و قلم‌های نمودار، زمانی شدند. ردیف بی‌تاریخ هم مثل قبل حذف نمی‌شود،
# ولی چون قلم زمانی ندارد در یک قلم جدا با برچسب «بی‌تاریخ» (آخرین ستون) نمایش داده می‌شود —
# نه با تاریخ جعلی و نه مخلوط در یک میلهٔ روزانه. جمع‌های مالیِ بازه‌دار (KPI «درآمد امروز» و
# `calculate_institute_collected_revenue`) عمداً فقط ردیف‌های تاریخ‌دار را می‌شمارند و پول
# بی‌تاریخ از مسیر شمارندهٔ اختصاصی خودش (O-10) گزارش می‌شود.
#
# اجرا (از ریشهٔ ریپو — روش مستند پروژه):
#   DATABASE_URL=sqlite:////tmp/a3_reports.db JWT_SECRET_KEY=<hex> \
#     python3 -m pytest Kharazmi_Server/test_reports_undated_rows.py -q
import datetime
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from dependencies import get_db
from main import app

VALID_DAY = "1405/06/02"


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


class ReportsUndatedWorld(unittest.TestCase):
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
            models.Branch(id=2, name="شعبه دو", active=True),
            models.Teacher(id=1, first_name="معلم", last_name="تست", mobile="09120000001",
                           national_code="0012345678", password="x", is_approved=True, is_deleted=False),
            models.Course(id=1, title="ریاضی", code="A3-1", teacher_id=1, branch_id=1,
                          grade_level="دهم", class_time="16:00-17:30", days_of_week="شنبه",
                          teacher_session_price=100000, is_deleted=False, is_admin_approved=True),
            models.Student(id=1, student_code=1, first_name="علی", last_name="تست",
                           national_code="0012345681", student_mobile="09121111111",
                           wallet_teacher=0, wallet_institute=0, wallet_balance=0, is_deleted=False),
            models.User(id=1, username="admin-global", password="x", full_name="مدیر مرکزی",
                        role="admin", sub_role="admin", branch_id=None),
            models.User(id=2, username="admin-b1", password="x", full_name="مدیر شعبه",
                        role="admin", sub_role="admin", branch_id=1),
            models.User(id=3, username="sec-1", password="x", full_name="منشی", role="admin",
                        sub_role="secretary", branch_id=1),
            models.User(id=4, username="student:1", password="x", full_name="شاگرد", role="student",
                        sub_role="student", branch_id=1),
        ])
        for uid, tok, role in [(1, "tok-global", "admin"), (2, "tok-b1", "admin"),
                               (3, "tok-secretary", "secretary"), (4, "tok-student", "student")]:
            self.db.add(models.UserSession(token=tok, user_id=uid, sub_role=role, created_at=now))
        self.db.commit()
        self._txn_id = 1000

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    # ---------------- کارخانه‌ی داده ----------------
    def add_transaction(self, date_value, amount=100000, share_teacher=40000, share_institute=60000,
                        ttype="deposit", wallet="institute", branch_id=1, is_deleted=False,
                        is_reversed=False):
        # O-07: نوع/کیف پیش‌فرض «deposit/institute» است چون این فایل موضوعش «درآمد» است و تعریف
        # درآمد = وصولی نقدی آموزشگاه؛ (پیش‌تر `tuition` بود چون نمودار همهٔ نوع‌ها را جمع می‌کرد).
        self._txn_id += 1
        t = models.Transaction(id=self._txn_id, student_id=1, course_id=1, branch_id=branch_id,
                               enrollment_id=None, amount=amount, type=ttype, date=date_value,
                               target_wallet=wallet,
                               description="تست", share_teacher=share_teacher,
                               share_institute=share_institute,
                               is_deleted=is_deleted, is_reversed=is_reversed)
        self.db.add(t)
        self.db.commit()
        return t.id

    def add_session(self, date_value, day_label="16:00", cost=100000, present=True):
        self._txn_id += 1
        sid = self._txn_id
        self.db.add(models.SessionLog(id=sid, course_id=1, date=date_value, time=day_label,
                                      final_teacher_cost=cost, final_institute_share=50000,
                                      cost_per_student=150000, attendee_count=1,
                                      status="Finished", is_deleted=False))
        self.db.flush()
        self.db.add(models.Attendance(id=sid, session_id=sid, student_id=1,
                                      status="Present" if present else "Absent",
                                      is_billed=False, is_deleted=False))
        self.db.commit()
        return sid

    # ---------------- فراخوانی‌ها ----------------
    def chart(self, token="tok-global", **params):
        r = self.client.get("/reports/chart-data", params=params or None, headers=hdr(token))
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def financial(self, token="tok-global", **params):
        r = self.client.get("/reports/financial", params=params or None, headers=hdr(token))
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    @staticmethod
    def total_income(chart_body):
        """جمع قلم‌های **تاریخ‌دار** نمودار (هم‌ارز `calculate_institute_collected_revenue`).

        O-07: پیش‌تر «آخرین میله = کل درآمد» بود؛ حالا میله‌ها واقعی‌اند و ردیف بی‌تاریخ در
        قلم جداگانهٔ «بی‌تاریخ» می‌آید، پس جدا حساب می‌شود.
        """
        return sum(row["amount"] for row in chart_body["income_chart"] if row["day"] != "بی‌تاریخ")

    @staticmethod
    def undated_income(chart_body):
        for row in chart_body["income_chart"]:
            if row["day"] == "بی‌تاریخ":
                return row["amount"]
        return 0


class TestChartDataUndatedRows(ReportsUndatedWorld):
    def test_valid_dated_transaction_behaves_as_before(self):
        self.add_transaction(VALID_DAY, amount=100000)
        body = self.chart()
        self.assertEqual(self.total_income(body), 100000)
        self.assertEqual(self.undated_income(body), 0, "بدون ردیف بی‌تاریخ، قلم «بی‌تاریخ» ساخته نمی‌شود")
        self.assertEqual([row["day"] for row in body["income_chart"]][-1].count("/"), 2,
                         "آخرین قلم، برچسب تاریخ شمسی است")

    def test_undated_transaction_is_still_counted_in_its_own_bucket(self):
        self.add_transaction(None, amount=250000)
        body = self.chart()
        self.assertEqual(self.undated_income(body), 250000,
                         "تراکنش بدون تاریخ نباید از نمودار حذف شود (تصمیم E1)")
        self.assertEqual(self.total_income(body), 0,
                         "و نباید در قلم روزانهٔ ساختگی جمع شود")

    def test_mixed_valid_and_undated_total(self):
        self.add_transaction(VALID_DAY, amount=100000)
        self.add_transaction(None, amount=250000)
        self.add_transaction("1405/06/05", amount=50000)
        body = self.chart()
        self.assertEqual(self.total_income(body), 150000, "جمع قلم‌های تاریخ‌دار")
        self.assertEqual(self.undated_income(body), 250000, "پول بی‌تاریخ جدا ولی دیده‌شدنی")

    def test_invalid_non_null_date_is_counted_without_fake_value(self):
        self.add_transaction("999/99/99", amount=70000)
        body = self.chart()
        self.assertEqual(self.undated_income(body), 70000)
        self.assertNotIn("999/99/99", [row["day"] for row in body["income_chart"]],
                         "تاریخ نامعتبر نباید به‌عنوان برچسب زمانی بیاید")

    def test_range_filter_limits_only_dated_rows(self):
        self.add_transaction("1405/06/01", amount=100000)   # قبل از بازه
        self.add_transaction("1405/06/04", amount=200000)   # داخل بازه
        self.add_transaction(None, amount=300000)           # بی‌تاریخ ⇒ می‌ماند (تصمیم E1)
        body = self.chart(start_date="1405/06/03", end_date="1405/06/05")
        self.assertEqual(self.total_income(body), 200000, "فقط ردیف تاریخ‌دارِ داخل بازه")
        self.assertEqual(self.undated_income(body), 300000,
                         "ردیف بی‌تاریخ بیرون از قاعدهٔ بازه می‌ماند (E1)")

    def test_attendance_trend_includes_undated_session_with_blank_date(self):
        self.add_session(VALID_DAY)
        self.add_session(None)
        trend = self.chart()["attendance_trend"]
        self.assertEqual(len(trend), 2, "جلسه‌ی بی‌تاریخ نباید از روند حضور حذف شود")
        dates = [row["date"] for row in trend]
        self.assertIn("", dates, "تاریخ نامعلوم باید \"\" باشد")
        self.assertIn(VALID_DAY, dates, "تاریخ معتبر باید دست‌نخورده بماند")

    def test_no_null_values_in_chart_payload(self):
        self.add_transaction(None, amount=1000)
        self.add_session(None)
        body = self.chart()
        for row in body["income_chart"]:
            self.assertNotIn(None, row.values(), row)
            self.assertIsInstance(row["day"], str, row)
        for row in body["attendance_trend"]:
            self.assertNotIn(None, row.values(), row)
        self.assertNotIn(None, body["shares_chart"].values() if body["shares_chart"] else {})

    def test_deterministic_order_with_undated_last(self):
        self.add_session("1405/06/05")
        self.add_session(None)
        self.add_session("1405/06/02")
        first = [row["date"] for row in self.chart()["attendance_trend"]]
        for _ in range(3):
            self.assertEqual([row["date"] for row in self.chart()["attendance_trend"]], first)
        self.assertEqual(first, ["1405/06/02", "1405/06/05", ""],
                         "تاریخ معتبر صعودی و ردیف بی‌تاریخ در انتها")

    def test_shares_chart_includes_undated_for_admin(self):
        self.add_transaction(VALID_DAY, share_teacher=40000, share_institute=60000)
        self.add_transaction(None, share_teacher=10000, share_institute=20000)
        # شاخص سهم‌ها جدولِ جداگانه است و مثل قبل ردیف بی‌تاریخ را هم می‌بیند (O-07 فقط نمودار درآمد را عوض کرد).
        shares = self.chart(token="tok-global")["shares_chart"]
        self.assertEqual(shares, {"teacher": 50000, "institute": 80000})

    def test_shares_chart_still_hidden_from_secretary(self):
        self.add_transaction(None)
        self.assertIsNone(self.chart(token="tok-secretary")["shares_chart"],
                          "منشی باید مثل قبل shares_chart=None بگیرد")

    def test_response_contract_preserved(self):
        self.add_transaction(None, amount=1000)
        body = self.chart()
        self.assertEqual(set(body.keys()), {"income_chart", "student_chart", "attendance_trend",
                                           "shares_chart"})
        self.assertGreater(len(body["income_chart"]), 0, "نمودار هرگز خالی برنمی‌گردد")
        for row in body["income_chart"]:
            self.assertEqual(set(row), {"day", "amount"}, row)
            self.assertIsInstance(row["day"], str, row)
            self.assertIsInstance(row["amount"], (int, float), row)
        self.assertNotIn("چهارشنبه", [row["day"] for row in body["income_chart"]],
                         "میله‌های ساختگی روزهای هفته باید حذف شده باشند (O-07)")

    def test_archived_and_reversed_transactions_stay_excluded(self):
        self.add_transaction(VALID_DAY, amount=100000)
        self.add_transaction(None, amount=999000, is_deleted=True)
        self.add_transaction(None, amount=888000, is_reversed=True)
        body = self.chart()
        self.assertEqual(self.total_income(body), 100000,
                         "ردیف آرشیوشده/برگشتی در هیچ قلمی نباید وارد شود")
        self.assertEqual(self.undated_income(body), 0,
                         "ردیف بی‌تاریخِ آرشیوشده/برگشتی هم نباید در قلم «بی‌تاریخ» بیاید")

    def test_permissions_unchanged(self):
        self.assertEqual(self.client.get("/reports/chart-data").status_code, 401)
        self.assertEqual(self.client.get("/reports/chart-data", headers=hdr("tok-student")).status_code, 403)
        self.assertEqual(self.client.get("/reports/chart-data", headers=hdr("tok-adminless")).status_code, 401)
        self.assertEqual(self.client.get("/reports/chart-data", headers=hdr("tok-secretary")).status_code, 200)


class TestFinancialReportUndatedRows(ReportsUndatedWorld):
    def test_valid_dated_row_unchanged(self):
        self.add_transaction(VALID_DAY, amount=100000)
        report = self.financial()
        self.assertEqual(len(report), 1)
        self.assertEqual(report[0]["amount"], 100000)
        self.assertEqual(report[0]["date"], VALID_DAY)

    def test_undated_row_is_included_with_blank_date(self):
        self.add_transaction(None, amount=250000)
        report = self.financial()
        self.assertEqual(len(report), 1, "تراکنش بدون تاریخ نباید از گزارش مالی حذف شود")
        self.assertEqual(report[0]["amount"], 250000)
        self.assertEqual(report[0]["date"], "", "تاریخ نامعلوم باید \"\" باشد، نه null")

    def test_mixed_rows_all_present_and_none_free(self):
        self.add_transaction(VALID_DAY, amount=100000)
        self.add_transaction(None, amount=250000)
        self.add_transaction("999/99/99", amount=50000)
        report = self.financial()
        self.assertEqual(len(report), 3)
        self.assertEqual(sum(row["amount"] for row in report), 400000)
        self.assertEqual(sorted(row["date"] for row in report), ["", "", VALID_DAY])
        for row in report:
            # تمرکز A3 روی فیلد تاریخ است: هرگز null یا رشتهٔ "None" نباشد.
            # (بقیهٔ کلیدها قرارداد موجود خود را دارند — مثلاً payment_method در تراکنش‌های
            #  نقدی/legacy می‌تواند null باشد و رفتارش در این تسک تغییر نکرده است.)
            self.assertIsInstance(row["date"], str, row)
            self.assertNotIn("None", row["date"], row)
            for key in ("amount", "student_id", "description"):
                self.assertNotIn(key, [k for k, v in row.items() if v is None], row)

    def test_order_stays_descending_by_id(self):
        ids = [self.add_transaction(None, amount=1000),
               self.add_transaction(VALID_DAY, amount=2000),
               self.add_transaction(None, amount=3000)]
        amounts = [row["amount"] for row in self.financial()]
        self.assertEqual(amounts, [3000, 2000, 1000], "ترتیب نزولی id باید حفظ شود")

    def test_range_filter_limits_only_dated_rows(self):
        self.add_transaction("1405/06/01", amount=100000)
        self.add_transaction("1405/06/04", amount=200000)
        self.add_transaction(None, amount=300000)
        report = self.financial(start_date="1405/06/03", end_date="1405/06/05")
        amounts = sorted(row["amount"] for row in report)
        self.assertEqual(amounts, [200000, 300000], "ردیف بی‌تاریخ باید بماند")

    def test_branch_isolation_preserved(self):
        self.add_transaction(VALID_DAY, amount=100000, branch_id=1)
        self.add_transaction(None, amount=250000, branch_id=2)
        global_amounts = sorted(row["amount"] for row in self.financial(token="tok-global"))
        self.assertEqual(global_amounts, [100000, 250000], "ادمین مرکزی همه‌ی شعبه‌ها را می‌بیند")
        branch_amounts = sorted(row["amount"] for row in self.financial(token="tok-b1"))
        self.assertEqual(branch_amounts, [100000], "ادمین شعبه فقط شعبه‌ی خودش را می‌بیند")

    def test_archived_and_reversed_excluded(self):
        self.add_transaction(None, amount=100000)
        self.add_transaction(None, amount=999000, is_deleted=True)
        self.add_transaction(None, amount=888000, is_reversed=True)
        report = self.financial()
        self.assertEqual(len(report), 1)
        self.assertEqual(report[0]["amount"], 100000)

    def test_permissions_unchanged(self):
        self.assertEqual(self.client.get("/reports/financial").status_code, 401)
        self.assertEqual(self.client.get("/reports/financial", headers=hdr("tok-secretary")).status_code, 403,
                         "گزارش مالی فقط ادمین است (بدون تغییر)")
        self.assertEqual(self.client.get("/reports/financial", headers=hdr("tok-b1")).status_code, 200)

    def test_empty_report_when_no_rows(self):
        self.assertEqual(self.financial(), [])


if __name__ == "__main__":
    unittest.main()
