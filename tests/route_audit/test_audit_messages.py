"""Temporary-database audit of messenger routes, side effects, and Android DTOs."""
from __future__ import annotations

import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import and_, delete, insert, select, update

from .clock import FIXED_NOW
from .kotlin_contract import audit_payload, discover_models
from .route_registry import route_id, routes

ROUTE_IDS = [
    "POST /messages/broadcast",
    "GET /messages/conversations",
    "POST /messages/conversations/create",
    "GET /messages/conversations/{id}/history",
    "POST /messages/conversations/{id}/pin",
    "POST /messages/conversations/{id}/send",
    "DELETE /messages/{id}",
]


# Restore messages and dependent rows first; User/Student shadow columns are
# included because notification resolution can lazily create a shadow account.
RESTORE_MODELS = (
    "Message", "ConversationParticipant", "Conversation", "Notification",
    "DeviceToken", "Student", "Teacher", "User",
)


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


def _restore_tables(db, before, model_names=RESTORE_MODELS):
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


def _new_rows(db, model, before, table_name):
    old_ids = {row[0] for row in before[table_name]}
    db.expire_all()
    return [row for row in db.query(model).order_by(model.id).all() if row.id not in old_ids]


def _message_times():
    return {
        "now": FIXED_NOW.strftime("%Y/%m/%d %H:%M"),
        "one_hour_ago": (FIXED_NOW - datetime.timedelta(hours=1)).strftime("%Y/%m/%d %H:%M"),
        "one_day_ago": (FIXED_NOW - datetime.timedelta(days=1)).strftime("%Y/%m/%d %H:%M"),
    }


def _message_conversation(db, models, *, title="گفتگوی ممیزی", type="group", pinned_by=None):
    conversation = models.Conversation(
        title=title, type=type, pinned_by=pinned_by, created_at=FIXED_NOW,
    )
    db.add(conversation)
    db.flush()
    return conversation


def test_messages_route_inventory_is_explicit(client):
    actual = {route_id(row) for row in routes() if row["handler"].split(".")[1] == "messages"}
    assert set(ROUTE_IDS) == actual
    openapi_routes = {
        (method.upper(), path)
        for path, methods in client.app.openapi()["paths"].items()
        for method in methods
    }
    assert all(tuple(route.split(" ", 1)) in openapi_routes for route in ROUTE_IDS)


