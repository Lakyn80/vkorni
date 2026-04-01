import tempfile
import os
from unittest.mock import patch

from app.services.vkorny_export import _absolute_attachment_url, _prepare_export_photo, _upload_attachment, send_profile


class DummyResponse:
    def __init__(self, payload: dict, ok: bool = True, status_code: int = 200, text: str = ""):
        self._payload = payload
        self.ok = ok
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._payload


def test_absolute_attachment_url_normalizes_relative_path():
    assert _absolute_attachment_url("/data/attachments/1/1-photo.jpg") == "https://vkorni.com/data/attachments/1/1-photo.jpg"


@patch("app.services.vkorny_export.requests.post")
def test_upload_attachment_returns_absolute_view_url(mock_post):
    mock_post.side_effect = [
        DummyResponse({"key": "upload-key"}),
        DummyResponse({"attachment": {"attachment_id": 42, "direct_url": "/data/attachments/1/42-photo.jpg"}}),
    ]

    fd, path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    try:
        result = _upload_attachment(path)
    finally:
        os.remove(path)

    assert result == {
        "attachment_id": 42,
        "view_url": "https://vkorni.com/data/attachments/1/42-photo.jpg",
    }


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
    "view_url": "https://vkorni.com/data/attachments/1/42-photo.jpg",
})
@patch("app.services.vkorny_export.requests.post")
def test_send_profile_creates_thread_only_after_static_attachment(mock_post, mock_upload, mock_prepare):
    mock_post.return_value = DummyResponse({"thread": {"thread_id": 99}})

    result = send_profile("Тест", "Биография", ["/static/photos/Test/a.webp"])

    assert result["status"] == "OK"
    assert result["thread_id"] == 99
    assert result["attachment_id"] == 42
    sent_body = mock_post.call_args.kwargs["data"].decode("utf-8")
    assert "attachment_ids%5B0%5D=42" in sent_body


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
