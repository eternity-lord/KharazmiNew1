import datetime
import io
import json  # FIX(A2): snapshot_json برای رکورد حذف کلاس
import os
import re
import secrets  # FIX H12: پسورد تصادفی امن (الگوی C12)
import uuid

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session, joinedload

import models
from dependencies import (
    check_admin_access,
    check_admin_or_secretary_access,
    check_user_login,
    get_current_user,
    get_db,
    get_logged_in_teacher,
    get_next_sequence_value,
    hash_password,
    normalize_mobile,
)

# FIX: Bug 16 - share the tuition-minus-payment debt calculation across financial views.
from financial_calculations import (
    MAX_TEACHER_SESSION_PRICE,
    calculate_student_debt,
)
from models import (
    ActivityLog,
    Attendance,
    Course,
    Enrollment,
    InstituteSettings,
    InstituteShare,
    SessionLog,
    Student,
    Teacher,
    Transaction,
    User,
    UserSession,
)
from schemas import (
    BulkSmsRequest,
    BulkSuspendRequest,
    ClassRestoreRequest,
    InstituteSettingsModel,
    PendingTeacherItem,
    PersonListItem,
    PricingTableUpdateModel,
    ShareConfigModel,
    SmsHistoryItem,
    SmsSendRequest,
    TransactionTestData,
    TransactionUpdate,
)

# REFAC(P3a): خوشهٔ «آرشیو کلاس‌های حذف‌شده» (۴۱۵ خط، ۱۱ تابعِ فقط‌خواندنی) به لایهٔ
# service رفت — services/class_archive.py. این ماژول هنوز ۹ تای آن‌ها را در handlerهای
# `/admin/deleted_classes*` و `/admin/restore_class` صدا می‌زند؛ کد بایت‌به‌بایت منتقل شده
# و هیچ منطقی عوض نشده، فقط جای تعریف از لایهٔ HTTP به لایهٔ service رفته است.
from services.class_archive import (
    _archive_jalali,
    _archive_parse_filter_date,
    _archive_search_variants,
    _archived_class_aggregates,
    _archived_class_people_report,
    _archived_deletion_meta,
    _fmt_datetime,
    _latest_class_restore_provenance,
    _safe_person_name,
)
from storage import resolve_existing, storage_dir

router = APIRouter()


@router.get("/admin/today_summary")
def get_admin_today_summary(
    db: Session = Depends(get_db),
    sub_role: str = Depends(check_user_login),
):
    """Real-time read-only summary for the admin dashboard."""
    if sub_role not in ("admin", "secretary"):
        raise HTTPException(
            status_code=403,
            detail="شما دسترسی لازم برای مشاهده وضعیت امروز را ندارید",
        )

    from today_summary import build_admin_today_summary

    return build_admin_today_summary(db=db, sub_role=sub_role)


@router.get("/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db), _: str = Depends(check_admin_or_secretary_access)):  # FIX (L14/Y3): آمار داشبورد — فقط کارکنان
    student_count = db.query(Student).filter(Student.is_deleted == False).count()
    class_count = db.query(Course).count()

    # FIX: Bug 12 - exclude archived Transaction rows from this active view.
    last_trans = db.query(Transaction).filter(Transaction.is_deleted == False, Transaction.is_reversed == False).order_by(desc(Transaction.id)).first()
    last_trans_data = None
    if last_trans:
        enrollment = (
            db.query(Enrollment)
            .filter(Enrollment.id == last_trans.enrollment_id)
            .first()
        )
        student = None
        if enrollment:
            student = db.query(Student).filter(
                Student.id == enrollment.student_id, Student.is_deleted == False
            ).first()
        # Legacy receipts can retain student_id without an enrollment_id; the
        # direct link is authoritative for the dashboard in that case.
        if student is None and last_trans.student_id is not None:
            student = db.query(Student).filter(
                Student.id == last_trans.student_id, Student.is_deleted == False
            ).first()
        student_name = f"{student.first_name} {student.last_name}" if student else "ناشناس"
        last_trans_data = {
            "student_name": student_name,
            "amount": last_trans.amount,
            "date": last_trans.date,
        }

    last_course = db.query(Course).order_by(desc(Course.id)).first()
    last_course_data = None
    if last_course:
        teacher = db.query(Teacher).filter(Teacher.id == last_course.teacher_id).first()
        teacher_name = (
            f"{teacher.first_name} {teacher.last_name}" if teacher else "نامشخص"
        )
        last_course_data = {
            "title": last_course.title,
            "code": last_course.code,
            "teacher": teacher_name,
            "grade": last_course.grade_level,
        }

    return {
        "student_count": student_count,
        "class_count": class_count,
        "last_transaction": last_trans_data,
        "last_course": last_course_data,
    }


@router.get("/test/debt_calculation")
def test_debt_calculation(db: Session = Depends(get_db), _: str = Depends(check_admin_access)):
    """Test endpoint to verify debt calculation logic"""
    test_student = db.query(Student).first()
    if not test_student:
        return {"error": "No students found in database"}

    # Calculate debt using the new logic
    w_t = test_student.wallet_teacher if test_student.wallet_teacher is not None else 0
    w_i = (
        test_student.wallet_institute
        if test_student.wallet_institute is not None
        else 0
    )

    debt_teacher = abs(w_t) if w_t < 0 else 0
    debt_institute = abs(w_i) if w_i < 0 else 0
    # FIX: Bug 16 - this diagnostic must use the same formula as production debt reports.
    total_debt = calculate_student_debt(db, test_student)

    return {
        "student_id": test_student.id,
        "student_name": f"{test_student.first_name} {test_student.last_name}",
        "wallet_teacher": w_t,
        "wallet_institute": w_i,
        "wallet_balance": test_student.wallet_balance,
        "calculated_debt_teacher": debt_teacher,
        "calculated_debt_institute": debt_institute,
        "calculated_total_debt": total_debt,
        # FIX: Bug 16 - describe the contractual balance and the limited legacy fallback.
        "note": "Debt is discounted tuition minus recorded payments; wallets are an unpriced legacy fallback.",
    }


# ==========================================
# 6. API های حضور و غیاب
# ==========================================


@router.post("/sms/send")
def send_sms(req: SmsSendRequest, db: Session = Depends(get_db), _: str = Depends(check_admin_or_secretary_access)):  # FIX (audit-v2/#10): ارسال گروهی فقط ادمین/منشی
    count = 0
    if req.target_group == "all_students":
        count = db.query(Student).filter(Student.is_deleted == False).count()
    elif req.target_group == "all_teachers":
        count = db.query(Teacher).filter(Teacher.is_deleted == False).count()
    elif req.target_group == "debtors":
        # FIX: Bug 16 - debtor notices must include unpaid tuition even with a positive wallet.
        count = sum(calculate_student_debt(db, student) > 0 for student in db.query(Student).filter(Student.is_deleted == False).all())
    today = datetime.datetime.now().strftime("%Y/%m/%d %H:%M")
    db.add(
        models.SmsLog(
            target_group=req.target_group,
            message_text=req.message_text,
            sent_count=count,
            date=today,
        )
    )
    db.commit()
    return {"message": "ارسال شد", "count": count}


# FIX(security): ماسک کدهای OTP و سایر رشته‌های عددی داخل متن پیامک (کدها ۶رقمی‌اند؛ سال/مبلغ هم ماسک می‌شود).
_OTP_MASK_RE = re.compile(r"\d{4,}")

def _mask_otp_codes(text: str | None) -> str | None:
    if not text:
        return text
    return _OTP_MASK_RE.sub("***", text)


@router.get("/sms/history", response_model=list[SmsHistoryItem])
def get_sms_history(db: Session = Depends(get_db), _: str = Depends(check_admin_or_secretary_access)):  # FIX (L14/R1-align): تاریخچه برای منشی هم باز — چون ارسال (تکی+گروهی) دارد، ندیدن تاریخچه ناسازگار بود.
    logs = db.query(models.SmsLog).order_by(desc(models.SmsLog.id)).all()
    return [
        SmsHistoryItem(
            id=log.id,
            target_group=log.target_group,
            message_text=_mask_otp_codes(log.message_text),
            sent_count=log.sent_count,
            date=log.date,
        )
        for log in logs
    ]


# ==========================================
# 8. API های مدیریت معلم (تایید)
# ==========================================


@router.get("/teachers/pending", response_model=list[PendingTeacherItem])
def get_pending_teachers(
    branch_id: int | None = None,
    db: Session = Depends(get_db),
    authorization: str | None = Header(None),
    _: str = Depends(check_admin_or_secretary_access),  # FIX (audit-v2/#11): لیست درانتظار (حاوی موبایل) فقط ادمین/منشی
):
    """صف «درخواست‌های تایید معلم» — در انتظار (is_approved=False) و حذف‌نشده.

    FIX(teacher-approval):
      • این مسیر قبلاً با route سایه‌شده مواجه بود (GET /teachers/{teacher_id} در teachers.router
        زودتر ثبت می‌شد) و عملاً هرگز اجرا نمی‌شد؛ ترتیب include در main.py اصلاح شد.
      • branch isolation: کاربرِ شعبه‌دار فقط معلم‌های شعبه‌ی خودش **و** رکوردهای بدون شعبه
        (branch_id IS NULL = ثبت‌شده‌ی بدون انتساب، متعلق به هیچ شعبه‌ای نیست) را می‌بیند؛
        رکورد شعبه‌ی دیگر هرگز دیده نمی‌شود. ادمین کل (بدون شعبه) همه را می‌بیند.
      • `branch_id` صریح = فیلتر **دقیق** روی همان شعبه (بدون رکوردهای بدون‌شعبه)؛ برای کاربرِ
        شعبه‌دار، شعبه‌ی خودش بر پارامتر غلبه می‌کند (branch isolation قابل دورزدن با query نیست).
      • ترتیب قطعی (id صعودی) و متادیتای شعبه در پاسخ برای UI ادمین.
    """
    resolved_branch = get_user_branch_filter(db, authorization, branch_id)
    explicit_filter = branch_id is not None

    q = db.query(Teacher).filter(Teacher.is_deleted == False, Teacher.is_approved == False)
    if resolved_branch is not None:
        if explicit_filter:
            q = q.filter(Teacher.branch_id == resolved_branch)      # فیلتر صریح: فقط همان شعبه
        else:
            q = q.filter(or_(Teacher.branch_id == resolved_branch, Teacher.branch_id.is_(None)))
    teachers = q.order_by(Teacher.id).all()

    branch_ids = {t.branch_id for t in teachers if t.branch_id is not None}
    branch_names = {
        b.id: (b.name or "")
        for b in (db.query(models.Branch).filter(models.Branch.id.in_(branch_ids)).all() if branch_ids else [])
    }

    # FIX(security): هرگز ORM خام برنگردان — فقط فیلدهای غیرحساس (بدون password/card_number/national_code).
    return [
        PendingTeacherItem(
            id=t.id,
            first_name=t.first_name or "",
            last_name=t.last_name or "",
            mobile=t.mobile,
            teacher_code=t.teacher_code,
            profile_image=t.profile_image,
            is_approved=bool(t.is_approved),
            is_suspended=bool(t.is_suspended),
            branch_id=t.branch_id,
            branch_name=branch_names.get(t.branch_id, ""),
        )
        for t in teachers
    ]


def _teacher_in_scope(db: Session, teacher, authorization: str | None) -> bool:
    """آیا این معلم در دامنه‌ی کاربرِ فراخوان است؟ (همان policy لیست pending)

    ادمین کل (بدون شعبه) → همه. کاربر شعبه‌دار → فقط شعبه‌ی خودش + رکوردهای بدون شعبه
    (branch_id IS NULL = بدون انتساب، متعلق به هیچ شعبه‌ای نیست). رکورد شعبه‌ی دیگر → خارج از دامنه.
    """
    resolved_branch = get_user_branch_filter(db, authorization, None)
    if resolved_branch is None:
        return True
    return teacher.branch_id == resolved_branch or teacher.branch_id is None


@router.post("/teachers/approve/{teacher_id}")
def approve_teacher(teacher_id: int, db: Session = Depends(get_db),
                    authorization: str | None = Header(None),
                    _: str = Depends(check_admin_or_secretary_access)):  # FIX H10-S2: تایید فقط ادمین/منشی (الگوی C1/H10-S)
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id, Teacher.is_deleted == False).first()
    # FIX(teacher-approval): کاربر شعبه‌دار نباید درخواست شعبه‌ی دیگر را تایید کند (404 بدون نشت وجود رکورد).
    if not teacher or not _teacher_in_scope(db, teacher, authorization):
        raise HTTPException(status_code=404, detail="معلم یافت نشد")
    teacher.is_approved = True
    db.commit()
    return {"message": "معلم با موفقیت تایید شد و اکنون می‌تواند وارد شود"}


