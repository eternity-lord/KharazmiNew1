"""Value, filtering, pagination, and Android-contract audit for audit_trail."""
from __future__ import annotations

import json
from datetime import datetime, time, timedelta, timezone

import pytest
from sqlalchemy import select

from .clock import FIXED_NOW
from .route_registry import route_id, routes

ROUTE_IDS = [
    'GET' + ' ' + '/audit-trail/logs',
]
AUDIT_RESPONSE_KEYS = {"logs", "total", "page", "limit", "pages"}
AUDIT_LOG_KEYS = {
    "id", "timestamp", "username", "action", "entity_type", "entity_id",
    "old_values", "new_values", "ip_address", "changed_fields", "labels",
    "changed_labels", "change_summary", "action_label", "change_type",
    "action_color", "icon_color", "entity_refs", "student_id", "student_name",
    "student_statement_path", "actor_username", "actor_source", "actor_action",
    "actor_action_key",
}


def _payload(response):
    assert response.status_code == 200, response.text
    value = response.json()
    assert set(value) == AUDIT_RESPONSE_KEYS
    assert isinstance(value["logs"], list)
    for log in value["logs"]:
        assert set(log) == AUDIT_LOG_KEYS
    return value


def _database_snapshot(db):
    import models

    snapshot = {}
    for table in models.Base.metadata.sorted_tables:
        statement = select(table)
        primary_key = list(table.primary_key.columns)
        if primary_key:
            statement = statement.order_by(*primary_key)
        snapshot[table.name] = [tuple(row) for row in db.execute(statement).all()]
    return snapshot


def _make_log(*, timestamp, entity_type="transaction", entity_id, action="create",
              user_id=None, username=None, old_values=None, new_values=None,
              ip_address=None):
    import models

    return models.FinancialAuditLog(
        timestamp=timestamp,
        user_id=user_id,
        username=username,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_values=json.dumps(old_values, ensure_ascii=False) if old_values is not None else None,
        new_values=json.dumps(new_values, ensure_ascii=False) if new_values is not None else None,
        ip_address=ip_address,
    )


def _delete_probe_rows(db, *, log_ids=(), entity_ids=(), activity_ids=()):
    import models

    if log_ids:
        db.query(models.FinancialAuditLog).filter(models.FinancialAuditLog.id.in_(log_ids)).delete(
            synchronize_session=False
        )
    if entity_ids:
        db.query(models.FinancialAuditLog).filter(
            models.FinancialAuditLog.entity_id.in_(entity_ids)
        ).delete(synchronize_session=False)
    if activity_ids:
        db.query(models.ActivityLog).filter(models.ActivityLog.id.in_(activity_ids)).delete(
            synchronize_session=False
        )
    db.commit()


def _local_iso_for_utc(value):
    return value.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None).isoformat(sep=" ")


def _utc_naive_for_local(value):
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def test_audit_trail_route_inventory_is_explicit():
    expected = {route_id(row) for row in routes() if row["handler"].split(".")[1] == 'audit_trail'}
    assert set(ROUTE_IDS) == expected


def test_audit_trail_empty_and_unmatched_search_return_empty_envelope(client, auth_headers, db):
    before = _database_snapshot(db)
    by_entity = _payload(client.get(
        "/audit-trail/logs", headers=auth_headers["admin"],
        params={"entity_type": "transaction", "entity_id": 9_910_001},
    ))
    assert by_entity == {"logs": [], "total": 0, "page": 1, "limit": 50, "pages": 0}

    no_search_match = _payload(client.get(
        "/audit-trail/logs", headers=auth_headers["admin"],
        params={"search": "AUDIT-TRAIL-NO-SUCH-RECEIVER-7F9C"},
    ))
    assert no_search_match == {"logs": [], "total": 0, "page": 1, "limit": 50, "pages": 0}
    db.expire_all()
    assert _database_snapshot(db) == before


