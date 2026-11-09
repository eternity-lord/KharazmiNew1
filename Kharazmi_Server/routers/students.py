from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Header, Request
from sqlalchemy.orm import Session, joinedload
from typing import Optional, Union
from sqlalchemy import desc, or_, text, func
import io
import uuid
import os
import datetime

import models
from models import (
    Attendance, Course, Enrollment, Grade, InstituteShare, SessionLog, SmsLog, Student, Teacher, Transaction, User, UserSession, Installment, Notification
)
from schemas import (
    HistoryRequest, LoginRequest, TeacherInfo, FullTeacherProfile, StudentCreate, TeacherCreate, CourseCreate, EnrollmentCreate, GradeCreate, GradeItem, AttendanceLogRequest, AttendanceItem, AttendanceSubmitData, SmsSendRequest, ChangePasswordRequest, StudentProfileInfo, FullStudentProfile, TeacherProfileInfo, FullTeacherProfile, ClassReportInfo, ClassStudentData, ClassSessionHistory, FullClassReport, ShareConfigModel, StudentUpdate, TeacherUpdate, PersonListItem, TransactionUpdate, StudentAttendanceHistoryRequest, AdvancedSearchItem, FinanceSubmitData, PrintReceiptRequest, TransactionTestData, StudentRegisterAndEnrollRequest
)
from storage import storage_dir, resolve_existing
from dependencies import (get_db, check_admin_access, check_admin_or_secretary_access,
                            check_admin_secretary_or_teacher_access, resolve_session_teacher,
                            check_user_login, check_student_access,
                            get_enrollment_tuition_and_discount, SESSION_EXPIRY_DAYS, limiter,
                            ensure_student_shadow_users, get_session_student, get_session_parent,
                            normalize_mobile, validate_image_upload, require_permission,
                            resolve_notification_role)
# FIX(C6): خواندن واقعی تکالیف/آزمون‌ها/برنامهٔ هفتگی برای پورتال‌ها (بدون کد تکراری).
from portal_data import build_portal_activity

# FIX: Bug 16 - share the tuition-minus-payment debt calculation across financial views.
from financial_calculations import calculate_student_debt

router = APIRouter()

# FIX: Bug 22 - reuse the same checksum as schemas and online registration.
from validation import is_valid_iranian_national_code
# FIX (F-T1): اعتبارسنجی مرکزی اقساط — مسیر ثبت دانش‌آموز + ثبت‌نام هم همان قاعده‌ی مسیر مستقل قسط را دارد.
from validation import normalize_installments


@router.post("/students/register")
@limiter.limit("5/hour")
def register_student(request: Request, student: StudentCreate, db: Session = Depends(get_db)):
    if not is_valid_iranian_national_code(student.national_code):
        raise HTTPException(status_code=400, detail="کد ملی وارد شده معتبر نیست")

    if db.query(Student).filter(Student.national_code == student.national_code).first():
        raise HTTPException(status_code=400, detail="کد ملی تکراری است")

    # FIX(security): یکتایی موبایل خود دانش‌آموز (موبایل ولی چون بین خواهر/برادر مشترک است چک نمی‌شود)
    # FIX H20: نرمال‌سازی قبل از چک یکتایی و ذخیره (خالی مجاز و دست‌نخورده می‌ماند).
    _raw_sm = (student.student_mobile or "").strip()
    student_mobile = normalize_mobile(_raw_sm) if _raw_sm else ""
    if _raw_sm and not student_mobile:
        raise HTTPException(status_code=400, detail="فرمت شماره موبایل دانش‌آموز صحیح نیست")
    if db.query(Student).filter(Student.student_mobile == student_mobile).first():
        raise HTTPException(status_code=409, detail="این شماره موبایل قبلاً ثبت شده است")
    _raw_pm = (student.parent_mobile or "").strip()
    parent_mobile = normalize_mobile(_raw_pm) if _raw_pm else ""
    if _raw_pm and not parent_mobile:
        raise HTTPException(status_code=400, detail="فرمت شماره موبایل ولی صحیح نیست")

    from dependencies import get_next_sequence_value, resolve_creation_branch
    next_code = get_next_sequence_value(db, "student", 100001)

    # FIX(branch): دانش‌آموز جدید باید branch معتبر داشته باشد — سیاست مرکزی:
    # branch صریح فعال، وگرنه فقط branch فعالِ تک‌شعبه‌ای؛ در حالت مبهم 400 واضح (تخمین ممنوع).
    branch_id = resolve_creation_branch(db, requested_branch_id=student.branch_id)

    student_data = student.dict()
    student_data["student_code"] = next_code
    student_data["student_mobile"] = student_mobile
    student_data["parent_mobile"] = parent_mobile
    student_data["branch_id"] = branch_id

    new_student = Student(**student_data)
    db.add(new_student)
    db.flush()  # جهت ایجاد آیدی قبل از ساخت سایه‌ها
    ensure_student_shadow_users(db, new_student)
    db.commit()
    return {"message": f"دانش‌آموز ثبت شد. کد دانش‌آموز: {next_code}", "id": new_student.id, "student_code": next_code}


