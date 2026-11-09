from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Header, Request
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional, Union
from sqlalchemy import desc, or_, text, func
import io
import uuid
import os
import datetime
import random

import models
from models import (
    Attendance, Course, Enrollment, Grade, InstituteShare, SessionLog, SmsLog, Student, Teacher, Transaction, User, UserSession, ActivityLog, DeviceToken, Notification, ParentOTP
)
from schemas import (
    HistoryRequest, LoginRequest, TeacherInfo, FullTeacherProfile, StudentCreate, TeacherCreate, CourseCreate, EnrollmentCreate, GradeCreate, GradeItem, AttendanceLogRequest, AttendanceItem, AttendanceSubmitData, SmsSendRequest, ChangePasswordRequest, StudentProfileInfo, FullStudentProfile, TeacherProfileInfo, FullTeacherProfile, ClassReportInfo, ClassStudentData, ClassSessionHistory, FullClassReport, ShareConfigModel, StudentUpdate, TeacherUpdate, PersonListItem, TransactionUpdate, StudentAttendanceHistoryRequest, AdvancedSearchItem, FinanceSubmitData, PrintReceiptRequest, TransactionTestData
)
from dependencies import get_db, check_admin_access, check_user_login, get_enrollment_tuition_and_discount, SESSION_EXPIRY_DAYS, limiter, get_current_user, hash_password, verify_password, ROLE_PERMISSIONS, create_jwt_token, ensure_student_shadow_users, get_session_student, get_session_parent, normalize_mobile, resolve_notification_role, display_name, safe_person_name

router = APIRouter()

