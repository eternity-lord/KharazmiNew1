import datetime
import html
import time  # O-05: چاپ حواله از time.time() برای ساخت print_job_id استفاده می‌کند

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import (  # FIX: Bug 22 - constrain online payment amounts at request validation.
    BaseModel,
    Field,
    field_validator,
)
from sqlalchemy import func
from sqlalchemy.orm import Session

import models

# FIX: Bug 16 - share the tuition-minus-payment debt calculation across financial views.
from dependencies import (
    _get_admin_username,
    check_admin_access,
    check_admin_or_secretary_access,
    check_student_access,
    check_user_login,
    display_name,
    get_db,
    get_enrollment_tuition_and_discount,
    get_session_parent,
    get_session_student,
    limiter,
)
from financial_calculations import (
    calculate_enrollment_debt_breakdown,
    session_fields_for_client,
)

# FIX: Bug 11 - the existing refund audit write needs its model imported at runtime.
from models import (
    ActivityLog,
    Attendance,
    Course,
    Enrollment,
    Installment,
    SessionLog,
    SmsLog,
    Student,
    Teacher,
    Transaction,
    TransactionInstallmentAllocation,
    User,
    UserSession,
)
from schemas import FinanceSubmitData, PrintReceiptRequest

# REFAC(P3a): دو خوشهٔ «دامنهٔ شعبه» و «گزارش بدهکاران» به لایهٔ service رفتند
# (services/branch_scope.py و services/debtor_report.py). این importها مصرفِ داخلیِ خودِ
# این فایل‌اند و هم‌زمان مسیر قدیمی `from routers.finance import build_debtor_rows /
# get_user_branch_filter` را زنده نگه می‌دارند — مسیری که `routers/exports.py` و
# `routers/reports.py` (و چند تست) استفاده می‌کردند. آن دو روتر حالا مستقیم از service
# import می‌کنند، پس دیگر وابستگیِ روتر→روتر و importِ lazy برای فرار از چرخه لازم نیست.
from services.branch_scope import get_user_branch_filter
from services.debtor_report import DEBT_AGE_BUCKETS, build_debtor_rows

# FIX (F-T2): اعتبارسنجی مرکزی تاریخ/مبلغ قسط — یک منبع حقیقت برای هر دو مسیر ساخت قسط.
from validation import validate_installment_amount, validate_jalali_due_date

router = APIRouter()


@router.get("/finance/search_advanced")
def search_finance_advanced(
    query: str,
    branch_id: int | None = None,
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
    sub_role: str = Depends(check_user_login)
):
    # REFAC(P3c): بدنهٔ دامنه (106 خط) به `services/finance_reports.py` رفت؛ این پوسته فقط لایهٔ HTTP است
    # (همان decorator، همان امضا، همان پاسخ JSON). نام تابع عمداً این‌جا می‌ماند:
    # امضا قراردادِ OpenAPI است و تست‌ها این handler را مستقیم از `routers.finance`
    # صدا می‌زنند.
    return finance_reports.search_finance_advanced(query, branch_id, authorization, db, sub_role)


# ==========================================
# اصلاح شده: ثبت واریزی و اصلاح کیف پول‌ها
# ==========================================


def _jalali_dt_str(value) -> str:
    """FIX (audit-v2/refund-date-followup): همان فرمت شمسی _jalali_now_str ولی برای datetime ذخیره‌شده (نه اکنون)."""
    from today_summary import jalali_date_string  # lazy، مثل H3-B3 همین فایل
    return jalali_date_string(value.date()) + value.strftime(" %H:%M")


@router.post("/finance/pay")
def submit_payment(
    data: FinanceSubmitData, db: Session = Depends(get_db), _: str = Depends(check_admin_or_secretary_access),
    branch_id: int | None = None, authorization: str | None = Header(None),
):
    # REFAC(P3b): بدنهٔ دامنه (335 خط) به `services/payments.py` رفت؛ این پوسته فقط لایهٔ HTTP است
    # (همان decorator، همان امضا، همان پاسخ). نام تابع عمداً این‌جا می‌ماند: امضا
    # قرارداد OpenAPI است و تست‌ها/اسکریپت‌ها این handler را مستقیم — گاهی با
    # آرگومان پوزیشنال — از `routers.finance` صدا می‌زنند.
    return payments.submit_payment(data, db, _, branch_id, authorization)


# ==========================================
# 🖨️ چاپ و ذخیره PDF حواله
# ==========================================


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
def print_receipt(req: PrintReceiptRequest, db: Session = Depends(get_db), authorization: str | None = Header(None), _: str = Depends(check_user_login)):
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
def generate_pdf_receipt(req: PrintReceiptRequest, db: Session = Depends(get_db), authorization: str | None = Header(None), _: str = Depends(check_user_login)):
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
def get_student_class_status(student_id: int, course_id: int | None = None, course_code: str | None = None, db: Session = Depends(get_db), authorization: str | None = Header(None), sub_role: str = Depends(check_user_login)):
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


# =========================================================================
# 💰 بخش جدید: اضافه کردن قابلیت‌های مالی پیشرفته و رفع نواقص (Finance Upgrades)
# =========================================================================

from fastapi.responses import HTMLResponse

from services import finance_reports, payments
from services.jalali_time import _jalali_now_str
from services.payments import PAYMENT_GATEWAY_ENABLED