@router.post("/students/register_and_enroll")
def register_and_enroll_student(
    req: StudentRegisterAndEnrollRequest, 
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    # FIX O-22: معلم هم می‌تواند دانش‌آموز جدید ثبت کند (و در **کلاس خودش** ثبت‌نام کند)؛
    # قبلاً این مسیر فقط ادمین/منشی بود و معلم ۴۰۳ می‌گرفت. منطق مالی هیچ تغییری ندارد.
    sub_role: str = Depends(check_admin_secretary_or_teacher_access)
):
    # 1. بررسی صحت کد ملی و عدم تکراری بودن کدملی دانش‌آموز
    if not is_valid_iranian_national_code(req.national_code):
        raise HTTPException(status_code=400, detail="کد ملی وارد شده معتبر نیست")

    if db.query(Student).filter(Student.national_code == req.national_code).first():
        raise HTTPException(status_code=400, detail="کد ملی وارد شده تکراری است")

    # FIX (F-T1): اقساط پیش از هر نوشتنی با قاعده‌ی مرکزی سنجیده می‌شوند تا مسیر «ثبت دانش‌آموز +
    # ثبت‌نام همراه اقساط» و مسیر مستقل قسط یک سیاست داشته باشند. schema در مرز HTTP ۴۲۲ می‌دهد؛
    # این لایه برای فراخوان داخلی است و مثل بقیه‌ی اعتبارسنجی‌های همین اندپوینت ۴۰۰ می‌دهد.
    try:
        normalized_installments = normalize_installments(req.installments)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
        
    try:
        from dependencies import get_next_sequence_value, get_current_user, resolve_creation_branch
        next_code = get_next_sequence_value(db, "student", 100001)

        # FIX(branch): دانش‌آموز با branch معتبر ساخته می‌شود (سیاست مرکزی — branch کاربر فعلی،
        # وگرنه branch همان کلاسِ انتخاب‌شده، وگرنه فقط تک‌شعبه‌ی فعال؛ در حالت مبهم 400 واضح).
        # Enrollment/Transaction هم از همین branch پیاده می‌شوند (منطق H7: شاگرد، وگرنه کلاس).
        current_user = get_current_user(authorization, db)
        fallback_branch = None
        if req.course_id is not None:
            _fb_course = db.query(Course).filter(Course.id == req.course_id).first()
            if _fb_course is not None:
                fallback_branch = _fb_course.branch_id
        # FIX O-22: برای معلم، پروندهٔ معلم پاس داده می‌شود تا سیاست شعبه دقیقاً «شعبهٔ خودش» باشد.
        branch_id = resolve_creation_branch(
            db, user=current_user, requested_branch_id=req.branch_id, fallback_branch_id=fallback_branch,
            teacher=(resolve_session_teacher(db, authorization) if sub_role == "teacher" else None),
        )

        # 2. ثبت فیزیکی مشخصات دانش‌آموز
        # FIX H20: نرمال‌سازی موبایل‌ها قبل از ذخیره (خالی مجاز و دست‌نخورده می‌ماند).
        _raw_sm = (req.student_mobile or "").strip()
        _sm = normalize_mobile(_raw_sm) if _raw_sm else ""
        if _raw_sm and not _sm:
            raise HTTPException(status_code=400, detail="فرمت شماره موبایل دانش‌آموز صحیح نیست")
        _raw_pm = (req.parent_mobile or "").strip()
        _pm = normalize_mobile(_raw_pm) if _raw_pm else ""
        if _raw_pm and not _pm:
            raise HTTPException(status_code=400, detail="فرمت شماره موبایل ولی صحیح نیست")
        new_student = Student(
            first_name=req.first_name,
            last_name=req.last_name,
            father_name=req.father_name,
            national_code=req.national_code,
            birth_date=req.birth_date,
            student_code=next_code,
            student_mobile=_sm,
            parent_mobile=_pm,
            home_phone=req.home_phone or "",
            address=req.address or "ثبت نشده",
            study_status=req.study_status or "در حال تحصیل",
            gender=req.gender,
            # FIX(branch): رکورد جدید بدون شعبه ساخته نمی‌شود.
            branch_id=branch_id,
            wallet_teacher=0,
            wallet_institute=0,
            wallet_balance=0
        )
        db.add(new_student)
        db.flush() # جهت ایجاد آیدی دانش‌آموز قبل از کامیت اصلی
        ensure_student_shadow_users(db, new_student)

        enroll_id = None
        
        # 3. ثبت‌نام در کلاس (در صورت ارسال اطلاعات کلاس)
        if req.course_id is not None:
            course = db.query(Course).filter(Course.id == req.course_id).first()
            if not course:
                raise HTTPException(status_code=404, detail="کلاس مورد نظر یافت نشد")
            # FIX O-22: معلم فقط برای کلاس‌های خودش؛ کلاس دیگری ⇒ ۴۰۳ پیش از هر نوشتنی
            # (تراکنش همین‌جا rollback می‌شود ⇒ شاگرد نیمه‌ساخته باقی نمی‌ماند).
            if sub_role == "teacher":
                _teacher = resolve_session_teacher(db, authorization)
                if _teacher is None:
                    raise HTTPException(status_code=403, detail="پروندهٔ معلم شما یافت نشد؛ با آموزشگاه تماس بگیرید")
                if course.teacher_id != _teacher.id:
                    raise HTTPException(status_code=403, detail="شما فقط می‌توانید برای کلاس‌های خودتان دانش‌آموز ثبت کنید")

            # شهریهٔ پایهٔ صفر یعنی دانش‌آموز رایگان/معاف و باید با مسیر
            # /enrollments/add و EnrollmentCreate یک قرارداد داشته باشد؛ فقط منفی نامعتبر است.
            if req.total_tuition is None or req.total_tuition < 0:
                raise HTTPException(status_code=400, detail="شهریه ثبت‌نام نمی‌تواند منفی باشد")
                
            # بررسی تکراری نبودن ثبت‌نام
            # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
            exists = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(
                Enrollment.student_id == new_student.id,
                Enrollment.course_id == req.course_id
            ).first()
            if exists:
                raise HTTPException(status_code=400, detail="این دانش‌آموز قبلاً در این کلاس ثبت شده است")
                
            # اعتبارسنجی تخفیف
            d_type = req.discount_type or "none"
            d_val = req.discount_value or 0
            if d_type == "percentage":
                if d_val < 0 or d_val > 100:
                    raise HTTPException(status_code=400, detail="درصد تخفیف باید بین ۰ و ۱۰۰ باشد")
            elif d_type == "fixed":
                if d_val < 0 or d_val > req.total_tuition:
                    raise HTTPException(status_code=400, detail="مبلغ تخفیف ثابت نمی‌تواند بیشتر از شهریه پایه باشد")
            else:
                d_type = "none"
                d_val = 0
                    
            new_enroll = Enrollment(
                student_id=new_student.id,
                course_id=req.course_id,
                # FIX (F-C2/S3 تکمیلی): شعبه‌ی ثبت‌نام — همان منطق تراکنش (شاگرد، وگرنه کلاس).
                # بدون آن، analytics که با Enrollment.branch_id فیلتر می‌کند (analytics.py:177/185/193)
                # این ثبت‌نام را برای کاربر شعبه‌دار از دست می‌داد (NULL هرگز =شعبه نمی‌شود).
                branch_id=new_student.branch_id if new_student.branch_id is not None else course.branch_id,
                register_date=req.register_date,
                shift=req.shift,
                total_tuition=req.total_tuition,
                total_paid=req.paid_amount,
                discount_type=d_type,
                discount_value=d_val
            )
            db.add(new_enroll)
            db.flush() # تولید آیدی اینرولمنت
            enroll_id = new_enroll.id
            
            # ذخیره فیزیکی اقساط شهریه در صورت ارسال (مقادیر اعتبارسنجی‌شده‌ی مرکزی)
            if normalized_installments:
                for amount, due_date in normalized_installments:
                    db.add(Installment(
                        enrollment_id=new_enroll.id,
                        amount=amount,
                        due_date=due_date,
                        is_paid=False
                    ))
            
            # ثبت تراکنش مالی پرداخت اولیه (در صورت پرداخت وجه)
            if req.paid_amount > 0:
                new_trans = Transaction(
                    enrollment_id=new_enroll.id,
                    student_id=new_student.id,
                    course_id=req.course_id,
                    # FIX (F-C2): branch_id طبق H7 — شعبه‌ی شاگرد، وگرنه شعبه‌ی کلاس.
                    branch_id=new_student.branch_id if new_student.branch_id is not None else course.branch_id,
                    amount=req.paid_amount,
                    payment_method=req.payment_method,
                    date=req.register_date,
                    receiver=req.receiver,
                    description="شارژ کیف پول (ثبت نام اولیه)",
                    type="enrollment_payment"
                )
                db.add(new_trans)
                new_student.wallet_institute += req.paid_amount
                # FIX: Bug 18 - derive the total only through the shared wallet helper.
                new_student.sync_wallet_balance()

        db.commit()
        return {
            "status": "success",
            "message": "دانش‌آموز با موفقیت ثبت‌نام شد" + (" و در کلاس قرار گرفت" if enroll_id else ""),
            "id": new_student.id,
            "enrollment_id": enroll_id
        }
    except Exception as e:
        db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"خطا در ثبت تراکنشی ثبت‌نام: {str(e)}")


