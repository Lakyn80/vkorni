import os
import json
import redis
import logging

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)


def get_json(key: str):
    try:
        val = r.get(f"bio:{key}")
        if val:
            return json.loads(val)
    except Exception:
        logger.exception("Redis get failed", extra={"key": key})
    return None


def set_json(key: str, value) -> None:
    try:
        r.set(f"bio:{key}", json.dumps(value))
    except Exception:
        logger.exception("Redis set failed", extra={"key": key})
        raise


def delete_key(key: str) -> bool:
    try:
        return bool(r.delete(f"bio:{key}"))
    except Exception:
        logger.exception("Redis delete failed", extra={"key": key})
        raise


def list_keys() -> list[str]:
    try:
        # Return only biography keys, strip the "bio:" prefix
        return sorted([k[4:] for k in r.scan_iter(match="bio:*")])
    except Exception:
        logger.exception("Redis list failed")
        raise


def delete_all_keys() -> int:
    try:
        keys = list(r.scan_iter(match="bio:*"))
        if keys:
            return r.delete(*keys)
        return 0
    except Exception:
        logger.exception("Redis delete_all failed")
        raise


def delete_cached(name: str) -> bool:
    key = f"bio:{name}"
    existed = r.exists(key)
    r.delete(key)
    return bool(existed)
