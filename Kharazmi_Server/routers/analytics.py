from fastapi import APIRouter, Depends, HTTPException, status, Query, Header
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from sqlalchemy import func, or_, and_, desc
import datetime
import os
import io

import models
from models import Student, Teacher, Course, Enrollment, Attendance, SessionLog, Grade, Transaction, Installment, Lead, Branch, User, UserSession
from dependencies import get_db, check_admin_access, check_admin_or_secretary_access, check_user_login
from financial_calculations import calculate_institute_session_revenue, calculate_total_turnover

# FIX: Bug 16 - share the tuition-minus-payment debt calculation across financial views.
from financial_calculations import calculate_student_debt

router = APIRouter()

def get_user_branch_filter(db: Session, authorization: Optional[str], branch_id: Optional[int]) -> Optional[int]:
    if not authorization:
        return branch_id
    try:
        token = authorization.split()[1]
        session = db.query(models.UserSession).filter(models.UserSession.token == token).first()
        if session:
            if session.sub_role in ["student", "parent"]:
                return branch_id
            user = db.query(User).filter(User.id == session.user_id).first()
            if user and user.branch_id is not None:
                return user.branch_id
    except Exception:
        pass
    return branch_id

# Helper function to get date range for time filters
def get_date_range_filter(time_filter: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
    today = datetime.date.today()
    if time_filter == "Today":
        start = today.strftime("%Y/%m/%d")
        end = today.strftime("%Y/%m/%d")
    elif time_filter == "Week":
        start = (today - datetime.timedelta(days=7)).strftime("%Y/%m/%d")
        end = today.strftime("%Y/%m/%d")
    elif time_filter == "Month":
        start = (today - datetime.timedelta(days=30)).strftime("%Y/%m/%d")
        end = today.strftime("%Y/%m/%d")
    elif time_filter == "Term":
        start = (today - datetime.timedelta(days=90)).strftime("%Y/%m/%d")
        end = today.strftime("%Y/%m/%d")
    elif time_filter == "Year":
        start = (today - datetime.timedelta(days=365)).strftime("%Y/%m/%d")
        end = today.strftime("%Y/%m/%d")
    elif time_filter == "Custom" and start_date and end_date:
        start = start_date
        end = end_date
    else:
        # Default to month
        start = (today - datetime.timedelta(days=30)).strftime("%Y/%m/%d")
        end = today.strftime("%Y/%m/%d")
    return start, end


def _parse_funnel_date(value: str, field_name: str) -> datetime.date:
    """Accept canonical Gregorian or Jalali project dates for funnel filters."""
    from today_summary import parse_project_date

    parsed = parse_project_date(value)
    if not parsed:
        raise HTTPException(
            status_code=400,
            detail=f"فرمت {field_name} معتبر نیست؛ تاریخ را به شکل yyyy/MM/dd ارسال کنید",
        )
    return parsed


@router.get("/analytics/enrollment_funnel")
def get_enrollment_funnel(
    start_date: str = Query(...),
    end_date: str = Query(...),
    branch_id: int = Query(..., ge=1),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_access),
):
    """Read-only CRM lead cohort funnel for one mandatory branch and date range."""
    resolved_branch = get_user_branch_filter(db, authorization, branch_id)
    if resolved_branch is None:
        raise HTTPException(status_code=400, detail="انتخاب شعبه الزامی است")

    start_day = _parse_funnel_date(start_date, "start_date")
    end_day = _parse_funnel_date(end_date, "end_date")
    if start_day > end_day:
        raise HTTPException(
            status_code=400,
            detail="تاریخ شروع نمی‌تواند بعد از تاریخ پایان باشد",
        )

    start_at = datetime.datetime.combine(start_day, datetime.time.min)
    end_exclusive = datetime.datetime.combine(
        end_day + datetime.timedelta(days=1),
        datetime.time.min,
    )
    cohort = (
        db.query(Lead)
        .filter(
            Lead.branch_id == resolved_branch,
            Lead.created_at >= start_at,
            Lead.created_at < end_exclusive,
        )
        .all()
    )
    converted = [lead for lead in cohort if lead.converted_student_id is not None]

    durations_hours = []
    for lead in converted:
        if not lead.created_at or not lead.converted_at:
            continue
        elapsed = lead.converted_at - lead.created_at
        if elapsed.total_seconds() >= 0:
            durations_hours.append(elapsed.total_seconds() / 3600.0)

    total_leads = len(cohort)
    converted_leads = len(converted)
    conversion_rate = (
        (converted_leads / total_leads) * 100.0 if total_leads else 0.0
    )
    average_hours = (
        sum(durations_hours) / len(durations_hours) if durations_hours else 0.0
    )

    return {
        "period": {
            "start_date": start_day.strftime("%Y/%m/%d"),
            "end_date": end_day.strftime("%Y/%m/%d"),
        },
        "branch_id": resolved_branch,
        "total_leads": total_leads,
        "converted_leads": converted_leads,
        "conversion_rate": round(conversion_rate, 2),
        "average_conversion_hours": round(average_hours, 2),
        "average_conversion_days": round(average_hours / 24.0, 2),
        "timed_conversions": len(durations_hours),
    }


