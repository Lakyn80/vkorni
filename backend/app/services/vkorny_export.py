import logging
import os
import re
import tempfile
from typing import Iterable
from urllib.parse import unquote, urlencode, urljoin, urlparse

import requests

from app.services.cache_service import get_biography

logger = logging.getLogger(__name__)

VKORNI_BASE_URL = os.getenv("VKORNI_BASE_URL", "https://vkorni.com/api")
VKORNI_API_KEY = os.getenv("VKORNI_API_KEY", "")
VKORNI_NODE_ID = os.getenv("VKORNI_NODE_ID", "")
VKORNI_USER_ID = os.getenv("VKORNI_USER_ID", "1")


def _headers() -> dict:
    return {
        "XF-Api-Key": VKORNI_API_KEY,
        "XF-Api-User": VKORNI_USER_ID,
    }


def _vkorni_origin() -> str:
    parsed = urlparse(VKORNI_BASE_URL)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return "https://vkorni.com"


def _is_vkorni_url(url: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    origin = urlparse(_vkorni_origin())
    return parsed.netloc == origin.netloc


def _absolute_attachment_url(url: str) -> str:
    if not url:
        return ""
    return urljoin(f"{_vkorni_origin()}/", url)


def _is_remote_image_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _upload_attachment(file_path: str) -> dict | None:
    base = VKORNI_BASE_URL.rstrip("/")
    try:
        r = requests.post(
            f"{base}/attachments/new-key/",
            data={"type": "post", "context[node_id]": VKORNI_NODE_ID},
            headers=_headers(),
            timeout=15,
        )
        if not r.ok:
            logger.error("XenForo new-key failed: %s %s", r.status_code, r.text[:200])
            return None

        key = r.json().get("key")
        if not key:
            logger.error("XenForo new-key response missing key")
            return None

        filename = os.path.basename(file_path)
        mime = "image/jpeg" if file_path.lower().endswith((".jpg", ".jpeg")) else "image/webp"
        with open(file_path, "rb") as f:
            r2 = requests.post(
                f"{base}/attachments/",
                params={"key": key},
                files={"attachment": (filename, f, mime)},
                headers=_headers(),
                timeout=30,
            )

        if not r2.ok:
            logger.error("XenForo attachment upload failed: %s %s", r2.status_code, r2.text[:200])
            return None

        att = r2.json().get("attachment", {})
        attachment_id = att.get("attachment_id")
        if not attachment_id:
            logger.error("XenForo attachment response missing attachment_id")
            return None

        raw_view_url = att.get("direct_url") or att.get("thumbnail_url") or ""
        view_url = _absolute_attachment_url(raw_view_url)
        if view_url and not _is_vkorni_url(view_url):
            logger.error("Unexpected attachment host returned by XenForo: %s", view_url)
            view_url = ""

        logger.info("Uploaded attachment id=%s url=%s for %s", attachment_id, view_url, filename)
        return {"attachment_id": attachment_id, "view_url": view_url}
    except Exception:
        logger.exception("XenForo attachment upload error")
        return None


def _build_message(
    text: str,
    attachment_ids: list[int],
    birth: str | None = None,
    death: str | None = None,
    attachment_url: str | None = None,
) -> str:
    parts = []

    if attachment_url:
        parts.append(f"[CENTER][IMG]{attachment_url}[/IMG][/CENTER]")
    else:
        for attachment_id in attachment_ids[:1]:
            parts.append(f"[CENTER][ATTACH=full]{attachment_id}[/ATTACH][/CENTER]")

    if parts:
        parts.append("")

    if birth or death:
        b = birth or "??"
        d = death or "наши дни"
        parts.append(f"[B]{b} - {d}[/B]")
        parts.append("")

    for paragraph in text.strip().split("\n\n"):
        paragraph = paragraph.strip()
        if paragraph:
            parts.append(paragraph)
            parts.append("")

    return "\n".join(parts).strip()


def _local_path(rel_url: str) -> str:
    decoded = unquote(rel_url)
    sub = decoded.lstrip("/")
    return os.path.join("/app", sub)


def _extract_birth_from_text(text: str) -> str | None:
    if not text:
        return None
    m = re.search(r"родил[сь][яь][^.]{0,40}?(1[89]\d{2}|20[01]\d)", text)
    if m:
        return m.group(1)
    m = re.search(r"\b(1[89]\d{2}|20[01]\d)\b", text)
    return m.group(1) if m else None


def _download_source_photo(url: str) -> str | None:
    try:
        parsed = urlparse(url)
        suffix = os.path.splitext(unquote(os.path.basename(parsed.path)))[1] or ".img"
        fd, path = tempfile.mkstemp(prefix="vkorni-export-", suffix=suffix)
        os.close(fd)

        response = requests.get(url, timeout=20)
        response.raise_for_status()
        with open(path, "wb") as f:
            f.write(response.content)
        return path
    except Exception:
        logger.exception("Source photo download failed", extra={"url": url})
        return None


def _prepare_export_photo(
    photos: Iterable[str],
    birth: str | None,
    death: str | None,
    photo_source_url: str | None,
) -> dict | None:
    photo_list = list(photos) if photos else []
    cleanup_paths: list[str] = []
    source_local_path: str | None = None
    source_photo_path: str | None = None
    image_origin: str | None = None
    resolved_source_url = photo_source_url

    for photo_url in photo_list[:1]:
        if _is_remote_image_url(photo_url):
            if not resolved_source_url:
                resolved_source_url = photo_url
            continue
        local = _local_path(photo_url)
        if os.path.exists(local):
            source_local_path = local
            source_photo_path = photo_url
            image_origin = "accepted_local" if "accepted_images" in photo_url else "photo_local"
            break
        logger.warning("Photo file not found: %s (resolved: %s)", photo_url, local)

    if source_local_path is None and resolved_source_url:
        downloaded = _download_source_photo(resolved_source_url)
        if downloaded:
            cleanup_paths.append(downloaded)
            source_local_path = downloaded
            image_origin = "photo_source_download"

    if source_local_path is None:
        return None

    export_path = source_local_path
    if image_origin != "accepted_local":
        try:
            from app.services.frame_service import compose_portrait

            export_path = compose_portrait(source_local_path, birth=birth, death=death)
            if image_origin == "photo_local":
                image_origin = "framed_local"
            elif image_origin == "photo_source_download":
                image_origin = "framed_source_download"
        except Exception:
            logger.exception("Frame composition failed - using original photo")
            if image_origin == "photo_local":
                image_origin = "raw_local"
            elif image_origin == "photo_source_download":
                image_origin = "raw_source_download"

    return {
        "export_path": export_path,
        "cleanup_paths": cleanup_paths,
        "source_photo_path": source_photo_path,
        "source_photo_url": resolved_source_url,
        "image_origin": image_origin,
    }


def _create_thread(name: str, message: str, attachment_ids: list[int]) -> dict:
    form: dict[str, str] = {
        "node_id": str(int(VKORNI_NODE_ID)),
        "title": name,
        "message": message,
    }
    for i, attachment_id in enumerate(attachment_ids):
        form[f"attachment_ids[{i}]"] = str(attachment_id)

    body_bytes = urlencode(form, encoding="utf-8").encode("utf-8")
    response = requests.post(
        f"{VKORNI_BASE_URL.rstrip('/')}/threads/",
        data=body_bytes,
        headers={**_headers(), "Content-Type": "application/x-www-form-urlencoded; charset=utf-8"},
        timeout=30,
    )
    if not response.ok:
        return {
            "status": "ERROR",
            "code": response.status_code,
            "error": response.text[:500],
        }

    body = response.json()
    thread_id = body.get("thread", {}).get("thread_id")
    thread_url = f"{_vkorni_origin()}/threads/{thread_id}/" if thread_id else None
    return {
        "status": "OK",
        "thread_id": thread_id,
        "url": thread_url,
    }


def _error_result(error: str, **extra) -> dict:
    payload = {"status": "ERROR", "error": error}
    payload.update(extra)
    return payload


def _resolve_cached_source_url(name: str, photo_list: list[str], explicit_source_url: str | None) -> str | None:
    if explicit_source_url or not photo_list:
        return explicit_source_url
    try:
        cached = get_biography(name)
        if not cached:
            return None
        photo_sources = cached.get("photo_sources") or {}
        return photo_sources.get(photo_list[0])
    except Exception:
        logger.exception("Failed to resolve cached source URL", extra={"profile_name": name})
        return None


def send_profile(
    name: str,
    text: str,
    photos: Iterable[str],
    birth: str | None = None,
    death: str | None = None,
    photo_source_url: str | None = None,
) -> dict:
    photo_list = list(photos) if photos else []

    if not VKORNI_API_KEY:
        return _error_result("VKORNI_API_KEY is not set")
    if not VKORNI_NODE_ID:
        return _error_result("VKORNI_NODE_ID is not set")

    if not birth:
        birth = _extract_birth_from_text(text)

    resolved_photo_source_url = _resolve_cached_source_url(name, photo_list, photo_source_url)
    prepared = _prepare_export_photo(photo_list, birth, death, resolved_photo_source_url)
    if not prepared:
        return _error_result(
            "No exportable photo found for static XenForo upload",
            source_photo_path=(photo_list[0] if photo_list else None),
            source_photo_url=resolved_photo_source_url,
            image_origin="missing",
        )

    try:
        upload = _upload_attachment(prepared["export_path"])
        if not upload or not upload.get("attachment_id"):
            return _error_result(
                "XenForo attachment upload failed; thread was not created",
                source_photo_path=prepared.get("source_photo_path"),
                source_photo_url=prepared.get("source_photo_url"),
                image_origin=prepared.get("image_origin"),
            )

        attachment_id = upload["attachment_id"]
        attachment_url = upload.get("view_url") or None
        message = _build_message(
            text,
            [attachment_id],
            birth=birth,
            death=death,
            attachment_url=attachment_url,
        )

        result = _create_thread(name, message, [attachment_id])
        if result.get("status") != "OK":
            result.update(
                {
                    "attachment_id": attachment_id,
                    "attachment_url": attachment_url,
                    "source_photo_path": prepared.get("source_photo_path"),
                    "source_photo_url": prepared.get("source_photo_url"),
                    "image_origin": prepared.get("image_origin"),
                }
            )
            return result

        result.update(
            {
                "attachment_id": attachment_id,
                "attachment_url": attachment_url,
                "source_photo_path": prepared.get("source_photo_path"),
                "source_photo_url": prepared.get("source_photo_url"),
                "image_origin": prepared.get("image_origin"),
            }
        )
        return result
    except Exception as exc:
        logger.exception("VKorni export failed")
        return _error_result(
            str(exc),
            source_photo_path=prepared.get("source_photo_path"),
            source_photo_url=prepared.get("source_photo_url"),
            image_origin=prepared.get("image_origin"),
        )
    finally:
        for path in prepared.get("cleanup_paths", []):
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except OSError:
                logger.warning("Failed to remove temporary export file: %s", path)
