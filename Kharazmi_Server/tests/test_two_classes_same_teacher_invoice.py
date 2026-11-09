"""«دانش‌آموز در دو کلاسِ یک معلم» + ثبت حوالهٔ جلسه‌محور — جریان واقعی، نه داده‌ی دستی.

گزارش کاربر (پاپ‌آپ «انتخاب کلاس» صدور حواله): یک دانش‌آموز دو کلاس هم‌معلم دارد (کد ۱۰۰۰۰۱ و ۱۰۰۰۰۲)،
فقط یک جلسه در یکی از آن‌ها بوده، اما «بدهی به معلم / بدهی به آموزشگاه» برای هر دو کلاس یکسان (جمع دو کلاس)
نمایش داده می‌شد. این تست سناریو را با مسیر واقعیِ ثبت جلسه (`submit_session_and_calculate`) می‌سازد و تک‌تک
سطوحِ نمایش (بنر کلاس، لیست دانش‌آموزان، اطلاعات کلاس، پروفایل دانش‌آموز، پاپ‌آپ صدور حواله) را می‌سنجد.

قواعد تحت آزمون:
- بدهی هر کلاس فقط از جلسه‌های همان کلاس می‌آید؛ کلاس بدون جلسه صفر است.
- برای هر کلاس «چند جلسه» و فهرست جلسه‌های پرداخت‌نشده (FIFO) می‌آید و جمعش = بدهی همان کلاس است.
- «بدهی بدون کلاس» شارژ جلسهٔ کلاس‌ها را دوباره نشان نمی‌دهد (جمع دو کلاس نشت نمی‌کند).
- حواله با `sessions_covered` ذخیره می‌شود و رسید/چاپ نام معلم، کد کلاس، تعداد جلسه و کیف‌پول را دارد.
- درخواست قدیمی (بدون `sessions_covered`) دقیقاً مثل قبل کار می‌کند.
"""
import datetime

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from financial_calculations import calculate_enrollment_debt_breakdown, calculate_student_debt
from routers import admin, attendance, classes, finance
from schemas import AttendanceItem, AttendanceSubmitData, FinanceSubmitData, PrintReceiptRequest

TOKEN = "two-classes-token"
AUTH = f"Bearer {TOKEN}"
TEACHER_NAME = "علی احمدی"
TEACHER_PRICE = 600_000   # سهم معلم هر جلسه (همان عدد اسکرین‌شات کاربر)
INSTITUTE_SHARE = 60_000  # سهم آموزشگاه هر جلسه (همان عدد اسکرین‌شات کاربر)
DATE_1 = "2026/09/26"
DATE_2 = "2026/09/29"


def _engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    models.Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def world():
    engine = _engine()
    with sessionmaker(bind=engine, expire_on_commit=False)() as db:
        db.add_all([
            models.Branch(id=1, name="شعبه تست", active=True),
            models.User(id=1, username="admin", password="x", role="admin", sub_role="admin", branch_id=1),
            models.Teacher(id=1, teacher_code=1, first_name="علی", last_name="احمدی",
                           mobile="09120000001", branch_id=1),
            models.Student(id=1, student_code=900001, first_name="مرضیه", last_name="ایرانی",
                           national_code="M-1", student_mobile="09121110001", parent_mobile="09122220001",
                           branch_id=1, wallet_teacher=0, wallet_institute=0, wallet_balance=0),
            models.InstituteShare(count_1=INSTITUTE_SHARE, count_2=2 * INSTITUTE_SHARE, count_3=3 * INSTITUTE_SHARE),
            models.UserSession(token=TOKEN, user_id=1, sub_role="admin", created_at=datetime.datetime.now()),
        ])
        db.flush()
        for course_id, code in ((1, "100001"), (2, "100002")):
            db.add(models.Course(
                id=course_id, title="ریاضی", code=code, teacher_id=1, branch_id=1, grade_level="دهم",
                teacher_session_price=TEACHER_PRICE, is_admin_approved=True, rule_calc_absent=True,
            ))
        db.flush()
        for course_id in (1, 2):
            db.add(models.Enrollment(student_id=1, course_id=course_id, branch_id=1, total_tuition=0,
                                     total_paid=0, register_date=DATE_1))
        db.commit()
        yield db
    models.Base.metadata.drop_all(engine)
    engine.dispose()


