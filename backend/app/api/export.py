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
from app.services.vkorny_export import send_profile
from app.services.wiki_service import convert_to_webp
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
    result = send_profile(
        payload.name,
        payload.text,
        payload.photos,
        birth=payload.birth,
        death=payload.death,
        photo_source_url=payload.photo_source_url,
    )
    return json_response(result)


@router.post("/upload")
def upload_photo(name: str = "", file: UploadFile = File(...)):
    url = _store_upload(file, name or None)
    return json_response({"url": url})
