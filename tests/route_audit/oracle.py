"""Independent expected-value ledger for route-audit tests.

Only SQLAlchemy model rows and arithmetic appear here. No function from the
application's financial_calculations module is imported; using the production
calculation would turn the test into a tautology.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


@dataclass(frozen=True)
class EnrollmentExpected:
    enrollment_id: int
    gross_tuition: int
    discount: int
    net_tuition: int
    paid: int
    due: int


@dataclass
class LedgerExpected:
    enrollments: dict[int, EnrollmentExpected] = field(default_factory=dict)
    student_due: dict[int, int] = field(default_factory=dict)
    student_paid: dict[int, int] = field(default_factory=dict)
    teacher_receivable: dict[int, int] = field(default_factory=dict)
    institute_receivable: int = 0
    institute_cash: int = 0
    teacher_settled: dict[int, int] = field(default_factory=dict)
    monthly_cash: dict[str, int] = field(default_factory=dict)
    daily_cash: dict[str, int] = field(default_factory=dict)


def _discount(gross: int, kind: str | None, value: int | None) -> int:
    value = int(value or 0)
    if kind == "percentage":
        return min(gross, int((Decimal(gross) * Decimal(value) / Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)))
    if kind == "fixed":
        return min(gross, max(0, value))
    return 0


def _valid_positive_transaction(tx: Any) -> bool:
    return not bool(getattr(tx, "is_deleted", False) or getattr(tx, "is_reversed", False)) and int(tx.amount or 0) > 0


def build_oracle(db: Any) -> LedgerExpected:
    """Build expected money values directly from seed events and row semantics."""
    import models  # imported after the test has selected its temporary DATABASE_URL

    result = LedgerExpected()
    enrollments = {e.id: e for e in db.query(models.Enrollment).all()}
    for e in enrollments.values():
        gross = int(e.total_tuition or 0)
        discount = _discount(gross, e.discount_type, e.discount_value)
        net = max(0, gross - discount)
        paid = 0
        for tx in db.query(models.Transaction).filter(models.Transaction.enrollment_id == e.id).all():
            if _valid_positive_transaction(tx):
                paid += int(tx.amount or 0)
        expected = EnrollmentExpected(e.id, gross, discount, net, paid, max(0, net - paid))
        result.enrollments[e.id] = expected
        if not e.is_deleted:
            result.student_paid[e.student_id] = result.student_paid.get(e.student_id, 0) + paid
            result.student_due[e.student_id] = result.student_due.get(e.student_id, 0) + expected.due

    for tx in db.query(models.Transaction).all():
        if not _valid_positive_transaction(tx):
            continue
        amount = int(tx.amount or 0)
        if tx.target_wallet in ("institute", "both"):
            result.institute_cash += int(tx.share_institute or (amount if tx.target_wallet == "institute" else 0))
        if tx.target_wallet in ("teacher", "both"):
            # For a both receipt the event's explicit share is authoritative;
            # fallback is only for a legacy teacher-only event.
            teacher_amount = int(tx.share_teacher or (amount if tx.target_wallet == "teacher" else 0))
            course = db.query(models.Course).filter(models.Course.id == tx.course_id).first() if tx.course_id else None
            if course:
                result.teacher_receivable[course.teacher_id] = result.teacher_receivable.get(course.teacher_id, 0) + teacher_amount
        date = (tx.date or "").strip()
        if date:
            result.daily_cash[date] = result.daily_cash.get(date, 0) + (int(tx.share_institute or 0) if tx.target_wallet in ("institute", "both") else 0)
            result.monthly_cash[date[:7]] = result.monthly_cash.get(date[:7], 0) + (int(tx.share_institute or 0) if tx.target_wallet in ("institute", "both") else 0)

    # Session charges are separate events from tuition receipts. The oracle uses
    # explicit snapshots, never a production helper.
    for session in db.query(models.SessionLog).filter(models.SessionLog.is_deleted == False).all():
        if session.status in ("Cancelled", "لغو", "cancelled"):
            continue
        for attendance in db.query(models.Attendance).filter(models.Attendance.session_id == session.id, models.Attendance.is_deleted == False).all():
            if attendance.status in ("Present", "Late") or (attendance.status == "Absent" and not attendance.excused):
                result.institute_receivable += int(session.final_institute_share or 0)
                course = db.query(models.Course).filter(models.Course.id == session.course_id).first()
                if course:
                    result.teacher_receivable[course.teacher_id] = result.teacher_receivable.get(course.teacher_id, 0) + int(session.final_teacher_cost or 0)
    for settlement in db.query(models.Settlement).all():
        if not settlement.is_reversed:
            result.teacher_settled[settlement.teacher_id] = result.teacher_settled.get(settlement.teacher_id, 0) + int(settlement.total_amount or 0)
    return result


def assert_invariants(snapshot: LedgerExpected) -> None:
    assert all(v.due >= 0 for v in snapshot.enrollments.values())
    for sid, value in snapshot.student_due.items():
        assert value >= 0, sid
    for day, value in snapshot.daily_cash.items():
        assert value >= 0, day
