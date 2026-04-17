"""
batch.py
--------
Endpoints: batch biography generation (async, RQ-backed).

Routes:
    POST /api/batch
    GET  /api/batch/{batch_id}
    POST /api/batch/{batch_id}/retry
"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import json_response, validate_person_name
from app.config import settings
from app.services.batch_service import (
    create_batch as _create_batch,
    get_batch_status,
    get_failed_names,
    update_job,
)
from app.workers.queue_backend import enqueue_job
from app.workers.bio_worker import process_biography

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["batch"])


class BatchRequest(BaseModel):
    names: list[str]
    style_name: str | None = None


@router.post("/batch")
def create_batch(payload: BatchRequest):
    names = [validate_person_name(n) for n in payload.names if n and n.strip()]
    if not names:
        raise HTTPException(status_code=400, detail="No names provided")
    if len(names) > 500:
        raise HTTPException(status_code=400, detail="Too many names (max 500 per batch)")

    try:
        batch_id = _create_batch(names)
        for name in names:
            enqueue_job(
                process_biography,
                batch_id,
                name,
                payload.style_name,
                queue=settings.bios_queue_name,
            )
    except Exception as exc:
        logger.error("Failed to create batch: %s", exc)
        raise HTTPException(status_code=503, detail="Queue unavailable — please retry later")

    logger.info("Batch %s created with %d names", batch_id, len(names))
    return json_response({"batch_id": batch_id, "total": len(names), "status": "queued"})


@router.get("/batch/{batch_id}")
def get_batch(batch_id: str):
    data = get_batch_status(batch_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Batch not found (expired or invalid id)")
    return json_response(data)


@router.post("/batch/{batch_id}/retry")
def retry_batch(batch_id: str):
    failed = get_failed_names(batch_id)
    if not failed:
        return json_response({"batch_id": batch_id, "retried": 0, "message": "No failed jobs"})

    retried = 0
    for name in failed:
        try:
            update_job(batch_id, name, status="queued")
            enqueue_job(process_biography, batch_id, name, queue=settings.bios_queue_name)
            retried += 1
        except Exception as exc:
            logger.error("Failed to re-enqueue '%s': %s", name, exc)

    return json_response({"batch_id": batch_id, "retried": retried})
