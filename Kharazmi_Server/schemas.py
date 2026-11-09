# FIX: Bug 22 - validate identity writes and cross-field score bounds centrally.
from pydantic import BaseModel, Field, field_validator, model_validator

from validation import (
    NationalCodeRequest,
    validate_attendance_status,
    validate_installment_amount,
    validate_jalali_due_date,
)


class HistoryRequest(BaseModel):
    course_id: int

class LoginRequest(BaseModel):
    mobile: str
    password: str | None = None

class TeacherInfo(BaseModel):
    name: str
    mobile: str
    national_code: str
    status: str

# FIX: Bug 22 - apply the national-code checksum to this write path.
class StudentCreate(NationalCodeRequest):
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
    # FIX(branch): اختیاری — اگر ارسال نشود، سیاست resolve_creation_branch تصمیم می‌گیرد.
    branch_id: int | None = None

# FIX: Bug 22 - apply the national-code checksum to this write path.
class TeacherCreate(NationalCodeRequest):
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
    profile_image: str | None = None
    # FIX(teacher-approval): شعبه‌ی معلم هنگام ثبت — اختیاری و سازگار با اپ فعلی (که نمی‌فرستد).
    # اعتبارسنجی و تصمیم‌گیری با سیاست مرکزی resolve_creation_branch است (بدون حدس).
    branch_id: int | None = None

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
    teacher_session_price: int = Field(ge=0)  # FIX: Bug 22 - a session price cannot be negative.
    capacity: int | None = Field(default=None, gt=0)
    rule_prepay_institute: bool = False
    rule_prepay_teacher: bool = False
    rule_calc_absent: bool = True
    bg_color: str = "#FFFFFF"
    # FIX(branch): اختیاری — اگر ارسال نشود، سیاست resolve_creation_branch تصمیم می‌گیرد.
    branch_id: int | None = None

class InstallmentCreate(BaseModel):
    # FIX (F-T1/F-T2): همان اعتبارسنجی مرکزی مسیر مستقل قسط — مبلغ صحیح مثبت + تاریخ شمسی موجود.
    amount: int = Field(gt=0)
    due_date: str

    @field_validator("amount", mode="before")
    @classmethod
    def _validate_amount(cls, value):
        return validate_installment_amount(value)

    @field_validator("due_date")
    @classmethod
    def _validate_due_date(cls, value):
        return validate_jalali_due_date(value)

class EnrollmentCreate(BaseModel):
    student_id: int
    course_id: int
    register_date: str
    shift: str
    # FIX (گروه۱/آیتم۲): شهریهٔ پایه «صفر» = دانش‌آموز رایگان/معاف و باید مجاز باشد؛ فقط منفی
    # نامعتبر است. پیش‌تر `gt=0` بود ⇒ ثبت دانش‌آموز معاف با ۴۲۲ و پیام خام انگلیسی pydantic رد
    # می‌شد (خطای عمومی برای کاربر). این ناسازگاری با مسیر `register_and_enroll` هم بود که همان
    # مقدار را `Optional[int] = 0` می‌پذیرد. پیام خطای منفی فارسی و گویا است (۴۲۲ مثل قبل).
    total_tuition: int
    paid_amount: int = Field(ge=0)  # FIX: Bug 22 - zero means no initial payment; negatives are invalid.
    payment_method: str
    receiver: str
    discount_type: str | None = "none"
    discount_value: int | None = 0
    installments: list[InstallmentCreate] | None = None

    @field_validator("total_tuition", mode="before")
    @classmethod
    def _validate_total_tuition(cls, value):
        # mode="before" عمداً است: اگر محدودیت روی Field باشد (ge/gt)، pydantic اول همان را اجرا
        # می‌کند و پیام خام انگلیسی می‌سازد ⇒ پیام فارسیِ این validator هرگز دیده نمی‌شد.
        if isinstance(value, bool) or not isinstance(value, int):
            try:
                value = int(value)
            except (TypeError, ValueError):
                raise ValueError("شهریهٔ ثبت‌نام باید یک عدد صحیح باشد")
        if value < 0:
            raise ValueError("شهریهٔ ثبت‌نام نمی‌تواند منفی باشد؛ برای دانش‌آموز رایگان یا معاف عدد ۰ را وارد کنید")
        return value


