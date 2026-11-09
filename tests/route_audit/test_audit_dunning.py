"""Temporary-database audit for dunning drafts, local send logs, and DTOs."""
from __future__ import annotations

import datetime

from sqlalchemy import and_, delete, insert, select, update

from .clock import FIXED_NOW
from .kotlin_contract import audit_payload, discover_models
from .route_registry import route_id, routes

ROUTE_IDS = [
    "GET /dunning/drafts",
    "POST /dunning/send_batch",
]


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


def _assert_unchanged_except(before, after, *changed_tables):
    assert set(before) == set(after)
    allowed = set(changed_tables)
    for table_name in before:
        if table_name not in allowed:
            assert after[table_name] == before[table_name], table_name


def _restore_tables(db, before, *model_names):
    """Restore selected tables so each probe leaves its temporary DB pristine."""
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
                non_primary_values = {
                    name: value for name, value in values.items()
                    if name not in {column.name for column in primary_keys}
                }
                db.execute(update(table).where(predicate).values(**non_primary_values))
            else:
                db.execute(insert(table).values(**values))
        db.flush()
    db.commit()
    db.expire_all()
    assert _database_snapshot(db) == before


def _project_date(delta_days):
    from today_summary import jalali_date_string

    return jalali_date_string(FIXED_NOW.date() + datetime.timedelta(days=delta_days))


def _make_installment(models, *, enrollment_id, due_delta, amount, paid=False, deleted=False):
    return models.Installment(
        enrollment_id=enrollment_id,
        amount=amount,
        due_date=_project_date(due_delta),
        is_paid=paid,
        paid_at=None,
        paid_amount=0,
        is_deleted=deleted,
    )


def test_dunning_route_inventory_is_explicit(client):
    actual = {route_id(row) for row in routes() if row["handler"].split(".")[1] == "dunning"}
    assert set(ROUTE_IDS) == actual
    openapi_routes = {
        (method.upper(), path)
        for path, methods in client.app.openapi()["paths"].items()
        for method in methods
    }
    assert all(tuple(route.split(" ", 1)) in openapi_routes for route in ROUTE_IDS)


