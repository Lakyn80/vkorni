"""Tests for api/batch.py endpoints."""
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

BATCH_STATUS = {
    "batch_id": "abc123",
    "total": 3,
    "queued": 1,
    "running": 1,
    "done": 1,
    "failed": 0,
    "results": [
        {"name": "Яшин", "status": "done"},
        {"name": "Харламов", "status": "running"},
        {"name": "Цой", "status": "queued"},
    ],
}


# ── POST /batch ────────────────────────────────────────────────────────────────

@patch("app.api.batch._create_batch", return_value="abc123")
@patch("app.api.batch.enqueue_job")
def test_create_batch_ok(mock_enqueue, mock_create):
    r = client.post("/api/batch", json={"names": ["Яшин", "Харламов", "Цой"]})
    assert r.status_code == 200
    body = r.json()
    assert body["batch_id"] == "abc123"
    assert body["total"] == 3
    assert mock_enqueue.call_count == 3


@patch("app.api.batch._create_batch", return_value="abc123")
@patch("app.api.batch.enqueue_job")
def test_create_batch_strips_empty_names(mock_enqueue, mock_create):
    r = client.post("/api/batch", json={"names": ["Яшин", "  ", "", "Цой"]})
    assert r.status_code == 200
    assert r.json()["total"] == 2


def test_create_batch_empty_list():
    r = client.post("/api/batch", json={"names": []})
    assert r.status_code == 400


def test_create_batch_too_many_names():
    r = client.post("/api/batch", json={"names": ["Имя"] * 501})
    assert r.status_code == 400


@patch("app.api.batch._create_batch", side_effect=Exception("Redis down"))
def test_create_batch_queue_unavailable(mock_create):
    r = client.post("/api/batch", json={"names": ["Яшин"]})
    assert r.status_code == 503


# ── GET /batch/{id} ────────────────────────────────────────────────────────────

@patch("app.api.batch.get_batch_status", return_value=BATCH_STATUS)
def test_get_batch_ok(mock_status):
    r = client.get("/api/batch/abc123")
    assert r.status_code == 200
    assert r.json()["batch_id"] == "abc123"
    assert r.json()["total"] == 3


@patch("app.api.batch.get_batch_status", return_value=None)
def test_get_batch_not_found(mock_status):
    r = client.get("/api/batch/nonexistent")
    assert r.status_code == 404


# ── POST /batch/{id}/retry ─────────────────────────────────────────────────────

@patch("app.api.batch.get_failed_names", return_value=["Цой"])
@patch("app.api.batch.update_job")
@patch("app.api.batch.enqueue_job")
def test_retry_batch_ok(mock_enqueue, mock_update, mock_failed):
    r = client.post("/api/batch/abc123/retry")
    assert r.status_code == 200
    assert r.json()["retried"] == 1
    mock_enqueue.assert_called_once()


@patch("app.api.batch.get_failed_names", return_value=[])
def test_retry_batch_no_failures(mock_failed):
    r = client.post("/api/batch/abc123/retry")
    assert r.status_code == 200
    assert r.json()["retried"] == 0
