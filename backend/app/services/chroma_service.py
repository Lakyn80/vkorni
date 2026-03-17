import os
import logging
from app.db.chroma_client import get_style, search_styles

logger = logging.getLogger(__name__)

DEFAULT_STYLE_NAME = os.getenv("DEFAULT_STYLE_NAME", "Владимир Высоцкий")


def get_style_context(style_name: str | None = None, top_k: int = 3) -> str:
    name = style_name or DEFAULT_STYLE_NAME
    style = get_style(name)
    if style:
        return style

    results = search_styles(name, top_k=top_k)
    if not results:
        logger.warning("No style found in Chroma", extra={"style": name})
        return ""
    return "\n".join([r["text"] for r in results])
