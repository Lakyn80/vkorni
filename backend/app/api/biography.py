"""
biography.py
------------
Endpoints: generate, cache CRUD, wiki lookup.

Routes:
    POST   /api/generate
    GET    /api/cache
    DELETE /api/cache
    GET    /api/cache/{name}
    DELETE /api/cache/{name}
    GET    /api/wiki/{name}
"""
import logging

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import validate_person_name, json_response
from app.services.cache_service import (
    get_biography, get_biography_strict, set_biography,
    delete_biography, list_biographies, delete_all_biographies,
)
from app.services.wiki_service import fetch_person_from_wikipedia, fetch_person_images
from app.services.deepseek_service import generate_text
from app.services.uniqueness_service import is_unique_enough
from app.services.chroma_service import get_style_context
from app.db.photos_repo import get_photos_by_person
from app.db.redis_client import CacheUnavailableError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["biography"])

MAX_GENERATION_ATTEMPTS = 3
MIN_WORD_COUNT = 400


def _cache_unavailable() -> HTTPException:
    return HTTPException(status_code=503, detail="Cache unavailable — please retry later")


def _is_text_too_short(text: str) -> bool:
    if not text:
        return True
    return len(text.split()) < MIN_WORD_COUNT or len([p for p in text.split("\n") if p.strip()]) < 2


def _build_photo_maps(downloaded: list[dict], photo_rows: list[dict], person: dict) -> tuple[list, dict]:
    if downloaded:
        photos = [p["file_path"] for p in downloaded if p.get("file_path")]
        sources = {p["file_path"]: p["source_url"] for p in downloaded if p.get("source_url")}
    elif photo_rows:
        photos = [p["file_path"] for p in photo_rows]
        sources = {p["file_path"]: p["source_url"] for p in photo_rows if p.get("source_url")}
    else:
        photos = person.get("images", [])
        sources = {}
    return photos, sources


@router.post("/generate")
def generate(
    name: str,
    force_regenerate: bool = Query(False, alias="FORCE_REGENERATE"),
    style_name: str | None = Query(None, alias="STYLE_NAME"),
):
    person_name = validate_person_name(name)

    if not force_regenerate:
        cached = get_biography(person_name)
        if cached:
            return json_response(cached)

    person = fetch_person_from_wikipedia(person_name)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found on Wikipedia")

    wiki_source = person.get("summary_text", "")
    context = (
        f"Имя: {person.get('name')}\n"
        f"Годы жизни: {person.get('birth')}–{person.get('death')}\n"
        f"Краткое описание: {wiki_source}\n"
    )
    style = get_style_context(style_name)

    text = ""
    candidate = ""
    tried_angles: list[str] = []

    for attempt in range(MAX_GENERATION_ATTEMPTS):
        candidate, angle_used = generate_text(context, style, exclude_angle_ids=tried_angles)
        tried_angles.append(angle_used)

        if _is_text_too_short(candidate):
            logger.warning("Attempt %d: text too short", attempt + 1)
            continue

        if is_unique_enough(candidate, wiki_source):
            text = candidate
            logger.info("Accepted text on attempt %d (angle=%s)", attempt + 1, angle_used)
            break

        logger.warning("Attempt %d: too similar to Wikipedia (angle=%s)", attempt + 1, angle_used)

    if not text:
        text = candidate

    if _is_text_too_short(text):
        raise HTTPException(status_code=500, detail="Generated text is too short")

    downloaded = fetch_person_images(person_name)
    photo_rows = get_photos_by_person(person_name)
    photos, photo_sources = _build_photo_maps(downloaded, photo_rows, person)

    birth = person.get("birth")
    death = person.get("death")
    try:
        set_biography(person_name, text, photos, birth=birth, death=death, photo_sources=photo_sources)
    except CacheUnavailableError:
        logger.warning("Cache write failed for '%s'; returning uncached profile", person_name)

    return json_response({
        "name": person_name, "text": text, "photos": photos,
        "birth": birth, "death": death, "photo_sources": photo_sources,
    })


@router.get("/cache")
def cache_list():
    try:
        return json_response({"names": list_biographies()})
    except CacheUnavailableError:
        raise _cache_unavailable()


@router.delete("/cache")
def cache_delete_all():
    try:
        deleted = delete_all_biographies()
    except CacheUnavailableError:
        raise _cache_unavailable()
    return json_response({"deleted": deleted})


@router.get("/cache/{name}")
def get_cached_profile(name: str):
    person_name = validate_person_name(name)
    try:
        cached = get_biography_strict(person_name)
    except CacheUnavailableError:
        raise _cache_unavailable()
    if not cached:
        raise HTTPException(status_code=404, detail="Profile not found in cache")
    return json_response(cached)


@router.delete("/cache/{name}")
def delete_cache(name: str):
    person_name = validate_person_name(name)
    try:
        deleted = delete_biography(person_name)
    except CacheUnavailableError:
        raise _cache_unavailable()
    return json_response({"deleted": deleted, "name": person_name})


@router.get("/wiki/{name}")
def wiki_lookup(name: str):
    person_name = validate_person_name(name)
    person = fetch_person_from_wikipedia(person_name)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found on Wikipedia")
    return json_response({
        "name": person.get("name"),
        "text": person.get("summary_text"),
        "photos": person.get("images", []),
    })
