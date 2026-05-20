"""Tests for api/biography.py endpoints."""
import sys
import types
from unittest.mock import patch

from fastapi.testclient import TestClient

fake_chroma_client = types.ModuleType("app.db.chroma_client")
fake_chroma_client.get_style = lambda name: None
fake_chroma_client.search_styles = lambda query, top_k=3: []
fake_chroma_client.upsert_style = lambda name, text: None
fake_chroma_client.add_document = lambda name, text: None
sys.modules.setdefault("app.db.chroma_client", fake_chroma_client)

from app.main import app
from app.db.redis_client import CacheUnavailableError
from app.services.deepseek_service import DeepSeekBillingError

client = TestClient(app)

FAKE_PERSON = {
    "name": "Лев Яшин",
    "summary_text": "Советский футбольный вратарь, олимпийский чемпион и чемпион Европы.",
    "birth": "22 октября 1929",
    "death": "20 марта 1990",
    "images": [],
}

LONG_TEXT = (
    "Лев Яшин остается одной из ключевых фигур в истории советского футбола. "
    "Его биография связана с выступлениями в воротах, международными турнирами и устойчивой памятью о спортивном наследии."
)


def assert_generate_contract(body: dict):
    assert body["status"] == "ok"
    assert isinstance(body["result"], dict)
    assert isinstance(body["result"]["biography"], str)
    assert body["result"]["biography"].strip()
    assert isinstance(body["result"]["used_fallback"], bool)
    assert isinstance(body["result"]["warnings"], list)
    assert body["text"] == body["result"]["biography"]


# ── /generate ──────────────────────────────────────────────────────────────────

@patch("app.api.biography.get_biography", return_value={"name": "Лев Яшин", "text": "cached", "photos": []})
def test_generate_returns_cache_with_contract(mock_get):
    r = client.post("/api/generate?name=Лев Яшин")
    assert r.status_code == 200
    body = r.json()
    assert_generate_contract(body)
    assert body["text"] == "cached"
    assert body["result"]["used_fallback"] is False
    mock_get.assert_called_once()


@patch("app.api.biography.get_biography", return_value=None)
@patch("app.api.biography.fetch_person_from_wikipedia", return_value=None)
@patch("app.api.biography.get_style_context", return_value="style")
@patch("app.api.biography.fetch_person_images", return_value=[])
@patch("app.api.biography.get_photos_by_person", return_value=[])
@patch("app.api.biography.set_biography")
def test_generate_wiki_not_found_returns_fallback_success(
    mock_set,
    mock_photos_repo,
    mock_images,
    mock_style,
    mock_wiki,
    mock_cache,
):
    r = client.post("/api/generate?name=НесуществующийЧеловек99")
    assert r.status_code == 200
    body = r.json()
    assert_generate_contract(body)
    assert body["name"] == "НесуществующийЧеловек99"
    assert body["result"]["used_fallback"] is True
    assert "НесуществующийЧеловек99" in body["result"]["biography"]
    mock_set.assert_called_once()


@patch("app.api.biography.get_biography", return_value=None)
@patch("app.api.biography.fetch_person_from_wikipedia", return_value=FAKE_PERSON)
@patch("app.api.biography.get_style_context", return_value="style")
@patch("app.api.biography.generate_text", return_value=(LONG_TEXT, "factual_memorial"))
@patch("app.api.biography.is_unique_enough", return_value=True)
@patch("app.api.biography.fetch_person_images", return_value=[])
@patch("app.api.biography.get_photos_by_person", return_value=[])
@patch("app.api.biography.set_biography")
def test_generate_new_profile_keeps_top_level_fields(
    mock_set,
    mock_photos_repo,
    mock_images,
    mock_unique,
    mock_gen,
    mock_style,
    mock_wiki,
    mock_cache,
):
    r = client.post("/api/generate?name=Лев Яшин")
    assert r.status_code == 200
    body = r.json()
    assert_generate_contract(body)
    assert body["name"] == "Лев Яшин"
    assert body["birth"] == "22 октября 1929"
    assert body["death"] == "20 марта 1990"
    assert body["result"]["used_fallback"] is False
    mock_set.assert_called_once()


