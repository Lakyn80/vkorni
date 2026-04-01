"""Tests for api/export.py endpoints."""
import io
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ── /export ────────────────────────────────────────────────────────────────────

@patch("app.api.export.export_profile_to_vkorni", return_value={"status": "OK", "thread_id": 42, "url": "https://vkorni.com/threads/42/"})
def test_export_ok(mock_send):
    r = client.post("/api/export", json={
        "name": "Лев Яшин",
        "text": "Биография...",
        "photos": [],
        "birth": "22 октября 1929",
        "death": "20 марта 1990",
        "photo_source_url": None,
    })
    assert r.status_code == 200
    assert r.json()["status"] == "OK"
    assert r.json()["thread_id"] == 42
    mock_send.assert_called_once()


@patch("app.api.export.export_profile_to_vkorni", return_value={"status": "ERROR", "error": "API key missing"})
def test_export_error_propagated(mock_send):
    r = client.post("/api/export", json={
        "name": "Тест", "text": "...", "photos": [],
    })
    assert r.status_code == 200       # HTTP 200 — error is in the body (XenForo-level)
    assert r.json()["status"] == "ERROR"


def test_export_missing_fields():
    r = client.post("/api/export", json={"name": "Тест"})  # missing "text"
    assert r.status_code == 422


# ── /upload ────────────────────────────────────────────────────────────────────

@patch("app.api.export.convert_to_webp", side_effect=lambda p: p)
@patch("app.api.export.os.makedirs")
def test_upload_unsupported_extension(mock_makedirs, mock_webp):
    data = io.BytesIO(b"fake gif data")
    r = client.post("/api/upload?name=Яшин",
                    files={"file": ("photo.gif", data, "image/gif")})
    assert r.status_code == 400
    assert "Unsupported" in r.json()["detail"]


@patch("app.api.export.convert_to_webp", side_effect=lambda p: p)
@patch("builtins.open", create=True)
@patch("app.api.export.os.makedirs")
def test_upload_jpg_accepted(mock_makedirs, mock_open, mock_webp):
    mock_open.return_value.__enter__ = lambda s: s
    mock_open.return_value.__exit__ = lambda *a: False
    mock_open.return_value.write = lambda b: None

    data = io.BytesIO(b"fake jpg data")
    r = client.post("/api/upload?name=Яшин",
                    files={"file": ("photo.jpg", data, "image/jpeg")})
    assert r.status_code == 200
    assert "url" in r.json()
