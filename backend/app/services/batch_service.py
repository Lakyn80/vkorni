"""
batch_service.py
----------------
Manages biography batch jobs in Redis.

Key schema:
  batch:{batch_id}:meta       → {total, created_at, names[]}
  batch:{batch_id}:job:{name} → {status, text, birth, death, photos, error, attempts}

Statuses: queued | running | done | failed | retrying
TTL: 24 hours (86400 s)
"""

import json
import logging
import time
from uuid import uuid4

from redis import Redis
from app.config import settings

logger = logging.getLogger(__name__)

_BATCH_TTL = 86_400  # 24 hours


def _redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def _meta_key(batch_id: str) -> str:
    return f"batch:{batch_id}:meta"


def _job_key(batch_id: str, name: str) -> str:
    return f"batch:{batch_id}:job:{name}"


# ─── Write ────────────────────────────────────────────────────────────────────

def create_batch(names: list[str]) -> str:
    """Create a new batch, store metadata, return batch_id."""
    batch_id = uuid4().hex
    r = _redis()
    pipe = r.pipeline()

    meta = json.dumps({
        "total": len(names),
        "created_at": time.time(),
        "names": names,
    })
    pipe.setex(_meta_key(batch_id), _BATCH_TTL, meta)

    for name in names:
        pipe.setex(
            _job_key(batch_id, name),
            _BATCH_TTL,
            json.dumps({"status": "queued", "attempts": 0}),
        )

    pipe.execute()
    logger.info("Created batch %s with %d names", batch_id, len(names))
    return batch_id


def update_job(batch_id: str, name: str, **fields) -> None:
    """Merge fields into an existing job record (preserves existing fields)."""
    r = _redis()
    key = _job_key(batch_id, name)
    raw = r.get(key)
    data: dict = json.loads(raw) if raw else {}
    data.update(fields)
    r.setex(key, _BATCH_TTL, json.dumps(data))


# ─── Read ─────────────────────────────────────────────────────────────────────

def get_batch_status(batch_id: str) -> dict | None:
    r = _redis()
    raw = r.get(_meta_key(batch_id))
    if not raw:
        return None

    meta = json.loads(raw)
    names: list[str] = meta["names"]

    counts = {"queued": 0, "running": 0, "done": 0, "failed": 0, "retrying": 0}
    results = []

    for name in names:
        job_raw = r.get(_job_key(batch_id, name))
        job = json.loads(job_raw) if job_raw else {"status": "queued"}
        status = job.get("status", "queued")
        counts[status] = counts.get(status, 0) + 1
        results.append({"name": name, **job})

    return {
        "batch_id": batch_id,
        "total": meta["total"],
        "created_at": meta["created_at"],
        **counts,
        "results": results,
    }


def get_failed_names(batch_id: str) -> list[str]:
    """Return names of all failed jobs in a batch."""
    r = _redis()
    raw = r.get(_meta_key(batch_id))
    if not raw:
        return []
    names = json.loads(raw)["names"]
    failed = []
    for name in names:
        job_raw = r.get(_job_key(batch_id, name))
        if job_raw:
            job = json.loads(job_raw)
            if job.get("status") == "failed":
                failed.append(name)
    return failed
