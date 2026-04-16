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

from app.services.batch_service import update_job
from app.services.wiki_service import fetch_person_from_wikipedia, fetch_person_images
from app.services.deepseek_service import generate_text, DeepSeekBillingError, DeepSeekServiceError
from app.services.chroma_service import get_style_context
from app.services.cache_service import set_biography
from app.services.uniqueness_service import is_unique_enough
from app.db.photos_repo import get_photos_by_person

logger = logging.getLogger(__name__)

MAX_GENERATION_ATTEMPTS = 3
MIN_WORD_COUNT = 400


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
        # ── 1. Fetch Wikipedia ──────────────────────────────────────────────
        try:
            person = _fetch_wiki(name)
        except Exception as exc:
            return _fail(batch_id, name, f"Wikipedia fetch failed: {exc}")

        if not person:
            return _fail(batch_id, name, "Person not found on Wikipedia")

        # ── 2. Generate unique text ─────────────────────────────────────────
        wiki_source = person.get("summary_text", "")
        context = (
            f"Имя: {person.get('name')}\n"
            f"Годы жизни: {person.get('birth')}–{person.get('death')}\n"
            f"Краткое описание: {wiki_source}\n"
        )
        style = get_style_context(style_name)

        text = ""
        tried_angles: list[str] = []

        for attempt in range(MAX_GENERATION_ATTEMPTS):
            try:
                candidate, angle_used = generate_text(
                    context, style, exclude_angle_ids=tried_angles
                )
                tried_angles.append(angle_used)
            except DeepSeekBillingError as exc:
                return _fail(batch_id, name, str(exc))
            except DeepSeekServiceError as exc:
                logger.warning("[batch:%s] DeepSeek unavailable on attempt %d: %s", batch_id, attempt + 1, exc)
                time.sleep(5 * (attempt + 1))
                continue
            except Exception as exc:
                logger.warning("[batch:%s] DeepSeek attempt %d failed: %s", batch_id, attempt + 1, exc)
                time.sleep(5 * (attempt + 1))
                continue

            words = len(candidate.split()) if candidate else 0
            if words < MIN_WORD_COUNT:
                logger.warning("[batch:%s] Text too short (%d words), retrying", batch_id, words)
                continue

            if is_unique_enough(candidate, wiki_source):
                text = candidate
                logger.info("[batch:%s] Accepted text (angle=%s)", batch_id, angle_used)
                break

            logger.warning("[batch:%s] Text too similar to Wikipedia, retrying", batch_id)

        if not text:
            # Last resort: use last candidate even if similarity high
            text = candidate if "candidate" in dir() and candidate else ""

        if not text or len(text.split()) < MIN_WORD_COUNT:
            return _fail(batch_id, name, "Failed to generate unique text after all attempts")

        # ── 3. Fetch images ─────────────────────────────────────────────────
        try:
            downloaded = _fetch_images(name)
        except Exception as exc:
            logger.warning("[batch:%s] Image fetch failed (continuing without): %s", batch_id, exc)
            downloaded = []

        photo_rows = get_photos_by_person(name)
        if downloaded:
            photos = [p["file_path"] for p in downloaded if p.get("file_path")]
            photo_sources = {p["file_path"]: p["source_url"] for p in downloaded if p.get("source_url")}
        elif photo_rows:
            photos = [p["file_path"] for p in photo_rows]
            photo_sources = {p["file_path"]: p["source_url"] for p in photo_rows if p.get("source_url")}
        else:
            photos = person.get("images", [])
            photo_sources = {}

        # ── 4. Cache result ─────────────────────────────────────────────────
        birth = person.get("birth")
        death = person.get("death")
        set_biography(name, text, photos, birth=birth, death=death, photo_sources=photo_sources)

        result = {
            "status": "done",
            "name": name,
            "birth": birth,
            "death": death,
            "photos": photos,
            "photo_sources": photo_sources,
            "finished_at": time.time(),
        }
        update_job(batch_id, name, status="done", birth=birth, death=death,
                   photos=photos, photo_sources=photo_sources, finished_at=result["finished_at"])
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
