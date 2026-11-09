"""Focused value, persistence, and side-effect audit for automation routes."""
from __future__ import annotations

import datetime
import json

import pytest
from sqlalchemy import and_, delete, insert, select, update

from .clock import FIXED_NOW
from .route_registry import route_id, routes

AUTOMATION_ROUTE_IDS = [
    ("GET", "/automation/logs"),
    ("GET", "/automation/rules"),
    ("POST", "/automation/rules"),
    ("PUT", "/automation/rules/{rule_id}"),
    ("POST", "/automation/run_rules"),
]
ROUTE_IDS = [f"{method} {path}" for method, path in AUTOMATION_ROUTE_IDS]


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
    """Restore the selected mutable rows to the exact pre-test image."""
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


def _new_rows(db, model, before, table_name):
    old_ids = {row[0] for row in before[table_name]}
    return [row for row in db.query(model).all() if row.id not in old_ids]


def _single_active_rule(db, models, *, condition, threshold, action, name=None):
    for existing in db.query(models.AutomationRule).all():
        existing.active = False
    rule = models.AutomationRule(
        name=name or f"audit {condition}",
        condition_type=condition,
        threshold=threshold,
        action_type=action,
        active=True,
    )
    db.add(rule)
    db.flush()
    return rule


def _add_session(db, models, *, course_id=1, date="2026/09/25"):
    session = models.SessionLog(
        course_id=course_id,
        date=date,
        time="16:00",
        status="Finished",
        is_deleted=False,
    )
    db.add(session)
    db.flush()
    return session


def _assert_engine_response(response, triggered_count):
    assert response.status_code == 200, response.text
    assert response.json() == {
        "status": "success",
        "message": "قوانین خودکارسازی با موفقیت بررسی و اجرا شدند.",
        "triggered_actions_count": triggered_count,
    }


def test_automation_route_inventory_is_explicit(client):
    actual = {route_id(row) for row in routes() if row["handler"].split(".")[1] == "automation"}
    assert {f"{method} {path}" for method, path in AUTOMATION_ROUTE_IDS} == actual
    openapi_routes = {
        (method.upper(), path)
        for path, methods in client.app.openapi()["paths"].items()
        for method in methods
    }
    assert all((method, path) in openapi_routes for method, path in AUTOMATION_ROUTE_IDS)


def test_automation_create_rule_persists_exact_values_and_rules_list_is_read_only(
    client, auth_headers, db,
):
    import models

    before = _database_snapshot(db)
    request = {
        "name": "هشدار حضور کمتر از هشتاد درصد",
        "condition_type": "attendance_low",
        "threshold": 80.5,
        "action_type": "parent_notification",
    }
    try:
        response = client.post("/automation/rules", json=request, headers=auth_headers["admin"])
        assert response.status_code == 200, response.text
        payload = response.json()
        assert set(payload) == {"message", "rule_id"}
        assert payload["message"] == "قانون خودکارسازی جدید با موفقیت ایجاد شد"

        db.expire_all()
        rule = db.get(models.AutomationRule, payload["rule_id"])
        assert rule is not None
        assert (
            rule.name, rule.condition_type, rule.threshold, rule.action_type, rule.active,
        ) == (request["name"], request["condition_type"], 80.5, request["action_type"], True)
        after_create = _database_snapshot(db)
        _assert_unchanged_except(before, after_create, "automation_rules")
        assert len(after_create["automation_rules"]) == len(before["automation_rules"]) + 1

        listed = client.get("/automation/rules", headers=auth_headers["admin"])
        assert listed.status_code == 200
        values = listed.json()
        created = next(item for item in values if item["id"] == rule.id)
        assert set(created) == {"id", "name", "condition_type", "threshold", "action_type", "active"}
        assert created == {
            "id": rule.id,
            "name": request["name"],
            "condition_type": "attendance_low",
            "threshold": 80.5,
            "action_type": "parent_notification",
            "active": True,
        }
        assert _database_snapshot(db) == after_create
    finally:
        _restore_tables(db, before, "AutomationRule")


