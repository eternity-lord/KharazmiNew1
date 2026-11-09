# FIX: Priority 2 regressions exercise real financial handlers, persisted rows, and concurrent connections.
import asyncio
import datetime
import io
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from openpyxl import load_workbook
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from dependencies import get_next_sequence_value, perform_delete_enrollment, reverse_session_financial_impacts
from financial_calculations import calculate_enrollment_debt, calculate_student_debt
from routers import admin, analytics, attendance, automation, classes, finance, reports
from schemas import AttendanceItem, AttendanceSubmitData, EnrollmentCreate, FinanceSubmitData, TransactionUpdate


# FIX: Bugs 13/14 - enable actual foreign-key enforcement so dangling audit links cannot pass tests.
def make_engine(url="sqlite:///:memory:", **kwargs):
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30}, **kwargs)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    models.Base.metadata.create_all(engine)
    return engine


# FIX: Priority 2 - isolated, valid accounting fixtures; no login/OTP/security implementation is mocked or changed.
def seed_finance(db):
    db.add_all([models.Branch(id=1, name="P2 North"), models.Branch(id=2, name="P2 South")])
    db.flush()
    user = models.User(id=1, username="p2-admin", password="unused", role="admin", sub_role="admin", branch_id=1)
    teacher = models.Teacher(id=1, teacher_code=101, first_name="Financial", last_name="Teacher", mobile="09120000101", branch_id=1)
    student = models.Student(
        id=101, student_code=100101, first_name="Financial", last_name="Student", national_code="P2-101",
        student_mobile="09121110101", parent_mobile="09122220101", branch_id=1,
        wallet_teacher=0, wallet_institute=0, wallet_balance=0,
    )
    db.add_all([user, teacher, student])
    db.flush()
    course = models.Course(
        id=1, title="P2 Math", code="P20001", teacher_id=teacher.id, branch_id=1,
        grade_level="دهم", teacher_session_price=70, is_admin_approved=True,
    )
    db.add(course)
    db.flush()
    enrollment = models.Enrollment(
        student_id=student.id, course_id=course.id, branch_id=1, total_tuition=1000, total_paid=200,
        register_date=datetime.date.today().strftime("%Y/%m/%d"),
    )
    db.add_all([
        enrollment,
        models.UserSession(token="p2-admin-token", user_id=user.id, sub_role="admin", created_at=datetime.datetime.now()),
        models.InstituteSettings(name="P2 School", address="Test", phone="021", card_number="1234"),
        models.PricingTable(category="high_school", count_1=70, count_2=140),
        models.PricingTable(category="institute", count_1=30, count_2=60),
        # FIX (audit-v2/test-call-repair): H5-canonical institute share (same 30/60 the old PricingTable row carried).
        models.InstituteShare(count_1=30, count_2=60),
    ])
    db.commit()
    return SimpleNamespace(db=db, user=user, teacher=teacher, student=student, course=course, enrollment=enrollment)


# FIX: Priority 2 - each handler test gets its own database and leaves no project data behind.
@pytest.fixture
def ledger():
    engine = make_engine(poolclass=StaticPool)
    with sessionmaker(bind=engine, expire_on_commit=False)() as db:
        yield seed_finance(db)
    models.Base.metadata.drop_all(engine)
    engine.dispose()


# FIX: Priority 2 - create receipts with explicit accounting associations and independently controlled flags.
def receipt(ledger, amount=100, **overrides):
    values = dict(
        student_id=ledger.student.id, enrollment_id=ledger.enrollment.id, course_id=ledger.course.id,
        branch_id=1, amount=amount, payment_method="نقدی", type="deposit", target_wallet="institute",
        date=datetime.date.today().strftime("%Y/%m/%d"), description="P2 receipt", share_teacher=40, share_institute=60,
    )
    values.update(overrides)
    transaction = models.Transaction(**values)
    ledger.db.add(transaction)
    ledger.db.flush()
    return transaction


# FIX: Bugs 9/10 - drive the real payment handler with the unchanged request schema.
def pay(ledger, amount=100, wallet="both", **overrides):
    values = dict(student_id=ledger.student.id, amount=amount, target_wallet=wallet, description="P2 payment", payment_method="نقدی", date="1405/06/16")
    values.update(overrides)
    return finance.submit_payment(FinanceSubmitData(**values), db=ledger.db, _="admin")


# FIX: Bug 9 - all five receipt creation branches, including split receipts, must persist the student's branch.
# FIX (audit-v2/test-triage): "legacy" عمداً 400 می‌گیرد (M12) و اپ هم ندارد — از پارام‌ها حذف شد.
@pytest.mark.parametrize("wallet", ["teacher", "institute", "both"])
def test_submit_payment_always_records_student_branch(ledger, wallet):
    result = pay(ledger, wallet=wallet)
    transactions = ledger.db.query(models.Transaction).all()
    assert transactions
    assert {transaction.id for transaction in transactions} == set(result["receipt_ids"])
    assert {transaction.branch_id for transaction in transactions} == {ledger.student.branch_id}


