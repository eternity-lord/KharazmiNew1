"""Dashboard KPI and push contract audit."""
from .route_registry import route_id, routes

ROUTE_IDS = [
    'GET' + ' ' + '/dashboard/kpis',
    'GET' + ' ' + '/dashboard/push_status',
]


def test_dashboard_route_inventory_is_explicit():
    expected = {route_id(row) for row in routes() if row["handler"].split(".")[1] == 'dashboard'}
    assert set(ROUTE_IDS) == expected


def test_dashboard_kpis_have_independent_seed_values_and_push_is_local(client, auth_headers):
    import routers.dashboard as dashboard

    dashboard._clear_dashboard_cache()
    response = client.get("/dashboard/kpis", headers=auth_headers["admin"])
    assert response.status_code == 200, response.text
    assert response.json() == {
        "today_revenue": 0,
        "total_overdue_amount": 700_000,
        "overdue_installments_count": 2,
        "active_students_count": 29,
        "suspicious_alerts_count": 0,
        "dunning_pending_count": 2,
    }
    push = client.get("/dashboard/push_status", headers=auth_headers["admin"])
    assert push.status_code == 200
    assert push.json() == {"fcm_configured": False, "device_token_count": 0}
    assert "private_key" not in push.text and "api_key" not in push.text


def test_today_summary_excludes_reversed_institute_cash(client, auth_headers, db):
    """Independent oracle: reversing a 111,111 receipt leaves today's cash total unchanged."""
    import models

    before = client.get("/admin/today_summary", headers=auth_headers["admin"])
    assert before.status_code == 200, before.text
    baseline = before.json()["today_payments"]
    reversed_receipt = models.Transaction(
        student_id=1, enrollment_id=1, course_id=1, branch_id=1,
        amount=111_111, payment_method="نقدی", tracking_code="AUD-REVERSED-TODAY",
        date="1405/07/06", receiver="آموزشگاه", description="وصول برگشتی ممیزی",
        type="deposit", target_wallet="institute", share_teacher=0,
        share_institute=111_111, is_deleted=False, is_reversed=True,
    )
    db.add(reversed_receipt)
    db.commit()
    try:
        after = client.get("/admin/today_summary", headers=auth_headers["admin"])
        assert after.status_code == 200, after.text
        assert after.json()["today_payments"] == baseline
    finally:
        db.delete(reversed_receipt)
        db.commit()
