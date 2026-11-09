from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def _logical_digest(path: Path) -> str:
    """Hash schema and rows canonically, independent of SQLite index DDL order."""
    connection = sqlite3.connect(path)
    try:
        schema = connection.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()
        tables = []
        for (name,) in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ):
            rows = connection.execute(f'SELECT * FROM "{name}"').fetchall()
            canonical_rows = sorted(
                [tuple(value.hex() if isinstance(value, bytes) else value for value in row) for row in rows],
                key=lambda row: json.dumps(row, ensure_ascii=False, sort_keys=True, default=repr),
            )
            tables.append((name, canonical_rows))
        payload = json.dumps(
            {"schema": schema, "tables": tables}, ensure_ascii=False, sort_keys=True, default=repr
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
    finally:
        connection.close()


def _seed_digest(path: Path) -> str:
    env = os.environ.copy()
    env["JWT_SECRET_KEY"] = "route-audit-reproducibility-test-secret-" + "x" * 32
    subprocess.run(
        [sys.executable, "-m", "tests.route_audit.seed", str(path)],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return _logical_digest(path)


def test_canonical_seed_is_byte_reproducible(tmp_path):
    first = _seed_digest(tmp_path / "first.db")
    second = _seed_digest(tmp_path / "second.db")
    assert first == second
