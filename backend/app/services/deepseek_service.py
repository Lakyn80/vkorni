import os
import re
import logging
import httpx

from app.services.prompt_service import pick_angle, build_system_prompt, build_user_message

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_BILLING_ERROR_MESSAGE = "У DeepSeek закончился API-кредит. Пополните баланс и повторите запрос."
DEEPSEEK_UNAVAILABLE_MESSAGE = "Сервис генерации текста DeepSeek временно недоступен. Попробуйте позже."
DEEPSEEK_MISCONFIGURED_MESSAGE = "Сервис генерации текста не настроен на сервере."

logger = logging.getLogger(__name__)


class DeepSeekServiceError(RuntimeError):
    """Raised when the upstream text generation service is unavailable."""


class DeepSeekBillingError(DeepSeekServiceError):
    """Raised when the upstream provider rejects requests due to billing."""


def _clean(raw: str) -> str:
    """Strip Markdown artifacts from the model output."""
    cleaned = raw.replace("***", "").replace("##", "").replace("#", "")
    cleaned = re.sub(r"-{3,}", "", cleaned)
    cleaned = re.sub(r"_{3,}", "", cleaned)
    cleaned = re.sub(r"\n\s*\n\s*\n+", "\n\n", cleaned)
    return cleaned.strip()


def _extract_error_message(response: httpx.Response | None) -> str | None:
    if response is None:
        return None

    try:
        payload = response.json()
    except ValueError:
        return None

    if not isinstance(payload, dict):
        return None

    error = payload.get("error")
    if isinstance(error, str) and error.strip():
        return error.strip()
    if isinstance(error, dict):
        for key in ("message", "detail", "msg"):
            value = error.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    for key in ("detail", "message"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return None


def _extract_generated_text(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError as exc:
        raise DeepSeekServiceError(DEEPSEEK_UNAVAILABLE_MESSAGE) from exc

    if not isinstance(payload, dict):
        raise DeepSeekServiceError(DEEPSEEK_UNAVAILABLE_MESSAGE)

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise DeepSeekServiceError(DEEPSEEK_UNAVAILABLE_MESSAGE)

    message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
    content = message.get("content", "") if isinstance(message, dict) else ""
    cleaned = _clean(content)
    if not cleaned:
        raise DeepSeekServiceError(DEEPSEEK_UNAVAILABLE_MESSAGE)

    return cleaned


def generate_text(
    context: str,
    style: str | None,
    angle_id: str | None = None,
    exclude_angle_ids: list[str] | None = None,
) -> tuple[str, str]:
    """
    Generate a biography text.

    Args:
        context:            Wikipedia facts for this person.
        style:              Optional writing style from ChromaDB.
        angle_id:           Force a specific angle (for tests/retry).
        exclude_angle_ids:  Angles already tried — will not repeat.

    Returns:
        (generated_text, angle_id_used)
    """
    DEEPSEEK_KEY = os.getenv("DEEPSEEK_KEY")
    if not DEEPSEEK_KEY:
        raise DeepSeekServiceError(DEEPSEEK_MISCONFIGURED_MESSAGE)

    angle = pick_angle(exclude_ids=exclude_angle_ids) if angle_id is None else next(
        (a for a in __import__("app.services.prompt_service", fromlist=["ANGLES"]).ANGLES if a["id"] == angle_id),
        pick_angle(exclude_ids=exclude_angle_ids),
    )

    system_prompt = build_system_prompt(angle, style)
    user_message = build_user_message(context, angle)

    payload = {
        "model": "deepseek-chat",
        "max_tokens": 2000,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
    }

    headers = {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {DEEPSEEK_KEY}",
    }

    try:
        response = httpx.post(DEEPSEEK_URL, json=payload, headers=headers, timeout=90)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        provider_message = _extract_error_message(exc.response) or str(exc)
        logger.exception("DeepSeek request failed: %s", provider_message)
        if exc.response is not None and exc.response.status_code == 402:
            raise DeepSeekBillingError(DEEPSEEK_BILLING_ERROR_MESSAGE) from exc
        raise DeepSeekServiceError(DEEPSEEK_UNAVAILABLE_MESSAGE) from exc
    except httpx.RequestError as exc:
        logger.exception("DeepSeek request failed")
        raise DeepSeekServiceError(DEEPSEEK_UNAVAILABLE_MESSAGE) from exc

    return _extract_generated_text(response), angle["id"]
