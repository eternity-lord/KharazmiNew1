"""Positive-flow, persistence, and Android-contract audit for auth/notifications."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from .clock import FIXED_NOW
from .route_registry import route_id, routes

ROUTE_IDS = [
    'POST' + ' ' + '/auth/change-mobile',
    'POST' + ' ' + '/auth/change-password',
    'POST' + ' ' + '/auth/device_token',
    'POST' + ' ' + '/auth/login',
    'POST' + ' ' + '/auth/logout',
    'GET' + ' ' + '/auth/me',
    'POST' + ' ' + '/auth/student/login',
    'POST' + ' ' + '/auth/student/request_otp',
    'GET' + ' ' + '/notifications',
    'POST' + ' ' + '/notifications/read_all',
    'GET' + ' ' + '/notifications/unread_count',
    'POST' + ' ' + '/notifications/{id}/read',
]


def _database_snapshot(db):
    import models

    snapshot = {}
    for table in models.Base.metadata.sorted_tables:
        statement = select(table)
        primary_key = list(table.primary_key.columns)
        if primary_key:
            statement = statement.order_by(*primary_key)
        snapshot[table.name] = [tuple(row) for row in db.execute(statement).all()]
    return snapshot


def _assert_unchanged_except(before, after, *changed_tables):
    assert set(before) == set(after)
    allowed = set(changed_tables)
    for table_name in before:
        if table_name not in allowed:
            assert after[table_name] == before[table_name], table_name


def _assert_android_contract(model, payload):
    from .kotlin_contract import audit_payload

    assert audit_payload(model, payload) == []


def test_auth_route_inventory_is_explicit():
    expected = {route_id(row) for row in routes() if row["handler"].split(".")[1] == "auth"}
    assert set(ROUTE_IDS) == expected


def test_auth_login_returns_android_values_and_sessions_for_admin_and_secretary(client, db):
    import models

    before = _database_snapshot(db)
    created_tokens = []
    cases = [
        {
            "mobile": "audit-admin",
            "password": "Admin-Route-1405!",
            "role": "admin",
            "sub_role": "admin",
            "user_id": 1,
            "name": "ادمین ممیزی",
            "branch_id": None,
        },
        {
            "mobile": "audit-secretary",
            "password": "Secretary-Route-1405!",
            "role": "admin",
            "sub_role": "secretary",
            "user_id": 2,
            "name": "منشی ممیزی",
            "branch_id": 1,
        },
    ]
    try:
        for case in cases:
            response = client.post(
                "/auth/login",
                json={"mobile": case["mobile"], "password": case["password"]},
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            created_tokens.append(payload["token"])
            assert set(payload) == {
                "status", "role", "sub_role", "token", "user_id", "name", "branch_id", "message",
            }
            assert payload["status"] == "success"
            assert payload["role"] == case["role"]
            assert payload["sub_role"] == case["sub_role"]
            assert payload["user_id"] == case["user_id"]
            assert payload["name"] == case["name"]
            assert payload["branch_id"] == case["branch_id"]
            assert isinstance(payload["token"], str) and payload["token"]
            assert payload["message"] == "ورود مدیر موفقیت آمیز بود"
            _assert_android_contract("LoginResponse", payload)

            db.expire_all()
            session = db.query(models.UserSession).filter(models.UserSession.token == payload["token"]).one()
            assert session.user_id == case["user_id"]
            assert session.sub_role == case["sub_role"]
            assert session.created_at == FIXED_NOW

        after = _database_snapshot(db)
        _assert_unchanged_except(before, after, "user_sessions")
        assert len(after["user_sessions"]) == len(before["user_sessions"]) + len(cases)
    finally:
        if created_tokens:
            db.query(models.UserSession).filter(models.UserSession.token.in_(created_tokens)).delete(
                synchronize_session=False
            )
            db.commit()
        db.expire_all()
        assert _database_snapshot(db) == before


def test_auth_teacher_login_returns_teacher_contract_and_records_shadow_session(client, db):
    import models
    from dependencies import hash_password

    teacher = db.query(models.Teacher).filter(models.Teacher.id == 1).one()
    user = db.query(models.User).filter(models.User.id == 3).one()
    original_teacher_password = teacher.password
    original_user_name = user.full_name
    before = _database_snapshot(db)
    created_token = None
    try:
        # The canonical seed keeps the legacy Teacher.password column readable; the real login
        # flow expects a stored password hash, so stage a valid hash for this isolated probe.
        teacher.password = hash_password("Teacher-Route-1405!")
        db.commit()
        before_login = _database_snapshot(db)

        response = client.post(
            "/auth/login",
            json={"mobile": "09120000001", "password": "Teacher-Route-1405!"},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        created_token = payload["token"]
        assert set(payload) == {
            "status", "role", "sub_role", "token", "user_id", "name", "branch_id", "message",
        }
        assert payload["status"] == "success"
        assert payload["role"] == "teacher"
        assert payload["sub_role"] == "teacher"
        assert payload["user_id"] == teacher.id
        assert payload["name"] == "رضا فعال"
        assert payload["branch_id"] == 1
        assert payload["message"] == "ورود معلم موفقیت آمیز بود"
        _assert_android_contract("LoginResponse", payload)

        db.expire_all()
        session = db.query(models.UserSession).filter(models.UserSession.token == created_token).one()
        assert session.user_id == user.id
        assert session.teacher_id == teacher.id
        assert session.sub_role == "teacher"
        assert session.created_at == FIXED_NOW
        assert db.get(models.User, user.id).full_name == "رضا فعال"
        after = _database_snapshot(db)
        _assert_unchanged_except(before_login, after, "users", "user_sessions")
        assert len(after["user_sessions"]) == len(before_login["user_sessions"]) + 1
    finally:
        db.rollback()
        if created_token:
            db.query(models.UserSession).filter(models.UserSession.token == created_token).delete(
                synchronize_session=False
            )
        db.query(models.Teacher).filter(models.Teacher.id == teacher.id).update(
            {"password": original_teacher_password}, synchronize_session=False
        )
        db.query(models.User).filter(models.User.id == user.id).update(
            {"full_name": original_user_name}, synchronize_session=False
        )
        db.commit()
        db.expire_all()
        assert _database_snapshot(db) == before


def test_auth_me_returns_current_admin_and_teacher_android_values(client, auth_headers, db):
    before = _database_snapshot(db)
    cases = [
        ("admin", {"user_id": 1, "name": "ادمین ممیزی", "role": "admin"}),
        ("teacher", {"user_id": 1, "name": "رضا فعال", "role": "teacher"}),
    ]
    for role, expected in cases:
        response = client.get("/auth/me", headers=auth_headers[role])
        assert response.status_code == 200, response.text
        payload = response.json()
        assert set(payload) == {"user_id", "name", "role", "permissions"}
        assert {key: payload[key] for key in expected} == expected
        assert isinstance(payload["permissions"], list)
        _assert_android_contract("MeResponse", payload)
    db.expire_all()
    assert _database_snapshot(db) == before


def test_auth_admin_password_change_updates_only_the_stored_password(client, auth_headers, db):
    import models
    from dependencies import verify_password

    user = db.query(models.User).filter(models.User.id == 1).one()
    original_password_hash = user.password
    before = _database_snapshot(db)
    new_password = "Admin-Route-Changed-1405!"
    try:
        response = client.post(
            "/auth/change-password",
            headers=auth_headers["admin"],
            json={
                "mobile": "audit-admin",
                "old_password": "Admin-Route-1405!",
                "new_password": new_password,
            },
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload == {"message": "رمز عبور مدیر با موفقیت تغییر کرد"}
        _assert_android_contract("SimpleResponse", payload)

        db.expire_all()
        updated = db.get(models.User, user.id)
        assert verify_password(new_password, updated.password)
        assert not verify_password("Admin-Route-1405!", updated.password)
        after = _database_snapshot(db)
        _assert_unchanged_except(before, after, "users")
    finally:
        db.rollback()
        db.query(models.User).filter(models.User.id == user.id).update(
            {"password": original_password_hash}, synchronize_session=False
        )
        db.commit()
        db.expire_all()
        assert _database_snapshot(db) == before


def test_auth_teacher_password_change_keeps_teacher_and_shadow_in_sync(client, auth_headers, db):
    import models
    from dependencies import hash_password, verify_password

    teacher = db.query(models.Teacher).filter(models.Teacher.id == 1).one()
    user = db.query(models.User).filter(models.User.id == 3).one()
    original_teacher_password = teacher.password
    original_user_password = user.password
    before = _database_snapshot(db)
    new_password = "Teacher-Route-Changed-1405!"
    try:
        teacher.password = hash_password("Teacher-Route-1405!")
        db.commit()
        before_change = _database_snapshot(db)

        response = client.post(
            "/auth/change-password",
            headers=auth_headers["teacher"],
            json={
                "mobile": "09120000001",
                "old_password": "Teacher-Route-1405!",
                "new_password": new_password,
            },
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload == {"message": "رمز عبور معلم با موفقیت تغییر کرد"}
        _assert_android_contract("SimpleResponse", payload)

        db.expire_all()
        updated_teacher = db.get(models.Teacher, teacher.id)
        updated_user = db.get(models.User, user.id)
        assert verify_password(new_password, updated_teacher.password)
        assert verify_password(new_password, updated_user.password)
        assert not verify_password("Teacher-Route-1405!", updated_teacher.password)
        after = _database_snapshot(db)
        _assert_unchanged_except(before_change, after, "teachers", "users")
    finally:
        db.rollback()
        db.query(models.Teacher).filter(models.Teacher.id == teacher.id).update(
            {"password": original_teacher_password}, synchronize_session=False
        )
        db.query(models.User).filter(models.User.id == user.id).update(
            {"password": original_user_password}, synchronize_session=False
        )
        db.commit()
        db.expire_all()
        assert _database_snapshot(db) == before


def test_auth_teacher_change_mobile_normalizes_digits_and_updates_linked_rows(client, auth_headers, db):
    import models

    teacher = db.query(models.Teacher).filter(models.Teacher.id == 1).one()
    user = db.query(models.User).filter(models.User.id == 3).one()
    old_mobile = teacher.mobile
    old_username = user.username
    new_mobile_input = "۰۹۱۲۹۹۹۸۸۸۸"
    new_mobile = "09129998888"
    before = _database_snapshot(db)
    try:
        response = client.post(
            "/auth/change-mobile",
            headers=auth_headers["teacher"],
            json={
                "current_mobile": old_mobile,
                "password": "Teacher-Route-1405!",
                "new_mobile": new_mobile_input,
            },
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload == {"message": "شماره‌ی شما با موفقیت تغییر کرد، لطفاً دوباره با شماره‌ی جدید وارد شوید"}
        _assert_android_contract("SimpleResponse", payload)

        db.expire_all()
        assert db.get(models.Teacher, teacher.id).mobile == new_mobile
        assert db.get(models.User, user.id).username == new_mobile
        log = db.query(models.ActivityLog).filter(
            models.ActivityLog.action == "change_teacher_mobile",
            models.ActivityLog.target_id == user.id,
            models.ActivityLog.admin_username == old_mobile,
            models.ActivityLog.details.contains(new_mobile),
        ).one()
        assert log.target_name == user.full_name
        assert old_mobile in log.details and new_mobile in log.details
        after = _database_snapshot(db)
        _assert_unchanged_except(before, after, "teachers", "users", "activity_logs")
    finally:
        db.rollback()
        db.query(models.Teacher).filter(models.Teacher.id == teacher.id).update(
            {"mobile": old_mobile}, synchronize_session=False
        )
        db.query(models.User).filter(models.User.id == user.id).update(
            {"username": old_username}, synchronize_session=False
        )
        db.query(models.ActivityLog).filter(
            models.ActivityLog.action == "change_teacher_mobile",
            models.ActivityLog.target_id == user.id,
            models.ActivityLog.admin_username == old_mobile,
            models.ActivityLog.details.contains(new_mobile),
        ).delete(synchronize_session=False)
        db.commit()
        db.expire_all()
        assert _database_snapshot(db) == before


def test_auth_change_mobile_rejects_an_existing_student_mobile_without_writes(client, auth_headers, db):
    before = _database_snapshot(db)
    response = client.post(
        "/auth/change-mobile",
        headers=auth_headers["teacher"],
        json={
            "current_mobile": "09120000001",
            "password": "Teacher-Route-1405!",
            "new_mobile": "09350000001",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "این شماره موبایل قبلاً در سیستم ثبت شده و تکراری است"}
    db.expire_all()
    assert _database_snapshot(db) == before


def test_auth_logout_matches_android_call_and_removes_only_its_session_and_device_token(client, auth_headers, db):
    import models

    token = auth_headers["admin"]["Authorization"].split(" ", 1)[1]
    session = db.query(models.UserSession).filter(models.UserSession.token == token).one()
    saved_session = {
        "id": session.id,
        "token": session.token,
        "user_id": session.user_id,
        "teacher_id": session.teacher_id,
        "sub_role": session.sub_role,
        "created_at": session.created_at,
    }
    device_token_value = "audit-route-logout-current-device"
    device_token = models.DeviceToken(user_id=1, role="admin", token=device_token_value)
    baseline = _database_snapshot(db)
    db.add(device_token)
    db.commit()
    before_logout = _database_snapshot(db)
    try:
        # Android logout sends its stored FCM token; only that user/role/device is removed.
        response = client.post(
            "/auth/logout", headers=auth_headers["admin"], params={"device_token": device_token_value},
        )
        assert response.status_code == 200, response.text
        assert response.json() == {"message": "خروج با موفقیت انجام شد و نشست باطل گردید"}

        db.expire_all()
        assert db.query(models.UserSession).filter(models.UserSession.token == token).first() is None
        assert db.query(models.DeviceToken).filter(models.DeviceToken.token == device_token_value).first() is None
        after_logout = _database_snapshot(db)
        _assert_unchanged_except(before_logout, after_logout, "user_sessions", "device_tokens")
        token_index = list(models.UserSession.__table__.columns.keys()).index("token")
        assert after_logout["user_sessions"] == [
            row for row in before_logout["user_sessions"] if row[token_index] != token
        ]
    finally:
        db.rollback()
        if db.query(models.UserSession).filter(models.UserSession.token == token).first() is None:
            db.add(models.UserSession(**saved_session))
        db.query(models.DeviceToken).filter(models.DeviceToken.token == device_token_value).delete(
            synchronize_session=False
        )
        db.commit()
        db.expire_all()
        assert _database_snapshot(db) == baseline


def test_auth_device_token_register_is_idempotent_for_same_actor(client, auth_headers, db):
    import models

    before = _database_snapshot(db)
    token = "audit-route-device-token-registration"
    try:
        response = client.post(
            "/auth/device_token", headers=auth_headers["admin"], json={"token": token},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload == {"message": "توکن دستگاه با موفقیت ثبت شد"}
        _assert_android_contract("SimpleResponse", payload)

        db.expire_all()
        registered = db.query(models.DeviceToken).filter(models.DeviceToken.token == token).one()
        assert registered.user_id == 1
        assert registered.role == "admin"
        assert registered.created_at == FIXED_NOW
        after_first = _database_snapshot(db)
        _assert_unchanged_except(before, after_first, "device_tokens")

        retry = client.post(
            "/auth/device_token", headers=auth_headers["admin"], json={"token": token},
        )
        assert retry.status_code == 200, retry.text
        assert retry.json() == payload
        db.expire_all()
        assert db.query(models.DeviceToken).filter(models.DeviceToken.token == token).count() == 1
        assert _database_snapshot(db) == after_first
    finally:
        db.query(models.DeviceToken).filter(models.DeviceToken.token == token).delete(
            synchronize_session=False
        )
        db.commit()
        db.expire_all()
        assert _database_snapshot(db) == before


def test_auth_student_request_otp_logs_mock_delivery_and_expires_after_three_minutes(client, db, monkeypatch):
    import models
    import routers.auth as auth_router

    otp_code = "654321"
    monkeypatch.setattr(auth_router.random, "randint", lambda low, high: int(otp_code))
    mobile = "09350000001"
    target_group = f"student_otp_{mobile}"
    before = _database_snapshot(db)
    otp_ids_before = {row.id for row in db.query(models.ParentOTP).all()}
    sms_ids_before = {row.id for row in db.query(models.SmsLog).all()}
    try:
        response = client.post("/auth/student/request_otp", json={"mobile": mobile})
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload == {
            "status": "success",
            "message": "کد یک‌بارمصرف ورود دانش‌آموز با موفقیت ارسال شد",
        }
        _assert_android_contract("SimpleResponse", payload)

        db.expire_all()
        otp = db.query(models.ParentOTP).filter(models.ParentOTP.mobile == mobile).one()
        sms = db.query(models.SmsLog).filter(models.SmsLog.target_group == target_group).one()
        assert otp.id not in otp_ids_before
        assert sms.id not in sms_ids_before
        assert otp.created_at == FIXED_NOW
        assert otp.expires_at == FIXED_NOW + timedelta(minutes=3)
        assert otp.is_used is False and otp.attempts == 0 and otp.is_locked is False
        assert sms.target_group == target_group
        assert sms.message_text == f"کد تایید ورود به پورتال دانش‌آموز خوارزمی: {otp_code}"
        assert sms.sent_count == 1
        assert sms.date == FIXED_NOW.strftime("%Y/%m/%d %H:%M")
        after = _database_snapshot(db)
        _assert_unchanged_except(before, after, "parent_otps", "sms_logs")
    finally:
        db.rollback()
        otp_cleanup = db.query(models.ParentOTP).filter(models.ParentOTP.mobile == mobile)
        sms_cleanup = db.query(models.SmsLog).filter(models.SmsLog.target_group == target_group)
        if otp_ids_before:
            otp_cleanup = otp_cleanup.filter(~models.ParentOTP.id.in_(otp_ids_before))
        if sms_ids_before:
            sms_cleanup = sms_cleanup.filter(~models.SmsLog.id.in_(sms_ids_before))
        otp_cleanup.delete(synchronize_session=False)
        sms_cleanup.delete(synchronize_session=False)
        db.commit()
        db.expire_all()
        assert _database_snapshot(db) == before


def test_auth_student_login_consumes_one_otp_and_retries_without_duplicate_session(client, db):
    import models
    from dependencies import hash_password

    mobile = "09350000001"
    otp_code = "345678"
    student = db.query(models.Student).filter(models.Student.id == 1).one()
    otp = models.ParentOTP(
        mobile=mobile,
        otp=hash_password(otp_code),
        created_at=FIXED_NOW,
        expires_at=FIXED_NOW + timedelta(minutes=3),
        is_used=False,
        attempts=0,
        is_locked=False,
    )
    baseline = _database_snapshot(db)
    session_ids_before = {row[0] for row in baseline["user_sessions"]}
    db.add(otp)
    db.commit()
    otp_id = otp.id
    before_login = _database_snapshot(db)
    token = None
    try:
        response = client.post(
            "/auth/student/login", json={"mobile": mobile, "otp": otp_code},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        token = payload["token"]
        assert set(payload) == {"status", "token", "student_name"}
        assert payload["status"] == "success"
        assert isinstance(token, str) and token
        assert payload["student_name"] == "دانش‌آموز تست 1"
        _assert_android_contract("StudentLoginResponse", payload)

        db.expire_all()
        used_otp = db.get(models.ParentOTP, otp_id)
        assert used_otp.is_used is True
        assert used_otp.attempts == 0 and used_otp.is_locked is False
        session = db.query(models.UserSession).filter(models.UserSession.token == token).one()
        assert session.user_id == student.user_id == 4
        assert session.sub_role == "student"
        assert session.created_at == FIXED_NOW
        after_login = _database_snapshot(db)
        _assert_unchanged_except(before_login, after_login, "parent_otps", "user_sessions")
        assert len(after_login["user_sessions"]) == len(before_login["user_sessions"]) + 1

        retry = client.post(
            "/auth/student/login", json={"mobile": mobile, "otp": otp_code},
        )
        assert retry.status_code == 400
        assert retry.json() == {"detail": "کد تایید نامعتبر یا منقضی شده است"}
        db.expire_all()
        assert _database_snapshot(db) == after_login
    finally:
        db.rollback()
        new_sessions = db.query(models.UserSession).filter(
            models.UserSession.user_id == student.user_id,
            models.UserSession.sub_role == "student",
        )
        if session_ids_before:
            new_sessions = new_sessions.filter(~models.UserSession.id.in_(session_ids_before))
        new_sessions.delete(synchronize_session=False)
        db.query(models.ParentOTP).filter(models.ParentOTP.id == otp_id).delete(synchronize_session=False)
        db.commit()
        db.expire_all()
        assert _database_snapshot(db) == baseline


def test_auth_notifications_values_order_nulls_and_empty_role(client, auth_headers, db):
    import models

    baseline = _database_snapshot(db)
    seed_notification = db.get(models.Notification, 1)
    assert seed_notification.recipient_user_id == 1 and seed_notification.recipient_role == "admin"
    old_unread = models.Notification(
        recipient_user_id=1, recipient_role="admin", type="attendance",
        title="اعلان قدیمی", body="پیام حضور", is_read=False,
        created_at=FIXED_NOW - timedelta(minutes=2), priority=2,
    )
    new_read = models.Notification(
        recipient_user_id=1, recipient_role="admin", type="payment",
        title="اعلان جدید", body="پیام پرداخت", is_read=True,
        created_at=FIXED_NOW + timedelta(minutes=1), priority=3,
    )
    legacy_null = models.Notification(
        recipient_user_id=1, recipient_role="admin", type="system",
        title="اعلان قدیمیِ بی‌زمان", body="پیام قدیمی", is_read=None,
        created_at=None, priority=1,
    )
    db.add_all([old_unread, new_read, legacy_null])
    db.commit()
    # SQLAlchemy's ORM defaults replace explicit None on INSERT; stage the legacy NULL directly.
    db.query(models.Notification).filter(models.Notification.id == legacy_null.id).update(
        {"created_at": None, "is_read": None}, synchronize_session=False
    )
    db.commit()
    probe_ids = [old_unread.id, new_read.id, legacy_null.id]
    before_reads = _database_snapshot(db)
    try:
        response = client.get("/notifications", headers=auth_headers["admin"])
        assert response.status_code == 200, response.text
        items = response.json()
        assert [item["id"] for item in items] == [new_read.id, seed_notification.id, old_unread.id, legacy_null.id]
        assert all(set(item) == {"id", "type", "title", "body", "is_read", "created_at"} for item in items)
        assert items == [
            {
                "id": new_read.id, "type": "payment", "title": "اعلان جدید", "body": "پیام پرداخت",
                "is_read": True, "created_at": (FIXED_NOW + timedelta(minutes=1)).strftime("%Y/%m/%d %H:%M"),
            },
            {
                "id": seed_notification.id, "type": "payment", "title": "پرداخت تست", "body": "اعلان تست",
                "is_read": False, "created_at": FIXED_NOW.strftime("%Y/%m/%d %H:%M"),
            },
            {
                "id": old_unread.id, "type": "attendance", "title": "اعلان قدیمی", "body": "پیام حضور",
                "is_read": False, "created_at": (FIXED_NOW - timedelta(minutes=2)).strftime("%Y/%m/%d %H:%M"),
            },
            {
                "id": legacy_null.id, "type": "system", "title": "اعلان قدیمیِ بی‌زمان", "body": "پیام قدیمی",
                "is_read": False, "created_at": "",
            },
        ]
        for item in items:
            _assert_android_contract("NotificationItem", item)

        count_response = client.get("/notifications/unread_count", headers=auth_headers["admin"])
        assert count_response.status_code == 200, count_response.text
        counts = count_response.json()
        assert counts == {"unread": 3, "total": 4}
        _assert_android_contract("UnreadCountResponse", counts)

        empty_response = client.get("/notifications", headers=auth_headers["secretary"])
        assert empty_response.status_code == 200, empty_response.text
        assert empty_response.json() == []
        empty_count_response = client.get("/notifications/unread_count", headers=auth_headers["secretary"])
        assert empty_count_response.status_code == 200, empty_count_response.text
        assert empty_count_response.json() == {"unread": 0, "total": 0}
        db.expire_all()
        assert _database_snapshot(db) == before_reads
    finally:
        db.query(models.Notification).filter(models.Notification.id.in_(probe_ids)).delete(
            synchronize_session=False
        )
        db.commit()
        db.expire_all()
        assert _database_snapshot(db) == baseline


def test_auth_notification_read_transitions_are_idempotent_and_read_all_persists(client, auth_headers, db):
    import models

    baseline = _database_snapshot(db)
    seeded = db.get(models.Notification, 1)
    seeded_read = seeded.is_read
    own_unread = models.Notification(
        recipient_user_id=1, recipient_role="admin", type="system",
        title="علامت‌گذاری تکی", body="unread", is_read=False,
        created_at=FIXED_NOW - timedelta(minutes=2), priority=1,
    )
    own_legacy = models.Notification(
        recipient_user_id=1, recipient_role="admin", type="system",
        title="علامت‌گذاری همه", body="legacy null", is_read=None,
        created_at=None, priority=1,
    )
    own_read = models.Notification(
        recipient_user_id=1, recipient_role="admin", type="system",
        title="از قبل خوانده‌شده", body="read", is_read=True,
        created_at=FIXED_NOW, priority=1,
    )
    db.add_all([own_unread, own_legacy, own_read])
    db.commit()
    db.query(models.Notification).filter(models.Notification.id == own_legacy.id).update(
        {"created_at": None, "is_read": None}, synchronize_session=False
    )
    db.commit()
    probe_ids = [own_unread.id, own_legacy.id, own_read.id]
    try:
        mark_response = client.post(
            f"/notifications/{own_unread.id}/read", headers=auth_headers["admin"],
        )
        assert mark_response.status_code == 200, mark_response.text
        assert mark_response.json() == {"message": "اعلان به عنوان خوانده شده ثبت شد"}
        _assert_android_contract("SimpleResponse", mark_response.json())
        db.expire_all()
        assert db.get(models.Notification, own_unread.id).is_read is True
        assert db.get(models.Notification, own_legacy.id).is_read is None
        assert db.get(models.Notification, own_read.id).is_read is True
        assert db.get(models.Notification, seeded.id).is_read is seeded_read
        after_single_read = _database_snapshot(db)
        _assert_unchanged_except(baseline, after_single_read, "notifications")

        retry = client.post(
            f"/notifications/{own_unread.id}/read", headers=auth_headers["admin"],
        )
        assert retry.status_code == 200, retry.text
        assert retry.json() == mark_response.json()
        missing = client.post("/notifications/999999999/read", headers=auth_headers["admin"])
        assert missing.status_code == 404
        db.expire_all()
        assert _database_snapshot(db) == after_single_read

        read_all = client.post("/notifications/read_all", headers=auth_headers["admin"])
        assert read_all.status_code == 200, read_all.text
        assert read_all.json() == {"message": "تمامی اعلان‌ها خوانده شدند"}
        _assert_android_contract("SimpleResponse", read_all.json())
        db.expire_all()
        assert all(
            db.get(models.Notification, notification_id).is_read is True
            for notification_id in [1, *probe_ids]
        )
        after_read_all = _database_snapshot(db)
        _assert_unchanged_except(after_single_read, after_read_all, "notifications")

        count_response = client.get("/notifications/unread_count", headers=auth_headers["admin"])
        assert count_response.status_code == 200, count_response.text
        assert count_response.json() == {"unread": 0, "total": 4}
        repeated_read_all = client.post("/notifications/read_all", headers=auth_headers["admin"])
        assert repeated_read_all.status_code == 200, repeated_read_all.text
        db.expire_all()
        assert _database_snapshot(db) == after_read_all
    finally:
        db.rollback()
        db.query(models.Notification).filter(models.Notification.id.in_(probe_ids)).delete(
            synchronize_session=False
        )
        db.query(models.Notification).filter(models.Notification.id == 1).update(
            {"is_read": seeded_read}, synchronize_session=False
        )
        db.commit()
        db.expire_all()
        assert _database_snapshot(db) == baseline
