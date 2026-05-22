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
        "Лев Яшин\n"
        "22 октября 1929 — 20 марта 1990\n\n"
        "🕯️ Биография\n\n"
        "Лев Яшин — советский футбольный вратарь, выступавший за клуб и сборную.\n\n"
        "📚 Путь и дело\n\n"
        "Среди подтвержденных достижений упоминаются олимпийский чемпион и чемпион Европы.",
        "chronology_focus",
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

    candidate = (
        "Тестовый Человек\n"
        "1900 — 1980\n\n"
        "🕯️ Биография\n\n"
        "Тестовый Человек родился в семье служащих и получил базовое образование в родном городе. "
        "В ранние годы он проявил интерес к технике и общественной деятельности.\n\n"
        "📚 Путь и дело\n\n"
        "Позднее он работал в нескольких учреждениях и участвовал в профильных проектах. "
        "В разные периоды его биографии упоминаются поездки, публикации и организационная работа.\n\n"
        "🕊️ Память\n\n"
        "Сохранившиеся сведения описывают его деятельность в хронологическом и документальном порядке. "
        "После смерти упоминания о нём продолжают встречаться в биографических и справочных публикациях."
    )

    result = generate_biography_text(
        source_person=person,
        requested_name="Тестовый Человек",
        style="style",
        llm_generate=lambda context, style: (candidate, "chronology_focus"),
        uniqueness_check=lambda candidate, source: True,
    )

    assert result["used_fallback"] is False
    assert result["biography"] == candidate
    assert result["warnings"] == ["missing_activity", "missing_achievements"]


def test_generate_biography_rejects_hallucinated_llm_output_against_source():
    person = {
        "name": "Тестовый Человек",
        "birth": "1900",
        "death": "1980",
        "source_text": (
            "Тестовый Человек родился в семье служащих и получил базовое образование в родном городе. "
            "Позднее он работал в нескольких учреждениях и участвовал в профильных проектах. "
            "После смерти упоминания о нём продолжают встречаться в биографических и справочных публикациях."
        ),
    }

    candidate = (
        "Тестовый Человек\n"
        "1900 — 1980\n\n"
        "🕯️ Биография\n\n"
        "Тестовый Человек родился в семье служащих и получил базовое образование в родном городе.\n\n"
        "👤 Характер\n\n"
        "Его друзья вспоминали его как замкнутого человека, который не доверял коллегам."
    )

    result = generate_biography_text(
        source_person=person,
        requested_name="Тестовый Человек",
        style="style",
        llm_generate=lambda context, style: (candidate, "human_flaw"),
        uniqueness_check=lambda candidate, source: True,
    )

    assert result["used_fallback"] is True
    assert result["biography"] != candidate
    assert "source_verification_failed" in result["warnings"]
    assert "🕯️ Биография" in result["biography"]


def test_generate_biography_for_ambiguous_person_returns_safe_notice():
    person = {
        "name": "Владимир Сергеевич Лукьянов",
        "is_ambiguous": True,
        "ambiguity_candidates": [
            {"title": "Лукьянов, Владимир Сергеевич (1902—1980)", "description": "советский учёный"},
            {"title": "Лукьянов, Владимир Сергеевич (архитектор)", "description": "советский, российский архитектор, художник"},
        ],
        "summary_text": (
            "Лукьянов, Владимир Сергеевич (1902—1980) — советский учёный. "
            "Лукьянов, Владимир Сергеевич — советский, российский архитектор, художник. "
            "Лукьянов, Владимир Сергеевич (1952—2009) — советский лыжник, тренер."
        ),
    }

    result = generate_biography_text(
        source_person=person,
        requested_name="Владимир Сергеевич Лукьянов",
        style="style",
        llm_generate=lambda context, style: ("опасный текст", "style"),
        uniqueness_check=lambda candidate, source: True,
    )

    assert result["used_fallback"] is True
    assert "ambiguous_source" in result["warnings"]
    assert "недостаточны для однозначного определения личности" in result["biography"]
    assert "Лукьянов, Владимир Сергеевич (архитектор)" in result["biography"]
    assert "гидравлического интегратора" not in result["biography"]


def test_compose_biography_from_facts_with_substantial_source_text_uses_memorial_sections():
    normalized = normalize_biography_input(
        {
            "name": "Тестовый Человек",
            "birth": "18 августа 1945",
            "source_text": (
                "Тестовый Человек родился в послевоенные годы и получил художественное образование. "
                "В ранние годы он жил в Ленинграде и постепенно вошёл в профессиональную среду. "
                "Позднее он работал архитектором и участвовал в проектировании городских объектов. "
                "Его деятельность соединяла проектную практику, графику и преподавание. "
                "Сохранившиеся сведения описывают выставки, рабочие проекты и документальные упоминания. "
                "Память о нём удерживается в биографических материалах и архивных источниках."
            ),
        },
        requested_name="Тестовый Человек",
    )

    biography = compose_biography_from_facts(normalized)

    assert "🌌 Сквозь биографию" in biography
    assert "🏛 Путь и дело" in biography
    assert "📜 Наследие" in biography
    assert "🌹" in biography
    assert "\n\n" in biography


def test_compose_biography_from_facts_caps_long_source_text_to_700_words():
    source_sentence = "Тестовый Человек последовательно работал с документальными материалами и участвовал в подтвержденных проектах."
    normalized = normalize_biography_input(
        {
            "name": "Тестовый Человек",
            "birth": "1900",
            "death": "1980",
            "source_text": " ".join([source_sentence] * 140),
        },
        requested_name="Тестовый Человек",
    )

    biography = compose_biography_from_facts(normalized)
    word_count = len(re.findall(r"[а-яёa-z0-9]+(?:-[а-яёa-z0-9]+)?", biography.lower()))

    assert word_count <= 700
    assert "🌌 Сквозь биографию" in biography


def test_generate_biography_truncates_llm_output_to_700_words():
    candidate_body = " ".join(["Подтвержденное предложение о биографии и деятельности."] * 220)
    candidate = (
        "Тестовый Человек\n"
        "1900 — 1980\n\n"
        "🕯️ Биография\n\n"
        f"{candidate_body}"
    )
    person = {
        "name": "Тестовый Человек",
        "birth": "1900",
        "death": "1980",
        "source_text": candidate_body,
    }

    result = generate_biography_text(
        source_person=person,
        requested_name="Тестовый Человек",
        style="style",
        llm_generate=lambda context, style: (candidate, "source_bound_profile"),
        uniqueness_check=lambda candidate, source: True,
    )

    word_count = len(re.findall(r"[а-яёa-z0-9]+(?:-[а-яёa-z0-9]+)?", result["biography"].lower()))

    assert result["used_fallback"] is False
    assert word_count <= 700


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
    assert result["used_fallback"] is True
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
    assert result["used_fallback"] is True
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
    assert result["used_fallback"] is True
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
