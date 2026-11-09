from pydantic import BaseModel, Field, field_validator  # FIX: Bug 22 - constrain online payment amounts at request validation.
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Header, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError  # FIX (audit-v2/idempotency): شکار مسابقه‌ی retry هم‌زمان روی UNIQUE کلید
from typing import List, Optional, Union
from sqlalchemy import desc, or_, text, func, case
import io
import uuid
import os
import datetime
import html
import time  # O-05: چاپ حواله از time.time() برای ساخت print_job_id استفاده می‌کند

import models
from models import (
    Attendance, Course, Enrollment, Grade, InstituteShare, SessionLog, SmsLog, Student, Teacher, Transaction, User, UserSession, Installment, TransactionInstallmentAllocation
)
from schemas import (
    HistoryRequest, LoginRequest, TeacherInfo, FullTeacherProfile, StudentCreate, TeacherCreate, CourseCreate, EnrollmentCreate, GradeCreate, GradeItem, AttendanceLogRequest, AttendanceItem, AttendanceSubmitData, SmsSendRequest, ChangePasswordRequest, StudentProfileInfo, FullStudentProfile, TeacherProfileInfo, FullTeacherProfile, ClassReportInfo, ClassStudentData, ClassSessionHistory, FullClassReport, ShareConfigModel, StudentUpdate, TeacherUpdate, PersonListItem, TransactionUpdate, StudentAttendanceHistoryRequest, AdvancedSearchItem, FinanceSubmitData, PrintReceiptRequest, TransactionTestData
)
from dependencies import get_db, check_admin_access, check_admin_or_secretary_access, check_user_login, check_student_access, get_enrollment_tuition_and_discount, SESSION_EXPIRY_DAYS, get_session_student, get_session_parent, display_name, safe_person_name  # FIX (L14/Y4): check_student_access برای 637

# FIX: Bug 16 - share the tuition-minus-payment debt calculation across financial views.
from dependencies import limiter  # FIX F-B1: ریت‌لیمیت کال‌بک پرداخت (endpoint پول بدون احراز).
from financial_calculations import calculate_student_debt, calculate_enrollment_debt_breakdown, session_fields_for_client
# FIX (F-T2): اعتبارسنجی مرکزی تاریخ/مبلغ قسط — یک منبع حقیقت برای هر دو مسیر ساخت قسط.
from validation import validate_installment_amount, validate_jalali_due_date
# FIX: Bug 11 - the existing refund audit write needs its model imported at runtime.
from models import ActivityLog

router = APIRouter()

def get_user_branch_filter(db: Session, authorization: Optional[str], branch_id: Optional[int]) -> Optional[int]:
    if not authorization:
        return branch_id
    try:
        token = authorization.split()[1]
        session = db.query(models.UserSession).filter(models.UserSession.token == token).first()
        if session:
            if session.sub_role in ["student", "parent"]:
                return branch_id
            user = db.query(User).filter(User.id == session.user_id).first()
            if user and user.branch_id is not None:
                return user.branch_id
    except Exception:
        pass
    return branch_id

@router.get("/finance/search_advanced")
def search_finance_advanced(
    query: str,
    branch_id: Optional[int] = None,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    sub_role: str = Depends(check_user_login)
):
    # FIX (L14/Y4): سرچ مالی — کارکنان کامل؛ معلم فقط کلاس‌ها/شاگردان خودش (صدور فاکتور)؛ شاگرد/ولی 403.
    if sub_role not in ("admin", "secretary", "teacher"):
        raise HTTPException(status_code=403, detail="شما دسترسی لازم برای جستجوی مالی را ندارید")
    _own_course_ids = _own_student_ids = None
    if sub_role == "teacher":
        from routers.reports import get_logged_in_teacher  # lazy (جلوگیری از import چرخه‌ای)
        _me = get_logged_in_teacher(db, authorization)
        if not _me:
            raise HTTPException(status_code=403, detail="شما دسترسی لازم برای جستجوی مالی را ندارید")
        _own_course_ids = [r[0] for r in db.query(Course.id).filter(Course.teacher_id == _me.id).all()]
        _own_student_ids = [r[0] for r in db.query(Enrollment.student_id).filter(Enrollment.course_id.in_(_own_course_ids), Enrollment.is_deleted == False).distinct().all()]
    resolved_branch = get_user_branch_filter(db, authorization, branch_id)
    results = []
    search = f"%{query}%"

    # الف) جستجو در کلاس‌ها
    courses_q = db.query(Course).filter(or_(Course.title.ilike(search), Course.code.ilike(search)))
    if _own_course_ids is not None:
        courses_q = courses_q.filter(Course.id.in_(_own_course_ids))
    if resolved_branch is not None:
        courses_q = courses_q.filter(Course.branch_id == resolved_branch)
    courses = courses_q.all()
    for c in courses:
        teacher = db.query(Teacher).filter(Teacher.id == c.teacher_id).first()
        t_name = display_name(teacher, "نامشخص") if teacher else "بدون معلم"

        # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
        enrollments = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.course_id == c.id).all()
        class_students = []
        for en in enrollments:
            st = db.query(Student).filter(Student.id == en.student_id, Student.is_deleted == False).first()
            if st:
                # این ردیف نمای یک enrollment داخل کلاس است؛ walletهای Student
                # سراسری‌اند و نباید بدهی کلاس دیگری را به این ردیف کپی کنند.
                breakdown = calculate_enrollment_debt_breakdown(db, en)
                class_students.append(
                    {
                        "id": st.id,
                        "name": display_name(st, "نامشخص"),
                        "debt": breakdown["debt"],
                        "total_debt": breakdown["debt"],
                        "debt_teacher": breakdown["debt_teacher"],
                        "debt_institute": breakdown["debt_institute"],
                        "enrollment_id": en.id,
                        "course_id": c.id,
                        "course_title": c.title,
                        "course_code": c.code or "",
                        "teacher_id": c.teacher_id,
                        "teacher_name": t_name,
                        "is_unassigned": False,
                        **session_fields_for_client(breakdown),
                    }
                )

        results.append(
            AdvancedSearchItem(
                type="class",
                id=c.id,
                title=f"کلاس: {c.title}",
                subtitle=f"مدرس: {t_name}",
                info=f"{len(class_students)} دانش‌آموز",
                students_in_class=class_students,
            )
        )

    # ب) جستجو در دانش‌آموزان (اصلاح حیاتی برای نمایش بدهی)
    students_q = db.query(Student).filter(Student.is_deleted == False).filter(
        or_(
            Student.first_name.ilike(search),
            Student.last_name.ilike(search),
            Student.national_code.ilike(search),
        )
    )
    if _own_student_ids is not None:
        students_q = students_q.filter(Student.id.in_(_own_student_ids))
    if resolved_branch is not None:
        students_q = students_q.filter(Student.branch_id == resolved_branch)
    students = students_q.all()

    for s in students:
        # نتیجهٔ دانش‌آموز چندکلاسه هنوز به یک کلاس مشخص وصل نیست؛ پس بدهی
        # wallet کل نباید در ردیف جستجو به‌عنوان بدهی کلاس نمایش داده شود.
        # نمایش بدهی فقط بعد از انتخاب enrollment واقعی انجام می‌شود؛ اینجا دیگر
        # wallet کل یا «بدهی کل» به‌عنوان بدهی کلاس نمایش داده نمی‌شود.
        enrollments = db.query(Enrollment).filter(
            Enrollment.is_deleted == False,
            Enrollment.student_id == s.id,
        ).all()
        class_count = len([en for en in enrollments if en.course is not None])
        results.append(
            AdvancedSearchItem(
                type="student",
                id=s.id,
                title=display_name(s, "نامشخص"),
                subtitle=f"{class_count} کلاس ثبت‌نام‌شده — برای مشاهده بدهی، کلاس را انتخاب کنید",
                info="بدهی پس از انتخاب کلاس نمایش داده می‌شود",
                student_id=s.id,
                debt_teacher=0,
                debt_institute=0,
                # This is an aggregate search hint only; the client must not
                # attribute it to a class until it selects an enrollment.
                total_debt=calculate_student_debt(db, s),
                unpaid_sessions=0,
            )
        )

    return results


# ==========================================
# اصلاح شده: ثبت واریزی و اصلاح کیف پول‌ها
# ==========================================


def _jalali_now_str() -> str:
    """FIX L7: paid_at شمسی (هماهنگ با due_date و Transaction.date) + ساعت سرور."""
    from today_summary import jalali_date_string  # lazy، مثل H3-B3 همین فایل
    _now = datetime.datetime.now()
    return jalali_date_string(_now.date()) + _now.strftime(" %H:%M")


def _jalali_dt_str(value) -> str:
    """FIX (audit-v2/refund-date-followup): همان فرمت شمسی _jalali_now_str ولی برای datetime ذخیره‌شده (نه اکنون)."""
    from today_summary import jalali_date_string  # lazy، مثل H3-B3 همین فایل
    return jalali_date_string(value.date()) + value.strftime(" %H:%M")


def _replay_idempotent_payment(db: Session, key: str, data: FinanceSubmitData):
    """FIX (audit-v2/idempotency-قدم۱): اگر کلیدی قبلاً پردازش شده، همان نتیجه برگردد — فقط-خواندنی، بدون هیچ نوشتن.
    برمی‌گرداند: dict پاسخ، یا None اگر کلید تازه است. 422 اگر کلید با مبلغ/شاگرد متفاوت reuse شده باشد (باگ کلاینت، نه retry)."""
    rows = (
        db.query(Transaction)
        .filter(Transaction.idempotency_key == key, Transaction.is_deleted == False)
        .order_by(Transaction.id.asc())
        .all()
    )
    if not rows:
        return None
    if rows[0].student_id != data.student_id or sum((r.amount or 0) for r in rows) != data.amount:
        raise HTTPException(status_code=422, detail="این کلید پرداخت قبلاً با مبلغ/شاگرد دیگری ثبت شده؛ کلید تازه تولید کنید")
    _st = db.query(Student).filter(Student.id == data.student_id).first()
    return {
        "message": "مبلغ ثبت و حساب بروزرسانی شد." + (" (تقسیم هر دو)" if data.target_wallet == "both" else ""),
        "receipt_id": rows[0].id,
        "receipt_ids": [r.id for r in rows],
        "new_balance_teacher": (_st.wallet_teacher or 0) if _st else 0,
        "new_balance_institute": (_st.wallet_institute or 0) if _st else 0,
        "duplicate": True,
    }


