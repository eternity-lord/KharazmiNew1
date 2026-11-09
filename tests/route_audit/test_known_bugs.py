"""Regression checks for known findings and their agreed contracts.

Unresolved issues remain in questions.md rather than being converted into
assumed behavior.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from .kotlin_contract import audit_payload


def test_O02_android_push_client_registers_FCM_token():
    root = Path(__file__).parents[2] / "KharazmiAdmin/app/src/main"
    source = "\n".join(path.read_text(encoding="utf-8") for path in (root / "java").rglob("*.kt"))
    model_source = (root / "java/com/example/kharazmiadmin/AppModels.kt").read_text(encoding="utf-8")
    manifest = (root / "AndroidManifest.xml").read_text(encoding="utf-8")
    gradle = (root.parents[1] / "build.gradle.kts").read_text(encoding="utf-8")
    assert "FirebaseMessaging.getInstance" in source
    assert '@POST("auth/device_token")' in source
    assert '@SerializedName("token") val token: String' in model_source
    assert "override fun onNewToken(token: String)" in source
    assert "PushTokenRegistration.refreshAndRegister(applicationContext)" in source
    assert 'android:name=".PushMessagingService"' in manifest
    assert "firebase-messaging" in gradle
    assert "FCM_SERVER_KEY" not in source, "FCM server credentials must stay on the backend"


def test_O12_unpublished_exam_is_hidden_from_student(client, auth_headers):
    response = client.get("/exams/student/list", headers=auth_headers["student"])
    assert response.status_code == 200, response.text
    assert all(row["id"] != 2 for row in response.json())


def test_O14_parent_exam_decimal_max_score_is_not_parsed_as_Int():
    issues = audit_payload("ParentExamItem", {"course_title": "ریاضی", "title": "آزمون", "date": "1405/06/25", "max_score": 12.5})
    assert not any(issue.kind == "int-parse" and issue.field == "max_score" for issue in issues)


def _o19_restore_fixture(db, *, teacher_wallet=1_000, institute_wallet=2_000,
                         share_teacher=100, share_institute=50):
    import models

    student = db.get(models.Student, 1)
    old_wallet = (student.wallet_teacher, student.wallet_institute, student.wallet_balance)
    student.wallet_teacher = teacher_wallet
    student.wallet_institute = institute_wallet
    student.wallet_balance = teacher_wallet + institute_wallet
    course = models.Course(
        title="کلاس آزمون بازیابی O-19",
        code=f"O19-{uuid.uuid4().hex[:12]}",
        teacher_id=1,
        branch_id=1,
        is_admin_approved=True,
        is_deleted=False,
        days_of_week="شنبه",
        class_time="10:00",
        teacher_session_price=share_teacher,
    )
    db.add(course)
    db.flush()
    enrollment = models.Enrollment(
        student_id=student.id,
        course_id=course.id,
        branch_id=1,
        register_date="1405/07/01",
        shift="صبح",
        total_tuition=500_000,
        total_paid=0,
        is_deleted=False,
    )
    db.add(enrollment)
    db.flush()
    session = models.SessionLog(
        course_id=course.id,
        date="1405/07/02",
        time="10:00",
        final_teacher_cost=share_teacher,
        final_institute_share=share_institute,
        cost_per_student=share_teacher + share_institute,
        attendee_count=1,
        status="Finished",
        is_deleted=False,
    )
    db.add(session)
    db.flush()
    attendance = models.Attendance(
        session_id=session.id,
        student_id=student.id,
        status="Present",
        is_deleted=False,
        is_billed=False,
    )
    transaction = models.Transaction(
        student_id=student.id,
        course_id=course.id,
        enrollment_id=enrollment.id,
        session_id=session.id,
        branch_id=1,
        amount=share_teacher + share_institute,
        type="session_charge",
        date="1405/07/02",
        description="هزینهٔ جلسهٔ آزمایشی",
        share_teacher=share_teacher,
        share_institute=share_institute,
        is_deleted=False,
        is_reversed=False,
    )
    installment = models.Installment(
        enrollment_id=enrollment.id,
        amount=250_000,
        due_date="1405/07/10",
        is_paid=False,
        paid_amount=0,
        is_deleted=False,
    )
    db.add_all([attendance, transaction, installment])
    db.commit()
    return {
        "course_id": course.id,
        "enrollment_id": enrollment.id,
        "session_id": session.id,
        "attendance_id": attendance.id,
        "transaction_id": transaction.id,
        "installment_id": installment.id,
        "student_id": student.id,
        "old_wallet": old_wallet,
        "start_wallet": (teacher_wallet, institute_wallet, teacher_wallet + institute_wallet),
        "credit": (share_teacher, share_institute),
    }


def _delete_o19_fixture(client, auth_headers, db, fixture):
    import models

    response = client.delete(f"/classes/{fixture['course_id']}", headers=auth_headers["admin"])
    assert response.status_code == 200, response.text
    db.expire_all()
    student = db.get(models.Student, fixture["student_id"])
    assert (student.wallet_teacher, student.wallet_institute) == (
        fixture["start_wallet"][0] + fixture["credit"][0],
        fixture["start_wallet"][1] + fixture["credit"][1],
    )


def _cleanup_o19_fixture(db, fixture):
    import models

    db.rollback()
    db.expire_all()
    course_id = fixture["course_id"]
    enrollment_id = fixture["enrollment_id"]
    db.query(models.ClassRestoreLog).filter(models.ClassRestoreLog.course_id == course_id).delete(synchronize_session=False)
    db.query(models.ClassDeletionRequest).filter(models.ClassDeletionRequest.course_id == course_id).delete(synchronize_session=False)
    db.query(models.ActivityLog).filter(models.ActivityLog.target_id == course_id).delete(synchronize_session=False)
    db.query(models.Attendance).filter(models.Attendance.session_id.in_(
        db.query(models.SessionLog.id).filter(models.SessionLog.course_id == course_id)
    )).delete(synchronize_session=False)
    db.query(models.Transaction).filter(models.Transaction.course_id == course_id).delete(synchronize_session=False)
    db.query(models.Installment).filter(models.Installment.enrollment_id == enrollment_id).delete(synchronize_session=False)
    db.query(models.Enrollment).filter(models.Enrollment.id == enrollment_id).delete(synchronize_session=False)
    db.query(models.SessionLog).filter(models.SessionLog.course_id == course_id).delete(synchronize_session=False)
    db.query(models.Course).filter(models.Course.id == course_id).delete(synchronize_session=False)
    student = db.get(models.Student, fixture["student_id"])
    student.wallet_teacher, student.wallet_institute, student.wallet_balance = fixture["old_wallet"]
    db.commit()


def test_O19_restore_class_restores_operational_history_and_optional_finance(client, auth_headers, db):
    import models

    fixture = _o19_restore_fixture(db)
    try:
        _delete_o19_fixture(client, auth_headers, db, fixture)
        detail = client.get(
            f"/admin/deleted_classes/{fixture['course_id']}", headers=auth_headers["admin"]
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["financial_restore_available"] is True

        response = client.post(
            f"/admin/deleted_classes/{fixture['course_id']}/restore",
            json={"include_financial_history": True, "reason": "audit reproduction"},
            headers=auth_headers["admin"],
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["mode"] == "full"
        assert body["include_financial_history"] is True
        assert body["finances_untouched"] is False
        db.expire_all()
        assert db.get(models.Course, fixture["course_id"]).is_deleted is False
        assert db.get(models.Enrollment, fixture["enrollment_id"]).is_deleted is False
        assert db.get(models.SessionLog, fixture["session_id"]).is_deleted is False
        assert db.get(models.Attendance, fixture["attendance_id"]).is_deleted is False
        assert db.get(models.Transaction, fixture["transaction_id"]).is_deleted is False
        assert db.get(models.Installment, fixture["installment_id"]).is_deleted is False
        student = db.get(models.Student, fixture["student_id"])
        assert (student.wallet_teacher, student.wallet_institute, student.wallet_balance) == fixture["start_wallet"]
        restore_log = db.query(models.ClassRestoreLog).filter_by(course_id=fixture["course_id"]).one()
        assert restore_log.mode == "full" and restore_log.finance_touched is True
        second = client.post(
            f"/admin/deleted_classes/{fixture['course_id']}/restore",
            json={"include_financial_history": True}, headers=auth_headers["admin"],
        )
        assert second.status_code == 409
    finally:
        _cleanup_o19_fixture(db, fixture)


def test_O19_financial_restore_blocks_spent_credit_atomically_but_allows_operational(client, auth_headers, db):
    import models

    fixture = _o19_restore_fixture(
        db, teacher_wallet=25, institute_wallet=70, share_teacher=100, share_institute=50
    )
    try:
        _delete_o19_fixture(client, auth_headers, db, fixture)
        student = db.get(models.Student, fixture["student_id"])
        student.wallet_teacher = 90  # credit of 100 was partly spent
        student.wallet_institute = 120
        student.wallet_balance = 210
        db.commit()

        response = client.post(
            f"/admin/deleted_classes/{fixture['course_id']}/restore",
            json={"mode": "full", "include_financial_history": True},
            headers=auth_headers["admin"],
        )
        assert response.status_code == 409
        assert "اعتبار" in response.json()["detail"]
        db.expire_all()
        assert db.get(models.Course, fixture["course_id"]).is_deleted is True
        assert db.get(models.Enrollment, fixture["enrollment_id"]).is_deleted is True
        assert db.get(models.SessionLog, fixture["session_id"]).is_deleted is True
        assert db.get(models.Transaction, fixture["transaction_id"]).is_deleted is True
        assert db.get(models.Installment, fixture["installment_id"]).is_deleted is True
        student = db.get(models.Student, fixture["student_id"])
        assert (student.wallet_teacher, student.wallet_institute, student.wallet_balance) == (90, 120, 210)
        assert db.query(models.ClassRestoreLog).filter_by(course_id=fixture["course_id"]).count() == 0

        # Financial choice off remains available and must leave the wallet/ledger untouched.
        nonfinancial = client.post(
            f"/admin/deleted_classes/{fixture['course_id']}/restore",
            json={"mode": "full", "include_financial_history": False},
            headers=auth_headers["admin"],
        )
        assert nonfinancial.status_code == 200, nonfinancial.text
        db.expire_all()
        assert db.get(models.Course, fixture["course_id"]).is_deleted is False
        assert db.get(models.Enrollment, fixture["enrollment_id"]).is_deleted is False
        assert db.get(models.SessionLog, fixture["session_id"]).is_deleted is False
        assert db.get(models.Transaction, fixture["transaction_id"]).is_deleted is True
        assert db.get(models.Installment, fixture["installment_id"]).is_deleted is True
        student = db.get(models.Student, fixture["student_id"])
        assert (student.wallet_teacher, student.wallet_institute, student.wallet_balance) == (90, 120, 210)
    finally:
        _cleanup_o19_fixture(db, fixture)


def test_O19_legacy_deletion_disables_financial_restore_but_keeps_operational_option(client, auth_headers, db):
    import models

    fixture = _o19_restore_fixture(db)
    try:
        # Simulate an old approved deletion snapshot with no row-level restore ledger.
        course = db.get(models.Course, fixture["course_id"])
        course.is_deleted = True
        db.get(models.Enrollment, fixture["enrollment_id"]).is_deleted = True
        db.get(models.SessionLog, fixture["session_id"]).is_deleted = True
        db.get(models.Transaction, fixture["transaction_id"]).is_deleted = True
        db.get(models.Installment, fixture["installment_id"]).is_deleted = True
        db.add(models.ClassDeletionRequest(
            course_id=course.id,
            requested_by_role="admin",
            status="approved",
            forgive_session_charges=True,
            snapshot_json=json.dumps({"students": []}),
        ))
        db.commit()

        detail = client.get(f"/admin/deleted_classes/{course.id}", headers=auth_headers["admin"])
        assert detail.status_code == 200
        assert detail.json()["financial_restore_available"] is False
        blocked = client.post(
            f"/admin/deleted_classes/{course.id}/restore",
            json={"mode": "full", "include_financial_history": True},
            headers=auth_headers["admin"],
        )
        assert blocked.status_code == 409
        db.expire_all()
        assert db.get(models.Course, course.id).is_deleted is True
        assert db.get(models.Enrollment, fixture["enrollment_id"]).is_deleted is True

        operational = client.post(
            f"/admin/deleted_classes/{course.id}/restore",
            json={"mode": "full", "include_financial_history": False},
            headers=auth_headers["admin"],
        )
        assert operational.status_code == 200, operational.text
        assert any("قدیمی" in item for item in operational.json()["warnings"])
        db.expire_all()
        assert db.get(models.Course, course.id).is_deleted is False
        assert db.get(models.Enrollment, fixture["enrollment_id"]).is_deleted is False
        assert db.get(models.SessionLog, fixture["session_id"]).is_deleted is False
        assert db.get(models.Transaction, fixture["transaction_id"]).is_deleted is True
        assert db.get(models.Installment, fixture["installment_id"]).is_deleted is True
        student = db.get(models.Student, fixture["student_id"])
        assert (student.wallet_teacher, student.wallet_institute, student.wallet_balance) == fixture["start_wallet"]
    finally:
        _cleanup_o19_fixture(db, fixture)


def test_O19_restore_conflict_does_not_partially_restore_class_or_history(client, auth_headers, db):
    import models

    fixture = _o19_restore_fixture(db)
    try:
        _delete_o19_fixture(client, auth_headers, db, fixture)
        archived = db.get(models.SessionLog, fixture["session_id"])
        db.add(models.SessionLog(
            course_id=fixture["course_id"],
            date=archived.date,
            time="11:00",
            status="Finished",
            is_deleted=False,
        ))
        db.commit()
        response = client.post(
            f"/admin/deleted_classes/{fixture['course_id']}/restore",
            json={"mode": "full"}, headers=auth_headers["admin"],
        )
        assert response.status_code == 409
        db.expire_all()
        assert db.get(models.Course, fixture["course_id"]).is_deleted is True
        assert db.get(models.Enrollment, fixture["enrollment_id"]).is_deleted is True
        assert db.get(models.SessionLog, fixture["session_id"]).is_deleted is True
        assert db.query(models.ClassRestoreLog).filter_by(course_id=fixture["course_id"]).count() == 0
    finally:
        _cleanup_o19_fixture(db, fixture)