# FIX: Bug 9 - fallback uses the existing resolved branch when no student branch is assigned.
def test_submit_payment_uses_resolved_branch_and_student_precedence(ledger):
    ledger.student.branch_id = None
    ledger.user.branch_id = 2
    ledger.db.commit()
    data = FinanceSubmitData(student_id=ledger.student.id, amount=100, target_wallet="both", description="Fallback", payment_method="online", date="1405/06/16")
    finance.submit_payment(data, db=ledger.db, _="admin", branch_id=1, authorization="Bearer p2-admin-token")
    assert {t.branch_id for t in ledger.db.query(models.Transaction).all()} == {2}
    ledger.student.branch_id = 1
    ledger.db.commit()
    result = finance.submit_payment(data, db=ledger.db, _="admin", branch_id=2, authorization="Bearer p2-admin-token")
    assert {ledger.db.get(models.Transaction, tid).branch_id for tid in result["receipt_ids"]} == {1}


# FIX: Bug 10 - odd totals and the smallest positive unit must never disappear or all go to the teacher.
@pytest.mark.parametrize("amount", [1, 2, 99, 100, 101, 1000001])
def test_both_without_explicit_amounts_is_an_exact_half_split(ledger, amount):
    result = pay(ledger, amount=amount)
    assert result["new_balance_teacher"] == amount // 2
    assert result["new_balance_institute"] == amount - amount // 2
    assert ledger.student.wallet_balance == amount
    assert sum(t.amount for t in ledger.db.query(models.Transaction).all()) == amount


# FIX: Bug 10 - retain fully explicit shares, including a deliberately zero institute share.
@pytest.mark.parametrize("amount,teacher,institute,expected", [(100, 30, 70, (30, 70)), (60, 60, 40, (60, 40)), (100, 100, 0, (100, 0))])
def test_both_explicit_amounts_are_not_reinterpreted(ledger, amount, teacher, institute, expected):
    result = pay(ledger, amount=amount, amount_teacher=teacher, amount_institute=institute)
    assert (result["new_balance_teacher"], result["new_balance_institute"]) == expected
    assert ledger.student.wallet_balance == sum(expected)


# FIX: Bug 10 - invalid implicit amounts fail before changing wallets or allocating receipts.
@pytest.mark.parametrize("amount", [0, -1, -100])
def test_both_invalid_amount_has_no_financial_side_effects(ledger, amount):
    with pytest.raises(HTTPException) as error:
        pay(ledger, amount=amount)
    assert error.value.status_code == 400
    assert ledger.student.wallet_balance == 0
    assert ledger.db.query(models.Transaction).count() == 0
    assert ledger.db.query(models.SequenceCounter).count() == 0


# FIX: Bug 11 - call the real refund handler and verify new references, both rows, and preserved foreign keys.
def test_refund_new_reference_history_and_repeat_protection(ledger):
    session = models.SessionLog(course_id=ledger.course.id, date="1405/06/15", session_code=200001)
    ledger.db.add(session)
    ledger.db.flush()
    original = receipt(ledger, remittance_number=100003, session_id=session.id)
    archived = receipt(ledger, amount=10, remittance_number=100004, is_deleted=True)
    ledger.student.wallet_institute = 100
    ledger.student.wallet_balance = 100
    ledger.db.commit()
    result = finance.refund_transaction(original.id, db=ledger.db, _="admin")
    ledger.db.refresh(original)  # FIX (audit-v2/test-triage): refund با bulk می‌نویسد (کامنت خود سرور).
    reversal = ledger.db.get(models.Transaction, result["refund_transaction_id"])
    assert original.is_reversed and not original.is_deleted
    assert reversal.type == "reversal" and reversal.amount == -100
    assert reversal.remittance_number not in {original.remittance_number, archived.remittance_number}
    assert (reversal.branch_id, reversal.enrollment_id, reversal.course_id, reversal.session_id) == (1, ledger.enrollment.id, ledger.course.id, session.id)
    assert ledger.student.wallet_institute == ledger.student.wallet_balance == 0
    assert ledger.db.query(models.Transaction).count() == 3
    with pytest.raises(HTTPException) as error:
        finance.refund_transaction(original.id, db=ledger.db, _="admin")
    assert error.value.status_code == 400
    assert ledger.db.query(models.Transaction).count() == 3
    assert ledger.student.wallet_balance == 0
    assert ledger.db.execute(text("PRAGMA foreign_key_check")).all() == []


# FIX: Bug 11 - an existing, behind-the-ledger counter must also skip historical references.
def test_refund_existing_counter_cannot_reuse_historical_numbers(ledger):
    ledger.db.add(models.SequenceCounter(name="remittance_institute", current_value=100000))
    original = receipt(ledger, remittance_number=100001)
    receipt(ledger, amount=1, remittance_number=100002, is_reversed=True)
    ledger.db.commit()
    result = finance.refund_transaction(original.id, db=ledger.db, _="admin")
    assert ledger.db.get(models.Transaction, result["refund_transaction_id"]).remittance_number == 100003


