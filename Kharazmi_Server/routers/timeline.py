"""
Student 360 Timeline - Unified Activity Feed (Read-Only, Optimized)
Isolated router - no modifications to finance/classes/audit.
All logic uses joinedload/selectinload to avoid N+1.
"""
import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import desc

from models import Attendance, Course, Enrollment, Grade, Installment, SessionLog, Student, Transaction
from dependencies import get_db, check_user_login, check_student_access

router = APIRouter()

class TimelineEvent(BaseModel):
    timestamp: str       # Sorted key (ISO or Jalali normalized)
    type: str            # 'payment', 'absence', 'grade', 'installment'
    title: str           # e.g., "پرداخت ۲,۰۰۰,۰۰۰ تومان"
    subtitle: str        # e.g., "کلاس: ریاضی - آقای رضایی"
    icon_name: str       # e.g., "ic_payment", "ic_absent", "ic_grade"
    color_hex: str       # e.g., "#4CAF50" (Green), "#F44336" (Red)

def _format_amount(amount: int) -> str:
    try:
        return f"{int(amount):,}"
    except:
        return str(amount)

def _normalize_timestamp(raw: Optional[str], fallback_id: int = 0) -> str:
    """Return sortable timestamp string; tries to parse Jalali/Gregorian via today_summary."""
    if not raw or not str(raw).strip():
        # fallback to epoch + id to keep stable sorting
        return f"1970/01/01 00:00:{fallback_id:02d}"
    raw_str = str(raw).strip()
    # Keep original for display, but ensure sortable prefix is date part
    # Try to parse via today_summary.parse_project_date to get real date for sorting
    try:
        from today_summary import parse_project_date  # lazy, central converter
        d = parse_project_date(raw_str)
        if d:
            # If raw contains time, try to preserve it
            # raw may be "1403/06/22 14:30" or "1403/06/22" or "2026/01/15"
            # For sorting, use ISO date + time part if exists
            time_part = ""
            if " " in raw_str:
                time_part = raw_str.split(" ")[-1]
                if ":" not in time_part:
                    time_part = ""
            if time_part:
                # normalize Persian digits
                time_part = time_part.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")).translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
                return f"{d.isoformat()} {time_part}"
            return d.isoformat()
    except Exception:
        pass
    # Fallback: raw string itself (lexicographically sortable if YYYY/MM/DD)
    return raw_str

def _sort_key(event: TimelineEvent):
    """Convert timestamp to sortable datetime key."""
    try:
        from today_summary import parse_project_date
        d = parse_project_date(event.timestamp)
        if d:
            # Try to extract time
            time_part = event.timestamp.split(" ")[-1] if " " in event.timestamp else ""
            hour = minute = 0
            if ":" in time_part:
                try:
                    tp = time_part.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")).translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
                    h, m = tp.split(":")[:2]
                    hour = int(h); minute = int(m)
                except:
                    pass
            return datetime.datetime.combine(d, datetime.time(hour, minute))
    except:
        pass
    # Fallback lexical
    return event.timestamp

