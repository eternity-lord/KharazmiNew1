"""Read-only value and pattern audit for the suspicious-pattern endpoint."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from .clock import FIXED_NOW
from .route_registry import route_id, routes

ROUTE_IDS = [
    'GET' + ' ' + '/audit/suspicious_patterns',
]


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


ALERT_KEYS = {
    "type", "severity", "title", "description", "entity_id", "entity_name", "detected_at",
}


def _alerts_from(response):
    assert response.status_code == 200, response.text
    alerts = response.json()
    assert isinstance(alerts, list)
    for alert in alerts:
        assert set(alert) == ALERT_KEYS
    return alerts


def _cleanup_transaction_probe(db, transaction_id):
    import models

    db.expire_all()
    transaction = db.get(models.Transaction, transaction_id)
    if transaction is not None:
        db.delete(transaction)
        db.commit()
    db.query(models.ActivityLog).filter(models.ActivityLog.target_id == transaction_id).delete(synchronize_session=False)
    db.query(models.FinancialAuditLog).filter(
        models.FinancialAuditLog.entity_type == "transaction",
        models.FinancialAuditLog.entity_id == transaction_id,
    ).delete(synchronize_session=False)
    db.commit()


def test_audit_route_inventory_is_explicit():
    expected = {route_id(row) for row in routes() if row["handler"].split(".")[1] == 'audit'}
    assert set(ROUTE_IDS) == expected


def test_audit_seed_response_has_exact_alert_shape_and_is_read_only(client, auth_headers, db):
    before = _database_snapshot(db)
    alerts = _alerts_from(client.get("/audit/suspicious_patterns", headers=auth_headers["admin"]))
    db.expire_all()
    assert alerts == []
    assert _database_snapshot(db) == before


def test_audit_pattern_a_reports_night_and_delayed_sessions_with_frozen_time(client, auth_headers, db):
    import models

    rows = [
        models.SessionLog(
            session_code=87_001, course_id=1, date="1405/07/10", time="۰۲:۳۰",
            start_time="۰۲:۳۰", end_time="۰۳:۰۰", status="Finished", is_deleted=False,
        ),
        models.SessionLog(
            session_code=87_002, course_id=1, date="1405/07/11", time="23:00",
            start_time="23:00", end_time="23:30", status="Finished", is_deleted=False,
        ),
    ]
    db.add_all(rows)
    db.commit()
    try:
        before = _database_snapshot(db)
        alerts = _alerts_from(client.get("/audit/suspicious_patterns", headers=auth_headers["admin"]))
        relevant = {row["entity_id"]: row for row in alerts if row["entity_id"] in {item.id for item in rows}}
        assert set(relevant) == {item.id for item in rows}
        night = relevant[rows[0].id]
        delay = relevant[rows[1].id]
        assert night["type"] == "suspicious_attendance"
        assert night["severity"] == "high"
        assert "02:30" in night["description"] or "۰۲:۳۰" in night["description"]
        assert delay["type"] == "suspicious_attendance"
        assert "اختلاف 7 ساعت" in delay["description"]
        assert night["detected_at"] == delay["detected_at"] == FIXED_NOW.strftime("%Y-%m-%d %H:%M:%S")
        db.expire_all()
        assert _database_snapshot(db) == before
    finally:
        db.query(models.SessionLog).filter(models.SessionLog.session_code.in_([87_001, 87_002])).delete(synchronize_session=False)
        db.commit()


def test_audit_pattern_b_flags_only_recent_rapid_deleted_transaction(client, auth_headers, db):
    import models

    transaction = models.Transaction(
        student_id=1, enrollment_id=1, course_id=1, branch_id=1,
        amount=234_567, payment_method="نقدی", tracking_code="AUD-RAPID-DELETE",
        date="1405/07/01", receiver="آموزشگاه", description="audit rapid delete",
        type="deposit", target_wallet="institute", share_teacher=0, share_institute=234_567,
        is_deleted=True, is_reversed=False,
    )
    boundary_transaction = models.Transaction(
        student_id=1, enrollment_id=1, course_id=1, branch_id=1,
        amount=345_678, payment_method="نقدی", tracking_code="AUD-ONE-HOUR-DELETE",
        date="1405/07/01", receiver="آموزشگاه", description="audit one-hour boundary",
        type="deposit", target_wallet="institute", share_teacher=0, share_institute=345_678,
        is_deleted=True, is_reversed=False,
    )
    db.add_all([transaction, boundary_transaction])
    db.flush()
    transaction_id = transaction.id
    boundary_transaction_id = boundary_transaction.id
    created = FIXED_NOW - timedelta(minutes=20)
    deleted = FIXED_NOW - timedelta(minutes=10)
    boundary_created = FIXED_NOW - timedelta(hours=2)
    boundary_deleted = FIXED_NOW - timedelta(hours=1)
    db.add_all([
        models.ActivityLog(
            admin_username="audit-admin", action="create_transaction", target_id=transaction_id,
            target_name="تراکنش آزمایشی", details=f"ایجاد تراکنش #{transaction_id}", timestamp=created,
        ),
        models.ActivityLog(
            admin_username="audit-admin", action="transaction_delete", target_id=transaction_id,
            target_name="تراکنش آزمایشی", details=f"حذف تراکنش #{transaction_id}", timestamp=deleted,
        ),
        models.ActivityLog(
            admin_username="audit-admin", action="create_transaction", target_id=boundary_transaction_id,
            details=f"ایجاد تراکنش #{boundary_transaction_id}", timestamp=boundary_created,
        ),
        models.ActivityLog(
            admin_username="audit-admin", action="transaction_delete", target_id=boundary_transaction_id,
            details=f"حذف تراکنش #{boundary_transaction_id}", timestamp=boundary_deleted,
        ),
    ])
    db.commit()
    try:
        before = _database_snapshot(db)
        alerts = _alerts_from(client.get("/audit/suspicious_patterns", headers=auth_headers["admin"]))
        matches = [row for row in alerts if row["type"] == "rapid_deletion" and row["entity_id"] == transaction_id]
        assert len(matches) == 1
        alert = matches[0]
        assert alert["severity"] == "high"
        assert str(transaction_id) in alert["entity_name"]
        assert "دانش‌آموز تست 1" in alert["entity_name"]
        assert "به سرعت پس از ایجاد حذف شده است" in alert["description"]
        assert not any(
            row["type"] == "rapid_deletion" and row["entity_id"] == boundary_transaction_id
            for row in alerts
        )  # exactly one hour is not <1h
        db.expire_all()
        assert _database_snapshot(db) == before
    finally:
        _cleanup_transaction_probe(db, transaction_id)
        _cleanup_transaction_probe(db, boundary_transaction_id)


def test_audit_pattern_b_ignores_deleted_rows_with_logs_older_than_thirty_days(client, auth_headers, db):
    import models

    transaction = models.Transaction(
        student_id=1, enrollment_id=1, course_id=1, branch_id=1,
        amount=345_678, payment_method="نقدی", tracking_code="AUD-OLD-DELETE",
        date="1405/06/01", receiver="آموزشگاه", description="old audit delete",
        type="deposit", target_wallet="institute", share_teacher=0, share_institute=345_678,
        is_deleted=True, is_reversed=False,
    )
    db.add(transaction)
    db.flush()
    transaction_id = transaction.id
    old_created = FIXED_NOW - timedelta(days=32)
    old_deleted = old_created + timedelta(minutes=10)
    db.add_all([
        models.ActivityLog(
            admin_username="audit-admin", action="create_transaction", target_id=transaction_id,
            details=f"ایجاد تراکنش #{transaction_id}", timestamp=old_created,
        ),
        models.ActivityLog(
            admin_username="audit-admin", action="transaction_delete", target_id=transaction_id,
            details=f"حذف تراکنش #{transaction_id}", timestamp=old_deleted,
        ),
    ])
    db.commit()
    try:
        before = _database_snapshot(db)
        alerts = _alerts_from(client.get("/audit/suspicious_patterns", headers=auth_headers["admin"]))
        assert not any(row["type"] == "rapid_deletion" and row["entity_id"] == transaction_id for row in alerts)
        db.expire_all()
        assert _database_snapshot(db) == before
    finally:
        _cleanup_transaction_probe(db, transaction_id)


def test_audit_pattern_c_uses_ten_latest_sessions_and_detects_new_absence(client, auth_headers, db):
    import models

    older_absence = models.SessionLog(
        session_code=87_999, course_id=1, date="1405/04/30", time="16:00",
        start_time="16:00", status="Finished", is_deleted=False,
    )
    db.add(older_absence)
    db.flush()
    sessions = [
        models.SessionLog(
            session_code=88_000 + index, course_id=1, date=f"1405/05/{index:02d}",
            time="16:00", start_time="16:00", status="Finished", is_deleted=False,
        )
        for index in range(1, 11)
    ]
    db.add_all(sessions)
    db.flush()
    session_ids = [older_absence.id, *(row.id for row in sessions)]
    db.add_all([
        models.Attendance(
            session_id=older_absence.id, student_id=1, status="Absent", is_deleted=False,
            is_billed=False, excused=False,
        ),
        *[
            models.Attendance(
                session_id=row.id, student_id=1, status="Present", is_deleted=False,
                is_billed=False, excused=False,
            )
            for row in sessions
        ],
    ])
    db.commit()
    try:
        before = _database_snapshot(db)
        alerts = _alerts_from(client.get("/audit/suspicious_patterns", headers=auth_headers["admin"]))
        perfect = [row for row in alerts if row["type"] == "perfect_attendance" and row["entity_id"] == 1]
        assert len(perfect) == 1
        assert "۱۰ جلسه اخیر" in perfect[0]["description"]
        assert "10 رکورد حضور" in perfect[0]["description"]
        db.expire_all()
        assert _database_snapshot(db) == before

        db.query(models.Attendance).filter(models.Attendance.session_id == sessions[0].id).one().status = "Absent"
        db.commit()
        before_absence_probe = _database_snapshot(db)
        after_absence = _alerts_from(client.get("/audit/suspicious_patterns", headers=auth_headers["admin"]))
        assert not any(row["type"] == "perfect_attendance" and row["entity_id"] == 1 for row in after_absence)
        db.expire_all()
        assert _database_snapshot(db) == before_absence_probe
    finally:
        db.query(models.Attendance).filter(models.Attendance.session_id.in_(session_ids)).delete(synchronize_session=False)
        db.query(models.SessionLog).filter(models.SessionLog.id.in_(session_ids)).delete(synchronize_session=False)
        db.commit()
