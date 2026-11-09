"""
Wallet / Internal Payment / Refund / Balance-Consistency — TEST-ONLY audit
(فقط تست؛ هیچ تغییری در کد اصلی پروژه انجام نشده است)

## Business rules تحت آزمون
- `wallet_teacher` مثبت = اعتبار نزد معلم | منفی = بدهی به معلم
- `wallet_institute` مثبت = اعتبار نزد آموزشگاه | منفی = بدهی به آموزشگاه
- صفر = تسویه
- **invariant همیشگی:** `wallet_balance == wallet_teacher + wallet_institute`

## نگاشت سناریوهای درخواستی ← تست‌ها
| # | سناریو | تست |
|---|--------|-----|
| ۱ | موجودی اولیه صفر | `test_s01_initial_wallets_are_zero` |
| ۲ | ثبت جلسه ۱۰۰ ⇒ ‎-۱۰۰ | `test_s02_session_charge_100_makes_minus_100` |
| ۳ | پرداخت ۴۰ ⇒ ‎-۶۰ | `test_s03_payment_40_moves_debt_from_100_to_60` |
| ۴ | پرداخت ۶۰ ⇒ ۰ | `test_s04_payment_60_settles_to_zero` |
| ۵ | پرداخت ۱۰۰ بعد از تسویه ⇒ ‎+۱۰۰ | `test_s05_payment_after_settlement_goes_positive` |
| ۶ | refund همان ۱۰۰ ⇒ ۰ | `test_s06_refund_returns_balance_to_zero` |
| ۷ | پرداخت فقط teacher | `test_s07_teacher_only_payment_touches_only_teacher_wallet` |
| ۸ | پرداخت فقط institute | `test_s08_institute_only_payment_touches_only_institute_wallet` |
| ۹ | پرداخت both ⇒ جمع سهم‌ها = مبلغ | `test_s09_split_payment_shares_sum_exactly_to_amount` |
| ۱۰ | مبلغ ۰/منفی/نامعتبر قبل از هر نوشتن رد شود | `test_s10_invalid_amounts_rejected_before_any_write` |
| ۱۱ | refund تکراری بی‌اثر | `test_s11_duplicate_refund_is_rejected_and_changes_nothing` |
| ۱۲ | deleted/reversed در گزارش درآمد و نمای فعال | `test_s12_*` |
| ۱۳ | invariant بعد از هر سناریو | `assert_wallet_invariant` (در همه‌ی تست‌ها) + `test_s13_full_walk_invariant_every_step` |
| ۱۴ | lost update در پرداخت هم‌زمان / bulk update | `test_s14a_*`, `test_s14b_*`, `test_s14c_*` |

## ✅ تست‌های رگرسیون سه باگ ممیزی (پس از فیکس)
سه تست `test_fix_fw1a_*` / `test_fix_fw1b_*` / `test_fix_fw2_*` نسخه‌ی سبزشده‌ی همان سه تست
یافته‌محورِ ممیزی‌اند (قبلاً `test_finding_*` بودند و عمداً fail می‌شدند). اکنون رفتار **پس از فیکس**
را قفل می‌کنند:
- **F-W1a:** ویرایش session_charge هیچ مقدار اعشاری در کیف/سهم ذخیره نمی‌کند (تقسیم صحیح، باقیمانده‌ی
  قطعی به آموزشگاه).
- **F-W1b:** `share_teacher`/`share_institute` با مبلغ جدید همراستا می‌شوند و گزارش‌های
  `financial_calculations` عدد جدید را نشان می‌دهند.
- **F-W2:** ویرایش رسید legacy `target_wallet="both"` دلتای واقعی را با نسبت قبلی (یا fallback
  مستند نصف-نصف) اعمال می‌کند.

## ✅ تست‌های رگرسیون F-D1 (حذف رسید legacy `both`)
تست‌های `test_delete_both_*` / `test_delete_never_touches_*` / `test_refund_after_delete_*`
سناریوهای تسک را قفل می‌کنند: حذف رسید `both` (سهم‌های مساوی/نامساوی/فرد)، حذف بعد از ویرایش،
حذف تکراری (۴۰۴ و بی‌اثر)، رسیدهای تک‌کیفی، ردیف deleted/reversed، استرداد بعد از حذف (۴۰۴)،
هم‌راستایی عددی با `refund_transaction` و fallback مستند «بدون سهم».

## اجرا (طبق قانون پروژه: فقط روی DB تست/کپی — هرگز gaj_db.db واقعی)
    cd /home/user/KharazmiApp && DATABASE_URL=sqlite:////tmp/wallet_audit.db \
        PYTHONPATH=/home/user/KharazmiApp/Kharazmi_Server \
        python3 -m pytest Kharazmi_Server/test_wallet_finance_audit.py -q
تست‌ها DB درون‌حافظه‌ای/فایل موقت خودشان را می‌سازند (StaticPool / tmp_path).
"""
import datetime
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, func, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from financial_calculations import (
    calculate_institute_collected_revenue,
    calculate_institute_session_revenue,
    calculate_student_debt,
    calculate_teacher_session_revenue,
    calculate_total_turnover,
)
from routers import attendance, finance
from schemas import AttendanceItem, AttendanceSubmitData, FinanceSubmitData

# سقف ایمنی: هر تست باید کوچک و قابل‌اتکا بمانَد
TODAY_JALALI = "1405/06/16"      # گذشته‌ی معتبر نسبت به امروز (۱۴۰۵/۰۶/۲۶)
RANGE_START, RANGE_END = "1400/01/01", "1410/01/01"


# ==========================================
# زیرساخت
# ==========================================
def make_engine(url="sqlite:///:memory:", **kwargs):
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30}, **kwargs)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    models.Base.metadata.create_all(engine)
    return engine


def seed_world(db):
    """دانش‌آموز با کیف صفر + کلاس با نرخ جلسه ۶۰ و سهم آموزشگاه ۴۰ ⇒ شارژ هر جلسه دقیقاً ۱۰۰."""
    db.add_all([models.Branch(id=1, name="شعبه تست", active=True)])
    db.flush()
    user = models.User(id=1, username="wallet-admin", password="unused", role="admin", sub_role="admin", branch_id=1)
    teacher = models.Teacher(id=1, teacher_code=101, first_name="معلم", last_name="تست",
                             mobile="09120000101", branch_id=1)
    student = models.Student(
        id=101, student_code=100101, first_name="دانش‌آموز", last_name="تست",
        national_code="W-101", student_mobile="09121110101", parent_mobile="09122220101",
        branch_id=1, wallet_teacher=0, wallet_institute=0, wallet_balance=0,
    )
    db.add_all([user, teacher, student])
    db.flush()
    course = models.Course(
        id=1, title="کلاس تست", code="W10001", teacher_id=teacher.id, branch_id=1,
        grade_level="دهم", teacher_session_price=60, is_admin_approved=True,
    )
    db.add(course)
    db.flush()
    enrollment = models.Enrollment(
        student_id=student.id, course_id=course.id, branch_id=1,
        total_tuition=1000, total_paid=0, register_date=TODAY_JALALI,
    )
    db.add_all([
        enrollment,
        models.UserSession(token="wallet-admin-token", user_id=user.id, sub_role="admin",
                           created_at=datetime.datetime.now()),
        models.InstituteSettings(name="آموزشگاه تست", address="ت", phone="021", card_number="1234"),
        # سهم آموزشگاه برای ۱ نفر = ۴۰ (جمع با ۶۰ معلم = ۱۰۰)
        models.InstituteShare(count_1=40, count_2=80, count_3=120),
    ])
    db.commit()
    return SimpleNamespace(db=db, user=user, teacher=teacher, student=student, course=course,
                           enrollment=enrollment)


@pytest.fixture
def world():
    """DB درون‌حافظه‌ای اختصاصی هر تست — هیچ فایلی از پروژه خوانده/نوشته نمی‌شود."""
    engine = make_engine(poolclass=StaticPool)
    with sessionmaker(bind=engine, expire_on_commit=False)() as db:
        yield seed_world(db)
    models.Base.metadata.drop_all(engine)
    engine.dispose()


# ---------- helpers با assert خودکار invariant (سناریو ۱۳) ----------
def wallets(db, student_id=101):
    """خواندن تازه از DB (نه از حافظه‌ی ORM) تا مقدار واقعیِ ذخیره‌شده سنجیده شود."""
    db.expire_all()
    student = db.get(models.Student, student_id)
    return student.wallet_teacher or 0, student.wallet_institute or 0, student.wallet_balance or 0


def assert_wallet_invariant(db, student_id=101, expected_teacher=None, expected_institute=None,
                            expected_balance=None, context=""):
    """invariant مرکزی: wallet_balance == wallet_teacher + wallet_institute (سناریو ۱۳)."""
    teacher, institute, balance = wallets(db, student_id)
    assert balance == teacher + institute, (
        f"نقض invariant {context}: balance={balance} != teacher({teacher}) + institute({institute})"
    )
    if expected_teacher is not None:
        assert teacher == expected_teacher, f"{context}: wallet_teacher={teacher} ≠ {expected_teacher}"
    if expected_institute is not None:
        assert institute == expected_institute, f"{context}: wallet_institute={institute} ≠ {expected_institute}"
    if expected_balance is not None:
        assert balance == expected_balance, f"{context}: wallet_balance={balance} ≠ {expected_balance}"
    return teacher, institute, balance


def pay(world, amount, wallet="institute", **overrides):
    values = dict(student_id=world.student.id, amount=amount, target_wallet=wallet,
                  description="پرداخت تستی", payment_method="نقدی", date=TODAY_JALALI)
    values.update(overrides)
    result = finance.submit_payment(FinanceSubmitData(**values), db=world.db, _="admin",
                                    authorization="Bearer wallet-admin-token")
    assert_wallet_invariant(world.db, context="بعد از پرداخت")
    return result