@router.post("/finance/pay")
# FIX: Bug 9 - accept the existing branch resolver inputs without changing payment payloads.
def submit_payment(
    data: FinanceSubmitData, db: Session = Depends(get_db), _: str = Depends(check_admin_or_secretary_access),
    branch_id: Optional[int] = None, authorization: Optional[str] = Header(None),
):
    # FIX (audit-v2/idempotency-قدم۱): کلید اختیاری (سازگار با عقب)؛ اگر آمده و قبلاً پردازش شده → replay بدون هیچ نوشتن.
    _idem_key = (data.idempotency_key or "").strip()
    if _idem_key:
        _hit = _replay_idempotent_payment(db, _idem_key, data)
        if _hit is not None:
            return _hit
    # FIX B1 (الگوی H8-P4): بدون with_for_update (روی SQLite بی‌اثر است) — این خواندن فقط برای
    # اعتبارسنجی/تعیین شعبه است؛ افزایش کیف‌پول با UPDATE اتمیک SQL بعد از شاخه‌ها انجام می‌شود.
    st = db.query(Student).filter(Student.id == data.student_id).first()
    if not st:
        raise HTTPException(404, "دانش‌آموز یافت نشد")

    # FIX: Bug 9 - every receipt inherits the student's branch, or the resolved branch if absent.
    payment_branch = st.branch_id if st.branch_id is not None else get_user_branch_filter(db, authorization, branch_id)
    # FIX: Bug 9 - never create an unassigned financial transaction when neither source has a branch.
    if payment_branch is None:
        raise HTTPException(status_code=400, detail="شعبه پرداخت مشخص نیست؛ شعبه دانش‌آموز یا شعبه پرداخت را تعیین کنید")

    # FIX: Bug 22 - reject non-positive single-wallet credits before counters, wallets or receipts change.
    # The existing Priority 2 split validation already requires nonnegative shares and a positive total.
    if data.target_wallet != "both" and data.amount <= 0:
        raise HTTPException(status_code=400, detail="مبلغ پرداخت باید بیشتر از صفر باشد")
    # FIX M12: کیف‌پول مقصد فقط یکی از سه مقدار معتبر است — هر چیز دیگری 400 می‌گیرد
    # (قبلاً شاخه‌ی else ساکت تراکنش ثبت می‌کرد ولی هیچ کیفی شارژ نمی‌شد: عدم‌تطابق دفتر/کیف،
    # و بدتر: همان مبلغِ شارژنشده قسط‌ها را تسویه می‌کرد — تسویه‌ی مجانی).
    if data.target_wallet not in ("teacher", "institute", "both"):
        raise HTTPException(status_code=400, detail="کیف‌پول مقصد نامعتبر است؛ فقط teacher، institute یا both")
    # FIX M27: تاریخ رسید قبل از ذخیره با مبدل مرکزی H3 اعتبارسنجی می‌شود (نامعتبر = 400).
    # کران منطقی: گذشته آزاد است (ثبت دستی معوقه مجاز)؛ آینده مردود است (رسید یعنی وجه گرفته‌شده —
    # تاریخ آینده گزارش روزانه را فاسد می‌کند). تلرانس +۱ روز برای اختلاف ساعت سرور/کلاینت تا
    # رسید «امروز» به‌خاطر تهران/UTC بودن false-positive نگیرد.
    from today_summary import parse_project_date  # lazy، مثل الگوی H3-B3 همین فایل
    _pay_date = parse_project_date(data.date)
    if _pay_date is None:
        raise HTTPException(status_code=400, detail="فرمت تاریخ پرداخت معتبر نیست (yyyy/MM/dd)")
    if _pay_date > datetime.date.today() + datetime.timedelta(days=1):
        raise HTTPException(status_code=400, detail="تاریخ پرداخت نمی‌تواند در آینده باشد")

    # 🔗 منبع حقیقت واحد بدهی: تعیین ثبت‌نام لینک‌شده (اعتبارسنجی زودهنگام، قبل از هر تغییری)
    linked_enrollment = None
    if data.enrollment_id is not None:
        linked_enrollment = db.query(Enrollment).filter(Enrollment.id == data.enrollment_id).first()
        if not linked_enrollment or linked_enrollment.is_deleted:
            raise HTTPException(status_code=404, detail="ثبت‌نام مورد نظر یافت نشد")
        if linked_enrollment.student_id != data.student_id:
            raise HTTPException(status_code=400, detail="این ثبت‌نام متعلق به این دانش‌آموز نیست")
    else:
        # قانون «تک‌ثبت‌نامی»: اگر شاگرد فقط یک ثبت‌نام فعال دارد، خودکار به همان وصل می‌شود
        active_enroll_ids = db.query(Enrollment.id).filter(Enrollment.is_deleted == False, Enrollment.student_id == data.student_id).all()
        if len(active_enroll_ids) == 1:
            linked_enrollment = db.query(Enrollment).filter(Enrollment.id == active_enroll_ids[0][0]).first()
            if linked_enrollment is None or linked_enrollment.is_deleted:
                linked_enrollment = None  # خطای هم‌زمان نادر: به شارژ عمومی کیف پول برمی‌گردیم تا پرداخت شکست نخورد
        elif len(active_enroll_ids) > 1:
            raise HTTPException(status_code=400, detail="این دانش‌آموز چند ثبت‌نام فعال دارد، enrollment_id مشخص کنید")

    # «حواله برای چند جلسه»: فقط توضیح/گزارش است و محاسبهٔ مالی را تغییر نمی‌دهد؛ ولی باید به یک کلاس مشخص
    # وصل باشد وگرنه معلوم نیست «جلسه‌های کدام کلاس» است.
    if data.sessions_covered is not None and linked_enrollment is None:
        raise HTTPException(status_code=400, detail="برای ثبت تعداد جلسه، کلاس (ثبت‌نام) دانش‌آموز را مشخص کنید")

    # FIX B1: بدون خواندن-جمع‌زدن در پایتون (RMW) — اینجا فقط سهم هر کیف‌پول محاسبه می‌شود؛
    # افزایش واقعی با یک UPDATE اتمیک SQL بعد از شاخه‌ها انجام می‌شود (رجوع به بلوک «آپدیت اتمیک» پایین).
    add_teacher = 0
    add_institute = 0

    desc_full = data.description
    from dependencies import get_next_sequence_value

    transactions_created = []
    total_amount_for_installment = 0

    # ✅ منطق جدید: پشتیبانی از target_wallet = "both" (تقسیم مبلغ بین دو کیف پول)
    if data.target_wallet == "both":
        # FIX: Bug 10 - explicit splits must be complete; omitting both shares requests a half split.
        amt_teacher = 0
        amt_institute = 0

        if data.amount_teacher is not None or data.amount_institute is not None:
            # FIX: Bug 10 - do not silently interpret a missing institute share as zero/100% teacher.
            if data.amount_teacher is None or data.amount_institute is None:
                raise HTTPException(400, "برای پرداخت به هر دو کیف‌پول، هر دو سهم را تعیین کنید؛ برای تقسیم مساوی، هر دو مبلغ را خالی بگذارید")
            amt_teacher = data.amount_teacher
            amt_institute = data.amount_institute
        else:
            # FIX: Bug 10 - amount is the total; preserve every unit, including an odd remainder.
            amt_teacher = data.amount // 2
            amt_institute = data.amount - amt_teacher

        # اعتبارسنجی
        if amt_teacher < 0 or amt_institute < 0:
            raise HTTPException(400, "مبالغ نمی‌توانند منفی باشند")
        if amt_teacher == 0 and amt_institute == 0:
            raise HTTPException(400, "حداقل یکی از مبالغ باید بیشتر از صفر باشد")

        # FIX B1: فقط تعیین سهم (افزایش اتمیک، بعد از شاخه‌ها).
        add_teacher = amt_teacher
        add_institute = amt_institute
        total_amount_for_installment = amt_teacher + amt_institute

        # ثبت دو تراکنش جداگانه برای شفافیت حسابداری
        if amt_teacher > 0:
            next_rem_teacher = get_next_sequence_value(db, "remittance_teacher", 100001)
            trans_t = Transaction(
                student_id=data.student_id,
                branch_id=payment_branch,  # FIX: Bug 9 - persist the branch on split receipts.
                amount=amt_teacher,
                payment_method=data.payment_method,
                date=data.date,
                description=desc_full + " (سهم معلم - تقسیم هر دو)",
                type="deposit",
                target_wallet="teacher",
                remittance_number=next_rem_teacher,
            )
            db.add(trans_t)
            transactions_created.append(trans_t)

        if amt_institute > 0:
            next_rem_inst = get_next_sequence_value(db, "remittance_institute", 100001)
            trans_i = Transaction(
                student_id=data.student_id,
                branch_id=payment_branch,  # FIX: Bug 9 - persist the branch on split receipts.
                amount=amt_institute,
                payment_method=data.payment_method,
                date=data.date,
                description=desc_full + " (سهم آموزشگاه - تقسیم هر دو)",
                type="deposit",
                target_wallet="institute",
                remittance_number=next_rem_inst,
            )
            db.add(trans_i)
            transactions_created.append(trans_i)

        # برای سازگاری، یک تراکنش تجمیعی هم با target_wallet=both ثبت می‌کنیم (اختیاری، برای گزارش)
        # اما اصلی دو تراکنش بالاست

    elif data.target_wallet == "teacher":
        add_teacher = data.amount
        desc_full += " (سهم معلم)"
        total_amount_for_installment = data.amount
        next_remittance = get_next_sequence_value(db, "remittance_teacher", 100001)
        new_trans = Transaction(
            student_id=data.student_id,
            branch_id=payment_branch,  # FIX: Bug 9 - persist the branch on every receipt.
            amount=data.amount,
            payment_method=data.payment_method,
            date=data.date,
            description=desc_full,
            type="deposit",
            target_wallet=data.target_wallet,
            remittance_number=next_remittance,
        )
        db.add(new_trans)
        transactions_created.append(new_trans)

    elif data.target_wallet == "institute":
        add_institute = data.amount
        desc_full += " (سهم آموزشگاه)"
        total_amount_for_installment = data.amount
        next_remittance = get_next_sequence_value(db, "remittance_institute", 100001)
        new_trans = Transaction(
            student_id=data.student_id,
            branch_id=payment_branch,  # FIX: Bug 9 - persist the branch on every receipt.
            amount=data.amount,
            payment_method=data.payment_method,
            date=data.date,
            description=desc_full,
            type="deposit",
            target_wallet=data.target_wallet,
            remittance_number=next_remittance,
        )
        db.add(new_trans)
        transactions_created.append(new_trans)

    else:
        # FIX M12 (دفاعی؛ با اعتبارسنجی بالای تابع عملاً unreachable): هیچ «واریز بدون کیف»ای
        # ثبت نمی‌شود — حالت «بدون کیف مشخص» نامشروع است چون تراکنشِ بدون شارژ کیف یعنی
        # عدم‌تطابق دفتر/کیف و تسویه‌ی مجانی قسط. هیچ تراکنشی هم ثبت نمی‌شود (۴۰۰ قبل از هر نوشتن).
        raise HTTPException(status_code=400, detail="کیف‌پول مقصد نامعتبر است؛ فقط teacher، institute یا both")

    # FIX (audit-v2/idempotency-قدم۱): مهر کلید روی همه‌ی رسیدهای همین پرداخت (both = دو ردیف، یک کلید).
    if _idem_key:
        for t in transactions_created:
            t.idempotency_key = _idem_key

    # FIX B1 (الگوی H8-P4): افزایش اتمیک کیف‌پول‌ها در SQL — جمع در دیتابیس، نه خواندن-جمع‌زدن در پایتون.
    # COALESCE رفتار قدیمی None→0 را حفظ می‌کند (ستون‌ها nullable هستند)؛ rowcount باید ۱ باشد (فقط existence).
    if add_teacher or add_institute:
        wallet_rows = (
            db.query(Student)
            .filter(Student.id == data.student_id)
            .update(
                {
                    Student.wallet_teacher: func.coalesce(Student.wallet_teacher, 0) + add_teacher,
                    Student.wallet_institute: func.coalesce(Student.wallet_institute, 0) + add_institute,
                },
                synchronize_session=False,
            )
        )
        if wallet_rows != 1:
            db.rollback()
            raise HTTPException(status_code=404, detail="دانش‌آموز یافت نشد")

    # 🔗 لینک تراکنش‌های ساخته‌شده به ثبت‌نام + افزایش اتمیک total_paid (در همان تراکنش دیتابیسی، اتمیک)
    if linked_enrollment is not None and total_amount_for_installment > 0:
        for t in transactions_created:
            t.enrollment_id = linked_enrollment.id
            t.course_id = linked_enrollment.course_id
            t.sessions_covered = data.sessions_covered  # None برای کلاینت قدیمی = رفتار قبلی
        # FIX B1 (الگوی H8-P4): اگر ثبت‌نام بین اعتبارسنجی بالا و این لحظه حذف شده باشد، rowcount صفر می‌شود.
        paid_rows = (
            db.query(Enrollment)
            .filter(Enrollment.id == linked_enrollment.id, Enrollment.is_deleted == False)
            .update(
                {Enrollment.total_paid: func.coalesce(Enrollment.total_paid, 0) + total_amount_for_installment},
                synchronize_session=False,
            )
        )
        if paid_rows != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail="ثبت‌نام هم‌زمان حذف شد؛ لطفاً صفحه را رفرش کنید")

    # ترتیب سینک با sync_wallet_balance (مهم): اول UPDATEهای خام بالا، بعد refresh برای گرفتن مقادیر
    # تازه از دیتابیس، بعد سینک بالانس کل. (آپدیت bulk شنونده‌ی before_update را اجرا نمی‌کند، پس سینک صریح لازم است.)
    if add_teacher or add_institute:
        db.refresh(st)
        # FIX: Bug 18 - derive the total only through the shared wallet helper.
        st.sync_wallet_balance()

    # مقادیر نهایی برای پاسخ — از روی آبجکت تازه‌شده (بعد از UPDATE اتمیک)
    final_w_t = st.wallet_teacher if st.wallet_teacher else 0
    final_w_i = st.wallet_institute if st.wallet_institute else 0

    # 💰 تخصیص هوشمند مبلغ پرداختی به قدیمی‌ترین اقساط تسویه نشده دانش‌آموز (در صورت وجود اقساط)
    # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
    # FIX (audit-v2/issue9-الف): پرداخت لینک‌شده فقط اقساط همان ثبت‌نام را می‌پوشاند — هم‌مبنا با
    # total_paid/debt که per-enrollment است (قبلاً cross بود و نمایش قسط با بدهی ناسازگار می‌شد).
    # بی‌لینک (شارژ عمومی کیف) عمداً رفتار cross قدیمی را نگه می‌دارد (جریان تخصیص ندارد — بیرون اسکوپ).
    if linked_enrollment is not None:
        enrollment_ids = [linked_enrollment.id]
    else:
        enrollments = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.student_id == data.student_id).all()
        enrollment_ids = [e.id for e in enrollments]
    if enrollment_ids:
        unpaid_installments = (
            # FIX: Bug 13 - exclude archived Installment rows from this active view.
            db.query(Installment).filter(Installment.is_deleted == False)
            .filter(
                Installment.enrollment_id.in_(enrollment_ids),
                Installment.is_paid == False
            )
            .order_by(Installment.due_date.asc())
            .all()
        )
        # FIX (audit-v2/issue7): autoflush خاموش است (models.SessionLocal) پس قبل از ledger، flush صریح —
        # رسیدها آیدی می‌گیرند (کامیت همان انتهای تابع؛ اتمیسیته عوض نمی‌شود).
        db.flush()
        # توزیع FIFO پوشش روی رسیدهای همین پرداخت (both = ۲ رسید): استردادِ هر رسید دقیقاً پوششِ
        # سهم خودش را برمی‌گرداند؛ تک‌کیفی (اکثریت) همیشه ایندکس صفر است.
        _alloc_receipts = [x.id for x in transactions_created]
        _alloc_amounts = [(x.amount or 0) for x in transactions_created]
        _alloc_idx = 0
        remaining_payment = total_amount_for_installment if total_amount_for_installment > 0 else data.amount
        # FIX (audit-v2/idempotency-قدم۲، الگوی H8-P4/B1): پوشش اتمیک قسط — هر ردیف فقط با UPDATE مشروط
        # (paid_amount == خوانده‌شده + is_paid == False) جلو می‌رود؛ rowcount صفر یعنی پرداخت موازی همین
        # قسط را تکان داد → رفرش + محاسبه‌ی مجدد (۳ تلاش) وگرنه 409. کسر از remaining فقط بعد از موفقیت
        # UPDATE انجام می‌شود پس lost-update ناممکن است و جمع پوشش‌ها هرگز از بدهی بیشتر نمی‌شود.
        for inst in unpaid_installments:
            if remaining_payment <= 0:
                break
            for _try in range(3):
                db.refresh(inst)  # وضعیت تازه — پرداخت‌های موازیِ کامیت‌شده دیده می‌شوند.
                if inst.is_paid or inst.is_deleted:
                    break  # موازی تسویه/حذفش کرد — remaining دست‌نخورده، قسط بعدی.
                # FIX M13 (گزینه‌ی ب، حفظ شد): تجمعی؛ is_paid فقط با پوشش کامل.
                _already = inst.paid_amount or 0
                _owed = (inst.amount or 0) - _already
                if _owed <= 0:
                    # ناسازگاری قدیمی نادر: فقط فلگ، مشروط (rowcount مهم نیست — موازی هم ممکن است فلیپ کرده باشد).
                    db.query(Installment).filter(Installment.id == inst.id, Installment.is_paid == False).update({Installment.is_paid: True}, synchronize_session=False)
                    break
                _cover = min(remaining_payment, _owed)
                _new_paid = _already + _cover
                _fully = _new_paid >= (inst.amount or 0)
                _set = {Installment.paid_amount: _new_paid}
                if _fully:
                    _set[Installment.is_paid] = True
                    _set[Installment.paid_at] = _jalali_now_str()  # FIX L7: شمسی.
                _rows = (
                    db.query(Installment)
                    .filter(Installment.id == inst.id, Installment.is_paid == False, Installment.is_deleted == False, func.coalesce(Installment.paid_amount, 0) == _already)
                    .update(_set, synchronize_session=False)
                )
                if _rows == 1:
                    remaining_payment -= _cover
                    # FIX (audit-v2/issue7): ثبت ledger — مبلغ دقیق همین پوشش، توزیع FIFO روی رسیدها.
                    _need = _cover
                    while _need > 0 and _alloc_idx < len(_alloc_receipts):
                        _take = min(_need, _alloc_amounts[_alloc_idx])
                        if _take > 0:
                            db.add(TransactionInstallmentAllocation(transaction_id=_alloc_receipts[_alloc_idx], installment_id=inst.id, amount=_take))
                            _need -= _take
                            _alloc_amounts[_alloc_idx] -= _take
                        if _alloc_amounts[_alloc_idx] <= 0:
                            _alloc_idx += 1
                    break
            else:
                db.rollback()
                raise HTTPException(status_code=409, detail="تغییر هم‌زمان در اقساط؛ لطفاً دوباره تلاش کنید")

    # FIX (audit-v2/idempotency-قدم۱): مسابقه‌ی دو retry هم‌زمان — هر دو pre-check را رد می‌کنند؛
    # دومی روی UNIQUE ایندکس می‌افتد → به‌جای 500، نتیجه‌ی برنده replay می‌شود.
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if _idem_key:
            _won = _replay_idempotent_payment(db, _idem_key, data)
            if _won is not None:
                return _won
        raise
    # رفرش تراکنش‌های ایجاد شده
    for t in transactions_created:
        db.refresh(t)

    primary_receipt_id = transactions_created[0].id if transactions_created else 0

    return {
        "message": "مبلغ ثبت و حساب بروزرسانی شد." + (" (تقسیم هر دو)" if data.target_wallet == "both" else ""),
        "receipt_id": primary_receipt_id,
        "receipt_ids": [t.id for t in transactions_created],
        "new_balance_teacher": final_w_t,
        "new_balance_institute": final_w_i,
        "sessions_covered": data.sessions_covered,
    }


# ==========================================
# 🖨️ چاپ و ذخیره PDF حواله
# ==========================================
class PrintReceiptRequest(BaseModel):
    transaction_id: int
    print_type: str  # "print" or "pdf"


def _receipt_context(db: Session, trans) -> dict:
    """اطلاعات کلاس/معلم/جلسهٔ یک حواله برای نمایش و چاپ (فقط خواندنی؛ حتی برای رسید قدیمی بدون این فیلدها).

    حوالهٔ «هر دو» دو رسید جدا دارد (سهم معلم و سهم آموزشگاه)؛ هر رسید همان کیف‌پول خودش را نشان می‌دهد.
    """
    course = None
    enrollment = None
    _enroll_id = getattr(trans, "enrollment_id", None)
    if _enroll_id:
        enrollment = db.query(Enrollment).filter(Enrollment.id == _enroll_id).first()
        if enrollment is not None and getattr(enrollment, "course_id", None):
            course = db.query(Course).filter(Course.id == enrollment.course_id).first()
    if course is None and getattr(trans, "course_id", None):
        course = db.query(Course).filter(Course.id == trans.course_id).first()
    teacher = None
    if course is not None and course.teacher_id:
        teacher = db.query(Teacher).filter(Teacher.id == course.teacher_id).first()
    teacher_name = display_name(teacher, "") if teacher is not None else ""
    wallet = getattr(trans, "target_wallet", None)
    wallet_label = {"teacher": "سهم معلم", "institute": "سهم آموزشگاه"}.get(wallet or "", "")
    ctx = {
        "course_name": (course.title if course is not None and course.title else "---"),
        "course_code": (course.code if course is not None and course.code else ""),
        "course_id": (course.id if course is not None else None),
        "teacher_id": (course.teacher_id if course is not None else None),
        "teacher_name": teacher_name,
        "sessions_covered": getattr(trans, "sessions_covered", None),
        "wallet_label": wallet_label,
        "paid_to_name": teacher_name if wallet == "teacher" else ("آموزشگاه" if wallet == "institute" else ""),
        # مانده‌ی «همین لحظه» ی همان کلاس (نه لحظه‌ی صدور) — برای مدیر که هنگام چاپ ببیند چقدر مانده.
        "class_remaining_teacher": None,
        "class_remaining_institute": None,
    }
    if enrollment is not None and not enrollment.is_deleted:
        try:
            breakdown = calculate_enrollment_debt_breakdown(db, enrollment)
            ctx["class_remaining_teacher"] = int(breakdown["debt_teacher"])
            ctx["class_remaining_institute"] = int(breakdown["debt_institute"])
        except Exception:  # چاپ رسید هرگز به‌خاطر این بخش اطلاعاتی نباید شکست بخورد
            pass
    return ctx


@router.post("/finance/receipt/print")
def print_receipt(req: PrintReceiptRequest, db: Session = Depends(get_db), authorization: Optional[str] = Header(None), _: str = Depends(check_user_login)):
    """
    چاپ مستقیم حواله روی پرینتر سیستم
    """
    transaction = (
        # FIX: Bug 12 - exclude archived Transaction rows from this active view.
        db.query(Transaction).filter(Transaction.is_deleted == False, Transaction.is_reversed == False).filter(Transaction.id == req.transaction_id).first()
    )
    if not transaction:
        raise HTTPException(404, "تراکنش یافت نشد")

    # FIX H16-IDOR: هماهنگ با GET رسید — فقط ادمین/منشی یا صاحب تراکنش.
    verify_financial_idor(transaction.student_id, authorization, db)
    
    student = db.query(Student).filter(Student.id == transaction.student_id).first()
    if not student:
        raise HTTPException(404, "دانش‌آموز یافت نشد")

    # اطلاعات حواله برای چاپ
    receipt_data = {
        "receipt_id": transaction.id,
        "student_name": display_name(student, "نامشخص"),
        "student_national_code": student.national_code,
        "amount": transaction.amount,
        "payment_method": transaction.payment_method,
        "date": transaction.date,
        "description": transaction.description,
        "target_wallet": transaction.target_wallet,
        "type": transaction.type,
        **_receipt_context(db, transaction),
    }

    # در اینجا منطق ارسال به پرینتر سیستم اجرا می‌شود
    # برای نمونه، اطلاعات را در قالب مناسب برای چاپ برمی‌گردانیم

    return {
        "status": "success",
        "message": "درخواست چاپ حواله به سیستم ارسال شد.",
        "print_job_id": f"PRINT_{transaction.id}_{int(time.time())}",
        "receipt_data": receipt_data,
    }


@router.post("/finance/receipt/pdf")
def generate_pdf_receipt(req: PrintReceiptRequest, db: Session = Depends(get_db), authorization: Optional[str] = Header(None), _: str = Depends(check_user_login)):
    """
    تولید و دانلود فایل PDF حواله
    """
    transaction = (
        # FIX: Bug 12 - exclude archived Transaction rows from this active view.
        db.query(Transaction).filter(Transaction.is_deleted == False, Transaction.is_reversed == False).filter(Transaction.id == req.transaction_id).first()
    )
    if not transaction:
        raise HTTPException(404, "تراکنش یافت نشد")

    # FIX H16-IDOR: هماهنگ با GET رسید — فقط ادمین/منشی یا صاحب تراکنش.
    verify_financial_idor(transaction.student_id, authorization, db)
    
    student = db.query(Student).filter(Student.id == transaction.student_id).first()
    if not student:
        raise HTTPException(404, "دانش‌آموز یافت نشد")

    # اطلاعات حواله برای PDF
    receipt_data = {
        "receipt_id": transaction.id,
        "student_name": display_name(student, "نامشخص"),
        "student_national_code": student.national_code,
        "amount": transaction.amount,
        "payment_method": transaction.payment_method,
        "date": transaction.date,
        "description": transaction.description,
        "target_wallet": transaction.target_wallet,
        "type": transaction.type,
        **_receipt_context(db, transaction),
    }

    # در اینجا منطق تولید PDF اجرا می‌شود
    # برای نمونه، اطلاعات را در قالب مناسب برای دانلود برمی‌گردانیم

    # شبیه‌سازی نام فایل PDF
    pdf_filename = f"receipt_{transaction.id}_{student.national_code}.pdf"

    return {
        "status": "success",
        "message": "فایل PDF حواله آماده دانلود است.",
        "pdf_url": f"/downloads/{pdf_filename}",
        "filename": pdf_filename,
        "receipt_data": receipt_data,
    }


