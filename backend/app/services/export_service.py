import logging
from typing import Iterable

from app.db.export_repo import add_export_record
from app.services.vkorny_export import send_profile

logger = logging.getLogger(__name__)


def export_profile_to_vkorni(
    *,
    name: str,
    text: str,
    photos: Iterable[str],
    birth: str | None = None,
    death: str | None = None,
    photo_source_url: str | None = None,
    export_kind: str = "manual",
) -> dict:
    photo_list = list(photos) if photos else []

    try:
        result = send_profile(
            name=name,
            text=text,
            photos=photo_list,
            birth=birth,
            death=death,
            photo_source_url=photo_source_url,
        )
    except Exception as exc:
        logger.exception("Export wrapper crashed", extra={"profile_name": name, "export_kind": export_kind})
        result = {
            "status": "ERROR",
            "error": str(exc),
            "source_photo_path": photo_list[0] if photo_list else None,
            "source_photo_url": photo_source_url,
            "image_origin": "unknown",
        }

    add_export_record(
        name=name,
        export_kind=export_kind,
        status=result.get("status", "ERROR"),
        source_photo_path=result.get("source_photo_path") or (photo_list[0] if photo_list else None),
        source_photo_url=result.get("source_photo_url", photo_source_url),
        image_origin=result.get("image_origin"),
        attachment_id=result.get("attachment_id"),
        attachment_url=result.get("attachment_url"),
        thread_id=result.get("thread_id"),
        thread_url=result.get("url"),
        error=result.get("error"),
    )
    return result
