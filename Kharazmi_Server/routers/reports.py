from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Header
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional, Union
from sqlalchemy import desc, or_, text, func
import io
import html
import uuid
import os
import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill

import models
from models import (
    Attendance, Course, Enrollment, Grade, InstituteShare, SessionLog, SmsLog, Student, Teacher, Transaction, User, UserSession, InstituteSettings, Installment
)
from schemas import (
    HistoryRequest, LoginRequest, TeacherInfo, FullTeacherProfile, StudentCreate, TeacherCreate, CourseCreate, EnrollmentCreate, GradeCreate, GradeItem, AttendanceLogRequest, AttendanceItem, AttendanceSubmitData, SmsSendRequest, ChangePasswordRequest, StudentProfileInfo, FullStudentProfile, TeacherProfileInfo, FullTeacherProfile, ClassReportInfo, ClassStudentData, ClassSessionHistory, FullClassReport, ShareConfigModel, StudentUpdate, TeacherUpdate, PersonListItem, TransactionUpdate, StudentAttendanceHistoryRequest, AdvancedSearchItem, FinanceSubmitData, PrintReceiptRequest, TransactionTestData
)
from dependencies import get_db, check_admin_access, check_admin_or_secretary_access, check_user_login, check_student_access, get_enrollment_tuition_and_discount, SESSION_EXPIRY_DAYS, resolve_effective_sub_role, display_name, safe_person_name

# FIX: Bug 16 - share the tuition-minus-payment debt calculation across financial views.
from financial_calculations import calculate_student_debt, calculate_enrollment_debt_breakdown, branch_scope_clause

router = APIRouter()

from financial_calculations import (
    calculate_institute_session_revenue,
    calculate_institute_collected_revenue,
    count_undated_payments,
    collected_revenue_rows,
    calculate_total_turnover,
    calculate_teacher_session_revenue,
    calculate_teacher_collected_revenue,
    report_period_diagnostics,
)
from today_summary import jalali_date_string  # FIX O-07: برچسب قلم‌های زمانی نمودار، شمسی


def _income_chart_buckets(rows, start_day, end_day):
    """قلم‌های زمانی نمودار وصولی (FIX O-07).

    • بازهٔ ≤ ۳۱ روز ⇒ قلم **روزانه** با برچسب تاریخ شمسی («1405/06/30»)
    • بازهٔ بلندتر ⇒ قلم **ماهانهٔ شمسی** با برچسب «1405/06»
    • بی‌تاریخ‌ها قلم زمانی ندارند ⇒ در نمودار نمی‌آیند (ولی در گزارش‌ها می‌مانند — فیکس A3)
    • همیشه حداقل یک قلم برمی‌گردد (روی برنامهٔ اندروید `setupBarChart` دادهٔ خالی = نمودار خالی؛
      یک قلم صفر ایمن‌تر و صادقانه‌تر است: «امروز: صفر»)
    قرارداد خروجی برای Kotlin (`IncomeData(day:String, amount:Float)`): `{"day": str, "amount": int}`.
    """
    # FIX(A3) روی نمودار: ردیف بی‌تاریخ/نامعتبر حذف نمی‌شود و تاریخ جعلی هم نمی‌گیرد؛
    # در قلم آخر با برچسب «بی‌تاریخ» می‌آید تا پول واقعیِ بی‌تاریخ از چشم مدیر نیفتد.
    dated_rows, undated_total = [], 0
    for amount, raw in rows:
        parsed_day = _parsed_project_date(raw)
        if parsed_day is None:
            undated_total += amount
        else:
            dated_rows.append((parsed_day, amount))
    parsed = dated_rows

    window_start, window_end = start_day, end_day
    if window_start is None or window_end is None:
        # بازهٔ نامشخص ⇒ پیش‌فرض «۳۰ روز اخیر» (همان فیلتر پیش‌فرض ChartActivity: «ماه اخیر»)
        # تا قلم‌بندی قطعی باشد و اسکن بی‌بازه/بی‌پایان رخ ندهد.
        _today = datetime.date.today()
        window_start = window_start if window_start is not None else _today - datetime.timedelta(days=29)
        window_end = window_end if window_end is not None else _today
    if window_end < window_start:
        window_start, window_end = window_end, window_start

    span_days = (window_end - window_start).days + 1
    if span_days <= 31:
        labels = [jalali_date_string(window_start + datetime.timedelta(days=offset))
                  for offset in range(span_days)]
        key_of = lambda day: jalali_date_string(day)  # noqa: E731
    else:
        start_key = jalali_date_string(window_start)[:7]
        end_key = jalali_date_string(window_end)[:7]
        labels = []
        year, month = int(start_key[:4]), int(start_key[5:7])
        end_year, end_month = int(end_key[:4]), int(end_key[5:7])
        while (year, month) <= (end_year, end_month):
            labels.append(f"{year:04d}/{month:02d}")
            month += 1
            if month == 13:
                year, month = year + 1, 1
        key_of = lambda day: jalali_date_string(day)[:7]  # noqa: E731

    index = {label: position for position, label in enumerate(labels)}
    buckets = [{"day": label, "amount": 0} for label in labels]
    for day, amount in parsed:
        position = index.get(key_of(day))
        if position is not None:
            buckets[position]["amount"] += amount
    if undated_total:
        buckets.append({"day": "بی‌تاریخ", "amount": undated_total})
    return buckets

def get_user_branch_filter(db: Session, authorization: Optional[str], branch_id: Optional[int]) -> Optional[int]:
    # FIX: JWT-aware + teacher_id handling
    if not authorization:
        return branch_id
    try:
        from dependencies import get_session_from_token
        token = authorization.split()[1]
        session, _ = get_session_from_token(db, token)
        if session:
            if session.sub_role in ["student", "parent"]:
                return branch_id
            user = db.query(User).filter(User.id == session.user_id).first()
            if user and user.branch_id is not None:
                return user.branch_id
            # اگر معلم است و User ندارد، از Teacher.branch_id
            if getattr(session, "teacher_id", None):
                teacher = db.query(Teacher).filter(Teacher.id == session.teacher_id).first()
                if teacher and teacher.branch_id is not None:
                    return teacher.branch_id
    except Exception:
        pass
    return branch_id

def _parsed_project_date(value):
    """تاریخ (شمسی/میلادی) را parse می‌کند؛ مقدار نامعلوم/نامعتبر ⇒ None (بدون استثنا)."""
    from today_summary import parse_project_date  # lazy، الگوی موجود پروژه
    try:
        return parse_project_date(value)
    except Exception:
        return None


