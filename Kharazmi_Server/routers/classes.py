from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Header
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional, Union
from sqlalchemy import desc, or_, text, func
import io
import json
import uuid
import os
import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from fastapi.responses import StreamingResponse

import models
from models import (
    Attendance, Course, Enrollment, Grade, InstituteShare, SessionLog, SmsLog, Student, Teacher, Transaction, User, UserSession, Installment, ActivityLog
)
from schemas import (
    HistoryRequest, LoginRequest, TeacherInfo, FullTeacherProfile, StudentCreate, TeacherCreate, CourseCreate, EnrollmentCreate, BulkEnrollmentCreate, GradeCreate, GradeItem, AttendanceLogRequest, AttendanceItem, AttendanceSubmitData, SmsSendRequest, ChangePasswordRequest, StudentProfileInfo, FullStudentProfile, TeacherProfileInfo, FullTeacherProfile, ClassReportInfo, ClassStudentData, ClassSessionHistory, ClassSessionStudent, FullClassReport, ShareConfigModel, StudentUpdate, TeacherUpdate, PersonListItem, TransactionUpdate, StudentAttendanceHistoryRequest, AdvancedSearchItem, FinanceSubmitData, PrintReceiptRequest, TransactionTestData
)
from dependencies import (get_db, check_admin_access, check_admin_or_secretary_access,
                            check_admin_secretary_or_teacher_access, resolve_session_teacher,
                            check_user_login, get_enrollment_tuition_and_discount,
                            SESSION_EXPIRY_DAYS, display_name, safe_person_name)

# FIX: Bug 16 - share the tuition-minus-payment debt calculation across financial views.
from financial_calculations import (
    calculate_enrollment_debt_breakdown,
    session_fields_for_client,
    MAX_TEACHER_SESSION_PRICE,
)
# FIX (F-T1): اعتبارسنجی مرکزی اقساط — همان قاعده‌ی مسیر مستقل قسط، برای مسیر ثبت‌نام همراه اقساط.
from validation import normalize_installments

router = APIRouter()

def parse_time_to_minutes(time_str):
    # E.g. "16:00-17:30" or "16:00" or "16"
    try:
        time_str = time_str.strip().replace(" ", "")
        if "-" in time_str:
            parts = time_str.split("-")
            start_str = parts[0]
            end_str = parts[1]
        else:
            start_str = time_str
            end_str = None
            
        def to_min(t_s):
            if ":" in t_s:
                h, m = t_s.split(":")
                return int(h) * 60 + int(m)
            else:
                return int(t_s) * 60
                
        start_m = to_min(start_str)
        if end_str:
            end_m = to_min(end_str)
        else:
            end_m = start_m + 90 # پیش‌فرض ۹۰ دقیقه برای جلسه کلاسی تک‌ساعته
        return start_m, end_m
    except Exception:
        return None

def days_overlap(day1, day2):
    day1 = day1.strip()
    day2 = day2.strip()
    if day1 == day2:
        return True
        
    even_days = {"شنبه", "دوشنبه", "چهارشنبه", "زوج"}
    odd_days = {"یکشنبه", "سه‌شنبه", "پنج‌شنبه", "فرد"}
    
    if day1 in even_days and day2 in even_days:
        if day1 == "زوج" or day2 == "زوج" or day1 == day2:
            return True
    if day1 in odd_days and day2 in odd_days:
        if day1 == "فرد" or day2 == "فرد" or day1 == day2:
            return True
            
    return False

@router.post("/classes/create")
def create_class(course: CourseCreate, override: bool = False, db: Session = Depends(get_db), authorization: Optional[str] = Header(None), sub_role: str = Depends(check_user_login)):
    # FIX (audit-v2/blind-approve-2a): ساخت کلاس فقط ادمین/منشی/معلم — شاگرد/ولی 403.
    # معلم فقط برای خودش (teacher_id اجباری، ورودی کلاینت نادیده) و با سقف نرخ؛ ادمین/منشی
    # معاف از سقف‌اند چون آگاهانه ثبت می‌کنند (approve بالای سقف جداگانه هشدار می‌دهد).
    if sub_role not in ("admin", "secretary"):
        from routers.reports import get_logged_in_teacher
        me = get_logged_in_teacher(db, authorization)
        if not me:
            raise HTTPException(status_code=403, detail="فقط ادمین، منشی یا معلم می‌تواند کلاس تعریف کند")
        course.teacher_id = me.id
        if (course.teacher_session_price or 0) > MAX_TEACHER_SESSION_PRICE:
            raise HTTPException(status_code=400, detail=f"نرخ هر جلسه برای هر شاگرد نمی‌تواند بیشتر از {MAX_TEACHER_SESSION_PRICE:,} تومان باشد؛ برای نرخ بالاتر با ادمین هماهنگ کنید")
    from dependencies import get_next_sequence_value, get_current_user, resolve_creation_branch
    next_code = str(get_next_sequence_value(db, "class", 100001))

    # FIX(branch): کلاس جدید باید branch معتبر داشته باشد — سیاست مرکزی resolve_creation_branch:
    # معلم → فقط branch خودش (ارزش ارسالی کلاینت برای معلم هرگز کورکورانه قبول نمی‌شود)؛
    # ادمین/منشی → branch خودشان یا branch صریحِ مجاز؛ حالت مبهم → 400 واضح.
    if sub_role not in ("admin", "secretary"):
        branch_id = resolve_creation_branch(db, teacher=me, requested_branch_id=course.branch_id)
    else:
        current_user = get_current_user(authorization, db)
        branch_id = resolve_creation_branch(db, user=current_user, requested_branch_id=course.branch_id)

    course_data = course.dict()
    course_data["code"] = next_code
    course_data["branch_id"] = branch_id
    # قرارداد legacy حفظ می‌شود: هر کلاس تازه تا تصمیم صریح approve در صف می‌ماند؛
    # تفاوت جدید فقط metadata صف و علت رد است، نه تغییر وضعیت مالی/تأیید قبلی.
    course_data["is_admin_approved"] = False
    course_data["pending_since"] = datetime.datetime.utcnow()
    course_data["rejection_reason"] = None

    if not override:
        # بررسی تداخل زمانی کلاس‌های غیرمعلق همین معلم
        teacher_courses = db.query(Course).filter(Course.teacher_id == course.teacher_id, Course.is_suspended == False).all()
        for tc in teacher_courses:
            if days_overlap(tc.days_of_week, course.days_of_week):
                time1 = parse_time_to_minutes(tc.class_time)
                time2 = parse_time_to_minutes(course.class_time)
                if time1 and time2:
                    start1, end1 = time1
                    start2, end2 = time2
                    if start1 < end2 and start2 < end1:
                        # تداخل شناسایی شد! فرستادن هشدار به ادمین کلاینت
                        return {
                            "status": "warning",
                            "message": f"⚠️ تداخل زمانی با کلاس '{tc.title}' در روز '{tc.days_of_week}' ساعت '{tc.class_time}' شناسایی شد.",
                            "clash_course": {
                                "title": tc.title,
                                "days": tc.days_of_week,
                                "time": tc.class_time
                            }
                        }

    new_course = Course(**course_data)
    db.add(new_course)
    db.commit()
    return {
        "status": "success",
        "message": "کلاس تعریف شد", 
        "id": new_course.id,
        "code": next_code
    }


