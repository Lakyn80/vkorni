import logging
import time

from sqlalchemy.orm import joinedload

from app.db.sqlalchemy_db import ProfileExportAttempt, SessionLocal, StoredProfile, StoredProfilePhoto

logger = logging.getLogger(__name__)


def _path_to_static_url(path: str | None) -> str | None:
    if not path:
        return None
    normalized = path.replace("\\", "/")
    prefix = "/app/static/"
    if not normalized.startswith(prefix):
        return None
    return f"/static/{normalized[len(prefix):]}"


def _serialize_photo(photo: StoredProfilePhoto) -> dict:
    return {
        "id": photo.id,
        "photo_url": photo.photo_url,
        "source_url": photo.source_url,
        "sort_order": photo.sort_order,
        "is_selected": bool(photo.is_selected),
    }


def _serialize_attempt(attempt: ProfileExportAttempt) -> dict:
    return {
        "id": attempt.id,
        "status": attempt.status,
        "export_kind": attempt.export_kind,
        "thread_id": attempt.thread_id,
        "thread_url": attempt.thread_url,
        "attachment_id": attempt.attachment_id,
        "attachment_url": attempt.attachment_url,
        "error": attempt.error,
        "created_at": attempt.created_at,
    }


def _serialize_profile(
    profile: StoredProfile,
    *,
    include_text: bool = False,
    include_photos: bool = False,
    include_attempts: bool = False,
) -> dict:
    payload = {
        "id": profile.id,
        "name": profile.name,
        "birth": profile.birth,
        "death": profile.death,
        "selected_photo_url": profile.selected_photo_url,
        "selected_source_url": profile.selected_source_url,
        "framed_image_path": profile.framed_image_path,
        "framed_image_url": _path_to_static_url(profile.framed_image_path),
        "frame_id": profile.frame_id,
        "attachment_id": profile.attachment_id,
        "attachment_url": profile.attachment_url,
        "last_thread_id": profile.last_thread_id,
        "last_thread_url": profile.last_thread_url,
        "status": profile.status,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
        "last_exported_at": profile.last_exported_at,
    }
    if include_text:
        payload["text"] = profile.text
    if include_photos:
        ordered_photos = sorted(profile.photos, key=lambda item: (item.sort_order, item.id))
        payload["photos"] = [_serialize_photo(photo) for photo in ordered_photos]
    if include_attempts:
        ordered_attempts = sorted(profile.export_attempts, key=lambda item: item.created_at, reverse=True)
        payload["export_attempts"] = [_serialize_attempt(attempt) for attempt in ordered_attempts]
    return payload


def store_exported_profile_snapshot(
    *,
    name: str,
    text: str,
    birth: str | None,
    death: str | None,
    selected_photo_url: str | None,
    selected_source_url: str | None,
    framed_image_path: str | None,
    frame_id: int | None,
    attachment_id: int | None,
    attachment_url: str | None,
    thread_id: int | None,
    thread_url: str | None,
    status: str,
    export_kind: str,
    error: str | None,
    photos: list[dict],
) -> int | None:
    now = time.time()
    try:
        with SessionLocal() as db:
            profile = db.query(StoredProfile).filter(StoredProfile.name == name).one_or_none()
            if profile is None:
                profile = StoredProfile(
                    name=name,
                    created_at=now,
                    updated_at=now,
                    last_exported_at=now,
                    status=status,
                )
                db.add(profile)
                db.flush()

            profile.text = text
            profile.birth = birth
            profile.death = death
            profile.selected_photo_url = selected_photo_url
            profile.selected_source_url = selected_source_url
            profile.framed_image_path = framed_image_path
            profile.frame_id = frame_id
            profile.attachment_id = attachment_id
            profile.attachment_url = attachment_url
            profile.last_thread_id = thread_id
            profile.last_thread_url = thread_url
            profile.status = status
            profile.updated_at = now
            profile.last_exported_at = now

            profile.photos.clear()
            db.flush()
            for item in photos:
                profile.photos.append(
                    StoredProfilePhoto(
                        photo_url=item["photo_url"],
                        source_url=item.get("source_url"),
                        sort_order=int(item.get("sort_order", 0)),
                        is_selected=1 if item.get("is_selected") else 0,
                    )
                )

            profile.export_attempts.append(
                ProfileExportAttempt(
                    status=status,
                    export_kind=export_kind,
                    thread_id=thread_id,
                    thread_url=thread_url,
                    attachment_id=attachment_id,
                    attachment_url=attachment_url,
                    error=error,
                    created_at=now,
                )
            )

            db.commit()
            db.refresh(profile)
            return profile.id
    except Exception:
        logger.exception("Failed to store exported profile snapshot", extra={"profile_name": name, "export_status": status})
        return None


def list_stored_profiles() -> list[dict]:
    try:
        with SessionLocal() as db:
            profiles = (
                db.query(StoredProfile)
                .order_by(StoredProfile.last_exported_at.desc(), StoredProfile.id.desc())
                .all()
            )
            return [_serialize_profile(profile) for profile in profiles]
    except Exception:
        logger.exception("Failed to list stored profiles")
        return []


def get_stored_profile(profile_id: int) -> dict | None:
    try:
        with SessionLocal() as db:
            profile = (
                db.query(StoredProfile)
                .options(joinedload(StoredProfile.photos), joinedload(StoredProfile.export_attempts))
                .filter(StoredProfile.id == profile_id)
                .one_or_none()
            )
            if profile is None:
                return None
            return _serialize_profile(profile, include_text=True, include_photos=True, include_attempts=True)
    except Exception:
        logger.exception("Failed to get stored profile", extra={"stored_profile_id": profile_id})
        return None


def add_stored_profile_attempt(
    *,
    stored_profile_id: int,
    status: str,
    export_kind: str,
    thread_id: int | None,
    thread_url: str | None,
    attachment_id: int | None,
    attachment_url: str | None,
    error: str | None,
) -> bool:
    now = time.time()
    try:
        with SessionLocal() as db:
            profile = db.query(StoredProfile).filter(StoredProfile.id == stored_profile_id).one_or_none()
            if profile is None:
                return False

            profile.status = status
            profile.updated_at = now
            if thread_id is not None:
                profile.last_thread_id = thread_id
            if thread_url is not None:
                profile.last_thread_url = thread_url
            if attachment_id is not None:
                profile.attachment_id = attachment_id
            if attachment_url is not None:
                profile.attachment_url = attachment_url
            if status == "OK":
                profile.last_exported_at = now

            profile.export_attempts.append(
                ProfileExportAttempt(
                    status=status,
                    export_kind=export_kind,
                    thread_id=thread_id,
                    thread_url=thread_url,
                    attachment_id=attachment_id,
                    attachment_url=attachment_url,
                    error=error,
                    created_at=now,
                )
            )
            db.commit()
            return True
    except Exception:
        logger.exception("Failed to add stored profile attempt", extra={"stored_profile_id": stored_profile_id, "export_status": status})
        return False
