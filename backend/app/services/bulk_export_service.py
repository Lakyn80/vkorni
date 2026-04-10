"""
bulk_export_service.py
----------------------
Redis store for bulk export jobs.

Key schema:
  bulkexport:{id}:meta  → {total, names[]}
  bulkexport:{id}:{name} → {status, url, error}

Statuses: pending | queued | retrying | running | done | failed
TTL: 24 hours
"""
import json
import time
from uuid import uuid4

from redis import Redis
from app.config import settings

_TTL = 86_400
_UNSET = object()


def _r() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def create_bulk_export(names: list[str]) -> str:
    now = time.time()
    eid = uuid4().hex
    r = _r()
    pipe = r.pipeline()
    pipe.setex(
        f"bulkexport:{eid}:meta",
        _TTL,
        json.dumps({"total": len(names), "names": names, "created_at": now, "updated_at": now}),
    )
    for name in names:
        pipe.setex(
            f"bulkexport:{eid}:{name}",
            _TTL,
            json.dumps({"status": "pending", "url": None, "error": None, "attempts": 0, "updated_at": now}),
        )
    pipe.execute()
    return eid


def get_bulk_export_job(eid: str, name: str) -> dict | None:
    r = _r()
    raw = r.get(f"bulkexport:{eid}:{name}")
    if not raw:
        return None
    return json.loads(raw)


def update_job(
    eid: str,
    name: str,
    status=_UNSET,
    url=_UNSET,
    error=_UNSET,
    attempts=_UNSET,
    updated_at=_UNSET,
) -> dict:
    r = _r()
    current = get_bulk_export_job(eid, name) or {}
    now = time.time() if updated_at is _UNSET else updated_at

    if status is not _UNSET:
        current["status"] = status
    if url is not _UNSET:
        current["url"] = url
    if error is not _UNSET:
        current["error"] = error
    if attempts is not _UNSET:
        current["attempts"] = attempts
    current["updated_at"] = now

    r.setex(f"bulkexport:{eid}:{name}", _TTL, json.dumps(current))
    meta_raw = r.get(f"bulkexport:{eid}:meta")
    if meta_raw:
        meta = json.loads(meta_raw)
        meta["updated_at"] = now
        r.setex(f"bulkexport:{eid}:meta", _TTL, json.dumps(meta))
    return current


def get_bulk_export(eid: str) -> dict | None:
    r = _r()
    raw = r.get(f"bulkexport:{eid}:meta")
    if not raw:
        return None
    meta = json.loads(raw)
    names = meta["names"]
    results = []
    for name in names:
        job_raw = r.get(f"bulkexport:{eid}:{name}")
        job = json.loads(job_raw) if job_raw else {"status": "pending", "attempts": 0, "updated_at": meta.get("created_at")}
        results.append({"name": name, **job})
    done = sum(1 for r_ in results if r_["status"] == "done")
    failed = sum(1 for r_ in results if r_["status"] == "failed")
    running = sum(1 for r_ in results if r_["status"] == "running")
    queued = sum(1 for r_ in results if r_["status"] == "queued")
    retrying = sum(1 for r_ in results if r_["status"] == "retrying")
    pending = meta["total"] - done - failed - running - queued - retrying
    return {
        "id": eid,
        "total": meta["total"],
        "done": done,
        "failed": failed,
        "running": running,
        "queued": queued,
        "retrying": retrying,
        "pending": max(0, pending),
        "created_at": meta.get("created_at"),
        "updated_at": meta.get("updated_at"),
        "results": results,
    }
