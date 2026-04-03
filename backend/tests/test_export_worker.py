from unittest.mock import patch

from app.workers.export_worker import schedule_bulk_export, run_bulk_export_item, run_bulk_export_watchdog


@patch("app.workers.export_worker._schedule_watchdog")
@patch("app.workers.export_worker._schedule_export_attempt")
@patch("app.workers.export_worker.get_bulk_export")
def test_schedule_bulk_export_queues_only_pending_jobs(mock_get_bulk_export, mock_schedule_attempt, mock_schedule_watchdog):
    mock_get_bulk_export.return_value = {
        "results": [
            {"name": "A", "status": "pending", "attempts": 0},
            {"name": "B", "status": "done", "attempts": 1},
            {"name": "C", "status": "retrying", "attempts": 2},
        ]
    }

    schedule_bulk_export("eid-1")

    mock_schedule_attempt.assert_called_once_with("eid-1", "A", current_state={"name": "A", "status": "pending", "attempts": 0})
    mock_schedule_watchdog.assert_called_once_with("eid-1")


@patch("app.workers.export_worker.update_job")
@patch("app.workers.export_worker.export_profile_to_vkorni")
@patch("app.workers.export_worker.get_biography")
@patch("app.workers.export_worker.get_bulk_export_job")
def test_run_bulk_export_item_marks_done_on_success(mock_get_job, mock_get_bio, mock_export, mock_update):
    mock_get_job.return_value = {"status": "queued", "attempts": 0}
    mock_get_bio.return_value = {
        "name": "Test",
        "text": "Bio",
        "photos": ["/static/photos/Test/a.webp"],
        "photo_sources": {"/static/photos/Test/a.webp": "https://example.com/a.webp"},
        "birth": "1900",
        "death": "1990",
    }
    mock_export.return_value = {"status": "OK", "url": "https://vkorni.com/threads/1/"}

    run_bulk_export_item("eid-1", "Test")

    assert mock_update.call_args_list[0].kwargs["status"] == "running"
    assert mock_update.call_args_list[0].kwargs["attempts"] == 1
    assert mock_update.call_args_list[1].kwargs["status"] == "done"
    assert mock_update.call_args_list[1].kwargs["url"] == "https://vkorni.com/threads/1/"


@patch("app.workers.export_worker._schedule_retry_or_fail")
@patch("app.workers.export_worker.update_job")
@patch("app.workers.export_worker.export_profile_to_vkorni")
@patch("app.workers.export_worker.get_biography")
@patch("app.workers.export_worker.get_bulk_export_job")
def test_run_bulk_export_item_retries_failed_export(mock_get_job, mock_get_bio, mock_export, mock_update, mock_retry):
    mock_get_job.return_value = {"status": "queued", "attempts": 0}
    mock_get_bio.return_value = {
        "name": "Test",
        "text": "Bio",
        "photos": [],
        "photo_sources": {},
    }
    mock_export.return_value = {"status": "ERROR", "error": "temporary error"}

    run_bulk_export_item("eid-1", "Test")

    assert mock_update.call_args_list[0].kwargs["status"] == "running"
    mock_retry.assert_called_once_with("eid-1", "Test", 1, "temporary error")


@patch("app.workers.export_worker._schedule_watchdog")
@patch("app.workers.export_worker._schedule_export_attempt")
@patch("app.workers.export_worker.update_job")
@patch("app.workers.export_worker.time.time", return_value=1000.0)
@patch("app.workers.export_worker.get_bulk_export")
def test_watchdog_resumes_stalled_running_job(mock_get_bulk_export, mock_time, mock_update, mock_schedule_attempt, mock_schedule_watchdog):
    mock_get_bulk_export.return_value = {
        "results": [
            {"name": "A", "status": "running", "attempts": 1, "updated_at": 700.0, "error": "timeout"},
            {"name": "B", "status": "pending", "attempts": 0, "updated_at": 1000.0},
            {"name": "C", "status": "done", "attempts": 1, "updated_at": 1000.0},
        ]
    }
    mock_update.return_value = {"status": "retrying", "attempts": 1, "updated_at": 1000.0, "error": "timeout"}

    run_bulk_export_watchdog("eid-1")

    mock_update.assert_called_once()
    assert mock_update.call_args.kwargs["status"] == "retrying"
    assert mock_schedule_attempt.call_count == 2
    mock_schedule_watchdog.assert_called_once_with("eid-1")
