"""لایهٔ سرویسِ «ثبت جلسهٔ کلاسی» — بدنهٔ دامنه‌ایِ `submit_session_and_calculate`.

این ماژول بخشی از لایهٔ سرویس است (قراردادِ لایه در `services/__init__.py`):
بدون route و بدون APIRouter؛ منطق خالصِ ثبت جلسه + محاسبهٔ سهم‌ها + تراکنش‌های
مالی + اعلان‌ها.

نکتهٔ مهم دربارهٔ نام: خودِ handler همچنان در `routers/attendance.py` تعریف شده
و بدنه‌اش را به تابعِ همین ماژول واگذار می‌کند. دلیلش این است که این تابع یک
**قرارداد عمومیِ فرا-HTTP** دارد:

* حدودِ دوازده تست (test_attendance_sessions_audit.py، test_priority2_financial.py،
  test_wallet_finance_audit.py، test_branch_resolution.py، ...) آن را مستقیم و به‌صورت
  `attendance.submit_session_and_calculate(request, db=..., authorization=..., sub_role=...)`
  صدا می‌زنند؛
* `scripts/run_financial_audit.py` آن را از `routers.attendance` import می‌کند و
  **به‌صورت پوزیشنال** (`(data, db, "admin")`) صدا می‌زند؛
* `finalize_live_session` (کلاس زنده) آن را با `_system_caller="live_system"` صدا می‌زند.

پس امضای تابعِ سرویس باید **همان ترتیب و همان اسمِ پارامترها** را داشته باشد تا
هر سه شیوهٔ فراخوانی (پوزیشنال، کلیدواژه‌ای، و از مسیر HTTP با Depends) دست‌نخورده
کار کنند. بدنه هم بایت‌به‌بایت همان کد قبلی است؛ هیچ رفتاری تغییر نکرده.
"""
# NOTE: `Depends` / `Header` / `check_user_login` / `get_db` اینجا فقط به این دلیل
# import شده‌اند که **امضای تابع** (annotationها) دقیقاً مثل قبل بماند؛ خودِ تزریق
# وابستگی کارِ FastAPI روی پوستهٔ داخل روتر است و این تابع مقدارِ تزریق‌شده را می‌گیرد.
from fastapi import Depends, Header, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from dependencies import (
    check_user_login,
    display_name,
    get_db,
    validate_session_item_statuses,
    validate_session_items_membership,
)
from financial_calculations import compute_session_shares
from models import Attendance, Course, SessionLog, Student, Transaction
from schemas import AttendanceSubmitData

# آجرهای مشترک، از همان لایهٔ سرویس (نه از روتر) گرفته می‌شوند؛ `routers/attendance.py`
# هم همین نام‌ها را بازصادرات می‌کند تا مسیرهای قدیمی دست‌نخورده بمانند.
from services.live_session import _upsert_attendance_row, _verify_live_course_teacher


