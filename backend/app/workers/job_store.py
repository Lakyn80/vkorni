"""
job_store.py
------------
Lightweight job status store backed by Redis.

Used to track pipeline progress independently of RQ's own job state,
which allows richer status detail (e.g. how many images accepted/rejected).
"""
import json
import logging
from typing import Any, Optional

from redis import Redis

from app.config import settings

logger = logging.getLogger(__name__)

_JOB_TTL = 3600  # seconds — jobs expire after 1 hour
_KEY_PREFIX = "imgpipeline:job:"

_redis_conn: Redis | None = None


def _get_redis() -> Redis:
    global _redis_conn
    if _redis_conn is None:
        _redis_conn = Redis.from_url(settings.redis_url)
    return _redis_conn


def _key(job_id: str) -> str:
    return f"{_KEY_PREFIX}{job_id}"


def set_status(job_id: str, status: str, detail: Optional[Any] = None) -> None:
    payload = json.dumps({"status": status, "detail": detail})
    try:
        _get_redis().setex(_key(job_id), _JOB_TTL, payload)
    except Exception:
        logger.exception("job_store.set_status failed for job %s", job_id)


def get_status(job_id: str) -> dict:
    try:
        raw = _get_redis().get(_key(job_id))
        if raw:
            return json.loads(raw)
    except Exception:
        logger.exception("job_store.get_status failed for job %s", job_id)
    return {"status": "unknown"}