# FIX: Bugs 10/11 - refunds of legacy combined receipts undo the same shares that were credited.
@pytest.mark.parametrize("shares,expected", [((30, 71), (30, 71)), ((0, 0), (50, 51))])
def test_refund_both_restores_both_wallets(ledger, shares, expected):
    original = receipt(ledger, amount=101, target_wallet="both", share_teacher=shares[0], share_institute=shares[1], remittance_number=100001)
    ledger.student.wallet_teacher, ledger.student.wallet_institute = expected
    ledger.student.wallet_balance = 101
    ledger.db.commit()
    finance.refund_transaction(original.id, db=ledger.db, _="admin")
    assert (ledger.student.wallet_teacher, ledger.student.wallet_institute, ledger.student.wallet_balance) == (0, 0, 0)


# FIX: Bug 12 - cover all six payment-method/wallet sums and both flags, including both flags together.
@pytest.mark.parametrize("method,key", [("نقدی", "cash"), ("کارت به کارت", "card"), ("online", "online")])
@pytest.mark.parametrize("wallet", ["teacher", "institute"])
@pytest.mark.parametrize("deleted,reversed_", [(True, False), (False, True), (True, True)])
def test_revenue_breakdown_excludes_every_inactive_combination(ledger, method, key, wallet, deleted, reversed_):
    receipt(ledger, payment_method=method, target_wallet=wallet)
    receipt(ledger, amount=900, payment_method=method, target_wallet=wallet, is_deleted=deleted, is_reversed=reversed_)
    ledger.db.commit()
    result = finance.get_revenue_summary(db=ledger.db, _="admin")
    assert result["revenue_by_wallet"][wallet + "_wallet"][key] == 100
    assert result["totals"]["total_revenue"] == 100


# FIX: Bug 12 - refund totals must not include archived or themselves reversed reversal records.
def test_refund_summary_filters_both_flags(ledger):
    receipt(ledger, amount=-7, type="reversal")
    receipt(ledger, amount=-90, type="reversal", is_deleted=True)
    receipt(ledger, amount=-80, type="reversal", is_reversed=True)
    ledger.db.commit()
    totals = finance.get_revenue_summary(db=ledger.db, _="admin")["totals"]
    assert totals["refund_count"] == 1
    assert totals["refund_total_amount"] == 7


# FIX: Bug 12 - validate actual admin/finance/report/analytics reads against the same mixed-status ledger.
def test_financial_reads_share_active_transaction_filters(ledger):
    good = receipt(ledger)
    receipt(ledger, amount=900, is_deleted=True)
    receipt(ledger, amount=800, is_reversed=True)
    # منبع حقیقت واحد: واریزی لینک‌شده سالم در total_paid منعکس است (حذف‌شده/برگشتی هرگز شمرده نمی‌شوند)
    ledger.enrollment.total_paid = 100
    ledger.db.commit()
    auth = "Bearer p2-admin-token"
    assert [t["id"] for t in admin.get_all_transactions(db=ledger.db, _="admin")] == [good.id]
    assert admin.get_dashboard_stats(db=ledger.db, _="admin")["last_transaction"]["amount"] == 100
    profile = admin.get_student_full_profile(ledger.student.id, authorization=auth, db=ledger.db, role="admin")
    assert len(profile["transactions"]) == 1
    assert profile["total_paid_institute"] == 100
    report = reports.get_financial_report(authorization=auth, db=ledger.db, _="admin")
    assert [row["amount"] for row in report] == [100]
    assert [row["id"] for row in finance.get_student_physical_transactions(ledger.student.id, authorization=auth, db=ledger.db, _role="admin")] == [good.id]
    dashboard = finance.get_student_financial_dashboard(ledger.student.id, authorization=auth, db=ledger.db, _role="admin")
    assert [row["id"] for row in dashboard["recent_transactions"]] == [good.id]
    assert dashboard["enrollments"][0]["total_paid"] == 100
    assert finance.get_invoice_details(ledger.enrollment.id, authorization=auth, db=ledger.db, _role="admin")["total_paid"] == 100
    status = finance.get_student_class_status(ledger.student.id, course_id=ledger.course.id, db=ledger.db, authorization=auth, sub_role="admin")
    assert status["paid_to_institute"] == 100
    assert reports.get_student_statement(ledger.student.id, db=ledger.db, authorization=auth, role="admin")["total_paid_institute"] == 100
    chart = reports.get_chart_data(authorization=auth, db=ledger.db, _="admin")
    assert chart["income_chart"][-1]["amount"] == 100
    assert chart["shares_chart"] == {"teacher": 40, "institute": 60}
    stats = analytics.get_analytics_dashboard(authorization=auth, db=ledger.db, _="admin")
    assert stats["total_turnover"] == 100
    from today_summary import gregorian_to_jalali  # FIX (audit-v2/test-triage): گزارش شمسی‌کانونیکال؛ پارام میلادی بازه‌ی ناممکن می‌ساخت (…/09/31).
    jy, jm, _ = gregorian_to_jalali(datetime.date.today())
    summary = reports.get_financial_summary(user_type="institute", year=jy, month=jm, authorization=auth, db=ledger.db, sub_role="admin")
    assert summary["monthly"]["collected"] == 100