def test_conversations_and_history_are_role_scoped_ordered_and_gson_compatible(
    client, auth_headers, db,
):
    import models

    before = _database_snapshot(db)
    kotlin_models = discover_models()
    try:
        # An actor with no participant row receives an actual empty list.
        empty = client.get("/messages/conversations", headers=auth_headers["student"])
        assert empty.status_code == 200
        assert empty.json() == []
        assert _database_snapshot(db) == before

        empty_conversation = _message_conversation(
            db, models, title=None, type="private", pinned_by=None,
        )
        empty_conversation.created_at = FIXED_NOW - datetime.timedelta(days=1)
        pinned_conversation = _message_conversation(
            db, models, title="گفتگوی خانواده", type="group", pinned_by="1_admin,1_teacher",
        )
        db.add_all([
            models.ConversationParticipant(conversation_id=empty_conversation.id, user_id=1, role="admin"),
            models.ConversationParticipant(conversation_id=pinned_conversation.id, user_id=1, role="admin"),
            models.ConversationParticipant(conversation_id=pinned_conversation.id, user_id=1, role="teacher"),
            models.ConversationParticipant(conversation_id=pinned_conversation.id, user_id=1, role="student"),
            models.ConversationParticipant(conversation_id=pinned_conversation.id, user_id=1, role="parent"),
            models.ConversationParticipant(conversation_id=pinned_conversation.id, user_id=2, role="secretary"),
            models.Message(
                conversation_id=pinned_conversation.id, sender_id=1, sender_role="admin",
                body="پیام زنده برای history", attachment=None,
                created_at=FIXED_NOW - datetime.timedelta(hours=1), is_deleted=False,
            ),
            models.Message(
                conversation_id=pinned_conversation.id, sender_id=2, sender_role="secretary",
                body="این پیام حذف شده است", attachment="messages/hidden.pdf",
                created_at=FIXED_NOW, is_deleted=True,
            ),
        ])
        db.commit()
        db.expire_all()
        before_reads = _database_snapshot(db)
        ids = {
            "seed": 1,
            "empty": empty_conversation.id,
            "pinned": pinned_conversation.id,
        }
        times = _message_times()

        expected_admin = [
            {
                "id": ids["pinned"], "title": "گفتگوی خانواده", "type": "group",
                "last_message": "پیام زنده برای history", "last_time": times["one_hour_ago"],
                "is_pinned": True,
            },
            {
                "id": ids["seed"], "title": "گفتگوی ممیزی", "type": "group",
                "last_message": "پیام seed", "last_time": times["now"], "is_pinned": False,
            },
            {
                "id": ids["empty"], "title": "گفتگوی خصوصی", "type": "private",
                "last_message": "هنوز پیامی ارسال نشده است", "last_time": times["one_day_ago"],
                "is_pinned": False,
            },
        ]
        admin_list = client.get("/messages/conversations", headers=auth_headers["admin"])
        assert admin_list.status_code == 200
        assert admin_list.json() == expected_admin
        assert all(audit_payload("ConversationItem", row, kotlin_models) == [] for row in admin_list.json())

        for role, pinned in (("teacher", True), ("student", False), ("parent", False), ("secretary", False)):
            response = client.get("/messages/conversations", headers=auth_headers[role])
            assert response.status_code == 200
            assert response.json() == [
                {
                    "id": ids["pinned"], "title": "گفتگوی خانواده", "type": "group",
                    "last_message": "پیام زنده برای history", "last_time": times["one_hour_ago"],
                    "is_pinned": pinned,
                }
            ]
            assert audit_payload("ConversationItem", response.json()[0], kotlin_models) == []

        history = client.get(
            f"/messages/conversations/{ids['pinned']}/history", headers=auth_headers["admin"],
        )
        assert history.status_code == 200
        assert history.json() == [{
            "id": 2, "sender_id": 1, "sender_role": "admin",
            "body": "پیام زنده برای history", "attachment": None,
            "created_at": times["one_hour_ago"],
        }]
        assert all(audit_payload("MessageHistoryItem", row, kotlin_models) == [] for row in history.json())

        empty_history = client.get(
            f"/messages/conversations/{ids['empty']}/history", headers=auth_headers["admin"],
        )
        assert empty_history.status_code == 200
        assert empty_history.json() == []
        # A teacher can see the shared family conversation but not admin's private fixture.
        denied = client.get(
            f"/messages/conversations/{ids['seed']}/history", headers=auth_headers["teacher"],
        )
        assert denied.status_code == 403
        assert denied.json() == {"detail": "شما مجاز به مشاهده پیام‌های این گفتگو نیستید (IDOR)"}
        assert _database_snapshot(db) == before_reads
    finally:
        _restore_tables(db, before)


def test_conversation_create_has_exact_participants_and_rolls_back_missing_targets(
    client, auth_headers, db,
):
    import models

    before = _database_snapshot(db)
    kotlin_models = discover_models()
    assert db.get(models.Student, 2).is_suspended is True
    assert db.get(models.Teacher, 2).is_suspended is True
    request = {
        "title": "گفتگوی جدید ممیزی",
        "type": "group",
        "participant_ids": [1, 1, 2, 2],
        "participant_roles": ["student", "teacher", "student", "teacher"],
    }
    try:
        assert audit_payload("ConversationCreateRequest", request, kotlin_models) == []
        created = client.post(
            "/messages/conversations/create", json=request, headers=auth_headers["admin"],
        )
        assert created.status_code == 200, created.text
        payload = created.json()
        assert set(payload) == {"message", "conversation_id"}
        assert payload["message"] == "گفتگو با موفقیت آغاز شد"
        assert audit_payload("SimpleResponse", payload, kotlin_models) == []

        db.expire_all()
        conversation = db.get(models.Conversation, payload["conversation_id"])
        assert conversation is not None
        assert (conversation.title, conversation.type, conversation.pinned_by, conversation.created_at) == (
            "گفتگوی جدید ممیزی", "group", None, FIXED_NOW,
        )
        participant_rows = db.query(models.ConversationParticipant).filter(
            models.ConversationParticipant.conversation_id == conversation.id,
        ).all()
        assert {(row.user_id, row.role) for row in participant_rows} == {
            (1, "admin"), (1, "student"), (1, "teacher"), (2, "student"), (2, "teacher"),
        }
        after_create = _database_snapshot(db)
        _assert_unchanged_except(before, after_create, "conversations", "conversation_participants")

        for participant_id, participant_role, detail in (
            (3, "student", "کاربر مخاطب با شناسه 3 و نقش student یافت نشد"),
            (999999, "student", "کاربر مخاطب با شناسه 999999 و نقش student یافت نشد"),
            (3, "teacher", "کاربر مخاطب با شناسه 3 و نقش teacher یافت نشد"),
        ):
            invalid_request = {
                "title": "نباید ساخته شود", "type": "private",
                "participant_ids": [participant_id], "participant_roles": [participant_role],
            }
            response = client.post(
                "/messages/conversations/create", json=invalid_request,
                headers=auth_headers["admin"],
            )
            assert response.status_code == 400
            assert response.json() == {"detail": detail}
            assert _database_snapshot(db) == after_create
    finally:
        _restore_tables(db, before)


