from unittest.mock import patch

from app.workers.export_worker import schedule_bulk_export, run_bulk_export_item, run_bulk_export_watchdog


@patch("app.workers.export_worker.enqueue_job")
def test_schedule_watchdog_uses_exports_queue(mock_enqueue):
    from app.workers.export_worker import _schedule_watchdog

    _schedule_watchdog("eid-1", delay_seconds=30)

    assert mock_enqueue.call_args.kwargs["queue"] == "exports"
    assert mock_enqueue.call_args.kwargs["delay_seconds"] == 30


@patch("app.workers.export_worker.enqueue_job")
@patch("app.workers.export_worker.update_job")
@patch("app.workers.export_worker.get_bulk_export_job")
def test_schedule_export_attempt_uses_exports_queue(mock_get_job, mock_update, mock_enqueue):
    from app.workers.export_worker import _schedule_export_attempt

    mock_get_job.return_value = {"status": "pending", "attempts": 0}

    _schedule_export_attempt("eid-1", "A")

    assert mock_update.call_args.kwargs["status"] == "queued"
    assert mock_enqueue.call_args.kwargs["queue"] == "exports"


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
@patch("app.workers.export_worker.get_attachment_limit_cooldown", return_value=None)
@patch("app.workers.export_worker.get_bulk_export_job")
def test_run_bulk_export_item_marks_done_on_success(mock_get_job, mock_get_cooldown, mock_get_bio, mock_export, mock_update):
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
@patch("app.workers.export_worker.get_attachment_limit_cooldown", return_value=None)
@patch("app.workers.export_worker.get_bulk_export_job")
def test_run_bulk_export_item_retries_failed_export(mock_get_job, mock_get_cooldown, mock_get_bio, mock_export, mock_update, mock_retry):
    mock_get_job.return_value = {"status": "queued", "attempts": 0}
    mock_get_bio.return_value = {
        "name": "Test",
        "text": "Bio",
        "photos": [],
        "photo_sources": {},
    }
    mock_export.return_value = {"status": "ERROR", "error": "temporary error"}

    with patch("app.workers.export_worker.get_photos_by_person", return_value=[]), \
         patch("app.workers.export_worker.fetch_person_images", return_value=[]), \
         patch("app.workers.export_worker.fetch_person_from_wikipedia", return_value=None):
        run_bulk_export_item("eid-1", "Test")

    assert mock_update.call_args_list[0].kwargs["status"] == "running"
    mock_retry.assert_called_once_with("eid-1", "Test", 1, "temporary error")


@patch("app.workers.export_worker.update_job")
@patch("app.workers.export_worker.export_profile_to_vkorni")
@patch("app.workers.export_worker.get_biography")
@patch("app.workers.export_worker.get_attachment_limit_cooldown", return_value=None)
@patch("app.workers.export_worker.get_bulk_export_job")
def test_run_bulk_export_item_hydrates_missing_photos_before_export(mock_get_job, mock_get_cooldown, mock_get_bio, mock_export, mock_update):
    mock_get_job.return_value = {"status": "queued", "attempts": 0}
    mock_get_bio.return_value = {
        "name": "Test",
        "text": "Bio",
        "photos": [],
        "photo_sources": {},
        "birth": "1900",
        "death": "1990",
    }
    mock_export.return_value = {"status": "OK", "url": "https://vkorni.com/threads/1/"}

    with patch("app.workers.export_worker.get_photos_by_person", return_value=[]), \
         patch(
             "app.workers.export_worker.fetch_person_images",
             return_value=[{"file_path": "/static/photos/Test/a.webp", "source_url": "https://example.com/a.jpg"}],
         ), \
         patch("app.workers.export_worker.fetch_person_from_wikipedia") as mock_wiki, \
         patch("app.workers.export_worker.set_biography") as mock_set_biography:
        run_bulk_export_item("eid-1", "Test")

    assert mock_export.call_args.kwargs["photos"] == ["/static/photos/Test/a.webp"]
    assert mock_export.call_args.kwargs["photo_source_url"] == "https://example.com/a.jpg"
    assert mock_export.call_args.kwargs["selected_photo_url"] == "/static/photos/Test/a.webp"
    mock_set_biography.assert_called_once()
    mock_wiki.assert_not_called()
    assert mock_update.call_args_list[-1].kwargs["status"] == "done"