@router.post("/auth/login")
@limiter.limit("5/5minutes")
def login_user(request: Request, req: LoginRequest, db: Session = Depends(get_db)):
    # FIX H14: throttle جداگانه per-mobile (مستقل از IP-limit که پشت تانل تک‌سطلی بود).
    from models import LoginAttempt  # lazy
    # FIX H20-B2: ورودی canonical برای throttle و lookupها؛ نامعتبر → همان خطاهای «یافت نشد» پایین.
    _raw_login = (req.mobile or "").strip()
    login_mobile = normalize_mobile(_raw_login)
    _throttle_mobile = login_mobile or _raw_login  # کلید H14: canonical وقتی ممکن است (بستن دورزدن با چرخش فرمت)
    # FIX H20-ESC (escape-hatch موقت تا بچ۳): fallback خام برای جلوگیری از lockout ردیف‌های legacy.
    # کلید throttle عمداً دست‌نخورده (canonical) — فقط lookup هویت دو کلیده است (پسورد همچنان گیت واقعی).
    _login_keys = []
    if login_mobile:
        _login_keys.append(login_mobile)
    if _raw_login not in _login_keys:
        _login_keys.append(_raw_login)
    _window_start = datetime.datetime.utcnow() - datetime.timedelta(minutes=5)
    _recent_fails = db.query(LoginAttempt).filter(
        LoginAttempt.mobile == _throttle_mobile,
        LoginAttempt.attempted_at > _window_start
    ).count()
    if _recent_fails >= 5:
        raise HTTPException(status_code=429, detail="تعداد تلاش‌های ناموفق برای این شماره زیاد است؛ لطفاً ۵ دقیقه دیگر تلاش کنید")
    # 1. بررسی مدیر
    # FIX O-01/O-21: سایهٔ معلم (role="teacher") از شاخهٔ «ادمین» کنار گذاشته می‌شود تا به شاخهٔ
    # معلم (پایین‌تر) برسد. چرا: این lookup اول جواب می‌داد و اگر `Teacher` متناظر وجود نداشت یا
    # حذف‌شده بود، گیت‌های H10 (تأیید/تعلیق) قابل اجرا نبودند ⇒ سایهٔ بی‌پرونده توکن می‌گرفت و
    # سایهٔ معلم هم با `role="admin"` و `user_id=User.id` پاسخ می‌گرفت (اپ معلم را به پنل ادمین می‌برد).
    # اگر ادمین واقعیِ هم‌نام هم وجود داشته باشد، او اولویت دارد (پس ادمین‌ها قفل نمی‌شوند).
    _shadow_roles = ("teacher",)
    admin = next((u for u in db.query(User).filter(User.username.in_(_login_keys)).all()
                  if (u.role or "") not in _shadow_roles), None)  # FIX H20-ESC: canonical + خام (username ادمین لزوماً موبایل نیست؛ legacy هم پوشش داده می‌شود)
    if admin:
        if req.password and verify_password(req.password, admin.password):
            # (FIX E2E-B1 قبلاً همین‌جا گیت‌های H10 را برای سایهٔ معلم اجرا می‌کرد؛ حالا خودِ سایه به
            #  شاخهٔ معلم می‌رود و همان گیت‌ها آنجا اجرا می‌شود — رفتار یکسان، بدون مسیر موازی.)
            # FIX: توکن امضادار JWT به جای uuid
            # FIX(A1): نقش با سیاست کمترین سطح دسترسی — سایهٔ معلمِ legacy بدون sub_role
            # دیگر توکن «admin» نمی‌گیرد.
            from dependencies import resolve_effective_sub_role
            sub_role = resolve_effective_sub_role(admin)
            token = create_jwt_token(user_id=admin.id, sub_role=sub_role)
            new_session = UserSession(
                token=token,
                user_id=admin.id,
                sub_role=sub_role
            )
            db.add(new_session)
            db.query(LoginAttempt).filter(LoginAttempt.mobile == _throttle_mobile).delete()  # FIX H14: موفقیت ← پاک‌سازی شمارنده
            db.commit()
            return {
                "status": "success",
                "role": "admin",
                "sub_role": sub_role,
                "token": token,
                "user_id": admin.id,
                "name": admin.full_name,
                "branch_id": admin.branch_id,
                "message": "ورود مدیر موفقیت آمیز بود",
            }
        elif req.password:
            db.add(LoginAttempt(mobile=_throttle_mobile, ip=(request.client.host if request.client else None)))  # FIX H14: ثبت تلاش ناموفق
            db.commit()
            raise HTTPException(status_code=400, detail="رمز عبور اشتباه است")

    # 2. بررسی معلم
    # FIX H20-ESC: canonical + fallback خام (موقت تا بچ۳)؛ خالی ماندن _login_keys ناممکن است (_raw همیشه هست).
    teacher = db.query(Teacher).filter(Teacher.mobile.in_(_login_keys), Teacher.is_deleted == False).first()
    if teacher:
        if not verify_password(req.password, teacher.password):
            db.add(LoginAttempt(mobile=_throttle_mobile, ip=(request.client.host if request.client else None)))  # FIX H14: ثبت تلاش ناموفق
            db.commit()
            raise HTTPException(status_code=400, detail="رمز عبور اشتباه است")
        if not teacher.is_approved:
            raise HTTPException(
                status_code=403, detail="حساب شما هنوز توسط مدیر تایید نشده است"
            )
        # FIX H10: حساب معلق حتی با پسورد درست لاگین نمی‌شود (بعد از گیت تایید مدیر).
        if teacher.is_suspended:
            raise HTTPException(status_code=403, detail="حساب شما توسط مدیر معلق شده است. لطفاً با آموزشگاه تماس بگیرید")

        # FIX: عدم overwrite پسورد در هر لاگین – فقط اگر User وجود ندارد بساز، با قفل برای race
        # استفاده از with_for_update برای جلوگیری از race condition دو معلم هم‌زمان
        # FIX H20-B2 (بازنویسی K بچ۱): username سایه با lookup دقیقِ امروز + pair-heal اتمیک.
        # چرا: lookupِ canonical-first می‌توانست در تصادم true-duplicate سایه‌ی معلم دیگر را برگرداند
        # (takeover) و heal یک‌طرفه invariant سالم username==mobile را می‌شکست (ریزالورهای get_me و جز آن).
        # این نسخه جفت را همیشه سازگار نگه می‌دارد (canonical یا legacy): دقیقِ legacy اول، heal جفت فقط
        # اگر canonical آزاد باشد، adopt سایه‌ی canonical فقط اگر مال دیگری نباشد، ساخت با جفت سازگار.
        mob_norm = normalize_mobile(teacher.mobile) or teacher.mobile
        # FIX(A4): نام معلم یک‌بار و امن ساخته می‌شود تا ساخت/مقایسه/به‌روزرسانی full_name
        # و پاسخ ورود همه یک مقدار بگیرند (الگوی قدیمی با نام NULL «None None» می‌ساخت).
        _teacher_name = safe_person_name(teacher.first_name, teacher.last_name, "معلم")
        u = db.query(User).filter(User.username == teacher.mobile).with_for_update().first()
        if u is not None and (u.role or "") == "teacher" and mob_norm != teacher.mobile:
            _owner = db.query(Teacher).filter(Teacher.mobile == mob_norm, Teacher.id != teacher.id).first()
            _uclash = db.query(User).filter(User.username == mob_norm, User.id != u.id).first()
            if _owner is None and _uclash is None:
                u.username = mob_norm
                teacher.mobile = mob_norm
        if u is None and mob_norm != teacher.mobile:
            _cand = db.query(User).filter(User.username == mob_norm, User.role == "teacher").first()
            if _cand is not None:
                _owner2 = db.query(Teacher).filter(Teacher.mobile == mob_norm, Teacher.id != teacher.id).first()
                if _owner2 is None:
                    u = _cand
                    teacher.mobile = mob_norm
        if not u:
            _new_name = teacher.mobile
            if mob_norm != teacher.mobile:
                _owner3 = db.query(Teacher).filter(Teacher.mobile == mob_norm, Teacher.id != teacher.id).first()
                _uclash3 = db.query(User).filter(User.username == mob_norm).first()
                if _owner3 is None and _uclash3 is None:
                    teacher.mobile = mob_norm
                    _new_name = mob_norm
            # FIX F-B2: race اولین لاگین همزمان → ساخت سایه با savepoint + catch IntegrityError
            from sqlalchemy.exc import IntegrityError  # local: فقط همین‌جا
            _candidate = User(
                username=_new_name,
                password=teacher.password,  # از Teacher هش کپی می‌شود فقط بار اول
                full_name=_teacher_name,
                role="teacher",
                sub_role="teacher",
                branch_id=teacher.branch_id
            )
            try:
                with db.begin_nested():
                    db.add(_candidate)
                    db.flush()
                u = _candidate
            except IntegrityError:
                # برنده‌ی مسابقه قبلاً همین username را ساخته؛ خودترمیم با fetch
                u = db.query(User).filter(User.username == _new_name).first()
                if u is None and _new_name != teacher.mobile:
                    u = db.query(User).filter(User.username == teacher.mobile).first()
                if u is None and mob_norm != _new_name and mob_norm != teacher.mobile:
                    u = db.query(User).filter(User.username == mob_norm).first()
                if u is None:
                    raise
                # همگام‌سازی سبک اگر برنده قدیمی باشد
                if u.full_name != _teacher_name:
                    u.full_name = _teacher_name
                if u.branch_id != teacher.branch_id:
                    u.branch_id = teacher.branch_id
                db.flush()
        else:
            # FIX: فقط full_name و branch_id را همگام کن، نه پسورد
            # اگر موبایل معلم عوض شده باشد، User.username قدیمی می‌ماند – برای همین teacher_id را جدا ذخیره می‌کنیم
            if u.full_name != _teacher_name:
                u.full_name = _teacher_name
            if u.branch_id != teacher.branch_id:
                u.branch_id = teacher.branch_id
            db.flush()

        # FIX: JWT با user_id = User.id ولی teacher_id هم در سشن ذخیره می‌شود برای mapping پایدار
        token = create_jwt_token(user_id=u.id, sub_role="teacher")
        new_session = UserSession(
            token=token,
            user_id=u.id,
            teacher_id=teacher.id,  # FIX: mapping مستقیم و مقاوم به تغییر موبایل
            sub_role="teacher"
        )
        db.add(new_session)
        db.query(LoginAttempt).filter(LoginAttempt.mobile == _throttle_mobile).delete()  # FIX H14: موفقیت ← پاک‌سازی شمارنده
        db.commit()

        return {
            "status": "success",
            "role": "teacher",
            # FIX O-01: `sub_role` هم مثل شاخهٔ ادمین برگردانده می‌شود؛ بدون آن اپ
            # (`LoginActivity.kt` → `USER_SUB_ROLE = response.sub_role ?: "admin"`) برای معلم
            # «admin» ذخیره می‌کرد (دکمهٔ ویژهٔ مدیر در تنظیمات معلم نمایان می‌شد).
            "sub_role": "teacher",
            "token": token,
            "user_id": teacher.id,  # برای سازگاری با اندروید که Teacher.id انتظار دارد
            "name": _teacher_name,
            "branch_id": teacher.branch_id,
            "message": "ورود معلم موفقیت آمیز بود",
        }

    raise HTTPException(status_code=404, detail="کاربری با این شماره یافت نشد")


