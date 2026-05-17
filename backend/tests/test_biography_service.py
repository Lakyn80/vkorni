"""Tests for services/biography_service.py."""

from app.services.biography_service import (
    LLM_FAILED_FALLBACK_USED,
    build_biography_response,
    generate_biography_text,
    normalize_biography_input,
)
from app.services.deepseek_service import DeepSeekServiceError


VALID_PERSON = {
    "name": "Лев Яшин",
    "birth": "22 октября 1929",
    "death": "20 марта 1990",
    "activity": "советский футбольный вратарь",
    "achievements": ["олимпийский чемпион", "чемпион Европы"],
    "summary_text": "Советский футбольный вратарь, выступавший за клуб и сборную.",
}


def _llm_success(context: str, style: str | None):
    return (
        "Лев Яшин остается одной из самых заметных фигур советского футбола. "
        "Его путь в спорте связан с игрой на позиции вратаря, крупными турнирами "
        "и устойчивой памятью о его вкладе в историю футбола.",
        "factual_memorial",
    )


def test_normalize_biography_input_accepts_partial_dict():
    normalized = normalize_biography_input({"name": "Лев Яшин", "achievements": []}, requested_name=None)
    assert normalized["full_name"] == "Лев Яшин"
    assert normalized["achievements"] == []
    assert normalized["source_notes"] == ""


def test_generate_biography_with_full_valid_data_uses_llm():
    result = generate_biography_text(
        source_person=VALID_PERSON,
        requested_name="Лев Яшин",
        style="style",
        llm_generate=_llm_success,
        uniqueness_check=lambda candidate, source: True,
    )
    assert result["used_fallback"] is False
    assert result["biography"]
    assert result["warnings"] == []


def test_generate_biography_missing_full_name_adds_warning():
    person = dict(VALID_PERSON)
    person.pop("name")
    result = generate_biography_text(
        source_person=person,
        requested_name=None,
        style=None,
        llm_generate=_llm_success,
    )
    assert "missing_full_name" in result["warnings"]
    assert result["biography"]


def test_generate_biography_missing_birth_date_adds_warning():
    person = dict(VALID_PERSON)
    person.pop("birth")
    result = generate_biography_text(
        source_person=person,
        requested_name="Лев Яшин",
        style=None,
        llm_generate=_llm_success,
    )
    assert "missing_birth_date" in result["warnings"]
    assert result["biography"]


def test_generate_biography_missing_death_date_adds_warning():
    person = dict(VALID_PERSON)
    person.pop("death")
    result = generate_biography_text(
        source_person=person,
        requested_name="Лев Яшин",
        style=None,
        llm_generate=_llm_success,
    )
    assert "missing_death_date" in result["warnings"]
    assert result["biography"]


def test_generate_biography_missing_activity_adds_warning():
    person = dict(VALID_PERSON)
    person.pop("activity")
    result = generate_biography_text(
        source_person=person,
        requested_name="Лев Яшин",
        style=None,
        llm_generate=_llm_success,
    )
    assert "missing_activity" in result["warnings"]
    assert result["biography"]


def test_generate_biography_empty_achievements_adds_warning():
    person = dict(VALID_PERSON)
    person["achievements"] = []
    result = generate_biography_text(
        source_person=person,
        requested_name="Лев Яшин",
        style=None,
        llm_generate=_llm_success,
    )
    assert "missing_achievements" in result["warnings"]
    assert result["biography"]


def test_generate_biography_empty_source_notes_adds_warning():
    person = dict(VALID_PERSON)
    person["summary_text"] = ""
    result = generate_biography_text(
        source_person=person,
        requested_name="Лев Яшин",
        style=None,
        llm_generate=_llm_success,
    )
    assert "missing_source_notes" in result["warnings"]
    assert result["biography"]


def test_generate_biography_empty_input_returns_fallback():
    result = generate_biography_text(
        source_person={},
        requested_name=None,
        style=None,
        llm_generate=_llm_success,
    )
    assert result["used_fallback"] is True
    assert result["biography"]
    assert LLM_FAILED_FALLBACK_USED not in result["warnings"]


def test_generate_biography_malformed_input_returns_fallback():
    result = generate_biography_text(
        source_person={"name": 123, "birth": ["bad"], "achievements": object()},
        requested_name=None,
        style=None,
        llm_generate=_llm_success,
    )
    assert result["used_fallback"] is True
    assert result["biography"]


def test_generate_biography_llm_failure_returns_fallback():
    def _llm_fail(context: str, style: str | None):
        raise DeepSeekServiceError("timeout")

    result = generate_biography_text(
        source_person=VALID_PERSON,
        requested_name="Лев Яшин",
        style=None,
        llm_generate=_llm_fail,
    )
    assert result["used_fallback"] is True
    assert result["biography"]
    assert LLM_FAILED_FALLBACK_USED in result["warnings"]


def test_generate_biography_empty_llm_output_returns_fallback():
    result = generate_biography_text(
        source_person=VALID_PERSON,
        requested_name="Лев Яшин",
        style=None,
        llm_generate=lambda context, style: ("", "factual_memorial"),
    )
    assert result["used_fallback"] is True
    assert result["biography"]
    assert LLM_FAILED_FALLBACK_USED in result["warnings"]


def test_generate_biography_invalid_llm_format_returns_fallback():
    result = generate_biography_text(
        source_person=VALID_PERSON,
        requested_name="Лев Яшин",
        style=None,
        llm_generate=lambda context, style: {"text": "bad"},
    )
    assert result["used_fallback"] is True
    assert result["biography"]
    assert LLM_FAILED_FALLBACK_USED in result["warnings"]


def test_build_biography_response_keeps_contract_and_legacy_fields():
    payload = build_biography_response(
        name="Лев Яшин",
        biography="Текст биографии",
        photos=[],
        birth="1929",
        death="1990",
        photo_sources={},
        used_fallback=False,
        warnings=[],
    )
    assert payload["status"] == "ok"
    assert payload["result"]["biography"] == "Текст биографии"
    assert payload["text"] == "Текст биографии"
