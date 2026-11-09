"""Temporary-database behavior audit for branch and resource endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import and_, delete, insert, select, update
import pytest

from .route_registry import route_id, routes

ROUTE_IDS = [
    "GET /branches",
    "POST /branches",
    "PUT /branches/{branch_id}",
    "POST /branches/{branch_id}/suspend",
    "GET /dashboard/branch_stats",
    "GET /resources",
    "POST /resources",
    "POST /resources/bookings",
    "PUT /resources/{id}",
]


def _database_snapshot(db):
    import models

    result = {}
    for table in models.Base.metadata.sorted_tables:
        statement = select(table)
        primary_key = list(table.primary_key.columns)
        if primary_key:
            statement = statement.order_by(*primary_key)
        result[table.name] = [tuple(row) for row in db.execute(statement).all()]
    return result


def _assert_unchanged_except(before, after, *changed_tables):
    assert set(before) == set(after)
    allowed = set(changed_tables)
    for table_name in before:
        if table_name not in allowed:
            assert after[table_name] == before[table_name], table_name


def _restore_tables(db, before, *model_names):
    """Restore selected ORM tables to their exact pre-test row sets."""
    import models

    db.rollback()
    db.expire_all()
    for model_name in model_names:
        table = getattr(models, model_name).__table__
        columns = list(table.columns)
        column_names = [column.name for column in columns]
        primary_keys = list(table.primary_key.columns)
        key_indexes = [column_names.index(column.name) for column in primary_keys]
        baseline_rows = before[table.name]
        baseline = {tuple(row[index] for index in key_indexes): row for row in baseline_rows}
        current_rows = [tuple(row) for row in db.execute(select(table)).all()]
        current = {tuple(row[index] for index in key_indexes): row for row in current_rows}

        for key in current.keys() - baseline.keys():
            predicate = and_(*(column == value for column, value in zip(primary_keys, key)))
            db.execute(delete(table).where(predicate))

        for key, row in baseline.items():
            predicate = and_(*(column == value for column, value in zip(primary_keys, key)))
            values = dict(zip(column_names, row))
            if key in current:
                non_primary_values = {
                    name: value for name, value in values.items()
                    if name not in {column.name for column in primary_keys}
                }
                db.execute(update(table).where(predicate).values(**non_primary_values))
            else:
                db.execute(insert(table).values(**values))
        db.flush()
    db.commit()
    db.expire_all()
    assert _database_snapshot(db) == before


def _assert_route_error(response, status, detail):
    assert response.status_code == status, response.text
    assert response.json() == {"detail": detail}


def _resource_row(resource):
    return {
        "id": resource.id,
        "name": resource.name,
        "type": resource.type,
        "serial_code": resource.serial_code,
        "branch_id": resource.branch_id,
        "active": resource.active,
    }


def test_branches_route_inventory_is_explicit(client):
    actual = {route_id(row) for row in routes() if row["handler"].split(".")[1] == "branches"}
    assert set(ROUTE_IDS) == actual
    openapi_routes = {
        (method.upper(), path)
        for path, methods in client.app.openapi()["paths"].items()
        for method in methods
    }
    assert all(tuple(route.split(" ", 1)) in openapi_routes for route in ROUTE_IDS)


def test_branch_create_duplicate_and_list_values_are_exact(client, auth_headers, db):
    import models

    before = _database_snapshot(db)
    request = {
        "name": "شعبهٔ ممیزی جدید",
        "address": "خیابان آزمایش",
        "phone": "02155550100",
        "manager": "مدیر ممیزی",
    }
    try:
        created = client.post("/branches", json=request, headers=auth_headers["admin"])
        assert created.status_code == 200, created.text
        payload = created.json()
        assert set(payload) == {"status", "message", "branch_id"}
        assert payload["status"] == "success"
        assert payload["message"] == "شعبه جدید با موفقیت ایجاد شد"

        db.expire_all()
        branch = db.get(models.Branch, payload["branch_id"])
        assert branch is not None
        assert (branch.name, branch.address, branch.phone, branch.manager, branch.active) == (
            request["name"], request["address"], request["phone"], request["manager"], True,
        )
        after_create = _database_snapshot(db)
        _assert_unchanged_except(before, after_create, "branches")
        assert len(after_create["branches"]) == len(before["branches"]) + 1

        listed = client.get("/branches", headers=auth_headers["admin"])
        assert listed.status_code == 200, listed.text
        values = listed.json()
        assert len(values) == 3
        assert {row["id"] for row in values} == {1, 2, branch.id}
        listed_branch = next(row for row in values if row["id"] == branch.id)
        assert set(listed_branch) == {"id", "name", "address", "phone", "manager", "active"}
        assert listed_branch == {
            "id": branch.id,
            "name": request["name"],
            "address": request["address"],
            "phone": request["phone"],
            "manager": request["manager"],
            "active": True,
        }
        assert _database_snapshot(db) == after_create

        duplicate = client.post("/branches", json=request, headers=auth_headers["admin"])
        _assert_route_error(duplicate, 400, "شعبه‌ای با این نام قبلاً ثبت شده است")
        assert _database_snapshot(db) == after_create

        missing_name = client.post(
            "/branches", json={"address": "بدون نام"}, headers=auth_headers["admin"],
        )
        assert missing_name.status_code == 422, missing_name.text
        assert _database_snapshot(db) == after_create
    finally:
        _restore_tables(db, before, "Branch")


def test_branch_update_suspend_toggle_missing_ids_and_exact_rows(client, auth_headers, db):
    import models

    before = _database_snapshot(db)
    request = {
        "name": "شعبه مرکزی ویرایش‌شده",
        "address": "نشانی تازه",
        "phone": "02155550200",
        "manager": "مدیر دوم",
        "active": False,
    }
    try:
        response = client.put("/branches/1", json=request, headers=auth_headers["admin"])
        assert response.status_code == 200, response.text
        assert response.json() == {"status": "success", "message": "اطلاعات شعبه با موفقیت بروزرسانی شد"}
        db.expire_all()
        branch = db.get(models.Branch, 1)
        assert (branch.name, branch.address, branch.phone, branch.manager, branch.active) == (
            request["name"], request["address"], request["phone"], request["manager"], False,
        )
        after_update = _database_snapshot(db)
        _assert_unchanged_except(before, after_update, "branches")

        missing_update = client.put(
            "/branches/999999", json=request, headers=auth_headers["admin"],
        )
        _assert_route_error(missing_update, 404, "شعبه یافت نشد")
        assert _database_snapshot(db) == after_update

        # Characterize current behavior while Q-019 leaves repeat semantics open:
        # the route toggles state, so the second identical call reactivates it.
        first_toggle = client.post("/branches/1/suspend", headers=auth_headers["admin"])
        assert first_toggle.status_code == 200
        assert first_toggle.json() == {
            "status": "success",
            "message": "شعبه با موفقیت به وضعیت 'فعال' تغییر یافت",
        }
        db.expire_all()
        assert db.get(models.Branch, 1).active is True
        after_first_toggle = _database_snapshot(db)
        _assert_unchanged_except(after_update, after_first_toggle, "branches")

        repeated_toggle = client.post("/branches/1/suspend", headers=auth_headers["admin"])
        assert repeated_toggle.status_code == 200
        assert repeated_toggle.json() == {
            "status": "success",
            "message": "شعبه با موفقیت به وضعیت 'غیرفعال (تعلیق)' تغییر یافت",
        }
        db.expire_all()
        assert db.get(models.Branch, 1).active is False
        after_second_toggle = _database_snapshot(db)
        _assert_unchanged_except(after_first_toggle, after_second_toggle, "branches")

        missing_suspend = client.post("/branches/999999/suspend", headers=auth_headers["admin"])
        _assert_route_error(missing_suspend, 404, "شعبه یافت نشد")
        assert _database_snapshot(db) == after_second_toggle
    finally:
        _restore_tables(db, before, "Branch")


def test_branch_stats_use_exact_seed_counts_and_branch_deposit_totals(client, auth_headers, db):
    import models

    before = _database_snapshot(db)
    db.add_all([
        models.Transaction(
            branch_id=1, amount=700_000, type="deposit", is_deleted=False,
            payment_method="کارت", tracking_code="BR-AUD-1", date="1405/07/01",
            receiver="آموزشگاه", description="branch one deposit",
        ),
        models.Transaction(
            branch_id=1, amount=900_000, type="deposit", is_deleted=True,
            payment_method="کارت", tracking_code="BR-AUD-2", date="1405/07/01",
            receiver="آموزشگاه", description="archived deposit decoy",
        ),
        models.Transaction(
            branch_id=1, amount=50_000, type="reversal", is_deleted=False,
            payment_method="کارت", tracking_code="BR-AUD-3", date="1405/07/01",
            receiver="آموزشگاه", description="reversal decoy", is_reversed=True,
        ),
        models.Transaction(
            branch_id=2, amount=200_000, type="deposit", is_deleted=False,
            payment_method="نقدی", tracking_code="BR-AUD-4", date="1405/07/01",
            receiver="آموزشگاه", description="branch two deposit",
        ),
    ])
    db.commit()
    before_reads = _database_snapshot(db)
    try:
        one = client.get("/dashboard/branch_stats", params={"branch_id": 1}, headers=auth_headers["admin"])
        assert one.status_code == 200, one.text
        assert one.json() == {
            "branch_id": 1,
            "branch_name": "شعبه مرکزی تست",
            "statistics": {
                "student_count": 15,
                "teacher_count": 2,
                "class_count": 4,
                "total_revenue": 700_000,
                "attendance_sessions_count": 3,
            },
        }

        two = client.get("/dashboard/branch_stats", params={"branch_id": 2}, headers=auth_headers["admin"])
        assert two.status_code == 200, two.text
        assert two.json() == {
            "branch_id": 2,
            "branch_name": "شعبه غرب تست",
            "statistics": {
                "student_count": 14,
                "teacher_count": 0,
                "class_count": 2,
                "total_revenue": 200_000,
                "attendance_sessions_count": 0,
            },
        }

        summary = client.get("/dashboard/branch_stats", headers=auth_headers["admin"])
        assert summary.status_code == 200, summary.text
        aggregate = summary.json()
        assert set(aggregate) == {
            "revenue_by_branch", "students_by_branch", "teachers_by_branch",
            "classes_by_branch", "attendance_by_branch",
        }
        for key, metric in (
            ("revenue_by_branch", "amount"),
            ("students_by_branch", "count"),
            ("teachers_by_branch", "count"),
            ("classes_by_branch", "count"),
            ("attendance_by_branch", "count"),
        ):
            assert {row["branch_id"]: row[metric] for row in aggregate[key]} == {
                1: {"amount": 700_000, "count": 15 if key == "students_by_branch" else 2 if key == "teachers_by_branch" else 4 if key == "classes_by_branch" else 3}[metric],
                2: {"amount": 200_000, "count": 14 if key == "students_by_branch" else 0 if key == "teachers_by_branch" else 2 if key == "classes_by_branch" else 0}[metric],
            }
        assert {row["branch_id"]: row["branch_name"] for row in aggregate["revenue_by_branch"]} == {
            1: "شعبه مرکزی تست", 2: "شعبه غرب تست",
        }

        missing = client.get("/dashboard/branch_stats", params={"branch_id": 999999}, headers=auth_headers["admin"])
        _assert_route_error(missing, 404, "شعبه مورد نظر یافت نشد")
        assert _database_snapshot(db) == before_reads
    finally:
        _restore_tables(db, before, "Transaction", "FinancialAuditLog")


def test_resource_create_duplicate_empty_and_branch_filtered_lists(client, auth_headers, db):
    import models

    before = _database_snapshot(db)
    try:
        empty = client.get("/resources", headers=auth_headers["admin"])
        assert empty.status_code == 200 and empty.json() == []
        assert _database_snapshot(db) == before

        first_request = {
            "name": "پروژکتور ممیزی",
            "type": "projector",
            "serial_code": "AUD-RES-1",
            "branch_id": 1,
        }
        first = client.post("/resources", json=first_request, headers=auth_headers["admin"])
        assert first.status_code == 200, first.text
        assert first.json()["status"] == "success"
        assert first.json()["message"] == "منبع جدید با موفقیت ثبت شد"
        first_id = first.json()["resource_id"]

        second_request = {
            "name": "تجهیز غیرفعال",
            "type": "equipment",
            "serial_code": "AUD-RES-2",
            "branch_id": 2,
        }
        second = client.post("/resources", json=second_request, headers=auth_headers["admin"])
        assert second.status_code == 200, second.text
        second_id = second.json()["resource_id"]
        db.query(models.Resource).filter(models.Resource.id == second_id).update({"active": False})
        db.commit()
        db.expire_all()

        after_create = _database_snapshot(db)
        _assert_unchanged_except(before, after_create, "resources")
        resource_one = db.get(models.Resource, first_id)
        resource_two = db.get(models.Resource, second_id)
        assert _resource_row(resource_one) == {
            "id": first_id, **first_request, "active": True,
        }
        assert _resource_row(resource_two) == {
            "id": second_id, **second_request, "active": False,
        }

        duplicate = client.post("/resources", json=first_request, headers=auth_headers["admin"])
        _assert_route_error(duplicate, 400, "منبعی با این کد سریال قبلاً ثبت شده است")
        assert _database_snapshot(db) == after_create

        missing_serial = client.post(
            "/resources", json={"name": "serial missing", "type": "board"},
            headers=auth_headers["admin"],
        )
        assert missing_serial.status_code == 422, missing_serial.text
        assert _database_snapshot(db) == after_create

        all_resources = client.get("/resources", headers=auth_headers["admin"])
        branch_one = client.get("/resources", params={"branch_id": 1}, headers=auth_headers["admin"])
        branch_two = client.get("/resources", params={"branch_id": 2}, headers=auth_headers["admin"])
        empty_branch = client.get("/resources", params={"branch_id": 999999}, headers=auth_headers["admin"])
        assert all(response.status_code == 200 for response in (all_resources, branch_one, branch_two, empty_branch))
        assert {row["id"] for row in all_resources.json()} == {first_id, second_id}
        assert branch_one.json() == [_resource_row(resource_one)]
        assert branch_two.json() == [_resource_row(resource_two)]
        assert empty_branch.json() == []
        assert _database_snapshot(db) == after_create
    finally:
        _restore_tables(db, before, "Resource")


def test_resource_update_replaces_fields_and_missing_is_no_write(client, auth_headers, db):
    import models

    before = _database_snapshot(db)
    resource = models.Resource(
        name="ישן", type="board", serial_code="AUD-UPD-1", branch_id=1, active=True,
    )
    db.add(resource)
    db.commit()
    db.expire_all()
    before_update = _database_snapshot(db)
    request = {
        "name": "تختهٔ ویرایش‌شده",
        "type": "books",
        "serial_code": "AUD-UPD-1-NEW",
        "branch_id": None,
        "active": False,
    }
    try:
        response = client.put(f"/resources/{resource.id}", json=request, headers=auth_headers["admin"])
        assert response.status_code == 200, response.text
        assert response.json() == {"status": "success", "message": "منبع با موفقیت بروزرسانی شد"}
        db.expire_all()
        updated = db.get(models.Resource, resource.id)
        assert _resource_row(updated) == {"id": resource.id, **request}
        after_update = _database_snapshot(db)
        _assert_unchanged_except(before_update, after_update, "resources")

        missing = client.put(
            "/resources/999999",
            json={**request, "serial_code": "AUD-UPD-MISSING"},
            headers=auth_headers["admin"],
        )
        _assert_route_error(missing, 404, "منبع یافت نشد")
        assert _database_snapshot(db) == after_update
    finally:
        _restore_tables(db, before, "Resource")


def test_resource_update_duplicate_serial_returns_validation_error_without_writes(
    client, auth_headers, db,
):
    import models

    before = _database_snapshot(db)
    db.add_all([
        models.Resource(name="اول", type="projector", serial_code="AUD-DUP-1", branch_id=1, active=True),
        models.Resource(name="دوم", type="computer", serial_code="AUD-DUP-2", branch_id=2, active=True),
    ])
    db.commit()
    db.expire_all()
    before_request = _database_snapshot(db)
    first_id = db.query(models.Resource).filter_by(serial_code="AUD-DUP-1").one().id
    request = {
        "name": "اول ویرایش‌شده",
        "type": "projector",
        "serial_code": "AUD-DUP-2",
        "branch_id": 1,
        "active": True,
    }
    safe_client = TestClient(client.app, raise_server_exceptions=False)
    try:
        response = safe_client.put(
            f"/resources/{first_id}", json=request, headers=auth_headers["admin"],
        )
        db.expire_all()
        assert _database_snapshot(db) == before_request
        assert response.status_code == 400, response.text
        assert response.json() == {"detail": "کد سریال واردشده متعلق به منبع دیگری است؛ کد یکتا وارد کنید"}
    finally:
        _restore_tables(db, before, "Resource")


def test_resource_duplicate_booking_is_allowed_and_adds_a_second_row(
    client, auth_headers, db,
):
    import models

    before = _database_snapshot(db)
    resource = models.Resource(
        name="پروژکتور رزرو", type="projector", serial_code="AUD-BOOK-1", branch_id=1, active=True,
    )
    db.add(resource)
    db.commit()
    db.expire_all()
    before_booking = _database_snapshot(db)
    body = {
        "resource_id": resource.id,
        "course_id": 1,
        "days_of_week": "شنبه",
        "class_time": "16:00",
    }
    safe_client = TestClient(client.app, raise_server_exceptions=False)
    try:
        first = client.post("/resources/bookings", json=body, headers=auth_headers["admin"])
        assert first.status_code == 200, first.text
        assert first.json()["status"] == "success"
        assert first.json()["message"] == "رزرو منبع با موفقیت انجام شد"
        first_id = first.json()["booking_id"]
        db.expire_all()
        booking = db.get(models.ResourceBooking, first_id)
        assert (booking.resource_id, booking.course_id, booking.days_of_week, booking.class_time) == (
            resource.id, 1, "شنبه", "16:00",
        )
        after_first = _database_snapshot(db)
        _assert_unchanged_except(before_booking, after_first, "resource_bookings")

        duplicate = safe_client.post("/resources/bookings", json=body, headers=auth_headers["admin"])
        assert duplicate.status_code == 200, duplicate.text
        payload = duplicate.json()
        assert set(payload) == {"status", "message", "booking_id"}
        assert payload["status"] == "success"
        assert payload["message"] == "رزرو منبع با موفقیت انجام شد"
        assert payload["booking_id"] != first_id
        db.expire_all()
        after_duplicate = _database_snapshot(db)
        _assert_unchanged_except(after_first, after_duplicate, "resource_bookings")
        rows = db.query(models.ResourceBooking).filter_by(resource_id=resource.id).order_by(models.ResourceBooking.id).all()
        assert len(rows) == 2
        assert [(row.course_id, row.days_of_week, row.class_time) for row in rows] == [
            (1, "شنبه", "16:00"), (1, "شنبه", "16:00"),
        ]
    finally:
        _restore_tables(db, before, "ResourceBooking", "Resource")


def test_resource_booking_valid_slots_and_missing_targets_have_exact_rows(client, auth_headers, db):
    import models

    before = _database_snapshot(db)
    resources = [
        models.Resource(name="اول", type="projector", serial_code="AUD-BOOK-2", branch_id=1, active=True),
        models.Resource(name="دوم", type="computer", serial_code="AUD-BOOK-3", branch_id=2, active=True),
    ]
    db.add_all(resources)
    db.commit()
    db.expire_all()
    before_requests = _database_snapshot(db)
    resource_one_id, resource_two_id = [resource.id for resource in resources]
    requests = [
        {"resource_id": resource_one_id, "course_id": 1, "days_of_week": "شنبه", "class_time": "16:00"},
        {"resource_id": resource_one_id, "course_id": 1, "days_of_week": "یکشنبه", "class_time": "16:00"},
        {"resource_id": resource_one_id, "course_id": 1, "days_of_week": "شنبه", "class_time": "17:00"},
        {"resource_id": resource_two_id, "course_id": 2, "days_of_week": "شنبه", "class_time": "16:00"},
    ]
    try:
        booking_ids = []
        for request in requests:
            response = client.post("/resources/bookings", json=request, headers=auth_headers["admin"])
            assert response.status_code == 200, response.text
            payload = response.json()
            assert set(payload) == {"status", "message", "booking_id"}
            assert payload["status"] == "success"
            assert payload["message"] == "رزرو منبع با موفقیت انجام شد"
            booking_ids.append(payload["booking_id"])

        db.expire_all()
        rows = db.query(models.ResourceBooking).order_by(models.ResourceBooking.id).all()
        assert [row.id for row in rows] == booking_ids
        assert [
            (row.resource_id, row.course_id, row.days_of_week, row.class_time) for row in rows
        ] == [
            (request["resource_id"], request["course_id"], request["days_of_week"], request["class_time"])
            for request in requests
        ]
        after_bookings = _database_snapshot(db)
        _assert_unchanged_except(before_requests, after_bookings, "resource_bookings")

        missing_resource = client.post(
            "/resources/bookings", json={**requests[0], "resource_id": 999999},
            headers=auth_headers["admin"],
        )
        _assert_route_error(missing_resource, 404, "منبع یافت نشد")
        missing_course = client.post(
            "/resources/bookings", json={**requests[0], "course_id": 999999},
            headers=auth_headers["admin"],
        )
        _assert_route_error(missing_course, 404, "کلاس یافت نشد")
        assert _database_snapshot(db) == after_bookings
    finally:
        _restore_tables(db, before, "ResourceBooking", "Resource")
