"""Value, persistence, state-transition, and Android-contract audit for CRM routes."""
from __future__ import annotations

from datetime import timedelta

import json

import pytest
from sqlalchemy import and_, delete, insert, select, update

from .clock import FIXED_NOW
from .route_registry import route_id, routes

CRM_ROUTE_IDS = [
    ("POST", "/crm/leads/create"),
    ("GET", "/crm/leads/list"),
    ("POST", "/crm/leads/{id}/convert"),
    ("POST", "/crm/leads/{id}/notes"),
    ("POST", "/crm/register_online"),
]
ROUTE_IDS = [f"{method} {path}" for method, path in CRM_ROUTE_IDS]


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


def _assert_android_contract(model_name, payload):
    from .kotlin_contract import audit_payload

    assert audit_payload(model_name, payload) == []


def _restore_tables(db, before, *model_names):
    """Restore selected tables to an exact pre-test image, including true SQL NULLs."""
    import models

    db.rollback()
    db.expire_all()
    for model_name in model_names:
        model = getattr(models, model_name)
        table = model.__table__
        columns = list(table.columns)
        column_names = [column.name for column in columns]
        primary_keys = list(table.primary_key.columns)
        key_indexes = [column_names.index(column.name) for column in primary_keys]
        baseline_rows = before[table.name]
        baseline = {
            tuple(row[index] for index in key_indexes): row
            for row in baseline_rows
        }
        current_rows = [tuple(row) for row in db.execute(select(table)).all()]
        current = {
            tuple(row[index] for index in key_indexes): row
            for row in current_rows
        }

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


def _lead_payload(**overrides):
    payload = {
        "name": "نرگس فرهادی",
        "mobile": "۰۹۱۲۹۹۹۸۸۸۸",
        "interested_course": "ریاضی دهم",
        "source": "Instagram",
        "notes": "تماس اولیه",
        "next_follow_up": "1405/07/10",
        "branch_id": 1,
    }
    payload.update(overrides)
    return payload


def _online_payload(**overrides):
    payload = {
        "first_name": "هستی",
        "last_name": "آزاده",
        "father_name": "علی",
        "national_code": "۰۰۰۱۱۱۲۲۲۸",
        "student_mobile": "۰۹۳۵۰۰۹۹۹۹۹",
        "parent_mobile": "٠٩٣٦٠٠٩٩٩٩٩",
        "course_id": 1,
        "paid_amount": 275_000,
        "payment_method": "کارتخوان",
    }
    payload.update(overrides)
    return payload


def test_crm_route_inventory_is_explicit(client):
    actual = {route_id(row) for row in routes() if row["handler"].split(".")[1] == "crm"}
    assert set(ROUTE_IDS) == actual
    openapi_routes = {
        (method.upper(), path)
        for path, methods in client.app.openapi()["paths"].items()
        for method in methods
    }
    assert all((method, path) in openapi_routes for method, path in CRM_ROUTE_IDS)