def submit_session(world, date=TODAY_JALALI):
    request = AttendanceSubmitData(course_id=world.course.id, date=date,
                                   items=[AttendanceItem(student_id=world.student.id, status="Present")])
    result = attendance.submit_session_and_calculate(request, db=world.db,
                                                     authorization="Bearer wallet-admin-token",
                                                     sub_role="admin")
    assert_wallet_invariant(world.db, context="بعد از ثبت جلسه")
    return result


def refund(world, transaction_id):
    result = finance.refund_transaction(transaction_id, db=world.db,
                                        authorization="Bearer wallet-admin-token", _="admin")
    assert_wallet_invariant(world.db, context="بعد از استرداد")
    return result


def deposit_count(db):
    return db.query(models.Transaction).filter(models.Transaction.type == "deposit").count()


def sqlite_money_types(db, transaction_id, student_id=101):
    """نوع واقعیِ ذخیره‌شده‌ی ستون‌های پول در SQLite (`integer` در برابر `real`).
    FIX F-W1a: بعد از هیچ ویرایشی نباید `real` (اعشاری) ببینیم."""
    row = db.execute(
        text("SELECT typeof(amount), typeof(share_teacher), typeof(share_institute) "
             "FROM transactions WHERE id = :i"), {"i": transaction_id}
    ).fetchone()
    wallet = db.execute(
        text("SELECT typeof(wallet_teacher), typeof(wallet_institute), typeof(wallet_balance) "
             "FROM students WHERE id = :i"), {"i": student_id}
    ).fetchone()
    return tuple(row) + tuple(wallet)


def assert_no_float_money(db, transaction_id, student_id=101, context=""):
    """F-W1a: هیچ‌کدام از amount/share_teacher/share_institute/wallet_* نباید اعشاری ذخیره شوند."""
    types = sqlite_money_types(db, transaction_id, student_id)
    assert types == ("integer",) * 6, (
        f"{context}: ستون‌های پول باید همه integer باشند؛ نوع‌های واقعی SQLite={types}"
    )
    teacher, institute, balance = wallets(db, student_id)
    assert all(isinstance(value, int) for value in (teacher, institute, balance)), (
        f"{context}: مقادیر خوانده‌شده باید int باشند؛ {teacher!r}/{institute!r}/{balance!r}"
    )
    return types


def receipt(db, amount=100, **overrides):
    """رسید مستقیم، فقط برای ساختن حالت‌های پرچمی (deleted/reversed) در سناریو ۱۲."""
    values = dict(student_id=101, enrollment_id=1, course_id=1, branch_id=1, amount=amount,
                  payment_method="نقدی", type="deposit", target_wallet="institute",
                  date=TODAY_JALALI, description="رسید تستی", share_teacher=0, share_institute=amount)
    values.update(overrides)
    transaction = models.Transaction(**values)
    db.add(transaction)
    db.flush()
    return transaction


# ==========================================
# سناریو ۱ — موجودی اولیه
# ==========================================
def test_s01_initial_wallets_are_zero(world):
    assert_wallet_invariant(world.db, expected_teacher=0, expected_institute=0, expected_balance=0,
                            context="موجودی اولیه")
    # صفر = تسویه: بدهی قراردادی صفر است (شهریه ۱۰۰۰ - پرداخت ۰ → بدهی ۱۰۰۰ طبق ثبت‌نام)
    assert calculate_student_debt(world.db, world.student) == 1000
    assert world.db.query(models.Transaction).count() == 0


# ==========================================
# سناریو ۲ — ثبت جلسه با مبلغ ۱۰۰
# ==========================================
def test_s02_session_charge_100_makes_minus_100(world):
    submit_session(world)
    teacher, institute, balance = assert_wallet_invariant(
        world.db, expected_teacher=-60, expected_institute=-40, expected_balance=-100,
        context="شارژ جلسه",
    )
    assert teacher + institute == -100, "مجموع دو کیف باید دقیقاً -100 باشد"
    charge = world.db.query(models.Transaction).filter(models.Transaction.type == "session_charge").one()
    assert charge.amount == -100
    assert charge.share_teacher == 60 and charge.share_institute == 40
    # علامت منفی = بدهی دانش‌آموز
    assert balance < 0


# ==========================================
# سناریو ۳ و ۴ — پرداخت ۴۰ سپس ۶۰
# ==========================================
def test_s03_payment_40_moves_debt_from_100_to_60(world):
    submit_session(world)
    pay(world, 40, wallet="institute")
    assert_wallet_invariant(world.db, expected_teacher=-60, expected_institute=0, expected_balance=-60,
                            context="پرداخت ۴۰")


def test_s04_payment_60_settles_total_balance_to_zero(world):
    """سناریوی ۳+۴ درخواست: بدهی کل -۱۰۰ → پرداخت ۴۰ → -۶۰ → پرداخت ۶۰ → صفر.
    نکته‌ی دقیق سیستم: پرداخت‌ها به کیف انتخاب‌شده می‌روند؛ «تسویه» در سطح
    جمعِ دو کیف معنا دارد (wallet_balance=0) و ممکن است یک کیف بستانکار بماند."""
    submit_session(world)
    pay(world, 40, wallet="institute")
    assert_wallet_invariant(world.db, expected_teacher=-60, expected_institute=0, expected_balance=-60,
                            context="بعد از پرداخت ۴۰")

    pay(world, 60, wallet="institute")
    teacher, institute, balance = assert_wallet_invariant(
        world.db, expected_teacher=-60, expected_institute=60, expected_balance=0,
        context="بعد از پرداخت ۶۰ (تسویه در سطح جمع)",
    )
    assert balance == 0, "جمع دو کیف باید صفر (تسویه) شود"
    assert teacher + institute == balance


def test_s04b_settling_both_wallets_to_exactly_zero(world):
    """تسویه‌ی دقیق هر دو کیف: ۴۰ به آموزشگاه (بدهی آموزشگاه ۴۰-) و ۶۰ به معلم (بدهی معلم ۶۰-)."""
    submit_session(world)
    pay(world, 40, wallet="institute")
    pay(world, 60, wallet="teacher")
    assert_wallet_invariant(world.db, expected_teacher=0, expected_institute=0, expected_balance=0,
                            context="تسویه‌ی دقیق دو کیف")


# ==========================================
# سناریو ۵ و ۶ — پرداخت بعد از تسویه و استرداد
# ==========================================
def test_s05_payment_after_settlement_goes_positive(world):
    pay(world, 100, wallet="institute")            # موجودی صفر بود؛ پرداخت ۱۰۰ ⇒ اعتبار
    assert_wallet_invariant(world.db, expected_teacher=0, expected_institute=100, expected_balance=100,
                            context="پرداخت بعد از تسویه")
    assert wallets(world.db)[2] > 0, "مقدار مثبت = اعتبار نزد آموزشگاه"


def test_s06_refund_returns_balance_to_zero(world):
    deposit_tx = pay(world, 100, wallet="institute")["receipt_id"]
    assert_wallet_invariant(world.db, expected_balance=100, context="قبل از استرداد")

    refund(world, deposit_tx)
    assert_wallet_invariant(world.db, expected_teacher=0, expected_institute=0, expected_balance=0,
                            context="بعد از استرداد")

    original = world.db.get(models.Transaction, deposit_tx)
    reversal = world.db.query(models.Transaction).filter(models.Transaction.type == "reversal").one()
    assert original.is_reversed is True
    assert reversal.amount == -100 and reversal.target_wallet == "institute"
    assert reversal.remittance_number != original.remittance_number, "شماره‌ی حواله‌ی استرداد نباید تکرار شود"


# ==========================================
# سناریو ۷ و ۸ — تک‌کیفی
# ==========================================
def test_s07_teacher_only_payment_touches_only_teacher_wallet(world):
    pay(world, 70, wallet="teacher")
    assert_wallet_invariant(world.db, expected_teacher=70, expected_institute=0, expected_balance=70,
                            context="پرداخت فقط معلم")
    transactions = world.db.query(models.Transaction).all()
    assert len(transactions) == 1 and transactions[0].target_wallet == "teacher"


def test_s08_institute_only_payment_touches_only_institute_wallet(world):
    pay(world, 30, wallet="institute")
    assert_wallet_invariant(world.db, expected_teacher=0, expected_institute=30, expected_balance=30,
                            context="پرداخت فقط آموزشگاه")
    transactions = world.db.query(models.Transaction).all()
    assert len(transactions) == 1 and transactions[0].target_wallet == "institute"


# ==========================================
# سناریو ۹ — پرداخت both
# ==========================================
@pytest.mark.parametrize("amount", [100, 101, 999, 1001])
def test_s09_split_payment_shares_sum_exactly_to_amount(world, amount):
    pay(world, amount, wallet="both")
    receipts_ = world.db.query(models.Transaction).filter(models.Transaction.type == "deposit").all()
    assert len(receipts_) == 2, "پرداخت both باید دو رسید (هر کیف یکی) ثبت کند"
    teacher_share = sum(t.amount for t in receipts_ if t.target_wallet == "teacher")
    institute_share = sum(t.amount for t in receipts_ if t.target_wallet == "institute")
    assert teacher_share + institute_share == amount, "جمع دو سهم باید دقیقاً برابر مبلغ پرداخت باشد"
    assert_wallet_invariant(world.db, expected_teacher=teacher_share, expected_institute=institute_share,
                            expected_balance=amount, context=f"تقسیم both برای {amount}")


def test_s09b_explicit_split_is_not_reinterpreted(world):
    pay(world, 500, wallet="both", amount_teacher=200, amount_institute=300)
    assert_wallet_invariant(world.db, expected_teacher=200, expected_institute=300, expected_balance=500,
                            context="تقسیم صریح")


