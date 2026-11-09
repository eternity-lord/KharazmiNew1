from __future__ import annotations

import importlib

from .route_registry import route_id, routes


def test_every_server_route_has_audit_module_and_explicit_registry():
    all_rows = routes()
    registered = set()
    for router in sorted({row["handler"].split(".")[1] for row in all_rows}):
        module = importlib.import_module(f"tests.route_audit.test_audit_{router}")
        registered.update(getattr(module, "ROUTE_IDS", []))
        if router == "finance":
            # Finance's explicit list is maintained in its behavioral module.
            registered.update(f"{method} {path}" for method, path in module.FINANCE_ROUTES)
    expected = {route_id(row) for row in all_rows}
    assert registered == expected