@router.get("/students/search")
def search_students(query: str, db: Session = Depends(get_db), sub_role: str = Depends(check_user_login)):
    # FIX (L14/Y1): جستجوی سراسری PII شاگردان — فقط کارکنان (ادمین/منشی/معلم). شاگرد/ولی 403.
    if sub_role not in ("admin", "secretary", "teacher"):
        raise HTTPException(status_code=403, detail="شما دسترسی لازم برای جستجوی دانش‌آموزان را ندارید")
    return (
        db.query(Student).filter(Student.is_deleted == False)
        .filter(
            (Student.last_name.contains(query))
            | (Student.national_code.contains(query))
        )
        .all()
    )


@router.get("/students/search_simple")
def search_students_simple(query: str, authorization: Optional[str] = Header(None), db: Session = Depends(get_db), sub_role: str = Depends(check_user_login)):
    # FIX (L14/Y1): جستجوی سراسری PII شاگردان — فقط کارکنان (ادمین/منشی/معلم). شاگرد/ولی 403.
    if sub_role not in ("admin", "secretary", "teacher"):
        raise HTTPException(status_code=403, detail="شما دسترسی لازم برای جستجوی دانش‌آموزان را ندارید")

    # FIX(search): ورودی را normalize کن (trim + جمع‌فشرده‌کردن فاصله‌های تکراری)؛ خالی/تک‌حرفی
    # → لیست خالی (بدون fetch گسترده).
    q = " ".join(query.split())
    if len(q) < 2:
        return []

    from routers.analytics import get_user_branch_filter
    # FIX(search): branch isolation — کاربر شعبه‌دار فقط شعبه‌ی خودش (شامل عدم دیدن رکوردهای
    # branch=NULL legacy). ادمین بدون شعبه = policy فعلی (دیدن همه). نقش‌های دیگر بدون شعبه
    # scope مشخصی ندارند → نتیجه خالی (نشت داده ممنوع؛ fallback حدسی ممنوع).
    resolved_branch = get_user_branch_filter(db, authorization, None)
    base = db.query(Student).filter(Student.is_deleted == False, Student.is_suspended == False)
    if resolved_branch is not None:
        base = base.filter(Student.branch_id == resolved_branch)
    elif sub_role != "admin":
        return []

    # FIX(search): چندفیلدی + چندکلمه‌ای + case-insensitive سازگار با SQLite/PostgreSQL
    # (func.lower + LIKE). هر کلمه باید حداقل یکی از فیلدها را بدهد (نام کامل = ترکیب
    # کلمات روی first/last). همه‌چیز در WHERE — load کردن دانش‌آموزان در Python ندارد.
    words = q.split()
    conds = []
    for word in words:
        w = f"%{word.lower()}%"
        match = or_(
            func.lower(Student.first_name).like(w),
            func.lower(Student.last_name).like(w),
            func.lower(Student.national_code).like(w),
            func.lower(Student.student_mobile).like(w),
        )
        if word.isdigit():
            # student_code عدد است؛ موبایل هم به‌صورت دقیق (شامل شکل بدون ۰ اول) چک می‌شود
            match = or_(
                match,
                Student.student_code == int(word),
                Student.student_mobile == word,
                *( [Student.student_mobile == "0" + word] if len(word) == 10 and word.startswith("9") else [] ),
            )
        conds.append(match)

    # FIX(search): سقف نتایج — ۲۰ مورد (استقرار پایدار، بدون صفحه‌بندی اضافه)
    results = base.filter(*conds).order_by(desc(Student.id)).limit(20).all()

    return [
        {
            # FIX(search): id فیلد واقعی response است — کلاینت جدید نباید از متن display-id parse کند
            "id": s.id,
            "name": f"{(s.first_name or '').strip()} {(s.last_name or '').strip()}".strip() + (f" ({s.national_code})" if s.national_code else ""),
        }
        for s in results
    ]