@pytest.mark.parametrize(
    "participant_ids,participant_roles",
    [([1, 2], ["student"]), ([1], ["student", "teacher"])],
    ids=["roles-shorter-than-ids", "roles-longer-than-ids"],
)
def test_conversation_create_rejects_mismatched_participant_arrays(
    client, auth_headers, db, participant_ids, participant_roles,
):
    """The two parallel lists must be length-checked before any row is flushed."""
    before = _database_snapshot(db)
    safe_client = TestClient(client.app, raise_server_exceptions=False)
    request = {
        "title": "رد شود", "type": "group",
        "participant_ids": participant_ids, "participant_roles": participant_roles,
    }
    try:
        response = safe_client.post(
            "/messages/conversations/create", json=request, headers=auth_headers["admin"],
        )
        assert response.status_code == 422, response.text
        assert response.json() == {
            "detail": {
                "code": "recipient_information_incomplete",
                "message": "اطلاعات را تکمیل کنید",
            }
        }
        assert _database_snapshot(db) == before

        # After the user completes the missing recipient information, the same flow can continue.
        completed = client.post(
            "/messages/conversations/create",
            json={
                "title": "اطلاعات تکمیل‌شده",
                "type": "group",
                "participant_ids": [1],
                "participant_roles": ["student"],
            },
            headers=auth_headers["admin"],
        )
        assert completed.status_code == 200, completed.text
        created_rows = _database_snapshot(db)
        _assert_unchanged_except(before, created_rows, "conversations", "conversation_participants")
        assert completed.json()["conversation_id"] > 0
    finally:
        _restore_tables(db, before)


def test_message_send_logs_local_notification_and_duplicate_retry_exactly(
    client, auth_headers, db, monkeypatch,
):
    import models
    import push_service

    before = _database_snapshot(db)
    conversation = _message_conversation(db, models, title="گفتگوی ادمین و منشی")
    db.add_all([
        models.ConversationParticipant(conversation_id=conversation.id, user_id=1, role="admin"),
        models.ConversationParticipant(conversation_id=conversation.id, user_id=2, role="secretary"),
        models.DeviceToken(user_id=2, role="secretary", token="audit-message-push-secretary"),
    ])
    db.commit()
    db.expire_all()
    before_send = _database_snapshot(db)
    push_calls = []

    def fake_deliver_push(db_arg, tokens, **kwargs):
        push_calls.append({
            "tokens": [token.token for token in tokens],
            "title": kwargs.get("title"),
            "body": kwargs.get("body"),
            "data": kwargs.get("data"),
            "commit": kwargs.get("commit"),
        })

    monkeypatch.setattr(push_service, "deliver_push", fake_deliver_push)
    kotlin_models = discover_models()
    body = "سلام؛ پیام ممیزی برای بررسی اعلان و جلوگیری از ارسال push واقعی."
    request = {"body": body}
    try:
        assert audit_payload("MessageSendRequest", request, kotlin_models) == []
        sent = client.post(
            f"/messages/conversations/{conversation.id}/send", json=request,
            headers=auth_headers["admin"],
        )
        assert sent.status_code == 200, sent.text
        assert sent.json() == {"message": "پیام با موفقیت ارسال شد"}
        assert audit_payload("SimpleResponse", sent.json(), kotlin_models) == []

        added_messages = _new_rows(db, models.Message, before_send, "messages")
        assert len(added_messages) == 1
        message = added_messages[0]
        assert (
            message.conversation_id, message.sender_id, message.sender_role, message.body,
            message.attachment, message.created_at, message.is_deleted,
        ) == (conversation.id, 1, "admin", body, None, FIXED_NOW, False)
        added_notifications = _new_rows(db, models.Notification, before_send, "notifications")
        assert len(added_notifications) == 1
        notification = added_notifications[0]
        expected_notification_body = f"پیام جدیدی برای شما ارسال شد: {body[:30]}..."
        assert (
            notification.recipient_user_id, notification.recipient_role, notification.type,
            notification.title, notification.body, notification.data, notification.is_read,
            notification.created_at, notification.priority,
        ) == (
            2, "secretary", "message", "📩 پیام جدید", expected_notification_body,
            None, False, FIXED_NOW, 1,
        )
        assert push_calls == [{
            "tokens": ["audit-message-push-secretary"],
            "title": "📩 پیام جدید", "body": expected_notification_body,
            "data": {"type": "message", "notification_id": notification.id},
            "commit": False,
        }]
        after_first_send = _database_snapshot(db)
        _assert_unchanged_except(before_send, after_first_send, "messages", "notifications")

        retry = client.post(
            f"/messages/conversations/{conversation.id}/send", json=request,
            headers=auth_headers["admin"],
        )
        assert retry.status_code == 200
        assert retry.json() == {"message": "پیام با موفقیت ارسال شد"}
        after_retry = _database_snapshot(db)
        _assert_unchanged_except(after_first_send, after_retry, "messages")
        assert len(_new_rows(db, models.Message, before_send, "messages")) == 2
        assert len(_new_rows(db, models.Notification, before_send, "notifications")) == 1
        # NotificationService's 10-second duplicate filter suppresses another
        # notification/push, but the message route itself has no idempotency key.
        assert len(push_calls) == 1
    finally:
        _restore_tables(db, before)


