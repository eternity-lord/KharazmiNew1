"""Route-by-route audit for routers.finance.

The assertions are intentionally value-based. A 200 response alone is not a
passing audit: the seed values and the independent oracle must agree.
"""
from __future__ import annotations

import pytest

from .oracle import build_oracle


FINANCE_ROUTES = [
    ("GET", "/finance/search_advanced"),
    ("POST", "/finance/pay"),
    ("POST", "/finance/receipt/print"),
    ("POST", "/finance/receipt/pdf"),
    ("GET", "/finance/receipt/{transaction_id}"),
    ("POST", "/finance/payment/initiate"),
    ("GET", "/finance/payment/callback"),
    ("GET", "/finance/mock_payment_page"),
    ("POST", "/finance/transaction/{transaction_id}/refund"),
    ("GET", "/finance/installments"),
    ("POST", "/finance/installments"),
    ("PUT", "/finance/installments/{installment_id}"),
    ("DELETE", "/finance/installments/{installment_id}"),
    ("POST", "/finance/installments/{installment_id}/pay"),
    ("POST", "/finance/installments/{installment_id}/remind"),
    ("GET", "/finance/student/{student_id}/payments"),
    ("GET", "/finance/student/{student_id}/transactions"),
    ("GET", "/finance/student/{student_id}/dashboard"),
    ("GET", "/finance/student_class_status"),
    ("GET", "/finance/invoice/{enrollment_id}"),
    ("GET", "/finance/parent/dashboard"),
    ("GET", "/finance/reports/debtors_list"),
    ("GET", "/finance/reports/debtors_grouped"),
    ("GET", "/finance/reports/revenue_summary"),
    ("GET", "/finance/reports/teacher_settlements_summary"),
    ("POST", "/finance/debtors/remind"),
]


def _h(auth_headers, role="admin"):
    return auth_headers[role]


def test_finance_route_inventory_is_explicit(client):
    """Keep the router's 26 routes visible in the audit, including write routes."""
    paths = {(path, method.upper()) for path, operations in client.app.openapi()["paths"].items() for method in operations}
    missing = [(method, path) for method, path in FINANCE_ROUTES if (path, method.upper()) not in paths]
    assert not missing, missing


def test_student_dashboard_values_match_independent_oracle(client, auth_headers, db):
    response = client.get("/finance/student/1/dashboard", headers=_h(auth_headers))
    assert response.status_code == 200, response.text
    body = response.json()
    oracle = build_oracle(db)
    assert body["wallet"] == {"balance": -5000, "wallet_teacher": -10000, "wallet_institute": 5000, "total_paid": 800000, "total_debt": 2000000}
    assert {row["enrollment_id"] for row in body["enrollments"]} == {1, 2}
    assert body["enrollments"][0]["total_paid"] == oracle.enrollments[1].paid
    assert body["enrollments"][0]["outstanding"] == oracle.enrollments[1].due
    assert body["enrollments"][1]["final_tuition"] == 1_800_000


def test_invoice_and_class_status_agree(client, auth_headers, db):
    invoice = client.get("/finance/invoice/1", headers=_h(auth_headers))
    status = client.get("/finance/student_class_status", params={"student_id": 1, "course_id": 1}, headers=_h(auth_headers))
    assert invoice.status_code == 200, invoice.text
    assert status.status_code == 200, status.text
    inv, cls = invoice.json(), status.json()
    assert inv["enrollment_id"] == cls["enrollment_id"] == 1
    assert inv["final_tuition"] == cls["total_amount"] == 1_000_000
    assert inv["total_paid"] == cls["paid_to_institute"] == 300_000
    assert inv["balance_due"] == cls["remaining_tuition"] == 700_000
    assert inv["student_name"] == "دانش‌آموز تست 1"
    assert len(inv["installments"]) == 2
    oracle = build_oracle(db)
    assert oracle.enrollments[1].due == inv["balance_due"]

    discounted = client.get("/finance/invoice/2", headers=_h(auth_headers))
    assert discounted.status_code == 200, discounted.text
    discounted_body = discounted.json()
    assert discounted_body["base_tuition"] == oracle.enrollments[2].gross_tuition == 2_000_000
    assert discounted_body["discount_type"] == "percentage"
    assert discounted_body["discount_value"] == 10
    assert discounted_body["discount_amount"] == oracle.enrollments[2].discount == 200_000
    assert discounted_body["final_tuition"] == oracle.enrollments[2].net_tuition == 1_800_000
    assert discounted_body["total_paid"] == oracle.enrollments[2].paid == 500_000
    assert discounted_body["balance_due"] == oracle.enrollments[2].due == 1_300_000


def test_installment_list_preserves_values_and_empty_filter(client, auth_headers):
    response = client.get("/finance/installments", params={"enrollment_id": 1}, headers=_h(auth_headers))
    assert response.status_code == 200, response.text
    rows = response.json()
    assert [row["id"] for row in rows] == [1, 2]
    assert rows[0]["amount"] == 350_000
    assert rows[0]["is_paid"] is False
    empty = client.get("/finance/installments", params={"enrollment_id": 99999}, headers=_h(auth_headers))
    assert empty.status_code == 200
    assert empty.json() == []


