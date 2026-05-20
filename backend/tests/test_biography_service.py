"""Tests for services/biography_service.py."""

import re

from app.services.biography_service import (
    build_biography_response,
    compose_biography_from_facts,
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


def test_generate_biography_with_full_source_text_skips_llm_and_keeps_source_coverage():
    person = {
        "name": "Тестовый Человек",
        "birth": "1900",
        "death": "1980",
        "source_text": (
            "Тестовый Человек родился в семье служащих и получил базовое образование в родном городе. "
            "В ранние годы он проявил интерес к технике и общественной деятельности. "
            "Позднее он работал в нескольких учреждениях и участвовал в профильных проектах. "
            "В разные периоды его биографии упоминаются поездки, публикации и организационная работа. "
            "Современники отмечали его последовательное участие в профессиональной среде. "
            "Отдельные этапы жизни связаны с преподаванием, архивной работой и подготовкой материалов. "
            "Сохранившиеся сведения описывают его деятельность в хронологическом и документальном порядке. "
            "После смерти упоминания о нём продолжают встречаться в биографических и справочных публикациях."
        ),
    }

    result = generate_biography_text(
        source_person=person,
        requested_name="Тестовый Человек",
        style="style",
        llm_generate=lambda context, style: (_ for _ in ()).throw(AssertionError("LLM should not be used")),
    )

    content = result["biography"]
    for marker in ("Тестовый Человек", "1900 — 1980", "🕯️ Биография", "📚 Путь и дело", "🕊️ Память"):
        content = content.replace(marker, "")

    source_words = len(re.findall(r"[а-яёa-z0-9]+(?:-[а-яёa-z0-9]+)?", person["source_text"].lower()))
    content_words = len(re.findall(r"[а-яёa-z0-9]+(?:-[а-яёa-z0-9]+)?", content.lower()))

    assert result["used_fallback"] is False
    assert "🕯️ Биография" in result["biography"]
    assert "📚 Путь и дело" in result["biography"]
    assert "🕊️ Память" in result["biography"]
    assert content_words >= int(source_words * 0.75)


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
    assert result["warnings"]


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
    assert result["used_fallback"] is False
    assert result["biography"]
    assert "🕯️ Биография" in result["biography"]
    assert "📚 Путь и дело" in result["biography"]


def test_generate_biography_empty_llm_output_returns_fallback():
    result = generate_biography_text(
        source_person=VALID_PERSON,
        requested_name="Лев Яшин",
        style=None,
        llm_generate=lambda context, style: ("", "factual_memorial"),
    )
    assert result["used_fallback"] is False
    assert result["biography"]
    assert "Лев Яшин" in result["biography"]
    assert "🕊️ Память" in result["biography"]


def test_generate_biography_invalid_llm_format_returns_fallback():
    result = generate_biography_text(
        source_person=VALID_PERSON,
        requested_name="Лев Яшин",
        style=None,
        llm_generate=lambda context, style: {"text": "bad"},
    )
    assert result["used_fallback"] is False
    assert result["biography"]
    assert "Лев Яшин" in result["biography"]


def test_compose_biography_from_facts_reorders_comma_name_naturally():
    normalized = normalize_biography_input(
        {
            "name": "Менделеев, Дмитрий Иванович",
            "birth": "27 января 1834",
            "death": "20 января 1907",
            "summary_text": "Дмитрий Иванович Менделеев — русский учёный-энциклопедист.",
        }
    )
    biography = compose_biography_from_facts(normalized)
    assert biography.startswith("Дмитрий Иванович Менделеев")
    assert "🕯️ Биография" in biography
    assert "🕊️ Память" in biography


def test_compose_biography_from_facts_keeps_sparse_summary_substantial():
    normalized = normalize_biography_input(
        {
            "name": "Юрий Гагарин",
            "birth": "9 марта 1934",
            "death": "27 марта 1968",
            "summary_text": "Советский космонавт и военный лётчик, первый человек, совершивший космический полёт.",
        }
    )
    biography = compose_biography_from_facts(normalized)
    assert "📚 Путь и дело" in biography
    assert biography.count(".") >= 4
    assert "9 марта 1934 — 27 марта 1968" in biography


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