def submit_session_and_calculate(
    data: AttendanceSubmitData, db: Session = Depends(get_db), authorization: str | None = Header(None),
    sub_role: str = Depends(check_user_login), _system_caller: str | None = None
):
    print(f"--- شروع ثبت جلسه برای کلاس {data.course_id} ---")  # Log

    # FIX B3: بدون with_for_update (روی SQLite بی‌اثر است و گیت واقعی تکراری‌ها پایین است) —
    # این خواندن فقط برای 404 و ruleهاست.
    course = db.query(Course).filter(Course.id == data.course_id).first()
    if not course:
        raise HTTPException(404, "کلاس یافت نشد")
    # FIX (audit-v2/H-caller): احراز مالکیت تماس‌گیرنده (معلمِ کلاس یا ادمین/منشی) — قبلاً هر
    # لاگینی (حتی شاگرد/ولی) می‌توانست برای هر کلاسی جلسه ثبت و کیف‌ها را شارژ کند. fail-fast
    # قبل از H10/409/422 تا کاربر غیرمجاز وضعیتی لو ندهد؛ مسیر مشروع بی‌تغییر می‌ماند (قدم ۴).
    # FIX F-C8: فراخوان داخلی finalize (سیستم) — مالکیت در end_live راستی‌آزمایی شده / ورکر actor معتمد است.
    # (گارد H-caller شاخه‌ی سیستم را نداشت و هر end_live را 500 می‌کرد؛ این پارامتر همان طرح اصلی است.)
    if _system_caller != "live_system":
        _verify_live_course_teacher(db, course, authorization, sub_role, action_label="جلسه‌ی این کلاس")
    # FIX H10: ثبت جلسه‌ی جدید در کلاس معلق ممنوع (قبل از هر محاسبه/شارژ).
    if course.is_suspended:
        raise HTTPException(status_code=403, detail="این کلاس معلق است و امکان ثبت جلسه‌ی جدید برای آن وجود ندارد")
    if course.is_paused:
        raise HTTPException(status_code=403, detail="این کلاس موقتاً متوقف است و امکان ثبت جلسه‌ی جدید وجود ندارد")

    # FIX (audit-v2/#13): تاریخ کانونیکال شمسی — ولیدیت + نرمالایز با مبدل مرکزی H3 (قبلاً رشته‌ی خام
    # کلاینت ذخیره/مقایسه می‌شد: «2026/09/12» در برابر «1405/06/21» روز متفاوت حساب می‌شد → دابل‌سشن
    # و دابل‌شارژ cross-client). نامعتبر → 422. بعد از 403ها (عدم لو وضعیت به غیرمجاز) و قبل از چک تکراری.
    from today_summary import jalali_date_string, parse_project_date  # lazy، مثل finance
    _sday = parse_project_date(data.date)
    if _sday is None:
        raise HTTPException(status_code=422, detail="فرمت تاریخ جلسه معتبر نیست (yyyy/MM/dd شمسی یا میلادی)")
    data.date = jalali_date_string(_sday)
    # FIX: Bug 17 - reject duplicates before allocating a session code or changing any wallet.
    if db.query(SessionLog.id).filter(
        SessionLog.course_id == data.course_id, SessionLog.date == data.date,
        SessionLog.is_deleted == False,
    ).first():
        raise HTTPException(status_code=409, detail="جلسه این کلاس در این تاریخ قبلاً ثبت شده است")

    # FIX (F-S3): درخواست بدون هیچ ردیف حضور/غیاب نباید جلسه بسازد (schema هم min_length=1 دارد؛
    # این گارد برای فراخوان مستقیم تابعی است) — وگرنه یک درخواست خالی تاریخ کلاس را برای همیشه قفل می‌کند.
    if not data.items:
        raise HTTPException(
            status_code=422,
            detail="لیست حضور/غیاب نمی‌تواند خالی باشد؛ برای ثبت جلسه حداقل یک دانش‌آموز لازم است",
        )

    # FIX: H6(C1) - آیتم تکراری برای یک دانش‌آموز در همین ثبت ممنوع (قبل از هر db.add).
    seen_ids = set()
    for i in data.items:
        if i.student_id in seen_ids:
            raise HTTPException(status_code=422, detail=f"دانش‌آموز {i.student_id} بیش از یک‌بار در لیست حضور/غیاب تکرار شده است")
        seen_ids.add(i.student_id)

    # FIX: H6(B) - همه‌ی آیتم‌ها باید عضو فعال همین کلاس باشند (قبل از هر db.add).
    validate_session_items_membership(db, course.id, data.items)
    # FIX (F-S4): وضعیت‌های نامعتبر باید قبل از ساخت جلسه/حضور/تراکنش رد شوند (گارد فراخوان مستقیم).
    validate_session_item_statuses(data.items)

    # 1. شمارش حاضرین و غایبین غیرموجه مشمول جریمه
    present_students = [i for i in data.items if i.status in ["Present", "Late"]]
    present_count = len(present_students)
    absent_unexcused_count = sum(
        1 for i in data.items
        if i.status == "Absent" and course.rule_calc_absent and not (getattr(i, "excused", False) or False)
    )
    print(f"تعداد حاضرین: {present_count}")  # Log

    # FIX: H5/H6 - محاسبه‌ی یکتا از تابع مشترک (قدم ۱ و ۲)؛ قبل از ساخت جلسه تا خطا، نیم‌کاره نماند.
    # FIX L2: seed چرخش = (کلاس، تاریخ) — هر جلسه آفست متفاوتی می‌گیرد.
    shares = compute_session_shares(db, course, present_count, absent_unexcused_count,
                                    rotation_seed=f"{course.id}:{data.date}")
    teacher_share_per_student = shares["teacher_share_per_student"]
    institute_share_per_student = shares["institute_share_per_student"]
    teacher_share_distribution = shares["teacher_share_distribution"]
    institute_share_distribution = shares["institute_share_distribution"]
    total_cost_per_student = shares["total_cost_per_student"]
    final_teacher_income = shares["T_total"]
    final_institute_income = shares["I_total"]
    if present_count <= 0:
        print("💡 تعداد حاضرین صفر است: هیچ هزینه‌ای کسر نمی‌شود.")

    # 4. ثبت جلسه
    from dependencies import get_next_sequence_value
    next_code = get_next_sequence_value(db, "session", 100001)

    session = SessionLog(
        course_id=course.id,
        date=data.date,
        session_code=next_code,
        final_teacher_cost=final_teacher_income,
        final_institute_share=final_institute_income,
        # FIX: H6(A2) - جریمه جدا از مبالغ قراردادی؛ در حلقه‌ی پایین انباشته می‌شود.
        absent_penalty_teacher=0,
        absent_penalty_institute=0,
        cost_per_student=total_cost_per_student,
        attendee_count=present_count,
    )
    db.add(session)
    # FIX: Bug 17 - the unique index also handles racing requests; do not commit a partial session.
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        if db.query(SessionLog.id).filter(
            SessionLog.course_id == data.course_id, SessionLog.date == data.date,
            SessionLog.is_deleted == False,
        ).first():
            raise HTTPException(status_code=409, detail="جلسه این کلاس در این تاریخ قبلاً ثبت شده است")
        raise

    # FIX B3 (backstop): شمارش بعد از flush و قبل از هر شارژ/کامیت — اگر رقیبی بین pre-check و flush
    # کامیت کرده باشد، سطر خودمان + آن = ۲ دیده می‌شود ← rollback + همان 409 تکراری.
    # NOTE: با وجود ایندکس یکتای partial (models.py، uq_session_course_date_active) گارد اصلی همان
    # ایندکس است (خطای flush) و این چک backstop برای schema drift است؛ با .count بدون ایمپورت جدید.
    dup_count = (
        db.query(SessionLog.id)
        .filter(
            SessionLog.course_id == data.course_id, SessionLog.date == data.date,
            SessionLog.is_deleted == False,
        )
        .count()
    )
    if dup_count > 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="جلسه این کلاس در این تاریخ قبلاً ثبت شده است")

    # 5. کسر پول از کیف پول‌ها و ثبت تراکنش‌ها
    charge_index = 0
    for item in data.items:
        excused_val = getattr(item, "excused", False) or False

        # FIX: H6(B) - بدون دانش‌آموز معتبر، نه رکورد حضور ساخته می‌شود نه شارژ/اطلاع‌رسانی.
        st = db.query(Student).filter(Student.id == item.student_id, Student.is_deleted == False).first()
        if st is None:
            continue

        # FIX (F-S2): upsert — ردیف آرشیوشده‌ی همین (جلسه، دانش‌آموز) احیا می‌شود نه INSERT تازه.
        att = _upsert_attendance_row(db, session.id, item.student_id, item.status, excused_val)

        # تعیین وضعیت کسر وجه: حاضرین و غایبین غیرموجه (اگر جریمه غیبت فعال باشد)
        should_charge = False
        if item.status in ["Present", "Late"]:
            should_charge = True
        elif item.status == "Absent":
            if course.rule_calc_absent and not excused_val:
                should_charge = True
                print("💡 دانش‌آموز دارای غیبت غیرموجه: جریمه جلسه اعمال می‌گردد")  # FIX L1: بدون PII.
            else:
                print("💡 دانش‌آموز دارای غیبت موجه یا جریمه‌ی غیرفعال کلاس: کسر وجه صورت نمی‌گیرد")  # FIX L1: بدون PII.

        if should_charge:
            curr_w_t = st.wallet_teacher if st.wallet_teacher is not None else 0
            curr_w_i = st.wallet_institute if st.wallet_institute is not None else 0

            if item.status in ["Present", "Late"]:
                inst_share_value = (
                    institute_share_distribution[charge_index]
                    if charge_index < len(institute_share_distribution)
                    else institute_share_per_student
                )
                teacher_share_value = (
                    teacher_share_distribution[charge_index]
                    if charge_index < len(teacher_share_distribution)
                    else teacher_share_per_student
                )
                charge_index += 1
            else:
                inst_share_value = institute_share_per_student
                teacher_share_value = teacher_share_per_student
                # FIX: H6(A2) - انباشت جریمه‌ی واقعی در ستون‌های جدا (نه داخل final_*).
                session.absent_penalty_teacher += teacher_share_value
                session.absent_penalty_institute += inst_share_value

            # عملیات کسر از کیف پول‌ها
            st.wallet_teacher = curr_w_t - teacher_share_value
            st.wallet_institute = curr_w_i - inst_share_value

            # FIX H7 (الگوی Bug 9): شارژ مالی دنبال شعبه‌ی شاگرد می‌رود، با fallback به شعبه‌ی کلاس.
            # مثل Bug 9، تراکنش مالی بدون شعبه ساخته نمی‌شود — این خطا قبل از کامیت نهایی است و همه‌چیز rollback می‌شود.
            charge_branch = st.branch_id if st.branch_id is not None else course.branch_id
            if charge_branch is None:
                db.rollback()
                raise HTTPException(status_code=400, detail="شعبه این دانش‌آموز یا کلاس مشخص نیست؛ امکان ثبت شارژ مالی نیست")

            # FIX: Bug 18 - derive the total only through the shared wallet helper.
            st.sync_wallet_balance()

            # ثبت تراکنش سیستم
            db.add(
                Transaction(
                    student_id=item.student_id,
                    branch_id=charge_branch,  # FIX H7: شعبه‌ی شاگرد (fallback: کلاس) — الگوی Bug 9.
                    course_id=course.id,
                    session_id=session.id, # جدید 🆕
                    amount=-(teacher_share_value + inst_share_value),
                    payment_method="System",
                    date=data.date,
                    type="session_charge",
                    share_teacher=teacher_share_value,
                    share_institute=inst_share_value,
                    description=f"هزینه جلسه - {'حاضر' if item.status in ['Present', 'Late'] else 'غایب غیرموجه'} (معلم: {teacher_share_value}، آموزشگاه: {inst_share_value})",
                )
            )

        if item.status == "Absent":
            from dependencies import NotificationService, ensure_student_shadow_users
            excused_str = "موجه" if excused_val else "غیرموجه"
            if st.parent_user_id is None:
                ensure_student_shadow_users(db, st)
            NotificationService.send_notification(
                db=db,
                recipient_user_id=st.parent_user_id,
                recipient_role="parent",
                type="attendance",
                title=f"⚠️ گزارش غیبت دانش‌آموز: {display_name(st, 'دانش‌آموز')}",
                body=f"به اطلاع می‌رساند فرزند شما در تاریخ {data.date} در کلاس {course.title} به صورت {excused_str} غایب بوده است.",
                commit=False,  # FIX atomicity: کامیت با کامیت نهایی حلقه ثبت جلسه (خط پایانی تابع)
            )


    # FIX: H6(C2) - backstop یکتایی (session_id, student_id) در سطح دیتابیس.
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="رکورد تکراری حضور/غیاب برای این جلسه ثبت شده است")
    print("--- پایان ثبت جلسه کلاسی ---")  # Log

    return {
        "message": "جلسه ثبت شد.",
        "session_id": session.id,
        "session_code": session.session_code,
        "details": {
            "present_count": present_count,
            "cost_per_student": total_cost_per_student,
            "teacher_share": final_teacher_income,
            "institute_share": final_institute_income,
            # FIX: H6(A2) - جریمه‌ی جدا + جمع واقعی جلسه.
            "absent_penalty_teacher": session.absent_penalty_teacher,
            "absent_penalty_institute": session.absent_penalty_institute,
            "total_session_cost": (
                (final_teacher_income or 0) + (final_institute_income or 0)
                + (session.absent_penalty_teacher or 0) + (session.absent_penalty_institute or 0)
            ),
        },
    }


