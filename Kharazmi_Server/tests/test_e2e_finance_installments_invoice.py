# test_e2e_finance_installments_invoice.py
# ═══════════════════════════════════════════════════════════════════════════════
# سناریوی end-to-end #۴: «مالی — پرداخت، قسط، کیف پول، فاکتور و رسید»
#
# مسیر اپ (KharazmiAdmin):
#   FinanceActivity.kt          → POST finance/pay                    (ApiInterfaces.kt:39-40)
#   InstallmentsActivity.kt     → POST finance/installments           (ApiInterfaces.kt:52-53)
#                                 POST finance/installments/{id}/pay  (ApiInterfaces.kt:54-56)
#                                 POST finance/installments/{id}/remind
#   StudentProfileActivity.kt   → GET  finance/student/{id}/dashboard (ApiInterfaces.kt:58)
#                                 GET  finance/student_class_status   (ApiInterfaces.kt:43)
#   InvoiceActivity.kt:57-82    → GET  finance/receipt/{transaction_id}
#                                 POST finance/receipt/print · /finance/receipt/pdf
#   InvoiceActivity            → GET  finance/invoice/{enrollment_id}
#
# ⚠ فاز دیباگ: صفر تغییر در کد برنامه؛ فقط سنجش + مستندسازی.
import datetime
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


def pay_payload(amount=100000, wallet="institute", key=None, date="1405/06/30", **kw):
    body = {"student_id": 41, "amount": amount, "target_wallet": wallet,
            "description": "پرداخت حضوری", "payment_method": "کارت", "date": date,
            "enrollment_id": 1}
    if key is not None:
        body["idempotency_key"] = key
    body.update(kw)
    return body


class FinanceWorld(unittest.TestCase):
    def setUp(self):
        self._limiter = limiter.enabled
        limiter.enabled = False
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                               poolclass=StaticPool)
        models.Base.metadata.create_all(engine)
        self.engine = engine
        self.db = sessionmaker(bind=engine, expire_on_commit=False)()

        self.db.add(models.Branch(id=1, name="شعبه مرکزی", active=True))
        self.db.add(models.User(id=101, username="09120000031", password=hash_password("a"),
                                full_name="مدیر مالی", role="admin", sub_role="admin", branch_id=1))
        self.db.add(models.Teacher(id=51, first_name="مریم", last_name="معلم", mobile="09120000032",
                                   national_code="0012347001", password=hash_password("t"),
                                   is_approved=True, is_deleted=False, branch_id=1))
        self.student = models.Student(id=41, student_code=41, first_name="علی", last_name="تست",
                                      national_code="0012347002", student_mobile="09120000033",
                                      parent_mobile="09120000034", branch_id=1,
                                      wallet_teacher=0, wallet_institute=400000, wallet_balance=400000,
                                      is_deleted=False)
        self.db.add(self.student)
        self.db.add(models.Course(id=71, title="ریاضی دهم", code="700001", teacher_id=51, branch_id=1,
                                  is_deleted=False, grade_level="دهم", days_of_week="شنبه",
                                  class_time="17:30", teacher_session_price=100000))
        self.db.add(models.Enrollment(id=1, student_id=41, course_id=71, branch_id=1,
                                      register_date="1405/06/01", shift="عصر",
                                      total_tuition=1000000, total_paid=400000,
                                      discount_type="none", discount_value=0, is_deleted=False))
        # پیش‌پرداخت ثبت‌نام (زنجیرهٔ سناریو ۲)
        self.db.add(models.Transaction(id=900, student_id=41, enrollment_id=1, course_id=71,
                                       branch_id=1, amount=400000, payment_method="کارت",
                                       date="1405/06/01", type="enrollment_payment",
                                       target_wallet="institute", description="پیش‌پرداخت ثبت‌نام"))
        self.db.add(models.UserSession(token="tok-admin", user_id=101, sub_role="admin",
                                       created_at=datetime.datetime.now()))
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

    def wallet(self):
        row = self.db.query(models.Student).filter(models.Student.id == 41).first()
        self.db.refresh(row)
        return row

    def create_installment(self, amount=300000, due="1405/07/15"):
        return self.client.post("/finance/installments",
                                json={"enrollment_id": 1, "amount": amount, "due_date": due},
                                headers=hdr("tok-admin"))