def _session(db, course_id, date):
    return attendance.submit_session_and_calculate(
        AttendanceSubmitData(course_id=course_id, date=date,
                             items=[AttendanceItem(student_id=1, status="Present")]),
        db=db, authorization=AUTH, sub_role="admin",
    )


def _enrollment(db, course_id):
    return db.query(models.Enrollment).filter(models.Enrollment.course_id == course_id).one()


def _pay(db, **kwargs):
    payload = dict(student_id=1, payment_method="نقدی", date="1405/07/07", description="تست")
    payload.update(kwargs)
    return finance.submit_payment(FinanceSubmitData(**payload), db=db, _="admin", branch_id=None, authorization=AUTH)


def test_one_session_in_one_class_never_leaks_into_the_other_class_on_any_screen(world):
    db = world
    _session(db, 2, DATE_2)  # فقط کلاس ۱۰۰۰۰۲ جلسه داشته

    a, b = _enrollment(db, 1), _enrollment(db, 2)
    bd_a, bd_b = calculate_enrollment_debt_breakdown(db, a), calculate_enrollment_debt_breakdown(db, b)
    assert (bd_a["debt_teacher"], bd_a["debt_institute"]) == (0, 0)
    assert (bd_b["debt_teacher"], bd_b["debt_institute"]) == (TEACHER_PRICE, INSTITUTE_SHARE)

    # بنر کلاس‌ها
    banner = {row["id"]: row for row in classes.get_all_classes(db=db, _="admin")}
    assert (banner[1]["debt_to_teacher"], banner[1]["debt_to_institute"]) == (0, 0)
    assert (banner[2]["debt_to_teacher"], banner[2]["debt_to_institute"]) == (TEACHER_PRICE, INSTITUTE_SHARE)

    # لیست دانش‌آموزان کلاس + تعداد جلسه
    rows = {}
    for cid in (1, 2):
        data = classes.get_class_students_full(id=cid, db=db, authorization=AUTH, sub_role="admin")
        rows[cid] = data["students"][0]
    assert (rows[1]["debt_teacher"], rows[1]["debt_institute"]) == (0, 0)
    assert (rows[2]["debt_teacher"], rows[2]["debt_institute"]) == (TEACHER_PRICE, INSTITUTE_SHARE)
    assert (rows[1]["sessions_billed"], rows[1]["unpaid_sessions"]) == (0, 0)
    assert (rows[2]["sessions_billed"], rows[2]["unpaid_sessions"]) == (1, 1)

    # پروفایل دانش‌آموز (پاپ‌آپ انتخاب کلاس + تفکیک کلاس‌ها)
    profile = admin.get_student_full_profile(id=1, authorization=AUTH, db=db, role="admin")
    picker = {row["course_id"]: row for row in profile["enrollments"]}
    assert (picker[1]["debt_teacher"], picker[1]["debt_institute"]) == (0, 0)
    assert (picker[2]["debt_teacher"], picker[2]["debt_institute"]) == (TEACHER_PRICE, INSTITUTE_SHARE)
    assert picker[2]["teacher_name"] == TEACHER_NAME and picker[2]["code"] == "100002"
    assert (picker[1]["sessions_billed"], picker[2]["sessions_billed"]) == (0, 1)
    assert picker[2]["unpaid_sessions"] == 1
    fin = {row["course_id"]: row for row in profile["teachers_financial"] if not row["is_unassigned"]}
    assert (fin[2]["debt_teacher"], fin[2]["debt_institute"]) == (TEACHER_PRICE, INSTITUTE_SHARE)
    assert fin[2]["course_code"] == "100002"
    # «بدهی بدون کلاس» نباید شارژ جلسهٔ همین کلاس‌ها را یک بار دیگر (جمع دو کلاس) نشان دهد.
    assert not [row for row in profile["teachers_financial"] if row["is_unassigned"]]
    assert profile["unassigned_debt"] == 0

    # وضعیت کلاس‌محور (بعد از انتخاب کلاس در صدور حواله)
    st_a = finance.get_student_class_status(student_id=1, course_id=1, db=db, authorization=AUTH, sub_role="admin")
    st_b = finance.get_student_class_status(student_id=1, course_id=2, db=db, authorization=AUTH, sub_role="admin")
    assert (st_a["due_to_teacher"], st_a["due_to_institute"], st_a["unpaid_sessions"]) == (0, 0, 0)
    assert (st_b["due_to_teacher"], st_b["due_to_institute"], st_b["unpaid_sessions"]) == (TEACHER_PRICE, INSTITUTE_SHARE, 1)
    assert st_b["teacher_name"] == TEACHER_NAME and st_b["course_code"] == "100002"
    assert st_b["session_unit_teacher"] == TEACHER_PRICE and st_b["session_unit_institute"] == INSTITUTE_SHARE
    assert [i["remaining_teacher"] for i in st_b["unpaid_session_items"]] == [TEACHER_PRICE]

    # جستجوی مالی بر پایهٔ کلاس (انتخاب سریع)
    found = finance.search_finance_advanced(query="100002", branch_id=None, authorization=AUTH, db=db, sub_role="admin")
    klass = next(item for item in found if item.type == "class")
    row = klass.students_in_class[0]
    assert (row["debt_teacher"], row["debt_institute"], row["unpaid_sessions"]) == (TEACHER_PRICE, INSTITUTE_SHARE, 1)
    assert row["teacher_name"] == TEACHER_NAME and row["course_code"] == "100002"