def test_message_send_empty_body_missing_body_and_nonparticipant_are_no_write(
    client, auth_headers, db,
):
    import models

    before = _database_snapshot(db)
    for payload, status_code, detail in (
        ({"body": "   "}, 400, "متن پیام نمی‌تواند خالی باشد"),
        ({}, 422, None),
    ):
        response = client.post(
            "/messages/conversations/1/send", json=payload, headers=auth_headers["admin"],
        )
        assert response.status_code == status_code, response.text
        if detail is not None:
            assert response.json() == {"detail": detail}
        assert _database_snapshot(db) == before

    denied = client.post(
        "/messages/conversations/999999/send", json={"body": "نباید ذخیره شود"},
        headers=auth_headers["admin"],
    )
    assert denied.status_code == 403
    assert denied.json() == {"detail": "شما مجاز به ارسال پیام در این گفتگو نیستید (IDOR)"}
    assert _database_snapshot(db) == before

    no_auth = client.post("/messages/conversations/1/send", json={"body": "بدون token"})
    assert no_auth.status_code == 401
    assert _database_snapshot(db) == before


def test_message_send_notifies_other_role_when_numeric_participant_ids_collide(
    client, auth_headers, db, monkeypatch,
):
    """Teacher 1 and Student 1 share the numeric subject ID but are distinct actors."""
    import models
    import push_service

    before = _database_snapshot(db)
    conversation = _message_conversation(db, models, title="گفتگوی معلم و شاگرد")
    db.add_all([
        models.ConversationParticipant(conversation_id=conversation.id, user_id=1, role="teacher"),
        models.ConversationParticipant(conversation_id=conversation.id, user_id=1, role="student"),
        models.DeviceToken(user_id=4, role="student", token="audit-message-push-student"),
    ])
    db.commit()
    db.expire_all()
    before_send = _database_snapshot(db)
    push_calls = []
    monkeypatch.setattr(
        push_service, "deliver_push",
        lambda db_arg, tokens, **kwargs: push_calls.append([token.token for token in tokens]),
    )
    body = "پیام معلم برای دانش‌آموز شماره یک"
    try:
        response = client.post(
            f"/messages/conversations/{conversation.id}/send", json={"body": body},
            headers=auth_headers["teacher"],
        )
        assert response.status_code == 200, response.text
        assert response.json() == {"message": "پیام با موفقیت ارسال شد"}
        assert len(_new_rows(db, models.Message, before_send, "messages")) == 1
        # Recipient identity is the pair (subject ID, role), so the student's
        # numeric ID collision with the sender's teacher ID does not suppress it.
        notifications = _new_rows(db, models.Notification, before_send, "notifications")
        assert len(notifications) == 1
        assert (
            notifications[0].recipient_user_id, notifications[0].recipient_role,
            notifications[0].type, notifications[0].body,
        ) == (
            4, "student", "message", f"پیام جدیدی برای شما ارسال شد: {body[:30]}...",
        )
        assert push_calls == [["audit-message-push-student"]]
    finally:
        _restore_tables(db, before)