def test_automation_create_rejects_unknown_condition_action_and_missing_fields_without_writes(
    client, auth_headers, db,
):
    before = _database_snapshot(db)
    requests = [
        ({"name": "invalid condition", "condition_type": "not-a-condition", "threshold": 1, "action_type": "sms"}, 400, {"detail": "نوع شرط نامعتبر است"}),
        ({"name": "invalid action", "condition_type": "grade_low", "threshold": 10, "action_type": "not-an-action"}, 400, {"detail": {"code": "unknown_action", "message": "نوع عملیات نامعتبر است", "can_continue": True}}),
        ({"name": "missing threshold", "condition_type": "grade_low", "action_type": "parent_alert"}, 422, None),
        ({"name": "invalid threshold", "condition_type": "grade_low", "threshold": "not-a-number", "action_type": "parent_alert"}, 422, None),
    ]
    try:
        for body, expected_status, expected_json in requests:
            response = client.post("/automation/rules", json=body, headers=auth_headers["admin"])
            assert response.status_code == expected_status, response.text
            if expected_json is not None:
                assert response.json() == expected_json
            assert _database_snapshot(db) == before
    finally:
        _restore_tables(db, before, "AutomationRule")


def test_automation_create_allows_unknown_action_only_after_explicit_confirmation(client, auth_headers, db):
    import models

    before = _database_snapshot(db)
    try:
        response = client.post(
            "/automation/rules",
            json={
                "name": "عملیات سفارشی تأییدشده",
                "condition_type": "grade_low",
                "threshold": 10,
                "action_type": "custom_action",
                "confirm_unknown_action": True,
            },
            headers=auth_headers["admin"],
        )
        assert response.status_code == 200, response.text
        created = db.get(models.AutomationRule, response.json()["rule_id"])
        assert created.action_type == "custom_action"
        after = _database_snapshot(db)
        _assert_unchanged_except(before, after, "automation_rules")
    finally:
        _restore_tables(db, before, "AutomationRule")


@pytest.mark.parametrize("name", ["", "  \t  "], ids=["empty", "whitespace"])
def test_automation_empty_rule_name_is_rejected_without_writes(client, auth_headers, db, name):
    before = _database_snapshot(db)
    try:
        response = client.post(
            "/automation/rules",
            json={"name": name, "condition_type": "grade_low", "threshold": 10, "action_type": "parent_alert"},
            headers=auth_headers["admin"],
        )
        assert _database_snapshot(db) == before
        assert response.status_code in (400, 422), (response.status_code, response.text)
    finally:
        _restore_tables(db, before, "AutomationRule")


def test_automation_rules_empty_list_is_empty_json_and_read_only(client, auth_headers, db):
    import models

    before = _database_snapshot(db)
    try:
        db.query(models.AutomationLog).delete(synchronize_session=False)
        db.query(models.AutomationRule).delete(synchronize_session=False)
        db.commit()
        empty_baseline = _database_snapshot(db)
        response = client.get("/automation/rules", headers=auth_headers["admin"])
        assert response.status_code == 200
        assert response.json() == []
        assert _database_snapshot(db) == empty_baseline
    finally:
        _restore_tables(db, before, "AutomationRule", "AutomationLog")


