# test_e2e_income_chart_buckets.py
# ═══════════════════════════════════════════════════════════════════════════════
# O-07: نمودار درآمد صفحهٔ «نمودارها» باید از **دادهٔ واقعی** ساخته شود، در قلم‌های زمانیِ
# درست، و جمعش با تعریف واحد وصولی (`collected_revenue_rows` /
# `calculate_institute_collected_revenue`) یکی باشد.
#
# مرجع سمت اندروید (خوانده‌شده از همین ریپو):
#   • ChartActivity.kt:75   → GET reports/chart-data  (class_id, start_date, end_date)
#   • ChartActivity.kt:136  → بازه‌ها: «ماه اخیر» = ۳۰ روز، «فصل» = ۹۰ روز
#   • ChartActivity.kt:213  → تاریخ بازه **میلادی** با قالب yyyy/MM/dd فرستاده می‌شود
#   • ChartActivity.kt:261  → setupBarChart(List<IncomeData>) — دادهٔ خالی ⇒ نمودار خالی
#   • ChartActivity.kt:43   → IncomeData(day: String, amount: Float)  ⇒ قرارداد `{day, amount}`
#
# اجرا (از ریشهٔ ریپو):
#   DATABASE_URL=sqlite:////tmp/e2e_chart.db JWT_SECRET_KEY=<hex> \
#     python3 -m pytest Kharazmi_Server/tests/test_e2e_income_chart_buckets.py -q
import datetime
import re
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from dependencies import get_db, hash_password, limiter
from financial_calculations import calculate_institute_collected_revenue, collected_revenue_rows
from main import app
from today_summary import jalali_date_string

DAILY_LABEL = re.compile(r"^\d{4}/\d{2}/\d{2}$")
MONTHLY_LABEL = re.compile(r"^\d{4}/\d{2}$")


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


def jalali_days_ago(days):
    return jalali_date_string(datetime.date.today() - datetime.timedelta(days=days))


def gregorian(days_ago):
    """همان قالبی که اپ می‌فرستد (ChartActivity.getGregorianDateString → yyyy/MM/dd)."""
    return (datetime.date.today() - datetime.timedelta(days=days_ago)).strftime("%Y/%m/%d")