def test_finance_search_and_debtors_are_not_only_status_checks(client, auth_headers, db):
    search = client.get("/finance/search_advanced", params={"query": "دانش‌آموز"}, headers=_h(auth_headers))
    debtors = client.get("/finance/reports/debtors_list", headers=_h(auth_headers))
    assert search.status_code == debtors.status_code == 200
    student = next(row for row in search.json() if row.get("type") == "student" and row.get("id") == 1)
    debtor = next(row for row in debtors.json() if row.get("student_id") == 1)
    assert student["title"] == "دانش‌آموز تست 1"
    assert student["total_debt"] == build_oracle(db).student_due[1]
    assert debtor["total_debt"] == student["total_debt"]
    assert debtor["active_courses"] == ["ریاضی پایه فعال", "فیزیک دوکلاسه"]


def test_revenue_summary_and_receipt_are_value_checked(client, auth_headers):
    revenue = client.get("/finance/reports/revenue_summary", headers=_h(auth_headers))
    receipt = client.get("/finance/receipt/1", headers=_h(auth_headers))
    transactions = client.get("/finance/student/1/transactions", headers=_h(auth_headers))
    assert revenue.status_code == receipt.status_code == transactions.status_code == 200
    totals = revenue.json()["totals"]
    assert totals["total_revenue"] == 675_000
    assert revenue.json()["revenue_by_wallet"]["teacher_wallet"]["total"] == 375_000
    assert revenue.json()["revenue_by_wallet"]["teacher_wallet"]["card"] == 125_000
    assert revenue.json()["revenue_by_wallet"]["institute_wallet"]["total"] == 300_000
    assert receipt.json()["amount"] == 300_000
    assert receipt.json()["student_name"] == "دانش‌آموز تست 1"
    assert {row["id"] for row in transactions.json()} == {1, 2}


def test_finance_schema_rejects_invalid_amounts_without_writing(client, auth_headers, db):
    before = db.query(__import__("models").Transaction).count()
    response = client.post("/finance/pay", json={"student_id": 1, "amount": -1, "target_wallet": "institute", "description": "bad", "payment_method": "نقدی", "date": "1405/06/20"}, headers=_h(auth_headers))
    assert response.status_code in (400, 422)
    db.expire_all()
    assert db.query(__import__("models").Transaction).count() == before


def test_direct_payment_retry_is_idempotent_without_duplicate_transaction(client, auth_headers, db):
    import models
    payload = {"student_id": 1, "amount": 12_345, "target_wallet": "institute", "description": "audit retry", "payment_method": "نقدی", "date": "1403/08/02", "enrollment_id": 1, "idempotency_key": "audit-direct-retry-01"}
    before_ids = {row.id for row in db.query(models.Transaction).all()}
    enrollment = db.get(models.Enrollment, 1)
    student = db.get(models.Student, 1)
    installment = db.get(models.Installment, 1)
    before_paid, before_wi = enrollment.total_paid, student.wallet_institute
    before_installment = (installment.is_paid, installment.paid_at, installment.paid_amount)
    first = client.post("/finance/pay", json=payload, headers=_h(auth_headers))
    second = client.post("/finance/pay", json=payload, headers=_h(auth_headers))
    assert first.status_code == second.status_code == 200, (first.text, second.text)
    assert first.json().get("transaction_id") == second.json().get("transaction_id")
    db.expire_all()
    created = db.query(models.Transaction).filter(~models.Transaction.id.in_(before_ids)).all()
    assert len(created) == 1
    assert created[0].amount == 12_345
    # Restore the seed event ledger for later tests.
    tx_id = created[0].id
    db.query(models.TransactionInstallmentAllocation).filter(models.TransactionInstallmentAllocation.transaction_id == tx_id).delete(synchronize_session=False)
    db.delete(created[0])
    enrollment = db.get(models.Enrollment, 1); student = db.get(models.Student, 1); installment = db.get(models.Installment, 1)
    enrollment.total_paid, student.wallet_institute = before_paid, before_wi
    installment.is_paid, installment.paid_at, installment.paid_amount = before_installment
    student.sync_wallet_balance()
    db.commit()