# FIX: Bug 12 - receipt lookups cannot expose inactive financial rows as valid current receipts.
@pytest.mark.parametrize("flag", ["is_deleted", "is_reversed"])
@pytest.mark.parametrize("handler", ["print_receipt", "generate_pdf_receipt", "get_receipt_details", "delete_transaction", "update_transaction"])
def test_inactive_receipts_are_not_printed_or_modified(ledger, flag, handler):
    transaction = receipt(ledger, **{flag: True})
    ledger.db.commit()
    with pytest.raises(HTTPException) as error:
        if handler in {"print_receipt", "generate_pdf_receipt"}:
            getattr(finance, handler)(finance.PrintReceiptRequest(transaction_id=transaction.id, print_type="pdf"), db=ledger.db, _="admin")
        elif handler == "get_receipt_details":
            finance.get_receipt_details(transaction.id, authorization="Bearer p2-admin-token", db=ledger.db, _role="admin")
        elif handler == "delete_transaction":
            admin.delete_transaction(transaction.id, db=ledger.db, _="admin")
        else:
            admin.update_transaction(transaction.id, TransactionUpdate(amount=1, description="Must not change", date="1405/06/16"), db=ledger.db, _="admin")
    assert error.value.status_code == 404
    assert ledger.db.get(models.Transaction, transaction.id).amount == 100


# FIX: Bug 12 - Excel exports must obey the same active-ledger policy as JSON responses.
def test_transaction_excel_excludes_inactive_amounts(ledger):
    receipt(ledger)
    receipt(ledger, amount=900, is_deleted=True)
    receipt(ledger, amount=800, is_reversed=True)
    ledger.db.commit()
    response = admin.get_transactions_excel(db=ledger.db, _="admin")

    async def collect():
        return b"".join([chunk async for chunk in response.body_iterator])

    workbook = load_workbook(io.BytesIO(asyncio.run(collect())), data_only=True)
    values = [cell for row in workbook.active.values for cell in row]
    assert 100 in values
    assert 900 not in values and 800 not in values


# FIX: Bug 13 - cancel only this enrollment and retain all audit links.
# تصمیم محصولی: وجه واقعی نزد شاگرد می‌ماند (اعتبار)؛ فقط شارژ جلسات مصرفی برمی‌گردد.
def test_delete_enrollment_preserves_links_installments_and_other_enrollment(ledger):
    other = models.Enrollment(student_id=ledger.student.id, course_id=ledger.course.id, total_tuition=200)
    ledger.db.add(other)
    ledger.db.flush()
    deposit = receipt(ledger, amount=101, target_wallet="both", share_teacher=30, share_institute=71)
    charge = receipt(ledger, amount=-50, type="session_charge", share_teacher=20, share_institute=30)
    unrelated = receipt(ledger, amount=20, enrollment_id=other.id, target_wallet="teacher")
    inactive = receipt(ledger, amount=-1000, type="session_charge", share_teacher=500, share_institute=500, is_reversed=True)
    paid = models.Installment(enrollment_id=ledger.enrollment.id, amount=50, due_date="1405/01/01", is_paid=True, paid_at="1405/01/01")
    unpaid = models.Installment(enrollment_id=ledger.enrollment.id, amount=50, due_date="1405/01/02", is_paid=False)
    ledger.db.add_all([paid, unpaid])
    ledger.student.wallet_teacher, ledger.student.wallet_institute, ledger.student.wallet_balance = 30, 41, 71
    ledger.db.commit()
    perform_delete_enrollment(ledger.enrollment, ledger.db)
    ledger.db.commit()
    ledger.db.refresh(charge); ledger.db.refresh(deposit)  # FIX (audit-v2/test-triage): bulk بدون sync.
    assert ledger.enrollment.is_deleted and not other.is_deleted
    assert ledger.db.get(models.Enrollment, ledger.enrollment.id) is not None
    for transaction in (deposit, charge, inactive):
        assert transaction.enrollment_id == ledger.enrollment.id
        assert transaction.course_id == ledger.course.id
    assert not deposit.is_deleted and charge.is_deleted
    assert not unrelated.is_deleted and inactive.is_reversed
    assert paid.is_deleted and unpaid.is_deleted
    assert paid.is_paid and paid.paid_at == "1405/01/01"
    assert not unpaid.is_paid and unpaid.paid_at is None
    # شروع (30, 41, 71): واریزی دست نمی‌خورد؛ فقط شارژ جلسه (+20/+30) برمی‌گردد
    assert (ledger.student.wallet_teacher, ledger.student.wallet_institute, ledger.student.wallet_balance) == (50, 71, 121)
    perform_delete_enrollment(ledger.enrollment, ledger.db)
    ledger.db.commit()
    assert ledger.student.wallet_balance == 121
    assert ledger.db.execute(text("PRAGMA foreign_key_check")).all() == []


# FIX: Bug 13 - legacy course-linked transactions without enrollment_id keep their course.
# تصمیم محصولی: وجه واقعی نزد شاگرد می‌ماند (اعتبار) و سابقه فعال می‌ماند.
def test_delete_enrollment_handles_legacy_course_receipts(ledger):
    transaction = receipt(ledger, amount=101, enrollment_id=None, target_wallet="both", share_teacher=0, share_institute=0)
    ledger.student.wallet_teacher, ledger.student.wallet_institute, ledger.student.wallet_balance = 50, 51, 101
    ledger.db.commit()
    perform_delete_enrollment(ledger.enrollment, ledger.db)
    ledger.db.commit()
    assert transaction.enrollment_id is None and transaction.course_id == ledger.course.id
    assert not transaction.is_deleted
    assert ledger.student.wallet_balance == 101