def test_audit_trail_android_contract_filters_and_enriched_values(client, auth_headers, db):
    import models

    transaction_params = {
        "entity_type": "transaction", "entity_id": 1, "action": "update",
        "user_id": 1, "search": "دانش‌آموز تست 1", "limit": 200,
    }
    installment_params = {
        "entity_type": "installment", "entity_id": 1, "action": "delete",
        "user_id": 1, "search": "دانش‌آموز تست 1", "limit": 200,
    }
    search_params = {"search": "دانش‌آموز تست 1", "limit": 200}
    baseline_transaction = _payload(client.get(
        "/audit-trail/logs", headers=auth_headers["admin"], params=transaction_params,
    ))["total"]
    baseline_installment = _payload(client.get(
        "/audit-trail/logs", headers=auth_headers["admin"], params=installment_params,
    ))["total"]
    baseline_search = _payload(client.get(
        "/audit-trail/logs", headers=auth_headers["admin"], params=search_params,
    ))["total"]

    transaction_old = {
        "amount": 100_000, "student_id": 1, "enrollment_id": 1,
        "course_id": 1, "branch_id": 1, "is_deleted": False, "is_reversed": False,
    }
    transaction_new = {**transaction_old, "amount": 125_000}
    transaction_log = _make_log(
        timestamp=FIXED_NOW + timedelta(minutes=1), entity_type="transaction", entity_id=1,
        action="update", user_id=1, username="audit-trail-contract-probe",
        old_values=transaction_old, new_values=transaction_new, ip_address="198.51.100.42",
    )
    installment_old = {
        "enrollment_id": 1, "amount": 350_000, "due_date": "1405/06/01",
        "is_paid": False, "paid_amount": 0,
    }
    installment_log = _make_log(
        timestamp=FIXED_NOW + timedelta(minutes=2), entity_type="installment", entity_id=1,
        action="delete", user_id=1, old_values=installment_old,
    )
    activity = models.ActivityLog(
        admin_username="audit-trail-fallback-probe", action="delete_installment",
        target_id=1, target_name="قسط آزمایشی", details="fallback actor probe",
        timestamp=FIXED_NOW + timedelta(minutes=2),
    )
    db.add_all([transaction_log, installment_log, activity])
    db.commit()
    log_ids = [transaction_log.id, installment_log.id]
    activity_ids = [activity.id]

    try:
        before_reads = _database_snapshot(db)
        filtered_transaction = _payload(client.get(
            "/audit-trail/logs", headers=auth_headers["admin"], params=transaction_params,
        ))
        from .kotlin_contract import audit_payload
        assert audit_payload("AuditTrailResponse", filtered_transaction) == []
        assert filtered_transaction["total"] == baseline_transaction + 1
        tx = next(item for item in filtered_transaction["logs"]
                  if item["username"] == "audit-trail-contract-probe")
        assert tx["id"] == transaction_log.id
        assert tx["timestamp"] == _local_iso_for_utc(transaction_log.timestamp)
        assert tx["username"] == "audit-trail-contract-probe"
        assert tx["action"] == "update"
        assert tx["entity_type"] == "transaction" and tx["entity_id"] == 1
        assert tx["old_values"] == transaction_old and tx["new_values"] == transaction_new
        assert tx["ip_address"] == "198.51.100.42"
        assert tx["changed_fields"] == ["amount"]
        assert tx["labels"] == {"amount": "مبلغ"}
        assert tx["changed_labels"] == ["مبلغ"]
        assert tx["change_summary"] == "تغییر کرد: مبلغ: 100,000 ← 125,000"
        assert tx["action_label"] == "ویرایش" and tx["change_type"] == "edited"
        assert tx["action_color"] == tx["icon_color"] == "#FB8C00"
        assert tx["entity_refs"] == {
            "student": "دانش‌آموز تست 1", "teacher": "رضا فعال",
            "course": "ریاضی پایه فعال", "branch": "شعبه مرکزی تست",
        }
        assert tx["student_id"] == 1 and tx["student_name"] == "دانش‌آموز تست 1"
        assert tx["student_statement_path"] == "/reports/student_statement?student_id=1"
        assert tx["actor_username"] == "audit-trail-contract-probe"
        assert tx["actor_source"] == "audit_context"
        assert tx["actor_action"] is None and tx["actor_action_key"] is None

        filtered_installment = _payload(client.get(
            "/audit-trail/logs", headers=auth_headers["admin"], params=installment_params,
        ))
        assert filtered_installment["total"] == baseline_installment + 1
        installment = next(item for item in filtered_installment["logs"]
                           if item["id"] == installment_log.id)
        assert installment["action"] == "delete"
        assert installment["entity_refs"] == {
            "student": "دانش‌آموز تست 1", "teacher": "رضا فعال",
            "course": "ریاضی پایه فعال", "branch": "شعبه مرکزی تست",
            "enrollment": "دانش‌آموز تست 1 — ریاضی پایه فعال",
        }
        assert installment["actor_username"] == "audit-trail-fallback-probe"
        assert installment["actor_source"] == "activity_log"
        assert installment["actor_action"] == "حذف قسط"
        assert installment["actor_action_key"] == "delete_installment"
        assert installment["change_type"] == "deleted"
        assert installment["action_color"] == "#E53935"

        searched = _payload(client.get(
            "/audit-trail/logs", headers=auth_headers["admin"], params=search_params,
        ))
        assert searched["total"] == baseline_search + 2
        assert {item["id"] for item in searched["logs"]} >= {transaction_log.id, installment_log.id}
        db.expire_all()
        assert _database_snapshot(db) == before_reads
    finally:
        _delete_probe_rows(db, log_ids=log_ids, activity_ids=activity_ids)


