"""
image_pipeline.py
-----------------
Orchestrates the full image-processing pipeline for a single person:

  fetch → validate (Vision API) → compose (frame + dates) → store

This module is intentionally stateless and has no knowledge of the job queue.
It is called directly by the RQ worker task.
"""
import logging
import os
import shutil
from typing import Optional

from app.config import settings
from app.services.vision_service import validate_image
from app.services.frame_service import compose_portrait
from app.services.wiki_service import fetch_person_images, _get_wikidata_id, _get_birth_death_from_wikidata
from app.db.photos_repo import update_photo_status

logger = logging.getLogger(__name__)


def _chunks(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def _resolve_dates(name: str) -> tuple[Optional[str], Optional[str]]:
    """Fetch birth/death years from Wikidata for the given person name."""
    try:
        qid = _get_wikidata_id(name)
        if not qid:
            return None, None
        dates = _get_birth_death_from_wikidata(qid)
        return dates.get("birth"), dates.get("death")
    except Exception:
        logger.exception("Failed to resolve Wikidata dates for %s", name)
        return None, None


def _move_to_rejected(source_path: str) -> str:
    os.makedirs(settings.rejected_dir, exist_ok=True)
    file_name = os.path.basename(source_path)
    dest = os.path.join(settings.rejected_dir, file_name)
    try:
        shutil.copy2(source_path, dest)
    except Exception:
        logger.exception("Failed to copy rejected image to rejected_dir")
    return dest


def run_pipeline(name: str, profession: Optional[str] = None) -> dict:
    """
    Run the full image pipeline for a person.

    Returns a result dict:
        {
            "name": str,
            "accepted": [str, ...],   # paths to composed portraits
            "rejected": [str, ...],   # paths to rejected originals
            "errors": [str, ...],
        }
    """
    result: dict = {"name": name, "accepted": [], "rejected": [], "errors": []}

    birth, death = _resolve_dates(name)

    try:
        images = fetch_person_images(name)
    except Exception:
        logger.exception("fetch_person_images failed for %s", name)
        result["errors"].append("Failed to fetch images from Wikipedia")
        return result

    if not images:
        logger.info("No images found for %s", name)
        return result

    for batch in _chunks(images, settings.batch_size):
        for img in batch:
            local_path = img.get("file_path", "")
            # Convert relative web path to absolute filesystem path
            if local_path.startswith("/static/"):
                abs_path = os.path.join(
                    os.path.dirname(settings.photos_dir),
                    local_path.lstrip("/"),
                )
            else:
                abs_path = local_path

            if not os.path.exists(abs_path):
                logger.warning("Image file not found on disk: %s", abs_path)
                result["errors"].append(f"File not found: {abs_path}")
                continue

            try:
                valid, reason = validate_image(abs_path)
                if not valid:
                    logger.info("Image rejected (%s): %s", reason, abs_path)
                    rejected_path = _move_to_rejected(abs_path)
                    result["rejected"].append(rejected_path)
                    update_photo_status(abs_path, "rejected")
                    continue

                composed_path = compose_portrait(
                    source_path=abs_path,
                    birth=birth,
                    death=death,
                    profession=profession,
                    person_name=name,
                )
                result["accepted"].append(composed_path)
                update_photo_status(abs_path, "accepted")

            except Exception as exc:
                logger.exception("Pipeline error on image %s: %s", abs_path, exc)
                result["errors"].append(f"Processing failed for {os.path.basename(abs_path)}: {exc}")

    logger.info(
        "Pipeline done for %s — accepted: %d, rejected: %d, errors: %d",
        name,
        len(result["accepted"]),
        len(result["rejected"]),
        len(result["errors"]),
    )
    return result