# FIX: Bug 13 - cancellation must close collection/reminder paths, not just set an unused database flag.
def test_cancelled_installments_cannot_be_collected_or_reminded(ledger):
    installment = models.Installment(enrollment_id=ledger.enrollment.id, amount=100, due_date="1400/01/01")
    ledger.db.add(installment)
    ledger.db.commit()
    perform_delete_enrollment(ledger.enrollment, ledger.db)
    ledger.db.commit()
    assert finance.get_all_installments(student_id=ledger.student.id, db=ledger.db, authorization="Bearer p2-admin-token", sub_role="admin") == []
    assert finance.get_student_financial_dashboard(ledger.student.id, authorization="Bearer p2-admin-token", db=ledger.db, _role="admin")["installments"] == []
    with pytest.raises(HTTPException) as error:
        finance.create_installment(finance.InstallmentCreateRequest(enrollment_id=ledger.enrollment.id, amount=1, due_date="1405/06/16"), db=ledger.db, _="admin")
    assert error.value.status_code == 404
    for handler in (finance.pay_installment_manually, finance.send_installment_payment_reminder):
        with pytest.raises(HTTPException) as error:
            handler(installment.id, db=ledger.db, _="admin")
        assert error.value.status_code == 404
    pay(ledger, amount=100, wallet="teacher")
    assert installment.is_deleted and not installment.is_paid
    ledger.db.add(models.AutomationRule(name="P2 overdue", condition_type="installment_overdue", action_type="parent_notification", active=True))
    ledger.db.commit()
    automation.run_automation_engine(db=ledger.db, _="admin")
    assert ledger.db.query(models.AutomationLog).count() == 0


# FIX: Bug 13 - a cancelled historical enrollment must not prevent registering the student again.
def test_cancelled_enrollment_allows_new_registration(ledger):
    old_id = ledger.enrollment.id
    classes.delete_enrollment(old_id, db=ledger.db, _="admin")
    request = EnrollmentCreate(student_id=ledger.student.id, course_id=ledger.course.id, register_date="1405/06/16", shift="عصر", total_tuition=1000, paid_amount=0, payment_method="نقدی", receiver="admin")
    result = classes.add_enrollment(request, db=ledger.db, sub_role="admin")
    assert result["enrollment_id"] != old_id
    assert ledger.db.get(models.Enrollment, old_id).is_deleted
    assert not ledger.db.get(models.Enrollment, result["enrollment_id"]).is_deleted


# FIX: Bugs 14/17 - drive billing with a real attendance request rather than a copy of its accounting code.
def submit_session(ledger, date="1405/06/16", course_id=None):
    request = AttendanceSubmitData(course_id=course_id or ledger.course.id, date=date, items=[AttendanceItem(student_id=ledger.student.id, status="Present")])
    return attendance.submit_session_and_calculate(request, db=ledger.db, authorization="Bearer p2-admin-token", sub_role="admin")


# FIX: Bug 14 - reversal retains rows and links, credits once, and ignores already deleted/reversed charges.
def test_session_reversal_is_soft_and_idempotent(ledger):
    result = submit_session(ledger)
    transaction = ledger.db.query(models.Transaction).one()
    assert ledger.student.wallet_balance == -100
    inactive = receipt(ledger, amount=-900, type="session_charge", session_id=result["session_id"], is_reversed=True, share_teacher=500, share_institute=400)
    ledger.db.commit()
    reverse_session_financial_impacts(result["session_id"], ledger.db)
    ledger.db.refresh(transaction)  # FIX (audit-v2/test-call-repair): B1/B2 به‌روزرسانی bulk بدون sync است؛ آبجکتِ نگه‌داشته‌شده stale می‌ماند.
    assert ledger.student.wallet_balance == 0
    assert transaction.is_deleted and transaction.session_id == result["session_id"]
    assert transaction.course_id == ledger.course.id and inactive.is_reversed
    assert ledger.db.query(models.Transaction).count() == 2
    reverse_session_financial_impacts(result["session_id"], ledger.db)
    assert ledger.student.wallet_balance == 0
    assert ledger.db.execute(text("PRAGMA foreign_key_check")).all() == []


# FIX: Bug 14 - deleting the parent session must not break the preserved financial foreign keys.
def test_delete_session_keeps_parent_and_can_rebill_cancelled_date(ledger):
    first = submit_session(ledger)
    attendance.delete_session_endpoint(first["session_code"], db=ledger.db, _="admin")
    archived = ledger.db.get(models.SessionLog, first["session_id"])
    assert archived.is_deleted
    assert ledger.student.wallet_balance == 0
    assert ledger.db.query(models.Transaction).one().is_deleted
    second = submit_session(ledger)
    assert second["session_id"] != first["session_id"]
    assert ledger.student.wallet_balance == -100
    assert ledger.db.query(models.Transaction).filter(models.Transaction.is_deleted == False).count() == 1
    assert ledger.db.execute(text("PRAGMA foreign_key_check")).all() == []


