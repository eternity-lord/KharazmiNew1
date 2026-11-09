#!/usr/bin/env python3
"""Validate stage-zero route/Retrofit mapping against the checked-out source.

The server portion imports ``main`` only after selecting a disposable SQLite
file. It never opens or migrates ``Kharazmi_Server/gaj_db.db``. With ``--write``
the helper writes a current Android declaration/field inventory and a current
server-vs-Android classification overlay under ``docs/route-tests/``; the older
``docs/app-map`` inputs remain untouched as historical map artifacts.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import io
import json
import os
import re
import sys
import tempfile
import threading
from collections import Counter
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SERVER = ROOT / "Kharazmi_Server"
ANDROID_SRC = ROOT / "KharazmiAdmin/app/src/main/java"
ROUTES_CSV = ROOT / "docs/app-map/server-routes.csv"
ANDROID_CSV = ROOT / "docs/app-map/android-api-calls.csv"
OLD_MISMATCHES = ROOT / "docs/app-map/mismatches.md"
OUT_DIR = ROOT / "docs/route-tests"
DYNAMIC_URL = "dynamic (@Url/نامشخص)"


def normalize_path(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", path.strip().lstrip("/")).rstrip("/")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _strip_line_comment(line: str) -> str:
    """Strip Kotlin // comments outside strings (annotation strings are retained)."""
    in_quote = False
    escaped = False
    for index in range(len(line) - 1):
        char = line[index]
        if in_quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_quote = False
        elif char == '"':
            in_quote = True
        elif line[index:index + 2] == "//":
            return line[:index]
    return line


def _matching_parenthesis(text: str, opening: int) -> int:
    depth = 1
    cursor = opening + 1
    quote = False
    escaped = False
    while cursor < len(text):
        if quote:
            char = text[cursor]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quote = False
            cursor += 1
            continue
        if text.startswith("//", cursor):
            newline = text.find("\n", cursor + 2)
            cursor = len(text) if newline < 0 else newline + 1
            continue
        if text.startswith("/*", cursor):
            end = text.find("*/", cursor + 2)
            cursor = len(text) if end < 0 else end + 2
            continue
        char = text[cursor]
        if char == '"':
            quote = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return cursor
        cursor += 1
    return len(text)

def _signature(lines: list[str], annotation_line: int) -> tuple[str, str]:
    """Return interface method and declared response type after a Retrofit annotation."""
    tail = "\n".join(lines[annotation_line + 1:min(len(lines), annotation_line + 40)])
    function = re.search(r"\b(?:suspend\s+)?fun\s+([A-Za-z_$][\w$]*)\s*\(", tail)
    if not function:
        return "<unknown>", "<unknown>"
    opening = tail.find("(", function.start())
    closing = _matching_parenthesis(tail, opening)
    after = tail[closing + 1:].lstrip()
    if not after.startswith(":"):
        return function.group(1), "Unit"
    response = after[1:].lstrip()
    depth = 0
    quote = False
    escaped = False
    end = len(response)
    for index, char in enumerate(response):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quote = False
            continue
        if char == '"':
            quote = True
        elif char == "<":
            depth += 1
        elif char == ">":
            depth = max(0, depth - 1)
        elif depth == 0 and char in "=\n{;":
            end = index
            break
    return function.group(1), re.sub(r"\s+", " ", response[:end]).strip()


