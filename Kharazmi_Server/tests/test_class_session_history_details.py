"""تاریخچهٔ جلسات صفحهٔ کلاس — TEST-ONLY (فقط تست؛ کد اصلی تغییری نکرده است).

خواستهٔ کاربر (اسکرین‌شات کلاس ۱۰۰۰۰۲): در تب «تاریخچه جلسات» به‌جای فقط عدد حاضرین/غایبین،
نام خودِ حاضرین و غایبین و روز هفته کنار تاریخ نوشته شود.

قواعد تحت آزمون (بدون هیچ تغییر مالی — این‌ها فقط خواندنی‌اند):
- `GET /classes/{id}/full_report` ⇒ `sessions[]` علاوه بر `present_count`/`absent_count`
  شامل `weekday` (روز هفتهٔ شمسی)، `present_students[]`، `absent_students[]` (نام + وضعیت)،
  هزینهٔ جلسه و ساعت (وقتی وجود دارد) است.
- «Late» مثل بقیهٔ اپ حاضر حساب می‌شود و با برچسب `status="Late"` می‌آید.
- غیبت موجه با `excused=True` می‌آید.
- شمارش‌ها با لیست نام‌ها هم‌خوان‌اند (جمع هر دو منبع یکی است).
- ترتیب جلسات بر اساس ترتیب ثبت (id) است تا «جلسه ۱، ۲، …» پایدار باشد.
"""
import datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from schemas import AttendanceItem, AttendanceSubmitData
from routers import attendance, classes

TOKEN = "class-history-token"
# ۲۰۲۶/۰۹/۲۹ (میلادی) = سه‌شنبه؛ مبدل پروژه آن را به شمسی کانونیکال تبدیل می‌کند.
GREG_DATE = "2026/09/29"
EXPECTED_WEEKDAY = "سه‌شنبه"
GREG_DATE_2 = "2026/09/30"
EXPECTED_WEEKDAY_2 = "چهارشنبه"


def make_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    models.Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def world():
    engine = make_engine()
    with sessionmaker(bind=engine, expire_on_commit=False)() as db:
        db.add_all([
            models.Branch(id=1, name="شعبه تست", active=True),
            models.User(id=1, username="hist-admin", password="unused", role="admin",
                        sub_role="admin", branch_id=1),
            models.Teacher(id=1, teacher_code=201, first_name="معلم", last_name="تاریخچه",
                           mobile="09120000201", branch_id=1),
            models.Student(id=201, student_code=555201, first_name="زهرا", last_name="حاضر",
                           national_code="H-201", student_mobile="09121110201",
                           parent_mobile="09122220201", branch_id=1,
                           wallet_teacher=0, wallet_institute=0, wallet_balance=0),
            models.Student(id=202, student_code=555202, first_name="محمد", last_name="با‌تأخیر",
                           national_code="H-202", student_mobile="09121110202",
                           parent_mobile="09122220202", branch_id=1,
                           wallet_teacher=0, wallet_institute=0, wallet_balance=0),
            models.Student(id=203, student_code=555203, first_name="رضا", last_name="غایب‌موجه",
                           national_code="H-203", student_mobile="09121110203",
                           parent_mobile="09122220203", branch_id=1,
                           wallet_teacher=0, wallet_institute=0, wallet_balance=0),
            models.InstituteShare(count_1=40, count_2=80, count_3=120),
            models.UserSession(token=TOKEN, user_id=1, sub_role="admin",
                               created_at=datetime.datetime.now()),
        ])
        db.flush()
        db.add(models.Course(
            id=1, title="کلاس تاریخچه", code="HIST-1", teacher_id=1, branch_id=1,
            grade_level="دهم", teacher_session_price=60, is_admin_approved=True,
            rule_calc_absent=True,
        ))
        db.flush()
        db.add_all([
            models.Enrollment(student_id=201, course_id=1, branch_id=1, total_tuition=1000,
                              total_paid=0, register_date=GREG_DATE),
            models.Enrollment(student_id=202, course_id=1, branch_id=1, total_tuition=1000,
                              total_paid=0, register_date=GREG_DATE),
            models.Enrollment(student_id=203, course_id=1, branch_id=1, total_tuition=1000,
                              total_paid=0, register_date=GREG_DATE),
        ])
        db.commit()
        yield db
    models.Base.metadata.drop_all(engine)
    engine.dispose()