# FIX: Bug 17 - a repeated course/date fails before another code, session, receipt, or wallet deduction.
def test_duplicate_session_is_rejected_before_financial_changes(ledger):
    first = submit_session(ledger)
    previous_wallets = (ledger.student.wallet_teacher, ledger.student.wallet_institute, ledger.student.wallet_balance)
    previous_sequence = ledger.db.query(models.SequenceCounter).filter_by(name="session").one().current_value
    with pytest.raises(HTTPException) as error:
        submit_session(ledger)
    assert error.value.status_code == 409
    assert (ledger.student.wallet_teacher, ledger.student.wallet_institute, ledger.student.wallet_balance) == previous_wallets
    assert ledger.db.query(models.SessionLog).count() == 1
    assert ledger.db.query(models.Transaction).count() == 1
    assert ledger.db.query(models.Attendance).count() == 1
    assert ledger.db.query(models.SequenceCounter).filter_by(name="session").one().current_value == previous_sequence
    assert first["session_id"] == ledger.db.query(models.SessionLog).one().id


# FIX: Bug 17 - the database constraint protects direct/racing writers as well as the handler pre-check.
def test_duplicate_session_has_database_enforcement(ledger):
    submit_session(ledger)
    ledger.db.add(models.SessionLog(course_id=ledger.course.id, date="1405/06/16", session_code=999999))
    with pytest.raises(IntegrityError):
        ledger.db.commit()
    ledger.db.rollback()
    assert ledger.db.query(models.SessionLog).count() == 1
    assert ledger.student.wallet_balance == -100


# FIX: Bug 17 - distinct dates remain valid; duplicate prevention must not suppress legitimate sessions.
def test_distinct_session_dates_remain_billable(ledger):
    first = submit_session(ledger, date="1405/06/16")
    second = submit_session(ledger, date="1405/06/17")
    assert first["session_id"] != second["session_id"]
    assert ledger.student.wallet_balance == -200


# FIX: Bug 16 - prioritize discounted tuition minus recorded payments, regardless of either wallet's sign.
@pytest.mark.parametrize("wallets,tuition,paid,discount_type,discount_value,expected", [
    ((0, 0), 1000, 200, "none", 0, 800),
    ((5000, 3000), 1000, 200, "percentage", 10, 700),
    ((-9000, -8000), 1000, 1000, "none", 0, 0),
    ((0, 0), 1000, 200, "fixed", 300, 500),
    ((0, 0), 1000, 1500, "none", 0, 0),
    ((-40, -60), 1000, 0, "percentage", 100, 0),
])
def test_tuition_debt_ignores_wallet_sign(ledger, wallets, tuition, paid, discount_type, discount_value, expected):
    ledger.student.wallet_teacher, ledger.student.wallet_institute = wallets
    ledger.enrollment.total_tuition, ledger.enrollment.total_paid = tuition, paid
    ledger.enrollment.discount_type, ledger.enrollment.discount_value = discount_type, discount_value
    ledger.db.commit()
    assert calculate_enrollment_debt(ledger.enrollment) == expected
    assert calculate_student_debt(ledger.db, ledger.student) == expected
    listed = finance.get_debtors_list(db=ledger.db, authorization="Bearer p2-admin-token", _="admin")
    assert [row["total_debt"] for row in listed] == ([expected] if expected else [])
    reported = reports.get_debtors_report(db=ledger.db, authorization="Bearer p2-admin-token", _="admin")
    assert [row["amount"] for row in reported] == ([expected] if expected else [])
    assert analytics.get_analytics_dashboard(db=ledger.db, authorization="Bearer p2-admin-token", _="admin")["outstanding_debt"] == expected
    assert finance.get_student_financial_dashboard(ledger.student.id, db=ledger.db, authorization="Bearer p2-admin-token", _role="admin")["wallet"]["total_debt"] == expected


# FIX: Bug 16 - a credit in another enrollment must not erase an unpaid contractual obligation.
def test_tuition_debt_does_not_net_overpayment_against_other_enrollment(ledger):
    other = models.Enrollment(student_id=ledger.student.id, course_id=ledger.course.id, total_tuition=1000, total_paid=3000)
    ledger.db.add(other)
    ledger.db.commit()
    assert calculate_student_debt(ledger.db, ledger.student) == 800
    ledger.enrollment.is_deleted = True
    other.is_deleted = True
    ledger.student.wallet_teacher = -9999
    ledger.db.commit()
    assert calculate_student_debt(ledger.db, ledger.student) == 0


# FIX: Bug 16 - preserve genuinely unpriced legacy session billing instead of discarding existing debts.
def test_legacy_unpriced_enrollment_keeps_wallet_fallback(ledger):
    ledger.enrollment.total_tuition = 0
    ledger.student.wallet_teacher, ledger.student.wallet_institute = -40, 100
    ledger.db.commit()
    assert calculate_student_debt(ledger.db, ledger.student) == 40