def test_dunning_drafts_bucket_boundaries_sort_filter_and_idempotency_are_read_only(
    client, auth_headers, db,
):
    import models

    before = _database_snapshot(db)
    kotlin_models = discover_models()
    try:
        # Make a compact deterministic fixture containing every bucket boundary
        # and decoys for paid/deleted installment, deleted enrollment/student, and no mobile.
        db.query(models.Installment).update({"is_deleted": True}, synchronize_session=False)
        student_without_mobile = db.get(models.Student, 4)
        old_mobile = student_without_mobile.parent_mobile
        student_without_mobile.parent_mobile = "   "
        rows = [
            _make_installment(models, enrollment_id=1, due_delta=1, amount=101_001),
            _make_installment(models, enrollment_id=1, due_delta=3, amount=103_003),
            _make_installment(models, enrollment_id=1, due_delta=0, amount=100_000),
            _make_installment(models, enrollment_id=1, due_delta=4, amount=104_000),
            _make_installment(models, enrollment_id=1, due_delta=-1, amount=99_001),
            _make_installment(models, enrollment_id=1, due_delta=-7, amount=93_007),
            _make_installment(models, enrollment_id=1, due_delta=-8, amount=92_008),
            # Enrollment 3 belongs to a suspended (but not deleted) student.
            _make_installment(models, enrollment_id=3, due_delta=-2, amount=85_002),
            _make_installment(models, enrollment_id=1, due_delta=-1, amount=50_000, paid=True),
            _make_installment(models, enrollment_id=1, due_delta=-1, amount=60_000, deleted=True),
            _make_installment(models, enrollment_id=6, due_delta=-1, amount=70_000),
            _make_installment(models, enrollment_id=4, due_delta=-1, amount=80_000),
            _make_installment(models, enrollment_id=5, due_delta=-1, amount=90_000),
        ]
        db.add_all(rows)
        db.commit()
        db.expire_all()
        student_without_mobile.parent_mobile = "   "
        db.commit()
        before_reads = _database_snapshot(db)
        ids = {row.amount: row.id for row in db.query(models.Installment).all() if row.amount >= 50_000}
        due = {delta: _project_date(delta) for delta in (1, 3, -1, -2, -7, -8)}

        first = client.get("/dunning/drafts", headers=auth_headers["admin"])
        assert first.status_code == 200, first.text
        drafts = first.json()
        assert [row["installment_id"] for row in drafts] == [
            ids[92_008], ids[93_007], ids[85_002], ids[99_001], ids[101_001], ids[103_003],
        ]
        assert [(row["category"], row["amount"], row["due_date"]) for row in drafts] == [
            ("critical", 92_008, due[-8]),
            ("overdue", 93_007, due[-7]),
            ("overdue", 85_002, due[-2]),
            ("overdue", 99_001, due[-1]),
            ("upcoming", 101_001, due[1]),
            ("upcoming", 103_003, due[3]),
        ]
        assert [(row["student_name"], row["parent_mobile"]) for row in drafts] == [
            ("دانش‌آموز تست 1", "09360000001"),
            ("دانش‌آموز تست 1", "09360000001"),
            ("دانش‌آموز تست 2", "09360000002"),
            ("دانش‌آموز تست 1", "09360000001"),
            ("دانش‌آموز تست 1", "09360000001"),
            ("دانش‌آموز تست 1", "09360000001"),
        ]
        expected_messages = {
            92_008: f"⚠️ هشدار: قسط شهریه فرزند شما دانش‌آموز تست 1 به مبلغ 92,008 تومان از تاریخ {due[-8]} (8 روز گذشته) پرداخت نشده است. جهت جلوگیری از محدودیت ثبت‌نام، سریعاً اقدام فرمایید. - آموزشگاه خوارزمی",
            93_007: f"سلام ولی محترم دانش‌آموز تست 1، قسط شهریه فرزند شما به مبلغ 93,007 تومان سررسید {due[-7]} (7 روز گذشته) معوق شده است. لطفاً در اسرع وقت پرداخت فرمایید. - خوارزمی",
            85_002: f"سلام ولی محترم دانش‌آموز تست 2، قسط شهریه فرزند شما به مبلغ 85,002 تومان سررسید {due[-2]} (2 روز گذشته) معوق شده است. لطفاً در اسرع وقت پرداخت فرمایید. - خوارزمی",
            99_001: f"سلام ولی محترم دانش‌آموز تست 1، قسط شهریه فرزند شما به مبلغ 99,001 تومان سررسید {due[-1]} (1 روز گذشته) معوق شده است. لطفاً در اسرع وقت پرداخت فرمایید. - خوارزمی",
            101_001: f"سلام ولی محترم دانش‌آموز تست 1، یادآوری: قسط شهریه فرزند شما به مبلغ 101,001 تومان سررسید {due[1]} (تا 1 روز آینده) می‌باشد. لطفاً نسبت به پرداخت اقدام فرمایید. با تشکر - آموزشگاه خوارزمی",
            103_003: f"سلام ولی محترم دانش‌آموز تست 1، یادآوری: قسط شهریه فرزند شما به مبلغ 103,003 تومان سررسید {due[3]} (تا 3 روز آینده) می‌باشد. لطفاً نسبت به پرداخت اقدام فرمایید. با تشکر - آموزشگاه خوارزمی",
        }
        assert [row["suggested_message"] for row in drafts] == [expected_messages[row["amount"]] for row in drafts]
        assert all(audit_payload("DunningDraft", row, kotlin_models) == [] for row in drafts)
        assert _database_snapshot(db) == before_reads

        # A recent ActivityLog and a recent local SmsLog independently suppress drafts.
        db.add(models.ActivityLog(
            admin_username="audit-admin", action="dunning_reminder", target_id=ids[101_001],
            target_name="student", details="recent activity", timestamp=FIXED_NOW - datetime.timedelta(hours=47),
        ))
        db.add(models.SmsLog(
            target_group=f"dunning_{ids[103_003]}", message_text="recent SMS",
            sent_count=1, date=f"{_project_date(0)} 08:00",
        ))
        # Precise 49-hour-old log rows must not suppress candidates under the
        # route's stated 48-hour window.
        db.add(models.ActivityLog(
            admin_username="audit-admin", action="dunning_reminder", target_id=ids[99_001],
            target_name="student", details="outside the window", timestamp=FIXED_NOW - datetime.timedelta(hours=49),
        ))
        db.add(models.SmsLog(
            target_group=f"dunning_{ids[93_007]}", message_text="outside the window",
            sent_count=1, date=f"{_project_date(-2)} 08:00",
        ))
        db.commit()
        before_suppressed_read = _database_snapshot(db)
        suppressed = client.get("/dunning/drafts", headers=auth_headers["admin"])
        assert suppressed.status_code == 200
        assert [row["installment_id"] for row in suppressed.json()] == [
            ids[92_008], ids[93_007], ids[85_002], ids[99_001],
        ]
        assert _database_snapshot(db) == before_suppressed_read
    finally:
        # Keep the selected student's original contact data in the exact baseline image.
        _restore_tables(
            db, before, "Installment", "ActivityLog", "SmsLog", "Student", "FinancialAuditLog",
        )


