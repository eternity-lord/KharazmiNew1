"""Analytics value, date-range, filter and paging audit."""
from .route_registry import route_id, routes

ROUTE_IDS = [
    'GET' + ' ' + '/analytics/classes',
    'GET' + ' ' + '/analytics/dashboard',
    'GET' + ' ' + '/analytics/enrollment_funnel',
    'GET' + ' ' + '/analytics/export/excel',
    'GET' + ' ' + '/analytics/export/pdf',
    'GET' + ' ' + '/analytics/teachers',
]


def test_analytics_route_inventory_is_explicit():
    expected = {route_id(row) for row in routes() if row["handler"].split(".")[1] == 'analytics'}
    assert set(ROUTE_IDS) == expected


def test_analytics_custom_oracle_filter_and_limit_order(client, auth_headers):
    headers = auth_headers["admin"]
    dashboard = client.get(
        "/analytics/dashboard",
        params={"time_filter": "Custom", "start_date": "1405/06/01", "end_date": "1405/06/30", "branch_id": 1},
        headers=headers,
    )
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json() == {
        "period": {"start": "1405/06/01", "end": "1405/06/30", "filter": "Custom"},
        "active_students": 5,
        "new_registrations": 6,
        "retention_rate": 20.0,
        "attendance_rate": 33.3,
        "average_grade": 15.5,
        "outstanding_debt": 2_000_000,
        "monthly_revenue": 0,
        "total_turnover": 1_175_000,
        "lead_conversion_rate": 100.0,
        "payment_collection_rate": 58.8,
    }
    classes = client.get("/analytics/classes", params={"limit": 1, "offset": 0}, headers=headers)
    teachers = client.get("/analytics/teachers", params={"limit": 1, "offset": 0}, headers=headers)
    assert classes.status_code == teachers.status_code == 200
    assert classes.json() == [{
        "course_id": 1, "course_code": "C-ACTIVE", "title": "ریاضی پایه فعال",
        "student_count": 4, "average_grade": 15.5, "attendance_rate": 33.3,
    }]
    assert teachers.json()[0]["teacher_id"] == 1
    assert teachers.json()[0]["student_count"] == 5
    assert teachers.json()[0]["wallet_balance"] == 300_000

    funnel = client.get("/analytics/enrollment_funnel", params={
        "start_date": "1405/06/01", "end_date": "1405/07/30", "branch_id": 1,
    }, headers=headers)
    assert funnel.status_code == 200
    assert funnel.json()["total_leads"] == 1
    assert funnel.json()["converted_leads"] == 0
    assert funnel.json()["conversion_rate"] == 0.0
    bad_range = client.get("/analytics/enrollment_funnel", params={
        "start_date": "1405/07/01", "end_date": "1405/06/01", "branch_id": 1,
    }, headers=headers)
    bad_date = client.get("/analytics/enrollment_funnel", params={
        "start_date": "not-a-date", "end_date": "1405/06/01", "branch_id": 1,
    }, headers=headers)
    assert bad_range.status_code == bad_date.status_code == 400