def test_automation_update_is_partial_supports_zero_and_false_and_missing_is_no_write(
    client, auth_headers, db,
):
    import models

    before = _database_snapshot(db)
    try:
        response = client.put(
            "/automation/rules/1",
            json={"name": "قانون اصلاح‌شده", "threshold": 0, "action_type": "sms", "active": False},
            headers=auth_headers["admin"],
        )
        assert response.status_code == 200, response.text
        assert response.json() == {"message": "قانون خودکارسازی با موفقیت بروزرسانی شد"}
        db.expire_all()
        rule = db.get(models.AutomationRule, 1)
        assert (rule.name, rule.threshold, rule.action_type, rule.active) == (
            "قانون اصلاح‌شده", 0.0, "sms", False,
        )
        after_update = _database_snapshot(db)
        _assert_unchanged_except(before, after_update, "automation_rules")

        noop = client.put("/automation/rules/1", json={}, headers=auth_headers["admin"])
        assert noop.status_code == 200
        assert noop.json() == {"message": "قانون خودکارسازی با موفقیت بروزرسانی شد"}
        assert _database_snapshot(db) == after_update

        missing = client.put("/automation/rules/999999", json={"active": False}, headers=auth_headers["admin"])
        assert missing.status_code == 404
        assert missing.json() == {"detail": "قانون مورد نظر یافت نشد"}
        assert _database_snapshot(db) == after_update
    finally:
        _restore_tables(db, before, "AutomationRule")


def test_automation_update_requires_confirmation_for_unknown_action_type(client, auth_headers, db):
    import models

    before = _database_snapshot(db)
    try:
        response = client.put(
            "/automation/rules/1", json={"action_type": "not-an-action"}, headers=auth_headers["admin"],
        )
        assert _database_snapshot(db) == before
        assert response.status_code == 400, response.text
        assert response.json() == {
            "detail": {
                "code": "unknown_action",
                "message": "نوع عملیات نامعتبر است",
                "can_continue": True,
            }
        }

        confirmed = client.put(
            "/automation/rules/1",
            json={"action_type": "not-an-action", "confirm_unknown_action": True},
            headers=auth_headers["admin"],
        )
        assert confirmed.status_code == 200, confirmed.text
        db.expire_all()
        assert db.get(models.AutomationRule, 1).action_type == "not-an-action"
        _assert_unchanged_except(before, _database_snapshot(db), "automation_rules")
    finally:
        _restore_tables(db, before, "AutomationRule")


def test_automation_logs_filter_descending_limit_offset_and_empty_results_are_read_only(
    client, auth_headers, db,
):
    import models

    before = _database_snapshot(db)
    try:
        rows = [
            models.AutomationLog(rule_id=1, triggered_at=FIXED_NOW + datetime.timedelta(minutes=minute), details=f"log-{minute}")
            for minute in (1, 2, 3)
        ]
        db.add_all(rows)
        db.commit()
        ids = {row.details: row.id for row in rows}
        before_read = _database_snapshot(db)

        response = client.get(
            "/automation/logs", params={"rule_id": 1, "limit": 2, "offset": 1}, headers=auth_headers["admin"],
        )
        assert response.status_code == 200, response.text
        assert response.json() == [
            {"id": ids["log-2"], "rule_id": 1, "triggered_at": (FIXED_NOW + datetime.timedelta(minutes=2)).isoformat(), "details": "log-2"},
            {"id": ids["log-1"], "rule_id": 1, "triggered_at": (FIXED_NOW + datetime.timedelta(minutes=1)).isoformat(), "details": "log-1"},
        ]
        empty = client.get("/automation/logs", params={"rule_id": 999999}, headers=auth_headers["admin"])
        assert empty.status_code == 200 and empty.json() == []
        zero_limit = client.get("/automation/logs", params={"rule_id": 1, "limit": 0}, headers=auth_headers["admin"])
        assert zero_limit.status_code == 200 and zero_limit.json() == []
        assert _database_snapshot(db) == before_read
    finally:
        _restore_tables(db, before, "AutomationLog")


def test_automation_run_rules_with_no_active_rules_returns_zero_without_writes(
    client, auth_headers, db,
):
    import models

    before = _database_snapshot(db)
    try:
        for rule in db.query(models.AutomationRule).all():
            rule.active = False
        db.commit()
        before_run = _database_snapshot(db)
        response = client.post("/automation/run_rules", headers=auth_headers["admin"])
        _assert_engine_response(response, 0)
        assert _database_snapshot(db) == before_run
    finally:
        _restore_tables(db, before, "AutomationRule")