def test_dunning_send_batch_deduplicates_logs_local_rows_and_retry_exactly(
    client, auth_headers, db,
):
    import models

    before = _database_snapshot(db)
    kotlin_models = discover_models()
    try:
        db.query(models.Installment).filter(models.Installment.id == 1).update(
            {"due_date": _project_date(-8)}, synchronize_session=False,
        )
        db.query(models.Installment).filter(models.Installment.id == 2).update(
            {"due_date": _project_date(-1)}, synchronize_session=False,
        )
        missing_enrollment = _make_installment(models, enrollment_id=6, due_delta=-1, amount=70_000)
        no_mobile = _make_installment(models, enrollment_id=5, due_delta=-1, amount=80_000)
        db.add_all([missing_enrollment, no_mobile])
        db.flush()
        student_without_mobile = db.get(models.Student, 4)
        student_without_mobile.parent_mobile = "   "
        db.add(models.ActivityLog(
            admin_username="audit-admin", action="dunning_reminder", target_id=2,
            target_name="student", details="already reminded", timestamp=FIXED_NOW - datetime.timedelta(hours=1),
        ))
        db.commit()
        db.expire_all()
        before_send = _database_snapshot(db)

        request = {"installment_ids": [1, 1, 2, 3, 4, 999999, missing_enrollment.id, no_mobile.id]}
        assert audit_payload("DunningSendRequest", request, kotlin_models) == []
        response = client.post("/dunning/send_batch", json=request, headers=auth_headers["admin"])
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload == {
            "sent_count": 1,
            "skipped_count": 6,
            "sent_ids": [1],
            "skipped_ids": [2, 3, 4, 999999, missing_enrollment.id, no_mobile.id],
            "skipped_reasons": {
                "2": "۴۸ ساعت گذشته یادآوری شده",
                "3": "پرداخت شده",
                "4": "یافت نشد",
                "999999": "یافت نشد",
                str(missing_enrollment.id): "ثبت‌نام حذف شده",
                str(no_mobile.id): "موبایل ولی یافت نشد",
            },
            "message": "1 پیام ارسال شد، 6 مورد رد شد (تکراری یا نامعتبر)",
        }
        assert audit_payload("DunningSendResponse", payload, kotlin_models) == []

        jalali_today = _project_date(0)
        expected_message = f"⚠️ هشدار: قسط شهریه فرزند شما دانش‌آموز تست 1 به مبلغ 350,000 تومان از تاریخ {_project_date(-8)} (8 روز گذشته) پرداخت نشده است. جهت جلوگیری از محدودیت ثبت‌نام، سریعاً اقدام فرمایید. - آموزشگاه خوارزمی"
        db.expire_all()
        sms_rows = [row for row in db.query(models.SmsLog).all() if row.id not in {row[0] for row in before_send["sms_logs"]}]
        activity_rows = [row for row in db.query(models.ActivityLog).all() if row.id not in {row[0] for row in before_send["activity_logs"]}]
        assert len(sms_rows) == len(activity_rows) == 1
        sms = sms_rows[0]
        assert (sms.target_group, sms.message_text, sms.sent_count, sms.date) == (
            "dunning_1", expected_message, 1, f"{jalali_today} 09:00",
        )
        activity = activity_rows[0]
        assert (
            activity.admin_username, activity.action, activity.target_id, activity.target_name,
            activity.details, activity.timestamp,
        ) == ("audit-admin", "dunning_reminder", 1, "دانش‌آموز تست 1", expected_message, FIXED_NOW)
        after_first = _database_snapshot(db)
        _assert_unchanged_except(before_send, after_first, "sms_logs", "activity_logs")

        retry = client.post("/dunning/send_batch", json=request, headers=auth_headers["admin"])
        assert retry.status_code == 200, retry.text
        retry_payload = retry.json()
        assert retry_payload == {
            "sent_count": 0,
            "skipped_count": 7,
            "sent_ids": [],
            "skipped_ids": [1, 2, 3, 4, 999999, missing_enrollment.id, no_mobile.id],
            "skipped_reasons": {
                "1": "۴۸ ساعت گذشته یادآوری شده",
                "2": "۴۸ ساعت گذشته یادآوری شده",
                "3": "پرداخت شده",
                "4": "یافت نشد",
                "999999": "یافت نشد",
                str(missing_enrollment.id): "ثبت‌نام حذف شده",
                str(no_mobile.id): "موبایل ولی یافت نشد",
            },
            "message": "0 پیام ارسال شد، 7 مورد رد شد (تکراری یا نامعتبر)",
        }
        assert audit_payload("DunningSendResponse", retry_payload, kotlin_models) == []
        assert _database_snapshot(db) == after_first
    finally:
        _restore_tables(
            db, before, "Installment", "ActivityLog", "SmsLog", "Student", "FinancialAuditLog",
        )


