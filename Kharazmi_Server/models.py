import datetime
import os
from dotenv import load_dotenv

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
# FIX: Bug 17 - enforce one active financial session per course and date in both databases.
from sqlalchemy import Index
# FIX: H6(C2) - one attendance row per (session, student).
from sqlalchemy import UniqueConstraint
# FIX: Bug 18 - keep the stored wallet total synchronized on ORM writes.
from sqlalchemy import event, inspect

# بارگذاری متغیرهای محیطی از فایل .env
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)

# --- تنظیمات اتصال ---
# FIX H13: پیش‌فرض غیرحساس، هم‌ارز کانفیگ واقعی (.env)؛ Postgres همچنان با DATABASE_URL قابل انتخاب است.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///gaj_db.db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ==========================================
# ۰. شعب آموزشگاه (Branches) - جدید 🆕
# ==========================================
class Branch(Base):
    __tablename__ = "branches"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    address = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    manager = Column(String, nullable=True)
    active = Column(Boolean, default=True)


# ==========================================
# 1. کاربران سیستم
# ==========================================
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True)
    password = Column(String)
    full_name = Column(String)
    role = Column(String)
    # FIX(A1): پیش‌فرض «admin» حذف شد — هر کاربری که نقشش صریحاً تعیین نشود، دیگر
    # به‌طور خودکار مدیر نمی‌شود. نقش مؤثر (fail-closed) در dependencies.resolve_effective_sub_role
    # محاسبه می‌شود: sub_role ست‌شده ⇒ همان؛ در غیر این‌صورت از ستون role و فقط برای
    # role خالی/«admin» ⇒ admin. (همهٔ مسیرهای ساخت کاربر در کد صریح‌اند.)
    sub_role = Column(String)  # "admin" | "secretary" | "teacher" | "student" | "parent"
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)


class UserSession(Base):
    __tablename__ = "user_sessions"
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    # FIX: ذخیره مستقیم teacher_id برای جلوگیری از وابستگی به mobile و رفع race
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=True)
    sub_role = Column(String)  # "admin" or "secretary" or "teacher"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


# ==========================================
# 2. معلمان
# ==========================================
class Teacher(Base):
    __tablename__ = "teachers"
    id = Column(Integer, primary_key=True, index=True)
    teacher_code = Column(Integer, unique=True, index=True, nullable=True) # جدید 🆕
    password = Column(String)
    is_approved = Column(Boolean, default=False)
    is_suspended = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False, server_default=text("FALSE"), nullable=False) # سافت‌دیلیت 🆕
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)

    first_name = Column(String)
    last_name = Column(String)
    father_name = Column(String)
    national_code = Column(String, unique=True)
    birth_date = Column(String)
    mobile = Column(String, unique=True)
    home_phone = Column(String)

    marital_status = Column(String)
    gender = Column(String)
    employment_type = Column(String)
    card_number = Column(String)
    profile_image = Column(String, nullable=True)

    # طلب معلم از آموزشگاه (بستانکاری)
    wallet_balance = Column(BigInteger, default=0)
    version = Column(Integer, default=1) # ستون نسخه برای قفل خوش‌بینانه (Optimistic Locking)

    courses = relationship("Course", back_populates="teacher")


# ==========================================
# 3. دانش‌آموزان
# ==========================================
class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True)
    student_code = Column(Integer, unique=True, index=True, nullable=True) # جدید 🆕
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)
    # FIX(H2): سایه‌های ورود (الگوی معلم) — nullable تا backfill بدون شکستن دیتای موجود
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # سایه‌ی نقش student
    parent_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # سایه‌ی نقش parent

    first_name = Column(String)
    last_name = Column(String)
    father_name = Column(String)
    national_code = Column(String, unique=True)
    birth_date = Column(String)
    # FIX M5: کیف‌پول‌ها BigInteger (هم‌خوان با Transaction.amount و بقیه‌ی ستون‌های مالی).
    wallet_teacher = Column(BigInteger, default=0)
    wallet_institute = Column(BigInteger, default=0)

    student_mobile = Column(String)
    parent_mobile = Column(String)
    home_phone = Column(String)
    address = Column(Text)

    study_status = Column(String)
    gender = Column(String)

    # 👇👇👇 فیلد جدید: وضعیت تعلیق 👇👇👇
    is_suspended = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False, server_default=text("FALSE"), nullable=False) # سافت‌دیلیت 🆕

    # کیف پول (مثبت = بستانکار / منفی = بدهکار)
    wallet_balance = Column(BigInteger, default=0)
    profile_image = Column(String, nullable=True)
    version = Column(Integer, default=1) # ستون نسخه برای قفل خوش‌بینانه (Optimistic Locking)

    enrollments = relationship("Enrollment", back_populates="student")

    # FIX: Bug 18 - the two component wallets are the single source of truth for the cached total.
    def sync_wallet_balance(self) -> int:
        self.wallet_balance = (self.wallet_teacher or 0) + (self.wallet_institute or 0)
        return self.wallet_balance


