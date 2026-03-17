import logging
import os
import re
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.cache_service import get_biography, set_biography, delete_biography, list_biographies, delete_all_biographies
from app.services.chroma_service import get_style_context
from app.db.chroma_client import upsert_style
from app.services.deepseek_service import generate_text
from app.services.uniqueness_service import is_unique_enough
from app.services.vkorny_export import send_profile
from app.services.wiki_service import fetch_person_from_wikipedia, fetch_person_images, convert_to_webp
from app.db.photos_repo import get_photos_by_person

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["vkorny"])

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
    "Access-Control-Allow-Headers": "*",
}

STATIC_PHOTOS_DIR = os.getenv("PHOTOS_DIR", "/app/static/photos")
ALLOWED_UPLOAD_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}


class ExportProfile(BaseModel):
    name: str
    text: str
    photos: list[str] = []
    birth: str | None = None
    death: str | None = None
    photo_source_url: str | None = None


class StylePayload(BaseModel):
    name: str
    text: str


def _validate_name(name: str) -> str:
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Missing or empty name")
    cleaned = name.strip()
    if len(cleaned) > 120:
        raise HTTPException(status_code=400, detail="Name is too long")
    if any(ord(ch) < 32 for ch in cleaned):
        raise HTTPException(status_code=400, detail="Invalid characters in name")
    return cleaned


def _is_text_too_short(text: str) -> bool:
    if not text:
        return True
    word_count = len(text.split())
    paragraphs = [p for p in text.split("\n") if p.strip()]
    return word_count < 400 or len(paragraphs) < 2


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
    target_dir = os.path.join(STATIC_PHOTOS_DIR, folder)
    os.makedirs(target_dir, exist_ok=True)
    filename = f"{uuid4().hex}{ext}"
    file_path = os.path.join(target_dir, filename)
    with open(file_path, "wb") as out:
        out.write(file.file.read())
    # convert to WebP (handles HEIC/HEIF from iPhone too)
    file_path = convert_to_webp(file_path)
    filename = os.path.basename(file_path)
    return f"/static/photos/{folder}/{filename}"


def _response(payload: dict) -> JSONResponse:
    return JSONResponse(content=payload, headers=CORS_HEADERS)


@router.post("/generate")
def generate(
    name: str,
    force_regenerate: bool = Query(False, alias="FORCE_REGENERATE"),
    style_name: str | None = Query(None, alias="STYLE_NAME"),
):
    person_name = _validate_name(name)

    if not force_regenerate:
        cached = get_biography(person_name)
        if cached:
            return _response(cached)

    person = fetch_person_from_wikipedia(person_name)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found on Wikipedia")

    style = get_style_context(style_name)
    wiki_source = person.get("summary_text", "")
    context = (
        f"Имя: {person.get('name')}\n"
        f"Годы жизни: {person.get('birth')}–{person.get('death')}\n"
        f"Краткое описание: {wiki_source}\n"
    )

    # Generate with uniqueness check — up to 3 attempts with different angles
    MAX_ATTEMPTS = 3
    text = ""
    tried_angles: list[str] = []

    for attempt in range(MAX_ATTEMPTS):
        candidate, angle_used = generate_text(context, style, exclude_angle_ids=tried_angles)
        tried_angles.append(angle_used)

        if _is_text_too_short(candidate):
            logger.warning("Attempt %d: text too short, retrying", attempt + 1)
            continue

        if is_unique_enough(candidate, wiki_source):
            text = candidate
            logger.info("Accepted text on attempt %d (angle=%s)", attempt + 1, angle_used)
            break

        logger.warning("Attempt %d: text too similar to Wikipedia (angle=%s), retrying", attempt + 1, angle_used)

    if not text:
        # Last resort — use last candidate even if similarity is high
        text = candidate if candidate else ""

    if _is_text_too_short(text):
        logger.error("All attempts produced short text for %s", person_name)
        raise HTTPException(status_code=500, detail="Generated text is too short")

    downloaded = fetch_person_images(person.get("name") or person_name)
    photo_rows = get_photos_by_person(person_name)
    if downloaded:
        photos = [p["file_path"] for p in downloaded if p.get("file_path")]
        photo_sources = {p["file_path"]: p["source_url"] for p in downloaded if p.get("source_url")}
    elif photo_rows:
        photos = [p["file_path"] for p in photo_rows]
        photo_sources = {p["file_path"]: p["source_url"] for p in photo_rows if p.get("source_url")}
    else:
        photos = person.get("images", [])
        photo_sources = {}

    birth = person.get("birth")
    death = person.get("death")
    set_biography(person_name, text, photos, birth=birth, death=death, photo_sources=photo_sources)
    return _response({"name": person_name, "text": text, "photos": photos, "birth": birth, "death": death, "photo_sources": photo_sources})