def test_unassigned_row_only_shows_real_unlinked_legacy_debt(world):
    db = world
    _session(db, 2, DATE_2)
    student = db.query(models.Student).one()
    # کسری کیف پول که به هیچ جلسه/کلاسی وصل نیست (legacy)
    student.wallet_teacher = (student.wallet_teacher or 0) - 1_000
    db.commit()

    profile = admin.get_student_full_profile(id=1, authorization=AUTH, db=db, role="admin")
    unassigned = [row for row in profile["teachers_financial"] if row["is_unassigned"]]
    class_total = sum(row["debt_teacher"] + row["debt_institute"]
                      for row in profile["teachers_financial"] if not row["is_unassigned"])
    assert class_total == TEACHER_PRICE + INSTITUTE_SHARE
    assert len(unassigned) == 1 and unassigned[0]["debt"] == 1_000
    assert class_total + profile["unassigned_debt"] == calculate_student_debt(db, student)


def test_unpaid_sessions_are_fifo_and_sum_to_the_class_debt(world):
    db = world
    _session(db, 2, DATE_1)
    _session(db, 2, DATE_2)
    en = _enrollment(db, 2)

    bd = calculate_enrollment_debt_breakdown(db, en)
    assert bd["sessions_billed"] == 2 and bd["unpaid_sessions"] == 2 and bd["sessions_held"] == 2
    assert bd["debt_teacher"] == 2 * TEACHER_PRICE and bd["debt_institute"] == 2 * INSTITUTE_SHARE

    # پرداخت دقیقاً یک جلسه (هر دو سهم) برای «۱ جلسه»
    result = _pay(db, amount=TEACHER_PRICE, target_wallet="both", amount_teacher=TEACHER_PRICE,
                  amount_institute=INSTITUTE_SHARE, enrollment_id=en.id, sessions_covered=1)
    assert result["sessions_covered"] == 1

    bd = calculate_enrollment_debt_breakdown(db, en)
    assert bd["sessions_billed"] == 2 and bd["unpaid_sessions"] == 1
    assert bd["debt_teacher"] == TEACHER_PRICE and bd["debt_institute"] == INSTITUTE_SHARE
    assert sum(i["remaining_teacher"] for i in bd["unpaid_session_items"]) == bd["debt_teacher"]
    assert sum(i["remaining_institute"] for i in bd["unpaid_session_items"]) == bd["debt_institute"]
    # قدیمی‌ترین جلسه تسویه شده؛ جلسهٔ دوم مانده است
    assert len(bd["unpaid_session_items"]) == 1

    # پرداخت جزئی سهم معلم: جلسه هنوز «پرداخت‌نشده» حساب می‌شود
    _pay(db, amount=100_000, target_wallet="teacher", enrollment_id=en.id)
    bd = calculate_enrollment_debt_breakdown(db, en)
    assert bd["unpaid_sessions"] == 1
    assert bd["unpaid_session_items"][0]["remaining_teacher"] == TEACHER_PRICE - 100_000

    # پرداخت مازاد = اعتبار، نه بدهی منفی
    _pay(db, amount=TEACHER_PRICE, target_wallet="teacher", enrollment_id=en.id)
    bd = calculate_enrollment_debt_breakdown(db, en)
    assert bd["debt_teacher"] == 0 and bd["credit_teacher"] == 100_000
    assert bd["unpaid_sessions"] == 1  # سهم آموزشگاه هنوز مانده


