"""Temporary-database audit of the unified student timeline and Android DTO."""
from __future__ import annotations

import collections
import datetime

import pytest
from sqlalchemy import and_, delete, insert, select, update

from .clock import FIXED_NOW
from .kotlin_contract import audit_payload, discover_models
from .route_registry import route_id, routes

ROUTE_IDS = ["GET /students/{student_id}/timeline"]
TARGET_STUDENT_ID = 9  # Active student with no seeded timeline rows or identity token.


def _database_snapshot(db):
    import models

    result = {}
    for table in models.Base.metadata.sorted_tables:
        statement = select(table)
        primary_key = list(table.primary_key.columns)
        if primary_key:
            statement = statement.order_by(*primary_key)
        result[table.name] = [tuple(row) for row in db.execute(statement).all()]
    return result


def _restore_tables(db, before, *model_names):
    """Restore rows inserted by a probe; core DELETE avoids ORM audit callbacks."""
    import models

    db.rollback()
    db.expire_all()
    for model_name in model_names:
        table = getattr(models, model_name).__table__
        columns = list(table.columns)
        column_names = [column.name for column in columns]
        primary_keys = list(table.primary_key.columns)
        key_indexes = [column_names.index(column.name) for column in primary_keys]
        baseline_rows = before[table.name]
        baseline = {tuple(row[index] for index in key_indexes): row for row in baseline_rows}
        current_rows = [tuple(row) for row in db.execute(select(table)).all()]
        current = {tuple(row[index] for index in key_indexes): row for row in current_rows}

        for key in current.keys() - baseline.keys():
            predicate = and_(*(column == value for column, value in zip(primary_keys, key)))
            db.execute(delete(table).where(predicate))

        for key, row in baseline.items():
            predicate = and_(*(column == value for column, value in zip(primary_keys, key)))
            values = dict(zip(column_names, row))
            if key in current:
                primary_names = {column.name for column in primary_keys}
                db.execute(
                    update(table).where(predicate).values(
                        **{name: value for name, value in values.items() if name not in primary_names}
                    )
                )
            else:
                db.execute(insert(table).values(**values))
        db.flush()
    db.commit()
    db.expire_all()
    assert _database_snapshot(db) == before


def _timeline_rows_for_cleanup():
    # FinancialAuditLog is restored because inserting test transactions triggers
    # the application's mapper listeners. All deletions below use Core statements.
    return (
        "Installment", "Attendance", "Grade", "Transaction", "FinancialAuditLog",
        "SessionLog", "Enrollment",
    )


def _iso_day(start: datetime.date, offset: int) -> str:
    return (start + datetime.timedelta(days=offset)).isoformat()


def _new_enrollment(models, *, student_id=TARGET_STUDENT_ID, deleted=False):
    return models.Enrollment(
        student_id=student_id, course_id=1, branch_id=1,
        register_date="1405/07/06", shift="عصر", total_tuition=1_000_000,
        total_paid=0, discount_type="none", discount_value=0, is_deleted=deleted,
    )


def _transaction(models, *, date, amount=100_000, description=None,
                 payment_method="کارت", target_wallet=None, deleted=False, reversed=False):
    return models.Transaction(
        student_id=TARGET_STUDENT_ID, course_id=1, enrollment_id=None,
        amount=amount, payment_method=payment_method, tracking_code=None,
        date=date, receiver="آموزشگاه", description=description, type="deposit",
        target_wallet=target_wallet, is_deleted=deleted, is_reversed=reversed,
    )


def test_timeline_route_inventory_is_explicit(client):
    actual = {
        route_id(row)
        for row in routes()
        if row["handler"].split(".")[1] == "timeline"
    }
    assert set(ROUTE_IDS) == actual
    openapi_routes = {
        (method.upper(), path)
        for path, methods in client.app.openapi()["paths"].items()
        for method in methods
    }
    assert all(tuple(route.split(" ", 1)) in openapi_routes for route in ROUTE_IDS)


