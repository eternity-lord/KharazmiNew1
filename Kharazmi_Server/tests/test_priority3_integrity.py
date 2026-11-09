# FIX: Priority 3 regression tests use real models, validators, HTTP routes and persisted wallet values.
import datetime

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import text

import models
import schemas
from dependencies import get_db, perform_delete_enrollment
from main import app
from routers import admin, classes, crm, finance, homework
from test_priority2_financial import ledger, pay
from validation import is_valid_iranian_national_code, validate_iranian_national_code


# FIX: Bug 22 - supply valid, synthetic identity input without bypassing any validators.
def identity_payload(model, national_code="0012345679"):
    values = {}
    for name, field in model.model_fields.items():
        if field.is_required():
            values[name] = 1 if field.annotation is int else "test"
    values["national_code"] = national_code
    return values


# FIX: Bug 18 - the helper treats null components as zero and is the only total formula.
@pytest.mark.parametrize("teacher,institute,total", [
    (None, None, 0), (None, 50, 50), (-20, None, -20),
    (-50, 100, 50), (10, -30, -20), (0, 0, 0), (10**12, 10**12, 2 * 10**12),
])
def test_wallet_total_uses_components(teacher, institute, total):
    student = models.Student(wallet_teacher=teacher, wallet_institute=institute, wallet_balance=999)
    assert student.sync_wallet_balance() == total
    assert student.wallet_balance == total


# FIX: Bug 18 - callers cannot persist a stale cached total through ordinary ORM writes.
def test_wallet_total_is_synchronized_on_insert_and_update(ledger):
    student = models.Student(national_code="P3-model-only", wallet_teacher=12, wallet_institute=-3, wallet_balance=900)
    ledger.db.add(student)
    ledger.db.commit()
    assert ledger.db.execute(text("SELECT wallet_balance FROM students WHERE id=:id"), {"id": student.id}).scalar_one() == 9
    student.wallet_institute = 30
    student.wallet_balance = -999
    ledger.db.commit()
    ledger.db.expire(student)
    assert (student.wallet_teacher, student.wallet_institute, student.wallet_balance) == (12, 30, 42)


# FIX: Bug 18 - registering with a payment must not lose it when the aggregate is recalculated.
def test_initial_enrollment_credit_uses_component_and_remains_reversible(ledger):
    ledger.enrollment.is_deleted = True
    ledger.db.commit()
    request = schemas.EnrollmentCreate(
        student_id=ledger.student.id, course_id=ledger.course.id,
        register_date="1405/06/15", shift="عصر", total_tuition=100,
        paid_amount=100, payment_method="نقدی", receiver="آموزشگاه",
    )
    result = classes.add_enrollment(request, db=ledger.db, sub_role="admin")
    enrollment = ledger.db.query(models.Enrollment).filter(models.Enrollment.is_deleted == False).one()
    transaction = ledger.db.query(models.Transaction).one()
    assert (ledger.student.wallet_teacher, ledger.student.wallet_institute, ledger.student.wallet_balance) == (0, 100, 100)
    assert transaction.target_wallet == "institute"
    assert transaction.enrollment_id == enrollment.id
    perform_delete_enrollment(enrollment, ledger.db)
    ledger.db.commit()
    # تصمیم محصولی: وجه پرداختی هنگام ثبت‌نام با حذف ثبت‌نام از بین نمی‌رود و به‌صورت اعتبار نزد شاگرد می‌ماند
    assert (ledger.student.wallet_teacher, ledger.student.wallet_institute, ledger.student.wallet_balance) == (0, 100, 100)
    assert not transaction.is_deleted


# FIX: Bug 18 - a component change still rolls back normally; syncing does not commit caller work.
def test_wallet_sync_obeys_rollback(ledger):
    ledger.student.wallet_teacher = 100
    ledger.student.sync_wallet_balance()
    ledger.db.flush()
    ledger.db.rollback()
    assert ledger.student.wallet_teacher == ledger.student.wallet_institute == ledger.student.wallet_balance == 0


