import os
import tempfile
from unittest.mock import patch

from app.services.vkorny_export import _absolute_attachment_url, _create_thread, _prepare_export_photo, _upload_attachment, send_profile


class DummyResponse:
    def __init__(self, payload: dict, ok: bool = True, status_code: int = 200, text: str = "", content: bytes = b""):
        self._payload = payload
        self.ok = ok
        self.status_code = status_code
        self.text = text
        self.content = content

    def json(self):
        return self._payload


def test_absolute_attachment_url_normalizes_relative_path():
    assert _absolute_attachment_url("/data/attachments/1/1-photo.jpg") == "https://vkorni.com/data/attachments/1/1-photo.jpg"


@patch("app.services.vkorny_export.requests.post")
def test_upload_attachment_returns_absolute_view_url(mock_post):
    mock_post.side_effect = [
        DummyResponse({"key": "upload-key"}),
        DummyResponse(
            {
                "attachment": {
                    "attachment_id": 42,
                    "direct_url": "/attachments/example.42/?hash=abc",
                    "filename": "example.webp",
                    "width": 800,
                    "height": 1000,
                }
            }
        ),
    ]

    fd, path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    try:
        result = _upload_attachment(path)
    finally:
        os.remove(path)

    assert result == {
        "attachment_id": 42,
        "full_size_source": {
            "download_url": "https://vkorni.com/attachments/example.42/?hash=abc",
            "filename": "example.webp",
            "width": 800,
            "height": 1000,
        },
    }


@patch("app.services.vkorny_export.requests.post")
def test_upload_attachment_strips_hash_from_static_attachment_url(mock_post):
    mock_post.side_effect = [
        DummyResponse({"key": "upload-key"}),
        DummyResponse(
            {
                "attachment": {
                    "attachment_id": 42,
                    "direct_url": "/attachments/example.42/?hash=RkG2CrX64j",
                    "filename": "example.webp",
                    "width": 800,
                    "height": 1000,
                }
            }
        ),
    ]

    fd, path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    try:
        result = _upload_attachment(path)
    finally:
        os.remove(path)

    assert result == {
        "attachment_id": 42,
        "full_size_source": {
            "download_url": "https://vkorni.com/attachments/example.42/?hash=RkG2CrX64j",
            "filename": "example.webp",
            "width": 800,
            "height": 1000,
        },
    }


@patch("app.services.vkorny_export.requests.post")
def test_upload_attachment_rejects_hash_thumbnail_url(mock_post):
    mock_post.side_effect = [
        DummyResponse({"key": "upload-key"}),
        DummyResponse(
            {
                "attachment": {
                    "attachment_id": 42,
                    "thumbnail_url": "/attachments/irina_rodnina_2018_frame8-webp.676/?hash=O50sMzkRy1xb85Yq34VKL5ejAKIZYkiR",
                }
            }
        ),
    ]

    fd, path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    try:
        result = _upload_attachment(path)
    finally:
        os.remove(path)

    assert result is None


@patch("app.services.vkorny_export.VKORNI_API_KEY", "test-key")
@patch("app.services.vkorny_export.VKORNI_NODE_ID", "8")
@patch("app.services.vkorny_export._prepare_export_photo", return_value={
    "export_path": "/tmp/photo.jpg",
    "cleanup_paths": [],
    "source_photo_path": "/static/photos/Test/a.webp",
    "source_photo_url": None,
    "image_origin": "framed_local",
})
@patch("app.services.vkorny_export._upload_attachment", return_value={
    "attachment_id": 42,
    "full_size_source": {
        "download_url": "https://vkorni.com/attachments/example.42/?hash=abc",
        "filename": "example.webp",
        "width": 800,
        "height": 1000,
    },
})
@patch("app.services.vkorny_export._download_and_store_internal_image", return_value={
    "local_path": "/app/static/exported_profiles/xenforo_full/42-example.webp",
    "public_url": "https://backend.example/static/exported_profiles/xenforo_full/42-example.webp",
})
@patch("app.services.vkorny_export.requests.post")
def test_send_profile_creates_thread_only_after_internal_image_storage(mock_post, mock_store_image, mock_upload, mock_prepare):
    mock_post.return_value = DummyResponse({"thread": {"thread_id": 99}})

    result = send_profile("Тест", "Биография", ["/static/photos/Test/a.webp"])

    assert result["status"] == "OK"
    assert result["thread_id"] == 99
    assert result["attachment_id"] == 42
    assert result["attachment_url"] == "https://vkorni.com/attachments/example.42/?hash=abc"
    sent_body = mock_post.call_args.kwargs["data"].decode("utf-8")
    assert "attachment_ids%5B0%5D=42" in sent_body
    assert "%5BATTACH%3Dfull%5D42%5B%2FATTACH%5D" in sent_body


@patch("app.services.vkorny_export.VKORNI_API_KEY", "test-key")
@patch("app.services.vkorny_export.VKORNI_NODE_ID", "8")
@patch("app.services.vkorny_export._prepare_export_photo", return_value={
    "export_path": "/tmp/photo.jpg",
    "cleanup_paths": [],
    "source_photo_path": "/static/photos/Test/a.webp",
    "source_photo_url": None,
    "image_origin": "framed_local",
})
@patch("app.services.vkorny_export._upload_attachment", return_value=None)
@patch("app.services.vkorny_export.requests.post")
def test_send_profile_does_not_create_thread_when_attachment_upload_fails(mock_post, mock_upload, mock_prepare):
    result = send_profile("Тест", "Биография", ["/static/photos/Test/a.webp"])

    assert result["status"] == "ERROR"
    assert "thread was not created" in result["error"]
    mock_post.assert_not_called()