# ==========================================
# 1. مدل‌های ورودی (Schemas)
# ==========================================
# --- مدل‌های معلم ---
class TeacherInfo(BaseModel):
    name: str
    mobile: str
    national_code: str
    status: str


class FullTeacherProfile(BaseModel):
    info: TeacherInfo
    total_students: int
    total_revenue: int
    active_classes_count: int
    classes: List[str]


class StudentCreate(BaseModel):
    first_name: str
    last_name: str
    father_name: str
    national_code: str
    birth_date: str
    student_mobile: str
    parent_mobile: str
    home_phone: str
    address: str
    study_status: str
    gender: str


class TeacherCreate(BaseModel):
    first_name: str
    last_name: str
    father_name: str
    national_code: str
    birth_date: str
    mobile: str
    password: str
    home_phone: str
    marital_status: str
    gender: str
    employment_type: str
    card_number: str
    profile_image: Optional[str] = None


class CourseCreate(BaseModel):
    title: str
    code: str
    teacher_id: int
    education_type: str
    grade_level: str
    gender_type: str
    class_type: str = "خصوصی"
    days_of_week: str = "نامشخص"
    class_time: str = "نامشخص"
    teacher_session_price: int
    rule_prepay_institute: bool = False
    rule_prepay_teacher: bool = False
    rule_calc_absent: bool = True
    bg_color: str = "#FFFFFF"