def _prepare_engine_case(db, models, case):
    """Prepare one targeted row transition; return precise expected effects."""
    if case == "attendance_low":
        rule = _single_active_rule(db, models, condition=case, threshold=80, action="parent_notification")
        first = _add_session(db, models, date="2026/09/25")
        second = _add_session(db, models, date="2026/09/26")
        archived_session = _add_session(db, models, date="2026/09/27")
        db.add_all([
            models.Attendance(session_id=first.id, student_id=1, status="Absent", excused=False, is_deleted=False),
            models.Attendance(session_id=second.id, student_id=1, status="Present", excused=False, is_deleted=False),
            models.Attendance(session_id=archived_session.id, student_id=1, status="Absent", excused=False, is_deleted=True),
        ])
        db.flush()
        rate = 200 / 3
        return rule, {
            "count": 1,
            "logs": [f"Triggered for parent #1. Student #1 in class 1 has {rate:.1f}% attendance."],
            "notifications": [(5, "parent", "⚠️ هشدار حضور و غیاب دانش‌آموز", f"ولی محترم، به اطلاع می‌رساند میزان حضور فرزند شما دانش‌آموز در کلاس ریاضی پایه فعال کمتر از 80.0% ({rate:.1f}%) است. لطفاً پیگیری فرمایید.", None)],
            "sms": [],
        }

    if case == "absence_high":
        rule = _single_active_rule(db, models, condition=case, threshold=1, action="parent_notification")
        excused_session = _add_session(db, models, date="2026/09/25")
        unexcused_session = _add_session(db, models, date="2026/09/26")
        archived_session = _add_session(db, models, date="2026/09/27")
        db.add_all([
            models.Attendance(session_id=excused_session.id, student_id=1, status="Absent", excused=True, is_deleted=False),
            models.Attendance(session_id=unexcused_session.id, student_id=1, status="Absent", excused=False, is_deleted=False),
            models.Attendance(session_id=archived_session.id, student_id=1, status="Absent", excused=False, is_deleted=True),
        ])
        db.flush()
        return rule, {
            "count": 1,
            "logs": ["Triggered for parent #1. Student #1 has 1 absences in class 1."],
            "notifications": [(5, "parent", "🚨 هشدار غیبت غیرموجه مکرر", "ولی محترم، فرزند شما دانش‌آموز دارای 1 جلسه غیبت غیرموجه در کلاس ریاضی پایه فعال می‌باشد.", None)],
            "sms": [],
        }

    if case == "installment_due":
        rule = _single_active_rule(db, models, condition=case, threshold=1, action="parent_notification")
        valid = models.Installment(enrollment_id=1, amount=123_456, due_date="2026/09/29", is_paid=False, is_deleted=False)
        paid = models.Installment(enrollment_id=1, amount=10_000, due_date="2026/09/29", is_paid=True, is_deleted=False)
        archived = models.Installment(enrollment_id=1, amount=20_000, due_date="2026/09/29", is_paid=False, is_deleted=True)
        db.add_all([valid, paid, archived])
        db.flush()
        return rule, {
            "count": 1,
            "logs": [f"Triggered for parent #1. Installment #{valid.id} is due tomorrow."],
            "notifications": [(5, "parent", "📅 سررسید قسط شهریه فردا", "ولی محترم، به اطلاع می‌رساند قسط شهریه فرزند شما دانش‌آموز به مبلغ 123,456 تومان فردا 2026/09/29 سررسید می‌شود.", None)],
            "sms": [],
        }

    if case == "installment_overdue":
        rule = _single_active_rule(db, models, condition=case, threshold=1, action="sms")
        # Seed's two unpaid installments are also past due at FIXED_NOW; archive only
        # those fixture rows so this probe has a single, unambiguous overdue target.
        for installment in db.query(models.Installment).filter(models.Installment.id.in_([1, 2])).all():
            installment.is_deleted = True
        valid = models.Installment(enrollment_id=1, amount=234_567, due_date="2026/09/27", is_paid=False, is_deleted=False)
        paid = models.Installment(enrollment_id=1, amount=10_000, due_date="2026/09/20", is_paid=True, is_deleted=False)
        archived = models.Installment(enrollment_id=1, amount=20_000, due_date="2026/09/20", is_paid=False, is_deleted=True)
        db.add_all([valid, paid, archived])
        db.flush()
        body = "ولی محترم، قسط شهریه فرزند شما دانش‌آموز به مبلغ 234,567 تومان معوقه شده است. لطفاً نسبت به تسویه حساب اقدام فرمایید."
        return rule, {
            "count": 1,
            "logs": [f"Triggered for parent #1. Installment #{valid.id} is overdue."],
            "notifications": [(5, "parent", "🚨 قسط شهریه معوقه شده", body, None)],
            "sms": [(f"overdue_{valid.id}", body, 1, FIXED_NOW.strftime("%Y/%m/%d %H:%M"))],
        }

    if case == "homework_deadline":
        rule = _single_active_rule(db, models, condition=case, threshold=24, action="student_notification")
        homework = models.Homework(
            course_id=2, teacher_id=1, title="تمرین نزدیک", description="آزمون deadline",
            due_date="2026/09/29", max_score=20, status="pending",
        )
        db.add(homework)
        db.flush()
        return rule, {
            "count": 1,
            "logs": [f"Triggered for student #1. HW #{homework.id} Student #1 deadline approaching."],
            "notifications": [(4, "student", "📝 یادآوری تمرین درسی", "دانش‌آموز گرامی، کمتر از ۲۴ ساعت به مهلت تحویل تمرین 'تمرین نزدیک' باقی مانده است. لطفاً پاسخ خود را بارگذاری کنید.", None)],
            "sms": [],
        }

    if case == "grade_low":
        rule = _single_active_rule(db, models, condition=case, threshold=5, action="parent_alert")
        grade = models.Grade(
            student_id=1, course_id=1, teacher_id=1, exam_title="آزمون ممیزی", score=4.5,
            max_score=20, date="1405/07/06", description="",
        )
        db.add(grade)
        db.flush()
        body = "ولی محترم، به اطلاع می‌رساند فرزند شما دانش‌آموز در آزمون 'آزمون ممیزی' نمره 4.5 از 20.0 را کسب کرده است."
        return rule, {
            "count": 1,
            "logs": [f"Triggered for parent #1. Grade #{grade.id} score 4.5 is below 5.0."],
            "notifications": [(5, "parent", "📉 هشدار افت تحصیلی و نمره ضعیف", body, None)],
            "sms": [],
        }

    if case == "student_inactive":
        rule = _single_active_rule(db, models, condition=case, threshold=30, action="parent_notification")
        # Keep the student's actual latest project-calendar date in Gregorian form;
        # silence the other active seed student with an old Jalali date in this case.
        for attendance in db.query(models.Attendance).filter(models.Attendance.student_id == 2).all():
            attendance.is_deleted = True
        session = _add_session(db, models, course_id=2, date="2026/08/01")
        db.add(models.Attendance(
            session_id=session.id, student_id=1, status="Present", excused=False, is_deleted=False,
        ))
        db.flush()
        elapsed = (FIXED_NOW - datetime.datetime(2026, 8, 1)).days
        return rule, {
            "count": 1,
            "logs": [f"Triggered for parent #1. Inactive Student #1 with last activity {elapsed} days ago."],
            "notifications": [(5, "parent", "👤 پیگیری وضعیت دانش‌آموز غیرفعال", "دانش‌آموز گرامی، مدتی است در کلاس‌ها غایب هستید. جهت هماهنگی با مدیریت تماس بگیرید.", None)],
            "sms": [],
        }

    if case == "lead_uncontacted":
        rule = _single_active_rule(db, models, condition=case, threshold=3, action="crm_reminder")
        lead = models.Lead(
            name="سرنخ قدیمی", mobile="09129991111", interested_course="ریاضی", source="Web",
            status="NEW", branch_id=2, created_at=FIXED_NOW - datetime.timedelta(days=5),
        )
        ignored = models.Lead(
            name="سرنخ قبلاً تماس‌گرفته", mobile="09129992222", interested_course="فیزیک", source="Web",
            status="CONTACTED", branch_id=2, created_at=FIXED_NOW - datetime.timedelta(days=10),
        )
        db.add_all([lead, ignored])
        db.flush()
        return rule, {
            "count": 1,
            "logs": [f"Triggered for admin staff (1 recipients). Lead #{lead.id} uncontacted for 5 days."],
            "notifications": [(1, "admin", "📞 پیگیری سرنخ جذب جدید", f"سرنخ '{lead.name}' به شماره '{lead.mobile}' به مدت 5 روز است که تماسی با او گرفته نشده است. لطفاً بررسی فرمایید.", {"lead_id": lead.id, "branch_id": 2})],
            "sms": [],
        }

    raise AssertionError(f"Unhandled automation case: {case}")


