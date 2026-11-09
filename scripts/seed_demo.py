#!/usr/bin/env python3
"""CLI wrapper for tests.route_audit.seed; never targets gaj_db.db."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.route_audit.seed import seed_database  # noqa: E402

if __name__ == "__main__":
    import argparse, json
    p = argparse.ArgumentParser()
    p.add_argument("output", type=Path)
    p.add_argument("--large", action="store_true")
    args = p.parse_args()
    print(json.dumps(seed_database(args.output, large=args.large), ensure_ascii=False, indent=2))
