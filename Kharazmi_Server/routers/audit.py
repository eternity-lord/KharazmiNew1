"""
Audit Radar - Fraud Detection System (Read-Only, Optimized)
Isolated router - no modifications to core routers.
All endpoints require admin access.

Optimizations:
- N+1 fixed via joinedload/selectinload (SessionLog.course, Transaction.student/course) and bulk fetches (Attendance, ActivityLog)
- Pattern B: only last 30 days + ActivityLog join + rapid <1h check
- No silent except:pass - log via logging + print
- Pattern A: proper midnight crossover via circular diff
"""

import datetime
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import desc, func

import models
from models import Course, SessionLog, Attendance, Transaction, ActivityLog, Student
from dependencies import get_db, check_admin_access

router = APIRouter()
logger = logging.getLogger(__name__)

from pydantic import BaseModel

class AuditAlert(BaseModel):
    type: str  # e.g., "suspicious_attendance", "rapid_deletion", "perfect_attendance"
    severity: str  # "high", "medium", "low"
    title: str
    description: str
    entity_id: int
    entity_name: str
    detected_at: str


def _parse_hour(time_str: Optional[str]) -> Optional[int]:
    """Extract hour from time string like '08:30', '16:00', '08:00-10:00'."""
    if not time_str:
        return None
    try:
        first = time_str.split("-")[0].strip().split(" ")[-1].strip()
        if ":" not in first:
            return None
        hour_part = first.split(":")[0].strip()
        fa_digits = "۰۱۲۳۴۵۶۷۸۹"
        ar_digits = "٠١٢٣٤٥٦٧٨٩"
        normalized = ""
        for c in hour_part:
            fi = fa_digits.find(c)
            ai = ar_digits.find(c) if fi == -1 else -1
            if fi != -1:
                normalized += str(fi)
            elif ai != -1:
                normalized += str(ai)
            elif c.isdigit():
                normalized += c
            else:
                return None
        hour = int(normalized) if normalized.isdigit() else None
        if hour is not None and 0 <= hour <= 23:
            return hour
        return None
    except Exception as e:
        logger.warning(f"[Audit] _parse_hour failed for {time_str}: {e}")
        print(f"[Audit] _parse_hour failed for {time_str}: {e}")
        return None


def _circular_hour_diff(h1: int, h2: int) -> int:
    """
    Proper 24h circular difference.
    Example: class 23:00, session 02:00 => abs=21, circular=min(21,3)=3 (valid, not suspicious)
    Without this, abs(23-2)=21 >5 would incorrectly flag midnight crossover as suspicious.
    """
    diff = abs(h1 - h2)
    return min(diff, 24 - diff)


