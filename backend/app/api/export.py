"""
export.py
---------
Endpoints: export profile to vkorni.com, upload photo.

Routes:
    POST /api/export
    POST /api/upload
"""
import logging
import os
import re
from uuid import uuid4

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from app.api.deps import validate_name, json_response
from app.services.export_service import export_profile_to_vkorni
from app.services.wiki_service import convert_to_webp
from app.services.bulk_export_service import create_bulk_export, get_bulk_export
from app.workers.export_worker import schedule_bulk_export
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["export"])

ALLOWED_UPLOAD_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}


class ExportProfile(BaseModel):
    name: str
    text: str
    photos: list[str] = []
    birth: str | None = None
    death: str | None = None
    photo_source_url: str | None = None


def _safe_dir_name(name: str) -> str:
    safe = re.sub(r"[^\w\-\. ]+", "", name, flags=re.UNICODE).strip()
    return safe.replace(" ", "_") or "uploads"


def _store_upload(file: UploadFile, person_name: str | None) -> str:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    _, ext = os.path.splitext(file.filename)
    ext = ext.lower()
    if ext not in ALLOWED_UPLOAD_EXTS:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    folder = _safe_dir_name(person_name or "uploads")
    target_dir = os.path.join(settings.photos_dir, folder)
    os.makedirs(target_dir, exist_ok=True)

    filename = f"{uuid4().hex}{ext}"
    file_path = os.path.join(target_dir, filename)
    with open(file_path, "wb") as out:
        out.write(file.file.read())

    # Convert to WebP — always (handles HEIC/HEIF from iPhone too)
    file_path = convert_to_webp(file_path)
    filename = os.path.basename(file_path)
    return f"/static/photos/{folder}/{filename}"


@router.post("/export")
def export_profile(payload: ExportProfile):
    result = export_profile_to_vkorni(
        name=payload.name,
        text=payload.text,
        photos=payload.photos,
        birth=payload.birth,
        death=payload.death,
        photo_source_url=payload.photo_source_url,
        export_kind="manual",
    )
    return json_response(result)


class BulkExportRequest(BaseModel):
    names: list[str]


@router.post("/bulk-export")
def start_bulk_export(payload: BulkExportRequest):
    if not payload.names:
        raise HTTPException(status_code=400, detail="No names provided")
    try:
        export_id = create_bulk_export(payload.names)
        schedule_bulk_export(export_id)
    except Exception as exc:
        logger.error("Failed to start bulk export: %s", exc)
        raise HTTPException(status_code=503, detail="Bulk export queue unavailable — please retry later")
    return json_response({"export_id": export_id, "total": len(payload.names)})


@router.get("/bulk-export/{export_id}")
def get_bulk_export_status(export_id: str):
    state = get_bulk_export(export_id)
    if not state:
        raise HTTPException(status_code=404, detail="Export not found")
    return json_response(state)


@router.post("/upload")
def upload_photo(name: str = "", file: UploadFile = File(...)):
    url = _store_upload(file, name or None)
    return json_response({"url": url})
