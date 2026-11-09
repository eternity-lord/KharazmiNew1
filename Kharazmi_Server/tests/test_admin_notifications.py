# test_admin_notifications.py
# Regression tests for مسیر اعلان ادمین: «ساخته شدن برای User ادمین» + «نمایش درست در /notifications».
#
# باگ‌هایی که این تست‌ها قفل می‌کنند (همه با probe زنده اثبات شده‌اند):
#   ۱) تنها مسیر تولید اعلان ادمینی (automation «سرنخ تماس‌نگرفته») گیرنده را هاردکد `1` می‌فرستاد
#      ⇒ اعلان به کاربر شماره ۱ (که معمولاً ادمین نیست) می‌رفت و ادمینِ واقعی هیچ‌وقت آن را نمی‌دید.
#   ۲) خواندن اعلان با `sub_role or "student"` نقش را resolve می‌کرد ولی بقیه‌ی پروژه «admin» را
#      fallback می‌گرفت ⇒ ادمین legacy (sub_role=NULL) هیچ اعلانی نمی‌دید.
#   ۳) created_at = NULL (رکورد legacy) ⇒ `None.strftime(...)` ⇒ 500 برای کل صندوق اعلان.
#   ۴) POST /notifications/{id}/read روی اعلان ناموجود/دیگری ۲۰۰ کاذب برمی‌گرداند (no-op خاموش).
#   ۵) endpoint شمارش خوانده‌نشده‌ها وجود نداشت.
#
# اجرا (DB موقت، هرگز DB واقعی):
#   DATABASE_URL=sqlite:////tmp/admin_notifications_test.db \
#   JWT_SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))") \
#   python3 -m pytest test_admin_notifications.py -q
import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from types import SimpleNamespace

import models
from dependencies import get_db, NotificationService, resolve_notification_role
from main import app

LEAD_TITLE_MARK = "سرنخ"


def hdr(token):
    return {"Authorization": f"Bearer {token}"}


def _seed(db):
    db.query(models.AutomationLog).delete()
    db.query(models.AutomationRule).delete()
    db.add_all([
        models.Branch(id=1, name="شعبه مرکزی", active=True),
        models.Branch(id=2, name="شعبه شرق", active=True),
        # id=1 عمداً سایه‌ی دانش‌آموز است: اثبات اینکه گیرنده‌ی اعلان ادمین از فضای User.id است
        # و باگ قبلی (hardcode=1) اعلان را به یک کاربر بی‌ربط می‌فرستاد.
        models.User(id=1, username="student:1", password="x", full_name="سایه دانش‌آموز",
                    role="student", sub_role="student", branch_id=1),
        models.User(id=2, username="09120000001", password="x", full_name="ادمین مرکزی",
                    role="admin", sub_role="admin", branch_id=None),
        models.User(id=3, username="09120000002", password="x", full_name="ادمین شعبه یک",
                    role="admin", sub_role="admin", branch_id=1),
        models.User(id=4, username="09120000003", password="x", full_name="منشی شعبه یک",
                    role="admin", sub_role="secretary", branch_id=1),
        models.User(id=6, username="student:6", password="x", full_name="دانش‌آموز شعبه دو",
                    role="student", sub_role="student", branch_id=2),
        models.User(id=7, username="09120000009", password="x", full_name="ادمین شعبه دو",
                    role="admin", sub_role="admin", branch_id=2),
    ])
    db.add_all([
        models.UserSession(token="tok-central", user_id=2, sub_role="admin", created_at=datetime.datetime.now()),
        models.UserSession(token="tok-branch1", user_id=3, sub_role="admin", created_at=datetime.datetime.now()),
        models.UserSession(token="tok-secretary", user_id=4, sub_role="secretary", created_at=datetime.datetime.now()),
        models.UserSession(token="tok-branch2", user_id=7, sub_role="admin", created_at=datetime.datetime.now()),
        models.UserSession(token="tok-student", user_id=6, sub_role="student", created_at=datetime.datetime.now()),
    ])
    # قانون اتوماسیون «سرنخ تماس‌نگرفته» + دو سرنخ در دو شعبه (threshold=-1 ⇒ همه‌ی سرنخ‌های NEW)
    db.add(models.AutomationRule(id=1, name="سرنخ بی‌پیگیری", condition_type="lead_uncontacted",
                                 threshold=-1, action_type="parent_notification", active=True))
    db.add_all([
        models.Lead(id=1, name="سرنخ شعبه یک", mobile="09121111111", status="NEW", branch_id=1,
                    created_at=datetime.datetime.utcnow() - datetime.timedelta(days=10)),
        models.Lead(id=2, name="سرنخ شعبه دو", mobile="09122222222", status="NEW", branch_id=2,
                    created_at=datetime.datetime.utcnow() - datetime.timedelta(days=10)),
    ])
    db.commit()