@router.delete("/teachers/reject/{teacher_id}")
def reject_teacher(teacher_id: int, db: Session = Depends(get_db),
                   authorization: str | None = Header(None),
                   _: str = Depends(check_admin_access)):
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id, Teacher.is_deleted == False).first()
    # FIX(teacher-approval): همان policy دامنه‌ی شعبه برای رد کردن (404 بدون نشت وجود رکورد).
    if not teacher or not _teacher_in_scope(db, teacher, authorization):
        raise HTTPException(status_code=404, detail="معلم یافت نشد")

    # سافت‌دیلیت: ردیف حفظ می‌شود (تاریخچه + جلوگیری از ثبت‌نام تکراری با همان کد ملی/موبایل)
    teacher.is_deleted = True
    db.commit()
    return {"message": "درخواست ثبت‌نام معلم رد و آرشیو شد"}


@router.post("/admin/teachers/{teacher_id}/suspend")
def suspend_teacher(teacher_id: int, db: Session = Depends(get_db), _: str = Depends(check_admin_or_secretary_access)):  # FIX H10-S: تعلیق فقط ادمین/منشی (الگوی C1)
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id, Teacher.is_deleted == False).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="معلم یافت نشد")

    # Toggle suspension status
    teacher.is_suspended = not teacher.is_suspended
    db.commit()

    status_text = "تعلیق شد" if teacher.is_suspended else "فعال شد"
    return {"message": f"معلم {status_text}", "is_suspended": teacher.is_suspended}


@router.delete("/admin/teachers/{teacher_id}")
def delete_teacher(teacher_id: int, db: Session = Depends(get_db), _: str = Depends(check_admin_access)):
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id, Teacher.is_deleted == False).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="معلم یافت نشد")

    # Check if teacher has any active classes
    # FIX O-11: «فعال» یعنی آرشیو نشده. قبلاً هر کلاس (حتی حذف‌شده) شمرده می‌شد و معلمی که
    # فقط کلاس آرشیوشده داشت قابل حذف نبود؛ پیام «N کلاس فعال دارد» هم درست نبود.
    active_classes = db.query(Course).filter(Course.teacher_id == teacher_id,
                                             Course.is_deleted == False).count()
    if active_classes > 0:
        raise HTTPException(
            status_code=400,
            detail=f"امکان حذف معلم وجود ندارد. این معلم {active_classes} کلاس فعال دارد.",
        )

    # سافت‌دیلیت + ابطال نشست‌ها و کاربر ورود معلم (دیگر نتواند وارد شود)
    teacher.is_deleted = True
    db.query(UserSession).filter(UserSession.sub_role == "teacher", UserSession.user_id == teacher_id).delete()
    if teacher.mobile:
        db.query(User).filter(User.username == teacher.mobile).delete()
    db.commit()
    return {"message": "معلم با موفقیت حذف (آرشیو) شد"}


@router.delete("/admin/reject_class/{course_id}")
def reject_class(
    course_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_access),
    authorization: str | None = Header(None),
    reason: str | None = Query(None, description="علت رد درخواست کلاس"),
):
    """رد و آرشیو کلاس (مسیر «کلاس در انتظار تایید» در اپ).

    FIX(A2): این مسیر سومِ حذف، قبلاً فقط ثبت‌نام‌ها را آرشیو می‌کرد و **جلسات را دست‌نخورده
    می‌گذاشت** و هیچ ردیف حذفی ثبت نمی‌کرد. پیامدش دو چیز بود:
      ۱) طلب معلم از کلاسی که دیگر وجود ندارد، همچنان در «طلبتسویهنشده» باز می‌ماند
         (پرداخت برای کلاس ناموجود ⇒ خطای مالی)،
      ۲) تاریخ حذف و عاملِ آن در تاریخچه‌ی حسابرسی گم می‌شد (نمای آرشیو: deleted_at خالی).
    اکنون هر سه مسیر حذف کلاس (حذف مستقیم ادمین، تایید درخواست، رد کلاس) دقیقاً یک اثر
    یکسان دارند: آرشیو کلاس + ثبت‌نام‌ها + جلسات + ثبت رکورد `ClassDeletionRequest` با
    snapshot و شناسه‌ی عامل. (`forgive_session_charges=True` — همان پیش‌فرض مسیر حذف مستقیم
    و همان رفتاری که `perform_delete_enrollment` قبلاً در همین مسیر داشت.)
    """
    # FIX(A2): lazy import — admin پیش از classes در main.py include می‌شود (جلوگیری از import چرخه‌ای).
    from services.class_lifecycle import _apply_class_deletion, _build_class_deletion_snapshot  # REFAC(P3a)

    c = db.query(Course).filter(Course.id == course_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="کلاس یافت نشد")
    if c.is_deleted is True:
        # حفظ idempotency برای فراخوانی تکراری؛ حذف جدید پس از restore رکورد تازه می‌سازد.
        return {"message": "کلاس قبلاً حذف و آرشیو شده است.", "reason": (reason or "").strip()}

    clean_reason = (reason or "").strip()
    if not clean_reason:
        clean_reason = "رد درخواست توسط مدیر"
    c.rejection_reason = clean_reason
    snapshot = _build_class_deletion_snapshot(db, c)
    # همین مسیر نیز provenance دقیق همان حذف را در رکورد تاییدشده نگه می‌دارد.
    snapshot["restore_provenance"] = _apply_class_deletion(db, c, True)

    # هر چرخهٔ حذف جدید پس از restore باید رکورد مستقل و provenance مستقل داشته باشد.
    from dependencies import resolve_actor_user_id
    _actor_user_id = resolve_actor_user_id(db, authorization)
    db.add(models.ClassDeletionRequest(
        course_id=c.id,
        requested_by_role="admin",
        requested_by_user_id=_actor_user_id,
        forgive_session_charges=True,
        status="approved",
        snapshot_json=json.dumps(snapshot, ensure_ascii=False, default=str),
        decided_at=datetime.datetime.now(),
        decided_by_user_id=_actor_user_id,
    ))
    db.add(ActivityLog(
        admin_username="group6", action="class_reject", target_id=c.id,
        target_name=c.title, details=clean_reason
    ))
    db.commit()
    return {"message": "کلاس رد و حذف شد و ترازهای مالی اصلاح گردید.", "reason": clean_reason}