def _now_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@router.get("/suspicious_patterns", response_model=List[AuditAlert])
def get_suspicious_patterns(
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_access)
):
    """
    Audit Radar - Detect suspicious patterns (Read-Only, Optimized).
    Pattern A: Suspicious Attendance (00:00-05:00 or delayed >5h with midnight-aware diff)
    Pattern B: Rapid Deletion (Transaction deleted <1h, only last 30 days via ActivityLog)
    Pattern C: Perfect Attendance (last 10 sessions 0 absences) - bulk optimized
    """
    alerts: List[AuditAlert] = []
    now_str = _now_str()

    # Pattern A: Suspicious Attendance - N+1 FIXED via joinedload
    try:
        # Single query fetches SessionLog + Course (avoids N+1 per row)
        # Before: len(SessionLog) queries for Course + another len for course_name => 2N queries
        # After: 1 query via joinedload (or 2 queries if selectinload)
        session_logs = db.query(SessionLog).options(joinedload(SessionLog.course)).filter(SessionLog.is_deleted == False).all()
        # Also alternative bulk via dict would be 2 queries; joinedload is 1 query with JOIN
        for sl in session_logs:
            suspicious = False
            reason = ""
            hour = _parse_hour(sl.time)
            if hour is not None and 0 <= hour < 5:
                suspicious = True
                reason = f"ساعت ثبت جلسه {sl.time} در بازه غیرمعقول 00:00-05:00 است"
            if not suspicious:
                hour2 = _parse_hour(sl.start_time)
                if hour2 is not None and 0 <= hour2 < 5:
                    suspicious = True
                    reason = f"ساعت شروع {sl.start_time} در بازه غیرمعقول 00:00-05:00 است"
            # Delayed check with proper midnight handling
            if not suspicious and sl.course_id and sl.course:
                course = sl.course  # already loaded via joinedload, no extra query
                if course.class_time:
                    course_hour = _parse_hour(course.class_time)
                    session_hour = hour if hour is not None else _parse_hour(sl.start_time)
                    if course_hour is not None and session_hour is not None:
                        diff = _circular_hour_diff(session_hour, course_hour)
                        if diff > 5:
                            suspicious = True
                            reason = f"تأخیر قابل توجه: ساعت کلاس {course.class_time} ولی جلسه در {sl.time or sl.start_time} ثبت شده (اختلاف {diff} ساعت - محاسبه‌ی حلقوی ۲۴ساعته)"
            elif not suspicious and sl.course_id and not sl.course:
                # Fallback if relationship not loaded (should not happen with joinedload, but keep for safety)
                logger.warning(f"[Audit] Pattern A: course not loaded for session {sl.id}, course_id {sl.course_id}")
                print(f"[Audit] Pattern A: course not loaded for session {sl.id}, course_id {sl.course_id}")

            if suspicious:
                course_name = sl.course.title if sl.course else "نامشخص"
                alerts.append(AuditAlert(
                    type="suspicious_attendance",
                    severity="high",
                    title="حضور مشکوک در ساعات غیرمعمول",
                    description=reason + f" | جلسه #{sl.id} | تاریخ {sl.date or 'نامشخص'} | کلاس {course_name}",
                    entity_id=sl.id,
                    entity_name=f"{course_name} - جلسه {sl.id}",
                    detected_at=now_str
                ))
    except Exception as e:
        logger.error(f"[Audit] Pattern A failed: {e}", exc_info=True)
        print(f"[Audit] Pattern A failed: {e}")
        # Continue to other patterns, return partial result

    # Pattern B: Rapid Deletion - FIXED: only last 30 days + ActivityLog join + <1h check
    try:
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=30)
        # Step 1: Fetch deleted transactions with joinedload for names (1 query, no N+1 for student/course)
        # Note: This fetches ALL deleted, but we will filter via ActivityLog below to only recent rapid
        # To reduce history spam, we immediately filter via ActivityLog join
        # Use subquery: only transactions that have a recent ActivityLog entry
        # We do two queries total: one for transactions + one for logs, then join in Python (avoids SQL LIKE complexity)
        deleted_txns = db.query(Transaction).options(joinedload(Transaction.student), joinedload(Transaction.course)).filter(Transaction.is_deleted == True).all()
        if deleted_txns:
            txn_ids = [t.id for t in deleted_txns]
            txn_map = {t.id: t for t in deleted_txns}
            # Fetch ActivityLogs for these transactions within last 30 days (1 query)
            # We consider both target_id match and details containing transaction id (creation logs may use different target)
            # For efficiency, fetch logs where target_id in txn_ids and timestamp >= cutoff
            logs_by_target = db.query(ActivityLog).filter(ActivityLog.target_id.in_(txn_ids), ActivityLog.timestamp >= cutoff).all()
            # Also fetch logs where details contains txn id (for creation logs that mention transaction)
            # To avoid N+1 LIKE per txn, fetch all recent logs and filter in Python
            # Fetch all recent logs within cutoff (1 query) and filter where details contains str(txn_id)
            # Limit to recent logs to avoid loading entire history: already have logs_by_target, now fetch recent logs with details
            recent_logs_with_details = db.query(ActivityLog).filter(ActivityLog.timestamp >= cutoff).all()  # 1 query (could be large, but cutoff 30 days limits it)
            # Build map txn_id -> logs
            from collections import defaultdict
            logs_by_txn = defaultdict(list)
            for log in logs_by_target:
                logs_by_txn[log.target_id].append(log)
            # Also check details containment
            for log in recent_logs_with_details:
                if log.details:
                    # Extract potential txn ids from details: look for "#<id>"
                    # Simple approach: for each txn_id, check if str(txn_id) in details
                    # To avoid O(N*M) with large txn_ids, we do per log check against txn_ids set
                    # But we can just check if any txn_id string appears in details
                    # For now, do per txn check but with small txn_ids (deleted) it's okay
                    for tid in txn_ids:
                        if f"#{tid}" in log.details or f"تراکنش #{tid}" in log.details or f"#{tid} " in log.details:
                            # Avoid duplicate if already added via target_id
                            if log not in logs_by_txn[tid]:
                                logs_by_txn[tid].append(log)
                        # Also generic containment fallback
                        elif str(tid) in log.details and "تراکنش" in log.details:
                            if log not in logs_by_txn[tid]:
                                logs_by_txn[tid].append(log)

            # Now evaluate rapid deletion: need creation and deletion logs within 1h
            for tid, logs in logs_by_txn.items():
                if not logs:
                    continue
                # Sort by timestamp
                logs_sorted = sorted(logs, key=lambda x: x.timestamp or datetime.datetime.min)
                # Classify logs: creation vs deletion
                # Creation keywords: payment_success, create, pay, deposit
                # Deletion keywords: refund, delete, reversal, reversed
                creation_logs = [l for l in logs_sorted if any(k in (l.action or "").lower() for k in ["create", "payment_success", "pay", "deposit", "online_payment"])]
                deletion_logs = [l for l in logs_sorted if any(k in (l.action or "").lower() for k in ["refund", "delete", "reversal", "reversed", "reversal"])]
                # Fallback: if action doesn't contain keywords but we have logs, treat earliest as creation, latest as deletion
                if not creation_logs and len(logs_sorted) >= 2:
                    creation_logs = [logs_sorted[0]]
                    deletion_logs = [logs_sorted[-1]]
                elif not deletion_logs and len(logs_sorted) >= 1:
                    # If only one log type, try to infer deletion from is_deleted flag + recent timestamp
                    # But without both, we cannot confirm rapid (<1h) - skip to avoid spam
                    continue

                is_rapid = False
                rapid_reason = ""
                for c_log in creation_logs:
                    for d_log in deletion_logs:
                        if not c_log.timestamp or not d_log.timestamp:
                            continue
                        if d_log.timestamp < c_log.timestamp:
                            continue
                        diff_seconds = (d_log.timestamp - c_log.timestamp).total_seconds()
                        if 0 <= diff_seconds < 3600:  # <1 hour
                            is_rapid = True
                            rapid_reason = f"حذف در {int(diff_seconds//60)} دقیقه پس از ایجاد (ایجاد: {c_log.timestamp}, حذف: {d_log.timestamp})"

                # Alternative strict check: if logs are within 1h cluster even without keyword classification
                if not is_rapid and len(logs_sorted) >= 2:
                    earliest = logs_sorted[0].timestamp
                    latest = logs_sorted[-1].timestamp
                    if earliest and latest and 0 <= (latest - earliest).total_seconds() < 3600:
                        # Check that at least one log is deletion-like and within 30 days
                        if any(any(k in (l.action or "").lower() for k in ["refund","delete","reversal"]) for l in logs_sorted):
                            is_rapid = True
                            rapid_reason = f"چند رویداد مرتبط در کمتر از ۱ ساعت (از {earliest} تا {latest})"

                if is_rapid:
                    txn = txn_map.get(tid)
                    if not txn:
                        continue
                    student_name = f"{txn.student.first_name} {txn.student.last_name}" if txn.student else "نامشخص"
                    course_name = txn.course.title if txn.course else "نامشخص"
                    alerts.append(AuditAlert(
                        type="rapid_deletion",
                        severity="high",
                        title="حذف سریع تراکنش مالی",
                        description=f"تراکنش #{txn.id} به مبلغ {txn.amount} تومان برای {student_name} در کلاس {course_name} به سرعت پس از ایجاد حذف شده است ({rapid_reason}) | is_deleted=True | بررسی ActivityLog در 30 روز اخیر",
                        entity_id=txn.id,
                        entity_name=f"تراکنش {txn.id} - {student_name} - {course_name}",
                        detected_at=now_str
                    ))
                # If not rapid, do not flag - this fixes spam of old deleted transactions
        # If no txn with recent logs, no alerts (correctly filters history)
    except Exception as e:
        logger.error(f"[Audit] Pattern B failed: {e}", exc_info=True)
        print(f"[Audit] Pattern B failed: {e}")

    # Pattern C: Perfect Attendance - N+1 FIXED via bulk queries
    try:
        # Before: N queries for courses * (1 session query + 2 attendance queries) = 3N+1
        # After: 3 queries total
        # 1) All active courses
        courses = db.query(Course).filter(Course.is_deleted == False).all()
        if courses:
            course_ids = [c.id for c in courses]
            course_map = {c.id: c for c in courses}
            # 2) All session_logs for these courses in one query (single)
            all_sessions = db.query(SessionLog).filter(SessionLog.course_id.in_(course_ids), SessionLog.is_deleted == False).order_by(SessionLog.course_id, desc(SessionLog.id)).all()
            # Group by course_id and take last 10 per course in Python
            from collections import defaultdict
            sessions_by_course = defaultdict(list)
            for s in all_sessions:
                sessions_by_course[s.course_id].append(s)
            # Collect relevant session ids (last 10 per course)
            relevant_sids = []
            course_to_last10 = {}
            for cid, sess_list in sessions_by_course.items():
                last10 = sess_list[:10]  # already ordered desc, so first 10 are most recent
                if len(last10) < 10:
                    continue
                course_to_last10[cid] = last10
                relevant_sids.extend([s.id for s in last10])

            if relevant_sids:
                # 3) All attendance for those session ids in one query (single)
                # Use joinedload not needed, just bulk fetch
                attendances = db.query(Attendance).filter(Attendance.session_id.in_(relevant_sids)).all()
                # Group by session_id and count
                from collections import defaultdict as _dd
                absent_by_course = defaultdict(int)
                total_by_course = defaultdict(int)
                # Build session_id -> course_id map
                sid_to_cid = {}
                for cid, sess_list in course_to_last10.items():
                    for s in sess_list:
                        sid_to_cid[s.id] = cid
                for att in attendances:
                    cid = sid_to_cid.get(att.session_id)
                    if cid is None:
                        continue
                    total_by_course[cid] += 1
                    if att.status == "Absent":
                        absent_by_course[cid] += 1

                for cid, last10 in course_to_last10.items():
                    absent = absent_by_course.get(cid, 0)
                    total = total_by_course.get(cid, 0)
                    if absent == 0 and total > 0:
                        course = course_map.get(cid)
                        if not course:
                            continue
                        alerts.append(AuditAlert(
                            type="perfect_attendance",
                            severity="medium",
                            title="حضور کامل مشکوک (احتمال تبانی)",
                            description=f"کلاس '{course.title}' (کد {course.code}) در ۱۰ جلسه اخیر هیچ غیبتی نداشته است ({total} رکورد حضور، ۰ غیبت) — نیاز به بررسی تبانی احتمالی",
                            entity_id=course.id,
                            entity_name=course.title,
                            detected_at=now_str
                        ))
    except Exception as e:
        logger.error(f"[Audit] Pattern C failed: {e}", exc_info=True)
        print(f"[Audit] Pattern C failed: {e}")

    return alerts