class BulkEnrollmentCreate(BaseModel):
    """ورودی مشترک شهریه برای افزودن چند دانش‌آموز به یک کلاس."""
    student_ids: list[int] = Field(min_length=1)
    course_id: int
    register_date: str
    shift: str
    total_tuition: int
    paid_amount: int = Field(ge=0)
    payment_method: str
    receiver: str
    discount_type: str | None = "none"
    discount_value: int | None = 0
    installments: list[InstallmentCreate] | None = None


# مدل‌های مربوط به نمره

class GradeCreate(BaseModel):
    student_id: int
    course_id: int
    exam_title: str
    # FIX: Bug 22 - reject negative/non-finite scores and invalid denominators.
    score: float = Field(ge=0, allow_inf_nan=False)
    max_score: float = Field(gt=0, allow_inf_nan=False)
    date: str
    description: str = ""

    # FIX: Bug 22 - a grade must be bounded by the submitted maximum, before any database write.
    @model_validator(mode="after")
    def score_within_maximum(self):
        if self.score > self.max_score:
            raise ValueError("نمره نمی‌تواند بیشتر از نمرهٔ کل باشد")
        return self

class GradeItem(BaseModel):
    course_name: str
    exam_title: str
    score: float
    max_score: float
    date: str

class AttendanceLogRequest(BaseModel):
    course_id: int
    date: str

class AttendanceItem(BaseModel):
    student_id: int
    status: str
    excused: bool | None = False

    # FIX (F-S4): فقط Present / Late / Absent (قرارداد رسمی کلاینت اندروید + همه‌ی فیلترهای سرور).
    @field_validator("status")
    @classmethod
    def _validate_status(cls, value):
        return validate_attendance_status(value)

class AttendanceSubmitData(BaseModel):
    course_id: int
    date: str
    # FIX (F-S3): جلسه‌ی بی‌محتوا ممنوع — پیش‌تر items=[] یک SessionLog می‌ساخت و تاریخ کلاس را
    # قفل می‌کرد (ثبت واقعی بعدی ۴۰۹ می‌گرفت). مرز HTTP ⇒ ۴۲۲ (رفتار استاندارد FastAPI).
    items: list[AttendanceItem] = Field(min_length=1)

class SmsSendRequest(BaseModel):
    target_group: str
    message_text: str

class ChangePasswordRequest(BaseModel):
    mobile: str
    old_password: str
    new_password: str

class StudentProfileInfo(BaseModel):
    name: str
    national_code: str
    student_mobile: str
    parent_mobile: str
    address: str
    is_suspended: bool = False

class StudentActiveEnrollment(BaseModel):
    # FIX(invoice): enrollment فعال با شناسه‌های واقعی — برای صدور فیش بدون حدس از نام کلاس
    enrollment_id: int
    course_id: int
    title: str = ""
    code: str = ""
    branch_id: int | None = None
    course_title: str | None = None
    teacher_id: int | None = None
    teacher_name: str | None = None
    debt: int | None = None
    debt_teacher: int | None = None
    debt_institute: int | None = None
    total_debt: int | None = None
    is_unassigned: bool = False

class FullStudentProfile(BaseModel):
    info: StudentProfileInfo
    classes: list[str]
    enrollments: list[StudentActiveEnrollment] = []
    transactions: list[str]
    total_debt: int
    wallet_total: int = 0
    wallet_teacher: int = 0
    wallet_institute: int = 0
    debt_teacher: int = 0
    debt_institute: int = 0
    unassigned_debt: int = 0
    teachers_financial: list[dict] | None = None

class TeacherProfileInfo(BaseModel):
    name: str
    mobile: str
    national_code: str
    status: str  # فعال/غیرفعال
    profile_image: str | None = None
    teacher_code: int | None = None


class TeacherCollaborationSummary(BaseModel):
    period_days: int = 30
    period_start: str
    period_end: str
    average_delay_minutes: float
    delay_samples_count: int
    live_sessions_last_30_days: int
    total_settlements_count: int
    total_settled_amount: int
    auto_ended_sessions_count: int
    auto_ended_last_30_days_count: int


class FullTeacherProfile(BaseModel):
    info: TeacherProfileInfo
    total_students: int
    total_revenue: int  # درآمدزایی کل
    active_classes_count: int
    classes: list[str]  # لیست نام کلاس‌ها
    collaboration_summary: TeacherCollaborationSummary | None = None

class ClassReportInfo(BaseModel):
    title: str
    code: str
    teacher_name: str
    session_count: int  # تعداد جلسات برگزار شده
    total_students: int
    total_revenue: int  # کل درآمد وصول شده
    total_debt: int  # کل مطالبات (سازگاری پاسخ قدیمی؛ UI دیگر نمایش نمی‌دهد)
    debt_to_teacher: int = 0
    debt_to_institute: int = 0

