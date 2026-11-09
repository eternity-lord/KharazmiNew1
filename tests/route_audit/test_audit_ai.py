"""Value, per-role tool payload, state and read-only audit for the AI route."""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from .route_registry import route_id, routes

ROUTE_IDS = [
    'POST' + ' ' + '/ai/chat',
]


def _table_counts(db):
    import models

    return {
        table.name: db.execute(select(func.count()).select_from(table)).scalar_one()
        for table in models.Base.metadata.sorted_tables
    }


class _RecordingProvider:
    def __init__(self):
        self.calls = []

    def generate_response(self, role, user_message, conversation_history, tools_data):
        self.calls.append({
            "role": role,
            "user_message": user_message,
            "conversation_history": list(conversation_history),
            "tools_data": dict(tools_data),
        })
        return "پاسخ قطعی ممیزی", "HUMAN_CONFIRMATION_REQUIRED"


def test_ai_route_inventory_is_explicit():
    expected = {route_id(row) for row in routes() if row["handler"].split(".")[1] == 'ai'}
    assert set(ROUTE_IDS) == expected


def test_ai_admin_revenue_response_uses_seeded_financial_values_without_writes(client, auth_headers, db, monkeypatch):
    import models
    import routers.ai as ai

    # Independent row arithmetic, not the AI endpoint's aggregations/helpers.
    expected_revenue = sum(
        int(row.amount or 0)
        for row in db.query(models.Transaction).filter(
            models.Transaction.type == "deposit",
            models.Transaction.is_deleted == False,
            models.Transaction.is_reversed == False,
        ).all()
    )
    from .oracle import build_oracle

    oracle = build_oracle(db)
    expected_debt = sum(oracle.student_due.values())
    expected_debtors = sum(value > 0 for value in oracle.student_due.values())
    before = _table_counts(db)
    monkeypatch.setattr(ai, "chat_conversations_in_memory", {})

    response = client.post("/ai/chat", json={"message": "گزارش درآمد"}, headers=auth_headers["admin"])
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["role"] == "admin"
    assert payload["suggested_action"] == "SEND_DEBT_REMINDERS"
    assert "[نسخه‌ی آزمایشی" in payload["response"]
    assert f"{expected_revenue:,} تومان" in payload["response"]
    assert f"{expected_debt:,} تومان" in payload["response"]
    assert expected_revenue == 1_250_000
    assert expected_debt == 3_850_000
    assert expected_debtors == 3
    history = ai.chat_conversations_in_memory["admin_1"]
    assert history == [{"user": "گزارش درآمد"}, {"assistant": payload["response"]}]
    db.expire_all()
    assert _table_counts(db) == before


@pytest.mark.parametrize(
    "role,message,request_fields,expected_tools",
    [
        (
            "teacher", "ضعف‌های کلاس", {"course_id": 1},
            {"class_summary": {"course_title": "ریاضی پایه فعال", "code": "C-ACTIVE"}},
        ),
        (
            "student", "برنامه درسی", {"student_id": 1},
            {
                "student_summary": {"first_name": "دانش‌آموز", "last_name": "تست 1", "student_code": 2001},
                "student_attendance": {"total_sessions": 2, "presents": 2, "attendance_rate": 100.0},
                "student_grades": {"average_grade": 18.5},
                "student_finance": {"wallet_teacher": -10_000, "wallet_institute": 5_000},
            },
        ),
        (
            "parent", "وضعیت فرزند", {"student_id": 1},
            {
                "student_summary": {"first_name": "دانش‌آموز", "last_name": "تست 1", "student_code": 2001},
                "student_attendance": {"total_sessions": 2, "presents": 2, "attendance_rate": 100.0},
                "student_grades": {"average_grade": 18.5},
                "student_finance": {"wallet_teacher": -10_000, "wallet_institute": 5_000},
            },
        ),
    ],
)
def test_ai_role_tool_values_are_passed_to_provider_without_database_side_effects(
    client, auth_headers, db, monkeypatch, role, message, request_fields, expected_tools
):
    import routers.ai as ai

    provider = _RecordingProvider()
    monkeypatch.setattr(ai, "active_ai_provider", provider)
    monkeypatch.setattr(ai, "chat_conversations_in_memory", {})
    before = _table_counts(db)

    response = client.post("/ai/chat", json={"message": message, **request_fields}, headers=auth_headers[role])
    assert response.status_code == 200, response.text
    assert response.json() == {
        "status": "success",
        "response": "پاسخ قطعی ممیزی",
        "role": role,
        "suggested_action": "HUMAN_CONFIRMATION_REQUIRED",
    }
    assert provider.calls == [{
        "role": role,
        "user_message": message,
        "conversation_history": [],
        "tools_data": expected_tools,
    }]
    session_user_ids = {"teacher": 3, "parent": 5, "student": 4}
    key = f"{role}_{session_user_ids[role]}"
    assert ai.chat_conversations_in_memory[key] == [
        {"user": message}, {"assistant": "پاسخ قطعی ممیزی"}
    ]
    db.expire_all()
    assert _table_counts(db) == before


def test_ai_invalid_request_does_not_call_provider_or_mutate_history(client, auth_headers, monkeypatch):
    import routers.ai as ai

    provider = _RecordingProvider()
    monkeypatch.setattr(ai, "active_ai_provider", provider)
    monkeypatch.setattr(ai, "chat_conversations_in_memory", {})

    response = client.post("/ai/chat", json={"student_id": "not-an-integer"}, headers=auth_headers["admin"])
    assert response.status_code == 422
    assert provider.calls == []
    assert ai.chat_conversations_in_memory == {}


def test_ai_conversation_history_stays_bounded_to_fifteen_messages(client, auth_headers, monkeypatch):
    """A two-message turn should not make the source's documented history cap grow forever."""
    import routers.ai as ai

    provider = _RecordingProvider()
    monkeypatch.setattr(ai, "active_ai_provider", provider)
    monkeypatch.setattr(ai, "chat_conversations_in_memory", {})

    for turn in range(20):
        response = client.post(
            "/ai/chat", json={"message": f"مکالمه {turn}"}, headers=auth_headers["admin"]
        )
        assert response.status_code == 200, response.text
    history = ai.chat_conversations_in_memory["admin_1"]
    assert len(history) == 15
    assert all(len(call["conversation_history"]) <= 15 for call in provider.calls)
    assert history[-2:] == [{"user": "مکالمه 19"}, {"assistant": "پاسخ قطعی ممیزی"}]
