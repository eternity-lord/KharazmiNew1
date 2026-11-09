"""Value/state audit for teacher settlement and read contracts."""
from __future__ import annotations

import json

from .route_registry import route_id, routes

ROUTE_IDS = [
    'GET' + ' ' + '/teachers/list',
    'GET' + ' ' + '/teachers/list/excel',
    'POST' + ' ' + '/teachers/register',
    'PUT' + ' ' + '/teachers/update/{teacher_id}',
    'GET' + ' ' + '/teachers/{id}/full_profile',
    'GET' + ' ' + '/teachers/{id}/today_summary',
    'POST' + ' ' + '/teachers/{id}/upload_photo',
    'GET' + ' ' + '/teachers/{teacher_id}',
    'GET' + ' ' + '/teachers/{teacher_id}/classes',
    'GET' + ' ' + '/teachers/{teacher_id}/collaboration_summary',
    'GET' + ' ' + '/teachers/{teacher_id}/communication_history',
    'GET' + ' ' + '/teachers/{teacher_id}/incomplete_classes',
    'GET' + ' ' + '/teachers/{teacher_id}/pending_classes',
    'GET' + ' ' + '/teachers/{teacher_id}/pending_settlement',
    'POST' + ' ' + '/teachers/{teacher_id}/settle',
    'GET' + ' ' + '/teachers/{teacher_id}/settlement_history',
    'PUT' + ' ' + '/teachers/{teacher_id}/settlements/{settlement_id}/edit',
    'POST' + ' ' + '/teachers/{teacher_id}/settlements/{settlement_id}/reverse',
]


def test_teachers_route_inventory_is_explicit():
    expected = {route_id(row) for row in routes() if row["handler"].split(".")[1] == 'teachers'}
    assert set(ROUTE_IDS) == expected


def test_teacher_settlement_retry_reversal_and_wallet_effect(client, auth_headers, db):
    """Independent numeric oracle: session 2 is a 300,000 تومان open claim."""
    import models

    teacher_headers = auth_headers["teacher"]
    admin_headers = auth_headers["admin"]
    student = db.get(models.Student, 1)
    wallet_before = (student.wallet_teacher, student.wallet_institute, student.wallet_balance)
    attendance = db.query(models.Attendance).filter(models.Attendance.session_id == 2).one()
    assert attendance.is_billed is False

    pending = client.get("/teachers/1/pending_settlement", headers=teacher_headers)
    assert pending.status_code == 200, pending.text
    pending_body = pending.json()
    session_row = next(row for row in pending_body["pending_sessions"] if row["session_id"] == 2)
    assert session_row["amount"] == 300_000
    assert pending_body["total_amount"] == 300_000

    before_transactions = db.query(models.Transaction).count()
    settled = client.post("/teachers/1/settle", json={"session_ids": [2]}, headers=admin_headers)
    assert settled.status_code == 200, settled.text
    settled_body = settled.json()
    assert settled_body["total_amount"] == 300_000
    assert settled_body["session_count"] == 1
    db.expire_all()
    settlement = db.get(models.Settlement, settled_body["settlement_id"])
    assert settlement.total_amount == 300_000
    assert sorted(json.loads(settlement.session_ids_json)) == [2]
    payout = db.get(models.Transaction, settlement.payout_transaction_id)
    assert payout.amount == -300_000
    assert payout.type == "settlement_payout"
    assert payout.settlement_id == settlement.id
    assert db.query(models.Transaction).count() == before_transactions + 1
    assert db.get(models.Attendance, attendance.id).is_billed is True
    assert (student.wallet_teacher, student.wallet_institute, student.wallet_balance) == wallet_before

    retry = client.post("/teachers/1/settle", json={"session_ids": [2]}, headers=admin_headers)
    assert retry.status_code == 400
    assert db.query(models.Transaction).count() == before_transactions + 1

    reversed_response = client.post(
        f"/teachers/1/settlements/{settlement.id}/reverse",
        params={"reason": "ممیزی برگشت"},
        headers=admin_headers,
    )
    assert reversed_response.status_code == 200, reversed_response.text
    reversal_body = reversed_response.json()
    assert reversal_body["session_ids"] == [2]
    db.expire_all()
    db.refresh(settlement)
    assert settlement.is_reversed is True
    reversal = db.get(models.Transaction, reversal_body["reversal_transaction_id"])
    assert reversal.amount == 300_000
    assert reversal.type == "reversal"
    assert db.get(models.Attendance, attendance.id).is_billed is False
    restored_pending = client.get("/teachers/1/pending_settlement", headers=teacher_headers).json()
    assert next(row for row in restored_pending["pending_sessions"] if row["session_id"] == 2)["amount"] == 300_000

    reverse_retry = client.post(
        f"/teachers/1/settlements/{settlement.id}/reverse",
        params={"reason": "تکرار"},
        headers=admin_headers,
    )
    assert reverse_retry.status_code == 409

    # Restore the fixture so this stateful audit is order-independent.
    db.rollback()
    db.query(models.Transaction).filter(models.Transaction.id.in_([payout.id, reversal.id])).delete(synchronize_session=False)
    db.delete(settlement)
    db.get(models.Attendance, attendance.id).is_billed = False
    db.commit()
    assert db.query(models.Transaction).count() == before_transactions
    assert (student.wallet_teacher, student.wallet_institute, student.wallet_balance) == wallet_before