# FIX: Bug 18 - also enforce the same total when a caller changes components without an explicit sync.
@event.listens_for(Student, "before_insert")
@event.listens_for(Student, "before_update")
def _sync_student_wallet_before_write(mapper, connection, student):
    # FIX: Bug 18 - do not silently rewrite legacy totals during unrelated profile/metadata edits.
    state = inspect(student)
    if state.pending or any(state.attrs[name].history.has_changes() for name in ("wallet_teacher", "wallet_institute", "wallet_balance")):
        student.sync_wallet_balance()


# ==========================================
# 4. کلاس‌ها (تغییرات جدید اعمال شد)
# ==========================================
class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True, index=True)

    title = Column(String)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)
    code = Column(String, unique=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"))
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=True) # شناسه کلاس فیزیکی / اتاق 🆕

    education_type = Column(String)
    grade_level = Column(String)
    gender_type = Column(String)

    # نوع کلاس همیشه خصوصی است (طبق دستور جدید)
    class_type = Column(String, default="خصوصی")

    days_of_week = Column(String)  # روزهای برگزاری
    class_time = Column(String)  # ساعت برگزاری

    # 💰 قیمت‌گذاری جدید
    # معلم تعیین میکند برای هر جلسه چقدر میخواهد (تومان)
    teacher_session_price = Column(BigInteger, default=0)

    bg_color = Column(String, default="#FFFFFF")

    rule_prepay_institute = Column(Boolean, default=False)
    rule_prepay_teacher = Column(Boolean, default=False)
    rule_calc_absent = Column(Boolean, default=True)

    # 🛡️ وضعیت تایید کلاس توسط ادمین
    is_admin_approved = Column(Boolean, default=False)

    # 👇👇👇 فیلد جدید: وضعیت تعلیق کلاس 👇👇👇
    is_suspended = Column(Boolean, default=False)
    # گروه ۶: توقف موقت مستقل از تعلیق کامل؛ ثبت‌نام‌های فعلی حفظ می‌شوند.
    is_paused = Column(Boolean, default=False)
    capacity = Column(Integer, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    pending_since = Column(DateTime, nullable=True)
    is_deleted = Column(Boolean, default=False) # جدید 🆕

    teacher = relationship("Teacher", back_populates="courses")
    enrollments = relationship("Enrollment", back_populates="course")


# ==========================================
# 5. ثبت‌نام
# ==========================================
class Enrollment(Base):
    __tablename__ = "enrollments"
    id = Column(Integer, primary_key=True, index=True)

    student_id = Column(Integer, ForeignKey("students.id"))
    course_id = Column(Integer, ForeignKey("courses.id"))
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)

    register_date = Column(String)
    shift = Column(String)

    # این فیلدها شاید کمتر استفاده شوند چون محاسبه دینامیک است، اما برای آرشیو میمانند
    total_tuition = Column(BigInteger, default=0)
    total_paid = Column(BigInteger, default=0)
    discount_type = Column(String, default="none")  # "percentage", "fixed", or "none"
    discount_value = Column(BigInteger, default=0)
    # FIX: Bug 13 - retain enrollment IDs and financial history when enrollment is cancelled.
    is_deleted = Column(Boolean, default=False, server_default=text("FALSE"), nullable=False)

    student = relationship("Student", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")


# ==========================================
# 6. تراکنش‌ها
# ==========================================
class Transaction(Base):
    __tablename__ = "transactions"
    # FIX L4: ایندکس مرکب گزارش‌های مالی (فیلتر پرتکرار روی شاگرد+تاریخ).
    __table_args__ = (
        Index("ix_transactions_student_date", "student_id", "date"),
    )
    id = Column(Integer, primary_key=True, index=True)
    remittance_number = Column(Integer, index=True, nullable=True) # جدید 🆕
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)
    session_id = Column(Integer, ForeignKey("session_logs.id"), nullable=True) # جدید برای رهگیری جلسات 🆕
    # گروه ۶: link قابل‌ردگیری بین payout/reversal و aggregate settlement.
    settlement_id = Column(Integer, nullable=True, index=True)

    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    enrollment_id = Column(Integer, ForeignKey("enrollments.id"), nullable=True)

    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)

    amount = Column(BigInteger)  # مبلغ
    payment_method = Column(String)
    tracking_code = Column(String)
    date = Column(String)

    receiver = Column(String)
    description = Column(String)
    type = Column(String, nullable=True)  # tuition, deposit, etc.

    # برای ذخیره سهم تفکیک شده در هر تراکنش (جهت گزارشگیری دقیق)
    share_teacher = Column(BigInteger, default=0)
    share_institute = Column(BigInteger, default=0)

    # برای ذخیره اینکه تراکنش به کدام کیف پول واریز شده
    target_wallet = Column(String, nullable=True)  # "teacher", "institute", or None
    # FIX (audit-v2/idempotency): کلید retry روی همین جدول (نه جدول جدا — رسیدها خودشان سندند).
    # FIX (E2E-B2): عمداً NON-UNIQUE — معنای ستون «شناسه‌ی عملیات پرداخت» است نه «شناسه‌ی ردیف»:
    # حالت both دو رسید (teacher+institute) با یک کلید می‌سازد (finance.py) و خواننده‌ی replay هم
    # چندردیفه طراحی شده؛ یکتایی یعنی 500 قطعی روی هر پرداخت کلیددارِ both. ایندکس ساده برای سرعت lookup.
    idempotency_key = Column(String, nullable=True, index=True)
    # تعداد جلسه‌هایی که ادمین هنگام ثبت حواله اعلام کرده (اختیاری/گزارشی؛ در هیچ محاسبهٔ مالی نقش ندارد).
    sessions_covered = Column(Integer, nullable=True)

    is_deleted = Column(Boolean, default=False)
    is_reversed = Column(Boolean, default=False)

    # 🔥 ارتباطات (اضافه شد برای رفع ارور) 🔥
    student = relationship("Student")
    course = relationship("Course")