# ==========================================
# 10. API اختصاصی پنل معلم
# ==========================================


@router.get("/admin/students/{id}/full_profile")
def get_student_full_profile(id: int, authorization: str | None = Header(None), db: Session = Depends(get_db), role: str = Depends(check_user_login)):
    # REFAC(P3b): بدنهٔ دامنه به `services/student_profile.py` رفت؛ این پوسته فقط لایهٔ HTTP است
    # (همان امضا، همان تزریق‌ها، همان پاسخ JSON). نام تابع عمداً این‌جا می‌ماند:
    # تست‌ها و اسکریپت‌ها این handler را مستقیم — گاهی با آرگومان پوزیشنال —
    # صدا می‌زنند، پس `routers.admin.get_student_full_profile` باید همان قرارداد قبلی را داشته باشد.
    return student_profile.get_student_full_profile(id, authorization, db, role)


# ==========================================
# 13. API پروفایل کامل معلم (Teacher Profile)
# ==========================================


@router.get("/config/share")
def get_share_config(db: Session = Depends(get_db), _: str = Depends(check_admin_access)):  # FIX (L14/Y3): پیکربندی سهم — فقط ادمین (متقارن با update؛ اپ هم از منشی پنهان است)
    # تلاش برای گرفتن تنظیمات
    config = db.query(InstituteShare).first()
    if not config:
        # اگر نبود، یکی با مقادیر صفر میسازیم
        config = InstituteShare()
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


@router.post("/config/share/update")
def update_share_config(data: ShareConfigModel, db: Session = Depends(get_db), _: str = Depends(check_admin_access)):
    config = db.query(InstituteShare).first()
    if not config:
        config = InstituteShare()
        db.add(config)

    # آپدیت مقادیر
    config.count_1 = data.count_1
    config.count_2 = data.count_2
    config.count_3 = data.count_3
    config.count_4 = data.count_4
    config.count_5 = data.count_5
    config.count_6 = data.count_6
    config.count_7 = data.count_7
    config.count_8 = data.count_8
    config.count_9 = data.count_9
    config.count_10 = data.count_10
    config.count_11 = data.count_11
    config.count_12 = data.count_12
    config.count_13 = data.count_13
    config.count_14 = data.count_14
    config.count_15 = data.count_15

    db.commit()
    return {"message": "تنظیمات سهم آموزشگاه ذخیره شد"}


@router.get("/admin/pending_classes")
def get_pending_classes(db: Session = Depends(get_db), authorization: str | None = Header(None), sub_role: str = Depends(check_user_login)):
    # FIX (L14/Y3): کلاس‌های درانتظار — کارکنان کامل؛ معلم فقط پیشنهادهای خودش (پیگیری ثبت از ClassSetup)؛ شاگرد/ولی 403.
    if sub_role not in ("admin", "secretary", "teacher"):
        raise HTTPException(status_code=403, detail="شما دسترسی لازم برای مشاهده کلاس‌های درانتظار را ندارید")
    _own_teacher_id = None
    if sub_role == "teacher":
        _me = get_logged_in_teacher(db, authorization)
        if not _me:
            raise HTTPException(status_code=403, detail="شما دسترسی لازم برای مشاهده کلاس‌های درانتظار را ندارید")
        _own_teacher_id = _me.id
    # 1. دریافت کلاس‌های تایید نشده از دیتابیس
    # FIX (گروه۱/آیتم۳): کلاس آرشیوشده (رد‌شده با DELETE /admin/reject_class یا حذف مستقیم ادمین)
    # نباید در صف «منتظر تأیید» بماند. `reject_class` فقط is_deleted=True می‌گذارد و
    # is_admin_approved همچنان False است ⇒ پیش‌تر ردیف رد‌شده در همین لیست دیده می‌شد و ادمین
    # می‌توانست دوباره تأییدش کند. هم‌سیاست با نمای معلم (`incomplete_classes`) و H10
    # (آرشیو مثل ناموجود است).
    courses = db.query(Course).filter(Course.is_admin_approved == False, Course.is_deleted == False)
    if _own_teacher_id is not None:
        courses = courses.filter(Course.teacher_id == _own_teacher_id)
    courses = courses.all()

    result = []
    # صف قدیمیِ اپ با قرارداد backward-compatible غنی می‌شود؛ تصمیم نهایی همچنان
    # از endpoint امن approve/bulk انجام می‌شود.
    from services.scheduling import check_scheduling_conflicts  # REFAC(P3a)
    for c in courses:
        # 2. پیدا کردن نام معلم برای نمایش
        teacher = db.query(Teacher).filter(Teacher.id == c.teacher_id).first()
        t_name = f"{teacher.first_name or ''} {teacher.last_name or ''}".strip() if teacher else "نامشخص"
        conflicts = check_scheduling_conflicts(
            db, c.teacher_id, c.days_of_week or "", c.class_time or "", c.id
        )

        # 3. ساخت دیکشنری دقیقاً با کلیدهایی که اندروید منتظر آن است
        # نکته کلیدی: نام سمت چپ (داخل گیومه) باید با متغیرهای AppModels.kt یکی باشد
        # FIX (audit-v2/blind-approve-2b): مبنای واقعی سهم آموزشگاه — H5 از InstituteShare؛
        # کلاسِ درانتظار شاگرد ندارد پس count_1 (مبنای یک‌شاگرد). قبلاً هاردکد ۰ بود و ادمین
        # نابینا تأیید می‌کرد. prepay یعنی واقعیِ صفر؛ نبود ردیف تعرفه هم صفر (submit جدا 500 می‌دهد).
        _base_inst_share = 0
        if not c.rule_prepay_institute:
            _share_row = db.query(models.InstituteShare).first()
            if _share_row is not None:
                _base_inst_share = getattr(_share_row, "count_1", 0) or 0
        result.append(
            {
                "id": c.id,
                "title": c.title,
                "code": c.code,
                "teacher_id": c.teacher_id,
                "teacher_name": t_name,  # اندروید: teacher_name
                "teacher_price": c.teacher_session_price,  # اندروید: teacher_price (در دیتابیس teacher_session_price است)
                "days": c.days_of_week,  # اندروید: days (در دیتابیس days_of_week است)
                "days_of_week": c.days_of_week,
                "time": c.class_time,  # اندروید: time (در دیتابیس class_time است)
                "class_time": c.class_time,
                "capacity": c.capacity,
                "branch_id": c.branch_id,
                "status": "rejected" if c.rejection_reason else "pending",
                "rejection_reason": c.rejection_reason,
                "pending_since": c.pending_since.isoformat() if c.pending_since else None,
                "conflict_course_ids": [item.id for item in conflicts],
                "has_schedule_conflict": bool(conflicts),
                "base_institute_share": _base_inst_share,  # FIX (audit-v2/blind-approve-2b): مبنای واقعی H5؛ صفر یعنی پیش‌پرداخت/نبود تعرفه
            }
        )

    return result