def test_delete_message_is_soft_own_only_and_repeatable(client, auth_headers, db):
    import models
    kotlin_models = discover_models()

    before = _database_snapshot(db)
    conversation = _message_conversation(db, models, title="گفتگوی شاگرد")
    db.add(models.ConversationParticipant(
        conversation_id=conversation.id, user_id=1, role="student",
    ))
    own_message = models.Message(
        conversation_id=conversation.id, sender_id=1, sender_role="student",
        body="پیام خود شاگرد", attachment="messages/student-note.pdf",
        created_at=FIXED_NOW, is_deleted=False,
    )
    db.add(own_message)
    db.commit()
    db.refresh(own_message)
    before_delete = _database_snapshot(db)
    try:
        other_message = client.delete("/messages/1", headers=auth_headers["student"])
        assert other_message.status_code == 404
        assert other_message.json() == {"detail": "پیام یافت نشد یا شما فرستنده آن نیستید"}
        assert _database_snapshot(db) == before_delete

        wrong_role = client.delete(
            f"/messages/{own_message.id}", headers=auth_headers["parent"],
        )
        assert wrong_role.status_code == 404
        assert _database_snapshot(db) == before_delete

        deleted = client.delete(
            f"/messages/{own_message.id}", headers=auth_headers["student"],
        )
        assert deleted.status_code == 200
        assert deleted.json() == {"message": "پیام با موفقیت حذف شد"}
        assert audit_payload("SimpleResponse", deleted.json(), kotlin_models) == []
        db.expire_all()
        row = db.get(models.Message, own_message.id)
        assert row is not None
        assert (
            row.conversation_id, row.sender_id, row.sender_role, row.body,
            row.attachment, row.created_at, row.is_deleted,
        ) == (conversation.id, 1, "student", "پیام خود شاگرد", "messages/student-note.pdf", FIXED_NOW, True)
        after_first_delete = _database_snapshot(db)
        _assert_unchanged_except(before_delete, after_first_delete, "messages")

        retry = client.delete(
            f"/messages/{own_message.id}", headers=auth_headers["student"],
        )
        assert retry.status_code == 200
        assert retry.json() == {"message": "پیام با موفقیت حذف شد"}
        assert _database_snapshot(db) == after_first_delete
        history = client.get(
            f"/messages/conversations/{conversation.id}/history", headers=auth_headers["student"],
        )
        assert history.status_code == 200
        assert history.json() == []
    finally:
        _restore_tables(db, before)


def test_pin_is_per_user_role_and_set_state_is_idempotent(client, auth_headers, db):
    import models
    kotlin_models = discover_models()

    before = _database_snapshot(db)
    conversation = db.get(models.Conversation, 1)
    conversation.pinned_by = "5_parent"
    db.add(models.ConversationParticipant(
        conversation_id=1, user_id=1, role="teacher",
    ))
    db.commit()
    before_pin = _database_snapshot(db)
    try:
        request = {"pinned": True}
        assert audit_payload("PinToggleRequest", request, kotlin_models) == []
        pinned = client.post(
            "/messages/conversations/1/pin", json=request, headers=auth_headers["admin"],
        )
        assert pinned.status_code == 200
        assert pinned.json() == {"is_pinned": True}
        assert audit_payload("PinToggleResponse", pinned.json(), kotlin_models) == []
        db.expire_all()
        assert db.get(models.Conversation, 1).pinned_by == "1_admin,5_parent"
        after_admin_pin = _database_snapshot(db)

        repeated = client.post(
            "/messages/conversations/1/pin", json=request, headers=auth_headers["admin"],
        )
        assert repeated.status_code == 200
        assert repeated.json() == {"is_pinned": True}
        assert _database_snapshot(db) == after_admin_pin

        teacher_pin = client.post(
            "/messages/conversations/1/pin", json=request, headers=auth_headers["teacher"],
        )
        assert teacher_pin.status_code == 200
        assert teacher_pin.json() == {"is_pinned": True}
        db.expire_all()
        assert db.get(models.Conversation, 1).pinned_by == "1_admin,1_teacher,5_parent"

        unpinned = client.post(
            "/messages/conversations/1/pin", json={"pinned": False},
            headers=auth_headers["admin"],
        )
        assert unpinned.status_code == 200
        assert unpinned.json() == {"is_pinned": False}
        db.expire_all()
        assert db.get(models.Conversation, 1).pinned_by == "1_teacher,5_parent"
        after_transitions = _database_snapshot(db)
        _assert_unchanged_except(before_pin, after_transitions, "conversations")

        missing = client.post(
            "/messages/conversations/999999/pin", json={"pinned": True},
            headers=auth_headers["admin"],
        )
        assert missing.status_code == 404
        assert missing.json() == {"detail": "گفتگو یافت نشد"}
        outsider = client.post(
            "/messages/conversations/1/pin", json={"pinned": True},
            headers=auth_headers["student"],
        )
        assert outsider.status_code == 403
        assert outsider.json() == {"detail": "شما مجاز به تغییر وضعیت این گفتگو نیستید (IDOR)"}
        assert _database_snapshot(db) == after_transitions
    finally:
        _restore_tables(db, before)


