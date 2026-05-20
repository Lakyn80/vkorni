import sys
import types
from unittest.mock import patch

fake_chroma_client = types.ModuleType("app.db.chroma_client")
fake_chroma_client.get_style = lambda name: None
fake_chroma_client.search_styles = lambda query, top_k=3: []
fake_chroma_client.upsert_style = lambda name, text: None
fake_chroma_client.add_document = lambda name, text: None
sys.modules.setdefault("app.db.chroma_client", fake_chroma_client)

from app.services.deepseek_service import DeepSeekServiceError
from app.workers.bio_worker import process_biography


FAKE_PERSON = {
    "name": "Астафуров Константин Алексеевич",
    "summary_text": "Советский военный деятель.",
    "birth": "1910",
    "death": "1943",
    "images": [],
}

LONG_TEXT = (
    "Астафуров Константин Алексеевич остается в памяти благодаря подтвержденным сведениям о его жизни и служении. "
    "Его биографическая заметка опирается только на доступные данные и сохраняет спокойный документальный тон."
)


@patch("app.workers.bio_worker.update_job")
@patch("app.workers.bio_worker.set_biography")
@patch("app.workers.bio_worker.get_photos_by_person", return_value=[])
@patch("app.workers.bio_worker._fetch_images", return_value=[])
@patch("app.workers.bio_worker.is_unique_enough", return_value=False)
@patch("app.workers.bio_worker.generate_text", return_value=(LONG_TEXT, "factual_memorial"))
@patch("app.workers.bio_worker.get_style_context", return_value=None)
@patch("app.workers.bio_worker._fetch_wiki", return_value=FAKE_PERSON)
def test_process_biography_uses_fallback_when_uniqueness_check_fails(
    mock_wiki,
    mock_style,
    mock_generate,
    mock_unique,
    mock_images,
    mock_photos,
    mock_set,
    mock_update,
):
    result = process_biography("batch-1", "Астафуров Константин Алексеевич")

    assert result["status"] == "done"
    assert result["used_fallback"] is False
    assert result["text"]
    assert "🕯️ Биография" in result["text"]
    mock_set.assert_called_once()
    assert mock_update.call_args_list[-1].kwargs["status"] == "done"


@patch("app.workers.bio_worker.update_job")
@patch("app.workers.bio_worker.set_biography")
@patch("app.workers.bio_worker.get_photos_by_person", return_value=[])
@patch("app.workers.bio_worker._fetch_images", return_value=[])
@patch("app.workers.bio_worker.is_unique_enough", return_value=True)
@patch("app.workers.bio_worker.generate_text", side_effect=DeepSeekServiceError("timeout"))
@patch("app.workers.bio_worker.get_style_context", return_value=None)
@patch("app.workers.bio_worker._fetch_wiki", return_value=FAKE_PERSON)
def test_process_biography_uses_fallback_when_llm_fails(
    mock_wiki,
    mock_style,
    mock_generate,
    mock_unique,
    mock_images,
    mock_photos,
    mock_set,
    mock_update,
):
    result = process_biography("batch-1", "Астафуров Константин Алексеевич")

    assert result["status"] == "done"
    assert result["used_fallback"] is False
    assert result["text"]
    assert "🕊️ Память" in result["text"]
    mock_set.assert_called_once()
    assert mock_update.call_args_list[-1].kwargs["status"] == "done"


@patch("app.workers.bio_worker.update_job")
@patch("app.workers.bio_worker.set_biography")
@patch("app.workers.bio_worker.get_photos_by_person", return_value=[])
@patch("app.workers.bio_worker._fetch_images", return_value=[])
@patch("app.workers.bio_worker.is_unique_enough", return_value=True)
@patch("app.workers.bio_worker.generate_text", return_value=(LONG_TEXT, "factual_memorial"))
@patch("app.workers.bio_worker.get_style_context", return_value=None)
@patch("app.workers.bio_worker._fetch_wiki", side_effect=RuntimeError("wiki down"))
def test_process_biography_returns_done_fallback_when_wiki_fails(
    mock_wiki,
    mock_style,
    mock_generate,
    mock_unique,
    mock_images,
    mock_photos,
    mock_set,
    mock_update,
):
    result = process_biography("batch-1", "Астафуров Константин Алексеевич")

    assert result["status"] == "done"
    assert result["used_fallback"] is True
    assert result["text"]
    mock_set.assert_called_once()
    assert mock_update.call_args_list[-1].kwargs["status"] == "done"
