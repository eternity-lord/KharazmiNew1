"""Deterministic, isolated demo fixture for route-audit tests.

This module deliberately imports the application model only after the caller has
set DATABASE_URL. It never opens, writes, or migrates the repository database.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "Kharazmi_Server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))


def _guard_path(path: Path) -> Path:
    path = path.expanduser().resolve()
    production = (SERVER / "gaj_db.db").resolve()
    if path == production or path.name == "gaj_db.db":
        raise ValueError(f"refusing to seed the production database: {path}")
    if path.exists() and path.is_dir():
        raise ValueError(f"seed output must be a database file, not a directory: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _imports():
    # Environment must be set before models/dependencies are imported.
    import dependencies  # type: ignore
    import models  # type: ignore

    return models, dependencies


def _stable_password_hash(dependencies, password: str, identity: str) -> str:
    """Passlib PBKDF2 hash with a fixture-only, identity-scoped salt."""
    salt = hashlib.sha256(f"route-audit-seed-v1:{identity}".encode("utf-8")).digest()[:16]
    return dependencies.pbkdf2_sha256.using(salt=salt, rounds=29_000).hash(password)


def _stable_jwt(dependencies, user_id: int, role: str, now: dt.datetime) -> str:
    """Sign a reproducible JWT that remains valid independently of wall time."""
    header = {"alg": dependencies.JWT_ALGORITHM, "typ": "JWT"}
    issued = int(now.replace(tzinfo=dt.timezone.utc).timestamp())
    payload = {
        "user_id": user_id,
        "sub_role": role,
        "exp": issued + 10 * 365 * 24 * 60 * 60,
        "iat": issued,
        "jti": f"route-audit-seed-v1-{user_id}-{role}",
    }
    header_b64 = dependencies._b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = dependencies._b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(dependencies.JWT_SECRET_KEY.encode(), signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{dependencies._b64url_encode(signature)}"


def _freeze_model_timestamp_defaults(models, now: dt.datetime) -> None:
    """Pin Python-side ORM timestamp defaults for a byte-reproducible fixture."""
    for table in models.Base.metadata.tables.values():
        for column in table.columns:
            default = column.default
            callback = getattr(default, "arg", None)
            if (
                isinstance(column.type, models.DateTime)
                and callable(callback)
                and getattr(callback, "__name__", "") in {"now", "utcnow"}
            ):
                default.arg = lambda _context=None, fixed=now: fixed


def seed_database(path: str | Path, *, large: bool = False) -> dict[str, Any]:
    """Create the canonical demo database and return a JSON-serialisable manifest."""
    target = _guard_path(Path(path))
    os.environ["DATABASE_URL"] = f"sqlite:///{target}"
    os.environ.setdefault("JWT_SECRET_KEY", "route-audit-test-secret-" + "x" * 48)
    models, dependencies = _imports()
    now = dt.datetime(2026, 9, 28, 9, 0, 0)
    _freeze_model_timestamp_defaults(models, now)

    # A fresh target is safer than trying to make the fixture idempotent by
    # deleting rows in a shared database.
    if target.exists():
        target.unlink()
    models.Base.metadata.create_all(bind=models.engine)
    db = models.SessionLocal()
    manifest: dict[str, Any] = {"database": str(target), "seed_version": 1, "roles": {}, "ids": {}}
    try:
        Branch = models.Branch
        branch = Branch(id=1, name="شعبه مرکزی تست", address="تهران", phone="02100000000", manager="مدیر تست", active=True)
        branch2 = Branch(id=2, name="شعبه غرب تست", address="تهران غرب", phone="02100000001", manager="مدیر دوم", active=True)
        db.add_all([branch, branch2])

        User = models.User
        users = [
            User(id=1, username="audit-admin", password=_stable_password_hash(dependencies, "Admin-Route-1405!", "user:1"), full_name="ادمین ممیزی", role="admin", sub_role="admin", branch_id=None),
            User(id=2, username="audit-secretary", password=_stable_password_hash(dependencies, "Secretary-Route-1405!", "user:2"), full_name="منشی ممیزی", role="secretary", sub_role="secretary", branch_id=1),
            User(id=3, username="09120000001", password=_stable_password_hash(dependencies, "Teacher-Route-1405!", "user:3"), full_name="معلم فعال", role="teacher", sub_role="teacher", branch_id=1),
            User(id=4, username="audit-student", password=_stable_password_hash(dependencies, "Student-Route-1405!", "user:4"), full_name="دانش‌آموز تست", role="student", sub_role="student", branch_id=1),
            User(id=5, username="audit-parent", password=_stable_password_hash(dependencies, "Parent-Route-1405!", "user:5"), full_name="ولی تست", role="parent", sub_role="parent", branch_id=1),
        ]
        db.add_all(users)

        Teacher = models.Teacher
        teachers = [
            Teacher(id=1, teacher_code=1001, password="Teacher-Route-1405!", is_approved=True, is_suspended=False, is_deleted=False, branch_id=1, first_name="رضا", last_name="فعال", father_name="علی", national_code="0010000001", birth_date="1370/01/01", mobile="09120000001", home_phone="02100000001", marital_status="single", gender="male", employment_type="full", card_number="603700000001", wallet_balance=0),
            Teacher(id=2, teacher_code=1002, password="Teacher-Route-1405!", is_approved=True, is_suspended=True, is_deleted=False, branch_id=1, first_name="مریم", last_name="معلق", father_name="حسن", national_code="0010000002", birth_date="1368/02/02", mobile="09120000002", home_phone="02100000002", marital_status="married", gender="female", employment_type="part", card_number="603700000002", wallet_balance=0),
            Teacher(id=3, teacher_code=1003, password="Teacher-Route-1405!", is_approved=False, is_suspended=False, is_deleted=True, branch_id=2, first_name="معلم", last_name="حذف‌شده", father_name="حسین", national_code="0010000003", birth_date="1365/03/03", mobile="09120000003", home_phone="02100000003", marital_status="single", gender="male", employment_type="part", card_number="603700000003", wallet_balance=0),
        ]
        db.add_all(teachers)

        Room = models.Room
        rooms = [Room(id=1, name="اتاق آفتاب", capacity=20, location="طبقه اول", equipment="برد", active=True, branch_id=1), Room(id=2, name="اتاق آرشیو", capacity=10, location="طبقه دوم", equipment=None, active=False, branch_id=2)]
        db.add_all(rooms)
        db.flush()

        Course = models.Course
        course_specs = [
            (1, "ریاضی پایه فعال", "C-ACTIVE", 1, "ابتدایی", False, False, False, True),
            (2, "فیزیک دوکلاسه", "C-MULTI", 1, "متوسطه", False, False, False, True),
            (3, "زبان معلق", "C-SUSP", 2, "متوسطه", True, False, False, True),
            (4, "کلاس آرشیوی", "C-ARCH", 1, "عالی", False, False, True, True),
            (5, "کلاس در انتظار", "C-PEND", 1, "ابتدایی", False, False, False, False),
            (6, "کلاس ردشده", "C-REJ", 2, "متوسطه", False, False, False, False),
            (7, "کلاس معلم حذف‌شده", "C-DELETED-TEACHER", 3, "متوسطه", False, False, False, True),
        ]
        courses = []
        if large:
            for cid in range(8, 31):
                course_specs.append((cid, f"کلاس حجیم {cid}", f"C-BULK-{cid}", 1 if cid % 3 else 2, "متوسطه", False, False, False, True))
        for cid, title, code, tid, grade, suspended, paused, deleted, approved in course_specs:
            courses.append(Course(id=cid, title=title, branch_id=1 if cid % 2 else 2, code=code, teacher_id=tid, room_id=1, education_type="school", grade_level=grade, gender_type="mixed", class_type="خصوصی", days_of_week="شنبه,دوشنبه", class_time="16:00", teacher_session_price=250000 + cid * 10000, bg_color="#FFFFFF", rule_prepay_institute=True, rule_prepay_teacher=True, rule_calc_absent=True, is_admin_approved=approved, is_suspended=suspended, is_paused=paused, capacity=20, rejection_reason="ظرفیت تکمیل" if not approved else None, pending_since=now if not approved else None, is_deleted=deleted))
        db.add_all(courses)

        Student = models.Student
        count = 300 if large else 30
        students = []
        for sid in range(1, count + 1):
            if sid == 1:
                state = (False, False, 1, 1)
            elif sid == 2:
                state = (True, False, 1, 1)
            elif sid == 3:
                state = (False, True, 1, 1)
            else:
                state = (False, False, 1 if sid % 2 else 2, sid % 3)
            is_suspended, is_deleted, bid, _ = state
            students.append(Student(id=sid, student_code=2000 + sid, branch_id=bid, first_name="دانش‌آموز", last_name=f"تست {sid}", father_name="پدر تست", national_code=f"002000{sid:04d}", birth_date="1390/01/01", wallet_teacher=-10000 if sid == 1 else 0, wallet_institute=5000 if sid == 1 else 0, student_mobile=f"093500{sid:05d}", parent_mobile=f"093600{sid:05d}", home_phone="02100000000", address="آدرس تست", study_status="active", gender="mixed", is_suspended=is_suspended, is_deleted=is_deleted, wallet_balance=-5000 if sid == 1 else 0, profile_image=None, user_id=4 if sid == 1 else None, parent_user_id=5 if sid == 1 else None))
        db.add_all(students)
        db.flush()

        Enrollment = models.Enrollment
        enrollments = [
            Enrollment(id=1, student_id=1, course_id=1, branch_id=1, register_date="1405/06/01", shift="عصر", total_tuition=1_000_000, total_paid=300_000, discount_type="none", discount_value=0, is_deleted=False),
            Enrollment(id=2, student_id=1, course_id=2, branch_id=1, register_date="1405/06/02", shift="عصر", total_tuition=2_000_000, total_paid=500_000, discount_type="percentage", discount_value=10, is_deleted=False),
            Enrollment(id=3, student_id=2, course_id=1, branch_id=1, register_date="1405/06/03", shift="صبح", total_tuition=0, total_paid=0, discount_type="none", discount_value=0, is_deleted=False),
            Enrollment(id=4, student_id=3, course_id=3, branch_id=1, register_date="1405/06/04", shift="عصر", total_tuition=1_500_000, total_paid=250_000, discount_type="fixed", discount_value=200_000, is_deleted=False),
            Enrollment(id=5, student_id=4, course_id=1, branch_id=1, register_date="1405/06/05", shift="عصر", total_tuition=100_000, total_paid=0, discount_type="fixed", discount_value=200_000, is_deleted=False),
            Enrollment(id=6, student_id=5, course_id=4, branch_id=1, register_date="1405/05/01", shift="عصر", total_tuition=900_000, total_paid=900_000, discount_type="none", discount_value=0, is_deleted=True),
            Enrollment(id=7, student_id=6, course_id=1, branch_id=1, register_date="1405/06/06", shift="عصر", total_tuition=800_000, total_paid=0, discount_type="none", discount_value=0, is_deleted=False),
        ]
        if large:
            for sid in range(7, count + 1):
                enrollments.append(Enrollment(student_id=sid, course_id=1 + (sid % 2), branch_id=1 if sid % 2 else 2, register_date="1405/06/10", shift="عصر", total_tuition=500_000 + sid, total_paid=100_000, discount_type="none", discount_value=0, is_deleted=False))
        db.add_all(enrollments)
        db.flush()

        Transaction = models.Transaction
        txs = [
            Transaction(id=1, student_id=1, enrollment_id=1, course_id=1, amount=300_000, payment_method="نقدی", tracking_code="AUD-1", date="1405/06/03", receiver="آموزشگاه", description="پرداخت enrollment اول", type="deposit", share_teacher=0, share_institute=300_000, target_wallet="institute", is_deleted=False, is_reversed=False),
            Transaction(id=2, student_id=1, enrollment_id=2, course_id=2, amount=500_000, payment_method="کارت", tracking_code="AUD-2", date="1405/06/04", receiver="آموزشگاه", description="پرداخت split", type="deposit", share_teacher=250_000, share_institute=250_000, target_wallet="both", is_deleted=False, is_reversed=False),
            Transaction(id=3, student_id=3, enrollment_id=4, course_id=3, amount=250_000, payment_method="نقدی", tracking_code="AUD-3", date="1405/06/05", receiver="معلم", description="legacy no course", type="deposit", share_teacher=250_000, share_institute=0, target_wallet="teacher", is_deleted=False, is_reversed=False),
            Transaction(id=4, student_id=6, enrollment_id=None, course_id=None, amount=75_000, payment_method="کارت", tracking_code="AUD-4", date="", receiver="آموزشگاه", description="legacy بی‌تاریخ", type="deposit", share_teacher=0, share_institute=75_000, target_wallet="institute", is_deleted=False, is_reversed=False),
            Transaction(id=5, student_id=7, enrollment_id=7, course_id=1, amount=100_000, payment_method="کارت", tracking_code="AUD-5", date="1405/06/07", receiver="آموزشگاه", description="برگشتی", type="reversal", share_teacher=0, share_institute=100_000, target_wallet="institute", is_deleted=False, is_reversed=True),
            # Gregorian-dated card receipt without an enrollment exercises mixed-calendar reporting.
            Transaction(id=6, student_id=8, enrollment_id=None, course_id=2, amount=125_000, payment_method="کارت به کارت", tracking_code="AUD-6", date="2026-09-20", receiver="معلم", description="پرداخت کارتی میلادی legacy", type="deposit", share_teacher=125_000, share_institute=0, target_wallet="teacher", is_deleted=False, is_reversed=False),
        ]
        db.add_all(txs)

        SessionLog = models.SessionLog
        sessions = [
            SessionLog(id=1, session_code=5001, course_id=1, date="1405/06/10", time="16:00", final_teacher_cost=450_000, final_institute_share=150_000, cost_per_student=200_000, attendee_count=3, status="Finished", start_time="16:00", end_time="17:30", is_deleted=False),
            SessionLog(id=2, session_code=5002, course_id=2, date="1405/06/11", time="16:00", final_teacher_cost=300_000, final_institute_share=100_000, cost_per_student=150_000, attendee_count=1, status="InProgress", start_time="16:00", end_time=None, is_deleted=False),
            SessionLog(id=3, session_code=5003, course_id=1, date="1405/06/12", time="16:00", final_teacher_cost=450_000, final_institute_share=150_000, cost_per_student=200_000, attendee_count=0, status="Cancelled", start_time=None, end_time=None, is_deleted=True),
        ]
        db.add_all(sessions)
        db.flush()
        Attendance = models.Attendance
        db.add_all([
            Attendance(session_id=1, student_id=1, status="Present", is_deleted=False, is_billed=True, excused=False),
            Attendance(session_id=1, student_id=2, status="Late", is_deleted=False, is_billed=True, excused=False),
            Attendance(session_id=1, student_id=3, status="Absent", is_deleted=False, is_billed=False, excused=True),
            Attendance(session_id=2, student_id=1, status="Present", is_deleted=False, is_billed=False, excused=False),
        ])

        LiveSession = models.LiveSession
        # Wall-clock dependent routes use tests.route_audit.clock.FIXED_NOW. Keep
        # the live payload deterministic and fractional to exercise Gson Long parsing.
        live_started = now
        db.add_all([
            LiveSession(id=1, course_id=2, teacher_id=1, status="LIVE", start_time=live_started.strftime("%Y-%m-%dT%H:%M:%S"), started_at_ts=live_started.timestamp() + 0.25, live_roster=json.dumps({"1": {"status": "Present", "excused": False}}, ensure_ascii=False)),
            LiveSession(id=2, course_id=1, teacher_id=1, status="ENDED", start_time="2026-09-27T08:00:00", end_time="2026-09-27T09:00:00", ended_automatically=True),
        ])

        Installment = models.Installment
        db.add_all([
            Installment(id=1, enrollment_id=1, amount=350_000, due_date="1405/06/01", is_paid=False, paid_at=None, paid_amount=0, is_deleted=False),
            Installment(id=2, enrollment_id=1, amount=350_000, due_date="1405/07/01", is_paid=False, paid_at=None, paid_amount=100_000, is_deleted=False),
            Installment(id=3, enrollment_id=2, amount=500_000, due_date="1405/06/20", is_paid=True, paid_at="1405/06/20", paid_amount=500_000, is_deleted=False),
            Installment(id=4, enrollment_id=6, amount=100_000, due_date="1405/05/01", is_paid=False, paid_at=None, paid_amount=0, is_deleted=True),
        ])

        Grade = models.Grade
        db.add_all([Grade(id=1, student_id=1, course_id=1, teacher_id=1, exam_title="میان‌ترم", score=18.5, max_score=20.0, date="1405/06/15", description="خوب"), Grade(id=2, student_id=2, course_id=1, teacher_id=1, exam_title="ریاضی", score=12.5, max_score=20.0, date="1405/06/15", description=None)])
        Homework = models.Homework
        db.add_all([Homework(id=1, course_id=1, teacher_id=1, title="تمرین هفته", description="حل تمرین", due_date="1405/07/01", max_score=20.0, status="pending")])
        db.flush()
        db.add(models.HomeworkSubmission(id=1, homework_id=1, student_id=1, file_path="demo.pdf", status="submitted", score=None, feedback=None))
        Exam = models.Exam
        db.add_all([Exam(id=1, title="آزمون منتشرشده", course_id=1, teacher_id=1, date="1405/06/25", duration=60, max_score=20.0, status="published"), Exam(id=2, title="آزمون پیش‌نویس", course_id=2, teacher_id=1, date="1405/07/01", duration=45, max_score=20.0, status="pending")])
        db.flush()
        db.add_all([models.ExamQuestion(id=1, exam_id=1, question_text="۲+۲؟", type="short_answer", options=None, correct_answer="۴", score_weight=1.0), models.ExamAttempt(id=1, exam_id=1, student_id=1, started_at=now, submitted_at=now, score=19.0, graded_by_teacher=True)])
        db.add_all([models.Notification(id=1, recipient_user_id=1, recipient_role="admin", type="payment", title="پرداخت تست", body="اعلان تست", data="{}", is_read=False, priority=1), models.SmsLog(id=1, target_group="test", message_text="پیام mock تست", sent_count=0, date="1405/06/15")])
        db.add(models.InstituteSettings(id=1, name="آموزشگاه ممیزی", address="تهران", phone="02100000000", official_email="audit@example.test", footer_text="پاورقی تست", card_number="6037000000000000", teachers_active=True, live_session_max_minutes=180, teacher_settlement_alert_days=30))
        db.add_all([models.InstituteShare(id=1, **{f"count_{i}": 10_000 * i for i in range(1, 16)}), models.PricingTable(id=1, category="elementary", count_1=100, count_2=200, count_3=300, count_4=400, count_5=500)])
        db.add_all([models.Lead(id=1, name="سرنخ تست", mobile="09120000999", interested_course="ریاضی", source="Demo", status="NEW", notes="seed", branch_id=1), models.AutomationRule(id=1, name="قسط معوق", condition_type="installment_overdue", threshold=1, action_type="parent_alert", active=True), models.AutomationLog(id=1, rule_id=1, triggered_at=now, details="seed")])
        db.add_all([models.ActivityLog(id=1, admin_username="audit-admin", action="seed", target_id=1, target_name="demo", details="route audit seed", timestamp=now)])
        # One staff-owned conversation makes history/send/pin list smoke routes
        # exercise a valid participant state without contacting a real provider.
        conversation = models.Conversation(id=1, title="گفتگوی ممیزی", type="group", created_at=now)
        db.add(conversation)
        db.add(models.ConversationParticipant(id=1, conversation_id=1, user_id=1, role="admin"))
        db.add(models.Message(id=1, conversation_id=1, sender_id=1, sender_role="admin", body="پیام seed", created_at=now, is_deleted=False))
        db.flush()

        # Fixed claims and identity-specific jti make the entire SQLite fixture
        # byte-for-byte reproducible; the token signing secret is test-only.
        for user, role in [(users[0], "admin"), (users[1], "secretary"), (users[2], "teacher"), (users[3], "student"), (users[4], "parent")]:
            token = _stable_jwt(dependencies, user.id, role, now)
            db.add(models.UserSession(user_id=user.id, teacher_id=1 if role == "teacher" else None, sub_role=role, token=token, created_at=now))
            manifest["roles"][role] = token
        manifest["ids"].update({"branch": 1, "active_course": 1, "second_course": 2, "student": 1, "multi_course_student": 1, "enrollment": 1, "session": 1, "installment": 1, "exam": 1})
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    manifest["counts"] = {name: db_count(target, name) for name in ("users", "teachers", "students", "courses", "enrollments", "transactions", "session_logs", "attendances", "installments", "grades", "homeworks", "exams", "crm_leads")}
    return manifest


def db_count(path: Path, table: str) -> int:
    # A tiny independent sqlite read avoids relying on a Session object after close.
    import sqlite3
    con = sqlite3.connect(path)
    try:
        return int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        con.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Create isolated route-audit demo data")
    parser.add_argument("output", type=Path)
    parser.add_argument("--large", action="store_true", help="also create the 300-student/30-class scale variant")
    args = parser.parse_args()
    print(json.dumps(seed_database(args.output, large=args.large), ensure_ascii=False, indent=2))