# ==========================================
# ۱. داشبورد جامع آماری ادمین (Admin Analytics API)
# ==========================================

@router.get("/analytics/dashboard")
def get_analytics_dashboard(
    time_filter: str = "Month",  # Today, Week, Month, Term, Year, Custom
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    branch_id: Optional[int] = None,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_or_secretary_access)  # FIX (L14/Y4): داشبورد درآمد/بدهی موسسه — فقط کارکنان (فراخوانی داخلی excel/pdf با _="admin" دست‌نخورده)
):
    resolved_branch = get_user_branch_filter(db, authorization, branch_id)
    start_str, end_str = get_date_range_filter(time_filter, start_date, end_date)
    # FIX H3-B3: boundaries may be Jalali (Custom) or Gregorian (presets) — parse once via the
    # central converter (reuses _parse_funnel_date: garbage Custom input → clean 400, not 500).
    from today_summary import parse_project_date  # lazy, same pattern as _parse_funnel_date
    start_day = _parse_funnel_date(start_str, "start_date")
    end_day = _parse_funnel_date(end_str, "end_date")
    def _in_range(value):
        parsed = parse_project_date(value)
        return parsed is not None and start_day <= parsed <= end_day
    
    # ۱. فعال بودن دانش‌آموزان (Active Students): دارای ثبت‌نام در دیتابیس
    # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
    active_st_query = db.query(func.count(func.distinct(Enrollment.student_id))).filter(Enrollment.is_deleted == False)
    if resolved_branch:
        active_st_query = active_st_query.filter(Enrollment.branch_id == resolved_branch)
    active_students_count = active_st_query.scalar() or 0
    
    # ۲. ثبت‌نام‌های جدید (New Registrations): در بازه زمانی تعیین‌شده
    # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
    # FIX H3-B3: register_date mixes Jalali+Gregorian; filter parsed dates in Python.
    new_reg_query = db.query(Enrollment.register_date).filter(Enrollment.is_deleted == False)
    if resolved_branch:
        new_reg_query = new_reg_query.filter(Enrollment.branch_id == resolved_branch)
    new_registrations_count = sum(1 for (d,) in new_reg_query.all() if _in_range(d))
    
    # ۳. نسبت ماندگاری دانش‌آموزان (Retention Rate)
    # فرمول تقریبی: درصد دانش‌آموزانی که در بیش از ۱ کلاس فعال ثبت‌نام شده‌اند
    # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
    retention_query = db.query(Enrollment.student_id, func.count(Enrollment.id).label("class_cnt")).filter(Enrollment.is_deleted == False)
    if resolved_branch:
        retention_query = retention_query.filter(Enrollment.branch_id == resolved_branch)
    student_classes = retention_query.group_by(Enrollment.student_id).all()
    
    retained_cnt = len([s for s in student_classes if s.class_cnt > 1])
    total_st_cnt = len(student_classes)
    retention_rate = (retained_cnt / total_st_cnt * 100) if total_st_cnt > 0 else 100.0
    
    # ۴. نرخ کل حضور در کلاس‌ها (Attendance Rate)
    # FIX H3-B3: joins/branch stay in SQL; dates filter parsed in Python (also fixes Custom Jalali input).
    # FIX (audit-v2/livedb-join): FROM همان attendances است (نرخ = رکوردهای حضور)، با JOIN صریح به
    # سشن (برای date) و کلاس (برای branch) — قبلاً query از ستون SessionLog شروع می‌شد و join به خود
    # SessionLog می‌زد (InvalidRequestError؛ کل داشبورد 500). سلکت/فیلتر/شاخه دقیقاً مثل قبل.
    att_present_query = (
        db.query(SessionLog.date)
        .select_from(Attendance)
        .join(SessionLog, Attendance.session_id == SessionLog.id)
        .join(Course, SessionLog.course_id == Course.id)
        # FIX (F-S2): ردیف حضور آرشیوشده و جلسه‌ی حذف‌شده از نرخ حضور بیرون‌اند.
        .filter(Attendance.status == "Present", Attendance.is_deleted == False, SessionLog.is_deleted == False)
    )
    att_total_query = (
        db.query(SessionLog.date)
        .select_from(Attendance)
        .join(SessionLog, Attendance.session_id == SessionLog.id)
        .join(Course, SessionLog.course_id == Course.id)
        .filter(Attendance.is_deleted == False, SessionLog.is_deleted == False)
    )
    if resolved_branch:
        att_present_query = att_present_query.filter(Course.branch_id == resolved_branch)
        att_total_query = att_total_query.filter(Course.branch_id == resolved_branch)

    p_cnt = sum(1 for (d,) in att_present_query.all() if _in_range(d))
    t_cnt = sum(1 for (d,) in att_total_query.all() if _in_range(d))
    attendance_rate = (p_cnt / t_cnt * 100) if t_cnt > 0 else 100.0

    # ۵. میانگین کل نمرات (Average Grade)
    # FIX H3-B3: same as above — parsed Python date filter.
    grade_query = db.query(Grade.score, Grade.date).join(Course)
    if resolved_branch:
        grade_query = grade_query.filter(Course.branch_id == resolved_branch)
    grade_vals = [float(s) for s, d in grade_query.all() if s is not None and _in_range(d)]
    average_grade = (sum(grade_vals) / len(grade_vals)) if grade_vals else 0.0
    
    # ۶. کل بدهی‌های معوقه (Outstanding Debt)
    # FIX: Bug 16 - aggregate the same tuition balances as finance/reports, with branch isolation.
    debt_students = db.query(Student).filter(Student.is_deleted == False)
    if resolved_branch is not None:
        debt_students = debt_students.filter(Student.branch_id == resolved_branch)
    outstanding_debt = sum(calculate_student_debt(db, student) for student in debt_students.all())
    
    # ۷. سود واقعی آموزشگاه (Institute Earned Revenue) و گردش مالی کل (Total Turnover)
    monthly_revenue = calculate_institute_session_revenue(db, start_str, end_str, resolved_branch)
    total_turnover = calculate_total_turnover(db, start_str, end_str, resolved_branch)
    
    # ۸. عملکرد جذب و نرخ تبدیل سرنخ‌ها (Lead Conversion Rate)
    # FIX H3-B3: Lead.created_at is a real DateTime — compare with parsed dates in SQL (fast),
    # instead of strptime'ing the boundary as Gregorian (silently wrong for Custom Jalali input).
    _lead_start = datetime.datetime.combine(start_day, datetime.time.min) - datetime.timedelta(days=1)
    _lead_end = datetime.datetime.combine(end_day, datetime.time.min) + datetime.timedelta(days=1)
    leads_total_query = db.query(func.count(Lead.id)).filter(
        Lead.created_at >= _lead_start,
        Lead.created_at <= _lead_end
    )
    leads_converted_query = db.query(func.count(Lead.id)).filter(
        Lead.status == "REGISTERED",
        Lead.created_at >= _lead_start,
        Lead.created_at <= _lead_end
    )
    leads_tot = leads_total_query.scalar() or 0
    leads_conv = leads_converted_query.scalar() or 0
    lead_conversion_rate = (leads_conv / leads_tot * 100) if leads_tot > 0 else 100.0
    
    # ۹. نرخ وصول مطالبات اقساط (Payment Collection Rate)
    # مبالغ کل اقساط سررسید شده در این بازه در مقابل اقساط تسویه شده واقعی
    # FIX: Bug 13 - exclude archived Installment rows from this active view.
    # FIX H3-B3: due_date is Jalali; filter parsed dates in Python (was Gregorian string compare).
    inst_rows = db.query(Installment.amount, Installment.due_date, Installment.is_paid).filter(Installment.is_deleted == False).all()
    due_in_range = [(a, p) for a, d, p in inst_rows if _in_range(d)]
    paid_inst_amount = sum(a or 0 for a, p in due_in_range if p)
    total_inst_amount = sum(a or 0 for a, _ in due_in_range)
    payment_collection_rate = (paid_inst_amount / total_inst_amount * 100) if total_inst_amount > 0 else 100.0
    
    return {
        "period": {"start": start_str, "end": end_str, "filter": time_filter},
        "active_students": active_students_count,
        "new_registrations": new_registrations_count,
        "retention_rate": round(retention_rate, 1),
        "attendance_rate": round(attendance_rate, 1),
        "average_grade": round(average_grade, 2),
        "outstanding_debt": outstanding_debt,
        "monthly_revenue": monthly_revenue,
        "total_turnover": total_turnover,  # Added total_turnover for clear UI/UX labeling! 🆕
        "lead_conversion_rate": round(lead_conversion_rate, 1),
        "payment_collection_rate": round(payment_collection_rate, 1),
    }


