from pathlib import Path
import re

from scripts.generate_route_audit_docs import END, REPORT_DIR, ROOT, START, cell, extract_calls


def _unescaped_pipe_count(line: str) -> int:
    count = 0
    for index, char in enumerate(line):
        if char != "|":
            continue
        backslashes = 0
        cursor = index - 1
        while cursor >= 0 and line[cursor] == "\\":
            backslashes += 1
            cursor -= 1
        if backslashes % 2 == 0:
            count += 1
    return count


def test_cell_escapes_literal_pipe_once_and_breaks_openapi_separators():
    assert cell("left|right") == r"left\|right"
    assert cell("query:a | query:b") == "query:a<br>query:b"


def test_route_call_evidence_includes_test_name_and_source_line():
    source = ROOT / "tests/route_audit/test_audit_audit.py"
    calls = extract_calls(source)
    matches = [
        call for call in calls
        if call[0] == "GET" and call[1] == "/audit/suspicious_patterns"
    ]
    assert matches
    assert all(call[3].startswith("test_audit_") and call[4] > 0 for call in matches)
    assert any(call[3] == "test_audit_pattern_c_uses_ten_latest_sessions_and_detects_new_absence" for call in matches)
    source_lines = source.read_text(encoding="utf-8").splitlines()
    assert all("_alerts_from(client.get(" in source_lines[call[4] - 1] for call in matches)


def test_helper_request_is_not_misattributed_to_the_previous_test():
    source = ROOT / "tests/route_audit/test_known_bugs.py"
    calls = extract_calls(source)
    deletion_calls = [
        call for call in calls
        if call[0] == "DELETE" and call[1].startswith("/classes/")
    ]
    assert {call[3] for call in deletion_calls} == {
        "test_O19_restore_class_restores_operational_history_and_optional_finance",
        "test_O19_financial_restore_blocks_spent_credit_atomically_but_allows_operational",
        "test_O19_restore_conflict_does_not_partially_restore_class_or_history",
    }
    assert len({call[4] for call in deletion_calls}) == 1


def test_audit_trail_ledger_shows_one_line_reference_per_test():
    source = ROOT / "tests/route_audit/test_audit_audit_trail.py"
    calls = extract_calls(source)
    expected = {
        call[3] for call in calls
        if call[0] == "GET" and call[1] == "/audit-trail/logs"
    }
    report = (REPORT_DIR / "audit_trail.md").read_text(encoding="utf-8")
    ledger = report.split(START, 1)[1].split(END, 1)[0]
    route_row = next(line for line in ledger.splitlines() if line.startswith("| `GET /audit-trail/logs`"))
    actual = re.findall(r"`tests/route_audit/test_audit_audit_trail\.py:\d+` \(`([^`]+)`\)", route_row)
    assert expected
    assert set(actual) == expected
    assert len(actual) == len(expected)


def _split_markdown_cells(line: str) -> list[str]:
    cells = []
    start = 1
    for index in range(1, len(line) - 1):
        if line[index] != "|":
            continue
        backslashes = 0
        cursor = index - 1
        while cursor >= 0 and line[cursor] == "\\":
            backslashes += 1
            cursor -= 1
        if backslashes % 2 == 0:
            cells.append(line[start:index])
            start = index + 1
    cells.append(line[start:-1])
    return cells


def test_generated_route_ledgers_keep_markdown_table_columns_intact():
    reports = sorted(REPORT_DIR.glob("*.md"))
    assert len(reports) == 25
    for report in reports:
        text = report.read_text(encoding="utf-8")
        assert START in text and END in text, report.name
        ledger = text.split(START, 1)[1].split(END, 1)[0]
        rows = [line for line in ledger.splitlines() if line.startswith("|")]
        assert rows, report.name
        for row in rows:
            assert _unescaped_pipe_count(row) == 9, f"{report.name}: malformed table row: {row}"
            longest_unbroken_cell = max(
                (len(segment) for cell_text in _split_markdown_cells(row) for segment in cell_text.split("<br>")),
                default=0,
            )
            assert longest_unbroken_cell <= 300, f"{report.name}: unwrapped table cell: {row}"