def _date_in_range(value, start_day, end_day) -> bool:
    """فیلتر بازهٔ تاریخ با سیاست «هیچ ردیف مالی بی‌صدا حذف نشود» (FIX A3).

    پیش‌تر این تابع در `reports.py` برای هر مقدار غیرقابل‌parse — از جمله `date = NULL` —
    `return False` می‌داد و ردیف از گزارش‌ها (نمودار درآمد، روند حضور، چارت سهم‌ها و گزارش
    مالی) حذف می‌شد؛ حتی وقتی کاربر هیچ بازه‌ای درخواست نکرده بود. نتیجه: جمع مالی آموزشگاه
    کمتر از واقع نمایش داده می‌شد. (همان باگی که در «طلب تسویه‌نشدهٔ معلم» رفع شد.)

    سیاست فعلی:
      • بدون بازه ⇒ همهٔ ردیف‌ها می‌آیند (تاریخ‌دار و بی‌تاریخ).
      • با بازه ⇒ فقط ردیف‌های دارای تاریخِ معتبر محدود می‌شوند؛ ردیف بی‌تاریخ/نامعتبر
        می‌ماند (نمی‌توان اثبات کرد بیرون بازه است) و هیچ تاریخ جعلی ساخته نمی‌شود.
    """
    parsed = _parsed_project_date(value)
    if parsed is None:
        return True
    if start_day is not None and parsed < start_day:
        return False
    if end_day is not None and parsed > end_day:
        return False
    return True


def _api_date_or_blank(value) -> str:
    """تاریخِ قابل‌نمایش در API: تاریخ معتبر ⇒ همان مقدار ذخیره‌شده؛ نامعلوم ⇒ "".

    کلاینت‌ها (اپ اندروید) مدل `String` غیر-null دارند؛ فرستادن `null` یا تاریخ جعلی
    ممنوع است. مقدار خام دیتابیس هم دست‌کاری نمی‌شود.
    """
    return value if _parsed_project_date(value) is not None else ""


@router.get("/reports/chart-data")
def get_chart_data(
    class_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_or_secretary_access)  # FIX (L14/Y4): نمودارهای درآمد/حضور سطح موسسه — فقط کارکنان
):
    # FIX H3-B3: boundaries may be Jalali (app ranges) or Gregorian; Transaction.date mixes both
    # by row type, so SQL string ranges can't bound it — parse and filter in Python.
    # FIX(A3): فیلتر/نمایش تاریخ از helper مشترک ماژول می‌آید (ردیف بی‌تاریخ حذف نمی‌شود).
    start_day = _parsed_project_date(start_date) if start_date else None
    end_day = _parsed_project_date(end_date) if end_date else None

    def _in_range(value):  # سازگاری با فراخوانی‌های همین تابع
        return _date_in_range(value, start_day, end_day)

    # 1. Income Chart — FIX O-07: پیش‌تر ۵ میلهٔ **ساختگی** بود (کل مبلغ تقسیم بر ۵/۴/۳/۲ با
    # برچسب روزهای هفته) ⇒ جمع ستون‌ها ۲٫۲۸ برابر «درآمد» می‌شد و هیچ روز/ماهی از دادهٔ واقعی
    # نمی‌آمد. حالا همان تعریف واحد وصولی (O-08) در قلم‌های زمانی واقعی.
    # FIX: Bug 12 - ردیف‌های آرشیوشده/برگشتی در این نمای فعال نمی‌آیند (داخل helper).
    _chart_today = datetime.date.today()
    _chart_fallback_end = None
    if start_day is None:
        # قرارداد UI «۳۰ روز اخیر» حفظ می‌شود. فقط وقتی این بازه هیچ تراکنش تاریخ‌داری
        # ندارد، برای جلوگیری از گزارش صفر، به قدیمی‌ترین تاریخ legacy fallback می‌کنیم.
        _default_start = _chart_today - datetime.timedelta(days=29)
        _known_chart_dates = [
            parsed for parsed in (_parsed_project_date(value) for (value,) in
                                  db.query(Transaction.date).filter(
                                      Transaction.is_deleted == False,
                                      Transaction.is_reversed == False,
                                  ).all())
            if parsed is not None
        ]
        has_recent = any(_default_start <= value <= _chart_today for value in _known_chart_dates)
        if has_recent or not _known_chart_dates:
            _chart_start = _default_start
        else:
            _chart_start = min(_known_chart_dates)
            _chart_fallback_end = max(_known_chart_dates)
    else:
        _chart_start = start_day
    _chart_end = end_day if end_day is not None else (_chart_fallback_end or _chart_today)
    if _chart_end < _chart_start:
        _chart_start, _chart_end = _chart_end, _chart_start
    _income_rows = collected_revenue_rows(db, _chart_start.isoformat(), _chart_end.isoformat(),
                                          course_id=class_id, include_undated=True)
    income_data = _income_chart_buckets(_income_rows, _chart_start, _chart_end)

    # 2. Student Chart (existing)
    boys = db.query(Student).filter(Student.gender == "آقا").count()
    girls = db.query(Student).filter(Student.gender == "خانم").count()
    student_stats = [{"label": "آقا", "count": boys}, {"label": "خانم", "count": girls}]

    # 3. Chart 1: Attendance Trend
    # FIX: Bug 14 - exclude archived SessionLog rows from this active view.
    q_sessions = db.query(SessionLog).filter(SessionLog.is_deleted == False)
    if class_id:
        q_sessions = q_sessions.filter(SessionLog.course_id == class_id)

    sessions = [s for s in q_sessions.all() if _in_range(s.date)]
    # FIX(A3): ترتیب قطعی (deterministic) — تاریخ معتبر صعودی، ردیف‌های بی‌تاریخ در انتها و
    # در تاریخ یکسان، id صعودی. پیش‌تر ترتیب به رفتار دیتابیس در NULL وابسته بود (در SQLite
    # اول، در PostgreSQL آخر) ⇒ خروجی بین محیط‌ها تفاوت داشت.
    sessions.sort(key=lambda s: (_parsed_project_date(s.date) is None,
                                 _parsed_project_date(s.date) or datetime.date.min,
                                 s.id))
    session_ids = [s.id for s in sessions]
    attendance_trend = []
    
    if session_ids:
        from sqlalchemy import func
        stats = (
            db.query(
                Attendance.session_id,
                Attendance.status,
                func.count(Attendance.id)
            )
            .filter(Attendance.session_id.in_(session_ids))
            .group_by(Attendance.session_id, Attendance.status)
            .all()
        )
        
        session_stats = {sid: {"present": 0, "absent": 0} for sid in session_ids}
        for sid, status_val, count in stats:
            if sid in session_stats:
                if status_val in ["Present", "Late"]:
                    session_stats[sid]["present"] += count
                elif status_val == "Absent":
                    session_stats[sid]["absent"] += count
                    
        for s in sessions:
            stat = session_stats.get(s.id, {"present": 0, "absent": 0})
            present = stat["present"]
            absent = stat["absent"]
            total = present + absent
            pct = (present / total * 100) if total > 0 else 100.0
            attendance_trend.append({
                # FIX(A3): مقدار نامعلوم ⇒ "" (بدون تاریخ جعلی و بدون null برای کلاینت)
                "date": _api_date_or_blank(s.date),
                "present": present,
                "absent": absent,
                "percentage": round(pct, 1)
            })

    # 4. Chart 2: Shares Chart
    # استخراج و اعتبارسنجی نقش ادمین برای نمایش چارت سهم‌ها به منشی
    sub_role = "secretary"
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
            session = db.query(UserSession).filter(UserSession.token == token).first()
            if session:
                user = db.query(User).filter(User.id == session.user_id).first()
                if user:
                    # FIX(A1): نقش با سیاست کمترین سطح دسترسی (سهم معلم/آموزشگاه
                    # فقط برای ادمین واقعی نمایش داده می‌شود، نه رکورد بی‌نقش).
                    sub_role = resolve_effective_sub_role(user)

    shares_chart = None
    if sub_role == "admin":
        # FIX: Bug 12 - exclude archived Transaction rows from this active view.
        q_shares = db.query(Transaction).filter(Transaction.is_deleted == False, Transaction.is_reversed == False)
        if class_id:
            q_shares = q_shares.filter(Transaction.course_id == class_id)

        # FIX H3-B3: same as income/sessions above — parsed Python filter (_in_range already in scope).
        shares_trans = [t for t in q_shares.all() if _in_range(t.date)]
        total_teacher_share = sum(t.share_teacher for t in shares_trans if t.share_teacher is not None)
        total_institute_share = sum(t.share_institute for t in shares_trans if t.share_institute is not None)
        
        shares_chart = {
            "teacher": total_teacher_share,
            "institute": total_institute_share
        }

    return {
        "income_chart": income_data,
        "student_chart": student_stats,
        "attendance_trend": attendance_trend,
        "shares_chart": shares_chart
    }


