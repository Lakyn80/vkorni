"""
Smoke-tests: verify all API routes return expected HTTP status codes.
Business logic is tested in dedicated test_api_*.py files.
"""
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

LONG_TEXT = "Биографический текст о человеке. " * 50


# ── biography ──────────────────────────────────────────────────────────────────

@patch("app.api.biography.get_biography", return_value={"name": "Яшин", "text": "T", "photos": []})
def test_smoke_generate_cached(mock_get):
    assert client.post("/api/generate?name=Яшин").status_code == 200


@patch("app.api.biography.list_biographies", return_value=[])
def test_smoke_cache_list(mock_list):
    assert client.get("/api/cache").status_code == 200


@patch("app.api.biography.get_biography", return_value=None)
def test_smoke_cache_get_missing(mock_get):
    assert client.get("/api/cache/НетТакого").status_code == 404


@patch("app.api.biography.delete_cached", return_value=True)
def test_smoke_cache_delete(mock_del):
    assert client.delete("/api/cache/Яшин").status_code == 200


@patch("app.api.biography.delete_all_biographies", return_value=0)
def test_smoke_cache_delete_all(mock_del):
    assert client.delete("/api/cache").status_code == 200


@patch("app.api.biography.fetch_person_from_wikipedia", return_value=None)
def test_smoke_wiki_not_found(mock_wiki):
    assert client.get("/api/wiki/НесуществующийЧеловек").status_code == 404


# ── export ─────────────────────────────────────────────────────────────────────

@patch("app.api.export.export_profile_to_vkorni", return_value={"status": "OK"})
def test_smoke_export(mock_send):
    assert client.post("/api/export", json={"name": "Яшин", "text": "Био"}).status_code == 200


def test_smoke_export_missing_body():
    assert client.post("/api/export", json={}).status_code == 422


# ── batch ──────────────────────────────────────────────────────────────────────

@patch("app.api.batch._create_batch", return_value="id1")
@patch("app.api.batch.enqueue_job")
def test_smoke_batch_create(mock_enqueue, mock_create):
    assert client.post("/api/batch", json={"names": ["Яшин"]}).status_code == 200


@patch("app.api.batch.get_batch_status", return_value=None)
def test_smoke_batch_get_missing(mock_status):
    assert client.get("/api/batch/nonexistent").status_code == 404


# ── images ─────────────────────────────────────────────────────────────────────

@patch("app.api.images.set_status")
@patch("app.api.images.enqueue_job")
def test_smoke_image_job(mock_enqueue, mock_status):
    assert client.post("/api/image-job?name=Яшин").status_code == 200


@patch("app.api.images.get_status", return_value={"status": "queued"})
def test_smoke_poll_image_job(mock_get):
    assert client.get("/api/image-job/abc").status_code == 200


# ── styles ─────────────────────────────────────────────────────────────────────

@patch("app.api.styles.upsert_style")
def test_smoke_style_upsert(mock_upsert):
    assert client.post("/api/style", json={
        "name": "Торжественный",
        "text": "Этот стиль написания используется для официальных биографий известных людей России." * 2,
    }).status_code == 200


def test_smoke_style_too_short():
    assert client.post("/api/style", json={"name": "X", "text": "кратко"}).status_code == 400
