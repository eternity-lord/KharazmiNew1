#!/usr/bin/env python3
"""Append a source-backed route ledger to each per-router audit report.

Primary route data remains docs/app-map/server-routes.csv. The generated appendix
joins the current Kotlin overlay and latest isolated sweep, while deliberately
labeling unmapped role/DB facts as static or probe-only evidence.
"""
from __future__ import annotations

import ast
import csv
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTE_MAP = ROOT / "docs/app-map/server-routes.csv"
ANDROID_MAP = ROOT / "docs/route-tests/android-api-current.csv"
SWEEP_REPORT = ROOT / "tests/route_audit/sweep/report.json"
CONTRACT_REPORT = ROOT / "tests/route_audit/sweep/contract-report.json"
TEST_ROOT = ROOT / "tests/route_audit"
REPORT_DIR = ROOT / "docs/route-tests/routes"
START = "<!-- GENERATED ROUTE LEDGER START -->"
END = "<!-- GENERATED ROUTE LEDGER END -->"

# Strict xfails that still reproduce an open issue today.
KNOWN_XFAILS = {}
# No partial-response route invariants currently remain as strict xfails.
PARTIAL_XFAILS = {}

# Direct file/image consumers do not appear in the Retrofit-only Android map.
DIRECT_ANDROID_CALLERS = {
    ("GET", "/uploads/{}"): {
        "callers": (
            "Glide authenticated image loads — `StudentProfileActivity.kt:344` "
            "(`profile_image`); `TeacherProfileActivity.kt:291` (`profile_image`); "
            "`InstituteSettingsActivity.kt:109` (`logo_path`)."
        ),
        "display": (
            "`FileResponse` bytes displayed by Glide `ImageView`; request uses "
            "`Authorization: Bearer <SecureLoginStore token>`. No Retrofit DTO."
        ),
    },
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def norm_path(path: str) -> str:
    path = "/" + path.lstrip("/")
    return re.sub(r"\{[^}]+\}", "{}", path).rstrip("/") or "/"


def cell(value: object) -> str:
    if value is None or value == "":
        return "—"
    text = str(value).replace("\r\n", "\n").replace("\n", "<br>")
    # Break long static input/DB/effect lists inside the cell so wide source
    # expressions do not force a huge Markdown table. Split the literal pipe
    # between OpenAPI fields to a line break before escaping remaining pipes.
    text = re.sub(r"\s+\|\s+", "<br>", text)
    text = text.replace(";", ";<br>").replace(", ", ",<br>")
    text = re.sub(r",(?=[A-Za-z_\[{])", ",<br>", text)
    return text.replace("|", "\\|")


def source_files() -> list[Path]:
    return sorted([*TEST_ROOT.glob("test_*.py"), *TEST_ROOT.glob("sweep/test_*.py")])


def extract_calls(path: Path):
    """Collect literal client calls as evidence references, not assertion proof.

    Use the enclosing Python function, rather than the last test definition in
    the file: request helpers between tests must not be attributed to an
    unrelated preceding test.
    """
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text)
        function_defs = sorted(
            [
                node for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            ],
            key=lambda node: node.lineno,
        )
    except SyntaxError:
        function_defs = []
    callers_by_helper: dict[str, list[str]] = defaultdict(list)
    for test_node in (node for node in function_defs if node.name.startswith("test_")):
        for call_node in ast.walk(test_node):
            if isinstance(call_node, ast.Call) and isinstance(call_node.func, ast.Name):
                helper_name = call_node.func.id
                if any(node.name == helper_name for node in function_defs):
                    callers_by_helper[helper_name].append(test_node.name)
    patterns = [
        re.compile(r"\bclient\.(get|post|put|delete|patch|options|head)\(\s*(?:f)?([\"'])(.*?)(?<!\\)\2", re.S),
        re.compile(r"\bclient\.request\(\s*([\"'])(GET|POST|PUT|DELETE|PATCH)\1\s*,\s*(?:f)?([\"'])(.*?)(?<!\\)\3", re.S),
    ]
    calls = []
    for pattern_index, pattern in enumerate(patterns):
        for match in pattern.finditer(text):
            if pattern_index == 0:
                method = match.group(1).upper()
                call_path = match.group(3)
            else:
                method = match.group(2).upper()
                call_path = match.group(4)
            line_number = text.count("\n", 0, match.start()) + 1
            enclosing = [
                node for node in function_defs
                if node.lineno <= line_number <= (node.end_lineno or node.lineno)
            ]
            if enclosing:
                owner = min(enclosing, key=lambda node: (node.end_lineno or node.lineno) - node.lineno)
                if owner.name.startswith("test_"):
                    test_names = [owner.name]
                else:
                    test_names = callers_by_helper.get(owner.name) or [f"helper:{owner.name}"]
            else:
                test_names = ["module-level"]
            for test_name in dict.fromkeys(test_names):
                calls.append((method, call_path, str(path.relative_to(ROOT)), test_name, line_number))
    return calls