def test_broadcast_admin_everyone_and_teacher_class_have_exact_local_fanout(
    client, auth_headers, db, monkeypatch,
):
    import models
    import push_service

    before = _database_snapshot(db)
    try:
        # Bound fan-out deterministically for the admin's `everyone` card. The
        # teacher path intentionally scopes via enrollments and can still include
        # deleted/suspended student rows; Q-029 keeps that eligibility policy open.
        db.query(models.Student).filter(~models.Student.id.in_([1, 4])).update(
            {"is_deleted": True}, synchronize_session=False,
        )
        db.query(models.Teacher).filter(models.Teacher.id != 1).update(
            {"is_deleted": True}, synchronize_session=False,
        )
        db.query(models.Student).filter(models.Student.id == 4).update(
            {"user_id": 14}, synchronize_session=False,
        )
        db.query(models.Student).filter(models.Student.id == 2).update(
            {"user_id": 12}, synchronize_session=False,
        )
        db.query(models.Student).filter(models.Student.id == 6).update(
            {"user_id": 16}, synchronize_session=False,
        )
        db.add(models.DeviceToken(
            user_id=4, role="student", token="audit-message-push-broadcast",
        ))
        db.commit()
        db.expire_all()
        before_broadcast = _database_snapshot(db)
        push_calls = []

        def fake_deliver_push(db_arg, tokens, **kwargs):
            push_calls.append({
                "tokens": [token.token for token in tokens],
                "title": kwargs.get("title"), "body": kwargs.get("body"),
                "data": kwargs.get("data"), "commit": kwargs.get("commit"),
            })

        monkeypatch.setattr(push_service, "deliver_push", fake_deliver_push)
        kotlin_models = discover_models()
        admin_body = "اطلاعیه مدیر برای همه: برنامه کلاس‌ها و آزمون هفته آینده اعلام شد."
        admin_request = {"target_type": "everyone", "target_id": None, "body": admin_body}
        assert audit_payload("BroadcastMessageRequest", admin_request, kotlin_models) == []
        admin_response = client.post(
            "/messages/broadcast", json=admin_request, headers=auth_headers["admin"],
        )
        assert admin_response.status_code == 200, admin_response.text
        assert admin_response.json() == {"message": "پیام گروهی با موفقیت ارسال شد"}
        assert audit_payload("SimpleResponse", admin_response.json(), kotlin_models) == []

        admin_conversations = _new_rows(db, models.Conversation, before_broadcast, "conversations")
        admin_messages = _new_rows(db, models.Message, before_broadcast, "messages")
        admin_notifications = _new_rows(db, models.Notification, before_broadcast, "notifications")
        assert len(admin_conversations) == len(admin_messages) == 1
        assert len(admin_notifications) == 3
        admin_conversation = admin_conversations[0]
        assert (admin_conversation.title, admin_conversation.type, admin_conversation.created_at) == (
            "اعلان عمومی", "broadcast", FIXED_NOW,
        )
        assert (
            admin_messages[0].conversation_id, admin_messages[0].sender_id,
            admin_messages[0].sender_role, admin_messages[0].body,
            admin_messages[0].created_at, admin_messages[0].is_deleted,
        ) == (admin_conversation.id, 1, "admin", admin_body, FIXED_NOW, False)
        admin_parts = db.query(models.ConversationParticipant).filter(
            models.ConversationParticipant.conversation_id == admin_conversation.id,
        ).all()
        assert {(row.user_id, row.role) for row in admin_parts} == {
            (1, "admin"), (1, "student"), (4, "student"), (1, "teacher"),
        }
        assert {
            (row.recipient_user_id, row.recipient_role, row.type, row.title, row.body,
             row.data, row.is_read, row.created_at, row.priority)
            for row in admin_notifications
        } == {
            (4, "student", "announcement", "📣 اطلاعیه کلاسی جدید", admin_body[:50], None, False, FIXED_NOW, 1),
            (14, "student", "announcement", "📣 اطلاعیه کلاسی جدید", admin_body[:50], None, False, FIXED_NOW, 1),
            (3, "teacher", "announcement", "📣 اطلاعیه کلاسی جدید", admin_body[:50], None, False, FIXED_NOW, 1),
        }
        assert len(push_calls) == 1
        assert push_calls[0]["tokens"] == ["audit-message-push-broadcast"]
        assert push_calls[0]["title"] == "📣 اطلاعیه کلاسی جدید"
        assert push_calls[0]["body"] == admin_body[:50]
        assert push_calls[0]["commit"] is False
        admin_student_notification = next(
            row for row in admin_notifications
            if row.recipient_user_id == 4 and row.recipient_role == "student"
        )
        assert push_calls[0]["data"] == {
            "type": "announcement", "notification_id": admin_student_notification.id,
        }
        after_admin_broadcast = _database_snapshot(db)
        _assert_unchanged_except(
            before_broadcast, after_admin_broadcast,
            "conversations", "conversation_participants", "messages", "notifications",
        )

        teacher_body = "اطلاعیه معلم: زمان‌بندی کلاس‌های این هفته به‌روزرسانی شد."
        teacher_request = {"target_type": "class", "target_id": None, "body": teacher_body}
        teacher_response = client.post(
            "/messages/broadcast", json=teacher_request, headers=auth_headers["teacher"],
        )
        assert teacher_response.status_code == 200, teacher_response.text
        assert teacher_response.json() == {"message": "پیام گروهی با موفقیت ارسال شد"}
        all_conversations = _new_rows(db, models.Conversation, before_broadcast, "conversations")
        all_messages = _new_rows(db, models.Message, before_broadcast, "messages")
        all_notifications = _new_rows(db, models.Notification, before_broadcast, "notifications")
        assert len(all_conversations) == len(all_messages) == 2
        assert len(all_notifications) == 7
        teacher_conversation = next(
            row for row in all_conversations if row.id != admin_conversation.id
        )
        teacher_message = next(row for row in all_messages if row.id != admin_messages[0].id)
        assert (teacher_conversation.title, teacher_conversation.type, teacher_conversation.created_at) == (
            "اعلان عمومی", "broadcast", FIXED_NOW,
        )
        assert (
            teacher_message.conversation_id, teacher_message.sender_id,
            teacher_message.sender_role, teacher_message.body,
            teacher_message.created_at, teacher_message.is_deleted,
        ) == (teacher_conversation.id, 1, "teacher", teacher_body, FIXED_NOW, False)
        teacher_parts = db.query(models.ConversationParticipant).filter(
            models.ConversationParticipant.conversation_id == teacher_conversation.id,
        ).all()
        assert {(row.user_id, row.role) for row in teacher_parts} == {
            (1, "teacher"), (1, "student"), (2, "student"), (4, "student"), (6, "student"),
        }
        teacher_notifications = [
            row for row in all_notifications if row.id not in {item.id for item in admin_notifications}
        ]
        assert {
            (row.recipient_user_id, row.recipient_role, row.type, row.title, row.body,
             row.data, row.is_read, row.created_at, row.priority)
            for row in teacher_notifications
        } == {
            (4, "student", "announcement", "📣 اطلاعیه کلاسی جدید", teacher_body[:50], None, False, FIXED_NOW, 1),
            (12, "student", "announcement", "📣 اطلاعیه کلاسی جدید", teacher_body[:50], None, False, FIXED_NOW, 1),
            (14, "student", "announcement", "📣 اطلاعیه کلاسی جدید", teacher_body[:50], None, False, FIXED_NOW, 1),
            (16, "student", "announcement", "📣 اطلاعیه کلاسی جدید", teacher_body[:50], None, False, FIXED_NOW, 1),
        }
        assert len(push_calls) == 2
        teacher_push = next(call for call in push_calls if call["body"] == teacher_body[:50])
        teacher_student_notification = next(
            row for row in teacher_notifications if row.recipient_user_id == 4
        )
        assert teacher_push == {
            "tokens": ["audit-message-push-broadcast"],
            "title": "📣 اطلاعیه کلاسی جدید", "body": teacher_body[:50],
            "data": {"type": "announcement", "notification_id": teacher_student_notification.id},
            "commit": False,
        }
        after_teacher_broadcast = _database_snapshot(db)
        _assert_unchanged_except(
            after_admin_broadcast, after_teacher_broadcast,
            "conversations", "conversation_participants", "messages", "notifications",
        )

        teacher_retry = client.post(
            "/messages/broadcast", json=teacher_request, headers=auth_headers["teacher"],
        )
        assert teacher_retry.status_code == 200
        assert teacher_retry.json() == {"message": "پیام گروهی با موفقیت ارسال شد"}
        after_teacher_retry = _database_snapshot(db)
        _assert_unchanged_except(
            after_teacher_broadcast, after_teacher_retry,
            "conversations", "conversation_participants", "messages",
        )
        assert len(_new_rows(db, models.Conversation, after_teacher_broadcast, "conversations")) == 1
        assert len(_new_rows(db, models.Message, after_teacher_broadcast, "messages")) == 1
        assert len(_new_rows(
            db, models.ConversationParticipant, after_teacher_broadcast, "conversation_participants",
        )) == 5
        assert len(_new_rows(db, models.Notification, before_broadcast, "notifications")) == 7
        # Retries create another broadcast/message but the 10-second notification
        # duplicate guard prevents another notification or mocked push delivery.
        assert len(push_calls) == 2
    finally:
        _restore_tables(db, before)