@pytest.fixture
def world():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()
    _seed(db)

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield SimpleNamespace(client=client, db=db, engine=engine)
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _run_rules(world, token="tok-central"):
    r = world.client.post("/automation/run_rules", headers=hdr(token))
    assert r.status_code == 200, r.text
    world.db.expire_all()
    return r


def _lead_notifications(world):
    return [n for n in world.db.query(models.Notification).all()
            if n.type == "automation" and n.title and LEAD_TITLE_MARK in n.title]


def _inbox(world, token):
    r = world.client.get("/notifications", headers=hdr(token))
    assert r.status_code == 200, r.text
    return r.json()


# ==========================================================
# ۱) ساخت event و notification برای ادمین
# ==========================================================
def test_01_lead_event_creates_notifications_for_staff(world):
    """رویداد «سرنخ تماس‌نگرفته» باید واقعاً اعلان بسازد (قبلاً فقط به کاربر ۱ می‌رفت)."""
    _run_rules(world)
    notifs = _lead_notifications(world)
    assert notifs, "رویداد automation هیچ اعلانی نساخت"


# ==========================================================
# ۲) mapping صحیح recipient به User.id
# ==========================================================
def test_02_recipients_are_user_ids_of_staff(world):
    """گیرندگان باید از فضای User.id و فقط کارکنانِ مجاز باشند (نه Student.id، نه id هاردکد ۱)."""
    _run_rules(world)
    pairs = sorted((n.recipient_user_id, n.recipient_role) for n in _lead_notifications(world))
    users = sorted({p[0] for p in pairs})

    assert users == [2, 3, 4, 7], pairs          # ادمین مرکزی + ادمین/منشی شعبه۱ + ادمین شعبه۲
    assert (2, "admin") in pairs
    assert (4, "secretary") in pairs             # نقش هر کاربر با resolve_notification_role
    assert 1 not in users, "اعلان به کاربر شماره ۱ (هاردکد قبلی) فرستاده شد"
    assert (1, "admin") not in pairs


def test_02b_recipient_is_never_student_or_teacher_namespace(world):
    """هیچ اعلان ادمینی نباید در فضای Student.id/Teacher.id ثبت شود."""
    _run_rules(world)
    student_ids = {s.id for s in world.db.query(models.Student).all()}
    teacher_ids = {t.id for t in world.db.query(models.Teacher).all()}
    for n in _lead_notifications(world):
        assert n.recipient_user_id not in student_ids
        assert n.recipient_user_id not in teacher_ids
    assert all(not n.recipient_role.startswith("temp_parent:") for n in _lead_notifications(world))


def test_02c_no_notification_with_null_recipient(world):
    """هیچ اعلانی با recipient_user_id=NULL ساخته نمی‌شود (بی‌صاحب)."""
    _run_rules(world)
    assert all(n.recipient_user_id is not None for n in world.db.query(models.Notification).all())


