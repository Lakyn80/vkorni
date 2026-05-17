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
from app.services.biography_service import (
    build_biography_response,
    build_biography_response_from_cache,
    generate_biography_text,
    normalize_requested_name,
)
from app.services.uniqueness_service import is_unique_enough
from app.services.chroma_service import get_style_context
from app.db.photos_repo import get_photos_by_person
from app.db.redis_client import CacheUnavailableError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["biography"])


def _cache_unavailable() -> HTTPException:
    return HTTPException(status_code=503, detail="Cache unavailable — please retry later")


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
    name: str | None = None,
    force_regenerate: bool = Query(False, alias="FORCE_REGENERATE"),
    style_name: str | None = Query(None, alias="STYLE_NAME"),
):
    person_name = normalize_requested_name(name)

    if not force_regenerate:
        try:
            cached = get_biography(person_name) if person_name else None
        except CacheUnavailableError:
            logger.warning("Cache read failed for '%s'; continuing without cache", person_name)
            cached = None
        except Exception:
            logger.exception("Unexpected cache read failure for '%s'", person_name)
            cached = None
        if cached:
            return json_response(build_biography_response_from_cache(cached))

    person: dict | None = None
    if person_name:
        try:
            person = fetch_person_from_wikipedia(person_name)
        except Exception:
            logger.exception("Wikipedia fetch failed for '%s'", person_name)
            person = None

    try:
        style = get_style_context(style_name)
    except Exception:
        logger.exception("Style lookup failed for '%s'", style_name)
        style = None

    generation = generate_biography_text(
        source_person=person,
        requested_name=person_name,
        style=style,
        llm_generate=generate_text,
        uniqueness_check=is_unique_enough,
    )

    downloaded: list[dict] = []
    photo_rows: list[dict] = []
    if person_name and person:
        try:
            downloaded = fetch_person_images(person_name)
        except Exception:
            logger.exception("Photo fetch failed for '%s'", person_name)
            downloaded = []
        try:
            photo_rows = get_photos_by_person(person_name)
        except Exception:
            logger.exception("Photo repository lookup failed for '%s'", person_name)
            photo_rows = []

    photos, photo_sources = _build_photo_maps(downloaded, photo_rows, person or {})

    try:
        if person_name:
            set_biography(
                person_name,
                generation["biography"],
                photos,
                birth=generation["birth"],
                death=generation["death"],
                photo_sources=photo_sources,
            )
    except CacheUnavailableError:
        logger.warning("Cache write failed for '%s'; returning uncached profile", person_name)
    except Exception:
        logger.exception("Unexpected cache write failure for '%s'", person_name)

    return json_response(
        build_biography_response(
            name=person_name or generation["name"],
            biography=generation["biography"],
            photos=photos,
            birth=generation["birth"],
            death=generation["death"],
            photo_sources=photo_sources,
            used_fallback=generation["used_fallback"],
            warnings=generation["warnings"],
        )
    )


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
