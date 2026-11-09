
import json

from fastapi import Depends, Header, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from dependencies import check_admin_access, get_db
from models import (
    ActivityLog,
    ClassRestoreLog,
    Course,
    Enrollment,
    Installment,
    SessionLog,
    Student,
    Teacher,
    Transaction,
    User,
)
from schemas import ClassRestoreRequest
from services.class_archive import (
    _archived_deletion_meta,
    _fmt_datetime,
    _latest_class_restore_provenance,
)

"""لایهٔ سرویسِ «بازیابی کلاسِ حذف‌شده».

بدنهٔ دامنه‌ایِ `POST /admin/deleted_classes/{course_id}/restore`: بازیابیِ
متادیتا و تاریخچهٔ عملیاتی یک کلاسِ حذف‌شده، با بازگشتِ اثرهای مالی فقط به‌صورت
opt-in و تنها وقتی منبعِ حذف (provenance) قابل راستی‌آزمایی باشد.

هم‌خانوادهٔ `services/class_archive.py` است (که گزارشِ فقط‌خواندنیِ کلاس‌های
حذف‌شده و منبعِ بازیابی را نگه می‌دارد) و از همان هلپرهایش استفاده می‌کند.

قرارداد لایه در `services/__init__.py`: بدون route و بدون APIRouter؛ handler در
`routers/admin.py` پوستهٔ HTTP باقی مانده — از جمله docstring آن، چون FastAPI
docstring را به‌عنوان `description` در OpenAPI منتشر می‌کند. اسکیمایِ
`ClassRestoreRequest` هم در همین فاز به `schemas.py` (منبعِ یگانهٔ اسکیم‌ها از P2c)
رفت و از روتر بازصادرات می‌شود.
"""