@router.get("/classes/list")
def get_all_classes(
    teacher_name: Optional[str] = None,
    student_name: Optional[str] = None,
    course_name: Optional[str] = None,
    grade_level: Optional[str] = None,
    start_year: Optional[str] = None,
    db: Session = Depends(get_db), 
    _: str = Depends(check_admin_or_secretary_access)  # FIX (L14/Y3): کاتالوگ+بدهی کلاس‌ها — فقط کارکنان (تک‌مصرف: ClassManagement)
):
    # پایش فیلترهای چندگانه جستجو (Multi-part advanced search)
    q = db.query(Course).filter(Course.is_deleted == False)
    
    if teacher_name:
        search_t = f"%{teacher_name}%"
        q = q.join(Teacher).filter(
            or_(
                Teacher.first_name.ilike(search_t),
                Teacher.last_name.ilike(search_t)
            )
        )
        
    if student_name:
        search_s = f"%{student_name}%"
        # FIX: Bug 13 - class search must not treat archived enrollments as current membership.
        q = q.join(Enrollment).join(Student).filter(
            Enrollment.is_deleted == False,
            or_(
                Student.first_name.ilike(search_s),
                Student.last_name.ilike(search_s)
            )
        )
        
    if course_name:
        q = q.filter(Course.title.ilike(f"%{course_name}%"))
        
    if grade_level:
        q = q.filter(Course.grade_level.ilike(f"%{grade_level}%"))
        
    if start_year:
        # FIX: Bug 13 - year-based searches use active enrollments too.
        q = q.join(Enrollment).filter(Enrollment.is_deleted == False, Enrollment.register_date.like(f"{start_year}%"))

    courses = q.order_by(desc(Course.id)).all()
    result = []

    for c in courses:
        # 1. Get Teacher Name
        teacher = db.query(Teacher).filter(Teacher.id == c.teacher_id).first()
        t_name = display_name(teacher, "نامشخص")

        # 2. Get Top 10 Students for Preview (Updated from 3 to 10)
        enrollments = (
            # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
            db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.course_id == c.id).limit(10).all()
        )
        student_names = []
        for en in enrollments:
            st = db.query(Student).filter(Student.id == en.student_id, Student.is_deleted == False).first()
            if st:
                student_names.append(display_name(st, "نامشخص"))

        # 3. Calculate debt for the class
        total_debt = 0
        debt_to_teacher = 0
        debt_to_institute = 0
        total_paid = 0
        paid_to_teacher = 0
        paid_to_institute = 0
        # فقط اطلاع‌رسانی برای بنر: «بدهی بابت چند جلسهٔ همین کلاس» (روی هیچ محاسبهٔ مالی اثر ندارد).
        unpaid_sessions_total = 0
        sessions_billed_total = 0

        # Get all students in this class
        all_enrollments = (
            # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
            db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.course_id == c.id).all()
        )

        print(f"\n=== کلاس {c.id} - {c.title} ===")
        print(f"تعداد دانش‌آموزان: {len(all_enrollments)}")

        for en in all_enrollments:
            st = db.query(Student).filter(Student.id == en.student_id, Student.is_deleted == False).first()
            if st:
                # کیف‌های Student سراسری‌اند؛ برای بنر کلاس فقط breakdown همین enrollment
                # مجاز است. کیف کل فقط در لاگ تشخیصی حفظ می‌شود و در اعداد کلاس وارد نمی‌شود.
                breakdown = calculate_enrollment_debt_breakdown(db, en)
                student_debt_teacher = breakdown["debt_teacher"]
                student_debt_institute = breakdown["debt_institute"]
                student_paid_teacher = breakdown["paid_teacher"]
                student_paid_institute = breakdown["paid_institute"]

                print(
                    f"  دانش‌آموز {st.id}: class_paid_teacher={student_paid_teacher}, "
                    f"class_paid_institute={student_paid_institute}"
                )
                print(
                    f"    بدهی همین کلاس به معلم: {student_debt_teacher}, "
                    f"به آموزشگاه: {student_debt_institute}"
                )

                debt_to_teacher += student_debt_teacher
                debt_to_institute += student_debt_institute
                total_debt += breakdown["debt"]
                unpaid_sessions_total += int(breakdown.get("unpaid_sessions", 0) or 0)
                sessions_billed_total += int(breakdown.get("sessions_billed", 0) or 0)
                paid_to_teacher += student_paid_teacher
                paid_to_institute += student_paid_institute
                total_paid += student_paid_teacher + student_paid_institute

        print(
            f"مجموع بدهی کلاس: {total_debt} (معلم: {debt_to_teacher}, آموزشگاه: {debt_to_institute})"
        )
        print(
            f"مجموع پرداختی کلاس: {total_paid} (معلم: {paid_to_teacher}, آموزشگاه: {paid_to_institute})"
        )

        # 4. Get actual session count from session_logs
        session_count = (
            # FIX: Bug 14 - exclude archived SessionLog rows from this active view.
            db.query(SessionLog).filter(SessionLog.is_deleted == False).filter(SessionLog.course_id == c.id).count()
        )

        print(f"تعداد جلسات برگزار شده: {session_count}")

        # 5. Add to result
        result.append(
            {
                "id": c.id,
                "title": c.title,
                "code": c.code,
                "grade_level": c.grade_level,
                "gender": c.gender_type,
                "teacher_id": c.teacher_id,
                "teacher_name": t_name,
                "students_preview": student_names,
                "session_count": session_count,
                "total_debt": total_debt,
                "debt_to_teacher": debt_to_teacher,
                "debt_to_institute": debt_to_institute,
                "total_paid": total_paid,
                "paid_to_teacher": paid_to_teacher,
                "paid_to_institute": paid_to_institute,
                "unpaid_sessions": unpaid_sessions_total,
                "sessions_billed": sessions_billed_total,
                # این ردیف aggregate کلاس است؛ enrollment_id عمداً null می‌ماند.
                "enrollment_id": None,
                "course_id": c.id,
                "course_title": c.title,
                "is_unassigned": False,
                "is_suspended": c.is_suspended if c.is_suspended is not None else False,
            }
        )

    return result


@router.get("/classes/{course_id}/details")
def get_class_details(course_id: int, db: Session = Depends(get_db), authorization: Optional[str] = Header(None), sub_role: str = Depends(check_user_login)):
    # FIX (E2E-B5): کلاس آرشیوی مثل ناموجود است — 404 به‌جای برگرداندن دیتای آرشیوشده (الگوی add_enrollment).
    course = db.query(Course).filter(Course.id == course_id, Course.is_deleted == False).first()
    if not course:
        raise HTTPException(status_code=404, detail="کلاس یافت نشد")
    # FIX (L14/Y3): گزارش کلاس — ادمین/منشی + معلمِ مالک کلاس (الگوی audit-v2/#11). شاگرد/ولی 403.
    if sub_role not in ("admin", "secretary"):
        if sub_role != "teacher":
            raise HTTPException(status_code=403, detail="شما مجاز به مشاهده اطلاعات این کلاس نیستید")
        from routers.reports import get_logged_in_teacher  # lazy (جلوگیری از import چرخه‌ای)
        _me = get_logged_in_teacher(db, authorization)
        if not _me or course.teacher_id != _me.id:
            raise HTTPException(status_code=403, detail="شما مجاز به مشاهده اطلاعات این کلاس نیستید")
    class_teacher = db.query(Teacher).filter(Teacher.id == course.teacher_id).first()
    class_teacher_name = display_name(class_teacher, "نامشخص")
    # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
    enrollments = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.course_id == course_id).all()
    students_list = []
    for enroll in enrollments:
        st = db.query(Student).filter(Student.id == enroll.student_id, Student.is_deleted == False).first()
        if not st:
            continue
        final_tuition, discount_amt = get_enrollment_tuition_and_discount(enroll)
        breakdown = calculate_enrollment_debt_breakdown(db, enroll)
        students_list.append(
            {
                # FIX(null-data): نام‌های legacy NULL → فال‌بک نمایشی امن (نه «None None»).
                "student_name": f"{st.first_name or ''} {st.last_name or ''}".strip() or "نامشخص",
                "student_id": st.id,
                "student_code": st.student_code,
                "total_tuition": final_tuition,
                "paid": breakdown["paid_teacher"] + breakdown["paid_institute"],
                "paid_teacher": breakdown["paid_teacher"],
                "paid_institute": breakdown["paid_institute"],
                "debt": breakdown["debt"],
                "debt_teacher": breakdown["debt_teacher"],
                "debt_institute": breakdown["debt_institute"],
                "enrollment_id": enroll.id,
                "course_id": course.id,
                "course_title": course.title,
                "teacher_id": course.teacher_id,
                "teacher_name": class_teacher_name,
                "is_unassigned": False,
                "discount_type": getattr(enroll, "discount_type", "none") or "none",
                "discount_value": getattr(enroll, "discount_value", 0) or 0,
                "discount_amount": discount_amt
            }
        )
    return {"course_info": course, "students": students_list}


