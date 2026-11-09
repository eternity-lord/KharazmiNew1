"""لایهٔ سرویسِ «نماهای فقط‌خواندنیِ مالی».

دو endpoint که پیش‌تر وسط `routers/finance.py` بودند:
  * `GET /finance/search_advanced` — جست‌وجوی مالی با دامنهٔ دسترسی بر اساس نقش
    (کارکنان کامل؛ معلم فقط کلاس‌ها/شاگردانِ خودش؛ شاگرد/ولی ۴۰۳) و branch isolation.
  * `GET /finance/student/{student_id}/dashboard` — داشبورد تراز مالی یک دانش‌آموز
    (کیف‌ها، بدهی، قسط‌ها) با گارد IDOR.

چرا جدا از `services/payments.py`: آن ماژول مسیرِ **نوشتن** و جابه‌جایی پول است
(کال‌بک درگاه، ثبت پرداخت، بازگشت رسید)؛ این ماژول مسیرِ **خواندن** و گزارش.

قرارداد لایه در `services/__init__.py`: بدون route و بدون APIRouter؛ بدنه‌ها
بایت‌به‌بایت منتقل شده‌اند و handlerها در روتر پوستهٔ HTTP مانده‌اند (امضا قراردادِ
OpenAPI است و تست‌ها این توابع را مستقیم صدا می‌زنند).
"""
import datetime

from fastapi import Depends, Header, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from dependencies import (
    check_student_access,
    check_user_login,
    display_name,
    get_db,
    get_enrollment_tuition_and_discount,
    get_logged_in_teacher,
)
from financial_calculations import (
    calculate_enrollment_debt_breakdown,
    calculate_student_debt,
    session_fields_for_client,
)
from models import Course, Enrollment, Installment, Student, Teacher, Transaction
from schemas import AdvancedSearchItem
from services.branch_scope import get_user_branch_filter


def search_finance_advanced(
    query: str,
    branch_id: int | None = None,
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
    sub_role: str = Depends(check_user_login)
):
    """بدنهٔ دامنه‌ایِ `search_finance_advanced`؛ توضیحِ HTTP در پوستهٔ روتر است."""
    # FIX (L14/Y4): سرچ مالی — کارکنان کامل؛ معلم فقط کلاس‌ها/شاگردان خودش (صدور فاکتور)؛ شاگرد/ولی 403.
    if sub_role not in ("admin", "secretary", "teacher"):
        raise HTTPException(status_code=403, detail="شما دسترسی لازم برای جستجوی مالی را ندارید")
    _own_course_ids = _own_student_ids = None
    if sub_role == "teacher":
        _me = get_logged_in_teacher(db, authorization)
        if not _me:
            raise HTTPException(status_code=403, detail="شما دسترسی لازم برای جستجوی مالی را ندارید")
        _own_course_ids = [r[0] for r in db.query(Course.id).filter(Course.teacher_id == _me.id).all()]
        _own_student_ids = [r[0] for r in db.query(Enrollment.student_id).filter(Enrollment.course_id.in_(_own_course_ids), Enrollment.is_deleted == False).distinct().all()]
    resolved_branch = get_user_branch_filter(db, authorization, branch_id)
    results = []
    search = f"%{query}%"

    # الف) جستجو در کلاس‌ها
    courses_q = db.query(Course).filter(or_(Course.title.ilike(search), Course.code.ilike(search)))
    if _own_course_ids is not None:
        courses_q = courses_q.filter(Course.id.in_(_own_course_ids))
    if resolved_branch is not None:
        courses_q = courses_q.filter(Course.branch_id == resolved_branch)
    courses = courses_q.all()
    for c in courses:
        teacher = db.query(Teacher).filter(Teacher.id == c.teacher_id).first()
        t_name = display_name(teacher, "نامشخص") if teacher else "بدون معلم"

        # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
        enrollments = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.course_id == c.id).all()
        class_students = []
        for en in enrollments:
            st = db.query(Student).filter(Student.id == en.student_id, Student.is_deleted == False).first()
            if st:
                # این ردیف نمای یک enrollment داخل کلاس است؛ walletهای Student
                # سراسری‌اند و نباید بدهی کلاس دیگری را به این ردیف کپی کنند.
                breakdown = calculate_enrollment_debt_breakdown(db, en)
                class_students.append(
                    {
                        "id": st.id,
                        "name": display_name(st, "نامشخص"),
                        "debt": breakdown["debt"],
                        "total_debt": breakdown["debt"],
                        "debt_teacher": breakdown["debt_teacher"],
                        "debt_institute": breakdown["debt_institute"],
                        "enrollment_id": en.id,
                        "course_id": c.id,
                        "course_title": c.title,
                        "course_code": c.code or "",
                        "teacher_id": c.teacher_id,
                        "teacher_name": t_name,
                        "is_unassigned": False,
                        **session_fields_for_client(breakdown),
                    }
                )

        results.append(
            AdvancedSearchItem(
                type="class",
                id=c.id,
                title=f"کلاس: {c.title}",
                subtitle=f"مدرس: {t_name}",
                info=f"{len(class_students)} دانش‌آموز",
                students_in_class=class_students,
            )
        )

    # ب) جستجو در دانش‌آموزان (اصلاح حیاتی برای نمایش بدهی)
    students_q = db.query(Student).filter(Student.is_deleted == False).filter(
        or_(
            Student.first_name.ilike(search),
            Student.last_name.ilike(search),
            Student.national_code.ilike(search),
        )
    )
    if _own_student_ids is not None:
        students_q = students_q.filter(Student.id.in_(_own_student_ids))
    if resolved_branch is not None:
        students_q = students_q.filter(Student.branch_id == resolved_branch)
    students = students_q.all()

    for s in students:
        # نتیجهٔ دانش‌آموز چندکلاسه هنوز به یک کلاس مشخص وصل نیست؛ پس بدهی
        # wallet کل نباید در ردیف جستجو به‌عنوان بدهی کلاس نمایش داده شود.
        # نمایش بدهی فقط بعد از انتخاب enrollment واقعی انجام می‌شود؛ اینجا دیگر
        # wallet کل یا «بدهی کل» به‌عنوان بدهی کلاس نمایش داده نمی‌شود.
        enrollments = db.query(Enrollment).filter(
            Enrollment.is_deleted == False,
            Enrollment.student_id == s.id,
        ).all()
        class_count = len([en for en in enrollments if en.course is not None])
        results.append(
            AdvancedSearchItem(
                type="student",
                id=s.id,
                title=display_name(s, "نامشخص"),
                subtitle=f"{class_count} کلاس ثبت‌نام‌شده — برای مشاهده بدهی، کلاس را انتخاب کنید",
                info="بدهی پس از انتخاب کلاس نمایش داده می‌شود",
                student_id=s.id,
                debt_teacher=0,
                debt_institute=0,
                # This is an aggregate search hint only; the client must not
                # attribute it to a class until it selects an enrollment.
                total_debt=calculate_student_debt(db, s),
                unpaid_sessions=0,
            )
        )

    return results


