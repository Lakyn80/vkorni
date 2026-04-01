from unittest.mock import patch

from app.services.export_service import export_profile_to_vkorni


@patch("app.services.export_service.add_export_record")
@patch("app.services.export_service.send_profile", side_effect=RuntimeError("boom"))
def test_export_service_converts_crash_to_error_result(mock_send, mock_record):
    result = export_profile_to_vkorni(
        name="Тест",
        text="Биография",
        photos=["/static/photos/Test/a.webp"],
        export_kind="bulk",
    )

    assert result["status"] == "ERROR"
    assert result["error"] == "boom"
    mock_record.assert_called_once()