# ==========================================
# 6.5. پرداخت‌های آنلاین (Online Payments)
# ==========================================
class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    internal_transaction_id = Column(String, unique=True, index=True)
    gateway_reference = Column(String, nullable=True)
    tracking_code = Column(String, nullable=True)
    amount = Column(BigInteger)
    status = Column(String, default="PENDING")  # PENDING, VERIFYING, SUCCESS, FAILED, REFUNDED, CANCELLED
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)

    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    enrollment_id = Column(Integer, ForeignKey("enrollments.id"), nullable=True)
    installment_id = Column(Integer, ForeignKey("installments.id"), nullable=True)
    target_wallet = Column(String, nullable=True)  # "teacher" or "institute"
    description = Column(String, nullable=True)
    # FIX F-B1: درگاه همان‌مسیر initiate (کال‌بک با همان درگاه وریفای می‌کند) + مهر تسخیر VERIFYING.
    gateway = Column(String, nullable=True)  # "zarinpal" | "mellat" | "saman"
    claimed_at = Column(DateTime, nullable=True)  # آخرین تسخیر PENDING→VERIFYING (بازیابی گیرکرده‌ها)

    student = relationship("Student")


# ==========================================
# 7. دفترچه جلسات (Session Log) - جدید 🆕
# ==========================================
# این جدول اطلاعات هر جلسه‌ای که برگزار می‌شود را نگه می‌دارد
class SessionLog(Base):
    __tablename__ = "session_logs"
    # FIX: Bugs 14/17 - preserve cancelled session history while preventing duplicate active charges.
    __table_args__ = (
        Index(
            "uq_session_course_date_active", "course_id", "date", unique=True,
            sqlite_where=text("is_deleted = FALSE"),
            postgresql_where=text("is_deleted = FALSE"),
        ),
    )
    is_deleted = Column(Boolean, default=False, server_default=text("FALSE"), nullable=False)
    id = Column(Integer, primary_key=True, index=True)
    session_code = Column(Integer, unique=True, index=True, nullable=True) # جدید 🆕

    course_id = Column(Integer, ForeignKey("courses.id"))
    # FIX Audit Radar N+1: relationship for joinedload optimization (read-only audit)
    course = relationship("Course", foreign_keys=[course_id], lazy="select")
    date = Column(String)
    time = Column(String)

    # ذخیره قیمت‌ها در لحظه برگزاری (Snapshot)
    # چون ممکن است تعرفه‌ها در آینده تغییر کند، قیمت این جلسه باید ثابت بماند
    final_teacher_cost = Column(BigInteger, default=0)  # پولی که به معلم میرسد
    final_institute_share = Column(BigInteger, default=0)  # سهم آموزشگاه برای این جلسه
    cost_per_student = Column(BigInteger, default=0)  # هزینه‌ای که از هر دانش‌آموز کسر شد
    # FIX: H6(A2) - جریمه‌ی غایبین غیرموجه، جدا از مبالغ قراردادی (T_total/I_total)
    absent_penalty_teacher = Column(BigInteger, default=0)
    absent_penalty_institute = Column(BigInteger, default=0)
    # FIX H8-gap: فلگ سطح-جلسه‌ی تسویه‌ی جریمه‌ی غیبت — مستقل از Attendance، چون جریمه سطح-جلسه است نه سطح-ردیف.
    is_penalty_settled = Column(Boolean, default=False)

    attendee_count = Column(Integer, default=0)  # تعداد حاضرین
    status = Column(String, default="Finished")  # وضعیت جلسه

    # 🆕 زمان واقعی شروع و پایان جلسه (برای کلاس زنده)
    start_time = Column(String, nullable=True)  # HH:MM واقعی شروع
    end_time = Column(String, nullable=True)    # HH:MM واقعی پایان


# ==========================================
# 7.5. جلسات زنده (Live Sessions) - جدید 🆕
# ==========================================
# این جدول وضعیت «در حال برگزاری» کلاس را نگه می‌دارد. لایه‌ی وضعیت روی فرآیند
# ثبت جلسه‌ی موجود است؛ هیچ محاسبه‌ی مالی‌ای در این جدول انجام نمی‌شود.
class LiveSession(Base):
    __tablename__ = "live_sessions"
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"))
    teacher_id = Column(Integer, ForeignKey("teachers.id"))
    status = Column(String, default="SCHEDULED")  # SCHEDULED / LIVE / ENDED
    start_time = Column(String, nullable=True)  # ISO/رشته‌ای زمان شروع
    end_time = Column(String, nullable=True)    # ISO/رشته‌ای زمان پایان
    ended_automatically = Column(Boolean, default=False)  # پایان خودکار به‌خاطر فراموشی

    # برچسب زمانی برای نمایش «X دقیقه گذشته» (از server به client)
    started_at_ts = Column(BigInteger, nullable=True)  # epoch seconds شروع

    # وضعیت لحظه‌ای حاضرین: JSON بر حسب student_id -> {status, excused}
    # از این داده برای پایان جلسه استفاده می‌شود (بدون تغییر منطق مالی).
    live_roster = Column(Text, nullable=True)


