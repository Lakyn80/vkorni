import os
import re
import logging
from typing import Iterable
from urllib.parse import unquote, urlencode, urlparse

import requests

logger = logging.getLogger(__name__)

VKORNI_BASE_URL   = os.getenv("VKORNI_BASE_URL", "https://vkorni.com/api")
VKORNI_API_KEY    = os.getenv("VKORNI_API_KEY", "")
VKORNI_NODE_ID    = os.getenv("VKORNI_NODE_ID", "")
VKORNI_USER_ID    = os.getenv("VKORNI_USER_ID", "1")
BACKEND_PUBLIC_URL = os.getenv("BACKEND_PUBLIC_URL", "").rstrip("/")

STATIC_PHOTOS_DIR = os.getenv("PHOTOS_DIR", "/app/static/photos")


def _wikimedia_thumb(url: str, width: int = 400) -> str:
    """
    Return a Wikimedia thumbnail URL at the given pixel width.

    Handles two cases:
      1. Already a thumb URL (.../thumb/.../NNNpx-file) → replace NNN with width
      2. Direct file URL (.../commons/X/XX/file.ext) → construct thumb URL
    """
    # Case 1: has /NNNpx- → just replace the size
    resized = re.sub(r"/\d+px-", f"/{width}px-", url)
    if resized != url:
        return resized

    # Case 2: direct Wikimedia file URL → build thumb URL
    parsed = urlparse(url)
    m = re.match(r"(/wikipedia/\w+/)([0-9a-f]/[0-9a-f]{2}/)(.*)", parsed.path)
    if m:
        prefix, hash_path, filename = m.groups()
        thumb_path = f"{prefix}thumb/{hash_path}{filename}/{width}px-{filename}"
        return f"{parsed.scheme}://{parsed.netloc}{thumb_path}"

    return url  # fallback: return as-is


def _headers() -> dict:
    return {
        "XF-Api-Key":  VKORNI_API_KEY,
        "XF-Api-User": VKORNI_USER_ID,
    }


def _upload_attachment(file_path: str) -> dict | None:
    """Upload a local image file to XenForo.

    Returns a dict with keys ``attachment_id`` and ``view_url`` on success,
    or *None* on failure.  ``view_url`` is the direct CDN URL of the uploaded
    image so we can embed it with ``[IMG]url[/IMG]`` instead of the inline
    ``[ATTACH=full]`` tag which renders as a link rather than an image.
    """
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
            return None

        filename = os.path.basename(file_path)
        # Detect MIME type from extension; frame_service saves as .jpg
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
        aid = att.get("attachment_id")
        # XenForo returns a direct URL in attachment.direct_url (or thumbnail_url)
        view_url = att.get("direct_url") or att.get("thumbnail_url") or ""
        logger.info("Uploaded attachment id=%s url=%s for %s", aid, view_url, filename)
        return {"attachment_id": aid, "view_url": view_url}

    except Exception:
        logger.exception("XenForo attachment upload error")
        return None


def _build_message(
    text: str,
    attachment_ids: list[int],
    birth: str | None = None,
    death: str | None = None,
    photo_source_url: str | None = None,
) -> str:
    parts = []

    # Inline photo — use [IMG] tag with the URL as-is (already a CDN/Wikimedia URL)
    # Only apply Wikimedia thumbnail normalization for actual Wikimedia URLs.
    if photo_source_url:
        is_wikimedia = "wikipedia.org" in photo_source_url or "wikimedia.org" in photo_source_url
        small_url = _wikimedia_thumb(photo_source_url, width=400) if is_wikimedia else photo_source_url
        parts.append(f"[CENTER][IMG]{small_url}[/IMG][/CENTER]")
    else:
        for aid in attachment_ids[:1]:
            parts.append(f"[CENTER][ATTACH=full]{aid}[/ATTACH][/CENTER]")

    if parts:
        parts.append("")

    # Date line with real Wikidata dates (not AI-guessed years)
    if birth or death:
        b = birth or "??"
        d = death or "наши дни"
        parts.append(f"[B]{b} — {d}[/B]")
        parts.append("")

    for paragraph in text.strip().split("\n\n"):
        paragraph = paragraph.strip()
        if paragraph:
            parts.append(paragraph)
            parts.append("")

    return "\n".join(parts).strip()


def _local_path(rel_url: str) -> str:
    """Convert /static/photos/... URL to absolute disk path, decoding percent-encoding."""
    decoded = unquote(rel_url)
    sub = decoded.lstrip("/")
    return os.path.join("/app", sub)


