"""لایهٔ service — چرخهٔ حذف/بازیابی کلاس (REFAC P3a).

چرا این ماژول: اسنپ‌شاتِ لحظهٔ حذف، خودِ عملیات آرشیو کلاس و ثبتِ تصمیمِ
(تایید/رد) در `ActivityLog`، منطق دامنه‌ایِ نوشتاری/خواندنی هستند نه لایهٔ HTTP.
پیش‌تر وسط `routers/classes.py` بودند و `routers/admin.py` هم برای استفاده از آن‌ها
از روترِ دیگر import می‌کرد (`from routers.classes import _apply_class_deletion,
_build_class_deletion_snapshot`). حالا یک لایهٔ service مشترک است.

کد **بایت‌به‌بایت** منتقل شده و هیچ منطقی تغییر نکرده؛ `routers/classes.py` همان
نام‌ها را re-export می‌کند تا مسیرهای import قبلی (از جمله admin.py) دست‌نخورده کار کنند.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from dependencies import display_name, get_enrollment_tuition_and_discount
from financial_calculations import calculate_enrollment_debt_breakdown
from models import ActivityLog, Attendance, Course, Enrollment, SessionLog, Student


def _build_class_deletion_snapshot(db: Session, course) -> dict:
    """اسنپ‌شات لحظه درخواست: جلسات رفته و بدهی هر شاگرد + اثر حذف بر معلم."""
    sessions = db.query(SessionLog).filter(SessionLog.is_deleted == False, SessionLog.course_id == course.id).all()
    session_ids = [s.id for s in sessions]
    enrollments = db.query(Enrollment).filter(Enrollment.is_deleted == False, Enrollment.course_id == course.id).all()
    students_rows = []
    total_debt = 0
    total_paid = 0
    for en in enrollments:
        st = db.query(Student).filter(Student.id == en.student_id).first()
        attended = 0
        if session_ids:
            attended = db.query(func.count(Attendance.id)).filter(
                Attendance.session_id.in_(session_ids),
                Attendance.student_id == en.student_id,
                Attendance.is_deleted == False,   # FIX (F-S2): آرشیوشده‌ها در «جلسات حاضرشده» نمی‌آیند.
                Attendance.status.in_(["Present", "Late"])
            ).scalar() or 0
        final_tuition, _ = get_enrollment_tuition_and_discount(en)
        breakdown = calculate_enrollment_debt_breakdown(db, en)
        paid = breakdown["paid_teacher"] + breakdown["paid_institute"]
        debt = breakdown["debt"]
        total_debt += debt
        total_paid += paid
        students_rows.append({
            "student_id": en.student_id,
            "name": display_name(st, "نامشخص"),
            "sessions_attended": attended,
            "tuition_final": final_tuition,
            "total_paid": paid,
            "debt": debt,
            "wallet_teacher": st.wallet_teacher if st and st.wallet_teacher is not None else 0,
            "wallet_institute": st.wallet_institute if st and st.wallet_institute is not None else 0,
        })
    # طلب معلم از همین کلاس (اثر حذف بر معلم) — همان منطق pending_settlement محدود به این کلاس
    teacher_pending = 0
    if session_ids:
        unbilled = {r[0] for r in db.query(Attendance.session_id).filter(
            Attendance.session_id.in_(session_ids),
            Attendance.is_billed == False,
            Attendance.is_deleted == False,   # FIX (F-S2): آرشیوشده‌ها طلب معلم را باز نمی‌کنند.
            Attendance.status.in_(["Present", "Late"])
        ).distinct().all()}
        # FIX: H6(A2) - طلب معلم = مبالغ قراردادی + جریمه‌ی غایبین غیرموجه.
        # FIX H8-gap/follow-up: شاخه‌ی جریمه هم طلب است (همان منطق دوشاخه‌ی settle).
        teacher_pending = sum((s.final_teacher_cost or 0) + (s.absent_penalty_teacher or 0) for s in sessions if s.id in unbilled or ((s.absent_penalty_teacher or 0) > 0 and not s.is_penalty_settled))
    return {
        "course_id": course.id,
        "course_title": course.title,
        "course_code": course.code,
        "sessions_total": len(session_ids),
        "students": students_rows,
        "totals": {
            "students": len(students_rows),
            "total_debt": total_debt,
            "total_paid": total_paid,
            "teacher_pending_this_class": teacher_pending,
        },
    }


def _apply_class_deletion(db: Session, course, forgive_session_charges: bool):
    """Archive a class and return deletion-scoped restore provenance.

    Only rows actually transitioned by this deletion are recorded. Financial
    row snapshots and wallet credits are stored with the approved deletion
    request so later restores can be exact and fail closed on legacy records.
    """
    from dependencies import perform_delete_enrollment

    course.is_deleted = True
    enrollment_ids = []
    transaction_rows = []
    installment_rows = []
    wallet_credits = {}
    enrollments = db.query(Enrollment).filter(
        Enrollment.is_deleted == False,
        Enrollment.course_id == course.id,
    ).all()
    for enrollment in enrollments:
        effect = perform_delete_enrollment(
            enrollment, db, forgive_session_charges=forgive_session_charges
        )
        if not effect.get("enrollment_archived"):
            continue
        enrollment_ids.append(int(enrollment.id))
        transaction_rows.extend(effect.get("transaction_rows") or [])
        installment_rows.extend(effect.get("installment_rows") or [])
        for raw_student_id, amounts in (effect.get("wallet_credits") or {}).items():
            student_id = int(raw_student_id)
            aggregate = wallet_credits.setdefault(student_id, {"teacher": 0, "institute": 0})
            aggregate["teacher"] += int(amounts.get("teacher") or 0)
            aggregate["institute"] += int(amounts.get("institute") or 0)

    session_ids = []
    if forgive_session_charges:
        session_ids = [int(row[0]) for row in db.query(SessionLog.id).filter(
            SessionLog.is_deleted == False,
            SessionLog.course_id == course.id,
        ).all()]
        if session_ids:
            db.query(SessionLog).filter(
                SessionLog.id.in_(session_ids),
                SessionLog.is_deleted == False,
            ).update({SessionLog.is_deleted: True}, synchronize_session="fetch")

    return {
        "version": 1,
        "enrollment_ids": sorted(set(enrollment_ids)),
        "session_ids": sorted(set(session_ids)),
        "transaction_rows": sorted(transaction_rows, key=lambda row: int(row["id"])),
        "installment_rows": sorted(installment_rows, key=lambda row: int(row["id"])),
        "wallet_credits": [
            {"student_id": student_id, **amounts}
            for student_id, amounts in sorted(wallet_credits.items())
        ],
    }


def _record_class_decision(db: Session, course: Course, action: str, reason: str | None):
    course.is_admin_approved = action == "approve"
    course.rejection_reason = None if action == "approve" else (reason or "بدون توضیح")
    course.pending_since = None
    db.add(ActivityLog(
        admin_username="group6", action=f"class_{action}", target_id=course.id,
        target_name=course.title, details=course.rejection_reason
    ))