@router.post("/admin/approve_class/{course_id}")
def approve_class(course_id: int, db: Session = Depends(get_db), _: str = Depends(check_admin_or_secretary_access)):  # FIX H10-S2: تایید فقط ادمین/منشی (الگوی C1/H10-S)
    # FIX (گروه۱/آیتم۳): کلاس آرشیوشده (رد‌شده/حذف‌شده) مثل ناموجود است ⇒ ۴۰۴ (سیاست H10،
    # هم‌ترتیب با reject_class همسایه). پیش‌تر تأییدِ کلاسِ رد‌شده ۲۰۰ می‌داد و ردیفی را که از صف
    # خارج شده بود دوباره «تأییدشده» می‌کرد (کلاس آرشیو با پرچم تأیید = وضعیت ناسازگار).
    c = db.query(Course).filter(Course.id == course_id, Course.is_deleted == False).first()
    if not c:  # FIX H10-S2: قبلاً None-check نداشت (500) — هم‌سبک reject_class همسایه
        raise HTTPException(status_code=404, detail="کلاس یافت نشد")
    # همان guard صف گروهی برای تأیید تکی؛ تأیید کلاسِ متداخل نباید با مسیر قدیمی
    # دور زده شود.
    from services.scheduling import check_scheduling_conflicts  # REFAC(P3a)
    conflicts = check_scheduling_conflicts(
        db, c.teacher_id, c.days_of_week or "", c.class_time or "", c.id
    )
    if conflicts:
        raise HTTPException(
            status_code=409,
            detail={"message": "تداخل زمان‌بندی وجود دارد", "conflict_course_ids": [item.id for item in conflicts]},
        )
    c.is_admin_approved = True
    c.rejection_reason = None
    c.pending_since = None
    db.add(ActivityLog(
        admin_username="group6", action="class_approve", target_id=c.id,
        target_name=c.title, details="تأیید تکی پس از بررسی ظرفیت و تداخل زمان‌بندی"
    ))
    db.commit()
    # FIX (audit-v2/blind-approve-2c): هشدار غیرمسدودکننده برای نرخ بالای سقف (اشتباه تایپی
    # موقع ثبت). مسدود نکردیم: کلاس VIP مشروع هم می‌تواند بالای سقف باشد و 400 فلو تأیید اپ را
    # می‌شکست؛ ادمین با دیدن مبلغ واقعی (قدم 2b) + این هشدار، آگاهانه تأیید می‌کند.
    _price_warning = None
    if (c.teacher_session_price or 0) > MAX_TEACHER_SESSION_PRICE:
        _price_warning = f"⚠️ نرخ هر جلسه ({c.teacher_session_price:,} تومان برای هر شاگرد) بالاتر از سقف معمول ({MAX_TEACHER_SESSION_PRICE:,} تومان) است؛ اگر اشتباه تایپی است قبل از برگزاری جلسه اصلاح کنید"
    return {"message": "تایید شد", "price_warning": _price_warning}


@router.get("/admin/parent_contacts")
def get_parent_contacts(
    class_id: int | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_or_secretary_access)  # FIX (audit-v2/contacts-PII): دفترچه‌ی تماس والدین گزارش مدیریتی است — فقط ادمین/منشی
):
    q = db.query(Student).outerjoin(Enrollment).outerjoin(Course).options(
        joinedload(Student.enrollments).joinedload(Enrollment.course)
    )
    q = q.filter(Student.is_deleted == False)

    if class_id:
        q = q.filter(Enrollment.course_id == class_id)

    if search:
        search_fmt = f"%{search}%"
        q = q.filter(
            or_(
                Student.first_name.ilike(search_fmt),
                Student.last_name.ilike(search_fmt),
                Student.national_code.ilike(search_fmt)
            )
        )

    students = q.all()

    result = []
    for st in students:
        # Get student classes
        classes = []
        for en in st.enrollments:
            if en.course:
                classes.append(en.course.title)

        result.append({
            "student_id": st.id,
            "student_name": f"{st.first_name} {st.last_name}",
            "student_mobile": st.student_mobile or "",
            "parent_mobile": st.parent_mobile or "",
            "classes": classes
        })
    return result


# ==========================================
# Excel Export Endpoints
# ==========================================

from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from services import class_restore, student_profile, transaction_admin
from services.branch_scope import get_user_branch_filter


@router.get("/admin/transactions/list/excel")
def get_transactions_excel(search: str | None = None, db: Session = Depends(get_db), _: str = Depends(check_admin_access)):
    # FIX: Bug 12 - exclude archived Transaction rows from this active view.
    q = db.query(Transaction).filter(Transaction.is_deleted == False, Transaction.is_reversed == False).outerjoin(Student).order_by(desc(Transaction.id))

    if search:
        search_fmt = f"%{search}%"
        q = q.filter(
            or_(
                Student.first_name.ilike(search_fmt),
                Student.last_name.ilike(search_fmt),
                Student.national_code.ilike(search_fmt),
                Transaction.description.ilike(search_fmt),
            )
        )

    trans_list = q.all()

    wb = Workbook()
    ws = wb.active
    ws.title = "گزارش تراکنش‌های مالی"
    ws.views.sheetView[0].rightToLeft = True

    headers = ["شناسه", "نام دانش‌آموز", "کلاس", "مبلغ (تومان)", "روش پرداخت", "کد پیگیری", "تاریخ", "دریافت‌کننده", "کیف پول هدف", "سهم معلم", "سهم آموزشگاه", "توضیحات"]
    ws.append(headers)

    header_fill = PatternFill(start_color="00695C", end_color="00695C", fill_type="solid")
    header_font = Font(name="Tahoma", size=11, bold=True, color="FFFFFF")
    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    row_num = 2
    for t in trans_list:
        course_name = t.course.title if t.course else "---"
        student_name = f"{t.student.first_name} {t.student.last_name}" if t.student else "ناشناس"

        target_w = "معلم" if t.target_wallet == "teacher" else "آموزشگاه" if t.target_wallet == "institute" else "---"

        row_data = [
            t.id,
            student_name,
            course_name,
            t.amount,
            t.payment_method or "---",
            t.tracking_code or "---",
            t.date or "---",
            t.receiver or "---",
            target_w,
            t.share_teacher or 0,
            t.share_institute or 0,
            t.description or ""
        ]
        ws.append(row_data)

        ws.cell(row=row_num, column=4).number_format = '#,##0'
        ws.cell(row=row_num, column=10).number_format = '#,##0'
        ws.cell(row=row_num, column=11).number_format = '#,##0'

        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=row_num, column=col_num)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.font = Font(name="Tahoma", size=10)

        row_num += 1

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = col[0].column_letter
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)

    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=transactions_report.xlsx"}
    )


# مدل پاسخ برای لیست


# 1. جستجوی دانش‌آموزان (همه یا با فیلتر)


@router.get("/admin/transactions/list")
def get_all_transactions(search: str | None = None, db: Session = Depends(get_db), _: str = Depends(check_admin_access)):
    # FIX: Bug 12 - exclude archived Transaction rows from this active view.
    q = db.query(Transaction).filter(Transaction.is_deleted == False, Transaction.is_reversed == False).join(Student).order_by(desc(Transaction.id))

    if search:
        search_fmt = f"%{search}%"
        q = q.filter(
            or_(
                Student.first_name.ilike(search_fmt),
                Student.last_name.ilike(search_fmt),
                Student.national_code.ilike(search_fmt),
                Transaction.description.ilike(search_fmt),
            )
        )

    trans_list = q.all()

    # مپ کردن دستی برای ارسال نام کلاس و دانش‌آموز
    result = []
    for t in trans_list:
        course_name = t.course.title if t.course else "---"
        student_name = f"{t.student.first_name} {t.student.last_name}"
        result.append(
            {
                "id": t.id,
                "student_id": t.student_id,
                "student_name": student_name,
                "course_id": t.course_id,
                "course_name": course_name,
                "amount": t.amount,
                "date": t.date,
                "description": t.description,
                "type": t.type,
            }
        )
    return result


# 2. حذف تراکنش (بسیار مهم: باید حساب کلاس هم اصلاح شود)


@router.delete("/admin/transactions/{id}")
def delete_transaction(id: int, db: Session = Depends(get_db), _: str = Depends(check_admin_access)):
    # REFAC(P3b): بدنهٔ دامنه به `services/transaction_admin.py` رفت؛ این پوسته فقط لایهٔ HTTP است
    # (همان امضا، همان تزریق‌ها، همان پاسخ JSON). نام تابع عمداً این‌جا می‌ماند:
    # تست‌ها و اسکریپت‌ها این handler را مستقیم — گاهی با آرگومان پوزیشنال —
    # صدا می‌زنند، پس `routers.admin.delete_transaction` باید همان قرارداد قبلی را داشته باشد.
    return transaction_admin.delete_transaction(id, db, _)


# 3. ویرایش تراکنش


@router.put("/admin/transactions/{id}")
def update_transaction(id: int, data: TransactionUpdate, db: Session = Depends(get_db), _: str = Depends(check_admin_access)):
    # REFAC(P3b): بدنهٔ دامنه به `services/transaction_admin.py` رفت؛ این پوسته فقط لایهٔ HTTP است
    # (همان امضا، همان تزریق‌ها، همان پاسخ JSON). نام تابع عمداً این‌جا می‌ماند:
    # تست‌ها و اسکریپت‌ها این handler را مستقیم — گاهی با آرگومان پوزیشنال —
    # صدا می‌زنند، پس `routers.admin.update_transaction` باید همان قرارداد قبلی را داشته باشد.
    return transaction_admin.update_transaction(id, data, db, _)


# ==========================================
# 🔥 API های جدید: مدیریت دانش‌آموز (حذف و تعلیق)
# ==========================================


# 1. حذف کامل دانش‌آموز به همراه سوابق


@router.delete("/admin/students/{id}")
def delete_student(id: int, db: Session = Depends(get_db), _: str = Depends(check_admin_access)):
    st = db.query(Student).filter(Student.id == id, Student.is_deleted == False).first()
    if not st:
        raise HTTPException(status_code=404, detail="دانش‌آموز یافت نشد")

    # سافت‌دیلیت: ثبت‌نام‌ها، نمرات، حضورها و تراکنش‌ها دست‌نخورده می‌مانند (حفظ سوابق مالی)؛
    # فقط خود شاگرد آرشیو و نشست‌ها + سایه‌های ورود او باطل/حذف می‌شود (آینه‌ی delete_teacher).
    st.is_deleted = True
    shadow_ids = [i for i in (st.user_id, st.parent_user_id) if i]
    if shadow_ids:
        db.query(UserSession).filter(UserSession.user_id.in_(shadow_ids)).delete()
        db.query(User).filter(User.id.in_(shadow_ids)).delete()
        st.user_id = None
        st.parent_user_id = None
    db.commit()
    return {"message": "دانش‌آموز با موفقیت آرشیو شد و سوابق مالی او حفظ گردید."}


