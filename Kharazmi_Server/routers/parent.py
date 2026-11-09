from fastapi import APIRouter, Depends, HTTPException, status, Header, Form
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Union
from sqlalchemy import desc, or_, text
import datetime
import random
import uuid

import models
from models import Student, Enrollment, Course, Grade, Installment, SessionLog, Attendance, SmsLog, ParentOTP, UserSession, User, Notification
from schemas import ParentOtpRequest, ParentLoginRequest, ChildSelectRequest
from dependencies import get_db, limiter, normalize_mobile, resolve_notification_role
# FIX(C6): خواندن واقعی تکالیف/آزمون‌ها/برنامهٔ هفتگی برای پورتال‌ها (بدون کد تکراری).
from portal_data import build_portal_activity
from fastapi import Request

# FIX: Bug 16 - share the tuition-minus-payment debt calculation across financial views.
from financial_calculations import calculate_student_debt

router = APIRouter()

# FIX(C1): سقف اعلان‌های نمایش‌داده‌شده در پورتال ولی (جدیدترین‌ها اول) — 
# جلوگیری از پاسخ سنگین برای ولی‌ای که ماه‌ها اعلان انبار کرده است.
PORTAL_NOTIFICATIONS_LIMIT = 50

# ==========================================
# 1. درخواست کد یک‌بارمصرف اولیا (OTP)
# ==========================================
@router.post("/parent/request_otp")
@limiter.limit("5/5minutes")
def request_parent_otp(request: Request, req: ParentOtpRequest, db: Session = Depends(get_db)):
    # FIX H20-B2: ورودی canonical (کوئری + کلیدهای OTP/rate)؛ نامعتبر → همان 404 «یافت نشد».
    _raw_mob = (req.mobile or "").strip()
    if not _raw_mob:
        raise HTTPException(status_code=400, detail="شماره موبایل الزامی است")
    mobile = normalize_mobile(_raw_mob)
    if not mobile:
        raise HTTPException(status_code=404, detail="شماره همراه ولی در سیستم ثبت نام نشده است")
        
    student_exists = db.query(Student).filter(Student.parent_mobile.in_([mobile, _raw_mob]), Student.is_deleted == False).first()  # FIX H20-ESC
    if not student_exists:
        raise HTTPException(status_code=404, detail="شماره همراه ولی در سیستم ثبت نام نشده است")
    # FIX (E2E-B4): H10 فقط خانواده‌ی auth.py را گیت کرده بود؛ این خانواده (parent_mobile) جا مانده بود.
    # اگر همه‌ی فرزندان این شماره معلق‌اند، OTP (هزینه‌ی SMS) صادر نمی‌شود.
    _kids = db.query(Student).filter(Student.parent_mobile.in_([mobile, _raw_mob]), Student.is_deleted == False).all()
    if _kids and all(k.is_suspended for k in _kids):
        raise HTTPException(status_code=403, detail="حساب شما توسط مدیر معلق شده است. لطفاً با آموزشگاه تماس بگیرید")

    # FIX: per-mobile rate limiting قوی‌تر – 3 در 5 دقیقه
    now = datetime.datetime.utcnow()
    five_min_ago = now - datetime.timedelta(minutes=5)
    recent_count = db.query(ParentOTP).filter(ParentOTP.mobile == mobile, ParentOTP.created_at > five_min_ago).count()
    if recent_count >= 3:
        raise HTTPException(status_code=429, detail="تعداد درخواست کد برای این شماره زیاد است، لطفاً 5 دقیقه صبر کنید")

    last_otp = db.query(ParentOTP).filter(ParentOTP.mobile == mobile).order_by(desc(ParentOTP.id)).first()
    if last_otp:
        elapsed = datetime.datetime.utcnow() - last_otp.created_at
        if elapsed.total_seconds() < 60:
            raise HTTPException(status_code=429, detail="لطفاً پس از ۶۰ ثانیه مجدداً تلاش کنید")

    # FIX: قفل به خاطر تلاش ناموفق
    locked = db.query(ParentOTP).filter(
        ParentOTP.mobile == mobile,
        ParentOTP.is_locked == True,
        ParentOTP.locked_until != None,
        ParentOTP.locked_until > now
    ).first()
    if locked:
        raise HTTPException(status_code=429, detail="این شماره به دلیل تلاش‌های ناموفق قفل شده")
            
    # FIX: 6 رقمی و هش شده
    otp_code = str(random.randint(100000, 999999))
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=3)
    from dependencies import hash_password
    hashed_otp = hash_password(otp_code)
    new_otp = ParentOTP(
        mobile=mobile,
        otp=hashed_otp,
        expires_at=expires_at,
        is_used=False,
        attempts=0,
        is_locked=False
    )
    db.add(new_otp)
    
    # شبیه‌سازی ارسال واقعی پیامک (ذخیره در sms_logs دیتابیس)
    from models import InstituteSettings
    settings = db.query(InstituteSettings).first()
    inst_name = settings.name if (settings and settings.name) else "خوارزمی"
    
    today = datetime.datetime.now().strftime("%Y/%m/%d %H:%M")
    msg = f"کد تایید ورود به پورتال اولیا {inst_name}: {otp_code} (معتبر تا ۵ دقیقه)"
    
    db.add(SmsLog(
        target_group=f"otp_{mobile}",
        message_text=msg,
        sent_count=1,
        date=today
    ))
    db.commit()
    
    # برای لو نرفتن کد در حالت پروداکشن، مقدار کد را در بدنه پاسخ ارسال نمی‌کنیم
    # ولی برای راحتی کار تست ادمین، اعلام می‌کنیم که شبیه‌سازی شد
    return {
        "status": "success",
        "message": "کد یک‌بارمصرف ورود با موفقیت صادر و پیامک شد (لاگ آن در جدول پیامک‌ها درج شد)"
    }

