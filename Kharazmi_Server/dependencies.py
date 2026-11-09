import datetime
from typing import List, Optional, Union
from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
import models
from models import User, SessionLocal, UserSession, Student, Teacher, Course, Enrollment, Transaction, SessionLog, Attendance, Settlement, Installment, ParentOTP, SequenceCounter, InstituteSettings, ActivityLog, Notification, DeviceToken, Homework, HomeworkSubmission, Room, Conversation, ConversationParticipant, Message, Exam, ExamQuestion, ExamAttempt, Lead

SESSION_EXPIRY_DAYS = 30

# FIX: JWT secret from env for signed tokens
import os
import base64
import json
import hmac
import hashlib
import uuid

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY") or os.getenv("SECRET_KEY")
if not JWT_SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY is not set! Copy Kharazmi_Server/.env.example to Kharazmi_Server/.env "
        "and set JWT_SECRET_KEY to a random 64-char hex string "
        "(generate one with: python3 -c \"import secrets; print(secrets.token_hex(32))\") "
        "— مقدار JWT_SECRET_KEY در فایل .env ست نشده است؛ سرور بدون کلید امضا بالا نمی‌آید."
    )
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_EXPIRE_DAYS", "7"))

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")

def _b64url_decode(data: str) -> bytes:
    # FIX: handle padding for base64url
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)

def create_jwt_token(user_id: int, sub_role: str, expires_days: int = None) -> str:
    # FIX: create signed JWT-like token with user_id, role, exp
    if expires_days is None:
        expires_days = JWT_ACCESS_TOKEN_EXPIRE_DAYS
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    now = datetime.datetime.utcnow()
    exp = now + datetime.timedelta(days=expires_days)
    payload = {
        "user_id": user_id,
        "sub_role": sub_role,
        "exp": int(exp.timestamp()),
        "iat": int(now.timestamp()),
        "jti": uuid.uuid4().hex
    }
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode()
    signature = hmac.new(JWT_SECRET_KEY.encode(), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{sig_b64}"

def verify_jwt_token(token: str) -> Optional[dict]:
    # FIX: verify HMAC signature and exp
    try:
        if "." not in token:
            return None
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode()
        expected_sig = hmac.new(JWT_SECRET_KEY.encode(), signing_input, hashlib.sha256).digest()
        provided_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, provided_sig):
            return None
        payload_json = _b64url_decode(payload_b64)
        payload = json.loads(payload_json)
        exp = payload.get("exp")
        if exp is None:
            return None
        now_ts = int(datetime.datetime.utcnow().timestamp())
        if now_ts > exp:
            return None
        return payload
    except Exception:
        return None

def get_session_from_token(db: Session, token: str):
    # FIX: verify JWT first, fallback to old opaque token for backward compatibility
    jwt_payload = verify_jwt_token(token)
    if jwt_payload:
        sess = db.query(UserSession).filter(UserSession.token == token).first()
        if not sess:
            return None, jwt_payload
        expiry_limit = datetime.datetime.utcnow() - datetime.timedelta(days=SESSION_EXPIRY_DAYS)
        if sess.created_at < expiry_limit:
            db.delete(sess)
            db.commit()
            return None, None
        return sess, jwt_payload
    else:
        # FIX: a JWT-shaped token that failed verification (bad signature or expired)
        # must NOT fall back to the 30-day opaque-token lookup — reject it outright.
        # (Same shape check as verify_jwt_token: contains "." and splits into 3 parts.)
        if token and "." in token and len(token.split(".")) == 3:
            return None, None
        sess = db.query(UserSession).filter(UserSession.token == token).first()
        if not sess:
            return None, None
        expiry_limit = datetime.datetime.utcnow() - datetime.timedelta(days=SESSION_EXPIRY_DAYS)
        if sess.created_at < expiry_limit:
            db.delete(sess)
            db.commit()
            return None, None
        return sess, None

def resolve_actor_user_id(db: Session, authorization: Optional[str]) -> Optional[int]:
    """شناسه‌ی کاربرِ عامل (actor) از هدر Authorization — برای ثبت «چه کسی این کار را کرد».

    پیش‌تر این بلوک ۱۰ خطی سه بار در `routers/classes.py` کپی شده بود (حذف مستقیم، تایید، رد
    درخواست حذف) و مسیر سومِ حذف (`/admin/reject_class`) هیچ actorی ثبت نمی‌کرد. این helper
    منطق را یک‌جا می‌کند تا هر سه مسیر حذف کلاس رد پای حسابرسی یکسان داشته باشند.

    نکته: گاردهای `check_admin_access` توکن خراب را از قبل رد می‌کنند؛ این تابع فقط برای
    تعیین شناسه است و در هر خطا `None` برمی‌گرداند (هیچ استثنایی به بیزینس نمی‌رسد).
    """
    if not authorization:
        return None
    try:
        from dependencies import get_session_from_token  # خودارجاع برای هم‌خوانی با الگوی ماژول
        parts = authorization.split()
        token = parts[1] if len(parts) == 2 and parts[0].lower() == "bearer" else None
        session, _ = get_session_from_token(db, token) if token else (None, None)
        if session is not None and getattr(session, "user_id", None):
            return session.user_id
    except Exception:
        pass
    return None


def get_next_sequence_value(db: Session, name: str, start_val: int) -> int:
    # FIX: Bug 15 - atomic increments and a savepoint protect concurrent first inserts.
    from sqlalchemy import update
    from sqlalchemy.exc import IntegrityError

    increment = (
        update(SequenceCounter)
        .where(SequenceCounter.name == name)
        .values(current_value=SequenceCounter.current_value + 1)
        .returning(SequenceCounter.current_value)
    )
    value = db.execute(increment).scalar_one_or_none()
    if value is not None:
        return value
    try:
        with db.begin_nested():
            db.add(SequenceCounter(name=name, current_value=start_val))
            db.flush()
    except IntegrityError:
        # FIX: Bug 15 - another transaction created the unique name; keep the outer transaction.
        return db.execute(increment).scalar_one()
    return start_val

def get_db():
    db = models.SessionLocal()
    try:
        yield db
    finally:
        db.close()