def parse_retrofit_calls(root: Path = ANDROID_SRC) -> list[dict[str, str]]:
    """Extract Retrofit method/path/response/function/file:line from Kotlin.

    Annotation arguments are balanced across lines and `//`/`/* */` comments are
    ignored outside string literals. This intentionally inventories declarations
    from source instead of trusting the historical phase-zero CSV.
    """
    annotation = re.compile(r"^\s*@(?:retrofit2\.http\.)?(GET|POST|PUT|DELETE)\b")
    string = re.compile(r'"((?:\\.|[^"\\])*)"')
    rows: list[dict[str, str]] = []
    for path in sorted(root.rglob("*.kt")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, raw_line in enumerate(lines):
            cleaned = _strip_line_comment(raw_line)
            match = annotation.match(cleaned)
            if not match:
                continue
            method = match.group(1)
            first_tail = cleaned[match.end():]
            args = ""
            if first_tail.lstrip().startswith("("):
                annotation_text = "\n".join(
                    _strip_line_comment(line)
                    for line in lines[index:min(len(lines), index + 20)]
                )
                opening = annotation_text.find("(", match.end())
                closing = _matching_parenthesis(annotation_text, opening)
                args = annotation_text[opening + 1:closing]
            literal = string.search(args)
            following = "\n".join(lines[index + 1:min(len(lines), index + 50)])
            if literal:
                endpoint = literal.group(1).replace(r"\/", "/")
            elif re.search(r"@(?:retrofit2\.http\.)?Url\b", following):
                endpoint = DYNAMIC_URL
            else:
                endpoint = "<missing-path>"
            function, response_type = _signature(lines, index)
            interface_name = "<unknown>"
            prefix = "\n".join(lines[:index])
            declarations = list(re.finditer(r"\binterface\s+([A-Za-z_$][\w$]*)\b", prefix))
            if declarations:
                interface_name = declarations[-1].group(1)
            rows.append({
                "method": method,
                "path": endpoint,
                "function": function,
                "response_type": response_type,
                "interface": interface_name,
                "file:line": f"{path.relative_to(ROOT)}:{index + 1}" if path.is_relative_to(ROOT) else f"{path}:{index + 1}",
            })
    return rows

def compare_retrofit_map(
    source_calls: Iterable[dict[str, str]] | None = None,
    android_rows: list[dict[str, str]] | None = None,
    server_rows: list[dict[str, str]] | None = None,
) -> dict:
    calls = list(source_calls if source_calls is not None else parse_retrofit_calls())
    android = android_rows if android_rows is not None else read_csv(ANDROID_CSV)
    server = server_rows if server_rows is not None else read_csv(ROUTES_CSV)
    source_counter = Counter((row["method"], row["path"]) for row in calls)
    map_counter = Counter((row["method"], row["path"]) for row in android)
    server_keys = {(row["method"], normalize_path(row["path کامل"])) for row in server}
    static_calls = {(method, normalize_path(path)) for method, path in source_counter if path != DYNAMIC_URL}
    server_only = server_keys - static_calls
    android_only = static_calls - server_keys
    return {
        "retrofit_declarations_source": len(calls),
        "retrofit_declarations_map": len(android),
        "retrofit_source_map_exact": source_counter == map_counter,
        "retrofit_source_map_missing": list((map_counter - source_counter).elements()),
        "retrofit_source_map_extra": list((source_counter - map_counter).elements()),
        "retrofit_unique_calls_source": len(source_counter),
        "retrofit_unique_calls_map": len(map_counter),
        "dynamic_url_declarations": sum(1 for _, path in source_counter if path == DYNAMIC_URL),
        "static_unique_calls": len({(method, normalize_path(path)) for method, path in source_counter if path != DYNAMIC_URL}),
        "server_routes": len(server_keys),
        "server_only_routes": len(server_only),
        "server_only_list": sorted(server_only),
        "android_only_routes": len(android_only),
        "android_only_list": sorted(android_only),
    }


def live_server_routes() -> set[tuple[str, str]]:
    """Import the FastAPI app against a disposable DB and return OpenAPI keys."""
    with tempfile.TemporaryDirectory(prefix="app-map-validate-") as tmp:
        db_path = Path(tmp) / "validate.db"
        old_database_url = os.environ.get("DATABASE_URL")
        old_jwt_secret = os.environ.get("JWT_SECRET_KEY")
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
        os.environ["JWT_SECRET_KEY"] = "app-map-validation-only-secret-" + "x" * 40
        original_start = threading.Thread.start

        def no_auto_end_worker(thread: threading.Thread, *args, **kwargs):
            if thread.name == "live-session-auto-ender":
                return None
            return original_start(thread, *args, **kwargs)

        try:
            threading.Thread.start = no_auto_end_worker
            sys.path.insert(0, str(SERVER))
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                import main  # type: ignore
                document = main.app.openapi()
            result = {
                (method.upper(), path)
                for path, operations in document.get("paths", {}).items()
                for method in operations
            }
            main.models.engine.dispose()
            return result
        finally:
            threading.Thread.start = original_start
            if old_database_url is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = old_database_url
            if old_jwt_secret is None:
                os.environ.pop("JWT_SECRET_KEY", None)
            else:
                os.environ["JWT_SECRET_KEY"] = old_jwt_secret


def _model_name(response_type: str) -> str | None:
    response_type = response_type.strip().rstrip("?")
    if response_type in ("ResponseBody", "Unit", "<unknown>"):
        return None
    match = re.fullmatch(r"(?:Response|List|MutableList)\s*<\s*(.+)\s*>", response_type)
    if match:
        response_type = match.group(1).strip()
    if response_type in ("ResponseBody", "Unit"):
        return None
    return response_type.rstrip("?")


def _render_current_android_inventory(calls: list[dict[str, str]]) -> str:
    from tests.route_audit.kotlin_contract import discover_models

    models = discover_models()
    fields = ["interface/method", "method", "path", "response class", "response fields/types + JSON name", "file:line"]
    out = []
    import io
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for call in calls:
        model = _model_name(call["response_type"])
        description = ""
        if model and model in models:
            description = ";".join(
                f"{field.name}:json={field.json_name}:{field.type_name}{'?' if field.nullable else ''}"
                for field in models[model]
            )
        writer.writerow({
            "interface/method": f"{call['interface']}.{call['function']}",
            "method": call["method"],
            "path": call["path"],
            "response class": call["response_type"],
            "response fields/types + JSON name": description,
            "file:line": call["file:line"],
        })
    return stream.getvalue()


def _old_route_classes() -> dict[tuple[str, str], tuple[str, str]]:
    """Reuse source-grounded classifications for still-unmatched route pairs."""
    result: dict[tuple[str, str], tuple[str, str]] = {}
    if not OLD_MISMATCHES.exists():
        return result
    for line in OLD_MISMATCHES.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| GET |") and not line.startswith("| POST |") and not line.startswith("| PUT |") and not line.startswith("| DELETE |"):
            continue
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        method, path, source, category = cells[:4]
        result[(method, normalize_path(path))] = (source, category)
    return result


def _render_route_diff(server_rows: list[dict[str, str]], calls: list[dict[str, str]]) -> str:
    android = {(call["method"], normalize_path(call["path"])) for call in calls if call["path"] != DYNAMIC_URL}
    server = {(row["method"], normalize_path(row["path کامل"])): row for row in server_rows}
    old_classes = _old_route_classes()
    missing = sorted(set(server) - android)
    lines = [
        "# Server–Android API map revalidation",
        "",
        "Generated from the current Kotlin Retrofit annotations and the current server route CSV; placeholders are normalized to `{}`.",
        "The historical `docs/app-map/mismatches.md` includes seven routes that now have direct callers in `LiveApi.kt`; this overlay supersedes its old unmatched-route count.",
        "",
        f"Current classification: **{len(server)}** server routes; **{len(android)}** unique static Retrofit calls; **{len(missing)}** server-only routes; **{sum(1 for call in calls if call['path'] == DYNAMIC_URL)}** dynamic `@Url`; Android-only static calls: **0**.",
        "",
        "| method | route | handler/source | current category |",
        "|---|---|---|---|",
    ]
    for key in missing:
        row = server[key]
        source, category = old_classes.get(key, (row.get("handler", "unknown"), "نیازمند طبقه‌بندی"))
        lines.append(f"| {key[0]} | `{key[1]}` | `{source}` | {category} |")
    lines.extend([
        "",
        "## Retrofit dynamic URL",
        "",
        "`DownloadApi.downloadFile(@Url url)` remains runtime-selected and is not counted as a fixed method/path pair. Source: `ReportExporter.kt` (see the current declaration inventory CSV).",
        "",
    ])
    return "\n".join(lines)


def write_current_overlays(calls: list[dict[str, str]] | None = None) -> None:
    calls = list(calls or parse_retrofit_calls())
    server_rows = read_csv(ROUTES_CSV)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "android-api-current.csv").write_text(_render_current_android_inventory(calls), encoding="utf-8-sig")
    (OUT_DIR / "android-route-diff.md").write_text(_render_route_diff(server_rows, calls), encoding="utf-8")


