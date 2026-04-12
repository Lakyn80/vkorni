import logging
import os
import re
import tempfile
import time
from io import BytesIO
from typing import Iterable
from urllib.parse import unquote, urlencode, urljoin, urlparse

import requests
from PIL import Image

from app.config import settings
from app.services.cache_service import get_biography

logger = logging.getLogger(__name__)

VKORNI_BASE_URL = os.getenv("VKORNI_BASE_URL", "https://vkorni.com/api")
VKORNI_API_KEY = os.getenv("VKORNI_API_KEY", "")
VKORNI_NODE_ID = os.getenv("VKORNI_NODE_ID", "")
VKORNI_USER_ID = os.getenv("VKORNI_USER_ID", "1")
HTTP_RETRY_ATTEMPTS = 3
HTTP_RETRY_DELAY_SECONDS = 2
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
STATIC_ATTACHMENT_PATH_PREFIX = "/data/attachments/"
XENFORO_ATTACHMENT_PATH_PREFIX = "/attachments/"
PRE_FRAMED_PREFIXES = ("/static/accepted_images/", "/static/exported_profiles/")
INTERNAL_EXPORT_SUBDIR = "xenforo_full"
EXPORT_GUARD_TAG = "[VKORNI_EXPORT_GUARD]"
PUBLISH_REPAIR_ATTEMPTS = 3


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


def _normalize_static_attachment_url(url: str) -> str:
    if not url:
        return ""

    absolute_url = _absolute_attachment_url(url)
    if not absolute_url:
        return ""
    if not _is_vkorni_url(absolute_url):
        logger.error("Unexpected attachment host returned by XenForo: %s", absolute_url)
        return ""

    parsed = urlparse(absolute_url)
    if not parsed.path.startswith(STATIC_ATTACHMENT_PATH_PREFIX):
        logger.warning("Ignoring non-static attachment URL returned by XenForo: %s", absolute_url)
        return ""
    if parsed.query or parsed.fragment:
        absolute_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return absolute_url


def _sanitize_filename_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value or "").strip("._")
    return cleaned or "image"


def _guess_extension(filename: str | None, image: Image.Image) -> str:
    _, ext = os.path.splitext(filename or "")
    ext = ext.lower()
    if ext in {".jpg", ".jpeg", ".png", ".webp"}:
        return ".jpg" if ext == ".jpeg" else ext

    image_format = (image.format or "").lower()
    if image_format in {"jpeg", "jpg"}:
        return ".jpg"
    if image_format in {"png", "webp"}:
        return f".{image_format}"
    return ".jpg"


def _build_internal_image_local_path(attachment_id: int, filename: str | None, image: Image.Image) -> str:
    safe_stem = _sanitize_filename_component(os.path.splitext(filename or "")[0])
    ext = _guess_extension(filename, image)
    target_dir = os.path.join(settings.exported_profiles_dir, INTERNAL_EXPORT_SUBDIR)
    os.makedirs(target_dir, exist_ok=True)
    return os.path.join(target_dir, f"{attachment_id}-{safe_stem}{ext}")


def _build_internal_image_public_url(local_path: str) -> str | None:
    if not settings.backend_public_url:
        logger.error("BACKEND_PUBLIC_URL is not set; cannot publish stable internal export image")
        return None

    normalized_root = os.path.normpath(settings.exported_profiles_dir)
    normalized_path = os.path.normpath(local_path)
    if not normalized_path.startswith(normalized_root):
        logger.error("Stable internal export image path is outside exported_profiles_dir: %s", local_path)
        return None

    rel = os.path.relpath(normalized_path, "/app").replace("\\", "/")
    return f"{settings.backend_public_url}/{rel}"