def resolve_effective_sub_role(user) -> str:
    """نقش مؤثر کاربر با سیاست «کمترین سطح دسترسی» (A1).

    پیش‌تر هر کاربری که `sub_role` نداشت (رکوردهای legacy) در همهٔ گاردها **ادمین** فرض
    می‌شد؛ یعنی سایهٔ معلم/شاگرد/ولی ساخته‌شده پیش از افزوده‌شدن ستون `sub_role` می‌توانست
    به سطح دسترسی مدیر برسد. اکنون:

    - `sub_role` ست‌شده ⇒ همان (شامل مقادیر ویژه مثل `temp_parent:...`).
    - `sub_role` خالی/NULL ⇒ از ستون `role` استفاده می‌شود؛ و فقط اگر `role` هم خالی یا
      `admin` باشد «admin» فرض می‌شود (سازگاری با ادمین‌های legacy که فقط role=admin دارند).
    - نقش ناشناخته ⇒ همان مقدار `role` برمی‌گردد؛ در گاردها اجازهٔ عبور نمی‌گیرد (fail-closed).
    """
    sub = (getattr(user, "sub_role", None) or "").strip()
    if sub:
        return sub
    role = (getattr(user, "role", None) or "").strip()
    if role in ("", "admin"):
        return "admin"
    return role


def safe_person_name(first, last, fallback: str = "") -> str:
    """نام کامل «نام + نام‌خانوادگی» با تحمل NULL — هرگز «None None»/«None» تولید نمی‌کند (FIX A4).

    فیلدهای `first_name`/`last_name` در رکوردهای legacy می‌توانند NULL باشند؛ الگوی قدیمی
    `f"{first_name} {last_name}"` در گزارش‌ها، رسیدها، پیامک‌ها و لیست‌ها «None None» چاپ می‌کرد.
    فقط بخش‌های موجود با فاصله به هم می‌چسبند و اگر هیچ بخشی نبود، `fallback` برمی‌گردد.
    """
    parts = []
    for value in (first, last):
        text = "" if value is None else str(value).strip()
        if text:
            parts.append(text)
    return " ".join(parts) if parts else fallback


def display_name(obj, fallback: str = "") -> str:
    """نام نمایشیِ امن یک موجودیت (Student/Teacher/User/…) — `None` ⇒ `fallback` (FIX A4)."""
    if obj is None:
        return fallback
    return safe_person_name(getattr(obj, "first_name", None), getattr(obj, "last_name", None), fallback)


def check_admin_access(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    # FIX: use signed token verification
    if not authorization:
        raise HTTPException(status_code=401, detail="توکن احراز هویت یافت نشد. لطفاً مجدداً وارد شوید")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="قالب توکن احراز هویت معتبر نیست")
    token = parts[1]
    session, _ = get_session_from_token(db, token)
    if not session:
        raise HTTPException(status_code=401, detail="توکن معتبر نیست یا منقضی شده است")
    user = db.query(User).filter(User.id == session.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="کاربر یافت نشد")
    # FIX(A1): نقش با سیاست کمترین سطح دسترسی (بدون فرض «admin» برای رکورد بی‌نقش)
    sub_role = resolve_effective_sub_role(user)
    if sub_role != "admin":
        raise HTTPException(status_code=403, detail="شما دسترسی لازم برای این عملیات را ندارید")
    return sub_role

def check_admin_or_secretary_access(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    # گارد ادمین + منشی: فقط این دو نقش اجازه عبور دارند (تصمیم کاربر برای C1)
    if not authorization:
        raise HTTPException(status_code=401, detail="توکن احراز هویت یافت نشد. لطفاً مجدداً وارد شوید")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="قالب توکن احراز هویت معتبر نیست")
    token = parts[1]
    session, _ = get_session_from_token(db, token)
    if not session:
        raise HTTPException(status_code=401, detail="توکن معتبر نیست یا منقضی شده است")
    user = db.query(User).filter(User.id == session.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="کاربر یافت نشد")
    # FIX(A1): همان سیاست نقش (fail-closed)
    sub_role = resolve_effective_sub_role(user)
    if sub_role not in ["admin", "secretary"]:
        raise HTTPException(status_code=403, detail="شما دسترسی لازم برای این عملیات را ندارید")
    return sub_role