# ==========================================
# 8. حضور و غیاب
# ==========================================
class Attendance(Base):
    __tablename__ = "attendances"
    # FIX: H6(C2) - یک رکورد حضور/غیاب برای هر (جلسه، دانش‌آموز).
    # FIX (F-S2): قید یکتا عمداً partial نشد؛ ردیف آرشیوشده هم جای خودش را نگه می‌دارد و مسیر
    # ویرایش جلسه همان ردیف را revive می‌کند (upsert) تا «یک ردیف به‌ازای هر جفت» همیشه برقرار بماند.
    # مزیت: روی دیتابیس‌های موجود (که این قید را از قبل دارند) هیچ مایگریشن قید لازم نیست.
    __table_args__ = (
        UniqueConstraint("session_id", "student_id", name="uq_attendance_session_student"),
    )
    id = Column(Integer, primary_key=True, index=True)

    # اتصال به جلسه خاص (نه فقط کلاس)
    session_id = Column(Integer, ForeignKey("session_logs.id"))
    student_id = Column(Integer, ForeignKey("students.id"))

    status = Column(String)  # Present, Absent, Late
    # FIX (F-S2): آرشیو نرم — سابقه‌ی حضور بعد از حذف/برگشت جلسه برای audit باقی می‌ماند.
    is_deleted = Column(Boolean, default=False, server_default=text("FALSE"), nullable=False)

    # آیا این جلسه در تسویه‌حساب معلم لحاظ شده؟ (فقط settle_teacher_sessions آن را True می‌کند)
    is_billed = Column(Boolean, default=False)
    excused = Column(Boolean, default=False)

    # Timeline N+1 fix: relationships for joinedload
    session = relationship("SessionLog", foreign_keys=[session_id], lazy="select")
    student = relationship("Student", foreign_keys=[student_id], lazy="select")


# ==========================================
# 9. پیامک‌ها
# ==========================================
class SmsLog(Base):
    __tablename__ = "sms_logs"
    id = Column(Integer, primary_key=True, index=True)
    target_group = Column(String)
    message_text = Column(String)
    sent_count = Column(Integer)
    date = Column(String)


# ==========================================
# 10. نمرات
# ==========================================
class Grade(Base):
    __tablename__ = "grades"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    course_id = Column(Integer, ForeignKey("courses.id"))
    teacher_id = Column(Integer, ForeignKey("teachers.id"))
    exam_title = Column(String)
    score = Column(Float)
    max_score = Column(Float)
    date = Column(String)
    description = Column(String, nullable=True)
    student = relationship("Student")
    course = relationship("Course")


# ==========================================
# 11. تنظیمات سهم آموزشگاه (15 حالت)
# ==========================================
class InstituteShare(Base):
    __tablename__ = "institute_shares"
    id = Column(Integer, primary_key=True, index=True)
    count_1 = Column(BigInteger, default=0)
    count_2 = Column(BigInteger, default=0)
    count_3 = Column(BigInteger, default=0)
    count_4 = Column(BigInteger, default=0)
    count_5 = Column(BigInteger, default=0)
    count_6 = Column(BigInteger, default=0)
    count_7 = Column(BigInteger, default=0)
    count_8 = Column(BigInteger, default=0)
    count_9 = Column(BigInteger, default=0)
    count_10 = Column(BigInteger, default=0)
    count_11 = Column(BigInteger, default=0)
    count_12 = Column(BigInteger, default=0)
    count_13 = Column(BigInteger, default=0)
    count_14 = Column(BigInteger, default=0)
    count_15 = Column(BigInteger, default=0)


# ==========================================
# 12. تسویه‌حساب با معلمان (Settlements) - جدید 🆕
# ==========================================
class Settlement(Base):
    __tablename__ = "settlements"
    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"))
    total_amount = Column(BigInteger, default=0)
    session_count = Column(Integer, default=0)
    # گروه ۶: snapshot شناسهٔ sessionها؛ immutable audit scope برای reverse/edit.
    session_ids_json = Column(Text, nullable=True)
    payout_transaction_id = Column(Integer, nullable=True)
    is_reversed = Column(Boolean, default=False)
    # نوع سند برگشت در Transaction با مقدار settlement_reversal/reversal ثبت می‌شود.
    reversal_reason = Column(Text, nullable=True)
    reversed_at = Column(DateTime, nullable=True)
    settled_at = Column(DateTime, default=datetime.datetime.utcnow)
    settled_by_user_id = Column(Integer, ForeignKey("users.id"))


