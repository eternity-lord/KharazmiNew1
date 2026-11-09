"""Run the Kotlin/Gson contract simulator against every unique Retrofit call."""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import threading
from pathlib import Path

from fastapi.testclient import TestClient

from ..clock import freeze_loaded_server_modules
from ..kotlin_contract import ContractIssue, audit_payload, discover_models
from ..seed import seed_database
from .common import block_external_network_calls, inventory, prepare_valid_route_fixture, request_parts, role_for

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent


def norm(path: str) -> str:
    path = path.strip().lstrip("/")
    return re.sub(r"\{[^}]+\}", "{}", path).rstrip("/")


def rows() -> list[dict[str, str]]:
    """Use live Retrofit declarations; the phase-zero CSV is historical."""
    from scripts.validate_app_map import parse_retrofit_calls

    return [
        {
            "interface/method": f"{call['interface']}.{call['function']}",
            "method": call["method"],
            "path": call["path"],
            "response class": call["response_type"],
            "file:line": call["file:line"],
        }
        for call in parse_retrofit_calls()
    ]


def model_name(response_class: str) -> str | None:
    response_class = response_class.strip().rstrip("?")
    match = re.fullmatch(r"(?:Response|List|MutableList)\s*<\s*(.+)\s*>", response_class)
    if match:
        response_class = match.group(1).strip()
    if response_class in {"ResponseBody", "Unit", "<unknown>"}:
        return None
    return response_class.rstrip("?")


def _sample_payload(value, depth: int = 0):
    if depth >= 4:
        return "<nested>"
    if isinstance(value, dict):
        return {str(key): _sample_payload(item, depth + 1) for key, item in list(value.items())[:30]}
    if isinstance(value, list):
        return [_sample_payload(item, depth + 1) for item in value[:3]]
    if isinstance(value, str) and len(value) > 120:
        return value[:117] + "..."
    return value


def _wire_shape(payload):
    if isinstance(payload, dict):
        return {"kind": "object", "keys": list(payload)}
    if isinstance(payload, list):
        first = payload[0] if payload else None
        return {"kind": "array", "length": len(payload), "item_keys": list(first) if isinstance(first, dict) else None}
    if payload is None:
        return {"kind": "empty-or-non-json"}
    return {"kind": type(payload).__name__}


