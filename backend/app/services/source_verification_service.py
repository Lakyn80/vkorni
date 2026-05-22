"""
source_verification_service.py
------------------------------
Post-generation guard for checking biography sentences against source text.
"""

from __future__ import annotations

import re
from typing import Any

_STOPWORDS = {
    "в", "на", "и", "с", "по", "из", "к", "за", "от", "до", "не", "что",
    "он", "она", "они", "его", "её", "их", "это", "был", "была", "были",
    "есть", "быть", "как", "так", "но", "а", "же", "ли", "бы", "то", "или",
    "о", "об", "для", "при", "со", "во", "под", "над", "между", "через",
    "после", "перед", "когда", "если", "чтобы", "который", "которая",
    "которые", "также", "ещё", "уже", "всё", "все", "один", "одна", "этот",
    "эта", "эти", "такой", "такая", "наш", "наши", "жизни", "время",
    "среди", "подтвержденных", "подтверждённых", "достижений", "упоминаются",
    "память", "биография", "дело", "путь", "истоки", "служение",
}

_HEADING_PREFIXES = ("🕯️", "📚", "🏅", "🕊️", "🌌", "🌳", "🎨", "👤", "📜", "🌿", "🏛️", "🌹")
_REFERENCE_SECTION_HEADINGS = {
    "литература",
    "библиография",
    "примечания",
    "ссылки",
    "источники",
    "публикации",
    "издания",
    "сочинения",
    "фильмография",
    "дискография",
}


def _clean_string(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = value.replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(ch for ch in text if ch == "\n" or ord(ch) >= 32)
    return re.sub(r"\s+", " ", text).strip()


def _count_words(text: str) -> int:
    return len(re.findall(r"[а-яёa-z0-9]+(?:-[а-яёa-z0-9]+)?", text.lower()))


def _is_heading_like_line(line: str) -> bool:
    if not line:
        return True
    if line.startswith(_HEADING_PREFIXES):
        return True
    if re.search(r"[.!?…]", line):
        return False
    return _count_words(line) <= 6


def _normalize_heading(line: str) -> str:
    cleaned = line.strip().strip(":").strip()
    cleaned = re.sub(r"^[^\wа-яёa-z]+", "", cleaned.lower())
    return cleaned


def _looks_like_reference_line(line: str) -> bool:
    lowered = line.lower()
    if not lowered:
        return True
    if any(marker in lowered for marker in ("isbn", "http://", "https://", "www.", "doi", "//")):
        return True
    if any(
        marker in lowered
        for marker in (
            "цгакффд", "цг архив", "фотодокумент", "персональная выставка",
            "выставочный зал", "журнал", "реж.", "к/ф", "каталог",
            "справочник", "путеводитель", "издательство", "музей",
        )
    ):
        return True
    if any(marker in lowered for marker in ("№", "№ ", "стр.", " с. ", "— с.", "арх.", "инж.", "ред.", "сост.")):
        return True
    if re.match(r"^(ар\s*\d+|№\s*\d+)", lowered):
        return True
    if "«" in lowered and "»" in lowered and any(marker in lowered for marker in ("выставка", "обелиск", "фильм", "журнал")):
        return True
    if "«" in lowered and "»" in lowered and _count_words(lowered) <= 6:
        return True
    if len(re.findall(r"(?:\b[а-яёa-z]\.){1,}|\b[А-ЯЁA-Z]\.", line)) >= 3:
        return True
    if len(re.findall(r"\b\d{4}\b", lowered)) >= 2 and any(
        marker in lowered for marker in ("— м.", "— спб.", "изд.", "издание", "стр.", " с.", "экз.")
    ):
        return True
    if lowered.count("—") >= 2 and any(marker in lowered for marker in ("isbn", "спб.", "м.:", "с.", "стр.")):
        return True
    return False


def _strip_leading_name_clause(text: str, display_name: str) -> str:
    cleaned = _clean_string(text)
    if not cleaned or not display_name:
        return cleaned

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
    cleaned = _clean_string(text)
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?…])\s+", cleaned)
    return [part.strip() for part in parts if part.strip()]


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[а-яёa-z0-9]+(?:-[а-яёa-z0-9]+)?", text.lower())
        if len(token) > 2 and token not in _STOPWORDS
    }


