import logging
import time

from app.db.sqlalchemy_db import ExportRecord, SessionLocal

logger = logging.getLogger(__name__)


def add_export_record(
    *,
    name: str,
    export_kind: str,
    status: str,
    source_photo_path: str | None = None,
    source_photo_url: str | None = None,
    image_origin: str | None = None,
    attachment_id: int | None = None,
    attachment_url: str | None = None,
    thread_id: int | None = None,
    thread_url: str | None = None,
    error: str | None = None,
) -> int | None:
    try:
        with SessionLocal() as db:
            record = ExportRecord(
                name=name,
                export_kind=export_kind,
                status=status,
                source_photo_path=source_photo_path,
                source_photo_url=source_photo_url,
                image_origin=image_origin,
                attachment_id=attachment_id,
                attachment_url=attachment_url,
                thread_id=thread_id,
                thread_url=thread_url,
                error=error,
                created_at=time.time(),
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return record.id
    except Exception:
        logger.exception("Failed to persist export record", extra={"profile_name": name, "export_status": status})
        return None
