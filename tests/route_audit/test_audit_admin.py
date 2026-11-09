"""Value and state-transition audit for router admin.

Behavioral cases are marked blocked in docs/route-tests/routes/admin.md until
the router is processed. This module still makes every route an explicit
pytest test input, so a missing route cannot disappear silently.
"""
import pytest

from .route_registry import route_id, routes

ROUTE_IDS = [
    'POST' + ' ' + '/admin/approve_class/{course_id}',
    'POST' + ' ' + '/admin/classes/suspend_bulk',
    'GET' + ' ' + '/admin/deleted_classes',
    'GET' + ' ' + '/admin/deleted_classes/{course_id}',
    'POST' + ' ' + '/admin/deleted_classes/{course_id}/restore',
    'GET' + ' ' + '/admin/institute_settings',
    'PUT' + ' ' + '/admin/institute_settings',
    'POST' + ' ' + '/admin/institute_settings/upload_logo',
    'GET' + ' ' + '/admin/parent_contacts',
    'GET' + ' ' + '/admin/pending_classes',
    'GET' + ' ' + '/admin/pricing_table',
    'PUT' + ' ' + '/admin/pricing_table',
    'DELETE' + ' ' + '/admin/reject_class/{course_id}',
    'GET' + ' ' + '/admin/session_history',
    'POST' + ' ' + '/admin/session_history/{session_id}/reopen',
    'GET' + ' ' + '/admin/students/search',
    'DELETE' + ' ' + '/admin/students/{id}',
    'GET' + ' ' + '/admin/students/{id}/full_profile',
    'POST' + ' ' + '/admin/students/{id}/toggle_suspend',
    'GET' + ' ' + '/admin/teachers/search',
    'GET' + ' ' + '/admin/teachers/{id}/credentials',
    'PUT' + ' ' + '/admin/teachers/{id}/credentials',
    'POST' + ' ' + '/admin/teachers/{id}/credentials/reset_password',
    'DELETE' + ' ' + '/admin/teachers/{teacher_id}',
    'POST' + ' ' + '/admin/teachers/{teacher_id}/suspend',
    'GET' + ' ' + '/admin/today_summary',
    'GET' + ' ' + '/admin/transactions/list',
    'GET' + ' ' + '/admin/transactions/list/excel',
    'DELETE' + ' ' + '/admin/transactions/{id}',
    'PUT' + ' ' + '/admin/transactions/{id}',
    'GET' + ' ' + '/config/share',
    'POST' + ' ' + '/config/share/update',
    'GET' + ' ' + '/dashboard/stats',
    'GET' + ' ' + '/sms/history',
    'POST' + ' ' + '/sms/send',
    'POST' + ' ' + '/sms/send_bulk',
    'POST' + ' ' + '/teachers/approve/{teacher_id}',
    'GET' + ' ' + '/teachers/pending',
    'DELETE' + ' ' + '/teachers/reject/{teacher_id}',
    'GET' + ' ' + '/test/debt_calculation',
    'POST' + ' ' + '/test/transaction_logic',
]

def test_admin_route_inventory_is_explicit():
    expected = {route_id(row) for row in routes() if row["handler"].split(".")[1] == 'admin'}
    assert set(ROUTE_IDS) == expected


def test_admin_dashboard_and_finance_reads_have_exact_seed_values(client, auth_headers):
    headers = auth_headers["admin"]
    stats = client.get("/dashboard/stats", headers=headers)
    debt = client.get("/test/debt_calculation", headers=headers)
    transactions = client.get("/admin/transactions/list", headers=headers)
    students = client.get("/admin/students/search", params={"query": "0020000001"}, headers=headers)
    teachers = client.get("/admin/teachers/search", params={"query": "0010000001"}, headers=headers)
    assert stats.status_code == debt.status_code == transactions.status_code == students.status_code == teachers.status_code == 200
    assert stats.json()["student_count"] == 29
    assert stats.json()["class_count"] == 7
    assert stats.json()["last_transaction"] == {"student_name": "دانش‌آموز تست 8", "amount": 125_000, "date": "2026-09-20"}
    assert stats.json()["last_course"]["code"] == "C-DELETED-TEACHER"
    debt_body = debt.json()
    assert debt_body["student_id"] == 1
    assert debt_body["wallet_teacher"] == -10_000 and debt_body["wallet_institute"] == 5_000
    assert debt_body["calculated_total_debt"] == 2_000_000
    assert [row["id"] for row in transactions.json()] == [6, 4, 3, 2, 1]
    assert transactions.json()[0]["course_name"] == "فیزیک دوکلاسه"
    assert students.json() == [{"id": 1, "name": "دانش‌آموز تست 1", "national_code": "0020000001", "mobile": "09350000001", "role": "student", "is_suspended": False}]
    assert teachers.json()[0]["name"] == "رضا فعال"