# FIX: Bug 22 - known-valid and generated checksums cover both remainder branches and leading zeroes.
@pytest.mark.parametrize("prefix", ["001234567", "000111222", "123456789", "098765432", "100000001", "000000010"])
def test_national_code_checksum_valid(prefix):
    remainder = sum(int(prefix[i]) * (10 - i) for i in range(9)) % 11
    code = prefix + str(remainder if remainder < 2 else 11 - remainder)
    assert validate_iranian_national_code(code) == code
    assert is_valid_iranian_national_code(code)


# FIX: Bug 22 - length-only checks, repeated digits and unsupported Unicode digits cannot pass.
@pytest.mark.parametrize("value", ["", "123", "0012345678", "1234567890", "0000000000", "1111111111", "9999999999", "00123a5679", "00123 5679", "²012345679", None, 1234567891])
def test_invalid_national_codes_are_rejected(value):
    assert not is_valid_iranian_national_code(value)
    with pytest.raises(ValueError):
        validate_iranian_national_code(value)


# FIX: Bug 22 - normalize supported keyboard digits so one identity cannot be stored in multiple alphabets.
@pytest.mark.parametrize("value", [" 0012345679 ", "۰۰۱۲۳۴۵۶۷۹", "٠٠١٢٣٤٥٦٧٩"])
def test_national_code_normalization(value):
    assert validate_iranian_national_code(value) == "0012345679"


# FIX: Bug 22 - all identity write models share the checksum, including edit/public registration gaps.
@pytest.mark.parametrize("model", [schemas.StudentCreate, schemas.TeacherCreate, schemas.StudentUpdate, schemas.TeacherUpdate, schemas.StudentRegisterAndEnrollRequest, crm.OnlineRegisterRequest])
def test_identity_write_models_use_checksum(model):
    valid = identity_payload(model)
    assert model(**valid).national_code == "0012345679"
    with pytest.raises(ValidationError):
        model(**dict(valid, national_code="0012345678"))
    with pytest.raises(ValidationError):
        model(**dict(valid, national_code=None))
    assert model(**dict(valid, national_code="۰۰۱۲۳۴۵۶۷۹")).national_code == "0012345679"


# FIX: Bug 22 - optional edits do not require clients to resend their national code.
@pytest.mark.parametrize("model", [schemas.StudentUpdate, schemas.TeacherUpdate])
def test_optional_identity_update_can_omit_national_code(model):
    assert model(first_name="Updated").model_dump(exclude_unset=True) == {"first_name": "Updated"}


# FIX: Bug 22 - price zero remains allowed; a negative teacher session price is not.
@pytest.mark.parametrize("price", [-1, -100, 0, 100])
def test_teacher_price_bounds(price):
    values = dict(title="P3", code="", teacher_id=1, education_type="دبیرستان", grade_level="دهم", gender_type="مختلط", teacher_session_price=price)
    if price < 0:
        with pytest.raises(ValidationError): schemas.CourseCreate(**values)
    else:
        assert schemas.CourseCreate(**values).teacher_session_price == price


# FIX: Bug 22 - grade limits are checked against that request's maximum, including finite numeric validation.
@pytest.mark.parametrize("score,maximum,valid", [
    (0, 20, True), (20, 20, True), (1.5, 2, True), (21, 20, False),
    (-1, 20, False), (0, 0, False), (1, -1, False),
    (float("nan"), 20, False), (float("inf"), 20, False), (10, float("inf"), False),
])
def test_grade_request_bounds(score, maximum, valid):
    values = dict(student_id=101, course_id=1, exam_title="P3 grade", score=score, max_score=maximum, date="1405/06/15")
    if valid:
        assert schemas.GradeCreate(**values).score == score
    else:
        with pytest.raises(ValidationError): schemas.GradeCreate(**values)