def _detect_full_size_source(attachment: dict) -> dict | None:
    direct_url = _absolute_attachment_url(attachment.get("direct_url") or "")
    if not direct_url:
        logger.error("XenForo attachment response missing direct_url for full-size export image")
        return None
    if not _is_vkorni_url(direct_url):
        logger.error("Unexpected XenForo direct_url host: %s", direct_url)
        return None

    parsed = urlparse(direct_url)
    if parsed.path.startswith(STATIC_ATTACHMENT_PATH_PREFIX):
        logger.error("Rejected static attachment path as full-size source: %s", direct_url)
        return None
    if not parsed.path.startswith(XENFORO_ATTACHMENT_PATH_PREFIX):
        logger.error("Rejected non-attachment direct_url for full-size source: %s", direct_url)
        return None

    width = int(attachment.get("width") or 0)
    height = int(attachment.get("height") or 0)
    if width <= 0 or height <= 0:
        logger.error("XenForo attachment response missing valid dimensions for attachment_id=%s", attachment.get("attachment_id"))
        return None

    logger.info(
        "Detected full-size XenForo source attachment_id=%s width=%s height=%s url=%s",
        attachment.get("attachment_id"),
        width,
        height,
        direct_url,
    )
    return {
        "download_url": direct_url,
        "filename": attachment.get("filename") or "",
        "width": width,
        "height": height,
    }


def _download_and_store_internal_image(*, attachment_id: int, source: dict) -> dict | None:
    download_url = source["download_url"]
    response = None
    for attempt in range(1, HTTP_RETRY_ATTEMPTS + 1):
        try:
            response = requests.get(download_url, timeout=30)
        except requests.RequestException:
            if attempt == HTTP_RETRY_ATTEMPTS:
                logger.exception("Failed to download XenForo full-size image attachment_id=%s", attachment_id)
                return None
            logger.warning(
                "Full-size XenForo download request failed for attachment_id=%s, retry %d/%d",
                attachment_id,
                attempt,
                HTTP_RETRY_ATTEMPTS,
            )
            _sleep_before_retry(attempt)
            continue

        if response.ok:
            break

        if attempt < HTTP_RETRY_ATTEMPTS and _should_retry_response(response.status_code):
            logger.warning(
                "Full-size XenForo download returned %s for attachment_id=%s, retry %d/%d",
                response.status_code,
                attachment_id,
                attempt,
                HTTP_RETRY_ATTEMPTS,
            )
            _sleep_before_retry(attempt)
            continue

        logger.error("Full-size XenForo download failed: %s attachment_id=%s", response.status_code, attachment_id)
        return None

    if not response or not response.ok:
        logger.error("Full-size XenForo download failed without usable response attachment_id=%s", attachment_id)
        return None

    content_type = (response.headers.get("content-type") or "").lower()
    if not content_type.startswith("image/"):
        logger.error("Rejected non-image full-size XenForo response attachment_id=%s content_type=%s", attachment_id, content_type)
        return None

    try:
        image = Image.open(BytesIO(response.content))
        image.load()
    except Exception:
        logger.exception("Failed to decode downloaded XenForo full-size image attachment_id=%s", attachment_id)
        return None

    expected_width = int(source["width"])
    expected_height = int(source["height"])
    if image.width < expected_width or image.height < expected_height:
        logger.error(
            "Rejected downloaded XenForo image attachment_id=%s because it looks like a thumbnail: expected=%sx%s actual=%sx%s",
            attachment_id,
            expected_width,
            expected_height,
            image.width,
            image.height,
        )
        return None

    logger.info(
        "Downloaded full-size XenForo image attachment_id=%s actual=%sx%s",
        attachment_id,
        image.width,
        image.height,
    )

    local_path = _build_internal_image_local_path(attachment_id, source.get("filename"), image)
    public_url = _build_internal_image_public_url(local_path)
    if not public_url:
        return None

    temp_path = f"{local_path}.tmp"
    try:
        with open(temp_path, "wb") as handle:
            handle.write(response.content)
        os.replace(temp_path, local_path)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                logger.warning("Failed to remove temporary internal export image: %s", temp_path)

    logger.info("Stored internal export image attachment_id=%s path=%s url=%s", attachment_id, local_path, public_url)
    return {"local_path": local_path, "public_url": public_url}


def _is_remote_image_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _is_pre_framed_local_url(url: str) -> bool:
    return any(url.startswith(prefix) for prefix in PRE_FRAMED_PREFIXES)


def _sleep_before_retry(attempt: int) -> None:
    time.sleep(HTTP_RETRY_DELAY_SECONDS * attempt)


def _should_retry_response(status_code: int) -> bool:
    return status_code in RETRYABLE_STATUS_CODES