# 2. تغییر وضعیت تعلیق (فعال/غیرفعال)


@router.post("/admin/students/{id}/toggle_suspend")
def toggle_suspend_student(id: int, db: Session = Depends(get_db), _: str = Depends(check_admin_or_secretary_access)):  # FIX H10-S: تعلیق فقط ادمین/منشی (الگوی C1)
    st = db.query(Student).filter(Student.id == id, Student.is_deleted == False).first()
    if not st:
        raise HTTPException(status_code=404, detail="دانش‌آموز یافت نشد")

    # تغییر وضعیت (اگر True بود False میشه و برعکس)
    st.is_suspended = not st.is_suspended
    db.commit()

    status_text = "معلق (غیرفعال)" if st.is_suspended else "فعال"
    return {
        "message": f"وضعیت دانش‌آموز به {status_text} تغییر کرد.",
        "is_suspended": st.is_suspended,
    }


# 3. تاریخچه حضور و غیاب دانش‌آموز در یک کلاس خاص


@router.post("/test/transaction_logic")
def test_transaction_logic(data: TransactionTestData, db: Session = Depends(get_db), _: str = Depends(check_admin_access)):
    """تست کامل منطق ایجاد، ویرایش و حذف تراکنش"""
    # REFAC(P3b): بدنهٔ دامنه به `services/transaction_admin.py` رفت؛ این پوسته فقط لایهٔ HTTP است
    # (همان امضا، همان تزریق‌ها، همان پاسخ JSON). نام تابع عمداً این‌جا می‌ماند:
    # تست‌ها و اسکریپت‌ها این handler را مستقیم — گاهی با آرگومان پوزیشنال —
    # صدا می‌زنند، پس `routers.admin.test_transaction_logic` باید همان قرارداد قبلی را داشته باشد.
    return transaction_admin.test_transaction_logic(data, db, _)


@router.post("/sms/send_bulk")
# FIX (L14/R1-align): ارسال گروهی هم ادمین/منشی — هماهنگ با /sms/send تکی (audit-v2/#10) و یادآور قسط (L14/R1). منشی همین قدرت را تک‌تک داشت؛ bulk فقط راحت‌تر و حسابرسی‌پذیرتر است.
def send_bulk_sms(req: BulkSmsRequest, db: Session = Depends(get_db), _: str = Depends(check_admin_or_secretary_access)):
    results = []
    success_count = 0
    today = datetime.datetime.now().strftime("%Y/%m/%d %H:%M")

    for s_id in req.student_ids:
        st = db.query(Student).filter(Student.id == s_id, Student.is_deleted == False).first()
        if not st:
            results.append({"student_id": s_id, "status": "failed", "message": "دانش‌آموز یافت نشد"})
            continue

        # Keep bulk reminders on the same tuition-aware calculation as the
        # debtor list and single SMS endpoint; aggregate wallets are not copied
        # into any class row and are not the sole source of tuition debt.
        debt = calculate_student_debt(db, st)

        msg = f"سلام {st.first_name} عزیز، بدینوسیله به شما اعلام می‌گردد که مبلغ {debt:,} تومان بدهی شهریه در سیستم دارید. لطفاً جهت تسویه حساب اقدام فرمایید."

        # ثبت تک‌تک لاگ‌های پیامک‌ها در دیتابیس
        db.add(
            models.SmsLog(
                target_group=f"student_{st.id}",
                message_text=msg,
                sent_count=1,
                date=today,
            )
        )
        success_count += 1
        results.append({"student_id": s_id, "student_name": f"{st.first_name} {st.last_name}", "status": "success", "message": "پیامک یادآوری بدهی ارسال شد"})

    db.commit()
    return {
        "status": "success",
        "message": f"پیامک برای {success_count} دانش‌آموز با موفقیت ارسال شد.",
        "results": results
    }


@router.post("/admin/classes/suspend_bulk")
# DELIBERATE (H10-S): تعلیق گروهی کلاس‌ها عمداً فقط-ادمین می‌ماند — شعاع انفجار (N کلاس به‌جای ۱) و یک‌طرفه‌بودن (فقط True، بدون برگشت) با تکی/گروهیِ پیامک فرق دارد. با bulk-sms هماهنگ نکنید.
def suspend_bulk_classes(req: BulkSuspendRequest, db: Session = Depends(get_db), _: str = Depends(check_admin_access)):
    results = []
    success_count = 0

    for c_id in req.course_ids:
        course = db.query(Course).filter(Course.id == c_id).first()
        if not course:
            results.append({"course_id": c_id, "status": "failed", "message": "کلاس یافت نشد"})
            continue

        course.is_suspended = True # معلق کردن کلاس
        success_count += 1
        results.append({"course_id": c_id, "course_title": course.title, "status": "success", "message": "کلاس با موفقیت معلق شد"})

    db.commit()
    return {
        "status": "success",
        "message": f"تعداد {success_count} کلاس با موفقیت معلق شدند.",
        "results": results
    }

@router.get("/admin/institute_settings")
def get_institute_settings(db: Session = Depends(get_db), sub_role: str = Depends(check_user_login)):
    # FIX (L14/Y3): تنظیمات — شاگرد/ولی 403؛ معلم نسخه‌ی بدون شماره‌کارت (رسید حضور/فاکتور)؛ کارکنان کامل.
    if sub_role not in ("admin", "secretary", "teacher"):
        raise HTTPException(status_code=403, detail="شما دسترسی لازم برای مشاهده تنظیمات آموزشگاه را ندارید")
    settings = db.query(InstituteSettings).first()
    if not settings:
        settings = InstituteSettings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    if sub_role == "teacher":
        data = {c.name: getattr(settings, c.name) for c in settings.__table__.columns}
        for _f in ("card_number", "card_number_1", "card_holder_1", "card_number_2", "card_holder_2"):
            data[_f] = None
        return data
    return settings

@router.put("/admin/institute_settings")
def update_institute_settings(data: InstituteSettingsModel, db: Session = Depends(get_db), _: str = Depends(check_admin_access)):
    settings = db.query(InstituteSettings).first()
    if not settings:
        settings = InstituteSettings()
        db.add(settings)

    settings.name = data.name
    settings.address = data.address
    settings.phone = data.phone
    if data.official_email is not None:
        settings.official_email = data.official_email
    if data.footer_text is not None:
        settings.footer_text = data.footer_text
    if data.card_number is not None:
        settings.card_number = data.card_number
    if data.manager_mobile_1 is not None:
        settings.manager_mobile_1 = data.manager_mobile_1
    if data.manager_mobile_2 is not None:
        settings.manager_mobile_2 = data.manager_mobile_2
    if data.card_number_1 is not None:
        settings.card_number_1 = data.card_number_1
    if data.card_holder_1 is not None:
        settings.card_holder_1 = data.card_holder_1
    if data.card_number_2 is not None:
        settings.card_number_2 = data.card_number_2
    if data.card_holder_2 is not None:
        settings.card_holder_2 = data.card_holder_2
    if data.teachers_active is not None:
        settings.teachers_active = data.teachers_active
    if data.live_session_max_minutes is not None:
        settings.live_session_max_minutes = data.live_session_max_minutes
    if data.teacher_settlement_alert_days is not None:
        settings.teacher_settlement_alert_days = data.teacher_settlement_alert_days

    db.commit()
    db.refresh(settings)
    return {"message": "تنظیمات آموزشگاه با موفقیت بروزرسانی شد", "settings": settings}

@router.post("/admin/institute_settings/upload_logo")
async def upload_institute_logo(file: UploadFile = File(...), db: Session = Depends(get_db), _: str = Depends(check_admin_access)):
    settings = db.query(InstituteSettings).first()
    if not settings:
        settings = InstituteSettings()
        db.add(settings)

    # Read file and validate size
    MAX_SIZE = 5 * 1024 * 1024 # 5 MB
    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="حجم فایل نباید بیشتر از ۵ مگابایت باشد")

    # Validate extension
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="فرمت فایل غیرمجاز است. فقط فرمت‌های JPG, PNG, WEBP مجاز هستند")

    # Generate unique filename
    unique_filename = f"logo_{uuid.uuid4().hex}{file_ext}"
    filepath = os.path.join(storage_dir("profiles"), unique_filename)

    # Write to disk
    with open(filepath, "wb") as f_out:
        f_out.write(contents)

    # Delete old file
    if settings.logo_path:
        # پاک‌کردن لوگوی قبلی — حتی اگر در مسیر قدیمی (نسبت به cwd) مانده باشد
        old_path = resolve_existing("profiles", settings.logo_path)
        if old_path:
            try:
                os.remove(old_path)
            except Exception:
                pass

    settings.logo_path = unique_filename
    db.commit()

    return {
        "message": "لوگوی آموزشگاه با موفقیت آپلود شد",
        "logo_path": unique_filename,
        "url": f"uploads/profiles/{unique_filename}"
    }


