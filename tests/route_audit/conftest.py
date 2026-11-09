from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "Kharazmi_Server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from .clock import FIXED_NOW, freeze_loaded_server_modules  # noqa: E402
from .seed import seed_database  # noqa: E402


@pytest.fixture(scope="session")
def audit_context(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("route-audit") / "demo.db"
    os.environ["JWT_SECRET_KEY"] = "route-audit-pytest-secret-" + "x" * 40
    os.environ["FCM_SERVER_KEY"] = ""
    manifest = seed_database(db_path)
    yield {"path": db_path, "manifest": manifest}


@pytest.fixture(scope="session")
def audit_app(audit_context):
    # Import only after seed selected the temporary DATABASE_URL. The route-audit
    # never starts the live auto-end worker: it would mutate the shared fixture DB.
    original_start = threading.Thread.start

    def no_live_auto_end_worker(thread, *args, **kwargs):
        if thread.name == "live-session-auto-ender":
            return None
        return original_start(thread, *args, **kwargs)

    try:
        threading.Thread.start = no_live_auto_end_worker
        import main  # type: ignore
        return main.app
    finally:
        threading.Thread.start = original_start


@pytest.fixture(scope="session")
def frozen_server_clock(audit_app):
    restore = freeze_loaded_server_modules()
    yield FIXED_NOW.date()
    restore()


@pytest.fixture(scope="session")
def client(audit_app, frozen_server_clock):
    with TestClient(audit_app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def network_isolation(monkeypatch):
    """Never allow SMS/push/provider code in route tests to reach a network."""
    monkeypatch.setenv("FCM_SERVER_KEY", "")
    import requests
    import socket
    import urllib.request

    def blocked_provider_request(*args, **kwargs):
        raise AssertionError("route-audit attempted an external network request")

    monkeypatch.setattr(requests, "post", blocked_provider_request)
    monkeypatch.setattr(requests, "request", blocked_provider_request)
    monkeypatch.setattr(requests.sessions.Session, "request", blocked_provider_request)
    monkeypatch.setattr(urllib.request, "urlopen", blocked_provider_request)
    monkeypatch.setattr(socket, "create_connection", blocked_provider_request)
    monkeypatch.setattr(socket.socket, "connect", blocked_provider_request)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked_provider_request)


@pytest.fixture
def auth_headers(audit_context):
    return {role: {"Authorization": f"Bearer {token}"} for role, token in audit_context["manifest"]["roles"].items()}


@pytest.fixture
def db(audit_context):
    import models  # type: ignore
    session = models.SessionLocal()
    try:
        yield session
    finally:
        session.close()
