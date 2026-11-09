from __future__ import annotations

import json
from pathlib import Path

import pytest

REPORT = Path(__file__).with_name("report.json")
CONTRACT_REPORT = Path(__file__).with_name("contract-report.json")


def _report():
    if not REPORT.exists():
        pytest.skip("run `python -m tests.route_audit.sweep.run_sweep` first")
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_sweep_has_all_221_routes():
    report = _report()
    assert report["route_count"] == 221
    assert len(report["routes"]) == 221


def test_sweep_route_statuses_and_json_shape():
    report = _report()
    failures = [f"{r['method']} {r['path']} => {r.get('status')}" for r in report["routes"] if r.get("status_500")]
    assert not failures, failures


def test_sweep_invalid_inputs_never_500():
    report = _report()
    failures = [f"{r['method']} {r['path']} invalid => {r.get('invalid', {}).get('status')}" for r in report["routes"] if r.get("invalid", {}).get("status_500")]
    assert report["invalid_target_count"] == 220
    assert not failures, failures


def test_sweep_empty_probes_have_no_null_list_shape():
    report = _report()
    assert report["empty_probe_count"] == 11
    assert not [r for r in report["routes"] if (r.get("empty") or {}).get("is_null_list")]


# These are the four historically resolved contract regressions. Tests pin
# their specific fields, leaving separate current candidates to their own triage.
_CONTRACT_CASES = [
    ("RA-sweep-01", "POST", "classes/pending_approval/bulk_approve"),
    ("RA-sweep-02", "GET", "exams/student/list"),
    ("RA-sweep-03", "GET", "homework/parent/child/{student_id}"),
    ("RA-sweep-04", "GET", "teachers/{id}/incomplete_classes"),
]
def _contract_entry(method: str, path: str) -> dict:
    if not CONTRACT_REPORT.exists():
        pytest.skip("run `python -m tests.route_audit.sweep.run_contract` first")
    report = json.loads(CONTRACT_REPORT.read_text(encoding="utf-8"))
    return next(entry for entry in report["entries"] if entry["method"] == method and entry["path"] == path)


@pytest.mark.parametrize(
    "bug_id,method,path",
    _CONTRACT_CASES,
    ids=[bug_id for bug_id, _, _ in _CONTRACT_CASES],
)
def test_fixed_contract_regression_fields_remain_present(bug_id, method, path):
    """Pin the specific resolved field without misclassifying separate candidates."""
    entry = _contract_entry(method, path)
    payload = entry.get("sample_payload")
    if bug_id in {"RA-sweep-01", "RA-sweep-02"}:
        assert entry["issues"] == []
    elif bug_id == "RA-sweep-03":
        assert payload and payload[0]["description"] == "حل تمرین"
        assert payload[0]["due_date"] == "1405/07/01"
        # max_score is a separate, reproducible candidate tracked by RA-homework-01.
    elif bug_id == "RA-sweep-04":
        assert payload and all(isinstance(item.get("students_preview"), list) for item in payload)
        # Other shared-model defaults are unresolved Q-006, not this fixed regression.