def test_timeline_empty_and_all_event_values_are_ordered_read_only_and_gson_compatible(
    client, auth_headers, db,
):
    import models

    before = _database_snapshot(db)
    kotlin_models = discover_models()
    fixed_today = FIXED_NOW.date().isoformat()
    fixed_yesterday = _iso_day(FIXED_NOW.date(), -1)
    fixed_paid_date = _iso_day(FIXED_NOW.date(), -11)
    empty = client.get(
        f"/students/{TARGET_STUDENT_ID}/timeline", headers=auth_headers["admin"],
    )
    assert empty.status_code == 200
    assert empty.json() == []
    assert _database_snapshot(db) == before

    try:
        enrollment = _new_enrollment(models)
        deleted_enrollment = _new_enrollment(models, deleted=True)
        db.add_all([enrollment, deleted_enrollment])
        db.flush()

        live_session = models.SessionLog(
            course_id=1, date="2026-09-15", time="09:10", start_time="09:00",
            session_code=91001, status="Finished", is_deleted=False,
        )
        deleted_session = models.SessionLog(
            course_id=1, date="2026-09-16", time=None, start_time="11:30",
            session_code=91002, status="Cancelled", is_deleted=True,
        )
        soft_deleted_attendance_session = models.SessionLog(
            course_id=1, date="2026-09-18", time="12:15", start_time="12:00",
            session_code=91003, status="Finished", is_deleted=False,
        )
        present_session = models.SessionLog(
            course_id=1, date="2026-09-30", time="10:00", start_time="10:00",
            session_code=91004, status="Finished", is_deleted=False,
        )
        db.add_all([live_session, deleted_session, soft_deleted_attendance_session, present_session])
        db.flush()

        long_transaction_description = "توضیح" + "x" * 61
        long_grade_description = "شرح" + "y" * 60
        db.add_all([
            _transaction(
                models, date="۱۴۰۵/۰۶/۲۲ ۱۰:۴۵", amount=1_234_567,
                description=long_transaction_description, target_wallet="both",
            ),
            _transaction(
                models, date="2026-09-14", amount=250_000,
                description=None, payment_method="کارت",
            ),
            _transaction(models, date="2026-09-29", amount=999_000, deleted=True),
            _transaction(models, date="2026-09-30", amount=888_000, reversed=True),
            models.Attendance(
                session_id=live_session.id, student_id=TARGET_STUDENT_ID,
                status="Absent", is_deleted=False, is_billed=False, excused=True,
            ),
            # Current code includes both an attendance soft-delete and a deleted session.
            models.Attendance(
                session_id=soft_deleted_attendance_session.id, student_id=TARGET_STUDENT_ID,
                status="Absent", is_deleted=True, is_billed=False, excused=False,
            ),
            models.Attendance(
                session_id=deleted_session.id, student_id=TARGET_STUDENT_ID,
                status="Absent", is_deleted=False, is_billed=False, excused=False,
            ),
            models.Attendance(
                session_id=present_session.id, student_id=TARGET_STUDENT_ID,
                status="Present", is_deleted=False, is_billed=True, excused=False,
            ),
            models.Grade(
                student_id=TARGET_STUDENT_ID, course_id=1, teacher_id=1,
                exam_title="پایان‌ترم", score=9.0, max_score=20.0,
                date="2026-09-21", description=None,
            ),
            models.Grade(
                student_id=TARGET_STUDENT_ID, course_id=1, teacher_id=1,
                exam_title=None, score=14.0, max_score=20.0,
                date="2026-09-20", description=None,
            ),
            models.Grade(
                student_id=TARGET_STUDENT_ID, course_id=1, teacher_id=1,
                exam_title="میان‌ترم", score=18.5, max_score=20.0,
                date="2026-09-19", description=long_grade_description,
            ),
            models.Installment(
                enrollment_id=enrollment.id, amount=700_000, due_date=fixed_yesterday,
                is_paid=False, paid_at=None, paid_amount=0, is_deleted=False,
            ),
            models.Installment(
                enrollment_id=enrollment.id, amount=250_000, due_date=fixed_today,
                is_paid=False, paid_at=None, paid_amount=0, is_deleted=False,
            ),
            models.Installment(
                enrollment_id=enrollment.id, amount=100_000, due_date=fixed_paid_date,
                is_paid=True, paid_at=fixed_paid_date, paid_amount=100_000, is_deleted=False,
            ),
            models.Installment(
                enrollment_id=enrollment.id, amount=500_000, due_date="2026-09-05",
                is_paid=False, paid_at=None, paid_amount=0, is_deleted=True,
            ),
            models.Installment(
                enrollment_id=deleted_enrollment.id, amount=600_000, due_date="2026-09-29",
                is_paid=False, paid_at=None, paid_amount=0, is_deleted=False,
            ),
        ])
        db.commit()
        db.expire_all()
        fixture_state = _database_snapshot(db)

        response = client.get(
            f"/students/{TARGET_STUDENT_ID}/timeline", headers=auth_headers["admin"],
        )
        assert response.status_code == 200
        expected = [
            {
                "timestamp": fixed_today, "type": "installment",
                "title": f"قسط 250,000 تومان — سررسید {fixed_today}",
                "subtitle": f"کلاس: ریاضی پایه فعال — سررسید: {fixed_today}",
                "icon_name": "ic_installment", "color_hex": "#FF9800",
            },
            {
                "timestamp": fixed_yesterday, "type": "installment",
                "title": "قسط معوق 700,000 تومان",
                "subtitle": f"کلاس: ریاضی پایه فعال — سررسید: {fixed_yesterday}",
                "icon_name": "ic_overdue", "color_hex": "#F44336",
            },
            {
                "timestamp": "2026-09-21", "type": "grade",
                "title": "نمره 9 از 20 — پایان‌ترم",
                "subtitle": "کلاس: ریاضی پایه فعال",
                "icon_name": "ic_grade", "color_hex": "#F44336",
            },
            {
                "timestamp": "2026-09-20", "type": "grade",
                "title": "نمره 14 از 20",
                "subtitle": "کلاس: ریاضی پایه فعال",
                "icon_name": "ic_grade", "color_hex": "#FF9800",
            },
            {
                "timestamp": "2026-09-19", "type": "grade",
                "title": "نمره 18.5 از 20 — میان‌ترم",
                "subtitle": f"کلاس: ریاضی پایه فعال — {long_grade_description[:50]}",
                "icon_name": "ic_grade", "color_hex": "#4CAF50",
            },
            {
                "timestamp": "2026-09-18 12:15", "type": "absence",
                "title": "غیبت در جلسه",
                "subtitle": "کلاس: ریاضی پایه فعال — تاریخ: 2026-09-18 (کد: 91003)",
                "icon_name": "ic_absent", "color_hex": "#F44336",
            },
            {
                "timestamp": fixed_paid_date, "type": "installment",
                "title": "قسط پرداخت شده 100,000 تومان",
                "subtitle": f"کلاس: ریاضی پایه فعال — سررسید: {fixed_paid_date} — پرداخت: {fixed_paid_date}",
                "icon_name": "ic_paid", "color_hex": "#4CAF50",
            },
            {
                "timestamp": "2026-09-16 11:30", "type": "absence",
                "title": "غیبت در جلسه",
                "subtitle": "کلاس: ریاضی پایه فعال — تاریخ: 2026-09-16 (کد: 91002)",
                "icon_name": "ic_absent", "color_hex": "#F44336",
            },
            {
                "timestamp": "2026-09-15 09:10", "type": "absence",
                "title": "غیبت موجه",
                "subtitle": "کلاس: ریاضی پایه فعال — تاریخ: 2026-09-15 (کد: 91001)",
                "icon_name": "ic_absent", "color_hex": "#F44336",
            },
            {
                "timestamp": "2026-09-14", "type": "payment",
                "title": "پرداخت 250,000 تومان",
                "subtitle": "کلاس: ریاضی پایه فعال — روش: کارت",
                "icon_name": "ic_payment", "color_hex": "#4CAF50",
            },
            {
                "timestamp": "2026-09-13 10:45", "type": "payment",
                "title": "پرداخت 1,234,567 تومان",
                "subtitle": f"کلاس: ریاضی پایه فعال — {long_transaction_description[:60]} (both)",
                "icon_name": "ic_payment", "color_hex": "#4CAF50",
            },
        ]
        actual = response.json()
        assert actual == expected
        assert all(audit_payload("TimelineEvent", event, kotlin_models) == [] for event in actual)

        malformed = dict(actual[0])
        malformed.pop("icon_name")
        issues = audit_payload("TimelineEvent", malformed, kotlin_models)
        assert [(issue.field, issue.kind) for issue in issues] == [("iconName", "missing-non-null")]

        # Same read is stable and does not append audit/financial rows.
        retry = client.get(
            f"/students/{TARGET_STUDENT_ID}/timeline", headers=auth_headers["admin"],
        )
        assert retry.status_code == 200
        assert retry.json() == expected
        assert _database_snapshot(db) == fixture_state
    finally:
        _restore_tables(db, before, *_timeline_rows_for_cleanup())