# ==========================================
# سناریو ۱۰ — مبالغ نامعتبر: رد قبل از هر نوشتن
# ==========================================
@pytest.mark.parametrize("case", [
    dict(amount=0, wallet="institute"),                       # صفر
    dict(amount=-50, wallet="institute"),                     # منفی
    dict(amount=0, wallet="teacher"),                         # صفر (کیف معلم)
    dict(amount=0, wallet="both"),                            # صفر در حالت both
    dict(amount=100, wallet="legacy"),                        # کیف نامعتبر (M12)
    dict(amount=100, wallet="both", amount_teacher=-10, amount_institute=110),   # سهم منفی
    dict(amount=100, wallet="both", amount_teacher=None, amount_institute=100),  # تقسیم ناقص
])
def test_s10_invalid_amounts_rejected_before_any_write(world, case):
    before_tx = world.db.query(models.Transaction).count()
    before_wallets = wallets(world.db)
    before_sequence = world.db.query(models.SequenceCounter).count()

    with pytest.raises(HTTPException) as error:
        pay(world, case["amount"], wallet=case["wallet"],
            **{k: v for k, v in case.items() if k.startswith("amount_")})

    assert error.value.status_code == 400, f"انتظار 400 برای {case}، دریافت {error.value.status_code}"
    world.db.rollback()
    assert world.db.query(models.Transaction).count() == before_tx, "هیچ تراکنشی نباید ثبت شود"
    assert wallets(world.db) == before_wallets, "هیچ کیف پولی نباید تغییر کند"
    assert world.db.query(models.SequenceCounter).count() == before_sequence, "شمارنده‌ها نباید مصرف شوند"
    assert_wallet_invariant(world.db, context="بعد از رد شدن پرداخت نامعتبر")


def test_s10c_null_wallet_is_rejected_at_schema_level(world):
    """کیف None به‌جای رسیدن به منطق پول، همان‌جا در اعتبارسنجی schema رد می‌شود (زودتر از هر نوشتن)."""
    from pydantic import ValidationError

    before_tx = world.db.query(models.Transaction).count()
    before_wallets = wallets(world.db)
    with pytest.raises(ValidationError):
        finance.submit_payment(
            FinanceSubmitData(student_id=101, amount=100, target_wallet=None,
                              description="کیف نامعتبر", payment_method="نقدی", date=TODAY_JALALI),
            db=world.db, _="admin", authorization="Bearer wallet-admin-token",
        )
    world.db.rollback()
    assert world.db.query(models.Transaction).count() == before_tx
    assert wallets(world.db) == before_wallets
    assert_wallet_invariant(world.db, context="بعد از رد شدن کیف None")


def test_s10b_invalid_amount_leaves_previous_debt_untouched(world):
    """پرداخت نامعتبر روی بدهی موجود: بدهی دقیقاً همان -۱۰۰ قبلی می‌ماند."""
    submit_session(world)
    with pytest.raises(HTTPException) as error:
        pay(world, 0, wallet="institute")
    assert error.value.status_code == 400
    world.db.rollback()
    assert_wallet_invariant(world.db, expected_teacher=-60, expected_institute=-40, expected_balance=-100,
                            context="بعد از تلاش پرداخت صفر")


# ==========================================
# سناریو ۱۱ — استرداد تکراری
# ==========================================
def test_s11_duplicate_refund_is_rejected_and_changes_nothing(world):
    deposit_tx = pay(world, 100, wallet="institute")["receipt_id"]
    refund(world, deposit_tx)
    snapshot = wallets(world.db)
    tx_count = world.db.query(models.Transaction).count()

    with pytest.raises(HTTPException) as error:
        refund(world, deposit_tx)

    assert error.value.status_code == 400, "استرداد دوم باید 400 بدهد"
    world.db.rollback()
    assert wallets(world.db) == snapshot, "استرداد تکراری نباید هیچ تغییر مالی بسازد"
    assert world.db.query(models.Transaction).count() == tx_count, "ردیف معکوس دوم نباید ثبت شود"
    assert world.db.query(models.Transaction).filter(models.Transaction.type == "reversal").count() == 1
    assert_wallet_invariant(world.db, expected_balance=0, context="بعد از استرداد تکراری")


def test_s11b_refund_of_session_charge_is_rejected(world):
    """شارژ جلسه مسیر استرداد عمومی ندارد (M16) — کیف نباید دست بخورد."""
    submit_session(world)
    charge = world.db.query(models.Transaction).filter(models.Transaction.type == "session_charge").one()
    with pytest.raises(HTTPException) as error:
        refund(world, charge.id)
    assert error.value.status_code == 400
    world.db.rollback()
    assert_wallet_invariant(world.db, expected_balance=-100, context="بعد از رد استرداد شارژ جلسه")
    assert world.db.get(models.Transaction, charge.id).is_reversed is False


# ==========================================
# سناریو ۱۲ — تراکنش‌های deleted/reversed
# ==========================================
def test_s12a_inactive_receipts_are_excluded_from_revenue_reports(world):
    receipt(world.db, amount=100)                                        # فعال ⇒ باید شمرده شود
    receipt(world.db, amount=100, is_deleted=True)                       # حذف‌شده
    receipt(world.db, amount=100, is_reversed=True)                      # برگشت‌خورده
    receipt(world.db, amount=-100, type="reversal")                      # ردیف معکوس (منفی)
    world.db.commit()

    institute_revenue = calculate_institute_collected_revenue(world.db, RANGE_START, RANGE_END)
    turnover = calculate_total_turnover(world.db, RANGE_START, RANGE_END)
    assert institute_revenue == 100, f"درآمد وصول‌شده باید فقط رسید فعال را بشمارد (شد {institute_revenue})"
    assert turnover == 100, f"گردش مالی باید فقط رسید فعال را بشمارد (شد {turnover})"


def test_s12b_refunded_payment_has_no_net_effect_on_active_revenue(world):
    deposit_tx = pay(world, 150, wallet="institute")["receipt_id"]
    assert calculate_institute_collected_revenue(world.db, RANGE_START, RANGE_END) == 150

    refund(world, deposit_tx)
    assert calculate_institute_collected_revenue(world.db, RANGE_START, RANGE_END) == 0, (
        "پس از استرداد، نه اصل رسید (is_reversed) و نه ردیف معکوس نباید در درآمد فعال بمانند"
    )
    assert calculate_total_turnover(world.db, RANGE_START, RANGE_END) == 0


def test_s12c_active_transactions_view_hides_reversed_rows(world):
    """نمای فعال تراکنش‌های دانش‌آموز: ردیف برگشت‌خورده/حذف‌شده نباید دیده شود."""
    active = pay(world, 100, wallet="institute")["receipt_id"]
    refund(world, active)

    rows = finance.get_student_physical_transactions(
        world.student.id, db=world.db, authorization="Bearer wallet-admin-token", _role="admin",
    )
    ids = {row["id"] for row in rows}
    assert active not in ids, "رسید برگشت‌خورده در نمای فعال نباید باشد"
    for row in rows:
        assert row["is_reversed"] is False
    assert_wallet_invariant(world.db, expected_balance=0, context="نمای فعال بعد از استرداد")


def test_s12d_reversed_session_charge_returns_wallet_to_baseline(world):
    """حذف/برگشت جلسه: کیف به حالت اول برمی‌گردد و گزارش درآمد صفر می‌ماند."""
    from dependencies import reverse_session_financial_impacts

    result = submit_session(world)
    assert_wallet_invariant(world.db, expected_balance=-100, context="بعد از شارژ جلسه")

    reverse_session_financial_impacts(result["session_id"], world.db)
    assert_wallet_invariant(world.db, expected_teacher=0, expected_institute=0, expected_balance=0,
                            context="بعد از برگشت جلسه")
    charge = world.db.query(models.Transaction).filter(models.Transaction.type == "session_charge").one()
    assert charge.is_deleted is True
    assert calculate_total_turnover(world.db, RANGE_START, RANGE_END) == 0


# ==========================================
# سناریو ۱۳ — invariant در کل مسیر
# ==========================================
def test_s13_full_walk_invariant_every_step(world):
    """مسیر کامل؛ **بلافاصله بعد از هر گام** مقدار مورد انتظار و invariant بررسی می‌شود."""
    def check(label, expected_teacher, expected_institute, expected_balance):
        teacher, institute, balance = wallets(world.db)
        assert (teacher, institute, balance) == (expected_teacher, expected_institute, expected_balance), (
            f"گام «{label}»: انتظار {(expected_teacher, expected_institute, expected_balance)} "
            f"واقعی {(teacher, institute, balance)}"
        )
        assert balance == teacher + institute, f"نقض invariant در گام «{label}»"
        assert_wallet_invariant(world.db, context=label)

    submit_session(world)                                              # شارژ جلسه ۱۰۰
    check("شارژ جلسه ۱۰۰", -60, -40, -100)

    pay(world, 40, wallet="institute")                                 # پرداخت جزئی
    check("پرداخت ۴۰ به آموزشگاه", -60, 0, -60)

    pay(world, 60, wallet="both", amount_teacher=30, amount_institute=30)
    check("پرداخت تقسیمی ۶۰", -30, 30, 0)

    split_ids = pay(world, 500, wallet="both")["receipt_ids"]           # پرداخت ۵۰۰ (۲۵۰/۲۵۰)
    check("پرداخت ۵۰۰ (both)", 220, 280, 500)

    for receipt_id in split_ids:                                        # استرداد کامل هر دو رسید
        refund(world, receipt_id)
    check("استرداد کامل پرداخت ۵۰۰", -30, 30, 0)


# ==========================================
# سناریو ۱۴ — هم‌زمانی و lost update
# ==========================================
def test_s14a_concurrent_payments_do_not_lose_updates(tmp_path):
    """سه پرداخت هم‌زمان از سه اتصال مستقل: هیچ پرداختی نباید گم شود (UPDATE اتمیک، بدون RMW)."""
    engine = make_engine(f"sqlite:///{tmp_path / 'wallet-concurrency.sqlite'}")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        seed_world(db)

    barrier = Barrier(3)

    def do_payment(_):
        with factory() as db:
            barrier.wait(timeout=20)
            try:
                finance.submit_payment(
                    FinanceSubmitData(student_id=101, amount=100, target_wallet="institute",
                                      description="پرداخت هم‌زمان", payment_method="نقدی", date=TODAY_JALALI),
                    db=db, _="admin", authorization="Bearer wallet-admin-token",
                )
                return 200
            except HTTPException as error:
                return error.status_code

    with ThreadPoolExecutor(max_workers=3) as pool:
        statuses = list(pool.map(do_payment, range(3)))

    with factory() as db:
        teacher, institute, balance = wallets(db)
        assert statuses == [200, 200, 200], f"هر سه پرداخت باید موفق شوند؛ وضعیت‌ها: {statuses}"
        assert institute == 300, f"lost update: انتظار 300، دریافت {institute}"
        assert balance == teacher + institute == 300
        assert db.query(models.Transaction).filter(models.Transaction.type == "deposit").count() == 3
    engine.dispose()