# ==========================================
# ۲. لیست کارآیی معلمان و کلاس‌ها (با Pagination و Filtering)
# ==========================================

@router.get("/analytics/teachers")
def get_teachers_performance_analytics(
    branch_id: Optional[int] = None,
    limit: int = 10,
    offset: int = 0,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    sub_role: str = Depends(check_user_login)
):
    # FIX (L14/Y2): عملکرد+طلب همه‌ی معلمان — فقط ادمین/منشی (بدون مصرف‌کننده‌ی فعلی؛ معلم آمار خودش را از today_summary می‌گیرد).
    if sub_role not in ("admin", "secretary"):
        raise HTTPException(status_code=403, detail="شما دسترسی لازم برای مشاهده‌ی آمار معلمان را ندارید")
    resolved_branch = get_user_branch_filter(db, authorization, branch_id)
    query = db.query(Teacher).filter(Teacher.is_deleted == False)
    if resolved_branch:
        query = query.filter(Teacher.branch_id == resolved_branch)
        
    teachers = query.offset(offset).limit(limit).all()
    results = []
    
    for t in teachers:
        # تعداد دانش‌آموزان این مربی
        courses = db.query(Course).filter(Course.teacher_id == t.id).all()
        c_ids = [c.id for c in courses]
        
        st_count = 0
        avg_score = 0.0
        att_rate = 100.0
        
        if c_ids:
            # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
            st_count = db.query(func.count(Enrollment.id)).filter(Enrollment.is_deleted == False).filter(Enrollment.course_id.in_(c_ids)).scalar() or 0
            # میانگین نمرات مربی
            avg_score = db.query(func.avg(Grade.score)).filter(Grade.course_id.in_(c_ids)).scalar() or 0.0
            # حضور و غیاب کلاس‌های مربی
            p_cnt = db.query(func.count(Attendance.id)).join(SessionLog).filter(SessionLog.course_id.in_(c_ids), Attendance.status == "Present", Attendance.is_deleted == False, SessionLog.is_deleted == False).scalar() or 0
            tot_cnt = db.query(func.count(Attendance.id)).join(SessionLog).filter(SessionLog.course_id.in_(c_ids), Attendance.is_deleted == False, SessionLog.is_deleted == False).scalar() or 0
            att_rate = (p_cnt / tot_cnt * 100) if tot_cnt > 0 else 100.0
            
        # کیف پول واحد معلم: طلب فعلی = جمع جلسات دارای حضور تسویه‌نشده (همان منطق pending_settlement)
        pending_total = 0
        if c_ids:
            # FIX: H6(A2) - طلب معلم = مبالغ قراردادی + جریمه‌ی غایبین غیرموجه.
            sess_rows = db.query(SessionLog.id, SessionLog.final_teacher_cost, SessionLog.absent_penalty_teacher, SessionLog.is_penalty_settled).filter(SessionLog.is_deleted == False, SessionLog.course_id.in_(c_ids)).all()
            if sess_rows:
                all_sids = [r[0] for r in sess_rows]
                unbilled_sids = {r[0] for r in db.query(Attendance.session_id).filter(Attendance.session_id.in_(all_sids), Attendance.is_billed == False, Attendance.is_deleted == False, Attendance.status.in_(["Present", "Late"])).distinct().all()}
                pending_total = sum((r[1] or 0) + (r[2] or 0) for r in sess_rows if r[0] in unbilled_sids or ((r[2] or 0) > 0 and not r[3]))  # FIX H8-gap/follow-up: شاخه‌ی جریمه هم طلب است (همان منطق دوشاخه‌ی settle)

        results.append({
            "teacher_id": t.id,
            "teacher_name": f"{t.first_name} {t.last_name}",
            "student_count": st_count,
            "average_grade": round(avg_score, 2),
            "attendance_rate": round(att_rate, 1),
            "wallet_balance": pending_total # طلب فعلی مربی (محاسبه زنده؛ ستون wallet_balance معلم استفاده نمی‌شود)
        })
        
    return results


