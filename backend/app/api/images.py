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
from urllib.parse import unquote
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import validate_person_name, json_response
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
    person_name = validate_person_name(name)
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
    person_name = validate_person_name(name)
    pattern = os.path.join(settings.accepted_dir, "*.jpg")
    files = sorted(_glob.glob(pattern))
    rel_paths = [f"/static/accepted_images/{os.path.basename(p)}" for p in files]
    return json_response({"name": person_name, "images": rel_paths})


class FrameRequest(BaseModel):
    photo_url: str          # relative URL like /static/photos/.../file.webp
    birth: str | None = None
    death: str | None = None
    frame_id: int | None = None


@router.post("/frame")
def generate_frame(payload: FrameRequest):
    """Generate a memorial frame for a photo and return its public URL."""
    decoded = unquote(payload.photo_url)
    local = os.path.join("/app", decoded.lstrip("/"))
    if not os.path.exists(local):
        raise HTTPException(status_code=404, detail=f"Photo not found: {payload.photo_url}")

    try:
        from app.services.frame_service import compose_portrait, resolve_frame_id

        frame_id = resolve_frame_id(payload.photo_url, payload.frame_id)
        framed = compose_portrait(local, birth=payload.birth, death=payload.death, frame_id=frame_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # framed is absolute path like /app/static/accepted_images/foo_frame3.jpg
    rel = os.path.relpath(framed, "/app").replace("\\", "/")
    return json_response({"url": f"/{rel}", "frame_id": frame_id})