@router.get("/finance/student_class_status")
def get_student_class_status(student_id: int, course_id: Optional[int] = None, course_code: Optional[str] = None, db: Session = Depends(get_db), authorization: Optional[str] = Header(None), sub_role: str = Depends(check_user_login)):
    # FIX (L14/Y4): وضعیت مالی ثبت‌نام یک شاگرد — check_student_access (نه verify_financial_idor که معلم را کامل 403 می‌کند؛ معلم برای فاکتور شاگرد خودش محق است).
    check_student_access(student_id, authorization, db, sub_role)
    student = db.query(Student).filter(Student.id == student_id, Student.is_deleted == False).first()
    if not student:
        raise HTTPException(status_code=404, detail="دانش‌آموز یافت نشد")
        
    # در صورت ارسال کد کلاس به جای آیدی
    if course_code:
        course = db.query(Course).filter(Course.code == course_code.strip()).first()
        if not course:
            raise HTTPException(status_code=404, detail="کلاس مورد نظر یافت نشد")
        course_id = course.id
        
    # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
    enroll = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.student_id == student_id, Enrollment.course_id == course_id).first()
    if not enroll:
        raise HTTPException(status_code=404, detail="ثبت‌نام یافت نشد")
        
    # وضعیت صورت‌حساب باید فقط از همین enrollment بیاید؛ wallet کلی دانش‌آموز
    # در این endpoint کلاس‌محور منبع due نیست.
    breakdown = calculate_enrollment_debt_breakdown(db, enroll)
    final_tuition = breakdown["tuition"]
    paid_to_teacher = breakdown["paid_teacher"]
    paid_to_institute = breakdown["paid_institute"]
    paid_total = paid_to_teacher + paid_to_institute
    due_to_teacher = breakdown["debt_teacher"]
    due_to_institute = breakdown["debt_institute"]
    return {
        "total_amount": final_tuition,
        "paid_to_teacher": paid_to_teacher,
        "paid_to_institute": paid_to_institute,
        "due_to_teacher": due_to_teacher,
        "due_to_institute": due_to_institute,
        # For the class-scoped quick-remittance form, the payable default is the
        # sum of the two actual shares, never the student's aggregate/contractual
        # balance from another class.
        "remaining_tuition": due_to_teacher + due_to_institute,
        "credit_balance": max(0, paid_total - final_tuition),
        "course_id": course_id,
        "course_title": enroll.course.title if enroll.course else None,
        "teacher_id": enroll.course.teacher_id if enroll.course else None,
        "teacher_name": display_name(enroll.course.teacher, "نامشخص") if enroll.course and enroll.course.teacher else None,
        "is_unassigned": False,
        # لینک دقیق ثبت‌نام فعال (همان سطری که شهریه از آن خوانده شد) برای اتصال پرداخت بعدی
        "enrollment_id": enroll.id,
        "course_code": (enroll.course.code if enroll.course and enroll.course.code else ""),
        # «این مبلغ برای چند جلسه است؟» + فهرست جلسه‌های پرداخت‌نشده (قدیمی‌ترین اول) برای محاسبهٔ
        # مبلغ «حواله برای N جلسه». فقط خواندنی؛ جمع فهرست = due_to_teacher / due_to_institute.
        **session_fields_for_client(breakdown, include_items=True),
    }


# ==========================================
# 🔥 تست منطق حذف و ویرایش تراکنش‌ها
# ==========================================
class TransactionTestData(BaseModel):
    student_id: int
    amount: int
    target_wallet: str
    description: str
    payment_method: str
    date: str


# =========================================================================
# 💰 بخش جدید: اضافه کردن قابلیت‌های مالی پیشرفته و رفع نواقص (Finance Upgrades)
# =========================================================================

from fastapi.responses import HTMLResponse, RedirectResponse
from payment_gateways import get_payment_gateway
import models

# --- Feature flag درگاه پرداخت آنلاین ---
# پیش‌فرض false: تا اتصال درگاه واقعی بانکی، کال‌بک و صفحه‌ی شبیه‌ساز 404 می‌دهند.
PAYMENT_GATEWAY_ENABLED = os.getenv("PAYMENT_GATEWAY_ENABLED", "false").lower() in ("1", "true", "yes")

# --- کمکی امنیتی جهت ممانعت از IDOR برای اولیا و دانش‌آموزان ---
def verify_financial_idor(student_id: int, authorization: Optional[str], db: Session) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="توکن احراز هویت یافت نشد")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="قالب توکن معتبر نیست")
    token = parts[1]
    session = db.query(UserSession).filter(UserSession.token == token).first()
    if not session:
        raise HTTPException(status_code=401, detail="نشست نامعتبر یا منقضی شده است")
    
    # ادمین و منشی دسترسی کامل دارند
    if session.sub_role in ["admin", "secretary"]:
        return session.sub_role
        
    # دانش‌آموز یا ولی فقط به اطلاعات مالی خودشان دسترسی دارند
    if session.sub_role in ["student", "parent"]:
        own = get_session_student(db, session) if session.sub_role == "student" else get_session_parent(db, session)
        if not own or own.id != student_id:
            raise HTTPException(status_code=403, detail="شما مجاز به دسترسی به اطلاعات مالی شخص دیگری نیستید (IDOR Protection)")
        return session.sub_role
        
    raise HTTPException(status_code=403, detail="دسترسی نامعتبر است")


# --- طرحواره‌های ورود اطلاعات (Pydantic Models) ---
class PaymentInitiateRequest(BaseModel):
    student_id: int
    amount: int = Field(gt=0)  # FIX: Bug 22 - reject non-positive amounts even while the gateway is disabled.
    target_wallet: str  # "teacher" یا "institute"
    enrollment_id: Optional[int] = None
    installment_id: Optional[int] = None
    description: Optional[str] = None
    gateway: Optional[str] = "zarinpal"

class InstallmentCreateRequest(BaseModel):
    enrollment_id: int
    amount: int = Field(gt=0)
    due_date: str  # FIX (F-T2): قالب + وجود تقویمی با validator مرکزی (نه فقط regex شکل)

    @field_validator("amount", mode="before")
    @classmethod
    def _validate_amount(cls, value):
        return validate_installment_amount(value)

    @field_validator("due_date")
    @classmethod
    def _validate_due_date(cls, value):
        return validate_jalali_due_date(value)

class InstallmentUpdateRequest(BaseModel):
    amount: Optional[int] = Field(default=None, gt=0)
    due_date: Optional[str] = None  # FIX (F-T2): ویرایش سررسید هم از همان قاعده‌ی تقویمی رد می‌شود
    is_paid: Optional[bool] = None

    @field_validator("amount", mode="before")
    @classmethod
    def _validate_amount(cls, value):
        if value is None:
            return None
        return validate_installment_amount(value)

    @field_validator("due_date")
    @classmethod
    def _validate_due_date(cls, value):
        if value is None:
            return None
        return validate_jalali_due_date(value)


# --- ۱. شروع فرآیند پرداخت آنلاین ---
@router.post("/finance/payment/initiate")
def initiate_online_payment(
    req: PaymentInitiateRequest,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    _role: str = Depends(check_user_login)
):
    # راستی‌آزمایی IDOR
    verify_financial_idor(req.student_id, authorization, db)
    
    raise HTTPException(
        status_code=400,
        detail="⚠️ پرداخت آنلاین در حال حاضر غیرفعال است (پرداخت آنلاین به‌زودی فعال خواهد شد). لطفا جهت پرداخت به صورت حضوری یا کارت به کارت اقدام فرمایید."
    )
    
    # TODO (audit-v2/#12): کد مرده‌ی زیر ۴۰۰ حذف شد (به payment/internal_id تعریف‌نشده ارجاع می‌داد —
    # NameError قطعی؛ اسکلت نبود، پوسیدگی بود). وقتی درگاه واقعی وصل شد، این تابع باید بازنویسی شود:
    #  ۱) ولیدیت (۴۰۰ این‌جا امن است چون هنوز پولی حرکت نکرده): amount>0 (همین حالا در اسکیما هست)،
    #     target_wallet ∈ {teacher, institute} (مثل M12)، enrollment_id/installment_id متعلق به همان شاگرد
    #     (درس closeout-3)، gateway از allowlist صریح (get_payment_gateway الان نام ناشناخته را ساکت به زرین‌پال می‌اندازد!).
    #  ۲) ساخت ردیف Payment با status=PENDING (+ internal_transaction_id یکتا) و capture شعبه (H7: شاگرد،
    #     وگرنه کلاسِ ثبت‌نام) تا کال‌بک هرگز رسید بدون‌شعبه نسازد (Bug-9).
    #  ۳) فراخوانی درگاه واقعی (ماژول payment_gateways.py الان Mock مستند است)، ذخیره‌ی authority روی ردیف
    #     PENDING، برگرداندن redirect_url.
    # FIX F-B1 (قرارداد initiate آینده با کال‌بک جدید — هنگام بازنویسی رعایت شود):
    #  ۴) ستون payment.gateway را از همان درگاه فراخوانی‌شده پر کن (کال‌بک با همان درگاه وریفای می‌کند؛
    #     خالی = پیش‌فرض زرین‌پال)؛ authority برگشتی را همان‌جا روی gateway_reference ذخیره کن (کال‌بک
    #     تطابق دقیق می‌خواهد و سطر بدون authority را 400 می‌دهد).
    #  ۵) claimed_at دست نزن (مال کال‌بک است)؛ status اولیه همیشه PENDING؛ internal_transaction_id یکتا.


# --- ۲ و ۳. کال‌بک / وب‌هووک درگاه پرداخت آنلاین (با قابلیت Idempotency کامل) ---
# --- FIX F-B1: صفحه‌های کمکی کال‌بک (بدون هیچ نوشتن/وریفای؛ فقط مسیریابی حالت) ---
def _callback_static_page(title: str, message: str, color: str):
    """نتیجه‌ی پایانیِ قبلاً ثبت‌شده (بازپخش) — ایستا، بدون رفرش خودکار."""
    return HTMLResponse(content=f"""
    <html>
    <head><title>{html.escape(title)}</title><meta charset="utf-8"></head>
    <body style="font-family: Tahoma; text-align: center; direction: rtl; padding-top: 50px; background-color: #f7f7f7;">
        <div style="border: 2px solid {color}; display: inline-block; padding: 30px; border-radius: 12px; background: white; width: 450px;">
            <h2 style="color: {color};">{html.escape(title)}</h2>
            <p>{html.escape(message)}</p>
        </div>
    </body>
    </html>
    """)


def _callback_refresh_page(payment_id: int):
    """تعارض گذرا (دیگری جلوتر وضعیت را برد) — رفرش خودکار، حالت تازه را نشان می‌دهد."""
    return HTMLResponse(content=f"""
    <html>
    <head><title>به‌روزرسانی وضعیت پرداخت</title><meta charset="utf-8"><meta http-equiv="refresh" content="3"></head>
    <body style="font-family: Tahoma; text-align: center; direction: rtl; padding-top: 50px; background-color: #f7f7f7;">
        <div style="border: 2px solid #007bff; display: inline-block; padding: 30px; border-radius: 12px; background: white; width: 450px;">
            <h2 style="color: #007bff;">وضعیت پرداخت در حال به‌روزرسانی است</h2>
            <p>پرداخت #{payment_id} هم‌زمان در حال پردازش است؛ چند لحظه دیگر به‌صورت خودکار تازه می‌شود.</p>
            <p><a href="">تلاش مجدد</a></p>
        </div>
    </body>
    </html>
    """)


def _callback_processing_page(payment_id: int):
    """VERIFYING تازه (دارنده‌ی دیگری در حال وریفای است) — صبر + رفرش خودکار، بدون وریفای دوم."""
    return HTMLResponse(content=f"""
    <html>
    <head><title>پرداخت در حال پردازش</title><meta charset="utf-8"><meta http-equiv="refresh" content="5"></head>
    <body style="font-family: Tahoma; text-align: center; direction: rtl; padding-top: 50px; background-color: #f7f7f7;">
        <div style="border: 2px solid #ffc107; display: inline-block; padding: 30px; border-radius: 12px; background: white; width: 450px;">
            <h2 style="color: #d39e00;">پرداخت در حال پردازش است</h2>
            <p>پرداخت #{payment_id} در درگاه در حال تایید نهایی است؛ لطفاً صبر کنید، این صفحه خودکار تازه می‌شود.</p>
            <p><a href="">تلاش مجدد</a></p>
        </div>
    </body>
    </html>
    """)