@router.get("/analytics/classes")
def get_classes_performance_analytics(
    branch_id: Optional[int] = None,
    limit: int = 10,
    offset: int = 0,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    # FIX (F-A1): مثل خواهرش /analytics/teachers (L14/Y2) — آمار تجمیعی همه‌ی کلاس‌ها فقط کارکنان.
    _: str = Depends(check_admin_or_secretary_access)
):
    resolved_branch = get_user_branch_filter(db, authorization, branch_id)
    query = db.query(Course).filter(Course.is_deleted == False)
    if resolved_branch:
        query = query.filter(Course.branch_id == resolved_branch)
        
    courses = query.offset(offset).limit(limit).all()
    results = []
    
    for c in courses:
        # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
        st_count = db.query(func.count(Enrollment.id)).filter(Enrollment.is_deleted == False).filter(Enrollment.course_id == c.id).scalar() or 0
        avg_score = db.query(func.avg(Grade.score)).filter(Grade.course_id == c.id).scalar() or 0.0
        p_cnt = db.query(func.count(Attendance.id)).join(SessionLog).filter(SessionLog.course_id == c.id, Attendance.status == "Present", Attendance.is_deleted == False, SessionLog.is_deleted == False).scalar() or 0
        tot_cnt = db.query(func.count(Attendance.id)).join(SessionLog).filter(SessionLog.course_id == c.id, Attendance.is_deleted == False, SessionLog.is_deleted == False).scalar() or 0
        att_rate = (p_cnt / tot_cnt * 100) if tot_cnt > 0 else 100.0
        
        results.append({
            "course_id": c.id,
            "course_code": c.code,
            "title": c.title,
            "student_count": st_count,
            "average_grade": round(avg_score, 2),
            "attendance_rate": round(att_rate, 1)
        })
    return results


