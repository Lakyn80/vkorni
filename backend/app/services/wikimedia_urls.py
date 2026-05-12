import os
from urllib.parse import unquote, urlparse, urlunparse


RASTER_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
WIKIMEDIA_UPLOAD_HOST = "upload.wikimedia.org"


def original_wikimedia_url_from_thumb(url: str | None) -> str | None:
    if not url:
        return None

    parsed = urlparse(url)
    if parsed.hostname != WIKIMEDIA_UPLOAD_HOST:
        return None

    parts = parsed.path.split("/")
    try:
        thumb_index = parts.index("thumb")
    except ValueError:
        return None

    if len(parts) <= thumb_index + 4:
        return None

    original_filename = parts[-2]
    _, ext = os.path.splitext(unquote(original_filename))
    if ext.lower() not in RASTER_IMAGE_EXTENSIONS:
        return None

    original_path = "/".join(parts[:thumb_index] + parts[thumb_index + 1 : -1])
    return urlunparse(parsed._replace(path=original_path, query="", fragment=""))


def wikimedia_download_candidates(url: str) -> list[str]:
    original = original_wikimedia_url_from_thumb(url)
    if original and original != url:
        return [original, url]
    return [url]
