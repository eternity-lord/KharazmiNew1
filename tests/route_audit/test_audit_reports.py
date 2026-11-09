"""Reports value, authorization and deterministic ordering audit."""
from .route_registry import route_id, routes

ROUTE_IDS = [
    'GET' + ' ' + '/reports/chart-data',
    'GET' + ' ' + '/reports/debtors',
    'GET' + ' ' + '/reports/debtors/excel',
    'GET' + ' ' + '/reports/financial',
    'GET' + ' ' + '/reports/financial/excel',
    'GET' + ' ' + '/reports/financial_summary',
    'GET' + ' ' + '/reports/student_profile/print',
    'GET' + ' ' + '/reports/student_statement',
    'GET' + ' ' + '/reports/student_statement/print',
]


def test_reports_route_inventory_is_explicit():
    expected = {route_id(row) for row in routes() if row["handler"].split(".")[1] == 'reports'}
    assert set(ROUTE_IDS) == expected


def test_reports_debt_oracle_statement_scope_and_chart_shape(client, auth_headers):
    headers = auth_headers["admin"]
    debtors = client.get("/reports/debtors", headers=headers)
    assert debtors.status_code == 200
    assert [(row["student_id"], row["amount"]) for row in debtors.json()] == [(1, 2_000_000), (6, 800_000)]
    assert all(row["amount"] > 0 for row in debtors.json())

    statement = client.get("/reports/student_statement", params={"student_id": 1}, headers=headers)
    assert statement.status_code == 200, statement.text
    statement_body = statement.json()
    assert statement_body["student_id"] == 1
    assert statement_body["total_paid_institute"] == 300_000
    assert statement_body["total_debt"] == 2_000_000
    assert statement_body["teachers"][0]["debt_institute"] == 700_000

    foreign = client.get("/reports/student_statement", params={"student_id": 2}, headers=auth_headers["parent"])
    assert foreign.status_code == 403
    chart = client.get("/reports/chart-data", params={
        "class_id": 1, "start_date": "1405/06/01", "end_date": "1405/06/30",
    }, headers=headers)
    assert chart.status_code == 200
    chart_body = chart.json()
    assert {"income_chart", "student_chart", "attendance_trend", "shares_chart"} == set(chart_body)
    assert chart_body["student_chart"] == [{"label": "آقا", "count": 0}, {"label": "خانم", "count": 0}]
    assert chart_body["shares_chart"] == {"teacher": 0, "institute": 300_000}