class EnrollmentCreate(BaseModel):
    student_id: int
    course_id: int
    register_date: str
    shift: str
    total_tuition: int
    paid_amount: int
    payment_method: str
    receiver: str
    discount_type: Optional[str] = "none"
    discount_value: Optional[int] = 0


# مدل‌های مربوط به نمره
class GradeCreate(BaseModel):
    student_id: int
    course_id: int
    exam_title: str
    score: float
    max_score: float
    date: str
    description: str = ""


class GradeItem(BaseModel):
    course_name: str
    exam_title: str
    score: float
    max_score: float
    date: str


# ==========================================
# 2. API های داشبورد و آمار
# ==========================================


@router.post("/auth/change-password")
def change_password(req: ChangePasswordRequest, authorization: Optional[str] = Header(None), db: Session = Depends(get_db), _: str = Depends(check_user_login)):
    if not authorization:
        raise HTTPException(status_code=401, detail="توکن احراز هویت یافت نشد")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="قالب توکن معتبر نیست")
    token = parts[1]
    session = db.query(UserSession).filter(UserSession.token == token).first()
    if not session:
        raise HTTPException(status_code=401, detail="نشست معتبر نیست یا منقضی شده است")
    
    # FIX(security): تشخیص نقش از روی سشن؛ معلم روی رکورد Teacher، بقیه‌ی نقش‌ها روی User.
    role = session.sub_role or ""
    # FIX H20-B2: اثبات هویت با raw-OR-canonical (بدون lockout برای legacy؛ مهاجم سودی نمی‌برد چون پسورد/سشن هم لازم است). lookups بالا norm-only هستند چون باید یک کلید واحد داشته باشند.
    _req_mob = normalize_mobile(req.mobile)

    if role == "teacher":
        # FIX: حل مستقیم معلم از session.teacher_id (H2)؛ fallback به هلپر فقط برای سشن‌های قدیمی بدون teacher_id.
        teacher = None
        if getattr(session, "teacher_id", None):
            teacher = db.query(Teacher).filter(Teacher.id == session.teacher_id).first()
        if teacher is None:
            from routers.reports import get_logged_in_teacher
            teacher = get_logged_in_teacher(db, authorization)
        if not teacher:
            raise HTTPException(status_code=404, detail="معلم یافت نشد")
        if teacher.mobile != req.mobile and (_req_mob is None or teacher.mobile != _req_mob):
            raise HTTPException(status_code=403, detail="شما مجاز به تغییر رمز عبور کاربر دیگری نیستید")
        if not verify_password(req.old_password, teacher.password):
            raise HTTPException(status_code=400, detail="رمز عبور قدیمی اشتباه است")
        teacher.password = hash_password(req.new_password)

        # FIX: همگام‌سازی User سایه از طریق session.user_id (مقاوم به تغییر موبایل؛ username سایه
        # عمداً با موبایل جدید به‌روز نمی‌شود، پس جست‌وجو با موبایل بعد از تعویض شماره خطا می‌دهد).
        # حیاتی: لاگین اول شاخه‌ی User را چک می‌کند، پس سایه‌ی قدیمی = قفل‌شدن معلم با پسورد جدید.
        u = db.query(User).filter(User.id == session.user_id).first()
        if u is None or u.role != "teacher":
            # fallback سشن‌های قدیمی (user_id ممکن است Teacher.id باشد، نه User.id)
            u = db.query(User).filter(User.username == teacher.mobile, User.role == "teacher").first()
        if u is not None:
            u.password = teacher.password

        db.commit()
        return {"message": "رمز عبور معلم با موفقیت تغییر کرد"}

    # نقش‌های دیگر (admin/secretary/...) — منطق فعلی User دست‌نخورده
    # برای افزایش امنیت، فقط به خود کاربر اجازه تغییر رمز عبور خودش را می‌دهیم
    user = db.query(User).filter(User.id == session.user_id).first()
    if user:
        if user.username != req.mobile and (_req_mob is None or user.username != _req_mob):
            raise HTTPException(status_code=403, detail="شما مجاز به تغییر رمز عبور مربی یا کاربر دیگری نیستید")
        if not verify_password(req.old_password, user.password):
            raise HTTPException(status_code=400, detail="رمز عبور قدیمی اشتباه است")
        user.password = hash_password(req.new_password)
        db.commit()
        return {"message": "رمز عبور مدیر با موفقیت تغییر کرد"}

    raise HTTPException(status_code=400, detail="کاربر یافت نشد")