# ==========================================
# 13. اقساط شهریه (Installments) - جدید 🆕
# ==========================================
class Installment(Base):
    __tablename__ = "installments"
    id = Column(Integer, primary_key=True, index=True)
    enrollment_id = Column(Integer, ForeignKey("enrollments.id"))
    amount = Column(BigInteger, default=0)
    due_date = Column(String)  # فرمت خورشیدی: yyyy/MM/dd
    is_paid = Column(Boolean, default=False)
    paid_at = Column(String, nullable=True)  # تاریخ واقعی پرداخت
    # FIX M13: پوشش تجمعی پرداخت جزئی — هر واریز به‌جای نادیده‌گرفتن، روی قسط انباشته می‌شود.
    paid_amount = Column(BigInteger, default=0)
    # FIX: Bug 13 - archive cancelled installments without falsifying their paid status.
    is_deleted = Column(Boolean, default=False, server_default=text("FALSE"), nullable=False)

    # Timeline N+1 fix: relationship for joinedload
    enrollment = relationship("Enrollment", foreign_keys=[enrollment_id], lazy="select")


# دفتر تخصیص پرداخت به اقساط (audit-v2/issues-7+9) - جدید 🆕
class TransactionInstallmentAllocation(Base):
    """هر پوششِ قسط از کدام رسید و به چه مبلغ. پوشش خودکار ۱→N با مبالغ جزئی است پس FK تکی
    روی Installment کافی نبود (تحلیل قدم ۳). استرداد دقیقاً همین ردیف‌ها را برمی‌گرداند؛ ردیف‌ها
    بعد از استرداد هم می‌مانند (تاریخچه). تاریخچه‌ی قبل-از-ledger ردیفی ندارد → رفتار امروز.
    مایگریشن طبق الگوی پروژه: create_all در main.py (تازه)؛ دیتابیس موجود: CREATE TABLE همین جدول."""
    __tablename__ = "transaction_installment_allocations"
    __table_args__ = (
        Index("ix_alloc_transaction", "transaction_id"),
        Index("ix_alloc_installment", "installment_id"),
    )
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    installment_id = Column(Integer, ForeignKey("installments.id"), nullable=False)
    amount = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)


# ==========================================
# 14. کدهای تایید موقت اولیا (Parent OTPs) - جدید 🆕
# ==========================================
class ParentOTP(Base):
    __tablename__ = "parent_otps"
    id = Column(Integer, primary_key=True, index=True)
    mobile = Column(String, index=True)
    otp = Column(String)  # FIX: حالا هش شده ذخیره می‌شود، نه plaintext
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime)
    is_used = Column(Boolean, default=False)
    # FIX: شمارنده تلاش و قفل برای امنیت OTP
    attempts = Column(Integer, default=0)
    is_locked = Column(Boolean, default=False)
    locked_until = Column(DateTime, nullable=True)


# ==========================================
# 14.5. لاگ فعالیت‌های حساس (Activity Log) - جدید 🆕
# ==========================================
class LoginAttempt(Base):
    """FIX H14: تلاش‌های ناموفق لاگین پسوردی — throttle جداگانه per-mobile (مستقل از ParentOTP که معناش OTP است)."""
    __tablename__ = "login_attempts"
    id = Column(Integer, primary_key=True, index=True)
    mobile = Column(String, index=True)
    attempted_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    ip = Column(String, nullable=True)  # IP تفکیک‌شده (forensics؛ throttle روی mobile است نه IP)


class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id = Column(Integer, primary_key=True, index=True)
    admin_username = Column(String)
    action = Column(String)
    target_id = Column(Integer, nullable=True)
    target_name = Column(String, nullable=True)
    details = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)


# ==========================================
# 14.6. اعلان‌ها (Notifications) - جدید 🆕
# ==========================================
class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    recipient_user_id = Column(Integer)
    recipient_role = Column(String)  # "admin", "secretary", "teacher", "student", "parent"
    type = Column(String)  # e.g., "attendance", "payment", "installment", etc.
    title = Column(String)
    body = Column(String)
    data = Column(String, nullable=True)  # JSON payload
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    scheduled_at = Column(DateTime, nullable=True)
    priority = Column(Integer, default=1)

class DeviceToken(Base):
    __tablename__ = "device_tokens"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    role = Column(String)
    token = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


# ==========================================
# 14.7. تکالیف (Homework & LMS) - جدید 🆕
# ==========================================
class Homework(Base):
    __tablename__ = "homeworks"
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"))
    teacher_id = Column(Integer, ForeignKey("teachers.id"))
    title = Column(String)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    due_date = Column(String)
    max_score = Column(Float, default=20.0)
    status = Column(String, default="pending")  # "pending", "submitted", "late", "graded", "returned"

class HomeworkSubmission(Base):
    __tablename__ = "homework_submissions"
    id = Column(Integer, primary_key=True, index=True)
    homework_id = Column(Integer, ForeignKey("homeworks.id"))
    student_id = Column(Integer, ForeignKey("students.id"))
    file_path = Column(String, nullable=True)
    status = Column(String, default="submitted")  # "submitted", "late", "graded", "returned"
    score = Column(Float, nullable=True)
    feedback = Column(String, nullable=True)
    submitted_at = Column(DateTime, default=datetime.datetime.utcnow)