@patch("app.api.biography.get_biography", return_value=None)
@patch("app.api.biography.fetch_person_from_wikipedia", return_value=FAKE_PERSON)
@patch("app.api.biography.get_style_context", return_value="style")
@patch("app.api.biography.generate_text", return_value=(LONG_TEXT, "factual_memorial"))
@patch("app.api.biography.is_unique_enough", return_value=True)
@patch("app.api.biography.fetch_person_images", return_value=[])
@patch("app.api.biography.get_photos_by_person", return_value=[])
@patch("app.api.biography.set_biography", side_effect=CacheUnavailableError("Redis down"))
def test_generate_returns_profile_when_cache_write_fails(
    mock_set,
    mock_photos_repo,
    mock_images,
    mock_unique,
    mock_gen,
    mock_style,
    mock_wiki,
    mock_cache,
):
    r = client.post("/api/generate?name=Лев Яшин")
    assert r.status_code == 200
    body = r.json()
    assert_generate_contract(body)
    assert body["name"] == "Лев Яшин"
    assert "🕯️ Биография" in body["text"]
    mock_set.assert_called_once()


@patch("app.api.biography.get_biography", return_value=None)
@patch("app.api.biography.fetch_person_from_wikipedia", return_value=FAKE_PERSON)
@patch("app.api.biography.get_style_context", return_value="style")
@patch("app.api.biography.generate_text", return_value=(LONG_TEXT, "factual_memorial"))
@patch("app.api.biography.is_unique_enough", return_value=True)
@patch("app.api.biography.fetch_person_images", return_value=[])
@patch("app.api.biography.get_photos_by_person", return_value=[])
@patch("app.api.biography.set_biography")
def test_generate_normalizes_comma_name(
    mock_set,
    mock_photos_repo,
    mock_images,
    mock_unique,
    mock_gen,
    mock_style,
    mock_wiki,
    mock_cache,
):
    r = client.post("/api/generate?name=Пушкин,%20Александр%20Сергеевич")
    assert r.status_code == 200
    body = r.json()
    assert_generate_contract(body)
    assert body["name"] == "Пушкин Александр Сергеевич"
    mock_wiki.assert_called_once_with("Пушкин Александр Сергеевич")
    mock_images.assert_called_once_with("Пушкин Александр Сергеевич")
    mock_set.assert_called_once()


@patch("app.api.biography.get_biography", return_value=None)
@patch("app.api.biography.fetch_person_from_wikipedia", return_value=FAKE_PERSON)
@patch("app.api.biography.get_style_context", return_value="style")
@patch("app.api.biography.generate_text", return_value=("кратко", "factual_memorial"))
@patch("app.api.biography.fetch_person_images", return_value=[])
@patch("app.api.biography.get_photos_by_person", return_value=[])
@patch("app.api.biography.set_biography")
def test_generate_short_text_uses_fallback(
    mock_set,
    mock_photos,
    mock_images,
    mock_gen,
    mock_style,
    mock_wiki,
    mock_cache,
):
    r = client.post("/api/generate?name=Лев Яшин")
    assert r.status_code == 200
    body = r.json()
    assert_generate_contract(body)
    assert body["result"]["used_fallback"] is False
    assert body["text"]
    assert "🕯️ Биография" in body["text"]