def test_payment_stores_sessions_and_receipt_shows_teacher_class_sessions_wallet(world):
    db = world
    _session(db, 2, DATE_2)
    en = _enrollment(db, 2)

    result = _pay(db, amount=TEACHER_PRICE, target_wallet="both", amount_teacher=TEACHER_PRICE,
                  amount_institute=INSTITUTE_SHARE, enrollment_id=en.id, sessions_covered=1)
    assert len(result["receipt_ids"]) == 2
    rows = {t.target_wallet: t for t in db.query(models.Transaction).filter(
        models.Transaction.id.in_(result["receipt_ids"])).all()}
    assert rows["teacher"].sessions_covered == 1 and rows["institute"].sessions_covered == 1
    assert rows["teacher"].enrollment_id == en.id and rows["teacher"].course_id == 2

    teacher_receipt = finance.get_receipt_details(rows["teacher"].id, db=db, authorization=AUTH, _role="admin")
    assert teacher_receipt["amount"] == TEACHER_PRICE
    assert teacher_receipt["teacher_name"] == TEACHER_NAME
    assert teacher_receipt["course_name"] == "ریاضی" and teacher_receipt["course_code"] == "100002"
    assert teacher_receipt["sessions_covered"] == 1
    assert teacher_receipt["wallet_label"] == "سهم معلم" and teacher_receipt["paid_to_name"] == TEACHER_NAME
    assert teacher_receipt["class_remaining_teacher"] == 0 and teacher_receipt["class_remaining_institute"] == 0

    inst_receipt = finance.get_receipt_details(rows["institute"].id, db=db, authorization=AUTH, _role="admin")
    assert inst_receipt["amount"] == INSTITUTE_SHARE
    assert inst_receipt["wallet_label"] == "سهم آموزشگاه" and inst_receipt["paid_to_name"] == "آموزشگاه"
    assert inst_receipt["teacher_name"] == TEACHER_NAME  # کلاس همان معلم است

    for endpoint in (finance.print_receipt, finance.generate_pdf_receipt):
        data = endpoint(PrintReceiptRequest(transaction_id=rows["teacher"].id, print_type="print"),
                        db=db, authorization=AUTH, _="admin")["receipt_data"]
        assert data["teacher_name"] == TEACHER_NAME and data["sessions_covered"] == 1
        assert data["course_code"] == "100002" and data["wallet_label"] == "سهم معلم"


def test_legacy_payload_without_sessions_is_unchanged(world):
    db = world
    _session(db, 2, DATE_2)
    en = _enrollment(db, 2)
    result = _pay(db, amount=1_000, target_wallet="teacher", enrollment_id=en.id)
    assert result["sessions_covered"] is None
    txn = db.query(models.Transaction).filter(models.Transaction.id == result["receipt_id"]).one()
    assert txn.sessions_covered is None
    receipt = finance.get_receipt_details(txn.id, db=db, authorization=AUTH, _role="admin")
    assert receipt["sessions_covered"] is None
    assert receipt["teacher_name"] == TEACHER_NAME  # حتی رسید قدیمی هم نام معلم را دارد
    assert receipt["course_name"] == "ریاضی"


def test_sessions_covered_validation(world):
    db = world
    _session(db, 2, DATE_2)
    for bad in (0, -1, 1001):
        with pytest.raises(ValidationError):
            FinanceSubmitData(student_id=1, amount=10, target_wallet="teacher", description="x",
                              payment_method="نقدی", date="1405/07/07", sessions_covered=bad)
    # بدون کلاس مشخص، «تعداد جلسه» معنا ندارد — و دانش‌آموز دوکلاسه اصلاً بدون enrollment پرداخت نمی‌کند.
    with pytest.raises(HTTPException) as raised:
        _pay(db, amount=10, target_wallet="teacher", sessions_covered=1)
    assert raised.value.status_code == 400
    # هیچ پرداختی ثبت نشده
    assert db.query(models.Transaction).filter(models.Transaction.type == "deposit").count() == 0
    # ثبت جلسه هیچ‌وقت مبلغ را عوض نمی‌کند: مبلغ و کیف‌پول همان چیزی است که ادمین فرستاده
    en = _enrollment(db, 2)
    _pay(db, amount=5_000, target_wallet="teacher", enrollment_id=en.id, sessions_covered=7)
    assert calculate_enrollment_debt_breakdown(db, en)["paid_teacher"] == 5_000