def get_student_financial_dashboard(
    student_id: int,
    db: Session = Depends(get_db),
    authorization: str | None = Header(None),
    _role: str = Depends(check_user_login)
):
    """بدنهٔ دامنه‌ایِ `get_student_financial_dashboard`؛ توضیحِ HTTP در پوستهٔ روتر است."""
    # FIX (F3): مثل invoice — check_student_access؛ معلمِ درگیر محق است (بدون PII اضافه).
    check_student_access(student_id, authorization, db, _role)

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="دانش‌آموز یافت نشد")

    w_t = student.wallet_teacher if student.wallet_teacher is not None else 0
    w_i = student.wallet_institute if student.wallet_institute is not None else 0
    total_balance = w_t + w_i
    # FIX: Bug 16 - keep wallet credit separate from unpaid enrollment tuition.
    total_debt = calculate_student_debt(db, student)

    # دریافت سوابق ثبت‌نام‌ها و مبالغ شهریه
    # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
    enrollments = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.student_id == student_id).all()
    # کیف پول واحد شاگرد: جمع پرداخت‌های enrollmentهای فعال؛ هر ردیف
    # پایین‌تر با breakdown همان enrollment ساخته می‌شود.
    enroll_list = []
    total_paid_all = 0
    for en in enrollments:
        final_tuition, discount = get_enrollment_tuition_and_discount(en)
        breakdown = calculate_enrollment_debt_breakdown(db, en)
        c_title = en.course.title if en.course else "کلاس حذف شده"
        class_teacher = en.course.teacher if en.course else None
        class_teacher_name = display_name(class_teacher, "نامشخص") if class_teacher else None
        paid_for_class = breakdown["paid_teacher"] + breakdown["paid_institute"]
        total_paid_all += paid_for_class

        enroll_list.append({
            "enrollment_id": en.id,
            "course_id": en.course_id,
            "course_title": c_title,
            "teacher_id": en.course.teacher_id if en.course else None,
            "teacher_name": class_teacher_name,
            "is_unassigned": False,
            "total_tuition": en.total_tuition,
            "discount": discount,
            "final_tuition": final_tuition,
            "total_paid": paid_for_class,
            "outstanding": breakdown["debt"]
        })

    # لیست اقساط
    enrollment_ids = [e.id for e in enrollments]
    installments_list = []
    if enrollment_ids:
        # FIX: Bug 13 - exclude archived Installment rows from this active view.
        insts = db.query(Installment).filter(Installment.is_deleted == False).filter(Installment.enrollment_id.in_(enrollment_ids)).order_by(Installment.due_date.asc()).all()
        for i in insts:
            # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
            enroll = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.id == i.enrollment_id).first()
            course = db.query(Course).filter(Course.id == enroll.course_id).first() if enroll else None
            c_title = course.title if course else "کلاس حذف شده"

            from today_summary import (
                parse_project_date,  # FIX H3-B3: same B1 pattern — due_date is Jalali (lazy import)
            )
            today_date = datetime.datetime.now().date()
            _due = parse_project_date(i.due_date)
            status_text = "پرداخت شده" if i.is_paid else ("معوقه" if (_due is not None and _due < today_date) else "در انتظار")

            installments_list.append({
                "id": i.id,
                "course_title": c_title,
                "amount": i.amount,
                "due_date": i.due_date,
                "is_paid": i.is_paid,
                "status": status_text,
                "paid_at": i.paid_at or "---"
            })

    # ۳ تراکنش اخیر
    recent_transactions = (
        # FIX: Bug 12 - exclude archived Transaction rows from this active view.
        db.query(Transaction).filter(Transaction.is_reversed == False)
        .filter(Transaction.student_id == student_id, Transaction.is_deleted == False)
        .order_by(Transaction.id.desc())
        .limit(3)
        .all()
    )

    return {
        "wallet": {
            "balance": total_balance,
            "wallet_teacher": w_t,
            "wallet_institute": w_i,
            "total_paid": total_paid_all,
            "total_debt": total_debt
        },
        "enrollments": enroll_list,
        "installments": installments_list,
        "recent_transactions": [
            {
                "id": t.id,
                "amount": t.amount,
                "date": t.date,
                "description": t.description,
                "type": t.type,
                "target_wallet": t.target_wallet
            }
            for t in recent_transactions
        ]
    }