@patch("app.services.vkorny_export.VKORNI_API_KEY", "test-key")
@patch("app.services.vkorny_export.VKORNI_NODE_ID", "8")
@patch("app.services.vkorny_export._prepare_export_photo", return_value={
    "export_path": "/tmp/photo.jpg",
    "cleanup_paths": [],
    "source_photo_path": "/static/photos/Test/a.webp",
    "source_photo_url": None,
    "image_origin": "framed_local",
})
@patch("app.services.vkorny_export._upload_attachment", return_value={
    "attachment_id": 42,
    "full_size_source": {
        "download_url": "https://vkorni.com/attachments/example.42/?hash=abc",
        "filename": "example.webp",
        "width": 800,
        "height": 1000,
    },
})
@patch("app.services.vkorny_export._download_and_store_internal_image", return_value=None)
@patch("app.services.vkorny_export.requests.post")
def test_send_profile_continues_when_internal_image_storage_fails(mock_post, mock_store_image, mock_upload, mock_prepare):
    mock_post.return_value = DummyResponse({"thread": {"thread_id": 99}})

    result = send_profile("Тест", "Биография", ["/static/photos/Test/a.webp"])

    assert result["status"] == "OK"
    assert result["thread_id"] == 99
    assert result["attachment_url"] == "https://vkorni.com/attachments/example.42/?hash=abc"
    assert result["stable_image_path"] is None
    mock_post.assert_called_once()


@patch("app.services.vkorny_export._download_source_photo", return_value="/tmp/downloaded.webp")
@patch("app.services.vkorny_export.os.path.exists", return_value=False)
@patch("app.services.frame_service.compose_portrait", return_value="/tmp/downloaded_frame.jpg")
def test_prepare_export_photo_accepts_absolute_photo_url(mock_frame, mock_exists, mock_download):
    result = _prepare_export_photo(
        ["https://upload.wikimedia.org/example/Test.webp"],
        birth="1934",
        death="1968",
        photo_source_url=None,
    )

    assert result is not None
    assert result["export_path"] == "/tmp/downloaded_frame.jpg"
    assert result["source_photo_url"] == "https://upload.wikimedia.org/example/Test.webp"
    assert result["image_origin"] == "framed_source_download"


@patch("app.services.vkorny_export.os.path.exists", side_effect=[False, True])
@patch("app.services.frame_service.compose_portrait", return_value="/app/static/accepted_images/second_frame.jpg")
def test_prepare_export_photo_falls_back_to_next_existing_local_photo(mock_frame, mock_exists):
    result = _prepare_export_photo(
        ["/static/photos/Test/missing.webp", "/static/photos/Test/second.webp"],
        birth="1934",
        death="1968",
        photo_source_url=None,
    )

    assert result is not None
    assert result["source_photo_path"] == "/static/photos/Test/second.webp"
    assert result["export_path"] == "/app/static/accepted_images/second_frame.jpg"
    assert result["image_origin"] == "framed_local"


@patch("app.services.vkorny_export.time.sleep")
@patch("app.services.vkorny_export.requests.post")
def test_upload_attachment_retries_transient_new_key_failure(mock_post, mock_sleep):
    mock_post.side_effect = [
        DummyResponse({}, ok=False, status_code=503, text="temporary outage"),
        DummyResponse({"key": "upload-key"}),
        DummyResponse(
            {
                "attachment": {
                    "attachment_id": 42,
                    "direct_url": "/attachments/example.42/?hash=abc",
                    "filename": "example.webp",
                    "width": 800,
                    "height": 1000,
                }
            }
        ),
    ]

    fd, path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    try:
        result = _upload_attachment(path)
    finally:
        os.remove(path)

    assert result == {
        "attachment_id": 42,
        "full_size_source": {
            "download_url": "https://vkorni.com/attachments/example.42/?hash=abc",
            "filename": "example.webp",
            "width": 800,
            "height": 1000,
        },
    }
    assert mock_post.call_count == 3
    mock_sleep.assert_called_once()


@patch("app.services.vkorny_export.requests.post")
def test_upload_attachment_surfaces_xenforo_error_code(mock_post):
    mock_post.side_effect = [
        DummyResponse({"key": "upload-key"}),
        DummyResponse(
            {
                "errors": [
                    {
                        "code": "you_have_reached_the_maximum_limit_for_attachment_uploads",
                        "message": "Лимит загрузок вложений достигнут.",
                    }
                ]
            },
            ok=False,
            status_code=400,
            text='{"errors":[{"code":"you_have_reached_the_maximum_limit_for_attachment_uploads"}]}',
        ),
    ]

    fd, path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    try:
        result = _upload_attachment(path)
    finally:
        os.remove(path)

    assert result is not None
    assert "you_have_reached_the_maximum_limit_for_attachment_uploads" in result["error"]


@patch("app.services.vkorny_export.time.sleep")
@patch("app.services.vkorny_export.requests.post")
@patch("app.services.vkorny_export.VKORNI_NODE_ID", "8")
def test_create_thread_retries_transient_failure(mock_post, mock_sleep):
    mock_post.side_effect = [
        DummyResponse({}, ok=False, status_code=503, text="temporary outage"),
        DummyResponse({"thread": {"thread_id": 99}}),
    ]

    result = _create_thread("Тест", "Биография", [42])

    assert result == {
        "status": "OK",
        "thread_id": 99,
        "url": "https://vkorni.com/threads/99/",
    }
    assert mock_post.call_count == 2
    mock_sleep.assert_called_once()