@patch("app.workers.export_worker.update_job")
@patch("app.workers.export_worker.export_profile_to_vkorni")
@patch("app.workers.export_worker.get_biography", return_value=None)
@patch("app.workers.export_worker.get_attachment_limit_cooldown", return_value=None)
@patch("app.workers.export_worker.get_bulk_export_job")
def test_run_bulk_export_item_generates_missing_cache_before_export(
    mock_get_job,
    mock_get_cooldown,
    mock_get_bio,
    mock_export,
    mock_update,
):
    mock_get_job.return_value = {"status": "queued", "attempts": 0}
    mock_export.return_value = {"status": "OK", "url": "https://vkorni.com/threads/1/"}

    with patch(
        "app.workers.export_worker.fetch_person_from_wikipedia",
        return_value={"name": "Test", "images": ["/static/photos/Test/a.webp"]},
    ), \
         patch(
             "app.workers.export_worker.generate_biography_text",
             return_value={
                 "name": "Test",
                 "biography": "Generated bio",
                 "birth": "1900",
                 "death": "1990",
                 "used_fallback": False,
                 "warnings": [],
             },
         ), \
         patch("app.workers.export_worker.fetch_person_images", return_value=[]), \
         patch("app.workers.export_worker.get_photos_by_person", return_value=[]), \
         patch("app.workers.export_worker.set_biography") as mock_set_biography:
        run_bulk_export_item("eid-1", "Test")

    mock_set_biography.assert_called_once()
    assert mock_export.call_args.kwargs["name"] == "Test"
    assert mock_export.call_args.kwargs["text"] == "Generated bio"
    assert mock_export.call_args.kwargs["photos"] == ["/static/photos/Test/a.webp"]
    assert mock_update.call_args_list[-1].kwargs["status"] == "done"


@patch("app.workers.export_worker._schedule_export_attempt")
@patch("app.workers.export_worker.update_job")
def test_schedule_retry_or_fail_marks_non_retryable_error_failed(mock_update, mock_schedule_attempt):
    from app.workers.export_worker import _schedule_retry_or_fail

    _schedule_retry_or_fail("eid-1", "Test", 1, "No exportable photo found for static XenForo upload")

    mock_update.assert_called_once()
    assert mock_update.call_args.kwargs["status"] == "failed"
    mock_schedule_attempt.assert_not_called()


@patch("app.workers.export_worker.set_attachment_limit_cooldown")
@patch("app.workers.export_worker._schedule_export_attempt")
@patch("app.workers.export_worker.update_job")
def test_schedule_retry_or_fail_adds_global_cooldown_for_attachment_limit(mock_update, mock_schedule_attempt, mock_set_cooldown):
    from app.workers.export_worker import _schedule_retry_or_fail

    mock_update.return_value = {"status": "retrying", "attempts": 1, "updated_at": 1000.0, "error": "limit"}
    _schedule_retry_or_fail(
        "eid-1",
        "Test",
        1,
        "XenForo attachment upload failed (400, you_have_reached_the_maximum_limit_for_attachment_uploads): limit",
    )

    mock_set_cooldown.assert_called_once()
    mock_schedule_attempt.assert_called_once()
    assert mock_schedule_attempt.call_args.kwargs["delay_seconds"] >= 900


@patch("app.workers.export_worker._schedule_export_attempt")
@patch("app.workers.export_worker.update_job")
@patch("app.workers.export_worker.get_attachment_limit_cooldown")
@patch("app.workers.export_worker.get_bulk_export_job")
def test_run_bulk_export_item_defers_when_global_attachment_cooldown_is_active(mock_get_job, mock_get_cooldown, mock_update, mock_schedule_attempt):
    mock_get_job.return_value = {"status": "queued", "attempts": 0}
    mock_get_cooldown.return_value = {"until": 2000.0, "reason": "attachment limit"}
    mock_update.return_value = {"status": "retrying", "attempts": 0, "updated_at": 1000.0, "error": "attachment limit"}

    with patch("app.workers.export_worker.time.time", return_value=1000.0):
        run_bulk_export_item("eid-1", "Test")

    mock_update.assert_called_once()
    assert mock_update.call_args.kwargs["status"] == "retrying"
    mock_schedule_attempt.assert_called_once()
    assert mock_schedule_attempt.call_args.kwargs["delay_seconds"] == 1000


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


@patch("app.workers.export_worker._schedule_watchdog")
@patch("app.workers.export_worker._schedule_export_attempt")
@patch("app.workers.export_worker.update_job")
@patch("app.workers.export_worker.time.time", return_value=1000.0)
@patch("app.workers.export_worker.get_bulk_export")
def test_watchdog_resumes_stalled_queued_job(mock_get_bulk_export, mock_time, mock_update, mock_schedule_attempt, mock_schedule_watchdog):
    mock_get_bulk_export.return_value = {
        "results": [
            {"name": "A", "status": "queued", "attempts": 0, "updated_at": 700.0, "error": None},
            {"name": "B", "status": "done", "attempts": 1, "updated_at": 1000.0},
        ]
    }
    mock_update.return_value = {"status": "retrying", "attempts": 0, "updated_at": 1000.0, "error": "Bulk export resumed after stalled queued job"}

    run_bulk_export_watchdog("eid-1")

    mock_update.assert_called_once()
    assert mock_update.call_args.kwargs["status"] == "retrying"
    assert "stalled queued job" in mock_update.call_args.kwargs["error"]
    mock_schedule_attempt.assert_called_once_with(
        "eid-1",
        "A",
        current_state={"status": "retrying", "attempts": 0, "updated_at": 1000.0, "error": "Bulk export resumed after stalled queued job"},
    )
    mock_schedule_watchdog.assert_called_once_with("eid-1")
