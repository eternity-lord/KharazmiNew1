"""Temporary-database audit of calendar, room, conflict, and Android contracts."""
from __future__ import annotations

from sqlalchemy import and_, delete, insert, select, update

from .kotlin_contract import audit_payload, discover_models
from .route_registry import route_id, routes

ROUTE_IDS = [
    "POST /calendar/check_conflicts",
    "GET /calendar/events",
    "POST /rooms/create",
    "GET /rooms/list",
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


def test_calendar_route_inventory_is_explicit(client):
    actual = {route_id(row) for row in routes() if row["handler"].split(".")[1] == "calendar"}
    assert set(ROUTE_IDS) == actual
    openapi_routes = {
        (method.upper(), path)
        for path, methods in client.app.openapi()["paths"].items()
        for method in methods
    }
    assert all(tuple(route.split(" ", 1)) in openapi_routes for route in ROUTE_IDS)


def test_room_create_list_empty_duplicate_and_android_shape(client, auth_headers, db):
    import models

    before = _database_snapshot(db)
    kotlin_models = discover_models()
    try:
        initial = client.get("/rooms/list", headers=auth_headers["admin"])
        assert initial.status_code == 200, initial.text
        rows = initial.json()
        assert len(rows) == 2
        assert {row["id"] for row in rows} == {1, 2}
        by_id = {row["id"]: row for row in rows}
        assert by_id[1] == {
            "id": 1, "name": "اتاق آفتاب", "capacity": 20,
            "location": "طبقه اول", "equipment": "برد", "active": True, "branch_id": 1,
        }
        assert by_id[2] == {
            "id": 2, "name": "اتاق آرشیو", "capacity": 10,
            "location": "طبقه دوم", "equipment": None, "active": False, "branch_id": 2,
        }
        assert all(audit_payload("RoomItem", row, kotlin_models) == [] for row in rows)
        assert _database_snapshot(db) == before

        duplicate = client.post(
            "/rooms/create",
            json={"name": "اتاق آفتاب", "capacity": 20, "location": "طبقه اول", "equipment": "برد"},
            headers=auth_headers["admin"],
        )
        assert duplicate.status_code == 400
        assert duplicate.json() == {"detail": "اتاقی با این نام قبلاً در سیستم ثبت شده است"}
        assert _database_snapshot(db) == before

        db.query(models.Room).delete(synchronize_session=False)
        db.commit()
        empty_baseline = _database_snapshot(db)
        empty = client.get("/rooms/list", headers=auth_headers["admin"])
        assert empty.status_code == 200 and empty.json() == []
        assert _database_snapshot(db) == empty_baseline

        missing_location = client.post(
            "/rooms/create", json={"name": "بدون موقعیت"}, headers=auth_headers["admin"],
        )
        assert missing_location.status_code == 422, missing_location.text
        assert _database_snapshot(db) == empty_baseline

        request = {
            "name": "اتاق ممیزی",
            "capacity": 17,
            "location": "طبقه QA",
            "equipment": "وایت‌برد",
        }
        created = client.post("/rooms/create", json=request, headers=auth_headers["admin"])
        assert created.status_code == 200, created.text
        response_row = created.json()
        assert response_row == {
            "id": response_row["id"],
            "name": request["name"],
            "capacity": 17,
            "location": request["location"],
            "equipment": request["equipment"],
            "active": True,
            "branch_id": 1,
        }
        assert audit_payload("RoomItem", response_row, kotlin_models) == []
        after_create = _database_snapshot(db)
        assert len(after_create["rooms"]) == 1
        assert _database_snapshot(db) == after_create
        listed = client.get("/rooms/list", headers=auth_headers["admin"])
        assert listed.status_code == 200 and listed.json() == [response_row]
        assert _database_snapshot(db) == after_create
    finally:
        _restore_tables(db, before, "Room")


def test_calendar_conflict_matrix_and_deleted_suspended_course_filter_are_read_only(
    client, auth_headers, db,
):
    import models

    before = _database_snapshot(db)
    resource = models.Resource(
        name="وسیلهٔ ممیزی", type="projector", serial_code="CAL-RES-1", branch_id=1, active=True,
    )
    db.add(resource)
    db.flush()
    db.add(models.ResourceBooking(
        resource_id=resource.id, course_id=1, days_of_week="شنبه,دوشنبه", class_time="16:00",
    ))
    db.commit()
    db.expire_all()
    before_reads = _database_snapshot(db)
    kotlin_models = discover_models()
    request = {
        "teacher_id": 1,
        "room_id": 1,
        "days_of_week": "شنبه,دوشنبه",
        "class_time": "16:00",
        "student_ids": [1],
        "resource_ids": [resource.id],
    }
    try:
        assert audit_payload("ConflictCheckRequest", request, kotlin_models) == []
        conflicted = client.post(
            "/calendar/check_conflicts", json=request, headers=auth_headers["admin"],
        )
        assert conflicted.status_code == 200, conflicted.text
        conflict_payload = conflicted.json()
        assert conflict_payload == {
            "has_conflict": True,
            "message": "تداخل زمانی یافت شد!",
            "details": [
                "👨‍🏫 تداخل معلم: این مربی قبلاً در همین روز و ساعت در کلاس 'ریاضی پایه فعال' حضور دارد.",
                "🏫 تداخل اتاق: اتاق مورد نظر قبلاً هم‌زمان به کلاس 'ریاضی پایه فعال' اختصاص داده شده است.",
                "👥 تداخل دانش‌آموز: شاگرد 'دانش‌آموز تست 1' هم‌زمان در کلاس 'ریاضی پایه فعال' حضور دارد.",
                "🔌 تداخل منبع: منبع 'وسیلهٔ ممیزی' قبلاً در همین روز و ساعت در کلاس 'ریاضی پایه فعال' رزرو شده است.",
            ],
        }
        assert audit_payload("ConflictCheckResponse", conflict_payload, kotlin_models) == []
        assert _database_snapshot(db) == before_reads

        free_request = {
            "teacher_id": 999999,
            "room_id": 999999,
            "days_of_week": "جمعه",
            "class_time": "22:15",
            "student_ids": [999999],
            "resource_ids": [999999],
        }
        free = client.post(
            "/calendar/check_conflicts", json=free_request, headers=auth_headers["admin"],
        )
        assert free.status_code == 200, free.text
        assert free.json() == {
            "has_conflict": False,
            "message": "برنامه زمانی کاملاً آزاد و بدون تداخل است.",
            "details": [],
        }

        # Course 3 is suspended and Course 6 is deleted; neither should be a
        # conflict for their teacher in the current source filters.
        db.query(models.Course).filter(models.Course.id == 6).update({"is_deleted": True})
        db.commit()
        before_archived_probe = _database_snapshot(db)
        archived_only = client.post(
            "/calendar/check_conflicts",
            json={
                "teacher_id": 2,
                "room_id": None,
                "days_of_week": "شنبه,دوشنبه",
                "class_time": "16:00",
                "student_ids": [],
                "resource_ids": [],
            },
            headers=auth_headers["admin"],
        )
        assert archived_only.status_code == 200
        assert archived_only.json() == {
            "has_conflict": False,
            "message": "برنامه زمانی کاملاً آزاد و بدون تداخل است.",
            "details": [],
        }
        assert _database_snapshot(db) == before_archived_probe
    finally:
        _restore_tables(db, before, "ResourceBooking", "Resource", "Course")


def test_calendar_events_are_role_scoped_exact_and_gson_compatible(
    client, auth_headers, db,
):
    import models

    before = _database_snapshot(db)
    db.add(models.Homework(
        course_id=1, teacher_id=1, title="تمرین بدون شرح", description=None,
        due_date="1405/07/02", max_score=10, status="pending",
    ))
    db.commit()
    before_reads = _database_snapshot(db)
    kotlin_models = discover_models()
    try:
        responses = {
            role: client.get("/calendar/events", headers=auth_headers[role])
            for role in ("admin", "secretary", "teacher", "student", "parent")
        }
        assert all(response.status_code == 200 for response in responses.values())
        payloads = {role: response.json() for role, response in responses.items()}
        for values in payloads.values():
            assert all(set(item) == {"type", "title", "detail", "schedule"} for item in values)

        expected_admin_courses = {
            "🎓 کلاس: ریاضی پایه فعال": ("کد: C-ACTIVE | مربی: رضا فعال", "شنبه,دوشنبه 16:00"),
            "🎓 کلاس: فیزیک دوکلاسه": ("کد: C-MULTI | مربی: رضا فعال", "شنبه,دوشنبه 16:00"),
            "🎓 کلاس: زبان معلق": ("کد: C-SUSP | مربی: مریم معلق", "شنبه,دوشنبه 16:00"),
            "🎓 کلاس: کلاس در انتظار": ("کد: C-PEND | مربی: رضا فعال", "شنبه,دوشنبه 16:00"),
            "🎓 کلاس: کلاس ردشده": ("کد: C-REJ | مربی: مریم معلق", "شنبه,دوشنبه 16:00"),
            "🎓 کلاس: کلاس معلم حذف‌شده": ("کد: C-DELETED-TEACHER | مربی: معلم حذف‌شده", "شنبه,دوشنبه 16:00"),
        }
        admin_rows = payloads["admin"]
        assert len(admin_rows) == 6
        assert {
            row["title"]: (row["detail"], row["schedule"]) for row in admin_rows
        } == expected_admin_courses
        assert len(payloads["secretary"]) == 6
        assert {row["title"] for row in payloads["secretary"]} == set(expected_admin_courses)

        expected_teacher = {
            "🎓 کلاس من: ریاضی پایه فعال": ("برگزاری کلاس ریاضی پایه فعال", "شنبه,دوشنبه 16:00"),
            "🎓 کلاس من: فیزیک دوکلاسه": ("برگزاری کلاس فیزیک دوکلاسه", "شنبه,دوشنبه 16:00"),
            "🎓 کلاس من: کلاس در انتظار": ("برگزاری کلاس کلاس در انتظار", "شنبه,دوشنبه 16:00"),
        }
        assert {
            row["title"]: (row["detail"], row["schedule"]) for row in payloads["teacher"]
        } == expected_teacher

        student_rows = payloads["student"]
        assert len(student_rows) == 7
        classes = [row for row in student_rows if row["type"] == "class"]
        assert {
            row["title"]: (row["detail"], row["schedule"]) for row in classes
        } == {
            "🎓 کلاس من: ریاضی پایه فعال": ("حضور در کلاس ریاضی پایه فعال", "شنبه,دوشنبه 16:00"),
            "🎓 کلاس من: فیزیک دوکلاسه": ("حضور در کلاس فیزیک دوکلاسه", "شنبه,دوشنبه 16:00"),
        }
        exam = next(row for row in student_rows if row["type"] == "exam")
        assert exam == {
            "type": "exam",
            "title": "📅 امتحان: میان‌ترم",
            "detail": "نمره کسب شده: 18.5 از 20.0 در ریاضی پایه فعال",
            "schedule": "1405/06/15",
        }
        homework_rows = [row for row in student_rows if row["type"] == "homework deadline"]
        assert len(homework_rows) == 2
        described = next(row for row in homework_rows if row["title"] == "📝 سررسید تکلیف: تمرین هفته")
        assert described == {
            "type": "homework deadline",
            "title": "📝 سررسید تکلیف: تمرین هفته",
            "detail": "حل تمرین",
            "schedule": "1405/07/01",
        }
        nullable_detail = next(row for row in homework_rows if row["title"] == "📝 سررسید تکلیف: تمرین بدون شرح")
        assert nullable_detail == {
            "type": "homework deadline",
            "title": "📝 سررسید تکلیف: تمرین بدون شرح",
            "detail": None,
            "schedule": "1405/07/02",
        }
        issues = audit_payload("CalendarEventItem", nullable_detail, kotlin_models)
        assert [(issue.field, issue.kind) for issue in issues] == [("detail", "null-non-null")]
        assert all(
            audit_payload("CalendarEventItem", row, kotlin_models) == []
            for row in student_rows if row is not nullable_detail
        )
        payment_rows = [row for row in student_rows if row["type"] == "payment due"]
        assert {(row["detail"], row["schedule"]) for row in payment_rows} == {
            ("مبلغ: 350,000 تومان بابت کلاس ریاضی پایه فعال", "1405/06/01"),
            ("مبلغ: 350,000 تومان بابت کلاس ریاضی پایه فعال", "1405/07/01"),
        }
        assert all(audit_payload("CalendarEventItem", row, kotlin_models) == [] for row in payment_rows)
        assert payloads["parent"] == payloads["student"]
        assert _database_snapshot(db) == before_reads
    finally:
        _restore_tables(db, before, "Homework")
