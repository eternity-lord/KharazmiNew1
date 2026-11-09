from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from .kotlin_contract import ContractIssue, KotlinField, audit_payload, decode, discover_models, inspect_gson_configuration
from .oracle import assert_invariants, build_oracle


def test_seed_is_isolated_and_has_required_states(audit_context):
    path = Path(audit_context["path"])
    assert path.name != "gaj_db.db"
    assert audit_context["manifest"]["counts"]["students"] == 30
    assert audit_context["manifest"]["counts"]["courses"] >= 6
    con = sqlite3.connect(path)
    try:
        assert con.execute("select count(*) from transactions").fetchone()[0] >= 5
        assert con.execute("select count(*) from installments").fetchone()[0] >= 4
    finally:
        con.close()


def test_oracle_does_not_need_production_db(db):
    snapshot = build_oracle(db)
    assert snapshot.enrollments[1].net_tuition == 1_000_000
    assert snapshot.enrollments[1].due == 700_000
    assert_invariants(snapshot)


def test_kotlin_contract_accepts_fixed_parent_decimal_score():
    models = discover_models()
    # RA-parent-01 is fixed: the Android model accepts a fractional max_score.
    if "ParentExamItem" in models:
        issues = audit_payload("ParentExamItem", {
            "course_title": "ریاضی", "title": "آزمون", "date": "1405/06/25", "max_score": 12.5,
        })
        assert not issues
        max_score = next(field for field in models["ParentExamItem"] if field.name == "max_score")
        assert max_score.type_name == "Float"
        assert not max_score.nullable
    else:
        pytest.skip("ParentExamItem is not present in the checked-out Android source")


def test_gson_default_constructor_and_unsafe_allocation_are_modelled():
    models = {
        "Defaulted": [
            KotlinField("title", "title", "String", False, 1, has_default=True, default_expression='"untitled"'),
            KotlinField("items", "items", "List<String>", False, 2, has_default=True, default_expression="emptyList()"),
            KotlinField("count", "count", "Int", False, 3, has_default=True, default_expression="7"),
        ],
        "PartlyDefaulted": [
            KotlinField("id", "id", "Int", False, 4),
            KotlinField("label", "label", "String", False, 5, has_default=True, default_expression='"fallback"'),
        ],
    }

    defaulted = decode("Defaulted", {}, models)
    assert defaulted.values == {"title": "untitled", "items": [], "count": 7}
    assert defaulted.issues == []

    partly_defaulted = decode("PartlyDefaulted", {}, models)
    assert partly_defaulted.values == {"id": 0, "label": None}
    assert {(issue.field, issue.kind) for issue in partly_defaulted.issues} == {
        ("id", "silent-zero"), ("label", "missing-non-null"),
    }


def test_gson_explicit_null_nonnull_and_any_wire_values():
    models = discover_models()
    assert any(issue.kind == "null-non-null" and issue.field == "date"
               for issue in audit_payload("TeacherTodaySummary", {"date": None}, models))
    receipt = audit_payload("ReceiptDetailsResponse", {
        "transaction_id": 1, "remittance_number": "R-001",
    }, models)
    assert not [issue for issue in receipt if issue.field == "remittance_number"]
    assert inspect_gson_configuration()["default_gson_semantics"] is True
