"""CSV/export value and role audit; no real files or network are used."""
import csv
import io

from .route_registry import route_id, routes

ROUTE_IDS = [
    'GET' + ' ' + '/exports/audit_alerts',
    'GET' + ' ' + '/exports/debtors',
    'GET' + ' ' + '/exports/overdue_installments',
]


def test_exports_route_inventory_is_explicit():
    expected = {route_id(row) for row in routes() if row["handler"].split(".")[1] == 'exports'}
    assert set(ROUTE_IDS) == expected


def test_export_csv_headers_rows_and_role_guard(client, auth_headers):
    headers = auth_headers["admin"]
    debtors = client.get("/exports/debtors", headers=headers)
    overdue = client.get("/exports/overdue_installments", headers=headers)
    alerts = client.get("/exports/audit_alerts", headers=headers)
    assert debtors.status_code == overdue.status_code == alerts.status_code == 200

    debt_rows = list(csv.reader(io.StringIO(debtors.text)))
    debt_rows[0][0] = debt_rows[0][0].lstrip("\ufeff")
    assert debt_rows[0] == ["شناسه", "نام دانش‌آموز", "کد ملی", "موبایل ولی", "بدهی معلم", "بدهی آموزشگاه", "بدهی کل", "کلاس‌های فعال", "تاریخ آخرین پرداخت", "قدمت بدهی (روز)"]
    assert debt_rows[1][0] == "1"
    assert int(debt_rows[1][6]) == 2_000_000
    overdue_rows = list(csv.reader(io.StringIO(overdue.text)))
    overdue_rows[0][0] = overdue_rows[0][0].lstrip("\ufeff")
    assert overdue_rows[0][0] == "شناسه قسط"
    assert {int(row[0]) for row in overdue_rows[1:]} == {1, 2}
    assert {int(row[4]) for row in overdue_rows[1:]} == {350_000}
    alert_rows = list(csv.reader(io.StringIO(alerts.text)))
    alert_rows[0][0] = alert_rows[0][0].lstrip("\ufeff")
    assert alert_rows[0] == ["نوع", "شدت", "عنوان", "توضیحات", "شناسه موجودیت", "نام موجودیت", "زمان تشخیص"]
    assert client.get("/exports/debtors", headers=auth_headers["student"]).status_code == 403