def test_s14b_concurrent_split_payments_keep_sum_consistent(tmp_path):
    """پرداخت‌های هم‌زمان both: هم جمع سهم‌ها و هم invariant باید حفظ شود."""
    engine = make_engine(f"sqlite:///{tmp_path / 'wallet-concurrency-split.sqlite'}")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        seed_world(db)

    barrier = Barrier(2)

    def do_split(_):
        with factory() as db:
            barrier.wait(timeout=20)
            finance.submit_payment(
                FinanceSubmitData(student_id=101, amount=101, target_wallet="both",
                                  description="تقسیمی هم‌زمان", payment_method="نقدی", date=TODAY_JALALI),
                db=db, _="admin", authorization="Bearer wallet-admin-token",
            )
            return 200

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(do_split, range(2)))

    with factory() as db:
        teacher, institute, balance = wallets(db)
        assert statuses == [200, 200]
        # هر پرداخت ۱۰۱ ⇒ ۵۰+۵۱؛ دو پرداخت ⇒ ۱۰۰+۱۰۲ (ترتیب سهم‌ها ثابت است)
        assert teacher + institute == 202, f"جمع سهم‌ها باید 202 باشد، شد {teacher + institute}"
        assert balance == teacher + institute
        receipts_ = db.query(models.Transaction).filter(models.Transaction.type == "deposit").all()
        assert sum(t.amount for t in receipts_) == 202
    engine.dispose()


def test_s14c_production_bulk_update_keeps_invariant_and_survives_stale_writer(tmp_path):
    """bulk update کیف (الگوی پروداکشن: UPDATE خام + refresh + sync) نباید هیچ اثری گم کند،
    و یک سشن دیگر با آبجکت کهنه که فقط فیلد نامرتبط را می‌نویسد نباید کیف‌ها را برگرداند."""
    engine = make_engine(f"sqlite:///{tmp_path / 'wallet-bulk.sqlite'}")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        seed_world(db)

    stale_db = factory()
    stale_db.get(models.Student, 101)          # خواندن کهنه (۰/۰/۰) پیش از پرداخت

    other_db = factory()
    other_db.query(models.Student).filter(models.Student.id == 101).update(
        {models.Student.wallet_institute: func.coalesce(models.Student.wallet_institute, 0) + 100},
        synchronize_session=False,
    )
    # دقیقاً همان کاری که اندپوینت‌های پول انجام می‌دهند: refresh + سینک کل
    writer_student = other_db.get(models.Student, 101)
    other_db.refresh(writer_student)
    writer_student.sync_wallet_balance()
    other_db.commit()
    other_db.close()

    with factory() as db:                      # invariant باید بعد از bulk update برقرار باشد
        teacher, institute, balance = wallets(db)
        assert (institute, balance) == (100, 100), (
            f"bulk update + sync باید جمع را 100 کند (شد institute={institute}, balance={balance})"
        )
        assert balance == teacher + institute

    stale_student = stale_db.get(models.Student, 101)
    stale_student.first_name = "نام جدید"       # نوشتن فیلد نامرتبط با آبجکت کهنه
    stale_db.commit()
    stale_db.close()

    with factory() as db:
        teacher, institute, balance = wallets(db)
        assert institute == 100, f"کیف آموزشگاه باید 100 بماند (نشد {institute}) — ریسک lost update"
        assert balance == teacher + institute == 100, (
            f"نقض invariant پس از کامیت سشن کهنه: balance={balance} != {teacher}+{institute}"
        )
    engine.dispose()


def test_s14d_counterfactual_read_modify_write_would_lose_update(tmp_path):
    """شاهدِ ریسک (فقط برای سنجش شدت — کد اصلی این الگو را استفاده نمی‌کند):
    اگر به‌جای UPDATE اتمیک، الگوی «بخوان-جمع-بنویس» در پایتون استفاده شود،
    پرداخت دوم مقدار پرداخت اول را پاک می‌کند."""
    engine = make_engine(f"sqlite:///{tmp_path / 'wallet-rmw.sqlite'}")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        seed_world(db)

    with factory() as db:
        student = db.get(models.Student, 101)
        read_teacher, read_institute = student.wallet_teacher, student.wallet_institute  # خواندن ۱

        with factory() as db2:  # «پرداخت موازی» که بین خواندن و نوشتن کامیت می‌شود
            db2.query(models.Student).filter(models.Student.id == 101).update(
                {models.Student.wallet_institute: func.coalesce(models.Student.wallet_institute, 0) + 100},
                synchronize_session=False,
            )
            db2.commit()

        # نوشتن کور با مقدار قدیمی ← همان چیزی که طراحی اتمیک فعلی از آن جلوگیری می‌کند
        student.wallet_institute = read_institute + 100
        student.sync_wallet_balance()
        db.commit()

    with factory() as db:
        institute = wallets(db)[1]
        assert institute == 100, (
            f"الگوی RMW به‌صورت مورد انتظار یک پرداخت را از دست داد (شد {institute}) — "
            "این تست ارزش UPDATE اتمیک فعلی را مستند می‌کند"
        )
    engine.dispose()


# ==========================================
# قواعد کسب‌وکار: معنای علامت کیف
# ==========================================
def test_business_rule_signs_and_settlement_semantics(world):
    # منفی = بدهی دانش‌آموز
    submit_session(world)
    assert_wallet_invariant(world.db, expected_teacher=-60, expected_institute=-40, expected_balance=-100,
                            context="بدهی")
    assert wallets(world.db)[2] < 0, "منفی = بدهی دانش‌آموز"

    # صفر = تسویه (هر دو کیف دقیقاً صفر)
    pay(world, 60, wallet="teacher")
    pay(world, 40, wallet="institute")
    assert_wallet_invariant(world.db, expected_teacher=0, expected_institute=0, expected_balance=0,
                            context="تسویه")
    assert wallets(world.db)[2] == 0, "صفر = تسویه"

    # مثبت = اعتبار، و فقط همان کیفی که پول گرفته تغییر می‌کند
    pay(world, 250, wallet="teacher")
    teacher, institute, balance = wallets(world.db)
    assert balance == 250 > 0, "مثبت = اعتبار"
    assert (teacher, institute) == (250, 0), "اعتبار فقط نزد همان کیفی که پرداخت شده"
    assert_wallet_invariant(world.db, expected_balance=250, context="اعتبار")


def test_business_rule_invariant_holds_for_legacy_null_wallets():
    """ستون‌های nullable: مقدار None باید مثل صفر رفتار کند و invariant نشکند."""
    engine = make_engine(poolclass=StaticPool)
    try:
        with sessionmaker(bind=engine, expire_on_commit=False)() as db:
            world = seed_world(db)
            student = db.get(models.Student, 101)
            student.wallet_teacher = None
            student.wallet_institute = None
            db.commit()
            teacher, institute, balance = wallets(db)
            assert (teacher, institute, balance) == (0, 0, 0), f"None باید صفر شود: {(teacher, institute, balance)}"
            assert balance == teacher + institute
    finally:
        models.Base.metadata.drop_all(engine)
        engine.dispose()


# ==========================================
# پوشش مسیرهای پول (Path coverage) — اثبات تجربی invariant روی همه‌ی مسیرهای نوشتن کیف
# ==========================================
def test_path_installment_manual_payment_keeps_invariant(world):
    """مسیر «پرداخت دستی قسط» (finance.pay_installment_manually): فقط آموزشگاه شارژ می‌شود."""
    installment = models.Installment(enrollment_id=world.enrollment.id, amount=300, due_date="1405/07/01", is_paid=False)
    world.db.add(installment)
    world.db.commit()

    finance.pay_installment_manually(installment.id, db=world.db, _="admin",
                                     payment_method="نقدی", authorization="Bearer wallet-admin-token")
    assert_wallet_invariant(world.db, expected_teacher=0, expected_institute=300, expected_balance=300,
                            context="پرداخت دستی قسط")

    # پرداخت دوم روی همان قسط باید رد شود و کیف دست‌نخورده بماند
    with pytest.raises(HTTPException) as error:
        finance.pay_installment_manually(installment.id, db=world.db, _="admin",
                                        payment_method="نقدی", authorization="Bearer wallet-admin-token")
    assert error.value.status_code == 400
    world.db.rollback()
    assert_wallet_invariant(world.db, expected_balance=300, context="بعد از رد پرداخت تکراری قسط")


def test_path_admin_update_transaction_keeps_invariant(world):
    """مسیر «ویرایش تراکنش توسط ادمین» (admin.update_transaction): دلتای اختلاف، اتمیک اعمال می‌شود."""
    from routers import admin as admin_router
    from schemas import TransactionUpdate

    receipt_id = pay(world, 100, wallet="institute")["receipt_id"]
    assert_wallet_invariant(world.db, expected_institute=100, expected_balance=100, context="قبل از ویرایش")

    admin_router.update_transaction(receipt_id, TransactionUpdate(amount=250, description="ویرایش مبلغ",
                                                                 date=TODAY_JALALI),
                                    db=world.db, _="admin")
    assert_wallet_invariant(world.db, expected_institute=250, expected_balance=250,
                            context="بعد از ویرایش ۱۰۰→۲۵۰")


def test_path_admin_delete_transaction_keeps_invariant(world):
    """مسیر «حذف تراکنش توسط ادمین» (admin.delete_transaction): اثر کیف باید کامل برگردد."""
    from routers import admin as admin_router

    submit_session(world)                                    # کیف: ‎-۶۰/-۴۰
    charge = world.db.query(models.Transaction).filter(models.Transaction.type == "session_charge").one()

    admin_router.delete_transaction(charge.id, db=world.db, _="admin")
    assert_wallet_invariant(world.db, expected_teacher=0, expected_institute=0, expected_balance=0,
                            context="بعد از حذف شارژ جلسه")


