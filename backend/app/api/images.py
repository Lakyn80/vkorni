"""
images.py
---------
Endpoints: background image-processing jobs, list accepted images.

Routes:
    POST /api/image-job
    GET  /api/image-job/{job_id}
    GET  /api/images/{name}
"""
import glob as _glob
import logging
import os
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import validate_name, json_response
from app.workers.queue_backend import enqueue_job
from app.workers.job_store import set_status, get_status
from app.workers.image_worker import process_images_for_person
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["images"])


@router.post("/image-job")
def start_image_job(
    name: str,
    profession: str | None = Query(None, description="artist, politician, scientist, athlete …"),
):
    """Enqueue a background image-processing job. Returns immediately with job_id."""
    person_name = validate_name(name)
    job_id = uuid4().hex

    try:
        set_status(job_id, "queued")
        enqueue_job(process_images_for_person, person_name, job_id, profession)
    except Exception as exc:
        logger.error("Failed to enqueue image job for '%s': %s", person_name, exc)
        raise HTTPException(status_code=503, detail="Queue unavailable — please retry later")

    return json_response({"job_id": job_id, "status": "queued", "name": person_name})


@router.get("/image-job/{job_id}")
def poll_image_job(job_id: str):
    """Poll status of a background image-processing job."""
    data = get_status(job_id)
    return json_response({"job_id": job_id, **data})


@router.get("/images/{name}")
def list_accepted_images(name: str):
    """List accepted (framed) portrait images for a person."""
    person_name = validate_name(name)
    pattern = os.path.join(settings.accepted_dir, "*.jpg")
    files = sorted(_glob.glob(pattern))
    rel_paths = [f"/static/accepted_images/{os.path.basename(p)}" for p in files]
    return json_response({"name": person_name, "images": rel_paths})