# ==========================================
# ۲. تایید تکی یا چندگانه ورود با OTP
# ==========================================
@router.post("/parent/login")
@limiter.limit("5/5minutes")
def parent_login(request: Request, req: ParentLoginRequest, db: Session = Depends(get_db)):
    # FIX H20-B2: ورودی canonical (OTP + lookup + temp-JWT)؛ نامعتبر → همان 400 کد نامعتبر.
    _raw_mob = (req.mobile or "").strip()
    mobile = normalize_mobile(_raw_mob)
    if not mobile:
        raise HTTPException(status_code=400, detail="کد تایید نامعتبر یا منقضی شده است")
    otp_plain = req.otp.strip()
    now = datetime.datetime.utcnow()

    # FIX: جستجوی OTP هش شده، بررسی قفل و انقضا
    from dependencies import verify_password, create_jwt_token, hash_password
    candidates = db.query(ParentOTP).filter(
        ParentOTP.mobile.in_([mobile, _raw_mob]),  # FIX H20-ESC
        ParentOTP.is_used == False,
        ParentOTP.expires_at > now,
        ParentOTP.is_locked == False
    ).order_by(desc(ParentOTP.id)).limit(5).all()

    otp_record = None
    for cand in candidates:
        try:
            if verify_password(otp_plain, cand.otp):
                otp_record = cand
                break
        except Exception:
            # fallback برای رکوردهای قدیمی plaintext
            if cand.otp == otp_plain:
                otp_record = cand
                break

    if not otp_record:
        # افزایش attempts
        latest = db.query(ParentOTP).filter(ParentOTP.mobile.in_([mobile, _raw_mob]), ParentOTP.is_used == False).order_by(desc(ParentOTP.id)).first()  # FIX H20-ESC
        if latest:
            latest.attempts = (latest.attempts or 0) + 1
            if latest.attempts >= 5:
                latest.is_locked = True
                latest.locked_until = now + datetime.timedelta(minutes=15)
            db.commit()
        raise HTTPException(status_code=400, detail="کد تایید نامعتبر یا منقضی شده است")

    otp_record.is_used = True
    db.commit()

    students = db.query(Student).filter(Student.parent_mobile.in_([mobile, _raw_mob]), Student.is_deleted == False).all()  # FIX H20-ESC
    if not students:
        raise HTTPException(status_code=404, detail="هیچ دانش‌آموزی برای این شماره همراه یافت نشد")

    if len(students) == 1:
        student = students[0]
        # FIX (E2E-B4): فرزند معلق حتی با OTP درست لاگین نمی‌شود (الگوی H10 در auth.py).
        if student.is_suspended:
            raise HTTPException(status_code=403, detail="حساب شما توسط مدیر معلق شده است. لطفاً با آموزشگاه تماس بگیرید")
        # FIX(H2): سشن به سایه‌ی parent اشاره می‌کند، نه Student.id (با ساخت lazy اگر نیست)
        from dependencies import ensure_student_shadow_users
        ensure_student_shadow_users(db, student)
        token = create_jwt_token(user_id=student.parent_user_id, sub_role="parent")
        new_session = UserSession(
            token=token,
            user_id=student.parent_user_id,
            sub_role="parent"
        )
        db.add(new_session)
        db.commit()
        return {
            "status": "success",
            "multiple_children": False,
            "token": token,
            "student_name": f"{student.first_name} {student.last_name}"
        }
    else:
        temp_token = create_jwt_token(user_id=-1, sub_role=f"temp_parent:{mobile}")
        new_session = UserSession(
            token=temp_token,
            user_id=-1,
            sub_role=f"temp_parent:{mobile}"
        )
        db.add(new_session)
        db.commit()
        # FIX (E2E-B4): فرزندان معلق از لیست انتخاب حذف می‌شوند؛ اگر همه معلق‌اند، 403.
        _active = [s for s in students if not s.is_suspended]
        if not _active:
            raise HTTPException(status_code=403, detail="حساب شما توسط مدیر معلق شده است. لطفاً با آموزشگاه تماس بگیرید")
        # FIX L3: کد ملی از لیست پیش‌انتخاب حذف شد — انتخاب فقط id لازم دارد و نمایش فقط نام؛
        # اپ (ParentSimpleStudentItem=id+name) و پورتال وب (child.id/child.name) به چیزی جز این دو نیاز ندارند.
        children_list = [{"id": s.id, "name": f"{s.first_name} {s.last_name}"} for s in _active]
        return {
            "status": "success",
            "multiple_children": True,
            "temp_token": temp_token,
            "children": children_list
        }