def test_timeline_role_scope_missing_deleted_and_suspended_students_are_observed_read_only(
    client, auth_headers, db,
):
    before = _database_snapshot(db)
    try:
        role_responses = {}
        for role in ("admin", "secretary", "teacher", "parent", "student"):
            response = client.get("/students/1/timeline", headers=auth_headers[role])
            assert response.status_code == 200, role
            assert isinstance(response.json(), list), role
            role_responses[role] = response.json()
        seeded_student_timeline = [
            {
                "timestamp": "2026-09-23", "type": "installment",
                "title": "قسط معوق 350,000 تومان",
                "subtitle": "کلاس: ریاضی پایه فعال — سررسید: 1405/07/01",
                "icon_name": "ic_overdue", "color_hex": "#F44336",
            },
            {
                "timestamp": "2026-09-11", "type": "installment",
                "title": "قسط پرداخت شده 500,000 تومان",
                "subtitle": "کلاس: فیزیک دوکلاسه — سررسید: 1405/06/20 — پرداخت: 1405/06/20",
                "icon_name": "ic_paid", "color_hex": "#4CAF50",
            },
            {
                "timestamp": "2026-09-06", "type": "grade",
                "title": "نمره 18.5 از 20 — میان‌ترم",
                "subtitle": "کلاس: ریاضی پایه فعال — خوب",
                "icon_name": "ic_grade", "color_hex": "#4CAF50",
            },
            {
                "timestamp": "2026-08-26", "type": "payment",
                "title": "پرداخت 500,000 تومان",
                "subtitle": "کلاس: فیزیک دوکلاسه — پرداخت split (both)",
                "icon_name": "ic_payment", "color_hex": "#4CAF50",
            },
            {
                "timestamp": "2026-08-25", "type": "payment",
                "title": "پرداخت 300,000 تومان",
                "subtitle": "کلاس: ریاضی پایه فعال — پرداخت enrollment اول (institute)",
                "icon_name": "ic_payment", "color_hex": "#4CAF50",
            },
            {
                "timestamp": "2026-08-23", "type": "installment",
                "title": "قسط معوق 350,000 تومان",
                "subtitle": "کلاس: ریاضی پایه فعال — سررسید: 1405/06/01",
                "icon_name": "ic_overdue", "color_hex": "#F44336",
            },
        ]
        assert all(value == seeded_student_timeline for value in role_responses.values())
        assert all(
            audit_payload("TimelineEvent", event, discover_models()) == []
            for event in seeded_student_timeline
        )

        # Teacher/parent/student scope checks happen before timeline queries.
        teacher_denied = client.get("/students/9/timeline", headers=auth_headers["teacher"])
        assert teacher_denied.status_code == 403
        assert teacher_denied.json() == {"detail": "شما مجاز به دسترسی به این دانش‌آموز نیستید"}
        parent_denied = client.get("/students/2/timeline", headers=auth_headers["parent"])
        assert parent_denied.status_code == 403
        assert parent_denied.json() == {"detail": "شما مجاز به دسترسی به این فرزند نیستید"}
        student_denied = client.get("/students/2/timeline", headers=auth_headers["student"])
        assert student_denied.status_code == 403
        assert student_denied.json() == {"detail": "شما مجاز به دسترسی به دانش‌آموز دیگری نیستید"}

        unauthorized = client.get("/students/1/timeline")
        assert unauthorized.status_code == 401
        assert unauthorized.json() == {"detail": "توکن احراز هویت یافت نشد. لطفاً مجدداً وارد شوید"}

        # Student 2 is suspended but not deleted. Current code still returns history to staff.
        suspended = client.get("/students/2/timeline", headers=auth_headers["admin"])
        assert suspended.status_code == 200
        assert suspended.json() == [{
            "timestamp": "2026-09-06", "type": "grade",
            "title": "نمره 12.5 از 20 — ریاضی",
            "subtitle": "کلاس: ریاضی پایه فعال",
            "icon_name": "ic_grade", "color_hex": "#FF9800",
        }]

        deleted = client.get("/students/3/timeline", headers=auth_headers["admin"])
        assert deleted.status_code == 404
        assert deleted.json() == {"detail": "دانش‌آموز یافت نشد"}
        missing = client.get("/students/999/timeline", headers=auth_headers["admin"])
        assert missing.status_code == 404
        assert missing.json() == {"detail": "دانش‌آموز یافت نشد"}
        invalid = client.get("/students/not-an-integer/timeline", headers=auth_headers["admin"])
        assert invalid.status_code == 422
        assert invalid.json()["detail"][0]["loc"] == ["path", "student_id"]
        assert _database_snapshot(db) == before
    finally:
        assert _database_snapshot(db) == before