# ==========================================
# 14.8. کلاس‌های فیزیکی و اتاق‌ها (Rooms) - جدید 🆕
# ==========================================
class Room(Base):
    __tablename__ = "rooms"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    capacity = Column(Integer, default=30)
    location = Column(String)
    equipment = Column(String, nullable=True)
    active = Column(Boolean, default=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)


# ==========================================
# ۱۴.۸.۵. منابع سخت‌افزاری و تجهیزات (Resources) - جدید 🆕
# ==========================================
class Resource(Base):
    __tablename__ = "resources"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)  # e.g., "پروژکتور سونی", "لپ‌تاپ دل"
    type = Column(String)  # "projector", "computer", "board", "books", "equipment"
    serial_code = Column(String, unique=True, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)
    active = Column(Boolean, default=True)

class ResourceBooking(Base):
    __tablename__ = "resource_bookings"
    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(Integer, ForeignKey("resources.id"))
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    days_of_week = Column(String)  # e.g., "شنبه"
    class_time = Column(String)    # e.g., "16:00"


# ==========================================
# 14.9. پیام‌رسان داخلی (Internal Messenger) - جدید 🆕
# ==========================================
class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=True)
    type = Column(String)  # "private", "group", "broadcast"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    pinned_by = Column(String, nullable=True)  # Comma-separated list of user_role_ids

class ConversationParticipant(Base):
    __tablename__ = "conversation_participants"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    user_id = Column(Integer)
    role = Column(String)

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    sender_id = Column(Integer)
    sender_role = Column(String)
    body = Column(String)
    attachment = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_deleted = Column(Boolean, default=False)

# ==========================================
# 14.10. آزمون‌های آنلاین و سوالات (Exam System) - جدید 🆕
# ==========================================
class Exam(Base):
    __tablename__ = "exams"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    course_id = Column(Integer, ForeignKey("courses.id"))
    teacher_id = Column(Integer, ForeignKey("teachers.id"))
    date = Column(String)
    duration = Column(Integer, default=60)  # duration in minutes
    max_score = Column(Float, default=20.0)
    status = Column(String, default="pending")  # "pending", "published"

class ExamQuestion(Base):
    __tablename__ = "exam_questions"
    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id"))
    question_text = Column(String)
    type = Column(String)  # "multiple_choice", "true_false", "short_answer", "descriptive"
    options = Column(String, nullable=True)  # Comma-separated options
    correct_answer = Column(String)  # Plain text answer or option number
    score_weight = Column(Float, default=1.0)

class ExamAttempt(Base):
    __tablename__ = "exam_attempts"
    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id"))
    student_id = Column(Integer, ForeignKey("students.id"))
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    submitted_at = Column(DateTime, nullable=True)
    score = Column(Float, nullable=True)
    graded_by_teacher = Column(Boolean, default=False)


# ==========================================
# 14.11. مدیریت جذب و سرنخ‌ها (CRM Lead) - جدید 🆕
# ==========================================
class Lead(Base):
    __tablename__ = "crm_leads"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    mobile = Column(String)
    interested_course = Column(String)
    source = Column(String, default="Web")  # "Web", "Referral", "Instagram", etc.
    status = Column(String, default="NEW")  # "NEW", "CONTACTED", "CONSULTATION", "WAITING", "REGISTERED", "LOST"
    assigned_user = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    next_follow_up = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True, default=1)
    converted_at = Column(DateTime, nullable=True)
    converted_student_id = Column(Integer, ForeignKey("students.id"), nullable=True)


# ==========================================
# 15. تنظیمات ثابت آموزشگاه - جدید 🆕
# ==========================================
class InstituteSettings(Base):
    __tablename__ = "institute_settings"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, default="آموزشگاه علمی خوارزمی")
    logo_path = Column(String, nullable=True)
    address = Column(String, default="تهران، خیابان شریعتی، نرسیده به پل صدر")
    phone = Column(String, default="02122222222")
    official_email = Column(String, default="info@kharazmi.com")
    footer_text = Column(String, default="با تشکر از اعتماد شما - آموزشگاه هوشمند خوارزمی") # جدید 🆕
    card_number = Column(String, default="۶۰۳۷۹۹۷۹۷۹۷۹۷۹۷۹") # شماره کارت آموزشگاه 🆕
    manager_mobile_1 = Column(String, default="09121112222") # موبایل مدیر ۱ 🆕
    manager_mobile_2 = Column(String, default="09123334444") # موبایل مدیر ۲ 🆕
    card_number_1 = Column(String, default="۶۰۳۷۹۹۷۹۷۹۷۹۷۹۷۹") # شماره کارت ۱ 🆕
    card_holder_1 = Column(String, default="خانم لطفی") # صاحب کارت ۱ 🆕
    card_number_2 = Column(String, default="۵۸۹۲۱۰۱۰۱۰۱۰۱۰۱۰") # شماره کارت ۲ 🆕
    card_holder_2 = Column(String, default="آقای علوی") # صاحب کارت ۲ 🆕
    teachers_active = Column(Boolean, default=True) # وضعیت فعالیت مربیان 🆕
    live_session_max_minutes = Column(Integer, default=180) # 🆕 آستانه‌ی پایان خودکار کلاس زنده (دقیقه)
    teacher_settlement_alert_days = Column(Integer, default=30) # آستانه هشدار تسویه‌نشده معلم (روز)