def test_installment_payment_is_atomic_and_updates_expected_rows(client, auth_headers, db):
    import models
    response = client.post("/finance/installments/1/pay", params={"payment_method": "نقدی"}, headers=_h(auth_headers))
    assert response.status_code == 200, response.text
    db.expire_all()
    inst = db.get(models.Installment, 1)
    assert inst.is_paid is True
    assert inst.paid_amount == 350_000
    tx = db.query(models.Transaction).filter(models.Transaction.id == response.json()["receipt_id"]).one()
    assert tx.amount == 350_000 and tx.target_wallet == "institute"
    # Replaying the state transition must not make a second receipt.
    second = client.post("/finance/installments/1/pay", params={"payment_method": "نقدی"}, headers=_h(auth_headers))
    assert second.status_code == 400
    assert db.query(models.Transaction).filter(models.Transaction.description.like("%قسط #1%")).count() == 1
    # Keep the shared seeded fixture immutable for later router tests.
    db.delete(tx)
    db.query(models.TransactionInstallmentAllocation).filter(models.TransactionInstallmentAllocation.transaction_id == tx.id).delete(synchronize_session=False)
    db.query(models.ActivityLog).filter(models.ActivityLog.action == "pay_installment_manual", models.ActivityLog.target_id == 1).delete(synchronize_session=False)
    inst.is_paid = False
    inst.paid_at = None
    inst.paid_amount = 0
    enrollment = db.get(models.Enrollment, 1)
    enrollment.total_paid = 300_000
    student = db.get(models.Student, 1)
    student.wallet_institute = 5_000
    student.sync_wallet_balance()
    db.commit()


def test_invoice_ignores_archived_payment_rows_in_debt_oracle(client, auth_headers, db):
    """Independent oracle: an archived 123,456 receipt cannot change enrollment 1's 300,000 paid total."""
    import models

    archived = models.Transaction(
        student_id=1, enrollment_id=1, course_id=1, branch_id=1,
        amount=123_456, payment_method="نقدی", tracking_code="AUD-ARCHIVED",
        date="1405/06/08", receiver="آموزشگاه", description="رسید آرشیوی ممیزی",
        type="deposit", target_wallet="institute", share_teacher=0,
        share_institute=123_456, is_deleted=True, is_reversed=False,
    )
    db.add(archived)
    db.commit()
    try:
        response = client.get("/finance/invoice/1", headers=_h(auth_headers))
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total_paid"] == 300_000
        assert body["balance_due"] == 700_000
        assert body["credit_balance"] == 0
    finally:
        db.delete(archived)
        db.commit()


def test_invoice_applies_fixed_discount_as_a_fixed_amount(client, auth_headers):
    """Independent oracle: 1,500,000 minus fixed 200,000 equals 1,300,000."""
    response = client.get("/finance/invoice/4", headers=_h(auth_headers))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["base_tuition"] == 1_500_000
    assert body["discount_type"] == "fixed"
    assert body["discount_value"] == 200_000
    assert body["discount_amount"] == 200_000
    assert body["final_tuition"] == 1_300_000
    assert body["total_paid"] == 250_000
    assert body["balance_due"] == 1_050_000


def test_direct_payment_decrements_each_installment_cover_once(client, auth_headers, db):
    """Independent FIFO oracle: a 50,000 payment covers only installment 1."""
    import models

    inst_one = db.get(models.Installment, 1)
    inst_two = db.get(models.Installment, 2)
    enrollment = db.get(models.Enrollment, 1)
    student = db.get(models.Student, 1)
    before_installments = ((inst_one.is_paid, inst_one.paid_amount, inst_one.paid_at), (inst_two.is_paid, inst_two.paid_amount, inst_two.paid_at))
    before_paid = enrollment.total_paid
    before_wallet = (student.wallet_teacher, student.wallet_institute, student.wallet_balance)
    before_transactions = {row.id for row in db.query(models.Transaction).all()}
    try:
        response = client.post(
            "/finance/pay",
            json={
                "student_id": 1, "enrollment_id": 1, "amount": 50_000,
                "target_wallet": "institute", "description": "پرداخت FIFO ممیزی",
                "payment_method": "نقدی", "date": "1405/07/06",
            },
            headers=_h(auth_headers),
        )
        assert response.status_code == 200, response.text
        db.expire_all()
        inst_one, inst_two = db.get(models.Installment, 1), db.get(models.Installment, 2)
        assert (inst_one.is_paid, inst_one.paid_amount) == (False, 50_000)
        assert (inst_two.is_paid, inst_two.paid_amount) == (False, 100_000)
        allocation = db.query(models.TransactionInstallmentAllocation).filter(
            models.TransactionInstallmentAllocation.installment_id == 1,
            ~models.TransactionInstallmentAllocation.transaction_id.in_(before_transactions),
        ).one()
        assert allocation.amount == 50_000
    finally:
        new_transactions = db.query(models.Transaction).filter(~models.Transaction.id.in_(before_transactions)).all()
        new_ids = [row.id for row in new_transactions]
        if new_ids:
            db.query(models.TransactionInstallmentAllocation).filter(models.TransactionInstallmentAllocation.transaction_id.in_(new_ids)).delete(synchronize_session=False)
            for row in new_transactions:
                db.delete(row)
        inst_one, inst_two = db.get(models.Installment, 1), db.get(models.Installment, 2)
        inst_one.is_paid, inst_one.paid_amount, inst_one.paid_at = before_installments[0]
        inst_two.is_paid, inst_two.paid_amount, inst_two.paid_at = before_installments[1]
        enrollment = db.get(models.Enrollment, 1)
        enrollment.total_paid = before_paid
        student = db.get(models.Student, 1)
        student.wallet_teacher, student.wallet_institute, student.wallet_balance = before_wallet
        db.commit()