def test_timeline_per_source_limit_filters_transactions_and_orders_latest_twenty(
    client, auth_headers, db,
):
    import models

    before = _database_snapshot(db)
    first_day = datetime.date(2026, 8, 1)
    try:
        db.add_all([
            _transaction(
                models,
                # ID 0 gets the newest timestamp but is evicted by the source's
                # descending-ID limit before the cross-type chronological merge.
                date=_iso_day(first_day, 21 if index == 0 else index - 1),
                amount=1_000 + index, description=None, payment_method="کارت",
            )
            for index in range(21)
        ])
        # These newest IDs are filtered before the source query's 20-row limit.
        db.add_all([
            _transaction(models, date="2027-01-01", amount=9_000_000, deleted=True),
            _transaction(models, date="2027-01-02", amount=8_000_000, reversed=True),
        ])
        db.commit()
        db.expire_all()
        fixture_state = _database_snapshot(db)

        response = client.get(
            f"/students/{TARGET_STUDENT_ID}/timeline", headers=auth_headers["admin"],
        )
        assert response.status_code == 200
        expected = [
            {
                "timestamp": _iso_day(first_day, index - 1), "type": "payment",
                "title": f"پرداخت {1_000 + index:,} تومان",
                "subtitle": "کلاس: ریاضی پایه فعال — روش: کارت",
                "icon_name": "ic_payment", "color_hex": "#4CAF50",
            }
            for index in range(20, 0, -1)
        ]
        assert response.json() == expected
        assert len(response.json()) == 20
        assert all(event["title"] != "پرداخت 1,021 تومان" for event in response.json())
        assert _database_snapshot(db) == fixture_state
    finally:
        _restore_tables(db, before, *_timeline_rows_for_cleanup())