@pytest.mark.parametrize(
    "case",
    [
        "attendance_low", "absence_high", "installment_due", "installment_overdue",
        "homework_deadline", "grade_low",
        "student_inactive",
        "lead_uncontacted",
    ],
)
def test_automation_engine_trigger_effects_and_retries_are_exact_and_network_free(
    client, auth_headers, db, monkeypatch, case,
):
    import models
    import push_service

    before = _database_snapshot(db)
    push_calls = []
    monkeypatch.setattr(push_service, "deliver_push", lambda *args, **kwargs: push_calls.append((args, kwargs)) or [])
    try:
        rule, expected = _prepare_engine_case(db, models, case)
        db.commit()
        db.expire_all()
        before_run = _database_snapshot(db)

        response = client.post("/automation/run_rules", headers=auth_headers["admin"])
        _assert_engine_response(response, expected["count"])
        db.expire_all()
        new_logs = _new_rows(db, models.AutomationLog, before_run, "automation_logs")
        assert len(new_logs) == len(expected["logs"])
        assert [(row.rule_id, row.triggered_at, row.details) for row in new_logs] == [
            (rule.id, FIXED_NOW, detail) for detail in expected["logs"]
        ]

        new_notifications = _new_rows(db, models.Notification, before_run, "notifications")
        assert len(new_notifications) == len(expected["notifications"])
        assert [
            (row.recipient_user_id, row.recipient_role, row.type, row.title, row.body, row.created_at, row.data, row.is_read, row.priority)
            for row in new_notifications
        ] == [
            (recipient_id, role, "automation", title, body, FIXED_NOW, json.dumps(data) if data is not None else None, False, 1)
            for recipient_id, role, title, body, data in expected["notifications"]
        ]

        new_sms = _new_rows(db, models.SmsLog, before_run, "sms_logs")
        assert sorted((row.target_group, row.message_text, row.sent_count, row.date) for row in new_sms) == sorted(expected["sms"])
        after_first = _database_snapshot(db)
        _assert_unchanged_except(
            before_run, after_first, "automation_logs", "notifications", "sms_logs",
        )
        assert push_calls == []  # no device token/provider call is allowed in this offline fixture

        retry = client.post("/automation/run_rules", headers=auth_headers["admin"])
        _assert_engine_response(retry, 0)
        db.expire_all()
        assert _database_snapshot(db) == after_first
    finally:
        _restore_tables(
            db, before, "Attendance", "SessionLog", "HomeworkSubmission", "Homework", "Installment",
            "Grade", "Lead", "AutomationLog", "SmsLog", "Notification", "AutomationRule", "Student", "User",
            "FinancialAuditLog",
        )
