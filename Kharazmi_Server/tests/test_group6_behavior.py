# گروه ۶ — قراردادهای فیچرهای جدید ۲۴ تا ۲۹
# این تست‌ها قراردادهای گروه ۶ را در backend و UI به‌صورت سریع regression-check می‌کنند.
import os
import re
import unittest

SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(SERVER_DIR)
KT_DIR = os.path.join(REPO_ROOT, "KharazmiAdmin", "app", "src", "main", "java", "com", "example", "kharazmiadmin")
RES_DIR = os.path.join(REPO_ROOT, "KharazmiAdmin", "app", "src", "main", "res")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def server(name):
    return read(os.path.join(SERVER_DIR, name))


def kotlin(name):
    return read(os.path.join(KT_DIR, name))


def layout(name):
    return read(os.path.join(RES_DIR, "layout", name))


class TestGroup6SettlementSafety(unittest.TestCase):
    def test_24_settlement_has_linked_scope_and_reversal_routes(self):
        models = server("models.py")
        teachers = server("routers/teachers.py")
        self.assertIn("session_ids", models)
        self.assertIn("settlement_reversal", models)
        self.assertIn('settlement_id', models)
        self.assertIn('settlement_payout', teachers)
        self.assertIn('/teachers/{teacher_id}/settlements/{settlement_id}/reverse', teachers)
        self.assertIn('/teachers/{teacher_id}/settlements/{settlement_id}/edit', teachers)
        self.assertIn('type="reversal"', teachers)
        self.assertNotIn('db.delete(settlement)', teachers)

    def test_24_profile_history_exposes_safe_actions(self):
        src = kotlin("TeacherProfileActivity.kt")
        xml = layout("item_settlement_history.xml")
        self.assertIn("reverseSettlement", src)
        self.assertIn("editSettlement", src)
        self.assertIn("operationId", src)
        self.assertIn("settlement_id", src)
        self.assertIn("btnReverseSettlement", xml)
        self.assertIn("btnEditSettlement", xml)


class TestGroup6SessionHistory(unittest.TestCase):
    def test_25_admin_history_has_flags_filters_reopen_and_export(self):
        admin = server("routers/admin.py")
        self.assertIn("attendance_missing", admin)
        self.assertIn("started_late", admin)
        self.assertIn("auto_ended", admin)
        self.assertIn('/admin/session_history', admin)
        self.assertIn('/admin/session_history/{session_id}/reopen', admin)
        self.assertIn('session_history', admin)
        self.assertIn('StreamingResponse', admin)

    def test_25_session_history_ui_has_filters_and_visual_flags(self):
        self.assertIn("SessionHistory", kotlin("AdminSessionHistoryActivity.kt"))
        xml = layout("activity_admin_session_history.xml")
        self.assertIn("filter", xml)
        self.assertIn("tvProblemFlags", xml)
        self.assertIn("btnReopenSession", xml)
        self.assertIn("btnExportSessions", xml)


class TestGroup6ClassApproval(unittest.TestCase):
    def test_26_pending_classes_have_reason_and_bulk_decisions(self):
        classes = server("routers/classes.py")
        models = server("models.py")
        self.assertIn("rejection_reason", models)
        self.assertIn('/classes/pending_approval', classes)
        self.assertIn('/classes/pending_approval/bulk_approve', classes)
        self.assertIn('/classes/pending_approval/bulk_reject', classes)
        self.assertIn("check_scheduling_conflicts", classes)
        self.assertIn("ActivityLog", classes)

    def test_26_admin_ui_supports_reason_and_bulk(self):
        src = kotlin("ClassManagementActivity.kt")
        self.assertIn("bulkApprove", src)
        self.assertIn("bulkReject", src)
        self.assertIn("rejectionReason", src)


class TestGroup6TeacherPending(unittest.TestCase):
    def test_27_teacher_pending_endpoint_and_dashboard_section(self):
        teachers = server("routers/teachers.py")
        self.assertIn('/teachers/{teacher_id}/pending_classes', teachers)
        src = kotlin("TeacherDashboardActivity.kt")
        xml = layout("activity_teacher_dashboard.xml")
        self.assertIn("pending_classes", src)
        self.assertIn("cardPendingApproval", xml)


class TestGroup6StudentStatement(unittest.TestCase):
    def test_28_statement_has_teacher_timeline_next_due_and_payment_link(self):
        reports = server("routers/reports.py")
        self.assertIn("teacher_name", reports)
        self.assertIn("payment_timeline", reports)
        self.assertIn("next_installment", reports)
        src = kotlin("ReportActivity.kt")
        xml = layout("activity_report.xml")
        self.assertIn("StudentProfileActivity", src)
        self.assertIn("btnStatementPay", xml)
        self.assertIn("rvPaymentTimeline", xml)


class TestGroup6ClassEdit(unittest.TestCase):
    def test_29_class_edit_contract_covers_schedule_capacity_transfer_pause(self):
        classes = server("routers/classes.py")
        self.assertIn("days_of_week", classes)
        self.assertIn("class_time", classes)
        self.assertIn("capacity", classes)
        self.assertIn("teacher_id", classes)
        self.assertIn("is_paused", classes)
        self.assertIn("check_scheduling_conflicts", classes)
        self.assertIn("/classes/update", classes)

    def test_29_both_panels_expose_class_edit(self):
        self.assertIn("updateClass", kotlin("ClassManagementActivity.kt"))
        self.assertIn("updateClass", kotlin("ClassDetailActivity.kt"))
        self.assertIn("capacity", layout("activity_class_detail.xml"))


if __name__ == "__main__":
    unittest.main()