@pytest.mark.parametrize("source", ["absence", "grade", "installment"])
def test_timeline_each_remaining_source_caps_at_twenty_and_orders_descending(
    source, client, auth_headers, db,
):
    import models

    before = _database_snapshot(db)
    first_day = datetime.date(2026, 8, 1)
    try:
        if source == "absence":
            sessions = [
                models.SessionLog(
                    course_id=1, date=_iso_day(first_day, index), time="12:00",
                    start_time="12:00", session_code=93000 + index,
                    status="Finished", is_deleted=False,
                )
                for index in range(21)
            ]
            db.add_all(sessions)
            db.flush()
            db.add_all([
                models.Attendance(
                    session_id=session.id, student_id=TARGET_STUDENT_ID,
                    status="Absent", is_deleted=False, is_billed=False, excused=False,
                )
                for session in sessions
            ])
        elif source == "grade":
            db.add_all([
                models.Grade(
                    student_id=TARGET_STUDENT_ID, course_id=1, teacher_id=1,
                    exam_title=None, score=15.0, max_score=20.0,
                    date=_iso_day(first_day, index), description=None,
                )
                for index in range(21)
            ])
        else:
            enrollment = _new_enrollment(models)
            db.add(enrollment)
            db.flush()
            db.add_all([
                models.Installment(
                    enrollment_id=enrollment.id, amount=1_000 + index,
                    due_date=_iso_day(first_day, index), is_paid=False,
                    paid_at=None, paid_amount=0, is_deleted=False,
                )
                for index in range(21)
            ])
        db.commit()
        db.expire_all()
        fixture_state = _database_snapshot(db)

        response = client.get(
            f"/students/{TARGET_STUDENT_ID}/timeline", headers=auth_headers["admin"],
        )
        assert response.status_code == 200
        actual = response.json()
        assert len(actual) == 20
        assert all(event["type"] == source for event in actual)
        expected_days = [_iso_day(first_day, index) for index in range(20, 0, -1)]
        if source == "absence":
            expected = [
                {
                    "timestamp": day + " 12:00", "type": "absence",
                    "title": "غیبت در جلسه",
                    "subtitle": f"کلاس: ریاضی پایه فعال — تاریخ: {day} (کد: {93000 + index})",
                    "icon_name": "ic_absent", "color_hex": "#F44336",
                }
                for index, day in zip(range(20, 0, -1), expected_days)
            ]
        elif source == "grade":
            expected = [
                {
                    "timestamp": day, "type": "grade",
                    "title": "نمره 15 از 20",
                    "subtitle": "کلاس: ریاضی پایه فعال",
                    "icon_name": "ic_grade", "color_hex": "#4CAF50",
                }
                for day in expected_days
            ]
        else:
            expected = [
                {
                    "timestamp": day, "type": "installment",
                    "title": f"قسط معوق {1_000 + index:,} تومان",
                    "subtitle": f"کلاس: ریاضی پایه فعال — سررسید: {day}",
                    "icon_name": "ic_overdue", "color_hex": "#F44336",
                }
                for index, day in zip(range(20, 0, -1), expected_days)
            ]
        assert actual == expected
        assert _database_snapshot(db) == fixture_state
    finally:
        _restore_tables(db, before, *_timeline_rows_for_cleanup())


