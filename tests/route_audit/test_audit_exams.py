"""Exam list/attempt state and Android response-shape audit."""
from .route_registry import route_id, routes

ROUTE_IDS = [
    'POST' + ' ' + '/exams/attempts/{attempt_id}/submit',
    'POST' + ' ' + '/exams/attempts/{exam_id}/start',
    'POST' + ' ' + '/exams/create',
    'GET' + ' ' + '/exams/student/list',
    'POST' + ' ' + '/exams/{id}/questions',
    'GET' + ' ' + '/students/{student_id}/report_card',
    'GET' + ' ' + '/students/{student_id}/report_card/pdf',
]


def test_exams_route_inventory_is_explicit():
    expected = {route_id(row) for row in routes() if row["handler"].split(".")[1] == 'exams'}
    assert set(ROUTE_IDS) == expected


def test_exam_list_shape_and_attempt_retry_state(client, auth_headers, db):
    import models

    listed = client.get("/exams/student/list", headers=auth_headers["student"])
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert {row["id"] for row in rows} == {1}  # Only published exams are student-visible (O-12 fixed).
    assert all(row["description"] == "" and row["due_date"] == "" for row in rows)
    assert next(row for row in rows if row["id"] == 1)["status"] == "attempted"

    started = client.post("/exams/attempts/2/start", headers=auth_headers["student"])
    assert started.status_code == 200, started.text
    assert started.json()["duration"] == 45
    assert started.json()["questions"] == []
    attempt_id = started.json()["attempt_id"]
    retry_start = client.post("/exams/attempts/2/start", headers=auth_headers["student"])
    assert retry_start.status_code == 400
    assert db.get(models.ExamAttempt, attempt_id).submitted_at is None

    # Cleanup the newly-created attempt; the canonical seed remains unchanged.
    db.delete(db.get(models.ExamAttempt, attempt_id))
    db.commit()
    assert client.post("/exams/attempts/2/start", headers=auth_headers["parent"]).status_code == 403