def literal_route_matches(route: str, literal: str) -> bool:
    """Match route templates against literal/f-string test paths by segment."""
    route_parts = route.strip("/").split("/")
    literal_parts = literal.split("?", 1)[0].strip("/").split("/")
    if len(route_parts) != len(literal_parts):
        return False
    for expected, actual in zip(route_parts, literal_parts):
        if expected.startswith("{") and expected.endswith("}"):
            if not actual or actual.startswith("{") and "}" not in actual:
                return False
        elif expected != actual:
            return False
    return True


def router_name(handler: str) -> str:
    if handler == "main.serve_upload":
        return "serve_upload"
    if handler.startswith("routers."):
        return handler.split(".", 2)[1]
    return "other"


def escape_name(path: str) -> str:
    return path.replace("/", "_").replace("{", "").replace("}", "")


def main() -> None:
    route_rows = read_csv(ROUTE_MAP)
    android_rows = read_csv(ANDROID_MAP) if ANDROID_MAP.exists() else []
    sweep = json.loads(SWEEP_REPORT.read_text(encoding="utf-8")) if SWEEP_REPORT.exists() else {"routes": []}
    contract = json.loads(CONTRACT_REPORT.read_text(encoding="utf-8")) if CONTRACT_REPORT.exists() else {"entries": []}
    try:
        branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    except Exception:
        branch = "unknown"

    android_by_key: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in android_rows:
        android_by_key[(row["method"].upper(), norm_path(row["path"]))].append(row)
    sweep_by_key = {(row["method"].upper(), norm_path(row["path"])): row for row in sweep.get("routes", [])}
    contract_by_key = {(row["method"].upper(), norm_path(row["path"])): row for row in contract.get("entries", [])}

    calls = [call for file in source_files() for call in extract_calls(file)]
    calls_by_router: dict[str, list[tuple[str, str, str, str, int]]] = defaultdict(list)
    for call in calls:
        calls_by_router["__all__"].append(call)

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in route_rows:
        grouped[router_name(row["handler"])].append(row)

    for router, rows in sorted(grouped.items()):
        lines = [
            START,
            "## Route ledger — map input + current isolated probes",
            "",
            f"Generated from `docs/app-map/server-routes.csv`; branch `{branch}`. Static DB columns and response keys are the supplied map's AST/OpenAPI summary, not runtime proof. ‘Probe actor’ is the role intentionally selected by the sweep; it is not a substitute for a complete authorization contract.",
            "",
            "| Route | One-sentence purpose / handler | Probe actor + observed result | Current Android caller / screen | Inputs → response values | Static DB reads → writes | Side effects | Audit evidence/status |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for row in sorted(rows, key=lambda item: (item["method"], item["path کامل"])):
            method = row["method"].upper()
            path = "/" + row["path کامل"].lstrip("/")
            key = (method, norm_path(path))
            handler = row["handler"]
            purpose_name = handler.rsplit(".", 1)[-1].replace("_", " ")
            purpose = f"Runs `{purpose_name}` for `{method} {path}`. Source: `{row['file:line']}`."
            probe = sweep_by_key.get(key, {})
            role_status = f"{probe.get('role', 'not probed')} / {probe.get('status', '—')} {probe.get('shape', '')}".strip()
            invalid = probe.get("invalid", {})
            if invalid:
                role_status += f"; invalid={invalid.get('status', '—')}"

            android = android_by_key.get(key, [])
            direct_android = DIRECT_ANDROID_CALLERS.get(key)
            display_contract = None
            if android:
                callers = "<br>".join(
                    f"`{item['interface/method']}` — `{Path(item['file:line'].split(':')[0]).name}`:{item['file:line'].rsplit(':', 1)[-1]}"
                    for item in android
                )
                android_models = "<br>".join(
                    f"`{item['response class']}` ({item.get('response fields/types + JSON name', '')})"
                    for item in android
                )
            elif direct_android:
                callers = direct_android["callers"]
                android_models = "—"
                display_contract = direct_android["display"]
            else:
                callers = "No static Retrofit caller in current overlay; server-only/deferred screen attribution."
                android_models = "—"
            response = row.get("response keys/schema", "")
            values = f"Input: {row.get('input', '')}<br>Server response: {response}"
            if android_models != "—":
                values += f"<br>Android model: {android_models}"
            if display_contract:
                values += f"<br>Android display: {display_contract}"

            direct_refs = []
            seen_test_refs = set()
            for ref_method, literal, rel_file, test_name, line_number in calls_by_router["__all__"]:
                if ref_method == method and literal_route_matches(row["path کامل"], literal):
                    test_ref = (rel_file, test_name)
                    if test_ref in seen_test_refs:
                        continue
                    seen_test_refs.add(test_ref)
                    direct_refs.append(f"`{rel_file}:{line_number}` (`{test_name}`)")
            xfail = KNOWN_XFAILS.get((method, path))
            issues = contract_by_key.get(key, {}).get("issues", [])
            issue_types = sorted({item.get("kind", "issue") for item in issues})
            if xfail:
                audit = f"**strict xfail `{xfail}`**; reproduced, see `../bugs.md`."
            elif direct_refs:
                audit = "Targeted request reference(s): " + ", ".join(direct_refs[:10])
                if len(direct_refs) > 10:
                    audit += f" (+{len(direct_refs)-10} more)"
                audit += "; assertion depth is per linked test, not inferred here."
            else:
                audit = "221-route smoke only; business values/DB effects need a focused test or an explicit blocker."
            partial_xfail = PARTIAL_XFAILS.get((method, path))
            if partial_xfail:
                issue_ids = partial_xfail.split(", ")
                if len(issue_ids) == 1:
                    audit += f" Open behavior xfail `{issue_ids[0]}` (route also has passing assertions); see `../bugs.md`."
                else:
                    issue_refs = ", ".join(f"`{issue}`" for issue in issue_ids)
                    audit += f" Open behavior xfails {issue_refs} (route also has passing assertions); see `../bugs.md`."
            if issues and not xfail:
                audit += f" Contract candidates: {len(issues)} ({', '.join(issue_types)}); triage in `../questions.md`/`../bugs.md`."
            if row.get("verification"):
                audit += f" Map note: {row['verification']}"

            read = row.get("DB tables read (static)", "")
            write = row.get("DB tables/columns written (static)", "")
            db_effects = f"Read: {read}<br>Write: {write}"
            side_effects = row.get("side effects", "")
            lines.append(
                "| " + " | ".join(map(cell, [f"`{method} {path}`", purpose, role_status, callers, values, db_effects, side_effects, audit])) + " |"
            )
        lines.extend([
            "",
            "**Interpretation:** a 2xx/4xx smoke result only records the observed response for this isolated seed. It does not prove the listed static DB effect or business invariant. Direct test references are navigation aids, not a claim that every requested edge case is covered.",
            END,
        ])
        report_path = REPORT_DIR / f"{router}.md"
        current = report_path.read_text(encoding="utf-8") if report_path.exists() else f"# Route audit `{router}`\n\n"
        if "The route ledger below is the current generated audit snapshot" not in current:
            first, separator, rest = current.partition("\n")
            if separator:
                current = first + "\n\n> The route ledger below is the current generated audit snapshot and supersedes any older status/count matrix above.\n" + rest
        generated = "\n".join(lines)
        if START in current and END in current:
            before = current.split(START, 1)[0]
            after = current.split(END, 1)[1]
            updated = before + generated + after
        else:
            updated = current.rstrip() + "\n\n" + generated + "\n"
        report_path.write_text(updated, encoding="utf-8")

    print(json.dumps({"routers": len(grouped), "routes": len(route_rows), "branch": branch}, ensure_ascii=False))


if __name__ == "__main__":
    main()