@router.post("/grades/submit")
def submit_grade(data: GradeCreate, db: Session = Depends(get_db), authorization: Optional[str] = Header(None), role: str = Depends(require_permission("grade.write"))):
    # پیدا کردن معلم کلاس برای ثبت در دیتابیس
    course = db.query(Course).filter(Course.id == data.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="کلاس یافت نشد")

    # FIX (audit-v2/H-caller): مالکیت معلم، عین الگوی exams.py:create_exam (require_permission در
    # امضای بالا + تطبیق Course.teacher_id) — با تنها دلتای مجاز: گذر ادمین/منشی (الگوی
    # _verify_live_course_teacher)، چون اصلاح نمره توسط ادمین مسیر مشروع اپ است و الگوی
    # teacher-only مرجع، ادمین را می‌شکست (قدم ۴). شاگرد/ولی همین‌جا 403 می‌گیرند.
    if role not in ("admin", "secretary"):
        from routers.reports import get_logged_in_teacher
        logged_teacher = get_logged_in_teacher(db, authorization)
        if not logged_teacher or logged_teacher.id != course.teacher_id:
            raise HTTPException(status_code=403, detail="شما مجاز به ثبت نمره برای این کلاس نیستید")

    new_grade = Grade(
        student_id=data.student_id,
        course_id=data.course_id,
        teacher_id=course.teacher_id,
        exam_title=data.exam_title,
        score=data.score,
        max_score=data.max_score,
        date=data.date,
        description=data.description,
    )
    db.add(new_grade)
    db.commit()

    # Dispatch Notifications to Student and Parent
    st = db.query(Student).filter(Student.id == data.student_id).first()
    if st:
        from dependencies import NotificationService
        if st.user_id is None:
            ensure_student_shadow_users(db, st)
        # 1. Student Notification
        NotificationService.send_notification(
            db=db,
            recipient_user_id=st.user_id,
            recipient_role="student",
            type="grade",
            title=f"📝 ثبت نمره جدید در {course.title}",
            body=f"نمره جدید برای شما ثبت شد: {data.score} از {data.max_score} در آزمون '{data.exam_title}' کلاسی."
        )
        if st.parent_user_id is None:
            ensure_student_shadow_users(db, st)
        # 2. Parent Notification
        NotificationService.send_notification(
            db=db,
            recipient_user_id=st.parent_user_id,
            recipient_role="parent",
            type="grade",
            title=f"📝 ثبت نمره جدید فرزند شما در {course.title}",
            body=f"نمره جدید برای فرزند شما {st.first_name} {st.last_name} ثبت شد: {data.score} از {data.max_score} در آزمون '{data.exam_title}' کلاسی."
        )

    return {"message": "نمره با موفقیت ثبت شد"}


# دریافت کارنامه دانش‌آموز (لیست نمرات)


@router.get("/students/{student_id}/grades")
def get_student_grades(student_id: int, db: Session = Depends(get_db), authorization: Optional[str] = Header(None), role: str = Depends(check_user_login)):
    # FIX (L14/Y1): نمرات هر شاگرد — فقط ادمین/منشی، معلمِ درگیر، خودِ شاگرد/ولیِ همان فرزند.
    check_student_access(student_id, authorization, db, role)
    grades = (
        db.query(Grade)
        .filter(Grade.student_id == student_id)
        .order_by(desc(Grade.id))
        .all()
    )
    
    # Calculate averages
    course_scores = {}
    result_grades = []
    
    for g in grades:
        course = db.query(Course).filter(Course.id == g.course_id).first()
        c_name = course.title if course else "حذف شده"
        
        if c_name not in course_scores:
            course_scores[c_name] = []
        course_scores[c_name].append(g.score)
        
        result_grades.append({
            "course_name": c_name,
            "exam_title": g.exam_title,
            "score": g.score,
            "max_score": g.max_score,
            "date": g.date,
            "description": g.description,
        })
        
    averages = {}
    for c_name, scores in course_scores.items():
        if scores:
            averages[c_name] = round(sum(scores) / len(scores), 2)
            
    return {
        "grades": result_grades,
        "averages": averages
    }