# ==========================================================
# ۳) دریافت notification توسط ادمین درست
# ==========================================================
def test_03_admin_and_secretary_receive_their_notifications(world):
    _run_rules(world)
    for token in ("tok-central", "tok-branch1", "tok-secretary", "tok-branch2"):
        inbox = _inbox(world, token)
        assert inbox, f"صندوق {token} خالی است"
        assert all(n["type"] == "automation" for n in inbox), inbox


# ==========================================================
# ۴) عدم دریافت توسط کاربر نامرتبط
# ==========================================================
def test_04_unrelated_user_does_not_receive(world):
    _run_rules(world)
    assert _inbox(world, "tok-student") == [], "کاربر نامرتبط (دانش‌آموز) اعلان ادمینی دید"


# ==========================================================
# ۵) branch isolation
# ==========================================================
def test_05_branch_isolation_of_admin_notifications(world):
    """اعلان سرنخِ شعبه ۱ نباید به کارکنانِ شعبه ۲ برود و برعکس (ادمین کل همه را می‌بیند)."""
    _run_rules(world)
    notifs = _lead_notifications(world)
    lead1_uids = sorted({n.recipient_user_id for n in notifs if "سرنخ شعبه یک" in (n.body or "")})
    lead2_uids = sorted({n.recipient_user_id for n in notifs if "سرنخ شعبه دو" in (n.body or "")})

    # شعبه ۱: ادمین مرکزی (۲) + ادمین شعبه ۱ (۳) + منشی شعبه ۱ (۴) — و نه ادمین شعبه ۲ (۷)
    assert lead1_uids == [2, 3, 4], lead1_uids
    # شعبه ۲: ادمین مرکزی (۲) + ادمین شعبه ۲ (۷) — و نه کارکنانِ شعبه ۱
    assert lead2_uids == [2, 7], lead2_uids

    # ادمین شعبه ۲ اعلان شعبه ۱ را در صندوق خود نمی‌بیند
    bodies_b2 = [n["body"] or "" for n in _inbox(world, "tok-branch2")]
    assert all("سرنخ شعبه یک" not in b for b in bodies_b2), bodies_b2


# ==========================================================
# ۶) unread count
# ==========================================================
def test_06_unread_count_endpoint(world):
    _run_rules(world)
    r = world.client.get("/notifications/unread_count", headers=hdr("tok-central"))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["unread"] >= 1 and data["total"] >= 1, data

    # خوانده‌کردن یکی ⇒ شمارش کم می‌شود
    first_id = _inbox(world, "tok-central")[0]["id"]
    assert world.client.post(f"/notifications/{first_id}/read", headers=hdr("tok-central")).status_code == 200
    after = world.client.get("/notifications/unread_count", headers=hdr("tok-central")).json()
    assert after["unread"] == data["unread"] - 1, (data, after)

    # read_all ⇒ صفر
    assert world.client.post("/notifications/read_all", headers=hdr("tok-central")).status_code == 200
    final = world.client.get("/notifications/unread_count", headers=hdr("tok-central")).json()
    assert final["unread"] == 0 and final["total"] == after["total"], final


def test_06b_unread_count_is_scoped_to_owner(world):
    """شمارش هر کاربر فقط روی اعلان‌های خودش است (بدون شمارش اعلان دیگری)."""
    _run_rules(world)
    assert world.client.get("/notifications/unread_count", headers=hdr("tok-student")).json() == {"unread": 0, "total": 0}


# ==========================================================
# ۷) mark-as-read
# ==========================================================
def test_07_mark_as_read_only_own_notification(world):
    _run_rules(world)
    own = _inbox(world, "tok-branch1")[0]["id"]
    other = _inbox(world, "tok-branch2")[0]["id"]

    assert world.client.post(f"/notifications/{own}/read", headers=hdr("tok-branch1")).status_code == 200
    world.db.expire_all()
    assert world.db.get(models.Notification, own).is_read is True

    # اعلان کاربر دیگر: خطای controlled و بدون تغییر داده
    r = world.client.post(f"/notifications/{other}/read", headers=hdr("tok-branch1"))
    world.db.expire_all()
    assert r.status_code == 404, r.text
    assert world.db.get(models.Notification, other).is_read is False


