"""Tests for api/images.py endpoints."""
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ── POST /image-job ────────────────────────────────────────────────────────────

@patch("app.api.images.set_status")
@patch("app.api.images.enqueue_job")
def test_start_image_job_ok(mock_enqueue, mock_status):
    r = client.post("/api/image-job?name=Яшин")
    assert r.status_code == 200
    body = r.json()
    assert "job_id" in body
    assert body["status"] == "queued"
    assert body["name"] == "Яшин"
    mock_status.assert_called_once()
    mock_enqueue.assert_called_once()


@patch("app.api.images.set_status")
@patch("app.api.images.enqueue_job", side_effect=Exception("Redis down"))
def test_start_image_job_queue_unavailable(mock_enqueue, mock_status):
    r = client.post("/api/image-job?name=Яшин")
    assert r.status_code == 503


# ── GET /image-job/{job_id} ────────────────────────────────────────────────────

@patch("app.api.images.get_status", return_value={"status": "done", "detail": {"accepted": ["/static/accepted_images/a.jpg"]}})
def test_poll_image_job(mock_get):
    r = client.get("/api/image-job/abc123")
    assert r.status_code == 200
    assert r.json()["status"] == "done"
    assert r.json()["job_id"] == "abc123"


@patch("app.api.images.get_status", return_value={"status": "unknown"})
def test_poll_image_job_unknown(mock_get):
    r = client.get("/api/image-job/nonexistent")
    assert r.status_code == 200
    assert r.json()["status"] == "unknown"


# ── GET /images/{name} ─────────────────────────────────────────────────────────

@patch("app.api.images._glob.glob", return_value=["/app/static/accepted_images/a_frame0.jpg",
                                                    "/app/static/accepted_images/b_frame3.jpg"])
def test_list_accepted_images(mock_glob):
    r = client.get("/api/images/Яшин")
    assert r.status_code == 200
    assert len(r.json()["images"]) == 2
    assert r.json()["images"][0].startswith("/static/accepted_images/")