class ClassStudentData(BaseModel):
    name: str
    mobile: str
    paid: int
    debt: int  # سازگاری پاسخ قدیمی؛ UI از دو سهم پایین استفاده می‌کند.
    debt_to_teacher: int = 0
    debt_to_institute: int = 0
    # Per-enrollment identity; optional defaults keep old clients/responses compatible.
    enrollment_id: int | None = None
    course_id: int | None = None
    course_title: str | None = None
    teacher_id: int | None = None
    teacher_name: str | None = None
    is_unassigned: bool = False

class ClassSessionStudent(BaseModel):
    """FIX (تاریخچهٔ جلسات): یک ردیف حاضر/غایبِ داخل یک جلسه — نام برای نمایش، شناسه‌ها برای
    استفاده‌های بعدی (مثل لینک به پروفایل شاگرد)."""
    student_id: int
    name: str  # نام نمایشی (legacy NULL ⇒ «نامشخص»)
    student_code: int | None = None
    status: str = "Present"  # Present / Late / Absent
    excused: bool = False


class ClassSessionHistory(BaseModel):
    date: str
    present_count: int
    absent_count: int
    # FIX (تاریخچهٔ جلسات): فیلدهای نمایشی این تب برای هر کلاس اضافه شد (نام حاضرین/غایبین،
    # روز هفته، هزینه و ساعت جلسه). همه با پیش‌فرض‌اند تا پاسخ برای کلاینت قدیمی سازگار بماند
    # و کش قدیمیِ اپ هم نشکند.
    session_id: int | None = None
    session_code: int | None = None
    weekday: str = ""
    present_students: list[ClassSessionStudent] = []
    absent_students: list[ClassSessionStudent] = []
    total_cost: int = 0
    cost_per_student: int = 0
    start_time: str = ""
    end_time: str = ""

class FullClassReport(BaseModel):
    info: ClassReportInfo
    students: list[ClassStudentData]
    sessions: list[ClassSessionHistory]

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

# FIX: Bug 22 - apply the national-code checksum to this write path.
class StudentUpdate(NationalCodeRequest):
    first_name: str | None = None
    last_name: str | None = None
    father_name: str | None = None
    national_code: str | None = None
    birth_date: str | None = None
    student_mobile: str | None = None
    parent_mobile: str | None = None
    home_phone: str | None = None
    address: str | None = None
    study_status: str | None = None
    gender: str | None = None
    version: int | None = None

# FIX: Bug 22 - apply the national-code checksum to this write path.
class TeacherUpdate(NationalCodeRequest):
    first_name: str | None = None
    last_name: str | None = None
    father_name: str | None = None
    national_code: str | None = None
    birth_date: str | None = None
    mobile: str | None = None
    password: str | None = None
    home_phone: str | None = None
    marital_status: str | None = None
    gender: str | None = None
    employment_type: str | None = None
    card_number: str | None = None
    profile_image: str | None = None
    version: int | None = None

class PersonListItem(BaseModel):
    id: int
    name: str
    national_code: str
    mobile: str
    role: str  # 'student' or 'teacher'
    is_suspended: bool = False


# FIX(security): آیتم امن لیست معلم‌ها — بدون password، بدون card_number، بدون national_code.
class TeacherListItem(BaseModel):
    id: int
    first_name: str
    last_name: str
    mobile: str | None = None
    teacher_code: int | None = None
    profile_image: str | None = None
    is_approved: bool = False
    is_suspended: bool = False


# FIX(teacher-approval): آیتم صف «درخواست‌های تایید معلم» — افزودنی و سازگار با TeacherListItem
# (کلاینت قدیمی فیلدهای اضافه را نادیده می‌گیرد) تا ادمین شعبه‌ی هر درخواست را ببیند.
class PendingTeacherItem(TeacherListItem):
    branch_id: int | None = None
    branch_name: str | None = None


# FIX(security): آیتم امن تاریخچه پیامک — message_text باید قبل از ساخت، ماسک شده باشد (کدهای OTP).
class SmsHistoryItem(BaseModel):
    id: int
    target_group: str | None = None
    message_text: str | None = None
    sent_count: int | None = None
    date: str | None = None


# 1. جستجوی دانش‌آموزان (همه یا با فیلتر)

