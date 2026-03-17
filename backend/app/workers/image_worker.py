"""
image_worker.py
---------------
RQ worker task.

This module is executed inside the RQ worker process (separate from the FastAPI
process). Errors here are isolated — they cannot crash the API or cause 502s.

To start the worker:
    rq worker images --url redis://redis:6379/0
"""
import logging
from typing import Optional

from app.workers.job_store import set_status
from app.services.image_pipeline import run_pipeline

logger = logging.getLogger(__name__)


def process_images_for_person(
    name: str,
    job_id: str,
    profession: Optional[str] = None,
) -> dict:
    """
    Entry point called by RQ.

    All exceptions are caught so the job result is always a structured dict,
    never a bare exception that leaves the job in an unclear state.
    """
    set_status(job_id, "running")
    logger.info("Worker: starting pipeline for '%s' (job=%s)", name, job_id)

    try:
        result = run_pipeline(name, profession=profession)
        set_status(job_id, "done", result)
        logger.info("Worker: pipeline done for '%s' (job=%s)", name, job_id)
        return result
    except Exception as exc:
        error_msg = f"Pipeline crashed: {exc}"
        logger.exception("Worker: unhandled error for '%s' (job=%s)", name, job_id)
        set_status(job_id, "failed", {"error": error_msg})
        # Return structured error so RQ stores a result, not a raw exception
        return {"name": name, "accepted": [], "rejected": [], "errors": [error_msg]}