def _extract_birth_from_text(text: str) -> str | None:
    """Extract birth year from biography text as last-resort fallback."""
    if not text:
        return None
    # Match patterns like "родился 12 апреля 1946" or standalone year 1800-1999
    m = re.search(r"родил[сь][яь][^.]{0,40}?(1[89]\d{2}|20[01]\d)", text)
    if m:
        return m.group(1)
    # Fallback: first 4-digit year in range 1800-2024
    m = re.search(r"\b(1[89]\d{2}|20[01]\d)\b", text)
    return m.group(1) if m else None


def send_profile(
    name: str,
    text: str,
    photos: Iterable[str],
    birth: str | None = None,
    death: str | None = None,
    photo_source_url: str | None = None,
) -> dict:
    if not VKORNI_API_KEY:
        return {"status": "ERROR", "error": "VKORNI_API_KEY is not set"}
    if not VKORNI_NODE_ID:
        return {"status": "ERROR", "error": "VKORNI_NODE_ID is not set"}

    # Use biography text as fallback source for birth date
    if not birth:
        birth = _extract_birth_from_text(text)

    photo_list = list(photos) if photos else []
    attachment_ids: list[int] = []
    effective_photo_url: str | None = None

    # ── Apply memorial frame ──────────────────────────────────────────────────
    # If the photo is already a framed image (from /static/accepted_images/),
    # use it directly — no need to re-frame.
    framed_path: str | None = None
    for photo_url in photo_list[:1]:
        local = _local_path(photo_url)
        if os.path.exists(local):
            if "accepted_images" in photo_url:
                # Already framed by /api/frame — use as-is
                framed_path = local
                logger.warning("Using pre-framed image: %s", framed_path)
            else:
                try:
                    from app.services.frame_service import compose_portrait
                    framed_path = compose_portrait(local, birth=birth, death=death)
                    logger.warning("Framed image: %s", framed_path)
                except Exception:
                    logger.exception("Frame composition failed — using original photo")
                    framed_path = local
            break
        logger.warning("Photo file not found: %s (resolved: %s)", photo_url, local)

    # ── Determine how to send the photo ──────────────────────────────────────
    # Priority:
    #   1. Upload framed image to XenForo → use returned direct_url in [IMG]
    #      (works from localhost; XenForo hosts the file on their CDN)
    #   2. Wikimedia URL as [IMG] fallback (no frame, but always reachable)
    if framed_path:
        logger.warning("Uploading framed image to XenForo: %s", framed_path)
        upload = _upload_attachment(framed_path)
        logger.warning("XenForo upload result: %s", upload)
        if upload:
            attachment_ids.append(upload["attachment_id"])
            if upload["view_url"]:
                effective_photo_url = upload["view_url"]
                logger.warning("Using XenForo CDN URL: %s", effective_photo_url)
            # If view_url is empty the [ATTACH=full] tag will be used as fallback
        else:
            # Upload failed — fall back to Wikimedia thumbnail
            logger.warning("Upload failed, falling back to Wikimedia URL")
            effective_photo_url = photo_source_url
    elif photo_source_url:
        # No framed image — use Wikimedia URL directly
        effective_photo_url = photo_source_url

    message = _build_message(text, attachment_ids, birth=birth, death=death,
                             photo_source_url=effective_photo_url)

    payload = {
        "node_id":        int(VKORNI_NODE_ID),
        "title":          name,
        "message":        message,
        "attachment_ids": attachment_ids,
    }

    try:
        form: dict[str, str] = {
            "node_id": str(int(VKORNI_NODE_ID)),
            "title":   payload["title"],
            "message": payload["message"],
        }
        for i, aid in enumerate(payload["attachment_ids"]):
            form[f"attachment_ids[{i}]"] = str(aid)

        body_bytes = urlencode(form, encoding="utf-8").encode("utf-8")
        response = requests.post(
            f"{VKORNI_BASE_URL.rstrip('/')}/threads/",
            data=body_bytes,
            headers={**_headers(), "Content-Type": "application/x-www-form-urlencoded; charset=utf-8"},
            timeout=30,
        )
        if response.ok:
            body = response.json()
            thread_id = body.get("thread", {}).get("thread_id")
            thread_url = f"https://vkorni.com/threads/{thread_id}/" if thread_id else None
            return {"status": "OK", "thread_id": thread_id, "url": thread_url}
        return {
            "status": "ERROR",
            "code": response.status_code,
            "error": response.text[:500],
        }
    except Exception as exc:
        logger.exception("VKorni export failed")
        return {"status": "ERROR", "error": str(exc)}