@router.get("/admin/deleted_classes")
def get_deleted_classes(
    query: str | None = None,
    title: str | None = None,
    teacher: str | None = None,
    code: str | None = None,
    deleted_from: str | None = None,
    deleted_to: str | None = None,
    branch_id: int | None = None,
    db: Session = Depends(get_db),
    authorization: str | None = Header(None),
    _: str = Depends(check_admin_access),
):
    """آرشیو کلاس‌های حذف‌شده — فقط ادمین، با branch isolation و اطلاعات کامل.

    تغییرات نسبت به نسخه‌ی قبلی: فیلدهای branch/تعداد دانش‌آموز/جلسه/تراکنش و تاریخ حذف
    اضافه شده، جست‌وجو ممکن است و ترتیب قطعی است. کلیدهای قبلی (id/title/code/teacher_name/
    grade_level/bg_color) دست‌نخورده مانده‌اند تا کلاینت قدیمی نشکند.
    """
    # الگوی branch isolation پروژه (analytics/crm/exports) — ادمینِ شعبه‌دار فقط شعبه‌ی خودش.
    resolved_branch = get_user_branch_filter(db, authorization, branch_id)

    # FIX(null-data): is_deleted=True صریح؛ ردیف‌های legacy با NULL «فعال» حساب می‌شوند و
    # طبق سیاست موجود پروژه در آرشیو نمی‌آیند (لیست عادی و آرشیو قاطی نمی‌شوند).
    q = db.query(Course).filter(Course.is_deleted == True)
    if resolved_branch is not None:
        q = q.filter(Course.branch_id == resolved_branch)
    # فیلترهای جست‌وجو (همه با AND): عبارت آزاد، نام کلاس، نام معلم، کد کلاس. هر واژه جدا حساب می‌شود
    # (ترتیب «نام و نام‌خانوادگی» مهم نیست) و ی/ي و ک/ك یکی‌اند.
    teacher_full = (
        func.coalesce(Teacher.first_name, "").op("||")(" ").op("||")(func.coalesce(Teacher.last_name, ""))
    )
    field_map = {"title": Course.title, "code": Course.code, "teacher": teacher_full}

    def _apply_terms(q_, raw: str | None, fields):
        for token in (raw or "").split():
            clauses = [f.ilike(f"%{v}%") for v in _archive_search_variants(token) for f in fields]
            q_ = q_.filter(or_(*clauses))
        return q_

    q = q.outerjoin(Teacher, Teacher.id == Course.teacher_id)
    q = _apply_terms(q, query, [field_map["title"], field_map["code"], field_map["teacher"]])
    q = _apply_terms(q, title, [field_map["title"]])
    q = _apply_terms(q, code, [field_map["code"]])
    q = _apply_terms(q, teacher, [field_map["teacher"]])

    date_from = _archive_parse_filter_date(deleted_from, "تاریخ شروع")
    date_to = _archive_parse_filter_date(deleted_to, "تاریخ پایان")
    if date_from and date_to and date_from > date_to:
        date_from, date_to = date_to, date_from   # بازهٔ وارونه ⇒ جابه‌جا (خطا نده)
    courses = q.all()
    course_ids = [c.id for c in courses]

    meta_map = _archived_deletion_meta(db, course_ids)
    if date_from or date_to:
        # کلاسِ بدون تاریخ حذف (legacy) در بازهٔ زمانی «نامعلوم» است و وارد نتیجه نمی‌شود.
        def _in_range(cid: int) -> bool:
            when = meta_map.get(cid, {}).get("deleted_at")
            if not when:
                return False
            day = when.date()
            return (date_from is None or day >= date_from) and (date_to is None or day <= date_to)
        courses = [c for c in courses if _in_range(c.id)]
        course_ids = [c.id for c in courses]
        meta_map = {cid: meta_map[cid] for cid in course_ids if cid in meta_map}
    stats_map = _archived_class_aggregates(db, course_ids)

    teacher_ids = {c.teacher_id for c in courses if c.teacher_id is not None}
    branch_ids = {c.branch_id for c in courses if c.branch_id is not None}
    teachers = {t.id: t for t in db.query(Teacher).filter(Teacher.id.in_(teacher_ids)).all()} if teacher_ids else {}
    branches = {b.id: b for b in db.query(models.Branch).filter(models.Branch.id.in_(branch_ids)).all()} if branch_ids else {}

    # ترتیب قطعی: تازه‌ترین حذف اول؛ کلاس‌های بدون تاریخ حذف آخر (شناسه نزولی).
    courses.sort(
        key=lambda c: (meta_map.get(c.id, {}).get("deleted_at") or datetime.datetime.min, c.id),
        reverse=True,
    )

    result = []
    for c in courses:
        st = stats_map.get(c.id, {})
        meta = meta_map.get(c.id, {})
        result.append({
            "id": c.id,
            # FIX(null-data): فیلدهای legacy می‌توانند NULL باشند — رشته‌ی خالی می‌رود و
            # فال‌بک نمایش در اپ انجام می‌شود (نه «None/null» در UI).
            "title": c.title or "",
            "code": c.code or "",
            "teacher_id": c.teacher_id,
            "teacher_name": _safe_person_name(teachers.get(c.teacher_id)) or "نامشخص",
            "branch_id": c.branch_id,
            "branch_name": (branches.get(c.branch_id).name if branches.get(c.branch_id) else "") or "",
            "grade_level": c.grade_level or "",
            "days_of_week": c.days_of_week or "",
            "class_time": c.class_time or "",
            "students_count": st.get("students_total", 0),
            "students_active_count": st.get("students_active", 0),
            "sessions_count": st.get("sessions_total", 0),
            "transactions_count": st.get("transactions_count", 0),
            "deleted_at": _fmt_datetime(meta.get("deleted_at")),
            **_archive_jalali(meta.get("deleted_at")),
            "forgive_session_charges": bool(meta.get("forgive_session_charges", False)),
            "is_suspended": bool(c.is_suspended),
            "bg_color": c.bg_color or "#FFFFFF",
        })
    return result


@router.get("/admin/deleted_classes/{course_id}")
def get_deleted_class_detail(
    course_id: int,
    db: Session = Depends(get_db),
    authorization: str | None = Header(None),
    _: str = Depends(check_admin_access),
):
    """جزئیات کنترول‌شده‌ی یک کلاس آرشیوشده (فقط ادمین + همان شعبه).

    فقط کلاسِ آرشیوشده سرو می‌شود؛ کلاس فعال، ناموجود و متعلق به شعبه‌ی دیگر همه 404
    می‌گیرند (بدون نشت وجود رکورد). خروجی dict تعریف‌شده است، نه dump خام ORM.
    """
    resolved_branch = get_user_branch_filter(db, authorization, None)

    course = (
        db.query(Course)
        .filter(Course.id == course_id, Course.is_deleted == True)
        .first()
    )
    if not course or (resolved_branch is not None and course.branch_id != resolved_branch):
        raise HTTPException(status_code=404, detail="کلاس آرشیوشده یافت نشد")

    meta = _archived_deletion_meta(db, [course.id]).get(course.id, {})
    restore_provenance = _latest_class_restore_provenance(db, course.id)
    stats = _archived_class_aggregates(db, [course.id]).get(course.id, {})
    teacher = db.query(Teacher).filter(Teacher.id == course.teacher_id).first() if course.teacher_id else None
    branch = db.query(models.Branch).filter(models.Branch.id == course.branch_id).first() if course.branch_id else None
    archived_enrollments = db.query(Enrollment).filter(
        Enrollment.course_id == course.id, Enrollment.is_deleted == True
    ).count()
    archived_sessions = db.query(SessionLog).filter(
        SessionLog.course_id == course.id, SessionLog.is_deleted == True
    ).count()

    return {
        # مشخصات پایه (همه null-safe)
        "id": course.id,
        "title": course.title or "",
        "code": course.code or "",
        "grade_level": course.grade_level or "",
        "days_of_week": course.days_of_week or "",
        "class_time": course.class_time or "",
        "is_suspended": bool(course.is_suspended),
        "bg_color": course.bg_color or "#FFFFFF",
        # معلم / شعبه
        "teacher_id": course.teacher_id,
        "teacher_name": _safe_person_name(teacher) or "نامشخص",
        "branch_id": course.branch_id,
        "branch_name": (branch.name if branch else "") or "",
        # تاریخچه (حفظ‌شده — چیزی حذف نمی‌شود)
        "students_count": stats.get("students_total", 0),
        "students_active_count": stats.get("students_active", 0),
        "archived_enrollments_count": archived_enrollments,
        "sessions_count": stats.get("sessions_total", 0),
        "archived_sessions_count": archived_sessions,
        "transactions_count": stats.get("transactions_count", 0),
        "transactions_total": stats.get("transactions_total", 0),
        # اطلاعات حذف (از ClassDeletionRequest؛ بدون تاریخ حدسی)
        "deleted_at": _fmt_datetime(meta.get("deleted_at")),
        "has_deletion_record": bool(meta),
        "financial_restore_available": restore_provenance is not None,
        "forgive_session_charges": bool(meta.get("forgive_session_charges", False)),
        "requested_by_role": meta.get("requested_by_role") or "",
        "admin_note": meta.get("admin_note") or "",
        **_archive_jalali(meta.get("deleted_at")),
        # گزارش کامل تاریخی: حضور/غیاب (موجه/غیرموجه)، فهرست دانش‌آموزان، پرداخت و مانده (فیلدهای افزوده)
        **_archived_class_people_report(db, course, bool(meta.get("forgive_session_charges", False))),
    }