# ==========================================
# 🆕 جدول قیمت‌گذاری ۵ نفره برای ۴ گروه 🆕
# ==========================================
class PricingTable(Base):
    __tablename__ = "pricing_table"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, unique=True, index=True) # "elementary", "middle_school", "high_school", "institute"
    count_1 = Column(Integer, default=0)
    count_2 = Column(Integer, default=0)
    count_3 = Column(Integer, default=0)
    count_4 = Column(Integer, default=0)
    count_5 = Column(Integer, default=0)


# ==========================================
# 16. شمارنده‌های ترتیبی مستقل - جدید 🆕
# ==========================================
class SequenceCounter(Base):
    __tablename__ = "sequence_counters"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True) # "teacher", "student", "class", "session", "remittance_teacher", "remittance_institute"
    current_value = Column(Integer, default=0)


# ==========================================
# 🆕 قوانین و لاگ‌های خودکارسازی (Automation Engine Models) 🆕
# ==========================================
class AutomationRule(Base):
    __tablename__ = "automation_rules"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    condition_type = Column(String)  # attendance_low, absence_high, installment_due, installment_overdue, homework_deadline, grade_low, student_inactive, lead_uncontacted
    threshold = Column(Float, default=0.0)
    action_type = Column(String)  # parent_notification, parent_alert, student_notification, teacher_alert, crm_reminder, sms
    active = Column(Boolean, default=True)

class AutomationLog(Base):
    __tablename__ = "automation_logs"
    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, ForeignKey("automation_rules.id"))
    triggered_at = Column(DateTime, default=datetime.datetime.utcnow)
    details = Column(String, nullable=True)


# --- اجرا و آپدیت دیتابیس ---
if __name__ == "__main__":
    # Base.metadata.drop_all(bind=engine)

    # ساختن جداول جدید (اگر جدولی نباشد میسازد، اگر باشد کاری ندارد)
    Base.metadata.create_all(bind=engine)

    # 🛠️ آپدیت دستی: اضافه کردن ستون is_suspended به جدول students اگر وجود نداشته باشد
    with engine.connect() as conn:
        try:
            # تلاش برای اضافه کردن ستون به دیتابیس واقعی Postgres
            # این دستور فقط اگر ستون وجود نداشته باشد اجرا می‌شود
            conn.execute(
                text(
                    "ALTER TABLE students ADD COLUMN IF NOT EXISTS is_suspended BOOLEAN DEFAULT FALSE;"
                )
            )
            print("✅ ستون 'is_suspended' به جدول دانش‌آموزان اضافه شد (یا از قبل بود).")

            # اضافه کردن ستون is_suspended به جدول courses اگر وجود نداشته باشد
            conn.execute(
                text(
                    "ALTER TABLE courses ADD COLUMN IF NOT EXISTS is_suspended BOOLEAN DEFAULT FALSE;"
                )
            )
            print("✅ ستون 'is_suspended' به جدول کلاس‌ها اضافه شد (یا از قبل بود).")

            # اضافه کردن ستون card_number به جدول institute_settings اگر وجود نداشته باشد
            try:
                conn.execute(
                    text(
                        "ALTER TABLE institute_settings ADD COLUMN IF NOT EXISTS card_number VARCHAR DEFAULT '۶۰۳۷۹۹۷۹۷۹۷۹۷۹۷۹';"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE institute_settings ADD COLUMN IF NOT EXISTS manager_mobile_1 VARCHAR DEFAULT '09121112222';"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE institute_settings ADD COLUMN IF NOT EXISTS manager_mobile_2 VARCHAR DEFAULT '09123334444';"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE institute_settings ADD COLUMN IF NOT EXISTS card_number_1 VARCHAR DEFAULT '۶۰۳۷۹۹۷۹۷۹۷۹۷۹۷۹';"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE institute_settings ADD COLUMN IF NOT EXISTS card_holder_1 VARCHAR DEFAULT 'خانم لطفی';"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE institute_settings ADD COLUMN IF NOT EXISTS card_number_2 VARCHAR DEFAULT '۵۸۹۲۱۰۱۰۱۰۱۰۱۰۱۰';"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE institute_settings ADD COLUMN IF NOT EXISTS card_holder_2 VARCHAR DEFAULT 'آقای علوی';"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE institute_settings ADD COLUMN IF NOT EXISTS teachers_active BOOLEAN DEFAULT 1;"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE institute_settings ADD COLUMN IF NOT EXISTS live_session_max_minutes INTEGER DEFAULT 180;"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE institute_settings ADD COLUMN IF NOT EXISTS teacher_settlement_alert_days INTEGER DEFAULT 30;"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS branch_id INTEGER DEFAULT 1;"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS converted_at TIMESTAMP;"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS converted_student_id INTEGER;"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE session_logs ADD COLUMN IF NOT EXISTS start_time VARCHAR;"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE session_logs ADD COLUMN IF NOT EXISTS end_time VARCHAR;"
                    )
                )
                # FIX F-B1: ستون‌های کال‌بک پرداخت.
                conn.execute(
                    text(
                        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS gateway VARCHAR;"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMP;"
                    )
                )
                print("✅ ستون‌های جدید به جدول تنظیمات اضافه شدند (یا از قبل بودند).")
            except Exception:
                # در صورتی که sqlite باشد و IF NOT EXISTS ارور دهد
                pass
        except Exception as e:
            print(f"⚠️ نکته: {e}")

    print("✅ دیتابیس آپدیت شد (اطلاعات قبلی حفظ شد).")