# FIX: Bug 16 - debt queries still respect the branch resolver after removing the wallet-only SQL predicate.
def test_tuition_debt_keeps_branch_filter(ledger):
    second = models.Student(first_name="Other", last_name="Branch", branch_id=2, student_mobile="09121110202")
    ledger.db.add(second)
    ledger.db.flush()
    ledger.db.add(models.Enrollment(student_id=second.id, course_id=ledger.course.id, branch_id=2, total_tuition=5000, total_paid=0))
    ledger.db.commit()
    result = finance.get_debtors_list(branch_id=1, authorization=None, db=ledger.db, _="admin")
    assert [row["student_id"] for row in result] == [ledger.student.id]
    assert analytics.get_analytics_dashboard(branch_id=1, authorization=None, db=ledger.db, _="admin")["outstanding_debt"] == 800


# FIX: Bug 15 - initial allocation and increments remain transactional, including caller rollbacks.
def test_sequence_allocation_respects_rollback(ledger):
    assert get_next_sequence_value(ledger.db, "p2-first", 100) == 100
    ledger.db.rollback()
    assert ledger.db.query(models.SequenceCounter).filter_by(name="p2-first").count() == 0
    assert get_next_sequence_value(ledger.db, "p2-first", 100) == 100
    ledger.db.commit()
    counter = ledger.db.query(models.SequenceCounter).filter_by(name="p2-first").one()
    assert get_next_sequence_value(ledger.db, "p2-first", 100) == 101
    assert counter.current_value == 101
    ledger.db.rollback()
    assert counter.current_value == 100
    assert get_next_sequence_value(ledger.db, "p2-other", 500) == 500


# FIX: Bug 15 - exercise the unique-name collision/savepoint path without rolling back the caller's work.
def test_sequence_insert_collision_keeps_outer_transaction(ledger, monkeypatch):
    ledger.db.add(models.SequenceCounter(name="p2-collision", current_value=50))
    ledger.db.commit()
    execute = ledger.db.execute
    first = True

    def simulate_racing_first_update(statement, *args, **kwargs):
        nonlocal first
        if first and getattr(statement, "is_update", False):
            first = False
            return SimpleNamespace(scalar_one_or_none=lambda: None)
        return execute(statement, *args, **kwargs)

    monkeypatch.setattr(ledger.db, "execute", simulate_racing_first_update)
    ledger.student.first_name = "Outer transaction retained"
    assert get_next_sequence_value(ledger.db, "p2-collision", 50) == 51
    ledger.db.commit()
    assert ledger.student.first_name == "Outer transaction retained"
    assert ledger.db.query(models.SequenceCounter).filter_by(name="p2-collision").count() == 1


# FIX: Bug 15 - use real simultaneous sessions/connections against a database with no counter row.
def test_concurrent_first_sequence_allocation_is_unique(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'sequence-race.sqlite'}")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    barrier = Barrier(8)

    def allocate():
        barrier.wait(timeout=15)
        values = []
        for _ in range(10):
            with factory() as db:
                values.append(get_next_sequence_value(db, "p2-race", 100001))
                db.commit()
        return values

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: allocate(), range(8)))
    values = [value for group in results for value in group]
    assert sorted(values) == list(range(100001, 100081))
    with factory() as db:
        assert db.query(models.SequenceCounter).filter_by(name="p2-race").one().current_value == 100080
    engine.dispose()


# FIX: Bug 17 - simultaneous submissions must produce one charge and one clear duplicate response.
def test_concurrent_session_submission_charges_once(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'session-race.sqlite'}")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        seed_finance(db)
    barrier = Barrier(2)

    def submit():
        with factory() as db:
            barrier.wait(timeout=15)
            data = AttendanceSubmitData(course_id=1, date="1405/06/16", items=[AttendanceItem(student_id=101, status="Present")])
            try:
                attendance.submit_session_and_calculate(data, db=db, authorization="Bearer p2-admin-token", sub_role="admin")
                return 200
            except HTTPException as error:
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: submit(), range(2)))
    assert sorted(statuses) == [200, 409]
    with factory() as db:
        assert db.query(models.SessionLog).count() == 1
        assert db.query(models.Transaction).count() == 1
        assert db.get(models.Student, 101).wallet_balance == -100
    engine.dispose()


# FIX: Bugs 13/14/17 - prove existing databases receive soft-delete columns and the active-session unique index.
def test_financial_schema_upgrade_preserves_existing_rows(ledger, monkeypatch):
    import main
    ledger.db.commit()
    engine = ledger.db.get_bind()
    with engine.begin() as connection:
        connection.execute(text("DROP INDEX uq_session_course_date_active"))
        for table in ("enrollments", "installments", "session_logs"):
            connection.execute(text(f"ALTER TABLE {table} DROP COLUMN is_deleted"))
    monkeypatch.setattr(models, "engine", engine)
    monkeypatch.setattr(models, "SessionLocal", sessionmaker(bind=engine))
    main.auto_patch_database()
    main.auto_patch_database()
    ledger.db.expire_all()
    assert ledger.db.get(models.Enrollment, ledger.enrollment.id).total_tuition == 1000
    assert ledger.db.get(models.Enrollment, ledger.enrollment.id).is_deleted is False
    for table in ("enrollments", "installments", "session_logs"):
        columns = ledger.db.execute(text(f"PRAGMA table_info({table})")).all()
        assert sum(row[1] == "is_deleted" for row in columns) == 1
    indexes = ledger.db.execute(text("PRAGMA index_list(session_logs)")).all()
    assert any(row[1] == "uq_session_course_date_active" and row[2] == 1 for row in indexes)