def test_dashboard_last_transaction_uses_direct_student_link(client, auth_headers):
    body = client.get("/dashboard/stats", headers=auth_headers["admin"]).json()
    assert body["last_transaction"]["student_name"] == "دانش‌آموز تست 8"


def test_admin_settings_search_and_history_shapes(client, auth_headers):
    headers = auth_headers["admin"]
    settings = client.get("/admin/institute_settings", headers=headers)
    original_settings = settings.json()
    teacher_settings = client.get("/admin/institute_settings", headers=auth_headers["teacher"])
    update_payload = {**original_settings, "name": "آموزشگاه ممیزی موقت"}
    updated_settings = client.put("/admin/institute_settings", json=update_payload, headers=headers)
    share = client.get("/config/share", headers=headers)
    pricing = client.get("/admin/pricing_table", headers=headers)
    history = client.get("/admin/session_history", headers=headers)
    session_export = client.get("/admin/session_history", params={"export": "true"}, headers=headers)
    pending_classes = client.get("/admin/pending_classes", headers=headers)
    parents = client.get("/admin/parent_contacts", params={"class_id": 1}, headers=headers)
    pending_teachers = client.get("/teachers/pending", headers=headers)
    assert all(response.status_code == 200 for response in (settings, teacher_settings, updated_settings, share, pricing, history, session_export, pending_classes, parents, pending_teachers))
    assert settings.json()["name"] == "آموزشگاه ممیزی"
    assert teacher_settings.json()["card_number"] is None
    assert updated_settings.json()["settings"]["name"] == "آموزشگاه ممیزی موقت"
    assert settings.json()["live_session_max_minutes"] == 180
    assert share.json()["count_1"] == 10_000 and share.json()["count_15"] == 150_000
    assert pricing.json()[0]["category"] == "elementary"
    assert pricing.json()[0]["count_5"] == 500
    assert history.json()["count"] == 2
    assert [item["id"] for item in history.json()["items"]] == [2, 1]
    assert history.json()["items"][0]["financial_status"]["has_financial_effect"] is False
    assert session_export.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument")
    assert pending_classes.json()[0]["id"] == 5
    assert parents.json()[0]["student_id"] == 1
    assert pending_teachers.json() == []
    restored_settings = client.put("/admin/institute_settings", json=original_settings, headers=headers)
    assert restored_settings.status_code == 200


def test_admin_profiles_archive_and_today_contracts(client, auth_headers, frozen_server_clock):
    headers = auth_headers["admin"]
    profile = client.get("/admin/students/1/full_profile", headers=headers)
    deleted = client.get("/admin/deleted_classes", headers=headers)
    deleted_detail = client.get("/admin/deleted_classes/4", headers=headers)
    today = client.get("/admin/today_summary", headers=headers)
    credentials = client.get("/admin/teachers/1/credentials", headers=headers)
    assert all(response.status_code == 200 for response in (profile, deleted, deleted_detail, today, credentials))
    body = profile.json()
    assert body["info"]["name"] == "دانش‌آموز تست 1"
    assert [row["enrollment_id"] for row in body["enrollments"]] == [1, 2]
    assert body["total_debt"] == 2_000_000
    assert deleted.json()[0]["id"] == 4
    assert deleted.json()[0]["title"] == "کلاس آرشیوی"
    assert deleted_detail.json()["id"] == 4
    assert deleted_detail.json()["archived_enrollments_count"] == 1
    assert {"date", "day_name", "scheduled_classes", "today_payments", "installment_alerts"} <= today.json().keys()
    # The suite freezes server wall-clock reads at FIXED_NOW; derive expectations
    # from that shared fixture and the project's central Jalali/schedule helpers.
    from today_summary import PERSIAN_DAY_NAMES as _PERSIAN_DAY_NAMES
    from today_summary import jalali_date_string as _jalali_date_string
    from today_summary import schedule_matches_date as _schedule_matches_date

    _today = frozen_server_clock
    assert today.json()["date"] == _jalali_date_string(_today)
    assert today.json()["day_name"] == _PERSIAN_DAY_NAMES[_today.weekday()]
    _expected_scheduled = 3 if _schedule_matches_date("شنبه,دوشنبه", _today) else 0
    assert today.json()["scheduled_classes"] == _expected_scheduled
    assert credentials.json()["name"] == "رضا فعال"
    assert credentials.json()["teacher_code"] == 1001
    assert credentials.json()["password"]


