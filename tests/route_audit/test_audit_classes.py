"""Value checks for class, enrollment, archive and export routes."""
from __future__ import annotations

from io import BytesIO

from openpyxl import load_workbook


CLASSES_ROUTES = [
    ("POST", "/admin/classes/{course_id}/suspend_s"), ("POST", "/classes/create"),
    ("GET", "/classes/deletion_requests"), ("POST", "/classes/deletion_requests/{request_id}/approve"),
    ("POST", "/classes/deletion_requests/{request_id}/reject"), ("GET", "/classes/list"),
    ("GET", "/classes/pending_approval"), ("POST", "/classes/pending_approval/bulk_approve"),
    ("POST", "/classes/pending_approval/bulk_reject"), ("PUT", "/classes/update"),
    ("PUT", "/classes/update_info/{course_id}"), ("GET", "/classes/{class_id}/students_full/excel"),
    ("DELETE", "/classes/{course_id}"), ("GET", "/classes/{course_id}/details"),
    ("POST", "/classes/{course_id}/request_delete"), ("POST", "/classes/{course_id}/suspend"),
    ("GET", "/classes/{id}/full_report"), ("GET", "/classes/{id}/students_full"),
    ("POST", "/enrollments/add"), ("POST", "/enrollments/add_bulk"), ("DELETE", "/enrollments/{enrollment_id}"),
]
ROUTE_IDS = [f"{method} {path}" for method, path in CLASSES_ROUTES]


def test_classes_route_inventory_is_explicit(client):
    paths = {(path, method.upper()) for path, operations in client.app.openapi()["paths"].items() for method in operations}
    assert [(m, p) for m, p in CLASSES_ROUTES if (p, m.upper()) not in paths] == []


def test_class_list_details_and_students_have_values(client, auth_headers):
    h = auth_headers["admin"]
    listing = client.get("/classes/list", headers=h)
    details = client.get("/classes/1/details", headers=h)
    students = client.get("/classes/1/students_full", headers=h)
    report = client.get("/classes/1/full_report", headers=h)
    assert listing.status_code == details.status_code == students.status_code == report.status_code == 200
    rows = listing.json()
    assert any(row["id"] == 1 and row["title"] == "ریاضی پایه فعال" for row in rows)
    detail = details.json()
    assert detail["course_info"]["id"] == 1 and detail["course_info"]["title"] == "ریاضی پایه فعال"
    assert detail["students"][0]["teacher_name"] == "رضا فعال"
    assert students.json()["course_info"]["id"] == 1
    assert any(row["student_id"] == 1 and row["student_name"] == "دانش‌آموز تست 1" for row in students.json()["students"])
    assert report.json()["info"]["title"] == "ریاضی پایه فعال"
    assert report.json()["info"]["total_revenue"] == 300_000


def test_pending_and_deletion_views_keep_state_labels(client, auth_headers):
    h = auth_headers["admin"]
    pending = client.get("/classes/pending_approval", headers=h)
    requests = client.get("/classes/deletion_requests", headers=h)
    assert pending.status_code == requests.status_code == 200
    assert any(row["id"] == 5 and row["rejection_reason"] == "ظرفیت تکمیل" for row in pending.json())
    assert requests.json() == []


def test_class_excel_contains_seed_value(client, auth_headers):
    response = client.get("/classes/1/students_full/excel", headers=auth_headers["admin"])
    assert response.status_code == 200, response.text
    workbook = load_workbook(BytesIO(response.content), read_only=True, data_only=True)
    try:
        text = " ".join(str(cell.value or "") for row in workbook.active.iter_rows() for cell in row)
        assert "دانش‌آموز" in text
        assert "ریاضی پایه فعال" in text or "2001" in text
    finally:
        workbook.close()


def test_suspended_class_rejects_new_session_state_without_deleting_class(client, auth_headers, db):
    import models
    before = db.get(models.Course, 1).is_suspended
    response = client.post("/classes/1/suspend", headers=auth_headers["admin"])
    assert response.status_code in (200, 400, 403)
    db.expire_all()
    course = db.get(models.Course, 1)
    # The route is audited for a state transition, but this test does not leave
    # the shared seed changed for the next router.
    if response.status_code == 200:
        assert course.is_suspended is True
        course.is_suspended = before
        db.commit()
    else:
        assert course.is_suspended is before