def test_audit_trail_date_filters_order_and_jalali_full_day(client, auth_headers, db):
    import models

    day = FIXED_NOW.date()
    local_start = datetime.combine(day, time.min)
    local_next = local_start + timedelta(days=1)
    start_utc = _utc_naive_for_local(local_start)
    midday_utc = _utc_naive_for_local(datetime.combine(day, time(hour=12)))
    last_tick_utc = _utc_naive_for_local(local_next - timedelta(microseconds=1))
    next_start_utc = _utc_naive_for_local(local_next)
    entity_id = 9_920_001
    entries = [
        _make_log(timestamp=start_utc, entity_id=entity_id, username="date-start"),
        _make_log(timestamp=midday_utc, entity_id=entity_id, username="date-midday"),
        _make_log(timestamp=last_tick_utc, entity_id=entity_id, username="date-last-tick"),
        _make_log(timestamp=next_start_utc, entity_id=entity_id, username="date-next-day"),
    ]
    db.add_all(entries)
    db.commit()
    log_ids = [row.id for row in entries]
    try:
        before_reads = _database_snapshot(db)
        gregorian = _payload(client.get(
            "/audit-trail/logs", headers=auth_headers["admin"],
            params={"entity_type": "transaction", "entity_id": entity_id,
                    "start_date": day.isoformat(), "end_date": "2026-09-28T23:59:59.999999", "limit": 10},
        ))
        assert gregorian["total"] == 3
        assert [item["id"] for item in gregorian["logs"]] == [entries[2].id, entries[1].id, entries[0].id]

        jalali = _payload(client.get(
            "/audit-trail/logs", headers=auth_headers["admin"],
            params={"entity_type": "transaction", "entity_id": entity_id,
                    "start_date": "1405/07/06", "end_date": "1405/07/06", "limit": 10},
        ))
        assert jalali["total"] == 3
        assert [item["id"] for item in jalali["logs"]] == [entries[2].id, entries[1].id, entries[0].id]

        exact_timestamp = _payload(client.get(
            "/audit-trail/logs", headers=auth_headers["admin"],
            params={"entity_type": "transaction", "entity_id": entity_id,
                    "start_date": "2026-09-28T12:00:00", "end_date": "2026-09-28T12:00:00"},
        ))
        assert exact_timestamp["total"] == 1
        assert exact_timestamp["logs"][0]["id"] == entries[1].id
        db.expire_all()
        assert _database_snapshot(db) == before_reads
    finally:
        _delete_probe_rows(db, entity_ids=[entity_id])


