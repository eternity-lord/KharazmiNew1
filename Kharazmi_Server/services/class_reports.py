
from fastapi import Depends, Header, HTTPException
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from dependencies import (
    check_admin_or_secretary_access,
    check_user_login,
    display_name,
    get_db,
    get_logged_in_teacher,
)
from financial_calculations import calculate_enrollment_debt_breakdown
from models import Attendance, Course, Enrollment, SessionLog, Student, Teacher
from schemas import ClassReportInfo, ClassSessionHistory, ClassSessionStudent, ClassStudentData, FullClassReport

"""لایهٔ سرویسِ «گزارش‌های کلاس».

شامل: فهرست کلاس‌ها با فیلتر/جست‌وجو/صفحه‌بندی (`GET /classes/list`) و گزارش
کامل یک کلاس (`GET /classes/{id}/full_report`) با ماندهٔ حساب و وضعیت هر دانش‌آموز.

قرارداد لایه در `services/__init__.py`: بدون route و بدون APIRouter؛ بدنه‌ها
بایت‌به‌بایت از `routers/classes.py` منتقل شده‌اند و handlerها در روتر پوستهٔ
HTTP باقی مانده‌اند (تست‌ها `get_all_classes` / `get_class_full_report` را مستقیم
import و صدا می‌زنند).
"""


def get_all_classes(
    teacher_name: str | None = None,
    student_name: str | None = None,
    course_name: str | None = None,
    grade_level: str | None = None,
    start_year: str | None = None,
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_or_secretary_access)  # FIX (L14/Y3): کاتالوگ+بدهی کلاس‌ها — فقط کارکنان (تک‌مصرف: ClassManagement)
):
    """بدنهٔ دامنه‌ایِ `get_all_classes`؛ توضیح HTTP در پوستهٔ روتر است."""
    # پایش فیلترهای چندگانه جستجو (Multi-part advanced search)
    q = db.query(Course).filter(Course.is_deleted == False)

    if teacher_name:
        search_t = f"%{teacher_name}%"
        q = q.join(Teacher).filter(
            or_(
                Teacher.first_name.ilike(search_t),
                Teacher.last_name.ilike(search_t)
            )
        )

    if student_name:
        search_s = f"%{student_name}%"
        # FIX: Bug 13 - class search must not treat archived enrollments as current membership.
        q = q.join(Enrollment).join(Student).filter(
            Enrollment.is_deleted == False,
            or_(
                Student.first_name.ilike(search_s),
                Student.last_name.ilike(search_s)
            )
        )

    if course_name:
        q = q.filter(Course.title.ilike(f"%{course_name}%"))

    if grade_level:
        q = q.filter(Course.grade_level.ilike(f"%{grade_level}%"))

    if start_year:
        # FIX: Bug 13 - year-based searches use active enrollments too.
        q = q.join(Enrollment).filter(Enrollment.is_deleted == False, Enrollment.register_date.like(f"{start_year}%"))

    courses = q.order_by(desc(Course.id)).all()
    result = []

    for c in courses:
        # 1. Get Teacher Name
        teacher = db.query(Teacher).filter(Teacher.id == c.teacher_id).first()
        t_name = display_name(teacher, "نامشخص")

        # 2. Get Top 10 Students for Preview (Updated from 3 to 10)
        enrollments = (
            # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
            db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.course_id == c.id).limit(10).all()
        )
        student_names = []
        for en in enrollments:
            st = db.query(Student).filter(Student.id == en.student_id, Student.is_deleted == False).first()
            if st:
                student_names.append(display_name(st, "نامشخص"))

        # 3. Calculate debt for the class
        total_debt = 0
        debt_to_teacher = 0
        debt_to_institute = 0
        total_paid = 0
        paid_to_teacher = 0
        paid_to_institute = 0
        # فقط اطلاع‌رسانی برای بنر: «بدهی بابت چند جلسهٔ همین کلاس» (روی هیچ محاسبهٔ مالی اثر ندارد).
        unpaid_sessions_total = 0
        sessions_billed_total = 0

        # Get all students in this class
        all_enrollments = (
            # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
            db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.course_id == c.id).all()
        )

        print(f"\n=== کلاس {c.id} - {c.title} ===")
        print(f"تعداد دانش‌آموزان: {len(all_enrollments)}")

        for en in all_enrollments:
            st = db.query(Student).filter(Student.id == en.student_id, Student.is_deleted == False).first()
            if st:
                # کیف‌های Student سراسری‌اند؛ برای بنر کلاس فقط breakdown همین enrollment
                # مجاز است. کیف کل فقط در لاگ تشخیصی حفظ می‌شود و در اعداد کلاس وارد نمی‌شود.
                breakdown = calculate_enrollment_debt_breakdown(db, en)
                student_debt_teacher = breakdown["debt_teacher"]
                student_debt_institute = breakdown["debt_institute"]
                student_paid_teacher = breakdown["paid_teacher"]
                student_paid_institute = breakdown["paid_institute"]

                print(
                    f"  دانش‌آموز {st.id}: class_paid_teacher={student_paid_teacher}, "
                    f"class_paid_institute={student_paid_institute}"
                )
                print(
                    f"    بدهی همین کلاس به معلم: {student_debt_teacher}, "
                    f"به آموزشگاه: {student_debt_institute}"
                )

                debt_to_teacher += student_debt_teacher
                debt_to_institute += student_debt_institute
                total_debt += breakdown["debt"]
                unpaid_sessions_total += int(breakdown.get("unpaid_sessions", 0) or 0)
                sessions_billed_total += int(breakdown.get("sessions_billed", 0) or 0)
                paid_to_teacher += student_paid_teacher
                paid_to_institute += student_paid_institute
                total_paid += student_paid_teacher + student_paid_institute

        print(
            f"مجموع بدهی کلاس: {total_debt} (معلم: {debt_to_teacher}, آموزشگاه: {debt_to_institute})"
        )
        print(
            f"مجموع پرداختی کلاس: {total_paid} (معلم: {paid_to_teacher}, آموزشگاه: {paid_to_institute})"
        )

        # 4. Get actual session count from session_logs
        session_count = (
            # FIX: Bug 14 - exclude archived SessionLog rows from this active view.
            db.query(SessionLog).filter(SessionLog.is_deleted == False).filter(SessionLog.course_id == c.id).count()
        )

        print(f"تعداد جلسات برگزار شده: {session_count}")

        # 5. Add to result
        result.append(
            {
                "id": c.id,
                "title": c.title,
                "code": c.code,
                "grade_level": c.grade_level,
                "gender": c.gender_type,
                "teacher_id": c.teacher_id,
                "teacher_name": t_name,
                "students_preview": student_names,
                "session_count": session_count,
                "total_debt": total_debt,
                "debt_to_teacher": debt_to_teacher,
                "debt_to_institute": debt_to_institute,
                "total_paid": total_paid,
                "paid_to_teacher": paid_to_teacher,
                "paid_to_institute": paid_to_institute,
                "unpaid_sessions": unpaid_sessions_total,
                "sessions_billed": sessions_billed_total,
                # این ردیف aggregate کلاس است؛ enrollment_id عمداً null می‌ماند.
                "enrollment_id": None,
                "course_id": c.id,
                "course_title": c.title,
                "is_unassigned": False,
                "is_suspended": c.is_suspended if c.is_suspended is not None else False,
            }
        )

    return result


