# گروه ۵ — رفتار اشتباه، آیتم‌های ۲۲ و ۲۳
# طبق قانون پروژه، قرارداد UI اندروید با تست ایستا قفل می‌شود؛ endpointهای سرور
# نیز با تست/اسکن مستقل و probe روی DB کپی بررسی می‌شوند.
import os
import re
import unittest

SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(SERVER_DIR)
KT_DIR = os.path.join(REPO_ROOT, "KharazmiAdmin", "app", "src", "main", "java", "com", "example", "kharazmiadmin")
RES_DIR = os.path.join(REPO_ROOT, "KharazmiAdmin", "app", "src", "main", "res")


def read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def kt(name: str) -> str:
    return read(os.path.join(KT_DIR, name))


def py(name: str) -> str:
    return read(os.path.join(SERVER_DIR, name))


def layout(name: str) -> str:
    return read(os.path.join(RES_DIR, "layout", name))


def function_body(source: str, name: str) -> str:
    match = re.search(
        r"\n\s*(?:(?:private|internal|public|override|open|suspend)\s+)*fun\s+"
        + re.escape(name)
        + r"\s*\(",
        source,
    )
    assert match, f"تابع {name} پیدا نشد"
    rest = source[match.end() :]
    nxt = re.search(r"\n\s{0,4}(?:private |internal |public |override )*fun\s+\w+", rest)
    return rest[: nxt.start()] if nxt else rest


class TestItem22TeacherLiveClass(unittest.TestCase):
    """کلاس زنده: ورود به صفحه نباید شروع/ثبت مالی انجام دهد."""

    def test_22a_dashboard_opens_pre_start_page_without_starting_endpoint(self):
        body = function_body(kt("TeacherDashboardActivity.kt"), "startLive")
        self.assertIn("LiveClassActivity::class.java", body)
        self.assertNotIn("liveApi.startLive", body,
                         "شروع جلسه باید پشت دکمهٔ شروع داخل صفحهٔ کلاس زنده باشد")
        self.assertNotIn('"LIVE_SESSION_ID"', body,
                         "ورود اولیه نباید session فعال را به صفحه تزریق کند")

    def test_22b_live_layout_has_start_and_cancel_actions(self):
        xml = layout("activity_live_class.xml")
        self.assertIn('android:id="@+id/btnStartLive"', xml)
        self.assertIn('android:id="@+id/btnCancelLive"', xml)
        self.assertIn("شروع کلاس", xml)
        self.assertIn("لغو", xml)

    def test_22c_live_activity_starts_only_from_start_button_and_cancel_is_separate(self):
        src = kt("LiveClassActivity.kt")
        body = function_body(src, "onCreate")
        self.assertIn("R.id.btnStartLive", body)
        self.assertIn("startLive", body)
        self.assertIn("R.id.btnCancelLive", body)
        self.assertIn("cancelLive", src)
        self.assertIn('"LIVE_SESSION_ID"', src)

    def test_22d_cancel_endpoint_does_not_finalize_attendance_or_finance(self):
        api = kt("LiveApi.kt")
        self.assertIn('attendance/{session_id}/cancel_live', api)
        attendance = py("routers/attendance.py")
        self.assertIn('@router.post("/attendance/{session_id}/cancel_live")', attendance)
        start = attendance.index('@router.post("/attendance/{session_id}/cancel_live")')
        end = attendance.find('@router.', start + 10)
        body = attendance[start:end if end != -1 else None]
        self.assertNotIn("finalize_live_session", body)
        self.assertIn('"CANCELLED"', body)

    def test_22e_end_flushes_final_roster_before_financial_finalize(self):
        src = kt("LiveClassActivity.kt")
        body = function_body(src, "endLive")
        self.assertIn("api.saveLiveStatus(liveSessionId, finalPayload)", body)
        self.assertIn("api.endLive(liveSessionId", body)
        self.assertLess(
            body.index("api.saveLiveStatus(liveSessionId, finalPayload)"),
            body.index("api.endLive(liveSessionId"),
            "پایان جلسه نباید قبل از ذخیره‌ی آخرین وضعیت حضور اجرا شود",
        )

    def test_22f_live_actions_use_live_session_identifier_and_legacy_fallback_is_server_side(self):
        api = kt("LiveApi.kt")
        self.assertIn('Path("session_id") sessionId: Int', api)
        attendance = py("routers/attendance.py")
        self.assertIn("_resolve_live_session_for_action", attendance)
        self.assertIn('LiveSession.course_id == identifier', attendance)


class TestItem23BulkStudentEnrollment(unittest.TestCase):
    """ثبت چند دانش‌آموز با چک‌باکس، بدون حذف مسیر ثبت تکی."""

    def test_23a_setup_dialog_has_multi_selection_surface(self):
        xml = layout("dialog_search_student.xml")
        self.assertIn('android:id="@+id/llStudentMultiSelect"', xml)
        self.assertIn('android:id="@+id/tvBulkSelectionSummary"', xml)

    def test_23b_single_endpoint_remains_and_bulk_endpoint_is_declared(self):
        src = kt("ClassSetupActivity.kt")
        self.assertIn('@POST("enrollments/add")', src)
        self.assertIn('@POST("enrollments/add_bulk")', src)
        self.assertIn("addToClass(", src)
        self.assertIn("addMultipleToClass(", src)
        self.assertIn("CheckBox", src)

    def test_23c_bulk_response_contains_added_and_rejected_reasons(self):
        models = kt("AppModels.kt")
        self.assertIn("BulkEnrollmentResponse", models)
        self.assertIn("added_count", models)
        self.assertIn("rejected_count", models)
        self.assertIn("rejected", models)

        server = py("routers/classes.py")
        self.assertIn('@router.post("/enrollments/add_bulk")', server)
        start = server.index('@router.post("/enrollments/add_bulk")')
        body = server[start:]
        self.assertIn("added_count", body)
        self.assertIn("rejected_count", body)
        self.assertIn("reason", body)

    def test_23d_bulk_path_reuses_single_enrollment_rules(self):
        server = py("routers/classes.py")
        start = server.index('@router.post("/enrollments/add_bulk")')
        body = server[start:]
        self.assertIn("add_enrollment(", body,
                         "مسیر گروهی باید همان validation و ruleهای مسیر تکی را reuse کند")


if __name__ == "__main__":
    unittest.main()