# ==========================================
# ۳. انتخاب فرزند و ارتقای سشن موقت به دایمی (مخصوص چند فرزندی)
# ==========================================
@router.post("/parent/select_child")
def parent_select_child(req: ChildSelectRequest, db: Session = Depends(get_db)):
    # راستی‌آزمایی سشن موقت پویا با پیشوند مناسب
    from dependencies import get_session_from_token  # FIX H17: اعمال انقضای ۷روزه‌ی JWT موقت
    temp_session, _ = get_session_from_token(db, req.temp_token)
    if not temp_session or not (temp_session.sub_role or "").startswith("temp_parent:"):
        raise HTTPException(status_code=401, detail="نشست موقت معتبر نیست یا منقضی شده است")
        
    role_parts = temp_session.sub_role.split(":")
    if len(role_parts) != 2:
        raise HTTPException(status_code=401, detail="نشست موقت نامعتبر است")
    parent_mobile = role_parts[1]
    
    student = db.query(Student).filter(Student.id == req.student_id, Student.is_deleted == False).first()
    if not student:
        raise HTTPException(status_code=404, detail="دانش‌آموز مورد نظر یافت نشد")
        
    # راستی‌آزمایی امنیتی جهت ممانعت از دسترسی به فرزند دیگران (IDOR Protection)
    # FIX H20-B2: مقایسه روی canonical هر دو طرف؛ اگر طرفی غیرقابل‌نرمال بود fallback به مقایسه‌ی دقیق امروز.
    _ns = normalize_mobile(student.parent_mobile)
    _nt = normalize_mobile(parent_mobile)
    _same = (_ns == _nt) if (_ns is not None and _nt is not None) else (student.parent_mobile == parent_mobile)
    if not _same:
        raise HTTPException(status_code=403, detail="شما مجاز به انتخاب این دانش‌آموز نیستید")
    # FIX (E2E-B4): انتخاب فرزند معلق ممنوع (توکن موقت ممکن است قبل از تعلیق صادر شده باشد).
    if student.is_suspended:
        raise HTTPException(status_code=403, detail="حساب شما توسط مدیر معلق شده است. لطفاً با آموزشگاه تماس بگیرید")
        
    # FIX(H2): سشن به سایه‌ی parent اشاره می‌کند، نه Student.id (با ساخت lazy اگر نیست)
    from dependencies import create_jwt_token
    from dependencies import ensure_student_shadow_users
    ensure_student_shadow_users(db, student)
    token = create_jwt_token(user_id=student.parent_user_id, sub_role="parent")
    new_session = UserSession(
        token=token,
        user_id=student.parent_user_id,
        sub_role="parent"
    )
    db.add(new_session)
    db.delete(temp_session)
    db.commit()
    
    return {
        "status": "success",
        "token": token,
        "student_name": f"{student.first_name} {student.last_name}"
    }

# ==========================================
# ۴. اندپوینت امن دریافت کل سوابق فرزند (بدون دریافت آیدی شاگرد از فرانت)
# ==========================================
def _portal_notifications(db: Session, student: Student) -> list:
    """اعلان‌های واقعیِ ولیِ همین فرزند (جدیدترین اول) — FIX(C1).

    - منبع: جدول `notifications` با کلید `recipient_user_id` (فضای User.id) و `recipient_role`.
    - نقش با همان helper مشترک resolve می‌شود تا رکورد legacy/نقش temp_parent هم درست نگاشت شود.
    - `created_at` می‌تواند NULL باشد (رکورد legacy): تاریخ به رشتهٔ خالی تبدیل می‌شود، نه null،
      تا مدل اندروید (`ParentNotificationItem.date: String` غیر-null) نشکند.
    """
    if not student or not student.parent_user_id:
        return []
    parent_user = db.query(User).filter(User.id == student.parent_user_id).first()
    if parent_user is None:
        return []
    role = resolve_notification_role(parent_user)
    rows = (
        db.query(Notification)
        .filter(Notification.recipient_user_id == parent_user.id,
                Notification.recipient_role == role)
        .order_by(Notification.created_at.desc().nullslast(), Notification.id.desc())
        .limit(PORTAL_NOTIFICATIONS_LIMIT)
        .all()
    )
    from today_summary import jalali_date_string  # lazy، مثل سایر تاریخ‌های شمسی پورتال
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