def _submit(db, date, items):
    return attendance.submit_session_and_calculate(
        AttendanceSubmitData(course_id=1, date=date, items=items),
        db=db, authorization=f"Bearer {TOKEN}", sub_role="admin",
    )


def _report(db):
    return classes.get_class_full_report(
        id=1, db=db, authorization=f"Bearer {TOKEN}", sub_role="admin",
    )


def test_session_history_has_names_weekday_and_costs(world):
    # یک جلسه: یکی حاضر، یکی با تأخیر، یکی غایب موجه.
    result = _submit(world, GREG_DATE, [
        AttendanceItem(student_id=201, status="Present"),
        AttendanceItem(student_id=202, status="Late"),
        AttendanceItem(student_id=203, status="Absent", excused=True),
    ])

    report = _report(world)
    assert len(report.sessions) == 1
    session = report.sessions[0]

    # روز هفته (کانونیکال شمسی ذخیره می‌شود ولی روزِ هفته همان سه‌شنبه می‌ماند).
    assert session.weekday == EXPECTED_WEEKDAY, (
        f"روز هفتهٔ {GREG_DATE} باید «{EXPECTED_WEEKDAY}» باشد، نه «{session.weekday}»"
    )
    assert session.date != GREG_DATE  # تاریخ کانونیکال شمسی

    # حاضرین: Present + Late (قرارداد بقیهٔ اپ)، با نام واقعی.
    assert session.present_count == 2
    present_by_id = {row.student_id: row for row in session.present_students}
    assert set(present_by_id) == {201, 202}
    assert present_by_id[201].name == "زهرا حاضر"
    assert present_by_id[201].status == "Present"
    assert present_by_id[202].name == "محمد با‌تأخیر"
    assert present_by_id[202].status == "Late"

    # غایب موجه با نام و پرچم موجه.
    assert session.absent_count == 1
    assert [row.student_id for row in session.absent_students] == [203]
    assert session.absent_students[0].name == "رضا غایب‌موجه"
    assert session.absent_students[0].excused is True
    assert session.present_students[0].excused is False

    # شمارش‌ها و نام‌ها هم‌خوان: total هزینه = سهم واقعیِ همان ثبت جلسه.
    details = result["details"]
    assert session.present_count == details["present_count"]
    assert session.total_cost == (
        details["teacher_share"] + details["institute_share"]
        + details["absent_penalty_teacher"] + details["absent_penalty_institute"]
    )
    assert session.cost_per_student == details["cost_per_student"]
    assert session.session_id == result["session_id"]
    assert session.session_code == result["session_code"]


def test_session_history_lists_sessions_in_registration_order(world):
    first = _submit(world, GREG_DATE, [
        AttendanceItem(student_id=201, status="Present"),
        AttendanceItem(student_id=202, status="Present"),
        AttendanceItem(student_id=203, status="Absent", excused=False),
    ])
    second = _submit(world, GREG_DATE_2, [
        AttendanceItem(student_id=201, status="Present"),
        AttendanceItem(student_id=202, status="Present"),
        AttendanceItem(student_id=203, status="Present"),
    ])

    report = _report(world)
    assert [row.session_id for row in report.sessions] == [first["session_id"], second["session_id"]]
    assert [row.weekday for row in report.sessions] == [EXPECTED_WEEKDAY, EXPECTED_WEEKDAY_2]
    # جلسهٔ دوم: همه حاضر (غایب غیرموجه هم فقط یک‌بار برای همان تاریخ قابل ثبت است).
    assert report.sessions[1].present_count == 3
    assert report.sessions[1].absent_count == 0
    assert [row.name for row in report.sessions[1].present_students] == [
        "زهرا حاضر", "محمد با‌تأخیر", "رضا غایب‌موجه",
    ]


def test_archived_attendance_rows_do_not_enter_history(world):
    _submit(world, GREG_DATE, [
        AttendanceItem(student_id=201, status="Present"),
        AttendanceItem(student_id=202, status="Present"),
        AttendanceItem(student_id=203, status="Present"),
    ])
    # FIX (F-S2): ردیف آرشیوشده نباید در تاریخچه بیاید (و شمارش/نام‌ها با هم بمانند).
    world.query(models.Attendance).filter(models.Attendance.student_id == 203).update(
        {models.Attendance.is_deleted: True}, synchronize_session=False
    )
    world.commit()

    report = _report(world)
    session = report.sessions[0]
    assert session.present_count == 2
    assert {row.student_id for row in session.present_students} == {201, 202}
    assert session.absent_count == 0
    assert session.absent_students == []
