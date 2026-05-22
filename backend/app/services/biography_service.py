"""
biography_service.py
--------------------
Safe biography generation pipeline helpers.
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any, Callable

from app.services.deepseek_service import DeepSeekServiceError
from app.services.source_verification_service import (
    build_source_excerpt,
    build_source_units as verification_build_source_units,
    verify_biography_against_source,
)

logger = logging.getLogger(__name__)

MISSING_FULL_NAME = "missing_full_name"
MISSING_BIRTH_DATE = "missing_birth_date"
MISSING_DEATH_DATE = "missing_death_date"
MISSING_ACTIVITY = "missing_activity"
MISSING_ACHIEVEMENTS = "missing_achievements"
MISSING_SOURCE_NOTES = "missing_source_notes"
AMBIGUOUS_SOURCE = "ambiguous_source"
SOURCE_VERIFICATION_FAILED = "source_verification_failed"

_WHITESPACE_RE = re.compile(r"\s+")
_MAX_NAME_LENGTH = 120
_MAX_NOTES_LENGTH = 1200
_MAX_SOURCE_TEXT_LENGTH = 24000
_MAX_ACTIVITY_LENGTH = 240
_MAX_ACHIEVEMENTS = 8
_MAX_BIOGRAPHY_LENGTH = 20000
_MAX_BIOGRAPHY_WORDS = 700
_TARGET_SOURCE_BIOGRAPHY_WORDS = 560
_MIN_SOURCE_COVERAGE_RATIO = 0.75


def normalize_requested_name(name: Any) -> str:
    if not isinstance(name, str):
        return ""

    safe = "".join(ch for ch in name if ord(ch) >= 32)
    cleaned = _WHITESPACE_RE.sub(" ", safe.replace(",", " ")).strip()
    if len(cleaned) > _MAX_NAME_LENGTH:
        cleaned = cleaned[:_MAX_NAME_LENGTH].strip()
    return cleaned


def _clean_string(value: Any, *, max_length: int | None = None) -> str:
    if not isinstance(value, str):
        return ""

    text = "".join(ch for ch in value if ord(ch) >= 32)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    if max_length is not None:
        text = text[:max_length].strip()
    return text


def _clean_multiline_text(value: Any, *, max_length: int | None = None) -> str:
    if not isinstance(value, str):
        return ""

    text = value.replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(ch for ch in text if ch == "\n" or ord(ch) >= 32)

    cleaned_lines: list[str] = []
    previous_blank = False
    for raw_line in text.split("\n"):
        line = _WHITESPACE_RE.sub(" ", raw_line).strip()
        if not line:
            if not previous_blank and cleaned_lines:
                cleaned_lines.append("")
            previous_blank = True
            continue
        cleaned_lines.append(line)
        previous_blank = False

    cleaned = "\n".join(cleaned_lines).strip()
    if max_length is not None:
        cleaned = cleaned[:max_length].strip()
    return cleaned


def _clean_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        return []

    cleaned: list[str] = []
    for item in items:
        text = _clean_string(item, max_length=240)
        if text and text not in cleaned:
            cleaned.append(text)
        if len(cleaned) >= _MAX_ACHIEVEMENTS:
            break
    return cleaned


def _first_non_empty(*values: Any, max_length: int | None = None) -> str:
    for value in values:
        text = _clean_string(value, max_length=max_length)
        if text:
            return text
    return ""


def _first_non_empty_multiline(*values: Any, max_length: int | None = None) -> str:
    for value in values:
        text = _clean_multiline_text(value, max_length=max_length)
        if text:
            return text
    return ""


def normalize_biography_input(source_person: Any, requested_name: str | None = None) -> dict[str, Any]:
    raw = source_person if isinstance(source_person, dict) else {}
    fallback_name = normalize_requested_name(requested_name)

    full_name = _first_non_empty(
        raw.get("full_name"),
        raw.get("name"),
        fallback_name,
        max_length=_MAX_NAME_LENGTH,
    )

    normalized = {
        "full_name": full_name,
        "birth_date": _first_non_empty(raw.get("birth_date"), raw.get("birth"), max_length=120),
        "death_date": _first_non_empty(raw.get("death_date"), raw.get("death"), max_length=120),
        "is_ambiguous": bool(raw.get("is_ambiguous")),
        "ambiguity_candidates": raw.get("ambiguity_candidates") if isinstance(raw.get("ambiguity_candidates"), list) else [],
        "activity": _first_non_empty(
            raw.get("activity"),
            raw.get("occupation"),
            raw.get("profession"),
            raw.get("short_description"),
            max_length=_MAX_ACTIVITY_LENGTH,
        ),
        "achievements": _clean_string_list(raw.get("achievements")),
        "source_text": _first_non_empty_multiline(
            raw.get("source_text"),
            raw.get("full_text"),
            raw.get("article_text"),
            max_length=_MAX_SOURCE_TEXT_LENGTH,
        ),
        "source_notes": _first_non_empty(
            raw.get("source_notes"),
            raw.get("summary_text"),
            raw.get("summary"),
            raw.get("notes"),
            raw.get("description"),
            max_length=_MAX_NOTES_LENGTH,
        ),
    }

    if not normalized["source_text"]:
        normalized["source_text"] = _first_non_empty_multiline(
            raw.get("source_notes"),
            raw.get("summary_text"),
            raw.get("summary"),
            raw.get("notes"),
            raw.get("description"),
            max_length=_MAX_SOURCE_TEXT_LENGTH,
        )

    if isinstance(source_person, str):
        if not normalized["source_text"]:
            normalized["source_text"] = _clean_multiline_text(source_person, max_length=_MAX_SOURCE_TEXT_LENGTH)
        if not normalized["source_notes"]:
            normalized["source_notes"] = _clean_string(source_person, max_length=_MAX_NOTES_LENGTH)

    if not normalized["source_notes"] and normalized["source_text"]:
        normalized["source_notes"] = _clean_string(normalized["source_text"], max_length=_MAX_NOTES_LENGTH)

    return normalized


def build_biography_warnings(normalized: dict[str, Any]) -> list[str]:
    warnings: list[str] = []

    if not normalized.get("full_name"):
        warnings.append(MISSING_FULL_NAME)
    if not normalized.get("birth_date"):
        warnings.append(MISSING_BIRTH_DATE)
    if not normalized.get("death_date"):
        warnings.append(MISSING_DEATH_DATE)
    if not normalized.get("activity"):
        warnings.append(MISSING_ACTIVITY)
    if not normalized.get("achievements"):
        warnings.append(MISSING_ACHIEVEMENTS)
    if not normalized.get("source_text") and not normalized.get("source_notes"):
        warnings.append(MISSING_SOURCE_NOTES)
    if normalized.get("is_ambiguous"):
        warnings.append(AMBIGUOUS_SOURCE)

    return warnings


def _has_material_facts(normalized: dict[str, Any]) -> bool:
    return any(
        [
            normalized.get("birth_date"),
            normalized.get("death_date"),
            normalized.get("activity"),
            normalized.get("achievements"),
            normalized.get("source_text"),
            normalized.get("source_notes"),
        ]
    )


def _is_ambiguous_source(normalized: dict[str, Any]) -> bool:
    return bool(normalized.get("is_ambiguous"))


def build_biography_context(normalized: dict[str, Any]) -> str:
    lines: list[str] = []
    display_name = _normalize_display_name(normalized.get("full_name", ""))

    if normalized.get("full_name"):
        lines.append(f"Полное имя: {normalized['full_name']}")
    if normalized.get("birth_date"):
        lines.append(f"Дата рождения: {normalized['birth_date']}")
    if normalized.get("death_date"):
        lines.append(f"Дата смерти: {normalized['death_date']}")
    if normalized.get("activity"):
        lines.append(f"Сфера деятельности: {normalized['activity']}")
    if normalized.get("achievements"):
        lines.append("Подтвержденные достижения:")
        lines.extend(f"- {item}" for item in normalized["achievements"])
    if normalized.get("source_text"):
        source_excerpt = build_source_excerpt(normalized["source_text"], display_name=display_name)
        lines.append("Полный подтвержденный текст источника:")
        lines.append(source_excerpt or normalized["source_text"])
    if normalized.get("source_notes"):
        lines.append(f"Примечания источника: {normalized['source_notes']}")

    if not lines:
        lines.append("Подтвержденных биографических данных не предоставлено.")

    return "\n".join(lines)


def _append_period(text: str) -> str:
    if not text:
        return ""
    if text.endswith((".", "!", "?", "…")):
        return text
    return f"{text}."


def _append_unique_sentence(sentences: list[str], candidate: str) -> None:
    normalized = _append_period(_clean_string(candidate, max_length=_MAX_NOTES_LENGTH))
    if not normalized:
        return
    if _is_redundant_sentence(normalized, sentences):
        return
    sentences.append(normalized)


def _normalize_display_name(name: str) -> str:
    cleaned = _clean_string(name, max_length=_MAX_NAME_LENGTH)
    if not cleaned:
        return ""
    if "," in cleaned:
        parts = [part.strip() for part in cleaned.split(",") if part.strip()]
        if len(parts) == 2:
            return f"{parts[1]} {parts[0]}".strip()
    return cleaned


def _build_life_span_fragment(normalized: dict[str, Any]) -> str:
    birth_date = normalized.get("birth_date")
    death_date = normalized.get("death_date")
    if birth_date and death_date:
        return f"{birth_date} — {death_date}"
    if birth_date:
        return f"родился {birth_date}"
    if death_date:
        return f"скончался {death_date}"
    return ""


def _strip_leading_name_clause(text: str, display_name: str) -> str:
    cleaned = _clean_string(text, max_length=_MAX_NOTES_LENGTH)
    if not cleaned:
        return ""
    if display_name:
        lowered = cleaned.lower()
        display_lower = display_name.lower()
        if lowered.startswith(display_lower):
            tail = cleaned[len(display_name):].lstrip(" —-,:")
            if tail:
                return tail
        parts = display_name.split()
        if parts:
            last_name = parts[-1].lower()
            if lowered.startswith(last_name):
                tail = cleaned[len(parts[-1]):].lstrip(" —-,:")
                if tail:
                    return tail
    return cleaned


def _split_sentences(text: str) -> list[str]:
    cleaned = _clean_string(text, max_length=_MAX_NOTES_LENGTH)
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?…])\s+", cleaned)
    return [_append_period(part.strip()) for part in parts if part.strip()]


def _count_words(text: str) -> int:
    return len(re.findall(r"[а-яёa-z0-9]+(?:-[а-яёa-z0-9]+)?", text.lower()))


def _truncate_sentence_to_word_limit(text: str, max_words: int) -> str:
    if max_words <= 0:
        return ""

    words: list[str] = []
    result_chars: list[str] = []
    for part in re.finditer(r"\S+|\s+", text):
        chunk = part.group(0)
        if chunk.isspace():
            if result_chars and not result_chars[-1].isspace():
                result_chars.append(" ")
            continue

        token_words = _count_words(chunk)
        if token_words > 0 and len(words) + token_words > max_words:
            break

        result_chars.append(chunk)
        if token_words > 0:
            words.extend(re.findall(r"[а-яёa-z0-9]+(?:-[а-яёa-z0-9]+)?", chunk.lower()))

    truncated = "".join(result_chars).strip(" ,;:-")
    return _append_period(truncated) if truncated else ""


def _truncate_biography_to_word_limit(text: str, max_words: int = _MAX_BIOGRAPHY_WORDS) -> str:
    cleaned = _clean_multiline_text(text, max_length=_MAX_BIOGRAPHY_LENGTH)
    if not cleaned or _count_words(cleaned) <= max_words:
        return cleaned

    lines = cleaned.split("\n")
    kept_lines: list[str] = []
    used_words = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if kept_lines and kept_lines[-1] != "":
                kept_lines.append("")
            continue

        line_words = _count_words(stripped)
        if line_words == 0:
            kept_lines.append(stripped)
            continue

        remaining_words = max_words - used_words
        if remaining_words <= 0:
            break

        if line_words <= remaining_words:
            kept_lines.append(stripped)
            used_words += line_words
            continue

        truncated_line = _truncate_sentence_to_word_limit(stripped, remaining_words)
        if truncated_line:
            kept_lines.append(truncated_line)
            used_words += _count_words(truncated_line)
        break

    while kept_lines and kept_lines[-1] == "":
        kept_lines.pop()

    return _clean_multiline_text("\n".join(kept_lines), max_length=_MAX_BIOGRAPHY_LENGTH)


def _is_heading_like_line(line: str) -> bool:
    if not line:
        return True
    if re.search(r"[.!?…]", line):
        return False
    return _count_words(line) <= 6


def _build_source_units(source_text: str, display_name: str) -> list[str]:
    units = verification_build_source_units(source_text, display_name=display_name)
    return [_append_period(_clean_string(unit, max_length=_MAX_SOURCE_TEXT_LENGTH)) for unit in units if unit]


def _select_source_units_for_coverage(
    units: list[str],
    min_ratio: float = _MIN_SOURCE_COVERAGE_RATIO,
    max_words: int = _TARGET_SOURCE_BIOGRAPHY_WORDS,
) -> list[str]:
    if not units:
        return []

    total_words = sum(_count_words(unit) for unit in units)
    if total_words <= 0:
        return units

    target_words = total_words if total_words <= 120 else math.ceil(total_words * min_ratio)
    target_words = min(target_words, max_words)
    selected: list[str] = []
    selected_words = 0
    cumulative_words = 0

    for index, unit in enumerate(units):
        unit_words = max(1, _count_words(unit))
        if selected and selected_words + unit_words > max_words:
            continue
        cumulative_words += unit_words
        desired_words = math.ceil(cumulative_words * (target_words / total_words))
        remaining_words = sum(_count_words(item) for item in units[index + 1 :])
        must_keep = selected_words + remaining_words < target_words

        if index == 0 or index == len(units) - 1 or selected_words < desired_words or must_keep:
            selected.append(unit)
            selected_words += unit_words

    if selected_words < target_words:
        for unit in reversed(units):
            if unit in selected:
                continue
            selected.insert(0, unit)
            selected_words += max(1, _count_words(unit))
            if selected_words >= target_words:
                break

    return selected


def _group_source_units_into_sections(units: list[str]) -> list[tuple[str, str]]:
    if not units:
        return []

    titles = [
        "🌌 Сквозь биографию",
        "🌳 Ранние годы",
        "🏛 Путь и дело",
        "🎨 Главное дело",
        "👤 Документальный облик",
        "📜 Наследие",
    ]
    section_count = min(len(titles), max(1, len(units)))
    chunk_size = math.ceil(len(units) / section_count)
    sections: list[tuple[str, str]] = []

    for index in range(section_count):
        chunk = units[index * chunk_size : (index + 1) * chunk_size]
        if not chunk:
            continue
        sections.append((titles[index], " ".join(chunk).strip()))

    return sections


def _build_source_header_lines(display_name: str, normalized: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    birth = normalized.get("birth_date")
    death = normalized.get("death_date")

    if birth and death:
        lines.append(f"{birth} — {death}")
    elif birth:
        lines.append(birth)
    elif death:
        lines.append(death)

    if display_name:
        lines.append(display_name)

    birth_year = re.search(r"\b(\d{4})\b", birth or "")
    death_year = re.search(r"\b(\d{4})\b", death or "")
    if birth_year and death_year:
        lines.append(f"{birth_year.group(1)} — {death_year.group(1)}")
    elif birth_year:
        lines.append(birth_year.group(1))
    elif death_year:
        lines.append(death_year.group(1))

    return lines


def _build_source_closing_lines(display_name: str, normalized: dict[str, Any]) -> list[str]:
    activity = normalized.get("activity") or "дело жизни"
    return [
        f"🌹 Память о {display_name} сохраняется там, где остаются подтвержденные документы, работы и свидетельства его пути.",
        f"🕊️ Этот биографический рассказ держится на реальных источниках и уважении к {activity}.",
    ]


def _compose_biography_from_source_text(display_name: str, normalized: dict[str, Any]) -> str:
    source_text = normalized.get("source_text") or ""
    units = _build_source_units(source_text, display_name)
    if not units:
        return ""

    selected_units = _select_source_units_for_coverage(units)
    sections = _group_source_units_into_sections(selected_units)
    if not sections:
        return ""

    lines = _build_source_header_lines(display_name, normalized)

    section_lines: list[str] = []
    for title, paragraph in sections:
        section_lines.append(title)
        section_lines.append(paragraph)

    section_lines.extend(["", *_build_source_closing_lines(display_name, normalized)])

    return _truncate_biography_to_word_limit(
        _clean_multiline_text("\n".join(lines) + "\n\n" + "\n\n".join(section_lines), max_length=_MAX_BIOGRAPHY_LENGTH)
    )


def _has_substantial_source_text(normalized: dict[str, Any]) -> bool:
    source_text = normalized.get("source_text") or ""
    if _count_words(source_text) >= 120:
        return True
    display_name = _normalize_display_name(normalized.get("full_name", ""))
    return len(_build_source_units(source_text, display_name)) >= 4


def _is_redundant_sentence(candidate: str, existing_sentences: list[str]) -> bool:
    candidate_tokens = set(re.findall(r"[а-яёa-z0-9]+", candidate.lower()))
    if not candidate_tokens:
        return True
    for sentence in existing_sentences:
        sentence_tokens = set(re.findall(r"[а-яёa-z0-9]+", sentence.lower()))
        if candidate_tokens <= sentence_tokens:
            return True
    return False


def _tokenize_meaningful(text: str) -> set[str]:
    return {token for token in re.findall(r"[а-яёa-z0-9]+", text.lower()) if len(token) > 2}


def _build_grounding_text(normalized: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("full_name", "birth_date", "death_date", "activity", "source_text", "source_notes"):
        value = normalized.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value)
    achievements = normalized.get("achievements") or []
    if achievements:
        parts.extend(achievements)
    return " ".join(parts)


def _is_generated_grounded(candidate: str, normalized: dict[str, Any]) -> bool:
    source_tokens = _tokenize_meaningful(_build_grounding_text(normalized))
    if not source_tokens:
        return False

    content_blocks = []
    for block in _clean_multiline_text(candidate, max_length=_MAX_BIOGRAPHY_LENGTH).split("\n"):
        line = block.strip()
        if not line or line.startswith(("🕯️", "📚", "🏅", "🕊️")):
            continue
        content_blocks.append(line)

    for block in content_blocks:
        tokens = _tokenize_meaningful(block)
        if not tokens:
            continue
        overlap = len(tokens & source_tokens)
        if overlap == 0:
            return False
        novel_ratio = 1 - (overlap / len(tokens))
        if novel_ratio > 0.45:
            return False

    return True


def _should_prefer_fact_composition(normalized: dict[str, Any]) -> bool:
    if normalized.get("source_text"):
        return False
    if normalized.get("activity") or normalized.get("achievements"):
        return False
    return bool(normalized.get("source_notes"))


def _build_intro_paragraph(display_name: str, normalized: dict[str, Any], source_sentences: list[str]) -> str:
    activity = normalized.get("activity") or ""
    sentences: list[str] = []

    if source_sentences:
        _append_unique_sentence(sentences, source_sentences[0])
    elif activity:
        _append_unique_sentence(sentences, f"{display_name} — {activity}")
    elif normalized.get("birth_date") and normalized.get("death_date"):
        _append_unique_sentence(sentences, f"{display_name} жил с {normalized['birth_date']} по {normalized['death_date']}")
    elif normalized.get("birth_date"):
        _append_unique_sentence(sentences, f"{display_name} родился {normalized['birth_date']}")
    elif normalized.get("death_date"):
        _append_unique_sentence(sentences, f"{display_name} скончался {normalized['death_date']}")
    else:
        _append_unique_sentence(sentences, f"{display_name} сохранился в памяти по доступным подтвержденным сведениям")

    if normalized.get("birth_date") and normalized.get("death_date"):
        _append_unique_sentence(sentences, f"Даты жизни: {normalized['birth_date']} — {normalized['death_date']}")
    elif normalized.get("birth_date"):
        _append_unique_sentence(sentences, f"Подтвержденная дата рождения: {normalized['birth_date']}")
    elif normalized.get("death_date"):
        _append_unique_sentence(sentences, f"Подтвержденная дата смерти: {normalized['death_date']}")

    if activity:
        _append_unique_sentence(sentences, f"Подтвержденная сфера деятельности: {activity}")

    return " ".join(sentences).strip()


def _build_details_paragraph(display_name: str, normalized: dict[str, Any], source_sentences: list[str]) -> str:
    details: list[str] = []

    for sentence in source_sentences[1:]:
        _append_unique_sentence(details, sentence)

    achievements = normalized.get("achievements") or []
    if achievements:
        _append_unique_sentence(
            details,
            "Среди подтвержденных сведений упоминаются: " + "; ".join(achievements),
        )

    if not details and normalized.get("source_notes"):
        anchors: list[str] = []
        if normalized.get("birth_date") or normalized.get("death_date"):
            anchors.append("датами жизни")
        if normalized.get("activity"):
            anchors.append("сферой деятельности")
        anchors.append("кратким документальным описанием")
        _append_unique_sentence(
            details,
            "Доступные сведения очерчивают биографический контур "
            + ", ".join(anchors),
        )

    return " ".join(details).strip()


def _build_memory_paragraph(display_name: str, normalized: dict[str, Any]) -> str:
    sentences = [
        f"{display_name} остаётся в памяти благодаря сохранённым биографическим сведениям и уважительному мемориальному тону повествования."
    ]

    remembered_parts: list[str] = []
    if normalized.get("birth_date") and normalized.get("death_date"):
        remembered_parts.append(f"датах жизни {normalized['birth_date']} — {normalized['death_date']}")
    elif normalized.get("birth_date"):
        remembered_parts.append(f"дате рождения {normalized['birth_date']}")
    elif normalized.get("death_date"):
        remembered_parts.append(f"дате смерти {normalized['death_date']}")

    if normalized.get("activity"):
        remembered_parts.append(f"сфере деятельности: {normalized['activity']}")

    achievements = normalized.get("achievements") or []
    if achievements:
        remembered_parts.append("отмеченных достижениях")

    if remembered_parts:
        _append_unique_sentence(
            sentences,
            "В подтвержденных данных сохранена память о "
            + ", ".join(remembered_parts)
            + ".",
        )
    else:
        _append_unique_sentence(
            sentences,
            "Даже краткие подтвержденные данные позволяют сохранить спокойное и документальное воспоминание.",
        )

    return " ".join(sentences)


def _build_ambiguous_biography(normalized: dict[str, Any]) -> str:
    display_name = _normalize_display_name(normalized.get("full_name", "")) or "Этот человек"
    lines = [display_name]

    safe_lines = [
        "🕯️ Биография",
        "Найденные источники недостаточны для однозначного определения личности. Ниже приведены только безопасно подтвержденные сведения.",
        "",
        "📚 Путь и дело",
    ]

    details: list[str] = []
    if normalized.get("birth_date") and normalized.get("death_date"):
        details.append(f"Подтверждены даты жизни: {normalized['birth_date']} — {normalized['death_date']}.")
    elif normalized.get("birth_date"):
        details.append(f"Подтверждена дата рождения: {normalized['birth_date']}.")
    elif normalized.get("death_date"):
        details.append(f"Подтверждена дата смерти: {normalized['death_date']}.")

    if normalized.get("activity"):
        details.append(f"Подтверждена только общая сфера деятельности: {normalized['activity']}.")
    if normalized.get("achievements"):
        details.append("Доступны отдельные подтвержденные упоминания о достижениях без безопасной полной атрибуции.")

    candidates = normalized.get("ambiguity_candidates") or []
    if not details:
        details.append("В открытых источниках это имя относится к нескольким разным людям, поэтому неподтвержденные детали исключены.")

    safe_lines.append(" ".join(details))
    if candidates:
        safe_lines.extend(["", "В источнике найдены такие варианты:"])
        for candidate in candidates[:5]:
            title = _clean_string(candidate.get("title", ""), max_length=180)
            description = _clean_string(candidate.get("description", ""), max_length=240)
            if title and description:
                safe_lines.append(f"{title} — {description}.")
            elif title:
                safe_lines.append(title)
    safe_lines.extend(
        [
            "",
            "🕊️ Память",
            "Для точного биографического текста нужен более конкретный источник или уточнение личности в запросе, например с указанием профессии или годов жизни.",
        ]
    )

    return _clean_multiline_text("\n".join(lines) + "\n\n" + "\n".join(safe_lines), max_length=_MAX_BIOGRAPHY_LENGTH)


def compose_biography_from_facts(normalized: dict[str, Any]) -> str:
    if _is_ambiguous_source(normalized):
        return _build_ambiguous_biography(normalized)

    display_name = _normalize_display_name(normalized.get("full_name", ""))
    if not display_name:
        display_name = "Этот человек"

    source_text_biography = ""
    if _has_substantial_source_text(normalized):
        source_text_biography = _compose_biography_from_source_text(display_name, normalized)
    if source_text_biography:
        return source_text_biography

    source_notes = _strip_leading_name_clause(normalized.get("source_notes", ""), display_name)
    source_sentences = _split_sentences(source_notes)
    lines = [display_name]

    if normalized.get("birth_date") and normalized.get("death_date"):
        lines.append(f"{normalized['birth_date']} — {normalized['death_date']}")
    elif normalized.get("birth_date"):
        lines.append(f"Родился: {normalized['birth_date']}")
    elif normalized.get("death_date"):
        lines.append(f"Скончался: {normalized['death_date']}")

    sections: list[tuple[str, str]] = []
    intro_paragraph = _build_intro_paragraph(display_name, normalized, source_sentences)
    if intro_paragraph:
        sections.append(("🕯️ Биография", intro_paragraph))

    details_paragraph = _build_details_paragraph(display_name, normalized, source_sentences)
    if details_paragraph and not _is_redundant_sentence(details_paragraph, [intro_paragraph]):
        sections.append(("📚 Путь и дело", details_paragraph))

    sections.append(("🕊️ Память", _build_memory_paragraph(display_name, normalized)))

    section_lines: list[str] = []
    for title, paragraph in sections:
        section_lines.append(title)
        section_lines.append(paragraph)

    return _clean_multiline_text("\n".join(lines) + "\n\n" + "\n\n".join(section_lines), max_length=_MAX_BIOGRAPHY_LENGTH)


def build_fallback_biography(normalized: dict[str, Any]) -> str:
    if _has_material_facts(normalized):
        return compose_biography_from_facts(normalized)

    if normalized.get("full_name"):
        name = _normalize_display_name(normalized["full_name"])
        return _clean_multiline_text(
            f"{name}\n\n🕯️ Биография\nКраткая биографическая заметка будет дополнена по мере появления подтвержденных сведений.\n\n🕊️ Память\nПамять об этом человеке сохраняется в уважительном и спокойном мемориальном формате.",
            max_length=_MAX_BIOGRAPHY_LENGTH,
        )
    return _clean_multiline_text(
        "🕯️ Биография\nКраткая биографическая заметка будет дополнена по мере появления подтвержденных сведений.\n\n🕊️ Память\nПамять об этом человеке сохраняется в уважительном и спокойном мемориальном формате.",
        max_length=_MAX_BIOGRAPHY_LENGTH,
    )


def _sanitize_generated_biography(text: Any) -> str:
    cleaned = _clean_multiline_text(text, max_length=_MAX_BIOGRAPHY_LENGTH)
    cleaned = _truncate_biography_to_word_limit(cleaned)
    return cleaned


def _is_valid_generated_biography(text: str) -> bool:
    if not text:
        return False
    if len(text.split()) < 8:
        return False
    return True


def _safe_llm_generate(
    normalized: dict[str, Any],
    style: str | None,
    llm_generate: Callable[..., Any],
    uniqueness_check: Callable[[str, str], bool] | None = None,
) -> tuple[str, list[str], bool]:
    if not _has_material_facts(normalized):
        return "", [], True

    if _is_ambiguous_source(normalized):
        return compose_biography_from_facts(normalized), [AMBIGUOUS_SOURCE], True

    if _should_prefer_fact_composition(normalized):
        return compose_biography_from_facts(normalized), [], True

    context = build_biography_context(normalized)

    try:
        generated = llm_generate(context, style)
    except DeepSeekServiceError:
        raise
    except Exception as exc:
        logger.warning("Biography LLM call failed: %s", exc)
        raise DeepSeekServiceError("Biography LLM call failed") from exc

    if not isinstance(generated, tuple) or not generated:
        raise DeepSeekServiceError("Biography LLM returned invalid payload")

    candidate = _sanitize_generated_biography(generated[0] if len(generated) > 0 else "")
    if not _is_valid_generated_biography(candidate):
        raise DeepSeekServiceError("Biography LLM returned empty or too short text")

    source_notes = normalized.get("source_notes") or ""
    if uniqueness_check and source_notes:
        try:
            if not uniqueness_check(candidate, source_notes):
                return compose_biography_from_facts(normalized), [], True
        except DeepSeekServiceError:
            raise
        except Exception as exc:
            logger.warning("Biography uniqueness check failed: %s", exc)

    display_name = _normalize_display_name(normalized.get("full_name", ""))
    verification = verify_biography_against_source(
        candidate,
        source_text=normalized.get("source_text") or normalized.get("source_notes") or "",
        display_name=display_name,
        extra_grounding_text=_build_grounding_text(normalized),
    )
    if not verification["is_verified"]:
        logger.warning(
            "Biography source verification failed; unsupported_sentences=%s",
            verification["unsupported_sentences"][:3],
        )
        return compose_biography_from_facts(normalized), [SOURCE_VERIFICATION_FAILED], True

    if not normalized.get("source_text") and not _is_generated_grounded(candidate, normalized):
        return compose_biography_from_facts(normalized), [SOURCE_VERIFICATION_FAILED], True

    return candidate, [], False


def generate_biography_text(
    source_person: Any,
    requested_name: str | None,
    style: str | None,
    llm_generate: Callable[..., Any],
    uniqueness_check: Callable[[str, str], bool] | None = None,
) -> dict[str, Any]:
    normalized = normalize_biography_input(source_person, requested_name=requested_name)
    warnings = build_biography_warnings(normalized)

    if not _has_material_facts(normalized):
        return {
            "name": normalized.get("full_name") or "",
            "birth": normalized.get("birth_date") or None,
            "death": normalized.get("death_date") or None,
            "biography": build_fallback_biography(normalized),
            "used_fallback": True,
            "warnings": list(dict.fromkeys(warnings)),
        }

    used_fallback = False
    biography = ""

    try:
        biography, extra_warnings, used_fallback = _safe_llm_generate(
            normalized,
            style,
            llm_generate,
            uniqueness_check=uniqueness_check,
        )
        warnings.extend(extra_warnings)
    except DeepSeekServiceError as exc:
        logger.warning("Biography generation switched to deterministic fact composition: %s", exc)
        biography = compose_biography_from_facts(normalized)
        used_fallback = True
    except Exception as exc:  # pragma: no cover - final safety net
        logger.exception("Unexpected biography generation failure: %s", exc)
        biography = compose_biography_from_facts(normalized)
        used_fallback = True

    biography = _sanitize_generated_biography(biography)
    if not biography:
        used_fallback = True
        biography = build_fallback_biography(normalized)

    # Preserve warning order but remove duplicates deterministically.
    warnings = list(dict.fromkeys(warnings))

    return {
        "name": normalized.get("full_name") or "",
        "birth": normalized.get("birth_date") or None,
        "death": normalized.get("death_date") or None,
        "biography": biography,
        "used_fallback": used_fallback,
        "warnings": warnings,
    }


def build_biography_response(
    *,
    name: str,
    biography: str,
    photos: list[str],
    birth: str | None,
    death: str | None,
    photo_sources: dict[str, str],
    used_fallback: bool,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    warning_list = list(dict.fromkeys(warnings or []))
    return {
        "status": "ok",
        "result": {
            "biography": biography,
            "used_fallback": used_fallback,
            "warnings": warning_list,
        },
        "name": name,
        "text": biography,
        "photos": photos,
        "birth": birth,
        "death": death,
        "photo_sources": photo_sources,
    }


def build_biography_response_from_cache(cached: Any) -> dict[str, Any]:
    payload = cached if isinstance(cached, dict) else {}
    biography = _sanitize_generated_biography(payload.get("text", ""))
    warnings: list[str] = []

    if isinstance(payload.get("result"), dict):
        result = payload["result"]
        biography = _sanitize_generated_biography(result.get("biography", biography))
        warnings = result.get("warnings") if isinstance(result.get("warnings"), list) else []
        used_fallback = bool(result.get("used_fallback", False))
    else:
        used_fallback = False

    if not biography:
        normalized = normalize_biography_input(payload, requested_name=payload.get("name"))
        biography = build_fallback_biography(normalized)
        used_fallback = True

    return build_biography_response(
        name=_clean_string(payload.get("name"), max_length=_MAX_NAME_LENGTH),
        biography=biography,
        photos=payload.get("photos") if isinstance(payload.get("photos"), list) else [],
        birth=_clean_string(payload.get("birth"), max_length=120) or None,
        death=_clean_string(payload.get("death"), max_length=120) or None,
        photo_sources=payload.get("photo_sources") if isinstance(payload.get("photo_sources"), dict) else {},
        used_fallback=used_fallback,
        warnings=warnings,
    )