class ClassRestoreLog(Base):
    """FIX(D1): دفتر بازیابی کلاس آرشیوشده — «چه کسی، چه زمانی، با چه دلیلی و در چه حالتی».

    چرا جدول جدا (نه تغییر وضعیت ClassDeletionRequest): وضعیت آن رکورد معنای «تصمیم حذف»
    دارد (pending/approved/rejected) و بازنویسی‌اش تاریخچهٔ تصمیم را از بین می‌برد.
    `pre_state_json` برای حسابرسی نگه داشته می‌شود که وضعیت پیش از بازیابی
    (کلاس/شمارش ردیف‌های آرشیوی و میزان اثر مالی) قابل بازبینی باشد.
    """
    __tablename__ = "class_restore_logs"
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    mode = Column(String, default="full")  # full or legacy metadata_only
    reason = Column(String, nullable=True)
    actor_user_id = Column(Integer, nullable=True)
    actor_name = Column(String, nullable=True)
    pre_state_json = Column(Text, nullable=True)
    finance_touched = Column(Boolean, default=False, nullable=False)
    restored_at = Column(DateTime, default=datetime.datetime.now)


class ClassDeletionRequest(Base):
    """درخواست حذف کلاس توسط معلم/منشی + تایید ادمین (اسنپ‌شات مالی برای بازبینی)."""
    __tablename__ = "class_deletion_requests"
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    requested_by_role = Column(String)  # teacher / secretary / admin
    requested_by_user_id = Column(Integer, nullable=True)
    requested_by_teacher_id = Column(Integer, nullable=True)
    forgive_session_charges = Column(Boolean, default=False)  # تیک: برگرداندن اثرات مالی جلسات
    status = Column(String, default="pending")  # pending / approved / rejected
    snapshot_json = Column(Text, nullable=True)  # اسنپ‌شات: جلسات/بدهی هر شاگرد + جمع‌ها
    admin_note = Column(String, nullable=True)
    decided_by_user_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.now)
    decided_at = Column(DateTime, nullable=True)


# ==========================================
# 15. ردگیری تغییرات مالی (Financial Audit Trail) - جدید 🆕
# ==========================================
class FinancialAuditLog(Base):
    """لاگ هر تغییر مالی روی Transaction/Installment («چه کسی، چه زمانی، چه چیزی را عوض کرد»).

    پر شدن این جدول **خودکار** است: listener های SQLAlchemy در `routers/audit_trail.py`
    (before_flush برای مقادیر قبلی + after_flush_postexec برای مقادیر جدید/PK) این ردیف‌ها را
    در **همان تراکنشِ نوشتن** درج می‌کنند؛ پس اگر تراکنش rollback شود، لاگ هم برمی‌گردد و
    هرگز تغییری لاگ نمی‌شود که commit نشده است.

    - old_values/new_values: JSON string از اسنپ‌شات کامل ستون‌ها (update: فقط اگر تغییر واقعی
      باشد؛ create: old تهی، delete: new تهی). ستون‌های تغییریافته در زمان خواندن محاسبه می‌شود.
    - user_id/username: از زمینه‌ی درخواست (میدل‌ور) — در نوشتن‌های سیستمی/ورکرها تهی می‌ماند.
    - timestamp: UTC ذخیره می‌شود (مثل بقیه‌ی ستون‌های زمانی سیستم) و اندپوینت آن را به وقت
      محلی سرور برمی‌گرداند تا در اپ درست دیده شود.
    مایگریشن طبق الگوی پروژه: `Base.metadata.create_all` در main.py + `CREATE TABLE IF NOT EXISTS`
    در `setup_audit_listeners()` (هر دو idempotent).
    """
    __tablename__ = "financial_audit_logs"
    # ایندکس‌ها برای صفحه‌بندی/فیلتر اندپوینت GET /audit-trail/logs (limit 50، ترتیب زمانی نزولی).
    __table_args__ = (
        Index("ix_fin_audit_timestamp", "timestamp"),
        Index("ix_fin_audit_entity", "entity_type", "entity_id"),
        Index("ix_fin_audit_action", "action"),
        Index("ix_fin_audit_user", "user_id"),
    )
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    username = Column(String(100), nullable=True)
    action = Column(String(50), nullable=False)       # 'create' | 'update' | 'delete'
    entity_type = Column(String(50), nullable=False)  # 'transaction' | 'installment'
    entity_id = Column(Integer, nullable=True)
    old_values = Column(Text, nullable=True)          # JSON string — مقادیر قبلی
    new_values = Column(Text, nullable=True)          # JSON string — مقادیر جدید
    ip_address = Column(String(45), nullable=True)    # IPv4/IPv6

    user = relationship("User")