def _extract_numbers(text: str) -> set[str]:
    return set(re.findall(r"\b\d{1,4}\b", text))


def build_source_units(source_text: str, display_name: str = "") -> list[str]:
    cleaned = source_text.replace("\r\n", "\n").replace("\r", "\n") if isinstance(source_text, str) else ""
    if not cleaned:
        return []

    units: list[str] = []
    skip_section = False

    for raw_line in cleaned.split("\n"):
        line = _clean_string(raw_line)
        if not line:
            continue

        if _is_heading_like_line(line):
            skip_section = _normalize_heading(line) in _REFERENCE_SECTION_HEADINGS
            continue

        if skip_section:
            continue

        line = _strip_leading_name_clause(line, display_name)
        for sentence in _split_sentences(line):
            if sentence and not _looks_like_reference_line(sentence):
                units.append(sentence)

    return units


def build_source_excerpt(source_text: str, display_name: str = "", max_units: int = 18, max_chars: int = 9000) -> str:
    excerpt_units: list[str] = []
    total_chars = 0

    for unit in build_source_units(source_text, display_name):
        next_len = total_chars + len(unit) + 1
        if excerpt_units and (len(excerpt_units) >= max_units or next_len > max_chars):
            break
        excerpt_units.append(unit)
        total_chars = next_len

    return " ".join(excerpt_units).strip()


def verify_biography_against_source(
    biography: str,
    *,
    source_text: str,
    display_name: str = "",
    extra_grounding_text: str = "",
) -> dict[str, Any]:
    source_units = build_source_units(source_text, display_name)
    if not source_units:
        return {"is_verified": False, "unsupported_sentences": [], "checked_sentences": 0}

    source_tokens = _tokenize(" ".join(source_units) + " " + extra_grounding_text)
    source_numbers = _extract_numbers(" ".join(source_units) + " " + extra_grounding_text)
    source_unit_tokens = [_tokenize(unit) for unit in source_units]

    checked_sentences = 0
    unsupported_sentences: list[str] = []

    for raw_line in biography.split("\n"):
        line = _clean_string(raw_line)
        if not line:
            continue
        if line.startswith(_HEADING_PREFIXES):
            continue
        if line == display_name:
            continue
        if re.fullmatch(r"(родился:\s*)?\d{1,2}\s+\S+\s+\d{4}(\s+—\s+(\d{1,2}\s+\S+\s+\d{4}|наши дни|наст\.\s*время))?", line.lower()):
            continue
        if re.fullmatch(r"\d{4}\s+—\s+(\d{4}|наши дни|наст\.\s*время)", line.lower()):
            continue

        for sentence in _split_sentences(line):
            checked_sentences += 1
            sentence_tokens = _tokenize(sentence)
            if not sentence_tokens:
                continue

            overall_overlap = len(sentence_tokens & source_tokens) / len(sentence_tokens)
            best_unit_overlap = 0.0
            for unit_tokens in source_unit_tokens:
                if not unit_tokens:
                    continue
                overlap = len(sentence_tokens & unit_tokens) / len(sentence_tokens)
                if overlap > best_unit_overlap:
                    best_unit_overlap = overlap

            sentence_numbers = _extract_numbers(sentence)
            numbers_supported = sentence_numbers <= source_numbers

            if not numbers_supported or (overall_overlap < 0.72 and best_unit_overlap < 0.5):
                unsupported_sentences.append(sentence)

    return {
        "is_verified": not unsupported_sentences and checked_sentences > 0,
        "unsupported_sentences": unsupported_sentences,
        "checked_sentences": checked_sentences,
    }