@router.get("/parent/child_profile")
def get_parent_child_profile(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    if not authorization:
        raise HTTPException(status_code=401, detail="توکن احراز هویت یافت نشد")
        
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="قالب توکن معتبر نیست")
        
    token = parts[1]
    from dependencies import get_session_from_token  # FIX H17: وریفای JWT+انقضا به‌جای کوئری دستی
    session, _ = get_session_from_token(db, token)
    if not session or session.sub_role != "parent":
        raise HTTPException(status_code=401, detail="نشست شما نامعتبر یا منقضی شده است")
        
    # شناسه دانش‌آموز (فرزند) مستقیماً از روی سشن امن استخراج می‌گردد (امنیتی - جلوگیری از نشت داده)
    from dependencies import get_session_parent
    student = get_session_parent(db, session)
    if not student:
        raise HTTPException(status_code=404, detail="دانش‌آموز یافت نشد")
    student_id = student.id
        
    # الف) واکشی کلاس‌ها
    classes = []
    # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
    enrollments = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.student_id == student_id).all()
    for en in enrollments:
        if en.course:
            classes.append(f"{en.course.title} ({en.course.code}) - {en.course.grade_level}")
            
    # ب) واکشی کارنامه نمرات
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
            
    # ج) واکشی تاریخچه حضور غیاب‌ها
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
            
    # د) واکشی وضعیت اقساط شهریه
    # FIX: Bug 13 - exclude archived Installment rows from this active view.
    installments_db = db.query(Installment).filter(Installment.is_deleted == False).filter(Installment.enrollment_id.in_([en.id for en in enrollments])).order_by(Installment.due_date.asc()).all()
    installments_list = []
    for inst in installments_db:
        # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
        enroll = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.id == inst.enrollment_id).first()
        course = db.query(Course).filter(Course.id == enroll.course_id).first() if enroll else None
        c_title = course.title if course else "کلاس حذف شده"
        
        from today_summary import parse_project_date  # FIX H3-B1: due_date is Jalali; compare as real dates via central converter (lazy import, same pattern as routers/analytics.py)
        today_date = datetime.datetime.now().date()
        due = parse_project_date(inst.due_date)
        status_text = "پرداخت شده" if inst.is_paid else ("معوقه" if (due is not None and due < today_date) else "در انتظار")
        
        installments_list.append({
            "course_title": c_title,
            "amount": inst.amount,
            "due_date": inst.due_date,
            "is_paid": inst.is_paid,
            "status": status_text,
            "paid_at": inst.paid_at or "---"
        })

    # ه) مبالغ تراز مالی دانش‌آموز
    w_t = student.wallet_teacher if student.wallet_teacher is not None else 0
    w_i = student.wallet_institute if student.wallet_institute is not None else 0
    # FIX: Bug 16 - student/parent financial views must agree with tuition debtor reports.
    total_debt = calculate_student_debt(db, student)

    # و) تکالیف، آزمون‌ها، جلسات پیش‌رو و اعلان‌ها برای ردیف‌های دانش‌آموز
    # FIX(C6): این سه لیست قبلاً **قالب ثابت جعلی** بودند (تکلیف «فصل ۲» با سررسید
    # ۱۴۰۵/۰۶/۰۵، آزمون «هماهنگ مستمر» با تاریخ ۱۴۰۵/۰۶/۱۰ و جلسهٔ «شنبه و دوشنبه‌ها
    # ۱۶:۰۰ الی ۱۷:۳۰») برای هر خانواده مستقل از واقعیت. حالا داده‌ی واقعیِ همان
    # دانش‌آموز (تکالیف و آزمون‌های ثبت‌شده + برنامهٔ هفتگی خود کلاس) خوانده می‌شود.
    portal_activity = build_portal_activity(db, student)
    homework_list = portal_activity["homework"]
    exams_list = portal_activity["exams"]
    upcoming_list = portal_activity["upcoming_sessions"]
    notifications_list = []

    # FIX(C1): اعلان‌های واقعیِ ولی از جدول `notifications` (به‌جای دو اعلان جعلیِ ثابت).
    # قبلاً هر ولی — مستقل از واقعیت — دو پیام نمایشی («شروع ترم»، «تعطیلی سرما») می‌دید و
    # اعلان‌های واقعی (پرداخت فرزند، یادآوری قسط، ...) هرگز به پورتال ولی نمی‌رسید.
    # فیلتر دقیقاً مثل اندپوینت /notifications است: recipient_user_id = کاربرِ سایه‌ی ولی
    # + نقشِ کانونیکال (resolve_notification_role) ⇒ هیچ اعلانِ کاربر دیگری دیده نمی‌شود.
    notifications_list = _portal_notifications(db, student)

    return {
        "info": {
            "name": f"{student.first_name} {student.last_name}",
            "national_code": student.national_code,
            "parent_mobile": student.parent_mobile,
            "profile_image": student.profile_image,
            # FIX H10 (نمایشی): پرچم تعلیق برای بنر اپ والد — لاگین والد بلاک نمی‌شود.
            "is_suspended": bool(student.is_suspended)
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

# ==========================================
# ۵. سرو فیزیکی تک‌صفحه استاتیک پورتال اولیا (HTML/CSS/JS)
# ==========================================
@router.get("/parent/portal", response_class=HTMLResponse)
def get_parent_portal_page(db: Session = Depends(get_db)):
    from models import InstituteSettings
    settings = db.query(InstituteSettings).first()
    if not settings:
        settings = InstituteSettings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
        
    inst_name = settings.name
    inst_phone = settings.phone
    inst_address = settings.address
    inst_email = settings.official_email
    # FIX M3-portal: src اولیه همیشه placeholder عمومی است؛ لوگوی آپلودی (نیازمند توکن)
    # جدا در data-auth-src می‌نشیند تا JS با fetch احرازی لودش کند.
    inst_logo = "https://img.icons8.com/color/96/user-male-circle--v1.png"
    inst_logo_auth = f"/uploads/profiles/{settings.logo_path}" if settings.logo_path else ""

    html_content = """
    <!DOCTYPE html>
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>پورتال هوشمند اولیا {inst_name}</title>
        <!-- لود فریم‌ورک سبک طراحی Tailwind CSS -->
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;700&display=swap');
            body { font-family: 'Vazirmatn', sans-serif; }
        </style>
    </head>
    <body class="bg-gray-100 min-h-screen text-gray-800">
        <!-- سربرگ شکیل پورتال -->
        <header class="bg-teal-800 text-white shadow-md p-4 text-center">
            <h1 class="text-xl font-bold">{inst_name}</h1>
            <p class="text-xs text-teal-200 mt-1">پورتال آنلاین مشاهده سوابق و وضعیت مالی فرزندان</p>
        </header>

        <div class="max-w-md mx-auto p-4 mt-6">
            <!-- ۱. فرم لاگین OTP اولیا (نمایش در صورت نبود توکن) -->
            <div id="loginSection" class="bg-white rounded-2xl shadow-md p-6">
                <h2 class="text-lg font-bold text-center text-teal-800 mb-6">ورود سریع به پورتال اولیا</h2>
                
                <!-- مرحله اول: دریافت شماره همراه ولی -->
                <div id="stepRequest" class="space-y-4">
                    <div>
                        <label class="block text-sm font-bold text-gray-700 mb-2">شماره همراه ولی (ثبت‌شده در سیستم):</label>
                        <input type="tel" id="parentMobile" placeholder="مثال: 09123456789" class="w-full p-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-teal-500 text-center" maxLength="11">
                    </div>
                    <button id="btnRequestOtp" class="w-full bg-teal-800 text-white p-3 rounded-xl font-bold shadow hover:bg-teal-700 transition">درخواست کد تایید پیامکی</button>
                </div>

                <!-- مرحله دوم: دریافت کد یک‌بارمصرف (OTP) -->
                <div id="stepVerify" class="space-y-4 hidden">
                    <p class="text-sm text-center text-gray-500">کد تایید پیامک‌شده را وارد نمایید:</p>
                    <div>
                        <input type="number" id="otpCode" placeholder="کد ۵ رقمی تایید" class="w-full p-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-teal-500 text-center font-bold tracking-widest" maxLength="5">
                    </div>
                    <button id="btnLogin" class="w-full bg-teal-800 text-white p-3 rounded-xl font-bold shadow hover:bg-teal-700 transition">تایید و ورود به پورتال</button>
                    <button id="btnBackToRequest" class="w-full text-center text-sm text-teal-800 font-bold hover:underline">ویرایش شماره همراه</button>
                </div>

                <!-- مرحله سوم: انتخاب فرزند (فقط در حالت چندفرزندی) -->
                <div id="stepChooseChild" class="space-y-4 hidden">
                    <h3 class="text-sm font-bold text-center text-gray-700">لطفاً فرزند مورد نظر را برای مشاهده انتخاب کنید:</h3>
                    <div id="childrenContainer" class="space-y-2">
                        <!-- دکمه‌های فرزندان پویا لود می‌شوند -->
                    </div>
                </div>
            </div>

            <!-- ۲. پیشخوان پورتال اولیا (نمایش بعد از لاگین موفق) -->
            <div id="portalDashboard" class="hidden space-y-6">
                <!-- کارت مشخصات فرزند -->
                <div class="bg-white rounded-2xl shadow-md p-6 text-center space-y-4">
                    <div class="flex justify-center">
                        <img id="childAvatar" src="{inst_logo}" data-auth-src="{inst_logo_auth}" class="w-20 h-20 rounded-full border-2 border-teal-800">
                    </div>
                    <h2 id="tvChildName" class="text-xl font-bold text-teal-800">نام فرزند شما</h2>
                    <p id="tvChildCode" class="text-sm text-gray-500">کد ملی: ---</p>
                    <button id="btnLogoutPortal" class="text-xs text-red-600 border border-red-300 px-3 py-1 rounded-lg hover:bg-red-50 transition">خروج از پورتال</button>
                </div>

                <!-- کارت وضعیت بدهی و مالی -->
                <div class="bg-white rounded-2xl shadow-md p-6 space-y-3">
                    <h3 class="text-md font-bold text-teal-800 border-b pb-2">💳 وضعیت شهریه و بدهی</h3>
                    <div class="flex justify-between items-center py-2">
                        <span class="text-sm text-gray-600">کل بدهی شهریه:</span>
                        <span id="tvTotalDebt" class="text-lg font-bold text-red-600">۰ تومان</span>
                    </div>
                    <div class="flex justify-between items-center py-2">
                        <span class="text-sm text-gray-600">تراز کیف پول کلاینت:</span>
                        <span id="tvWalletBalance" class="text-lg font-bold">۰ تومان</span>
                    </div>
                </div>

                <!-- بخش اقساط شهریه -->
                <div class="bg-white rounded-2xl shadow-md p-6 space-y-3">
                    <h3 class="text-md font-bold text-teal-800 border-b pb-2">📅 اقساط شهریه</h3>
                    <div id="installmentsContainer" class="space-y-3 pt-2">
                        <!-- لیست اقساط پویا لود می‌شوند -->
                    </div>
                </div>

                <!-- بخش کارنامه نمرات -->
                <div class="bg-white rounded-2xl shadow-md p-6 space-y-3">
                    <h3 class="text-md font-bold text-teal-800 border-b pb-2">📈 کارنامه نمرات تجمیعی</h3>
                    <div id="gradesContainer" class="space-y-3 pt-2">
                        <!-- لیست نمرات و میانگین‌ها پویا لود می‌شوند -->
                    </div>
                </div>

                <!-- بخش حضور و غیاب -->
                <div class="bg-white rounded-2xl shadow-md p-6 space-y-3">
                    <h3 class="text-md font-bold text-teal-800 border-b pb-2">📅 تاریخچه حضور و غیاب</h3>
                    <div id="attendanceContainer" class="space-y-3 pt-2 max-h-60 overflow-y-auto">
                        <!-- لیست حضور غیاب پویا لود می‌شوند -->
                    </div>
                </div>
            </div>

            <!-- اطلاعات ثابت آموزشگاه در پایین صفحه -->
            <footer class="text-center text-xs text-gray-400 py-8 space-y-2">
                <p>📍 آدرس: {inst_address}</p>
                <p>📞 تلفن تماس: {inst_phone} | ✉️ ایمیل: {inst_email}</p>
            </footer>
        </div>

        <script>
            const API_BASE = window.location.origin + "/";
            let tempToken = "";
            let verifiedMobile = "";
...

            // FIX M3-portal: لود عکس آپلودی با توکن (اندپوینت /uploads دیگر عمومی نیست).
            // عمومی برای همه‌ی img های پورتال: کافی است data-auth-src داشته باشند یا مستقیم صدا شود.
            async function loadAuthImage(imgEl, url) {
                if (!imgEl || !url) return;
                if (!url.startsWith("/") && !url.startsWith(API_BASE)) { imgEl.src = url; return; } // URL خارجی/عمومی بدون توکن
                try {
                    const token = localStorage.getItem("parent_token");
                    if (!token) return; // لاگین نکرده: همان placeholder فعلی می‌ماند.
                    const res = await fetch(url, { headers: { "Authorization": "Bearer " + token } });
                    if (!res.ok) return; // 401 (توکن منقضی) / 404: placeholder حفظ می‌شود، بدون کرش.
                    imgEl.src = URL.createObjectURL(await res.blob());
                } catch (e) {
                    // خطای شبکه: placeholder فعلی حفظ می‌شود.
                }
            }

            // FIX M3-portal: لود خودکار همه‌ی عکس‌های آپلودی رندرشده در HTML.
            document.addEventListener("DOMContentLoaded", () => {
                document.querySelectorAll("img[data-auth-src]").forEach(img => {
                    const u = img.getAttribute("data-auth-src");
                    if (u) loadAuthImage(img, u);
                });
            });

            // بررسی خودکار وجود سشن فعال در حافظه مرورگر اولیا (localStorage)
            document.addEventListener("DOMContentLoaded", () => {
                const savedToken = localStorage.getItem("parent_token");
                if (savedToken) {
                    loadChildProfile(savedToken);
                } else {
                    document.getElementById("loginSection").classList.remove("hidden");
                }
            });

            // درخواست کد تایید OTP
            document.getElementById("btnRequestOtp").addEventListener("click", async () => {
                const mobile = document.getElementById("parentMobile").value.trim();
                if (mobile.length !== 11) {
                    alert("لطفاً شماره همراه ۱۱ رقمی معتبری وارد کنید.");
                    return;
                }

                try {
                    const res = await fetch(API_BASE + "parent/request_otp", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ mobile: mobile })
                    });
                    const data = await res.json();
                    if (res.status === 200) {
                        verifiedMobile = mobile;
                        document.getElementById("stepRequest").classList.add("hidden");
                        document.getElementById("stepVerify").classList.remove("hidden");
                        alert(data.message);
                    } else {
                        alert(data.detail || "خطا در برقراری ارتباط با سرور");
                    }
                } catch (e) {
                    alert("خطا در ارسال درخواست.");
                }
            });

            // بازگشت به ویرایش شماره
            document.getElementById("btnBackToRequest").addEventListener("click", () => {
                document.getElementById("stepVerify").classList.add("hidden");
                document.getElementById("stepRequest").classList.remove("hidden");
            });

            // لاگین با کد یک‌بارمصرف
            document.getElementById("btnLogin").addEventListener("click", async () => {
                const otp = document.getElementById("otpCode").value.trim();
                if (otp.length < 4) {
                    alert("کد تایید معتبر نیست.");
                    return;
                }

                try {
                    const res = await fetch(API_BASE + "parent/login", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ mobile: verifiedMobile, otp: otp })
                    });
                    const data = await res.json();
                    if (res.status === 200) {
                        if (data.multiple_children) {
                            // سناریو چندفرزندی: لود لیست برای انتخاب
                            tempToken = data.temp_token;
                            document.getElementById("stepVerify").classList.add("hidden");
                            document.getElementById("stepChooseChild").classList.remove("hidden");
                            
                            const container = document.getElementById("childrenContainer");
                            container.innerHTML = "";
                            data.children.forEach(child => {
                                const btn = document.createElement("button");
                                btn.className = "w-full bg-teal-50 border-2 border-teal-800 text-teal-800 p-3 rounded-xl font-bold hover:bg-teal-100 transition";
                                btn.innerText = child.name;
                                btn.addEventListener("click", () => selectChild(child.id));
                                container.appendChild(btn);
                            });
                        } else {
                            // یک فرزندی: لاگین مستقیم
                            localStorage.setItem("parent_token", data.token);
                            document.getElementById("loginSection").classList.add("hidden");
                            loadChildProfile(data.token);
                        }
                    } else {
                        alert(data.detail || "کد تایید نامعتبر است");
                    }
                } catch (e) {
                    alert("خطا در تایید کد.");
                }
            });

            // انتخاب فرزند مخصوص چندفرزندی
            async function selectChild(studentId) {
                try {
                    const res = await fetch(API_BASE + "parent/select_child", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ student_id: studentId, temp_token: tempToken })
                    });
                    const data = await res.json();
                    if (res.status === 200) {
                        localStorage.setItem("parent_token", data.token);
                        document.getElementById("loginSection").classList.add("hidden");
                        loadChildProfile(data.token);
                    } else {
                        alert(data.detail || "خطا در انتخاب فرزند");
                    }
                } catch (e) {
                    alert("خطا در ثبت نهایی انتخاب.");
                }
            }

            // خروج از پورتال
            document.getElementById("btnLogoutPortal").addEventListener("click", () => {
                localStorage.removeItem("parent_token");
                window.location.reload();
            });

            // دریافت و رندر مشخصات فرزند
            async function loadChildProfile(token) {
                try {
                    const res = await fetch(API_BASE + "parent/child_profile", {
                        headers: { "Authorization": "Bearer " + token }
                    });
                    if (res.status === 401) {
                        // توکن منقضی شده
                        localStorage.removeItem("parent_token");
                        document.getElementById("loginSection").classList.remove("hidden");
                        document.getElementById("portalDashboard").classList.add("hidden");
                        alert("⚠️ نشست شما منقضی شده است، لطفاً مجدداً وارد شوید.");
                        return;
                    }
                    const data = await res.json();
                    if (res.status === 200) {
                        document.getElementById("loginSection").classList.add("hidden");
                        document.getElementById("portalDashboard").classList.remove("hidden");

                        // ۱. رندر اطلاعات هویتی
                        document.getElementById("tvChildName").innerText = data.info.name;
                        document.getElementById("tvChildCode").innerText = "کد ملی: " + data.info.national_code;
                        if (data.info.profile_image) {
                            loadAuthImage(document.getElementById("childAvatar"), API_BASE + "uploads/profiles/" + data.info.profile_image);
                        }

                        // ۲. رندر بدهی و کیف پول
                        const bal = data.wallet.balance;
                        const totalDebt = data.wallet.total_debt;
                        document.getElementById("tvTotalDebt").innerText = totalDebt.toLocaleString() + " تومان";
                        
                        const walletView = document.getElementById("tvWalletBalance");
                        walletView.innerText = Math.abs(bal).toLocaleString() + " تومان " + (bal < 0 ? "[بدهکار]" : "[بستانکار]");
                        walletView.className = "text-lg font-bold " + (bal < 0 ? "text-red-600" : "text-green-600");

                        // ۳. رندر اقساط شهریه
                        const instContainer = document.getElementById("installmentsContainer");
                        instContainer.innerHTML = "";
                        if (data.installments.length === 0) {
                            instContainer.innerHTML = "<p class='text-xs text-gray-400 text-center py-2'>هیچ قسطی ثبت نشده است</p>";
                        } else {
                            data.installments.forEach(inst => {
                                const color = inst.status === "پرداخت شده" ? "bg-green-100 text-green-800" : (inst.status === "معوقه" ? "bg-red-100 text-red-800" : "bg-yellow-100 text-yellow-800");
                                instContainer.innerHTML += `
                                    <div class="p-3 border rounded-xl flex justify-between items-center text-xs">
                                        <div class="space-y-1">
                                            <p class="font-bold text-gray-700">${inst.course_title}</p>
                                            <p class="text-gray-400">📅 سررسید: ${inst.due_date}</p>
                                        </div>
                                        <div class="text-left space-y-1">
                                            <p class="font-bold text-teal-800">${inst.amount.toLocaleString()} تومان</p>
                                            <span class="px-2 py-0.5 rounded-full font-bold ${color}">${inst.status}</span>
                                        </div>
                                    </div>
                                `;
                            });
                        }

                        // ۴. رندر نمرات و میانگین‌ها
                        const gradesContainer = document.getElementById("gradesContainer");
                        gradesContainer.innerHTML = "";
                        if (data.grades.length === 0) {
                            gradesContainer.innerHTML = "<p class='text-xs text-gray-400 text-center py-2'>هنوز نمره‌ای ثبت نشده است</p>";
                        } else {
                            // نمایش میانگین‌ها در ابتدا
                            if (Object.keys(data.averages).length > 0) {
                                let avgsHtml = "<div class='p-3 bg-teal-50 border border-teal-200 rounded-xl mb-3 space-y-1'><p class='text-xs font-bold text-teal-800 mb-2'>📊 میانگین نمرات دروس:</p>";
                                for (const [course, avg] of Object.entries(data.averages)) {
                                    avgsHtml += `<div class="flex justify-between text-xs text-teal-900"><span>• ${course}:</span><span class="font-bold">${avg}</span></div>`;
                                }
                                avgsHtml += "</div>";
                                gradesContainer.innerHTML += avgsHtml;
                            }

                            // لیست نمرات
                            data.grades.forEach(g => {
                                gradesContainer.innerHTML += `
                                    <div class="p-3 border rounded-xl flex justify-between items-center text-xs">
                                        <div class="space-y-1">
                                            <p class="font-bold text-gray-700">${g.course_name} (${g.exam_title})</p>
                                            <p class="text-gray-400">📅 تاریخ: ${g.date}</p>
                                        </div>
                                        <div class="font-bold text-teal-800 text-sm">${g.score} از ${g.max_score}</div>
                                    </div>
                                `;
                            });
                        }

                        // ۵. رندر تاریخچه حضور و غیاب
                        const attContainer = document.getElementById("attendanceContainer");
                        attContainer.innerHTML = "";
                        if (data.attendance.length === 0) {
                            attContainer.innerHTML = "<p class='text-xs text-gray-400 text-center py-2'>هیچ حضور و غیابی ثبت نشده است</p>";
                        } else {
                            data.attendance.forEach(att => {
                                const color = att.status === "حاضر" ? "text-green-600 bg-green-50 border-green-200" : (att.status === "تاخیر" ? "text-yellow-600 bg-yellow-50 border-yellow-200" : "text-red-600 bg-red-50 border-red-200");
                                attContainer.innerHTML += `
                                    <div class="p-3 border rounded-xl flex justify-between items-center text-xs bg-white">
                                        <div class="space-y-1">
                                            <p class="font-bold text-gray-700">${att.course_title}</p>
                                            <p class="text-gray-400">📅 تاریخ: ${att.date}</p>
                                        </div>
                                        <span class="px-3 py-1 border rounded-lg font-bold ${color}">${att.status}</span>
                                    </div>
                                `;
                            });
                        }

                    } else {
                        alert("خطا در دریافت اطلاعات پروفایل.");
                    }
                } catch (e) {
                    alert("خطا در اتصال به شبکه.");
                }
            }
        </script>
    </body>
    </html>
    """
    html_content = html_content.replace("{inst_name}", inst_name)\
                               .replace("{inst_logo}", inst_logo)\
                               .replace("{inst_logo_auth}", inst_logo_auth)\
                               .replace("{inst_address}", inst_address)\
                               .replace("{inst_phone}", inst_phone)\
                               .replace("{inst_email}", inst_email or "")
    return html_content