@router.post("/auth/logout")
def logout_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db), device_token: Optional[str] = None, _: str = Depends(check_user_login)):
    if not authorization:
        raise HTTPException(status_code=400, detail="توکن یافت نشد")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=400, detail="قالب توکن معتبر نیست")
    token = parts[1]
    session = db.query(UserSession).filter(UserSession.token == token).first()
    if session:
        role = session.sub_role or "student"
        # FIX M18: فقط دیوایس فعلی (ردیف همین FCM token) باطل می‌شود، نه همه‌ی دیوایس‌های کاربر.
        # درخواست logout شناسه‌ی دیوایس ندارد، پس کالر باید device_token خودش را بفرستد؛ اگر نفرستاد
        # هیچ ردیف push پاک نمی‌شود (نمی‌دانیم کدام مال این دیوایس است). اسکوپ user/role جلوی پاک‌سازی
        # متقاطع را می‌گیرد حتی اگر توکنِ فرستاده‌شده مال کاربر دیگری باشد (idempotent: هیچ‌چیز).
        if device_token:
            db.query(DeviceToken).filter(
                DeviceToken.token == device_token,
                DeviceToken.user_id == session.user_id,
                DeviceToken.role == role,
            ).delete()
        db.delete(session)
        db.commit()
    return {"message": "خروج با موفقیت انجام شد و نشست باطل گردید"}

@router.get("/auth/me")
def get_me(authorization: Optional[str] = Header(None), db: Session = Depends(get_db), _: str = Depends(check_user_login)):
    if not authorization:
        raise HTTPException(status_code=401, detail="توکن یافت نشد")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="قالب توکن معتبر نیست")
    token = parts[1]
    session = db.query(UserSession).filter(UserSession.token == token).first()
    if not session:
        raise HTTPException(status_code=401, detail="نشست نامعتبر یا منقضی شده است")
        
    role = session.sub_role or "student"
    if role.startswith("temp_parent:"):
        role = "parent"
        
    permissions = ROLE_PERMISSIONS.get(role, [])
    
    user_name = "کاربر سیستم"
    user_id = session.user_id
    
    if role == "teacher":
        # FIX M19 (الگوی H1/H8): اول teacher_id مستقیم سشن (مقاوم به تغییر موبایل)،
        # بعد fallback به mobile==username برای سشن‌های قدیمیِ بدون teacher_id.
        teacher = None
        if getattr(session, "teacher_id", None):
            teacher = db.query(Teacher).filter(Teacher.id == session.teacher_id).first()
        if teacher is None:
            user_obj = db.query(User).filter(User.id == session.user_id).first()
            if user_obj:
                teacher = db.query(Teacher).filter(Teacher.mobile == user_obj.username).first()
        if teacher:
            user_name = display_name(teacher, "نامشخص")
            user_id = teacher.id
    elif role in ["admin", "secretary"]:
        user = db.query(User).filter(User.id == session.user_id).first()
        if user:
            user_name = user.full_name
            user_id = user.id
    elif role == "parent":
        student = get_session_parent(db, session)
        if not student:
            raise HTTPException(status_code=401, detail="نشست معتبر نیست؛ لطفاً دوباره وارد شوید")
        user_name = f"ولی {safe_person_name(student.first_name, student.last_name, 'دانش‌آموز')}"
        user_id = student.id
    elif role == "student":
        student = get_session_student(db, session)
        if not student:
            raise HTTPException(status_code=401, detail="نشست معتبر نیست؛ لطفاً دوباره وارد شوید")
        user_name = display_name(student, "نامشخص")
        user_id = student.id
            
    return {
        "user_id": user_id,
        "name": user_name,
        "role": role,
        "permissions": permissions if "*" not in permissions else ["*"]
    }

class StudentOtpRequest(BaseModel):
    mobile: str

class StudentLoginRequest(BaseModel):
    mobile: str
    otp: str