# ==========================================
# 3. API های ثبت نام
# ==========================================


@router.get("/reports/financial")
def get_financial_report(
    start_date: str = None,
    end_date: str = None,
    branch_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_access)
):
    resolved_branch = get_user_branch_filter(db, authorization, branch_id)
    # FIX H3-B3: boundaries may be Jalali or Gregorian; Transaction.date mixes both by row type —
    # parse and filter in Python (same pattern as get_chart_data above).
    # FIX(A3): همان helper مشترک — ردیف بی‌تاریخ از گزارش مالی حذف نمی‌شود.
    start_day = _parsed_project_date(start_date) if start_date else None
    end_day = _parsed_project_date(end_date) if end_date else None

    def _in_range(value):
        return _date_in_range(value, start_day, end_day)
    # FIX: Bug 12 - exclude archived Transaction rows from this active view.
    query = db.query(Transaction).filter(Transaction.is_deleted == False, Transaction.is_reversed == False)
    if resolved_branch is not None:
        scope = branch_scope_clause(Transaction.branch_id, resolved_branch)
        if scope is not None:
            query = query.filter(scope)
    if teacher_id is not None:
        teacher_course_ids = [row[0] for row in db.query(Course.id).filter(Course.teacher_id == teacher_id).all()]
        if not teacher_course_ids:
            return []
        query = query.filter(Transaction.course_id.in_(teacher_course_ids))

    trans = [t for t in query.order_by(desc(Transaction.id)).all() if _in_range(t.date)]
    report = []
    for t in trans:
        st_name = "ناشناس"
        student_id = None
        if t.enrollment_id:
            en = db.query(Enrollment).filter(Enrollment.id == t.enrollment_id).first()
            if en:
                st = db.query(Student).filter(Student.id == en.student_id).first()
                if st:
                    st_name = display_name(st, "نامشخص")
                    student_id = st.id
        elif t.student_id:
            st = db.query(Student).filter(Student.id == t.student_id).first()
            if st:
                st_name = display_name(st, "نامشخص")
                student_id = st.id
        course = db.query(Course).filter(Course.id == t.course_id).first() if t.course_id else None
        teacher = db.query(Teacher).filter(Teacher.id == course.teacher_id).first() if course and course.teacher_id else None
        effective_branch_id = t.branch_id if t.branch_id is not None else (course.branch_id if course else None)
        branch = db.query(models.Branch).filter(models.Branch.id == effective_branch_id).first() if effective_branch_id else None
        report.append(
            {
                "transaction_id": t.id,
                "student_id": student_id,
                "student_name": st_name,
                "amount": int(t.amount or 0),
                # FIX(A3): تاریخ نامعلوم ⇒ "" (نه null؛ نه تاریخ جعلی)
                "date": _api_date_or_blank(t.date),
                "description": t.description or "",
                "payment_method": t.payment_method or "",
                "target_wallet": t.target_wallet,
                "type": t.type,
                "course_id": t.course_id,
                "course_title": course.title if course else "کلاس عمومی/نامشخص",
                "teacher_id": course.teacher_id if course else None,
                "teacher_name": display_name(teacher, "بدون معلم") if teacher else "بدون معلم",
                "branch_id": effective_branch_id,
                "branch_name": branch.name if branch else "شعبهٔ legacy/نامشخص",
                "share_teacher": int(t.share_teacher or 0),
                "share_institute": int(t.share_institute or 0),
                "student_statement_path": f"/reports/student_statement?student_id={student_id}" if student_id else "",
            }
        )
    return report


@router.get("/reports/financial/excel")
def get_financial_report_excel(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    branch_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_access),
):
    """خروجی Excel همان دادهٔ گزارش مالی، با همان scope/تاریخ و بدون محاسبهٔ جداگانه."""
    rows = get_financial_report(
        start_date=start_date, end_date=end_date, branch_id=branch_id, teacher_id=teacher_id,
        authorization=authorization, db=db, _=_
    )
    wb = Workbook()
    ws = wb.active
    ws.title = "گزارش مالی"
    ws.views.sheetView[0].rightToLeft = True
    headers = [
        "شناسه تراکنش", "دانش‌آموز", "معلم", "کلاس", "شعبه", "مبلغ (تومان)",
        "کیف مقصد", "نوع", "تاریخ", "روش پرداخت", "شرح", "سهم معلم", "سهم آموزشگاه",
    ]
    ws.append(headers)
    for row in rows:
        ws.append([
            row.get("transaction_id"), row.get("student_name") or "نامشخص",
            row.get("teacher_name") or "بدون معلم", row.get("course_title") or "—",
            row.get("branch_name") or "شعبهٔ legacy/نامشخص", row.get("amount", 0),
            row.get("target_wallet") or "—", row.get("type") or "—", row.get("date") or "بی‌تاریخ",
            row.get("payment_method") or "—", row.get("description") or "—",
            row.get("share_teacher", 0), row.get("share_institute", 0),
        ])
    for cell in ws[1]:
        cell.font = Font(name="Tahoma", size=11, bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="00695C", end_color="00695C", fill_type="solid")
        cell.alignment = Alignment(horizontal="center")
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.font = Font(name="Tahoma", size=10)
    for col in ws.columns:
        width = max(len(str(cell.value or "")) for cell in col) + 3
        ws.column_dimensions[col[0].column_letter].width = min(max(width, 12), 42)
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=financial_report.xlsx"},
    )


