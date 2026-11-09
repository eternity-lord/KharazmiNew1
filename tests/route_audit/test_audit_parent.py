"""Parent portal value, child scope and HTML contract audit."""
from .route_registry import route_id, routes

ROUTE_IDS = [
    'GET' + ' ' + '/parent/child_profile',
    'POST' + ' ' + '/parent/login',
    'GET' + ' ' + '/parent/portal',
    'POST' + ' ' + '/parent/request_otp',
    'POST' + ' ' + '/parent/select_child',
]


def test_parent_route_inventory_is_explicit():
    expected = {route_id(row) for row in routes() if row["handler"].split(".")[1] == 'parent'}
    assert set(ROUTE_IDS) == expected


def test_parent_child_profile_exact_values_and_no_real_sms(client, auth_headers, db):
    import models

    before_sms = db.query(models.SmsLog).count()
    profile = client.get("/parent/child_profile", headers=auth_headers["parent"])
    assert profile.status_code == 200, profile.text
    body = profile.json()
    assert body["info"]["name"] == "دانش‌آموز تست 1"
    assert body["wallet"]["total_debt"] == 2_000_000
    assert body["averages"]["ریاضی پایه فعال"] == 18.5
    assert {item["exam_title"] for item in body["grades"]} == {"میان‌ترم"}
    assert db.query(models.SmsLog).count() == before_sms

    page = client.get("/parent/portal", headers=auth_headers["parent"])
    assert page.status_code == 200
    assert "پورتال" in page.text or "portal" in page.text.lower()
    assert client.get("/parent/child_profile", headers=auth_headers["student"]).status_code == 401