@router.get("/finance/payment/callback")
@limiter.limit("30/minute")  # FIX F-B1: کال‌بک پول بدون احراز است (ریدایرکت درگاه) — سقف ضد-Hammering؛ کاربر مشروع ۱-۳ هیت.
def payment_callback(
    request: Request,
    payment_id: int,
    status: str,
    gateway_ref: Optional[str] = None,
    db: Session = Depends(get_db)
):
    # TODO(security) (audit-v2/#12 + FIX F-B1): وضعیت بازنویسی کال‌بک:
    #  ۱) DONE: تطابق authority با ردیف PENDING (عدم‌تطابق → ۴۰۰ بدون تغییر وضعیت)؛
    #  ۲) OPEN: وریفای واقعی درگاه (امضا/استعلام) هنوز Mock است — اتصال درگاه واقعی + کلید merchant
    #     لازم دارد؛ تا آن زمان: فلگ پیش‌فرض خاموش + نگهبان ENV=production (fail-loud).
    #     نکته‌ی تک‌مصرف برای بازنویسی آینده: پاسخ «قبلاً وریفای‌شده» درگاه را موفقیت حساب کن، چون
    #     بازیابی تسخیر کهنه (کرش بین وریفای و ثبت نهایی) دوباره وریفای می‌زند و درگاهِ مصرف‌شده خطا می‌دهد!
    #  ۳) DONE: هرگز به status کوئری اعتماد نمی‌شود (فقط راهنمای انصراف؛ تنها منبع حقیقت کردیت = پاسخ وریفای)؛
    #  ۴) DONE: ماشین‌حالت اتمیک PENDING→VERIFYING→SUCCESS/FAILED (+CANCELLED) با UPDATE مشروط و بازیابی
    #     تسخیر کهنه (۱۰ دقیقه)؛ بازپخش روی وضعیت پایانی بدون وریفای مجدد.
    if not PAYMENT_GATEWAY_ENABLED:
        raise HTTPException(status_code=404, detail="درگاه پرداخت آنلاین غیرفعال است")
    # FIX F-B1: نگهبان پروداکشن — ماژول payment_gateways سراسر Mock است؛ حتی با فلگ روشن،
    # در پروداکشن fail-loud (500) نه mint ساکت. (factory هم مستقلاً همین گارد را دارد.)
    if os.getenv("ENV", "development").lower() == "production":
        raise HTTPException(status_code=500, detail="درگاه پرداخت آنلاین در پروداکشن پیکربندی نشده است")
    # FIX F-B1: بدون with_for_update (روی SQLite بی‌اثر است؛ گیت‌های واقعی، UPDATEهای مشروط پایین‌اند —
    # همان الگوی H8-P4). این خواندن فقط مسیریابی اولیه است؛ هر تصمیم با UPDATE مشروط بازتأیید می‌شود.
    payment = db.query(models.Payment).filter(models.Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="تراکنش آنلاین یافت نشد")

    # Idempotency: بازپخش روی وضعیت پایانی — همان نتیجه، بدون هیچ وریفای/نوشتن مجدد.
    # (وریفای واقعی تک‌مصرف است؛ FAILED قبلاً دوباره وارد وریفای می‌شد — دیگر نه.)
    # REFUNDED هم همان صفحه‌ی «از قبل ثبت شده» را می‌گیرد (پرداخت واقعاً ثبت شده بود).
    if payment.status in ("SUCCESS", "REFUNDED"):
        return HTMLResponse(content=f"""
        <html>
        <head>
            <title>تراکنش موفق</title>
            <meta charset="utf-8">
        </head>
        <body style="font-family: Tahoma; text-align: center; direction: rtl; padding-top: 50px; background-color: #f4fdf4;">
            <div style="border: 2px solid #28a745; display: inline-block; padding: 30px; border-radius: 12px; background: white; box-shadow: 0px 4px 12px rgba(0,0,0,0.05); width: 450px;">
                <h2 style="color: #28a745; margin-bottom: 20px;">تراکنش از قبل ثبت شده است</h2>
                <hr style="border: 0.5px solid #eee; margin-bottom: 20px;">
                <p>این پرداخت قبلاً با موفقیت پردازش و در سیستم ثبت شده است.</p>
                <p>شناسه رهگیری درگاه: <code>{payment.tracking_code}</code></p>
                <p>مبلغ پرداختی: <strong>{payment.amount:,} تومان</strong></p>
                <p style="color: #666; font-size: 0.9em; margin-top: 20px;">(رعایت قابلیت هم‌راستایی و عدم ثبت مجدد تراکنش تکراری)</p>
            </div>
        </body>
        </html>
        """)

    # FIX F-B1: بازپخش FAILED/CANCELLED دیگر وریفای مجدد نمی‌زند — فقط همان نتیجه‌ی پایانی.
    if payment.status == "FAILED":
        return _callback_static_page("پرداخت ناموفق", "این پرداخت قبلاً ناموفق ثبت شده و دوباره بررسی نمی‌شود.", "#dc3545")
    if payment.status == "CANCELLED":
        return _callback_static_page("پرداخت لغو شد", "این پرداخت قبلاً لغوشده ثبت شده است.", "#d39e00")

    # FIX F-B1: اتصال authority — شناسه‌ی برگشتی باید دقیقاً همان باشد که در initiate روی ردیف
    # PENDING ذخیره شده؛ وگرنه 400 بدون هیچ تغییر وضعیتی (fail-closed؛ جلوی enumeration با payment_id
    # تنها و دستکاری پرداخت دیگران). سطر بدون authority ذخیره‌شده هم بسته می‌ماند (initiate آینده همیشه ست می‌کند).
    if not gateway_ref or not payment.gateway_reference or gateway_ref != payment.gateway_reference:
        raise HTTPException(status_code=400, detail="شناسه‌ی درگاه با این پرداخت مطابقت ندارد")

    # FIX F-B1: ساخت درگاهِ همان‌مسیر (نه هاردکد زرین‌پال) — قبل از هر تسخیر؛ نام ناشناخته → 400.
    try:
        gateway = get_payment_gateway(payment.gateway or "zarinpal")
    except ValueError:
        raise HTTPException(status_code=400, detail="درگاه این پرداخت نامعتبر است")

    # FIX F-B1: status کوئری فقط «راهنما»ست نه «حقیقت» (OK/NOK همان قرارداد زرین‌پال واقعی است؛
    # Mock فعلی SUCCESS/FAILED می‌فرستد). تنها منبع حقیقتِ کردیت، پاسخ وریفای پایین است.
    if status.upper() in ("SUCCESS", "OK"):
        # FIX F-B1: تسخیر اتمیک PENDING→VERIFYING (الگوی H8-P4) — فقط یک کال‌بکِ هم‌زمان وارد وریفای
        # تک‌مصرف می‌شود؛ بازنده‌ها صفحه‌ی پردازش/رفرش می‌گیرند نه وریفای دوم.
        _claimed = (
            db.query(models.Payment)
            .filter(models.Payment.id == payment.id, models.Payment.status == "PENDING")
            .update({models.Payment.status: "VERIFYING", models.Payment.claimed_at: datetime.datetime.utcnow()}, synchronize_session=False)
        )
        db.commit()  # تسخیر قبل از فراخوان خارجی کامیت می‌شود (وریفای نگه‌داشتن تراکنش باز نمی‌خواهد).
        if _claimed != 1:
            # دیگری جلوتر است — یک خوانش تازه و مسیریابی بدون هیچ نوشتن/وریفای:
            payment = db.query(models.Payment).filter(models.Payment.id == payment_id).first()
            if payment is not None and payment.status == "VERIFYING":
                _stale_cutoff = datetime.datetime.utcnow() - datetime.timedelta(minutes=10)
                _stale = payment.claimed_at is not None and payment.claimed_at < _stale_cutoff
                _reclaimed = 0
                if _stale:
                    # بازیابی تسخیر گیرکرده (کرش بین تسخیر و ثبت نهایی) — فقط اگر واقعاً کهنه باشد:
                    _reclaimed = (
                        db.query(models.Payment)
                        .filter(models.Payment.id == payment.id, models.Payment.status == "VERIFYING", models.Payment.claimed_at < _stale_cutoff)
                        .update({models.Payment.claimed_at: datetime.datetime.utcnow()}, synchronize_session=False)
                    )
                    db.commit()
                if _stale and _reclaimed == 1:
                    pass  # حالا ما دارنده‌ایم — ادامه به وریفای پایین.
                else:
                    return _callback_processing_page(payment.id)  # تازه است یا مسابقه را باختیم — صبر + رفرش.
            else:
                return _callback_refresh_page(payment_id)  # پایانی شده — رفرش، همان نتیجه را نشان می‌دهد.
        # تایید رسمی صحت مبلغ تراکنش از درگاه — فقط با مقادیر ذخیره‌شده‌ی سرور (هرگز ورودی کوئری):
        verified_ok, trk_code = gateway.verify_payment(payment.gateway_reference, payment.amount)
        
        if verified_ok:
            # FIX F-B1: پیش‌شرط‌های فقط-خواندنی قبل از علامت SUCCESS — هر کدام نامعتبر بود، همان سرنوشت
            # M12 (FAILED مشروط + رد حسابرسی + همان صفحه‌ی خطا؛ پول درگاه وریفای شده پس 400 نه).
            _bad_reason = None
            if (payment.amount or 0) <= 0:
                _bad_reason = ("online_payment_invalid_amount", f"مبلغ نامعتبر «{payment.amount}» برای پرداخت وریفای‌شده #{payment.id} — شارژ نشد، مغایرت‌گیری دستی لازم است.")
            elif payment.target_wallet not in ("teacher", "institute"):
                _bad_reason = ("online_payment_invalid_wallet", f"کیف نامعتبر «{payment.target_wallet}» برای پرداخت وریفای‌شده #{payment.id} (مبلغ {payment.amount:,}) — شارژ نشد، مغایرت‌گیری دستی لازم است.")
            elif payment.student_id is None or db.query(Student.id).filter(Student.id == payment.student_id).first() is None:
                _bad_reason = ("online_payment_missing_student", f"شاگرد #{payment.student_id} پرداخت وریفای‌شده #{payment.id} یافت نشد (مبلغ {payment.amount:,}) — شارژ نشد، مغایرت‌گیری دستی لازم است.")
            if _bad_reason is not None:
                _bad_action, _bad_details = _bad_reason
                _brows = (
                    db.query(models.Payment)
                    .filter(models.Payment.id == payment.id, models.Payment.status == "VERIFYING")
                    .update({models.Payment.status: "FAILED"}, synchronize_session=False)
                )
                if _brows != 1:
                    db.rollback()
                    return _callback_refresh_page(payment.id)
                db.add(ActivityLog(
                    admin_username="online_payment_system",
                    action=_bad_action,
                    target_id=payment.id,
                    target_name="online_payment",
                    details=_bad_details,
                ))
                db.commit()
                return HTMLResponse(content=f"""
            <html>
            <head><title>خطای پردازش پرداخت</title><meta charset="utf-8"></head>
            <body style="font-family: Tahoma; text-align: center; direction: rtl; padding-top: 50px; background-color: #fdf4f4;">
                <div style="border: 2px solid #dc3545; display: inline-block; padding: 30px; border-radius: 12px; background: white; width: 450px;">
                    <h2 style="color: #dc3545;">خطای پردازش پرداخت</h2>
                    <p>پرداخت شما در درگاه تایید شد ولی به‌خاطر خطای سیستمی در حساب شما ثبت نشد.</p>
                    <p>لطفاً با پشتیبانی تماس بگیرید (شناسه پرداخت: <code>{payment.id}</code>)؛ مبلغ شما محفوظ است.</p>
                </div>
            </body>
            </html>
            """)
            # ۱. تغییر وضعیت رکورد تراکنش آنلاین به موفق — UPDATE مشروط (فقط دارنده‌ی VERIFYING).
            _srows = (
                db.query(models.Payment)
                .filter(models.Payment.id == payment.id, models.Payment.status == "VERIFYING")
                .update({models.Payment.status: "SUCCESS", models.Payment.tracking_code: trk_code, models.Payment.paid_at: datetime.datetime.utcnow()}, synchronize_session=False)
            )
            if _srows != 1:
                db.rollback()  # چیزی جز علامت (کامیت‌نشده) در تراکنش نیست — VERIFYING دست‌نخورده می‌ماند.
                return _callback_refresh_page(payment.id)
            db.refresh(payment)  # UPDATE خام آبجکت را stale کرد؛ ادامه با مقادیر تازه.

            # ۲. بروزرسانی کیف پول دانش‌آموز — افزایش اتمیک (نه RMW؛ دو پرداخت هم‌زمان یک شاگرد هم گم نمی‌شود).
            student = db.query(Student).filter(Student.id == payment.student_id).first()
            _wrows = 0
            if student is not None:
                _wcol = Student.wallet_teacher if payment.target_wallet == "teacher" else Student.wallet_institute
                _wrows = (
                    db.query(Student)
                    .filter(Student.id == payment.student_id)
                    .update({_wcol: func.coalesce(_wcol, 0) + payment.amount}, synchronize_session=False)
                )
            if student is None or _wrows != 1:
                # شاگرد بین پیش‌شرط و این‌جا حذف شد — پول هنوز هیچ‌جا نرفته: کل تراکنش rollback،
                # سپس FAILED مشروط + رد حسابرسی (همان سرنوشت M12).
                db.rollback()
                db.query(models.Payment).filter(models.Payment.id == payment.id, models.Payment.status == "VERIFYING").update({models.Payment.status: "FAILED"}, synchronize_session=False)
                db.add(ActivityLog(
                    admin_username="online_payment_system",
                    action="online_payment_missing_student",
                    target_id=payment.id,
                    target_name="online_payment",
                    details=f"شاگرد #{payment.student_id} پرداخت وریفای‌شده #{payment.id} حین ثبت حذف شده بود (مبلغ {payment.amount:,}) — شارژ نشد، مغایرت‌گیری دستی لازم است.",
                ))
                db.commit()
                return _callback_static_page("خطای پردازش پرداخت", f"پرداخت شما در درگاه تایید شد ولی به‌خاطر خطای سیستمی در حساب شما ثبت نشد. لطفاً با پشتیبانی تماس بگیرید (شناسه پرداخت: {payment.id})؛ مبلغ شما محفوظ است.", "#dc3545")
            db.refresh(student)  # افزایش خام را ببین تا بالانس درست همگام شود.
            if student:  # همیشه True (گیت بالا)؛ ساختار بلوک پایین حفظ می‌شود.
                # همگام‌سازی بالانس کل دانش‌آموز
                # FIX: Bug 18 - derive the total only through the shared wallet helper.
                student.sync_wallet_balance()
                
                # ۳. درج فیزیکی در جدول تراکنش‌ها (Transactions) جهت حفظ Traceability مالی کامل بدون حذف
                from dependencies import get_next_sequence_value
                if payment.target_wallet == "teacher":
                    next_remittance = get_next_sequence_value(db, "remittance_teacher", 100001)
                else:
                    next_remittance = get_next_sequence_value(db, "remittance_institute", 100001)

                # FIX (audit-v2/#12-Bug9): شعبه‌ی رسید — شاگرد اول، وگرنه کلاسِ ثبت‌نام لینک‌شده (الگوی H7).
                # اگر هیچ‌کدام نبود: پول وریفای‌شده را گرو نمی‌گیریم (خلاف M12 که پول نامعتبر بود، این‌جا فقط
                # متادیتا ناقص است) — رسید با branch=NULL ثبت + هشدار حسابرسی برای تخصیص دستی. initiate آینده
                # باید شعبه را همان‌جا capture و 400 بدهد (بخش ۲ TODO بالا).
                _cb_branch = student.branch_id
                if _cb_branch is None and payment.enrollment_id:
                    _cb_en = db.query(Enrollment).filter(Enrollment.id == payment.enrollment_id).first()
                    _cb_co = db.query(Course).filter(Course.id == _cb_en.course_id).first() if _cb_en is not None else None
                    _cb_branch = _cb_co.branch_id if _cb_co is not None else None
                if _cb_branch is None:
                    db.add(ActivityLog(
                        admin_username="online_payment_system",
                        action="online_payment_missing_branch",
                        target_id=payment.id,
                        target_name="online_payment",
                        details=f"شعبه‌ی پرداخت وریفای‌شده #{payment.id} (شاگرد #{payment.student_id}) قابل‌تشخیص نیست — رسید بدون‌شعبه ثبت شد، تخصیص دستی لازم است.",
                    ))

                new_trans = Transaction(
                    student_id=payment.student_id,
                    enrollment_id=payment.enrollment_id,
                    branch_id=_cb_branch,
                    amount=payment.amount,
                    payment_method="online",
                    tracking_code=trk_code,
                    date=_jalali_now_str(),  # FIX (audit-v2/#12-H3): شمسی (قبلاً میلادی وسط ستون شمسی).
                    description=f"پرداخت آنلاین موفق بابت {payment.description or 'شهریه'}",
                    type="deposit",
                    target_wallet=payment.target_wallet,
                    remittance_number=next_remittance,
                )
                db.add(new_trans)
                db.flush()  # دریافت آیدی تراکنش جدید

                # 🔗 همگام‌سازی منبع حقیقت بدهی (الگوی submit_payment): پرداخت لینک‌شده total_paid را زیاد می‌کند
                if payment.enrollment_id:
                    # FIX F-B1: افزایش اتمیک مشروط (مالکیت/حذف‌نشده در WHERE؛ نه RMW با قفل نمایشی).
                    _erows = (
                        db.query(Enrollment)
                        .filter(Enrollment.id == payment.enrollment_id, Enrollment.is_deleted == False, Enrollment.student_id == payment.student_id)
                        .update({Enrollment.total_paid: func.coalesce(Enrollment.total_paid, 0) + payment.amount}, synchronize_session=False)
                    )
                    if _erows != 1:
                        # ثبت‌نام هم‌زمان حذف/جابه‌جا شد — پول در کیف امن است؛ فقط لینک بدهی از دست رفت (قابل مغایرت‌گیری).
                        db.add(ActivityLog(
                            admin_username="online_payment_system",
                            action="online_payment_enroll_link_lost",
                            target_id=payment.id,
                            target_name="online_payment",
                            details=f"لینک بدهی پرداخت وریفای‌شده #{payment.id} (ثبت‌نام #{payment.enrollment_id}) حین ثبت از دست رفت — مبلغ {payment.amount:,} در کیف شاگرد #{payment.student_id} شارژ شد، تخصیص دستی لازم است.",
                        ))

                # ۴. تخصیص هوشمند به اقساط پرداخت نشده دانش‌آموز (اولویت با قسط خاص یا قدیمی‌ترین اقساط)
                _use_fallback = not payment.installment_id
                _target_ok = False
                if payment.installment_id:
                    # FIX: Bug 13 - exclude archived Installment rows from this active view.
                    target_inst = db.query(Installment).filter(Installment.is_deleted == False).filter(Installment.id == payment.installment_id).first()
                    if target_inst and not target_inst.is_paid:
                        # FIX (audit-v2/closeout-قدم۳): مالکیت نیت هدفمند — قسط باید متعلق به شاگردِ پرداخت
                        # (و اگر پرداخت لینک است، همان ثبت‌نام) باشد؛ وگرنه (دستکاری installment_id؟) نیت خنثی
                        # و fallback اعمال می‌شود + رد حسابرسی. عمداً 400 نمی‌دهیم: پول درگاه وریفای شده و
                        # rollback کامل، اعتبار مشروع را هم دور می‌ریخت (authority درگاه یک‌بارمصرف است!).
                        _towner = db.query(Enrollment).filter(Enrollment.id == target_inst.enrollment_id).first()
                        if _towner is not None and not _towner.is_deleted and _towner.student_id == payment.student_id and (not payment.enrollment_id or target_inst.enrollment_id == payment.enrollment_id):
                            _target_ok = True
                        else:
                            _use_fallback = True
                            db.add(ActivityLog(
                                admin_username="online_payment_system",
                                action="targeted_installment_mismatch",
                                target_id=payment.id,
                                target_name="online_payment",
                                details=f"نیت هدفمند نامعتبر خنثی شد: قسط #{target_inst.id} (ثبت‌نام #{target_inst.enrollment_id}) متعلق به شاگرد #{payment.student_id} / ثبت‌نام {payment.enrollment_id} نیست — fallback اعمال شد.",
                            ))
                    if _target_ok:
                        # FIX (audit-v2/issue7): تسویه‌ی هدفمند اتمیک + ledger — همان الگوی submit (قبلاً RMW
                        # غیراتمیک که پوشش موازی را گم می‌کرد). مبلغ ledger = سهم واقعی همین پرداخت (کامل −
                        # پوشش قبلی)؛ اگر قسط هم‌زمان تسویه شده بود، ledger نوشته نمی‌شود (پس استردادش قسط
                        # دیگری را باز نمی‌کند) و پول همان اعتبار عمومی می‌ماند — عمداً 409 نمی‌دهیم چون
                        # پرداخت درگاه وریفای شده است. paid_amount هم هرگز به پایین clamp نمی‌شود (حفظ تاریخچه).
                        for _try in range(10):
                            db.refresh(target_inst)
                            if target_inst.is_paid or target_inst.is_deleted:
                                break
                            _talready = target_inst.paid_amount or 0
                            _tfull = target_inst.amount or 0
                            _tset = {Installment.is_paid: True, Installment.paid_at: _jalali_now_str()}
                            if _tfull > _talready:
                                _tset[Installment.paid_amount] = _tfull
                            _trows = (
                                db.query(Installment)
                                .filter(Installment.id == target_inst.id, Installment.is_paid == False, Installment.is_deleted == False, func.coalesce(Installment.paid_amount, 0) == _talready)
                                .update(_tset, synchronize_session=False)
                            )
                            if _trows == 1:
                                if _tfull > _talready:
                                    db.add(TransactionInstallmentAllocation(transaction_id=new_trans.id, installment_id=target_inst.id, amount=_tfull - _talready))
                                break
                if _use_fallback:
                    # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
                    # FIX (audit-v2/issue9-الف): مثل submit — لینک‌شده فقط همان ثبت‌نام؛ بی‌لینک cross قدیمی.
                    if payment.enrollment_id:
                        enrollment_ids = [payment.enrollment_id]
                    else:
                        # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
                        enrollments = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.student_id == payment.student_id).all()
                        enrollment_ids = [e.id for e in enrollments]
                    if enrollment_ids:
                        unpaid_installments = (
                            # FIX: Bug 13 - exclude archived Installment rows from this active view.
                            db.query(Installment).filter(Installment.is_deleted == False)
                            .filter(
                                Installment.enrollment_id.in_(enrollment_ids),
                                Installment.is_paid == False
                            )
                            .order_by(Installment.due_date.asc())
                            .all()
                        )
                        remaining_payment = payment.amount
                        # FIX (audit-v2/issue7+9-قدم۳): همان الگوی UPDATE مشروط submit (قبلاً RMW غیراتمیک) +
                        # ledger روی تک‌رسید همین پرداخت (new_trans قبلاً flush شده و آیدی دارد).
                        # 409 در کال‌بک فقط همین پرداخت را rollback می‌کند (تک‌پرداخت در هر کال) — با توجه به
                        # TODO بازنویسی کال‌بک و غیرفعال‌بودن درگاه، قابل‌قبول.
                        for inst in unpaid_installments:
                            if remaining_payment <= 0:
                                break
                            for _try in range(10):
                                db.refresh(inst)
                                if inst.is_paid or inst.is_deleted:
                                    break
                                _already = inst.paid_amount or 0
                                _owed = (inst.amount or 0) - _already
                                if _owed <= 0:
                                    db.query(Installment).filter(Installment.id == inst.id, Installment.is_paid == False).update({Installment.is_paid: True}, synchronize_session=False)
                                    break
                                _cover = min(remaining_payment, _owed)
                                _new_paid = _already + _cover
                                _fully = _new_paid >= (inst.amount or 0)
                                _set = {Installment.paid_amount: _new_paid}
                                if _fully:
                                    _set[Installment.is_paid] = True
                                    _set[Installment.paid_at] = _jalali_now_str()
                                _rows = (
                                    db.query(Installment)
                                    .filter(Installment.id == inst.id, Installment.is_paid == False, Installment.is_deleted == False, func.coalesce(Installment.paid_amount, 0) == _already)
                                    .update(_set, synchronize_session=False)
                                )
                                if _rows == 1:
                                    remaining_payment -= _cover
                                    db.add(TransactionInstallmentAllocation(transaction_id=new_trans.id, installment_id=inst.id, amount=_cover))
                                    break
                            else:
                                # FIX F-B1: اتمام تلاش تخصیص دیگر rollback+409 نمی‌دهد (وریفای تک‌مصرف مصرف شده؛
                                # پول باید همان‌جا در کیف/رسید بنشیند). رد حسابرسی + ادامه به قسط بعدی.
                                db.add(ActivityLog(
                                    admin_username="online_payment_system",
                                    action="online_payment_alloc_deferred",
                                    target_id=payment.id,
                                    target_name="online_payment",
                                    details=f"تخصیص خودکار قسط #{inst.id} برای پرداخت وریفای‌شده #{payment.id} پس از تلاش ناموفق ماند — مبلغ در کیف/رسید ثبت شد، تخصیص دستی لازم است.",
                                ))
                                continue

                # ۵. ثبت لاگ حسابرسی (Audit Log) جهت تغییرات مبالغ
                db.add(ActivityLog(
                    admin_username="online_payment_system",
                    action="online_payment_success",
                    target_id=student.id,
                    target_name=display_name(student, "نامشخص"),
                    details=f"پرداخت آنلاین موفق به مبلغ {payment.amount:,} تومان به کیف پول {payment.target_wallet}. شماره تراکنش: {new_trans.id}"
                ))

                # ۶. ارسال نوتیفیکیشن‌های درون‌برنامه‌ای و پیامکی
                try:
                    today_str = _jalali_now_str()  # FIX (audit-v2/#12-H3): شمسی.
                    msg_sms = f"ولی محترم، پرداخت آنلاین بابت فرزند شما {display_name(student, 'دانش‌آموز')} به مبلغ {payment.amount:,} تومان با موفقیت انجام شد. کد پیگیری: {trk_code}"
                    db.add(SmsLog(
                        target_group=f"online_pay_{payment.id}",
                        message_text=msg_sms,
                        sent_count=1,
                        date=today_str
                    ))
                    
                    from dependencies import NotificationService, ensure_student_shadow_users
                    if student.user_id is None:
                        ensure_student_shadow_users(db, student)
                    # نوتیفیکیشن دانش‌آموز
                    NotificationService.send_notification(
                        db=db, recipient_user_id=student.user_id, recipient_role="student",
                        type="payment", title="✅ پرداخت آنلاین موفق",
                        body=f"پرداخت آنلاین شما به مبلغ {payment.amount:,} تومان با موفقیت ثبت شد. کد پیگیری: {trk_code}"
                    )
                    if student.parent_user_id is None:
                        ensure_student_shadow_users(db, student)
                    # نوتیفیکیشن ولی
                    NotificationService.send_notification(
                        db=db, recipient_user_id=student.parent_user_id, recipient_role="parent",
                        type="payment", title="✅ پرداخت آنلاین موفق فرزند",
                        body=f"پرداخت آنلاین بابت فرزند شما به مبلغ {payment.amount:,} تومان با موفقیت انجام شد. کد پیگیری: {trk_code}"
                    )
                except Exception:
                    pass

            db.commit()
            return HTMLResponse(content=f"""
            <html>
            <head>
                <title>پرداخت موفقیت‌آمیز</title>
                <meta charset="utf-8">
            </head>
            <body style="font-family: Tahoma; text-align: center; direction: rtl; padding-top: 50px; background-color: #f4fdf4;">
                <div style="border: 2px solid #28a745; display: inline-block; padding: 30px; border-radius: 12px; background: white; box-shadow: 0px 4px 12px rgba(0,0,0,0.05); width: 450px;">
                    <div style="font-size: 50px; color: #28a745; margin-bottom: 10px;">✓</div>
                    <h2 style="color: #28a745; margin-bottom: 20px;">پرداخت شما با موفقیت انجام شد</h2>
                    <hr style="border: 0.5px solid #eee; margin-bottom: 20px;">
                    <p>دانش‌آموز گرامی، تراکنش مالی شما تایید شد.</p>
                    <p>کد پیگیری تراکنش: <code>{trk_code}</code></p>
                    <p>مبلغ پرداختی: <strong>{payment.amount:,} تومان</strong></p>
                    <p style="color: #666; font-size: 0.9em; margin-top: 20px;">کیف پول شما بروزرسانی شد و این رسید به عنوان حواله در سیستم ثبت گردید.</p>
                </div>
            </body>
            </html>
            """)
        else:
            # FIX F-B1: FAILED مشروط (فقط دارنده‌ی VERIFYING) — اگر دیگری جلوتر وضعیت را برده، رفرش.
            _ffrows = (
                db.query(models.Payment)
                .filter(models.Payment.id == payment.id, models.Payment.status == "VERIFYING")
                .update({models.Payment.status: "FAILED"}, synchronize_session=False)
            )
            db.commit()
            if _ffrows != 1:
                return _callback_refresh_page(payment.id)
            return HTMLResponse(content="""
            <html>
            <head>
                <title>پرداخت ناموفق</title>
                <meta charset="utf-8">
            </head>
            <body style="font-family: Tahoma; text-align: center; direction: rtl; padding-top: 50px; background-color: #fdf4f4;">
                <div style="border: 2px solid #dc3545; display: inline-block; padding: 30px; border-radius: 12px; background: white; box-shadow: 0px 4px 12px rgba(0,0,0,0.05); width: 450px;">
                    <div style="font-size: 50px; color: #dc3545; margin-bottom: 10px;">✗</div>
                    <h2 style="color: #dc3545; margin-bottom: 20px;">پرداخت ناموفق بود</h2>
                    <hr style="border: 0.5px solid #eee; margin-bottom: 20px;">
                    <p style="color: #dc3545; font-weight: bold;">تراکنش توسط درگاه بانک معتبر شناخته نشد.</p>
                    <p>در صورتی که مبلغی از حساب شما کسر شده باشد، تا ۷۲ ساعت آینده به حساب شما بازخواهد گشت.</p>
                </div>
            </body>
            </html>
            """)
    else:
        # FIX F-B1: انصراف/شکست سمت درگاه → CANCELLED مشروط (فقط از PENDING؛ SUCCESS/VERIFYING هرگز
        # با هیت لغو رونویسی نمی‌شود). اگر دیگری جلوتر برده، رفرش همان نتیجه را نشان می‌دهد.
        _crows = (
            db.query(models.Payment)
            .filter(models.Payment.id == payment.id, models.Payment.status == "PENDING")
            .update({models.Payment.status: "CANCELLED"}, synchronize_session=False)
        )
        db.commit()
        if _crows != 1:
            return _callback_refresh_page(payment.id)
        return HTMLResponse(content="""
        <html>
        <head>
            <title>پرداخت لغو شد</title>
            <meta charset="utf-8">
        </head>
        <body style="font-family: Tahoma; text-align: center; direction: rtl; padding-top: 50px; background-color: #fdfbf4;">
            <div style="border: 2px solid #ffc107; display: inline-block; padding: 30px; border-radius: 12px; background: white; box-shadow: 0px 4px 12px rgba(0,0,0,0.05); width: 450px;">
                <div style="font-size: 50px; color: #ffc107; margin-bottom: 10px;">!</div>
                <h2 style="color: #d39e00; margin-bottom: 20px;">پرداخت لغو گردید</h2>
                <hr style="border: 0.5px solid #eee; margin-bottom: 20px;">
                <p>عملیات پرداخت آنلاین توسط شما لغو شد یا با شکست مواجه گردید.</p>
                <p>در صورت تمایل می‌توانید مجدداً از طریق پورتال خود برای پرداخت اقدام فرمایید.</p>
            </div>
        </body>
        </html>
        """)


