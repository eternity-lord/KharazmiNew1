"""Value and state-transition audit for routers.attendance."""
from __future__ import annotations

from .clock import FIXED_NOW
from .oracle import build_oracle


ATTENDANCE_ROUTES = [
    ("GET", "/admin/live_sessions"),
    ("GET", "/admin/live_sessions/{session_id}/roster"),
    ("POST", "/attendance/get"),
    ("POST", "/attendance/get_history"),
    ("GET", "/attendance/live/current"),
    ("POST", "/attendance/qr_check-in"),
    ("DELETE", "/attendance/session/{session_code}"),
    ("GET", "/attendance/session/{session_code}"),
    ("PUT", "/attendance/session/{session_code}"),
    ("POST", "/attendance/student_history"),
    ("POST", "/attendance/submit_session"),
    ("POST", "/attendance/{course_id}/start_live"),
    ("POST", "/attendance/{session_id}/cancel_live"),
    ("POST", "/attendance/{session_id}/end_live"),
    ("POST", "/attendance/{session_id}/live_status"),
]
ROUTE_IDS = [f"{method} {path}" for method, path in ATTENDANCE_ROUTES]


def test_attendance_route_inventory_is_explicit(client):
    paths = {(path, method.upper()) for path, operations in client.app.openapi()["paths"].items() for method in operations}
    assert [(m, p) for m, p in ATTENDANCE_ROUTES if (p, m.upper()) not in paths] == []


def test_session_details_and_class_attendance_have_values(client, auth_headers):
    headers = auth_headers["admin"]
    details = client.get("/attendance/session/5001", headers=headers)
    by_date = client.post("/attendance/get", json={"course_id": 1, "date": "1405/06/10"}, headers=headers)
    history = client.post("/attendance/get_history", json={"course_id": 1}, headers=headers)
    student = client.post("/attendance/student_history", json={"student_id": 1, "course_id": 1}, headers=headers)
    assert details.status_code == by_date.status_code == history.status_code == student.status_code == 200
    body = details.json()
    assert body["session_code"] == 5001
    assert body["class_title"] == "ریاضی پایه فعال"
    assert body["attendee_count"] == 3
    assert {item["status"] for item in body["items"]} == {"Present", "Late", "Absent"}
    assert by_date.json()[0]["name"] == "دانش‌آموز تست 1"
    assert history.json()[0]["date"] == "1405/06/10"
    assert history.json()[0]["total_cost"] == 600_000
    assert student.json()["present_count"] == 1
    assert student.json()["attendance_history"][0]["status"] == "حاضر"


def test_qr_checkin_rejects_stale_session_then_records_same_day_attendance(client, auth_headers, db, frozen_server_clock):
    """Probe both stale-state rejection and a valid same-day QR check-in without external calls."""
    import models
    from today_summary import jalali_date_string

    session = db.query(models.SessionLog).filter_by(session_code=5001).one()
    attendance = db.query(models.Attendance).filter_by(session_id=session.id, student_id=1).one()
    original_date = session.date
    original_status = attendance.status
    original_notification_ids = {row.id for row in db.query(models.Notification).all()}
    payload = {
        "session_code": 5001,
        "token": "route-audit-qr-token",
        "expires_at": FIXED_NOW.timestamp() + 600,
        "salt": "route-audit-qr-salt",
    }
    try:
        stale = client.post("/attendance/qr_check-in", json=payload, headers=auth_headers["student"])
        assert stale.status_code == 403
        db.expire_all()
        assert db.query(models.Attendance).filter_by(session_id=session.id, student_id=1).one().status == original_status

        session = db.query(models.SessionLog).filter_by(session_code=5001).one()
        attendance = db.query(models.Attendance).filter_by(session_id=session.id, student_id=1).one()
        session.date = jalali_date_string(FIXED_NOW.date())
        attendance.status = "Absent"
        db.commit()
        accepted = client.post("/attendance/qr_check-in", json=payload, headers=auth_headers["student"])
        assert accepted.status_code == 200, accepted.text
        db.expire_all()
        attendance = db.query(models.Attendance).filter_by(session_id=session.id, student_id=1).one()
        assert attendance.status == "Present"
        assert accepted.json()["message"] == "حضور شما با موفقیت با اسکن کد QR ثبت گردید"
    finally:
        db.expire_all()
        session = db.query(models.SessionLog).filter_by(session_code=5001).one()
        attendance = db.query(models.Attendance).filter_by(session_id=session.id, student_id=1).one()
        session.date = original_date
        attendance.status = original_status
        db.query(models.Notification).filter(~models.Notification.id.in_(original_notification_ids)).delete(synchronize_session=False)
        db.commit()