@router.post("/auth/student/request_otp")
@limiter.limit("5/5minutes")
def request_student_otp(request: Request, req: StudentOtpRequest, db: Session = Depends(get_db)):
    # FIX H20-B2: ورودی canonical (کوئری + کلیدهای OTP/rate)؛ نامعتبر → همان 404 «یافت نشد».
    _raw_mob = (req.mobile or "").strip()
    if not _raw_mob:
        raise HTTPException(status_code=400, detail="شماره موبایل الزامی است")
    mobile = normalize_mobile(_raw_mob)
    if not mobile:
        raise HTTPException(status_code=404, detail="شماره همراه دانش‌آموز در سیستم یافت نشد")
        
    student = db.query(Student).filter(Student.student_mobile.in_([mobile, _raw_mob]), Student.is_deleted == False).first()  # FIX H20-ESC
    if not student:
        raise HTTPException(status_code=404, detail="شماره همراه دانش‌آموز در سیستم یافت نشد")
    # FIX H10: برای حساب معلق، OTP (هزینه‌ی SMS) صادر نمی‌شود.
    if student.is_suspended:
        raise HTTPException(status_code=403, detail="حساب شما توسط مدیر معلق شده است. لطفاً با آموزشگاه تماس بگیرید")

    # FIX: per-mobile rate limiting – حداکثر 3 درخواست در 5 دقیقه
    now = datetime.datetime.utcnow()
    five_min_ago = now - datetime.timedelta(minutes=5)
    recent_count = db.query(ParentOTP).filter(
        ParentOTP.mobile == mobile,
        ParentOTP.created_at > five_min_ago
    ).count()
    if recent_count >= 3:
        raise HTTPException(status_code=429, detail="تعداد درخواست کد برای این شماره زیاد است، لطفاً 5 دقیقه صبر کنید")

    # FIX: بررسی قفل به خاطر تلاش‌های ناموفق قبلی
    locked = db.query(ParentOTP).filter(
        ParentOTP.mobile == mobile,
        ParentOTP.is_locked == True,
        ParentOTP.locked_until != None,
        ParentOTP.locked_until > now
    ).first()
    if locked:
        raise HTTPException(status_code=429, detail="این شماره به دلیل تلاش‌های ناموفق قفل شده، لطفاً بعداً تلاش کنید")
        
    # FIX: Generate 6-digit code
    otp_code = str(random.randint(100000, 999999))
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=3)  # FIX: کوتاه‌تر 3 دقیقه
    
    # FIX: هش کردن OTP – هرگز plaintext ذخیره نشود
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
    
    # Log sms – متن شامل کد اصلی است (فقط برای ارسال)
    db.add(SmsLog(
        target_group=f"student_otp_{mobile}",
        message_text=f"کد تایید ورود به پورتال دانش‌آموز خوارزمی: {otp_code}",
        sent_count=1,
        date=datetime.datetime.now().strftime("%Y/%m/%d %H:%M")
    ))
    db.commit()
    
    return {
        "status": "success",
        "message": "کد یک‌بارمصرف ورود دانش‌آموز با موفقیت ارسال شد"
    }

@router.post("/auth/student/login")
@limiter.limit("5/5minutes")
def student_login(request: Request, req: StudentLoginRequest, db: Session = Depends(get_db)):
    # FIX H20-B2: ورودی canonical؛ نامعتبر → همان 400 کد نامعتبر (رفتار شماره‌ی ناشناس امروز).
    _raw_mob = (req.mobile or "").strip()
    mobile = normalize_mobile(_raw_mob)
    if not mobile:
        raise HTTPException(status_code=400, detail="کد تایید نامعتبر یا منقضی شده است")
    otp = req.otp.strip()
    
    now = datetime.datetime.utcnow()
    # FIX: پیدا کردن آخرین OTP معتبر (is_used=False, not expired, not locked)
    otp_record = (
        db.query(ParentOTP)
        .filter(
            ParentOTP.mobile.in_([mobile, _raw_mob]),  # FIX H20-ESC (فقط selector؛ شمارش‌ها canonical می‌مانند)
            ParentOTP.is_used == False,
            ParentOTP.expires_at > now,
            ParentOTP.is_locked == False
        )
        .order_by(desc(ParentOTP.id))
        .first()
    )
    if not otp_record:
        raise HTTPException(status_code=400, detail="کد تایید نامعتبر یا منقضی شده است")

    # FIX: بررسی هش
    from dependencies import verify_password
    if not verify_password(otp, otp_record.otp):
        # FIX: افزایش شمارنده تلاش
        otp_record.attempts = (otp_record.attempts or 0) + 1
        if otp_record.attempts >= 5:
            otp_record.is_locked = True
            otp_record.locked_until = now + datetime.timedelta(minutes=15)  # قفل 15 دقیقه
        db.commit()
        raise HTTPException(status_code=400, detail="کد تایید نامعتبر است")
        
    otp_record.is_used = True
    db.commit()
    
    student = db.query(Student).filter(Student.student_mobile.in_([mobile, _raw_mob]), Student.is_deleted == False).first()  # FIX H20-ESC
    if not student:
        raise HTTPException(status_code=404, detail="دانش‌آموز یافت نشد")
    # FIX H10: حساب معلق حتی با OTP درست لاگین نمی‌شود.
    if student.is_suspended:
        raise HTTPException(status_code=403, detail="حساب شما توسط مدیر معلق شده است. لطفاً با آموزشگاه تماس بگیرید")

    # FIX(H2): سشن به سایه‌ی student اشاره می‌کند، نه Student.id (با ساخت lazy اگر نیست)
    from dependencies import create_jwt_token
    ensure_student_shadow_users(db, student)
    token = create_jwt_token(user_id=student.user_id, sub_role="student")
    new_session = UserSession(
        token=token,
        user_id=student.user_id,
        sub_role="student"
    )
    db.add(new_session)
    db.commit()
    
    return {
        "status": "success",
        "token": token,
        "student_name": display_name(student, "نامشخص")
    }

class DeviceTokenRequest(BaseModel):
    token: str