# FIX: Bug 22 - all single-wallet payment routes reject invalid credits without any side effects.
@pytest.mark.parametrize("wallet", ["teacher", "institute", "legacy"])
@pytest.mark.parametrize("amount", [0, -1, -100])
def test_payment_requires_positive_total(ledger, wallet, amount):
    with pytest.raises(HTTPException) as error:
        pay(ledger, wallet=wallet, amount=amount)
    assert error.value.status_code == 400
    assert ledger.db.query(models.Transaction).count() == ledger.db.query(models.SequenceCounter).count() == 0
    assert ledger.student.wallet_teacher == ledger.student.wallet_institute == ledger.student.wallet_balance == 0


# FIX: Bug 22 - a zero explicit share is valid when the complete payment total is positive; retain Priority 2 semantics.
def test_positive_combined_payment_allows_explicit_zero_share(ledger):
    result = pay(ledger, amount=0, amount_teacher=0, amount_institute=100)
    assert result["new_balance_teacher"] == 0
    assert result["new_balance_institute"] == ledger.student.wallet_balance == 100


# FIX: Bug 22 - validate payment initiation before the currently-disabled gateway handler.
@pytest.mark.parametrize("amount", [0, -1, -100, 1])
def test_online_payment_amount_bounds(amount):
    values = dict(student_id=101, amount=amount, target_wallet="institute")
    if amount <= 0:
        with pytest.raises(ValidationError): finance.PaymentInitiateRequest(**values)
    else:
        assert finance.PaymentInitiateRequest(**values).amount == 1


# FIX: Bug 22 - payment edits cannot turn credits into zero/negative records.
@pytest.mark.parametrize("amount", [0, -100])
def test_payment_edit_rejects_nonpositive_credit_without_changes(ledger, amount):
    result = pay(ledger, wallet="institute")
    original = ledger.db.get(models.Transaction, result["receipt_ids"][0])
    before = (original.amount, original.description, ledger.student.wallet_balance)
    with pytest.raises(HTTPException) as error:
        admin.update_transaction(original.id, schemas.TransactionUpdate(amount=amount, description="bad edit", date="1405/06/16"), db=ledger.db, _="admin")
    assert error.value.status_code == 400
    assert (original.amount, original.description, ledger.student.wallet_balance) == before


# FIX: Bug 22 - reuse the real app/dependencies; an HTTP validation failure must not write database rows.
@pytest.fixture
def api(ledger):
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = lambda: ledger.db
    client = TestClient(app, headers={"Authorization": "Bearer p2-admin-token"})
    yield client
    client.close()
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


# FIX: Bug 22 - the invalid public identity cannot reach registration/receipt creation.
def test_http_public_registration_rejects_bad_checksum_without_writes(api, ledger):
    values = identity_payload(crm.OnlineRegisterRequest, "0012345678")
    response = api.post("/crm/register_online", json=values)
    assert response.status_code == 422, response.text
    assert ledger.db.query(models.Student).count() == 1
    assert ledger.db.query(models.Enrollment).count() == 1
    assert ledger.db.query(models.Transaction).count() == 0


# FIX: Bug 22 - actual edit endpoints reject invalid identity before changing the existing student/teacher.
@pytest.mark.parametrize("path,model_name", [("/students/update/101", "Student"), ("/teachers/update/1", "Teacher")])
def test_http_identity_update_rejects_bad_checksum(api, ledger, path, model_name):
    target = ledger.student if model_name == "Student" else ledger.teacher
    original = target.national_code
    response = api.put(path, json={"national_code": "0012345678"})
    assert response.status_code == 422, response.text
    ledger.db.refresh(target)
    assert target.national_code == original


# FIX: Bug 22 - actual class/grade/payment HTTP responses demonstrate validation, not just model construction.
def test_http_price_grade_and_online_payment_validation(api, ledger):
    course = dict(title="P3", code="", teacher_id=1, education_type="دبیرستان", grade_level="دهم", gender_type="مختلط", teacher_session_price=-1)
    response = api.post("/classes/create", json=course)
    assert response.status_code == 422, response.text
    grade = dict(student_id=101, course_id=1, exam_title="P3", score=21, max_score=20, date="1405/06/15")
    response = api.post("/grades/submit", json=grade)
    assert response.status_code == 422, response.text
    response = api.post("/finance/payment/initiate", json=dict(student_id=101, amount=0, target_wallet="teacher"))
    assert response.status_code == 422, response.text
    assert ledger.db.query(models.Course).count() == 1
    assert ledger.db.query(models.Grade).count() == 0
    assert ledger.db.query(models.Transaction).count() == 0


