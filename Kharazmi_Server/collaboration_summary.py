"""Read-only collaboration summary for teacher profiles (admin view).

Informational only: raw numbers, no automatic judgment.
- average delay in starting live classes (last 30 days)
- total settlements count and total paid amount
- auto-ended live sessions count
"""

import datetime
import re
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from models import Course, LiveSession, Settlement, Teacher
from today_summary import parse_project_date, parse_schedule_start


_TIME_RE = re.compile(r"([01]?\d|2[0-3])\s*[:٫.]\s*([0-5]\d)")


def _parse_hhmm_from_string(value: Optional[str]) -> Optional[Tuple[int, int]]:
    if not value:
        return None
    # Normalize Persian/Arabic digits
    normalized = (value or "").translate(
        str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    )
    m = _TIME_RE.search(normalized)
    if m:
        try:
            h = int(m.group(1))
            mm = int(m.group(2))
            if 0 <= h <= 23 and 0 <= mm <= 59:
                return h, mm
        except Exception:
            return None
    return None


def _live_datetime(live: LiveSession) -> Optional[datetime.datetime]:
    # Prefer start_time string because it contains the real HH:MM that spec asks for
    if getattr(live, "start_time", None):
        # Try strict Gregorian parse first (most common: "2026-08-10 16:05")
        for fmt in ("%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
            try:
                return datetime.datetime.strptime(live.start_time, fmt)
            except Exception:
                continue
        # Try to parse date part via parse_project_date (handles Jalali/Gregorian) + time
        date_part = parse_project_date(live.start_time)
        time_part = _parse_hhmm_from_string(live.start_time)
        if date_part and time_part:
            try:
                return datetime.datetime.combine(
                    date_part, datetime.time(time_part[0], time_part[1])
                )
            except Exception:
                pass

    # Fallback to epoch ts
    if getattr(live, "started_at_ts", None):
        try:
            ts = int(live.started_at_ts)
            if ts > 1577836800 and ts < 4102444800:
                return datetime.datetime.fromtimestamp(ts)
        except Exception:
            pass
    return None


def build_teacher_collaboration_summary(
    db: Session,
    teacher_id: int,
    period_days: int = 30,
    now: Optional[datetime.datetime] = None,
) -> Dict:
    now = now or datetime.datetime.now()
    threshold_date = now - datetime.timedelta(days=period_days)
    threshold_ts = int(threshold_date.timestamp())

    teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not teacher:
        return {}

    courses = db.query(Course).filter(Course.teacher_id == teacher_id).all()
    course_map: Dict[int, Course] = {c.id: c for c in courses}

    # All live sessions for this teacher
    lives: List[LiveSession] = (
        db.query(LiveSession).filter(LiveSession.teacher_id == teacher_id).all()
    )

    delays: List[int] = []
    auto_ended_total = 0
    auto_ended_last_30 = 0
    live_last_30_count = 0

    for live in lives:
        if getattr(live, "ended_automatically", False):
            auto_ended_total += 1

        live_dt = _live_datetime(live)
        # Determine if in last 30 days
        in_last_30 = False
        if live_dt:
            if live_dt >= threshold_date:
                in_last_30 = True
        else:
            # If we cannot parse dt, fallback to started_at_ts threshold check already done,
            # or try to use end_time/start_time existence as recent? For safety, if ts exists:
            if getattr(live, "started_at_ts", None):
                try:
                    if int(live.started_at_ts) >= threshold_ts:
                        in_last_30 = True
                except Exception:
                    pass

        if in_last_30:
            live_last_30_count += 1
            if getattr(live, "ended_automatically", False):
                auto_ended_last_30 += 1

            # Delay calculation only for last 30 days and only if we have scheduled time
            course = course_map.get(live.course_id)
            if course and live_dt:
                sched = parse_schedule_start(course.class_time)
                if sched:
                    sched_minutes = sched[0] * 60 + sched[1]
                    actual_minutes = live_dt.hour * 60 + live_dt.minute
                    # Raw diff; treat early start as 0 delay (not negative)
                    diff = actual_minutes - sched_minutes
                    if diff < 0:
                        diff = 0
                    # Ignore absurd diffs > 12h (likely date mismatch)
                    if diff <= 12 * 60:
                        delays.append(diff)

    avg_delay = round(sum(delays) / len(delays), 1) if delays else 0.0

    settlements = (
        db.query(Settlement).filter(Settlement.teacher_id == teacher_id).all()
    )
    total_settlements = len(settlements)
    total_paid = sum(int(s.total_amount or 0) for s in settlements)

    return {
        "period_days": period_days,
        "period_start": threshold_date.strftime("%Y/%m/%d"),
        "period_end": now.strftime("%Y/%m/%d"),
        "average_delay_minutes": avg_delay,
        "delay_samples_count": len(delays),
        "live_sessions_last_30_days": live_last_30_count,
        "total_settlements_count": total_settlements,
        "total_settled_amount": total_paid,
        "auto_ended_sessions_count": auto_ended_total,
        "auto_ended_last_30_days_count": auto_ended_last_30,
    }
