from unittest.mock import patch

from app.services.export_service import export_profile_to_vkorni


@patch("app.services.export_service.store_exported_profile_snapshot")
@patch("app.services.export_service._archive_framed_image", return_value="/app/static/exported_profiles/abc/portrait.jpg")
@patch("app.services.export_service.add_export_record")
@patch(
    "app.services.export_service.send_profile",
    return_value={
        "status": "OK",
        "thread_id": 42,
        "url": "https://vkorni.com/threads/42/",
        "attachment_id": 77,
        "attachment_url": "https://backend.example/static/exported_profiles/xenforo_full/77-photo.webp",
        "stable_image_path": "/app/static/exported_profiles/xenforo_full/77-photo.webp",
        "source_photo_url": "https://example.com/a.jpg",
        "selected_photo_url": "/static/photos/Test/a.webp",
        "image_origin": "framed_local",
        "export_path": "/app/static/accepted_images/a_frame1.jpg",
        "frame_id": 1,
    },
)
def test_export_service_stores_snapshot_on_success(mock_send, mock_record, mock_archive, mock_store):
    result = export_profile_to_vkorni(
        name="Тест",
        text="Биография",
        photos=["/static/photos/Test/a.webp", "/static/photos/Test/b.webp"],
        photo_source_url="https://example.com/a.jpg",
        selected_photo_url="/static/photos/Test/a.webp",
        photo_sources={"/static/photos/Test/a.webp": "https://example.com/a.jpg"},
        export_kind="manual",
        frame_id=1,
    )

    assert result["status"] == "OK"
    mock_record.assert_called_once()
    mock_archive.assert_not_called()
    mock_store.assert_called_once()
    assert mock_store.call_args.kwargs["selected_photo_url"] == "/static/photos/Test/a.webp"
    assert mock_store.call_args.kwargs["framed_image_path"] == "/app/static/exported_profiles/xenforo_full/77-photo.webp"


@patch("app.services.export_service.store_exported_profile_snapshot")
@patch("app.services.export_service.add_export_record")
@patch("app.services.export_service.send_profile", side_effect=RuntimeError("boom"))
def test_export_service_converts_crash_to_error_result(mock_send, mock_record, mock_store):
    result = export_profile_to_vkorni(
        name="Тест",
        text="Биография",
        photos=["/static/photos/Test/a.webp"],
        export_kind="bulk",
    )

    assert result["status"] == "ERROR"
    assert result["error"] == "boom"
    mock_record.assert_called_once()
    mock_store.assert_not_called()