def test_broadcast_validations_and_teacher_course_ownership_are_no_write(
    client, auth_headers, db,
):
    before = _database_snapshot(db)
    for payload, status_code, detail in (
        ({"target_type": "everyone", "body": "   "}, 400, "متن پیام نمی‌تواند خالی باشد"),
        ({"target_type": "everyone"}, 422, None),
        ({"target_type": "class", "body": "بدون target"}, 400, "شناسه کلاس برای اطلاعیه آموزشگاه الزامی است"),
    ):
        response = client.post("/messages/broadcast", json=payload, headers=auth_headers["admin"])
        assert response.status_code == status_code, response.text
        if detail:
            assert response.json() == {"detail": detail}
        assert _database_snapshot(db) == before

    # Teacher 1 cannot broadcast to suspended course 3, which belongs to Teacher 2.
    forbidden = client.post(
        "/messages/broadcast",
        json={"target_type": "class", "target_id": 3, "body": "غیرمجاز"},
        headers=auth_headers["teacher"],
    )
    assert forbidden.status_code == 403
    assert forbidden.json() == {
        "detail": "شما مجاز به ارسال پیام گروهی به شاگردان کلاس دیگران نیستید (IDOR)"
    }
    missing = client.post(
        "/messages/broadcast",
        json={"target_type": "class", "target_id": 999999, "body": "کلاس ناموجود"},
        headers=auth_headers["teacher"],
    )
    assert missing.status_code == 404
    assert missing.json() == {"detail": "کلاس مورد نظر یافت نشد"}
    denied_role = client.post(
        "/messages/broadcast",
        json={"target_type": "everyone", "body": "دانش‌آموز نباید broadcast کند"},
        headers=auth_headers["student"],
    )
    assert denied_role.status_code == 403
    assert _database_snapshot(db) == before


def test_broadcast_role_target_remains_unsupported_without_writes(client, auth_headers, db):
    before = _database_snapshot(db)
    response = client.post(
        "/messages/broadcast",
        json={"target_type": "role", "target_id": None, "body": "پیام برای یک نقش"},
        headers=auth_headers["admin"],
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "نوع گیرنده پیام گروهی نامعتبر است"}
    assert _database_snapshot(db) == before


@pytest.mark.parametrize("target_type", ["not-a-target"])
def test_broadcast_rejects_unknown_target_type_without_writes(client, auth_headers, db, target_type):
    before = _database_snapshot(db)
    safe_client = TestClient(client.app, raise_server_exceptions=False)
    try:
        response = safe_client.post(
            "/messages/broadcast",
            json={"target_type": target_type, "target_id": None, "body": "پیام نامعتبر"},
            headers=auth_headers["admin"],
        )
        assert response.status_code == 400, response.text
        assert response.json() == {"detail": "نوع گیرنده پیام گروهی نامعتبر است"}
        assert _database_snapshot(db) == before
    finally:
        _restore_tables(db, before)