def _format_xenforo_error(prefix: str, response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        snippet = response.text[:200].strip()
        return f"{prefix} ({response.status_code}): {snippet}" if snippet else f"{prefix} ({response.status_code})"

    errors = payload.get("errors") or []
    if errors:
        first = errors[0] or {}
        code = first.get("code")
        message = first.get("message")
        parts = [prefix, f"({response.status_code}"]
        if code:
            parts[-1] += f", {code}"
        parts[-1] += ")"
        base = " ".join(parts)
        return f"{base}: {message}" if message else base

    return f"{prefix} ({response.status_code})"


def _delete_thread(thread_id: int, reason: str) -> bool:
    base = VKORNI_BASE_URL.rstrip("/")
    delete_reason = f"Automatic cleanup: {reason}"[:250]

    for hard_delete in (True, False):
        response = None
        for attempt in range(1, HTTP_RETRY_ATTEMPTS + 1):
            try:
                response = requests.delete(
                    f"{base}/threads/{thread_id}/",
                    params={
                        "hard_delete": 1 if hard_delete else 0,
                        "reason": delete_reason,
                    },
                    headers=_headers(),
                    timeout=20,
                )
            except requests.RequestException:
                if attempt == HTTP_RETRY_ATTEMPTS:
                    logger.exception(
                        "%s cleanup delete request failed thread_id=%s hard_delete=%s",
                        EXPORT_GUARD_TAG,
                        thread_id,
                        hard_delete,
                    )
                    break
                logger.warning(
                    "%s cleanup delete request retry thread_id=%s hard_delete=%s attempt=%d/%d",
                    EXPORT_GUARD_TAG,
                    thread_id,
                    hard_delete,
                    attempt,
                    HTTP_RETRY_ATTEMPTS,
                )
                _sleep_before_retry(attempt)
                continue

            if response.ok:
                logger.error(
                    "%s deleted thread without verified attachment thread_id=%s hard_delete=%s reason=%s",
                    EXPORT_GUARD_TAG,
                    thread_id,
                    hard_delete,
                    reason,
                )
                return True

            if attempt < HTTP_RETRY_ATTEMPTS and _should_retry_response(response.status_code):
                logger.warning(
                    "%s cleanup delete retry thread_id=%s hard_delete=%s status=%s attempt=%d/%d",
                    EXPORT_GUARD_TAG,
                    thread_id,
                    hard_delete,
                    response.status_code,
                    attempt,
                    HTTP_RETRY_ATTEMPTS,
                )
                _sleep_before_retry(attempt)
                continue

            logger.error(
                "%s cleanup delete failed thread_id=%s hard_delete=%s status=%s body=%s",
                EXPORT_GUARD_TAG,
                thread_id,
                hard_delete,
                response.status_code if response is not None else "n/a",
                (response.text[:500] if response is not None else ""),
            )
            break

    return False


def _verify_thread_attachment(thread_id: int, expected_attachment_id: int) -> tuple[bool, str]:
    base = VKORNI_BASE_URL.rstrip("/")
    response = None

    for attempt in range(1, HTTP_RETRY_ATTEMPTS + 1):
        try:
            response = requests.get(
                f"{base}/threads/{thread_id}/",
                params={"with_first_post": 1},
                headers=_headers(),
                timeout=20,
            )
        except requests.RequestException as exc:
            if attempt == HTTP_RETRY_ATTEMPTS:
                logger.exception(
                    "%s verification request failed thread_id=%s attachment_id=%s",
                    EXPORT_GUARD_TAG,
                    thread_id,
                    expected_attachment_id,
                )
                return False, f"Thread verification request failed: {exc}"
            logger.warning(
                "%s verification request retry thread_id=%s attachment_id=%s attempt=%d/%d",
                EXPORT_GUARD_TAG,
                thread_id,
                expected_attachment_id,
                attempt,
                HTTP_RETRY_ATTEMPTS,
            )
            _sleep_before_retry(attempt)
            continue

        if response.ok:
            break

        if attempt < HTTP_RETRY_ATTEMPTS and _should_retry_response(response.status_code):
            logger.warning(
                "%s verification retry thread_id=%s attachment_id=%s status=%s attempt=%d/%d",
                EXPORT_GUARD_TAG,
                thread_id,
                expected_attachment_id,
                response.status_code,
                attempt,
                HTTP_RETRY_ATTEMPTS,
            )
            _sleep_before_retry(attempt)
            continue

        return False, _format_xenforo_error("Thread verification failed", response)

    if not response or not response.ok:
        return False, "Thread verification failed without usable response"

    try:
        payload = response.json()
    except ValueError:
        snippet = response.text[:200].strip()
        return False, f"Thread verification returned invalid JSON: {snippet or 'empty response'}"

    first_post = payload.get("first_post") or {}
    attach_count = int(first_post.get("attach_count") or 0)
    attachments = first_post.get("Attachments") or []
    attachment_ids = {int(item["attachment_id"]) for item in attachments if item.get("attachment_id")}

    if expected_attachment_id in attachment_ids:
        logger.info(
            "%s verified attachment via attachment list thread_id=%s attachment_id=%s attach_count=%s",
            EXPORT_GUARD_TAG,
            thread_id,
            expected_attachment_id,
            attach_count,
        )
        return True, ""

    if attach_count > 0 and not attachments:
        logger.info(
            "%s verified attachment via attach_count only thread_id=%s attachment_id=%s attach_count=%s",
            EXPORT_GUARD_TAG,
            thread_id,
            expected_attachment_id,
            attach_count,
        )
        return True, ""

    if attach_count <= 0:
        return False, f"Thread created without attachment in first post (thread_id={thread_id}, attachment_id={expected_attachment_id})"

    return False, (
        "Thread attachment mismatch after creation "
        f"(thread_id={thread_id}, expected_attachment_id={expected_attachment_id}, actual_attachment_ids={sorted(attachment_ids)})"
    )


def _upload_attachment(file_path: str) -> dict | None:
    base = VKORNI_BASE_URL.rstrip("/")
    try:
        key = None
        for attempt in range(1, HTTP_RETRY_ATTEMPTS + 1):
            try:
                r = requests.post(
                    f"{base}/attachments/new-key/",
                    data={"type": "post", "context[node_id]": VKORNI_NODE_ID},
                    headers=_headers(),
                    timeout=15,
                )
            except requests.RequestException:
                if attempt == HTTP_RETRY_ATTEMPTS:
                    raise
                logger.warning("XenForo new-key request failed for %s, retry %d/%d", file_path, attempt, HTTP_RETRY_ATTEMPTS)
                _sleep_before_retry(attempt)
                continue

            if r.ok:
                key = r.json().get("key")
                break

            if attempt < HTTP_RETRY_ATTEMPTS and _should_retry_response(r.status_code):
                logger.warning(
                    "XenForo new-key returned %s for %s, retry %d/%d",
                    r.status_code,
                    file_path,
                    attempt,
                    HTTP_RETRY_ATTEMPTS,
                )
                _sleep_before_retry(attempt)
                continue

            error_message = _format_xenforo_error("XenForo new-key failed", r)
            logger.error(error_message)
            return {"error": error_message}

        if not key:
            logger.error("XenForo new-key response missing key")
            return None

        filename = os.path.basename(file_path)
        mime = "image/jpeg" if file_path.lower().endswith((".jpg", ".jpeg")) else "image/webp"
        r2 = None
        for attempt in range(1, HTTP_RETRY_ATTEMPTS + 1):
            try:
                with open(file_path, "rb") as f:
                    r2 = requests.post(
                        f"{base}/attachments/",
                        params={"key": key},
                        files={"attachment": (filename, f, mime)},
                        headers=_headers(),
                        timeout=30,
                    )
            except requests.RequestException:
                if attempt == HTTP_RETRY_ATTEMPTS:
                    raise
                logger.warning("XenForo attachment upload request failed for %s, retry %d/%d", file_path, attempt, HTTP_RETRY_ATTEMPTS)
                _sleep_before_retry(attempt)
                continue

            if r2.ok:
                break

            if attempt < HTTP_RETRY_ATTEMPTS and _should_retry_response(r2.status_code):
                logger.warning(
                    "XenForo attachment upload returned %s for %s, retry %d/%d",
                    r2.status_code,
                    file_path,
                    attempt,
                    HTTP_RETRY_ATTEMPTS,
                )
                _sleep_before_retry(attempt)
                continue

            error_message = _format_xenforo_error("XenForo attachment upload failed", r2)
            logger.error(error_message)
            return {"error": error_message}

        if not r2 or not r2.ok:
            logger.error("XenForo attachment upload failed without usable response for %s", file_path)
            return None

        att = r2.json().get("attachment", {})
        attachment_id = att.get("attachment_id")
        if not attachment_id:
            logger.error("XenForo attachment response missing attachment_id")
            return None

        full_size_source = _detect_full_size_source(att)
        if not full_size_source:
            return None

        logger.info("Attachment upload success attachment_id=%s filename=%s", attachment_id, filename)
        return {
            "attachment_id": attachment_id,
            "attachment_key": key,
            "full_size_source": full_size_source,
        }
    except Exception:
        logger.exception("XenForo attachment upload error")
        return {"error": "XenForo attachment upload error"}


def _build_message(
    text: str,
    attachment_id: int | None = None,
    birth: str | None = None,
    death: str | None = None,
    attachment_url: str | None = None,
) -> str:
    if attachment_id is None and not attachment_url:
        raise ValueError("Attachment id or attachment URL is required for final post render")

    parts = []
    if attachment_id is not None:
        parts.append(f"[CENTER][ATTACH=full]{attachment_id}[/ATTACH][/CENTER]")
    else:
        parts.append(f"[CENTER][IMG]{attachment_url}[/IMG][/CENTER]")

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
    path = None
    try:
        parsed = urlparse(url)
        suffix = os.path.splitext(unquote(os.path.basename(parsed.path)))[1] or ".img"
        fd, path = tempfile.mkstemp(prefix="vkorni-export-", suffix=suffix)
        os.close(fd)

        response = None
        for attempt in range(1, HTTP_RETRY_ATTEMPTS + 1):
            try:
                response = requests.get(url, timeout=20)
            except requests.RequestException:
                if attempt == HTTP_RETRY_ATTEMPTS:
                    raise
                logger.warning("Source photo download request failed for %s, retry %d/%d", url, attempt, HTTP_RETRY_ATTEMPTS)
                _sleep_before_retry(attempt)
                continue

            if response.ok:
                break

            if attempt < HTTP_RETRY_ATTEMPTS and _should_retry_response(response.status_code):
                logger.warning(
                    "Source photo download returned %s for %s, retry %d/%d",
                    response.status_code,
                    url,
                    attempt,
                    HTTP_RETRY_ATTEMPTS,
                )
                _sleep_before_retry(attempt)
                continue
            break

        if not response or not response.ok:
            status = response.status_code if response is not None else "n/a"
            logger.error("Source photo download failed: %s %s", status, url)
            return None

        with open(path, "wb") as f:
            f.write(response.content)
        return path
    except Exception:
        logger.exception("Source photo download failed", extra={"url": url})
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                logger.warning("Failed to remove temporary downloaded photo: %s", path)
        return None


def _prepare_export_photo(
    photos: Iterable[str],
    birth: str | None,
    death: str | None,
    photo_source_url: str | None,
    frame_id: int | None = None,
) -> dict | None:
    from app.services.frame_service import compose_portrait, extract_frame_id, resolve_frame_id

    photo_list = list(photos) if photos else []
    cleanup_paths: list[str] = []
    source_local_path: str | None = None
    source_photo_path: str | None = None
    selected_photo_url: str | None = None
    image_origin: str | None = None
    resolved_source_url = photo_source_url
    accepted_local_candidates: list[tuple[str, str]] = []
    local_candidates: list[tuple[str, str]] = []
    remote_candidates: list[str] = []
    seen_remote_candidates: set[str] = set()

    def add_remote_candidate(url: str | None) -> None:
        if not url or url in seen_remote_candidates:
            return
        seen_remote_candidates.add(url)
        remote_candidates.append(url)

    add_remote_candidate(photo_source_url)

    for photo_url in photo_list:
        if _is_remote_image_url(photo_url):
            add_remote_candidate(photo_url)
            resolved_source_url = resolved_source_url or photo_url
            continue
        local = _local_path(photo_url)
        if os.path.exists(local):
            if _is_pre_framed_local_url(photo_url):
                accepted_local_candidates.append((local, photo_url))
            else:
                local_candidates.append((local, photo_url))
            continue
        logger.warning("Photo file not found: %s (resolved: %s)", photo_url, local)

    if accepted_local_candidates:
        source_local_path, source_photo_path = accepted_local_candidates[0]
        selected_photo_url = source_photo_path
        image_origin = "exported_local" if source_photo_path.startswith("/static/exported_profiles/") else "accepted_local"
    elif local_candidates:
        source_local_path, source_photo_path = local_candidates[0]
        selected_photo_url = source_photo_path
        image_origin = "photo_local"

    if source_local_path is None:
        for remote_url in remote_candidates:
            downloaded = _download_source_photo(remote_url)
            if not downloaded:
                continue
            cleanup_paths.append(downloaded)
            source_local_path = downloaded
            resolved_source_url = remote_url
            selected_photo_url = remote_url
            image_origin = "photo_source_download"
            break

    if source_local_path is None:
        return None

    export_path = source_local_path
    resolved_frame_id = frame_id
    if image_origin not in {"accepted_local", "exported_local"}:
        try:
            resolved_frame_id = resolve_frame_id(selected_photo_url or source_local_path, frame_id)
            export_path = compose_portrait(source_local_path, birth=birth, death=death, frame_id=resolved_frame_id)
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
    else:
        resolved_frame_id = frame_id if frame_id is not None else extract_frame_id(source_photo_path or source_local_path)

    return {
        "export_path": export_path,
        "cleanup_paths": cleanup_paths,
        "selected_photo_url": selected_photo_url,
        "source_photo_path": source_photo_path,
        "source_photo_url": resolved_source_url,
        "image_origin": image_origin,
        "frame_id": resolved_frame_id,
    }


def _create_thread(name: str, message: str, attachment_key: str | None = None) -> dict:
    form: dict[str, str] = {
        "node_id": str(int(VKORNI_NODE_ID)),
        "title": name,
        "message": message,
    }
    if attachment_key:
        form["attachment_key"] = attachment_key

    body_bytes = urlencode(form, encoding="utf-8").encode("utf-8")
    response = None
    for attempt in range(1, HTTP_RETRY_ATTEMPTS + 1):
        try:
            response = requests.post(
                f"{VKORNI_BASE_URL.rstrip('/')}/threads/",
                data=body_bytes,
                headers={**_headers(), "Content-Type": "application/x-www-form-urlencoded; charset=utf-8"},
                timeout=30,
            )
        except requests.RequestException as exc:
            if attempt == HTTP_RETRY_ATTEMPTS:
                logger.exception("XenForo thread create request failed for %s", name)
                return {
                    "status": "ERROR",
                    "error": str(exc),
                }
            logger.warning("XenForo thread create request failed for %s, retry %d/%d", name, attempt, HTTP_RETRY_ATTEMPTS)
            _sleep_before_retry(attempt)
            continue

        if response.ok:
            break

        if attempt < HTTP_RETRY_ATTEMPTS and _should_retry_response(response.status_code):
            logger.warning(
                "XenForo thread create returned %s for %s, retry %d/%d",
                response.status_code,
                name,
                attempt,
                HTTP_RETRY_ATTEMPTS,
            )
            _sleep_before_retry(attempt)
            continue

        return {
            "status": "ERROR",
            "code": response.status_code,
            "error": response.text[:500],
        }

    if not response or not response.ok:
        return {
            "status": "ERROR",
            "error": "XenForo thread create failed without usable response",
        }

    body = response.json()
    thread_id = body.get("thread", {}).get("thread_id")
    if not thread_id:
        logger.error("XenForo thread create response missing thread_id for %s: %s", name, str(body)[:500])
        return {
            "status": "ERROR",
            "code": response.status_code,
            "error": "XenForo thread response missing thread_id",
        }
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
    frame_id: int | None = None,
    preferred_source_photo_url: str | None = None,
) -> dict:
    photo_list = list(photos) if photos else []

    if not VKORNI_API_KEY:
        return _error_result("VKORNI_API_KEY is not set")
    if not VKORNI_NODE_ID:
        return _error_result("VKORNI_NODE_ID is not set")

    if not birth:
        birth = _extract_birth_from_text(text)

    resolved_photo_source_url = _resolve_cached_source_url(name, photo_list, photo_source_url)
    prepared = _prepare_export_photo(photo_list, birth, death, resolved_photo_source_url, frame_id=frame_id)
    if not prepared:
        return _error_result(
            "No exportable photo found for static XenForo upload",
            source_photo_path=(photo_list[0] if photo_list else None),
            source_photo_url=resolved_photo_source_url,
            image_origin="missing",
        )

    try:
        exported_selected_photo_url = prepared.get("selected_photo_url")
        if preferred_source_photo_url and exported_selected_photo_url == photo_list[0]:
            exported_selected_photo_url = preferred_source_photo_url

        last_error = "XenForo publish failed"
        for publish_attempt in range(1, PUBLISH_REPAIR_ATTEMPTS + 1):
            logger.info(
                "%s publish attempt name=%s attempt=%d/%d export_path=%s selected_photo=%s",
                EXPORT_GUARD_TAG,
                name,
                publish_attempt,
                PUBLISH_REPAIR_ATTEMPTS,
                prepared.get("export_path"),
                exported_selected_photo_url,
            )

            upload = _upload_attachment(prepared["export_path"])
            if not upload or not upload.get("attachment_id"):
                upload_error = (upload or {}).get("error") or "XenForo attachment upload failed"
                last_error = f"{upload_error}; thread was not created"
                if publish_attempt < PUBLISH_REPAIR_ATTEMPTS:
                    logger.warning(
                        "%s upload failed, retrying whole publish name=%s attempt=%d/%d error=%s",
                        EXPORT_GUARD_TAG,
                        name,
                        publish_attempt,
                        PUBLISH_REPAIR_ATTEMPTS,
                        last_error,
                    )
                    _sleep_before_retry(publish_attempt)
                    continue
                return _error_result(
                    last_error,
                    source_photo_path=prepared.get("source_photo_path"),
                    source_photo_url=prepared.get("source_photo_url"),
                    image_origin=prepared.get("image_origin"),
                    selected_photo_url=exported_selected_photo_url,
                    export_path=prepared.get("export_path"),
                    frame_id=prepared.get("frame_id"),
                )

            attachment_id = upload["attachment_id"]
            attachment_key = upload.get("attachment_key")
            if not attachment_key:
                last_error = f"XenForo attachment upload missing attachment_key for attachment_id={attachment_id}"
                if publish_attempt < PUBLISH_REPAIR_ATTEMPTS:
                    logger.error(
                        "%s upload missing attachment_key, retrying name=%s attempt=%d/%d attachment_id=%s",
                        EXPORT_GUARD_TAG,
                        name,
                        publish_attempt,
                        PUBLISH_REPAIR_ATTEMPTS,
                        attachment_id,
                    )
                    _sleep_before_retry(publish_attempt)
                    continue
                return _error_result(
                    last_error,
                    source_photo_path=prepared.get("source_photo_path"),
                    source_photo_url=prepared.get("source_photo_url"),
                    image_origin=prepared.get("image_origin"),
                    selected_photo_url=exported_selected_photo_url,
                    export_path=prepared.get("export_path"),
                    frame_id=prepared.get("frame_id"),
                )

            xenforo_attachment_url = upload["full_size_source"]["download_url"]
            stored_image = _download_and_store_internal_image(
                attachment_id=attachment_id,
                source=upload["full_size_source"],
            )
            if not stored_image:
                logger.warning("Failed to persist full-size XenForo image attachment_id=%s; continuing with forum attachment only", attachment_id)

            stable_image_path = stored_image["local_path"] if stored_image else None
            logger.info("Final post image source selected attachment_id=%s url=%s", attachment_id, xenforo_attachment_url)
            message = _build_message(
                text,
                attachment_id=attachment_id,
                birth=birth,
                death=death,
                attachment_url=xenforo_attachment_url,
            )

            result = _create_thread(name, message, attachment_key)
            if result.get("status") != "OK":
                last_error = result.get("error") or "XenForo thread create failed"
                if publish_attempt < PUBLISH_REPAIR_ATTEMPTS:
                    logger.warning(
                        "%s thread creation failed, retrying whole publish name=%s attempt=%d/%d attachment_id=%s error=%s",
                        EXPORT_GUARD_TAG,
                        name,
                        publish_attempt,
                        PUBLISH_REPAIR_ATTEMPTS,
                        attachment_id,
                        last_error,
                    )
                    _sleep_before_retry(publish_attempt)
                    continue
                result.update(
                    {
                        "attachment_id": attachment_id,
                        "attachment_url": xenforo_attachment_url,
                        "source_photo_path": prepared.get("source_photo_path"),
                        "source_photo_url": prepared.get("source_photo_url"),
                        "image_origin": prepared.get("image_origin"),
                        "selected_photo_url": exported_selected_photo_url,
                        "export_path": prepared.get("export_path"),
                        "frame_id": prepared.get("frame_id"),
                        "stable_image_path": stable_image_path,
                    }
                )
                return result

            thread_id = result.get("thread_id")
            verified, verify_error = _verify_thread_attachment(thread_id, attachment_id)
            if verified:
                logger.info(
                    "%s publish verified name=%s thread_id=%s attachment_id=%s attempt=%d/%d",
                    EXPORT_GUARD_TAG,
                    name,
                    thread_id,
                    attachment_id,
                    publish_attempt,
                    PUBLISH_REPAIR_ATTEMPTS,
                )
                result.update(
                    {
                        "attachment_id": attachment_id,
                        "attachment_url": xenforo_attachment_url,
                        "source_photo_path": prepared.get("source_photo_path"),
                        "source_photo_url": prepared.get("source_photo_url"),
                        "image_origin": prepared.get("image_origin"),
                        "selected_photo_url": exported_selected_photo_url,
                        "export_path": prepared.get("export_path"),
                        "frame_id": prepared.get("frame_id"),
                        "stable_image_path": stable_image_path,
                    }
                )
                return result

            logger.error(
                "%s verification failed name=%s thread_id=%s attachment_id=%s attempt=%d/%d error=%s",
                EXPORT_GUARD_TAG,
                name,
                thread_id,
                attachment_id,
                publish_attempt,
                PUBLISH_REPAIR_ATTEMPTS,
                verify_error,
            )
            cleanup_ok = _delete_thread(thread_id, verify_error)
            if not cleanup_ok:
                last_error = f"{verify_error}; cleanup failed for thread_id={thread_id}"
                return _error_result(
                    last_error,
                    thread_id=thread_id,
                    attachment_id=attachment_id,
                    attachment_url=xenforo_attachment_url,
                    source_photo_path=prepared.get("source_photo_path"),
                    source_photo_url=prepared.get("source_photo_url"),
                    image_origin=prepared.get("image_origin"),
                    selected_photo_url=exported_selected_photo_url,
                    export_path=prepared.get("export_path"),
                    frame_id=prepared.get("frame_id"),
                    stable_image_path=stable_image_path,
                )

            last_error = verify_error
            if publish_attempt < PUBLISH_REPAIR_ATTEMPTS:
                logger.warning(
                    "%s cleaned broken thread and will retry name=%s thread_id=%s next_attempt=%d/%d",
                    EXPORT_GUARD_TAG,
                    name,
                    thread_id,
                    publish_attempt + 1,
                    PUBLISH_REPAIR_ATTEMPTS,
                )
                _sleep_before_retry(publish_attempt)
                continue

            return _error_result(
                last_error,
                thread_id=thread_id,
                attachment_id=attachment_id,
                attachment_url=xenforo_attachment_url,
                source_photo_path=prepared.get("source_photo_path"),
                source_photo_url=prepared.get("source_photo_url"),
                image_origin=prepared.get("image_origin"),
                selected_photo_url=exported_selected_photo_url,
                export_path=prepared.get("export_path"),
                frame_id=prepared.get("frame_id"),
                stable_image_path=stable_image_path,
            )

        return _error_result(
            last_error,
            source_photo_path=prepared.get("source_photo_path"),
            source_photo_url=prepared.get("source_photo_url"),
            image_origin=prepared.get("image_origin"),
            selected_photo_url=exported_selected_photo_url,
            export_path=prepared.get("export_path"),
            frame_id=prepared.get("frame_id"),
        )
    except Exception as exc:
        logger.exception("VKorni export failed")
        return _error_result(
            str(exc),
            source_photo_path=prepared.get("source_photo_path"),
            source_photo_url=prepared.get("source_photo_url"),
            image_origin=prepared.get("image_origin"),
            selected_photo_url=preferred_source_photo_url or prepared.get("selected_photo_url"),
            export_path=prepared.get("export_path"),
            frame_id=prepared.get("frame_id"),
        )
    finally:
        for path in prepared.get("cleanup_paths", []):
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except OSError:
                logger.warning("Failed to remove temporary export file: %s", path)