def restore_deleted_class(
    course_id: int,
    data: ClassRestoreRequest,
    db: Session = Depends(get_db),
    authorization: str | None = Header(None),
    _: str = Depends(check_admin_access),
):
    """بدنهٔ دامنه‌ایِ `restore_deleted_class`؛ توضیحِ HTTP در پوستهٔ روتر است."""
    mode = (data.mode or "").strip()
    include_finance = bool(data.include_financial_history)
    if mode not in ("full", "metadata_only"):
        raise HTTPException(status_code=400, detail="mode نامعتبر؛ مقادیر full و metadata_only پشتیبانی می‌شوند")
    if mode == "metadata_only" and include_finance:
        raise HTTPException(status_code=400, detail="بازیابی مالی فقط همراه mode=full مجاز است")

    from routers.analytics import get_user_branch_filter  # lazy: جلوگیری از import چرخه‌ای
    resolved_branch = get_user_branch_filter(db, authorization, None)

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="کلاس آرشیوشده یافت نشد")
    if resolved_branch is not None and course.branch_id != resolved_branch:
        raise HTTPException(status_code=404, detail="کلاس آرشیوشده یافت نشد")
    if course.is_deleted is not True:
        raise HTTPException(status_code=409, detail="این کلاس از قبل فعال است و نیازی به بازیابی ندارد")

    provenance = _latest_class_restore_provenance(db, course.id)
    if include_finance and provenance is None:
        raise HTTPException(
            status_code=409,
            detail="برای این حذف قدیمی سابقهٔ مالی قابل‌اعتماد ثبت نشده است؛ بازیابی مالی انجام نشد. گزینهٔ مالی را خاموش کنید تا اطلاعات عملیاتی بازگردد.",
        )

    if mode == "full":
        if provenance is not None:
            enrollment_ids = list(provenance["enrollment_ids"])
            session_ids = list(provenance["session_ids"])
        else:
            # Old snapshots lack row-level operational provenance. Per the approved
            # policy, operational history can still be restored; finance stays closed.
            enrollment_ids = [row[0] for row in db.query(Enrollment.id).filter(
                Enrollment.course_id == course.id,
                Enrollment.is_deleted == True,
            ).all()]
            session_ids = [row[0] for row in db.query(SessionLog.id).filter(
                SessionLog.course_id == course.id,
                SessionLog.is_deleted == True,
            ).all()]
    else:
        enrollment_ids, session_ids = [], []

    enrollment_ids = sorted(set(int(row_id) for row_id in enrollment_ids))
    session_ids = sorted(set(int(row_id) for row_id in session_ids))
    enrollments = db.query(Enrollment).filter(Enrollment.id.in_(enrollment_ids)).all() if enrollment_ids else []
    sessions = db.query(SessionLog).filter(SessionLog.id.in_(session_ids)).all() if session_ids else []
    if (len(enrollments) != len(enrollment_ids)
            or any(row.course_id != course.id or row.is_deleted is not True for row in enrollments)):
        db.rollback()
        raise HTTPException(status_code=409, detail="وضعیت ثبت‌نام‌های کلاس با سابقهٔ حذف سازگار نیست؛ هیچ تغییری اعمال نشد")
    if (len(sessions) != len(session_ids)
            or any(row.course_id != course.id or row.is_deleted is not True for row in sessions)):
        db.rollback()
        raise HTTPException(status_code=409, detail="وضعیت جلسات کلاس با سابقهٔ حذف سازگار نیست؛ هیچ تغییری اعمال نشد")

    # The active partial unique index on (course_id, date) must remain valid.
    for archived_session in sessions:
        collision = db.query(SessionLog.id).filter(
            SessionLog.course_id == course.id,
            SessionLog.date == archived_session.date,
            SessionLog.is_deleted == False,
            SessionLog.id != archived_session.id,
        ).first()
        if collision:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="برای یکی از جلسات آرشیوشده، جلسهٔ فعال دیگری با همان تاریخ وجود دارد؛ هیچ تغییری اعمال نشد.",
            )

    transaction_rows = provenance["transaction_rows"] if include_finance else []
    installment_rows = provenance["installment_rows"] if include_finance else []
    wallet_credits = provenance["wallet_credits"] if include_finance else []
    enrollment_id_set = set(enrollment_ids)
    transactions = []
    installments = []
    if include_finance:
        transaction_ids = [int(row["id"]) for row in transaction_rows]
        transactions = db.query(Transaction).filter(Transaction.id.in_(transaction_ids)).all() if transaction_ids else []
        if len(transactions) != len(transaction_ids):
            db.rollback()
            raise HTTPException(status_code=409, detail="یکی از تراکنش‌های ثبت‌شده در سابقهٔ حذف پیدا نشد؛ هیچ تغییری اعمال نشد")
        transaction_by_id = {row.id: row for row in transactions}
        transaction_fields = (
            "student_id", "course_id", "enrollment_id", "session_id", "type", "amount",
            "share_teacher", "share_institute",
        )
        # REFAC(P2c/B023): این تابع پیش‌تر **داخل** حلقه تعریف می‌شد و متغیرهای حلقه
        # (`current`/`expected`) را late-bind می‌کرد. چون بی‌درنگ در همان تکرار مصرف می‌شد
        # باگِ عملی نداشت، ولی تلهٔ معروف closure-over-loop-variable بود (ruff B023) و
        # هر تکرار هم یک آبجکت تابع تازه می‌ساخت. حالا یک بار بیرون حلقه تعریف می‌شود و
        # مقادیر را صریح به‌صورت پارامتر می‌گیرد ⇒ رفتار دقیقاً یکسان.
        def _same_transaction_value(field, current_row, expected_row):
            current_value = getattr(current_row, field)
            expected_value = expected_row.get(field)
            if field in ("share_teacher", "share_institute"):
                current_value = current_value or 0
            return current_value == expected_value

        for expected in transaction_rows:
            current = transaction_by_id[int(expected["id"])]
            if current.is_deleted is not True or bool(current.is_reversed):
                db.rollback()
                raise HTTPException(status_code=409, detail="وضعیت یکی از تراکنش‌ها پس از حذف تغییر کرده است؛ هیچ تغییری اعمال نشد")
            if current.course_id != course.id and current.enrollment_id not in enrollment_id_set:
                db.rollback()
                raise HTTPException(status_code=409, detail="تراکنش ثبت‌شده به این کلاس تعلق ندارد؛ هیچ تغییری اعمال نشد")
            if not all(_same_transaction_value(field, current, expected) for field in transaction_fields):
                db.rollback()
                raise HTTPException(status_code=409, detail="اطلاعات یکی از تراکنش‌ها پس از حذف تغییر کرده است؛ هیچ تغییری اعمال نشد")

        installment_ids = [int(row["id"]) for row in installment_rows]
        installments = db.query(Installment).filter(Installment.id.in_(installment_ids)).all() if installment_ids else []
        if len(installments) != len(installment_ids):
            db.rollback()
            raise HTTPException(status_code=409, detail="یکی از اقساط ثبت‌شده در سابقهٔ حذف پیدا نشد؛ هیچ تغییری اعمال نشد")
        installment_by_id = {row.id: row for row in installments}
        installment_fields = ("enrollment_id", "amount", "due_date", "is_paid", "paid_at", "paid_amount")
        for expected in installment_rows:
            current = installment_by_id[int(expected["id"])]
            if (current.is_deleted is not True
                    or current.enrollment_id not in enrollment_id_set
                    or any(getattr(current, field) != expected.get(field) for field in installment_fields)):
                db.rollback()
                raise HTTPException(status_code=409, detail="وضعیت یکی از اقساط پس از حذف تغییر کرده است؛ هیچ تغییری اعمال نشد")

        # Preflight the requested reversal; conditional UPDATEs below repeat this
        # constraint so concurrent spending cannot produce a negative component.
        for credit in wallet_credits:
            student = db.query(Student).filter(Student.id == int(credit["student_id"])).first()
            if not student:
                db.rollback()
                raise HTTPException(status_code=409, detail="دانش‌آموزِ دارای اعتبار مالی پیدا نشد؛ هیچ تغییری اعمال نشد")
            current_teacher = int(student.wallet_teacher or 0)
            current_institute = int(student.wallet_institute or 0)
            delta_teacher = int(credit["teacher"])
            delta_institute = int(credit["institute"])
            if ((delta_teacher > 0 and current_teacher < delta_teacher)
                    or (delta_institute > 0 and current_institute < delta_institute)):
                db.rollback()
                raise HTTPException(
                    status_code=409,
                    detail="اعتبار ایجادشده هنگام حذف خرج شده است و برگشت آن موجودی کیف‌پول را منفی می‌کند؛ بازیابی مالی انجام نشد.",
                )

    meta = _archived_deletion_meta(db, [course.id]).get(course.id, {})
    pre_state = {
        "is_deleted": True,
        "is_suspended": bool(course.is_suspended),
        "archived_enrollments": db.query(Enrollment).filter(
            Enrollment.course_id == course.id, Enrollment.is_deleted == True
        ).count(),
        "archived_sessions": db.query(SessionLog).filter(
            SessionLog.course_id == course.id, SessionLog.is_deleted == True
        ).count(),
        "archived_transactions": db.query(Transaction).filter(
            Transaction.course_id == course.id, Transaction.is_deleted == True
        ).count(),
        "wallet_debit": sum(int(item["teacher"]) + int(item["institute"]) for item in wallet_credits),
        "financial_restore_available": provenance is not None,
    }

    actor_user_id, actor_name = None, ""
    try:
        from dependencies import resolve_actor_user_id
        actor_user_id = resolve_actor_user_id(db, authorization)
        if actor_user_id:
            actor = db.query(User).filter(User.id == actor_user_id).first()
            actor_name = (actor.full_name or actor.username) if actor else ""
    except Exception:
        actor_user_id, actor_name = None, ""

    teacher = db.query(Teacher).filter(Teacher.id == course.teacher_id).first() if course.teacher_id else None
    teacher_archived = bool(teacher is not None and teacher.is_deleted is True)
    warnings = []
    if teacher_archived:
        warnings.append("معلم این کلاس آرشیو (حذف) شده است؛ کلاس بدون معلم فعال برمی‌گردد.")
    elif teacher is None:
        warnings.append("این کلاس معلم ثبت‌شده ندارد؛ پس از بازیابی بدون معلم فعال است.")
    if mode == "full" and provenance is None:
        warnings.append("این حذف قدیمی سابقهٔ ردیف‌به‌ردیف ندارد؛ اطلاعات عملیاتی بازیابی شد اما سوابق مالی دست‌نخورده ماند.")

    try:
        claimed = db.query(Course).filter(
            Course.id == course.id,
            Course.is_deleted == True,
        ).update({Course.is_deleted: False}, synchronize_session=False)
        if claimed != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail="کلاس هم‌زمان بازیابی شده است؛ هیچ تغییری اعمال نشد")

        if enrollment_ids:
            restored = db.query(Enrollment).filter(
                Enrollment.id.in_(enrollment_ids),
                Enrollment.course_id == course.id,
                Enrollment.is_deleted == True,
            ).update({Enrollment.is_deleted: False}, synchronize_session=False)
            if restored != len(enrollment_ids):
                db.rollback()
                raise HTTPException(status_code=409, detail="ثبت‌نام‌ها هم‌زمان تغییر کردند؛ هیچ تغییری اعمال نشد")
        if session_ids:
            restored = db.query(SessionLog).filter(
                SessionLog.id.in_(session_ids),
                SessionLog.course_id == course.id,
                SessionLog.is_deleted == True,
            ).update({SessionLog.is_deleted: False}, synchronize_session=False)
            if restored != len(session_ids):
                db.rollback()
                raise HTTPException(status_code=409, detail="جلسات هم‌زمان تغییر کردند؛ هیچ تغییری اعمال نشد")

        if include_finance:
            transaction_ids = [int(row["id"]) for row in transaction_rows]
            if transaction_ids:
                restored = db.query(Transaction).filter(
                    Transaction.id.in_(transaction_ids),
                    Transaction.is_deleted == True,
                    Transaction.is_reversed == False,
                ).update({Transaction.is_deleted: False}, synchronize_session=False)
                if restored != len(transaction_ids):
                    db.rollback()
                    raise HTTPException(status_code=409, detail="تراکنش‌ها هم‌زمان تغییر کردند؛ هیچ تغییری اعمال نشد")

            installment_ids = [int(row["id"]) for row in installment_rows]
            if installment_ids:
                restored = db.query(Installment).filter(
                    Installment.id.in_(installment_ids),
                    Installment.is_deleted == True,
                ).update({Installment.is_deleted: False}, synchronize_session=False)
                if restored != len(installment_ids):
                    db.rollback()
                    raise HTTPException(status_code=409, detail="اقساط هم‌زمان تغییر کردند؛ هیچ تغییری اعمال نشد")

            for credit in wallet_credits:
                student_id = int(credit["student_id"])
                delta_teacher = int(credit["teacher"])
                delta_institute = int(credit["institute"])
                if not delta_teacher and not delta_institute:
                    continue
                teacher_balance = func.coalesce(Student.wallet_teacher, 0) - delta_teacher
                institute_balance = func.coalesce(Student.wallet_institute, 0) - delta_institute
                criteria = [Student.id == student_id]
                wallet_updates = {Student.wallet_balance: teacher_balance + institute_balance}
                if delta_teacher != 0:
                    wallet_updates[Student.wallet_teacher] = teacher_balance
                if delta_institute != 0:
                    wallet_updates[Student.wallet_institute] = institute_balance
                if delta_teacher > 0:
                    criteria.append(func.coalesce(Student.wallet_teacher, 0) >= delta_teacher)
                if delta_institute > 0:
                    criteria.append(func.coalesce(Student.wallet_institute, 0) >= delta_institute)
                updated = db.query(Student).filter(*criteria).update(
                    wallet_updates,
                    synchronize_session=False,
                )
                if updated != 1:
                    db.rollback()
                    raise HTTPException(
                        status_code=409,
                        detail="اعتبار حذف‌شده دیگر قابل برگشت امن نیست؛ بازیابی مالی انجام نشد و هیچ تغییری اعمال نشد.",
                    )

        db.add(ClassRestoreLog(
            course_id=course.id,
            mode=mode,
            reason=(data.reason or "").strip() or None,
            actor_user_id=actor_user_id,
            actor_name=actor_name or None,
            pre_state_json=json.dumps(pre_state, ensure_ascii=False),
            finance_touched=include_finance,
        ))
        try:
            db.add(ActivityLog(
                admin_username=actor_name or "admin",
                action="restore_class_metadata" if mode == "metadata_only" else "restore_class_full",
                target_id=course.id,
                target_name=course.title or "",
                details=f"restore {mode}; include_financial_history={include_finance} — دلیل: {(data.reason or '').strip() or 'ثبت نشده'}",
            ))
        except Exception:
            pass  # دفتر اصلی بازیابی در ClassRestoreLog است؛ ActivityLog تکمیلی است.
        db.commit()
    except HTTPException:
        raise
    except Exception as error:
        from sqlalchemy.exc import IntegrityError
        db.rollback()
        if isinstance(error, IntegrityError):
            raise HTTPException(
                status_code=409,
                detail="بازیابی با یک دادهٔ فعالِ متعارض روبه‌رو شد؛ هیچ تغییری اعمال نشد.",
            )
        raise

    db.refresh(course)
    finance_note = (
        "سوابق مالی و اعتبارهای برگشتی نیز بازیابی شد."
        if include_finance
        else "تراکنش‌ها و موجودی کیف‌پول تغییر نکرد."
    )
    if mode == "metadata_only":
        response_message = "کلاس بازیابی شد (فقط اطلاعات کلاس؛ تاریخچهٔ مرتبط دست‌نخورده ماند)."
    else:
        response_message = f"کلاس و تاریخچهٔ عملیاتی بازیابی شد؛ {finance_note}"
    return {
        "message": response_message,
        "id": course.id,
        "title": course.title or "",
        "code": course.code or "",
        "is_deleted": bool(course.is_deleted),
        "is_suspended": bool(course.is_suspended),
        "mode": mode,
        "include_financial_history": include_finance,
        "finances_untouched": not include_finance,
        "financial_restore_available": provenance is not None,
        "teacher_archived": teacher_archived,
        "warnings": warnings,
        "note": finance_note,
        "deleted_at_was": _fmt_datetime(meta.get("deleted_at")),
        "reason": (data.reason or "").strip() or "",
    }
