# test_undated_pending_settlement.py
# Regression tests for «پرداخت‌نشده‌های معلم (pending_settlement) با جلسه‌های بدون تاریخ».
#
# باگی که این تست‌ها قفل می‌کنند (با probe زنده اثبات شده):
#   در routers/teachers.py تابع _in_range برای هر مقدارِ غیرقابل‌parse — از جمله date=NULL —
#   `return False` می‌داد و جلسه **بی‌صدا** از نتیجه حذف می‌شد؛ حتی وقتی هیچ بازه‌ی تاریخی
#   درخواست نشده بود. نتیجه: total_amount و session_count کمتر از واقع ⇒ طلب معلم کم‌نمایش.
#   در سناریوی اثبات: ۴ جلسه از ۶ جلسه حذف شد و طلب ۴۵۰٬۰۰۰ به‌جای ۳۰۰٬۰۰۰ کم اعلام شد.
#
# اجرا (DB موقت، هرگز DB واقعی):
#   DATABASE_URL=sqlite:////tmp/undated_settlement_test.db \
#   JWT_SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))") \
#   python3 -m pytest test_undated_pending_settlement.py -q
import datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from dependencies import get_db
from main import app
from routers.teachers import get_pending_settlement

VALID_DATE = "1405/06/02"


def hdr(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def world():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()

    db.add_all([
        models.Branch(id=1, name="شعبه مرکزی", active=True),
        models.Teacher(id=1, first_name="مریم", last_name="تست", mobile="09120000001",
                       national_code="0012345678", password="x", is_approved=True, is_deleted=False),
        models.Teacher(id=2, first_name="سارا", last_name="دیگر", mobile="09120000002",
                       national_code="0012345679", password="x", is_approved=True, is_deleted=False),
        models.Course(id=1, title="ریاضی", code="300001", teacher_id=1, is_admin_approved=True,
                      is_deleted=False, grade_level="دهم", class_time="16:00-17:30",
                      days_of_week="شنبه", teacher_session_price=100000),
        models.Course(id=2, title=None, code="300002", teacher_id=1, is_admin_approved=True,
                      is_deleted=False, grade_level=None, class_time="18:00-19:30",
                      days_of_week="یکشنبه", teacher_session_price=100000),
        models.Student(id=1, student_code=1, first_name="علی", last_name="تست", national_code="0012345683",
                       student_mobile="09121111111", wallet_teacher=0, wallet_institute=0, wallet_balance=0),
        models.User(id=1, username="09120000001", password="x", full_name="ادمین", role="admin",
                    sub_role="admin", branch_id=None),
        models.User(id=2, username="09120000003", password="x", full_name="منشی", role="admin",
                    sub_role="secretary", branch_id=1),
        models.User(id=3, username="teacher:1", password="x", full_name="مریم تست", role="teacher",
                    sub_role="teacher", branch_id=None),
        models.User(id=4, username="student:1", password="x", full_name="علی تست", role="student",
                    sub_role="student", branch_id=None),
    ])
    db.add_all([
        models.UserSession(token="tok-admin", user_id=1, sub_role="admin", created_at=datetime.datetime.now()),
        models.UserSession(token="tok-secretary", user_id=2, sub_role="secretary", created_at=datetime.datetime.now()),
        models.UserSession(token="tok-teacher", user_id=3, sub_role="teacher", teacher_id=1,
                           created_at=datetime.datetime.now()),
        models.UserSession(token="tok-student", user_id=4, sub_role="student", created_at=datetime.datetime.now()),
    ])
    db.commit()

    _next_id = [100]

    def add_session(date_value, cost=100000, penalty=0, course_id=1, billed=False,
                    att_status="Present", penalty_settled=False):
        _next_id[0] += 1
        sid = _next_id[0]
        db.add(models.SessionLog(id=sid, course_id=course_id, date=date_value, time="16:00",
                                 final_teacher_cost=cost, final_institute_share=50000,
                                 cost_per_student=150000, attendee_count=1, status="Finished",
                                 is_deleted=False, absent_penalty_teacher=penalty,
                                 is_penalty_settled=penalty_settled))
        db.flush()
        db.add(models.Attendance(session_id=sid, student_id=1, status=att_status, is_billed=billed,
                                 excused=False, is_deleted=False))
        db.commit()
        return sid

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield SimpleNamespace(client=client, db=db, engine=engine, add_session=add_session)
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _pending(world, teacher_id=1, **kwargs):
    params = {k: v for k, v in kwargs.items() if v is not None}
    r = world.client.get(f"/teachers/{teacher_id}/pending_settlement", params=params or None, headers=hdr("tok-admin"))
    assert r.status_code == 200, r.text
    return r.json()


def _tokens(world, body):
    return [row["session_id"] for row in body["pending_sessions"]]


# ==========================================================
# ۱) session با تاریخ معتبر — رفتار قبلی حفظ شود
# ==========================================================
def test_01_valid_dated_session_behaves_as_before(world):
    sid = world.add_session(VALID_DATE, cost=100000)
    body = _pending(world)
    assert body["session_count"] == 1 and body["total_amount"] == 100000
    row = body["pending_sessions"][0]
    assert row["session_id"] == sid
    assert row["date"] == VALID_DATE, "تاریخ معتبر نباید تغییر کند"
    assert row["amount"] == 100000 and row["class_title"] == "ریاضی" and row["present_count"] == 1


# ==========================================================
# ۲) session با date=NULL — نباید حذف شود
# ==========================================================
def test_02_null_date_session_is_not_dropped(world):
    sid = world.add_session(None, cost=200000)
    body = _pending(world)
    assert _tokens(world, body) == [sid], "جلسه‌ی بدون تاریخ از نتیجه حذف شد"
    assert body["session_count"] == 1
    assert body["total_amount"] == 200000, "طلب جلسه‌ی بدون تاریخ باید در total_amount باشد"
    assert body["pending_sessions"][0]["date"] == "", "برای رکورد بی‌تاریخ باید \"\" برگردد"


# ==========================================================
# ۳) ترکیب معتبر و NULL
# ==========================================================
def test_03_mixed_valid_and_undated(world):
    s1 = world.add_session(VALID_DATE, cost=100000)
    s2 = world.add_session(None, cost=200000)
    body = _pending(world)
    assert sorted(_tokens(world, body)) == sorted([s1, s2])
    assert body["session_count"] == 2
    assert body["total_amount"] == 300000


# ==========================================================
# ۴) چند session با هر دو حالت
# ==========================================================
def test_04_many_sessions_of_both_kinds(world):
    world.add_session("1405/06/02", cost=100000)
    world.add_session(None, cost=200000)
    world.add_session("1405/06/05", cost=50000)
    world.add_session(None, cost=None)
    world.add_session("1405/06/09", cost=70000)
    world.add_session(None, cost=30000, course_id=2)
    body = _pending(world)
    assert body["session_count"] == 6, f"ids={_tokens(world, body)}"
    assert body["total_amount"] == 450000, "جمع شامل هر ۶ جلسه (شامل ۴ جلسه‌ی بی‌تاریخ/ناقص)"


# ==========================================================
# ۵) amount یا هزینه NULL همراه date=NULL
# ==========================================================
def test_05_null_cost_with_null_date(world):
    sid = world.add_session(None, cost=None, penalty=None)
    body = _pending(world)
    assert sid in _tokens(world, body)
    assert body["total_amount"] == 0
    row = body["pending_sessions"][0]
    assert row["amount"] == 0 and row["date"] == "" and None not in row.values()


# ==========================================================
# ۶) course title=NULL همراه date=NULL
# ==========================================================
def test_06_null_course_title_with_null_date(world):
    sid = world.add_session(None, cost=70000, course_id=2)
    body = _pending(world)
    row = [r for r in body["pending_sessions"] if r["session_id"] == sid][0]
    assert row["class_title"] == "کلاس بدون عنوان"
    assert row["date"] == "" and None not in row.values()


# ==========================================================
# ۷) teacher بدون pending
# ==========================================================
def test_07_teacher_without_pending(world):
    body = _pending(world)
    assert body["total_amount"] == 0 and body["session_count"] == 0 and body["pending_sessions"] == []
    assert body["teacher_id"] == 1 and body["settled_total_amount"] == 0
    assert body["earned_total_amount"] == 0
    # معلم دوم هیچ کلاسی ندارد
    other = _pending(world, teacher_id=2)
    assert other["total_amount"] == 0 and other["pending_sessions"] == []


# ==========================================================
# ۸) نبود تاریخ جعلی
# ==========================================================
def test_08_no_fabricated_date(world):
    world.add_session(None, cost=100000)
    world.add_session("999/99/99", cost=10000)      # invalid غیرNULL
    body = _pending(world)
    today_jalali_like = datetime.date.today().strftime("%Y/%m/%d")
    for row in body["pending_sessions"]:
        assert row["date"] == "", f"تاریخ کنترل‌نشده/جعلی: {row['date']!r}"
        assert row["date"] != today_jalali_like
    # مقدار خام ذخیره‌شده در دیتابیس دست‌کاری نشده است
    world.db.expire_all()
    assert world.db.query(models.SessionLog).count() == 2


# ==========================================================
# ۹) session_count صحیح
# ==========================================================
def test_09_session_count_includes_undated(world):
    # نکته‌ی مدل داده: ایندکس یکتای (course_id, date) فقط برای جلسه‌های حذف‌نشده‌ی «دارای تاریخ»
    # اعمال می‌شود (NULL در ایندکس یکتا تکراری حساب نمی‌شود) ⇒ سه جلسه‌ی بی‌تاریخ مجازند،
    # ولی تاریخ‌های معتبر باید متفاوت باشند.
    for day in ("1405/06/02", "1405/06/03", "1405/06/04"):
        world.add_session(day, cost=10000)
    for _ in range(3):
        world.add_session(None, cost=10000)
    body = _pending(world)
    assert body["session_count"] == 6, f"count={body['session_count']} ids={_tokens(world, body)}"


# ==========================================================
# ۱۰) total_amount صحیح (شامل جریمه و جلسه‌ی بی‌تاریخ)
# ==========================================================
def test_10_total_amount_includes_undated_and_penalty(world):
    world.add_session(VALID_DATE, cost=100000, penalty=5000)
    world.add_session(None, cost=200000, penalty=2500)
    body = _pending(world)
    assert body["total_amount"] == 307500, body
    # جلسه‌ی تماماً-غایب با جریمه و بدون تاریخ هم طلب است (شاخه‌ی penalty_only)
    world.add_session(None, cost=0, penalty=90000, att_status="Absent")
    body2 = _pending(world)
    assert body2["total_amount"] == 397500, body2
    penalty_rows = [r for r in body2["pending_sessions"] if r["penalty_only"] and r["date"] == ""]
    assert penalty_rows, "جلسه‌ی جریمه‌ی بی‌تاریخ باید در لیست باشد"


# ==========================================================
# ۱۱) permission و branch isolation (حفظ رفتار)
# ==========================================================
def test_11_permission_and_scope_preserved(world):
    world.add_session(None, cost=100000)
    c = world.client
    assert c.get("/teachers/1/pending_settlement").status_code == 401              # بدون توکن
    assert c.get("/teachers/1/pending_settlement", headers=hdr("tok-student")).status_code == 403
    assert c.get("/teachers/2/pending_settlement", headers=hdr("tok-teacher")).status_code == 403  # معلم دیگر
    assert c.get("/teachers/1/pending_settlement", headers=hdr("tok-teacher")).status_code == 200  # خودش
    assert c.get("/teachers/1/pending_settlement", headers=hdr("tok-admin")).status_code == 200
    assert c.get("/teachers/1/pending_settlement", headers=hdr("tok-secretary")).status_code == 200
    assert c.get("/teachers/999/pending_settlement", headers=hdr("tok-admin")).status_code == 404


# ==========================================================
# ۱۲) حفظ قرارداد response برای داده سالم
# ==========================================================
def test_12_response_contract_for_healthy_data(world):
    world.add_session(VALID_DATE, cost=100000)
    body = _pending(world)
    assert set(body.keys()) == {"teacher_id", "teacher_name", "total_amount", "session_count",
                                "settled_total_amount", "earned_total_amount", "pending_sessions"}
    assert isinstance(body["total_amount"], int) and isinstance(body["session_count"], int)
    assert set(body["pending_sessions"][0].keys()) == {"session_id", "date", "class_title",
                                                       "amount", "present_count", "penalty_only"}
    assert body["earned_total_amount"] == body["settled_total_amount"] + body["total_amount"]
    assert body["teacher_name"] == "مریم تست"


# ==========================================================
# ۱۳) تاریخ invalid غیرNULL — کنترل‌شده و بدون جعل
# ==========================================================
def test_13_invalid_non_null_date_is_controlled(world):
    sid = world.add_session("not-a-date", cost=10000)
    body = _pending(world)
    assert sid in _tokens(world, body), "رکورد با تاریخ نامعتبر هم نباید حذف شود"
    assert body["pending_sessions"][0]["date"] == ""


# ==========================================================
# ۱۴) ترتیب deterministic
# ==========================================================
def test_14_output_order_is_deterministic(world):
    world.add_session("1405/06/02", cost=1000)
    world.add_session(None, cost=1000)
    world.add_session("1405/06/05", cost=1000)
    world.add_session(None, cost=1000)
    first = [r["session_id"] for r in _pending(world)["pending_sessions"]]
    for _ in range(3):
        assert [r["session_id"] for r in _pending(world)["pending_sessions"]] == first
    # تاریخ‌های معتبر نزولی، بی‌تاریخ‌ها در انتها
    dates = [r["date"] for r in _pending(world)["pending_sessions"]]
    assert dates == sorted(dates, reverse=True), dates


# ==========================================================
# ۱۵) فیلتر بازه: تاریخ‌های معتبر مثل قبل، بی‌تاریخ‌ها حذف نمی‌شوند
# ==========================================================
def test_15_range_filter_keeps_valid_behavior(world):
    s_old = world.add_session("1405/06/02", cost=100000)
    s_mid = world.add_session("1405/06/04", cost=100000)
    s_undated = world.add_session(None, cost=100000)
    body = _pending(world, start_date="1405/06/03", end_date="1405/06/05")
    ids = _tokens(world, body)
    assert s_old not in ids, "جلسه‌ی قبل از بازه باید مثل قبل حذف شود"
    assert s_mid in ids and s_undated in ids, f"ids={ids}"
    assert body["total_amount"] == 200000


# ==========================================================
# ۱۶) داده‌ی مالی دست‌نخورده (بدون ثبت/محاسبه‌ی دوباره)
# ==========================================================
def test_16_no_financial_mutation(world):
    sid = world.add_session(None, cost=100000)
    before = [(a.id, a.is_billed) for a in world.db.query(models.Attendance).all()]
    _pending(world)
    _pending(world)
    world.db.expire_all()
    assert [(a.id, a.is_billed) for a in world.db.query(models.Attendance).all()] == before
    assert world.db.query(models.Settlement).count() == 0, "هیچ تسویه‌ای نباید ثبت شود"
    assert world.db.get(models.SessionLog, sid).final_teacher_cost == 100000, "مبلغ جلسه باید دست‌نخورده بماند"


# ==========================================================
# ۱۷) جلسه‌ی تسویه‌شده (is_billed) وارد pending نشود
# ==========================================================
def test_17_billed_session_not_pending(world):
    world.add_session(None, cost=900000, billed=True)
    body = _pending(world)
    assert body["session_count"] == 0 and body["total_amount"] == 0, body