# FIX (تاریخچهٔ جلسات): چهار کلاسِ تکراریِ زیر (ClassReportInfo/ClassStudentData/ClassSessionHistory/
# FullClassReport) سایهٔ نسخهٔ `schemas.py` بودند، هیچ‌جا در این فایل استفاده نمی‌شدند و هیچ روتِ
# full-reportی هم این‌جا وجود ندارد (پیاده‌سازی در `routers/classes.py` است) ⇒ حذف شدند تا
# «یک منبعِ حقیقت» بماند و شکلِ پاسخِ تاریخچهٔ جلسات دو جا واگرا نشود.


@router.get("/students/{student_id}/communication_history")
def get_student_communication_history(
    student_id: int,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    role: str = Depends(check_user_login),
):
    """Combined SMS and internal-message history, without mutating either system."""
    if role not in ("admin", "secretary", "teacher"):
        raise HTTPException(
            status_code=403,
            detail="شما دسترسی لازم برای مشاهده تاریخچه ارتباطات را ندارید",
        )

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="دانش‌آموز یافت نشد")

    viewer_teacher = None
    include_sms = True
    if role == "teacher":
        check_student_access(student_id, authorization, db, role)
        from routers.reports import get_logged_in_teacher

        viewer_teacher = get_logged_in_teacher(db, authorization)
        if not viewer_teacher:
            raise HTTPException(status_code=403, detail="مربی لاگین شده یافت نشد")
        # A teacher sees only conversations in which that teacher is also a
        # participant. SMS/parent financial notices are not exposed to teachers.
        include_sms = False

    from communication_history import build_student_communication_history

    return build_student_communication_history(
        db=db,
        student=student,
        viewer_teacher=viewer_teacher,
        include_sms=include_sms,
    )


# ==========================================
# ۱۱. اندپوینت امن پورتال دانش‌آموزی (Student Portal) - جدید 🆕
# ==========================================
# FIX(C1): سقف اعلان‌های نمایش‌داده‌شده در پورتال دانش‌آموز (جدیدترین‌ها اول).
STUDENT_PORTAL_NOTIFICATIONS_LIMIT = 50


def _student_portal_notifications(db: Session, student: Student) -> list:
    """اعلان‌های واقعیِ خودِ دانش‌آموز (جدیدترین اول) — FIX(C1).

    قبلاً این اندپوینت دو اعلان جعلیِ ثابت برمی‌گرداند («شروع ترم»، «تعطیلی سرما») و
    اعلان‌های واقعی (غیبت، آزمون، پیام‌ها) هرگز به پورتال دانش‌آموز نمی‌رسید.
    فیلتر مثل /notifications: recipient_user_id = کاربرِ سایه‌ی خودِ شاگرد + نقش کانونیکال.
    """
    if not student or not student.user_id:
        return []
    shadow = db.query(User).filter(User.id == student.user_id).first()
    if shadow is None:
        return []
    role = resolve_notification_role(shadow)
    rows = (
        db.query(Notification)
        .filter(Notification.recipient_user_id == shadow.id,
                Notification.recipient_role == role)
        .order_by(Notification.created_at.desc().nullslast(), Notification.id.desc())
        .limit(STUDENT_PORTAL_NOTIFICATIONS_LIMIT)
        .all()
    )
    from today_summary import jalali_date_string  # lazy، مثل بقیه تاریخ‌های شمسی
    return [
        {
            "id": n.id,
            "type": n.type,
            "title": n.title,
            "body": n.body,
            "date": jalali_date_string(n.created_at.date()) if n.created_at else "",
            "is_read": bool(n.is_read),
        }
        for n in rows
    ]


