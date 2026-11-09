
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from dependencies import check_admin_secretary_or_teacher_access, get_db, resolve_session_teacher
from models import Course, Enrollment, Installment, Student, Transaction
from schemas import EnrollmentCreate
from validation import normalize_installments

"""لایهٔ سرویسِ «ثبت‌نام دانش‌آموز در کلاس».

بدنهٔ دامنه‌ایِ `POST /enrollments/add`: اعتبارسنجی ظرفیت/تکراری/شعبه، ساخت
Enrollment، و اثرهای مالیِ ثبت‌نام.

قرارداد لایه در `services/__init__.py`: بدون route و بدون APIRouter. این تابع هم
توسط `add_bulk_enrollments` در همان روتر و هم توسط تست‌ها مستقیم صدا زده
می‌شود (`from routers.classes import add_enrollment`)، پس handler در روتر به‌صورت
پوستهٔ HTTP باقی مانده است.
"""


def add_enrollment(
    data: EnrollmentCreate,
    db: Session = Depends(get_db),
    sub_role: str = Depends(check_admin_secretary_or_teacher_access),
    authorization: str | None = Header(None),
):
    """بدنهٔ دامنه‌ایِ `add_enrollment`؛ توضیح HTTP در پوستهٔ روتر است."""
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
