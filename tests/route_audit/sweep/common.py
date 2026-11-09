from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "Kharazmi_Server"


def block_external_network_calls() -> None:
    """Fail closed if provider code tries to send an SMS/push/HTTP request."""
    import requests
    import socket
    import urllib.request

    def blocked(*args, **kwargs):
        raise AssertionError("route-audit blocked an external network call")

    requests.post = blocked
    requests.request = blocked
    requests.sessions.Session.request = blocked
    urllib.request.urlopen = blocked
    socket.create_connection = blocked
    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked


def prepare_valid_route_fixture(row: dict[str, str], models) -> None:
    """Create per-request prerequisites without changing the canonical seed."""
    path = row.get("path کامل")
    if path not in {
        "/attendance/qr_check-in",
        "/classes/deletion_requests/{request_id}/approve",
        "/classes/deletion_requests/{request_id}/reject",
    }:
        return
    db = models.SessionLocal()
    try:
        if path == "/attendance/qr_check-in":
            from ..clock import FIXED_NOW
            from today_summary import jalali_date_string

            session = db.query(models.SessionLog).filter(models.SessionLog.session_code == 5001).one()
            session.date = jalali_date_string(FIXED_NOW.date())
            attendance = db.query(models.Attendance).filter(
                models.Attendance.session_id == session.id,
                models.Attendance.student_id == 1,
            ).one()
            # Exercise the successful reactivation branch, not duplicate-present 400.
            attendance.status = "Absent"
        else:
            if not db.query(models.ClassDeletionRequest).filter_by(id=1).first():
                db.add(models.ClassDeletionRequest(
                    id=1, course_id=1, requested_by_role="teacher",
                    requested_by_user_id=3, requested_by_teacher_id=1,
                    forgive_session_charges=False, status="pending", snapshot_json="{}",
                ))
        db.commit()
    finally:
        db.close()


def inventory() -> list[dict[str, str]]:
    with (ROOT / "docs/app-map/server-routes.csv").open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def role_for(row: dict[str, str]) -> str:
    """Choose the endpoint's intended actor (not the easiest token to pass)."""
    path = row["path کامل"]
    handler = row["handler"]

    # Truly public entry points are called without a session; body validity and
    # account/OTP state are audited separately from access-control security.
    if path in {
        "/auth/login", "/auth/student/login", "/auth/request_otp", "/auth/student/request_otp",
        "/parent/login", "/parent/request_otp", "/crm/register_online",
        "/finance/payment/callback", "/finance/mock_payment_page",
    } or path == "/teachers/register":
        return "public"

    # Explicit staff pages/routes win over names containing "student" or
    # "teacher". Finance statements are staff reports, not student self-service.
    if path.startswith(("/admin", "/config", "/dashboard")):
        return "admin"
    if path in {
        "/reports/student_statement", "/reports/student_statement/print",
        "/students/{student_id}/communication_history", "/teachers/list/excel",
        "/teachers/update/{teacher_id}", "/teachers/{id}/upload_photo",
        "/teachers/{teacher_id}/settle",
        "/teachers/{teacher_id}/settlements/{settlement_id}/edit",
        "/teachers/{teacher_id}/settlements/{settlement_id}/reverse",
        "/teachers/{teacher_id}/collaboration_summary",
    }:
        return "admin"

    if "/finance/parent" in path or path.startswith("/parent") or path.startswith("/homework/parent/") or ".parent." in handler:
        return "parent"
    if path.endswith("/grade") and path.startswith("/homework/submissions/"):
        return "teacher"
    if path.endswith("/request_delete") and path.startswith("/classes/"):
        return "teacher"
    if (
        "/finance/student/" in path or "/students/my_profile" in path
        or "/students/{student_id}" in path or "/students/{id}/" in path
        or "/attendance/student_history" in path or "qr_check-in" in path
        or "/exams/student" in path or "/exams/attempts" in path
        or "/homework/student" in path or "/homework/submissions/" in path
        or ".get_student_exams" in handler
    ):
        return "student"
    if "attendance/live/current" in path or any(token in path for token in ("start_live", "end_live", "cancel_live", "live_status")):
        return "teacher"
    if any(token in path for token in ("/exams/create", "/exams/{id}/questions", "/homework/create", "/homework/{id}", "/homework/submissions/{sub_id}/grade")):
        return "teacher"
    if ".teacher" in handler and "/admin" not in path:
        return "teacher"
    return "admin"