def test_admin_sms_is_local_log_only_and_masks_numeric_payload(client, auth_headers, db):
    import models
    headers = auth_headers["admin"]
    before = db.query(models.SmsLog).count()
    sent = client.post("/sms/send", json={"target_group": "all_students", "message_text": "کد 123456 برای آزمون"}, headers=headers)
    assert sent.status_code == 200
    assert sent.json() == {"message": "ارسال شد", "count": 29}
    history = client.get("/sms/history", headers=headers)
    assert history.status_code == 200
    assert history.json()[0]["message_text"] == "کد *** برای آزمون"
    assert history.json()[0]["sent_count"] == 29
    created = db.query(models.SmsLog).order_by(models.SmsLog.id.desc()).first()
    assert db.query(models.SmsLog).count() == before + 1
    db.delete(created)
    db.commit()


def test_admin_share_and_pricing_updates_restore_seed(client, auth_headers, db):
    import models
    headers = auth_headers["admin"]
    share = db.query(models.InstituteShare).first()
    original_share = {f"count_{i}": getattr(share, f"count_{i}") for i in range(1, 16)}
    update_share = {**original_share, "count_1": 12_345, "count_15": 54_321}
    response = client.post("/config/share/update", json=update_share, headers=headers)
    assert response.status_code == 200
    assert client.get("/config/share", headers=headers).json()["count_1"] == 12_345
    pricing = db.query(models.PricingTable).first()
    original_pricing = {f"count_{i}": getattr(pricing, f"count_{i}") for i in range(1, 6)}
    update_pricing = {"rows": [{"category": pricing.category, **{**original_pricing, "count_3": 333}}]}
    response = client.put("/admin/pricing_table", json=update_pricing, headers=headers)
    assert response.status_code == 200
    assert client.get("/admin/pricing_table", headers=headers).json()[0]["count_3"] == 333
    for key, value in original_share.items():
        setattr(share, key, value)
    for key, value in original_pricing.items():
        setattr(pricing, key, value)
    db.commit()


def test_admin_exports_and_credentials_validation(client, auth_headers, db):
    import models
    headers = auth_headers["admin"]
    excel = client.get("/admin/transactions/list/excel", headers=headers)
    assert excel.status_code == 200
    assert excel.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument")
    assert len(excel.content) > 100
    invalid_logo = client.post("/admin/institute_settings/upload_logo", files={"file": ("logo.txt", b"not an image", "text/plain")}, headers=headers)
    assert invalid_logo.status_code == 400

    teacher = db.get(models.Teacher, 1)
    shadow_session = db.query(models.UserSession).filter(models.UserSession.teacher_id == 1).first()
    shadow = db.get(models.User, shadow_session.user_id)
    old_card, old_shadow_username = teacher.card_number, shadow.username
    updated = client.put("/admin/teachers/1/credentials", json={"mobile": teacher.mobile, "card_number": "6037000000099999"}, headers=headers)
    assert updated.status_code == 200
    db.expire_all()
    assert db.get(models.Teacher, 1).card_number == "6037000000099999"
    db.get(models.Teacher, 1).card_number = old_card
    db.get(models.User, shadow.id).username = old_shadow_username
    db.query(models.ActivityLog).filter(models.ActivityLog.action == "update_teacher_credentials", models.ActivityLog.target_id == 1).delete(synchronize_session=False)
    db.commit()


def test_admin_single_class_approval_rejects_schedule_conflict_without_write(client, auth_headers, db):
    import models
    headers = auth_headers["admin"]
    course = db.get(models.Course, 5)
    original = (course.is_admin_approved, course.rejection_reason, course.pending_since)
    response = client.post("/admin/approve_class/5", headers=headers)
    assert response.status_code == 409
    db.expire_all()
    course = db.get(models.Course, 5)
    assert (course.is_admin_approved, course.rejection_reason, course.pending_since) == original