# ==========================================================
# ۸) جلوگیری از duplicate در retry
# ==========================================================
def test_08_no_duplicate_notifications_on_retry(world):
    """اجرای دوباره‌ی موتور اتوماسیون نباید اعلان تکراری بسازد (گارد AutomationLog)."""
    _run_rules(world)
    # کلید یکتا = (گیرنده، عنوان، متن) — ادمین مرکزی برای هر سرنخ یک اعلان جدا می‌گیرد
    first = sorted((n.recipient_user_id, n.title, n.body) for n in _lead_notifications(world))
    assert len(first) == len(set(first)), f"در همان اجرای اول اعلان تکراری ساخته شد: {first}"
    _run_rules(world)
    second = sorted((n.recipient_user_id, n.title, n.body) for n in _lead_notifications(world))
    assert first == second, f"اجرای دوباره اعلان تکراری ساخت:\nاول={first}\nدوم={second}"


def test_08b_send_notification_dedupes_within_window(world):
    """send_notification در بازه‌ی کوتاه همان اعلان را دوباره نمی‌سازد (dedupe داخلی)."""
    db = world.db
    a = NotificationService.send_notification(db, recipient_user_id=2, recipient_role="admin",
                                              type="automation", title="t-dedupe", body="b-dedupe")
    b = NotificationService.send_notification(db, recipient_user_id=2, recipient_role="admin",
                                              type="automation", title="t-dedupe", body="b-dedupe")
    rows = db.query(models.Notification).filter(models.Notification.title == "t-dedupe").all()
    assert len(rows) == 1, [r.id for r in rows]
    assert a.id == b.id


# ==========================================================
# ۹) notification ناموجود با خطای controlled
# ==========================================================
def test_09_missing_notification_returns_controlled_404(world):
    r = world.client.post("/notifications/999999/read", headers=hdr("tok-central"))
    assert r.status_code == 404, r.text
    assert "یافت نشد" in r.text


# ==========================================================
# ۱۰) لیست خالی بدون crash
# ==========================================================
def test_10_empty_list_returns_200_empty_array(world):
    r = world.client.get("/notifications", headers=hdr("tok-student"))
    assert r.status_code == 200 and r.json() == []


# ==========================================================
# ۱۱) داده nullable (رکورد legacy)
# ==========================================================
def test_11_nullable_legacy_rows_do_not_500(world):
    """رکورد legacy با created_at=NULL: قبلاً کل لیست ۵۰۰ می‌شد (None.strftime)."""
    db = world.db
    db.execute(text("INSERT INTO notifications (id, recipient_user_id, recipient_role, type, title, body, is_read, created_at) "
                    "VALUES (900, 2, 'admin', 'system', 'قدیمی', NULL, NULL, NULL)"))
    db.commit()

    r = world.client.get("/notifications", headers=hdr("tok-central"))
    assert r.status_code == 200, r.text
    row = [n for n in r.json() if n["id"] == 900]
    assert row, r.text
    assert row[0]["created_at"] == "" and row[0]["title"] == "قدیمی"
    assert row[0]["is_read"] is False, "is_read=NULL باید خوانده‌نشده (False) گزارش شود"
    # is_read=NULL در شمارش هم خوانده‌نشده حساب می‌شود
    assert world.client.get("/notifications/unread_count", headers=hdr("tok-central")).json()["unread"] >= 1