@router.get("/reports/debtors")
def get_debtors_report(
    branch_id: Optional[int] = None,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_access)
):
    resolved_branch = get_user_branch_filter(db, authorization, branch_id)
    # FIX (گروه۲/آیتم ۶): فیلتر سختِ شعبه (`Student.branch_id == resolved_branch`) خروجی را
    # با دادهٔ واقعی خالی می‌کرد — در پایگاه واقعی ردیف‌های `students` بی‌شعبه (NULL) هستند و
    # ادمینِ شعبه‌دار `branch_id=1` دارد ⇒ `NULL == 1` هرگز درست نیست.
    # حالا از منبع یگانهٔ `build_debtor_rows` استفاده می‌شود: ردیف بی‌شعبه = سراسری/legacy
    # (دیده می‌شود)، ردیف شعبهٔ دیگر = پنهان (بدون نشت داده بین شعبه‌ها).
    from routers.finance import build_debtor_rows  # lazy: بدون چرخهٔ import
    rows = build_debtor_rows(db, resolved_branch)
    return [
        {
            "student_id": row["student_id"],
            "student_name": row["student_name"],
            "amount": row["total_debt"],
            "date": "-",
            "description": "بدهی",
            "payment_method": "-",
        }
        for row in rows
    ]


# Test endpoint to verify debt calculation


@router.get("/reports/debtors/excel")
def get_debtors_excel(
    branch_id: Optional[int] = None,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_access)
):
    resolved_branch = get_user_branch_filter(db, authorization, branch_id)
    # FIX (گروه۲/آیتم ۶): همان اصلاح لیست بدهکاران — فیلتر سختِ شعبه با دادهٔ واقعی
    # (دانش‌آموزان بی‌شعبه/legacy) فایل Excel را هم خالی تحویل می‌داد. منبع یگانه: build_debtor_rows
    from routers.finance import build_debtor_rows  # lazy: بدون چرخهٔ import
    debtor_rows = build_debtor_rows(db, resolved_branch)

    wb = Workbook()
    ws = wb.active
    ws.title = "لیست بدهکاران"
    ws.views.sheetView[0].rightToLeft = True

    # FIX (گروه۲/آیتم ۹ — «پیشنهاد من»): ستون‌های جدید برای پیگیری عملی
    headers = ["شناسه", "نام و نام خانوادگی", "بدهی به معلم (تومان)", "بدهی به آموزشگاه (تومان)", "کل بدهی (تومان)", "تلفن همراه", "تلفن والدین", "تاریخ آخرین پرداخت", "قدمت بدهی (روز)"]
    ws.append(headers)
    
    header_fill = PatternFill(start_color="00695C", end_color="00695C", fill_type="solid")
    header_font = Font(name="Tahoma", size=11, bold=True, color="FFFFFF")
    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        
    row_num = 2
    for row in debtor_rows:
        row_data = [
            row["student_id"],
            row["student_name"],
            row["debt_teacher"],
            row["debt_institute"],
            row["total_debt"],
            row.get("student_mobile") or "",
            row.get("parent_mobile") or "",
            row.get("last_payment_date") or "بدون پرداخت",
            row.get("debt_age_days") if row.get("debt_age_days") is not None else "بدون پرداخت",
        ]
        ws.append(row_data)

        ws.cell(row=row_num, column=3).number_format = '#,##0'
        ws.cell(row=row_num, column=4).number_format = '#,##0'
        ws.cell(row=row_num, column=5).number_format = '#,##0'

        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=row_num, column=col_num)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.font = Font(name="Tahoma", size=10)

        row_num += 1
            
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = col[0].column_letter
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)
        
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=debtors_list.xlsx"}
    )


# ==========================================
# 🆕 گزارش‌گیری جدید و صورت‌حساب دانش‌آموز 🆕
# ==========================================

def get_current_shamsi_date():
    # FIX H3-B3: unified on the central converter (was a second ~30-line day-counting implementation).
    from today_summary import gregorian_to_jalali  # lazy import, same pattern as routers/analytics.py
    return gregorian_to_jalali(datetime.date.today())


def get_logged_in_teacher(db: Session, authorization: Optional[str]) -> Optional[Teacher]:
    # FIX: مقاوم به تغییر موبایل – اول teacher_id مستقیم، بعد fallback به mobile
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1]
    # FIX: از helper جدید برای JWT + fallback استفاده کن
    try:
        from dependencies import get_session_from_token
        session, _ = get_session_from_token(db, token)
    except Exception:
        session = db.query(UserSession).filter(UserSession.token == token).first()
    if not session:
        return None
    # اگر teacher_id مستقیم ذخیره شده باشد (فیکس Bug 3)
    if getattr(session, "teacher_id", None):
        t = db.query(Teacher).filter(Teacher.id == session.teacher_id).first()
        if t:
            return t
    user = db.query(User).filter(User.id == session.user_id).first()
    if not user or user.role != "teacher":
        return None
    teacher = db.query(Teacher).filter(Teacher.mobile == user.username).first()
    if teacher:
        return teacher
    # فقط برای کاربر معلم: ممکن است session.user_id در مهاجرت قدیمی همان Teacher.id باشد
    return db.query(Teacher).filter(Teacher.id == session.user_id).first()


def _optional_int_param(value: Optional[str], field_label: str) -> Optional[int]:
    """FIX (گروه۲/آیتم۵): پارامتر عددیِ «خالی» در query string ⇒ None، نه ۴۲۲ خام pydantic.

    چرا لازم است: کلاینت Retrofit یک `@Query` با مقدار `null` را به‌صورت `teacher_id=`
    (رشتهٔ خالی) روی URL می‌گذارد؛ امضای `Optional[int]` در FastAPI همان را با بدنهٔ خام
    «Input should be a valid integer» رد می‌کرد ⇒ گزارش مالی پنل معلم هیچ‌وقت باز نمی‌شد.
    مقدارِ واقعاً نامعتبر (مثل «abc») بی‌صدا نادیده گرفته نمی‌شود: ۴۰۰ با پیام فارسی.
    """
    if value is None:
        return None
    text_value = str(value).strip()
    if not text_value:
        return None
    try:
        return int(text_value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400,
                            detail=f"{field_label} باید یک عدد صحیح باشد (مثال: 1405)")