def test_timeline_combined_feed_keeps_fifty_newest_after_per_type_limits(
    client, auth_headers, db,
):
    import models

    before = _database_snapshot(db)
    enrollment = None
    try:
        enrollment = _new_enrollment(models)
        db.add(enrollment)
        db.flush()
        db.add_all([
            *[
                _transaction(
                    models, date=_iso_day(datetime.date(2026, 1, 1), index),
                    amount=1_000 + index, description=f"transaction-{index}",
                )
                for index in range(21)
            ],
            *[
                models.SessionLog(
                    course_id=1, date=_iso_day(datetime.date(2026, 2, 1), index),
                    time="12:00", start_time="12:00", session_code=92000 + index,
                    status="Finished", is_deleted=False,
                )
                for index in range(21)
            ],
            *[
                models.Grade(
                    student_id=TARGET_STUDENT_ID, course_id=1, teacher_id=1,
                    exam_title=f"grade-{index}", score=15.0, max_score=20.0,
                    date=_iso_day(datetime.date(2026, 3, 1), index), description=None,
                )
                for index in range(21)
            ],
        ])
        db.flush()
        sessions = (
            db.query(models.SessionLog)
            .filter(models.SessionLog.session_code.between(92000, 92020))
            .order_by(models.SessionLog.id)
            .all()
        )
        db.add_all([
            models.Attendance(
                session_id=session.id, student_id=TARGET_STUDENT_ID,
                status="Absent", is_deleted=False, is_billed=False, excused=False,
            )
            for session in sessions
        ])
        db.add_all([
            models.Installment(
                enrollment_id=enrollment.id, amount=2_000 + index,
                due_date=_iso_day(datetime.date(2026, 4, 1), index),
                is_paid=False, paid_at=None, paid_amount=0, is_deleted=False,
            )
            for index in range(21)
        ])
        db.commit()
        db.expire_all()
        fixture_state = _database_snapshot(db)

        response = client.get(
            f"/students/{TARGET_STUDENT_ID}/timeline", headers=auth_headers["admin"],
        )
        assert response.status_code == 200
        actual = response.json()
        assert len(actual) == 50
        assert collections.Counter(event["type"] for event in actual) == {
            "installment": 20, "grade": 20, "absence": 10,
        }
        expected_order = [
            ("installment", _iso_day(datetime.date(2026, 4, 1), index))
            for index in range(20, 0, -1)
        ] + [
            ("grade", _iso_day(datetime.date(2026, 3, 1), index))
            for index in range(20, 0, -1)
        ] + [
            ("absence", _iso_day(datetime.date(2026, 2, 1), index) + " 12:00")
            for index in range(20, 10, -1)
        ]
        assert [(event["type"], event["timestamp"]) for event in actual] == expected_order
        assert all(audit_payload("TimelineEvent", event, discover_models()) == [] for event in actual)
        assert _database_snapshot(db) == fixture_state
    finally:
        _restore_tables(db, before, *_timeline_rows_for_cleanup())


