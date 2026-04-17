"""
queue_backend.py
----------------
Thin abstraction over RQ (Redis Queue).

Keeping this as a separate module means the queue technology can be swapped
(e.g. to Dramatiq or Celery) without touching any business logic.
"""
import logging
from datetime import timedelta
from typing import Callable

from redis import Redis
from rq import Queue
from rq.job import Job
from rq.exceptions import NoSuchJobError

from app.config import settings

logger = logging.getLogger(__name__)

_redis_conn: Redis | None = None
_queues: dict[str, Queue] = {}


def _get_redis() -> Redis:
    global _redis_conn
    if _redis_conn is None:
        _redis_conn = Redis.from_url(settings.redis_url)
    return _redis_conn


def _get_queue(name: str = "images") -> Queue:
    if name not in _queues:
        _queues[name] = Queue(name, connection=_get_redis())
    return _queues[name]


def enqueue_job(
    func: Callable,
    *args,
    queue: str = "images",
    job_timeout: int = 600,
    delay_seconds: int = 0,
    **kwargs,
) -> str:
    """
    Enqueue a function for background execution.

    Args:
        func: The function to execute.
        *args: Positional arguments for func.
        queue: Queue name ("images", "bios", "exports"). Default: "images".
        **kwargs: Keyword arguments for func.

    Returns the job ID string, or raises RuntimeError if Redis is unavailable.
    """
    from rq import Retry

    q = _get_queue(queue)
    enqueue_fn = q.enqueue_in if delay_seconds and delay_seconds > 0 else q.enqueue
    enqueue_args = [timedelta(seconds=delay_seconds), func, *args] if delay_seconds and delay_seconds > 0 else [func, *args]
    job = enqueue_fn(
        *enqueue_args,
        **kwargs,
        job_timeout=job_timeout,
        result_ttl=3600,
        failure_ttl=3600,
        retry=Retry(max=settings.worker_max_retries, interval=settings.worker_retry_delay),
    )
    logger.info("Enqueued job %s → %s (queue=%s)", job.id, func.__name__, queue)
    return job.id


def get_job_status(job_id: str) -> dict:
    """
    Retrieve RQ job status by job_id.

    Returns a dict compatible with job_store format.
    """
    try:
        job = Job.fetch(job_id, connection=_get_redis())
        status = job.get_status(refresh=True)
        result = job.result if job.is_finished else None
        exc = str(job.exc_info) if job.is_failed else None
        return {
            "status": str(status),
            "result": result,
            "error": exc,
        }
    except NoSuchJobError:
        return {"status": "not_found"}
    except Exception:
        logger.exception("Failed to fetch RQ job %s", job_id)
        return {"status": "error"}
