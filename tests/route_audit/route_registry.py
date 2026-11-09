from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSV = ROOT / "docs/app-map/server-routes.csv"


def routes():
    with CSV.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def route_id(row):
    return f"{row['method']} {row['path کامل']}"
