"""Behavioral audit of the authenticated profile-upload download route."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from .route_registry import route_id, routes

ROUTE_IDS = ["GET /uploads/{filename}"]
AUTHENTICATED_ROLES = ("admin", "secretary", "teacher", "student", "parent")


def _database_snapshot(db):
    import models

    result = {}
    for table in models.Base.metadata.sorted_tables:
        statement = select(table)
        primary_key = list(table.primary_key.columns)
        if primary_key:
            statement = statement.order_by(*primary_key)
        result[table.name] = [tuple(row) for row in db.execute(statement).all()]
    return result


def test_serve_upload_route_inventory_is_explicit(client):
    actual = {
        route_id(row)
        for row in routes()
        if row["handler"].split(".")[1] == "serve_upload"
    }
    assert set(ROUTE_IDS) == actual
    openapi_routes = {
        (method.upper(), path)
        for path, methods in client.app.openapi()["paths"].items()
        for method in methods
    }
    assert all(tuple(route.split(" ", 1)) in openapi_routes for route in ROUTE_IDS)


def test_android_profile_image_callers_use_authenticated_upload_urls():
    repository = Path(__file__).resolve().parents[2]
    app_root = repository / "KharazmiAdmin" / "app" / "src" / "main" / "java" / "com" / "example" / "kharazmiadmin"
    callers = {
        "StudentProfileActivity.kt": "data.info.profile_image",
        "TeacherProfileActivity.kt": "data.info.profile_image",
        "InstituteSettingsActivity.kt": "data.logo_path",
    }
    for filename, image_field in callers.items():
        source = (app_root / filename).read_text(encoding="utf-8")
        assert image_field in source, filename
        assert '"uploads/profiles/" + ' in source, filename
        assert "GlideUrl(" in source, filename
        assert "SecureLoginStore.getToken" in source, filename
        assert '.addHeader("Authorization", "Bearer $glideAuthToken")' in source, filename
        assert ".load(glideUrl)" in source, filename
        assert ".error(android.R.drawable.sym_def_app_icon)" in source, filename


def test_serve_upload_returns_exact_temp_file_for_each_authenticated_role(
    client, auth_headers, db, monkeypatch, tmp_path,
):
    import main

    before = _database_snapshot(db)
    upload_root = tmp_path / "uploads"
    profiles = upload_root / "profiles"
    profiles.mkdir(parents=True)
    filename = "audit-avatar.jpg"
    contents = b"\xff\xd8route-audit-temporary-image\xff\xd9"
    (profiles / filename).write_bytes(contents)
    monkeypatch.setenv("KHARAZMI_UPLOAD_ROOT", str(upload_root))

    for role in AUTHENTICATED_ROLES:
        response = client.get(f"/uploads/{filename}", headers=auth_headers[role])
        assert response.status_code == 200, role
        assert response.content == contents, role
        assert response.headers["content-type"] == "image/jpeg", role
        assert response.headers["content-length"] == str(len(contents)), role
        assert response.headers["x-content-type-options"] == "nosniff", role

    assert _database_snapshot(db) == before
    assert (profiles / filename).read_bytes() == contents
    assert main.resolve_existing("profiles", filename) == str(profiles / filename)


def test_serve_upload_requires_authentication_before_resolving_file(
    client, db, monkeypatch,
):
    import main

    before = _database_snapshot(db)
    lookups = []
    monkeypatch.setattr(main, "resolve_existing", lambda *parts: lookups.append(parts))
    response = client.get("/uploads/private.jpg")
    assert response.status_code == 401
    assert response.json() == {"detail": "توکن احراز هویت یافت نشد. لطفاً مجدداً وارد شوید"}
    assert lookups == []
    assert _database_snapshot(db) == before


def test_serve_upload_missing_file_is_404_and_read_only(client, auth_headers, db, monkeypatch):
    import main

    before = _database_snapshot(db)
    lookups = []

    def missing(*parts):
        lookups.append(parts)
        return None

    monkeypatch.setattr(main, "resolve_existing", missing)
    response = client.get("/uploads/no-such-audit-file.jpg", headers=auth_headers["admin"])
    assert response.status_code == 404
    assert response.json() == {"detail": "فایل یافت نشد"}
    assert lookups == [("profiles", "no-such-audit-file.jpg")]
    assert _database_snapshot(db) == before


@pytest.mark.parametrize(
    "filename",
    ["", ".hidden", "..", "../outside.jpg", "folder/photo.jpg", r"folder\\photo.jpg"],
)
def test_serve_upload_rejects_empty_hidden_or_path_like_names_without_lookup(
    filename, monkeypatch,
):
    import main

    lookups = []
    monkeypatch.setattr(main, "resolve_existing", lambda *parts: lookups.append(parts))
    with pytest.raises(HTTPException) as exc_info:
        main.serve_upload(filename, "admin")
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "نام فایل معتبر نیست"
    assert lookups == []