def test_dunning_send_batch_empty_or_missing_ids_is_no_write(client, auth_headers, db):
    before = _database_snapshot(db)
    empty = client.post(
        "/dunning/send_batch", json={"installment_ids": []}, headers=auth_headers["admin"],
    )
    assert empty.status_code == 400
    assert empty.json() == {"detail": "لیست اقساط خالی است"}
    assert _database_snapshot(db) == before

    missing = client.post("/dunning/send_batch", json={}, headers=auth_headers["admin"])
    assert missing.status_code == 422, missing.text
    assert _database_snapshot(db) == before


def test_dunning_routes_reject_non_admin_without_writes(client, auth_headers, db):
    before = _database_snapshot(db)
    drafts = client.get("/dunning/drafts", headers=auth_headers["teacher"])
    assert drafts.status_code == 403
    batch = client.post(
        "/dunning/send_batch", json={"installment_ids": [1]}, headers=auth_headers["teacher"],
    )
    assert batch.status_code == 403
    assert _database_snapshot(db) == before


def test_dunning_send_batch_deleted_and_suspended_student_behavior_is_unresolved(
    client, auth_headers, db,
):
    """Record current direct-send behavior without treating it as settled policy."""
    import models

    before = _database_snapshot(db)
    try:
        deleted_student_installment = _make_installment(
            models, enrollment_id=4, due_delta=-8, amount=110_000,
        )
        suspended_student_installment = _make_installment(
            models, enrollment_id=3, due_delta=-8, amount=120_000,
        )
        db.add_all([deleted_student_installment, suspended_student_installment])
        db.commit()
        db.refresh(deleted_student_installment)
        db.refresh(suspended_student_installment)
        before_send = _database_snapshot(db)

        requested_ids = [deleted_student_installment.id, suspended_student_installment.id]
        response = client.post(
            "/dunning/send_batch",
            json={"installment_ids": requested_ids},
            headers=auth_headers["admin"],
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["sent_count"] == 2
        assert payload["sent_ids"] == requested_ids
        assert payload["skipped_count"] == 0

        after_send = _database_snapshot(db)
        _assert_unchanged_except(before_send, after_send, "sms_logs", "activity_logs")
        sms_rows = [
            row for row in db.query(models.SmsLog).all()
            if row.id not in {row[0] for row in before_send["sms_logs"]}
        ]
        activity_rows = [
            row for row in db.query(models.ActivityLog).all()
            if row.id not in {row[0] for row in before_send["activity_logs"]}
        ]
        assert len(sms_rows) == len(activity_rows) == 2
        assert [row.target_group for row in sms_rows] == [f"dunning_{iid}" for iid in requested_ids]
        assert [row.target_id for row in activity_rows] == requested_ids
    finally:
        _restore_tables(
            db, before, "Installment", "ActivityLog", "SmsLog", "FinancialAuditLog",
        )