# --- ۴ و ۵. صفحه درگاه پرداخت شبیه‌سازی شده ---
@router.get("/finance/mock_payment_page")
def mock_payment_page(
    gateway: str,
    authority: str,
    amount: int,
    callback: str
):
    # TODO(security): شبیه‌ساز موقت است؛ با اتصال درگاه واقعی بانکی باید حذف شود.
    if not PAYMENT_GATEWAY_ENABLED:
        raise HTTPException(status_code=404, detail="درگاه پرداخت آنلاین غیرفعال است")
    # FIX(XSS): escape مقادیر بازتابی قبل از قرار دادن در HTML (حتی وقتی فلگ خاموش است، بی‌ضرر است).
    safe_gateway = html.escape(gateway.upper())
    safe_authority = html.escape(authority)
    safe_callback = html.escape(callback)
    html_content = f"""
    <html>
    <head>
        <title>شبیه‌ساز درگاه پرداخت {safe_gateway}</title>
        <meta charset="utf-8">
    </head>
    <body style="font-family: Tahoma; text-align: center; direction: rtl; padding-top: 50px; background-color: #f7f7f7;">
        <div style="border: 1px solid #ccc; display: inline-block; padding: 30px; border-radius: 10px; background: white; box-shadow: 0px 4px 10px rgba(0,0,0,0.1); width: 400px;">
            <h2>شبیه‌ساز درگاه پرداخت {safe_gateway}</h2>
            <hr style="border: 0.5px solid #eee; margin-bottom: 20px;">
            <p>مبلغ تراکنش: <strong style="color: #007bff; font-size: 1.2em;">{amount:,} تومان</strong></p>
            <p>شناسه درگاه: <code>{safe_authority}</code></p>
            <div style="margin-top: 30px; display: flex; justify-content: space-around;">
                <a href="{safe_callback}&status=SUCCESS&gateway_ref={safe_authority}" style="background-color: #28a745; color: white; padding: 12px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">پرداخت موفق (Success)</a>
                <a href="{safe_callback}&status=FAILED&gateway_ref={safe_authority}" style="background-color: #dc3545; color: white; padding: 12px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">انصراف / خطا (Fail)</a>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


# --- ۶. استرداد وجه و برگشت دادن تراکنش‌ها (Refund / Reversal) ---
# به جای حذف فیزیکی رکوردها (Traceability کامل) تراکنش برگشتی صادر و بالانس اصلاح می‌شود.
@router.post("/finance/transaction/{transaction_id}/refund")
def refund_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    _: str = Depends(check_admin_access)  # فقط مخصوص ادمین
):
    # FIX: Bug 11 - this audit lookup deliberately includes reversed rows to reject repeat refunds.
    # FIX B2 (الگوی H8-P4): بدون with_for_update — این خواندن فقط اعتبارسنجی اولیه است؛ گیت واقعی، UPDATE مشروط پایین است.
    trans = db.query(Transaction).filter(Transaction.id == transaction_id, Transaction.is_deleted == False).first()
    if not trans:
        raise HTTPException(status_code=404, detail="تراکنش مورد نظر یافت نشد")
    # FIX M16: فقط واریز واقعی از مسیر استرداد عمومی برمی‌گردد — قبل از تسخیر اتمیک، پس چیزی ثبت نمی‌شود.
    # session_charge مسیر مخصوص خودش را دارد (reverse_session_financial_impacts هنگام حذف جلسه)؛
    # استرداد عمومی آن هم کیف را دست‌نخورده می‌گذاشت، هم is_reversed را می‌سوزاند (مسیر درست را برای همیشه می‌بست).
    # settlement_payout پول‌خروجی و reversal معکوس است و استرداد عمومی برایشان بی‌معناست.
    if trans.type not in ("deposit", "enrollment_payment"):
        _m16_hint = "؛ برگشت هزینه‌ی جلسه فقط با حذف جلسه انجام می‌شود" if trans.type == "session_charge" else ""
        raise HTTPException(status_code=400, detail=f"تراکنش نوع «{trans.type}» از مسیر استرداد عمومی قابل برگشت نیست{_m16_hint}")
        
    if trans.is_reversed:
        raise HTTPException(status_code=400, detail="این تراکنش قبلاً استرداد شده است (Idempotent Refund)")
        
    # فریز مبلغ در لحظه‌ی اعتبارسنجی (آبجکت ORM بعد از UPDATE خام، در فیلد is_reversed stale می‌شود).
    t_amount = trans.amount

    # FIX B2 (الگوی H8-P4): تسخیر اتمیک تراکنش — فقط اگر هنوز استردادنشده و حذف‌نشده باشد فلیپ می‌خورد.
    # ۱. علامت‌گذاری تراکنش اصلی به عنوان بازگردانده شده
    claimed_rows = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id, Transaction.is_reversed == False, Transaction.is_deleted == False)
        .update({Transaction.is_reversed: True}, synchronize_session=False)
    )
    if claimed_rows != 1:
        db.rollback()
        raise HTTPException(status_code=400, detail="این تراکنش قبلاً استرداد شده است (Idempotent Refund)")
    
    # FIX: Bug 11 - issue a new reference, including protection against pre-counter legacy numbers.
    from dependencies import get_next_sequence_value
    # FIX: Bug 11 - initialize above historical references, including archived transactions.
    first_refund_number = max(100000, db.query(func.max(Transaction.remittance_number)).scalar() or 0) + 1
    # FIX: Bug 11 - share the wallet's counter so its next deposit cannot reuse the refund reference.
    counter_name = "remittance_teacher" if trans.target_wallet == "teacher" else "remittance_institute"
    next_remittance = get_next_sequence_value(db, counter_name, first_refund_number)
    # FIX: Bug 11 - reference uniqueness must consider archived/reversed rows, not just active revenue.
    while db.query(Transaction.id).filter(Transaction.remittance_number == next_remittance).first():
        next_remittance = get_next_sequence_value(db, counter_name, first_refund_number)

    # ۲. ثبت یک تراکنش معکوس (با مقدار منفی) جهت حفظ تاریخچه کامل
    reversal_trans = Transaction(
        student_id=trans.student_id,
        enrollment_id=trans.enrollment_id,
        # FIX: Bug 11 - preserve the original branch/course/session audit links on the reversal.
        branch_id=trans.branch_id,
        course_id=trans.course_id,
        session_id=trans.session_id,
        amount=-trans.amount,
        payment_method=trans.payment_method,
        tracking_code=f"REFUND_{trans.tracking_code or trans.id}",
        date=_jalali_now_str(),  # FIX (audit-v2/refund-date): شمسی (قبلاً میلادی وسط ستون شمسی — همان الگوی L7/#12).
        description=f"استرداد تراکنش شماره #{trans.id} - شرح قبلی: {trans.description}",
        type="reversal",
        target_wallet=trans.target_wallet,
        remittance_number=next_remittance  # FIX: Bug 11 - never reuse the original reference.
    )
    db.add(reversal_trans)
    
    # ۳. کسر مبلغ استرداد شده از کیف پول دانش‌آموز
    # FIX B2: بدون with_for_update — فقط خواندن برای وجودسنجی/نام؛ کسر با UPDATE اتمیک پایین است.
    student = db.query(Student).filter(Student.id == trans.student_id).first()
    if student:
        # FIX B2: بدون خواندن-جمع‌زدن در پایتون — اینجا فقط سهم کسر هر کیف‌پول محاسبه می‌شود.
        sub_teacher = 0
        sub_institute = 0
        if trans.target_wallet == "teacher":
            sub_teacher = t_amount
        elif trans.target_wallet == "institute":
            sub_institute = t_amount
        elif trans.target_wallet == "both":
            # FIX: Bugs 10/11 - legacy combined receipts must reverse both actual wallet shares.
            teacher_amount = trans.share_teacher or 0
            institute_amount = trans.share_institute or 0
            if teacher_amount + institute_amount != trans.amount:
                teacher_amount = trans.amount // 2
                institute_amount = trans.amount - teacher_amount
            sub_teacher = teacher_amount
            sub_institute = institute_amount
        elif trans.type == "enrollment_payment":
            # FIX M16: واریز ثبت‌نامی همیشه به کیف آموزشگاه رفته (هر دو سایت ساخت) ولی target_wallet=None دارد —
            # بدون این شاخه، استردادش تراکنش معکوس ثبت می‌کرد ولی کیف را دست‌نخورده می‌گذاشت (همان تله‌ی session_charge).
            sub_institute = t_amount
        # (شاخه‌ی else قدیمی سهمی کسر نمی‌کرد؛ مثل الگوی بچ ۱، بدون UPDATE و بدون سینک رد می‌شود.)

        # FIX B2 (الگوی H8-P4): کسر اتمیک از کیف‌پول‌ها در SQL — منها در دیتابیس، نه خواندن-منها در پایتون.
        # COALESCE رفتار قدیمی None→0 را حفظ می‌کند (ستون‌ها nullable هستند)؛ rowcount باید ۱ باشد (فقط existence).
        if sub_teacher or sub_institute:
            wallet_rows = (
                db.query(Student)
                .filter(Student.id == trans.student_id)
                .update(
                    {
                        Student.wallet_teacher: func.coalesce(Student.wallet_teacher, 0) - sub_teacher,
                        Student.wallet_institute: func.coalesce(Student.wallet_institute, 0) - sub_institute,
                    },
                    synchronize_session=False,
                )
            )
            if wallet_rows != 1:
                db.rollback()
                raise HTTPException(status_code=404, detail="دانش‌آموز یافت نشد")

        # ترتیب سینک (مثل بچ ۱): اول UPDATE خام، بعد refresh برای مقادیر تازه، بعد سینک بالانس کل.
        if sub_teacher or sub_institute:
            db.refresh(student)
            # FIX: Bug 18 - derive the total only through the shared wallet helper.
            student.sync_wallet_balance()
            
        # 🔗 همگام‌سازی منبع حقیقت بدهی: استردادِ پرداختِ لینک‌شده، total_paid ثبت‌نام را کم می‌کند
        if trans.enrollment_id and trans.type in ("deposit", "enrollment_payment", "tuition") and (trans.amount or 0) > 0:
            # FIX B2 (الگوی H8-P4): کسر اتمیک با کف صفر (همان max(0,...) قبلی، به‌صورت CASE اتمیک در SQL).
            # مثل رفتار قبلی (if تأییدی)، rowcount صفر (ثبت‌نام حذف‌شده/نبود) بی‌صدا رد می‌شود — چون اینجا
            # برخلاف submit_payment، ثبت‌نام از قبل اعتبارسنجی نشده و نبودش خطا نیست.
            db.query(Enrollment).filter(
                Enrollment.id == trans.enrollment_id, Enrollment.is_deleted == False
            ).update(
                {
                    Enrollment.total_paid: case(
                        (func.coalesce(Enrollment.total_paid, 0) - t_amount < 0, 0),
                        else_=func.coalesce(Enrollment.total_paid, 0) - t_amount,
                    )
                },
                synchronize_session=False,
            )

        # FIX (audit-v2/issue7): برگرداندن پوشش‌های اقساط از روی ledger — در همان تراکنش دیتابیسی،
        # اتمیک با کیف/total_paid (کامیت واحد انتهای تابع). فقط پوشش‌های همین رسید برمی‌گردند؛
        # ردیف‌های ledger نگه داشته می‌شوند (تاریخچه) و استرداد تکراری با گیت is_reversed ناممکن است.
        # تاریخچه‌ی قبل-از-ledger ردیفی ندارد → همان رفتار امروز (قسط دست‌نخورده).
        _allocs = db.query(TransactionInstallmentAllocation).filter(TransactionInstallmentAllocation.transaction_id == transaction_id).order_by(TransactionInstallmentAllocation.id.asc()).all()
        for _al in _allocs:
            for _try in range(3):
                _rinst = db.query(Installment).filter(Installment.id == _al.installment_id, Installment.is_deleted == False).first()
                if _rinst is None:
                    break  # قسط آرشیو/حذف شده — پوشش عملاً بی‌اثر است.
                _ralready = _rinst.paid_amount or 0
                _rnew = max(0, _ralready - (_al.amount or 0))
                _rstill = _rnew >= (_rinst.amount or 0)
                _rrows = (
                    db.query(Installment)
                    .filter(Installment.id == _rinst.id, Installment.is_deleted == False, func.coalesce(Installment.paid_amount, 0) == _ralready)
                    .update({Installment.paid_amount: _rnew, Installment.is_paid: _rstill, Installment.paid_at: (_rinst.paid_at if _rstill else None)}, synchronize_session=False)
                )
                if _rrows == 1:
                    break
            else:
                db.rollback()
                raise HTTPException(status_code=409, detail="تغییر هم‌زمان در اقساط؛ لطفاً دوباره تلاش کنید")

        # ۴. ثبت فعالیت حسابرسی (Audit Log) تغییر مبلغ
        # FIX H9: admin_username باید کاربر واقعی همین درخواست باشد، نه هاردکد "admin_portal".
        # همان الگوی H8-P2؛ چون check_* بالا توکن خراب را از قبل رد کرده، فالبک "unknown"
        # عملاً نباید هیچ‌وقت اجرا شود (فقط safety net).
        from dependencies import get_session_from_token  # lazy، مثل H8
        _audit_username = "unknown"
        if authorization:
            try:
                _parts = authorization.split()
                _token = _parts[1] if len(_parts) == 2 and _parts[0].lower() == "bearer" else None
                _sess, _ = get_session_from_token(db, _token) if _token else (None, None)
                if _sess is not None and getattr(_sess, "user_id", None):
                    _audit_user = db.query(User).filter(User.id == _sess.user_id).first()
                    if _audit_user is not None and _audit_user.username:
                        _audit_username = _audit_user.username
            except Exception:
                pass
        db.add(ActivityLog(
            admin_username=_audit_username,
            action="transaction_refund",
            target_id=student.id,
            target_name=display_name(student, "نامشخص"),
            details=f"استرداد تراکنش #{trans.id} به مبلغ {trans.amount:,} تومان و کسر از کیف پول {trans.target_wallet}."
        ))
        
    db.commit()
    return {
        "status": "success",
        "message": "تراکنش مالی با موفقیت استرداد و کیف پول مربوطه کسر گردید.",
        "refund_transaction_id": reversal_trans.id
    }


# --- ۷. مدیریت اقساط شهریه (Installment Management) ---

# دریافت اقساط شهریه (ادمین / منشی)
@router.get("/finance/installments")
def get_all_installments(
    enrollment_id: Optional[int] = None,
    student_id: Optional[int] = None,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    sub_role: str = Depends(check_user_login)
):
    # FIX (audit-v2/#11): IDOR خواندن — ادمین/منشی همه؛ شاگرد/ولی فقط محدوده‌ی خود (قبلاً بدون فیلتر،
    # همه‌ی اقساط همه برمی‌گشت). اپ این اندپوینت را صدا نمی‌زند (پورتال‌ها از پروفایل می‌خوانند) پس شکستن ندارد.
    if sub_role not in ("admin", "secretary"):
        if sub_role not in ("student", "parent"):
            raise HTTPException(status_code=403, detail="شما مجاز به مشاهده اقساط نیستید")
        _parts = (authorization or "").split()
        _tok = _parts[1] if len(_parts) == 2 and _parts[0].lower() == "bearer" else None
        _sess = db.query(UserSession).filter(UserSession.token == _tok).first() if _tok else None
        _own = get_session_student(db, _sess) if sub_role == "student" else get_session_parent(db, _sess)
        if not _own:
            raise HTTPException(status_code=401, detail="نشست معتبر نیست؛ لطفاً دوباره وارد شوید")
        if enrollment_id:
            _en = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.id == enrollment_id).first()
            if not _en:
                raise HTTPException(status_code=404, detail="ثبت‌نام دانش‌آموز یافت نشد")
            if _en.student_id != _own.id:
                raise HTTPException(status_code=403, detail="شما مجاز به مشاهده اقساط این ثبت‌نام نیستید")
        elif student_id:
            if student_id != _own.id:
                raise HTTPException(status_code=403, detail="شما مجاز به مشاهده اقساط این دانش‌آموز نیستید")
        else:
            student_id = _own.id
    # FIX: Bug 13 - exclude archived Installment rows from this active view.
    query = db.query(Installment).filter(Installment.is_deleted == False)
    if enrollment_id:
        query = query.filter(Installment.enrollment_id == enrollment_id)
    elif student_id:
        # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
        enroll_ids = [e.id for e in db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.student_id == student_id).all()]
        query = query.filter(Installment.enrollment_id.in_(enroll_ids))
        
    installments = query.order_by(Installment.due_date.asc()).all()
    result = []
    for inst in installments:
        # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
        enroll = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.id == inst.enrollment_id).first()
        course = db.query(Course).filter(Course.id == enroll.course_id).first() if enroll else None
        c_title = course.title if course else "کلاس حذف شده"
        result.append({
            "id": inst.id,
            "enrollment_id": inst.enrollment_id,
            "course_title": c_title,
            "amount": inst.amount,
            "due_date": inst.due_date,
            "is_paid": inst.is_paid,
            "paid_at": inst.paid_at or "---"
        })
    return result

# ایجاد قسط شهریه جدید (ادمین / منشی)
@router.post("/finance/installments")
def create_installment(
    req: InstallmentCreateRequest,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    _: str = Depends(check_admin_or_secretary_access)
):
    # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
    enroll = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.id == req.enrollment_id).first()
    if not enroll:
        raise HTTPException(status_code=404, detail="ثبت‌نام دانش‌آموز یافت نشد")
        
    new_inst = Installment(
        enrollment_id=req.enrollment_id,
        amount=req.amount,
        due_date=req.due_date,
        is_paid=False
    )
    db.add(new_inst)
    # FIX (F-C3): تک‌کامیت — flush برای id کافی است؛ کامیت واحد انتهای تابع (با لاگ حسابرسی).
    db.flush()
    db.refresh(new_inst)
    
    # لاگ حسابرسی
    # FIX H9: admin_username باید کاربر واقعی همین درخواست باشد، نه هاردکد "admin_portal".
    # همان الگوی H8-P2؛ چون check_* بالا توکن خراب را از قبل رد کرده، فالبک "unknown"
    # عملاً نباید هیچ‌وقت اجرا شود (فقط safety net).
    from dependencies import get_session_from_token  # lazy، مثل H8
    _audit_username = "unknown"
    if authorization:
        try:
            _parts = authorization.split()
            _token = _parts[1] if len(_parts) == 2 and _parts[0].lower() == "bearer" else None
            _sess, _ = get_session_from_token(db, _token) if _token else (None, None)
            if _sess is not None and getattr(_sess, "user_id", None):
                _audit_user = db.query(User).filter(User.id == _sess.user_id).first()
                if _audit_user is not None and _audit_user.username:
                    _audit_username = _audit_user.username
        except Exception:
            pass
    db.add(ActivityLog(
        admin_username=_audit_username,
        action="create_installment",
        target_id=new_inst.id,
        target_name="installment",
        details=f"ایجاد قسط جدید به مبلغ {req.amount:,} تومان با سررسید {req.due_date}."
    ))
    db.commit()
    
    return {"message": "قسط شهریه با موفقیت ایجاد شد", "installment_id": new_inst.id}

# ویرایش قسط شهریه (ادمین / منشی) همراه با Audit دقیق تغییر مبلغ
@router.put("/finance/installments/{installment_id}")
def update_installment(
    installment_id: int,
    req: InstallmentUpdateRequest,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    force: bool = False,
    reason: Optional[str] = None,
    _: str = Depends(check_admin_or_secretary_access)
):
    # FIX: Bug 13 - exclude archived Installment rows from this active view.
    inst = db.query(Installment).filter(Installment.is_deleted == False).filter(Installment.id == installment_id).with_for_update().first()
    if not inst:
        raise HTTPException(status_code=404, detail="قسط یافت نشد")
        
    old_amount = inst.amount
    
    # FIX M10: مبلغ قسط تسویه‌شده قفل است — تغییر فقط با force صریح + دلیل.
    if inst.is_paid and req.amount is not None and req.amount != old_amount:
        if not force:
            raise HTTPException(status_code=409, detail="مبلغ قسط تسویه‌شده قفل است؛ برای تغییر، force=true همراه با دلیل بدهید")
        if not (reason and reason.strip()):
            raise HTTPException(status_code=400, detail="تغییر مبلغ قسط تسویه‌شده بدون دلیل مجاز نیست؛ reason بدهید")
    if req.amount is not None:
        # 🛡️ بررسی و ممیزی اجباری تغییر مبالغ
        if req.amount != old_amount:
            # FIX H9: admin_username باید کاربر واقعی همین درخواست باشد، نه هاردکد "admin_portal".
            # همان الگوی H8-P2؛ چون check_* بالا توکن خراب را از قبل رد کرده، فالبک "unknown"
            # عملاً نباید هیچ‌وقت اجرا شود (فقط safety net).
            from dependencies import get_session_from_token  # lazy، مثل H8
            _audit_username = "unknown"
            if authorization:
                try:
                    _parts = authorization.split()
                    _token = _parts[1] if len(_parts) == 2 and _parts[0].lower() == "bearer" else None
                    _sess, _ = get_session_from_token(db, _token) if _token else (None, None)
                    if _sess is not None and getattr(_sess, "user_id", None):
                        _audit_user = db.query(User).filter(User.id == _sess.user_id).first()
                        if _audit_user is not None and _audit_user.username:
                            _audit_username = _audit_user.username
                except Exception:
                    pass
            db.add(ActivityLog(
                admin_username=_audit_username,
                action="update_installment_amount",
                target_id=inst.id,
                target_name="installment",
                details=f"تغییر مبلغ قسط #{inst.id} از {old_amount:,} به {req.amount:,} تومان." + (f" [force روی قسط تسویه‌شده: {reason.strip()}]" if inst.is_paid else "")
            ))
        inst.amount = req.amount
        
    if req.due_date is not None:
        inst.due_date = req.due_date
        
    if req.is_paid is not None:
        inst.is_paid = req.is_paid
        if req.is_paid:
            inst.paid_at = _jalali_now_str()  # FIX L7: شمسی.
            inst.paid_amount = inst.amount  # FIX M13: مارک تسویه‌ی دستی یعنی پوشش کامل.
        # FIX M10 (تصمیم گزارش اولیه): برگرداندن تسویه، تاریخ پرداخت واقعی را پاک نمی‌کند —
        # paid_at سند تاریخی دریافت وجه است، نه وضعیت فعلی.
            
    db.commit()
    return {"message": "قسط شهریه با موفقیت بروزرسانی شد"}

# حذف قسط شهریه (ادمین / منشی) همراه با Audit
@router.delete("/finance/installments/{installment_id}")
def delete_installment(
    installment_id: int,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    force: bool = False,
    _: str = Depends(check_admin_or_secretary_access)
):
    # FIX: Bug 13 - exclude archived Installment rows from this active view.
    inst = db.query(Installment).filter(Installment.is_deleted == False).filter(Installment.id == installment_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="قسط یافت نشد")
        
    # FIX H9: admin_username باید کاربر واقعی همین درخواست باشد، نه هاردکد "admin_portal".
    # همان الگوی H8-P2؛ چون check_* بالا توکن خراب را از قبل رد کرده، فالبک "unknown"
    # عملاً نباید هیچ‌وقت اجرا شود (فقط safety net).
    from dependencies import get_session_from_token  # lazy، مثل H8
    _audit_username = "unknown"
    if authorization:
        try:
            _parts = authorization.split()
            _token = _parts[1] if len(_parts) == 2 and _parts[0].lower() == "bearer" else None
            _sess, _ = get_session_from_token(db, _token) if _token else (None, None)
            if _sess is not None and getattr(_sess, "user_id", None):
                _audit_user = db.query(User).filter(User.id == _sess.user_id).first()
                if _audit_user is not None and _audit_user.username:
                    _audit_username = _audit_user.username
        except Exception:
            pass
    # FIX M15: قسط تسویه‌شده بدون force صریح حذف نمی‌شود (پول واقعی پشت آن است).
    if inst.is_paid and not force:
        raise HTTPException(status_code=409, detail="قسط تسویه‌شده قابل حذف نیست؛ برای حذف force=true بدهید")
    db.add(ActivityLog(
        admin_username=_audit_username,
        action="delete_installment",
        target_id=inst.id,
        target_name="installment",
        details=f"حذف قسط #{inst.id} به مبلغ {inst.amount:,} تومان سررسید {inst.due_date}." + (" [force روی قسط تسویه‌شده]" if inst.is_paid else "")
    ))
    # FIX M15 (الگوی H11): حذف منطقی، نه فیزیکی — سابقه‌ی مالی هرگز از دیتابیس پاک نمی‌شود.
    inst.is_deleted = True
    db.commit()
    return {"message": "قسط شهریه با موفقیت حذف گردید"}

# تسویه دستی قسط شهریه از طریق ادمین/منشی (با ثبت تراکنش واقعی)
@router.post("/finance/installments/{installment_id}/pay")
def pay_installment_manually(
    installment_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_or_secretary_access),
    branch_id: Optional[int] = None,
    payment_method: Optional[str] = "نقدی",
    authorization: Optional[str] = Header(None)
):
    # FIX: Bug 13 - exclude archived Installment rows from this active view.
    # FIX B1: بدون with_for_update — این خواندن فقط اعتبارسنجی اولیه است؛ گیت واقعی، UPDATE مشروط پایین است.
    inst = db.query(Installment).filter(Installment.is_deleted == False).filter(Installment.id == installment_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="قسط یافت نشد")
    if inst.is_paid:
        raise HTTPException(status_code=400, detail="این قسط قبلاً تسویه شده است")
    if inst.amount is None or inst.amount <= 0:
        raise HTTPException(status_code=400, detail="مبلغ قسط معتبر نیست")

    # ثبت‌نام و دانش‌آموز مربوط به قسط (فقط خواندن برای اعتبارسنجی؛ نوشتن‌ها با UPDATE اتمیک پایین است)
    enroll = db.query(Enrollment).filter(Enrollment.id == inst.enrollment_id).first()
    if not enroll or enroll.is_deleted:
        raise HTTPException(status_code=404, detail="ثبت‌نام مربوط به این قسط یافت نشد")
    student = db.query(Student).filter(Student.id == enroll.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="دانش‌آموز مربوط به این قسط یافت نشد")

    # تعیین شعبه با همان الگوی submit_payment: شعبه شاگرد، وگرنه شعبه کاربر/پارامتر
    payment_branch = student.branch_id if student.branch_id is not None else get_user_branch_filter(db, authorization, branch_id)
    if payment_branch is None:
        raise HTTPException(status_code=400, detail="شعبه پرداخت مشخص نیست؛ شعبه دانش‌آموز یا شعبه پرداخت را تعیین کنید")

    from dependencies import get_next_sequence_value
    paid_at = _jalali_now_str()  # FIX L7: شمسی (این همان تاریخ رسید Transaction است).
    # فریز مبلغ در لحظه‌ی اعتبارسنجی (آبجکت‌های ORM بعد از UPDATE خام، stale می‌مانند).
    inst_amount = inst.amount
    _man_pre = inst.paid_amount or 0  # FIX (audit-v2/issue7): پوششِ قبل-از-فلیپ، برای سهم واقعی همین تسویه در ledger.

    # FIX B1 (الگوی H8-P4) + FIX (audit-v2/closeout-قدم۲): تسخیر اتمیک قسط با predicate روی paid_amount
    # (مثل بقیه‌ی مسیرها) — پوشش خودکارِ هم‌زمان دیگر گم نمی‌شود. rowcount صفر یعنی تسویه/حذف موازی
    # (→ همان 400 قبلی) یا حرکت پوشش (→ رفرش + محاسبه‌ی مجدد، ۳ تلاش) وگرنه 409.
    _marginal = 0
    for _try in range(3):
        claimed_rows = (
            db.query(Installment)
            .filter(Installment.id == installment_id, Installment.is_paid == False, Installment.is_deleted == False, func.coalesce(Installment.paid_amount, 0) == _man_pre)
            .update(
                # FIX M13: تسویه‌ی دستی یعنی پوشش کامل.
                {Installment.is_paid: True, Installment.paid_at: paid_at, Installment.paid_amount: inst_amount},
                synchronize_session=False,
            )
        )
        if claimed_rows == 1:
            _marginal = inst_amount - _man_pre
            break
        db.refresh(inst)
        if inst.is_paid or inst.is_deleted:
            db.rollback()
            raise HTTPException(status_code=400, detail="این قسط قبلاً تسویه شده است")
        inst_amount = inst.amount or 0
        if inst_amount <= 0:
            db.rollback()
            raise HTTPException(status_code=400, detail="مبلغ قسط معتبر نیست")
        _man_pre = inst.paid_amount or 0
    else:
        db.rollback()
        raise HTTPException(status_code=409, detail="تغییر هم‌زمان در اقساط؛ لطفاً دوباره تلاش کنید")
    # FIX (audit-v2/closeout-قدم۱): اگر پوشش قبلی از قبل کامل بود (ناسازگاری قدیمی)، چیزی برای وصول
    # نیست — به‌جای رسید صفر/منفی و clamp تاریخچه، 400 صادقانه (rollback فلیپ را هم برمی‌گرداند).
    if _marginal <= 0:
        db.rollback()
        raise HTTPException(status_code=400, detail="این قسط قبلاً پوشش کامل دارد؛ مبلغی برای وصول نیست")

    # FIX B1 (الگوی H8-P4): شارژ اتمیک کیف‌پول آموزشگاه — جمع در SQL، نه خواندن-جمع‌زدن در پایتون.
    wallet_rows = (
        db.query(Student)
        .filter(Student.id == student.id)
        .update(
            {Student.wallet_institute: func.coalesce(Student.wallet_institute, 0) + _marginal},  # FIX (audit-v2/closeout-قدم۱): فقط مابه‌التفاوت، نه کل (دابل‌کانت)
            synchronize_session=False,
        )
    )
    if wallet_rows != 1:
        db.rollback()
        raise HTTPException(status_code=404, detail="دانش‌آموز مربوط به این قسط یافت نشد")

    # FIX B1 (الگوی H8-P4): افزایش اتمیک total_paid ثبت‌نام — فقط اگر حذف‌نشده باشد.
    paid_rows = (
        db.query(Enrollment)
        .filter(Enrollment.id == enroll.id, Enrollment.is_deleted == False)
        .update(
            {Enrollment.total_paid: func.coalesce(Enrollment.total_paid, 0) + _marginal},  # FIX (audit-v2/closeout-قدم۱): فقط مابه‌التفاوت، نه کل (دابل‌کانت)
            synchronize_session=False,
        )
    )
    if paid_rows != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="ثبت‌نام هم‌زمان حذف شد؛ لطفاً صفحه را رفرش کنید")

    # ترتیب سینک (مثل قدم ۱): بعد از UPDATEهای خام، refresh بعد sync — چون bulk شنونده‌ی before_update را اجرا نمی‌کند.
    db.refresh(student)
    student.sync_wallet_balance()

    # سند deposit تازه — فقط بعد از موفقیت هر سه UPDATE بالا ساخته می‌شود (قبلش هیچ رسیدی مصرف نمی‌شود).
    new_trans = Transaction(
        student_id=student.id,
        enrollment_id=enroll.id,
        course_id=enroll.course_id,
        branch_id=payment_branch,
        amount=_marginal,  # FIX (audit-v2/closeout-قدم۱): رسید به اندازه‌ی وصول واقعی
        payment_method=payment_method or "نقدی",
        date=paid_at,
        description=f"وصول دستی قسط #{inst.id} (سررسید {inst.due_date})",
        type="deposit",
        target_wallet="institute",
        remittance_number=get_next_sequence_value(db, "remittance_institute", 100001),
    )
    db.add(new_trans)
    db.flush()

    # FIX (audit-v2/issue7): ledger تسویه‌ی دستی — همان _marginal (کامل − پوشش قبلی؛ حالت عادی = مبلغ کامل قسط).
    db.add(TransactionInstallmentAllocation(transaction_id=new_trans.id, installment_id=installment_id, amount=_marginal))

    # FIX H9: admin_username باید کاربر واقعی همین درخواست باشد، نه هاردکد "admin_portal".
    # همان الگوی H8-P2؛ چون check_* بالا توکن خراب را از قبل رد کرده، فالبک "unknown"
    # عملاً نباید هیچ‌وقت اجرا شود (فقط safety net).
    from dependencies import get_session_from_token  # lazy، مثل H8
    _audit_username = "unknown"
    if authorization:
        try:
            _parts = authorization.split()
            _token = _parts[1] if len(_parts) == 2 and _parts[0].lower() == "bearer" else None
            _sess, _ = get_session_from_token(db, _token) if _token else (None, None)
            if _sess is not None and getattr(_sess, "user_id", None):
                _audit_user = db.query(User).filter(User.id == _sess.user_id).first()
                if _audit_user is not None and _audit_user.username:
                    _audit_username = _audit_user.username
        except Exception:
            pass
    db.add(ActivityLog(
        admin_username=_audit_username,
        action="pay_installment_manual",
        target_id=inst.id,
        target_name="installment",
        details=f"وصول دستی قسط #{inst.id} به مبلغ {_marginal:,} تومان. رسید #{new_trans.id}."
    ))
    db.commit()
    return {"message": "قسط تسویه و رسید پرداخت ثبت شد", "receipt_id": new_trans.id}


# --- ۸. سیستم ارسال دستی پیامک یادآوری اقساط شهریه ---
@router.post("/finance/installments/{installment_id}/remind")
def send_installment_payment_reminder(
    installment_id: int,
    db: Session = Depends(get_db),
    # FIX (L14/R1): ارسال پیامک واقعی + SmsLog — فقط ادمین/منشی (قبلاً هر لاگینی، حتی شاگرد، به ولیِ هر کسی پیامک می‌زد).
    _: str = Depends(check_admin_or_secretary_access)
):
    # FIX: Bug 13 - exclude archived Installment rows from this active view.
    inst = db.query(Installment).filter(Installment.is_deleted == False).filter(Installment.id == installment_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="قسط یافت نشد")
        
    # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
    enroll = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.id == inst.enrollment_id).first()
    if not enroll:
        raise HTTPException(status_code=404, detail="ثبت‌نام قسط یافت نشد")
        
    student = db.query(Student).filter(Student.id == enroll.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="دانش‌آموز یافت نشد")
        
    if not student.parent_mobile:
        raise HTTPException(status_code=400, detail="شماره موبایل ولی برای این دانش‌آموز ثبت نشده است")

    msg = f"ولی محترم دانش‌آموز {display_name(student, 'گرامی')}، بدینوسیله به اطلاع می‌رساند قسط شهریه فرزند شما به مبلغ {inst.amount:,} تومان سررسید {inst.due_date} معوقه/سررسید شده است. لطفاً جهت واریز اقدام فرمایید."
    
    # ۱. ثبت در بخش پیامک‌ها
    db.add(SmsLog(
        target_group=f"manual_remind_{inst.id}",
        message_text=msg,
        sent_count=1,
        date=_jalali_now_str(),  # FIX (audit-v2/refund-date-followup): شمسی (این تاریخ در تاریخچه‌ی پیامک به کاربر نمایش داده می‌شود).
    ))
    
    # ۲. ارسال نوتیفیکیشن درون‌برنامه‌ای به ولی و دانش‌آموز
    try:
        from dependencies import NotificationService, ensure_student_shadow_users
        if student.parent_user_id is None:
            ensure_student_shadow_users(db, student)
        NotificationService.send_notification(
            db=db, recipient_user_id=student.parent_user_id, recipient_role="parent",
            type="installment", title="⚠️ یادآوری سررسید قسط فرزند",
            body=f"ولی محترم، قسط شهریه فرزند شما {student.first_name} به مبلغ {inst.amount:,} تومان سررسید {inst.due_date} معوقه شده است."
        )
        if student.user_id is None:
            ensure_student_shadow_users(db, student)
        NotificationService.send_notification(
            db=db, recipient_user_id=student.user_id, recipient_role="student",
            type="installment", title="⚠️ یادآوری سررسید قسط شهریه",
            body=f"دانش‌آموز گرامی، قسط شهریه شما به مبلغ {inst.amount:,} تومان سررسید {inst.due_date} معوقه شده است."
        )
    except Exception:
        pass
        
    db.commit()
    return {"status": "success", "message": "پیامک و نوتیفیکیشن یادآوری قسط شهریه با موفقیت ارسال شد."}


# --- ۹. دریافت تاریخچه کامل پرداخت‌ها و تراکنش‌ها با رعایت کامل IDOR ---

# تاریخچه تراکنش‌های آنلاین دانش‌آموز (مجهز به IDOR)
@router.get("/finance/student/{student_id}/payments")
def get_student_online_payments(
    student_id: int,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    _role: str = Depends(check_user_login)
):
    # FIX (F3): مثل invoice — check_student_access؛ معلمِ درگیر محق است (بدون PII اضافه).
    check_student_access(student_id, authorization, db, _role)
    payments = db.query(models.Payment).filter(models.Payment.student_id == student_id).order_by(models.Payment.created_at.desc()).all()
    return [
        {
            "id": p.id,
            "internal_transaction_id": p.internal_transaction_id,
            "amount": p.amount,
            "status": p.status,
            "created_at": _jalali_dt_str(p.created_at) if p.created_at else "---",  # FIX (audit-v2/refund-date-followup): شمسی.
            "paid_at": _jalali_dt_str(p.paid_at) if p.paid_at else "---",  # FIX (audit-v2/refund-date-followup): شمسی.
            "tracking_code": p.tracking_code or "---",
            "target_wallet": p.target_wallet,
            "description": p.description
        }
        for p in payments
    ]

# تاریخچه تراکنش‌های فیزیکی دانش‌آموز (مجهز به IDOR)
@router.get("/finance/student/{student_id}/transactions")
def get_student_physical_transactions(
    student_id: int,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    _role: str = Depends(check_user_login)
):
    # FIX (F3): مثل invoice — check_student_access؛ معلمِ درگیر محق است (بدون PII اضافه).
    check_student_access(student_id, authorization, db, _role)
    # FIX: Bug 12 - exclude archived Transaction rows from this active view.
    trans = db.query(Transaction).filter(Transaction.is_reversed == False).filter(Transaction.student_id == student_id, Transaction.is_deleted == False).order_by(Transaction.id.desc()).all()
    return [
        {
            "id": t.id,
            "remittance_number": t.remittance_number or "---",
            "amount": t.amount,
            "payment_method": t.payment_method,
            "tracking_code": t.tracking_code or "---",
            "date": t.date,
            "description": t.description,
            "type": t.type,
            "target_wallet": t.target_wallet,
            "is_reversed": t.is_reversed
        }
        for t in trans
    ]


# --- ۱۰. داشبورد تراز مالی دانش‌آموز (Student Financial Dashboard - مجهز به IDOR) ---
@router.get("/finance/student/{student_id}/dashboard")
def get_student_financial_dashboard(
    student_id: int,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    _role: str = Depends(check_user_login)
):
    # FIX (F3): مثل invoice — check_student_access؛ معلمِ درگیر محق است (بدون PII اضافه).
    check_student_access(student_id, authorization, db, _role)
    
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="دانش‌آموز یافت نشد")
        
    w_t = student.wallet_teacher if student.wallet_teacher is not None else 0
    w_i = student.wallet_institute if student.wallet_institute is not None else 0
    total_balance = w_t + w_i
    # FIX: Bug 16 - keep wallet credit separate from unpaid enrollment tuition.
    total_debt = calculate_student_debt(db, student)
    
    # دریافت سوابق ثبت‌نام‌ها و مبالغ شهریه
    # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
    enrollments = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.student_id == student_id).all()
    # کیف پول واحد شاگرد: جمع پرداخت‌های enrollmentهای فعال؛ هر ردیف
    # پایین‌تر با breakdown همان enrollment ساخته می‌شود.
    enroll_list = []
    total_paid_all = 0
    for en in enrollments:
        final_tuition, discount = get_enrollment_tuition_and_discount(en)
        breakdown = calculate_enrollment_debt_breakdown(db, en)
        c_title = en.course.title if en.course else "کلاس حذف شده"
        class_teacher = en.course.teacher if en.course else None
        class_teacher_name = display_name(class_teacher, "نامشخص") if class_teacher else None
        paid_for_class = breakdown["paid_teacher"] + breakdown["paid_institute"]
        total_paid_all += paid_for_class
        
        enroll_list.append({
            "enrollment_id": en.id,
            "course_id": en.course_id,
            "course_title": c_title,
            "teacher_id": en.course.teacher_id if en.course else None,
            "teacher_name": class_teacher_name,
            "is_unassigned": False,
            "total_tuition": en.total_tuition,
            "discount": discount,
            "final_tuition": final_tuition,
            "total_paid": paid_for_class,
            "outstanding": breakdown["debt"]
        })
        
    # لیست اقساط
    enrollment_ids = [e.id for e in enrollments]
    installments_list = []
    if enrollment_ids:
        # FIX: Bug 13 - exclude archived Installment rows from this active view.
        insts = db.query(Installment).filter(Installment.is_deleted == False).filter(Installment.enrollment_id.in_(enrollment_ids)).order_by(Installment.due_date.asc()).all()
        for i in insts:
            # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
            enroll = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.id == i.enrollment_id).first()
            course = db.query(Course).filter(Course.id == enroll.course_id).first() if enroll else None
            c_title = course.title if course else "کلاس حذف شده"
            
            from today_summary import parse_project_date  # FIX H3-B3: same B1 pattern — due_date is Jalali (lazy import)
            today_date = datetime.datetime.now().date()
            _due = parse_project_date(i.due_date)
            status_text = "پرداخت شده" if i.is_paid else ("معوقه" if (_due is not None and _due < today_date) else "در انتظار")
            
            installments_list.append({
                "id": i.id,
                "course_title": c_title,
                "amount": i.amount,
                "due_date": i.due_date,
                "is_paid": i.is_paid,
                "status": status_text,
                "paid_at": i.paid_at or "---"
            })
            
    # ۳ تراکنش اخیر
    recent_transactions = (
        # FIX: Bug 12 - exclude archived Transaction rows from this active view.
        db.query(Transaction).filter(Transaction.is_reversed == False)
        .filter(Transaction.student_id == student_id, Transaction.is_deleted == False)
        .order_by(Transaction.id.desc())
        .limit(3)
        .all()
    )
    
    return {
        "wallet": {
            "balance": total_balance,
            "wallet_teacher": w_t,
            "wallet_institute": w_i,
            "total_paid": total_paid_all,
            "total_debt": total_debt
        },
        "enrollments": enroll_list,
        "installments": installments_list,
        "recent_transactions": [
            {
                "id": t.id,
                "amount": t.amount,
                "date": t.date,
                "description": t.description,
                "type": t.type,
                "target_wallet": t.target_wallet
            }
            for t in recent_transactions
        ]
    }


# --- ۱۱. داشبورد تراز مالی اولیا (Parent Financial Dashboard - مجهز به IDOR) ---
# ولی مستقیماً بر اساس توکن امن والدینی خود و فرزند انتخابی، اطلاعات مالی را دریافت می‌کند.
@router.get("/finance/parent/dashboard")
def get_parent_financial_dashboard(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    _role: str = Depends(check_user_login)
):
    if not authorization:
        raise HTTPException(status_code=401, detail="توکن احراز هویت یافت نشد")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="قالب توکن معتبر نیست")
    token = parts[1]
    
    session = db.query(UserSession).filter(UserSession.token == token, UserSession.sub_role == "parent").first()
    if not session:
        raise HTTPException(status_code=401, detail="نشست والد یافت نشد یا منقضی شده است")
        
    own = get_session_parent(db, session)
    if not own:
        raise HTTPException(status_code=401, detail="نشست معتبر نیست؛ لطفاً دوباره وارد شوید")
    student_id = own.id # شناسه فرزند امن استخراج می‌شود
    return get_student_financial_dashboard(
        student_id=student_id,
        db=db,
        authorization=authorization,
        _role=_role,
    )


# --- ۱۲. اطلاعات کامل رسید تراکنش (Receipt Details - مجهز به IDOR) ---
@router.get("/finance/receipt/{transaction_id}")
def get_receipt_details(
    transaction_id: int,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    _role: str = Depends(check_user_login)
):
    # FIX: Bug 12 - exclude archived Transaction rows from this active view.
    trans = db.query(Transaction).filter(Transaction.is_reversed == False).filter(Transaction.id == transaction_id, Transaction.is_deleted == False).first()
    if not trans:
        raise HTTPException(status_code=404, detail="رسید مورد نظر یافت نشد")
        
    # راستی‌آزمایی IDOR
    verify_financial_idor(trans.student_id, authorization, db)
    
    student = db.query(Student).filter(Student.id == trans.student_id).first()
    student_name = display_name(student, "نامشخص")
    student_national = student.national_code if student else "---"
    # FIX H16: نام کلاس برای چاپ مجددِ سرور-محور؛ بدون فیلتر is_deleted (رسید سند تاریخی است).
    # کلاس/معلم/تعداد جلسه با همان helper مشترک چاپ می‌آید.
    ctx = _receipt_context(db, trans)
    course_name = ctx["course_name"]
    
    return {
        "transaction_id": trans.id,
        "remittance_number": trans.remittance_number or "---",
        "student_name": student_name,
        "student_national_code": student_national,
        "amount": trans.amount,
        "payment_method": trans.payment_method,
        "tracking_code": trans.tracking_code or "---",
        "date": trans.date,
        "description": trans.description,
        "course_name": course_name,  # FIX H16: نام کلاس برای بازسازی چاپ مجدد از سرور
        "target_wallet": trans.target_wallet,
        "type": trans.type,
        "is_reversed": trans.is_reversed,
        "course_code": ctx["course_code"],
        "course_id": ctx["course_id"],
        "teacher_id": ctx["teacher_id"],
        "teacher_name": ctx["teacher_name"],
        "sessions_covered": ctx["sessions_covered"],
        "wallet_label": ctx["wallet_label"],
        "paid_to_name": ctx["paid_to_name"],
        "class_remaining_teacher": ctx["class_remaining_teacher"],
        "class_remaining_institute": ctx["class_remaining_institute"],
    }


# --- ۱۳. اطلاعات کامل صورتحساب کلاس (Invoice details - مجهز به IDOR) ---
@router.get("/finance/invoice/{enrollment_id}")
def get_invoice_details(
    enrollment_id: int,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    _role: str = Depends(check_user_login)
):
    # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
    enroll = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.id == enrollment_id).first()
    if not enroll:
        raise HTTPException(status_code=404, detail="ثبت‌نام مورد نظر یافت نشد")
        
    # FIX (F3): فاکتور ثبت‌نام — check_student_access مثل student_class_status (:653)؛
    # معلمِ درگیر برای فاکتور شاگرد خودش محق است (داده‌ها هم‌سطح statement، بدون PII اضافه).
    check_student_access(enroll.student_id, authorization, db, _role)
    
    student = db.query(Student).filter(Student.id == enroll.student_id).first()
    course = db.query(Course).filter(Course.id == enroll.course_id).first()
    
    final_tuition, discount = get_enrollment_tuition_and_discount(enroll)
    breakdown = calculate_enrollment_debt_breakdown(db, enroll)
    total_paid = breakdown["paid_teacher"] + breakdown["paid_institute"]
    balance_due = breakdown["debt"]
    
    # دریافت اقساط این کلاس
    # FIX: Bug 13 - exclude archived Installment rows from this active view.
    installments = db.query(Installment).filter(Installment.is_deleted == False).filter(Installment.enrollment_id == enrollment_id).order_by(Installment.due_date.asc()).all()
    
    return {
        "enrollment_id": enroll.id,
        "course_id": course.id if course else enroll.course_id,
        "student_name": display_name(student, "نامشخص"),
        "course_title": course.title if course else "کلاس حذف شده",
        "teacher_id": course.teacher_id if course else None,
        "teacher_name": display_name(course.teacher, "نامشخص") if course and course.teacher else None,
        "is_unassigned": False,
        "base_tuition": enroll.total_tuition,
        "discount_type": enroll.discount_type,
        "discount_value": enroll.discount_value,
        "discount_amount": discount,
        "final_tuition": final_tuition,
        "total_paid": total_paid,
        "balance_due": balance_due,
        # FIX O-09: همان معنا با نام صریح + اعتبار مازاد پرداخت (افزودنی؛ فیلدهای قبلی دست‌نخورده)
        "remaining_tuition": balance_due,
        "credit_balance": max(0, total_paid - final_tuition),
        "installments": [
            {
                "id": inst.id,
                "amount": inst.amount,
                "due_date": inst.due_date,
                "is_paid": inst.is_paid,
                "paid_at": inst.paid_at or "---"
            }
            for inst in installments
        ]
    }


# --- ۱۴. گزارش جامع بدهکاران (Debt Report - ادمین و منشی) ---
# FIX (گروه۲/آیتم ۶ و ۹): هلپر مشترک «ردیف بدهکار» — یک منطق برای لیست، نمای گروه‌بندی‌شده،
# پیامک دسته‌جمعی و خروجی‌ها (CSV/Excel) تا عددها واگرا نشوند.
DEBT_AGE_BUCKETS = (("0-7", 0, 7), ("8-30", 8, 30), ("over_30", 31, None))


def _debtor_last_payment(db: Session, student_id: int):
    """(تاریخ خام آخرین پرداخت، تاریخ پارس‌شده) — فقط پولِ ورودیِ واقعیِ همین دانش‌آموز.

    انواع مجاز همان تعریف یگانهٔ وصولی نقدی است (`INSTITUTE_CASH_TYPES` + ردیف legacy بی‌type)
    و واریزی به کیف معلم/شارژ جلسه/برگشت‌خورده/حذف‌شده «پرداخت» حساب نمی‌شود.
    """
    from financial_calculations import INSTITUTE_CASH_TYPES  # lazy، الگوی پروژه
    from today_summary import parse_project_date
    rows = (
        db.query(models.Transaction.date)
        .filter(
            models.Transaction.student_id == student_id,
            models.Transaction.amount > 0,
            models.Transaction.is_deleted == False,
            models.Transaction.is_reversed == False,
            or_(models.Transaction.type.in_(INSTITUTE_CASH_TYPES),
                models.Transaction.type.is_(None)),
        )
        .all()
    )
    dated = [(raw, parse_project_date(raw)) for raw, in rows]
    dated = [(raw, parsed) for raw, parsed in dated if parsed is not None]
    if not dated:
        return "", None
    dated.sort(key=lambda pair: (pair[1], pair[0]), reverse=True)
    return dated[0][0] or "", dated[0][1]


def _debtor_age_bucket(last_payment_day, today: datetime.date):
    """دستهٔ قدمت بدهی: از آخرین پرداخت تا امروز؛ بی‌پرداخت ⇒ `no_payment`."""
    if last_payment_day is None:
        return "no_payment", None
    age = (today - last_payment_day).days
    if age < 0:
        age = 0
    for name, low, high in DEBT_AGE_BUCKETS:
        if high is None or age <= high:
            if age >= low:
                return name, age
    return "over_30", age


def _debtor_teacher_rows(db: Session, student_id: int, wallet_teacher_debt: int = 0):
    """(teacher_id, teacher_name, course_title, بدهیِ همان enrollment).

    این نمای per-class فقط بدهیِ enrollment را نشان می‌دهد. بدهی legacy که
    `calculate_student_debt` از wallet کلی دانش‌آموز می‌گیرد، در `unassigned_debt`
    باقی می‌ماند؛ حتی اگر دانش‌آموز فقط یک کلاس فعال داشته باشد. نسبت‌دادن wallet
    کلی به تنها کلاس هم همچنان نسبت‌دادن نادرست بین کلاس‌هاست.
    """
    from financial_calculations import calculate_enrollment_debt_breakdown  # lazy، الگوی پروژه
    enrollments = (
        db.query(Enrollment)
        .filter(Enrollment.student_id == student_id, Enrollment.is_deleted == False)
        .all()
    )
    rows = []
    for en in enrollments:
        course = db.query(Course).filter(Course.id == en.course_id).first()
        if course is None:
            continue
        teacher = db.query(Teacher).filter(Teacher.id == course.teacher_id).first()
        breakdown = calculate_enrollment_debt_breakdown(db, en)
        rows.append({
            "teacher_id": course.teacher_id,
            "teacher_name": display_name(teacher, "نامشخص") if teacher else "بدون معلم",
            "course_id": course.id,
            "course_title": course.title or "کلاس بدون نام",
            "debt": breakdown["debt"],
            "debt_teacher": breakdown["debt_teacher"],
            "debt_institute": breakdown["debt_institute"],
            "enrollment_id": en.id,
            "is_unassigned": False,
        })
    # A legacy wallet balance has no enrollment scope. Keep its remainder as an
    # explicit row instead of assigning it to an arbitrary active class.
    student = db.query(Student).filter(Student.id == student_id).first()
    if student is not None:
        total_debt = calculate_student_debt(db, student)
        assigned = sum(int(row["debt"] or 0) for row in rows)
        unassigned = max(0, int(total_debt) - assigned)
        # ``unassigned`` is contractual/tuition debt that has no enrollment
        # owner. Wallet debt is reported in its own top-level fields and must
        # not be smuggled into this row's teacher/institute class split.
        if unassigned:
            rows.append({
                "teacher_id": None,
                "teacher_name": None,
                "course_id": None,
                "course_title": None,
                "debt": unassigned,
                "debt_teacher": 0,
                "debt_institute": unassigned,
                "enrollment_id": None,
                "is_unassigned": True,
            })
    return rows


def build_debtor_rows(db: Session, resolved_branch: Optional[int], search: Optional[str] = None):
    """فهرست بدهکاران با فیلدهای کامل — منبع یگانهٔ لیست/گروه‌بندی/پیامک/خروجی.

    FIX (گروه۲/آیتم۶): `branch_scope_clause` به‌جای فیلتر سختِ شعبه؛ در دادهٔ واقعی آموزشگاه
    `students.branch_id` برای ردیف‌های legacy NULL است و ادمینِ شعبه‌دار `branch_id=1` دارد ⇒
    `NULL == 1` هرگز درست نیست و **خروجی بدهکاران با وجود داده خالی می‌شد**.
    سیاست: ردیف بی‌شعبه = سراسری/legacy (دیده می‌شود) · ردیف شعبهٔ دیگر = پنهان (بدون نشت).
    """
    from financial_calculations import branch_scope_clause  # lazy، الگوی پروژه
    from today_summary import parse_project_date
    today = datetime.datetime.now().date()

    query = db.query(Student).filter(Student.is_deleted == False)  # noqa: E712 (سبک پروژه)
    scope = branch_scope_clause(Student.branch_id, resolved_branch)
    if scope is not None:
        query = query.filter(scope)
    students = query.order_by(Student.id).all()

    needle = (search or "").strip().lower()
    result = []
    for s in students:
        w_t = s.wallet_teacher if s.wallet_teacher is not None else 0
        w_i = s.wallet_institute if s.wallet_institute is not None else 0
        # FIX: Bug 16 - include only positive outstanding tuition (or legacy unpriced debt).
        total_debt = calculate_student_debt(db, s)
        if total_debt <= 0:
            continue

        enrollments = db.query(Enrollment).filter(
            Enrollment.is_deleted == False,  # noqa: E712
            Enrollment.student_id == s.id).all()
        courses = [e.course.title for e in enrollments if e.course]

        student_name = display_name(s, "نامشخص")
        teacher_rows = _debtor_teacher_rows(db, s.id, abs(w_t) if w_t < 0 else 0)
        teacher_names = sorted({r["teacher_name"] for r in teacher_rows if r.get("teacher_name")})
        if needle:
            haystack = " ".join([student_name, *teacher_names, *(c or "" for c in courses)]).lower()
            if needle not in haystack:
                continue

        last_payment_raw, last_payment_day = _debtor_last_payment(db, s.id)
        bucket, age_days = _debtor_age_bucket(last_payment_day, today)
        # Category totals are the sum of explicit enrollment rows. The global
        # wallet is used only for the explicit unassigned row above.
        class_debt_teacher = sum(int(row.get("debt_teacher") or 0) for row in teacher_rows)
        class_debt_institute = sum(int(row.get("debt_institute") or 0) for row in teacher_rows)
        result.append({
            "student_id": s.id,
            "student_name": student_name,
            "national_code": s.national_code,
            "parent_mobile": s.parent_mobile,
            "student_mobile": s.student_mobile,
            "contact_mobile": s.parent_mobile or s.student_mobile or "",
            "debt_teacher": class_debt_teacher,
            "debt_institute": class_debt_institute,
            # Legacy wallet debt is deliberately exposed under separate names;
            # it is never merged into a class/enrollment row.
            "wallet_debt_teacher": max(0, -w_t),
            "wallet_debt_institute": max(0, -w_i),
            "total_debt": total_debt,
            "active_courses": courses,
            # FIX (گروه۲/آیتم۹): فیلدهای خواسته‌شده — تاریخ آخرین پرداخت، شماره تماس،
            # قدمت بدهی (برای اولویت پیگیری) و تفکیک «بدهی به کدام معلم».
            "last_payment_date": last_payment_raw if parse_project_date(last_payment_raw) is not None else "",
            "debt_age_days": age_days,
            "debt_age_bucket": bucket,
            "teachers": teacher_rows,
        })
    result.sort(key=lambda row: row["total_debt"], reverse=True)
    return result


@router.get("/finance/reports/debtors_list")
def get_debtors_list(
    branch_id: Optional[int] = None,
    search: Optional[str] = None,  # FIX (گروه۲/آیتم۹): جست‌وجو بر اساس نام دانش‌آموز/معلم/کلاس
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_or_secretary_access) # FIX (L14/Y4): کامنت «ادمین و منشی» حالا واقعاً اعمال می‌شود
):
    # FIX (گروه۲/آیتم ۶ و ۹): بدنهٔ تکراری با هلپر مشترک `build_debtor_rows` جایگزین شد —
    # همان فیلدهای قبلی (کلیدهای موجود برای کلاینت منتشرشده حفظ شده) به‌علاوهٔ فیلدهای جدید.
    resolved_branch = get_user_branch_filter(db, authorization, branch_id)
    return build_debtor_rows(db, resolved_branch, search)


@router.get("/finance/reports/debtors_grouped")
def get_debtors_grouped(
    branch_id: Optional[int] = None,
    search: Optional[str] = None,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_or_secretary_access),
):
    """FIX (گروه۲/آیتم۹ — «پیشنهاد من»): نمای مدیریتی بدهکاران، نه فقط لیست تخت.

    * `by_teacher`: کدام معلم بیشترین بدهی معوقهٔ کلاس‌هایش را دارد (برای تصمیم مدیریتی).
    * `by_age`: دستهٔ قدمت بدهی (`0-7` / `8-30` / `over_30` / `no_payment`) برای اولویت پیگیری.
    منبع عددها دقیقاً همان `build_debtor_rows` است ⇒ با لیست/خروجی‌ها واگرا نمی‌شود.
    """
    resolved_branch = get_user_branch_filter(db, authorization, branch_id)
    rows = build_debtor_rows(db, resolved_branch, search)

    teacher_groups: dict = {}
    for row in rows:
        teacher_entries = row["teachers"] or [
            {"teacher_id": None, "teacher_name": "بدون کلاس فعال", "course_title": "", "debt": 0}
        ]
        for entry in teacher_entries:
            # The explicit unassigned row is reported through the top-level
            # unassigned_debt field, not as a teacher group.
            if entry.get("is_unassigned"):
                continue
            key = entry["teacher_id"]
            group = teacher_groups.setdefault(key, {
                "teacher_id": key,
                "teacher_name": entry["teacher_name"],
                "debt": 0,
                "students_count": 0,
                "student_ids": [],
                "courses": [],
            })
            group["debt"] += int(entry["debt"] or 0)
            group["students_count"] += 1
            group["student_ids"].append(row["student_id"])
            label = entry.get("course_title") or "کلاس بدون نام"
            if label not in group["courses"]:
                group["courses"].append(label)

    bucket_groups = {
        name: {"bucket": name, "debt": 0, "students_count": 0, "student_ids": []}
        for name, _low, _high in DEBT_AGE_BUCKETS
    }
    bucket_groups["no_payment"] = {"bucket": "no_payment", "debt": 0, "students_count": 0,
                                   "student_ids": []}
    for row in rows:
        group = bucket_groups[row["debt_age_bucket"]]
        group["debt"] += int(row["total_debt"])
        group["students_count"] += 1
        group["student_ids"].append(row["student_id"])

    total_debt = sum(int(row["total_debt"]) for row in rows)
    wallet_debt_teacher = sum(int(row.get("wallet_debt_teacher") or 0) for row in rows)
    wallet_debt_institute = sum(int(row.get("wallet_debt_institute") or 0) for row in rows)
    by_teacher = sorted(teacher_groups.values(), key=lambda g: (-g["debt"], g["teacher_id"] or 0))
    assigned = sum(int(group["debt"]) for group in by_teacher)
    return {
        "total_debt": total_debt,
        "debtors_count": len(rows),
        "wallet_debt_teacher": wallet_debt_teacher,
        "wallet_debt_institute": wallet_debt_institute,
        "by_teacher": by_teacher,
        "by_age": [bucket_groups[name] for name in ("0-7", "8-30", "over_30", "no_payment")],
        # FIX (گروه۲/آیتم۹): بخشی از بدهی که قطعی به معلمِ خاصی نسبت داده نمی‌شود
        # (دادهٔ legacy با چند کلاس فعال و بدهیِ کیف پول) ⇒ عدد گزارش همیشه می‌خواند:
        # `sum(by_teacher.debt) + unassigned_debt == total_debt`
        "unassigned_debt": max(0, total_debt - assigned),
        "rows": rows,
    }


class DebtorsRemindRequest(BaseModel):
    student_ids: List[int]
    message: Optional[str] = None


@router.post("/finance/debtors/remind")
def remind_debtors(
    req: DebtorsRemindRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_access),
):
    """FIX (گروه۲/آیتم۹ — «پیشنهاد من»): پیامک یادآوری دسته‌جمعی به بدهکارانِ فیلترشده.

    عمداً روی **همان زیرساخت موجود** dunning سوار است (نه موتور جدید): `SmsLog` +
    `ActivityLog` + idempotency «۴۸ ساعت گذشته یادآوری شده» + الگوی متن پیام.
    تفاوت فقط کلید هدف است: `dunning_<installment_id>` در برابر `debtor_<student_id>`
    (بدهکار ممکن است اصلاً قسط نداشته باشد). ارسال واقعی مثل بقیهٔ پروژه mock است
    (بدون `FCM_SERVER_KEY`/درگاه پیامک فعال) و فقط رکورد/لاگ می‌سازد. فقط ادمین.
    """
    from routers.dunning import _jalali_now_str, _get_admin_username  # lazy: استفادهٔ مجدد، نه بازنویسی

    ids = list(dict.fromkeys(int(sid) for sid in (req.student_ids or [])))
    if not ids:
        raise HTTPException(status_code=400, detail="لیست بدهکاران خالی است")

    resolved_branch = get_user_branch_filter(db, authorization, None)
    debtors = {row["student_id"]: row for row in build_debtor_rows(db, resolved_branch)}

    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=48)
    recent_rows = db.query(ActivityLog.target_id).filter(
        ActivityLog.action == "debtors_reminder",
        ActivityLog.target_id.in_(ids),
        ActivityLog.timestamp >= cutoff,
    ).all()
    recent_ids = {row[0] for row in recent_rows}

    admin_username = _get_admin_username(db, authorization)
    sent_ids: List[int] = []
    skipped_ids: List[int] = []
    skipped_reasons: dict = {}

    for sid in ids:
        row = debtors.get(sid)
        if row is None:
            skipped_ids.append(sid)
            skipped_reasons[str(sid)] = "بدهی فعالی ندارد یا در شعبهٔ شما نیست"
            continue
        mobile = (row.get("contact_mobile") or "").strip()
        if not mobile:
            skipped_ids.append(sid)
            skipped_reasons[str(sid)] = "موبایل ولی یافت نشد"
            continue
        if sid in recent_ids:
            skipped_ids.append(sid)
            skipped_reasons[str(sid)] = "۴۸ ساعت گذشته یادآوری شده"
            continue
        amount = f"{int(row['total_debt']):,}"
        text_message = (req.message or "").strip() or (
            f"سلام ولی محترم {row['student_name']}، ماندهٔ بدهی فرزند شما {amount} تومان است. "
            f"لطفاً در اسرع وقت نسبت به پرداخت اقدام فرمایید. - آموزشگاه خوارزمی"
        )
        db.add(SmsLog(target_group=f"debtor_{sid}", message_text=text_message, sent_count=1,
                      date=_jalali_now_str()))
        db.add(ActivityLog(admin_username=admin_username, action="debtors_reminder",
                           target_id=sid, target_name=row["student_name"], details=text_message,
                           timestamp=datetime.datetime.utcnow()))
        sent_ids.append(sid)
        recent_ids.add(sid)

    if sent_ids:
        db.commit()
    return {
        "message": f"{len(sent_ids)} یادآوری بدهی ثبت شد",
        "sent_count": len(sent_ids),
        "skipped_count": len(skipped_ids),
        "sent": sent_ids,
        "skipped": skipped_ids,
        "skipped_reasons": skipped_reasons,
    }


# --- ۱۵. گزارش درآمدهای آموزشگاه (Revenue Report - فقط ادمین) ---
@router.get("/finance/reports/revenue_summary")
def get_revenue_summary(
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_access) # فقط ادمین ارشد
):
    # کل مبالغ دریافتی موفق به تفکیک روش پرداخت و کیف پول هدف
    # FIX: Bug 12 - exclude archived Transaction rows from this active view.
    cash_teacher = db.query(func.sum(Transaction.amount)).filter(Transaction.is_reversed == False).filter(Transaction.type == "deposit", Transaction.payment_method == "نقدی", Transaction.target_wallet == "teacher", Transaction.is_deleted == False).scalar() or 0
    # FIX: Bug 12 - exclude archived Transaction rows from this active view.
    cash_inst = db.query(func.sum(Transaction.amount)).filter(Transaction.is_reversed == False).filter(Transaction.type == "deposit", Transaction.payment_method == "نقدی", Transaction.target_wallet == "institute", Transaction.is_deleted == False).scalar() or 0
    
    # FIX: Bug 12 - exclude archived Transaction rows from this active view.
    card_teacher = db.query(func.sum(Transaction.amount)).filter(Transaction.is_reversed == False).filter(Transaction.type == "deposit", Transaction.payment_method == "کارت به کارت", Transaction.target_wallet == "teacher", Transaction.is_deleted == False).scalar() or 0
    # FIX: Bug 12 - exclude archived Transaction rows from this active view.
    card_inst = db.query(func.sum(Transaction.amount)).filter(Transaction.is_reversed == False).filter(Transaction.type == "deposit", Transaction.payment_method == "کارت به کارت", Transaction.target_wallet == "institute", Transaction.is_deleted == False).scalar() or 0
    
    # FIX: Bug 12 - exclude archived Transaction rows from this active view.
    online_teacher = db.query(func.sum(Transaction.amount)).filter(Transaction.is_reversed == False).filter(Transaction.type == "deposit", Transaction.payment_method == "online", Transaction.target_wallet == "teacher", Transaction.is_deleted == False).scalar() or 0
    # FIX: Bug 12 - exclude archived Transaction rows from this active view.
    online_inst = db.query(func.sum(Transaction.amount)).filter(Transaction.is_reversed == False).filter(Transaction.type == "deposit", Transaction.payment_method == "online", Transaction.target_wallet == "institute", Transaction.is_deleted == False).scalar() or 0
    
    total_teacher = cash_teacher + card_teacher + online_teacher
    total_inst = cash_inst + card_inst + online_inst
    
    # تعداد تراکنش‌های استرداد شده (Refunds)
    # FIX: Bug 12 - exclude archived Transaction rows from this active view.
    # برگشت payout معلم ledger است و refund دانش‌آموز نیست؛ با settlement_id تفکیک می‌شود.
    refund_count = db.query(Transaction).filter(Transaction.is_deleted == False, Transaction.is_reversed == False, Transaction.settlement_id.is_(None)).filter(Transaction.type == "reversal").count()
    # FIX: Bug 12 - exclude archived Transaction rows from this active view.
    refund_amount = db.query(func.sum(Transaction.amount)).filter(Transaction.is_deleted == False, Transaction.is_reversed == False, Transaction.settlement_id.is_(None)).filter(Transaction.type == "reversal").scalar() or 0
    
    return {
        "revenue_by_wallet": {
            "teacher_wallet": {
                "cash": cash_teacher,
                "card": card_teacher,
                "online": online_teacher,
                "total": total_teacher
            },
            "institute_wallet": {
                "cash": cash_inst,
                "card": card_inst,
                "online": online_inst,
                "total": total_inst
            }
        },
        "totals": {
            "total_revenue": total_teacher + total_inst,
            "refund_count": refund_count,
            "refund_total_amount": abs(refund_amount)
        }
    }


# --- ۱۶. گزارش تسویه حساب مربیان (Teacher Settlement Report - فقط ادمین) ---
@router.get("/finance/reports/teacher_settlements_summary")
def get_teacher_settlements_summary(
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_access) # فقط ادمین ارشد
):
    teachers = db.query(Teacher).all()
    result = []
    for t in teachers:
        # تعداد کل جلسات مربی
        courses = db.query(Course).filter(Course.teacher_id == t.id).all()
        course_ids = [c.id for c in courses]
        
        session_count = 0
        if course_ids:
            # FIX: Bug 14 - exclude archived SessionLog rows from this active view.
            session_count = db.query(SessionLog).filter(SessionLog.is_deleted == False).filter(SessionLog.course_id.in_(course_ids)).count()
            
        # مبالغ تسویه شده قبلی مربی
        settlements = db.query(models.Settlement).filter(models.Settlement.teacher_id == t.id).all()
        settled_total = sum(s.total_amount for s in settlements)

        # کیف پول واحد معلم: طلب فعلی = جمع جلسات دارای حضور تسویه‌نشده (همان منطق pending_settlement)
        pending_total = 0
        if course_ids:
            # FIX: H6(A2) - طلب معلم = مبالغ قراردادی + جریمه‌ی غایبین غیرموجه.
            sess_rows = db.query(SessionLog.id, SessionLog.final_teacher_cost, SessionLog.absent_penalty_teacher, SessionLog.is_penalty_settled).filter(SessionLog.is_deleted == False, SessionLog.course_id.in_(course_ids)).all()
            if sess_rows:
                all_sids = [r[0] for r in sess_rows]
                unbilled_sids = {r[0] for r in db.query(Attendance.session_id).filter(Attendance.session_id.in_(all_sids), Attendance.is_billed == False, Attendance.status.in_(["Present", "Late"])).distinct().all()}
                pending_total = sum((r[1] or 0) + (r[2] or 0) for r in sess_rows if r[0] in unbilled_sids or ((r[2] or 0) > 0 and not r[3]))  # FIX H8-gap/follow-up: شاخه‌ی جریمه هم طلب است (همان منطق دوشاخه‌ی settle)

        result.append({
            "teacher_id": t.id,
            # FIX(A4): نام معلم با تحمل NULL (رکورد legacy نباید «None None» بدهد)
            "teacher_name": display_name(t, "نامشخص"),
            "mobile": t.mobile,
            "card_number": t.card_number or "---",
            "session_count": session_count,
            "wallet_balance": pending_total, # طلب فعلی مربی (محاسبه زنده؛ ستون wallet_balance معلم استفاده نمی‌شود)
            "pending_total_amount": pending_total,
            "settled_total_amount": settled_total,
            "earned_total_amount": settled_total + pending_total,
            "last_settled_at": _jalali_dt_str(settlements[-1].settled_at) if settlements else "---"  # FIX (audit-v2/refund-date-followup): شمسی.
        })
    return result
