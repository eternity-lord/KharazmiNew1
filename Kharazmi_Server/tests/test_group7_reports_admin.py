"""Regression contracts for the reports/admin follow-up batch.

Android is intentionally checked statically in this repository; backend behavior is
covered by the existing report/session suites. These checks keep the new contracts
from being silently removed during later UI work.
"""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(ROOT)
KT = os.path.join(REPO, "KharazmiAdmin", "app", "src", "main", "java", "com", "example", "kharazmiadmin")
LAYOUT = os.path.join(REPO, "KharazmiAdmin", "app", "src", "main", "res", "layout")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class TestGroup7FinancialReportContracts(unittest.TestCase):
    def test_financial_report_uses_legacy_branch_scope_and_has_excel_contract(self):
        reports = read(os.path.join(ROOT, "routers", "reports.py"))
        calculations = read(os.path.join(ROOT, "financial_calculations.py"))
        self.assertIn("branch_scope_clause(Transaction.branch_id, resolved_branch)", reports)
        self.assertIn('@router.get("/reports/financial/excel")', reports)
        self.assertIn("financial_report.xlsx", reports)
        self.assertIn("branch_scope_clause(models.Transaction.branch_id, branch_id)", calculations)

    def test_student_statement_exposes_per_teacher_class_breakdown(self):
        reports = read(os.path.join(ROOT, "routers", "reports.py"))
        activity = read(os.path.join(KT, "ReportActivity.kt"))
        for key in ("teachers", "teacher_id", "course_id", "debt_teacher", "debt_institute",
                    "teacher_profile_path", "active_enrollments"):
            self.assertIn(key, reports)
        self.assertIn("StudentStatementTeacher", activity)
        self.assertIn("TeacherProfileActivity", activity)

    def test_teacher_dashboard_does_not_repeat_global_wallet_for_each_class(self):
        teachers = read(os.path.join(ROOT, "routers", "teachers.py"))
        calculations = read(os.path.join(ROOT, "financial_calculations.py"))
        self.assertIn("calculate_enrollment_debt_breakdown", teachers)
        self.assertIn("Transaction.enrollment_id", calculations)
        self.assertNotIn("student_debt_teacher + student_debt_institute", teachers)


class TestGroup7AdminSessionAndApprovalContracts(unittest.TestCase):
    def test_session_history_has_detail_filters_and_financial_export_columns(self):
        admin = read(os.path.join(ROOT, "routers", "admin.py"))
        activity = read(os.path.join(KT, "AdminSessionHistoryActivity.kt"))
        layout = read(os.path.join(LAYOUT, "activity_admin_session_history.xml"))
        for key in ("attendance", "financial_status", "charge_amount", "billed_attendance_count",
                    "search", "status"):
            self.assertIn(key, admin)
        self.assertIn("AdminFinancialStatus", activity)
        self.assertIn("etSessionDateFrom", layout)
        self.assertIn("etSessionSearch", layout)

    def test_single_and_bulk_approval_keep_conflict_and_rejection_audit(self):
        admin = read(os.path.join(ROOT, "routers", "admin.py"))
        classes = read(os.path.join(ROOT, "routers", "classes.py"))
        pending = read(os.path.join(KT, "PendingClassesActivity.kt"))
        self.assertIn("check_scheduling_conflicts", admin)
        self.assertIn('action="class_approve"', admin)
        self.assertIn('action="class_reject"', admin)
        self.assertIn("conflict_course_ids", classes)
        self.assertIn("bulkApprove", pending)
        self.assertIn("bulkReject", pending)
        self.assertIn("reason", pending)


if __name__ == "__main__":
    unittest.main()