class TestWalletPayments(FinanceWorld):
    def test_1_payment_credits_institute_wallet_and_writes_transaction(self):
        resp = self.client.post("/finance/pay", json=pay_payload(200000, "institute"),
                                headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(set(body) >= {"message", "receipt_id", "new_balance_teacher",
                                       "new_balance_institute"}, True, body)
        self.assertEqual(body["new_balance_institute"], 600000)
        self.assertFalse(body.get("duplicate", False))

        tx = self.db.query(models.Transaction).filter(models.Transaction.id == body["receipt_id"]).first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.amount, 200000)
        self.assertEqual(tx.type, "deposit")
        self.assertEqual(tx.target_wallet, "institute")
        self.assertEqual(tx.branch_id, 1, "رسید باید شعبهٔ شاگرد را بگیرد (Bug 9)")
        self.assertEqual(self.wallet().wallet_balance, 600000,
                         "wallet_balance باید جمع دو کیف بماند")

    def test_2_idempotency_key_prevents_double_payment(self):
        first = self.client.post("/finance/pay", json=pay_payload(150000, "institute", key="k-1"),
                                 headers=hdr("tok-admin"))
        second = self.client.post("/finance/pay", json=pay_payload(150000, "institute", key="k-1"),
                                  headers=hdr("tok-admin"))
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertTrue(second.json()["duplicate"], "تلاش دوم باید replay شود")
        self.assertEqual(second.json()["receipt_id"], first.json()["receipt_id"])
        self.assertEqual(self.wallet().wallet_institute, 550000,
                         "کیف پول فقط یک‌بار شارژ می‌شود (ضد پرداخت تکراری)")
        self.assertEqual(self.db.query(models.Transaction).filter(
            models.Transaction.idempotency_key == "k-1").count(), 1)

    def test_3_reusing_key_with_other_amount_is_rejected(self):
        self.client.post("/finance/pay", json=pay_payload(100000, "institute", key="k-2"),
                         headers=hdr("tok-admin"))
        other = self.client.post("/finance/pay", json=pay_payload(200000, "institute", key="k-2"),
                                 headers=hdr("tok-admin"))
        self.assertEqual(other.status_code, 422, other.text)
        self.assertEqual(self.wallet().wallet_institute, 500000, "مبلغ دوم نباید اعمال شود")

    def test_4_both_wallets_split_payment(self):
        resp = self.client.post("/finance/pay", json=pay_payload(
            300000, "both", amount_institute=200000, amount_teacher=100000), headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        st = self.wallet()
        self.assertEqual(st.wallet_institute, 600000)
        self.assertEqual(st.wallet_teacher, 100000)
        self.assertEqual(st.wallet_balance, 700000)

    def test_5_invalid_payments_are_rejected(self):
        cases = [pay_payload(0, "institute"), pay_payload(-5000, "institute"),
                 pay_payload(1000, "nowhere"), pay_payload(date="1410/01/01")]
        for body in cases:
            resp = self.client.post("/finance/pay", json=body, headers=hdr("tok-admin"))
            self.assertEqual(resp.status_code, 400, f"{body} ⇒ {resp.status_code}")
        self.assertEqual(self.wallet().wallet_institute, 400000, "هیچ‌کدام نباید کیف پول را تغییر دهند")


class TestInstallments(FinanceWorld):
    def test_6_create_pay_and_invoice_chain(self):
        created = self.create_installment(300000)
        self.assertEqual(created.status_code, 200, created.text)
        inst_id = created.json()["installment_id"]
        inst = self.db.query(models.Installment).filter(models.Installment.id == inst_id).first()
        self.assertIsNotNone(inst)
        self.assertEqual(inst.amount, 300000)
        self.assertFalse(bool(inst.is_paid))

        listing = self.client.get("/finance/installments?enrollment_id=1", headers=hdr("tok-admin"))
        self.assertEqual(listing.status_code, 200, listing.text)
        self.assertTrue(any(i["id"] == inst_id for i in listing.json()), listing.text)

        paid = self.client.post(f"/finance/installments/{inst_id}/pay",
                                params={"payment_method": "کارت"}, headers=hdr("tok-admin"))
        self.assertEqual(paid.status_code, 200, paid.text)
        if isinstance(paid.json(), dict) and "message" in paid.json():
            self.assertIn("رسید", paid.json()["message"])
        self.db.refresh(inst)
        self.assertTrue(bool(inst.is_paid))
        self.assertIsNotNone(inst.paid_at)
        self.assertEqual(self.wallet().wallet_institute, 700000, "قسط به کیف مؤسسه واریز می‌شود")

        invoice = self.client.get("/finance/invoice/1", headers=hdr("tok-admin"))
        self.assertEqual(invoice.status_code, 200, invoice.text)
        inv = invoice.json()
        self.assertEqual(inv["base_tuition"], 1000000)
        self.assertEqual(inv["final_tuition"], 1000000)
        self.assertEqual([i["id"] for i in inv["installments"]], [inst_id])

    def test_7_paying_an_already_paid_installment_is_rejected(self):
        inst_id = self.create_installment().json()["installment_id"]
        self.assertEqual(self.client.post(f"/finance/installments/{inst_id}/pay",
                                          params={"payment_method": "کارت"},
                                          headers=hdr("tok-admin")).status_code, 200)
        again = self.client.post(f"/finance/installments/{inst_id}/pay",
                                 params={"payment_method": "کارت"}, headers=hdr("tok-admin"))
        self.assertEqual(again.status_code, 400, again.text)
        self.assertEqual(self.wallet().wallet_institute, 700000, "دوباره واریز نمی‌شود")

    def test_8_reminder_needs_parent_mobile_and_writes_sms_log(self):
        inst_id = self.create_installment().json()["installment_id"]
        ok = self.client.post(f"/finance/installments/{inst_id}/remind", headers=hdr("tok-admin"))
        self.assertEqual(ok.status_code, 200, ok.text)
        self.assertEqual(ok.json()["status"], "success")
        sms = self.db.query(models.SmsLog).order_by(models.SmsLog.id.desc()).first()
        self.assertIsNotNone(sms, "یادآوری قسط باید پیامک ثبت کند")
        self.assertIn("قسط", sms.message_text)

        self.student.parent_mobile = None
        self.db.commit()
        blocked = self.client.post(f"/finance/installments/{inst_id}/remind", headers=hdr("tok-admin"))
        self.assertEqual(blocked.status_code, 400, blocked.text)


class TestDashboardsAndReceipts(FinanceWorld):
    def test_9_student_dashboard_numbers_are_consistent(self):
        self.create_installment(300000)
        self.client.post("/finance/pay", json=pay_payload(100000, "institute"), headers=hdr("tok-admin"))
        resp = self.client.get("/finance/student/41/dashboard", headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["wallet"]["wallet_institute"], 500000)
        self.assertEqual(body["wallet"]["wallet_teacher"], 0)
        self.assertEqual(body["wallet"]["balance"], 500000, "balance = مجموع دو کیف پول")
        self.assertEqual(body["wallet"]["total_paid"], 500000, "جمع پرداخت‌ها = پیش‌پرداخت + پرداخت جدید")
        self.assertEqual(body["wallet"]["total_debt"], 500000,
                         "بدهی = شهریه نهایی − پرداخت‌شده = 1,000,000 − 500,000")
        self.assertTrue(any(i["amount"] == 300000 for i in body["installments"]))
        self.assertTrue(any(t["amount"] == 100000 for t in body["recent_transactions"]))

    def test_10_receipt_and_invoice_render_for_the_android_invoice_screen(self):
        receipt = self.client.post("/finance/pay", json=pay_payload(120000, "institute"),
                                   headers=hdr("tok-admin")).json()
        tx_id = receipt["receipt_id"]

        detail = self.client.get(f"/finance/receipt/{tx_id}", headers=hdr("tok-admin"))
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["amount"], 120000, detail.text)
        self.assertEqual(detail.json()["student_name"], "علی تست")

        # ⛔ چاپ حواله در سرور با NameError می‌خورد (test_12 را ببینید) — اینجا فقط pdf تست می‌شود
        pdf = self.client.post("/finance/receipt/pdf",
                               json={"transaction_id": tx_id, "print_type": "pdf"},
                               headers=hdr("tok-admin"))
        self.assertEqual(pdf.status_code, 200, pdf.text)

    def test_12_receipt_print_endpoint_returns_print_job(self):
        """O-05 (رفع‌شده): «چاپ حواله» باید ۲۰۰ بدهد و `print_job_id` بسازد.

        ریشهٔ باگ: `routers/finance.py:602` از `time.time()` استفاده می‌کرد ولی `time` در فایل
        import نشده بود ⇒ هر فراخوانی `NameError` و **HTTP 500** می‌شد و دکمهٔ چاپ در
        `InvoiceActivity` هیچ‌وقت کار نمی‌کرد.
        """
        receipt = self.client.post("/finance/pay", json=pay_payload(90000, "institute"),
                                   headers=hdr("tok-admin")).json()
        printing = self.client.post("/finance/receipt/print",
                                    json={"transaction_id": receipt["receipt_id"], "print_type": "print"},
                                    headers=hdr("tok-admin"))
        self.assertEqual(printing.status_code, 200, printing.text)
        body = printing.json()
        self.assertEqual(body["status"], "success")
        self.assertTrue(body["print_job_id"].startswith("PRINT_"), body["print_job_id"])
        self.assertIn("receipt_data", body)

        pdf = self.client.post("/finance/receipt/pdf",
                               json={"transaction_id": receipt["receipt_id"], "print_type": "pdf"},
                               headers=hdr("tok-admin"))
        self.assertEqual(pdf.status_code, 200, "مسیر pdf هم‌خانواده باید سالم بماند")

    def test_11_student_class_status_matches_enrollment(self):
        self.client.post("/finance/pay", json=pay_payload(100000, "institute"), headers=hdr("tok-admin"))
        resp = self.client.get("/finance/student_class_status?student_id=41&course_id=71",
                               headers=hdr("tok-admin"))
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["total_amount"], 1000000, "کل شهریهٔ ثبت‌نام")
        self.assertEqual(body["paid_to_institute"], 500000, "پیش‌پرداخت ۴۰۰٬۰۰۰ + پرداخت ۱۰۰٬۰۰۰")
        # Contractual debt remains scoped to this enrollment even without a
        # session_charge; no other class is charged with this amount.
        self.assertEqual(body["due_to_institute"], 500000)
        self.assertEqual(body["due_to_teacher"], 0)
        self.assertEqual(body["enrollment_id"], 1)


    def test_11b_remaining_tuition_and_credit_are_sign_safe(self):
        """O-09: «باقی‌ماندهٔ شهریه» و «اعتبار» هر دو نامنفی و بی‌ابهام‌اند.

        `due_to_teacher`/`due_to_institute` همچنان با همان نام‌ها برمی‌گردند، اما
        اکنون از breakdown همین enrollment می‌آیند؛ wallet کلی دانش‌آموز در بدهی کلاس
        مصرف نمی‌شود.
        """
        self.client.post("/finance/pay", json=pay_payload(100000, "institute"), headers=hdr("tok-admin"))
        body = self.client.get("/finance/student_class_status?student_id=41&course_id=71",
                               headers=hdr("tok-admin")).json()
        # The selected enrollment's contractual remainder is the payable
        # amount; another enrollment's wallet is not used as a substitute.
        self.assertEqual(body["remaining_tuition"], 500000)
        self.assertEqual(body["credit_balance"], 0)
        self.assertEqual(body["due_to_institute"], 500000)
        self.assertEqual(body["due_to_teacher"], 0)
        self.assertEqual(body["total_amount"], 1000000)

        # پرداخت بیشتر از باقی‌مانده ⇒ باقی‌مانده صفر و مابه‌التفاوت «اعتبار» می‌شود
        self.client.post("/finance/pay", json=pay_payload(600000, "institute"), headers=hdr("tok-admin"))
        over = self.client.get("/finance/student_class_status?student_id=41&course_id=71",
                               headers=hdr("tok-admin")).json()
        self.assertEqual(over["remaining_tuition"], 0, "باقی‌مانده هرگز منفی نمی‌شود")
        self.assertEqual(over["credit_balance"], 100000, "مازاد پرداخت = اعتبار شاگرد")

        # فاکتور ثبت‌نام هم همین دو معنا را دارد (balance_due سبک قبلی خودش را حفظ کرده است)
        invoice = self.client.get("/finance/invoice/1", headers=hdr("tok-admin")).json()
        self.assertEqual(invoice["balance_due"], 0)
        self.assertEqual(invoice["remaining_tuition"], 0)
        self.assertEqual(invoice["credit_balance"], 100000)


if __name__ == "__main__":
    unittest.main()
