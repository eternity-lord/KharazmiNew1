"""Homework parent/student scope and response-shape audit."""
from .route_registry import route_id, routes

ROUTE_IDS = [
    'POST' + ' ' + '/homework/create',
    'GET' + ' ' + '/homework/parent/child/{student_id}',
    'GET' + ' ' + '/homework/student/list',
    'POST' + ' ' + '/homework/submissions/{homework_id}/submit',
    'POST' + ' ' + '/homework/submissions/{sub_id}/grade',
    'DELETE' + ' ' + '/homework/{id}',
]


def test_homework_route_inventory_is_explicit():
    expected = {route_id(row) for row in routes() if row["handler"].split(".")[1] == 'homework'}
    assert set(ROUTE_IDS) == expected


def test_homework_parent_scope_values_and_empty_optional_contract(client, auth_headers):
    own = client.get("/homework/parent/child/1", headers=auth_headers["parent"])
    foreign = client.get("/homework/parent/child/2", headers=auth_headers["parent"])
    student = client.get("/homework/parent/child/1", headers=auth_headers["student"])
    assert own.status_code == 200, own.text
    row = next(item for item in own.json() if item["id"] == 1)
    assert row["title"] == "تمرین هفته"
    assert row["description"] == "حل تمرین"
    assert row["status"] == "submitted"
    assert row["score"] is None and row["feedback"] is None
    assert foreign.status_code == 403
    assert student.status_code == 403
    student_list = client.get("/homework/student/list", headers=auth_headers["student"])
    assert student_list.status_code == 200
    assert all("description" in item and "due_date" in item for item in student_list.json())