def test_path_session_reversal_restores_every_component(world):
    """برگشت جلسه (dependencies.reverse_session_financial_impacts): هر دو مؤلفه دقیقاً برمی‌گردند."""
    from dependencies import reverse_session_financial_impacts

    result = submit_session(world)
    assert_wallet_invariant(world.db, expected_teacher=-60, expected_institute=-40, context="پس از شارژ")

    reverse_session_financial_impacts(result["session_id"], world.db)
    assert_wallet_invariant(world.db, expected_teacher=0, expected_institute=0, expected_balance=0,
                            context="پس از برگشت جلسه")


# ==========================================
# پرداخت داخلی: idempotency و استرداد پس از مصرف اعتبار
# ==========================================
def test_idempotent_replay_credits_wallet_only_once(world):
    """پرداخت با همان idempotency_key دوبار ⇒ فقط یک‌بار شارژ (بدون شارژ دوباره)."""
    first = pay(world, 120, wallet="institute", idempotency_key="wallet-key-1")
    assert_wallet_invariant(world.db, expected_institute=120, expected_balance=120, context="پرداخت اول")

    second = pay(world, 120, wallet="institute", idempotency_key="wallet-key-1")
    assert second.get("duplicate") is True, "پاسخ دوم باید replay باشد (duplicate=True)"
    assert_wallet_invariant(world.db, expected_institute=120, expected_balance=120,
                            context="بعد از replay (نباید دوباره شارژ شود)")
    assert deposit_count(world.db) == 1, "replay نباید رسید دوم بسازد"
    assert second["receipt_id"] == first["receipt_id"]


def test_refund_after_credit_was_consumed_by_session_still_keeps_invariant(world):
    """استرداد پس از مصرف اعتبار: کیف می‌تواند منفی شود ولی invariant هرگز نمی‌شکند."""
    deposit_id = pay(world, 100, wallet="both")["receipt_ids"]
    submit_session(world)                                    # اعتبار خرج می‌شود
    for receipt_id in deposit_id:
        refund(world, receipt_id)

    teacher, institute, balance = wallets(world.db)
    assert balance == teacher + institute, f"invariant شکست: {balance} != {teacher}+{institute}"
    # پرداخت ۱۰۰ (۵۰/۵۰) سپس شارژ ۱۰۰ (۶۰/۴۰) سپس استرداد ۱۰۰ ⇒ ‎-۶۰/-۴۰
    assert (teacher, institute, balance) == (-60, -40, -100)


# ==========================================
# هم‌زمانی استرداد (گیت UPDATE مشروط)
# ==========================================
def test_concurrent_double_refund_applies_exactly_once(tmp_path):
    """دو استرداد هم‌زمان از دو اتصال: دقیقاً یکی موفق، کیف فقط یک‌بار کسر می‌شود."""
    engine = make_engine(f"sqlite:///{tmp_path / 'wallet-refund-race.sqlite'}")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        seed_world(db)
        deposit_id = finance.submit_payment(
            FinanceSubmitData(student_id=101, amount=200, target_wallet="institute",
                              description="پرداخت برای استرداد هم‌زمان", payment_method="نقدی",
                              date=TODAY_JALALI),
            db=db, _="admin", authorization="Bearer wallet-admin-token",
        )["receipt_id"]

    barrier = Barrier(2)

    def do_refund(_):
        with factory() as db:
            barrier.wait(timeout=20)
            try:
                finance.refund_transaction(deposit_id, db=db, authorization="Bearer wallet-admin-token", _="admin")
                return 200
            except HTTPException as error:
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(do_refund, range(2)))

    with factory() as db:
        assert sorted(statuses) == [200, 400], f"دقیقاً یکی باید موفق شود؛ وضعیت‌ها: {statuses}"
        teacher, institute, balance = wallets(db)
        assert balance == teacher + institute, f"invariant شکست: {balance} != {teacher}+{institute}"
        assert (teacher, institute, balance) == (0, 0, 0), (
            f"کسر باید یک‌بار انجام شود (شد {(teacher, institute, balance)})"
        )
        assert db.query(models.Transaction).filter(models.Transaction.type == "reversal").count() == 1
    engine.dispose()


# ==========================================
# لبه‌های خطرناک (ادامه‌ی آدیت — سناریو ۱۳)
# ==========================================
def credit_legacy_both_receipt(world, amount=100, share_teacher=40, share_institute=60, **overrides):
    """ساخت رسید legacy با target_wallet='both' و شارژ کیف‌ها به همان اندازه (وضعیت نسخه‌های قدیمی)."""
    legacy = receipt(world.db, amount=amount, target_wallet="both",
                     share_teacher=share_teacher, share_institute=share_institute, **overrides)
    world.db.query(models.Student).filter(models.Student.id == 101).update(
        {
            models.Student.wallet_teacher: func.coalesce(models.Student.wallet_teacher, 0) + share_teacher,
            models.Student.wallet_institute: func.coalesce(models.Student.wallet_institute, 0) + share_institute,
        },
        synchronize_session=False,
    )
    world.db.commit()
    student = world.db.get(models.Student, 101)
    world.db.refresh(student)
    student.sync_wallet_balance()
    world.db.commit()
    return legacy


def edit_transaction(world, transaction_id, amount, description="ویرایش تستی"):
    """ویرایش ادمین + assert خودکار invariant (سناریو ۱۳)."""
    from routers import admin as admin_router
    from schemas import TransactionUpdate

    result = admin_router.update_transaction(
        transaction_id, TransactionUpdate(amount=amount, description=description, date=TODAY_JALALI),
        db=world.db, _="admin",
    )
    assert_wallet_invariant(world.db, context=f"بعد از ویرایش به {amount}")
    return result


def test_fix_fw2_legacy_both_receipt_edit_applies_real_delta(world):
    """✅ رگرسیون F-W2 (نسخه‌ی سبزشده‌ی `test_finding_fw2_*`): ویرایش رسید legacy با
    `target_wallet='both'` باید delta واقعی را با **نسبت سهم قبلی** روی هر دو کیف اعمال کند
    (قبلاً هیچ دلتایی اعمال نمی‌شد ⇒ دفتر و کیف واگرا می‌شدند)."""
    legacy = credit_legacy_both_receipt(world)             # کیف: ۴۰/۶۰ و سهم: ۴۰/۶۰
    assert wallets(world.db) == (40, 60, 100)

    edit_transaction(world, legacy.id, 200, "ویرایش رسید both")
    # delta = ۱۰۰ با نسبت ۴۰:۶۰ ⇒ ۴۰ به معلم و ۶۰ به آموزشگاه
    assert_wallet_invariant(world.db, expected_teacher=80, expected_institute=120, expected_balance=200,
                            context="پس از ویرایش ۱۰۰→۲۰۰ رسید both")

    world.db.expire_all()
    legacy = world.db.get(models.Transaction, legacy.id)
    assert (legacy.share_teacher, legacy.share_institute) == (80, 120), (
        "سهم‌های رسید both باید با مبلغ جدید همراستا شوند (همان چیزی که مسیر refund ملاک می‌گیرد)"
    )
    assert legacy.share_teacher + legacy.share_institute == legacy.amount == 200
    assert_no_float_money(world.db, legacy.id, context="رسید both پس از ویرایش")


def test_fix_fw1b_session_charge_edit_updates_shares_and_reports(world):
    """✅ رگرسیون F-W1b (نسخه‌ی سبزشده‌ی `test_finding_fw1b_*`): هنگام ویرایش session_charge،
    `share_teacher/share_institute` هم اصلاح می‌شوند و گزارش‌های `financial_calculations`
    سهم جدید را نشان می‌دهند (قبلاً سهم قدیمی در گزارش می‌ماند)."""
    submit_session(world)                                  # شارژ ۱۰۰ (۶۰/۴۰)
    charge = world.db.query(models.Transaction).filter(models.Transaction.type == "session_charge").one()

    edit_transaction(world, charge.id, -130, "افزایش شارژ جلسه")

    world.db.expire_all()
    charge = world.db.get(models.Transaction, charge.id)
    shares_total = abs(charge.share_teacher or 0) + abs(charge.share_institute or 0)
    assert shares_total == abs(charge.amount) == 130, (
        f"جمع سهم‌ها ({shares_total}) باید با مبلغ شارژ ({abs(charge.amount)}) برابر باشد"
    )
    assert (charge.share_teacher, charge.share_institute) == (78, 52), "تقسیم ۱۳۰ با نسبت ۶۰/۴۰"

    # گزارش‌ها دقیقاً از همین ستون‌ها تغذیه می‌شوند ⇒ باید عدد جدید را نشان دهند نه ۴۰/۶۰ قدیمی
    assert calculate_institute_session_revenue(world.db, RANGE_START, RANGE_END) == 52
    assert calculate_teacher_session_revenue(world.db, world.teacher.id, RANGE_START, RANGE_END) == 78

    # کیف‌ها هم با همان سهم‌ها هم‌راستا هستند و invariant برقرار است
    assert_wallet_invariant(world.db, expected_teacher=-78, expected_institute=-52, expected_balance=-130,
                            context="پس از ویرایش شارژ جلسه")
    assert_no_float_money(world.db, charge.id, context="شارژ جلسه پس از ویرایش")


def test_edge_enrollment_payment_refund_reverses_institute_wallet(world):
    """استرداد واریز ثبت‌نامی (type=enrollment_payment، target_wallet=None) — شاخه‌ی M16:
    باید کیف آموزشگاه را برگرداند و invariant نشکند."""
    transaction = models.Transaction(
        student_id=101, enrollment_id=world.enrollment.id, course_id=1, branch_id=1,
        amount=80, payment_method="نقدی", date=TODAY_JALALI, type="enrollment_payment",
        description="واریز ثبت‌نامی",
    )
    world.db.add(transaction)
    world.db.query(models.Student).filter(models.Student.id == 101).update(
        {models.Student.wallet_institute: func.coalesce(models.Student.wallet_institute, 0) + 80},
        synchronize_session=False,
    )
    world.db.commit()
    student = world.db.get(models.Student, 101)
    world.db.refresh(student)
    student.sync_wallet_balance()
    world.db.commit()
    assert_wallet_invariant(world.db, expected_institute=80, expected_balance=80, context="واریز ثبت‌نامی")

    refund(world, transaction.id)
    assert_wallet_invariant(world.db, expected_teacher=0, expected_institute=0, expected_balance=0,
                            context="استرداد واریز ثبت‌نامی")