class TransactionUpdate(BaseModel):
    amount: int
    description: str
    date: str


# 1. دریافت لیست کامل تراکنش‌ها (با قابلیت جستجو)

class StudentAttendanceHistoryRequest(BaseModel):
    student_id: int
    course_id: int

class AdvancedSearchItem(BaseModel):
    type: str
    id: int
    title: str
    subtitle: str
    info: str
    student_id: int | None = None
    course_id: int | None = None
    debt_teacher: int | None = 0
    debt_institute: int | None = 0
    total_debt: int | None = 0
    unpaid_sessions: int | None = 0
    students_in_class: list[dict] | None = None

class FinanceSubmitData(BaseModel):
    student_id: int
    amount: int
    target_wallet: str  # "teacher" یا "institute" یا "both"
    description: str
    payment_method: str
    date: str
    amount_institute: int | None = None
    amount_teacher: int | None = None
    enrollment_id: int | None = None  # اتصال پرداخت به یک ثبت‌نام خاص (اختیاری؛ اگر خالی باشد و شاگرد فقط یک ثبت‌نام فعال داشته باشد، خودکار وصل می‌شود)
    idempotency_key: str | None = None  # FIX (audit-v2/idempotency): اختیاری و backward-compatible — کلاینت قدیمی نفرستد = رفتار فعلی
    # «این حواله برای چند جلسه است؟» — اختیاری و فقط گزارشی (روی مبلغ/کیف‌پول اثر ندارد)؛ نیازمند enrollment مشخص.
    sessions_covered: int | None = Field(default=None, ge=1, le=1000)

class PrintReceiptRequest(BaseModel):
    transaction_id: int
    print_type: str  # "print" or "pdf"

class TransactionTestData(BaseModel):
    student_id: int
    amount: int = Field(gt=0)  # FIX: Bug 22 - even the payment diagnostic must require a positive credit.
    target_wallet: str
    description: str
    payment_method: str
    date: str

class SettleRequest(BaseModel):
    session_ids: list[int]

# FIX: Bug 22 - apply the national-code checksum to this write path.
class StudentRegisterAndEnrollRequest(NationalCodeRequest):
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
    course_id: int | None = None
    total_tuition: int | None = 0
    paid_amount: int = Field(default=0, ge=0)  # FIX: Bug 22 - permit unpaid registration, not null/negative payments.
    payment_method: str | None = "-"
    receiver: str | None = "-"
    discount_type: str | None = "none"
    discount_value: int | None = 0
    register_date: str | None = "1404/09/01"
    shift: str | None = "عصر"
    installments: list[InstallmentCreate] | None = None
    # FIX(branch): اختیاری — اگر ارسال نشود، سیاست resolve_creation_branch تصمیم می‌گیرد.
    branch_id: int | None = None

class BulkSmsRequest(BaseModel):
    student_ids: list[int]

class BulkSuspendRequest(BaseModel):
    course_ids: list[int]

class ParentOtpRequest(BaseModel):
    mobile: str

class ParentLoginRequest(BaseModel):
    mobile: str
    otp: str

class ChildSelectRequest(BaseModel):
    student_id: int
    temp_token: str

class InstituteSettingsModel(BaseModel):
    name: str
    logo_path: str | None = None
    address: str
    phone: str
    official_email: str | None = None
    footer_text: str | None = "با تشکر از اعتماد شما - آموزشگاه هوشمند خوارزمی"
    card_number: str | None = "۶۰۳۷۹۹۷۹۷۹۷۹۷۹۷۹"
    manager_mobile_1: str | None = "09121112222"
    manager_mobile_2: str | None = "09123334444"
    card_number_1: str | None = "۶۰۳۷۹۹۷۹۷۹۷۹۷۹۷۹"
    card_holder_1: str | None = "خانم لطفی"
    card_number_2: str | None = "۵۸۹۲۱۰۱۰۱۰۱۰۱۰۱۰"
    card_holder_2: str | None = "آقای علوی"
    teachers_active: bool | None = True
    live_session_max_minutes: int | None = 180
    teacher_settlement_alert_days: int | None = Field(default=None, ge=1, le=3650)


# ==========================================
# 🆕 طرح‌واره‌ی جدول قیمت‌گذاری ۵ نفره 🆕
# ==========================================
class PricingRowModel(BaseModel):
    category: str
    count_1: int
    count_2: int
    count_3: int
    count_4: int
    count_5: int

class PricingTableUpdateModel(BaseModel):
    rows: list[PricingRowModel]