@router.post("/classes/{course_id}/suspend")
def suspend_class(course_id: int, db: Session = Depends(get_db), _: str = Depends(check_admin_or_secretary_access)):  # FIX H10-S: تعلیق فقط ادمین/منشی (الگوی C1)
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="کلاس یافت نشد")

    # تغییر وضعیت تعلیق (اگر True بود False میشه و برعکس)
    course.is_suspended = not course.is_suspended
    db.commit()

    status_text = "معلق (غیرفعال)" if course.is_suspended else "فعال"
    return {
        "message": f"وضعیت کلاس به {status_text} تغییر کرد.",
        "is_suspended": course.is_suspended,
    }


@router.post("/admin/classes/{course_id}/suspend_s")
def suspend_class_admin(course_id: int, db: Session = Depends(get_db), _: str = Depends(check_admin_or_secretary_access)):  # FIX H10-S: تعلیق فقط ادمین/منشی (الگوی C1)
    """
    endpoint مخصوص ادمین برای تعلیق/فعال‌سازی کلاس (دکمه S)
    کلاس را معلق می‌کند یا فعال می‌سازد و برای معلم غیرفعال/فعال می‌شود
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="کلاس یافت نشد")

    # تغییر وضعیت تعلیق (toggle)
    course.is_suspended = not course.is_suspended
    db.commit()

    status_text = "معلق (غیرفعال)" if course.is_suspended else "فعال"
    return {
        "message": f"وضعیت کلاس به {status_text} تغییر کرد.",
        "is_suspended": course.is_suspended,
    }


@router.post("/enrollments/add")
def add_enrollment(
    data: EnrollmentCreate,
    db: Session = Depends(get_db),
    sub_role: str = Depends(check_admin_secretary_or_teacher_access),
    authorization: Optional[str] = Header(None),
):
    # FIX O-22: معلم هم می‌تواند برای **کلاس خودش** دانش‌آموز اضافه کند (قبلاً ۴۰۳ می‌گرفت و کلاس
    # تازه‌ساخته‌اش خالی می‌ماند). دامنهٔ معلم دو خط پایین‌تر روی همان کلاس قفل می‌شود؛ منطق
    # مالی هیچ تغییری ندارد.
    # اعتبارسنجی وجود دانش‌آموز و کلاس (جلوگیری از رکورد یتیم)
    student = db.query(Student).filter(Student.id == data.student_id, Student.is_deleted == False).first()
    if not student:
        raise HTTPException(status_code=404, detail="دانش‌آموز یافت نشد")
    # FIX H10: دانش‌آموز معلق، ثبت‌نام جدید نمی‌شود.
    if student.is_suspended:
        raise HTTPException(status_code=403, detail="این دانش‌آموز در حال حاضر معلق است و ثبت‌نام جدید امکان‌پذیر نیست")
    # FIX H10: کلاس آرشیوی مثل ناموجود است (404 پایین) — قبلاً اصلاً چک نمی‌شد.
    course = db.query(Course).filter(Course.id == data.course_id, Course.is_deleted == False).first()
    if not course:
        raise HTTPException(status_code=404, detail="کلاس مورد نظر یافت نشد")
    # FIX O-22: معلم فقط در کلاس‌های خودش؛ هر کلاس دیگری (حتی موجود) ⇒ ۴۰۳ بدون هیچ نوشتنی.
    # ترتیب عمدی: اول ۴۰۴ «ناموجود/آرشیوی» بعد ۴۰۳ «مالِ دیگری» — مثل سیاست H10.
    if sub_role == "teacher":
        _teacher = resolve_session_teacher(db, authorization)
        if _teacher is None:
            raise HTTPException(status_code=403, detail="پروندهٔ معلم شما یافت نشد؛ با آموزشگاه تماس بگیرید")
        if course.teacher_id != _teacher.id:
            raise HTTPException(status_code=403, detail="شما فقط می‌توانید در کلاس‌های خودتان دانش‌آموز ثبت‌نام کنید")
    # FIX H10: ثبت‌نام جدید در کلاس معلق ممنوع.
    if course.is_suspended:
        raise HTTPException(status_code=403, detail="این کلاس در حال حاضر معلق است و ثبت‌نام جدید امکان‌پذیر نیست")
    if course.is_paused:
        raise HTTPException(status_code=403, detail="این کلاس موقتاً متوقف است و ثبت‌نام جدید امکان‌پذیر نیست")

    # چک تکراری نبودن
    exists = (
        # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
        db.query(Enrollment).filter(Enrollment.is_deleted == False)
        .filter(
            Enrollment.student_id == data.student_id,
            Enrollment.course_id == data.course_id,
        )
        .first()
    )
    if exists:
        raise HTTPException(
            status_code=400, detail="این دانش‌آموز قبلاً در این کلاس ثبت شده است"
        )

    # Validation of discount
    d_type = data.discount_type or "none"
    d_val = data.discount_value or 0

    if d_type == "percentage":
        if d_val < 0 or d_val > 100:
            raise HTTPException(status_code=400, detail="درصد تخفیف باید بین ۰ و ۱۰۰ باشد")
    elif d_type == "fixed":
        if d_val < 0 or d_val > data.total_tuition:
            raise HTTPException(status_code=400, detail="مبلغ تخفیف ثابت نمی‌تواند بیشتر از شهریه پایه باشد")
    else:
        d_type = "none"
        d_val = 0

    # FIX (F-T1): اقساط همین‌جا و پیش از هر نوشتنی با قاعده‌ی مرکزی سنجیده می‌شوند تا
    # مسیر «ثبت‌نام همراه اقساط» و مسیر مستقل قسط رفتار یکسان داشته باشند. schema همین قاعده را
    # در مرز HTTP اجرا می‌کند (۴۲۲)؛ این لایه برای فراخوان‌های داخلی/آینده است ⇒ ۴۰۰ مثل بقیه‌ی
    # اعتبارسنجی‌های همین اندپوینت (تخفیف) و اعتبارسنجی مبلغ در pay_installment_manually.
    try:
        normalized_installments = normalize_installments(data.installments)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # FIX S3: Enrollment.branch_id همان منطق Transaction.branch_id (student.branch_id وگرنه course.branch_id) — قبلاً همیشه NULL می‌ماند
    new_enroll = Enrollment(
        student_id=data.student_id,
        course_id=data.course_id,
        branch_id=student.branch_id if student.branch_id is not None else course.branch_id,
        register_date=data.register_date,
        shift=data.shift,
        total_tuition=data.total_tuition,
        total_paid=data.paid_amount,
        discount_type=d_type,
        discount_value=d_val
    )
    db.add(new_enroll)
    db.flush() # جهت تولید آیدی ثبت‌نام کلاسی

    # ذخیره فیزیکی اقساط شهریه در صورت ارسال از کلاینت (مقادیر اعتبارسنجی‌شده‌ی مرکزی)
    if normalized_installments:
        for amount, due_date in normalized_installments:
            db.add(Installment(
                enrollment_id=new_enroll.id,
                amount=amount,
                due_date=due_date,
                is_paid=False
            ))

    # 💰 منطق جدید مالی: واریز به کیف پول
    if data.paid_amount > 0:
        from dependencies import get_next_sequence_value  # lazy، مثل submit_payment
        # FIX (F-C1): تک‌کامیت — new_enroll.id بعد از flush موجود است پس enrollment_id همان‌جا
        # ست می‌شود (کامیت دوم و ریسک یتیم‌شدن لینک حذف شد) + branch_id طبق H7 (شاگرد، وگرنه
        # کلاس) + شماره‌ی حواله از همان شمارنده‌ی submit_payment (Bug 11).
        new_trans = Transaction(
            enrollment_id=new_enroll.id,
            student_id=data.student_id,
            course_id=data.course_id,
            branch_id=student.branch_id if student.branch_id is not None else course.branch_id,
            amount=data.paid_amount,
            payment_method=data.payment_method,
            date=data.register_date,
            receiver=data.receiver,
            description="شارژ کیف پول (ثبت نام)",
            type="enrollment_payment",  # اضافه کردن نوع برای شناسایی بهتر
            target_wallet="institute",
            remittance_number=get_next_sequence_value(db, "remittance_institute", 100001),
        )
        db.add(new_trans)

        # شارژ حساب دانش‌آموز
        st = db.query(Student).filter(Student.id == data.student_id).first()
        # FIX: Bug 18 - book initial credit in the institute wallet, as the other registration paths do.
        st.wallet_institute = (st.wallet_institute or 0) + data.paid_amount
        st.sync_wallet_balance()

    db.commit()

    return {
        "message": "ثبت نام انجام شد و حساب شارژ شد",
        "enrollment_id": new_enroll.id,
    }


@router.post("/enrollments/add_bulk")
def add_enrollments_bulk(
    data: BulkEnrollmentCreate,
    db: Session = Depends(get_db),
    sub_role: str = Depends(check_admin_secretary_or_teacher_access),
    authorization: Optional[str] = Header(None),
):
    """افزودن چندتایی با reuse کامل مسیر تکی و گزارش موفق/ردشده برای هر شناسه."""
    added_student_ids = []
    rejected = []
    for student_id in data.student_ids:
        try:
            # ساخت schema تکی عمداً validationهای مسیر /enrollments/add را حفظ می‌کند.
            single_data = EnrollmentCreate(
                student_id=student_id,
                course_id=data.course_id,
                register_date=data.register_date,
                shift=data.shift,
                total_tuition=data.total_tuition,
                paid_amount=data.paid_amount,
                payment_method=data.payment_method,
                receiver=data.receiver,
                discount_type=data.discount_type,
                discount_value=data.discount_value,
                installments=data.installments,
            )
            add_enrollment(single_data, db=db, sub_role=sub_role, authorization=authorization)
            added_student_ids.append(student_id)
        except HTTPException as exc:
            db.rollback()
            detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            rejected.append({"student_id": student_id, "reason": detail})
        except Exception:
            # خطای یک شاگرد نباید موفقیت قبلی‌ها را rollback کند؛ commit مسیر تکی مستقل است.
            db.rollback()
            rejected.append({"student_id": student_id, "reason": "خطای غیرمنتظره هنگام ثبت"})

    added_count = len(added_student_ids)
    rejected_count = len(rejected)
    return {
        "message": f"{added_count} اضافه شد، {rejected_count} رد شد",
        "added_count": added_count,
        "rejected_count": rejected_count,
        "added_student_ids": added_student_ids,
        "rejected": rejected,
    }


@router.delete("/enrollments/{enrollment_id}")
def delete_enrollment(enrollment_id: int, db: Session = Depends(get_db), _: str = Depends(check_admin_access)):
    # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
    enrollment = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.id == enrollment_id).first()
    if not enrollment:
        raise HTTPException(
            status_code=404, detail="این دانش‌آموز در این کلاس ثبت نام نشده است"
        )

    from dependencies import perform_delete_enrollment
    perform_delete_enrollment(enrollment, db)
    db.commit()
    return {"message": "دانش‌آموز از کلاس حذف شد و حساب‌ها اصلاح گردید."}


@router.get("/classes/{id}/full_report")
def get_class_full_report(id: int, db: Session = Depends(get_db), authorization: Optional[str] = Header(None), sub_role: str = Depends(check_user_login)):
    # 1. اطلاعات پایه کلاس و معلم
    # FIX (E2E-B5): دوقلوی هم‌الگو — کلاس آرشیوی 404.
    course = db.query(Course).filter(Course.id == id, Course.is_deleted == False).first()
    if not course:
        raise HTTPException(status_code=404, detail="کلاس یافت نشد")
    # FIX (L14/Y3): گزارش کلاس — ادمین/منشی + معلمِ مالک کلاس (الگوی audit-v2/#11). شاگرد/ولی 403.
    if sub_role not in ("admin", "secretary"):
        if sub_role != "teacher":
            raise HTTPException(status_code=403, detail="شما مجاز به مشاهده اطلاعات این کلاس نیستید")
        from routers.reports import get_logged_in_teacher  # lazy (جلوگیری از import چرخه‌ای)
        _me = get_logged_in_teacher(db, authorization)
        if not _me or course.teacher_id != _me.id:
            raise HTTPException(status_code=403, detail="شما مجاز به مشاهده اطلاعات این کلاس نیستید")

    teacher = db.query(Teacher).filter(Teacher.id == course.teacher_id).first()
    t_name = display_name(teacher, "نامشخص")

    # 2. اطلاعات دانش‌آموزان و مالی
    # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
    enrollments = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.course_id == id).all()

    student_list = []
    total_rev = 0
    total_deb = 0
    debt_to_teacher = 0
    debt_to_institute = 0

    for en in enrollments:
        st = db.query(Student).filter(Student.id == en.student_id, Student.is_deleted == False).first()
        if not st:
            continue
        # بدهی گزارش کلاس باید متعلق به همین enrollment باشد؛ بدهی کل دانش‌آموز
        # عمداً برای نمای کلاس استفاده نمی‌شود.
        breakdown = calculate_enrollment_debt_breakdown(db, en)
        paid = breakdown["paid_teacher"] + breakdown["paid_institute"]
        debt = breakdown["debt"]
        debt_to_teacher += breakdown["debt_teacher"]
        debt_to_institute += breakdown["debt_institute"]

        total_rev += paid
        total_deb += debt

        student_list.append(
            ClassStudentData(
                name=display_name(st, "نامشخص"),
                mobile=st.student_mobile,
                paid=paid,
                debt=debt,
                debt_to_teacher=breakdown["debt_teacher"],
                debt_to_institute=breakdown["debt_institute"],
                enrollment_id=en.id,
                course_id=course.id,
                course_title=course.title,
                teacher_id=course.teacher_id,
                teacher_name=t_name,
                is_unassigned=False,
            )
        )

    # 3. محاسبه جلسات برگزار شده (اصلاح شده با ساختار جدید) ✅
    # اول لیست جلسات این کلاس رو میگیریم
    # FIX: Bug 14 - exclude archived SessionLog rows from this active view.
    # FIX (تاریخچهٔ جلسات): ترتیب صریح بر اساس id (ترتیب ثبت) تا شمارهٔ «جلسه ۱، ۲، …» پایدار بماند.
    sessions = (
        db.query(SessionLog)
        .filter(SessionLog.is_deleted == False)
        .filter(SessionLog.course_id == id)
        .order_by(SessionLog.id.asc())
        .all()
    )

    # FIX (تاریخچهٔ جلسات): نام روز هفته از مبدل مرکزی تاریخ (همان منبع بقیهٔ اپ).
    from today_summary import parse_project_date, PERSIAN_DAY_NAMES  # lazy، مثل attendance/finance

    session_history = []
    for sess in sessions:
        # FIX (تاریخچهٔ جلسات): یک کوئری ردیف‌های حضور/غیاب همین جلسه (قبلاً دو count جدا بود).
        # حالا شمارش و نام‌ها از یک منبع می‌آیند تا «حاضرین: ۲ نفر» با لیست نام‌ها ناسازگار نشود.
        # FIX (F-S2): ردیف‌های آرشیوشده در گزارش کلاس نمی‌آیند.
        attendance_rows = (
            db.query(Attendance, Student)
            .outerjoin(Student, Student.id == Attendance.student_id)
            .filter(Attendance.session_id == sess.id, Attendance.is_deleted == False)
            .order_by(Attendance.id.asc())
            .all()
        )
        present_students = []
        absent_students = []
        for att, att_student in attendance_rows:
            status_value = att.status or ""
            if status_value in ("Present", "Late"):
                # «تأخیر» هم حاضر است — همان قرارداد بقیهٔ اپ (students_full/تاریخچهٔ شاگرد).
                present_students.append(
                    ClassSessionStudent(
                        student_id=att.student_id,
                        name=display_name(att_student, "نامشخص"),
                        student_code=getattr(att_student, "student_code", None),
                        status=status_value or "Present",
                        excused=bool(att.excused),
                    )
                )
            elif status_value == "Absent":
                absent_students.append(
                    ClassSessionStudent(
                        student_id=att.student_id,
                        name=display_name(att_student, "نامشخص"),
                        student_code=getattr(att_student, "student_code", None),
                        status="Absent",
                        excused=bool(att.excused),
                    )
                )
            # وضعیت ناشناس (legacy) در هیچ‌کدام شمرده نمی‌شود — مثل رفتار قبلیِ شمارش‌ها.

        day = parse_project_date(sess.date)
        session_history.append(
            ClassSessionHistory(
                date=sess.date,
                present_count=len(present_students),
                absent_count=len(absent_students),
                session_id=sess.id,
                session_code=sess.session_code,
                weekday=PERSIAN_DAY_NAMES.get(day.weekday(), "") if day else "",
                present_students=present_students,
                absent_students=absent_students,
                # همان فرمول هزینهٔ جلسه در attendance/get_history (خواندنی؛ هیچ مالی‌ای نوشته نمی‌شود).
                total_cost=int(
                    (sess.final_teacher_cost or 0)
                    + (sess.final_institute_share or 0)
                    + (sess.absent_penalty_teacher or 0)
                    + (sess.absent_penalty_institute or 0)
                ),
                cost_per_student=int(sess.cost_per_student or 0),
                start_time=sess.start_time or "",
                end_time=sess.end_time or "",
            )
        )

    return FullClassReport(
        info=ClassReportInfo(
            title=course.title,
            code=course.code,
            teacher_name=t_name,
            session_count=len(sessions),
            total_students=len(enrollments),
            total_revenue=total_rev,
            total_debt=total_deb,
            debt_to_teacher=debt_to_teacher,
            debt_to_institute=debt_to_institute,
        ),
        students=student_list,
        sessions=session_history,
    )


# ==========================================
# 16. API تنظیمات سهم آموزشگاه (Share Config)
# ==========================================


# مدل ورودی و خروجی
class ShareConfigModel(BaseModel):
    count_1: int
    count_2: int
    count_3: int
    count_4: int
    count_5: int
    count_6: int
    count_7: int
    count_8: int
    count_9: int
    count_10: int
    count_11: int
    count_12: int
    count_13: int
    count_14: int
    count_15: int


@router.get("/classes/{class_id}/students_full/excel")
def get_class_students_excel(class_id: int, db: Session = Depends(get_db), _: str = Depends(check_admin_or_secretary_access)):
    course = db.query(Course).filter(Course.id == class_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="کلاس یافت نشد")
        
    # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
    enrollments = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.course_id == class_id).all()
    
    wb = Workbook()
    ws = wb.active
    ws.title = "لیست دانش‌آموزان کلاس"
    ws.views.sheetView[0].rightToLeft = True
    
    ws.append([f"کلاس: {course.title}", "", f"کد کلاس: {course.code}"])
    ws.append([])
    
    headers = ["شناسه", "نام و نام خانوادگی", "شهریه پایه (تومان)", "نوع تخفیف", "تخفیف انتخابی", "مبلغ تخفیف (تومان)", "شهریه نهایی (تومان)", "کل پرداختی (تومان)", "بدهی به معلم", "بدهی به آموزشگاه", "بدهی کل", "جلسات حاضر", "جلسات غایب", "درصد حضور"]
    ws.append(headers)
    
    ws.cell(row=1, column=1).font = Font(name="Tahoma", size=12, bold=True, color="004D40")
    ws.cell(row=1, column=3).font = Font(name="Tahoma", size=12, bold=True, color="004D40")
    
    header_fill = PatternFill(start_color="00695C", end_color="00695C", fill_type="solid")
    header_font = Font(name="Tahoma", size=11, bold=True, color="FFFFFF")
    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=3, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        
    row_num = 4
    for enroll in enrollments:
        st = db.query(Student).filter(Student.id == enroll.student_id, Student.is_deleted == False).first()
        if st:
            final_tuition, discount_amt = get_enrollment_tuition_and_discount(enroll)
            breakdown = calculate_enrollment_debt_breakdown(db, enroll)
            debt_teacher = breakdown["debt_teacher"]
            debt_institute = breakdown["debt_institute"]
            total_debt = breakdown["debt"]

            # FIX: Bug 14 - exclude archived SessionLog rows from this active view.
            sessions = db.query(SessionLog).filter(SessionLog.is_deleted == False).filter(SessionLog.course_id == class_id).all()
            present_count = 0
            absent_count = 0
            for session in sessions:
                att = db.query(Attendance).filter(Attendance.session_id == session.id, Attendance.student_id == st.id, Attendance.is_deleted == False).first()
                if att:
                    if att.status in ["Present", "Late"]:
                        present_count += 1
                    elif att.status == "Absent":
                        absent_count += 1
                        
            total_s = present_count + absent_count
            att_rate = (present_count / total_s * 100) if total_s > 0 else 100.0
            
            d_type = getattr(enroll, "discount_type", "none") or "none"
            d_type_farsi = "درصدی" if d_type == "percentage" else "مبلغ ثابت" if d_type == "fixed" else "بدون تخفیف"
            d_val_disp = f"{enroll.discount_value}%" if d_type == "percentage" else enroll.discount_value
            
            row_data = [
                st.id,
                display_name(st, "نامشخص"),
                enroll.total_tuition,
                d_type_farsi,
                d_val_disp,
                discount_amt,
                final_tuition,
                breakdown["paid_teacher"] + breakdown["paid_institute"],
                debt_teacher,
                debt_institute,
                total_debt,
                present_count,
                absent_count,
                f"{att_rate:.1f}%"
            ]
            ws.append(row_data)
            
            ws.cell(row=row_num, column=3).number_format = '#,##0'
            ws.cell(row=row_num, column=6).number_format = '#,##0'
            ws.cell(row=row_num, column=7).number_format = '#,##0'
            ws.cell(row=row_num, column=8).number_format = '#,##0'
            ws.cell(row=row_num, column=9).number_format = '#,##0'
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
        headers={"Content-Disposition": f"attachment; filename=class_students_{class_id}.xlsx"}
    )


@router.get("/classes/{id}/students_full")
def get_class_students_full(id: int, db: Session = Depends(get_db), authorization: Optional[str] = Header(None), sub_role: str = Depends(check_user_login)):
    # FIX (E2E-B5): دوقلوی هم‌الگو — کلاس آرشیوی 404.
    course = db.query(Course).filter(Course.id == id, Course.is_deleted == False).first()
    if not course:
        raise HTTPException(status_code=404, detail="کلاس یافت نشد")
    # FIX (L14/Y3): گزارش کلاس — ادمین/منشی + معلمِ مالک کلاس (الگوی audit-v2/#11). شاگرد/ولی 403.
    if sub_role not in ("admin", "secretary"):
        if sub_role != "teacher":
            raise HTTPException(status_code=403, detail="شما مجاز به مشاهده اطلاعات این کلاس نیستید")
        from routers.reports import get_logged_in_teacher  # lazy (جلوگیری از import چرخه‌ای)
        _me = get_logged_in_teacher(db, authorization)
        if not _me or course.teacher_id != _me.id:
            raise HTTPException(status_code=403, detail="شما مجاز به مشاهده اطلاعات این کلاس نیستید")

    class_teacher = db.query(Teacher).filter(Teacher.id == course.teacher_id).first()
    class_teacher_name = display_name(class_teacher, "نامشخص")
    # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
    enrollments = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.course_id == id).all()
    students_list = []

    for enroll in enrollments:
        st = db.query(Student).filter(Student.id == enroll.student_id, Student.is_deleted == False).first()
        if st:
            final_tuition, discount_amt = get_enrollment_tuition_and_discount(enroll)
            # کیف‌های Student سراسری‌اند؛ اعداد این ردیف فقط برای همین enrollment هستند.
            breakdown = calculate_enrollment_debt_breakdown(db, enroll)
            debt_teacher = breakdown["debt_teacher"]
            debt_institute = breakdown["debt_institute"]
            total_debt = breakdown["debt"]
            # این دو مقدار برای سازگاری response، کیف کلی دانش‌آموزند و منبع بدهی کلاس نیستند.
            w_t = st.wallet_teacher if st.wallet_teacher is not None else 0
            w_i = st.wallet_institute if st.wallet_institute is not None else 0

            # محاسبه تعداد جلسات حاضر و غایب
            # دریافت تمام جلسات این کلاس
            # FIX: Bug 14 - exclude archived SessionLog rows from this active view.
            sessions = db.query(SessionLog).filter(SessionLog.is_deleted == False).filter(SessionLog.course_id == id).all()
            present_count = 0
            absent_count = 0

            for session in sessions:
                attendance = (
                    db.query(Attendance)
                    .filter(
                        Attendance.session_id == session.id,
                        Attendance.student_id == st.id,
                        Attendance.is_deleted == False
                    )
                    .first()
                )

                if attendance:
                    if attendance.status == "Present" or attendance.status == "Late":
                        present_count += 1
                    elif attendance.status == "Absent":
                        absent_count += 1

            students_list.append(
                {
                    "student_id": st.id,
                    "student_code": st.student_code,
                    "student_name": display_name(st, "نامشخص"),
                    "national_code": st.national_code,
                    "mobile": st.student_mobile,
                    "total_tuition": final_tuition,
                    "paid": breakdown["paid_teacher"] + breakdown["paid_institute"],
                    "paid_teacher": breakdown["paid_teacher"],
                    "paid_institute": breakdown["paid_institute"],
                    "debt": total_debt,
                    "debt_teacher": debt_teacher,
                    "debt_institute": debt_institute,
                    "wallet_teacher": w_t,
                    "wallet_institute": w_i,
                    "course_id": course.id,
                    "course_title": course.title,
                    "teacher_id": course.teacher_id,
                    "teacher_name": class_teacher_name,
                    "is_unassigned": False,
                    **session_fields_for_client(breakdown),
                    "present_count": present_count,
                    "absent_count": absent_count,
                    "total_sessions": len(sessions),
                    "attendance_rate": round((present_count / len(sessions) * 100), 2)
                    if len(sessions) > 0
                    else 0,
                    "is_suspended": st.is_suspended
                    if st.is_suspended is not None
                    else False,
                    "enrollment_id": enroll.id,
                    "discount_type": getattr(enroll, "discount_type", "none") or "none",
                    "discount_value": getattr(enroll, "discount_value", 0) or 0,
                    "discount_amount": discount_amt
                }
            )

    return {
        "course_info": {
            "id": course.id,
            "title": course.title,
            "code": course.code,
            "teacher_id": course.teacher_id,
            "is_suspended": course.is_suspended
            if course.is_suspended is not None
            else False,
        },
        "students": students_list,
    }


# ==========================================
# 🔥 بخش جدید: مدیریت مالی هوشمند (نسخه 2)
# ==========================================


# 1. مدل‌های ورودی و خروجی جدید
class AdvancedSearchItem(BaseModel):
    type: str
    id: int
    title: str
    subtitle: str
    info: str
    student_id: Optional[int] = None
    course_id: Optional[int] = None
    debt_teacher: Optional[int] = 0
    debt_institute: Optional[int] = 0
    total_debt: Optional[int] = 0
    unpaid_sessions: Optional[int] = 0
    students_in_class: Optional[List[dict]] = None


class FinanceSubmitData(BaseModel):
    student_id: int
    amount: int
    target_wallet: str  # "teacher" یا "institute" یا "both"
    description: str
    payment_method: str
    date: str
    amount_institute: Optional[int] = None
    amount_teacher: Optional[int] = None


@router.delete("/classes/{course_id}")
def delete_class_endpoint(
    course_id: int,
    forgive_session_charges: bool = True,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    _: str = Depends(check_admin_access)
):
    # حذف مستقیم و فوری فقط برای ادمین (معلم/منشی از مسیر درخواست + تایید استفاده می‌کنند)
    course = db.query(Course).filter(Course.id == course_id, Course.is_deleted == False).first()
    if not course:
        raise HTTPException(status_code=404, detail="کلاس یافت نشد")

    snapshot = _build_class_deletion_snapshot(db, course)
    snapshot["restore_provenance"] = _apply_class_deletion(db, course, forgive_session_charges)
    # ثبت ردیف تاییدشده برای یکدستی تاریخچه حسابرسی
    # FIX H9: شناسه‌ی تصمیم‌گیرنده باید کاربر واقعی همین درخواست باشد (الگوی H8-P2).
    # چون check_admin_access بالا توکن خراب را از قبل رد کرده، None عملاً نباید بماند (فقط safety net).
    from dependencies import resolve_actor_user_id  # FIX(A2): helper مشترک (یکدستی سه مسیر حذف)
    _actor_user_id = resolve_actor_user_id(db, authorization)
    db.add(models.ClassDeletionRequest(
        course_id=course.id,
        requested_by_role="admin",
        requested_by_user_id=_actor_user_id,
        forgive_session_charges=forgive_session_charges,
        status="approved",
        snapshot_json=json.dumps(snapshot, ensure_ascii=False, default=str),
        decided_at=datetime.datetime.now(),
        decided_by_user_id=_actor_user_id
    ))
    db.commit()
    return {"message": "کلاس با موفقیت حذف و آرشیو شد."}


# ==========================================
# فلوی درخواست حذف کلاس + تایید ادمین
# ==========================================
class DeletionRequestCreate(BaseModel):
    forgive_session_charges: bool = False


class DeletionDecisionRequest(BaseModel):
    admin_note: Optional[str] = None


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



@router.post("/classes/{course_id}/request_delete")
def request_class_deletion(
    course_id: int,
    data: DeletionRequestCreate,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    sub_role: str = Depends(check_user_login)
):
    # معلم (فقط کلاس خودش) و منشی (همه کلاس‌ها) درخواست می‌دهند؛ ادمین مستقیم حذف می‌کند
    if sub_role not in ["secretary", "teacher"]:
        raise HTTPException(status_code=403, detail="ادمین از مسیر حذف مستقیم استفاده می‌کند")
    course = db.query(Course).filter(Course.id == course_id, Course.is_deleted == False).first()
    if not course:
        raise HTTPException(status_code=404, detail="کلاس یافت نشد")
    from dependencies import get_current_user
    current_user = get_current_user(authorization, db)
    teacher_id = None
    if sub_role == "teacher":
        teacher = db.query(Teacher).filter(Teacher.mobile == current_user.username).first()
        if not teacher or course.teacher_id != teacher.id:
            raise HTTPException(status_code=403, detail="شما مجاز به حذف کلاس‌های معلمان دیگر نیستید")
        teacher_id = teacher.id
    pending = db.query(models.ClassDeletionRequest).filter(
        models.ClassDeletionRequest.course_id == course.id,
        models.ClassDeletionRequest.status == "pending"
    ).first()
    if pending:
        raise HTTPException(status_code=400, detail="برای این کلاس یک درخواست حذف باز وجود دارد")
    snapshot = _build_class_deletion_snapshot(db, course)
    req = models.ClassDeletionRequest(
        course_id=course.id,
        requested_by_role=sub_role,
        requested_by_user_id=current_user.id,
        requested_by_teacher_id=teacher_id,
        forgive_session_charges=data.forgive_session_charges,
        status="pending",
        snapshot_json=json.dumps(snapshot, ensure_ascii=False, default=str)
    )
    db.add(req)
    db.commit()
    return {"request_id": req.id, "status": "pending", "message": "درخواست حذف ثبت شد و پس از تایید ادمین اعمال می‌گردد."}


@router.get("/classes/deletion_requests")
def list_class_deletion_requests(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_access)
):
    q = db.query(models.ClassDeletionRequest).order_by(desc(models.ClassDeletionRequest.id))
    if status:
        q = q.filter(models.ClassDeletionRequest.status == status)
    result = []
    for r in q.all():
        course = db.query(Course).filter(Course.id == r.course_id).first()
        requester_name = "نامشخص"
        if r.requested_by_teacher_id:
            t = db.query(Teacher).filter(Teacher.id == r.requested_by_teacher_id).first()
            if t:
                requester_name = display_name(t, "نامشخص")
        elif r.requested_by_user_id:
            u = db.query(User).filter(User.id == r.requested_by_user_id).first()
            if u:
                requester_name = u.username
        try:
            snapshot = json.loads(r.snapshot_json) if r.snapshot_json else {}
        except Exception:
            snapshot = {}
        result.append({
            "request_id": r.id,
            "course_id": r.course_id,
            "course_title": course.title if course else "کلاس حذف شده",
            "course_code": course.code if course else "",
            "requested_by_role": r.requested_by_role,
            "requester_name": requester_name,
            "forgive_session_charges": r.forgive_session_charges,
            "status": r.status,
            "admin_note": r.admin_note,
            "created_at": r.created_at.strftime("%Y/%m/%d %H:%M") if r.created_at else "---",
            "snapshot": snapshot,
        })
    return result


@router.post("/classes/deletion_requests/{request_id}/approve")
def approve_class_deletion(request_id: int, db: Session = Depends(get_db), _: str = Depends(check_admin_access), authorization: Optional[str] = Header(None)):
    # FIX H9: شناسه‌ی تصمیم‌گیرنده باید کاربر واقعی همین درخواست باشد (الگوی H8-P2).
    # چون check_admin_access بالا توکن خراب را از قبل رد کرده، None عملاً نباید بماند (فقط safety net).
    from dependencies import resolve_actor_user_id  # FIX(A2): helper مشترک (یکدستی سه مسیر حذف)
    _actor_user_id = resolve_actor_user_id(db, authorization)
    req = db.query(models.ClassDeletionRequest).filter(models.ClassDeletionRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="درخواست یافت نشد")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="این درخواست قبلاً تعیین تکلیف شده است")
    course = db.query(Course).filter(Course.id == req.course_id, Course.is_deleted == False).first()
    if not course:
        req.status = "rejected"
        req.admin_note = "کلاس قبلاً حذف شده بود"
        req.decided_at = datetime.datetime.now()
        req.decided_by_user_id = _actor_user_id
        db.commit()
        raise HTTPException(status_code=400, detail="کلاس قبلاً حذف شده است؛ درخواست بسته شد")
    provenance = _apply_class_deletion(db, course, req.forgive_session_charges)
    try:
        deletion_snapshot = json.loads(req.snapshot_json or "{}")
        if not isinstance(deletion_snapshot, dict):
            deletion_snapshot = {}
    except (TypeError, ValueError):
        deletion_snapshot = _build_class_deletion_snapshot(db, course)
    deletion_snapshot["restore_provenance"] = provenance
    req.snapshot_json = json.dumps(deletion_snapshot, ensure_ascii=False, default=str)
    req.status = "approved"
    req.decided_at = datetime.datetime.now()
    req.decided_by_user_id = _actor_user_id
    db.commit()
    return {"message": "حذف کلاس تایید و اعمال شد."}


@router.post("/classes/deletion_requests/{request_id}/reject")
def reject_class_deletion(request_id: int, data: DeletionDecisionRequest, db: Session = Depends(get_db), _: str = Depends(check_admin_access), authorization: Optional[str] = Header(None)):
    # FIX H9: شناسه‌ی تصمیم‌گیرنده باید کاربر واقعی همین درخواست باشد (الگوی H8-P2).
    # چون check_admin_access بالا توکن خراب را از قبل رد کرده، None عملاً نباید بماند (فقط safety net).
    from dependencies import resolve_actor_user_id  # FIX(A2): helper مشترک (یکدستی سه مسیر حذف)
    _actor_user_id = resolve_actor_user_id(db, authorization)
    req = db.query(models.ClassDeletionRequest).filter(models.ClassDeletionRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="درخواست یافت نشد")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="این درخواست قبلاً تعیین تکلیف شده است")
    req.status = "rejected"
    req.admin_note = data.admin_note
    req.decided_at = datetime.datetime.now()
    req.decided_by_user_id = _actor_user_id
    db.commit()
    return {"message": "درخواست حذف رد شد؛ کلاس دست نخورده باقی ماند."}


class ClassUpdateInfoModel(BaseModel):
    title: Optional[str] = None
    grade_level: Optional[str] = None

# FIX (grade-289/srv): لیست معتبر مقاطع = همان لیست L13 در financial_calculations.py
# (ابتدایی/راهنمایی/دبیرستان + معادل‌ها) به‌علاوه‌ی مقادیر مشروعِ غیرتعرفه‌ای که مسیر ساخت
# (اسپینر AddClass) می‌پذیرد: «کنکور»، «فارغ‌التحصیل»، «سایر». L13 خودش این‌ها را
# category=None می‌کند و فقط هنگام نیاز واقعی به تعرفه خطای واضح می‌دهد؛ پس این‌جا هم
# معتبرند و فقط آشغال واقعی (مثل «نامشخص» یا تایپی) 400 می‌گیرد.
_VALID_GRADE_LEVELS = frozenset({
    "اول", "دوم", "سوم", "چهارم", "پنجم", "ششم", "ابتدایی", "دبستان",
    "هفتم", "هشتم", "نهم", "راهنمایی", "متوسطه اول",
    "دهم", "یازدهم", "دوازدهم", "دبیرستان", "متوسطه دوم",
    "کنکور", "فارغ‌التحصیل", "سایر",
})

@router.put("/classes/update_info/{course_id}")
def update_class_info(
    course_id: int, 
    data: ClassUpdateInfoModel, 
    db: Session = Depends(get_db), 
    authorization: Optional[str] = Header(None),
    sub_role: str = Depends(check_user_login)
):
    course = db.query(Course).filter(Course.id == course_id, Course.is_deleted == False).first()
    if not course:
        raise HTTPException(status_code=404, detail="کلاس یافت نشد")

    # FIX (audit-v2/H-caller): فقط ادمین/منشی یا معلمِ مالکِ همین کلاس — قبلاً هر لاگینی
    # (حتی شاگرد) عنوان و grade_level هر کلاسی را عوض می‌کرد. معلمِ مالک عمداً مجاز است چون
    # ClassDetail اپ (مسیر مشروع معلم) همین اندپوینت را صدا می‌زند (قدم ۴)؛ باقی‌مانده‌ی آگاهانه:
    # grade_level روی تعرفه اثر دارد پس تغییرش توسط معلم بعداً باید audit شود (follow-up).
    if sub_role not in ("admin", "secretary"):
        from routers.reports import get_logged_in_teacher
        logged = get_logged_in_teacher(db, authorization)
        if not logged or logged.id != course.teacher_id:
            raise HTTPException(status_code=403, detail="شما مجاز به ویرایش اطلاعات این کلاس نیستید")
        
    if data.title is not None and data.title.strip():
        course.title = data.title.strip()
    if data.grade_level is not None and data.grade_level.strip():
        # FIX (grade-289/srv): اعتبارسنجی به‌جای پذیرش کورکورانه — نرمال‌سازی دقیقاً مثل L13.
        _g = data.grade_level.strip().replace("ي", "ی").replace("ك", "ک").replace("‌", " ")
        _g = " ".join(_g.split())
        if _g not in _VALID_GRADE_LEVELS:
            raise HTTPException(status_code=400, detail=f"مقطع تحصیلی «{data.grade_level.strip()}» نامعتبر است")
        course.grade_level = data.grade_level.strip()
        
    db.commit()
    return {"message": "اطلاعات کلاس با موفقیت ویرایش شد."}


# ==========================================
# اصلاح شده: جستجوی پیشرفته با محاسبه دقیق بدهی
# ==========================================


# ===================== گروه ۶: صف تأیید و ویرایش امن کلاس =====================
class BulkClassDecisionRequest(BaseModel):
    course_ids: List[int]
    reason: Optional[str] = None


class ClassAdminUpdateModel(BaseModel):
    title: Optional[str] = None
    grade_level: Optional[str] = None
    days_of_week: Optional[str] = None
    class_time: Optional[str] = None
    capacity: Optional[int] = None
    teacher_id: Optional[int] = None
    is_paused: Optional[bool] = None


def check_scheduling_conflicts(db: Session, teacher_id: int, days_of_week: str,
                               class_time: str, exclude_course_id: Optional[int] = None):
    """Return active classes which overlap the proposed weekly slot."""
    proposed = parse_time_to_minutes(class_time)
    if not proposed:
        raise HTTPException(status_code=400, detail="ساعت کلاس معتبر نیست")
    result = []
    for other in db.query(Course).filter(
        Course.teacher_id == teacher_id, Course.is_deleted == False,
        Course.is_suspended == False, Course.is_paused == False
    ).all():
        if exclude_course_id and other.id == exclude_course_id:
            continue
        if not days_overlap(other.days_of_week or "", days_of_week or ""):
            continue
        other_time = parse_time_to_minutes(other.class_time or "")
        if other_time and proposed[0] < other_time[1] and other_time[0] < proposed[1]:
            result.append(other)
    return result


@router.get("/classes/pending_approval")
def pending_classes_for_admin(
    db: Session = Depends(get_db), _: str = Depends(check_admin_access)
):
    rows = db.query(Course).filter(
        Course.is_deleted == False, Course.is_admin_approved == False
    ).order_by(desc(Course.pending_since), desc(Course.id)).all()
    return [{
        "id": c.id, "title": c.title, "code": c.code, "teacher_id": c.teacher_id,
        "teacher_name": display_name(c.teacher, "نامشخص") if c.teacher else "نامشخص",
        "days_of_week": c.days_of_week, "class_time": c.class_time,
        "capacity": c.capacity, "rejection_reason": c.rejection_reason,
        "pending_since": c.pending_since.isoformat() if c.pending_since else None,
    } for c in rows]


def _record_class_decision(db: Session, course: Course, action: str, reason: Optional[str]):
    course.is_admin_approved = action == "approve"
    course.rejection_reason = None if action == "approve" else (reason or "بدون توضیح")
    course.pending_since = None
    db.add(ActivityLog(
        admin_username="group6", action=f"class_{action}", target_id=course.id,
        target_name=course.title, details=course.rejection_reason
    ))


@router.post("/classes/pending_approval/bulk_approve")
def bulk_approve_classes(
    data: BulkClassDecisionRequest, db: Session = Depends(get_db),
    _: str = Depends(check_admin_access)
):
    courses = db.query(Course).filter(
        Course.id.in_(data.course_ids), Course.is_deleted == False,
        Course.is_admin_approved == False
    ).all()
    conflicts = []
    for course in courses:
        conflict = check_scheduling_conflicts(
            db, course.teacher_id, course.days_of_week or "", course.class_time or "", course.id
        )
        if conflict:
            conflicts.append({"course_id": course.id, "conflict_course_ids": [c.id for c in conflict]})
    if conflicts:
        raise HTTPException(status_code=409, detail={"message": "تداخل زمان‌بندی وجود دارد", "conflicts": conflicts})
    for course in courses:
        _record_class_decision(db, course, "approve", data.reason)
    db.commit()
    return {"message": "تایید شد", "approved_count": len(courses), "course_ids": [c.id for c in courses]}


@router.post("/classes/pending_approval/bulk_reject")
def bulk_reject_classes(
    data: BulkClassDecisionRequest, db: Session = Depends(get_db),
    _: str = Depends(check_admin_access)
):
    if not data.reason or not data.reason.strip():
        raise HTTPException(status_code=400, detail="علت رد کلاس الزامی است")
    courses = db.query(Course).filter(
        Course.id.in_(data.course_ids), Course.is_deleted == False,
        Course.is_admin_approved == False
    ).all()
    for course in courses:
        _record_class_decision(db, course, "reject", data.reason.strip())
    db.commit()
    return {"rejected_count": len(courses), "course_ids": [c.id for c in courses], "reason": data.reason.strip()}


@router.put("/classes/update")
def update_class_by_admin(
    data: ClassAdminUpdateModel, course_id: int,
    db: Session = Depends(get_db), _: str = Depends(check_admin_access)
):
    """Admin-only schedule/capacity/teacher transfer with conflict and finance guards."""
    course = db.query(Course).filter(Course.id == course_id, Course.is_deleted == False).first()
    if not course:
        raise HTTPException(status_code=404, detail="کلاس یافت نشد")
    new_teacher = data.teacher_id if data.teacher_id is not None else course.teacher_id
    new_days = data.days_of_week if data.days_of_week is not None else course.days_of_week
    new_time = data.class_time if data.class_time is not None else course.class_time
    if data.capacity is not None and data.capacity < 1:
        raise HTTPException(status_code=400, detail="ظرفیت باید حداقل یک نفر باشد")
    active_enrollments = db.query(Enrollment).filter(
        Enrollment.course_id == course.id, Enrollment.is_deleted == False
    ).count()
    if data.capacity is not None and data.capacity < active_enrollments:
        raise HTTPException(status_code=409, detail="ظرفیت جدید از ثبت‌نام‌های فعلی کمتر است")
    if data.teacher_id is not None and data.teacher_id != course.teacher_id:
        # انتقال مالک مالیِ کلاس پس از billing/settlement ممنوع است؛ اصلاحش باید از مسیر
        # reversal همان ledger انجام شود، نه با تغییر retroactive teacher_id.
        existing_session_ids = [row[0] for row in db.query(SessionLog.id).filter(
            SessionLog.course_id == course.id, SessionLog.is_deleted == False
        ).all()]
        if existing_session_ids:
            billed = db.query(Attendance).filter(
                Attendance.session_id.in_(existing_session_ids), Attendance.is_billed == True,
                Attendance.is_deleted == False
            ).first()
            settled = db.query(models.Settlement).filter(
                models.Settlement.is_reversed == False,
                models.Settlement.session_ids_json.isnot(None)
            ).all()
            settled_scope = False
            for item in settled:
                try:
                    scope = {int(value) for value in json.loads(item.session_ids_json or "[]")}
                except (TypeError, ValueError, json.JSONDecodeError):
                    scope = set()
                if set(existing_session_ids).intersection(scope):
                    settled_scope = True
                    break
            if billed or settled_scope:
                raise HTTPException(status_code=409, detail="انتقال معلم پس از اثر مالی جلسه نیازمند reversal/audit است")
    conflicts = check_scheduling_conflicts(db, new_teacher, new_days or "", new_time or "", course.id)
    if conflicts:
        raise HTTPException(status_code=409, detail={
            "message": "تداخل زمان‌بندی با کلاس فعال", "conflict_course_ids": [c.id for c in conflicts]
        })
    if data.title is not None:
        course.title = data.title.strip() or course.title
    if data.grade_level is not None:
        course.grade_level = data.grade_level.strip() or course.grade_level
    course.days_of_week = new_days
    course.class_time = new_time
    course.teacher_id = new_teacher
    if data.capacity is not None:
        course.capacity = data.capacity
    if data.is_paused is not None:
        course.is_paused = data.is_paused
    db.add(ActivityLog(
        admin_username="group6", action="class_update", target_id=course.id,
        target_name=course.title,
        details=json.dumps({"teacher_id": new_teacher, "days_of_week": new_days,
                            "class_time": new_time, "capacity": course.capacity,
                            "is_paused": course.is_paused}, ensure_ascii=False)
    ))
    db.commit()
    return {"message": "کلاس با guardهای زمان‌بندی و مالی ویرایش شد", "course_id": course.id}