@router.get("/students/{student_id}/timeline", response_model=List[TimelineEvent])
def get_student_timeline(
    student_id: int,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    sub_role: str = Depends(check_user_login),
):
    """
    Unified Timeline - 4 optimized queries (joinedload), merge & sort in Python, slice 50.
    Read-Only, <200ms expected via limit 20 each + single queries.
    """
    # Security: Admin, Secretary, Teacher (own), Parent (own child), Student (self)
    check_student_access(student_id, authorization, db, sub_role)

    # Verify student exists (not deleted)
    student = db.query(Student).filter(Student.id == student_id, Student.is_deleted == False).first()
    if not student:
        raise HTTPException(status_code=404, detail="دانش‌آموز یافت نشد")

    events: List[TimelineEvent] = []
    # We will use fallback id for timestamp when date missing, to keep sorting stable
    # 1. Transactions - optimized with joinedload(course) to avoid N+1 per row for course title
    try:
        # Single query: Transaction + Course (avoids N+1 for course_name)
        transactions = (
            db.query(Transaction)
            .options(joinedload(Transaction.course))
            .filter(
                Transaction.student_id == student_id,
                Transaction.is_deleted == False,
                Transaction.is_reversed == False,
            )
            .order_by(desc(Transaction.id))  # recent first; spec says desc(date) but id is more reliable for recent
            .limit(20)
            .all()
        )
        for t in transactions:
            # Use joinedloaded course, no extra query
            course_title = t.course.title if t.course else "نامشخص"
            # Also try to get teacher name via course.teacher if needed? Avoid extra query, keep subtitle simple
            ts = _normalize_timestamp(t.date, t.id)
            amount_str = _format_amount(t.amount or 0)
            title = f"پرداخت {amount_str} تومان"
            if (t.amount or 0) < 0:
                title = f"بازگشت {amount_str} تومان"
            subtitle = f"کلاس: {course_title}"
            if t.description:
                # Truncate long description
                desc_short = str(t.description)[:60]
                subtitle += f" — {desc_short}"
            elif t.payment_method:
                subtitle += f" — روش: {t.payment_method}"
            # Also include target_wallet if present
            if t.target_wallet:
                subtitle += f" ({t.target_wallet})"
            events.append(TimelineEvent(
                timestamp=ts,
                type="payment",
                title=title,
                subtitle=subtitle,
                icon_name="ic_payment",
                color_hex="#4CAF50",
            ))
    except Exception as e:
        # Log but continue with other types (partial result)
        print(f"[Timeline] Transactions query failed for student {student_id}: {e}")

    # 2. Attendance - optimized with joinedload(session -> course)
    try:
        attendances = (
            db.query(Attendance)
            .options(joinedload(Attendance.session).joinedload(SessionLog.course))
            .filter(Attendance.student_id == student_id)
            .filter(Attendance.status == "Absent")  # only absences are meaningful in timeline
            .order_by(desc(Attendance.id))
            .limit(20)
            .all()
        )
        for att in attendances:
            sess = att.session  # already loaded via joinedload, no N+1
            course_title = "نامشخص"
            date_str = ""
            time_str = ""
            if sess:
                if sess.course:
                    course_title = sess.course.title
                date_str = sess.date or ""
                time_str = sess.time or sess.start_time or ""
            ts_raw = f"{date_str} {time_str}".strip() if date_str else f"1970/01/01"
            ts = _normalize_timestamp(ts_raw, att.id)
            title = "غیبت در جلسه"
            if att.excused:
                title = "غیبت موجه"
            subtitle = f"کلاس: {course_title}"
            if date_str:
                subtitle += f" — تاریخ: {date_str}"
            if sess and sess.session_code:
                subtitle += f" (کد: {sess.session_code})"
            events.append(TimelineEvent(
                timestamp=ts,
                type="absence",
                title=title,
                subtitle=subtitle,
                icon_name="ic_absent",
                color_hex="#F44336",
            ))
    except Exception as e:
        print(f"[Timeline] Attendance query failed for student {student_id}: {e}")

    # 3. Grades - optimized with joinedload(course)
    try:
        grades = (
            db.query(Grade)
            .options(joinedload(Grade.course))
            .filter(Grade.student_id == student_id)
            .order_by(desc(Grade.id))
            .limit(20)
            .all()
        )
        for g in grades:
            course_title = g.course.title if g.course else "نامشخص"
            ts = _normalize_timestamp(g.date, g.id)
            # Format score
            try:
                score_str = f"{g.score:g}"
                max_str = f"{g.max_score:g}" if g.max_score else ""
            except:
                score_str = str(g.score)
                max_str = str(g.max_score)
            title = f"نمره {score_str}"
            if max_str:
                title += f" از {max_str}"
            if g.exam_title:
                title += f" — {g.exam_title}"
            subtitle = f"کلاس: {course_title}"
            if g.description:
                subtitle += f" — {str(g.description)[:50]}"
            # Color based on score ratio
            color = "#4CAF50"
            try:
                if g.max_score and g.max_score > 0:
                    ratio = float(g.score) / float(g.max_score)
                    if ratio < 0.5:
                        color = "#F44336"
                    elif ratio < 0.75:
                        color = "#FF9800"
            except:
                pass
            events.append(TimelineEvent(
                timestamp=ts,
                type="grade",
                title=title,
                subtitle=subtitle,
                icon_name="ic_grade",
                color_hex=color,
            ))
    except Exception as e:
        print(f"[Timeline] Grades query failed for student {student_id}: {e}")

    # 4. Installments - optimized via join + joinedload(enrollment -> course)
    try:
        # Installments have no direct student_id, must join via Enrollment
        # Use joinedload to avoid N+1 for enrollment and course
        installments = (
            db.query(Installment)
            .join(Enrollment, Installment.enrollment_id == Enrollment.id)
            .options(
                joinedload(Installment.enrollment).joinedload(Enrollment.course),
                joinedload(Installment.enrollment).joinedload(Enrollment.student),  # not needed but for completeness
            )
            .filter(
                Enrollment.student_id == student_id,
                Enrollment.is_deleted == False,
                Installment.is_deleted == False,
            )
            .order_by(desc(Installment.id))
            .limit(20)
            .all()
        )
        for inst in installments:
            # Already loaded via joinedload, no extra query
            course_title = "نامشخص"
            try:
                if inst.enrollment and inst.enrollment.course:
                    course_title = inst.enrollment.course.title
                elif inst.enrollment:
                    # Fallback query if not loaded (should not happen)
                    c = db.query(Course).filter(Course.id == inst.enrollment.course_id).first()
                    if c:
                        course_title = c.title
            except:
                pass
            ts = _normalize_timestamp(inst.due_date, inst.id)
            amount_str = _format_amount(inst.amount or 0)
            if inst.is_paid:
                title = f"قسط پرداخت شده {amount_str} تومان"
                color = "#4CAF50"
                icon = "ic_paid"
            else:
                # Check overdue via parse
                overdue = False
                try:
                    from today_summary import parse_project_date
                    due_d = parse_project_date(inst.due_date)
                    if due_d and due_d < datetime.date.today():
                        overdue = True
                except:
                    pass
                if overdue:
                    title = f"قسط معوق {amount_str} تومان"
                    color = "#F44336"
                    icon = "ic_overdue"
                else:
                    title = f"قسط {amount_str} تومان — سررسید {inst.due_date}"
                    color = "#FF9800"
                    icon = "ic_installment"
            subtitle = f"کلاس: {course_title} — سررسید: {inst.due_date}"
            if inst.paid_at:
                subtitle += f" — پرداخت: {inst.paid_at}"
            events.append(TimelineEvent(
                timestamp=ts,
                type="installment",
                title=title,
                subtitle=subtitle,
                icon_name=icon,
                color_hex=color,
            ))
    except Exception as e:
        print(f"[Timeline] Installments query failed for student {student_id}: {e}")

    # Merge & sort in Python by timestamp descending, slice top 50
    # All 4 lists already limited to 20 each (max 80), merge sort 50 ensures <200ms
    try:
        events.sort(key=_sort_key, reverse=True)
    except Exception as e:
        print(f"[Timeline] Sort failed: {e}")
        # Fallback lexical sort
        events.sort(key=lambda x: x.timestamp, reverse=True)

    return events[:50]