# FIX: Bug 9 - missing branch metadata must reject, never silently persist a branchless receipt.
def test_payment_without_any_resolvable_branch_is_rejected(ledger):
    ledger.student.branch_id = None
    ledger.user.branch_id = None
    ledger.db.commit()
    with pytest.raises(HTTPException) as error:
        pay(ledger, amount=100, wallet="teacher")
    assert error.value.status_code == 400
    assert "شعبه" in error.value.detail
    assert ledger.db.query(models.Transaction).count() == 0
    assert ledger.student.wallet_balance == 0


# FIX: Bugs 13/16 - cancelled priced history must not suppress genuinely active, unpriced session debt.
def test_active_legacy_debt_survives_archived_priced_enrollment(ledger):
    ledger.enrollment.is_deleted = True
    ledger.db.add(models.Enrollment(student_id=ledger.student.id, course_id=ledger.course.id, total_tuition=0))
    ledger.student.wallet_teacher = -40
    ledger.db.commit()
    assert calculate_student_debt(ledger.db, ledger.student) == 40


# FIX: Bug 16 - the statement's combined tuition debt is distinct from an individual wallet deficit.
def test_statement_does_not_misassign_combined_tuition_to_institute_wallet(ledger):
    ledger.student.wallet_teacher = -30
    ledger.student.wallet_institute = -20
    ledger.db.commit()
    statement = reports.get_student_statement(ledger.student.id, db=ledger.db, authorization="Bearer p2-admin-token", role="admin")
    assert statement["total_debt"] == 800
    assert statement["total_debt_institute"] == 20


# FIX: Bug 14 - editing a session replaces its active charge, but retains the original transaction history.
def test_edit_session_keeps_archived_charge_without_double_deduction(ledger):
    first = submit_session(ledger)
    original = ledger.db.query(models.Transaction).one()
    request = AttendanceSubmitData(course_id=ledger.course.id, date="1405/06/16", items=[AttendanceItem(student_id=ledger.student.id, status="Present")])
    attendance.edit_past_session(first["session_code"], request, db=ledger.db, authorization="Bearer p2-admin-token", sub_role="admin")
    ledger.db.refresh(original)  # FIX (audit-v2/test-call-repair): مثل بالا — reverse/edit با bulk بایگانی می‌کنند.
    assert original.is_deleted and original.session_id == first["session_id"]
    assert ledger.db.query(models.Transaction).count() == 2
    assert ledger.db.query(models.Transaction).filter(models.Transaction.is_deleted == False, models.Transaction.is_reversed == False).count() == 1
    assert ledger.student.wallet_balance == -100
    assert ledger.db.execute(text("PRAGMA foreign_key_check")).all() == []


# FIX: Bug 14 - retaining a cancelled session must not make it eligible for another teacher settlement.
def test_cancelled_session_cannot_be_settled(ledger):
    from routers.teachers import get_pending_settlement, settle_teacher_sessions
    from schemas import SettleRequest
    first = submit_session(ledger)
    assert get_pending_settlement(ledger.teacher.id, db=ledger.db, authorization="Bearer p2-admin-token", sub_role="admin")["total_amount"] == 70
    attendance.delete_session_endpoint(first["session_code"], db=ledger.db, _="admin")
    assert get_pending_settlement(ledger.teacher.id, db=ledger.db, authorization="Bearer p2-admin-token", sub_role="admin")["total_amount"] == 0
    with pytest.raises(HTTPException) as error:
        settle_teacher_sessions(ledger.teacher.id, SettleRequest(session_ids=[first["session_id"]]), db=ledger.db, admin_sub_role="admin")
    assert error.value.status_code == 400
    assert ledger.db.query(models.Settlement).count() == 0


# FIX: Bug 10 - partially omitted shares are ambiguous and must not silently credit only the teacher.
@pytest.mark.parametrize("teacher,institute", [(None, 40), (100, None), (None, 0), (0, None)])
def test_both_partial_split_is_rejected_without_posting(ledger, teacher, institute):
    with pytest.raises(HTTPException) as error:
        pay(ledger, amount=100, amount_teacher=teacher, amount_institute=institute)
    assert error.value.status_code == 400
    assert "هر دو" in error.value.detail
    assert ledger.student.wallet_balance == 0
    assert ledger.db.query(models.Transaction).count() == 0


# FIX: Bug 11 - a separate refund counter would allow the next same-wallet deposit to reuse its number.
@pytest.mark.parametrize("wallet", ["teacher", "institute"])
def test_refund_and_later_deposit_share_unique_wallet_references(ledger, wallet):
    first = pay(ledger, amount=100, wallet=wallet)
    refund = finance.refund_transaction(first["receipt_ids"][0], db=ledger.db, _="admin")
    second = pay(ledger, amount=100, wallet=wallet)
    ids = [first["receipt_ids"][0], refund["refund_transaction_id"], second["receipt_ids"][0]]
    references = [ledger.db.get(models.Transaction, transaction_id).remittance_number for transaction_id in ids]
    assert len(set(references)) == 3
    assert references == sorted(references)