@router.get("/students/my_profile")
def get_student_my_profile(authorization: Optional[str] = Header(None), db: Session = Depends(get_db), _: str = Depends(check_user_login)):
    if not authorization:
        raise HTTPException(status_code=401, detail="توکن احراز هویت یافت نشد")
        
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="قالب توکن معتبر نیست")
        
    token = parts[1]
    session = db.query(UserSession).filter(UserSession.token == token, UserSession.sub_role == "student").first()
    if not session:
        raise HTTPException(status_code=401, detail="نشست شما نامعتبر یا منقضی شده است")
        
    student = get_session_student(db, session)
    if not student:
        raise HTTPException(status_code=404, detail="دانش‌آموز یافت نشد")
    student_id = student.id
        
    # ۱. واکشی کلاس‌ها
    classes = []
    # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
    enrollments = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.student_id == student_id).all()
    for en in enrollments:
        if en.course:
            classes.append(f"{en.course.title} ({en.course.code}) - {en.course.grade_level}")
            
    # ۲. واکشی کارنامه نمرات
    grades_db = db.query(Grade).filter(Grade.student_id == student_id).order_by(desc(Grade.id)).all()
    grades_list = []
    course_scores = {}
    for g in grades_db:
        course = db.query(Course).filter(Course.id == g.course_id).first()
        c_name = course.title if course else "حذف شده"
        
        if c_name not in course_scores:
            course_scores[c_name] = []
        course_scores[c_name].append(g.score)
        
        grades_list.append({
            "course_name": c_name,
            "exam_title": g.exam_title,
            "score": g.score,
            "max_score": g.max_score,
            "date": g.date,
            "description": g.description
        })
        
    averages = {}
    for c_name, scores in course_scores.items():
        if scores:
            averages[c_name] = round(sum(scores) / len(scores), 2)
            
    # ۳. واکشی تاریخچه حضور غیاب‌ها
    # FIX: Bug 14 - exclude archived SessionLog rows from this active view.
    sessions = db.query(SessionLog).filter(SessionLog.is_deleted == False).filter(SessionLog.course_id.in_([en.course_id for en in enrollments if en.course])).all()
    session_map = {s.id: s for s in sessions}
    attendances_db = db.query(Attendance).filter(Attendance.student_id == student_id).all()
    attendance_history = []
    for att in attendances_db:
        sess = session_map.get(att.session_id)
        if sess:
            course = db.query(Course).filter(Course.id == sess.course_id).first()
            c_title = course.title if course else "کلاس حذف شده"
            status_text = "حاضر" if att.status in ["Present", "Late"] else "غایب موجه" if att.excused else "غایب غیرموجه"
            attendance_history.append({
                "date": sess.date,
                "course_title": c_title,
                "status": status_text
            })
            
    # ۴. واکشی وضعیت اقساط شهریه
    # FIX: Bug 13 - exclude archived Installment rows from this active view.
    installments_db = db.query(Installment).filter(Installment.is_deleted == False).filter(Installment.enrollment_id.in_([en.id for en in enrollments])).order_by(Installment.due_date.asc()).all()
    installments_list = []
    for inst in installments_db:
        # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
        enroll = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.id == inst.enrollment_id).first()
        course = db.query(Course).filter(Course.id == enroll.course_id).first() if enroll else None
        c_title = course.title if course else "کلاس حذف شده"
        
        from today_summary import parse_project_date  # FIX H3-B3: same B1 pattern — due_date is Jalali (lazy import)
        today_date = datetime.datetime.now().date()
        _due = parse_project_date(inst.due_date)
        status_text = "پرداخت شده" if inst.is_paid else ("معوقه" if (_due is not None and _due < today_date) else "در انتظار")
        
        installments_list.append({
            "course_title": c_title,
            "amount": inst.amount,
            "due_date": inst.due_date,
            "is_paid": inst.is_paid,
            "status": status_text,
            "paid_at": inst.paid_at or "---"
        })

    # ۵. مبالغ تراز مالی دانش‌آموز
    w_t = student.wallet_teacher if student.wallet_teacher is not None else 0
    w_i = student.wallet_institute if student.wallet_institute is not None else 0
    # FIX: Bug 16 - student/parent financial views must agree with tuition debtor reports.
    total_debt = calculate_student_debt(db, student)

    # ۶. تکالیف، آزمون‌ها، جلسات پیش‌رو و اعلان‌ها
    # FIX(C6): قبلاً این سه لیست برای **هر** دانش‌آموز یک تکلیف و آزمون ساختگی با تاریخ‌های
    # ثابت (۱۴۰۵/۰۶/۰۵ و ۱۴۰۵/۰۶/۱۰) و برنامهٔ هفتگیِ جعلی نشان می‌دادند. حالا همان داده‌ی
    # واقعیِ ثبت‌شده در سیستم خوانده می‌شود (مثل پورتال ولی — یک منبع مشترک).
    portal_activity = build_portal_activity(db, student)
    homework_list = portal_activity["homework"]
    exams_list = portal_activity["exams"]
    upcoming_list = portal_activity["upcoming_sessions"]
    notifications_list = []

    # FIX(C1): اعلان‌های واقعیِ دانش‌آموز از جدول `notifications` (به‌جای دو اعلان جعلیِ ثابت).
    notifications_list = _student_portal_notifications(db, student)

    return {
        "info": {
            "name": f"{student.first_name} {student.last_name}",
            "national_code": student.national_code,
            "student_mobile": student.student_mobile,
            "profile_image": student.profile_image
        },
        "classes": classes,
        "wallet": {
            "balance": student.wallet_balance,
            "total_debt": total_debt
        },
        "grades": grades_list,
        "averages": averages,
        "attendance": sorted(attendance_history, key=lambda x: x["date"], reverse=True),
        "installments": installments_list,
        "homework": homework_list,
        "exams": exams_list,
        "upcoming_sessions": upcoming_list,
        "notifications": notifications_list
    }

# FIX (F-R1): ترتیب ثبت route در FastAPI مهم است — مسیر ثابت «/students/my_profile» باید قبل از
# مسیر داینامیک «/students/{student_id}» ثبت شود؛ وگرنه route داینامیک آن را می‌بلعد و درخواست
# با خطای 422 (int_parsing روی student_id) برمی‌گردد. این بلوک را پایین‌تر از route داینامیک منتقل نکنید.

@router.get("/students/{student_id}")
def get_student_profile(student_id: int, authorization: Optional[str] = Header(None), db: Session = Depends(get_db), role: str = Depends(check_user_login)):
    # FIX (L14/Y1): بازنویسی کامل تله‌ی گارد نصفه — قبلاً فقط معلم چک می‌شد و شاگرد/ولیِ غریبه رد می‌شدند.
    check_student_access(student_id, authorization, db, role)

    student = db.query(Student).filter(Student.id == student_id, Student.is_deleted == False).first()
    if not student:
        raise HTTPException(status_code=404, detail="دانش‌آموز یافت نشد")
    return {
        "id": student.id,
        "first_name": student.first_name,
        "last_name": student.last_name,
        "father_name": student.father_name,
        "national_code": student.national_code,
        "birth_date": student.birth_date,
        "student_mobile": student.student_mobile,
        "parent_mobile": student.parent_mobile,
        "home_phone": student.home_phone,
        "address": student.address,
        "study_status": student.study_status,
        "gender": student.gender,
        "version": student.version if student.version is not None else 1
    }


