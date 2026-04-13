import os
import re
import logging
import random
import time
import requests
import redis
from PIL import Image
from typing import Optional, Dict
from email.utils import parsedate_to_datetime
from threading import Lock
from urllib.parse import urlparse, unquote

try:
    import cv2
except ImportError:  # pragma: no cover - optional in lightweight test envs
    cv2 = None

try:
    from pillow_heif import register_heif_opener
except ImportError:  # pragma: no cover - optional in lightweight test envs
    def register_heif_opener():
        return None

register_heif_opener()  # enable HEIC/HEIF support in Pillow

from app.config import settings
from app.db.photos_repo import add_photo, find_photo_by_source_url

logger = logging.getLogger(__name__)

_LANG          = settings.wiki_lang
_AGENT         = settings.wiki_user_agent
_WIKIDATA_BASE = settings.wikidata_base

HEADERS = {
    "User-Agent": _AGENT,
    "Accept": "application/json",
}

IMAGE_HEADERS = {
    "User-Agent": _AGENT,
    "Accept": "image/*,*/*;q=0.8",
}

WIKI_SUMMARY_URL = f"https://{_LANG}.wikipedia.org/api/rest_v1/page/summary/{{title}}"
WIKI_API_URL     = f"https://{_LANG}.wikipedia.org/w/api.php"
WIKI_ACTION_URL  = WIKI_API_URL + "?action=query&prop=pageprops&titles={title}&format=json"
WIKIDATA_URL     = _WIKIDATA_BASE + "/wiki/Special:EntityData/{qid}.json"

STATIC_PHOTOS_DIR = settings.photos_dir
MAX_IMAGES = settings.wiki_max_images

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
ALLOWED_IMAGE_HOSTS = {"upload.wikimedia.org"}