def resolve_schema(openapi: dict[str, Any], schema: dict[str, Any] | None) -> dict[str, Any]:
    if not schema:
        return {}
    if "$ref" in schema:
        return openapi["components"]["schemas"].get(schema["$ref"].rsplit("/", 1)[-1], {})
    if "anyOf" in schema:
        choices = [item for item in schema["anyOf"] if item.get("type") != "null"]
        return resolve_schema(openapi, choices[0] if choices else {})
    return schema


def example_value(openapi: dict[str, Any], schema: dict[str, Any], field_name: str = "") -> Any:
    schema = resolve_schema(openapi, schema)
    if "example" in schema: return schema["example"]
    if "default" in schema: return schema["default"]
    if "enum" in schema and schema["enum"]: return schema["enum"][0]
    typ = schema.get("type")
    lname = field_name.lower()
    if typ == "object" or "properties" in schema:
        return {name: example_value(openapi, child, name) for name, child in schema.get("properties", {}).items() if name in schema.get("required", []) or "default" in child}
    if typ == "array": return [example_value(openapi, schema.get("items", {}), field_name)]
    if typ == "integer":
        if "student" in lname: return 1
        if "course" in lname or "class" in lname: return 1
        if "session_code" in lname: return 5001
        return 1
    if typ == "number": return 1.0
    if typ == "boolean": return False
    if typ == "string":
        if "date" in lname: return "1405/06/20"
        if "time" in lname: return "16:00"
        if "status" in lname: return "Present"
        if "mode" in lname: return "metadata_only"
        if "type" in lname: return "deposit"
        if "target_wallet" in lname: return "institute"
        if "payment_method" in lname: return "نقدی"
        if "token" in lname: return "route-audit-token"
        if "mobile" in lname: return "09120000001"
        return "route-audit"
    return None


def path_value(name: str) -> str:
    lname = name.lower()
    if "session_code" in lname: return "5001"
    if "course" in lname or "class" in lname: return "1"
    if "student" in lname: return "1"
    if "transaction" in lname: return "1"
    if "installment" in lname: return "1"
    if "exam" in lname or "attempt" in lname: return "1"
    if "request" in lname: return "1"
    return "1"


def build_url(path: str, *, invalid_path: bool = False) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if invalid_path:
            return "not-an-integer"
        if "deleted_classes" in path and name == "course_id":
            return "4"  # canonical seed course 4 is the archived/deleted class
        return path_value(name)
    return re.sub(r"\{([^}]+)\}", replace, path)


def operation(openapi: dict[str, Any], row: dict[str, str]) -> dict[str, Any]:
    return openapi["paths"][row["path کامل"]][row["method"].lower()]


def request_parts(openapi: dict[str, Any], row: dict[str, str], *, invalid: bool = False) -> tuple[str, dict[str, Any], dict[str, Any], Any]:
    op = operation(openapi, row)
    url = build_url(row["path کامل"], invalid_path=invalid)
    params: dict[str, Any] = {}
    for param in op.get("parameters", []):
        if param.get("in") == "query" and param.get("required") and not invalid:
            params[param["name"]] = example_value(openapi, param.get("schema", {}), param["name"])
    body = None
    request_body = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
    if request_body is not None:
        body = example_value(openapi, request_body)
        if invalid:
            resolved = resolve_schema(openapi, request_body)
            required = resolved.get("required", [])
            if required:
                body = {required[0]: []}
            else:
                body = {}
        elif row["path کامل"] == "/auth/change-password":
            body = {
                "mobile": "audit-admin",
                "old_password": "Admin-Route-1405!",
                "new_password": "Admin-Route-1405-Changed!",
            }
        elif row["path کامل"] == "/auth/change-mobile":
            body = {
                "current_mobile": "audit-admin",
                "password": "Admin-Route-1405!",
                "new_mobile": "09379999999",
            }
        elif row["path کامل"] == "/auth/student/request_otp":
            body = {"mobile": "09350000001"}
        elif row["path کامل"] == "/parent/request_otp":
            body = {"mobile": "09360000001"}
    if not invalid and row["path کامل"] == "/finance/student_class_status":
        params["course_id"] = 1
    if invalid and not request_body:
        required_query = [p for p in op.get("parameters", []) if p.get("in") == "query" and p.get("required")]
        if required_query:
            params[required_query[0]["name"]] = []
    return url, params, {"content-type": "application/json"} if body is not None else {}, body


def shape(response) -> tuple[bool, str, Any]:
    try:
        value = response.json()
    except Exception:
        return False, "non-json", None
    if value is None: return True, "null", value
    if isinstance(value, list): return True, "list", value
    if isinstance(value, dict): return True, "object", value
    return True, "scalar", value
