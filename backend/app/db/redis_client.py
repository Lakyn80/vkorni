import json
import redis
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class CacheUnavailableError(RuntimeError):
    pass


def _build_client() -> redis.Redis:
    return redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
        health_check_interval=30,
    )


r = _build_client()


def get_json(key: str, *, raise_on_error: bool = False):
    try:
        val = r.get(f"bio:{key}")
        if val:
            return json.loads(val)
    except Exception as exc:
        logger.exception("Redis get failed", extra={"key": key})
        if raise_on_error:
            raise CacheUnavailableError("Cache read failed") from exc
    return None


def set_json(key: str, value) -> None:
    try:
        r.set(f"bio:{key}", json.dumps(value))
    except Exception as exc:
        logger.exception("Redis set failed", extra={"key": key})
        raise CacheUnavailableError("Cache write failed") from exc


def delete_key(key: str) -> bool:
    try:
        return bool(r.delete(f"bio:{key}"))
    except Exception as exc:
        logger.exception("Redis delete failed", extra={"key": key})
        raise CacheUnavailableError("Cache delete failed") from exc


def list_keys() -> list[str]:
    try:
        # Return only biography keys, strip the "bio:" prefix
        return sorted([k[4:] for k in r.scan_iter(match="bio:*")])
    except Exception as exc:
        logger.exception("Redis list failed")
        raise CacheUnavailableError("Cache list failed") from exc


def delete_all_keys() -> int:
    try:
        keys = list(r.scan_iter(match="bio:*"))
        if keys:
            return r.delete(*keys)
        return 0
    except Exception as exc:
        logger.exception("Redis delete_all failed")
        raise CacheUnavailableError("Cache delete_all failed") from exc


def delete_cached(name: str) -> bool:
    try:
        key = f"bio:{name}"
        existed = r.exists(key)
        r.delete(key)
        return bool(existed)
    except Exception as exc:
        logger.exception("Redis delete failed", extra={"key": name})
        raise CacheUnavailableError("Cache delete failed") from exc