def test_crm_create_lead_returns_exact_android_values_and_only_inserts_lead(client, auth_headers, db):
    import models

    before = _database_snapshot(db)
    android_request = {
        "name": "نرگس فرهادی",
        "mobile": "۰۹۱۲۹۹۹۸۸۸۸",
        "interested_course": "ریاضی دهم",
        "branch_id": 1,
    }
    try:
        response = client.post(
            "/crm/leads/create", json=android_request, headers=auth_headers["secretary"],
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert set(payload) == {
            "id", "name", "mobile", "interested_course", "source", "status",
            "notes", "next_follow_up", "created_at",
        }
        assert payload == {
            "id": payload["id"],
            "name": "نرگس فرهادی",
            "mobile": "09129998888",
            "interested_course": "ریاضی دهم",
            "source": "Web",
            "status": "NEW",
            "notes": None,
            "next_follow_up": None,
            "created_at": FIXED_NOW.strftime("%Y/%m/%d"),
        }
        _assert_android_contract("LeadResponseModel", payload)

        db.expire_all()
        lead = db.get(models.Lead, payload["id"])
        assert lead is not None
        assert (lead.branch_id, lead.created_at) == (1, FIXED_NOW)
        after = _database_snapshot(db)
        _assert_unchanged_except(before, after, "crm_leads")
        assert len(after["crm_leads"]) == len(before["crm_leads"]) + 1
    finally:
        _restore_tables(db, before, "Lead")


def test_crm_create_lead_rejects_invalid_mobile_branch_and_inactive_branch_without_writes(
    client, auth_headers, db
):
    import models

    before = _database_snapshot(db)
    try:
        bad_mobile = client.post(
            "/crm/leads/create",
            json=_lead_payload(mobile="12345"),
            headers=auth_headers["secretary"],
        )
        assert bad_mobile.status_code == 400
        assert bad_mobile.json() == {"detail": "فرمت شماره موبایل صحیح نیست"}

        missing_branch = client.post(
            "/crm/leads/create",
            json=_lead_payload(branch_id=999),
            headers=auth_headers["admin"],
        )
        assert missing_branch.status_code == 400
        assert missing_branch.json() == {"detail": "شعبه انتخابی معتبر یا فعال نیست"}
        no_branch_payload = _lead_payload()
        no_branch_payload.pop("branch_id")
        no_branch = client.post(
            "/crm/leads/create", json=no_branch_payload, headers=auth_headers["admin"],
        )
        assert no_branch.status_code == 400
        assert no_branch.json() == {"detail": "شعبه مشخص نیست؛ لطفاً branch_id معتبر ارسال کنید"}

        branch = db.get(models.Branch, 2)
        old_active = branch.active
        branch.active = False
        db.commit()
        inactive_branch = client.post(
            "/crm/leads/create",
            json=_lead_payload(branch_id=2),
            headers=auth_headers["admin"],
        )
        assert inactive_branch.status_code == 400
        assert inactive_branch.json() == {"detail": "شعبه انتخابی معتبر یا فعال نیست"}
        db.expire_all()
        assert db.get(models.Branch, 2).active is False
        assert _database_snapshot(db) != before  # only the deliberate branch probe differs before cleanup
    finally:
        _restore_tables(db, before, "Lead", "Branch")


@pytest.mark.parametrize(
    "field,value",
    [
        (field, value)
        for field in ("name", "mobile", "interested_course", "notes")
        for value in ("", "   \t")
    ],
)
def test_crm_create_lead_rejects_empty_required_text_fields(client, auth_headers, db, field, value):
    before = _database_snapshot(db)
    try:
        response = client.post(
            "/crm/leads/create",
            json=_lead_payload(**{field: value}),
            headers=auth_headers["secretary"],
        )
        assert _database_snapshot(db) == before
        assert response.status_code in (400, 422), (field, response.status_code, response.text)
    finally:
        _restore_tables(db, before, "Lead")


def test_crm_lead_list_empty_is_an_empty_json_array_and_read_only(client, auth_headers, db):
    import models

    before = _database_snapshot(db)
    try:
        db.query(models.Lead).delete(synchronize_session=False)
        db.commit()
        empty_baseline = _database_snapshot(db)
        response = client.get("/crm/leads/list", headers=auth_headers["secretary"])
        assert response.status_code == 200, response.text
        assert response.json() == []
        assert _database_snapshot(db) == empty_baseline
    finally:
        _restore_tables(db, before, "Lead")


def test_crm_lead_list_is_complete_descending_null_safe_and_gson_compatible(client, auth_headers, db):
    import models

    before = _database_snapshot(db)
    count_to_insert = 205
    try:
        rows = [
            models.Lead(
                name=f"سرنخ {index}",
                mobile=f"0912000{index:04d}",
                interested_course="فیزیک",
                source="Referral",
                status="NEW",
                notes=None,
                next_follow_up=None,
                created_at=FIXED_NOW - timedelta(minutes=index),
                branch_id=1,
            )
            for index in range(count_to_insert)
        ]
        db.add_all(rows)
        db.commit()
        null_row = rows[0]
        db.execute(
            update(models.Lead)
            .where(models.Lead.id == null_row.id)
            .values(name=None, mobile=None, interested_course=None, source=None, status=None, created_at=None)
        )
        db.commit()
        inserted_ids = [row.id for row in rows]
        expected_ids = sorted([1, *inserted_ids], reverse=True)
        before_read = _database_snapshot(db)

        response = client.get("/crm/leads/list", headers=auth_headers["secretary"])
        assert response.status_code == 200, response.text
        values = response.json()
        assert len(values) == count_to_insert + 1  # no hidden truncation/limit
        assert [row["id"] for row in values] == expected_ids  # explicit ORDER BY id DESC
        assert all(
            set(row) == {
                "id", "name", "mobile", "interested_course", "source", "status",
                "notes", "next_follow_up", "created_at",
            }
            for row in values
        )
        legacy = next(row for row in values if row["id"] == null_row.id)
        assert legacy == {
            "id": null_row.id,
            "name": "",
            "mobile": "",
            "interested_course": "",
            "source": "Web",
            "status": "NEW",
            "notes": None,
            "next_follow_up": None,
            "created_at": "",
        }
        assert next(row for row in values if row["id"] == 1)["name"] == "سرنخ تست"
        _assert_android_contract("LeadResponseModel", legacy)
        _assert_android_contract("LeadResponseModel", values[0])
        assert _database_snapshot(db) == before_read
    finally:
        _restore_tables(db, before, "Lead")


def test_crm_add_notes_updates_contacted_followup_and_only_the_lead_row(client, auth_headers, db):
    import models

    before = _database_snapshot(db)
    try:
        response = client.post(
            "/crm/leads/1/notes",
            json={"notes": "تماس انجام شد؛ خانواده علاقه‌مند است", "next_follow_up": "1405/07/15", "status": "CONTACTED"},
            headers=auth_headers["secretary"],
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload == {"message": "یادداشت پیگیری با موفقیت ثبت شد"}
        _assert_android_contract("SimpleResponse", payload)

        db.expire_all()
        lead = db.get(models.Lead, 1)
        assert (lead.notes, lead.next_follow_up, lead.status) == (
            "تماس انجام شد؛ خانواده علاقه‌مند است", "1405/07/15", "CONTACTED",
        )
        assert lead.created_at == FIXED_NOW
        after = _database_snapshot(db)
        _assert_unchanged_except(before, after, "crm_leads")
        changed = {
            name for name, old, new in zip(
                models.Lead.__table__.columns.keys(), before["crm_leads"][0], after["crm_leads"][0]
            ) if old != new
        }
        assert changed == {"notes", "next_follow_up", "status"}
    finally:
        _restore_tables(db, before, "Lead")


def test_crm_add_notes_missing_lead_and_missing_body_field_have_controlled_4xx(client, auth_headers, db):
    before = _database_snapshot(db)
    missing = client.post(
        "/crm/leads/999999/notes",
        json={"notes": "یادداشت", "status": "CONTACTED"},
        headers=auth_headers["secretary"],
    )
    assert missing.status_code == 404
    assert missing.json() == {"detail": "سرنخ یافت نشد"}
    invalid = client.post(
        "/crm/leads/1/notes",
        json={"status": "CONTACTED"},
        headers=auth_headers["secretary"],
    )
    assert invalid.status_code == 422
    assert _database_snapshot(db) == before


@pytest.mark.parametrize("note", ["", "  \t  "], ids=["empty", "whitespace"])
def test_crm_add_notes_rejects_blank_required_note(client, auth_headers, db, note):
    before = _database_snapshot(db)
    try:
        response = client.post(
            "/crm/leads/1/notes",
            json={"notes": note, "next_follow_up": None, "status": "CONTACTED"},
            headers=auth_headers["secretary"],
        )
        assert _database_snapshot(db) == before
        assert response.status_code in (400, 422), (response.status_code, response.text)
    finally:
        _restore_tables(db, before, "Lead")


def test_crm_convert_without_course_creates_one_student_and_rejects_retry(client, auth_headers, db):
    import models

    before = _database_snapshot(db)
    lead = models.Lead(
        name="سرنخ تبدیل دقیق", mobile="۰۹۱۲۳۴۵۶۷۸۹", interested_course="شیمی",
        source="Referral", status="NEW", notes="پیگیری", branch_id=1, created_at=FIXED_NOW,
    )
    db.add(lead)
    db.commit()
    lead_id = lead.id
    before_convert = _database_snapshot(db)
    try:
        response = client.post(f"/crm/leads/{lead_id}/convert", headers=auth_headers["secretary"])
        assert response.status_code == 200, response.text
        payload = response.json()
        assert set(payload) == {"message", "student_id"}
        student_id = payload["student_id"]
        assert isinstance(student_id, int)
        _assert_android_contract("SimpleResponse", payload)

        db.expire_all()
        lead = db.get(models.Lead, lead_id)
        student = db.get(models.Student, student_id)
        assert payload["message"] == f"سرنخ با موفقیت به دانش‌آموز 'سرنخ تبدیل دقیق' با کد {student.student_code} تبدیل شد."
        assert (lead.status, lead.converted_student_id, lead.converted_at) == (
            "REGISTERED", student_id, FIXED_NOW,
        )
        assert (student.first_name, student.last_name, student.father_name) == ("سرنخ تبدیل دقیق", "", "")
        assert student.student_mobile == "09123456789"
        assert student.national_code.startswith("0000") and len(student.national_code) == 10
        assert student.student_code >= 100001
        assert (student.branch_id, student.parent_mobile, student.user_id, student.parent_user_id) == (
            1, "", None, None,
        )
        assert student.address == "ثبت شده از سرنخ"
        assert student.study_status == "در حال تحصیل" and student.gender == "نامشخص"
        assert db.query(models.Enrollment).filter(models.Enrollment.student_id == student_id).count() == 0
        after_convert = _database_snapshot(db)
        _assert_unchanged_except(before_convert, after_convert, "crm_leads", "students", "sequence_counters")

        retry = client.post(f"/crm/leads/{lead_id}/convert", headers=auth_headers["secretary"])
        assert retry.status_code == 400
        assert retry.json() == {"detail": "این سرنخ قبلاً به دانش‌آموز تبدیل شده است"}
        db.expire_all()
        assert _database_snapshot(db) == after_convert
    finally:
        _restore_tables(db, before, "Lead", "Enrollment", "Student", "SequenceCounter")


def test_crm_convert_with_active_course_records_enrollment_values_pending_tuition_decision(
    client, auth_headers, db
):
    import models
    from .oracle import build_oracle

    before = _database_snapshot(db)
    lead = models.Lead(
        name="سرنخ کلاس‌دار", mobile="09129990001", interested_course="ریاضی",
        status="NEW", branch_id=1, created_at=FIXED_NOW,
    )
    db.add(lead)
    db.commit()
    lead_id = lead.id
    before_convert = _database_snapshot(db)
    try:
        response = client.post(
            f"/crm/leads/{lead_id}/convert?course_id=1", headers=auth_headers["secretary"],
        )
        assert response.status_code == 200, response.text
        student_id = response.json()["student_id"]
        db.expire_all()
        student = db.get(models.Student, student_id)
        enrollment = db.query(models.Enrollment).filter_by(student_id=student_id, course_id=1).one()
        assert student.branch_id == 1
        assert (enrollment.branch_id, enrollment.register_date, enrollment.shift) == (
            1, FIXED_NOW.strftime("%Y/%m/%d"), "عصر",
        )
        # 1,000,000 is the current observed route default, not a product-approved fee; see Q-010.
        assert (enrollment.total_tuition, enrollment.total_paid, enrollment.discount_type, enrollment.discount_value) == (
            1_000_000, 0, "none", 0,
        )
        assert _database_snapshot(db) != before_convert
        oracle = build_oracle(db)
        assert oracle.enrollments[enrollment.id].paid == 0
        assert oracle.enrollments[enrollment.id].due == 1_000_000
        assert not [tx for tx in db.query(models.Transaction).filter_by(student_id=student_id).all()]
    finally:
        _restore_tables(db, before, "Lead", "Transaction", "Enrollment", "Student", "SequenceCounter")


def test_crm_convert_returns_404_for_missing_lead_and_400_for_invalid_or_duplicate_mobile(
    client, auth_headers, db
):
    import models

    before = _database_snapshot(db)
    try:
        missing = client.post("/crm/leads/999999/convert", headers=auth_headers["secretary"])
        assert missing.status_code == 404
        assert missing.json() == {"detail": "سرنخ یافت نشد"}

        for mobile in ("", "not-a-mobile"):
            lead = models.Lead(
                name="سرنخ موبایل نامعتبر", mobile=mobile, interested_course="ریاضی",
                status="NEW", branch_id=1, created_at=FIXED_NOW,
            )
            db.add(lead)
            db.commit()
            lead_id = lead.id
            response = client.post(f"/crm/leads/{lead_id}/convert", headers=auth_headers["secretary"])
            assert response.status_code == 400
            assert "موبایل" in response.json()["detail"]
            db.expire_all()
            assert db.get(models.Lead, lead_id).status == "NEW"
            assert db.query(models.Student).count() == len(before["students"])

        lead = models.Lead(
            name="سرنخ موبایل موجود", mobile="09350000001", interested_course="ریاضی",
            status="NEW", branch_id=1, created_at=FIXED_NOW,
        )
        db.add(lead)
        db.commit()
        lead_id = lead.id
        duplicate = client.post(f"/crm/leads/{lead_id}/convert", headers=auth_headers["secretary"])
        assert duplicate.status_code == 400
        assert duplicate.json() == {"detail": "دانش‌آموزی با این شماره موبایل قبلاً در سیستم ثبت‌نام شده است"}
        db.expire_all()
        assert db.get(models.Lead, lead_id).status == "NEW"
        assert db.query(models.Student).count() == len(before["students"])
    finally:
        _restore_tables(db, before, "Lead", "Enrollment", "Student", "SequenceCounter")


def test_crm_convert_rejects_nonexistent_course_without_partial_student(client, auth_headers, db):
    import models

    before = _database_snapshot(db)
    lead = models.Lead(
        name="سرنخ کلاس مفقود", mobile="09129990002", interested_course="ریاضی",
        status="NEW", branch_id=1, created_at=FIXED_NOW,
    )
    db.add(lead)
    db.commit()
    lead_id = lead.id
    before_convert = _database_snapshot(db)
    try:
        response = client.post(
            f"/crm/leads/{lead_id}/convert?course_id=999999", headers=auth_headers["secretary"],
        )
        assert _database_snapshot(db) == before_convert
        assert response.status_code == 404, response.text
        assert response.json() == {"detail": "کلاس انتخابی یافت نشد؛ لطفاً یک دورهٔ معتبر انتخاب کنید"}
    finally:
        _restore_tables(db, before, "Lead", "Transaction", "Enrollment", "Student", "SequenceCounter")


def test_crm_online_registration_creates_financial_rows_and_mocked_notifications(
    client, auth_headers, db, monkeypatch
):
    import models
    import push_service
    from dependencies import NotificationService
    from .oracle import build_oracle

    before = _database_snapshot(db)
    oracle_before = build_oracle(db)
    send_calls = []
    push_calls = []
    original_send = NotificationService.send_notification

    def send_spy(**kwargs):
        send_calls.append({key: value for key, value in kwargs.items() if key != "db"})
        return original_send(**kwargs)

    def mocked_push(*args, **kwargs):
        push_calls.append(kwargs)
        return []

    monkeypatch.setattr(NotificationService, "send_notification", staticmethod(send_spy))
    monkeypatch.setattr(push_service, "deliver_push", mocked_push)
    paid_amount = 275_000
    try:
        response = client.post("/crm/register_online", json=_online_payload(paid_amount=paid_amount))
        assert response.status_code == 200, response.text
        payload = response.json()
        assert set(payload) == {"status", "message", "student_id", "enrollment_id", "is_new_student"}
        assert payload["status"] == "success"
        assert payload["message"] == "ثبت‌نام آنلاین شما با موفقیت انجام شد"
        assert payload["is_new_student"] is True

        db.expire_all()
        student = db.get(models.Student, payload["student_id"])
        enrollment = db.get(models.Enrollment, payload["enrollment_id"])
        transaction = db.query(models.Transaction).filter_by(enrollment_id=enrollment.id).one()
        assert (student.first_name, student.last_name, student.father_name) == ("هستی", "آزاده", "علی")
        assert student.national_code == "0001112228"  # valid Persian digits normalize to ASCII
        assert (student.student_mobile, student.parent_mobile) == ("09350099999", "09360099999")
        assert student.student_code >= 100001
        assert student.branch_id is None  # current behavior; branch/ownership policy is Q-011
        assert (student.user_id is not None) and (student.parent_user_id is not None)
        assert (enrollment.student_id, enrollment.course_id, enrollment.branch_id) == (student.id, 1, 1)
        assert (enrollment.total_paid, enrollment.discount_type, enrollment.discount_value) == (paid_amount, "none", 0)
        # Tuition is read from the row for the independent due oracle; its business source remains Q-010.
        assert student.wallet_teacher == 0
        assert (student.wallet_institute, student.wallet_balance) == (paid_amount, paid_amount)
        assert (transaction.student_id, transaction.course_id, transaction.branch_id) == (student.id, 1, 1)
        assert (transaction.amount, transaction.payment_method, transaction.date, transaction.type, transaction.target_wallet) == (
            paid_amount, "کارتخوان", FIXED_NOW.strftime("%Y/%m/%d"), "tuition", "institute",
        )
        assert transaction.description == "ثبت‌نام آنلاین و پرداخت پیش‌پرداخت شهریه"

        oracle_after = build_oracle(db)
        assert oracle_after.institute_cash == oracle_before.institute_cash + paid_amount
        assert oracle_after.enrollments[enrollment.id].paid == paid_amount
        assert oracle_after.enrollments[enrollment.id].due == max(0, enrollment.total_tuition - paid_amount)
        assert oracle_after.student_due[student.id] == max(0, enrollment.total_tuition - paid_amount)

        student_user = db.get(models.User, student.user_id)
        parent_user = db.get(models.User, student.parent_user_id)
        assert (student_user.role, student_user.sub_role, student_user.username, student_user.full_name) == (
            "student", "student", f"student:{student.id}", "هستی آزاده",
        )
        assert (parent_user.role, parent_user.sub_role, parent_user.username, parent_user.full_name) == (
            "parent", "parent", f"parent:{student.id}", "ولی هستی آزاده",
        )
        notifications = db.query(models.Notification).filter_by(recipient_user_id=student.user_id).all()
        assert len(notifications) == 1
        notification = notifications[0]
        expected_body = f"ثبت‌نام شما در کلاس 'ریاضی پایه فعال' با موفقیت انجام شد و مبلغ {paid_amount:,} تومان ثبت گردید."
        assert (notification.recipient_role, notification.type, notification.title, notification.body) == (
            "student", "payment", "✅ ثبت‌نام آنلاین موفقیت‌آمیز", expected_body,
        )
        assert notification.is_read is False and notification.created_at == FIXED_NOW
        assert send_calls == [{
            "recipient_user_id": student.user_id,
            "recipient_role": "student",
            "type": "payment",
            "title": "✅ ثبت‌نام آنلاین موفقیت‌آمیز",
            "body": expected_body,
        }]
        assert push_calls == []  # No real device token/provider call in this isolated flow.

        added_sms = [row for row in db.query(models.SmsLog).all() if row.id not in {r[0] for r in before["sms_logs"]}]
        assert len(added_sms) == 2  # route's SMS log + the notification service's local log; no SMS network
        sms_by_target = {row.target_group: row for row in added_sms}
        assert sms_by_target[f"online_reg_{student.id}"].message_text == (
            "ثبت‌نام آنلاین دانش‌آموز هستی آزاده در کلاس ریاضی پایه فعال با موفقیت انجام شد."
        )
        notification_sms = sms_by_target[f"notif_student_{student.user_id}"]
        assert notification_sms.message_text == f"🔔 {notification.title}\n{expected_body}"
        assert all(row.sent_count == 1 and row.date == FIXED_NOW.strftime("%Y/%m/%d %H:%M") for row in added_sms)
        before_audit_ids = {row[0] for row in before["financial_audit_logs"]}
        audit_logs = [row for row in db.query(models.FinancialAuditLog).all() if row.id not in before_audit_ids]
        assert len(audit_logs) == 1
        audit = audit_logs[0]
        assert (audit.action, audit.entity_type, audit.entity_id, audit.timestamp) == (
            "create", "transaction", transaction.id, FIXED_NOW,
        )
        audit_values = json.loads(audit.new_values)
        assert (audit_values["amount"], audit_values["target_wallet"], audit_values["enrollment_id"]) == (
            paid_amount, "institute", enrollment.id,
        )
        after_first = _database_snapshot(db)
        _assert_unchanged_except(
            before, after_first, "students", "enrollments", "transactions", "financial_audit_logs",
            "sequence_counters", "users", "notifications", "sms_logs",
        )

        retry = client.post("/crm/register_online", json=_online_payload(paid_amount=paid_amount))
        assert retry.status_code == 400
        assert retry.json() == {"detail": "شما قبلاً در این کلاس ثبت‌نام کرده‌اید"}
        db.expire_all()
        assert _database_snapshot(db) == after_first
    finally:
        _restore_tables(
            db, before, "Notification", "SmsLog", "FinancialAuditLog", "Transaction", "Enrollment", "Student", "User", "SequenceCounter",
        )


def test_crm_online_registration_allows_zero_payment_without_financial_receipt(client, db):
    import models
    from .oracle import build_oracle

    before = _database_snapshot(db)
    oracle_before = build_oracle(db)
    try:
        response = client.post("/crm/register_online", json=_online_payload(paid_amount=0))
        assert response.status_code == 200, response.text
        payload = response.json()
        db.expire_all()
        student = db.get(models.Student, payload["student_id"])
        enrollment = db.get(models.Enrollment, payload["enrollment_id"])
        assert payload["is_new_student"] is True
        assert enrollment.total_paid == 0
        assert (student.wallet_teacher, student.wallet_institute, student.wallet_balance) == (0, 0, 0)
        assert db.query(models.Transaction).filter_by(enrollment_id=enrollment.id).count() == 0
        after = _database_snapshot(db)
        _assert_unchanged_except(
            before, after, "students", "enrollments", "sequence_counters", "users", "notifications", "sms_logs",
        )
        oracle_after = build_oracle(db)
        assert oracle_after.institute_cash == oracle_before.institute_cash
        assert oracle_after.enrollments[enrollment.id].paid == 0
        assert oracle_after.enrollments[enrollment.id].due == enrollment.total_tuition
    finally:
        _restore_tables(
            db, before, "Notification", "SmsLog", "FinancialAuditLog", "Transaction", "Enrollment", "Student", "User", "SequenceCounter",
        )


def test_crm_online_registration_reuses_existing_student_and_duplicate_retry_writes_nothing(
    client, db
):
    import models
    from .oracle import build_oracle

    before = _database_snapshot(db)
    student = db.get(models.Student, 14)  # active seed student with no enrollment and valid national-code checksum
    original_student = {
        "wallet_teacher": student.wallet_teacher,
        "wallet_institute": student.wallet_institute,
        "wallet_balance": student.wallet_balance,
        "user_id": student.user_id,
        "parent_user_id": student.parent_user_id,
    }
    oracle_before = build_oracle(db)
    audit_ids_before = {row[0] for row in before["financial_audit_logs"]}
    payload = _online_payload(
        first_name="دانش‌آموز",
        last_name="تست 14",
        father_name="پدر تست",
        national_code="۰۰۲۰۰۰۰۰۱۴",
        student_mobile="۰۹۳۵۰۰۰۰۰۱۴",
        parent_mobile="۰۹۳۶۰۰۰۰۰۱۴",
        course_id=2,
        paid_amount=125_000,
        payment_method="نقدی",
    )
    try:
        response = client.post("/crm/register_online", json=payload)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["is_new_student"] is False
        assert result["student_id"] == student.id == 14
        db.expire_all()
        updated_student = db.get(models.Student, 14)
        enrollment = db.get(models.Enrollment, result["enrollment_id"])
        tx = db.query(models.Transaction).filter_by(enrollment_id=enrollment.id).one()
        assert (updated_student.first_name, updated_student.last_name) == ("دانش‌آموز", "تست 14")
        assert (updated_student.wallet_teacher, updated_student.wallet_institute, updated_student.wallet_balance) == (
            original_student["wallet_teacher"], original_student["wallet_institute"] + 125_000,
            original_student["wallet_balance"] + 125_000,
        )
        assert (enrollment.branch_id, tx.branch_id, tx.target_wallet, tx.amount) == (2, 2, "institute", 125_000)
        assert db.query(models.Student).count() == len(before["students"])
        audit_logs = [row for row in db.query(models.FinancialAuditLog).all() if row.id not in audit_ids_before]
        assert len(audit_logs) == 1
        audit = audit_logs[0]
        assert (audit.action, audit.entity_type, audit.entity_id, audit.timestamp) == (
            "create", "transaction", tx.id, FIXED_NOW,
        )
        assert json.loads(audit.new_values)["amount"] == 125_000
        after_first = _database_snapshot(db)
        _assert_unchanged_except(
            before, after_first, "students", "enrollments", "transactions", "financial_audit_logs",
            "sequence_counters", "users", "notifications", "sms_logs",
        )
        oracle_after = build_oracle(db)
        assert oracle_after.institute_cash == oracle_before.institute_cash + 125_000
        assert oracle_after.enrollments[enrollment.id].paid == 125_000

        retry = client.post("/crm/register_online", json=payload)
        assert retry.status_code == 400
        assert retry.json() == {"detail": "شما قبلاً در این کلاس ثبت‌نام کرده‌اید"}
        db.expire_all()
        assert _database_snapshot(db) == after_first
    finally:
        _restore_tables(
            db, before, "Notification", "SmsLog", "FinancialAuditLog", "Transaction", "Enrollment", "Student", "User", "SequenceCounter",
        )


def test_crm_online_registration_invalid_identity_mobile_payment_and_missing_course_are_no_write(
    client, db
):
    import models

    before = _database_snapshot(db)
    try:
        invalid_national_code = client.post(
            "/crm/register_online", json=_online_payload(national_code="0000000000"),
        )
        assert invalid_national_code.status_code == 422
        invalid_mobile = client.post(
            "/crm/register_online", json=_online_payload(student_mobile="12345"),
        )
        assert invalid_mobile.status_code == 400
        assert invalid_mobile.json() == {"detail": "فرمت شماره موبایل دانش‌آموز صحیح نیست"}
        negative_amount = client.post(
            "/crm/register_online", json=_online_payload(paid_amount=-1),
        )
        assert negative_amount.status_code == 422
        missing_course = client.post(
            "/crm/register_online", json=_online_payload(course_id=999999, paid_amount=0),
        )
        assert missing_course.status_code == 404
        assert missing_course.json() == {"detail": "کلاس انتخابی یافت نشد"}
        assert _database_snapshot(db) == before
        assert db.query(models.Student).count() == len(before["students"])
    finally:
        _restore_tables(
            db, before, "Notification", "SmsLog", "FinancialAuditLog", "Transaction", "Enrollment", "Student", "User", "SequenceCounter",
        )


@pytest.mark.parametrize(
    "field,value",
    [
        (field, value)
        for field in ("first_name", "last_name", "father_name", "national_code", "student_mobile", "parent_mobile")
        for value in ("", "   \t")
    ],
)
def test_crm_online_registration_rejects_empty_required_name_fields(client, db, field, value):
    before = _database_snapshot(db)
    try:
        response = client.post(
            "/crm/register_online", json=_online_payload(**{field: value, "paid_amount": 0}),
        )
        assert _database_snapshot(db) == before
        assert response.status_code in (400, 422), (field, response.status_code, response.text)
    finally:
        _restore_tables(
            db, before, "Notification", "SmsLog", "FinancialAuditLog", "Transaction", "Enrollment", "Student", "User", "SequenceCounter",
        )


def test_crm_online_registration_rejects_amount_above_database_integer_range(client, db):
    before = _database_snapshot(db)
    try:
        response = client.post("/crm/register_online", json=_online_payload(paid_amount=2**63))
        assert _database_snapshot(db) == before  # failed request must roll back student, enrollment, wallet, and receipt
        assert response.status_code == 422, response.text
    finally:
        _restore_tables(
            db, before, "Notification", "SmsLog", "FinancialAuditLog", "Transaction", "Enrollment", "Student", "User", "SequenceCounter",
        )
