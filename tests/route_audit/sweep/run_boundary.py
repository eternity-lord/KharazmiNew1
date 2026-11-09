"""Run focused route and Gson checks against the independent boundary seed."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from ..clock import freeze_loaded_server_modules
from ..kotlin_contract import audit_payload
from .common import block_external_network_calls
from .boundary_seed import (
    BOUNDARY_AMOUNT,
    BOUNDARY_EXAM_ID,
    BOUNDARY_HOMEWORK_ID,
    seed_boundary_database,
)

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent


def run() -> dict:
    with tempfile.TemporaryDirectory(prefix="route-audit-boundary-") as tmp:
        os.environ["JWT_SECRET_KEY"] = "route-audit-boundary-secret-" + "x" * 40
        db_path = Path(tmp) / "boundary.db"
        manifest = seed_boundary_database(db_path)
        sys.path.insert(0, str(ROOT / "Kharazmi_Server"))
        block_external_network_calls()
        import threading

        original_start = threading.Thread.start

        def no_live_auto_end_worker(thread, *args, **kwargs):
            if thread.name == "live-session-auto-ender":
                return None
            return original_start(thread, *args, **kwargs)

        try:
            threading.Thread.start = no_live_auto_end_worker
            import main  # type: ignore
        finally:
            threading.Thread.start = original_start
        freeze_loaded_server_modules()

        client = TestClient(main.app, raise_server_exceptions=False)
        headers = {
            role: {"Authorization": f"Bearer {token}"}
            for role, token in manifest["roles"].items()
        }

        calls = [
            ("GET", "/exams/student/list", headers["student"], None),
            ("GET", "/admin/transactions/list", headers["admin"], None),
            ("GET", "/homework/parent/child/1", headers["parent"], None),
            ("GET", "/teachers/1/incomplete_classes", headers["teacher"], None),
        ]
        route_results = []
        for method, path, request_headers, body in calls:
            response = client.request(method, path, headers=request_headers, json=body)
            try:
                payload = response.json()
            except Exception:
                payload = None
            route_results.append({
                "method": method,
                "path": path,
                "status": response.status_code,
                "json": payload,
                "status_500": response.status_code >= 500,
            })

        exams = next(row for row in route_results if row["path"] == "/exams/student/list")["json"]
        transactions = next(row for row in route_results if row["path"] == "/admin/transactions/list")["json"]
        homework = next(row for row in route_results if row["path"] == "/homework/parent/child/1")["json"]
        incomplete = next(row for row in route_results if row["path"] == "/teachers/1/incomplete_classes")["json"]
        values = {
            "exam_99_max_score": next(item["max_score"] for item in exams if item["id"] == BOUNDARY_EXAM_ID),
            "transaction_99_amount": next(item["amount"] for item in transactions if item["id"] == 99),
            "transaction_99_date": next(item["date"] for item in transactions if item["id"] == 99),
            "transaction_99_description": next(item["description"] for item in transactions if item["id"] == 99),
            "homework_99_description": next(item["description"] for item in homework if item["id"] == BOUNDARY_HOMEWORK_ID),
            "homework_99_due_date": next(item["due_date"] for item in homework if item["id"] == BOUNDARY_HOMEWORK_ID),
            "incomplete_students_preview_are_lists": all(isinstance(item["students_preview"], list) for item in incomplete),
        }
        vectors = {
            "decimal_max_score": audit_payload("ParentExamItem", {
                "course_title": "ریاضی", "title": "مرزی", "date": "1405/08/01", "max_score": 12.5,
            }),
            "large_long_amount": audit_payload("TransactionFullItem", {
                "id": 99, "student_id": 1, "student_name": "دانش‌آموز تست 1", "course_id": None,
                "course_name": "---", "amount": BOUNDARY_AMOUNT, "date": "", "description": None,
                "type": "deposit", "remittance_number": None,
            }),
            "null_optional": audit_payload("ParentStudentInfo", {
                "name": "دانش‌آموز تست 1", "national_code": "0020000001",
                "parent_mobile": "09360000001", "profile_image": None,
            }),
            "empty_string": audit_payload("HomeworkItem", {
                "id": 99, "course_id": 1, "course_title": "ریاضی پایه فعال", "title": "مرزی",
                "description": "", "due_date": "", "max_score": 20.0, "status": "pending",
                "score": None, "feedback": None,
            }),
            "empty_list": audit_payload("TeacherClassItem", incomplete[0]),
        }
        q006_unresolved_fields = {
            "is_admin_approved", "is_suspended", "total_debt", "debt_to_teacher", "debt_to_institute"
        }
        confirmed_issues = [
            issue
            for name, issues in vectors.items()
            for issue in issues
            if not (name == "empty_list" and issue.field in q006_unresolved_fields)
        ]
        result = {
            "fixture": manifest["boundary"],
            "routes": route_results,
            "values": values,
            "gson_vectors": {
                name: [issue.__dict__ for issue in issues]
                for name, issues in vectors.items()
            },
            "gson_issue_count": sum(len(issues) for issues in vectors.values()),
            "confirmed_contract_issue_count": len(confirmed_issues),
            "confirmed_contract_issues": [issue.__dict__ for issue in confirmed_issues],
            "unresolved_question": {
                "id": "Q-006",
                "fields": sorted(q006_unresolved_fields),
                "reason": "The incomplete-class dialog consumes only id/title/code; no visible behavior is yet established for these five model defaults.",
            },
            "expected": {
                "decimal_max_score": 12.5,
                "large_long_amount": BOUNDARY_AMOUNT,
                "empty_strings": {"transaction_date": "", "homework_due_date": ""},
                "empty_lists_are_lists": True,
                "gson_issue_count": 5,
                "confirmed_contract_issue_count": 0,
                "unresolved_question": "Q-006",
            },
        }
        OUT.joinpath("boundary-report.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return result


if __name__ == "__main__":
    result = run()
    print(json.dumps({
        "routes": len(result["routes"]),
        "status_500": sum(row["status_500"] for row in result["routes"]),
        "gson_candidate_count": result["gson_issue_count"],
        "confirmed_contract_issue_count": result["confirmed_contract_issue_count"],
        "values": result["values"],
    }, ensure_ascii=False))
