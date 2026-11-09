"""Value, access-control, optimistic-lock and empty/filter audit for students."""
from __future__ import annotations

from .route_registry import route_id, routes

ROUTE_IDS = [
    'POST' + ' ' + '/admin/students/{id}/send_portal_link',
    'POST' + ' ' + '/grades/submit',
    'GET' + ' ' + '/students/my_profile',
    'POST' + ' ' + '/students/register',
    'POST' + ' ' + '/students/register_and_enroll',
    'GET' + ' ' + '/students/search',
    'GET' + ' ' + '/students/search_simple',
    'PUT' + ' ' + '/students/update/{student_id}',
    'POST' + ' ' + '/students/{id}/upload_photo',
    'GET' + ' ' + '/students/{student_id}',
    'GET' + ' ' + '/students/{student_id}/communication_history',
    'GET' + ' ' + '/students/{student_id}/grades',
    'GET' + ' ' + '/students/{student_id}/installments',
]


def test_students_route_inventory_is_explicit():
    expected = {route_id(row) for row in routes() if row["handler"].split(".")[1] == 'students'}
    assert set(ROUTE_IDS) == expected


def test_student_profile_grade_oracle_access_and_optimistic_conflict(client, auth_headers, db):
    import models

    profile = client.get("/students/my_profile", headers=auth_headers["student"])
    assert profile.status_code == 200, profile.text
    body = profile.json()
    assert body["info"]["name"] == "دانش‌آموز تست 1"
    assert body["wallet"]["total_debt"] == 2_000_000
    assert body["averages"]["ریاضی پایه فعال"] == 18.5
    assert {item["exam_title"] for item in body["grades"]} == {"میان‌ترم"}

    own = client.get("/students/1", headers=auth_headers["parent"])
    foreign = client.get("/students/2", headers=auth_headers["parent"])
    assert own.status_code == 200 and own.json()["id"] == 1
    assert foreign.status_code == 403
    assert client.get("/students/1/grades", headers=auth_headers["parent"]).json()["averages"] == {"ریاضی پایه فعال": 18.5}

    assert client.get("/students/search_simple", params={"query": "x"}, headers=auth_headers["admin"]).json() == []
    assert client.get("/students/search_simple", params={"query": "دانش‌آموز"}, headers=auth_headers["student"]).status_code == 403

    student = db.get(models.Student, 6)
    original_last_name = student.last_name
    original_version = student.version or 1
    stale = client.put(
        "/students/update/6",
        json={"last_name": "نباید ذخیره شود", "version": original_version - 1},
        headers=auth_headers["admin"],
    )
    assert stale.status_code == 409
    db.expire_all()
    assert db.get(models.Student, 6).last_name == original_last_name

    updated = client.put(
        "/students/update/6",
        json={"last_name": "نام موقت ممیزی", "version": original_version},
        headers=auth_headers["admin"],
    )
    assert updated.status_code == 200, updated.text
    db.expire_all()
    assert db.get(models.Student, 6).last_name == "نام موقت ممیزی"
    db.get(models.Student, 6).last_name = original_last_name
    db.get(models.Student, 6).version = original_version
    db.commit()