@patch("app.api.biography.get_biography", return_value=None)
@patch("app.api.biography.fetch_person_from_wikipedia", return_value=FAKE_PERSON)
@patch("app.api.biography.get_style_context", return_value="style")
@patch(
    "app.api.biography.generate_text",
    side_effect=DeepSeekBillingError("У DeepSeek закончился API-кредит. Пополните баланс и повторите запрос."),
)
@patch("app.api.biography.fetch_person_images", return_value=[])
@patch("app.api.biography.get_photos_by_person", return_value=[])
@patch("app.api.biography.set_biography")
def test_generate_deepseek_failure_uses_fallback(
    mock_set,
    mock_photos_repo,
    mock_images,
    mock_gen,
    mock_style,
    mock_wiki,
    mock_cache,
):
    r = client.post("/api/generate?name=Лев Яшин")
    assert r.status_code == 200
    body = r.json()
    assert_generate_contract(body)
    assert body["result"]["used_fallback"] is False
    assert body["text"]
    assert "🕊️ Память" in body["text"]


@patch("app.api.biography.get_biography", return_value=None)
@patch("app.api.biography.fetch_person_from_wikipedia", return_value=None)
@patch("app.api.biography.get_style_context", return_value=None)
def test_generate_missing_name_returns_success(mock_style, mock_wiki, mock_cache):
    r = client.post("/api/generate")
    assert r.status_code == 200
    body = r.json()
    assert_generate_contract(body)
    assert body["name"] == ""
    assert body["result"]["used_fallback"] is True
    assert "missing_full_name" in body["result"]["warnings"]


# ── /cache ─────────────────────────────────────────────────────────────────────

@patch("app.api.biography.list_biographies", return_value=["Яшин", "Харламов"])
def test_cache_list(mock_list):
    r = client.get("/api/cache")
    assert r.status_code == 200
    assert r.json()["names"] == ["Яшин", "Харламов"]


@patch("app.api.biography.list_biographies", side_effect=CacheUnavailableError("Redis down"))
def test_cache_list_returns_503_when_cache_unavailable(mock_list):
    r = client.get("/api/cache")
    assert r.status_code == 503


@patch("app.api.biography.get_biography_strict", return_value={"name": "Яшин", "text": "bio", "photos": []})
def test_get_cached_profile(mock_get):
    r = client.get("/api/cache/Яшин")
    assert r.status_code == 200
    assert r.json()["name"] == "Яшин"


@patch("app.api.biography.get_biography_strict", return_value=None)
def test_get_cached_profile_not_found(mock_get):
    r = client.get("/api/cache/НетТакого")
    assert r.status_code == 404


@patch("app.api.biography.get_biography_strict", side_effect=CacheUnavailableError("Redis down"))
def test_get_cached_profile_returns_503_when_cache_unavailable(mock_get):
    r = client.get("/api/cache/Яшин")
    assert r.status_code == 503


@patch("app.api.biography.delete_biography", return_value=True)
def test_delete_cache(mock_del):
    r = client.delete("/api/cache/Яшин")
    assert r.status_code == 200
    assert r.json()["deleted"] is True


@patch("app.api.biography.delete_biography", side_effect=CacheUnavailableError("Redis down"))
def test_delete_cache_returns_503_when_cache_unavailable(mock_del):
    r = client.delete("/api/cache/Яшин")
    assert r.status_code == 503


@patch("app.api.biography.delete_all_biographies", return_value=5)
def test_delete_all_cache(mock_del):
    r = client.delete("/api/cache")
    assert r.status_code == 200
    assert r.json()["deleted"] == 5


@patch("app.api.biography.delete_all_biographies", side_effect=CacheUnavailableError("Redis down"))
def test_delete_all_cache_returns_503_when_cache_unavailable(mock_del):
    r = client.delete("/api/cache")
    assert r.status_code == 503


# ── /wiki ──────────────────────────────────────────────────────────────────────

@patch("app.api.biography.fetch_person_from_wikipedia", return_value=FAKE_PERSON)
def test_wiki_lookup(mock_wiki):
    r = client.get("/api/wiki/Лев Яшин")
    assert r.status_code == 200
    assert r.json()["name"] == "Лев Яшин"


@patch("app.api.biography.fetch_person_from_wikipedia", return_value=None)
def test_wiki_lookup_not_found(mock_wiki):
    r = client.get("/api/wiki/НетТакого")
    assert r.status_code == 404
