import logging
import os
import shutil
from typing import Iterable
from uuid import uuid4

from app.config import settings
from app.db.export_repo import add_export_record
from app.db.stored_profiles_repo import store_exported_profile_snapshot
from app.services.vkorny_export import send_profile

logger = logging.getLogger(__name__)

FRAMED_IMAGE_ORIGINS = {"accepted_local", "exported_local", "framed_local", "framed_source_download"}


def _dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _build_export_candidates(
    *,
    photos: list[str],
    selected_photo_url: str | None,
    preferred_export_photo_url: str | None,
) -> list[str]:
    candidates: list[str] = []
    if preferred_export_photo_url:
        candidates.append(preferred_export_photo_url)
    if selected_photo_url:
        candidates.append(selected_photo_url)
    candidates.extend(photos)
    return _dedupe_preserve_order(candidates)


def _build_snapshot_photos(
    *,
    photos: list[str],
    photo_sources: dict[str, str] | None,
    selected_photo_url: str | None,
) -> list[dict]:
    sources = photo_sources or {}
    ordered_photos = _dedupe_preserve_order(([selected_photo_url] if selected_photo_url else []) + photos)
    snapshot_photos: list[dict] = []
    for index, photo_url in enumerate(ordered_photos):
        snapshot_photos.append(
            {
                "photo_url": photo_url,
                "source_url": sources.get(photo_url),
                "sort_order": index,
                "is_selected": photo_url == selected_photo_url,
            }
        )
    return snapshot_photos


def _archive_framed_image(export_path: str | None, image_origin: str | None) -> str | None:
    if not export_path or not image_origin:
        return None
    if image_origin not in FRAMED_IMAGE_ORIGINS:
        return None
    if not os.path.exists(export_path):
        logger.warning("Framed image missing, skipping archive: %s", export_path)
        return None

    normalized_exported_dir = os.path.normpath(settings.exported_profiles_dir)
    normalized_export_path = os.path.normpath(export_path)
    if normalized_export_path.startswith(normalized_exported_dir):
        return export_path

    archive_dir = os.path.join(settings.exported_profiles_dir, uuid4().hex)
    archive_path = os.path.join(archive_dir, "portrait.jpg")
    try:
        os.makedirs(archive_dir, exist_ok=True)
        shutil.copy2(export_path, archive_path)
        return archive_path
    except Exception:
        logger.exception("Failed to archive framed image", extra={"export_path": export_path, "archive_path": archive_path})
        return None


def export_profile_to_vkorni(
    *,
    name: str,
    text: str,
    photos: Iterable[str],
    birth: str | None = None,
    death: str | None = None,
    photo_source_url: str | None = None,
    export_kind: str = "manual",
    selected_photo_url: str | None = None,
    preferred_export_photo_url: str | None = None,
    preferred_source_photo_url: str | None = None,
    photo_sources: dict[str, str] | None = None,
    frame_id: int | None = None,
) -> dict:
    photo_list = list(photos) if photos else []
    export_candidates = _build_export_candidates(
        photos=photo_list,
        selected_photo_url=selected_photo_url,
        preferred_export_photo_url=preferred_export_photo_url,
    )
    preferred_source = preferred_source_photo_url or selected_photo_url

    try:
        result = send_profile(
            name=name,
            text=text,
            photos=export_candidates,
            birth=birth,
            death=death,
            photo_source_url=photo_source_url,
            frame_id=frame_id,
            preferred_source_photo_url=preferred_source,
        )
    except Exception as exc:
        logger.exception("Export wrapper crashed", extra={"profile_name": name, "export_kind": export_kind})
        result = {
            "status": "ERROR",
            "error": str(exc),
            "source_photo_path": export_candidates[0] if export_candidates else None,
            "source_photo_url": photo_source_url,
            "image_origin": "unknown",
            "selected_photo_url": selected_photo_url,
            "frame_id": frame_id,
        }

    add_export_record(
        name=name,
        export_kind=export_kind,
        status=result.get("status", "ERROR"),
        source_photo_path=result.get("source_photo_path") or (export_candidates[0] if export_candidates else None),
        source_photo_url=result.get("source_photo_url", photo_source_url),
        image_origin=result.get("image_origin"),
        attachment_id=result.get("attachment_id"),
        attachment_url=result.get("attachment_url"),
        thread_id=result.get("thread_id"),
        thread_url=result.get("url"),
        error=result.get("error"),
    )

    if result.get("status") != "OK":
        return result

    exported_selected_photo_url = result.get("selected_photo_url") or selected_photo_url
    archived_framed_image_path = result.get("stable_image_path") or _archive_framed_image(
        result.get("export_path"),
        result.get("image_origin"),
    )
    snapshot_photos = _build_snapshot_photos(
        photos=photo_list,
        photo_sources=photo_sources,
        selected_photo_url=exported_selected_photo_url,
    )

    store_exported_profile_snapshot(
        name=name,
        text=text,
        birth=birth,
        death=death,
        selected_photo_url=exported_selected_photo_url,
        selected_source_url=result.get("source_photo_url") or photo_source_url,
        framed_image_path=archived_framed_image_path,
        frame_id=result.get("frame_id"),
        attachment_id=result.get("attachment_id"),
        attachment_url=result.get("attachment_url"),
        thread_id=result.get("thread_id"),
        thread_url=result.get("url"),
        status=result.get("status", "ERROR"),
        export_kind=export_kind,
        error=result.get("error"),
        photos=snapshot_photos,
    )

    result["framed_image_path"] = archived_framed_image_path
    return result