@router.post("/auth/device_token")
def register_device_token(req: DeviceTokenRequest, db: Session = Depends(get_db), current_user = Depends(get_current_user), _: str = Depends(check_user_login)):
    # FIX: جلوگیری از hijack توکن دستگاه
    role = current_user.sub_role or "student"
    if role.startswith("temp_parent:"):
        role = "parent"
        
    existing = db.query(DeviceToken).filter(DeviceToken.token == req.token).first()
    if existing:
        # FIX: اگر توکن متعلق به کاربر دیگری است، reject
        if existing.user_id != current_user.id or existing.role != role:
            raise HTTPException(status_code=403, detail="این توکن دستگاه قبلاً به کاربر دیگری اختصاص دارد و قابل تصاحب نیست")
        # اگر متعلق به خود کاربر است، فقط timestamp را به‌روزرسانی کن
        existing.user_id = current_user.id
        existing.role = role
    else:
        new_token = DeviceToken(
            user_id=current_user.id,
            role=role,
            token=req.token
        )
        db.add(new_token)
    db.commit()
    return {"message": "توکن دستگاه با موفقیت ثبت شد"}

@router.get("/notifications")
def get_notifications(db: Session = Depends(get_db), current_user = Depends(get_current_user), _: str = Depends(check_user_login)):
    # FIX(admin-notifications): نقش با helper مشترک resolve می‌شود (نه `sub_role or "student"`)
    # تا ادمینِ legacy با sub_role خالی هم اعلان‌های نقش admin خودش را ببیند.
    role = resolve_notification_role(current_user)

    notifs = (
        db.query(Notification)
        .filter(Notification.recipient_user_id == current_user.id, Notification.recipient_role == role)
        .order_by(desc(Notification.created_at))
        .all()
    )
    return [
        {
            "id": n.id,
            "type": n.type,
            "title": n.title,
            "body": n.body,
            # FIX(admin-notifications): is_read می‌تواند NULL باشد (رکورد legacy) — به boolean واقعی
            # نرمال می‌شود تا پاسخ هیچ‌وقت null به کلاینت ندهد (کلاینت هم جداگانه null-safe است).
            "is_read": bool(n.is_read),
            # FIX(admin-notifications): created_at در رکوردهای legacy می‌تواند NULL باشد و
            # `None.strftime(...)` کل لیست را ۵۰۰ می‌کرد (AttributeError) ⇒ کل صندوق ادمین
            # با یک رکورد قدیمی از کار می‌افتاد. حالا رشته‌ی خالی برمی‌گردد.
            "created_at": n.created_at.strftime("%Y/%m/%d %H:%M") if n.created_at else ""
        }
        for n in notifs
    ]


@router.get("/notifications/unread_count")
def get_unread_notifications_count(db: Session = Depends(get_db), current_user = Depends(get_current_user), _: str = Depends(check_user_login)):
    """FIX(admin-notifications): شمارش اعلان‌های خوانده‌نشده‌ی خودِ کاربر (قبلاً چنین endpointی وجود نداشت).

    همین فیلترِ لیست اعمال می‌شود (recipient_user_id + role کانونیکال) ⇒ هیچ شمارش/داده‌ی
    کاربر دیگر برنمی‌گردد. is_read=NULL (رکورد legacy) خوانده‌نشده حساب می‌شود.
    """
    role = resolve_notification_role(current_user)
    base = db.query(Notification).filter(
        Notification.recipient_user_id == current_user.id,
        Notification.recipient_role == role,
    )
    total = base.count()
    unread = base.filter(or_(Notification.is_read.is_(None), Notification.is_read == False)).count()  # noqa: E712
    return {"unread": unread, "total": total}


@router.post("/notifications/{id}/read")
def mark_notification_read(id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user), _: str = Depends(check_user_login)):
    # FIX(admin-notifications): همان نقش کانونیکال لیست (وگرنه اعلانِ دیده‌شده هرگز read نمی‌شد).
    role = resolve_notification_role(current_user)

    notif = db.query(Notification).filter(Notification.id == id, Notification.recipient_user_id == current_user.id, Notification.recipient_role == role).first()
    if not notif:
        # FIX(admin-notifications): قبلاً ۲۰۰ با پیام موفقیت برمی‌گشت (no-op خاموش) و کاربر
        # فکر می‌کرد اعلان خوانده شده؛ حالا خطای controlled و بدون نشت وجود رکورد کاربر دیگر.
        raise HTTPException(status_code=404, detail="اعلان یافت نشد")
    notif.is_read = True
    db.commit()
    return {"message": "اعلان به عنوان خوانده شده ثبت شد"}


@router.post("/notifications/read_all")
def mark_all_notifications_read(db: Session = Depends(get_db), current_user = Depends(get_current_user), _: str = Depends(check_user_login)):
    # FIX(admin-notifications): همان نقش کانونیکال (فقط اعلان‌های خودِ کاربر).
    role = resolve_notification_role(current_user)

    db.query(Notification).filter(Notification.recipient_user_id == current_user.id, Notification.recipient_role == role).update({"is_read": True})
    db.commit()
    return {"message": "تمامی اعلان‌ها خوانده شدند"}


