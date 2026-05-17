"""
biography_service.py
--------------------
Safe biography generation pipeline helpers.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable

from app.services.deepseek_service import DeepSeekServiceError

logger = logging.getLogger(__name__)

MISSING_FULL_NAME = "missing_full_name"
MISSING_BIRTH_DATE = "missing_birth_date"
MISSING_DEATH_DATE = "missing_death_date"
MISSING_ACTIVITY = "missing_activity"
MISSING_ACHIEVEMENTS = "missing_achievements"
MISSING_SOURCE_NOTES = "missing_source_notes"
LLM_FAILED_FALLBACK_USED = "llm_failed_fallback_used"

_WHITESPACE_RE = re.compile(r"\s+")
_MAX_NAME_LENGTH = 120
_MAX_NOTES_LENGTH = 1200
_MAX_ACTIVITY_LENGTH = 240
_MAX_ACHIEVEMENTS = 8


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
        "activity": _first_non_empty(
            raw.get("activity"),
            raw.get("occupation"),
            raw.get("profession"),
            raw.get("short_description"),
            max_length=_MAX_ACTIVITY_LENGTH,
        ),
        "achievements": _clean_string_list(raw.get("achievements")),
        "source_notes": _first_non_empty(
            raw.get("source_notes"),
            raw.get("summary_text"),
            raw.get("summary"),
            raw.get("notes"),
            raw.get("description"),
            max_length=_MAX_NOTES_LENGTH,
        ),
    }

    if not normalized["source_notes"] and isinstance(source_person, str):
        normalized["source_notes"] = _clean_string(source_person, max_length=_MAX_NOTES_LENGTH)

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
    if not normalized.get("source_notes"):
        warnings.append(MISSING_SOURCE_NOTES)

    return warnings


def _has_material_facts(normalized: dict[str, Any]) -> bool:
    return any(
        [
            normalized.get("birth_date"),
            normalized.get("death_date"),
            normalized.get("activity"),
            normalized.get("achievements"),
            normalized.get("source_notes"),
        ]
    )


def build_biography_context(normalized: dict[str, Any]) -> str:
    lines: list[str] = []

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


def build_fallback_biography(normalized: dict[str, Any]) -> str:
    sentences: list[str] = []

    if normalized.get("full_name"):
        sentences.append(
            f"{normalized['full_name']} — человек, память о котором сохраняется на основе доступных проверенных сведений."
        )
    else:
        sentences.append(
            "Для этой страницы пока доступно немного проверенных сведений, поэтому приводится краткая нейтральная биографическая заметка."
        )

    birth_date = normalized.get("birth_date")
    death_date = normalized.get("death_date")
    if birth_date and death_date:
        sentences.append(f"Из доступных данных известны годы жизни: {birth_date} — {death_date}.")
    elif birth_date:
        sentences.append(f"Из доступных данных известна дата рождения: {birth_date}.")
    elif death_date:
        sentences.append(f"Из доступных данных известна дата смерти: {death_date}.")

    if normalized.get("activity"):
        sentences.append(f"Основная сфера деятельности, указанная в источниках: {normalized['activity']}.")

    achievements = normalized.get("achievements") or []
    if achievements:
        sentences.append(
            "Среди подтвержденных сведений упоминаются следующие достижения: "
            + "; ".join(achievements)
            + "."
        )

    if normalized.get("source_notes"):
        sentences.append(_append_period(normalized["source_notes"]))
    elif not normalized.get("full_name"):
        sentences.append(
            "Подробная биография будет возможна после появления дополнительных подтвержденных данных."
        )
    else:
        sentences.append(
            "Подробная биография может быть дополнена после появления новых подтвержденных источников."
        )

    return " ".join(sentence.strip() for sentence in sentences if sentence.strip())


def _sanitize_generated_biography(text: Any) -> str:
    cleaned = _clean_string(text, max_length=4000)
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
) -> tuple[str, list[str]]:
    if not _has_material_facts(normalized):
        return "", []

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
                raise DeepSeekServiceError("Biography LLM output too close to source text")
        except DeepSeekServiceError:
            raise
        except Exception as exc:
            logger.warning("Biography uniqueness check failed: %s", exc)

    return candidate, []


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
        biography, extra_warnings = _safe_llm_generate(
            normalized,
            style,
            llm_generate,
            uniqueness_check=uniqueness_check,
        )
        warnings.extend(extra_warnings)
    except DeepSeekServiceError as exc:
        logger.warning("Biography generation fallback engaged: %s", exc)
        used_fallback = True
        warnings.append(LLM_FAILED_FALLBACK_USED)
        biography = build_fallback_biography(normalized)
    except Exception as exc:  # pragma: no cover - final safety net
        logger.exception("Unexpected biography generation failure: %s", exc)
        used_fallback = True
        warnings.append(LLM_FAILED_FALLBACK_USED)
        biography = build_fallback_biography(normalized)

    biography = _sanitize_generated_biography(biography)
    if not biography:
        used_fallback = True
        if LLM_FAILED_FALLBACK_USED not in warnings:
            warnings.append(LLM_FAILED_FALLBACK_USED)
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
        warnings = list(dict.fromkeys([*warnings, LLM_FAILED_FALLBACK_USED]))

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
