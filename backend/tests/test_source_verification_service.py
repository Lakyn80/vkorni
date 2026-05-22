from app.services.source_verification_service import build_source_excerpt, build_source_units, verify_biography_against_source


def test_build_source_units_skips_reference_sections_and_lines():
    source_text = (
        "Биография\n"
        "Иван Иванов родился в 1900 году в Москве.\n"
        "Работал инженером и преподавателем.\n"
        "Литература\n"
        "Петров П. Иванов. — М.: Наука, 2001. — ISBN 1-2-3-4.\n"
        "Ссылки\n"
        "https://example.com/profile\n"
    )

    units = build_source_units(source_text, display_name="Иван Иванов")

    assert units == [
        "родился в 1900 году в Москве.",
        "Работал инженером и преподавателем.",
    ]


def test_build_source_excerpt_returns_clean_plain_excerpt():
    source_text = (
        "Биография\n"
        "Иван Иванов родился в 1900 году в Москве.\n"
        "Работал инженером и преподавателем.\n"
        "Примечания\n"
        "Петров П. Иванов. — М.: Наука, 2001. — ISBN 1-2-3-4.\n"
    )

    excerpt = build_source_excerpt(source_text, display_name="Иван Иванов")

    assert "ISBN" not in excerpt
    assert "родился в 1900 году в Москве." in excerpt
    assert "Работал инженером и преподавателем." in excerpt


def test_build_source_units_skips_archive_and_exhibition_reference_lines():
    source_text = (
        "Биография\n"
        "Иван Иванов работал архитектором и художником.\n"
        "Персональная выставка художника-архитектора И. Иванова «Свет и камень».\n"
        "ЦГ Архив КФД. АР 215704 Обелиск «Городу-герою».\n"
        "Он преподавал в профильном институте.\n"
    )

    units = build_source_units(source_text, display_name="Иван Иванов")

    assert units == [
        "работал архитектором и художником.",
        "Он преподавал в профильном институте.",
    ]


def test_verify_biography_against_source_rejects_unsupported_sentence():
    biography = (
        "Иван Иванов\n"
        "1900 — 1980\n\n"
        "🕯️ Биография\n\n"
        "Иван Иванов родился в 1900 году в Москве.\n\n"
        "👤 Характер\n\n"
        "Современники вспоминали его как вспыльчивого и одинокого человека."
    )
    source_text = (
        "Иван Иванов родился в 1900 году в Москве. "
        "Работал инженером и преподавателем."
    )

    result = verify_biography_against_source(
        biography,
        source_text=source_text,
        display_name="Иван Иванов",
        extra_grounding_text="1900 1980",
    )

    assert result["is_verified"] is False
    assert result["unsupported_sentences"]