@router.post("/admin/deleted_classes/{course_id}/restore")
def restore_deleted_class(
    course_id: int,
    data: ClassRestoreRequest,
    db: Session = Depends(get_db),
    authorization: str | None = Header(None),
    _: str = Depends(check_admin_access),
):
    """Restore a deleted class and its operational history; finance is explicit opt-in.

    New deletions persist exact row-level provenance in the approved deletion
    request. Financial restore is rejected for legacy/unverifiable deletions and
    when reversing deletion-created wallet credits would make a wallet negative.
    """
    # REFAC(P3b): بدنهٔ دامنه (321 خط) به `services/class_restore.py` رفت؛ این پوسته فقط لایهٔ HTTP است
    # (همان decorator، همان امضا، همان پاسخ). نام تابع عمداً این‌جا می‌ماند: امضا
    # قرارداد OpenAPI است و تست‌ها/اسکریپت‌ها این handler را مستقیم — گاهی با
    # آرگومان پوزیشنال — از `routers.admin` صدا می‌زنند.
    return class_restore.restore_deleted_class(course_id, data, db, authorization, _)


@router.get("/admin/pricing_table")
def get_pricing_table(db: Session = Depends(get_db), _: str = Depends(check_admin_access)):
    from models import PricingTable
    return db.query(PricingTable).all()


@router.put("/admin/pricing_table")
def update_pricing_table(data: PricingTableUpdateModel, db: Session = Depends(get_db), _: str = Depends(check_admin_access)):
    from models import PricingTable
    for r in data.rows:
        row = db.query(PricingTable).filter(PricingTable.category == r.category).first()
        if not row:
            row = PricingTable(category=r.category)
            db.add(row)
        row.count_1 = r.count_1
        row.count_2 = r.count_2
        row.count_3 = r.count_3
        row.count_4 = r.count_4
        row.count_5 = r.count_5
    db.commit()
    return {"message": "جدول قیمت‌گذاری با موفقیت بروزرسانی شد"}


@router.get("/admin/students/search", response_model=list[PersonListItem])
def search_admin_students(query: str | None = None, db: Session = Depends(get_db), sub_role: str = Depends(check_user_login)):
    # FIX (L14/Y1): جستجوی سراسری PII شاگردان — فقط کارکنان (ادمین/منشی/معلم). شاگرد/ولی 403.
    if sub_role not in ("admin", "secretary", "teacher"):
        raise HTTPException(status_code=403, detail="شما دسترسی لازم برای جستجوی دانش‌آموزان را ندارید")
    q = db.query(Student).filter(Student.is_deleted == False)
    if query:
        search_fmt = f"%{query}%"
        q = q.filter(
            or_(
                Student.first_name.ilike(search_fmt),
                Student.last_name.ilike(search_fmt),
                Student.national_code.ilike(search_fmt)
            )
        )
    students = q.all()
    return [
        PersonListItem(
            id=s.id,
            # FIX(null-data): هم‌سان با جستجوی معلمان — یک رکورد ناقص نباید کل لیست را 500 کند.
            name=f"{s.first_name or ''} {s.last_name or ''}".strip() or "نامشخص",
            national_code=s.national_code or "",
            mobile=s.student_mobile or "",
            role="student",
            is_suspended=s.is_suspended if s.is_suspended is not None else False
        )
        for s in students
    ]


@router.get("/admin/teachers/search", response_model=list[PersonListItem])
def search_admin_teachers(query: str | None = None, db: Session = Depends(get_db), sub_role: str = Depends(check_user_login)):
    # FIX (L14/Y2): جستجوی سراسری PII معلمان — فقط کارکنان (ادمین/منشی/معلم؛ معلم برای PersonList). شاگرد/ولی 403.
    if sub_role not in ("admin", "secretary", "teacher"):
        raise HTTPException(status_code=403, detail="شما دسترسی لازم برای جستجوی معلمان را ندارید")
    q = db.query(Teacher).filter(Teacher.is_deleted == False)
    if query:
        search_fmt = f"%{query}%"
        q = q.filter(
            or_(
                Teacher.first_name.ilike(search_fmt),
                Teacher.last_name.ilike(search_fmt),
                Teacher.national_code.ilike(search_fmt)
            )
        )
    teachers = q.all()
    return [
        PersonListItem(
            id=t.id,
            # FIX(null-data): فیلدهای legacy ممکن است NULL باشند — پاسخ امن به‌جای ValidationError/500
            # (یک رکورد ناقص نباید کل لیست مربیان/افراد را خراب کند).
            name=f"{t.first_name or ''} {t.last_name or ''}".strip() or "نامشخص",
            national_code=t.national_code or "",
            mobile=t.mobile or "",
            role="teacher",
            is_suspended=t.is_suspended if t.is_suspended is not None else False
        )
        for t in teachers
    ]


# Pydantic models for credentials
class TeacherCredentialsResponse(BaseModel):
    id: int
    name: str
    national_code: str
    mobile: str
    teacher_code: int | None = None
    password: str
    card_number: str | None = None

class TeacherCredentialsUpdateRequest(BaseModel):
    mobile: str
    card_number: str | None = None

@router.get("/admin/teachers/{id}/credentials", response_model=TeacherCredentialsResponse)
def get_teacher_credentials(id: int, db: Session = Depends(get_db), _: str = Depends(check_admin_access)):
    teacher = db.query(Teacher).filter(Teacher.id == id, Teacher.is_deleted == False).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="معلم یافت نشد")
    return TeacherCredentialsResponse(
        id=teacher.id,
        # FIX(null-data): این response_model فیلدهای str اجباری دارد و رکورد legacy با
        # mobile/national_code/نام NULL قبلاً ValidationError/500 می‌داد؛ الان مقدار امن برمی‌گردد.
        name=f"{teacher.first_name or ''} {teacher.last_name or ''}".strip() or "نامشخص",
        national_code=teacher.national_code or "",
        mobile=teacher.mobile or "",
        teacher_code=teacher.teacher_code,
        password=teacher.password or "",
        card_number=teacher.card_number
    )

@router.post("/admin/teachers/{id}/credentials/reset_password")
def reset_teacher_password(id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user), _: str = Depends(check_admin_access)):
    teacher = db.query(Teacher).filter(Teacher.id == id, Teacher.is_deleted == False).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="معلم یافت نشد")

    # FIX H12: کد بدون‌تصادم از شمارنده‌ی ترتیبی (نه رندوم خام روی ستون UNIQUE).
    new_code = get_next_sequence_value(db, "teacher", 101)

    # FIX H12: پسورد تصادفی امن با الگوی C12 (مستقل از کد حدس‌زدنی)؛ فقط همین یک‌بار در پاسخ برمی‌گردد.
    _READABLE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"  # بدون 0/O/1/l/I
    new_password = "".join(secrets.choice(_READABLE_ALPHABET) for _ in range(8))

    old_code = teacher.teacher_code
    old_password = teacher.password

    teacher.teacher_code = new_code
    teacher.password = hash_password(new_password)

    # FIX (same shadow-sync as change_password): لاگین اول شاخه‌ی User را چک می‌کند،
    # پس بدون سینک سایه، معلم با پسورد جدید قفل می‌شود (400) — سایه را هم به‌روز کن.
    shadow = db.query(User).filter(User.username == teacher.mobile, User.role == "teacher").first()
    if shadow is None:
        # fallback ناهماهنگی‌های قدیمی (username سایه با موبایل فعلی فرق دارد): حل از طریق سشن
        last_sess = db.query(UserSession).filter(UserSession.teacher_id == teacher.id).order_by(UserSession.id.desc()).first()
        if last_sess is not None:
            cand = db.query(User).filter(User.id == last_sess.user_id, User.role == "teacher").first()
            if cand is not None:
                shadow = cand
    if shadow is not None:
        shadow.password = teacher.password

    # Write to activity log
    log_entry = ActivityLog(
        admin_username=current_user.username,
        action="reset_teacher_password",
        target_id=teacher.id,
        target_name=f"{teacher.first_name or ''} {teacher.last_name or ''}".strip() or "نامشخص",
        details=f"تغییر رمز از {old_code}/{old_password} to {new_code}"
    )
    db.add(log_entry)
    db.commit()

    return {
        "message": "رمز عبور جدید معلم با موفقیت صادر شد",
        "new_password": new_password
    }

