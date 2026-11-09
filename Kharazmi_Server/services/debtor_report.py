"""لایهٔ service — گزارش بدهکاران (REFAC P3a).

چرا این ماژول: این خوشه «منبع یگانهٔ ردیف بدهکار» است (ساخت لیست، نمای گروه‌بندی‌شده،
پیامک دسته‌جمعی و خروجی CSV/Excel همه از `build_debtor_rows` استفاده می‌کنند تا عددها
واگرا نشوند). منطق خالصِ گزارش‌سازی است، نه لایهٔ HTTP؛ ولی وسط `routers/finance.py`
تعریف شده بود و `routers/exports.py` و `routers/reports.py` مجبور بودند آن را **lazy از
روترِ مالی** import کنند (`from routers.finance import build_debtor_rows  # lazy: بدون
چرخهٔ import`). حالا که در لایهٔ service است، آن وابستگیِ روتر→روتر از بین رفته و
مصرف‌کننده‌ها مستقیم import می‌کنند.

کد **بایت‌به‌بایت** منتقل شده؛ `DEBT_AGE_BUCKETS` (دسته‌های قدمت بدهی) هم همراهش آمده
چون فقط همین خوشه مصرفش می‌کند. `routers/finance.py` خودش `build_debtor_rows` و
`DEBT_AGE_BUCKETS` را مصرف می‌کند، پس مسیر import قبلی هم دست‌نخورده کار می‌کند.
"""

import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

import models
from dependencies import display_name
from financial_calculations import calculate_student_debt
from models import Course, Enrollment, Student, Teacher

# --- ۱۴. گزارش جامع بدهکاران (Debt Report - ادمین و منشی) ---
# FIX (گروه۲/آیتم ۶ و ۹): هلپر مشترک «ردیف بدهکار» — یک منطق برای لیست، نمای گروه‌بندی‌شده،
# پیامک دسته‌جمعی و خروجی‌ها (CSV/Excel) تا عددها واگرا نشوند.
DEBT_AGE_BUCKETS = (("0-7", 0, 7), ("8-30", 8, 30), ("over_30", 31, None))


def _debtor_last_payment(db: Session, student_id: int):
    """(تاریخ خام آخرین پرداخت، تاریخ پارس‌شده) — فقط پولِ ورودیِ واقعیِ همین دانش‌آموز.

    انواع مجاز همان تعریف یگانهٔ وصولی نقدی است (`INSTITUTE_CASH_TYPES` + ردیف legacy بی‌type)
    و واریزی به کیف معلم/شارژ جلسه/برگشت‌خورده/حذف‌شده «پرداخت» حساب نمی‌شود.
    """
    from financial_calculations import INSTITUTE_CASH_TYPES  # lazy، الگوی پروژه
    from today_summary import parse_project_date
    rows = (
        db.query(models.Transaction.date)
        .filter(
            models.Transaction.student_id == student_id,
            models.Transaction.amount > 0,
            models.Transaction.is_deleted == False,
            models.Transaction.is_reversed == False,
            or_(models.Transaction.type.in_(INSTITUTE_CASH_TYPES),
                models.Transaction.type.is_(None)),
        )
        .all()
    )
    dated = [(raw, parse_project_date(raw)) for raw, in rows]
    dated = [(raw, parsed) for raw, parsed in dated if parsed is not None]
    if not dated:
        return "", None
    dated.sort(key=lambda pair: (pair[1], pair[0]), reverse=True)
    return dated[0][0] or "", dated[0][1]


def _debtor_age_bucket(last_payment_day, today: datetime.date):
    """دستهٔ قدمت بدهی: از آخرین پرداخت تا امروز؛ بی‌پرداخت ⇒ `no_payment`."""
    if last_payment_day is None:
        return "no_payment", None
    age = (today - last_payment_day).days
    if age < 0:
        age = 0
    for name, low, high in DEBT_AGE_BUCKETS:
        if high is None or age <= high:
            if age >= low:
                return name, age
    return "over_30", age