def test_timeline_android_api_dto_and_display_contract_sources():
    from pathlib import Path

    repository = Path(__file__).resolve().parents[2]
    android = repository / "KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin"
    api = (android / "ApiInterfaces.kt").read_text(encoding="utf-8")
    models = (android / "AppModels.kt").read_text(encoding="utf-8")
    profile = (android / "StudentProfileActivity.kt").read_text(encoding="utf-8")
    adapter = (android / "TimelineAdapter.kt").read_text(encoding="utf-8")

    assert '@GET("students/{id}/timeline")' in api
    assert '@Path("id") id: Int): List<TimelineEvent>' in api
    assert "data class TimelineEvent(" in models
    for wire_name in ('@SerializedName("icon_name")', '@SerializedName("color_hex")'):
        assert wire_name in models
    assert "api.getTimeline(studentId)" in profile
    assert "timelineAdapter?.update(list)" in profile
    assert "if (list.isEmpty())" in profile
    assert "holder.tvTitle.text = ev.title" in adapter
    assert "holder.tvSubtitle.text = ev.subtitle" in adapter
    assert "holder.tvDate.text = ev.timestamp" in adapter
    assert "Color.parseColor(ev.colorHex)" in adapter
    for event_type in ("payment", "absence", "grade", "installment"):
        assert f'"{event_type}" ->' in adapter