@router.put("/students/update/{student_id}")
def update_student(student_id: int, data: StudentUpdate, db: Session = Depends(get_db), _: str = Depends(check_admin_or_secretary_access)):
    # استفاده از قفل ردیف دیتابیسی برای امنیت نسخه و تداخل
    # FIX (audit-v2/#15): بدون with_for_update (روی SQLite بی‌اثر است؛ الگوی ممیزی) — این خواندن فقط
    # اعتبارسنجی اولیه است؛ گیت واقعیِ race، UPDATE مشروط روی version پایین است.
    student = db.query(Student).filter(Student.id == student_id, Student.is_deleted == False).first()
    if not student:
        raise HTTPException(status_code=404, detail="دانش‌آموز یافت نشد")

    # بررسی قفل خوش‌بینانه (Optimistic Locking) برای جلوگیری از هم‌پوشانی ویرایش‌ها
    # FIX L11: version اجباری است — حذف آن از درخواست، گارد را دور می‌زد (اپ می‌فرستد، پس سازگار است).
    if data.version is None:
        raise HTTPException(status_code=400, detail="نسخه‌ی رکورد (version) اجباری است؛ ابتدا رکورد را مجدد بخوانید و دوباره تلاش کنید")
    if data.version is not None:
        current_ver = student.version if student.version is not None else 1
        if data.version != current_ver:
            raise HTTPException(
                status_code=409, 
                detail="این اطلاعات توسط شخص دیگری تغییر یافته است. لطفاً صفحه را مجدداً بارگذاری کنید."
            )

    # Validation
    if data.first_name is not None and not data.first_name.strip():
        raise HTTPException(status_code=400, detail="نام نمی‌تواند خالی باشد")
    if data.last_name is not None and not data.last_name.strip():
        raise HTTPException(status_code=400, detail="نام خانوادگی نمی‌تواند خالی باشد")
        
    if data.national_code is not None:
        nc = data.national_code.strip()
        # FIX: Bug 22 - edits must pass the checksum too, not just a length check.
        if not is_valid_iranian_national_code(nc):
            raise HTTPException(status_code=400, detail="کد ملی وارد شده معتبر نیست")
        exists = db.query(Student).filter(Student.national_code == nc, Student.id != student_id).first()
        if exists:
            raise HTTPException(status_code=400, detail="کد ملی وارد شده قبلاً ثبت شده است")
            
    norm_student_mobile = None
    norm_parent_mobile = None
    if data.student_mobile is not None:
        # FIX H20: نرمال‌سازی جایگزین رد خام H1 (خالی مثل قبل 400).
        mob = normalize_mobile(data.student_mobile)
        if not mob:
            raise HTTPException(status_code=400, detail="شماره موبایل باید ۱۰ یا ۱۱ رقم باشد")
        # FIX H20-adjacent: چک یکتایی گمشده‌ی موبایل در ویرایش (الگوی update_teacher).
        exists = db.query(Student).filter(Student.student_mobile == mob, Student.id != student_id).first()
        if exists:
            raise HTTPException(status_code=400, detail="شماره موبایل وارد شده قبلاً ثبت شده است")
        norm_student_mobile = mob
            
    if data.parent_mobile is not None:
        # FIX H20: نرمال‌سازی؛ خالی مثل قبل مجاز و دست‌نخورده (بدون چک یکتایی — مشترک بین خواهر/برادر).
        _raw_pm = (data.parent_mobile or "").strip()
        mob = normalize_mobile(_raw_pm) if _raw_pm else ""
        if _raw_pm and not mob:
            raise HTTPException(status_code=400, detail="شماره موبایل والدین باید ۱۰ یا ۱۱ رقم باشد")
        norm_parent_mobile = mob

    # FIX (audit-v2/#15): نوشتن با UPDATE مشروط روی version (الگوی ممیزی with_for_update) — گیت خواندن
    # بالا فقط fail-fast است؛ اگر ویرایش موازی بین خواندن و نوشتن کامیت شده باشد، version حرکت کرده و
    # این rowcount صفر می‌دهد → 409 (قبلاً lost-update ساکت بود چون قفل روی SQLite بی‌اثر است).
    update_data = data.dict(exclude_unset=True)
    _update = {}
    for key, value in update_data.items():
        if key == "version":
            continue
        if key not in Student.__table__.c:  # دفاعی: کلید غیرستونی (مثل قبل) نادیده، نه 500.
            continue
        _update[getattr(Student, key)] = value.strip() if (value is not None and isinstance(value, str)) else value
    # FIX H20: مقادیر نرمال جایگزین strip خام (حفظ شد).
    if norm_student_mobile is not None:
        _update[Student.student_mobile] = norm_student_mobile
    if norm_parent_mobile is not None:
        _update[Student.parent_mobile] = norm_parent_mobile
    _update[Student.version] = data.version + 1  # گیت بالا data.version == خوانده‌شده را تضمین کرده (None→2 مثل قبل).
    _rows = (
        db.query(Student)
        .filter(Student.id == student_id, Student.is_deleted == False, func.coalesce(Student.version, 1) == data.version)
        .update(_update, synchronize_session=False)
    )
    if _rows != 1:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="این اطلاعات توسط شخص دیگری تغییر یافته است. لطفاً صفحه را مجدداً بارگذاری کنید.",
        )

    db.commit()
    return {"message": "اطلاعات دانش‌آموز با موفقیت بروزرسانی شد"}