# FIX: Bug 22 - valid grade boundaries remain usable through the real endpoint.
def test_http_grade_equal_to_maximum_is_saved(api, ledger):
    response = api.post("/grades/submit", json=dict(student_id=101, course_id=1, exam_title="P3", score=20, max_score=20, date="1405/06/15"))
    assert response.status_code == 200, response.text
    grade = ledger.db.query(models.Grade).one()
    assert grade.score == grade.max_score == 20


# FIX: Bug 22 - homework grading checks the saved maximum without changing existing access control.
def test_homework_grade_cannot_exceed_saved_maximum(ledger):
    teacher_user = models.User(id=2, username=ledger.teacher.mobile, password="unused", role="teacher", sub_role="teacher", branch_id=1)
    ledger.db.add(teacher_user)
    ledger.db.flush()
    ledger.db.add(models.UserSession(token="p3-teacher-token", user_id=2, teacher_id=ledger.teacher.id, sub_role="teacher", created_at=datetime.datetime.now()))
    hw = models.Homework(course_id=1, teacher_id=1, title="P3", description="P3", due_date="1405/06/15", max_score=10)
    ledger.db.add(hw)
    ledger.db.flush()
    submission = models.HomeworkSubmission(homework_id=hw.id, student_id=101, file_path="synthetic-no-file.pdf", status="submitted")
    ledger.db.add(submission)
    ledger.db.commit()
    with pytest.raises(HTTPException) as error:
        homework.grade_homework_submission(submission.id, homework.GradeSubmissionRequest(score=11, feedback="P3"), authorization="Bearer p3-teacher-token", db=ledger.db, role="teacher")
    assert error.value.status_code == 400
    assert submission.status == "submitted"
    assert submission.score is None


# FIX: Bug 22 - no-payment registration is legitimate; negative/null initial credits are not.
@pytest.mark.parametrize("model", [schemas.EnrollmentCreate, schemas.StudentRegisterAndEnrollRequest, crm.OnlineRegisterRequest])
def test_initial_payment_validation_preserves_unpaid_registration(model):
    values = identity_payload(model)
    values["paid_amount"] = 0
    assert model(**values).paid_amount == 0
    for invalid in (-1, None):
        with pytest.raises(ValidationError):
            model(**dict(values, paid_amount=invalid))


# FIX: Bug 22 - actual payment HTTP handlers reject zero/negative credits before posting.
@pytest.mark.parametrize("wallet", ["teacher", "institute"])
@pytest.mark.parametrize("amount", [0, -1])
def test_http_payment_amount_rejection_has_no_side_effects(api, ledger, wallet, amount):
    response = api.post("/finance/pay", json=dict(student_id=101, amount=amount, target_wallet=wallet, description="P3", payment_method="نقدی", date="1405/06/15"))
    assert response.status_code == 400, response.text
    assert ledger.db.query(models.Transaction).count() == 0
    assert ledger.db.query(models.SequenceCounter).count() == 0
    assert ledger.student.wallet_balance == 0


# FIX: Bug 18 - legacy aggregate-only history needs explicit reconciliation, not a profile edit that erases it.
def test_unrelated_profile_edit_does_not_rewrite_legacy_wallet_total(ledger):
    ledger.db.execute(text("UPDATE students SET wallet_balance=12345 WHERE id=:id"), {"id": ledger.student.id})
    ledger.db.commit()
    ledger.db.refresh(ledger.student)
    ledger.student.first_name = "Updated profile"
    ledger.db.commit()
    assert ledger.db.execute(text("SELECT wallet_balance FROM students WHERE id=:id"), {"id": ledger.student.id}).scalar_one() == 12345