def run():
    with tempfile.TemporaryDirectory(prefix="route-audit-contract-") as tmp:
        os.environ["JWT_SECRET_KEY"] = "route-audit-contract-secret-" + "x" * 40
        os.environ["FCM_SERVER_KEY"] = ""
        db_path = Path(tmp) / "contract.db"
        manifest = seed_database(db_path)
        sys.path.insert(0, str(ROOT / "Kharazmi_Server"))
        block_external_network_calls()
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
        import models  # type: ignore
        from dependencies import create_jwt_token  # type: ignore
        client = TestClient(main.app, raise_server_exceptions=False)
        openapi = client.get("/openapi.json").json()
        baseline = db_path.read_bytes()
        def reset():
            main.models.engine.dispose(); db_path.write_bytes(baseline)
        user_ids = {"admin": 1, "secretary": 2, "teacher": 3, "student": 4, "parent": 5}
        def headers(role):
            if role == "public":
                return {}
            token = create_jwt_token(user_ids[role], role)
            db = models.SessionLocal(); db.add(models.UserSession(user_id=user_ids[role], teacher_id=1 if role == "teacher" else None, sub_role=role, token=token)); db.commit(); db.close()
            return {"Authorization": f"Bearer {token}"}
        server = {(r["method"], norm(r["path کامل"])): r for r in inventory()}
        source_calls = rows()
        unique_call_pairs = {(row["method"], row["path"]) for row in source_calls}
        unique_static_routes = {
            (row["method"], norm(row["path"]))
            for row in source_calls if not row["path"].startswith("dynamic ")
        }
        models_found = discover_models()
        out = {
            "declarations": len(source_calls),
            "unique_calls": len(unique_call_pairs),
            "unique_static_routes": len(unique_static_routes),
            "duplicate_method_path_declarations": len(source_calls) - len(unique_call_pairs),
            "entries": [],
            "counts": {
                "dynamic": 0, "unmatched": 0, "route_non_success": 0,
                "successful_non_json": 0, "empty_json_body": 0,
                "parse": 0, "npe": 0, "silent_zero": 0,
                "missing_key": 0, "simulation_gap": 0,
            },
        }
        for android_row in source_calls:
            method, android_path = android_row["method"], android_row["path"]
            if android_path.startswith("dynamic "):
                out["counts"]["dynamic"] += 1
                out["entries"].append({"method": method, "path": android_path, "android_call": android_row["interface/method"], "android_source": android_row["file:line"], "response_class": android_row["response class"], "status": None, "dynamic": True, "issues": []})
                continue
            key = (method, norm(android_path))
            server_row = server.get(key)
            if server_row is None:
                out["counts"]["unmatched"] += 1
                out["entries"].append({"method": method, "path": android_path, "android_call": android_row["interface/method"], "android_source": android_row["file:line"], "response_class": android_row["response class"], "status": None, "unmatched": True, "issues": []})
                continue
            reset()
            role = role_for(server_row)
            url, params, _, body = request_parts(openapi, server_row)
            prepare_valid_route_fixture(server_row, models)
            try:
                response = client.request(method, url, params=params, json=body, headers=headers(role))
                status = response.status_code
                try: payload = response.json()
                except Exception: payload = None
            except Exception as exc:
                out["entries"].append({"method": method, "path": android_path, "response_class": android_row["response class"], "status": None, "error": repr(exc), "issues": []})
                continue
            model = model_name(android_row["response class"])
            entry = {
                "method": method,
                "path": android_path,
                "android_call": android_row["interface/method"],
                "server_path": server_row["path کامل"],
                "handler": server_row["handler"],
                "response_class": android_row["response class"],
                "android_source": android_row["file:line"],
                "role": role,
                "status": status,
                "model": model,
                "wire_shape": _wire_shape(payload),
                "issues": [],
            }
            if status < 200 or status >= 300:
                out["counts"]["route_non_success"] += 1
                entry["route_non_success"] = True
                out["entries"].append(entry)
                continue
            if model is None:
                # Unit and ResponseBody endpoints intentionally do not produce a
                # JSON contract (logout and downloads/exports respectively).
                if payload is None and android_row["response class"] != "Unit":
                    out["counts"]["successful_non_json"] += 1
                    entry["non_json_expected"] = True
                elif payload is not None:
                    entry["sample_payload"] = _sample_payload(payload)
                out["entries"].append(entry)
                continue
            if payload is None:
                issue = {
                    "kind": "empty-json-body",
                    "field": "",
                    "detail": f"2xx response could not be decoded as JSON for Kotlin {android_row['response class']}",
                    "line": 0,
                    "source": android_row["file:line"],
                }
                entry["issues"] = [issue]
                entry["empty_json_body"] = True
                out["counts"]["empty_json_body"] += 1
                out["counts"]["parse"] += 1
                out["entries"].append(entry)
                continue
            entry["sample_payload"] = _sample_payload(payload)
            if model not in models_found:
                entry["issues"] = [{
                    "kind": "model-not-found", "field": "",
                    "detail": f"Kotlin model {model} was not discovered in Android source parser",
                    "line": 0, "source": android_row["file:line"],
                }]
                out["counts"]["missing_key"] += 1
                out["entries"].append(entry)
                continue
            payloads = payload if android_row["response class"].startswith(("List<", "MutableList<")) and isinstance(payload, list) else [payload]
            issues = []
            for item in payloads:
                if isinstance(item, dict):
                    issues.extend(audit_payload(model, item, models_found))
                else:
                    issues.append(ContractIssue(
                        "", "type-mismatch",
                        f"Gson expected an object for Kotlin {model}; got {type(item).__name__}",
                        0, android_row["file:line"],
                    ))
            entry["issues"] = [issue.__dict__ for issue in issues]
            for issue in issues:
                if issue.kind in ("int-parse", "long-overflow", "long-parse", "float-parse", "type-mismatch"):
                    out["counts"]["parse"] += 1
                elif issue.kind in ("missing-non-null", "null-non-null"):
                    out["counts"]["npe"] += 1
                elif issue.kind in ("missing-list", "null-list"):
                    out["counts"]["missing_key"] += 1
                elif issue.kind == "silent-zero":
                    out["counts"]["silent_zero"] += 1
                elif issue.kind == "unmodeled-default":
                    out["counts"]["simulation_gap"] += 1
            out["entries"].append(entry)
        OUT.joinpath("contract-report.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return out


if __name__ == "__main__":
    result = run()
    print(json.dumps(result["counts"] | {
        "unique_calls": result["unique_calls"],
        "unique_static_routes": result["unique_static_routes"],
        "declarations": result["declarations"],
    }, ensure_ascii=False))