@router.post("/students/{id}/upload_photo")
async def upload_student_photo(id: int, file: UploadFile = File(...), db: Session = Depends(get_db), authorization: Optional[str] = Header(None), sub_role: str = Depends(check_user_login)):
    student = db.query(Student).filter(Student.id == id, Student.is_deleted == False).first()
    if not student:
        raise HTTPException(status_code=404, detail="دانش‌آموز یافت نشد")
    # FIX M25-IDOR: فقط ادمین/منشی یا خودِ دانش‌آموز.
    if sub_role not in ("admin", "secretary"):
        if sub_role != "student":
            raise HTTPException(status_code=403, detail="شما مجاز به تغییر عکس این دانش‌آموز نیستید")
        from dependencies import get_session_from_token  # lazy
        _parts = (authorization or "").split()
        _tok = _parts[1] if len(_parts) == 2 and _parts[0].lower() == "bearer" else None
        _sess, _ = get_session_from_token(db, _tok) if _tok else (None, None)
        _own = get_session_student(db, _sess) if _sess is not None else None
        if _own is None or _own.id != id:
            raise HTTPException(status_code=403, detail="شما مجاز به تغییر عکس این دانش‌آموز نیستید")
        
    # Read file and validate size
    MAX_SIZE = 5 * 1024 * 1024 # 5 MB
    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="حجم فایل نباید بیشتر از ۵ مگابایت باشد")
        
    # FIX M25: پسوند + magic bytes (فایل غیرعکس با پسوند جعلی رد می‌شود).
    file_ext = validate_image_upload(file.filename, contents)
        
    # Generate unique filename
    unique_filename = f"{uuid.uuid4().hex}{file_ext}"
    filepath = os.path.join(storage_dir("profiles"), unique_filename)
    
    # Write to disk
    with open(filepath, "wb") as f_out:
        f_out.write(contents)
        
    # Delete old file
    if student.profile_image:
        # پاک‌کردن فایل قبلی — حتی اگر در مسیر قدیمی (نسبت به cwd) مانده باشد
        old_path = resolve_existing("profiles", student.profile_image)
        if old_path:
            try:
                os.remove(old_path)
            except Exception:
                pass
                
    student.profile_image = unique_filename
    db.commit()
    
    return {
        "message": "عکس پروفایل دانش‌آموز با موفقیت آپلود شد",
        "profile_image": unique_filename,
        "url": f"uploads/profiles/{unique_filename}"
    }


@router.get("/students/{student_id}/installments")
def get_student_installments(student_id: int, db: Session = Depends(get_db), authorization: Optional[str] = Header(None), role: str = Depends(check_user_login)):
    # FIX (L14/Y1): اقساط هر شاگرد — فقط ادمین/منشی، معلمِ درگیر، خودِ شاگرد/ولیِ همان فرزند.
    check_student_access(student_id, authorization, db, role)
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="دانش‌آموز یافت نشد")
        
    # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
    enrollments = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.student_id == student_id).all()
    enrollment_ids = [e.id for e in enrollments]
    
    if not enrollment_ids:
        return []
        
    # FIX: Bug 13 - exclude archived Installment rows from this active view.
    installments = db.query(Installment).filter(Installment.is_deleted == False).filter(Installment.enrollment_id.in_(enrollment_ids)).order_by(Installment.due_date.asc()).all()
    
    result = []
    for inst in installments:
        # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
        enroll = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.id == inst.enrollment_id).first()
        course = db.query(Course).filter(Course.id == enroll.course_id).first() if enroll else None
        c_title = course.title if course else "کلاس حذف شده"
        result.append({
            "id": inst.id,
            "course_title": c_title,
            "amount": inst.amount,
            "due_date": inst.due_date,
            "is_paid": inst.is_paid,
            "paid_at": inst.paid_at or "---"
        })
    return result


@router.post("/admin/students/{id}/send_portal_link")
def send_portal_link(id: int, db: Session = Depends(get_db), _: str = Depends(check_admin_or_secretary_access)):
    # این متد برای ادمین و منشی مجاز است (تصمیم کاربر برای C1)
    student = db.query(Student).filter(Student.id == id, Student.is_deleted == False).first()
    if not student:
        raise HTTPException(status_code=404, detail="دانش‌آموز یافت نشد")
        
    if not student.parent_mobile:
        raise HTTPException(status_code=400, detail="شماره همراه ولی برای این دانش‌آموز ثبت نشده است")
        
    # شبیه‌سازی ارسال واقعی پیامک حاوی لینک اختصاصی پورتال
    from models import InstituteSettings
    settings = db.query(InstituteSettings).first()
    inst_name = settings.name if (settings and settings.name) else "خوارزمی"
    
    today = datetime.datetime.now().strftime("%Y/%m/%d %H:%M")
    public_server_url = os.getenv("PUBLIC_SERVER_URL", "http://192.168.1.5:8000")
    public_portal_url = f"{public_server_url}/parent/portal"
    msg = f"ولی محترم دانش‌آموز {student.first_name} {student.last_name}، جهت مشاهده زنده حضور و غیاب، نمرات و وضعیت اقساط شهریه فرزند خود، به پورتال اولیا {inst_name} مراجعه فرمایید: {public_portal_url}"
    
    db.add(SmsLog(
        target_group=f"portal_link_{student.id}",
        message_text=msg,
        sent_count=1,
        date=today
    ))
    db.commit()
    
    return {"message": "لینک پورتال با موفقیت پیامک شد."}