@router.delete("/cache/{name}")
def delete_cache(name: str):
    from app.db.redis_client import delete_cached

    deleted = delete_cached(name)
    return _response({"deleted": deleted, "name": name})


@router.get("/cache/{name}")
def get_cached_profile(name: str):
    person_name = _validate_name(name)
    cached = get_biography(person_name)
    if not cached:
        raise HTTPException(status_code=404, detail="Profile not found in cache")
    return _response(cached)


@router.post("/export")
def export_profile(payload: ExportProfile):
    result = send_profile(payload.name, payload.text, payload.photos, birth=payload.birth, death=payload.death, photo_source_url=payload.photo_source_url)
    return _response(result)


@router.post("/style")
def upsert_style_profile(payload: StylePayload):
    style_name = _validate_name(payload.name)
    style_text = (payload.text or "").strip()
    if len(style_text) < 50:
        raise HTTPException(status_code=400, detail="Style text is too short")
    upsert_style(style_name, style_text)
    return _response({"status": "OK", "name": style_name})


@router.post("/upload")
def upload_photo(name: str = "", file: UploadFile = File(...)):
    url = _store_upload(file, name)
    return _response({"url": url})


@router.get("/wiki/{name}")
def wiki(name: str):
    person_name = _validate_name(name)
    person = fetch_person_from_wikipedia(person_name)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found on Wikipedia")

    return _response({
        "name": person.get("name"),
        "text": person.get("summary_text"),
        "photos": person.get("images", []),
    })


@router.get("/cache")
def cache_list():
    return _response({"names": list_biographies()})


@router.delete("/cache")
def cache_delete_all():
    deleted = delete_all_biographies()
    return _response({"deleted": deleted})


# ---------------------------------------------------------------------------
# Image pipeline endpoints
# ---------------------------------------------------------------------------

@router.post("/image-job")
def start_image_job(
    name: str,
    profession: str | None = Query(None, description="Artist, politician, scientist, athlete …"),
):
    """
    Enqueue a background image-processing job for a person.
    Returns immediately with a job_id — never blocks.
    """
    from uuid import uuid4
    from app.workers.queue_backend import enqueue_job
    from app.workers.job_store import set_status
    from app.workers.image_worker import process_images_for_person

    person_name = _validate_name(name)
    job_id = uuid4().hex

    try:
        set_status(job_id, "queued")
        enqueue_job(process_images_for_person, person_name, job_id, profession)
    except Exception as exc:
        logger.error("Failed to enqueue image job for '%s': %s", person_name, exc)
        raise HTTPException(
            status_code=503,
            detail="Queue unavailable — please retry later",
        )

    return _response({"job_id": job_id, "status": "queued", "name": person_name})


@router.get("/image-job/{job_id}")
def poll_image_job(job_id: str):
    """
    Poll the status of a background image-processing job.

    Possible statuses: queued | running | done | failed | unknown
    """
    from app.workers.job_store import get_status

    data = get_status(job_id)
    return _response({"job_id": job_id, **data})


@router.get("/images/{name}")
def list_accepted_images(name: str):
    """
    List accepted (composed) portrait images for a person.
    """
    import glob as _glob
    from app.config import settings

    person_name = _validate_name(name)
    accepted_dir = settings.accepted_dir

    pattern = os.path.join(accepted_dir, "*.jpg")
    all_files = _glob.glob(pattern)

    rel_paths = [
        f"/static/accepted_images/{os.path.basename(p)}"
        for p in sorted(all_files)
    ]
    return _response({"name": person_name, "images": rel_paths})