def test_admin_remaining_delete_approval_and_logic_guards_roundtrip(client, auth_headers, db):
    import models
    headers = auth_headers["admin"]
    assert client.post("/teachers/approve/3", headers=headers).status_code == 404
    assert client.delete("/teachers/reject/3", headers=headers).status_code == 404
    assert client.delete("/admin/teachers/1", headers=headers).status_code == 400
    assert client.delete("/admin/students/999", headers=headers).status_code == 404

    course = db.get(models.Course, 6)
    original_course = (course.is_deleted, course.rejection_reason)
    before_requests = {row.id for row in db.query(models.ClassDeletionRequest).filter(models.ClassDeletionRequest.course_id == 6).all()}
    rejected = client.delete("/admin/reject_class/6", params={"reason": "عدم تایید ممیزی"}, headers=headers)
    assert rejected.status_code == 200
    db.expire_all()
    assert db.get(models.Course, 6).is_deleted is True
    db.get(models.Course, 6).is_deleted, db.get(models.Course, 6).rejection_reason = original_course
    db.query(models.ClassDeletionRequest).filter(models.ClassDeletionRequest.course_id == 6, ~models.ClassDeletionRequest.id.in_(before_requests)).delete(synchronize_session=False)
    db.commit()

    transaction = db.get(models.Transaction, 4)
    student = db.get(models.Student, 6)
    snapshot = {column.name: getattr(transaction, column.name) for column in models.Transaction.__table__.columns}
    original_wallets = (student.wallet_institute, student.wallet_balance)
    deleted = client.delete("/admin/transactions/4", headers=headers)
    assert deleted.status_code == 200
    db.expire_all()
    assert db.get(models.Transaction, 4) is None
    assert db.get(models.Student, 6).wallet_institute == original_wallets[0] - 75_000
    db.add(models.Transaction(**snapshot))
    restored_student = db.get(models.Student, 6)
    restored_student.wallet_institute, restored_student.wallet_balance = original_wallets
    db.commit()

    roundtrip = client.post("/test/transaction_logic", json={"student_id": 6, "amount": 12_345, "target_wallet": "teacher", "description": "audit roundtrip", "payment_method": "نقدی", "date": "1405/06/08"}, headers=headers)
    assert roundtrip.status_code == 200
    assert roundtrip.json()["test_passed"] is True


def test_admin_transaction_update_preserves_ledger_and_wallet_invariant(client, auth_headers, db):
    import models
    headers = auth_headers["admin"]
    transaction = db.get(models.Transaction, 4)
    student = db.get(models.Student, 6)
    original = (transaction.amount, transaction.description, transaction.date, student.wallet_institute, student.wallet_balance)
    response = client.put("/admin/transactions/4", json={"amount": 76_000, "description": "ویرایش ممیزی", "date": "1405/06/08"}, headers=headers)
    assert response.status_code == 200
    db.expire_all()
    assert db.get(models.Transaction, 4).amount == 76_000
    assert db.get(models.Transaction, 4).description == "ویرایش ممیزی"
    assert db.get(models.Student, 6).wallet_institute == original[3] + 1_000
    assert db.get(models.Student, 6).wallet_balance == db.get(models.Student, 6).wallet_teacher + db.get(models.Student, 6).wallet_institute
    transaction = db.get(models.Transaction, 4); student = db.get(models.Student, 6)
    transaction.amount, transaction.description, transaction.date = original[:3]
    student.wallet_institute, student.wallet_balance = original[3:]
    db.commit()


def test_admin_reset_teacher_password_rotates_shadow_and_restores_seed(client, auth_headers, db):
    import models
    headers = auth_headers["admin"]
    teacher = db.get(models.Teacher, 1)
    shadow_session = db.query(models.UserSession).filter(models.UserSession.teacher_id == 1).first()
    shadow = db.get(models.User, shadow_session.user_id)
    sequence = db.query(models.SequenceCounter).filter(models.SequenceCounter.name == "teacher").first()
    original = (teacher.teacher_code, teacher.password, shadow.password, sequence.current_value if sequence else None)
    response = client.post("/admin/teachers/1/credentials/reset_password", headers=headers)
    assert response.status_code == 200
    assert len(response.json()["new_password"]) == 8
    db.expire_all()
    teacher = db.get(models.Teacher, 1); shadow = db.get(models.User, shadow.id)
    assert teacher.teacher_code != original[0]
    assert teacher.password == shadow.password
    assert teacher.password != original[1]
    teacher.teacher_code, teacher.password = original[:2]
    shadow.password = original[2]
    if sequence:
        sequence.current_value = original[3]
    db.query(models.ActivityLog).filter(models.ActivityLog.action == "reset_teacher_password", models.ActivityLog.target_id == 1).delete(synchronize_session=False)
    db.commit()