# --- کمکی امنیتی جهت ممانعت از IDOR برای اولیا و دانش‌آموزان ---
def verify_financial_idor(student_id: int, authorization: str | None, db: Session) -> str:
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
    enrollment_id: int | None = None
    installment_id: int | None = None
    description: str | None = None
    gateway: str | None = "zarinpal"

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
    amount: int | None = Field(default=None, gt=0)
    due_date: str | None = None  # FIX (F-T2): ویرایش سررسید هم از همان قاعده‌ی تقویمی رد می‌شود
    is_paid: bool | None = None

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
    authorization: str | None = Header(None),
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


@router.get("/finance/payment/callback")
@limiter.limit("30/minute")
def payment_callback(
    request: Request,
    payment_id: int,
    status: str,
    gateway_ref: str | None = None,
    db: Session = Depends(get_db)
):
    # REFAC(P3b): بدنهٔ دامنه (462 خط) به `services/payments.py` رفت؛ این پوسته فقط لایهٔ HTTP است
    # (همان decorator، همان امضا، همان پاسخ). نام تابع عمداً این‌جا می‌ماند: امضا
    # قرارداد OpenAPI است و تست‌ها/اسکریپت‌ها این handler را مستقیم — گاهی با
    # آرگومان پوزیشنال — از `routers.finance` صدا می‌زنند.
    return payments.payment_callback(request, payment_id, status, gateway_ref, db)


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
    authorization: str | None = Header(None),
    _: str = Depends(check_admin_access)  # فقط مخصوص ادمین
):
    # REFAC(P3b): بدنهٔ دامنه (182 خط) به `services/payments.py` رفت؛ این پوسته فقط لایهٔ HTTP است
    # (همان decorator، همان امضا، همان پاسخ). نام تابع عمداً این‌جا می‌ماند: امضا
    # قرارداد OpenAPI است و تست‌ها/اسکریپت‌ها این handler را مستقیم — گاهی با
    # آرگومان پوزیشنال — از `routers.finance` صدا می‌زنند.
    return payments.refund_transaction(transaction_id, db, authorization, _)


# --- ۷. مدیریت اقساط شهریه (Installment Management) ---

# دریافت اقساط شهریه (ادمین / منشی)
@router.get("/finance/installments")
def get_all_installments(
    enrollment_id: int | None = None,
    student_id: int | None = None,
    db: Session = Depends(get_db),
    authorization: str | None = Header(None),
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
    authorization: str | None = Header(None),
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
    authorization: str | None = Header(None),
    force: bool = False,
    reason: str | None = None,
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
    authorization: str | None = Header(None),
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
    branch_id: int | None = None,
    payment_method: str | None = "نقدی",
    authorization: str | None = Header(None)
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
    authorization: str | None = Header(None),
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
    authorization: str | None = Header(None),
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
    authorization: str | None = Header(None),
    _role: str = Depends(check_user_login)
):
    # REFAC(P3c): بدنهٔ دامنه (104 خط) به `services/finance_reports.py` رفت؛ این پوسته فقط لایهٔ HTTP است
    # (همان decorator، همان امضا، همان پاسخ JSON). نام تابع عمداً این‌جا می‌ماند:
    # امضا قراردادِ OpenAPI است و تست‌ها این handler را مستقیم از `routers.finance`
    # صدا می‌زنند.
    return finance_reports.get_student_financial_dashboard(student_id, db, authorization, _role)


# --- ۱۱. داشبورد تراز مالی اولیا (Parent Financial Dashboard - مجهز به IDOR) ---
# ولی مستقیماً بر اساس توکن امن والدینی خود و فرزند انتخابی، اطلاعات مالی را دریافت می‌کند.
@router.get("/finance/parent/dashboard")
def get_parent_financial_dashboard(
    db: Session = Depends(get_db),
    authorization: str | None = Header(None),
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
    authorization: str | None = Header(None),
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
    authorization: str | None = Header(None),
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


@router.get("/finance/reports/debtors_list")
def get_debtors_list(
    branch_id: int | None = None,
    search: str | None = None,  # FIX (گروه۲/آیتم۹): جست‌وجو بر اساس نام دانش‌آموز/معلم/کلاس
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_or_secretary_access) # FIX (L14/Y4): کامنت «ادمین و منشی» حالا واقعاً اعمال می‌شود
):
    # FIX (گروه۲/آیتم ۶ و ۹): بدنهٔ تکراری با هلپر مشترک `build_debtor_rows` جایگزین شد —
    # همان فیلدهای قبلی (کلیدهای موجود برای کلاینت منتشرشده حفظ شده) به‌علاوهٔ فیلدهای جدید.
    resolved_branch = get_user_branch_filter(db, authorization, branch_id)
    return build_debtor_rows(db, resolved_branch, search)


@router.get("/finance/reports/debtors_grouped")
def get_debtors_grouped(
    branch_id: int | None = None,
    search: str | None = None,
    authorization: str | None = Header(None),
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
    student_ids: list[int]
    message: str | None = None


@router.post("/finance/debtors/remind")
def remind_debtors(
    req: DebtorsRemindRequest,
    authorization: str | None = Header(None),
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
    sent_ids: list[int] = []
    skipped_ids: list[int] = []
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
