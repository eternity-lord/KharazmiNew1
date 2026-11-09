
from fastapi import Depends, Header, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from dependencies import check_student_access, check_user_login, get_db
from financial_calculations import (
    calculate_enrollment_debt_breakdown,
    calculate_student_debt,
    session_fields_for_client,
)
from models import Student, Teacher, Transaction

"""لایهٔ سرویسِ «پروفایل کامل دانش‌آموز».

بدنهٔ دامنه‌ایِ `GET /admin/students/{id}/full_profile`: جمع‌آوری کلاس‌ها،
ماندهٔ حساب، قسط‌ها، تراکنش‌ها و خلاصهٔ حضور/غیاب یک دانش‌آموز در یک پاسخ.

قرارداد لایه در `services/__init__.py`: بدون route و بدون APIRouter؛ بدنه‌ها
بایت‌به‌بایت از روتر منتقل شده‌اند و handlerها در روتر به‌صورت پوستهٔ HTTP باقی
مانده‌اند (چون تست‌ها آن‌ها را مستقیم صدا می‌زنند).
"""


def get_student_full_profile(id: int, authorization: str | None = Header(None), db: Session = Depends(get_db), role: str = Depends(check_user_login)):
    """بدنهٔ دامنه‌ایِ `get_student_full_profile`؛ توضیح HTTP در پوستهٔ روتر است."""
    # FIX (L14/Y1): بازنویسی کامل تله‌ی گارد نصفه (مشابه students.py:414) — شاگرد/ولیِ غریبه دیگر رد نمی‌شوند.
    check_student_access(id, authorization, db, role)

    st = db.query(Student).filter(Student.id == id, Student.is_deleted == False).first()
    if not st:
        raise HTTPException(404, "دانش‌آموز یافت نشد")

    # لیست کلاس‌ها
    classes = []
    for en in st.enrollments:
        # FIX: Bug 13 - cancelled enrollment history is not an active class.
        if en.course and not en.is_deleted:
            classes.append(f"{en.course.title} (کد: {en.course.code})")

    # FIX(invoice): enrollmentهای فعال با شناسه‌های واقعی — کلاینت (صدور فیش) enrollment درست را
    # انتخاب/می‌فرستد؛ دیگر حدس از روی نام نمایشی کلاس لازم نیست و backend مجبور به حدس‌زدن
    # برای دانش‌آموز چندکلاسه نمی‌شود (400 «چند ثبت‌نام فعال» فقط واقعاً مبهم می‌ماند).
    enrollments_list = []
    for en in st.enrollments:
        if en.is_deleted or en.course is None:
            continue
        course = en.course
        teacher = db.query(Teacher).filter(Teacher.id == course.teacher_id).first()
        teacher_name = f"{teacher.first_name} {teacher.last_name}" if teacher else "بدون معلم"
        breakdown = calculate_enrollment_debt_breakdown(db, en)
        enrollments_list.append({
            "enrollment_id": en.id,
            "course_id": en.course_id,
            "title": course.title or "",
            "course_title": course.title,
            "code": course.code or "",
            "branch_id": en.branch_id,
            "teacher_id": course.teacher_id,
            "teacher_name": teacher_name,
            "debt": int(breakdown["debt"]),
            "debt_teacher": int(breakdown["debt_teacher"]),
            "debt_institute": int(breakdown["debt_institute"]),
            "total_debt": int(breakdown["debt"]),
            "is_unassigned": False,
            # «این مبلغ برای چند جلسهٔ همین کلاس است؟» — افزوده و سازگار با عقب؛ سرور قدیمی این کلیدها را ندارد
            # و اپ از نبودشان می‌فهمد سرور به‌روز نیست.
            **session_fields_for_client(breakdown),
        })

    # لیست تراکنش‌ها
    trans = (
        # FIX: Bug 12 - exclude archived Transaction rows from this active view.
        db.query(Transaction).filter(Transaction.is_deleted == False, Transaction.is_reversed == False)
        .filter(Transaction.student_id == id)
        .order_by(desc(Transaction.id))
        .limit(5)
        .all()
    )
    trans_list = [f"{t.date}: {t.amount:,} ({t.description})" for t in trans]

    # محاسبه دقیق بدهی‌ها از دیتابیس
    w_t = st.wallet_teacher if st.wallet_teacher is not None else 0
    w_i = st.wallet_institute if st.wallet_institute is not None else 0

    # اگر منفی باشد یعنی بدهکار است (برای نمایش مثبتش میکنیم)
    debt_t = abs(w_t) if w_t < 0 else 0
    debt_i = abs(w_i) if w_i < 0 else 0
    # FIX: Bug 16 - expose the tuition-based total while retaining separate wallet balances.
    total_d = calculate_student_debt(db, st)
    wallet_total = w_t + w_i

    # محاسبات تفکیک شده مالی به ازای مربیان و آموزشگاه
    teachers_financial = []
    class_debt_total = 0
    # calculate_student_debt: اگر هیچ ثبت‌نام فعالِ قیمت‌دار نباشد، بدهی از کیف پول (شارژ جلسه‌ها) می‌آید.
    session_based_total = not any(
        (en.total_tuition or 0) > 0
        for en in st.enrollments
        if not en.is_deleted
    )
    for en in st.enrollments:
        # FIX: Bug 13 - do not include archived enrollments in financial class balances.
        if en.is_deleted or not en.course:
            continue
        course = en.course
        teacher = db.query(Teacher).filter(Teacher.id == course.teacher_id).first()
        teacher_name = f"{teacher.first_name} {teacher.last_name}" if teacher else "بدون معلم"

        # breakdown به enrollment متصل است؛ کیف کلی دانش‌آموز و پرداخت عمومی
        # در بدهی این کلاس وارد نمی‌شوند. سهم پرداخت‌های target_wallet=both نیز
        # داخل helper با share_teacher/share_institute تفکیک می‌شود.
        breakdown = calculate_enrollment_debt_breakdown(db, en)
        paid_teacher = breakdown["paid_teacher"]
        paid_inst = breakdown["paid_institute"]
        debt_teacher_course = breakdown["debt_teacher"]
        debt_inst_course = breakdown["debt_institute"]
        # مبنای «بدهی کلاسی» با مبنای total_d یکی است: دانش‌آموزِ دارای شهریه‌ی قراردادی → بدهی شهریه؛
        # بدون شهریه (فقط شارژ جلسه) → بدهی جلسه‌ها (سهم معلم + آموزشگاه). قبلاً حالت دوم صفر
        # حساب می‌شد و کل شارژ جلسهٔ کلاس‌ها به‌غلط زیر «بدهی بدون کلاس» دوباره نمایش داده می‌شد.
        if session_based_total:
            class_debt_total += int(debt_teacher_course) + int(debt_inst_course)
        else:
            class_debt_total += int(breakdown["debt"])

        teachers_financial.append({
            "enrollment_id": en.id,
            "course_id": course.id,
            "course_title": course.title,
            "course_code": course.code or "",
            "teacher_id": course.teacher_id,
            "teacher_name": teacher_name,
            "paid_teacher": int(paid_teacher),
            "debt_teacher": int(debt_teacher_course),
            "paid_institute": int(paid_inst),
            "debt_institute": int(debt_inst_course),
            "debt": int(breakdown["debt"]),
            "is_unassigned": False,
            **session_fields_for_client(breakdown),
        })

    # Legacy wallet debt has no class scope. Keep it visible as a separate row rather
    # than leaking it into any enrollment (course_title is intentionally null).
    unassigned_debt = max(0, int(total_d) - class_debt_total)
    if unassigned_debt:
        teachers_financial.append({
            "enrollment_id": None,
            "course_id": None,
            "course_title": None,
            "teacher_id": None,
            "teacher_name": None,
            "paid_teacher": 0,
            "debt_teacher": 0,
            "paid_institute": 0,
            "debt_institute": int(unassigned_debt),
            "debt": int(unassigned_debt),
            "is_unassigned": True,
        })

    # مجموع کل پرداخت دانش‌آموز به آموزشگاه (همه کلاس‌ها). سهم institute از
    # رسیدهای both نیز باید در این جمع کلی دیده شود؛ breakdown هر کلاس بالاتر
    # همین تفکیک را با scope enrollment انجام می‌دهد.
    overall_payments = db.query(Transaction).filter(
        Transaction.student_id == id,
        Transaction.amount > 0,
        Transaction.is_deleted == False,
        Transaction.is_reversed == False,
    ).all()
    total_paid_institute_overall = 0
    for payment in overall_payments:
        if payment.target_wallet == "institute":
            total_paid_institute_overall += int(payment.amount or 0)
        elif payment.target_wallet == "both":
            amount = int(payment.amount or 0)
            share_teacher = int(payment.share_teacher or 0)
            share_institute = int(payment.share_institute or 0)
            if share_teacher + share_institute != amount:
                share_institute = amount - amount // 2
            total_paid_institute_overall += share_institute

    return {
        "info": {
            "name": f"{st.first_name} {st.last_name}",
            "national_code": st.national_code,
            "student_mobile": st.student_mobile,
            "parent_mobile": st.parent_mobile,
            "address": st.address if st.address else "---",
            "is_suspended": st.is_suspended if st.is_suspended else False,
            "profile_image": st.profile_image,
            "student_code": st.student_code,
        },
        "classes": classes,
        # FIX(invoice): شناسه‌های واقعی enrollmentهای فعال (سازگار با عقب: کلاینت‌های قدیمی این کلید را نمی‌خوانند)
        "enrollments": enrollments_list,
        "transactions": trans_list,
        "total_debt": total_d,
        "debt_teacher": debt_t,  # ✅ مقدار واقعی از دیتابیس
        "debt_institute": debt_i,  # ✅ مقدار واقعی از دیتابیس
        "wallet_teacher": w_t,
        "wallet_institute": w_i,
        "wallet_total": wallet_total,
        "total_paid_institute": int(total_paid_institute_overall),
        "unassigned_debt": int(unassigned_debt),
        "teachers_financial": teachers_financial,
    }