_WIKIMEDIA_SESSION = requests.Session()
_WIKIMEDIA_REQUEST_LOCK = Lock()
_LAST_WIKIMEDIA_REQUEST_AT = 0.0
_WIKI_RATE_LIMIT_REDIS = None
_WIKI_RATE_LIMIT_REDIS_LOCK = Lock()
_LAST_WIKI_RATE_LIMIT_WARNING_AT = 0.0
_WIKI_RATE_LIMIT_LUA = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
end
return current
"""

_RU_MONTHS = [
    "", "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]


def _throttle_wikimedia_request() -> None:
    global _LAST_WIKIMEDIA_REQUEST_AT

    min_delay = max(0.0, settings.wiki_request_delay_seconds)
    max_jitter = max(0.0, settings.wiki_request_jitter_seconds)
    required_gap = min_delay + random.uniform(0.0, max_jitter)

    with _WIKIMEDIA_REQUEST_LOCK:
        now = time.monotonic()
        if _LAST_WIKIMEDIA_REQUEST_AT > 0:
            elapsed = now - _LAST_WIKIMEDIA_REQUEST_AT
            wait_for = max(0.0, required_gap - elapsed)
            if wait_for > 0:
                time.sleep(wait_for)
        _LAST_WIKIMEDIA_REQUEST_AT = time.monotonic()


def _get_wiki_rate_limit_redis() -> redis.Redis:
    global _WIKI_RATE_LIMIT_REDIS
    if _WIKI_RATE_LIMIT_REDIS is None:
        with _WIKI_RATE_LIMIT_REDIS_LOCK:
            if _WIKI_RATE_LIMIT_REDIS is None:
                _WIKI_RATE_LIMIT_REDIS = redis.Redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                    health_check_interval=30,
                )
    return _WIKI_RATE_LIMIT_REDIS


def _increment_wiki_rate_limit_window(client: redis.Redis, key: str, ttl_seconds: int) -> int:
    return int(client.eval(_WIKI_RATE_LIMIT_LUA, 1, key, ttl_seconds))


def _log_wiki_rate_limit_backend_failure(exc: Exception) -> None:
    global _LAST_WIKI_RATE_LIMIT_WARNING_AT
    now = time.monotonic()
    if now - _LAST_WIKI_RATE_LIMIT_WARNING_AT < 60:
        return
    _LAST_WIKI_RATE_LIMIT_WARNING_AT = now
    logger.warning("Global wiki rate limiter unavailable; falling back to local throttling: %s", exc)


def wait_for_wiki_rate_limit() -> None:
    limit = max(1, int(settings.wiki_rate_limit_per_sec))
    ttl_seconds = 2

    while True:
        current_second = int(time.time())
        key = f"wiki_rate_limit:{current_second}"
        try:
            current = _increment_wiki_rate_limit_window(_get_wiki_rate_limit_redis(), key, ttl_seconds)
        except Exception as exc:
            _log_wiki_rate_limit_backend_failure(exc)
            return

        if current <= limit:
            return

        wait_for = max(0.01, (current_second + 1) - time.time())
        logger.debug(
            "Waiting %.3fs for global wiki rate limit slot (limit=%d current=%d key=%s)",
            wait_for,
            limit,
            current,
            key,
        )
        time.sleep(wait_for)


def _parse_retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
            return max(0.0, retry_at.timestamp() - time.time())
        except Exception:
            return None


def _request_wikimedia(
    url: str,
    *,
    headers: dict[str, str],
    params: dict | None = None,
    timeout: int | None = None,
    purpose: str,
    stream: bool = False,
) -> requests.Response | None:
    max_attempts = max(1, settings.wiki_request_max_retries)
    timeout = timeout or settings.wiki_request_timeout_seconds

    for attempt in range(1, max_attempts + 1):
        _throttle_wikimedia_request()
        wait_for_wiki_rate_limit()
        try:
            response = _WIKIMEDIA_SESSION.get(
                url,
                headers=headers,
                params=params,
                timeout=timeout,
                stream=stream,
            )
        except requests.RequestException as exc:
            if attempt >= max_attempts:
                logger.warning("Wikimedia %s failed after %d attempts for %s: %s", purpose, attempt, url, exc)
                return None
            backoff = settings.wiki_request_backoff_seconds * (2 ** (attempt - 1))
            logger.warning(
                "Wikimedia %s request error on attempt %d/%d for %s; retrying in %.1fs: %s",
                purpose,
                attempt,
                max_attempts,
                url,
                backoff,
                exc,
            )
            time.sleep(backoff)
            continue

        status = response.status_code

        if status == 403:
            logger.warning("Wikimedia %s returned 403 for %s; skipping without aggressive retry", purpose, url)
            response.close()
            return None

        if status == 429:
            retry_after = _parse_retry_after_seconds(response.headers.get("Retry-After"))
            backoff = max(
                settings.wiki_rate_limit_backoff_seconds,
                settings.wiki_request_backoff_seconds * (2 ** (attempt - 1)),
                retry_after or 0.0,
            )
            if attempt >= max_attempts:
                logger.warning(
                    "Wikimedia %s stayed rate-limited (429) after %d attempts for %s; skipping",
                    purpose,
                    attempt,
                    url,
                )
                response.close()
                return None
            logger.warning(
                "Wikimedia %s hit 429 on attempt %d/%d for %s; retrying in %.1fs",
                purpose,
                attempt,
                max_attempts,
                url,
                backoff,
            )
            response.close()
            time.sleep(backoff)
            continue

        if 500 <= status < 600:
            backoff = settings.wiki_request_backoff_seconds * (2 ** (attempt - 1))
            if attempt >= max_attempts:
                logger.warning(
                    "Wikimedia %s failed with HTTP %d after %d attempts for %s; skipping",
                    purpose,
                    status,
                    attempt,
                    url,
                )
                response.close()
                return None
            logger.warning(
                "Wikimedia %s failed with HTTP %d on attempt %d/%d for %s; retrying in %.1fs",
                purpose,
                status,
                attempt,
                max_attempts,
                url,
                backoff,
            )
            response.close()
            time.sleep(backoff)
            continue

        if status >= 400:
            logger.warning("Wikimedia %s failed with HTTP %d for %s; skipping", purpose, status, url)
            response.close()
            return None

        return response

    return None


def _request_wikimedia_json(
    url: str,
    *,
    headers: dict[str, str],
    params: dict | None = None,
    timeout: int | None = None,
    purpose: str,
) -> dict | None:
    response = _request_wikimedia(
        url,
        headers=headers,
        params=params,
        timeout=timeout,
        purpose=purpose,
    )
    if response is None:
        return None

    try:
        return response.json()
    except ValueError:
        logger.warning("Wikimedia %s returned invalid JSON for %s; skipping", purpose, url)
        return None
    finally:
        response.close()


def _relative_static_to_abs_path(path: str) -> str:
    if path.startswith("/static/"):
        return os.path.join(os.path.dirname(STATIC_PHOTOS_DIR), path.lstrip("/"))
    return path


def _abs_photo_path_to_rel_path(path: str) -> str:
    static_root = os.path.dirname(STATIC_PHOTOS_DIR)
    rel_path = os.path.relpath(path, static_root).replace("\\", "/")
    return f"/static/{rel_path}"


def _find_cached_download(folder_name: str, target_dir: str, file_name: str, source_url: str | None) -> tuple[str, str] | None:
    if source_url:
        cached = find_photo_by_source_url(source_url)
        if cached:
            rel_path = cached.get("file_path") or ""
            abs_path = _relative_static_to_abs_path(rel_path)
            if rel_path and os.path.exists(abs_path):
                return abs_path, rel_path

    stem, _ = os.path.splitext(file_name)
    if not stem or not os.path.isdir(target_dir):
        return None

    for existing_name in os.listdir(target_dir):
        existing_path = os.path.join(target_dir, existing_name)
        if not os.path.isfile(existing_path):
            continue
        if os.path.splitext(existing_name)[0] != stem:
            continue
        rel_path = f"/static/photos/{folder_name}/{existing_name}"
        return existing_path, rel_path

    return None


def _safe_search_wiki_title(name: str) -> Optional[str]:
    params = {
        "action": "query",
        "list": "search",
        "srsearch": name,
        "srlimit": 1,
        "srnamespace": 0,
        "format": "json",
    }

    data = _request_wikimedia_json(
        WIKI_API_URL,
        headers=HEADERS,
        params=params,
        timeout=settings.wiki_request_timeout_seconds,
        purpose=f"title search for {name}",
    )
    if not data:
        return None

    results = data.get("query", {}).get("search", [])
    if results:
        title = results[0]["title"]
        logger.info("Wiki search '%s' → '%s'", name, title)
        return title
    return None


def _safe_get_pageimage(title: str) -> Optional[str]:
    params = {
        "action": "query",
        "prop": "pageimages",
        "titles": title,
        "piprop": "original",
        "format": "json",
    }

    data = _request_wikimedia_json(
        WIKI_API_URL,
        headers=HEADERS,
        params=params,
        timeout=settings.wiki_request_timeout_seconds,
        purpose=f"pageimage lookup for {title}",
    )
    if not data:
        return None

    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        original = page.get("original")
        if original:
            return original.get("source")
    return None


def _download_wikimedia_image(url: str, file_path: str) -> str | None:
    response = _request_wikimedia(
        url,
        headers=IMAGE_HEADERS,
        timeout=settings.wiki_image_timeout_seconds,
        purpose="image download",
        stream=True,
    )
    if response is None:
        return None

    try:
        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return file_path
    except Exception as exc:
        logger.warning("Failed to persist Wikimedia image %s to %s: %s", url, file_path, exc)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except OSError:
            logger.warning("Failed to remove partial Wikimedia download %s", file_path)
        return None
    finally:
        response.close()


def convert_to_webp(file_path: str) -> str:
    """Convert any image to WebP in-place. Returns new file path (.webp)."""
    try:
        base, _ = os.path.splitext(file_path)
        out_path = base + ".webp"
        with Image.open(file_path) as img:
            img = img.convert("RGBA") if img.mode in ("RGBA", "LA", "P") else img.convert("RGB")
            img.save(out_path, "WEBP", quality=88, method=4)
        if file_path != out_path and os.path.exists(file_path):
            os.remove(file_path)
        return out_path
    except Exception:
        logger.exception("WebP conversion failed for %s", file_path)
        return file_path


def center_face_in_image(path: str):
    if cv2 is None:
        logger.info("OpenCV not installed; skipping face centering for %s", path)
        return
    try:
        img = cv2.imread(path)
        if img is None:
            return

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.2,
            minNeighbors=5,
            minSize=(60, 60),
        )

        if len(faces) == 0:
            return

        x, y, w, h = faces[0]

        height, width = img.shape[:2]

        cx = x + w // 2
        cy = y + h // 2

        crop_size = max(w, h) * 3

        x1 = max(cx - crop_size // 2, 0)
        y1 = max(cy - crop_size // 2, 0)
        x2 = min(cx + crop_size // 2, width)
        y2 = min(cy + crop_size // 2, height)

        cropped = img[y1:y2, x1:x2]

        pil_img = Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))
        pil_img = pil_img.resize((512, 512), Image.LANCZOS)

        pil_img.save(path)

    except Exception:
        logger.exception("Face centering failed", extra={"file": path})


def _wiki_title(name: str) -> str:
    return name.replace(" ", "_")


def _search_wiki_title(name: str) -> Optional[str]:
    return _safe_search_wiki_title(name)


def _safe_dir_name(name: str) -> str:
    safe = re.sub(r"[^\w\-\. ]+", "", name, flags=re.UNICODE).strip()
    return safe.replace(" ", "_") or "unknown"


def _get_wikidata_id(name: str) -> Optional[str]:
    url = WIKI_ACTION_URL.format(title=_wiki_title(name))
    data = _request_wikimedia_json(
        url,
        headers=HEADERS,
        timeout=settings.wiki_request_timeout_seconds,
        purpose=f"wikidata id lookup for {name}",
    )
    if not data:
        return None

    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        props = page.get("pageprops", {})
        qid = props.get("wikibase_item")
        if qid:
            return qid
    return None


def _get_birth_death_from_wikidata(qid: str) -> Dict[str, Optional[str]]:
    url = WIKIDATA_URL.format(qid=qid)
    data = _request_wikimedia_json(
        url,
        headers=HEADERS,
        timeout=settings.wiki_request_timeout_seconds,
        purpose=f"wikidata entity lookup for {qid}",
    ) or {}
    entities = data.get("entities", {})
    entity = entities.get(qid, {})
    claims = entity.get("claims", {})

    def extract_date(prop_id: str) -> Optional[str]:
        """Return date as 'DD месяц YYYY' or 'YYYY' depending on precision."""
        if prop_id not in claims:
            return None
        mainsnak = claims[prop_id][0].get("mainsnak", {})
        datavalue = mainsnak.get("datavalue", {})
        value = datavalue.get("value", {})
        time_str = value.get("time")       # e.g. "+1946-04-25T00:00:00Z"
        precision = value.get("precision", 9)  # 9=year, 10=month, 11=day
        if not time_str:
            return None
        try:
            # strip leading +/-
            clean = time_str.lstrip("+-")
            year = int(clean[0:4])
            month = int(clean[5:7])
            day = int(clean[8:10])
            if precision >= 11 and 1 <= month <= 12 and 1 <= day <= 31:
                return f"{day} {_RU_MONTHS[month]} {year}"
            if precision >= 10 and 1 <= month <= 12:
                return f"{_RU_MONTHS[month].capitalize()} {year}"
            return str(year)
        except Exception:
            return time_str[1:5]

    return {
        "birth": extract_date("P569"),
        "death": extract_date("P570"),
    }


def _get_pageimage(title: str) -> Optional[str]:
    return _safe_get_pageimage(title)


def fetch_person_from_wikipedia(name: str) -> Optional[Dict]:
    wiki_title = _search_wiki_title(name) or name
    url = WIKI_SUMMARY_URL.format(title=_wiki_title(wiki_title))
    data = _request_wikimedia_json(
        url,
        headers=HEADERS,
        timeout=settings.wiki_request_timeout_seconds,
        purpose=f"summary lookup for {name}",
    )
    if not data:
        return None

    if not data.get("title"):
        return None

    result = {
        "name": data.get("title"),
        "summary_text": data.get("extract"),
        "birth": None,
        "death": None,
        "wiki_url": None,
        "images": [],
    }

    urls = data.get("content_urls", {})
    desktop = urls.get("desktop", {})
    result["wiki_url"] = desktop.get("page")

    qid = _get_wikidata_id(result["name"])
    if qid:
        dates = _get_birth_death_from_wikidata(qid)
        result["birth"] = dates["birth"]
        result["death"] = dates["death"]

    original = data.get("originalimage", {})
    if original.get("source"):
        result["images"] = [original["source"]]
    else:
        try:
            img = _get_pageimage(_wiki_title(result["name"]))
            if img and urlparse(img).hostname in ALLOWED_IMAGE_HOSTS:
                result["images"] = [img]
        except Exception:
            logger.exception("Wikipedia pageimage fetch failed", extra={"name": name})

    return result


def fetch_person_images(name: str) -> list[dict]:
    try:
        wiki_title = _safe_search_wiki_title(name) or name
        summary_url = WIKI_SUMMARY_URL.format(title=_wiki_title(wiki_title))
        summary_data = _request_wikimedia_json(
            summary_url,
            headers=HEADERS,
            timeout=settings.wiki_request_timeout_seconds,
            purpose=f"summary lookup for {name}",
        ) or {}

        original = summary_data.get("originalimage", {})
        src = original.get("source", "")

        if src and urlparse(src).hostname in ALLOWED_IMAGE_HOSTS:
            image_infos = [{"url": src, "description": None}]
        else:
            img = _safe_get_pageimage(_wiki_title(wiki_title))
            if img and urlparse(img).hostname in ALLOWED_IMAGE_HOSTS:
                image_infos = [{"url": img, "description": None}]
            else:
                return []

    except Exception:
        logger.exception("Wikipedia image fetch failed", extra={"name": name})
        return []

    folder_name = _safe_dir_name(name)
    target_dir = os.path.join(STATIC_PHOTOS_DIR, folder_name)
    os.makedirs(target_dir, exist_ok=True)

    stored: list[dict] = []

    for info in image_infos[:MAX_IMAGES]:
        url = info.get("url")
        if not url:
            continue

        file_name = unquote(os.path.basename(urlparse(url).path))
        if not file_name:
            continue

        cached = _find_cached_download(folder_name, target_dir, file_name, url)
        if cached:
            file_path, rel_path = cached
        else:
            file_path = os.path.join(target_dir, file_name)
            rel_path = f"/static/photos/{folder_name}/{file_name}"

            downloaded_path = _download_wikimedia_image(url, file_path)
            if downloaded_path is None:
                logger.warning("Skipping Wikimedia image after download failure: %s", url)
                continue

            try:
                center_face_in_image(downloaded_path)
                file_path = convert_to_webp(downloaded_path)
            except Exception as exc:
                logger.warning("Image post-processing failed for %s: %s", url, exc)
                continue

            file_name = os.path.basename(file_path)
            rel_path = f"/static/photos/{folder_name}/{file_name}"

        if not file_path.endswith(".webp") and os.path.exists(file_path):
            file_path = convert_to_webp(file_path)
            rel_path = _abs_photo_path_to_rel_path(file_path)

        description = info.get("description")
        add_photo(name, rel_path, url, description)

        stored.append({
            "file_path": rel_path,
            "source_url": url,
            "description": description,
        })

    return stored