def main_cli() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-server-import", action="store_true", help="compare Android declarations only")
    parser.add_argument("--write", action="store_true", help="write current Retrofit field inventory and route-diff overlay")
    args = parser.parse_args()
    calls = parse_retrofit_calls()
    report = compare_retrofit_map(source_calls=calls)
    server_rows = read_csv(ROUTES_CSV)
    saved_keys = {(row["method"], row["path کامل"]) for row in server_rows}
    live_keys = None if args.skip_server_import else live_server_routes()
    report["server_map_exact"] = None if live_keys is None else live_keys == saved_keys
    report["server_runtime_count"] = None if live_keys is None else len(live_keys)
    if live_keys is not None:
        report["server_map_missing"] = sorted(live_keys - saved_keys)
        report["server_map_stale"] = sorted(saved_keys - live_keys)
    if args.write:
        write_current_overlays(calls)
        report["written"] = ["docs/route-tests/android-api-current.csv", "docs/route-tests/android-route-diff.md"]
    print(json.dumps(report, ensure_ascii=False, indent=2))
    # Keep the historical map mismatch visible even when overlays were written;
    # `--write` does not rewrite the supplied phase-zero inputs.
    map_current = (
        report["retrofit_source_map_exact"]
        and report["android_only_routes"] == 0
        and len(saved_keys) == 221
        and (live_keys is None or live_keys == saved_keys)
    )
    return 0 if map_current else 1


if __name__ == "__main__":
    raise SystemExit(main_cli())
