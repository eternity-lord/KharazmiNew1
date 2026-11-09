"""Regression coverage for per-enrollment financial isolation.

A student's wallets are aggregate legacy balances. They must not be copied into
an unrelated class row when the student is enrolled in more than one class.
"""
import asyncio
import datetime
import io
import json
import unittest

from fastapi import HTTPException
from openpyxl import load_workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models import (
    Base,
    Branch,
    Course,
    Enrollment,
    Attendance,
    SessionLog,
    Student,
    Teacher,
    Transaction,
    User,
    UserSession,
)
from financial_calculations import calculate_enrollment_debt_breakdown, calculate_student_debt
from routers.classes import (
    get_all_classes,
    get_class_details,
    get_class_full_report,
    get_class_students_excel,
    get_class_students_full,
)
from routers.admin import get_student_full_profile
from routers.finance import (
    FinanceSubmitData,
    get_debtors_list,
    get_invoice_details,
    get_student_class_status,
    get_student_financial_dashboard,
    search_finance_advanced,
    submit_payment,
)
from routers.reports import get_student_statement
from routers.teachers import get_my_classes


class TestPerClassDebtIsolation(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine, expire_on_commit=False)()

        self.db.add(Branch(id=1, name="مرکزی", active=True))
        self.admin = User(
            id=1, username="admin", password="x", full_name="مدیر",
            role="admin", sub_role="admin", branch_id=1,
        )
        self.teacher = Teacher(
            id=1, first_name="معلم", last_name="مشترک", mobile="09120000001",
            national_code="0012345678", is_approved=True,
        )
        self.student = Student(
            id=1, first_name="علی", last_name="دوکلاسه", national_code="0012345680",
            student_mobile="09121111111", wallet_teacher=-300,
            wallet_institute=-200, wallet_balance=-500,
        )
        self.course_a = Course(
            id=1, title="کلاس A", code="A", teacher_id=self.teacher.id,
            branch_id=1, teacher_session_price=100, is_admin_approved=True,
            is_deleted=False,
        )
        self.course_b = Course(
            id=2, title="کلاس B", code="B", teacher_id=self.teacher.id,
            branch_id=1, teacher_session_price=100, is_admin_approved=True,
            is_deleted=False,
        )
        self.enrollment_a = Enrollment(
            id=1, student_id=self.student.id, course_id=self.course_a.id,
            branch_id=1, register_date="1405/06/01", shift="عصر",
            total_tuition=1000, total_paid=0, is_deleted=False,
        )
        # B intentionally has no priced tuition: this is the legacy enrollment
        # that used to inherit A's aggregate wallet debt.
        self.enrollment_b = Enrollment(
            id=2, student_id=self.student.id, course_id=self.course_b.id,
            branch_id=1, register_date="1405/06/02", shift="عصر",
            total_tuition=0, total_paid=0, is_deleted=False,
        )
        self.db.add_all([
            self.admin, self.teacher, self.student, self.course_a, self.course_b,
            self.enrollment_a, self.enrollment_b,
            UserSession(
                token="admin-token", user_id=self.admin.id, sub_role="admin",
                created_at=datetime.datetime.now(),
            ),
            # A session charge is class-scoped and creates the legacy wallet
            # state represented above; it is never a payment for class B.
            SessionLog(id=1, course_id=self.course_a.id, date="1405/06/03", session_code=1),
            Transaction(
                id=1, student_id=self.student.id, course_id=self.course_a.id,
                session_id=1, amount=-500, type="session_charge",
                share_teacher=300, share_institute=200,
                date="1405/06/03", description="A charge",
                is_deleted=False, is_reversed=False,
            ),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _admin(self):
        return "Bearer admin-token"

    def _excel_rows(self, course_id):
        response = get_class_students_excel(class_id=course_id, db=self.db, _="admin")

        async def read_body():
            return b"".join([chunk async for chunk in response.body_iterator])

        payload = asyncio.run(read_body())
        sheet = load_workbook(io.BytesIO(payload), data_only=True).active
        return list(sheet.iter_rows(min_row=4, values_only=True))

    REQUIRED_DEBT_METADATA = {
        "enrollment_id", "course_id", "course_title",
        "teacher_id", "teacher_name", "is_unassigned",
    }

    def _assert_debt_metadata(self, row, enrollment_id, course_id, course_title):
        self.assertTrue(self.REQUIRED_DEBT_METADATA.issubset(row.keys()), row)
        self.assertEqual(row["enrollment_id"], enrollment_id)
        self.assertEqual(row["course_id"], course_id)
        self.assertEqual(row["course_title"], course_title)
        self.assertEqual(row["teacher_id"], self.teacher.id)
        self.assertEqual(row["teacher_name"], "معلم مشترک")
        self.assertFalse(row["is_unassigned"])

    def test_debt_metadata_contract_is_present_on_every_debt_endpoint(self):
        classes = {row["id"]: row for row in get_all_classes(db=self.db, _="admin")}
        self._assert_debt_metadata(classes[self.course_b.id], None, self.course_b.id, "کلاس B")

        details = get_class_details(
            course_id=self.course_b.id, db=self.db,
            authorization=self._admin(), sub_role="admin",
        )["students"][0]
        self._assert_debt_metadata(details, self.enrollment_b.id, self.course_b.id, "کلاس B")

        report_student = get_class_full_report(
            id=self.course_b.id, db=self.db,
            authorization=self._admin(), sub_role="admin",
        ).students[0].model_dump()
        self._assert_debt_metadata(report_student, self.enrollment_b.id, self.course_b.id, "کلاس B")

        full_student = get_class_students_full(
            id=self.course_b.id, db=self.db,
            authorization=self._admin(), sub_role="admin",
        )["students"][0]
        self._assert_debt_metadata(full_student, self.enrollment_b.id, self.course_b.id, "کلاس B")

        search_class = next(row for row in search_finance_advanced(
            query="کلاس B", branch_id=None, authorization=self._admin(),
            db=self.db, sub_role="admin",
        ) if row.type == "class")
        self._assert_debt_metadata(
            search_class.students_in_class[0], self.enrollment_b.id,
            self.course_b.id, "کلاس B",
        )

        status = get_student_class_status(
            student_id=self.student.id, course_id=self.course_b.id,
            db=self.db, authorization=self._admin(), sub_role="admin",
        )
        self._assert_debt_metadata(status, self.enrollment_b.id, self.course_b.id, "کلاس B")

        invoice = get_invoice_details(
            enrollment_id=self.enrollment_b.id, db=self.db,
            authorization=self._admin(), _role="admin",
        )
        self._assert_debt_metadata(invoice, self.enrollment_b.id, self.course_b.id, "کلاس B")

        dashboard = get_student_financial_dashboard(
            student_id=self.student.id, db=self.db,
            authorization=self._admin(), _role="admin",
        )
        dashboard_row = next(row for row in dashboard["enrollments"] if row["enrollment_id"] == self.enrollment_b.id)
        self._assert_debt_metadata(dashboard_row, self.enrollment_b.id, self.course_b.id, "کلاس B")

        profile = get_student_full_profile(
            id=self.student.id, authorization=self._admin(), db=self.db, role="admin",
        )
        profile_enrollment = next(row for row in profile["enrollments"] if row["enrollment_id"] == self.enrollment_b.id)
        self._assert_debt_metadata(profile_enrollment, self.enrollment_b.id, self.course_b.id, "کلاس B")
        profile_financial = next(row for row in profile["teachers_financial"] if row["enrollment_id"] == self.enrollment_b.id)
        self._assert_debt_metadata(profile_financial, self.enrollment_b.id, self.course_b.id, "کلاس B")

        statement = get_student_statement(
            student_id=self.student.id, db=self.db,
            authorization=self._admin(), role="admin",
        )
        statement_row = next(row for row in statement["teachers"] if row["enrollment_id"] == self.enrollment_b.id)
        self._assert_debt_metadata(statement_row, self.enrollment_b.id, self.course_b.id, "کلاس B")

        debtor = next(row for row in get_debtors_list(
            branch_id=None, search="دوکلاسه", authorization=self._admin(), db=self.db, _="admin"
        ) if row["student_id"] == self.student.id)
        debtor_row = next(row for row in debtor["teachers"] if row["enrollment_id"] == self.enrollment_b.id)
        self._assert_debt_metadata(debtor_row, self.enrollment_b.id, self.course_b.id, "کلاس B")

        teacher_class = next(row for row in get_my_classes(
            teacher_id=self.teacher.id, db=self.db,
            authorization=self._admin(), sub_role="admin",
        ) if row["id"] == self.course_b.id)
        self._assert_debt_metadata(teacher_class, None, self.course_b.id, "کلاس B")

    def test_breakdown_does_not_copy_wallet_debt_to_legacy_class(self):
        a = calculate_enrollment_debt_breakdown(self.db, self.enrollment_a)
        b = calculate_enrollment_debt_breakdown(self.db, self.enrollment_b)
        self.assertEqual(a["debt"], 1000)
        self.assertEqual(a["debt_teacher"], 300)
        self.assertEqual(a["debt_institute"], 200)
        self.assertEqual(b["debt"], 0)
        self.assertEqual(b["debt_teacher"], 0)
        self.assertEqual(b["debt_institute"], 0)

    def test_session_charge_is_isolated_by_session_not_a_mistyped_course_id(self):
        self.enrollment_b.total_tuition = 1000
        legacy_charge = self.db.query(Transaction).filter(Transaction.id == 1).one()
        # Even if a legacy charge carries B's course_id, session_id=1 identifies
        # course A and must keep the charge out of B.
        legacy_charge.course_id = self.course_b.id
        self.db.commit()

        a = calculate_enrollment_debt_breakdown(
            self.db, self.enrollment_a, session_scoped=True
        )
        b = calculate_enrollment_debt_breakdown(
            self.db, self.enrollment_b, session_scoped=True
        )
        self.assertEqual((a["debt_teacher"], a["debt_institute"]), (300, 200))
        # A priced enrollment is debt even before its first session; only its
        # own institute share may carry the remainder.
        self.assertEqual((b["debt_teacher"], b["debt_institute"]), (0, 1000))

    def test_session_scoped_financial_views_show_only_the_attended_class(self):
        """Two classes keep separate contractual/session debt shares."""
        # Make the second registration priced too. Its lack of a session must
        # not erase its own contractual enrollment debt or copy class A's shares.
        self.enrollment_b.total_tuition = 1000
        self.student.branch_id = 1
        self.db.add(Attendance(
            session_id=1,
            student_id=self.student.id,
            status="Present",
            is_billed=False,
            is_deleted=False,
        ))
        self.db.commit()

        legacy_a = calculate_enrollment_debt_breakdown(self.db, self.enrollment_a)
        legacy_b = calculate_enrollment_debt_breakdown(self.db, self.enrollment_b)
        scoped_a = calculate_enrollment_debt_breakdown(
            self.db, self.enrollment_a, session_scoped=True
        )
        scoped_b = calculate_enrollment_debt_breakdown(
            self.db, self.enrollment_b, session_scoped=True
        )
        self.assertEqual((scoped_a["debt_teacher"], scoped_a["debt_institute"]), (300, 200))
        # The second enrollment has its own contractual tuition debt; it must
        # not become zero merely because class A has the only session charge.
        self.assertEqual((scoped_b["debt_teacher"], scoped_b["debt_institute"]), (0, 1000))
        self.assertEqual(scoped_b["debt"], 1000)
        # Default/legacy calculation remains available for non-class-scoped reports.
        self.assertEqual(legacy_b["debt"], 1000)
        self.assertEqual(legacy_a["debt"], 1000)

        class_rows = {row["id"]: row for row in get_all_classes(db=self.db, _="admin")}
        self.assertEqual(
            (class_rows[self.course_a.id]["debt_to_teacher"], class_rows[self.course_a.id]["debt_to_institute"]),
            (300, 200),
        )
        self.assertEqual(
            (class_rows[self.course_b.id]["debt_to_teacher"], class_rows[self.course_b.id]["debt_to_institute"]),
            (0, 1000),
        )

        detail_a = get_class_students_full(
            id=self.course_a.id, db=self.db,
            authorization=self._admin(), sub_role="admin",
        )["students"][0]
        detail_b = get_class_students_full(
            id=self.course_b.id, db=self.db,
            authorization=self._admin(), sub_role="admin",
        )["students"][0]
        self.assertEqual((detail_a["debt_teacher"], detail_a["debt_institute"]), (300, 200))
        self.assertEqual((detail_b["debt_teacher"], detail_b["debt_institute"]), (0, 1000))
        self.assertEqual(detail_b["debt"], 1000)

        status_a = get_student_class_status(
            student_id=self.student.id, course_id=self.course_a.id,
            db=self.db, authorization=self._admin(), sub_role="admin",
        )
        status_b = get_student_class_status(
            student_id=self.student.id, course_id=self.course_b.id,
            db=self.db, authorization=self._admin(), sub_role="admin",
        )
        self.assertEqual((status_a["due_to_teacher"], status_a["due_to_institute"]), (300, 200))
        self.assertEqual(status_a["remaining_tuition"], 500)
        self.assertEqual((status_b["due_to_teacher"], status_b["due_to_institute"]), (0, 1000))
        self.assertEqual(status_b["remaining_tuition"], 1000)
        self.assertEqual(status_b["enrollment_id"], self.enrollment_b.id)

        # The quick-remittance picker source is the student's active enrollment
        # list. It must carry the same per-class values before a class is picked.
        profile = get_student_full_profile(
            id=self.student.id, authorization=self._admin(), db=self.db, role="admin",
        )
        profile_rows = {row["enrollment_id"]: row for row in profile["enrollments"]}
        self.assertEqual((profile_rows[self.enrollment_a.id]["debt_teacher"], profile_rows[self.enrollment_a.id]["debt_institute"]), (300, 200))
        self.assertEqual((profile_rows[self.enrollment_b.id]["debt_teacher"], profile_rows[self.enrollment_b.id]["debt_institute"]), (0, 1000))

        advanced = search_finance_advanced(
            query="0012345680", branch_id=None, authorization=self._admin(),
            db=self.db, sub_role="admin",
        )
        student_result = next(row for row in advanced if row.type == "student")
        # Aggregate search debt is informational only; class attribution happens
        # after enrollment selection.
        self.assertEqual(student_result.total_debt, 2000)
        self.assertNotIn("بدهی کل", student_result.info)

        class_search = search_finance_advanced(
            query="کلاس B", branch_id=None, authorization=self._admin(),
            db=self.db, sub_role="admin",
        )
        class_result = next(row for row in class_search if row.type == "class")
        class_student = class_result.students_in_class[0]
        self.assertEqual((class_student["debt_teacher"], class_student["debt_institute"]), (0, 1000))
        self.assertEqual(class_student["enrollment_id"], self.enrollment_b.id)

    def test_payment_with_enrollment_id_isolated_and_ambiguous_payment_rejected(self):
        before_a = calculate_enrollment_debt_breakdown(self.db, self.enrollment_a)
        before_b = calculate_enrollment_debt_breakdown(self.db, self.enrollment_b)
        before_transactions = self.db.query(Transaction).count()

        response = submit_payment(
            FinanceSubmitData(
                student_id=self.student.id,
                amount=100,
                target_wallet="institute",
                description="پرداخت کلاس B",
                payment_method="نقدی",
                date="1405/06/04",
                enrollment_id=self.enrollment_b.id,
            ),
            db=self.db,
            _="admin",
            branch_id=None,
            authorization=self._admin(),
        )
        self.assertEqual(response["receipt_id"] > 0, True)
        after_a = calculate_enrollment_debt_breakdown(self.db, self.enrollment_a)
        after_b = calculate_enrollment_debt_breakdown(self.db, self.enrollment_b)
        self.assertEqual(after_a, before_a)
        self.assertEqual(after_b["paid_institute"], before_b["paid_institute"] + 100)
        self.assertEqual(after_b["debt"], 0)
        payment = self.db.query(Transaction).filter(Transaction.id == response["receipt_id"]).one()
        self.assertEqual(payment.enrollment_id, self.enrollment_b.id)
        self.assertEqual(payment.course_id, self.course_b.id)

        with self.assertRaises(HTTPException) as raised:
            submit_payment(
                FinanceSubmitData(
                    student_id=self.student.id,
                    amount=50,
                    target_wallet="institute",
                    description="پرداخت مبهم",
                    payment_method="نقدی",
                    date="1405/06/04",
                ),
                db=self.db,
                _="admin",
                branch_id=None,
                authorization=self._admin(),
            )
        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("چند ثبت‌نام فعال دارد", str(raised.exception.detail))
        self.assertEqual(self.db.query(Transaction).count(), before_transactions + 1)

    def test_class_list_details_full_report_and_excel_are_isolated(self):
        classes = {row["id"]: row for row in get_all_classes(db=self.db, _="admin")}
        self.assertEqual(classes[self.course_a.id]["total_debt"], 1000)
        self.assertEqual(classes[self.course_b.id]["total_debt"], 0)
        self.assertEqual(classes[self.course_b.id]["debt_to_teacher"], 0)
        self.assertEqual(classes[self.course_b.id]["debt_to_institute"], 0)
        self.assertEqual(classes[self.course_a.id]["course_id"], self.course_a.id)
        self.assertEqual(classes[self.course_a.id]["course_title"], "کلاس A")
        self.assertEqual(classes[self.course_a.id]["teacher_id"], self.teacher.id)
        self.assertFalse(classes[self.course_a.id]["is_unassigned"])

        details_b = get_class_details(
            course_id=self.course_b.id, db=self.db,
            authorization=self._admin(), sub_role="admin",
        )["students"][0]
        self.assertEqual(details_b["debt"], 0)
        self.assertEqual(details_b["paid"], 0)
        self.assertEqual(details_b["enrollment_id"], self.enrollment_b.id)
        self.assertEqual(details_b["course_title"], "کلاس B")
        self.assertEqual(details_b["teacher_id"], self.teacher.id)
        self.assertFalse(details_b["is_unassigned"])

        report_b = get_class_full_report(
            id=self.course_b.id, db=self.db,
            authorization=self._admin(), sub_role="admin",
        )
        self.assertEqual(report_b.info.total_debt, 0)
        self.assertEqual(report_b.info.total_revenue, 0)
        self.assertEqual(report_b.students[0].enrollment_id, self.enrollment_b.id)
        self.assertEqual(report_b.students[0].course_title, "کلاس B")

        full_b = get_class_students_full(
            id=self.course_b.id, db=self.db,
            authorization=self._admin(), sub_role="admin",
        )["students"][0]
        self.assertEqual(full_b["debt"], 0)
        self.assertEqual(full_b["debt_teacher"], 0)
        self.assertEqual(full_b["debt_institute"], 0)
        # These keys remain aggregate wallets for backward compatibility, not
        # class debt inputs.
        self.assertEqual(full_b["wallet_teacher"], -300)
        self.assertEqual(full_b["wallet_institute"], -200)
        self.assertEqual(full_b["enrollment_id"], self.enrollment_b.id)
        self.assertEqual(full_b["course_title"], "کلاس B")
        self.assertEqual(full_b["teacher_id"], self.teacher.id)
        self.assertFalse(full_b["is_unassigned"])

        excel_b = self._excel_rows(self.course_b.id)[0]
        # columns: id, name, base, discount type, selected discount,
        # discount amount, final tuition, paid, teacher debt, institute debt,
        # total debt, ...
        self.assertEqual(excel_b[7], 0)
        self.assertEqual(excel_b[8], 0)
        self.assertEqual(excel_b[9], 0)
        self.assertEqual(excel_b[10], 0)

        # finance.py invoice/status/search paths must use the same enrollment scope.
        status_b = get_student_class_status(
            student_id=self.student.id, course_id=self.course_b.id,
            db=self.db, authorization=self._admin(), sub_role="admin",
        )
        self.assertEqual(status_b["due_to_teacher"], 0)
        self.assertEqual(status_b["due_to_institute"], 0)
        self.assertEqual(status_b["enrollment_id"], self.enrollment_b.id)
        self.assertEqual(status_b["course_title"], "کلاس B")
        self.assertEqual(status_b["teacher_id"], self.teacher.id)
        invoice_b = get_invoice_details(
            enrollment_id=self.enrollment_b.id, db=self.db,
            authorization=self._admin(), _role="admin",
        )
        self.assertEqual(invoice_b["balance_due"], 0)
        self.assertEqual(invoice_b["enrollment_id"], self.enrollment_b.id)
        self.assertEqual(invoice_b["course_id"], self.course_b.id)
        self.assertEqual(invoice_b["teacher_id"], self.teacher.id)
        dashboard = get_student_financial_dashboard(
            student_id=self.student.id, db=self.db,
            authorization=self._admin(), _role="admin",
        )
        dashboard_rows = {row["enrollment_id"]: row for row in dashboard["enrollments"]}
        self.assertEqual(dashboard_rows[self.enrollment_b.id]["outstanding"], 0)
        self.assertEqual(dashboard_rows[self.enrollment_b.id]["course_id"], self.course_b.id)
        self.assertEqual(dashboard_rows[self.enrollment_b.id]["teacher_id"], self.teacher.id)
        advanced = search_finance_advanced(
            query="کلاس B", branch_id=None, authorization=self._admin(),
            db=self.db, sub_role="admin",
        )
        class_result = next(row for row in advanced if row.type == "class")
        self.assertEqual(class_result.students_in_class[0]["total_debt"], 0)
        self.assertEqual(class_result.students_in_class[0]["enrollment_id"], self.enrollment_b.id)
        self.assertEqual(class_result.students_in_class[0]["course_title"], "کلاس B")
        self.assertEqual(class_result.students_in_class[0]["teacher_id"], self.teacher.id)

        teacher_classes = get_my_classes(
            teacher_id=self.teacher.id, db=self.db,
            authorization=self._admin(), sub_role="admin",
        )
        teacher_rows = {row["id"]: row for row in teacher_classes}
        self.assertEqual(teacher_rows[self.course_a.id]["total_debt"], 1000)
        self.assertEqual(teacher_rows[self.course_b.id]["total_debt"], 0)
        self.assertEqual(teacher_rows[self.course_b.id]["debt_to_teacher"], 0)
        self.assertEqual(teacher_rows[self.course_b.id]["debt_to_institute"], 0)
        self.assertEqual(teacher_rows[self.course_b.id]["course_title"], "کلاس B")
        self.assertEqual(teacher_rows[self.course_b.id]["teacher_name"], "معلم مشترک")

    def test_class_row_sums_equal_class_totals_on_every_export_path(self):
        classes = {row["id"]: row for row in get_all_classes(db=self.db, _="admin")}
        for course_id in (self.course_a.id, self.course_b.id):
            details = get_class_details(
                course_id=course_id, db=self.db,
                authorization=self._admin(), sub_role="admin",
            )
            full_report = get_class_full_report(
                id=course_id, db=self.db,
                authorization=self._admin(), sub_role="admin",
            )
            students_full = get_class_students_full(
                id=course_id, db=self.db,
                authorization=self._admin(), sub_role="admin",
            )
            excel = self._excel_rows(course_id)

            class_total = classes[course_id]["total_debt"]
            self.assertEqual(sum(row["debt"] for row in details["students"]), class_total)
            self.assertEqual(sum(row.debt for row in full_report.students), full_report.info.total_debt)
            self.assertEqual(sum(row["debt"] for row in students_full["students"]), class_total)
            self.assertEqual(sum(row[10] or 0 for row in excel), class_total)
            self.assertEqual(full_report.info.total_debt, class_total)

    def test_kotlin_gson_like_response_contract_uses_per_enrollment_debt(self):
        """Validate the JSON keys consumed by Android without running Android compile."""
        full = get_class_students_full(
            id=self.course_b.id, db=self.db,
            authorization=self._admin(), sub_role="admin",
        )
        wire = json.loads(json.dumps(full, ensure_ascii=False))
        student = wire["students"][0]
        for key in (
            "enrollment_id", "debt", "debt_teacher", "debt_institute",
            "paid", "paid_teacher", "paid_institute", "wallet_teacher", "wallet_institute",
        ):
            self.assertIn(key, student)
        self.assertEqual(student["enrollment_id"], self.enrollment_b.id)
        self.assertEqual(student["debt"], 0)
        self.assertEqual(student["debt_teacher"], 0)
        self.assertEqual(student["debt_institute"], 0)
        self.assertEqual(student["wallet_teacher"], -300)
        self.assertEqual(student["wallet_institute"], -200)

        source_root = __import__("pathlib").Path(__file__).parents[2]
        class_detail = (source_root / "KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ClassDetailActivity.kt").read_text()
        invoice = (source_root / "KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/InvoiceActivity.kt").read_text()
        attendance = (source_root / "KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/AttendanceActivity.kt").read_text()
        profile = (source_root / "KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/StudentProfileActivity.kt").read_text()
        self.assertIn("String.format(\"%,d\", student.debt)", class_detail)
        self.assertIn("R.string.cdetail_debt_split", class_detail)
        self.assertNotIn("val totalDebt = fullStudent.debt", class_detail)
        self.assertIn("it.enrollment_id == student.enrollment_id", class_detail)
        self.assertIn("tvSelectedClass", invoice)
        self.assertNotIn("R.id.tvTotalDebt", invoice)
        self.assertIn("debtTeacher", invoice)
        self.assertIn("debtInstitute", invoice)
        self.assertIn("getStudentClassStatus(studentId, enrollment.course_id, null)", invoice)
        self.assertIn("row.debt_teacher", profile)
        self.assertIn("row.debt_institute", profile)
        self.assertIn("sumOf { it.paid_teacher }", attendance)
        self.assertIn("val debtTeacher = student.debt_teacher", attendance)
        self.assertIn("s.paid_teacher, s.paid_institute", attendance)
        self.assertNotIn("student.wallet_teacher", attendance)
        self.assertNotIn("student.wallet_institute", attendance)

    def test_payment_for_b_does_not_change_a_and_legacy_course_payment_is_scoped(self):
        before_a = calculate_enrollment_debt_breakdown(self.db, self.enrollment_a)
        self.db.add(Transaction(
            id=2, student_id=self.student.id, course_id=self.course_b.id,
            enrollment_id=None, amount=100, target_wallet="institute",
            type="deposit", date="1405/06/04", description="legacy B payment",
            is_deleted=False, is_reversed=False,
        ))
        self.db.commit()
        after_a = calculate_enrollment_debt_breakdown(self.db, self.enrollment_a)
        after_b = calculate_enrollment_debt_breakdown(self.db, self.enrollment_b)
        self.assertEqual(after_a, before_a)
        self.assertEqual(after_b["paid_institute"], 100)
        self.assertEqual(after_b["debt"], 0)

        self.db.add(Transaction(
            id=3, student_id=self.student.id, course_id=None,
            enrollment_id=None, amount=700, target_wallet="institute",
            type="deposit", date="1405/06/04", description="general credit",
            is_deleted=False, is_reversed=False,
        ))
        self.db.commit()
        self.assertEqual(calculate_enrollment_debt_breakdown(self.db, self.enrollment_a), after_a)
        self.assertEqual(calculate_enrollment_debt_breakdown(self.db, self.enrollment_b), after_b)

        classes = {row["id"]: row for row in get_all_classes(db=self.db, _="admin")}
        self.assertEqual(classes[self.course_a.id]["total_debt"], 1000)
        self.assertEqual(classes[self.course_a.id]["total_paid"], 0)
        self.assertEqual(classes[self.course_b.id]["total_paid"], 100)
        self.assertEqual(get_class_details(
            course_id=self.course_a.id, db=self.db,
            authorization=self._admin(), sub_role="admin",
        )["students"][0]["paid"], 0)
        self.assertEqual(get_class_details(
            course_id=self.course_b.id, db=self.db,
            authorization=self._admin(), sub_role="admin",
        )["students"][0]["paid"], 100)
        self.assertEqual(get_class_full_report(
            id=self.course_a.id, db=self.db,
            authorization=self._admin(), sub_role="admin",
        ).info.total_revenue, 0)
        self.assertEqual(get_class_full_report(
            id=self.course_b.id, db=self.db,
            authorization=self._admin(), sub_role="admin",
        ).info.total_revenue, 100)
        self.assertEqual(self._excel_rows(self.course_a.id)[0][7], 0)
        self.assertEqual(self._excel_rows(self.course_b.id)[0][7], 100)

    def test_per_class_and_unassigned_rows_reconcile_to_calculate_student_debt(self):
        expected = calculate_student_debt(self.db, self.student)

        profile = get_student_full_profile(
            id=self.student.id, authorization=self._admin(), db=self.db, role="admin",
        )
        profile_class_sum = sum(
            row["debt"]
            for row in profile["teachers_financial"]
            if not row["is_unassigned"]
        )
        self.assertEqual(profile_class_sum + profile["unassigned_debt"], expected)

        statement = get_student_statement(
            student_id=self.student.id, db=self.db,
            authorization=self._admin(), role="admin",
        )
        statement_class_sum = sum(
            row["debt"] for row in statement["teachers"] if not row["is_unassigned"]
        )
        self.assertEqual(statement_class_sum + statement["unassigned_debt"], expected)

        debtor = next(row for row in get_debtors_list(
            branch_id=None, search="دوکلاسه", authorization=self._admin(), db=self.db, _="admin"
        ) if row["student_id"] == self.student.id)
        self.assertEqual(sum(row["debt"] for row in debtor["teachers"]), expected)

    def test_both_payment_is_split_in_admin_teacher_financial_profile(self):
        self.db.add(Transaction(
            id=4, student_id=self.student.id, course_id=self.course_b.id,
            enrollment_id=self.enrollment_b.id, amount=100, target_wallet="both",
            share_teacher=40, share_institute=60, type="deposit",
            date="1405/06/05", description="both B payment",
            is_deleted=False, is_reversed=False,
        ))
        self.db.commit()
        profile = get_student_full_profile(
            id=self.student.id, authorization=self._admin(), db=self.db, role="admin",
        )
        financial = {row["course_title"]: row for row in profile["teachers_financial"]}
        self.assertEqual(financial["کلاس A"]["paid_teacher"], 0)
        self.assertEqual(financial["کلاس A"]["paid_institute"], 0)
        self.assertEqual(financial["کلاس B"]["paid_teacher"], 40)
        self.assertEqual(financial["کلاس B"]["paid_institute"], 60)
        self.assertEqual(financial["کلاس B"]["enrollment_id"], self.enrollment_b.id)
        self.assertEqual(financial["کلاس B"]["teacher_id"], self.teacher.id)
        self.assertEqual(profile["total_paid_institute"], 60)

        statement = get_student_statement(
            student_id=self.student.id, db=self.db,
            authorization=self._admin(), role="admin",
        )
        statement_rows = {row["course_title"]: row for row in statement["teachers"]}
        self.assertEqual(statement_rows["کلاس A"]["enrollment_id"], self.enrollment_a.id)
        self.assertEqual(statement_rows["کلاس B"]["enrollment_id"], self.enrollment_b.id)
        self.assertFalse(statement_rows["کلاس B"]["is_unassigned"])

    def test_class_debt_plus_unallocated_legacy_debt_equals_student_total(self):
        total = calculate_student_debt(self.db, self.student)
        class_sum = sum(
            calculate_enrollment_debt_breakdown(self.db, enrollment)["debt"]
            for enrollment in (self.enrollment_a, self.enrollment_b)
        )
        unallocated = total - class_sum
        self.assertEqual(total, 1000)
        self.assertEqual(class_sum + unallocated, total)
        self.assertGreaterEqual(unallocated, 0)

        legacy_student = Student(
            id=2, first_name="سارا", last_name="بدون کلاس", national_code="0012345681",
            student_mobile="09122222222", wallet_teacher=-400, wallet_institute=-300,
            wallet_balance=-700, branch_id=1,
        )
        self.db.add_all([
            legacy_student,
            Enrollment(
                id=3, student_id=legacy_student.id, course_id=self.course_a.id,
                branch_id=1, register_date="1405/06/03", shift="عصر",
                total_tuition=0, total_paid=0, is_deleted=False,
            ),
            Enrollment(
                id=4, student_id=legacy_student.id, course_id=self.course_b.id,
                branch_id=1, register_date="1405/06/04", shift="عصر",
                total_tuition=0, total_paid=0, is_deleted=False,
            ),
        ])
        self.db.commit()
        profile = get_student_full_profile(
            id=legacy_student.id, authorization=self._admin(), db=self.db, role="admin",
        )
        self.assertEqual(profile["unassigned_debt"], 700)
        profile_rows = profile["teachers_financial"]
        self.assertEqual(len(profile_rows), 3)
        assigned_profile_rows = [row for row in profile_rows if not row["is_unassigned"]]
        self.assertEqual({row["course_title"] for row in assigned_profile_rows}, {"کلاس A", "کلاس B"})
        self.assertTrue(all(row["debt_teacher"] + row["debt_institute"] == 0 for row in assigned_profile_rows))
        unassigned_profile_row = next(row for row in profile_rows if row["is_unassigned"])
        self.assertIsNone(unassigned_profile_row["course_title"])
        self.assertEqual(unassigned_profile_row["paid_institute"], 0)
        self.assertEqual(unassigned_profile_row["debt_institute"], 700)

        statement = get_student_statement(
            student_id=legacy_student.id, db=self.db,
            authorization=self._admin(), role="admin",
        )
        self.assertEqual(statement["unassigned_debt"], 700)
        statement_rows = statement["teachers"]
        self.assertEqual(len(statement_rows), 3)
        self.assertEqual(
            {row["course_title"] for row in statement_rows if not row["is_unassigned"]},
            {"کلاس A", "کلاس B"},
        )
        self.assertTrue(all(row["debt"] == 0 for row in statement_rows if not row["is_unassigned"]))
        unassigned_statement_row = next(row for row in statement_rows if row["is_unassigned"])
        self.assertIsNone(unassigned_statement_row["course_title"])
        self.assertEqual(unassigned_statement_row["debt"], 700)

        debtor = next(row for row in get_debtors_list(
            branch_id=None, search="سارا", authorization=self._admin(), db=self.db, _="admin"
        ) if row["student_id"] == legacy_student.id)
        self.assertEqual(debtor["total_debt"], 700)
        debtor_rows = debtor["teachers"]
        self.assertEqual(len(debtor_rows), 3)
        self.assertTrue(all(row["debt"] == 0 for row in debtor_rows if not row["is_unassigned"]))
        unassigned_debtor_row = next(row for row in debtor_rows if row["is_unassigned"])
        self.assertIsNone(unassigned_debtor_row["course_title"])
        self.assertEqual(unassigned_debtor_row["debt"], 700)


if __name__ == "__main__":
    unittest.main()
