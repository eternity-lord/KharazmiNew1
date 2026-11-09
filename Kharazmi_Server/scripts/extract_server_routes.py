#!/usr/bin/env python3
"""Extract the registered FastAPI route surface for comparison with the hand map.

Run from the repository root with a disposable database, for example:
  DATABASE_URL=sqlite:////tmp/kharazmi-real-current.db \
  JWT_SECRET_KEY=ci-only-test-secret-not-production \
  PYTHONPATH=Kharazmi_Server \
  python Kharazmi_Server/scripts/extract_server_routes.py \
      --output docs/app-map/server-routes-extracted.csv

Importing ``main`` follows the application's normal startup path.  Therefore the
caller must point DATABASE_URL at a copy, never at the institute database.
"""
from __future__ import annotations

import argparse
import ast
import csv
import inspect
import json
import sys
from pathlib import Path
from typing import Any


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _json_schema_summary(schema: dict[str, Any] | None) -> str:
    if not schema:
        return "نامشخص"
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]
    if schema.get("type") == "array":
        return "List[" + _json_schema_summary(schema.get("items")) + "]"
    if schema.get("type") == "object":
        props = schema.get("properties") or {}
        keys = list(props.keys())
        return "object{" + ",".join(keys[:60]) + (",…" if len(keys) > 60 else "") + "}"
    return str(schema.get("type") or schema)


def _operation_inputs(operation: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in operation.get("parameters", []):
        schema = item.get("schema") or {}
        parts.append(
            f"{item.get('in')}:{item.get('name')}:{_json_schema_summary(schema)}"
            + (":required" if item.get("required") else ":optional")
        )
    body = operation.get("requestBody")
    if body:
        content = body.get("content") or {}
        schema = next(iter(content.values()), {}).get("schema") if content else None
        parts.append("body:" + _json_schema_summary(schema) + (":required" if body.get("required") else ":optional"))
    return " | ".join(parts) or "none"


def _keys_from_ast(node: ast.AST) -> list[str]:
    keys: list[str] = []
    if isinstance(node, ast.Dict):
        for key in node.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                keys.append(key.value)
    return keys


def _static_return_keys(source: str) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return "نامشخص"
    keys: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and node.value is not None:
            keys.extend(_keys_from_ast(node.value))
    unique = list(dict.fromkeys(keys))
    return ",".join(unique[:100]) + (",…" if len(unique) > 100 else "") if unique else "نامشخص"


def _source_facts(source: str) -> tuple[str, str, str, str]:
    """Collect literal ORM and side-effect references; never invent a table name."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return "نامشخص", "نامشخص", "نامشخص", "نامشخص"
    reads: set[str] = set()
    writes: set[str] = set()
    columns: set[str] = set()
    effects: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Attribute):
                method = fn.attr
                if method in {"query", "get", "scalar", "count", "first", "all", "one"} and isinstance(fn.value, ast.Name) and fn.value.id == "db":
                    for arg in node.args:
                        if isinstance(arg, ast.Name):
                            reads.add(arg.id)
                        elif isinstance(arg, ast.Attribute):
                            reads.add(ast.unparse(arg))
                if method in {"add", "add_all", "delete", "commit", "flush", "refresh", "execute", "bulk_save_objects"} and isinstance(fn.value, ast.Name) and fn.value.id == "db":
                    effects.add("db." + method)
                    for arg in node.args:
                        text = ast.unparse(arg)
                        if method in {"add", "add_all", "delete", "bulk_save_objects"}:
                            writes.add(text)
            name = ast.unparse(fn)
            if any(token in name.lower() for token in ("sms", "notification", "push", "send_", "remind")):
                effects.add(name)
            if any(token in name for token in ("FileResponse", "StreamingResponse", "HTMLResponse", "Workbook", "get_pdf", "render")):
                effects.add(name)
        if isinstance(node, ast.Attribute):
            attr = node.attr
            if attr in {"wallet_teacher", "wallet_institute", "wallet_balance", "total_paid", "amount", "enrollment_id", "course_id", "share_teacher", "share_institute", "is_deleted", "is_reversed"}:
                columns.add(attr)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute):
                    columns.add(ast.unparse(target))
    return (
        ";".join(sorted(reads)) or "نامشخص",
        ";".join(sorted(writes)) or "نامشخص",
        ";".join(sorted(columns)) or "نامشخص",
        ";".join(sorted(effects)) or "نامشخص",
    )


def extract(output: Path | None) -> list[dict[str, str]]:
    root = _project_root()
    sys.path.insert(0, str(root / "Kharazmi_Server"))
    from fastapi.routing import APIRoute  # imported after project path is set
    import main

    document = main.app.openapi()
    rows: list[dict[str, str]] = []

    def registered_routes(routes, inherited_prefix=""):
        # FastAPI 0.141 stores included routers as _IncludedRouter objects;
        # their original_router.routes contain the APIRoute objects.  The
        # include context carries a prefix that is not always copied into
        # APIRoute.path, so retain it explicitly for the full-path contract.
        for item in routes:
            if isinstance(item, APIRoute):
                full_path = inherited_prefix.rstrip("/") + item.path
                yield item, (full_path or "/")
            else:
                nested = getattr(item, "original_router", None)
                if nested is not None:
                    context = getattr(item, "include_context", None)
                    prefix = getattr(context, "prefix", "") if context is not None else ""
                    yield from registered_routes(nested.routes, inherited_prefix + prefix)

    for route, full_path in registered_routes(main.app.routes):
        endpoint = route.endpoint
        while hasattr(endpoint, "__wrapped__"):
            endpoint = endpoint.__wrapped__
        source_file = inspect.getsourcefile(endpoint)
        if not source_file:
            source_file = "نامشخص"
            line = "نامشخص"
            source = ""
        else:
            try:
                source_lines, line = inspect.getsourcelines(endpoint)
                source = "".join(source_lines)
            except (OSError, TypeError):
                line = "نامشخص"
                source = ""
        if source_file == "نامشخص":
            relative = source_file
        else:
            resolved_source = Path(source_file).resolve()
            try:
                relative = str(resolved_source.relative_to(root))
            except ValueError:
                relative = str(resolved_source)
        operation = next((document.get("paths", {}).get(full_path, {}).get(method.lower()) for method in route.methods), {}) or {}
        if not operation:
            operation = next((document.get("paths", {}).get(route.path, {}).get(method.lower()) for method in route.methods), {}) or {}
        reads, writes, columns, effects = _source_facts(source)
        rows.append({
            "method": ",".join(sorted(route.methods or [])),
            "path": full_path,
            "handler": f"{endpoint.__module__}.{endpoint.__qualname__}",
            "file:line": f"{relative}:{line}",
            "input": _operation_inputs(operation),
            "response_keys_or_schema": (_json_schema_summary((operation.get("responses") or {}).get("200", {}).get("content", {}).get("application/json", {}).get("schema")) if operation else "نامشخص") + "; static_return_keys=" + _static_return_keys(source),
            "db_reads_detected": reads,
            "db_writes_detected": writes,
            "columns_referenced": columns,
            "side_effects_detected": effects,
        })
    rows.sort(key=lambda row: (row["path"], row["method"]))
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["method"])
            writer.writeheader()
            writer.writerows(rows)
    return rows


def main_cli() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="CSV path; omit to print JSON")
    args = parser.parse_args()
    rows = extract(args.output)
    if args.output:
        print(f"wrote {len(rows)} routes to {args.output}")
    else:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main_cli())
