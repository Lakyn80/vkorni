"""Tests for api/biography.py endpoints."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

FAKE_PERSON = {
    "name": "Лев Яшин",
    "summary_text": "Советский футбольный вратарь. " * 30,
    "birth": "22 октября 1929",
    "death": "20 марта 1990",
    "images": [],
}

LONG_TEXT = ("Уникальный биографический текст о великом спортсмене достойном памяти. " * 40
             + "\n\n"
             + "Второй абзац биографии великого человека советской эпохи. " * 40)


# ── /generate ──────────────────────────────────────────────────────────────────

@patch("app.api.biography.get_biography", return_value={"name": "Лев Яшин", "text": "cached", "photos": []})
def test_generate_returns_cache(mock_get):
    r = client.post("/api/generate?name=Лев Яшин")
    assert r.status_code == 200
    assert r.json()["text"] == "cached"
    mock_get.assert_called_once()


@patch("app.api.biography.get_biography", return_value=None)
@patch("app.api.biography.fetch_person_from_wikipedia", return_value=None)
def test_generate_wiki_not_found(mock_wiki, mock_cache):
    r = client.post("/api/generate?name=НесуществующийЧеловек99")
    assert r.status_code == 404


@patch("app.api.biography.get_biography", return_value=None)
@patch("app.api.biography.fetch_person_from_wikipedia", return_value=FAKE_PERSON)
@patch("app.api.biography.get_style_context", return_value="style")
@patch("app.api.biography.generate_text", return_value=(LONG_TEXT, "angle1"))
@patch("app.api.biography.is_unique_enough", return_value=True)
@patch("app.api.biography.fetch_person_images", return_value=[])
@patch("app.api.biography.get_photos_by_person", return_value=[])
@patch("app.api.biography.set_biography")
def test_generate_new_profile(mock_set, mock_photos_repo, mock_images, mock_unique,
                               mock_gen, mock_style, mock_wiki, mock_cache):
    r = client.post("/api/generate?name=Лев Яшин")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Лев Яшин"
    assert body["birth"] == "22 октября 1929"
    assert body["death"] == "20 марта 1990"
    mock_set.assert_called_once()


@patch("app.api.biography.get_biography", return_value=None)
@patch("app.api.biography.fetch_person_from_wikipedia", return_value=FAKE_PERSON)
@patch("app.api.biography.get_style_context", return_value="style")
@patch("app.api.biography.generate_text", return_value=(LONG_TEXT, "angle1"))
@patch("app.api.biography.is_unique_enough", return_value=True)
@patch("app.api.biography.fetch_person_images", return_value=[])
@patch("app.api.biography.get_photos_by_person", return_value=[])
@patch("app.api.biography.set_biography")
def test_generate_normalizes_comma_name(mock_set, mock_photos_repo, mock_images, mock_unique,
                                        mock_gen, mock_style, mock_wiki, mock_cache):
    r = client.post("/api/generate?name=Пушкин,%20Александр%20Сергеевич")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Пушкин Александр Сергеевич"
    mock_wiki.assert_called_once_with("Пушкин Александр Сергеевич")
    mock_images.assert_called_once_with("Пушкин Александр Сергеевич")
    mock_set.assert_called_once()


@patch("app.api.biography.get_biography", return_value=None)
@patch("app.api.biography.fetch_person_from_wikipedia", return_value=FAKE_PERSON)
@patch("app.api.biography.get_style_context", return_value="style")
@patch("app.api.biography.generate_text", return_value=("кратко", "angle1"))
@patch("app.api.biography.fetch_person_images", return_value=[])
@patch("app.api.biography.get_photos_by_person", return_value=[])
@patch("app.api.biography.set_biography")
def test_generate_short_text_returns_500(mock_set, mock_photos, mock_images,
                                          mock_gen, mock_style, mock_wiki, mock_cache):
    r = client.post("/api/generate?name=Лев Яшин")
    assert r.status_code == 500


# ── /cache ─────────────────────────────────────────────────────────────────────

@patch("app.api.biography.list_biographies", return_value=["Яшин", "Харламов"])
def test_cache_list(mock_list):
    r = client.get("/api/cache")
    assert r.status_code == 200
    assert r.json()["names"] == ["Яшин", "Харламов"]


@patch("app.api.biography.get_biography", return_value={"name": "Яшин", "text": "bio", "photos": []})
def test_get_cached_profile(mock_get):
    r = client.get("/api/cache/Яшин")
    assert r.status_code == 200
    assert r.json()["name"] == "Яшин"


@patch("app.api.biography.get_biography", return_value=None)
def test_get_cached_profile_not_found(mock_get):
    r = client.get("/api/cache/НетТакого")
    assert r.status_code == 404


@patch("app.api.biography.delete_cached", return_value=True)
def test_delete_cache(mock_del):
    r = client.delete("/api/cache/Яшин")
    assert r.status_code == 200
    assert r.json()["deleted"] is True


@patch("app.api.biography.delete_all_biographies", return_value=5)
def test_delete_all_cache(mock_del):
    r = client.delete("/api/cache")
    assert r.status_code == 200
    assert r.json()["deleted"] == 5


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