@router.get("/reports/financial_summary")
def get_financial_summary(
    user_type: str,  # "institute" or "teacher"
    teacher_id: Optional[str] = None,
    year: Optional[str] = None,
    month: Optional[str] = None,
    branch_id: Optional[str] = None,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    sub_role: str = Depends(check_user_login)
):
    # FIX (L14/Y4): تکمیل تله — شاگرد/ولی 403؛ معلم در ادامه به خلاصه‌ی خودش قفل می‌شود (کد موجود).
    if sub_role not in ("admin", "secretary", "teacher"):
        raise HTTPException(status_code=403, detail="شما دسترسی لازم برای مشاهده خلاصه مالی را ندارید")
    # FIX (گروه۲/آیتم۵): `user_type` نامعتبر پیش‌تر **۲۰۰ با بدنهٔ `null`** می‌داد (تابع بدون
    # return پایان می‌یافت) ⇒ Gson در کلاینت روی `FinancialSummaryResponse` غیرnullable خطا
    # می‌کرد. حالا صریح ۴۰۰ با پیام فارسی؛ پارامترهای عددی هم از هلپر `_optional_int_param`
    # عبور می‌کنند تا query خالی (`teacher_id=`/`year=`) به‌جای ۴۲۲ خام، None شود.
    if user_type not in ("institute", "teacher"):
        raise HTTPException(status_code=400, detail="user_type باید institute یا teacher باشد")
    teacher_id = _optional_int_param(teacher_id, "شناسهٔ معلم")
    year = _optional_int_param(year, "سال")
    month = _optional_int_param(month, "ماه")
    branch_id = _optional_int_param(branch_id, "شناسهٔ شعبه")
    resolved_branch = get_user_branch_filter(db, authorization, branch_id)
    # بررسی و محدودسازی در صورتی که کاربر جاری معلم باشد
    logged_teacher = get_logged_in_teacher(db, authorization)
    if logged_teacher:
        user_type = "teacher"
        teacher_id = logged_teacher.id

    curr_jy, curr_jm, _ = get_current_shamsi_date()
    if not year:
        year = curr_jy
    if not month:
        month = curr_jm

    month_prefix = f"{year}/{month:02d}/%"
    year_prefix = f"{year}/%"

    start_date = f"{year}/{month:02d}/01"
    # روز ۳۱ برای ماه‌های ۷ تا ۱۱ جلالی نامعتبر است و helper مرکزی عمداً
    # بازهٔ نامعتبر را صفر می‌کند. آخرین روز معتبر ماه را بدون حدس تقویمی پیدا کن.
    month_last_day = 31 if month <= 6 else 30
    if month == 12:
        month_last_day = 30
    while month_last_day > 1 and _parsed_project_date(f"{year}/{month:02d}/{month_last_day:02d}") is None:
        month_last_day -= 1
    end_date = f"{year}/{month:02d}/{month_last_day:02d}"

    start_year_date = f"{year}/01/01"
    year_last_day = 30
    while year_last_day > 1 and _parsed_project_date(f"{year}/12/{year_last_day:02d}") is None:
        year_last_day -= 1
    end_year_date = f"{year}/12/{year_last_day:02d}"

    if user_type == "institute":
        # گزارش ماهانه آموزشگاه با استفاده از توابع متمرکز
        total_m = calculate_institute_session_revenue(db, start_date, end_date, resolved_branch)
        collected_m = calculate_institute_collected_revenue(db, start_date, end_date, resolved_branch)
        uncollected_m = max(0, total_m - collected_m)

        # گزارش سالانه آموزشگاه
        total_y = calculate_institute_session_revenue(db, start_year_date, end_year_date, resolved_branch)
        collected_y = calculate_institute_collected_revenue(db, start_year_date, end_year_date, resolved_branch)
        uncollected_y = max(0, total_y - collected_y)

        # FIX O-10: پول بی‌تاریخ در جمع‌های ماه/سال نمی‌آید (تصمیم E1) — این دو شمارنده آن را
        # آشکار می‌کنند تا مدیر فکر نکند پولی گم شده است. جمع‌های بالا دست‌نخورده‌اند.
        undated_count, undated_amount = count_undated_payments(db, target_wallet="institute",
                                                              branch_id=resolved_branch)

        return {
            "user_type": "institute",
            "year": year,
            "month": month,
            "undated_count": int(undated_count),
            "undated_amount": int(undated_amount),
            "monthly": {
                "total": int(total_m),
                "collected": int(collected_m),
                "uncollected": int(uncollected_m)
            },
            "yearly": {
                "total": int(total_y),
                "collected": int(collected_y),
                "uncollected": int(uncollected_y)
            },
            # فقط توضیح (افزودنی): چرا عددها صفرند / پیش‌پرداخت‌ها کجایند. اعداد بالا را تغییر نمی‌دهد.
            "diagnostics": report_period_diagnostics(db, start_date, end_date, branch_id=resolved_branch),
        }

    elif user_type == "teacher":
        if not teacher_id:
            raise HTTPException(status_code=400, detail="شناسه معلم الزامی است")

        teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
        if not teacher:
            raise HTTPException(status_code=404, detail="معلم یافت نشد")

        # محاسبات ماهانه و سالانه معلم با توابع متمرکز
        total_m = calculate_teacher_session_revenue(db, teacher_id, start_date, end_date)
        collected_m = calculate_teacher_collected_revenue(db, teacher_id, start_date, end_date)
        uncollected_m = max(0, total_m - collected_m)

        total_y = calculate_teacher_session_revenue(db, teacher_id, start_year_date, end_year_date)
        collected_y = calculate_teacher_collected_revenue(db, teacher_id, start_year_date, end_year_date)
        uncollected_y = max(0, total_y - collected_y)

        # FIX O-10: مثل شاخهٔ مؤسسه، ولی فقط پرداخت‌های به کیف همین معلم.
        _teacher_course_ids = [c.id for c in db.query(Course).filter(Course.teacher_id == teacher_id).all()]
        undated_count, undated_amount = count_undated_payments(db, target_wallet="teacher",
                                                              course_ids=_teacher_course_ids)

        return {
            "user_type": "teacher",
            "teacher_id": teacher_id,
            "teacher_name": display_name(teacher, "نامشخص"),
            "year": year,
            "month": month,
            "undated_count": int(undated_count),
            "undated_amount": int(undated_amount),
            "monthly": {
                "total": int(total_m),
                "collected": int(collected_m),
                "uncollected": int(uncollected_m)
            },
            "yearly": {
                "total": int(total_y),
                "collected": int(collected_y),
                "uncollected": int(uncollected_y)
            },
            "diagnostics": report_period_diagnostics(db, start_date, end_date, teacher_id=teacher_id),
        }