class ChangeMobileRequest(BaseModel):
    current_mobile: str
    password: str
    new_mobile: str

@router.post("/auth/change-mobile")
def change_mobile(req: ChangeMobileRequest, db: Session = Depends(get_db), current_user = Depends(get_current_user), _: str = Depends(check_user_login)):
    # FIX H20: نرمال‌سازی به‌جای رد خام H1 — ورودی معتبرِ بدفرمت تمیز و canonical ذخیره می‌شود.
    new_mobile = normalize_mobile(req.new_mobile)
    if not new_mobile:
        raise HTTPException(status_code=400, detail="فرمت شماره موبایل جدید صحیح نیست. باید ۱۰ یا ۱۱ رقم باشد")
        
    # 2. Check if new mobile is already taken by anyone in the system
    exists_user = db.query(User).filter(User.username == new_mobile).first()
    exists_teacher = db.query(Teacher).filter(Teacher.mobile == new_mobile).first()
    exists_student = db.query(Student).filter(Student.student_mobile == new_mobile).first()
    
    if exists_user or exists_teacher or exists_student:
        raise HTTPException(status_code=400, detail="این شماره موبایل قبلاً در سیستم ثبت شده و تکراری است")
        
    # 3. Check current user's password and identity
    user = db.query(User).filter(User.id == current_user.id).first()
    
    if user:
        # FIX H20-B2: اثبات هویت با raw-OR-canonical (همان استدلال change_password).
        _cur_mob = normalize_mobile(req.current_mobile)
        if user.username != req.current_mobile and (_cur_mob is None or user.username != _cur_mob):
            raise HTTPException(status_code=403, detail="شما مجاز به تغییر شماره کاربری دیگری نیستید")
        if not verify_password(req.password, user.password):
            raise HTTPException(status_code=400, detail="کلمه عبور وارد شده اشتباه است")
            
        old_mobile = user.username
        user.username = new_mobile

        # FIX: اگه کاربر معلمه، موبایل رکورد Teacher هم همگام شود تا لینک سایه (username==mobile) یتیم نشود.
        teacher_row = None
        if (user.sub_role or "") == "teacher":
            teacher_row = db.query(Teacher).filter(Teacher.mobile == old_mobile).first()
            if teacher_row is None:
                # سایه‌ی قدیمی (username با موبایل فعلی ناهماهنگ): حل از طریق سشن
                sess = db.query(UserSession).filter(UserSession.user_id == user.id).order_by(UserSession.id.desc()).first()
                if sess is not None and getattr(sess, "teacher_id", None):
                    teacher_row = db.query(Teacher).filter(Teacher.id == sess.teacher_id).first()
            if teacher_row is not None:
                # چک تداخل یکتایی قبل از commit (به‌جای IntegrityError خام)؛ خودِ رکورد مستثنی است.
                clash = db.query(Teacher).filter(Teacher.mobile == new_mobile, Teacher.id != teacher_row.id).first()
                if clash:
                    raise HTTPException(status_code=409, detail="این شماره موبایل قبلاً توسط معلم دیگری ثبت شده است")
                teacher_row.mobile = new_mobile

        # Write to activity log
        log_entry = ActivityLog(
            admin_username=old_mobile,
            action="change_teacher_mobile" if teacher_row is not None else "change_admin_mobile",
            target_id=user.id,
            target_name=user.full_name,
            details=(
                f"تغییر شماره ورود معلم از {old_mobile} به {new_mobile}"
                if teacher_row is not None
                else f"تغییر شماره ورود ادمین از {old_mobile} به {new_mobile}"
            )
        )
        db.add(log_entry)
        from sqlalchemy.exc import IntegrityError  # local: فقط همین‌جا لازم است
        try:
            db.commit()
        except IntegrityError:
            # backstop مسابقه‌ی هم‌زمان (race) بین چک‌های بالا و commit
            db.rollback()
            raise HTTPException(status_code=409, detail="این شماره موبایل قبلاً در سیستم ثبت شده است")
        
        return {"message": "شماره‌ی شما با موفقیت تغییر کرد، لطفاً دوباره با شماره‌ی جدید وارد شوید"}
        
    raise HTTPException(status_code=400, detail="کاربر سیستم یافت نشد")


# ==========================================
# 12. API جدید: پروفایل کامل دانش‌آموز (NEW)
# ==========================================
class StudentProfileInfo(BaseModel):
    name: str
    national_code: str
    student_mobile: str
    parent_mobile: str
    address: str
    is_suspended: bool = False


class FullStudentProfile(BaseModel):
    info: StudentProfileInfo
    classes: List[str]
    transactions: List[str]
    total_debt: int


# ==========================================
# 🔥 5. دریافت پروفایل کامل دانش‌آموز (با تفکیک کیف پول)
# ==========================================
