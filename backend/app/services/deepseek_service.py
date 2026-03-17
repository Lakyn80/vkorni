import os
import re
import requests
import logging

from app.services.prompt_service import pick_angle, build_system_prompt, build_user_message

DEEPSEEK_KEY = os.getenv("DEEPSEEK_KEY")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

logger = logging.getLogger(__name__)


def _clean(raw: str) -> str:
    """Strip Markdown artifacts from the model output."""
    cleaned = raw.replace("***", "").replace("##", "").replace("#", "")
    cleaned = re.sub(r"-{3,}", "", cleaned)
    cleaned = re.sub(r"_{3,}", "", cleaned)
    cleaned = re.sub(r"\n\s*\n\s*\n+", "\n\n", cleaned)
    return cleaned.strip()


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
    if not DEEPSEEK_KEY:
        raise RuntimeError("Chybí DEEPSEEK_KEY v .env")

    angle = pick_angle(exclude_ids=exclude_angle_ids) if angle_id is None else next(
        (a for a in __import__("app.services.prompt_service", fromlist=["ANGLES"]).ANGLES if a["id"] == angle_id),
        pick_angle(exclude_ids=exclude_angle_ids),
    )

    system_prompt = build_system_prompt(angle, style)
    user_message = build_user_message(context, angle)

    payload = {
        "model": "deepseek-chat",
        "max_tokens": 2000,
        "temperature": 0.9,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_KEY}",
    }

    try:
        response = requests.post(DEEPSEEK_URL, json=payload, headers=headers, timeout=90)
        response.raise_for_status()
    except Exception:
        logger.exception("DeepSeek request failed")
        raise

    raw = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    return _clean(raw), angle["id"]