def test_audit_trail_iso_end_date_includes_the_whole_selected_day(client, auth_headers, db):
    import models

    day = FIXED_NOW.date()
    entity_id = 9_920_002
    local_start = datetime.combine(day, time.min)
    entries = [
        _make_log(timestamp=_utc_naive_for_local(local_start), entity_id=entity_id, username="iso-day-start"),
        _make_log(timestamp=_utc_naive_for_local(local_start + timedelta(hours=9)),
                  entity_id=entity_id, username="iso-day-midday"),
    ]
    db.add_all(entries)
    db.commit()
    try:
        response = _payload(client.get(
            "/audit-trail/logs", headers=auth_headers["admin"],
            params={"entity_type": "transaction", "entity_id": entity_id,
                    "end_date": day.isoformat(), "limit": 10},
        ))
        assert response["total"] == 2
        assert {item["id"] for item in response["logs"]} == {row.id for row in entries}
    finally:
        _delete_probe_rows(db, entity_ids=[entity_id])


def test_audit_trail_rejects_invalid_filters_without_database_changes(client, auth_headers, db):
    cases = [
        ({"entity_type": "payment"}, 400),
        ({"action": "refund"}, 400),
        ({"entity_id": 0}, 422),
        ({"page": 0}, 422),
        ({"limit": 201}, 422),
        ({"start_date": "2026-02-30"}, 400),
        ({"start_date": "1405/13/01"}, 400),
    ]
    before = _database_snapshot(db)
    for params, expected_status in cases:
        response = client.get("/audit-trail/logs", headers=auth_headers["admin"], params=params)
        assert response.status_code == expected_status, (params, response.text)
        assert response.json().get("detail")
    db.expire_all()
    assert _database_snapshot(db) == before


@pytest.mark.parametrize(
    "start_date,end_date",
    [("2026-09-29", "2026-09-28"), ("1405/07/07", "1405/07/06")],
    ids=["iso", "jalali"],
)
def test_audit_trail_rejects_reversed_date_only_range(client, auth_headers, start_date, end_date):
    response = client.get(
        "/audit-trail/logs", headers=auth_headers["admin"],
        params={"start_date": start_date, "end_date": end_date},
    )
    assert response.status_code == 400, response.text


def test_audit_trail_survives_orphan_deleted_and_suspended_references(client, auth_headers, db):
    missing_entity_id = 9_930_001
    historic_entity_id = 9_930_002
    missing = _make_log(
        timestamp=FIXED_NOW + timedelta(minutes=3), entity_id=missing_entity_id,
        action="delete", username="orphan-reference",
        old_values={"amount": 1, "student_id": 999_999, "course_id": 999_999,
                    "branch_id": 999_999, "enrollment_id": 999_999},
    )
    historical = _make_log(
        timestamp=FIXED_NOW + timedelta(minutes=4), entity_id=historic_entity_id,
        action="create", username="historic-deleted-student",
        new_values={"amount": 50_000, "student_id": 3, "course_id": 3,
                    "branch_id": 2, "enrollment_id": 4},
    )
    db.add_all([missing, historical])
    db.commit()
    try:
        before_reads = _database_snapshot(db)
        orphan_response = _payload(client.get(
            "/audit-trail/logs", headers=auth_headers["admin"],
            params={"entity_type": "transaction", "entity_id": missing_entity_id},
        ))
        orphan = orphan_response["logs"][0]
        assert orphan_response["total"] == 1
        assert orphan["entity_refs"] == {"student": "", "teacher": ""}
        assert orphan["student_name"] == ""
        assert "None" not in str(orphan["entity_refs"])

        historic_response = _payload(client.get(
            "/audit-trail/logs", headers=auth_headers["admin"],
            params={"entity_type": "transaction", "entity_id": historic_entity_id},
        ))
        historic = historic_response["logs"][0]
        assert historic_response["total"] == 1
        assert historic["entity_refs"]["student"] == "دانش‌آموز تست 3"  # soft-deleted student
        assert historic["entity_refs"]["teacher"] == "مریم معلق"  # suspended teacher
        assert historic["entity_refs"]["course"] == "زبان معلق"  # suspended course
        assert historic["entity_refs"]["branch"] == "شعبه غرب تست"
        db.expire_all()
        assert _database_snapshot(db) == before_reads
    finally:
        _delete_probe_rows(db, entity_ids=[missing_entity_id, historic_entity_id])