# ==========================================================
# ۱۲) حفظ notificationهای قبلی (policy فعلی)
# ==========================================================
def test_12_existing_student_parent_notifications_are_preserved(world):
    """اعلان‌های شاگرد/ولی نه جابه‌جا می‌شوند نه با اقدامات ادمین تغییر می‌کنند."""
    db = world.db
    db.add_all([
        models.Notification(id=800, recipient_user_id=1, recipient_role="student", type="installment",
                            title="اعلان شاگرد", body="...", is_read=False,
                            created_at=datetime.datetime.utcnow()),
        models.Notification(id=801, recipient_user_id=4, recipient_role="parent", type="installment",
                            title="اعلان نقش دیگرِ همان کاربر", body="...", is_read=False,
                            created_at=datetime.datetime.utcnow()),
    ])
    db.commit()

    _run_rules(world)
    # ادمین ۴ (منشی) اعلان نقش secretary خودش را می‌بیند، ولی اعلان نقش parent خودش را نه
    inbox = _inbox(world, "tok-secretary")
    assert 801 not in [n["id"] for n in inbox], "فیلتر نقش نقض شد (اعلان نقش دیگر نمایش داده شد)"

    # read_all ادمین نباید اعلان نقش student کاربر ۱ را لمس کند
    assert world.client.post("/notifications/read_all", headers=hdr("tok-central")).status_code == 200
    db.expire_all()
    assert db.get(models.Notification, 800).is_read is False, "read_all ادمین روی اعلان شاگرد اثر گذاشت"
    assert db.get(models.Notification, 801).is_read is False, "read_all ادمین روی اعلان ولی اثر گذاشت"

    # صندوق شاگرد ۱ هنوز فقط اعلان خودش را دارد
    assert [n["id"] for n in _inbox(world, "tok-central") if n["id"] == 800] == []


# ==========================================================
# ۱۳) ادمین legacy با sub_role = NULL (باگ fallback نقش)
# ==========================================================
def test_13_legacy_admin_with_null_sub_role_sees_notifications(world):
    """ادمینِ legacy (sub_role=NULL خام، role=admin) باید اعلان نقش admin خودش را ببیند."""
    db = world.db
    db.execute(text("INSERT INTO users (id, username, password, full_name, role, sub_role) "
                    "VALUES (30, 'legacy_admin', 'x', 'ادمین قدیمی', 'admin', NULL)"))
    db.execute(text("INSERT INTO user_sessions (token, user_id, sub_role, created_at) VALUES ('tok-legacy', 30, 'admin', :now)"),
               {"now": datetime.datetime.now()})
    db.execute(text("INSERT INTO notifications (id, recipient_user_id, recipient_role, type, title, body, is_read, created_at) "
                    "VALUES (901, 30, 'admin', 'automation', 'اعلان ادمین قدیمی', 'x', 0, :now)"),
               {"now": datetime.datetime.utcnow()})
    db.commit()

    raw = db.query(models.User).filter(models.User.id == 30).first()
    assert raw.sub_role is None and raw.role == "admin"
    assert resolve_notification_role(raw) == "admin"

    inbox = _inbox(world, "tok-legacy")
    assert 901 in [n["id"] for n in inbox], f"اعلان ادمین legacy نمایش داده نشد: {inbox}"


# ==========================================================
# ۱۴) دسترسی و ورودی‌های مرزی
# ==========================================================
def test_14_unauthenticated_is_401(world):
    assert world.client.get("/notifications").status_code == 401
    assert world.client.get("/notifications/unread_count").status_code == 401
    assert world.client.post("/notifications/1/read").status_code == 401


def test_15_legacy_admin_without_sub_role_receives_automation_notifications(world):
    """ادمین legacy (sub_role=NULL) هم باید در fan-out اعلان‌های ادمینی باشد."""
    db = world.db
    db.execute(text("INSERT INTO users (id, username, password, full_name, role, sub_role) "
                    "VALUES (31, 'legacy_admin2', 'x', 'ادمین قدیمی ۲', 'admin', NULL)"))
    db.commit()
    _run_rules(world)
    recipients = {n.recipient_user_id for n in _lead_notifications(world)}
    assert 31 in recipients, recipients
