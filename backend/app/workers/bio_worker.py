"""
bio_worker.py
-------------
RQ task for processing a single biography in a batch.

Fault-tolerance layers:
  1. try/except around every external call (Wiki, DeepSeek) — never crashes
  2. Exponential backoff retry via tenacity (max 3 attempts per step)
  3. On total failure: marks job as "failed" in batch_service (not raises)
  4. Worker process itself never dies — all errors are caught and stored
"""

import logging
import time

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.api.deps import is_probable_person_name
from app.services.batch_service import update_job
from app.services.wiki_service import fetch_person_from_wikipedia, fetch_person_images
from app.services.deepseek_service import generate_text
from app.services.biography_service import generate_biography_text
from app.services.chroma_service import get_style_context
from app.services.cache_service import set_biography
from app.services.uniqueness_service import is_unique_enough
from app.db.photos_repo import get_photos_by_person

logger = logging.getLogger(__name__)


# ─── Retried helpers ──────────────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=5, min=5, max=45),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _fetch_wiki(name: str) -> dict | None:
    return fetch_person_from_wikipedia(name)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=5, min=5, max=45),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _fetch_images(name: str) -> list[dict]:
    return fetch_person_images(name) or []


# ─── Main task ────────────────────────────────────────────────────────────────

def process_biography(batch_id: str, name: str, style_name: str | None = None) -> dict:
    """
    RQ task — process one biography name for a batch.

    Always returns a dict (never raises), so the worker never dies.
    Error details are stored via batch_service.update_job().
    """
    logger.info("[batch:%s] Starting biography for '%s'", batch_id, name)
    update_job(batch_id, name, status="running", started_at=time.time())

    try:
        if not is_probable_person_name(name):
            return _fail(batch_id, name, "Rejected non-person batch entry")

        # ── 1. Fetch source data ────────────────────────────────────────────
        try:
            person = _fetch_wiki(name)
        except Exception as exc:
            logger.warning("[batch:%s] Wikipedia fetch failed for '%s'; continuing with fallback-safe generation: %s", batch_id, name, exc)
            person = None

        try:
            style = get_style_context(style_name)
        except Exception as exc:
            logger.warning("[batch:%s] Style lookup failed for '%s'; continuing without style: %s", batch_id, name, exc)
            style = None

        generation = generate_biography_text(
            source_person=person,
            requested_name=name,
            style=style,
            llm_generate=generate_text,
            uniqueness_check=is_unique_enough,
        )
        text = generation["biography"]
        birth = generation["birth"]
        death = generation["death"]
        used_fallback = generation["used_fallback"]
        warnings = generation["warnings"]

        # ── 3. Fetch images ─────────────────────────────────────────────────
        try:
            downloaded = _fetch_images(name)
        except Exception as exc:
            logger.warning("[batch:%s] Image fetch failed (continuing without): %s", batch_id, exc)
            downloaded = []

        try:
            photo_rows = get_photos_by_person(name)
        except Exception as exc:
            logger.warning("[batch:%s] Photo lookup failed (continuing without): %s", batch_id, exc)
            photo_rows = []

        if downloaded:
            photos = [p["file_path"] for p in downloaded if p.get("file_path")]
            photo_sources = {p["file_path"]: p["source_url"] for p in downloaded if p.get("source_url")}
        elif photo_rows:
            photos = [p["file_path"] for p in photo_rows]
            photo_sources = {p["file_path"]: p["source_url"] for p in photo_rows if p.get("source_url")}
        else:
            photos = person.get("images", []) if person else []
            photo_sources = {}

        # ── 4. Cache result ─────────────────────────────────────────────────
        try:
            set_biography(name, text, photos, birth=birth, death=death, photo_sources=photo_sources)
        except Exception as exc:
            logger.warning("[batch:%s] Cache write failed for '%s'; returning uncached result: %s", batch_id, name, exc)

        result = {
            "status": "done",
            "name": name,
            "text": text,
            "birth": birth,
            "death": death,
            "photos": photos,
            "photo_sources": photo_sources,
            "used_fallback": used_fallback,
            "warnings": warnings,
            "finished_at": time.time(),
        }
        update_job(
            batch_id,
            name,
            status="done",
            text=text,
            birth=birth,
            death=death,
            photos=photos,
            photo_sources=photo_sources,
            used_fallback=used_fallback,
            warnings=warnings,
            finished_at=result["finished_at"],
            error=None,
        )
        logger.info("[batch:%s] Done '%s'", batch_id, name)
        return result

    except Exception as exc:
        # Catch-all — worker must NEVER crash
        logger.exception("[batch:%s] Unexpected error for '%s'", batch_id, name)
        return _fail(batch_id, name, f"Unexpected error: {exc}")


def _fail(batch_id: str, name: str, reason: str) -> dict:
    logger.error("[batch:%s] Failed '%s': %s", batch_id, name, reason)
    update_job(batch_id, name, status="failed", error=reason, finished_at=time.time())
    return {"status": "failed", "name": name, "error": reason}