def count_suspicious_patterns(db: Session) -> int:
    """
    Lightweight COUNT for dashboard — reuses same optimized queries as get_suspicious_patterns
    but returns integer count only (no Alert objects, no string building).
    Used by dashboard to avoid full endpoint execution.
    """
    count = 0
    # Pattern A: night or delayed >5 circular
    try:
        session_logs = db.query(SessionLog).options(joinedload(SessionLog.course)).filter(SessionLog.is_deleted == False).all()
        for sl in session_logs:
            suspicious = False
            hour = _parse_hour(sl.time)
            if hour is not None and 0 <= hour < 5:
                suspicious = True
            if not suspicious:
                hour2 = _parse_hour(sl.start_time)
                if hour2 is not None and 0 <= hour2 < 5:
                    suspicious = True
            if not suspicious and sl.course_id and sl.course and sl.course.class_time:
                course_hour = _parse_hour(sl.course.class_time)
                session_hour = hour if hour is not None else _parse_hour(sl.start_time)
                if course_hour is not None and session_hour is not None:
                    if _circular_hour_diff(session_hour, course_hour) > 5:
                        suspicious = True
            if suspicious:
                count += 1
    except Exception as e:
        logger.error(f"[Audit] count Pattern A failed: {e}", exc_info=True)
        print(f"[Audit] count Pattern A failed: {e}")

    # Pattern B: rapid deletion <1h within 30 days via ActivityLog
    try:
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=30)
        deleted_txns = db.query(Transaction).options(joinedload(Transaction.student), joinedload(Transaction.course)).filter(Transaction.is_deleted == True).all()
        if deleted_txns:
            txn_ids = [t.id for t in deleted_txns]
            txn_map = {t.id: t for t in deleted_txns}
            logs_by_target = db.query(ActivityLog).filter(ActivityLog.target_id.in_(txn_ids), ActivityLog.timestamp >= cutoff).all()
            recent_logs_with_details = db.query(ActivityLog).filter(ActivityLog.timestamp >= cutoff).all()
            from collections import defaultdict
            logs_by_txn = defaultdict(list)
            for log in logs_by_target:
                logs_by_txn[log.target_id].append(log)
            for log in recent_logs_with_details:
                if log.details:
                    for tid in txn_ids:
                        if f"#{tid}" in log.details or f"تراکنش #{tid}" in log.details or f"#{tid} " in log.details:
                            if log not in logs_by_txn[tid]:
                                logs_by_txn[tid].append(log)
                        elif str(tid) in log.details and "تراکنش" in log.details:
                            if log not in logs_by_txn[tid]:
                                logs_by_txn[tid].append(log)
            for tid, logs in logs_by_txn.items():
                if not logs:
                    continue
                logs_sorted = sorted(logs, key=lambda x: x.timestamp or datetime.datetime.min)
                creation_logs = [l for l in logs_sorted if any(k in (l.action or "").lower() for k in ["create", "payment_success", "pay", "deposit", "online_payment"])]
                deletion_logs = [l for l in logs_sorted if any(k in (l.action or "").lower() for k in ["refund", "delete", "reversal", "reversed", "reversal"])]
                if not creation_logs and len(logs_sorted) >= 2:
                    creation_logs = [logs_sorted[0]]
                    deletion_logs = [logs_sorted[-1]]
                elif not deletion_logs and len(logs_sorted) >= 1:
                    continue
                is_rapid = False
                for c_log in creation_logs:
                    for d_log in deletion_logs:
                        if not c_log.timestamp or not d_log.timestamp:
                            continue
                        if d_log.timestamp < c_log.timestamp:
                            continue
                        diff_seconds = (d_log.timestamp - c_log.timestamp).total_seconds()
                        if 0 <= diff_seconds < 3600:
                            is_rapid = True
                            break
                    if is_rapid:
                        break
                if not is_rapid and len(logs_sorted) >= 2:
                    earliest = logs_sorted[0].timestamp
                    latest = logs_sorted[-1].timestamp
                    if earliest and latest and 0 <= (latest - earliest).total_seconds() < 3600:
                        if any(any(k in (l.action or "").lower() for k in ["refund","delete","reversal"]) for l in logs_sorted):
                            is_rapid = True
                if is_rapid:
                    count += 1
    except Exception as e:
        logger.error(f"[Audit] count Pattern B failed: {e}", exc_info=True)
        print(f"[Audit] count Pattern B failed: {e}")

    # Pattern C: perfect attendance last 10 sessions 0 absences
    try:
        courses = db.query(Course).filter(Course.is_deleted == False).all()
        if courses:
            course_ids = [c.id for c in courses]
            all_sessions = db.query(SessionLog).filter(SessionLog.course_id.in_(course_ids), SessionLog.is_deleted == False).order_by(SessionLog.course_id, desc(SessionLog.id)).all()
            from collections import defaultdict
            sessions_by_course = defaultdict(list)
            for s in all_sessions:
                sessions_by_course[s.course_id].append(s)
            relevant_sids = []
            course_to_last10 = {}
            for cid, sess_list in sessions_by_course.items():
                last10 = sess_list[:10]
                if len(last10) < 10:
                    continue
                course_to_last10[cid] = last10
                relevant_sids.extend([s.id for s in last10])
            if relevant_sids:
                attendances = db.query(Attendance).filter(Attendance.session_id.in_(relevant_sids)).all()
                from collections import defaultdict as _dd
                absent_by_course = defaultdict(int)
                total_by_course = defaultdict(int)
                sid_to_cid = {}
                for cid, sess_list in course_to_last10.items():
                    for s in sess_list:
                        sid_to_cid[s.id] = cid
                for att in attendances:
                    cid = sid_to_cid.get(att.session_id)
                    if cid is None:
                        continue
                    total_by_course[cid] += 1
                    if att.status == "Absent":
                        absent_by_course[cid] += 1
                for cid, last10 in course_to_last10.items():
                    absent = absent_by_course.get(cid, 0)
                    total = total_by_course.get(cid, 0)
                    if absent == 0 and total > 0:
                        count += 1
    except Exception as e:
        logger.error(f"[Audit] count Pattern C failed: {e}", exc_info=True)
        print(f"[Audit] count Pattern C failed: {e}")

    return count

