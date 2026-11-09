from __future__ import annotations

import json
from pathlib import Path


REPORT = Path(__file__).with_name("large-report.json")


def test_large_seed_limit_order_filter_contract():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert all(row["status"] == 200 for row in report["responses"].values())
    assert all(report["checks"].values()), report["checks"]