def get_class_full_report(id: int, db: Session = Depends(get_db), authorization: str | None = Header(None), sub_role: str = Depends(check_user_login)):
    """بدنهٔ دامنه‌ایِ `get_class_full_report`؛ توضیح HTTP در پوستهٔ روتر است."""
    # 1. اطلاعات پایه کلاس و معلم
    # FIX (E2E-B5): دوقلوی هم‌الگو — کلاس آرشیوی 404.
    course = db.query(Course).filter(Course.id == id, Course.is_deleted == False).first()
    if not course:
        raise HTTPException(status_code=404, detail="کلاس یافت نشد")
    # FIX (L14/Y3): گزارش کلاس — ادمین/منشی + معلمِ مالک کلاس (الگوی audit-v2/#11). شاگرد/ولی 403.
    if sub_role not in ("admin", "secretary"):
        if sub_role != "teacher":
            raise HTTPException(status_code=403, detail="شما مجاز به مشاهده اطلاعات این کلاس نیستید")
        _me = get_logged_in_teacher(db, authorization)
        if not _me or course.teacher_id != _me.id:
            raise HTTPException(status_code=403, detail="شما مجاز به مشاهده اطلاعات این کلاس نیستید")

    teacher = db.query(Teacher).filter(Teacher.id == course.teacher_id).first()
    t_name = display_name(teacher, "نامشخص")

    # 2. اطلاعات دانش‌آموزان و مالی
    # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
    enrollments = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.course_id == id).all()

    student_list = []
    total_rev = 0
    total_deb = 0
    debt_to_teacher = 0
    debt_to_institute = 0

    for en in enrollments:
        st = db.query(Student).filter(Student.id == en.student_id, Student.is_deleted == False).first()
        if not st:
            continue
        # بدهی گزارش کلاس باید متعلق به همین enrollment باشد؛ بدهی کل دانش‌آموز
        # عمداً برای نمای کلاس استفاده نمی‌شود.
        breakdown = calculate_enrollment_debt_breakdown(db, en)
        paid = breakdown["paid_teacher"] + breakdown["paid_institute"]
        debt = breakdown["debt"]
        debt_to_teacher += breakdown["debt_teacher"]
        debt_to_institute += breakdown["debt_institute"]

        total_rev += paid
        total_deb += debt

        student_list.append(
            ClassStudentData(
                name=display_name(st, "نامشخص"),
                mobile=st.student_mobile,
                paid=paid,
                debt=debt,
                debt_to_teacher=breakdown["debt_teacher"],
                debt_to_institute=breakdown["debt_institute"],
                enrollment_id=en.id,
                course_id=course.id,
                course_title=course.title,
                teacher_id=course.teacher_id,
                teacher_name=t_name,
                is_unassigned=False,
            )
        )

    # 3. محاسبه جلسات برگزار شده (اصلاح شده با ساختار جدید) ✅
    # اول لیست جلسات این کلاس رو میگیریم
    # FIX: Bug 14 - exclude archived SessionLog rows from this active view.
    # FIX (تاریخچهٔ جلسات): ترتیب صریح بر اساس id (ترتیب ثبت) تا شمارهٔ «جلسه ۱، ۲، …» پایدار بماند.
    sessions = (
        db.query(SessionLog)
        .filter(SessionLog.is_deleted == False)
        .filter(SessionLog.course_id == id)
        .order_by(SessionLog.id.asc())
        .all()
    )

    # FIX (تاریخچهٔ جلسات): نام روز هفته از مبدل مرکزی تاریخ (همان منبع بقیهٔ اپ).
    from today_summary import PERSIAN_DAY_NAMES, parse_project_date  # lazy، مثل attendance/finance

    session_history = []
    for sess in sessions:
        # FIX (تاریخچهٔ جلسات): یک کوئری ردیف‌های حضور/غیاب همین جلسه (قبلاً دو count جدا بود).
        # حالا شمارش و نام‌ها از یک منبع می‌آیند تا «حاضرین: ۲ نفر» با لیست نام‌ها ناسازگار نشود.
        # FIX (F-S2): ردیف‌های آرشیوشده در گزارش کلاس نمی‌آیند.
        attendance_rows = (
            db.query(Attendance, Student)
            .outerjoin(Student, Student.id == Attendance.student_id)
            .filter(Attendance.session_id == sess.id, Attendance.is_deleted == False)
            .order_by(Attendance.id.asc())
            .all()
        )
        present_students = []
        absent_students = []
        for att, att_student in attendance_rows:
            status_value = att.status or ""
            if status_value in ("Present", "Late"):
                # «تأخیر» هم حاضر است — همان قرارداد بقیهٔ اپ (students_full/تاریخچهٔ شاگرد).
                present_students.append(
                    ClassSessionStudent(
                        student_id=att.student_id,
                        name=display_name(att_student, "نامشخص"),
                        student_code=getattr(att_student, "student_code", None),
                        status=status_value or "Present",
                        excused=bool(att.excused),
                    )
                )
            elif status_value == "Absent":
                absent_students.append(
                    ClassSessionStudent(
                        student_id=att.student_id,
                        name=display_name(att_student, "نامشخص"),
                        student_code=getattr(att_student, "student_code", None),
                        status="Absent",
                        excused=bool(att.excused),
                    )
                )
            # وضعیت ناشناس (legacy) در هیچ‌کدام شمرده نمی‌شود — مثل رفتار قبلیِ شمارش‌ها.

        day = parse_project_date(sess.date)
        session_history.append(
            ClassSessionHistory(
                date=sess.date,
                present_count=len(present_students),
                absent_count=len(absent_students),
                session_id=sess.id,
                session_code=sess.session_code,
                weekday=PERSIAN_DAY_NAMES.get(day.weekday(), "") if day else "",
                present_students=present_students,
                absent_students=absent_students,
                # همان فرمول هزینهٔ جلسه در attendance/get_history (خواندنی؛ هیچ مالی‌ای نوشته نمی‌شود).
                total_cost=int(
                    (sess.final_teacher_cost or 0)
                    + (sess.final_institute_share or 0)
                    + (sess.absent_penalty_teacher or 0)
                    + (sess.absent_penalty_institute or 0)
                ),
                cost_per_student=int(sess.cost_per_student or 0),
                start_time=sess.start_time or "",
                end_time=sess.end_time or "",
            )
        )

    return FullClassReport(
        info=ClassReportInfo(
            title=course.title,
            code=course.code,
            teacher_name=t_name,
            session_count=len(sessions),
            total_students=len(enrollments),
            total_revenue=total_rev,
            total_debt=total_deb,
            debt_to_teacher=debt_to_teacher,
            debt_to_institute=debt_to_institute,
        ),
        students=student_list,
        sessions=session_history,
    )