def test_edge_direct_balance_write_is_resynced_to_components(world):
    """اگر کسی wallet_balance را مستقیم و ناسازگار بنویسد، listener پروژه باید آن را به
    جمع دو مؤلفه برگرداند (مؤلفه‌ها منبع حقیقت‌اند)."""
    student = world.db.get(models.Student, 101)
    student.wallet_teacher = 0
    student.wallet_institute = 0
    student.wallet_balance = 9999          # نوشتن عمداً ناسازگار
    world.db.commit()

    assert_wallet_invariant(world.db, expected_teacher=0, expected_institute=0, expected_balance=0,
                            context="بازنویسی مستقیم balance")


def test_edge_absent_penalty_charge_keeps_invariant(world):
    """مسیر جریمه‌ی غیبت غیرموجه (دومین نقطه‌ی تغییر کیف در attendance.py)."""
    world.course.rule_calc_absent = True
    world.db.commit()

    request = AttendanceSubmitData(course_id=world.course.id, date=TODAY_JALALI,
                                   items=[AttendanceItem(student_id=world.student.id, status="Absent",
                                                         excused=False)])
    attendance.submit_session_and_calculate(request, db=world.db,
                                            authorization="Bearer wallet-admin-token", sub_role="admin")
    assert_wallet_invariant(world.db, expected_teacher=-60, expected_institute=-40, expected_balance=-100,
                            context="جریمه‌ی غیبت غیرموجه")
    session = world.db.query(models.SessionLog).order_by(models.SessionLog.id.desc()).first()
    assert session.absent_penalty_teacher == 60 and session.absent_penalty_institute == 40


def test_fix_fw1a_session_charge_edit_keeps_money_integer(world):
    """✅ رگرسیون F-W1a (نسخه‌ی سبزشده‌ی `test_finding_fw1a_*`): ویرایش session_charge با
    مبلغی که تقسیمش اعشاری می‌شود (۱۰۱ با نسبت ۶۰/۴۰) نباید هیچ مقدار اعشاری در کیف یا
    ستون‌های سهم بنویسد؛ باقیمانده به‌صورت قطعی به آموزشگاه می‌رسد."""
    submit_session(world)                                     # شارژ ۱۰۰ ⇒ ‎-۶۰/-۴۰
    charge = world.db.query(models.Transaction).filter(models.Transaction.type == "session_charge").one()

    edit_transaction(world, charge.id, -101, "اصلاح شارژ جلسه")

    # ۱۰۱ با نسبت ۶۰:۴۰ ⇒ ۶۰.۶ و ۴۰.۴؛ تقسیم صحیح: ۶۰ معلم و ۴۱ آموزشگاه (باقیمانده به آموزشگاه)
    assert_wallet_invariant(world.db, expected_teacher=-60, expected_institute=-41, expected_balance=-101,
                            context="پس از ویرایش شارژ جلسه به ۱۰۱")
    world.db.expire_all()
    charge = world.db.get(models.Transaction, charge.id)
    assert (charge.share_teacher, charge.share_institute) == (60, 41)
    assert charge.share_teacher + charge.share_institute == abs(charge.amount) == 101
    assert_no_float_money(world.db, charge.id, context="شارژ ۱۰۱ پس از ویرایش")


# ==========================================
# رگرسیون تکمیلی سه باگ F-W1a / F-W1b / F-W2 (تسک fix)
# ==========================================
@pytest.mark.parametrize("new_amount", [-1, -7, -101, -103, -999, -1001, -1500])
def test_fix_fw1a_no_float_for_any_awkward_charge_amount(world, new_amount):
    """F-W1a: هیچ مبلغ «بدتقسیمی» نباید اعشار تولید کند — نه در کیف، نه در سهم‌ها."""
    submit_session(world)
    charge = world.db.query(models.Transaction).filter(models.Transaction.type == "session_charge").one()
    edit_transaction(world, charge.id, new_amount)

    teacher, institute, balance = wallets(world.db)
    assert (teacher, institute, balance) == (-60 - (abs(new_amount) - 100) * 60 // 100,
                                             -40 - (abs(new_amount) - 100) + (abs(new_amount) - 100) * 60 // 100,
                                             -abs(new_amount)), "تقسیم ۶۰:۴۰ با باقیمانده به آموزشگاه"
    assert balance == teacher + institute
    assert_no_float_money(world.db, charge.id, context=f"شارژ {new_amount}")


def test_fix_fw1a_no_float_when_charge_is_reduced_or_untouched(world):
    """F-W1a: هم کاهش مبلغ (برگشت اعتبار) و هم ویرایشِ بدون تغییر مبلغ باید صحیح‌بمانند."""
    submit_session(world)
    charge = world.db.query(models.Transaction).filter(models.Transaction.type == "session_charge").one()

    edit_transaction(world, charge.id, -100, "فقط تغییر شرح")     # مبلغ ثابت ⇒ کیف نباید عوض شود
    assert_wallet_invariant(world.db, expected_teacher=-60, expected_institute=-40, expected_balance=-100,
                            context="ویرایش بدون تغییر مبلغ")

    edit_transaction(world, charge.id, -3, "کاهش شارژ")           # ۳ با نسبت ۶۰:۴۰ ⇒ ۱ و ۲
    assert_wallet_invariant(world.db, expected_teacher=-1, expected_institute=-2, expected_balance=-3,
                            context="کاهش شارژ به ۳")
    assert_no_float_money(world.db, charge.id, context="شارژ ۳")


def test_fix_fw1b_shares_stay_consistent_across_many_edits(world):
    """F-W1b: در یک زنجیره‌ی ویرایش، هر بار جمع سهم‌ها == |مبلغ| و گزارش‌ها با کیف هم‌راستا بمانند."""
    submit_session(world)
    charge = world.db.query(models.Transaction).filter(models.Transaction.type == "session_charge").one()

    for amount in (-130, -77, -501, -100):
        edit_transaction(world, charge.id, amount)
        world.db.expire_all()
        row = world.db.get(models.Transaction, charge.id)
        assert abs(row.share_teacher or 0) + abs(row.share_institute or 0) == abs(row.amount), (
            f"پس از ویرایش به {amount}: سهم‌ها ({row.share_teacher}/{row.share_institute}) "
            f"با مبلغ ({row.amount}) ناسازگارند"
        )
        assert calculate_institute_session_revenue(world.db, RANGE_START, RANGE_END) == row.share_institute
        assert calculate_teacher_session_revenue(world.db, world.teacher.id, RANGE_START, RANGE_END) == row.share_teacher
        assert_wallet_invariant(world.db, expected_teacher=-row.share_teacher,
                                expected_institute=-row.share_institute, expected_balance=-abs(row.amount),
                                context=f"زنجیره‌ی ویرایش در گام {amount}")


def test_fix_fw1b_legacy_zero_share_charge_is_left_untouched(world):
    """F-W1b (محدودیت مستند): ردیف legacy با سهم صفر (چیزی که سازنده‌ی فعلی attendance تولید
    نمی‌کند) دست‌نخورده می‌ماند تا مسیر delete سهمی را برنگرداند که هرگز کسر نشده بود."""
    legacy = receipt(world.db, amount=-100, type="session_charge", target_wallet=None,
                     share_teacher=0, share_institute=0)
    world.db.commit()

    edit_transaction(world, legacy.id, -250, "ویرایش شارژ بی‌سهم")
    assert_wallet_invariant(world.db, expected_teacher=0, expected_institute=0, expected_balance=0,
                            context="ویرایش ردیف legacy بی‌سهم")
    world.db.expire_all()
    legacy = world.db.get(models.Transaction, legacy.id)
    assert (legacy.share_teacher, legacy.share_institute) == (0, 0), "سهم صفر legacy نباید مصنوعی پر شود"
    assert legacy.amount == -250


def test_fix_fw1b_legacy_inconsistent_shares_are_healed(world):
    """F-W1b: ردیف legacy که سهمش با مبلغ هم‌خوان نیست، با ویرایش «درمان» می‌شود:
    سهم‌ها به نسبت قبلی با مبلغ هم‌راستا می‌شوند و کیف هم دقیقاً با همان سهم‌ها منطبق می‌گردد."""
    legacy = receipt(world.db, amount=-100, type="session_charge", target_wallet=None,
                     share_teacher=30, share_institute=30)
    world.db.query(models.Student).filter(models.Student.id == 101).update(
        {models.Student.wallet_teacher: -30, models.Student.wallet_institute: -30},
        synchronize_session=False)
    world.db.commit()
    student = world.db.get(models.Student, 101)
    world.db.refresh(student)
    student.sync_wallet_balance()
    world.db.commit()

    edit_transaction(world, legacy.id, -100, "ویرایش ردیف ناسازگار")
    world.db.expire_all()
    legacy = world.db.get(models.Transaction, legacy.id)
    assert (legacy.share_teacher, legacy.share_institute) == (50, 50)
    assert legacy.share_teacher + legacy.share_institute == abs(legacy.amount) == 100
    assert_wallet_invariant(world.db, expected_teacher=-50, expected_institute=-50, expected_balance=-100,
                            context="هم‌راستاشدن سهم legacy با کیف")
    assert_no_float_money(world.db, legacy.id, context="ردیف legacy درمان‌شده")