def test_admin_bulk_suspend_and_bulk_sms_restore_fixture(client, auth_headers, db):
    import models
    headers = auth_headers["admin"]
    courses = [db.get(models.Course, cid) for cid in (5, 6)]
    original = [course.is_suspended for course in courses]
    suspended = client.post("/admin/classes/suspend_bulk", json={"course_ids": [5, 6, 999]}, headers=headers)
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "success"
    assert [item["status"] for item in suspended.json()["results"]] == ["success", "success", "failed"]
    db.expire_all()
    assert all(db.get(models.Course, cid).is_suspended is True for cid in (5, 6))

    before_logs = {row.id for row in db.query(models.SmsLog).all()}
    bulk = client.post("/sms/send_bulk", json={"student_ids": [1, 999]}, headers=headers)
    assert bulk.status_code == 200
    assert [item["status"] for item in bulk.json()["results"]] == ["success", "failed"]
    created_logs = db.query(models.SmsLog).filter(~models.SmsLog.id.in_(before_logs)).all()
    assert len(created_logs) == 1 and created_logs[0].sent_count == 1
    for row in created_logs:
        db.delete(row)
    for course, value in zip(courses, original):
        course.is_suspended = value
    db.commit()


def test_admin_session_reopen_and_archived_class_restore_are_atomic(client, auth_headers, db):
    import models
    headers = auth_headers["admin"]
    session = db.get(models.SessionLog, 2)
    original_status = session.status
    reopened = client.post("/admin/session_history/2/reopen", params={"reason": "اصلاح ممیزی"}, headers=headers)
    assert reopened.status_code == 200
    assert reopened.json()["session_id"] == 2
    db.expire_all()
    assert db.get(models.SessionLog, 2).status == "Reopened"
    blocked = client.post("/admin/session_history/1/reopen", params={"reason": "نباید باز شود"}, headers=headers)
    assert blocked.status_code == 409

    course = db.get(models.Course, 4)
    original_deleted = course.is_deleted
    original_enrollments = db.query(models.Enrollment).filter(models.Enrollment.course_id == 4).count()
    restored = client.post("/admin/deleted_classes/4/restore", json={"mode": "metadata_only", "reason": "ممیزی restore"}, headers=headers)
    assert restored.status_code == 200
    assert restored.json()["mode"] == "metadata_only"
    assert restored.json()["finances_untouched"] is True
    db.expire_all()
    assert db.get(models.Course, 4).is_deleted is False
    assert db.query(models.Enrollment).filter(models.Enrollment.course_id == 4).count() == original_enrollments
    db.query(models.ClassRestoreLog).filter(models.ClassRestoreLog.course_id == 4).delete(synchronize_session=False)
    db.query(models.ActivityLog).filter(models.ActivityLog.action == "restore_class_metadata", models.ActivityLog.target_id == 4).delete(synchronize_session=False)
    db.get(models.Course, 4).is_deleted = original_deleted
    db.get(models.SessionLog, 2).status = original_status
    db.query(models.ActivityLog).filter(models.ActivityLog.action == "session_reopen", models.ActivityLog.target_id == 2).delete(synchronize_session=False)
    db.commit()


def test_admin_student_and_teacher_toggles_restore_state(client, auth_headers, db):
    import models
    headers = auth_headers["admin"]
    student = db.get(models.Student, 1)
    teacher = db.get(models.Teacher, 1)
    old_student, old_teacher = student.is_suspended, teacher.is_suspended
    student_result = client.post("/admin/students/1/toggle_suspend", headers=headers)
    teacher_result = client.post("/admin/teachers/1/suspend", headers=headers)
    assert student_result.status_code == teacher_result.status_code == 200
    assert student_result.json()["is_suspended"] is (not old_student)
    assert teacher_result.json()["is_suspended"] is (not old_teacher)
    db.expire_all()
    assert db.get(models.Student, 1).is_suspended is (not old_student)
    assert db.get(models.Teacher, 1).is_suspended is (not old_teacher)
    db.get(models.Student, 1).is_suspended = old_student
    db.get(models.Teacher, 1).is_suspended = old_teacher
    db.commit()
