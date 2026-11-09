"""Shared calculations for the real-time "Today" dashboards.

This module is read-only: it never mutates attendance, live-session, or financial
records.  Keeping these calculations outside the routers also makes the date and
schedule rules directly unit-testable.
"""

import datetime
import re
import time
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from models import (
    Attendance,
    Course,
    Enrollment,
    Installment,
    InstituteSettings,
    LiveSession,
    SessionLog,
    Settlement,
    Student,
    Teacher,
    Transaction,
)


PERSIAN_DAY_NAMES = {
    0: "دوشنبه",
    1: "سه‌شنبه",
    2: "چهارشنبه",
    3: "پنجشنبه",
    4: "جمعه",
    5: "شنبه",
    6: "یکشنبه",
}

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_DAY_ALIASES = {
    "پنج	شنبه": "پنجشنبه",
    "پنج شنبه": "پنجشنبه",
    "پنج‌شنبه": "پنجشنبه",
    "سه شنبه": "سه‌شنبه",
    "سه	شنبه": "سه‌شنبه",
}


def gregorian_to_jalali(date_value: datetime.date) -> Tuple[int, int, int]:
    """Convert a Gregorian date to its canonical Jalali year, month and day."""
    gy, gm, gd = date_value.year, date_value.month, date_value.day
    cumulative_month_days = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    adjusted_year = gy + 1 if gm > 2 else gy
    days = (
        355666
        + (365 * gy)
        + ((adjusted_year + 3) // 4)
        - ((adjusted_year + 99) // 100)
        + ((adjusted_year + 399) // 400)
        + gd
        + cumulative_month_days[gm - 1]
    )

    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365

    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd


def jalali_date_string(date_value: datetime.date) -> str:
    jy, jm, jd = gregorian_to_jalali(date_value)
    return f"{jy:04d}/{jm:02d}/{jd:02d}"


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> datetime.date:
    """Convert a Jalali date to Gregorian without introducing a new dependency."""
    if not (1 <= jm <= 12 and 1 <= jd <= 31):
        raise ValueError("Invalid Jalali date")

    original = (jy, jm, jd)
    jy += 1595
    days = (
        -355668
        + (365 * jy)
        + ((jy // 33) * 8)
        + (((jy % 33) + 3) // 4)
        + jd
    )
    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += ((jm - 7) * 30) + 186

    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1

    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365

    gd = days + 1
    month_days = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if (gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0:
        month_days[2] = 29

    gm = 1
    while gm <= 12 and gd > month_days[gm]:
        gd -= month_days[gm]
        gm += 1
    result = datetime.date(gy, gm, gd)
    if gregorian_to_jalali(result) != original:
        raise ValueError("Invalid Jalali date")
    return result


def parse_project_date(value: Optional[str]) -> Optional[datetime.date]:
    """Parse legacy Jalali or Gregorian date strings, with optional time suffix."""
    normalized = (value or "").translate(_PERSIAN_DIGITS).translate(_ARABIC_DIGITS)
    match = re.search(r"(?<!\d)(\d{4})[/-](\d{1,2})[/-](\d{1,2})(?!\d)", normalized)
    if not match:
        return None
    year, month, day = (int(part) for part in match.groups())
    try:
        if year < 1700:
            return jalali_to_gregorian(year, month, day)
        return datetime.date(year, month, day)
    except (ValueError, IndexError):
        return None


def _normalize_day_text(value: Optional[str]) -> str:
    normalized = (value or "").strip().replace("ي", "ی").replace("ك", "ک")
    for source, target in _DAY_ALIASES.items():
        normalized = normalized.replace(source, target)
    return normalized


def schedule_matches_date(days_of_week: Optional[str], date_value: datetime.date) -> bool:
    """Match one/multiple Persian weekdays plus the project's زوج/فرد shorthand."""
    schedule = _normalize_day_text(days_of_week)
    if not schedule or schedule == "نامشخص":
        return False

    day_name = PERSIAN_DAY_NAMES[date_value.weekday()]

    # Extract longer names first so «شنبه» is not accidentally found inside
    # «یکشنبه»، «دوشنبه» or «چهارشنبه».
    remaining = schedule
    explicit_days = set()
    for candidate in sorted(set(PERSIAN_DAY_NAMES.values()), key=len, reverse=True):
        if candidate in remaining:
            explicit_days.add(candidate)
            remaining = remaining.replace(candidate, " ")
    if day_name in explicit_days:
        return True

    # Existing scheduling code defines زوج as Sat/Mon/Wed and فرد as Sun/Tue/Thu.
    if "زوج" in schedule and date_value.weekday() in (5, 0, 2):
        return True
    if "فرد" in schedule and date_value.weekday() in (6, 1, 3):
        return True
    return False


def parse_schedule_start(class_time: Optional[str]) -> Optional[Tuple[int, int]]:
    """Return the first HH:MM in a class-time value such as 16:00-17:30."""
    value = (class_time or "").translate(_PERSIAN_DIGITS).translate(_ARABIC_DIGITS)
    match = re.search(r"(?<!\d)([01]?\d|2[0-3])\s*[:٫.]\s*([0-5]\d)(?!\d)", value)
    if match:
        return int(match.group(1)), int(match.group(2))

    # Preserve compatibility with existing schedules that contain an hour only.
    match = re.search(r"(?<!\d)([01]?\d|2[0-3])(?!\d)", value)
    if match:
        return int(match.group(1)), 0
    return None


def _date_prefixes(date_value: datetime.date) -> List[str]:
    """Accepted date prefixes in legacy and newer rows."""
    return [
        jalali_date_string(date_value),
        date_value.strftime("%Y/%m/%d"),
        date_value.strftime("%Y-%m-%d"),
    ]


def _date_prefix_filter(column, date_values: List[datetime.date]):
    clauses = []
    seen = set()
    for date_value in date_values:
        for prefix in _date_prefixes(date_value):
            if prefix not in seen:
                seen.add(prefix)
                clauses.append(column.like(f"{prefix}%"))
    return or_(*clauses)


def _active_courses_query(db: Session):
    return db.query(Course).filter(
        or_(Course.is_deleted == False, Course.is_deleted.is_(None)),
        or_(Course.is_suspended == False, Course.is_suspended.is_(None)),
        Course.is_admin_approved == True,
    )


def _today_live_sessions(db: Session, now: datetime.datetime) -> List[LiveSession]:
    start = datetime.datetime.combine(now.date(), datetime.time.min).timestamp()
    end = datetime.datetime.combine(now.date() + datetime.timedelta(days=1), datetime.time.min).timestamp()
    gregorian_prefix = now.strftime("%Y-%m-%d")
    return (
        db.query(LiveSession)
        .filter(
            or_(
                (LiveSession.started_at_ts >= int(start)) & (LiveSession.started_at_ts < int(end)),
                LiveSession.start_time.like(f"{gregorian_prefix}%"),
            )
        )
        .order_by(LiveSession.id)
        .all()
    )


def _teacher_settlement_alert_threshold(db: Session) -> int:
    settings = db.query(InstituteSettings).first()
    try:
        configured = int(
            getattr(settings, "teacher_settlement_alert_days", 30) or 30
        )
    except (TypeError, ValueError):
        configured = 30
    return max(1, min(configured, 3650))


def build_admin_smart_alerts(
    db: Session,
    now: Optional[datetime.datetime] = None,
) -> Dict:
    """Read-only installment and teacher-settlement alerts for administrators."""
    now = now or datetime.datetime.now()
    today = now.date()

    installment_items = []
    installment_rows = (
        # FIX: Bug 13 - exclude archived Installment rows from this active view.
        db.query(Installment, Enrollment, Student).filter(Installment.is_deleted == False)
        .join(Enrollment, Enrollment.id == Installment.enrollment_id)
        .join(Student, Student.id == Enrollment.student_id)
        .filter(Installment.is_paid == False)
        .all()
    )
    for installment, enrollment, student in installment_rows:
        due_date = parse_project_date(installment.due_date)
        if not due_date:
            continue
        days_overdue = (today - due_date).days
        if days_overdue < 0:
            continue
        installment_items.append(
            {
                "installment_id": installment.id,
                "enrollment_id": enrollment.id,
                "student_id": student.id,
                "student_name": f"{student.first_name or ''} {student.last_name or ''}".strip(),
                "amount": int(installment.amount or 0),
                "due_date": installment.due_date,
                "days_overdue": days_overdue,
            }
        )
    installment_items.sort(
        key=lambda item: (item["days_overdue"], item["amount"]), reverse=True
    )

    threshold_days = _teacher_settlement_alert_threshold(db)
    pending_session_ids = [
        row[0]
        for row in (
            db.query(Attendance.session_id)
            .filter(
                Attendance.is_billed == False,
                Attendance.is_deleted == False,   # FIX (F-S2)
                Attendance.status.in_(["Present", "Late"]),
            )
            .distinct()
            .all()
        )
    ]
    # FIX H8-gap/follow-up: جلسات تماماً-غایب با جریمه‌ی باز هم تسویه‌نشده‌اند (همان منطق دوشاخه‌ی settle).
    # (تکراری‌ها در IN پایین بی‌اثرند پس dedupe لازم نیست.)
    pending_session_ids += [
        row[0]
        for row in (
            db.query(SessionLog.id)
            .filter(
                SessionLog.is_deleted == False,
                SessionLog.absent_penalty_teacher > 0,
                SessionLog.is_penalty_settled == False,
            )
            .distinct()
            .all()
        )
    ]

    grouped_teachers = {}
    if pending_session_ids:
        rows = (
            # FIX: Bug 14 - exclude archived SessionLog rows from this active view.
            db.query(SessionLog, Course, Teacher).filter(SessionLog.is_deleted == False)
            .join(Course, Course.id == SessionLog.course_id)
            .join(Teacher, Teacher.id == Course.teacher_id)
            .filter(SessionLog.id.in_(pending_session_ids))
            .all()
        )
        for session, course, teacher in rows:
            session_date = parse_project_date(session.date)
            if not session_date:
                continue
            days_unsettled = (today - session_date).days
            # Requirement is strictly "more than" the configured threshold.
            if days_unsettled <= threshold_days:
                continue

            item = grouped_teachers.setdefault(
                teacher.id,
                {
                    "teacher_id": teacher.id,
                    "teacher_name": f"{teacher.first_name or ''} {teacher.last_name or ''}".strip(),
                    "unsettled_amount": 0,
                    "session_count": 0,
                    "oldest_unsettled_date": session.date,
                    "oldest_days_unsettled": days_unsettled,
                    "last_settlement_at": None,
                },
            )
            # FIX: H6(A2) - مبلغ تسویه‌نشده = قراردادی + جریمه‌ی غایبین غیرموجه.
            item["unsettled_amount"] += int(session.final_teacher_cost or 0) + int(session.absent_penalty_teacher or 0)
            item["session_count"] += 1
            if days_unsettled > item["oldest_days_unsettled"]:
                item["oldest_days_unsettled"] = days_unsettled
                item["oldest_unsettled_date"] = session.date

    teacher_items = list(grouped_teachers.values())
    latest_settlements = {}
    teacher_ids = list(grouped_teachers.keys())
    if teacher_ids:
        settlements = (
            db.query(Settlement)
            .filter(Settlement.teacher_id.in_(teacher_ids))
            .order_by(Settlement.settled_at.desc(), Settlement.id.desc())
            .all()
        )
        for settlement in settlements:
            latest_settlements.setdefault(settlement.teacher_id, settlement)
    for item in teacher_items:
        last_settlement = latest_settlements.get(item["teacher_id"])
        if last_settlement and last_settlement.settled_at:
            item["last_settlement_at"] = last_settlement.settled_at.strftime(
                "%Y/%m/%d %H:%M"
            )
    teacher_items.sort(
        key=lambda item: (item["oldest_days_unsettled"], item["unsettled_amount"]),
        reverse=True,
    )

    return {
        "teacher_settlement_alert_days": threshold_days,
        "installment_alerts": {
            "count": len(installment_items),
            "total_amount": sum(item["amount"] for item in installment_items),
            "items": installment_items,
        },
        "teacher_settlement_alerts": {
            "count": len(teacher_items),
            "total_amount": sum(item["unsettled_amount"] for item in teacher_items),
            "items": teacher_items,
        },
    }


def build_admin_today_summary(
    db: Session,
    sub_role: str,
    now: Optional[datetime.datetime] = None,
) -> Dict:
    """Build the admin/secretary summary without changing any financial state."""
    now = now or datetime.datetime.now()
    today = now.date()

    scheduled_courses = [
        course
        for course in _active_courses_query(db).all()
        if schedule_matches_date(course.days_of_week, today)
    ]
    scheduled_ids = {course.id for course in scheduled_courses}

    today_lives = _today_live_sessions(db, now)
    started_course_ids = {live.course_id for live in today_lives if live.course_id in scheduled_ids}

    teacher_ids = {course.teacher_id for course in scheduled_courses if course.teacher_id}
    teachers = {}
    if teacher_ids:
        teachers = {
            teacher.id: teacher
            for teacher in db.query(Teacher).filter(Teacher.id.in_(teacher_ids)).all()
        }

    late_classes = []
    now_minutes = now.hour * 60 + now.minute
    for course in scheduled_courses:
        if course.id in started_course_ids:
            continue
        parsed_time = parse_schedule_start(course.class_time)
        if not parsed_time:
            continue
        scheduled_minutes = parsed_time[0] * 60 + parsed_time[1]
        minutes_late = now_minutes - scheduled_minutes
        if minutes_late <= 0:
            continue
        teacher = teachers.get(course.teacher_id)
        late_classes.append(
            {
                "course_id": course.id,
                "class_name": course.title or "کلاس بدون نام",
                "teacher_id": course.teacher_id,
                "teacher_name": (
                    f"{teacher.first_name or ''} {teacher.last_name or ''}".strip()
                    if teacher
                    else "نامشخص"
                ),
                "scheduled_time": f"{parsed_time[0]:02d}:{parsed_time[1]:02d}",
                "minutes_late": minutes_late,
            }
        )
    late_classes.sort(key=lambda item: item["minutes_late"], reverse=True)

    # FIX (گروه۲/آیتم۴): «پرداخت امروز» از تعریف یگانهٔ وصولی نقدی آموزشگاه می‌آید
    # (`financial_calculations.calculate_institute_cash_collected`) — همان چیزی که KPI
    # «درآمد امروز» در `/dashboard/kpis` نشان می‌دهد.
    # پیش‌تر اینجا `SUM(amount)` روی `type in (deposit, enrollment_payment, tuition, payment)`
    # با `LIKE` روی سه پیشوند تاریخ بود ⇒ (الف) واریزی به **کیف معلم** هم «پرداخت امروز»
    # حساب می‌شد (دقیقاً باگ O-08 که فقط در KPI فیکس شده بود)، (ب) ردیف legacy با
    # `type=NULL` دیده نمی‌شد، (پ) دو عدد متفاوت برای یک روز در دو صفحهٔ اپ.
    from financial_calculations import calculate_institute_cash_collected  # lazy (الگوی پروژه)
    today_jalali = jalali_date_string(today)
    try:
        payment_total = int(calculate_institute_cash_collected(db, today_jalali, today_jalali) or 0)
    except Exception as exc:  # هم‌سبک KPIهای dashboard: خطا ⇒ ۰ و لاگ، نه ۵۰۰
        print(f"[TodaySummary] today_payments failed: {exc}")
        payment_total = 0

    # FIX (گروه۲/آیتم۴): «ثبت‌نام امروز» با پارس مرکزی تاریخ (ستون دو تقویمه/دو قالبی است)
    # و بدون شمردن ثبت‌نام‌های آرشیوشده — پیش‌تر `LIKE` روی register_date بود و
    # `is_deleted` را نمی‌دید ⇒ ثبت‌نامِ رد/حذف‌شده هم «امروز» شمرده می‌شد.
    enrollment_rows = db.query(Enrollment.register_date, Enrollment.is_deleted).all()
    enrollment_count = sum(
        1
        for register_date, is_deleted in enrollment_rows
        if not is_deleted and parse_project_date(register_date) == today
    )

    is_admin = sub_role == "admin"
    result = {
        "date": jalali_date_string(today),
        "day_name": PERSIAN_DAY_NAMES[today.weekday()],
        "scheduled_classes": len(scheduled_courses),
        "started_classes": len(started_course_ids),
        "late_classes": late_classes,
        "today_payments": int(payment_total) if is_admin else None,
        "payment_visible": is_admin,
        "today_enrollments": enrollment_count,
        "smart_alerts_visible": is_admin,
    }
    if is_admin:
        result.update(build_admin_smart_alerts(db=db, now=now))
    else:
        # Do not calculate or serialize aggregate financial alert data for secretary.
        result.update(
            {
                "teacher_settlement_alert_days": None,
                "installment_alerts": None,
                "teacher_settlement_alerts": None,
            }
        )
    return result


def _find_next_class(
    courses: List[Course],
    now: datetime.datetime,
    horizon_days: int = 7,
) -> Optional[Dict]:
    candidates = []
    for offset in range(horizon_days + 1):
        candidate_date = now.date() + datetime.timedelta(days=offset)
        for course in courses:
            if not schedule_matches_date(course.days_of_week, candidate_date):
                continue
            parsed_time = parse_schedule_start(course.class_time)
            if not parsed_time:
                continue
            scheduled_at = datetime.datetime.combine(
                candidate_date,
                datetime.time(parsed_time[0], parsed_time[1]),
            )
            if scheduled_at < now:
                continue
            candidates.append((scheduled_at, course))

    if not candidates:
        return None
    scheduled_at, course = min(candidates, key=lambda item: item[0])
    minutes_until = max(0, int((scheduled_at - now).total_seconds() // 60))
    return {
        "course_id": course.id,
        "class_name": course.title or "کلاس بدون نام",
        "scheduled_time": scheduled_at.strftime("%H:%M"),
        "scheduled_date": jalali_date_string(scheduled_at.date()),
        "minutes_until": minutes_until,
    }


def _teacher_unsettled_amount(
    db: Session,
    course_ids: List[int],
    week_dates: List[datetime.date],
) -> int:
    """Use the existing pending-settlement marker, limited to the current week."""
    if not course_ids:
        return 0
    pending_session_ids = (
        db.query(Attendance.session_id)
        .join(SessionLog, SessionLog.id == Attendance.session_id)
        .filter(
            SessionLog.course_id.in_(course_ids),
            _date_prefix_filter(SessionLog.date, week_dates),
            Attendance.is_billed == False,
            Attendance.is_deleted == False,   # FIX (F-S2)
            Attendance.status.in_(["Present", "Late"]),
        )
        .distinct()
        .subquery()
    )
    # FIX H8-gap/follow-up: جلسات تماماً-غایب با جریمه‌ی باز هم تسویه‌نشده‌اند (همان منطق دوشاخه‌ی settle).
    penalty_ids = [
        r[0]
        for r in db.query(SessionLog.id)
        .filter(
            SessionLog.is_deleted == False,
            SessionLog.course_id.in_(course_ids),
            _date_prefix_filter(SessionLog.date, week_dates),
            SessionLog.absent_penalty_teacher > 0,
            SessionLog.is_penalty_settled == False,
        )
        .all()
    ]
    _id_filter = SessionLog.id.in_(select(pending_session_ids.c.session_id))
    if penalty_ids:
        _id_filter = or_(_id_filter, SessionLog.id.in_(penalty_ids))
    amount = (
        # FIX: Bug 14 - exclude archived SessionLog rows from this active view.
        # FIX: H6(A2) - جمع قراردادی + جریمه (coalesce برای سطرهای قدیمی NULL).
        db.query(func.sum(func.coalesce(SessionLog.final_teacher_cost, 0) + func.coalesce(SessionLog.absent_penalty_teacher, 0))).filter(SessionLog.is_deleted == False)
        .filter(_id_filter)
        .scalar()
        or 0
    )
    return int(amount)


def build_teacher_today_summary(
    db: Session,
    teacher_id: int,
    now: Optional[datetime.datetime] = None,
) -> Dict:
    """Build a teacher's live/next-class state and compact weekly summary."""
    now = now or datetime.datetime.now()
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not teacher:
        return {}

    all_courses = db.query(Course).filter(Course.teacher_id == teacher_id).all()
    all_course_ids = [course.id for course in all_courses]
    active_courses = [
        course
        for course in all_courses
        if course.is_admin_approved is True
        and course.is_deleted is not True
        and course.is_suspended is not True
    ]

    live = (
        db.query(LiveSession)
        .filter(LiveSession.teacher_id == teacher_id, LiveSession.status == "LIVE")
        .order_by(LiveSession.id.desc())
        .first()
    )
    live_class = None
    if live:
        live_course = next((course for course in all_courses if course.id == live.course_id), None)
        started_ts = int(live.started_at_ts or time.mktime(now.timetuple()))
        elapsed = max(0, int((now.timestamp() - started_ts) // 60))
        live_class = {
            "live_session_id": live.id,
            "course_id": live.course_id,
            "class_name": live_course.title if live_course else "کلاس",
            "started_at_ts": int(live.started_at_ts) if live.started_at_ts is not None else None,
            "elapsed_minutes": elapsed,
        }

    # Persian weeks begin on Saturday. Python weekday: Monday=0, Saturday=5.
    days_since_saturday = (now.date().weekday() - 5) % 7
    week_start = now.date() - datetime.timedelta(days=days_since_saturday)
    week_dates = [week_start + datetime.timedelta(days=i) for i in range(7)]

    sessions_taught = 0
    if all_course_ids:
        sessions_taught = (
            # FIX: Bug 14 - exclude archived SessionLog rows from this active view.
            db.query(SessionLog).filter(SessionLog.is_deleted == False)
            .filter(
                SessionLog.course_id.in_(all_course_ids),
                _date_prefix_filter(SessionLog.date, week_dates),
            )
            .count()
        )

    return {
        "date": jalali_date_string(now.date()),
        "day_name": PERSIAN_DAY_NAMES[now.date().weekday()],
        "live_class": live_class,
        "next_class": None if live_class else _find_next_class(active_courses, now),
        "week_summary": {
            "sessions_taught": sessions_taught,
            "unsettled_amount": _teacher_unsettled_amount(db, all_course_ids, week_dates),
        },
    }