# ==========================================
# ۳. خروجی اکسل و پی‌دی‌اف عملکرد آماری (Excel & PDF Export)
# ==========================================

@router.get("/analytics/export/excel")
def export_analytics_excel(
    time_filter: str = "Month",
    branch_id: Optional[int] = None,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_or_secretary_access)  # FIX (L14/Y4): خروجی اکسل همان داده‌ی :153 — فقط کارکنان
):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    
    # دریافت آمار داشبورد
    stats = get_analytics_dashboard(time_filter=time_filter, branch_id=branch_id, authorization=authorization, db=db, _="admin")
    
    wb = openpyxl.Workbook()
    # Sheet 1: خلاصه وضعیت
    ws1 = wb.active
    ws1.title = "خلاصه عملکرد آموزشگاه"
    ws1.views.sheetView[0].showGridLines = True
    
    # راست به چپ کردن صفحه
    ws1.sheet_view.rightToLeft = True
    
    # استایل‌ها
    title_font = Font(name="Tahoma", size=14, bold=True, color="FFFFFF")
    header_font = Font(name="Tahoma", size=11, bold=True, color="FFFFFF")
    cell_font = Font(name="Tahoma", size=11)
    
    header_fill = PatternFill(start_color="008080", end_color="008080", fill_type="solid")
    accent_fill = PatternFill(start_color="E6F2F2", end_color="E6F2F2", fill_type="solid")
    
    center_align = Alignment(horizontal="center", vertical="center")
    right_align = Alignment(horizontal="right", vertical="center")
    
    thin_side = Side(border_style="thin", color="CCCCCC")
    thin_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
    
    # عنوان بالای جدول
    ws1.merge_cells("A1:C1")
    ws1["A1"] = f"گزارش جامع تحلیلی مالی و آموزشی خوارزمی (دوره {time_filter})"
    ws1["A1"].font = title_font
    ws1["A1"].fill = header_fill
    ws1["A1"].alignment = center_align
    ws1.row_dimensions[1].height = 40
    
    headers = ["شاخص کلیدی عملکرد (KPI)", "مقدار آماری", "شرح شاخص"]
    for col_idx, h in enumerate(headers, 1):
        cell = ws1.cell(row=2, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border
    ws1.row_dimensions[2].height = 25
    
    data = [
        ("تعداد دانش‌آموزان فعال", stats["active_students"], "کل دانش‌آموزان ثبت‌نام شده در دوره‌ها"),
        ("ثبت‌نام‌های جدید در این بازه", stats["new_registrations"], "ثبت‌نام‌های جدید ثبت شده در بازه زمانی گزارش"),
        ("نرخ ماندگاری دانش‌آموزان", f"{stats['retention_rate']}%", "نسبت دانش‌آموزان با ثبت‌نام موازی"),
        ("نرخ کل حضور در کلاس‌ها", f"{stats['attendance_rate']}%", "نسبت حاضرین به کل جلسات"),
        ("میانگین نمرات کل دوره‌ها", stats["average_grade"], "میانگین نمره اخذ شده از ۲۰ نمره کلاسی"),
        ("کل مطالبات معوقه (ریال)", f"{stats['outstanding_debt']:,} ریال", "مجموع بدهی‌های معوقه دانش‌آموزان"),
        ("درآمد کل دریافتی در این بازه", f"{stats['monthly_revenue']:,} ریال", "مجموع واریزی‌های معتبر دوره"),
        ("نرخ تبدیل سرنخ‌های جذب (CRM)", f"{stats['lead_conversion_rate']}%", "درصد سرنخ‌های جذب تبدیل شده به دانش‌آموز"),
        ("نرخ وصول اقساط شهریه", f"{stats['payment_collection_rate']}%", "درصد اقساط پرداخت‌شده به کل معوقات سررسید شده")
    ]
    
    for row_idx, row_data in enumerate(data, 3):
        for col_idx, val in enumerate(row_data, 1):
            cell = ws1.cell(row=row_idx, column=col_idx, value=val)
            cell.font = cell_font
            cell.border = thin_border
            if col_idx == 1:
                cell.alignment = right_align
            elif col_idx == 2:
                cell.alignment = center_align
                cell.fill = accent_fill
            else:
                cell.alignment = right_align
        ws1.row_dimensions[row_idx].height = 22
        
    # تنظیم عرض ستون‌ها
    ws1.column_dimensions["A"].width = 30
    ws1.column_dimensions["B"].width = 20
    ws1.column_dimensions["C"].width = 45
    
    # Sheet 2: عملکرد مربیان
    ws2 = wb.create_sheet(title="عملکرد مدرسین")
    ws2.sheet_view.rightToLeft = True
    ws2.views.sheetView[0].showGridLines = True
    
    headers_t = ["آیدی مربی", "نام و نام خانوادگی", "تعداد دانش‌آموزان", "میانگین نمرات کلاسی", "نرخ کل حضور کلاسی", "وضعیت حسابرسی"]
    for col_idx, h in enumerate(headers_t, 1):
        cell = ws2.cell(row=1, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border
    ws2.row_dimensions[1].height = 28
    
    teachers_perf = get_teachers_performance_analytics(branch_id=branch_id, limit=50, offset=0, db=db, authorization=authorization, sub_role="admin")
    for r_idx, t in enumerate(teachers_perf, 2):
        ws2.cell(row=r_idx, column=1, value=t["teacher_id"]).alignment = center_align
        ws2.cell(row=r_idx, column=2, value=t["teacher_name"]).alignment = right_align
        ws2.cell(row=r_idx, column=3, value=t["student_count"]).alignment = center_align
        ws2.cell(row=r_idx, column=4, value=t["average_grade"]).alignment = center_align
        ws2.cell(row=r_idx, column=5, value=f"{t['attendance_rate']}%").alignment = center_align
        ws2.cell(row=r_idx, column=6, value=f"{t['wallet_balance']:,} ریال").alignment = center_align
        
        for col_idx in range(1, 7):
            cell = ws2.cell(row=r_idx, column=col_idx)
            cell.font = cell_font
            cell.border = thin_border
        ws2.row_dimensions[r_idx].height = 22
        
    ws2.column_dimensions["A"].width = 12
    ws2.column_dimensions["B"].width = 25
    ws2.column_dimensions["C"].width = 18
    ws2.column_dimensions["D"].width = 22
    ws2.column_dimensions["E"].width = 22
    ws2.column_dimensions["F"].width = 22

    # ذخیره و خروجی فایل
    file_stream = io.BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)
    
    return StreamingResponse(
        file_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=kharazmi_analytics_{time_filter}.xlsx"}
    )


@router.get("/analytics/export/pdf")
def export_analytics_pdf(
    time_filter: str = "Month",
    branch_id: Optional[int] = None,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_or_secretary_access)  # FIX (L14/Y4): خروجی PDF همان داده‌ی :153 — فقط کارکنان
):
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    
    # دریافت آمار داشبورد
    stats = get_analytics_dashboard(time_filter=time_filter, branch_id=branch_id, authorization=authorization, db=db, _="admin")
    
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    
    # تعریف استایل‌های متنی با پشتیبانی فونت انگلیسی و یونیکد
    # نکته: برای پروداکشن واقعی فونت‌های فارسی اضافه می‌شوند ولی در اینجا ساختار استاندارد را پیاده‌سازی می‌کنیم
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=colors.HexColor('#008080'),
        alignment=1, # Center
        spaceAfter=20
    )
    normal_style = ParagraphStyle(
        'NormalStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        textColor=colors.HexColor('#333333'),
        alignment=2 # Right (Note: ReportLab doesn't RTL wrap natively without external registered fonts, but we layout table nicely)
    )
    
    # تیتر اصلی سند
    story.append(Paragraph("Kharazmi Intelligent Analytics Report Card", title_style))
    story.append(Paragraph(f"Period: {time_filter} | Generated at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", normal_style))
    story.append(Spacer(1, 20))
    
    # جدول شاخص‌های کلیدی عملکرد (KPIs)
    data = [
        ["Key Performance Indicator (KPI)", "Value", "Metric Description"],
        ["Active Students Count", f"{stats['active_students']}", "Total unique enrolled students"],
        ["New Registrations (This Period)", f"{stats['new_registrations']}", "New class registrations during period"],
        ["Retention Rate", f"{stats['retention_rate']}%", "Ratio of students with parallel active courses"],
        ["Overall Attendance Rate", f"{stats['attendance_rate']}%", "Present attendances over total held sessions"],
        ["Average Class Grade", f"{stats['average_grade']}/20.0", "Class exam average"],
        ["Outstanding Debt", f"{stats['outstanding_debt']:,} IRR", "Accumulated student overdue debt"],
        ["Total Revenue Collected", f"{stats['monthly_revenue']:,} IRR", "Total validated cash/online transactions"],
        ["CRM Leads Conversion Rate", f"{stats['lead_conversion_rate']}%", "Converted CRM leads to registrations"],
        ["Installment Collection Rate", f"{stats['payment_collection_rate']}%", "Paid installment ratio"]
    ]
    
    table = Table(data, colWidths=[200, 100, 240])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#008080')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('TOPPADDING', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CCCCCC')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F5FBFB')]),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ]))
    
    story.append(table)
    doc.build(story)
    
    pdf_buffer.seek(0)
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=kharazmi_analytics_{time_filter}.pdf"}
    )