def test_live_start_status_cancel_is_idempotent_without_financial_effect(client, auth_headers, db):
    import models
    headers = auth_headers["admin"]
    sessions_before = db.query(models.SessionLog).count()
    tx_before = db.query(models.Transaction).count()
    started = client.post("/attendance/1/start_live", headers=headers)
    assert started.status_code == 200, started.text
    live_id = started.json()["live_session_id"]
    assert started.json()["status"] == "LIVE"
    duplicate = client.post("/attendance/1/start_live", headers=headers)
    assert duplicate.status_code == 409
    saved = client.post(f"/attendance/{live_id}/live_status", json={"items": {"1": {"status": "Present", "excused": False}, "2": {"status": "Late", "excused": False}}}, headers=headers)
    assert saved.status_code == 200
    assert saved.json()["count"] == 2
    cancelled = client.post(f"/attendance/{live_id}/cancel_live", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    replay = client.post(f"/attendance/{live_id}/cancel_live", headers=headers)
    assert replay.status_code == 200
    db.expire_all()
    live = db.get(models.LiveSession, live_id)
    assert live.status == "CANCELLED"
    assert db.query(models.SessionLog).count() == sessions_before
    assert db.query(models.Transaction).count() == tx_before


def test_session_charge_retry_is_atomic_and_rejects_duplicate_date(client, auth_headers, db):
    import models
    headers = auth_headers["admin"]
    payload = {
        "course_id": 1,
        "date": "1403/08/03",
        "items": [{"student_id": 1, "status": "Present", "excused": False}],
    }
    before_sessions = {row.id for row in db.query(models.SessionLog).all()}
    before_attendance = {row.id for row in db.query(models.Attendance).all()}
    before_transactions = {row.id for row in db.query(models.Transaction).all()}
    student = db.get(models.Student, 1)
    enrollment = db.get(models.Enrollment, 1)
    before_wallets = (student.wallet_teacher, student.wallet_institute, student.wallet_balance)
    before_paid = enrollment.total_paid

    first = client.post("/attendance/submit_session", json=payload, headers=headers)
    retry = client.post("/attendance/submit_session", json=payload, headers=headers)
    assert first.status_code == 200, first.text
    assert retry.status_code == 409, retry.text

    db.expire_all()
    new_sessions = db.query(models.SessionLog).filter(~models.SessionLog.id.in_(before_sessions)).all()
    new_attendance = db.query(models.Attendance).filter(~models.Attendance.id.in_(before_attendance)).all()
    new_transactions = db.query(models.Transaction).filter(~models.Transaction.id.in_(before_transactions)).all()
    assert len(new_sessions) == 1
    assert len(new_attendance) == 1
    assert len(new_transactions) >= 1
    session_id = new_sessions[0].id
    assert all(row.session_id == session_id for row in new_transactions)

    # Remove only this test's ledger rows and restore the seeded wallet snapshot.
    tx_ids = {row.id for row in new_transactions}
    for allocation in db.query(models.TransactionInstallmentAllocation).filter(models.TransactionInstallmentAllocation.transaction_id.in_(tx_ids)).all():
        db.delete(allocation)
    for row in new_attendance:
        db.delete(row)
    for row in new_transactions:
        db.delete(row)
    for row in new_sessions:
        db.delete(row)
    student = db.get(models.Student, 1)
    student.wallet_teacher, student.wallet_institute, student.wallet_balance = before_wallets
    db.get(models.Enrollment, 1).total_paid = before_paid
    db.commit()


def test_live_state_and_role_specific_reads(client, auth_headers):
    teacher_live = client.get("/attendance/live/current", headers=auth_headers["teacher"])
    admin_live = client.get("/attendance/live/current", headers=auth_headers["admin"])
    all_live = client.get("/admin/live_sessions", headers=auth_headers["admin"])
    roster = client.get("/admin/live_sessions/1/roster", headers=auth_headers["admin"])
    assert teacher_live.status_code == admin_live.status_code == all_live.status_code == roster.status_code == 200
    assert teacher_live.json()["live_session_id"] == 1
    assert admin_live.json() is None
    assert any(row["live_session_id"] == 1 and row["present"] == 1 for row in all_live.json())
    assert roster.json()["live_session_id"] == 1
    assert roster.json()["students"][0]["status"] == "Present"


def test_suspended_course_cannot_start_live_without_writing(client, auth_headers, db):
    import models
    before = db.query(models.LiveSession).count()
    response = client.post("/attendance/3/start_live", headers=auth_headers["admin"])
    assert response.status_code == 403
    db.expire_all()
    assert db.query(models.LiveSession).count() == before



def test_session_charge_uses_the_declared_teacher_share_value(client, auth_headers, db):
    """Numeric oracle: a one-student class priced at 260,000 charges exactly 260,000."""
    import models

    course = db.get(models.Course, 1)
    original_rule, original_price = course.rule_prepay_teacher, course.teacher_session_price
    course.rule_prepay_teacher = False
    course.teacher_session_price = 260_000
    db.commit()
    student = db.get(models.Student, 1)
    before_wallet = (student.wallet_teacher, student.wallet_institute, student.wallet_balance)
    before_sessions = {row.id for row in db.query(models.SessionLog).all()}
    before_attendance = {row.id for row in db.query(models.Attendance).all()}
    before_transactions = {row.id for row in db.query(models.Transaction).all()}
    created_session = None
    created_transaction = None
    try:
        response = client.post(
            "/attendance/submit_session",
            json={"course_id": 1, "date": "1403/08/04", "items": [{"student_id": 1, "status": "Present", "excused": False}]},
            headers=auth_headers["admin"],
        )
        assert response.status_code == 200, response.text
        db.expire_all()
        created_session = db.query(models.SessionLog).filter(~models.SessionLog.id.in_(before_sessions)).one()
        created_transaction = db.query(models.Transaction).filter(~models.Transaction.id.in_(before_transactions)).one()
        assert created_session.final_teacher_cost == 260_000
        assert created_session.final_institute_share == 0
        assert created_transaction.amount == -260_000
        assert created_transaction.share_teacher == 260_000
        assert created_transaction.share_institute == 0
        student = db.get(models.Student, 1)
        assert (student.wallet_teacher, student.wallet_institute) == (-270_000, 5_000)
    finally:
        if created_transaction is None:
            created_transaction = next((row for row in db.query(models.Transaction).all() if row.id not in before_transactions), None)
        if created_session is None:
            created_session = next((row for row in db.query(models.SessionLog).all() if row.id not in before_sessions), None)
        if created_transaction is not None:
            db.query(models.TransactionInstallmentAllocation).filter(models.TransactionInstallmentAllocation.transaction_id == created_transaction.id).delete(synchronize_session=False)
            db.delete(created_transaction)
        for row in db.query(models.Attendance).filter(~models.Attendance.id.in_(before_attendance)).all():
            db.delete(row)
        if created_session is not None:
            db.delete(created_session)
        course = db.get(models.Course, 1)
        course.rule_prepay_teacher, course.teacher_session_price = original_rule, original_price
        student = db.get(models.Student, 1)
        student.wallet_teacher, student.wallet_institute, student.wallet_balance = before_wallet
        db.commit()



def test_deleting_a_settled_session_is_a_conflict_without_side_effects(client, auth_headers, db):
    """Independent oracle: billed session 5001 must remain active and return HTTP 409."""
    import models

    before_attendance = db.query(models.Attendance).filter(models.Attendance.session_id == 1).count()
    before_session_transactions = {row.id for row in db.query(models.Transaction).filter(models.Transaction.session_id == 1).all()}
    response = client.delete("/attendance/session/5001", headers=auth_headers["admin"])
    assert response.status_code == 409, response.text
    db.expire_all()
    session = db.query(models.SessionLog).filter(models.SessionLog.session_code == 5001).one()
    assert session.is_deleted is False
    assert db.query(models.Attendance).filter(models.Attendance.session_id == session.id).count() == before_attendance
    assert {row.id for row in db.query(models.Transaction).filter(models.Transaction.session_id == session.id).all()} == before_session_transactions
    assert db.query(models.Attendance).filter(models.Attendance.session_id == session.id, models.Attendance.is_billed == True).count() == 2