class IncomeChartWorld(unittest.TestCase):
    """دنیای نمودار: دو کلاس، پرداخت‌های شمسی/میلادی/بی‌تاریخ، سهم معلم و شارژ جلسه."""

    def setUp(self):
        self._limiter = limiter.enabled
        limiter.enabled = False
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                               poolclass=StaticPool)
        models.Base.metadata.create_all(engine)
        self.engine = engine
        self.db = sessionmaker(bind=engine, expire_on_commit=False)()

        self.db.add(models.Branch(id=1, name="شعبه مرکزی", active=True))
        self.db.add_all([
            models.User(id=101, username="09120000301", password=hash_password("a"), full_name="مدیر",
                        role="admin", sub_role="admin", branch_id=1),
            models.User(id=102, username="09120000302", password=hash_password("b"), full_name="منشی",
                        role="secretary", sub_role="secretary", branch_id=1),
        ])
        self.db.add(models.Teacher(id=51, first_name="مریم", last_name="معلم", mobile="09120000303",
                                   national_code="0012347001", password=hash_password("t"),
                                   is_approved=True, is_deleted=False, branch_id=1))
        self.db.add(models.Student(id=41, student_code=41, first_name="علی", last_name="تست",
                                  national_code="0012347002", student_mobile="09120000304",
                                  parent_mobile="09120000305", branch_id=1, is_deleted=False))
        self.db.add_all([
            models.Course(id=71, title="ریاضی دهم", code="700101", teacher_id=51, branch_id=1,
                          is_deleted=False, days_of_week="شنبه", class_time="17:30",
                          teacher_session_price=100000),
            models.Course(id=72, title="فیزیک دهم", code="700102", teacher_id=51, branch_id=1,
                          is_deleted=False, days_of_week="یکشنبه", class_time="19:00",
                          teacher_session_price=100000),
        ])
        self.db.commit()

        today, ten, forty_five = jalali_date_string(datetime.date.today()), jalali_days_ago(10), jalali_days_ago(45)
        today_iso = datetime.date.today().isoformat()
        self.db.add_all([
            # وصولی‌های واقعی آموزشگاه (کلاس ۷۱)
            models.Transaction(id=801, student_id=41, course_id=71, branch_id=1, amount=100000,
                               payment_method="کارت", date=today, type="deposit",
                               target_wallet="institute", description="امروز (شمسی)"),
            models.Transaction(id=802, student_id=41, course_id=71, branch_id=1, amount=50000,
                               payment_method="کارت", date=ten, type="deposit",
                               target_wallet="institute", description="۱۰ روز پیش"),
            models.Transaction(id=803, student_id=41, course_id=71, branch_id=1, amount=30000,
                               payment_method="کارت", date=today_iso, type="deposit",
                               target_wallet="institute", description="امروز (میلادی)"),
            models.Transaction(id=804, student_id=41, course_id=71, branch_id=1, amount=25000,
                               payment_method="کارت", date=forty_five, type="deposit",
                               target_wallet="institute", description="۴۵ روز پیش (بیرون از بازهٔ ۳۰ روزه)"),
            models.Transaction(id=805, student_id=41, course_id=71, branch_id=1, amount=11000,
                               payment_method=None, date="", type="deposit",
                               target_wallet="institute", description="بی‌تاریخ"),
            # کلاس دیگر (سنجش فیلتر class_id)
            models.Transaction(id=806, student_id=41, course_id=72, branch_id=1, amount=70000,
                               payment_method="کارت", date=ten, type="deposit",
                               target_wallet="institute", description="کلاس دیگر"),
            # پول معلم و بدهی شاگرد — هیچ‌کدام وصولی آموزشگاه نیستند
            models.Transaction(id=807, student_id=41, course_id=71, branch_id=1, amount=900000,
                               payment_method="کارت", date=today, type="deposit",
                               target_wallet="teacher", description="سهم معلم"),
            models.Transaction(id=808, student_id=41, course_id=71, branch_id=1, amount=-200000,
                               payment_method="System", date=today, type="session_charge",
                               share_teacher=150000, share_institute=50000, description="شارژ جلسه"),
        ])
        self.db.add_all([
            models.UserSession(token="tok-admin", user_id=101, sub_role="admin",
                               created_at=datetime.datetime.now()),
            models.UserSession(token="tok-secretary", user_id=102, sub_role="secretary",
                               created_at=datetime.datetime.now()),
        ])
        self.db.commit()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        limiter.enabled = self._limiter
        self.db.close()
        self.engine.dispose()

    @staticmethod
    def dated_sum(chart):
        """جمع قلم‌های زمانی (بدون «بی‌تاریخ») — هم‌ارز تعریف واحد وصولی در بازه."""
        return sum(b["amount"] for b in chart if b["day"] != "بی‌تاریخ")

    @staticmethod
    def undated_bucket(chart):
        for bucket in chart:
            if bucket["day"] == "بی‌تاریخ":
                return bucket
        return None

    def chart(self, start_date=None, end_date=None, class_id=None, token="tok-admin"):
        params = {}
        if start_date is not None:
            params["start_date"] = start_date
        if end_date is not None:
            params["end_date"] = end_date
        if class_id is not None:
            params["class_id"] = class_id
        resp = self.client.get("/reports/chart-data", params=params, headers=hdr(token))
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp.json()["income_chart"]

    # ---------------------------------------------------------------- تست‌ها
    def test_1_thirty_day_window_is_daily_and_matches_the_shared_function(self):
        """بازهٔ «ماه اخیر» اپ (۳۰ روز): ۳۱ قلم روزانهٔ شمسی و جمعِ برابر با تعریف واحد."""
        start, end = gregorian(30), gregorian(0)
        chart = self.chart(start, end)

        self.assertEqual(len([b for b in chart if b["day"] != "بی‌تاریخ"]), 31,
                         "بازهٔ ۳۰ روزه باید ۳۱ قلم روزانه بدهد (+ یک قلم «بی‌تاریخ» در انتها)")
        for bucket in chart[:-1]:
            self.assertTrue(DAILY_LABEL.match(bucket["day"]), f"برچسب روزانه نیست: {bucket}")
        self.assertEqual(chart[-1]["day"], "بی‌تاریخ", "قلم بی‌تاریخ همیشه آخر است")
        self.assertEqual(self.dated_sum(chart),
                         calculate_institute_collected_revenue(self.db, start, end),
                         "جمع ستون‌های تاریخ‌دار باید با تعریف واحد وصولی یکی باشد")
        self.assertEqual(self.undated_bucket(chart), {"day": "بی‌تاریخ", "amount": 11000},
                         "وصولی بی‌تاریخ حذف نمی‌شود و قلم «بی‌تاریخ» می‌گیرد (تصمیم E1)")

        # امروز: ۱۰۰٬۰۰۰ (شمسی) + ۳۰٬۰۰۰ (میلادی) — سهم معلم و شارژ جلسه نمی‌آیند
        today_label = jalali_date_string(datetime.date.today())
        by_label = {b["day"]: b["amount"] for b in chart}
        self.assertEqual(by_label[today_label], 130000,
                         "پرداخت امروز با تاریخ میلادی هم باید در قلم امروز شمرده شود")
        # بدون فیلتر class_id هر دو کلاس می‌آیند: ۵۰٬۰۰۰ (کلاس ۷۱) + ۷۰٬۰۰۰ (کلاس ۷۲)
        self.assertEqual(by_label[jalali_days_ago(10)], 120000)
        self.assertEqual(self.dated_sum(chart), 130000 + 120000,
                         "۴۵ روز پیش بیرون از این بازه است و بی‌تاریخ قلم زمانی نمی‌گیرد")

    def test_2_ninety_day_window_is_monthly(self):
        """بازهٔ «فصل» اپ (۹۰ روز): قلم‌های ماهانهٔ شمسی با جمعِ برابر با تعریف واحد."""
        start, end = gregorian(90), gregorian(0)
        chart = self.chart(start, end)

        labels = [b["day"] for b in chart if b["day"] != "بی‌تاریخ"]
        for label in labels:
            self.assertTrue(MONTHLY_LABEL.match(label), f"برچسب ماهانه نیست: {label}")
        self.assertEqual(len(labels), len(set(labels)), "برچسب ماه‌ها باید یکتا باشد")
        self.assertEqual(self.dated_sum(chart),
                         calculate_institute_collected_revenue(self.db, start, end))
        self.assertEqual(self.dated_sum(chart), 100000 + 50000 + 30000 + 25000 + 70000,
                         "وصولی‌های شمسی/میلادی هر دو قلم می‌گیرند (۷۰٬۰۰۰ هم کلاس ۷۲ است)")
        self.assertEqual(self.undated_bucket(chart)["amount"], 11000,
                         "بی‌تاریخ در قلم مخصوص خودش می‌ماند")

    def test_3_class_filter_applies_to_chart_and_rows(self):
        """فیلتر `class_id` (Transaction.course_id) باید هم روی نمودار و هم روی helper اثر کند."""
        start, end = gregorian(90), gregorian(0)
        only_71 = self.chart(start, end, class_id=71)
        rows_71 = collected_revenue_rows(self.db, start, end, course_id=71)
        self.assertEqual(self.dated_sum(only_71), sum(amount for amount, _ in rows_71))
        self.assertEqual(self.undated_bucket(only_71)["amount"], 11000,
                         "وصولی بی‌تاریخِ همان کلاس هم باید دیده شود")

        only_72 = self.chart(start, end, class_id=72)
        self.assertEqual(self.dated_sum(only_72), 70000, "کلاس ۷۲ فقط همان ۷۰٬۰۰۰ را دارد")
        self.assertIsNone(self.undated_bucket(only_72), "کلاس ۷۲ ردیف بی‌تاریخ ندارد")

    def test_4_range_without_payments_returns_zero_buckets(self):
        """بازهٔ بدون وصولی: قلم‌های زمانی می‌مانند ولی صفر (نمودار بی‌داده نمی‌شود).

        ردیف بی‌تاریخ به بازه کاری ندارد (تصمیم E1) ⇒ قلم «بی‌تاریخ» مستقل از بازه می‌ماند.
        """
        chart = self.chart(gregorian(20), gregorian(15))
        dated = [b for b in chart if b["day"] != "بی‌تاریخ"]
        self.assertEqual(len(dated), 6, "شش قلم روزانهٔ بازه")
        self.assertEqual([b["amount"] for b in dated], [0] * 6, "بدون وصولی در این بازه")
        self.assertEqual(self.undated_bucket(chart), {"day": "بی‌تاریخ", "amount": 11000},
                         "وصولی بی‌تاریخ بیرون از بازه هم دیده می‌شود")

    def test_5_no_range_defaults_to_thirty_days_and_never_an_empty_list(self):
        """تصمیم O-07 بر اساس `setupBarChart`: هرگز لیست خالی فرستاده نمی‌شود.

        بدون بازه، پیش‌فرض «۳۰ روز اخیر» است (همان فیلتر «ماه اخیر» اپ) و بدون داده هم
        ۳۰ قلم صفر برمی‌گردد — نه لیست خالی (که در اپ نمودار بی‌برچسب می‌شد).
        """
        self.db.query(models.Transaction).delete()
        self.db.commit()
        chart = self.chart()
        self.assertEqual(len(chart), 30, "بازهٔ پیش‌فرض = ۳۰ روز اخیر")
        self.assertEqual({b["amount"] for b in chart}, {0}, "بدون داده ⇒ همهٔ قلم‌ها صفر")
        self.assertEqual(chart[-1]["day"], jalali_date_string(datetime.date.today()),
                         "آخرین قلم باید امروز باشد")

    def test_6_contract_shape_and_no_fabricated_weekday_bars(self):
        """قرارداد Kotlin (`IncomeData(day:String, amount:Float)`) + نبود میله‌های ساختگی."""
        chart = self.chart(gregorian(30), gregorian(0))
        for bucket in chart:
            self.assertEqual(set(bucket), {"day", "amount"}, "کلیدهای قرارداد عوض شده‌اند")
            self.assertIsInstance(bucket["day"], str)
            self.assertIsInstance(bucket["amount"], (int, float))

        weekdays = {"شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه"}
        self.assertFalse(weekdays & {b["day"] for b in chart},
                         "میله‌های ساختگی روزهای هفته باید حذف شده باشند")
        total = calculate_institute_collected_revenue(self.db, gregorian(30), gregorian(0))
        self.assertGreater(total, 0, "باید دادهٔ واقعی داشته باشیم تا سنجش معنا داشته باشد")
        self.assertEqual(self.dated_sum(chart), total,
                         "جمع نمودار نباید چند برابر عدد واقعی باشد")

    def test_7_secretary_can_read_the_chart_but_students_cannot(self):
        """سطح دسترسی نمودار: کارکنان بله، شاگرد/معلم نه (گارد L14/Y4 دست‌نخورده)."""
        resp = self.client.get("/reports/chart-data", headers=hdr("tok-secretary"))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertIsNone(resp.json()["shares_chart"], "سهم معلم/آموزشگاه فقط برای ادمین")
        self.assertEqual(self.client.get("/reports/chart-data").status_code, 401)


if __name__ == "__main__":
    unittest.main()