@router.get("/reports/student_statement")
def get_student_statement(
    student_id: int,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    role: str = Depends(check_user_login)
):
    # FIX (L14/Y1): صورت‌حساب/چاپ هر شاگرد — فقط ادمین/منشی، معلمِ درگیر، خودِ شاگرد/ولیِ همان فرزند.
    check_student_access(student_id, authorization, db, role)
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="دانش‌آموز یافت نشد")

    # FIX: Bug 12 - exclude archived Transaction rows from this active view.
    total_paid_institute = db.query(func.sum(Transaction.amount)).filter(Transaction.is_deleted == False, Transaction.is_reversed == False).filter(
        Transaction.student_id == student_id,
        Transaction.target_wallet == "institute",
        Transaction.amount > 0
    ).scalar() or 0

    wallet_inst = student.wallet_institute if student.wallet_institute is not None else 0
    total_debt_institute = abs(wallet_inst) if wallet_inst < 0 else 0

    settings = db.query(InstituteSettings).first()
    if not settings:
        settings = InstituteSettings()
        db.add(settings)
        db.commit()
        db.refresh(settings)

    enrollments = db.query(Enrollment).filter(
        Enrollment.student_id == student_id, Enrollment.is_deleted == False
    ).all()
    teacher_names = []
    enrollment_ids = [e.id for e in enrollments]
    teacher_details = []
    for enrollment in enrollments:
        course = enrollment.course
        if not course:
            continue
        teacher = course.teacher
        name = display_name(teacher, "نامشخص") if teacher else "بدون معلم"
        if name not in teacher_names:
            teacher_names.append(name)
        breakdown = calculate_enrollment_debt_breakdown(db, enrollment)
        teacher_details.append({
            "enrollment_id": enrollment.id,
            "teacher_id": course.teacher_id,
            "teacher_name": name,
            "course_id": course.id,
            "course_title": course.title or "کلاس بدون نام",
            "course_code": course.code or "",
            "branch_id": enrollment.branch_id if enrollment.branch_id is not None else course.branch_id,
            "paid_teacher": int(breakdown["paid_teacher"]),
            "paid_institute": int(breakdown["paid_institute"]),
            "debt_teacher": int(breakdown["debt_teacher"]),
            "debt_institute": int(breakdown["debt_institute"]),
            "debt": int(breakdown["debt"]),
            "tuition": int(breakdown["tuition"]),
            "enrollment_status": "فعال" if not enrollment.is_deleted else "آرشیو",
            "teacher_profile_path": f"/teachers/{course.teacher_id}/full_profile" if course.teacher_id else "",
            "student_profile_path": f"/admin/students/{student_id}/full_profile",
            "is_unassigned": False,
        })
    assigned_debt = sum(int(row.get("debt") or 0) for row in teacher_details)
    unassigned_debt = max(0, int(calculate_student_debt(db, student)) - assigned_debt)
    if unassigned_debt:
        teacher_details.append({
            "enrollment_id": None,
            "teacher_id": None,
            "teacher_name": None,
            "course_id": None,
            "course_title": None,
            "course_code": None,
            "branch_id": None,
            "paid_teacher": 0,
            "paid_institute": 0,
            "debt_teacher": 0,
            "debt_institute": int(unassigned_debt),
            "debt": int(unassigned_debt),
            "tuition": 0,
            "enrollment_status": "بدون کلاس",
            "teacher_profile_path": "",
            "student_profile_path": f"/admin/students/{student_id}/full_profile",
            "is_unassigned": True,
        })
    # Explicit class-scoped totals are separate from the legacy wallet summary
    # above. A global wallet balance must never be silently attributed to one of
    # these classes; any remainder is already represented by the unassigned row.
    class_paid_institute = sum(int(row.get("paid_institute") or 0) for row in teacher_details)
    class_debt_institute = sum(int(row.get("debt_institute") or 0) for row in teacher_details if not row.get("is_unassigned"))
    class_debt_total = sum(int(row.get("debt") or 0) for row in teacher_details if not row.get("is_unassigned"))

    payment_rows = db.query(Transaction).filter(
        Transaction.student_id == student_id, Transaction.is_deleted == False,
        Transaction.is_reversed == False, Transaction.amount > 0
    ).order_by(Transaction.id.desc()).all()
    payment_timeline = [{
        "transaction_id": row.id, "date": row.date, "amount": int(row.amount or 0),
        "target_wallet": row.target_wallet, "description": row.description,
        "payment_link": f"/finance/receipt/{row.id}"
    } for row in payment_rows]
    next_installment = None
    if enrollment_ids:
        installment = db.query(Installment).filter(
            Installment.enrollment_id.in_(enrollment_ids), Installment.is_deleted == False,
            Installment.is_paid == False
        ).order_by(Installment.due_date.asc(), Installment.id.asc()).first()
        if installment:
            next_installment = {
                "id": installment.id, "amount": int(installment.amount or 0),
                "paid_amount": int(installment.paid_amount or 0),
                "due_date": installment.due_date,
                "remaining_amount": max(0, int((installment.amount or 0) - (installment.paid_amount or 0))),
                "payment_link": f"/finance/payment/initiate?installment_id={installment.id}"
            }

    return {
        "student_id": student.id,
        "student_name": display_name(student, "نامشخص"),
        "student_code": student.student_code or str(100000 + student.id),
        "teacher_name": ", ".join(teacher_names) if teacher_names else "بدون معلم",
        "teachers": teacher_details,
        "active_enrollments": [
            {
                "enrollment_id": e.id, "course_id": e.course_id,
                "status": "فعال" if not e.is_deleted else "آرشیو",
                "register_date": e.register_date, "branch_id": e.branch_id,
            }
            for e in enrollments
        ],
        "total_paid_institute": int(total_paid_institute),
        "total_debt_institute": int(total_debt_institute),
        # New explicit class-scoped values for the report UI. The legacy total_*
        # fields remain for compatibility and continue to describe the aggregate
        # student wallet/ledger, not a selected class.
        "class_paid_institute": int(class_paid_institute),
        "class_debt_institute": int(class_debt_institute),
        "class_debt_total": int(class_debt_total),
        "unassigned_debt": int(unassigned_debt),
        # FIX: Bug 16 - expose contractual debt separately; do not assign all tuition to one wallet.
        "total_debt": calculate_student_debt(db, student),
        "payment_timeline": payment_timeline,
        "next_installment": next_installment,
        "payment_link": (next_installment or {}).get("payment_link") if next_installment else "/payments/initiate",
        "institute_card_number": settings.card_number or "۶۰۳۷۹۹۷۹۷۹۷۹۷۹۷۹",
        "institute_name": settings.name,
        "address": settings.address,
        "phone": settings.phone,
        "footer_text": settings.footer_text
    }


