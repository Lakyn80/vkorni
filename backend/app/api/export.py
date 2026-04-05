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

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import json_response, validate_name
from app.config import settings
from app.db.stored_profiles_repo import add_stored_profile_attempt, get_stored_profile, list_stored_profiles
from app.services.bulk_export_service import create_bulk_export, get_bulk_export
from app.services.export_service import export_profile_to_vkorni
from app.services.wiki_service import convert_to_webp
from app.workers.export_worker import schedule_bulk_export

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["export"])

ALLOWED_UPLOAD_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}


class ExportProfile(BaseModel):
    name: str
    text: str
    photos: list[str] = Field(default_factory=list)
    birth: str | None = None
    death: str | None = None
    photo_source_url: str | None = None
    selected_photo: str | None = None
    photo_sources: dict[str, str] = Field(default_factory=dict)
    frame_id: int | None = None
    framed_photo_url: str | None = None
    framed_source_photo: str | None = None


class BulkExportRequest(BaseModel):
    names: list[str]


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

    file_path = convert_to_webp(file_path)
    filename = os.path.basename(file_path)
    return f"/static/photos/{folder}/{filename}"


def _ordered_snapshot_photos(payload: ExportProfile) -> list[str]:
    selected = payload.selected_photo or (payload.photos[0] if payload.photos else None)
    ordered = []
    if selected:
        ordered.append(selected)
    ordered.extend(payload.photos)

    seen: set[str] = set()
    result: list[str] = []
    for photo in ordered:
        if not photo or photo in seen:
            continue
        seen.add(photo)
        result.append(photo)
    return result


def _to_relative_static_url(path: str | None) -> str | None:
    if not path:
        return None
    normalized = os.path.normpath(path)
    static_root = os.path.normpath("/app/static")
    if not normalized.startswith(static_root):
        return None
    rel = os.path.relpath(normalized, "/app").replace("\\", "/")
    return f"/{rel}"


@router.post("/export")
def export_profile(payload: ExportProfile):
    ordered_photos = _ordered_snapshot_photos(payload)
    selected_photo = payload.selected_photo or (ordered_photos[0] if ordered_photos else None)
    resolved_photo_source = payload.photo_source_url or (payload.photo_sources.get(selected_photo) if selected_photo else None)

    result = export_profile_to_vkorni(
        name=payload.name,
        text=payload.text,
        photos=ordered_photos,
        birth=payload.birth,
        death=payload.death,
        photo_source_url=resolved_photo_source,
        export_kind="manual",
        selected_photo_url=selected_photo,
        photo_sources=payload.photo_sources,
        frame_id=payload.frame_id,
    )
    return json_response(result)


@router.get("/exported-profiles")
def exported_profiles_list():
    return json_response({"profiles": list_stored_profiles()})


@router.get("/exported-profiles/{profile_id}")
def exported_profiles_detail(profile_id: int):
    profile = get_stored_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Stored profile not found")
    return json_response(profile)


@router.post("/exported-profiles/{profile_id}/resend")
def resend_exported_profile(profile_id: int):
    stored = get_stored_profile(profile_id)
    if not stored:
        raise HTTPException(status_code=404, detail="Stored profile not found")

    ordered_photos = [photo["photo_url"] for photo in stored.get("photos", [])]
    selected_photo_url = stored.get("selected_photo_url")
    preferred_export_photo_url = None
    framed_image_path = stored.get("framed_image_path")
    if framed_image_path and os.path.exists(framed_image_path):
        preferred_export_photo_url = _to_relative_static_url(framed_image_path)

    photo_sources = {
        photo["photo_url"]: photo.get("source_url")
        for photo in stored.get("photos", [])
        if photo.get("source_url")
    }

    result = export_profile_to_vkorni(
        name=validate_name(stored["name"]),
        text=stored["text"] or "",
        photos=ordered_photos,
        birth=stored.get("birth"),
        death=stored.get("death"),
        photo_source_url=stored.get("selected_source_url"),
        export_kind="resend",
        selected_photo_url=selected_photo_url,
        preferred_export_photo_url=preferred_export_photo_url,
        preferred_source_photo_url=selected_photo_url,
        photo_sources=photo_sources,
        frame_id=stored.get("frame_id"),
    )

    if result.get("status") != "OK":
        add_stored_profile_attempt(
            stored_profile_id=profile_id,
            status=result.get("status", "ERROR"),
            export_kind="resend",
            thread_id=result.get("thread_id"),
            thread_url=result.get("url"),
            attachment_id=result.get("attachment_id"),
            attachment_url=result.get("attachment_url"),
            error=result.get("error"),
        )

    return json_response(result)


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
