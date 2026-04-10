import logging
from app.db.redis_client import get_json, set_json, delete_key, list_keys, delete_all_keys

logger = logging.getLogger(__name__)


def get_biography(name: str) -> dict | None:
    return get_json(name)


def get_biography_strict(name: str) -> dict | None:
    return get_json(name, raise_on_error=True)


def set_biography(name: str, text: str, photos: list[str], birth: str | None = None, death: str | None = None, photo_sources: dict | None = None) -> None:
    value = {"name": name, "text": text, "photos": photos, "birth": birth, "death": death, "photo_sources": photo_sources or {}}
    set_json(name, value)


def delete_biography(name: str) -> bool:
    return delete_key(name)


def list_biographies() -> list[str]:
    return list_keys()


def delete_all_biographies() -> int:
    return delete_all_keys()