@router.put("/admin/teachers/{id}/credentials")
def update_teacher_credentials(id: int, data: TeacherCredentialsUpdateRequest, db: Session = Depends(get_db), current_user = Depends(get_current_user), _: str = Depends(check_admin_access)):
    teacher = db.query(Teacher).filter(Teacher.id == id, Teacher.is_deleted == False).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="معلم یافت نشد")

    # FIX H20: نرمال‌سازی به‌جای رد خام H1 — ورودی معتبرِ بدفرمت تمیز و canonical ذخیره می‌شود.
    new_mobile = normalize_mobile(data.mobile)
    if not new_mobile:
        raise HTTPException(status_code=400, detail="فرمت شماره موبایل جدید صحیح نیست. باید ۱۰ یا ۱۱ رقم باشد")

    old_mobile = teacher.mobile
    old_card = teacher.card_number

    # FIX (same pattern as change_mobile): چک یکتایی موبایل جدید بین معلم‌های دیگر، قبل از commit.
    if new_mobile != old_mobile:
        clash = db.query(Teacher).filter(Teacher.mobile == new_mobile, Teacher.id != teacher.id).first()
        if clash:
            raise HTTPException(status_code=409, detail="این شماره موبایل قبلاً توسط معلم دیگری ثبت شده است")

    teacher.mobile = new_mobile
    teacher.card_number = data.card_number

    # FIX: سینک username سایه با موبایل جدید تا لینک سایه یتیم نشود (وگرنه «لاگین زامبی» با موبایل قدیمی).
    if new_mobile != old_mobile:
        shadow = db.query(User).filter(User.username == old_mobile, User.role == "teacher").first()
        if shadow is None:
            # fallback ناهماهنگی‌های قدیمی (username سایه با موبایل فعلی فرق دارد): حل از طریق سشن
            last_sess = db.query(UserSession).filter(UserSession.teacher_id == teacher.id).order_by(UserSession.id.desc()).first()
            if last_sess is not None:
                cand = db.query(User).filter(User.id == last_sess.user_id, User.role == "teacher").first()
                if cand is not None:
                    shadow = cand
        if shadow is not None:
            shadow.username = new_mobile

    # Write to activity log
    log_entry = ActivityLog(
        admin_username=current_user.username,
        action="update_teacher_credentials",
        target_id=teacher.id,
        target_name=f"{teacher.first_name or ''} {teacher.last_name or ''}".strip() or "نامشخص",
        details=f"موبایل: {old_mobile}->{new_mobile} | شماره کارت: {old_card}->{data.card_number}"
    )
    db.add(log_entry)
    from sqlalchemy.exc import IntegrityError  # local: فقط همین‌جا لازم است
    try:
        db.commit()
    except IntegrityError:
        # backstop مسابقه‌ی هم‌زمان (race) بین چک بالا و commit
        db.rollback()
        raise HTTPException(status_code=409, detail="این شماره موبایل قبلاً در سیستم ثبت شده است")

    return {
        "message": "اطلاعات تماس و حساب بانکی معلم با موفقیت به‌روزرسانی شد"
    }


# ===================== گروه ۶: تاریخچهٔ جلسهٔ ادمین =====================
def _session_problem_flags(db: Session, session: SessionLog) -> list[str]:
    enrollments = db.query(func.count(Enrollment.id)).filter(
        Enrollment.course_id == session.course_id, Enrollment.is_deleted == False
    ).scalar() or 0
    attendance_count = db.query(func.count(Attendance.id)).filter(
        Attendance.session_id == session.id, Attendance.is_deleted == False
    ).scalar() or 0
    flags = []
    if enrollments and attendance_count < enrollments:
        flags.append("attendance_missing")
    if session.start_time and session.time and session.start_time != session.time:
        flags.append("started_late")
    if str(session.status or "").lower() in ("auto_ended", "auto-ended", "automatically_ended"):
        flags.append("auto_ended")
    return flags


@router.get("/admin/session_history")
def admin_session_history(
    date_from: str | None = None, date_to: str | None = None,
    teacher_id: int | None = None, course_id: int | None = None,
    flag: str | None = None, status: str | None = None,
    search: str | None = None, export: bool = False,
    db: Session = Depends(get_db), _: str = Depends(check_admin_access)
):
    query = db.query(SessionLog).join(Course).filter(SessionLog.is_deleted == False)
    if teacher_id is not None:
        query = query.filter(Course.teacher_id == teacher_id)
    if course_id is not None:
        query = query.filter(SessionLog.course_id == course_id)
    if status:
        query = query.filter(SessionLog.status == status)
    rows = query.order_by(desc(SessionLog.id)).all()
    from today_summary import parse_project_date
    date_from_parsed = parse_project_date(date_from) if date_from else None
    date_to_parsed = parse_project_date(date_to) if date_to else None
    search_term = (search or "").strip().lower()
    items = []
    for session in rows:
        session_date = parse_project_date(session.date)
        if date_from_parsed and (session_date is None or session_date < date_from_parsed):
            continue
        if date_to_parsed and (session_date is None or session_date > date_to_parsed):
            continue
        teacher = db.query(Teacher).filter(Teacher.id == session.course.teacher_id).first() if session.course else None
        teacher_name = f"{teacher.first_name or ''} {teacher.last_name or ''}".strip() if teacher else "بدون معلم"
        course_title = session.course.title if session.course else "کلاس نامشخص"
        if search_term and search_term not in " ".join((course_title or "", teacher_name, str(session.course_id))).lower():
            continue
        flags = _session_problem_flags(db, session)
        if flag and flag not in flags:
            continue
        attendance_rows = db.query(Attendance).filter(
            Attendance.session_id == session.id, Attendance.is_deleted == False
        ).all()
        charge_total = db.query(func.coalesce(func.sum(Transaction.amount * -1), 0)).filter(
            Transaction.session_id == session.id, Transaction.type == "session_charge",
            Transaction.is_deleted == False, Transaction.is_reversed == False,
        ).scalar() or 0
        billed_count = sum(1 for attendance in attendance_rows if attendance.is_billed)
        items.append({
            "id": session.id, "course_id": session.course_id,
            "course_title": course_title, "teacher_id": session.course.teacher_id if session.course else None,
            "teacher_name": teacher_name,
            "branch_id": session.course.branch_id if session.course else None,
            "date": session.date, "time": session.time, "start_time": session.start_time,
            "end_time": session.end_time, "status": session.status,
            "attendance_count": len(attendance_rows),
            "attendance": [
                {"student_id": row.student_id,
                 "student_name": (f"{row.student.first_name or ''} {row.student.last_name or ''}".strip()
                                   if row.student else "دانش‌آموز نامشخص"),
                 "status": row.status, "excused": bool(row.excused), "is_billed": bool(row.is_billed)}
                for row in attendance_rows
            ],
            "financial_status": {
                "charge_amount": int(charge_total), "billed_attendance_count": billed_count,
                "penalty_settled": bool(session.is_penalty_settled),
                "has_financial_effect": bool(charge_total or billed_count or session.is_penalty_settled),
            },
            "problem_flags": flags,
            "attendance_missing": "attendance_missing" in flags,
            "started_late": "started_late" in flags,
            "auto_ended": "auto_ended" in flags,
            "reopen_allowed": not db.query(Attendance).filter(
                Attendance.session_id == session.id, Attendance.is_billed == True
            ).first() and not session.is_penalty_settled,
        })
    if not export:
        return {"items": items, "count": len(items), "filters": {
            "date_from": date_from, "date_to": date_to, "teacher_id": teacher_id,
            "course_id": course_id, "flag": flag, "status": status, "search": search
        }}
    wb = Workbook()
    ws = wb.active
    ws.title = "session_history"
    ws.append(["id", "course", "teacher", "date", "time", "status", "flags", "attendance_count",
               "billed_attendance_count", "charge_amount", "penalty_settled"])
    for item in items:
        financial = item["financial_status"]
        ws.append([item["id"], item["course_title"], item["teacher_name"], item["date"], item["time"],
                   item["status"], ",".join(item["problem_flags"]), item["attendance_count"],
                   financial["billed_attendance_count"], financial["charge_amount"], financial["penalty_settled"]])
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return StreamingResponse(stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=session_history.xlsx"})


@router.post("/admin/session_history/{session_id}/reopen")
def reopen_admin_session(
    session_id: int, reason: str, db: Session = Depends(get_db), _: str = Depends(check_admin_access)
):
    if not reason or not reason.strip():
        raise HTTPException(status_code=400, detail="علت بازگشایی جلسه الزامی است")
    session = db.query(SessionLog).filter(SessionLog.id == session_id, SessionLog.is_deleted == False).first()
    if not session:
        raise HTTPException(status_code=404, detail="جلسه یافت نشد")
    if session.is_penalty_settled or db.query(Attendance).filter(
        Attendance.session_id == session.id, Attendance.is_billed == True
    ).first():
        raise HTTPException(status_code=409, detail="جلسهٔ دارای اثر مالی قابل بازگشایی نیست")
    session.status = "Reopened"
    db.add(ActivityLog(admin_username="group6", action="session_reopen",
                        target_id=session.id, target_name=str(session.course_id), details=reason.strip()))
    db.commit()
    return {"message": "جلسه برای اصلاح حضور و غیاب باز شد", "session_id": session.id}