@router.get("/reports/student_statement/print", response_class=HTMLResponse)
def print_student_statement(
    student_id: int,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    role: str = Depends(check_user_login)
):
    # FIX (L14/Y1): صورت‌حساب/چاپ هر شاگرد — فقط ادمین/منشی، معلمِ درگیر، خودِ شاگرد/ولیِ همان فرزند.
    check_student_access(student_id, authorization, db, role)
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        return "<h3>دانش‌آموز یافت نشد</h3>"

    # FIX: Bug 12 - exclude archived Transaction rows from this active view.
    total_paid_institute = db.query(func.sum(Transaction.amount)).filter(Transaction.is_deleted == False, Transaction.is_reversed == False).filter(
        Transaction.student_id == student_id,
        Transaction.target_wallet == "institute",
        Transaction.amount > 0
    ).scalar() or 0

    wallet_inst = student.wallet_institute if student.wallet_institute is not None else 0
    total_debt_institute = abs(wallet_inst) if wallet_inst < 0 else 0

    # Keep the printable statement useful for multi-class students too. The
    # aggregate wallet summary remains for backward compatibility, while this
    # list is calculated per active enrollment and never assigns a global wallet
    # remainder to an arbitrary class.
    class_breakdown = []
    active_enrollments = db.query(Enrollment).filter(
        Enrollment.student_id == student_id,
        Enrollment.is_deleted == False,
    ).all()
    assigned_debt = 0
    for enrollment in active_enrollments:
        course = enrollment.course
        if not course:
            continue
        breakdown = calculate_enrollment_debt_breakdown(db, enrollment)
        assigned_debt += int(breakdown["debt"] or 0)
        class_breakdown.append({
            "title": course.title or "کلاس بدون نام",
            "teacher": display_name(course.teacher, "بدون معلم") if course.teacher else "بدون معلم",
            "debt_teacher": int(breakdown["debt_teacher"] or 0),
            "debt_institute": int(breakdown["debt_institute"] or 0),
            "debt": int(breakdown["debt"] or 0),
        })
    unassigned_debt = max(0, int(calculate_student_debt(db, student)) - assigned_debt)
    class_rows_html = "".join(
        f"<div class=\"row-info\"><span class=\"label\">{html.escape(row['title'])} / {html.escape(row['teacher'])}</span>"
        f"<span class=\"value\">معلم: {row['debt_teacher']:,} | آموزشگاه: {row['debt_institute']:,} | کل: {row['debt']:,} تومان</span></div>"
        for row in class_breakdown
    )
    if unassigned_debt:
        class_rows_html += (
            f"<div class=\"row-info\"><span class=\"label\">بدون انتساب به کلاس</span>"
            f"<span class=\"value highlight\">{unassigned_debt:,} تومان</span></div>"
        )
    if not class_rows_html:
        class_rows_html = "<p class=\"label\">برای این دانش‌آموز ردیف کلاس‌محور ثبت نشده است.</p>"

    settings = db.query(InstituteSettings).first()
    if not settings:
        settings = InstituteSettings()

    card_num = settings.card_number or "۶۰۳۷۹۹۷۹۷۹۷۹۷۹۷۹"
    inst_name = settings.name
    address = settings.address
    phone = settings.phone
    footer = settings.footer_text

    current_date = datetime.datetime.now().strftime("%Y/%m/%d %H:%M")

    html_content = f"""
    <!DOCTYPE html>
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>صورت‌حساب آموزشگاه</title>
        <style>
            @font-face {{
                font-family: 'Tahoma';
                src: local('Tahoma');
            }}
            body {{
                font-family: 'Tahoma', sans-serif;
                margin: 0;
                padding: 10px;
                color: #212121;
                background-color: #ffffff;
                font-size: 13px;
                line-height: 1.6;
            }}
            .ticket {{
                max-width: 320px;
                margin: 0 auto;
                padding: 15px;
                border: 1px dashed #00695C;
                border-radius: 8px;
            }}
            .header {{
                text-align: center;
                border-bottom: 2px dashed #00695C;
                padding-bottom: 10px;
                margin-bottom: 15px;
            }}
            .header h2 {{
                margin: 5px 0;
                font-size: 16px;
                color: #00695C;
            }}
            .header p {{
                margin: 3px 0;
                font-size: 11px;
                color: #666666;
            }}
            .row-info {{
                display: flex;
                justify-content: space-between;
                margin: 8px 0;
                border-bottom: 1px dotted #eeeeee;
                padding-bottom: 4px;
            }}
            .label {{
                font-weight: bold;
                color: #555555;
            }}
            .value {{
                color: #000000;
            }}
            .highlight {{
                color: #D32F2F;
                font-weight: bold;
                font-size: 14px;
            }}
            .success-val {{
                color: #388E3C;
                font-weight: bold;
                font-size: 14px;
            }}
            .footer {{
                text-align: center;
                border-top: 2px dashed #00695C;
                padding-top: 10px;
                margin-top: 20px;
                font-size: 11px;
            }}
            .card-box {{
                background-color: #E8F5E9;
                border: 1px solid #C8E6C9;
                border-radius: 4px;
                padding: 8px;
                margin-top: 10px;
                text-align: center;
            }}
            .card-number {{
                font-weight: bold;
                font-size: 15px;
                color: #2E7D32;
                letter-spacing: 1px;
                margin: 4px 0 0 0;
            }}
            @media print {{
                body {{
                    padding: 0;
                }}
                .ticket {{
                    border: none;
                    max-width: 100%;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="ticket">
            <div class="header">
                <h2>{inst_name}</h2>
                <p>صورت‌حساب رسمی دانش‌آموز</p>
                <p>تاریخ چاپ: {current_date}</p>
            </div>
            
            <div class="row-info">
                <span class="label">نام دانش‌آموز:</span>
                <span class="value">{display_name(student, 'نامشخص')}</span>
            </div>
            <div class="row-info">
                <span class="label">کد دانش‌آموزی:</span>
                <span class="value">{student.student_code or str(100000 + student.id)}</span>
            </div>
            <div class="row-info">
                <span class="label">کد ملی:</span>
                <span class="value">{student.national_code}</span>
            </div>
            
            <div style="margin-top: 15px; border-bottom: 1px solid #00695C; padding-bottom: 5px; font-weight: bold; color: #00695C;">خلاصه تراز مالی آموزشگاه:</div>
            
            <div class="row-info">
                <span class="label">مجموع کل واریزی‌ها:</span>
                <span class="value success-val">{total_paid_institute:,} تومان</span>
            </div>
            <div class="row-info">
                <span class="label">مانده بدهی تجمیعی کیف/ledger:</span>
                <span class="value highlight">{total_debt_institute:,} تومان</span>
            </div>

            <div style="margin-top: 15px; border-bottom: 1px solid #00695C; padding-bottom: 5px; font-weight: bold; color: #00695C;">تفکیک بدهی هر کلاس و معلم:</div>
            {class_rows_html}
            
            <div class="card-box">
                <div class="label" style="color: #2E7D32;">شماره کارت جهت واریز بدهی:</div>
                <p class="card-number">{card_num}</p>
            </div>
            
            <div class="footer">
                <p>{footer}</p>
                <p style="font-size: 9px; color: #888888;">آدرس: {address} | تلفن: {phone}</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content


@router.get("/reports/student_profile/print", response_class=HTMLResponse)
def print_student_profile(
    student_id: int,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    role: str = Depends(check_user_login)
):
    # FIX (L14/Y1): صورت‌حساب/چاپ هر شاگرد — فقط ادمین/منشی، معلمِ درگیر، خودِ شاگرد/ولیِ همان فرزند.
    check_student_access(student_id, authorization, db, role)
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        return "<h3>دانش‌آموز یافت نشد</h3>"

    # FIX: Bug 12 - exclude archived Transaction rows from this active view.
    total_paid_institute = db.query(func.sum(Transaction.amount)).filter(Transaction.is_deleted == False, Transaction.is_reversed == False).filter(
        Transaction.student_id == student_id,
        Transaction.target_wallet == "institute",
        Transaction.amount > 0
    ).scalar() or 0

    wallet_inst = student.wallet_institute if student.wallet_institute is not None else 0
    total_debt_institute = abs(wallet_inst) if wallet_inst < 0 else 0

    teachers_financial = []
    for en in student.enrollments:
        # FIX: Bug 13 - archived enrollment links remain available, but not in active balances.
        if en.is_deleted or not en.course:
            continue
        course = en.course
        teacher = db.query(Teacher).filter(Teacher.id == course.teacher_id).first()
        teacher_name = display_name(teacher, "نامشخص") if teacher else "بدون معلم"
        
        # Use the same enrollment-scoped source as the in-app profile and
        # statement. A course_id-only aggregate can merge two enrollments that
        # share a teacher, while the helper keeps payment and charge ownership
        # tied to the actual enrollment/session.
        breakdown = calculate_enrollment_debt_breakdown(db, en)
        teachers_financial.append({
            "course_title": course.title,
            "teacher_name": teacher_name,
            "paid_teacher": int(breakdown["paid_teacher"] or 0),
            "paid_institute": int(breakdown["paid_institute"] or 0),
            "debt_teacher": int(breakdown["debt_teacher"] or 0),
            "debt_institute": int(breakdown["debt_institute"] or 0),
            "debt": int(breakdown["debt"] or 0),
        })

    class_paid_institute = sum(row["paid_institute"] for row in teachers_financial)
    class_debt_institute = sum(row["debt_institute"] for row in teachers_financial)
    unassigned_debt = max(0, int(calculate_student_debt(db, student)) - sum(row["debt"] for row in teachers_financial))
    if unassigned_debt:
        teachers_financial.append({
            "course_title": "بدون کلاس / بدهی عمومی",
            "teacher_name": "بدون معلم",
            "paid_teacher": 0,
            "paid_institute": 0,
            "debt_teacher": 0,
            "debt_institute": unassigned_debt,
            "debt": unassigned_debt,
        })
    # These two headline values are now class-scoped. The legacy wallet is not
    # displayed as if it belonged to one of the classes.
    total_paid_institute = class_paid_institute
    total_debt_institute = class_debt_institute + unassigned_debt

    settings = db.query(InstituteSettings).first()
    if not settings:
        settings = InstituteSettings()

    inst_name = settings.name
    address = settings.address
    phone = settings.phone
    footer = settings.footer_text

    current_date = datetime.datetime.now().strftime("%Y/%m/%d %H:%M")

    teachers_html_rows = ""
    for tf in teachers_financial:
        teachers_html_rows += f"""
        <div class="teacher-block" style="border: 1px solid #e0e0e0; border-radius: 4px; padding: 8px; margin-bottom: 8px; background-color: #fafafa;">
            <div class="row-info" style="font-weight: bold; border-bottom: 1px solid #eee; padding-bottom: 4px; margin-bottom: 4px;">
                <span>{tf['course_title']} ({tf['teacher_name']})</span>
            </div>
            <div class="row-info">
                <span class="label">واریزی به معلم:</span>
                <span class="value success-val" style="color: #388E3C; font-weight: bold;">{tf['paid_teacher']:,} تومان</span>
            </div>
            <div class="row-info">
                <span class="label">واریزی به آموزشگاه:</span>
                <span class="value success-val" style="color: #388E3C; font-weight: bold;">{tf['paid_institute']:,} تومان</span>
            </div>
            <div class="row-info">
                <span class="label">بدهی به معلم:</span>
                <span class="value highlight" style="color: #D32F2F; font-weight: bold;">{tf['debt_teacher']:,} تومان</span>
            </div>
            <div class="row-info">
                <span class="label">بدهی به آموزشگاه:</span>
                <span class="value highlight" style="color: #D32F2F; font-weight: bold;">{tf['debt_institute']:,} تومان</span>
            </div>
        </div>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>خلاصه‌ی اطلاعات دانش‌آموز</title>
        <style>
            @font-face {{
                font-family: 'Tahoma';
                src: local('Tahoma');
            }}
            body {{
                font-family: 'Tahoma', sans-serif;
                margin: 0;
                padding: 10px;
                color: #212121;
                background-color: #ffffff;
                font-size: 13px;
                line-height: 1.6;
            }}
            .ticket {{
                max-width: 450px;
                margin: 0 auto;
                padding: 15px;
                border: 1px dashed #00695C;
                border-radius: 8px;
            }}
            .header {{
                text-align: center;
                border-bottom: 2px dashed #00695C;
                padding-bottom: 10px;
                margin-bottom: 15px;
            }}
            .header h2 {{
                margin: 5px 0;
                font-size: 16px;
                color: #00695C;
            }}
            .header p {{
                margin: 3px 0;
                font-size: 11px;
                color: #666666;
            }}
            .section-title {{
                margin-top: 15px;
                margin-bottom: 8px;
                border-bottom: 1px solid #00695C;
                padding-bottom: 4px;
                font-weight: bold;
                color: #00695C;
            }}
            .row-info {{
                display: flex;
                justify-content: space-between;
                margin: 6px 0;
                border-bottom: 1px dotted #eeeeee;
                padding-bottom: 3px;
            }}
            .label {{
                font-weight: bold;
                color: #555555;
            }}
            .value {{
                color: #000000;
            }}
            .highlight {{
                color: #D32F2F;
                font-weight: bold;
            }}
            .success-val {{
                color: #388E3C;
                font-weight: bold;
            }}
            .footer {{
                text-align: center;
                border-top: 2px dashed #00695C;
                padding-top: 10px;
                margin-top: 20px;
                font-size: 11px;
            }}
            @media print {{
                body {{
                    padding: 0;
                }}
                .ticket {{
                    border: none;
                    max-width: 100%;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="ticket">
            <div class="header">
                <h2>{inst_name}</h2>
                <p>خلاصه اطلاعات هویتی و تراز مالی جدید دانش‌آموز</p>
                <p>تاریخ گزارش: {current_date}</p>
            </div>
            
            <div class="section-title">مشخصات هویتی</div>
            <div class="row-info">
                <span class="label">نام و نام خانوادگی:</span>
                <span class="value" style="font-weight: bold;">{display_name(student, 'نامشخص')}</span>
            </div>
            <div class="row-info">
                <span class="label">کد دانش‌آموزی:</span>
                <span class="value">{student.student_code or str(100000 + student.id)}</span>
            </div>
            <div class="row-info">
                <span class="label">کد ملی:</span>
                <span class="value">{student.national_code}</span>
            </div>
            <div class="row-info">
                <span class="label">نام پدر:</span>
                <span class="value">{student.father_name or "---"}</span>
            </div>
            <div class="row-info">
                <span class="label">تاریخ تولد:</span>
                <span class="value">{student.birth_date or "---"}</span>
            </div>
            <div class="row-info">
                <span class="label">موبایل ۱ (دانش‌آموز):</span>
                <span class="value">{student.student_mobile}</span>
            </div>
            <div class="row-info">
                <span class="label">موبایل ۲ (والدین):</span>
                <span class="value">{student.parent_mobile or "---"}</span>
            </div>
            
            <div class="section-title">تراز مالی آموزشگاه</div>
            <div class="row-info">
                <span class="label">کل واریزی‌ها به آموزشگاه:</span>
                <span class="value success-val">{total_paid_institute:,} تومان</span>
            </div>
            <div class="row-info">
                <span class="label">بدهی آموزشگاه در کلاس‌ها/بدون انتساب:</span>
                <span class="value highlight">{total_debt_institute:,} تومان</span>
            </div>
            
            <div class="section-title">تراز مالی معلمان</div>
            {teachers_html_rows if teachers_html_rows else "<p style='color:#888; text-align:center;'>کلاس ثبت‌نام شده‌ای وجود ندارد</p>"}
            
            <div class="footer">
                <p>{footer}</p>
                <p style="font-size: 9px; color: #888888;">آدرس: {address} | تلفن: {phone}</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content
