"""Run list scale checks against the independent 300-student fixture."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from ..clock import freeze_loaded_server_modules
from .common import block_external_network_calls
from .large_seed import seed_large_list_database

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent


def run() -> dict:
    with tempfile.TemporaryDirectory(prefix="route-audit-large-") as tmp:
        os.environ["JWT_SECRET_KEY"] = "route-audit-large-secret-" + "x" * 40
        manifest = seed_large_list_database(Path(tmp) / "large.db")
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
        response = {}
        students = client.get("/students/search_simple", params={"query": "دانش‌آموز"}, headers=headers["admin"])
        classes = client.get("/classes/list", headers=headers["admin"])
        classes_filtered = client.get("/classes/list", params={"student_name": "تست 300"}, headers=headers["admin"])
        transactions = client.get("/admin/transactions/list", headers=headers["admin"])
        debtors = client.get("/reports/debtors", headers=headers["admin"])
        sessions = client.get("/teachers/1/pending_settlement", headers=headers["teacher"])
        for name, result in {
            "students": students, "classes": classes, "classes_filtered": classes_filtered,
            "transactions": transactions, "debtors": debtors, "sessions": sessions,
        }.items():
            try:
                payload = result.json()
            except Exception:
                payload = None
            response[name] = {"status": result.status_code, "payload": payload}
        response_summary = {}
        for name, row in response.items():
            payload = row["payload"]
            if isinstance(payload, list):
                response_summary[name] = {
                    "status": row["status"], "count": len(payload),
                    "first_ids": [item.get("id") for item in payload[:3] if isinstance(item, dict)],
                }
            else:
                pending = (payload or {}).get("pending_sessions", [])
                response_summary[name] = {
                    "status": row["status"], "pending_count": len(pending),
                    "first_session_ids": [item.get("session_id") for item in pending[:3]],
                }
        report = {
            "fixture": {"students": 300, "classes": 30, "extra_transactions": 300, "extra_sessions": 300},
            "responses": response_summary,
            "checks": {
                "student_limit_20": len(response["students"]["payload"]) == 20,
                "student_order_desc": [row["id"] for row in response["students"]["payload"]] == list(range(300, 280, -1)),
                "class_count_excludes_deleted": len(response["classes"]["payload"]) == 29,
                "class_order_desc": response["classes"]["payload"][0]["id"] == 30,
                "class_filter_exact": len(response["classes_filtered"]["payload"]) == 1 and response["classes_filtered"]["payload"][0]["id"] == 1,
                "transaction_count_and_order": len(response["transactions"]["payload"]) == 305 and response["transactions"]["payload"][0]["id"] == 399,
                "debtor_full_list": len(response["debtors"]["payload"]) >= 290,
                "session_order_desc": len(response["sessions"]["payload"]["pending_sessions"]) == 301 and response["sessions"]["payload"]["pending_sessions"][1]["session_id"] == 399,
            },
        }
        OUT.joinpath("large-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report


if __name__ == "__main__":
    report = run()
    print(json.dumps({"checks": report["checks"], "statuses": {k: v["status"] for k, v in report["responses"].items()}}, ensure_ascii=False))