def _debtor_teacher_rows(db: Session, student_id: int, wallet_teacher_debt: int = 0):
    """(teacher_id, teacher_name, course_title, بدهیِ همان enrollment).

    این نمای per-class فقط بدهیِ enrollment را نشان می‌دهد. بدهی legacy که
    `calculate_student_debt` از wallet کلی دانش‌آموز می‌گیرد، در `unassigned_debt`
    باقی می‌ماند؛ حتی اگر دانش‌آموز فقط یک کلاس فعال داشته باشد. نسبت‌دادن wallet
    کلی به تنها کلاس هم همچنان نسبت‌دادن نادرست بین کلاس‌هاست.
    """
    from financial_calculations import calculate_enrollment_debt_breakdown  # lazy، الگوی پروژه
    enrollments = (
        db.query(Enrollment)
        .filter(Enrollment.student_id == student_id, Enrollment.is_deleted == False)
        .all()
    )
    rows = []
    for en in enrollments:
        course = db.query(Course).filter(Course.id == en.course_id).first()
        if course is None:
            continue
        teacher = db.query(Teacher).filter(Teacher.id == course.teacher_id).first()
        breakdown = calculate_enrollment_debt_breakdown(db, en)
        rows.append({
            "teacher_id": course.teacher_id,
            "teacher_name": display_name(teacher, "نامشخص") if teacher else "بدون معلم",
            "course_id": course.id,
            "course_title": course.title or "کلاس بدون نام",
            "debt": breakdown["debt"],
            "debt_teacher": breakdown["debt_teacher"],
            "debt_institute": breakdown["debt_institute"],
            "enrollment_id": en.id,
            "is_unassigned": False,
        })
    # A legacy wallet balance has no enrollment scope. Keep its remainder as an
    # explicit row instead of assigning it to an arbitrary active class.
    student = db.query(Student).filter(Student.id == student_id).first()
    if student is not None:
        total_debt = calculate_student_debt(db, student)
        assigned = sum(int(row["debt"] or 0) for row in rows)
        unassigned = max(0, int(total_debt) - assigned)
        # ``unassigned`` is contractual/tuition debt that has no enrollment
        # owner. Wallet debt is reported in its own top-level fields and must
        # not be smuggled into this row's teacher/institute class split.
        if unassigned:
            rows.append({
                "teacher_id": None,
                "teacher_name": None,
                "course_id": None,
                "course_title": None,
                "debt": unassigned,
                "debt_teacher": 0,
                "debt_institute": unassigned,
                "enrollment_id": None,
                "is_unassigned": True,
            })
    return rows


def build_debtor_rows(db: Session, resolved_branch: int | None, search: str | None = None):
    """فهرست بدهکاران با فیلدهای کامل — منبع یگانهٔ لیست/گروه‌بندی/پیامک/خروجی.

    FIX (گروه۲/آیتم۶): `branch_scope_clause` به‌جای فیلتر سختِ شعبه؛ در دادهٔ واقعی آموزشگاه
    `students.branch_id` برای ردیف‌های legacy NULL است و ادمینِ شعبه‌دار `branch_id=1` دارد ⇒
    `NULL == 1` هرگز درست نیست و **خروجی بدهکاران با وجود داده خالی می‌شد**.
    سیاست: ردیف بی‌شعبه = سراسری/legacy (دیده می‌شود) · ردیف شعبهٔ دیگر = پنهان (بدون نشت).
    """
    from financial_calculations import branch_scope_clause  # lazy، الگوی پروژه
    from today_summary import parse_project_date
    today = datetime.datetime.now().date()

    query = db.query(Student).filter(Student.is_deleted == False)
    scope = branch_scope_clause(Student.branch_id, resolved_branch)
    if scope is not None:
        query = query.filter(scope)
    students = query.order_by(Student.id).all()

    needle = (search or "").strip().lower()
    result = []
    for s in students:
        w_t = s.wallet_teacher if s.wallet_teacher is not None else 0
        w_i = s.wallet_institute if s.wallet_institute is not None else 0
        # FIX: Bug 16 - include only positive outstanding tuition (or legacy unpriced debt).
        total_debt = calculate_student_debt(db, s)
        if total_debt <= 0:
            continue

        enrollments = db.query(Enrollment).filter(
            Enrollment.is_deleted == False,
            Enrollment.student_id == s.id).all()
        courses = [e.course.title for e in enrollments if e.course]

        student_name = display_name(s, "نامشخص")
        teacher_rows = _debtor_teacher_rows(db, s.id, abs(w_t) if w_t < 0 else 0)
        teacher_names = sorted({r["teacher_name"] for r in teacher_rows if r.get("teacher_name")})
        if needle:
            haystack = " ".join([student_name, *teacher_names, *(c or "" for c in courses)]).lower()
            if needle not in haystack:
                continue

        last_payment_raw, last_payment_day = _debtor_last_payment(db, s.id)
        bucket, age_days = _debtor_age_bucket(last_payment_day, today)
        # Category totals are the sum of explicit enrollment rows. The global
        # wallet is used only for the explicit unassigned row above.
        class_debt_teacher = sum(int(row.get("debt_teacher") or 0) for row in teacher_rows)
        class_debt_institute = sum(int(row.get("debt_institute") or 0) for row in teacher_rows)
        result.append({
            "student_id": s.id,
            "student_name": student_name,
            "national_code": s.national_code,
            "parent_mobile": s.parent_mobile,
            "student_mobile": s.student_mobile,
            "contact_mobile": s.parent_mobile or s.student_mobile or "",
            "debt_teacher": class_debt_teacher,
            "debt_institute": class_debt_institute,
            # Legacy wallet debt is deliberately exposed under separate names;
            # it is never merged into a class/enrollment row.
            "wallet_debt_teacher": max(0, -w_t),
            "wallet_debt_institute": max(0, -w_i),
            "total_debt": total_debt,
            "active_courses": courses,
            # FIX (گروه۲/آیتم۹): فیلدهای خواسته‌شده — تاریخ آخرین پرداخت، شماره تماس،
            # قدمت بدهی (برای اولویت پیگیری) و تفکیک «بدهی به کدام معلم».
            "last_payment_date": last_payment_raw if parse_project_date(last_payment_raw) is not None else "",
            "debt_age_days": age_days,
            "debt_age_bucket": bucket,
            "teachers": teacher_rows,
        })
    result.sort(key=lambda row: row["total_debt"], reverse=True)
    return result
