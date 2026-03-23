"""
export_worker.py
----------------
RQ task: export a list of profiles to vkorni.com one by one with 2s pauses.
Never crashes — all errors are caught and stored in Redis.
"""
import logging
import time

from app.services.bulk_export_service import update_job, get_bulk_export
from app.services.cache_service import get_biography
from app.services.vkorny_export import send_profile

logger = logging.getLogger(__name__)


def run_bulk_export(export_id: str) -> None:
    state = get_bulk_export(export_id)
    if not state:
        logger.error("bulk export %s not found in Redis", export_id)
        return

    names = [r["name"] for r in state["results"]]

    for i, name in enumerate(names):
        update_job(export_id, name, "running")
        try:
            cached = get_biography(name)
            if not cached:
                update_job(export_id, name, "failed", error="Профиль не найден в кэше")
                continue

            result = send_profile(
                name=cached["name"],
                text=cached["text"],
                photos=cached.get("photos", []),
                birth=cached.get("birth"),
                death=cached.get("death"),
                photo_source_url=None,
            )

            if result.get("status") == "OK":
                update_job(export_id, name, "done", url=result.get("url"))
                logger.info("bulk export [%d/%d] OK: %s → %s", i + 1, len(names), name, result.get("url"))
            else:
                update_job(export_id, name, "failed", error=result.get("error", "Неизвестная ошибка"))
                logger.warning("bulk export [%d/%d] FAILED: %s — %s", i + 1, len(names), name, result.get("error"))

        except Exception as exc:
            logger.exception("bulk export crashed for %s", name)
            update_job(export_id, name, "failed", error=str(exc))

        # 2s pause between profiles — avoid hammering the API
        if i < len(names) - 1:
            time.sleep(2)