def test_audit_trail_default_limit_sorting_and_page_boundaries(client, auth_headers, db):
    entity_id = 9_940_001
    timestamp = FIXED_NOW - timedelta(minutes=1)
    entries = [
        _make_log(timestamp=timestamp, entity_id=entity_id, username="pagination-probe", new_values={})
        for _ in range(205)
    ]
    db.add_all(entries)
    db.commit()
    ids = [row.id for row in entries]
    try:
        before_reads = _database_snapshot(db)
        first = _payload(client.get(
            "/audit-trail/logs", headers=auth_headers["admin"],
            params={"entity_type": "transaction", "entity_id": entity_id},
        ))
        assert first["total"] == 205 and first["page"] == 1 and first["limit"] == 50 and first["pages"] == 5
        assert [item["id"] for item in first["logs"]] == list(reversed(ids[-50:]))

        fifth = _payload(client.get(
            "/audit-trail/logs", headers=auth_headers["admin"],
            params={"entity_type": "transaction", "entity_id": entity_id, "page": 5},
        ))
        assert fifth["total"] == 205 and fifth["page"] == 5 and fifth["pages"] == 5
        assert [item["id"] for item in fifth["logs"]] == list(reversed(ids[:5]))

        past_end = _payload(client.get(
            "/audit-trail/logs", headers=auth_headers["admin"],
            params={"entity_type": "transaction", "entity_id": entity_id, "page": 6},
        ))
        assert past_end == {"logs": [], "total": 205, "page": 6, "limit": 50, "pages": 5}

        maximum = _payload(client.get(
            "/audit-trail/logs", headers=auth_headers["admin"],
            params={"entity_type": "transaction", "entity_id": entity_id, "limit": 200},
        ))
        assert maximum["total"] == 205 and maximum["limit"] == 200 and maximum["pages"] == 2
        assert [item["id"] for item in maximum["logs"]] == list(reversed(ids[-200:]))
        db.expire_all()
        assert _database_snapshot(db) == before_reads
    finally:
        _delete_probe_rows(db, entity_ids=[entity_id])


def test_audit_trail_rolled_back_financial_write_does_not_leak_into_history(client, auth_headers, db):
    import models
    from routers.audit_trail import reset_audit_context, set_audit_context

    baseline = _payload(client.get(
        "/audit-trail/logs", headers=auth_headers["admin"],
        params={"entity_type": "transaction", "entity_id": 1, "action": "update", "user_id": 1,
                "search": "دانش‌آموز تست 1", "limit": 200},
    ))["total"]
    before_mutation = _database_snapshot(db)
    transaction = db.get(models.Transaction, 1)
    original_amount = transaction.amount
    context_token = set_audit_context(1, "audit-trail-rollback-probe", "198.51.100.77")
    try:
        transaction.amount = original_amount + 1
        db.flush()
        pending = db.query(models.FinancialAuditLog).filter(
            models.FinancialAuditLog.entity_type == "transaction",
            models.FinancialAuditLog.entity_id == 1,
            models.FinancialAuditLog.action == "update",
            models.FinancialAuditLog.username == "audit-trail-rollback-probe",
        ).all()
        assert len(pending) == 1
        db.rollback()
    finally:
        reset_audit_context(context_token)
        db.rollback()

    assert db.get(models.Transaction, 1).amount == original_amount
    assert db.query(models.FinancialAuditLog).filter(
        models.FinancialAuditLog.username == "audit-trail-rollback-probe"
    ).count() == 0
    assert _database_snapshot(db) == before_mutation
    after = _payload(client.get(
        "/audit-trail/logs", headers=auth_headers["admin"],
        params={"entity_type": "transaction", "entity_id": 1, "action": "update", "user_id": 1,
                "search": "دانش‌آموز تست 1", "limit": 200},
    ))
    assert after["total"] == baseline
    assert not any(item["username"] == "audit-trail-rollback-probe" for item in after["logs"])
