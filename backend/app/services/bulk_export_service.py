"""
bulk_export_service.py
----------------------
Redis store for bulk export jobs.

Key schema:
  bulkexport:{id}:meta  → {total, names[]}
  bulkexport:{id}:{name} → {status, url, error}

Statuses: pending | running | done | failed
TTL: 24 hours
"""
import json
import time
from uuid import uuid4

from redis import Redis
from app.config import settings

_TTL = 86_400


def _r() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def create_bulk_export(names: list[str]) -> str:
    eid = uuid4().hex
    r = _r()
    pipe = r.pipeline()
    pipe.setex(f"bulkexport:{eid}:meta", _TTL, json.dumps({"total": len(names), "names": names, "created_at": time.time()}))
    for name in names:
        pipe.setex(f"bulkexport:{eid}:{name}", _TTL, json.dumps({"status": "pending"}))
    pipe.execute()
    return eid


def update_job(eid: str, name: str, status: str, url: str | None = None, error: str | None = None) -> None:
    r = _r()
    r.setex(f"bulkexport:{eid}:{name}", _TTL, json.dumps({"status": status, "url": url, "error": error}))


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
        job = json.loads(job_raw) if job_raw else {"status": "pending"}
        results.append({"name": name, **job})
    done = sum(1 for r_ in results if r_["status"] == "done")
    failed = sum(1 for r_ in results if r_["status"] == "failed")
    running = sum(1 for r_ in results if r_["status"] == "running")
    return {
        "id": eid,
        "total": meta["total"],
        "done": done,
        "failed": failed,
        "running": running,
        "pending": meta["total"] - done - failed - running,
        "results": results,
    }
