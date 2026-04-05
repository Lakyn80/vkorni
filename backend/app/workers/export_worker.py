"""
export_worker.py
----------------
RQ tasks for resilient bulk export to vkorni.com.
Each profile is exported in an isolated job with persisted attempts.
"""
import logging
import time

from app.config import settings
from app.services.bulk_export_service import get_bulk_export, get_bulk_export_job, update_job
from app.services.cache_service import get_biography
from app.services.export_service import export_profile_to_vkorni
from app.workers.queue_backend import enqueue_job

logger = logging.getLogger(__name__)


def _schedule_watchdog(export_id: str, delay_seconds: int | None = None) -> None:
    enqueue_job(
        run_bulk_export_watchdog,
        export_id,
        queue="bios",
        job_timeout=max(settings.bulk_export_item_timeout, 300),
        delay_seconds=delay_seconds or settings.bulk_export_watchdog_interval_seconds,
    )


def _schedule_export_attempt(
    export_id: str,
    name: str,
    *,
    current_state: dict | None = None,
    delay_seconds: int = 0,
) -> None:
    state = current_state or get_bulk_export_job(export_id, name)
    if not state or state.get("status") == "done":
        return

    next_status = "retrying" if int(state.get("attempts", 0) or 0) > 0 else "queued"
    update_job(export_id, name, status=next_status, updated_at=time.time())
    enqueue_job(
        run_bulk_export_item,
        export_id,
        name,
        queue="bios",
        job_timeout=settings.bulk_export_item_timeout,
        delay_seconds=delay_seconds,
    )


def _schedule_retry_or_fail(export_id: str, name: str, attempts: int, error: str) -> None:
    if attempts < settings.bulk_export_max_attempts:
        delay_seconds = settings.bulk_export_retry_delay_seconds * attempts
        state = update_job(export_id, name, status="retrying", error=error, attempts=attempts, updated_at=time.time())
        _schedule_export_attempt(export_id, name, current_state=state, delay_seconds=delay_seconds)
        logger.warning(
            "bulk export retry scheduled for %s (%d/%d): %s",
            name,
            attempts,
            settings.bulk_export_max_attempts,
            error,
        )
        return

    update_job(export_id, name, status="failed", error=error, attempts=attempts, updated_at=time.time())
    logger.error("bulk export permanently failed for %s after %d attempts: %s", name, attempts, error)


def schedule_bulk_export(export_id: str) -> None:
    state = get_bulk_export(export_id)
    if not state:
        logger.error("bulk export %s not found in Redis", export_id)
        return

    for result in state["results"]:
        if result["status"] in {"done", "failed", "queued", "running", "retrying"}:
            continue
        _schedule_export_attempt(export_id, result["name"], current_state=result)

    _schedule_watchdog(export_id)


def run_bulk_export_item(export_id: str, name: str) -> None:
    state = get_bulk_export_job(export_id, name)
    if not state or state.get("status") == "done":
        return

    attempts = int(state.get("attempts", 0) or 0) + 1
    update_job(export_id, name, status="running", error=None, attempts=attempts, updated_at=time.time())

    try:
        cached = get_biography(name)
        if not cached:
            update_job(export_id, name, status="failed", error="Профиль не найден в кэше", attempts=attempts, updated_at=time.time())
            return

        photos = cached.get("photos", [])
        photo_sources = cached.get("photo_sources") or {}
        photo_source_url = photo_sources.get(photos[0]) if photos else None

        result = export_profile_to_vkorni(
            name=cached["name"],
            text=cached["text"],
            photos=photos,
            birth=cached.get("birth"),
            death=cached.get("death"),
            photo_source_url=photo_source_url,
            export_kind="bulk",
            selected_photo_url=photos[0] if photos else None,
            photo_sources=photo_sources,
        )

        if result.get("status") == "OK":
            update_job(export_id, name, status="done", url=result.get("url"), error=None, attempts=attempts, updated_at=time.time())
            logger.info("bulk export OK: %s → %s", name, result.get("url"))
            return

        _schedule_retry_or_fail(export_id, name, attempts, result.get("error", "Неизвестная ошибка"))
    except Exception as exc:
        logger.exception("bulk export crashed for %s", name)
        _schedule_retry_or_fail(export_id, name, attempts, str(exc))


def run_bulk_export_watchdog(export_id: str) -> None:
    state = get_bulk_export(export_id)
    if not state:
        logger.error("bulk export %s not found in Redis", export_id)
        return

    now = time.time()
    incomplete = 0

    for result in state["results"]:
        status = result.get("status", "pending")
        if status in {"done", "failed"}:
            continue

        incomplete += 1
        if status == "pending":
            _schedule_export_attempt(export_id, result["name"], current_state=result)
            continue

        if status not in {"running", "retrying"}:
            continue

        updated_at = float(result.get("updated_at") or 0)
        if updated_at and (now - updated_at) < settings.bulk_export_stall_seconds:
            continue

        attempts = int(result.get("attempts", 0) or 0)
        if attempts >= settings.bulk_export_max_attempts:
            update_job(
                export_id,
                result["name"],
                status="failed",
                error=result.get("error") or "Bulk export stalled too many times",
                attempts=attempts,
                updated_at=now,
            )
            continue

        logger.warning("bulk export watchdog resumed stalled job for %s", result["name"])
        resumed_state = update_job(
            export_id,
            result["name"],
            status="retrying",
            error=result.get("error") or "Bulk export resumed after stalled job",
            attempts=attempts,
            updated_at=now,
        )
        _schedule_export_attempt(export_id, result["name"], current_state=resumed_state)

    if incomplete > 0:
        _schedule_watchdog(export_id)