def test_fix_fw2_both_edit_fallback_is_half_split_with_remainder_to_institute(world):
    """F-W2 (fallback مستند): رسید legacy with بدون سهم قبلی ⇒ تقسیم دلتا نصف-نصف و
    باقیمانده‌ی فرد به آموزشگاه — دقیقاً همان قاعده‌ی مسیر refund."""
    legacy = receipt(world.db, amount=100, target_wallet="both", share_teacher=0, share_institute=0)
    world.db.commit()

    edit_transaction(world, legacy.id, 201)          # delta = ۱۰۱ ⇒ ۵۰ معلم و ۵۱ آموزشگاه
    world.db.expire_all()
    legacy = world.db.get(models.Transaction, legacy.id)
    assert_wallet_invariant(world.db, expected_teacher=50, expected_institute=51, expected_balance=101,
                            context="fallback نصف-نصف برای ردیف both بی‌سهم")
    assert (legacy.share_teacher, legacy.share_institute) == (100, 101)
    assert legacy.share_teacher + legacy.share_institute == legacy.amount == 201
    assert_no_float_money(world.db, legacy.id, context="رسید both با fallback")


def test_fix_fw2_repeated_both_edits_split_delta_by_prior_ratio(world):
    """F-W2: ویرایش‌های پیاپی روی یک رسید both — هر گام delta را با نسبت جاری تقسیم می‌کند."""
    legacy = credit_legacy_both_receipt(world)                 # ۴۰/۶۰ از ۱۰۰
    edit_transaction(world, legacy.id, 150)                    # ‎+۵۰ با ۴۰:۶۰ ⇒ ‎+۲۰/+۳۰
    assert_wallet_invariant(world.db, expected_teacher=60, expected_institute=90, expected_balance=150,
                            context="گام اول ویرایش both")

    edit_transaction(world, legacy.id, 75)                     # ‎-۷۵ با ۴۰:۶۰ ⇒ ‎-۳۰/-۴۵
    world.db.expire_all()
    row = world.db.get(models.Transaction, legacy.id)
    assert (row.share_teacher, row.share_institute) == (30, 45)
    assert_wallet_invariant(world.db, expected_teacher=30, expected_institute=45, expected_balance=75,
                            context="گام دوم ویرایش both")
    assert_no_float_money(world.db, legacy.id, context="رسید both پس از دو ویرایش")


def test_fix_fw2_refund_after_edit_reverses_exactly_what_was_credited(world):
    """F-W2 + رگرسیون refund: استردادِ رسیدِ ویرایش‌شده باید دقیقاً همان چیزی را برگرداند که
    ویرایش اعمال کرده بود ⇒ کیف‌ها به حالت پایه برمی‌گردند (سهم‌ها مبنای refund هستند)."""
    legacy = credit_legacy_both_receipt(world)                 # کیف: ۴۰/۶۰
    edit_transaction(world, legacy.id, 300)                    # ‎+۲۰۰ با ۴۰:۶۰ ⇒ کیف: ۱۲۰/۱۸۰

    refund(world, legacy.id)
    assert_wallet_invariant(world.db, expected_teacher=0, expected_institute=0, expected_balance=0,
                            context="استرداد کامل پس از ویرایش رسید both")


def test_fix_fw1b_refund_and_reports_unaffected_for_normal_receipts(world):
    """رگرسیون: مسیرهای سالم قبلی (پرداخت teacher/institute، refund و گزارش‌ها) دست‌نخورده‌اند."""
    teacher_receipt = pay(world, 90, wallet="teacher")["receipt_id"]
    institute_receipt = pay(world, 110, wallet="institute")["receipt_id"]
    assert_wallet_invariant(world.db, expected_teacher=90, expected_institute=110, expected_balance=200,
                            context="پرداخت‌های teacher/institute")

    # همان خروجی قبلیِ گزارش‌ها: فقط institute درآمد وصولی دارد (۹۰ نزد معلم است، نه آموزشگاه)
    assert calculate_institute_collected_revenue(world.db, RANGE_START, RANGE_END) == 110
    assert calculate_total_turnover(world.db, RANGE_START, RANGE_END) == 200

    refund(world, teacher_receipt)
    assert_wallet_invariant(world.db, expected_teacher=0, expected_institute=110, expected_balance=110,
                            context="استرداد فقط رسید معلم")
    refund(world, institute_receipt)
    assert_wallet_invariant(world.db, expected_teacher=0, expected_institute=0, expected_balance=0,
                            context="استرداد هر دو رسید")

    for receipt_id in (teacher_receipt, institute_receipt):
        assert_no_float_money(world.db, receipt_id, context="رسید عادی")


def test_fix_teacher_and_institute_edit_behavior_is_preserved(world):
    """رگرسیون: ویرایش رسید teacher-only و institute-only همان رفتار قبلی را دارد
    (کل delta فقط به همان یک کیف می‌رود و کیف دیگر دست‌نخورده می‌ماند)."""
    teacher_receipt = pay(world, 100, wallet="teacher")["receipt_id"]
    edit_transaction(world, teacher_receipt, 260)
    assert_wallet_invariant(world.db, expected_teacher=260, expected_institute=0, expected_balance=260,
                            context="ویرایش رسید teacher-only")

    institute_receipt = pay(world, 100, wallet="institute")["receipt_id"]
    edit_transaction(world, institute_receipt, 40)
    assert_wallet_invariant(world.db, expected_teacher=260, expected_institute=40, expected_balance=300,
                            context="ویرایش رسید institute-only")

    world.db.expire_all()
    for receipt_id in (teacher_receipt, institute_receipt):
        assert_no_float_money(world.db, receipt_id, context="رسید تک‌کیفی ویرایش‌شده")


def test_fix_delete_after_session_charge_edit_restores_wallets(world):
    """رگرسیون delete: حذف شارژ جلسه‌ای که ویرایش شده باید کیف‌ها را با همان سهم‌های جدید
    کامل برگرداند (بدون اعشار و با invariant برقرار)."""
    from routers import admin as admin_router

    submit_session(world)
    charge = world.db.query(models.Transaction).filter(models.Transaction.type == "session_charge").one()
    edit_transaction(world, charge.id, -130)                   # ‎-۷۸/-۵۲
    assert_wallet_invariant(world.db, expected_teacher=-78, expected_institute=-52, context="پیش از حذف")

    admin_router.delete_transaction(charge.id, db=world.db, _="admin")
    assert_wallet_invariant(world.db, expected_teacher=0, expected_institute=0, expected_balance=0,
                            context="پس از حذف شارژ ویرایش‌شده")


def test_fix_float_amount_input_never_reaches_money_columns(world):
    """F-W1a (لایه‌ی ورودی): مبلغ اعشاری در `TransactionUpdate` نباید به عدد اعشاری در DB برسد —
    یا در اعتبارسنجی رد می‌شود یا به int کوتاه می‌شود؛ در هر حال ستون‌ها integer می‌مانند."""
    from pydantic import ValidationError
    from schemas import TransactionUpdate

    try:
        payload = TransactionUpdate(amount=100.5, description="ورودی اعشاری", date=TODAY_JALALI)
        assert isinstance(payload.amount, int), f"مبلغ باید int شود؛ شد {payload.amount!r}"
    except ValidationError:
        pass   # مسیر مطلوب‌تر: رد کامل ورودی اعشاری

    receipt_id = pay(world, 100, wallet="institute")["receipt_id"]
    edit_transaction(world, receipt_id, 250)
    assert_no_float_money(world.db, receipt_id, context="پس از ورودی اعشاری و ویرایش")


def test_fix_fw2_negative_delta_stays_integer_and_coherent(world):
    """F-W2: دلتای منفیِ یک واحدی باید بدون اعشار و با همان نسبت قبلی تقسیم شود؛
    کیف‌ها هم دقیقاً هم‌راستای سهم‌های ذخیره‌شده بمانند (سازگاری کامل با refund)."""
    legacy = credit_legacy_both_receipt(world)                  # کیف ۴۰/۶۰ | سهم ۴۰/۶۰
    edit_transaction(world, legacy.id, 99)                      # delta = ‎-۱ با نسبت ۴۰:۶۰

    world.db.expire_all()
    row = world.db.get(models.Transaction, legacy.id)
    assert (row.share_teacher, row.share_institute) == (39, 60)
    assert row.share_teacher + row.share_institute == row.amount == 99
    # جمع کیف‌ها دقیقاً به اندازه‌ی delta (‎-۱) تغییر کرد: ۱۰۰ ⇒ ۹۹
    assert_wallet_invariant(world.db, expected_teacher=39, expected_institute=60, expected_balance=99,
                            context="دلتای منفی ۱ روی رسید both")
    assert_no_float_money(world.db, legacy.id, context="دلتای منفی رسید both")

    # و استرداد بعدی، با همان سهم‌های ذخیره‌شده، کیف‌ها را کامل به حالت پایه برمی‌گرداند
    # (اثبات هم‌راستایی «کیف ⇄ سهم» بعد از ویرایش با دلتای منفی و باقیمانده‌ی نسبتی)
    refund(world, legacy.id)
    assert_wallet_invariant(world.db, expected_teacher=0, expected_institute=0, expected_balance=0,
                            context="استرداد پس از ویرایش دلتای منفی")


# ==========================================
# F-D1 — delete_transaction برای رسیدهای target_wallet="both"
# (تست‌های failing-first طبق تسک؛ قبل از فیکس باید fail شوند)
# ==========================================
def assert_wallet_money_integer(db, student_id=101, context=""):
    """ستون‌های کیف باید در SQLite واقعاً integer باشند (بدون اعشار) — نسخه‌ی بدون وابستگی به ردیف تراکنش."""
    types = db.execute(
        text("SELECT typeof(wallet_teacher), typeof(wallet_institute), typeof(wallet_balance) "
             "FROM students WHERE id = :i"), {"i": student_id}
    ).fetchone()
    assert tuple(types) == ("integer",) * 3, f"{context}: نوع ستون‌های کیف باید integer باشد؛ شد {tuple(types)}"
    teacher, institute, balance = wallets(db, student_id)
    assert all(isinstance(v, int) for v in (teacher, institute, balance)), (
        f"{context}: مقادیر کیف باید int باشند؛ {teacher!r}/{institute!r}/{balance!r}"
    )