def edit_past_session(
    session_code: int,
    data: AttendanceSubmitData,
    db: Session = Depends(get_db),
    authorization: str | None = Header(None),
    sub_role: str = Depends(check_user_login)
):
    """بدنهٔ دامنه‌ایِ `edit_past_session`؛ توضیح HTTP در پوستهٔ روتر است."""
    # FIX: Bug 14 - exclude archived SessionLog rows from this active view.
    session = db.query(SessionLog).filter(SessionLog.is_deleted == False).filter(SessionLog.session_code == session_code).first()
    if not session:
        raise HTTPException(status_code=404, detail="جلسه یافت نشد")

    course = db.query(Course).filter(Course.id == session.course_id).first()
    if not course:
        raise HTTPException(404, "کلاس یافت نشد")
    # FIX (audit-v2/H-caller): همان گارد مالکیت ثبت جلسه — ویرایش هم reverse/recharge مالی دارد
    # پس تماس‌گیرنده‌ی ناشناس/نامالک قبل از هر تغییری 403 می‌گیرد (قدم ۴: مسیر مشروع بی‌تغییر).
    _verify_live_course_teacher(db, course, authorization, sub_role, action_label="جلسه‌ی این کلاس")
    # FIX H10: ویرایش جلسات کلاس معلق ممنوع (فریز یعنی فریز).
    if course.is_suspended:
        raise HTTPException(status_code=403, detail="این کلاس معلق است و امکان ویرایش جلسات آن وجود ندارد")

    # FIX: جلسه‌ی تسویه‌شده قابل ویرایش نیست — قبل از هر تغییری و قبل از اعتبارسنجی ورودی،
    # تا خطای قطعی 409 زودتر از خطای قابل‌اصلاح 422 برگردد (هم‌ترتیب با submit: اول 404، بعد 409، بعد 422).
    settled_exists = db.query(Attendance.id).filter(
        Attendance.session_id == session.id,
        Attendance.is_billed == True,
        Attendance.is_deleted == False,   # FIX (F-S2): ردیف آرشیوشده جلسه‌ی فعال را قفل نمی‌کند.
    ).first()
    # FIX H8-gap: جلسه‌ی تسویه‌شده از هر مسیر (حضور یا جریمه) قفل ویرایش است — وگرنه جلسه‌ی
    # تماماً-غایبِ تسویه‌شده (که ردیف billed ندارد) بعد از تسویه دست‌کاری و دوباره تسویه می‌شد.
    if settled_exists or session.is_penalty_settled:
        raise HTTPException(
            status_code=409,
            detail="این جلسه قبلاً با معلم تسویه شده و قابل ویرایش نیست؛ برای اصلاح، ابتدا با بخش مالی/تسویه هماهنگ کنید",
        )

    # FIX (audit-v2/#13): تاریخ کانونیکال شمسی — ولیدیت + نرمالایز با مبدل مرکزی H3 (قبلاً رشته‌ی خام
    # کلاینت ذخیره/مقایسه می‌شد: «2026/09/12» در برابر «1405/06/21» روز متفاوت حساب می‌شد → دابل‌سشن
    # و دابل‌شارژ cross-client). نامعتبر → 422. بعد از 403ها (عدم لو وضعیت به غیرمجاز) و قبل از چک تکراری.
    from today_summary import jalali_date_string, parse_project_date  # lazy، مثل finance
    _sday = parse_project_date(data.date)
    if _sday is None:
        raise HTTPException(status_code=422, detail="فرمت تاریخ جلسه معتبر نیست (yyyy/MM/dd شمسی یا میلادی)")
    data.date = jalali_date_string(_sday)
    # FIX H19-F1: پیش‌چک تداخل تاریخ (الگوی Bug-17 در submit) — قبل از reverse مخرب.
    # بدون این چک، data.date متداخل در کامیت #۲ به IntegrityError خام (500) می‌رسید.
    date_clash = db.query(SessionLog.id).filter(
        SessionLog.course_id == session.course_id,
        SessionLog.date == data.date,
        SessionLog.is_deleted == False,
        SessionLog.id != session.id,
    ).first()
    if date_clash:
        raise HTTPException(status_code=409, detail="جلسه این کلاس در این تاریخ قبلاً ثبت شده است")

    # FIX (F-S3): ویرایش هم نمی‌تواند جلسه را به «هیچ‌کس» تبدیل کند (هم‌سیاست با ثبت).
    if not data.items:
        raise HTTPException(
            status_code=422,
            detail="لیست حضور/غیاب نمی‌تواند خالی باشد؛ برای ثبت جلسه حداقل یک دانش‌آموز لازم است",
        )

    # FIX: H6(C1) - آیتم تکراری برای یک دانش‌آموز در همین ثبت ممنوع (قبل از reverse مخرب).
    seen_ids = set()
    for i in data.items:
        if i.student_id in seen_ids:
            raise HTTPException(status_code=422, detail=f"دانش‌آموز {i.student_id} بیش از یک‌بار در لیست حضور/غیاب تکرار شده است")
        seen_ids.add(i.student_id)

    # FIX: H6(B) - همه‌ی آیتم‌ها باید عضو فعال همین کلاس باشند (قبل از reverse مخرب).
    validate_session_items_membership(db, course.id, data.items)
    # FIX (F-S4): وضعیت نامعتبر قبل از reverse/شارژ رد شود.
    validate_session_item_statuses(data.items)

    # FIX H19-F2: پیش‌گشت شعبه (hoist چک H7 از داخل حلقه) — قبل از reverse مخرب.
    # شرط عین حلقه‌ی اصلی: فقط آیتم‌های «شاگرد موجود + باید شارژ شود» چک می‌شوند.
    for _bi in data.items:
        _exc = getattr(_bi, "excused", False) or False
        _should = _bi.status in ["Present", "Late"] or (_bi.status == "Absent" and course.rule_calc_absent and not _exc)
        if not _should:
            continue
        _bst = db.query(Student).filter(Student.id == _bi.student_id, Student.is_deleted == False).first()
        if _bst is None:
            continue
        _bbr = _bst.branch_id if _bst.branch_id is not None else course.branch_id
        if _bbr is None:
            raise HTTPException(status_code=400, detail="شعبه این دانش‌آموز یا کلاس مشخص نیست؛ امکان ثبت شارژ مالی نیست")

    # 1. شمارش حاضرین و غایبین غیرموجه مشمول جریمه
    present_students = [i for i in data.items if i.status in ["Present", "Late"]]
    present_count = len(present_students)
    absent_unexcused_count = sum(
        1 for i in data.items
        if i.status == "Absent" and course.rule_calc_absent and not (getattr(i, "excused", False) or False)
    )

    # FIX: H5/H6 - محاسبه‌ی یکتا از تابع مشترک (قدم ۱ و ۲)؛ قبل از reverse تا خطا، نیم‌کاره نماند.
    # FIX L2: seed چرخش = (کلاس، تاریخ) — هر جلسه آفست متفاوتی می‌گیرد.
    shares = compute_session_shares(db, course, present_count, absent_unexcused_count,
                                    rotation_seed=f"{course.id}:{data.date}")
    teacher_share_per_student = shares["teacher_share_per_student"]
    institute_share_per_student = shares["institute_share_per_student"]
    teacher_share_distribution = shares["teacher_share_distribution"]
    institute_share_distribution = shares["institute_share_distribution"]
    total_cost_per_student = shares["total_cost_per_student"]
    final_teacher_income = shares["T_total"]
    final_institute_income = shares["I_total"]
    if present_count <= 0:
        print("💡 تعداد حاضرین صفر است: هیچ هزینه‌ای کسر نمی‌شود.")

    # همه‌ی اعتبارسنجی‌ها و محاسبات پاس شد؛ حالا اثر مالی قبلی برگردانده می‌شود.
    from dependencies import reverse_session_financial_impacts
    # FIX (audit-v2/#14): تک‌تراکنش — reverse بدون کامیت داخلی (مثل delete)؛ تنها کامیت، نهاییِ پایین است.
    reverse_session_financial_impacts(session.id, db, commit=False)

    session.date = data.date
    session.final_teacher_cost = final_teacher_income
    session.final_institute_share = final_institute_income
    # FIX: H6(A2) - ریست جریمه (اثر قبلی reverse شد)؛ در حلقه‌ی پایین دوباره انباشته می‌شود.
    session.absent_penalty_teacher = 0
    session.absent_penalty_institute = 0
    session.cost_per_student = total_cost_per_student
    session.attendee_count = present_count
    # FIX H19-F1b: backstop مسابقه برای تداخل تاریخ (الگوی H6-C2 پایین) — پیش‌چک بالا
    # مسابقه‌ی دو ویرایش هم‌زمان را پوشش نمی‌دهد.
    # FIX (audit-v2/#14): این backstop حالا flush است نه commit — تشخیص تداخل سر جایش (flush همان UPDATE
    # را می‌فرستد و ایندکس یکتا همان‌جا می‌گیرد) ولی هیچ‌چیز persist نمی‌شود: rollback پایین همه‌چیز شامل
    # reverse را برمی‌گرداند (قبلاً reverse ایستاده بود — همان F3-deferred که حالا انجام شد).
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="جلسه این کلاس در این تاریخ قبلاً ثبت شده است")

    charge_index = 0
    for item in data.items:
        excused_val = getattr(item, "excused", False) or False

        # FIX: H6(B) - بدون دانش‌آموز معتبر، نه رکورد حضور ساخته می‌شود نه شارژ.
        st = db.query(Student).filter(Student.id == item.student_id, Student.is_deleted == False).first()
        if st is None:
            continue

        # FIX (F-S2): upsert — ردیف آرشیوشده‌ی همین (جلسه، دانش‌آموز) احیا می‌شود نه INSERT تازه.
        att = _upsert_attendance_row(db, session.id, item.student_id, item.status, excused_val)

        should_charge = False
        if item.status in ["Present", "Late"]:
            should_charge = True
        elif item.status == "Absent":
            if course.rule_calc_absent and not excused_val:
                should_charge = True

        if should_charge:
            curr_w_t = st.wallet_teacher if st.wallet_teacher is not None else 0
            curr_w_i = st.wallet_institute if st.wallet_institute is not None else 0

            if item.status in ["Present", "Late"]:
                inst_share_value = (
                    institute_share_distribution[charge_index]
                    if charge_index < len(institute_share_distribution)
                    else institute_share_per_student
                )
                teacher_share_value = (
                    teacher_share_distribution[charge_index]
                    if charge_index < len(teacher_share_distribution)
                    else teacher_share_per_student
                )
                charge_index += 1
            else:
                inst_share_value = institute_share_per_student
                teacher_share_value = teacher_share_per_student
                # FIX: H6(A2) - انباشت جریمه‌ی واقعی در ستون‌های جدا (نه داخل final_*).
                session.absent_penalty_teacher += teacher_share_value
                session.absent_penalty_institute += inst_share_value

            st.wallet_teacher = curr_w_t - teacher_share_value
            st.wallet_institute = curr_w_i - inst_share_value

            # FIX H7 (الگوی Bug 9): شارژ مالی دنبال شعبه‌ی شاگرد می‌رود، با fallback به شعبه‌ی کلاس.
            # مثل Bug 9، تراکنش مالی بدون شعبه ساخته نمی‌شود — این فقط backstop داخل حلقه است؛
            # محافظ اصلی پیش‌گشت H19-F2 است (قبل از reverse). توجه (#14): حالا تک‌تراکنش است — rollback زیر همه‌چیز شامل reverse را برمی‌گرداند (قبلاً کامیت #۱ ایستاده بود).
            charge_branch = st.branch_id if st.branch_id is not None else course.branch_id
            if charge_branch is None:
                db.rollback()
                raise HTTPException(status_code=400, detail="شعبه این دانش‌آموز یا کلاس مشخص نیست؛ امکان ثبت شارژ مالی نیست")

            # FIX: Bug 18 - derive the total only through the shared wallet helper.
            st.sync_wallet_balance()

            # NOTE: is_billed یعنی «تسویه با معلم» و فقط settle_teacher_sessions آن را True می‌کند؛
            # اینجا عمداً دست نمی‌خورد تا جلسه‌ی ویرایش‌شده هم مثل ثبت تازه، تسویه‌نشده بماند.
            db.add(
                Transaction(
                    student_id=item.student_id,
                    branch_id=charge_branch,  # FIX H7: شعبه‌ی شاگرد (fallback: کلاس) — الگوی Bug 9.
                    course_id=course.id,
                    session_id=session.id,
                    amount=-(teacher_share_value + inst_share_value),
                    payment_method="System",
                    date=data.date,
                    type="session_charge",
                    share_teacher=teacher_share_value,
                    share_institute=inst_share_value,
                    description=f"هزینه جلسه - {'حاضر' if item.status in ['Present', 'Late'] else 'غایب غیرموجه'} (معلم: {teacher_share_value}، آموزشگاه: {inst_share_value})",
                )
            )


    # FIX: H6(C2) - backstop یکتایی (session_id, student_id) در سطح دیتابیس.
    # FIX (audit-v2/#14): این حالا تنها کامیت تابع است (reverse با commit=False است و backstop بالا flush).
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="رکورد تکراری حضور/غیاب برای این جلسه ثبت شده است")
    return {
        "message": "جلسه با موفقیت اصلاح شد و مبالغ مالی مجدداً محاسبه شدند.",
        "session_id": session.id,
        "session_code": session.session_code,
        "details": {
            "present_count": present_count,
            "cost_per_student": total_cost_per_student,
            "teacher_share": final_teacher_income,
            "institute_share": final_institute_income,
            # FIX: H6(A2) - جریمه‌ی جدا + جمع واقعی جلسه.
            "absent_penalty_teacher": session.absent_penalty_teacher,
            "absent_penalty_institute": session.absent_penalty_institute,
            "total_session_cost": (
                (final_teacher_income or 0) + (final_institute_income or 0)
                + (session.absent_penalty_teacher or 0) + (session.absent_penalty_institute or 0)
            ),
        },
    }