def check_admin_secretary_or_teacher_access(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    """ادمین/منشی/معلم — برای کارهایی که معلم هم باید بتواند در **حوزهٔ خودش** انجام دهد.

    تفاوت با `check_admin_or_secretary_access`: معلم هم عبور می‌کند، ولی خودِ اندپوینت باید
    مالکیت/شعبه را برای معلم محدود کند (مثلاً فقط کلاس‌های خودش). گیت‌های معلم (تعلیق کل
    همکاران با `teachers_active`) عیناً مثل `check_user_login` اعمال می‌شود.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="توکن احراز هویت یافت نشد. لطفاً مجدداً وارد شوید")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="قالب توکن احراز هویت معتبر نیست")
    token = parts[1]
    session, _ = get_session_from_token(db, token)
    if not session:
        raise HTTPException(status_code=401, detail="توکن معتبر نیست یا منقضی شده است")
    user = db.query(User).filter(User.id == session.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="کاربر یافت نشد")
    # FIX(A1): همان سیاست نقش (fail-closed)
    sub_role = resolve_effective_sub_role(user)
    if sub_role not in ("admin", "secretary", "teacher"):
        raise HTTPException(status_code=403, detail="شما دسترسی لازم برای این عملیات را ندارید")
    if sub_role == "teacher":
        settings = db.query(InstituteSettings).first()
        if settings and not settings.teachers_active:
            raise HTTPException(status_code=403, detail="فعالیت همکاران محترم موقتاً توسط مدیریت آموزشگاه متوقف شده است. لطفاً بعداً تلاش فرمایید.")
    return sub_role


def resolve_session_teacher(db: Session, authorization: Optional[str]) -> Optional[Teacher]:
    """پروندهٔ معلمِ همین سشن (O-22) — `None` یعنی این کاربر معلمِ دارای پرونده نیست.

    ترتیب: `UserSession.teacher_id` (استاندارد جدید) وگرنه تطبیق موبایل سایهٔ کاربر.
    """
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    session, _ = get_session_from_token(db, parts[1])
    if not session:
        return None
    if getattr(session, "teacher_id", None):
        teacher = db.query(Teacher).filter(Teacher.id == session.teacher_id,
                                           Teacher.is_deleted == False).first()
        if teacher is not None:
            return teacher
    user = db.query(User).filter(User.id == session.user_id).first()
    if not user or user.role != "teacher":
        return None
    return db.query(Teacher).filter(Teacher.mobile == user.username,
                                    Teacher.is_deleted == False).first()


def check_user_login(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    # FIX: use signed token verification
    if not authorization:
        raise HTTPException(status_code=401, detail="توکن احراز هویت یافت نشد. لطفاً مجدداً وارد شوید")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="قالب توکن احراز هویت معتبر نیست")
    token = parts[1]
    session, _ = get_session_from_token(db, token)
    if not session:
        raise HTTPException(status_code=401, detail="توکن معتبر نیست یا منقضی شده است")
    user = db.query(User).filter(User.id == session.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="کاربر یافت نشد")
    # FIX(A1): همان سیاست نقش — معلمِ legacy بدون sub_role هم به گیت تعلیق معلمان می‌رسد
    sub_role = resolve_effective_sub_role(user)
    if sub_role == "teacher":
        settings = db.query(InstituteSettings).first()
        if settings and not settings.teachers_active:
            raise HTTPException(status_code=403, detail="فعالیت همکاران محترم موقتاً توسط مدیریت آموزشگاه متوقف شده است. لطفاً بعداً تلاش فرمایید.")
    return sub_role

def get_current_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)) -> User:
    # FIX: use signed token verification
    if not authorization:
        raise HTTPException(status_code=401, detail="توکن احراز هویت یافت نشد. لطفاً مجدداً وارد شوید")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="قالب توکن احراز هویت معتبر نیست")
    token = parts[1]
    session, _ = get_session_from_token(db, token)
    if not session:
        raise HTTPException(status_code=401, detail="توکن معتبر نیست یا منقضی شده است")
    user = db.query(User).filter(User.id == session.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="کاربر یافت نشد")
    if user.sub_role == "teacher":
        settings = db.query(InstituteSettings).first()
        if settings and not settings.teachers_active:
            raise HTTPException(status_code=403, detail="فعالیت همکاران محترم موقتاً توسط مدیریت آموزشگاه متوقف شده است. لطفاً بعداً تلاش فرمایید.")
    return user

def get_enrollment_tuition_and_discount(enroll):
    # FIX(null-data): total_tuition legacy ممکن است NULL باشد — مثل 0 حساب می‌شود
    # (صرفاً در محاسبه/نمایش؛ مقدار ذخیره‌شده در دیتابیس دست نمی‌خورد).
    base_tuition = enroll.total_tuition or 0
    discount_amount = 0
    d_type = getattr(enroll, "discount_type", "none") or "none"
    d_val = getattr(enroll, "discount_value", 0) or 0
    if d_type == "percentage":
        discount_amount = (base_tuition * d_val) // 100
    elif d_type == "fixed":
        discount_amount = d_val
    final_tuition = max(0, base_tuition - discount_amount)
    return final_tuition, discount_amount


def get_active_branch(db: Session, branch_id: Optional[int]):
    """شعبه‌ی فعال با شناسه‌ی داده‌شده؛ اگر وجود نداشته باشد یا غیرفعال باشد None."""
    if branch_id is None:
        return None
    branch = db.query(models.Branch).filter(models.Branch.id == branch_id).first()
    if branch and branch.active:
        return branch
    return None


def resolve_creation_branch(
    db: Session,
    *,
    user: Optional[User] = None,
    teacher: Optional[Teacher] = None,
    requested_branch_id: Optional[int] = None,
    fallback_branch_id: Optional[int] = None,
) -> int:
    """سیاست مرکزی و شفاف تعیین branch_id برای مسیرهای نوشتن (ثبت شاگرد، ساخت کلاس، ...).

    ترتیب تصمیم‌گیری (به‌دنبال هم):
      1) branch صریح ارسالی — فقط اگر فراخوان مجاز به استفاده از آن باشد:
         - کارمند (ادمین/منشی) که خود branch دارد: فقط branch خودش (وگرنه 403 — branch isolation).
         - کارمند بدون branch (مدیر کل): هر branch فعالی (وگرنه 400).
         - معلم: فقط branch خودش (ارزش ارسالی معلم هرگز به‌صورت کورکورانه قبول نمی‌شود).
         - فراخوان عمومی (بدون هویت، مثلاً /students/register): فقط branch فعال (وگرنه 400).
      2) branch خودِ فراخوان (user.branch_id یا teacher.branch_id) — فقط اگر فعال باشد.
         اگر branch خودِ کاربر غیرفعال/حذف شده باشد، به branch دیگر «لغزیده» نمی‌شود (400).
      3) branch مشتق‌شده از شیء تجاری مربوطه (fallback_branch_id — مثلاً branch همان کلاسی
         که دانش‌آموز در آن ثبت‌نام می‌کند) — فقط اگر فعال باشد. این تخمین کورکورانه نیست،
         چون دقیقاً شعبه‌ی جایی است که ثبت‌نام/معامله در آن اتفاق می‌افتد (منطق H7).
      4) اگر در کل سیستم دقیقاً یک branch فعال وجود دارد — فقط در همین حالت از آن استفاده می‌شود.
      5) چند branch فعال بدون منبع قابل‌اعتماد → 400 با پیام واضح (تخمین کورکورانه ممنوع).

    همیشه int برمی‌گرداند (هرگز None) و هرگز داده نمی‌سازد/تغییر نمی‌دهد — فقط تصمیم می‌گیرد.
    """
    # 1) branch صریح
    if requested_branch_id is not None:
        branch = get_active_branch(db, requested_branch_id)
        if branch is None:
            raise HTTPException(status_code=400, detail="شعبه‌ی ارسالی نامعتبر است (وجود ندارد یا غیرفعال است).")
        if teacher is not None:
            if teacher.branch_id != branch.id:
                raise HTTPException(status_code=403, detail="شما فقط می‌توانید در شعبه‌ی خودتان داده ثبت کنید.")
        elif user is not None and user.branch_id is not None:
            if user.branch_id != branch.id:
                raise HTTPException(status_code=403, detail="شما مجاز به ایجاد داده در شعبه‌ی دیگر نیستید.")
        return branch.id

    # 2) branch خودِ فراخوان
    own_branch_id = teacher.branch_id if teacher is not None else (user.branch_id if user is not None else None)
    if own_branch_id is not None:
        branch = get_active_branch(db, own_branch_id)
        if branch is not None:
            return branch.id
        raise HTTPException(status_code=400, detail="شعبه‌ی شما غیرفعال یا حذف شده است؛ برای ادامه با مدیریت تماس بگیرید.")

    # 3) branch مشتق‌شده از شیء تجاری (مثلاً کلاسِ انتخاب‌شده در register_and_enroll)
    if fallback_branch_id is not None:
        branch = get_active_branch(db, fallback_branch_id)
        if branch is not None:
            return branch.id

    # 4) تک‌شعبه‌ی فعال در کل سیستم
    active_branches = db.query(models.Branch).filter(models.Branch.active == True).all()
    if len(active_branches) == 1:
        return active_branches[0].id

    # 5) مبهم — تخمین ممنوع
    raise HTTPException(
        status_code=400,
        detail="شعبه مشخص نیست: سیستم چند شعبه‌ی فعال دارد و شعبه‌ی قابل‌اعتمادی برای این داده پیدا نشد. لطفاً branch_id معتبر ارسال کنید یا شعبه‌ی کاربر/معلم را تنظیم کنید.",
    )


def perform_delete_enrollment(enrollment, db: Session, forgive_session_charges: bool = True):
    """Archive one enrollment and return the exact changes made by this call.

    The effect payload is used by class deletion to create deletion-scoped restore
    provenance. Existing callers may ignore the return value.
    """
    # FIX: Bug 13 - archive once; never detach or delete historical enrollment links.
    # پول واقعی دریافت‌شده از بین نمی‌رود؛ فقط session_chargeهای مشمول بخشودگی به کیف پول برمی‌گردند.
    from sqlalchemy import and_, or_, func

    effects = {
        "enrollment_id": enrollment.id,
        "enrollment_archived": False,
        "transaction_rows": [],
        "installment_rows": [],
        "wallet_credits": {},
    }
    # FIX B3 (الگوی H8-P4): تسخیر اتمیک ثبت‌نام — اولین کار تابع؛ فقط enrollment.id لازم است.
    claimed_rows = (
        db.query(Enrollment)
        .filter(Enrollment.id == enrollment.id, Enrollment.is_deleted == False)
        .update({Enrollment.is_deleted: True}, synchronize_session=False)
    )
    if claimed_rows != 1:
        return effects
    effects["enrollment_archived"] = True

    # FIX B3: کشف کاندیداها بدون قفل — گیت واقعی، claim سطری داخل حلقه است.
    transactions = db.query(Transaction).filter(
        or_(
            Transaction.enrollment_id == enrollment.id,
            and_(
                Transaction.enrollment_id == None,
                Transaction.student_id == enrollment.student_id,
                Transaction.course_id == enrollment.course_id,
            ),
        ),
        Transaction.is_deleted == False,
        Transaction.is_reversed == False,
    ).all()
    credited_student_ids = set()
    for t in transactions:
        if t.type in ["tuition", "enrollment_payment", "deposit", "reversal"]:
            # وجه واقعی: کیف پول دست نمی‌خورد و سابقه با همان لینک تاریخی فعال می‌ماند.
            continue
        if t.type == "session_charge" and not forgive_session_charges:
            continue
        # FIX B3: تسخیر اتمیک هر تراکنش — فقط اگر هنوز فعال باشد آرشیو می‌شود.
        t_claimed = (
            db.query(Transaction)
            .filter(Transaction.id == t.id, Transaction.is_deleted == False, Transaction.is_reversed == False)
            .update({Transaction.is_deleted: True}, synchronize_session=False)
        )
        if t_claimed != 1:
            continue

        transaction_effect = {
            "id": t.id,
            "student_id": t.student_id,
            "course_id": t.course_id,
            "enrollment_id": t.enrollment_id,
            "session_id": t.session_id,
            "type": t.type,
            "amount": t.amount,
            "share_teacher": t.share_teacher or 0,
            "share_institute": t.share_institute or 0,
            "is_reversed": bool(t.is_reversed),
            "wallet_credited": False,
        }
        effects["transaction_rows"].append(transaction_effect)
        if t.type == "session_charge":
            share_t = t.share_teacher or 0
            share_i = t.share_institute or 0
            if share_t or share_i:
                wallet_rows = (
                    db.query(Student)
                    .filter(Student.id == t.student_id)
                    .update(
                        {
                            Student.wallet_teacher: func.coalesce(Student.wallet_teacher, 0) + share_t,
                            Student.wallet_institute: func.coalesce(Student.wallet_institute, 0) + share_i,
                        },
                        synchronize_session=False,
                    )
                )
                if wallet_rows == 1:
                    transaction_effect["wallet_credited"] = True
                    credited_student_ids.add(t.student_id)
                    credit = effects["wallet_credits"].setdefault(
                        t.student_id, {"teacher": 0, "institute": 0}
                    )
                    credit["teacher"] += int(share_t)
                    credit["institute"] += int(share_i)
        # تایپ‌های ناشناخته نیز مانند رفتار قبلی آرشیو می‌شوند، بدون اعتباردهی.

    # ترتیب سینک: پس از UPDATEهای خام، هر کیف‌پول متأثر یک بار refresh و sync می‌شود.
    for sid in credited_student_ids:
        st = db.query(Student).filter(Student.id == sid).first()
        if st is not None:
            db.refresh(st)
            st.sync_wallet_balance()

    # ثبت دقیق اقساطی که این عملیات از فعال به آرشیو تغییر می‌دهد.
    installments = db.query(Installment).filter(
        Installment.enrollment_id == enrollment.id,
        Installment.is_deleted == False,
    ).all()
    effects["installment_rows"] = [
        {
            "id": item.id,
            "enrollment_id": item.enrollment_id,
            "amount": item.amount,
            "due_date": item.due_date,
            "is_paid": bool(item.is_paid),
            "paid_at": item.paid_at,
            "paid_amount": item.paid_amount,
        }
        for item in installments
    ]
    db.query(Installment).filter(
        Installment.enrollment_id == enrollment.id,
        Installment.is_deleted == False,
    ).update({Installment.is_deleted: True}, synchronize_session="fetch")
    enrollment.is_deleted = True
    return effects

def reverse_session_financial_impacts(session_id: int, db: Session, commit: bool = True):  # FIX (audit-v2/critical-8-قدم۲): الگوی H4 (send_notification) — کالر اتمیک commit=False می‌دهد
    # FIX B2 (الگوی H8-P4): بدون with_for_update — این SELECT فقط کشف کاندیداست؛ گیت واقعی، UPDATE مشروط داخل حلقه است.
    from sqlalchemy import func  # lazy، مثل and_/or_ همین فایل
    transactions = db.query(Transaction).filter(
        Transaction.session_id == session_id, Transaction.type == "session_charge",
        Transaction.is_deleted == False, Transaction.is_reversed == False,
    ).all()
    credited_student_ids = set()
    for t in transactions:
        # FIX B2: تسخیر اتمیک هر تراکنش — فقط اگر هنوز فعال باشد آرشیو می‌شود.
        # rowcount صفر یعنی کال موازی/تکراری همین‌الان آن را برگرداند → بدون اعتباردهی رد شو (idempotent).
        claimed_rows = (
            db.query(Transaction)
            .filter(Transaction.id == t.id, Transaction.is_deleted == False, Transaction.is_reversed == False)
            .update({Transaction.is_deleted: True}, synchronize_session=False)
        )
        if claimed_rows != 1:
            continue
        # FIX B2: اعتبار اتمیک کیف‌پول — جمع در SQL (COALESCE رفتار None→0 قبلی را حفظ می‌کند).
        share_t = t.share_teacher or 0
        share_i = t.share_institute or 0
        if share_t or share_i:
            wallet_rows = (
                db.query(Student)
                .filter(Student.id == t.student_id)
                .update(
                    {
                        Student.wallet_teacher: func.coalesce(Student.wallet_teacher, 0) + share_t,
                        Student.wallet_institute: func.coalesce(Student.wallet_institute, 0) + share_i,
                    },
                    synchronize_session=False,
                )
            )
            if wallet_rows == 1:
                credited_student_ids.add(t.student_id)
            # rowcount صفر = دانش‌آموز هم‌زمان حذف سخت شده؛ مثل رفتار قبلی (if student) رد شو.
    # ترتیب سینک: بعد از همه‌ی UPDATEهای خام، به‌ازای هر شاگرد متأثر فقط یک refresh بعد sync.
    for sid in credited_student_ids:
        st = db.query(Student).filter(Student.id == sid).first()
        if st is not None:
            db.refresh(st)
            # FIX: Bug 18 - derive the total only through the shared wallet helper.
            st.sync_wallet_balance()
    # FIX (F-S2): برگشت مالی جلسه، ردیف‌های حضور را **آرشیو** می‌کند نه پاک فیزیکی — الگوی نرم
    # بقیه‌ی حذف‌های پروژه (SessionLog/Transaction/Enrollment/Installment). سابقه‌ی حضور برای audit
    # می‌ماند؛ چون قید یکتای (session_id, student_id) برجاست، مسیر ویرایش باید upsert کند
    # (revive همان ردیف) نه INSERT تازه.
    # idempotent: UPDATE روی همه‌ی ردیف‌های جلسه، پس اجرای دوباره بی‌اثر است.
    db.query(Attendance).filter(Attendance.session_id == session_id).update(
        {Attendance.is_deleted: True}, synchronize_session="fetch"
    )
    if commit:
        db.commit()


def validate_session_items_membership(db: Session, course_id: int, items) -> None:
    """FIX: H6(B) - همه‌ی student_idهای آیتم‌های حضور/غیاب باید عضو فعال همین کلاس باشند.

    یک کوئری برای همه؛ در صورت تخلف 422 با لیست دقیق idهای خاطی.
    حتماً قبل از هر db.add/commit صدا زده شود.
    """
    wanted = {i.student_id for i in items if getattr(i, "student_id", None) is not None}
    if not wanted:
        return
    enrolled = {
        r[0]
        for r in db.query(Enrollment.student_id)
        .filter(
            Enrollment.course_id == course_id,
            Enrollment.is_deleted == False,
            Enrollment.student_id.in_(list(wanted)),
        )
        .all()
    }
    offenders = sorted(wanted - enrolled)
    if offenders:
        raise HTTPException(
            status_code=422,
            detail=f"این دانش‌آموزان عضو فعال کلاس {course_id} نیستند: {offenders}",
        )
    # FIX H10: دانش‌آموز معلق حتی اگر عضو فعال باشد، در جلسه ثبت نمی‌شود (هم‌فرمت 422 موجود).
    suspended = sorted(
        r[0]
        for r in db.query(Student.id)
        .filter(
            Student.id.in_(list(wanted)),
            Student.is_suspended == True,
        )
        .all()
    )
    if suspended:
        raise HTTPException(
            status_code=422,
            detail=f"این دانش‌آموزان معلق هستند و نمی‌توانند در جلسه ثبت شوند: {suspended}",
        )
    # FIX (F-S1): دانش‌آموز آرشیوشده (soft-deleted) هم مثل معلق باید **قبل از** هر نوشتنی رد شود.
    # پیش‌تر نه عضویتش چک می‌شد و نه معلق بودنش؛ نتیجه این بود که در شمارش حاضرین و سهم‌های
    # SessionLog «حاضر» حساب می‌شد ولی حلقه‌ی شارژ او را رد می‌کرد ⇒ جلسه با سهم معلمِ بدون وصول.
    archived = sorted(
        r[0]
        for r in db.query(Student.id)
        .filter(
            Student.id.in_(list(wanted)),
            Student.is_deleted == True,
        )
        .all()
    )
    if archived:
        raise HTTPException(
            status_code=422,
            detail=f"این دانش‌آموزان حذف/آرشیو شده‌اند و نمی‌توانند در جلسه ثبت شوند: {archived}",
        )


def validate_session_item_statuses(items) -> None:
    """FIX (F-S4): وضعیت هر ردیف حضور/غیاب باید یکی از مقادیر رسمی قرارداد باشد.

    یک اعتبارسنج مرکزی برای همه‌ی مسیرهای ثبت/ویرایش جلسه (schema هم همان قاعده را در مرز HTTP
    با ۴۲۲ اجرا می‌کند). حتماً قبل از ساخت SessionLog/Attendance/Transaction صدا زده می‌شود.
    """
    from validation import ATTENDANCE_STATUSES, validate_attendance_status  # lazy، مثل بقیه‌ی این فایل

    invalid = []
    for item in items:
        status = getattr(item, "status", None)
        try:
            validate_attendance_status(status)
        except ValueError:
            invalid.append(repr(status))
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=(
                f"وضعیت حضور نامعتبر است: {', '.join(sorted(set(invalid)))}؛ "
                f"مقادیر مجاز: {' / '.join(ATTENDANCE_STATUSES)}"
            ),
        )


def check_student_access(student_id: int, authorization: Optional[str], db: Session, sub_role: str):
    # FIX: use signed token helper for JWT compatibility
    if sub_role == "teacher":
        from routers.reports import get_logged_in_teacher
        logged_teacher = get_logged_in_teacher(db, authorization)
        if not logged_teacher:
            raise HTTPException(status_code=403, detail="مربی لاگین شده یافت نشد")
        related = (
            db.query(Enrollment)
            .join(Course)
            .filter(Enrollment.student_id == student_id, Course.teacher_id == logged_teacher.id)
            .first()
        )
        if not related:
            raise HTTPException(status_code=403, detail="شما مجاز به دسترسی به این دانش‌آموز نیستید")
    elif sub_role == "parent":
        if not authorization:
            raise HTTPException(status_code=401, detail="توکن یافت نشد")
        parts = authorization.split()
        token = parts[1] if len(parts) == 2 else ""
        session, _ = get_session_from_token(db, token)
        own = get_session_parent(db, session) if session else None
        if not own or own.id != student_id:
            raise HTTPException(status_code=403, detail="شما مجاز به دسترسی به این فرزند نیستید")
    elif sub_role == "student":
        if not authorization:
            raise HTTPException(status_code=401, detail="توکن یافت نشد")
        parts = authorization.split()
        token = parts[1] if len(parts) == 2 else ""
        session, _ = get_session_from_token(db, token)
        own = get_session_student(db, session) if session else None
        if not own or own.id != student_id:
            raise HTTPException(status_code=403, detail="شما مجاز به دسترسی به دانش‌آموز دیگری نیستید")
    else:
        # FIX (L14/Y1-helper): نقش‌های ناشناخته (مثل temp_parent:موبایلِ قبل از انتخاب فرزند)
        # قبلاً از همه‌ی شاخه‌ها رد می‌شدند = bypass کامل. فقط ادمین/منشی عبور می‌کنند.
        if sub_role not in ("admin", "secretary"):
            raise HTTPException(status_code=403, detail="نقش کاربری برای این دسترسی معتبر نیست")

from slowapi import Limiter
from slowapi.util import get_remote_address

# FIX H14: IP واقعی پشت Cloudflare Tunnel — get_remote_address خام همیشه 127.0.0.1 می‌دید (تک‌سطلی).
# به هدر پروکسی فقط وقتی اعتماد می‌شود که client.host ثابت کند از تانل/پروکسی لوکال رد شده (ضد-spoof).
_TRUSTED_PROXY_IPS = {ip.strip() for ip in os.getenv("TRUSTED_PROXY_IPS", "127.0.0.1,::1").split(",") if ip.strip()}


def tunnel_aware_key(request):
    direct = get_remote_address(request)  # حقیقت TCP، غیرقابل‌جعل
    if direct in _TRUSTED_PROXY_IPS:
        cf_ip = (request.headers.get("cf-connecting-ip") or "").strip()
        if cf_ip:
            return cf_ip  # Cloudflare edge بازنویسی می‌کند = کلاینت واقعی
        xff = request.headers.get("x-forwarded-for") or ""
        if xff:
            last_hop = xff.split(",")[-1].strip()  # جزء افزوده‌ی edge = کلاینت واقعی
            if last_hop:
                return last_hop
    return direct


limiter = Limiter(key_func=tunnel_aware_key)


def ensure_student_shadow_users(db: Session, student) -> None:
    """FIX(H2): ساخت User سایه (نقش student و parent) برای شاگرد — عین الگوی معلم.

    تفاوت‌ها با معلم (آگاهانه): username نام‌فضادار است چون موبایل ولی بین
    خواهر/برادر مشترک است و موبایل شاگرد ممکن است با معلم تداخل کند؛ پسورد
    تصادفی است چون ورود OTP-محور است و هرگز تایپ نمی‌شود.
    اگر سایه‌ای از قبل باشد دست نمی‌خورد (idempotent — امن برای backfill و لاگین).
    """
    import secrets
    from sqlalchemy.exc import IntegrityError  # FIX F-B2 local
    if student.id is None:
        db.flush()
    full_name = f"{student.first_name or ''} {student.last_name or ''}".strip()
    if not getattr(student, "user_id", None):
        # FIX F-B2: race همزمان ساخت سایه student → UNIQUE → self-heal
        try:
            with db.begin_nested():
                u = User(
                    username=f"student:{student.id}",
                    password=hash_password(secrets.token_urlsafe(12)),
                    full_name=full_name or f"دانش‌آموز {student.id}",
                    role="student",
                    sub_role="student",
                    branch_id=student.branch_id,
                )
                db.add(u)
                db.flush()
                student.user_id = u.id
        except IntegrityError:
            existing = db.query(User).filter(User.username == f"student:{student.id}").first()
            if existing is not None:
                student.user_id = existing.id
            else:
                raise
    if not getattr(student, "parent_user_id", None):
        # FIX F-B2: race همزمان ساخت سایه parent → UNIQUE → self-heal
        try:
            with db.begin_nested():
                p = User(
                    username=f"parent:{student.id}",
                    password=hash_password(secrets.token_urlsafe(12)),
                    full_name=f"ولی {full_name}".strip() or f"ولی دانش‌آموز {student.id}",
                    role="parent",
                    sub_role="parent",
                    branch_id=student.branch_id,
                )
                db.add(p)
                db.flush()
                student.parent_user_id = p.id
        except IntegrityError:
            existing = db.query(User).filter(User.username == f"parent:{student.id}").first()
            if existing is not None:
                student.parent_user_id = existing.id
            else:
                raise


def get_session_student(db: Session, session) -> Optional[Student]:
    """FIX(H2): Student متناظر سشن نقش student — از طریق FK موجود Student.user_id.

    None یعنی سشن خراب/قدیمی یا شاگرد آرشیوی؛ caller خودش 401/403/404 می‌دهد.
    """
    if session is None or not getattr(session, "user_id", None):
        return None
    shadow = db.query(User).filter(User.id == session.user_id).first()
    if not shadow:
        return None
    return db.query(Student).filter(Student.user_id == shadow.id, Student.is_deleted == False).first()


def get_session_parent(db: Session, session) -> Optional[Student]:
    """FIX(H2): فرزند متناظر سشن نقش parent — از طریق FK موجود Student.parent_user_id.

    None یعنی سشن خراب/قدیمی یا شاگرد آرشیوی؛ caller خودش 401/403/404 می‌دهد.
    """
    if session is None or not getattr(session, "user_id", None):
        return None
    shadow = db.query(User).filter(User.id == session.user_id).first()
    if not shadow:
        return None
    return db.query(Student).filter(Student.parent_user_id == shadow.id, Student.is_deleted == False).first()


def resolve_participant_keys(db: Session, session, role: str) -> Optional[List[int]]:
    """کلیدهای کاندید ConversationParticipant/Message برای سشن فعلی (dual-lookup موقت).

    ترتیب مهم است: عنصر اول استاندارد جدید است (تنها مقداری که برای رکورد جدید ثبت می‌شود)،
    بقیه فقط فالبک خواندن برای سطرهای قدیمی. اگر هویت قابل رزولو نباشد None و caller باید 401 بدهد.
    """
    if not session:
        return None
    if role == "student":
        own = get_session_student(db, session)
        if not own:
            return None
        keys = [own.id]
        if session.user_id != own.id:
            keys.append(session.user_id)
        return keys
    if role == "parent":
        own = get_session_parent(db, session)
        if not own:
            return None
        keys = [own.id]
        if session.user_id != own.id:
            keys.append(session.user_id)
        return keys
    if role == "teacher":
        if session.teacher_id:
            keys = [session.teacher_id]
            if session.user_id != session.teacher_id:
                keys.append(session.user_id)
            return keys
        return [session.user_id]
    return [session.user_id]


def resolve_notification_recipient(db: Session, subject_id: int, role: str) -> Optional[int]:
    """مپ مرکزی subject به recipient_user_id نوتیفیکیشن (بچ D — آخرین بچ H2).

    خواننده‌ها (get_notifications و...) با current_user.id می‌خوانند، پس خروجی همیشه فضای User.id است.
    اگر قابل رزولو نباشد None و caller باید آن مخاطب را skip کند (نه ثبت با None).
    """
    if role == "student":
        st = db.query(Student).filter(Student.id == subject_id).first()
        if st is None:
            return None
        if st.user_id is None:
            ensure_student_shadow_users(db, st)
        return st.user_id
    if role == "parent":
        st = db.query(Student).filter(Student.id == subject_id).first()
        if st is None:
            return None
        if st.parent_user_id is None:
            ensure_student_shadow_users(db, st)
        return st.parent_user_id
    if role == "teacher":
        # استاندارد جدید اول (همه‌ی نوشته‌های جدید Teacher.id هستند)؛ اگر معلم لاگین نکرده skip
        t = db.query(Teacher).filter(Teacher.id == subject_id).first()
        if t is not None:
            u = db.query(User).filter(User.username == t.mobile).first()
            return u.id if u else None
        # فالبک سطرهای قدیمی که با User.id ثبت شده‌اند (فقط اگر واقعاً اکانت معلم باشد)
        legacy = db.query(User).filter(User.id == subject_id).first()
        if legacy is not None and legacy.sub_role == "teacher":
            return legacy.id
        return None
    return subject_id


# FIX(admin-notifications): نقش کانونیکالِ notification — تنها مرجعِ مشترک بین «نوشتن»
# (recipient_role هنگام ساخت) و «خواندن» (فیلتر get_notifications/mark-read/read_all).
# قبلاً خواندن از `sub_role or "student"` استفاده می‌کرد ولی بقیه‌ی پروژه (login،
# check_admin_access، check_user_login) `sub_role or "admin"` داشت ⇒ برای ادمینِ legacy
# (رکوردی که sub_role آن NULL است و role="admin") اعلان‌های نقش admin ساخته می‌شد
# ولی هرگز نمایش داده نمی‌شد. حالا fallback به role و در نهایت "student" است تا هم
# ادمینِ قدیمی اعلانش را ببیند و هم رفتار فعلی شاگرد/ولی تغییر نکند.
STAFF_NOTIFICATION_ROLES = ("admin", "secretary")


def resolve_notification_role(user) -> str:
    """نقش کانونیکال کاربر برای notification (همان رشته‌ای که در recipient_role ذخیره می‌شود)."""
    if user is None:
        return "student"
    role = (user.sub_role or "").strip() or (getattr(user, "role", None) or "").strip() or "student"
    if role.startswith("temp_parent:"):
        return "parent"
    return role


ROLE_PERMISSIONS = {
    "admin": ["*"],
    "secretary": [
        "student.read", "student.create", "student.update",
        "teacher.read", "teacher.create",
        "class.read", "class.create", "class.update",
        "attendance.read", "attendance.write", "attendance.edit",
        "grade.read", "grade.write",
        "finance.read", "finance.create",
        "reports.read",
        "messages.read", "messages.send",
        "messages.broadcast",  # FIX (L14/Y2-F1): ارسال همگانی فقط کارکنان+معلم
        "settings.read"
    ],
    "teacher": [
        "student.read",
        "teacher.read", "teacher.update",
        "class.read",
        "attendance.read", "attendance.write", "attendance.edit",
        "grade.read", "grade.write", "grade.edit",
        "finance.read",
        "homework.create", "homework.delete", "homework.grade",
        "messages.read", "messages.send",
        "messages.broadcast"  # FIX (L14/Y2-F1): معلم برای اطلاعیه‌ی کلاس خودش
    ],
    "student": [
        "student.read",
        "class.read",
        "grade.read",
        "finance.read",
        "homework.read", "homework.update",
        "messages.read", "messages.send"
    ],
    "parent": [
        "student.read",
        "class.read",
        "grade.read",
        "finance.read",
        "homework.read",
        "messages.read", "messages.send"
    ]
}

def require_permission(permission: str):
    def dependency(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
        # FIX: use signed token verification
        if not authorization:
            raise HTTPException(status_code=401, detail="توکن یافت نشد")
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(status_code=401, detail="قالب توکن معتبر نیست")
        token = parts[1]
        session, _ = get_session_from_token(db, token)
        if not session:
            raise HTTPException(status_code=401, detail="نشست نامعتبر یا منقضی شده است")
        role = session.sub_role or "student"
        if role.startswith("temp_parent:"):
            raise HTTPException(status_code=401, detail="ابتدا فرزند را انتخاب کنید")
        permissions = ROLE_PERMISSIONS.get(role, [])
        if "*" in permissions or permission in permissions:
            return role
        raise HTTPException(status_code=403, detail="شما دسترسی لازم برای این عملیات را ندارید")
    return dependency

from passlib.handlers.pbkdf2 import pbkdf2_sha256

# FIX M28: کانتکست bcrypt یک‌بار در سطح ماژول (نه هر بار داخل verify) — فقط برای هش‌های legacy.
# ساخت داخل try است تا رفتار قبلی حفظ شود: اگر bcrypt در دسترس نباشد، import نمی‌شکند و verify همان False را می‌دهد.
from passlib.context import CryptContext as _CryptContext

try:
    _BCRYPT_CTX = _CryptContext(schemes=["bcrypt"])
except Exception:
    _BCRYPT_CTX = None

# FIX H20: نگاشت ارقام فارسی/عربی به انگلیسی (self-contained تا چرخه‌ی import با today_summary نسازد).
_MOBILE_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalize_mobile(raw) -> Optional[str]:
    """FIX H20: canonical موبایل ایرانی ← «09xxxxxxxxx»؛ None اگر غیرقابل‌نرمال.

    هرگز رشته‌ی نامعتبر برنمی‌گرداند — کالر روی None باید 400 بدهد.
    """
    if raw is None:
        return None
    s = str(raw).translate(_MOBILE_DIGITS).strip()
    for ch in (" ", "-", "(", ")"):
        s = s.replace(ch, "")
    if s.startswith("+"):
        s = s[1:]
    if s.startswith("0098"):
        s = s[4:]
    elif s.startswith("98") and len(s) == 12:
        s = s[2:]
    if len(s) == 10 and s.startswith("9"):
        s = "0" + s
    if len(s) == 11 and s.startswith("09") and s.isdigit():
        return s
    return None


def validate_image_upload(filename, contents) -> str:
    """FIX M25: پسوند + magic bytes برای آپلود عکس. ext را برمی‌گرداند یا 400 می‌دهد."""
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        raise HTTPException(status_code=400, detail="فرمت فایل غیرمجاز است. فقط فرمت‌های JPG, PNG, WEBP مجاز هستند")
    sig = bytes(contents[:12])
    ok = (
        (ext in (".jpg", ".jpeg") and sig[:3] == b"\xff\xd8\xff")
        or (ext == ".png" and sig[:8] == b"\x89PNG\r\n\x1a\n")
        or (ext == ".webp" and sig[:4] == b"RIFF" and sig[8:12] == b"WEBP")
    )
    if not ok:
        raise HTTPException(status_code=400, detail="محتوای فایل با فرمت تصویری اعلام‌شده مطابقت ندارد")
    return ext


def hash_password(password: str) -> str:
    return pbkdf2_sha256.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # FIX: remove plaintext fallback, only accept real hashes, invalid -> False
    if not hashed_password:
        return False
    if hashed_password.startswith("$pbkdf2-sha256$"):
        try:
            return pbkdf2_sha256.verify(plain_password, hashed_password)
        except Exception:
            return False
    if hashed_password.startswith("$2b$") or hashed_password.startswith("$2a$") or hashed_password.startswith("$2y$"):
        # FIX M28: استفاده از کانتکست ماژول؛ None یعنی bcrypt در دسترس نیست (همان False قبلی).
        if _BCRYPT_CTX is None:
            return False
        try:
            return _BCRYPT_CTX.verify(plain_password, hashed_password)
        except Exception:
            return False
    # FIX: unknown or plaintext hash -> False
    return False

import json
import time
from models import SmsLog

class NotificationService:
    @staticmethod
    def send_notification(
        db: Session,
        recipient_user_id: int,
        recipient_role: str,
        type: str,
        title: str,
        body: str,
        data: Optional[dict] = None,
        priority: int = 1,
        commit: bool = True,  # False فقط وقتی کالر خودش اتمیسیته را مدیریت می‌کند (مثل حلقه شارژ ثبت جلسه)
    ):
        from sqlalchemy import desc
        now = datetime.datetime.utcnow()
        ten_seconds_ago = now - datetime.timedelta(seconds=10)
        duplicate = (
            db.query(Notification)
            .filter(
                Notification.recipient_user_id == recipient_user_id,
                Notification.recipient_role == recipient_role,
                Notification.title == title,
                Notification.body == body,
                Notification.created_at > ten_seconds_ago
            )
            .first()
        )
        if duplicate:
            return duplicate
        new_notification = Notification(
            recipient_user_id=recipient_user_id,
            recipient_role=recipient_role,
            type=type,
            title=title,
            body=body,
            data=json.dumps(data) if data else None,
            is_read=False,
            created_at=now,
            priority=priority
        )
        db.add(new_notification)
        db.flush()
        device_tokens = db.query(DeviceToken).filter(DeviceToken.user_id == recipient_user_id, DeviceToken.role == recipient_role).all()
        if device_tokens:
            # FIX(C2): این حلقه قبلاً **خالی** بود ⇒ هیچ اعلان سیستمی (Push) ارسال نمی‌شد و کاربری که
            # اپ را باز نمی‌کرد، از پرداخت/قسط/غیبت/پیام بی‌خبر می‌ماند. حالا ارسال واقعی انجام می‌شود:
            #  • گارد محیطی: تا وقتی FCM_SERVER_KEY تنظیم نشده، هیچ درخواست شبکه‌ای زده نمی‌شود (فقط لاگ شفاف).
            #  • بدون ریسک: deliver_push هرگز exception بیرون نمی‌دهد (شکست push نباید ثبت اعلان/تراکنش را بشکند).
            #  • commit=False ⇒ پاک‌سازی توکن‌های نامعتبر به همان commit پایانی همین تابع واگذار می‌شود
            #    تا تراکنش مالی کالر (مثلاً ثبت جلسه) اتمیک بماند.
            try:
                from push_service import deliver_push  # lazy: جلوگیری از import چرخه‌ای
                deliver_push(
                    db, device_tokens, title=title, body=body,
                    data={"type": type, "notification_id": getattr(new_notification, "id", None)},
                    commit=False,
                )
            except Exception:  # belt-and-braces؛ deliver_push خودش استثنا بیرون نمی‌دهد
                pass
        if type in ["attendance", "installment", "payment"]:
            db.add(SmsLog(
                target_group=f"notif_{recipient_role}_{recipient_user_id}",
                message_text=f"🔔 {title}\n{body}",
                sent_count=1,
                date=datetime.datetime.now().strftime("%Y/%m/%d %H:%M")
            ))
        if commit:
            db.commit()
        return new_notification

    # ------------------------------------------------------------------
    # FIX(admin-notifications): گیرندگان اعلانِ کارکنان — همیشه از فضای User.id.
    # ------------------------------------------------------------------
    @staticmethod
    def get_staff_recipients(db: Session, branch_id: Optional[int] = None):
        """لیست (user_id, role) کارکنانِ مجاز برای دریافت اعلان ادمینی.

        - منبعِ شناسه: جدول users (User.id) — هرگز Student.id/Teacher.id.
        - رکورد legacy با sub_role خالی: role جایگزین می‌شود (coalesce/nullif) — همان قرارداد
          resolve_notification_role؛ وگرنه ادمینِ قدیمی هیچ اعلانی نمی‌گرفت.
        - branch_id مشخص: کارکنانِ همان شعبه + کارکنانِ بدون شعبه (ادمین کل) — آینه‌ی policy
          «شعبه‌ی خودم + بدون‌شعبه» که در مسیرهای ادمین استفاده می‌شود ⇒ شعبه‌ی دیگر نمی‌بیند.
        - branch_id نامشخص (None): همه‌ی کارکنان (اعلان بی‌صاحب رها نمی‌شود).
        """
        from sqlalchemy import func, or_
        canonical = func.lower(func.coalesce(
            func.nullif(User.sub_role, ""), func.nullif(User.role, ""), "student"
        ))
        q = db.query(User).filter(canonical.in_(STAFF_NOTIFICATION_ROLES))
        if branch_id is not None:
            q = q.filter(or_(User.branch_id == branch_id, User.branch_id.is_(None)))
        return [(u.id, resolve_notification_role(u)) for u in q.order_by(User.id).all()]

    @staticmethod
    def send_to_staff(db: Session, *, type: str, title: str, body: str,
                      data: Optional[dict] = None, branch_id: Optional[int] = None,
                      priority: int = 1):
        """ارسال اعلان به کارکنانِ مجاز (ادمین/منشی) — شناسه‌ها از فضای User.id.

        جایگزین الگوی غلط `trigger_notification_action(..., 1, "admin", ...)` که اعلان را
        همیشه به کاربرِ شماره ۱ می‌فرستاد (معمولاً ادمین نبود ⇒ اعلان هیچ‌وقت دیده نمی‌شد).
        """
        created = []
        for user_id, role in NotificationService.get_staff_recipients(db, branch_id=branch_id):
            created.append(NotificationService.send_notification(
                db, recipient_user_id=user_id, recipient_role=role,
                type=type, title=title, body=body, data=data,
                priority=priority, commit=False,  # یک commit واحد برای کل fan-out
            ))
        db.commit()
        return created