def delete_receipt(world, transaction_id):
    """حذف ادمین + assert خودکار invariant (سناریو ز)."""
    from routers import admin as admin_router

    result = admin_router.delete_transaction(transaction_id, db=world.db, _="admin")
    assert_wallet_invariant(world.db, context="بعد از حذف تراکنش")
    return result


def test_delete_both_receipt_returns_both_wallets_to_zero(world):
    """سناریوی اصلی F-D1: رسید both (مبلغ ۱۰۰، سهم ۴۰/۶۰) که کیف‌ها ۴۰/۶۰ شارژ شده‌اند؛
    حذف باید هر دو کیف را به صفر برگرداند و هیچ ردیف reversal تکراری نسازد.
    (سیاست پروژه برای delete = hard-delete — تصمیم H11.)"""
    legacy = credit_legacy_both_receipt(world)                 # کیف ۴۰/۶۰ | سهم ۴۰/۶۰
    assert_wallet_invariant(world.db, expected_teacher=40, expected_institute=60, expected_balance=100,
                            context="پیش از حذف رسید both")
    transaction_id = legacy.id

    delete_receipt(world, transaction_id)

    assert_wallet_invariant(world.db, expected_teacher=0, expected_institute=0, expected_balance=0,
                            context="پس از حذف رسید both")
    assert_wallet_money_integer(world.db, context="پس از حذف رسید both")
    # سیاست H11: ردیف hard-delete می‌شود و هیچ ردیف reversal جدیدی ساخته نمی‌شود
    assert world.db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first() is None
    assert world.db.query(models.Transaction).filter(models.Transaction.type == "reversal").count() == 0


def test_delete_both_receipt_unequal_shares(world):
    """سناریو الف: سهم‌های نامساوی (۳۰/۷۰) هم باید کامل برگردند."""
    legacy = credit_legacy_both_receipt(world, amount=100, share_teacher=30, share_institute=70)
    assert wallets(world.db) == (30, 70, 100)

    delete_receipt(world, legacy.id)
    assert_wallet_invariant(world.db, expected_teacher=0, expected_institute=0, expected_balance=0,
                            context="حذف رسید both با سهم نامساوی")


def test_delete_both_receipt_odd_amount(world):
    """سناریو ب: مبلغ فرد (۱۰۱ با سهم ۵۰/۵۱) هم باید بی‌اعشار و کامل برگردد."""
    legacy = credit_legacy_both_receipt(world, amount=101, share_teacher=50, share_institute=51)
    assert wallets(world.db) == (50, 51, 101)

    delete_receipt(world, legacy.id)
    assert_wallet_invariant(world.db, expected_teacher=0, expected_institute=0, expected_balance=0,
                            context="حذف رسید both با مبلغ فرد")
    assert_wallet_money_integer(world.db, context="حذف مبلغ فرد")


def test_delete_both_receipt_after_edit_reverses_final_amount(world):
    """سناریو ج: ویرایش ۱۰۰→۲۰۱ (سهم ۸۰/۱۲۱) و سپس حذف ⇒ اثر کامل مبلغ نهایی باید برگردد."""
    legacy = credit_legacy_both_receipt(world)                 # ۴۰/۶۰ از ۱۰۰
    edit_transaction(world, legacy.id, 201)
    assert_wallet_invariant(world.db, expected_teacher=80, expected_institute=121, expected_balance=201,
                            context="پس از ویرایش به ۲۰۱")
    world.db.expire_all()
    edited = world.db.get(models.Transaction, legacy.id)
    assert (edited.share_teacher, edited.share_institute) == (80, 121)

    delete_receipt(world, legacy.id)
    assert_wallet_invariant(world.db, expected_teacher=0, expected_institute=0, expected_balance=0,
                            context="حذف رسید both ویرایش‌شده")


def test_delete_both_receipt_twice_is_rejected_and_idempotent(world):
    """سناریو د: حذف تکراری باید ۴۰۴ بدهد و اثر مالی را دوباره برنگرداند."""
    from routers import admin as admin_router

    legacy = credit_legacy_both_receipt(world)
    delete_receipt(world, legacy.id)
    assert wallets(world.db) == (0, 0, 0)

    with pytest.raises(HTTPException) as error:
        admin_router.delete_transaction(legacy.id, db=world.db, _="admin")
    assert error.value.status_code == 404
    world.db.rollback()
    assert_wallet_invariant(world.db, expected_teacher=0, expected_institute=0, expected_balance=0,
                            context="حذف تکراری رسید both")


def test_delete_teacher_only_and_institute_only_behaviour_preserved(world):
    """سناریو هـ: حذف رسیدهای تک‌کیفی همان رفتار قبلی را دارد (فقط همان کیف برمی‌گردد)."""
    from routers import admin as admin_router

    teacher_receipt_id = pay(world, 100, wallet="teacher")["receipt_id"]
    admin_router.delete_transaction(teacher_receipt_id, db=world.db, _="admin")
    assert_wallet_invariant(world.db, expected_teacher=0, expected_institute=0, expected_balance=0,
                            context="حذف رسید teacher-only")

    institute_receipt_id = pay(world, 120, wallet="institute")["receipt_id"]
    admin_router.delete_transaction(institute_receipt_id, db=world.db, _="admin")
    assert_wallet_invariant(world.db, expected_teacher=0, expected_institute=0, expected_balance=0,
                            context="حذف رسید institute-only")
    assert_wallet_money_integer(world.db, context="حذف رسیدهای تک‌کیفی")


def test_delete_never_touches_already_deleted_or_reversed_rows(world):
    """سناریو و: ردیف deleted یا reversed نباید دوباره اثر مالی برگرداند (۴۰۴، کیف دست‌نخورده)."""
    from routers import admin as admin_router

    soft_deleted = credit_legacy_both_receipt(world)           # کیف ۴۰/۶۰ شارژ شد
    soft_deleted.is_deleted = True
    world.db.commit()

    reversed_row = receipt(world.db, amount=100, target_wallet="both",
                           share_teacher=40, share_institute=60, is_reversed=True)
    world.db.commit()

    for label, transaction_id in (("deleted", soft_deleted.id), ("reversed", reversed_row.id)):
        with pytest.raises(HTTPException) as error:
            admin_router.delete_transaction(transaction_id, db=world.db, _="admin")
        assert error.value.status_code == 404, f"ردیف {label} باید ۴۰۴ بدهد"
        world.db.rollback()
        assert_wallet_invariant(world.db, expected_teacher=40, expected_institute=60, expected_balance=100,
                                context=f"حذف ردیف {label}")
    assert world.db.query(models.Transaction).filter(models.Transaction.type == "reversal").count() == 0


def test_refund_after_delete_is_rejected_and_changes_nothing(world):
    """سناریو ح: بعد از hard-delete ردیف وجود ندارد ⇒ استرداد باید ۴۰۴ بدهد و کیف دست‌نخورده بماند."""
    legacy = credit_legacy_both_receipt(world)
    delete_receipt(world, legacy.id)
    assert wallets(world.db) == (0, 0, 0)

    with pytest.raises(HTTPException) as error:
        refund(world, legacy.id)
    assert error.value.status_code == 404, "استرداد تراکنش حذف‌شده باید ۴۰۴ (یافت نشد) بدهد"
    world.db.rollback()
    assert_wallet_invariant(world.db, expected_teacher=0, expected_institute=0, expected_balance=0,
                            context="استرداد بعد از حذف")


def test_refund_of_soft_deleted_both_receipt_is_rejected(world):
    """سناریو ح (تکمیل): رسید soft-deleted هنوز در DB هست ولی استرداد نباید آن را برگرداند (۴۰۴)."""
    legacy = credit_legacy_both_receipt(world)
    legacy.is_deleted = True
    world.db.commit()

    with pytest.raises(HTTPException) as error:
        refund(world, legacy.id)
    assert error.value.status_code == 404
    world.db.rollback()
    assert_wallet_invariant(world.db, expected_teacher=40, expected_institute=60, expected_balance=100,
                            context="استرداد ردیف soft-deleted")


def test_delete_both_matches_refund_for_identical_receipt(world):
    """هم‌راستایی با refund: دو رسید یکسان both ⇒ حذف یکی و استرداد دیگری باید **همان** مبالغ را برگردانند."""
    from routers import admin as admin_router

    first = credit_legacy_both_receipt(world, amount=101, share_teacher=50, share_institute=51)
    second = credit_legacy_both_receipt(world, amount=101, share_teacher=50, share_institute=51)
    assert wallets(world.db) == (100, 102, 202)

    admin_router.delete_transaction(first.id, db=world.db, _="admin")
    after_delete = wallets(world.db)
    assert after_delete == (50, 51, 101), (
        f"حذف باید دقیقاً سهم‌های رسید اول (۵۰/۵۱) را برگرداند؛ شد {after_delete}"
    )

    refund(world, second.id)
    assert wallets(world.db) == (0, 0, 0), "استرداد رسید دوم هم باید دقیقاً همان سهم‌ها را برگرداند"


def test_delete_both_receipt_without_shares_uses_documented_fallback(world):
    """F-D1 + fallback مستند: رسید both بدون سهم قبلی ⇒ همان قاعده‌ی refund (نصف-نصف، باقیمانده به آموزشگاه)."""
    legacy = receipt(world.db, amount=101, target_wallet="both", share_teacher=0, share_institute=0)
    world.db.query(models.Student).filter(models.Student.id == 101).update(
        {
            models.Student.wallet_teacher: func.coalesce(models.Student.wallet_teacher, 0) + 50,
            models.Student.wallet_institute: func.coalesce(models.Student.wallet_institute, 0) + 51,
        },
        synchronize_session=False,
    )
    world.db.commit()
    student = world.db.get(models.Student, 101)
    world.db.refresh(student)
    student.sync_wallet_balance()
    world.db.commit()
    assert wallets(world.db) == (50, 51, 101)

    delete_receipt(world, legacy.id)
    assert_wallet_invariant(world.db, expected_teacher=0, expected_institute=0, expected_balance=0,
                            context="حذف رسید both بدون سهم (fallback)")
    assert_wallet_money_integer(world.db, context="fallback رسید both")
