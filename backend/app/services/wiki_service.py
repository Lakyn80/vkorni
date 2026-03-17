import os
import re
import logging
import requests
import cv2
from PIL import Image
from pillow_heif import register_heif_opener
from typing import Optional, Dict
from urllib.parse import urlparse, unquote

register_heif_opener()  # enable HEIC/HEIF support in Pillow

from app.db.photos_repo import add_photo

logger = logging.getLogger(__name__)

_LANG          = os.getenv("WIKI_LANG", "ru")
_AGENT         = os.getenv("WIKI_USER_AGENT", "vkorni-bot/1.0")
_WIKIDATA_BASE = os.getenv("WIKIDATA_BASE_URL", "https://www.wikidata.org")

HEADERS = {"User-Agent": _AGENT}

IMAGE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
}

WIKI_SUMMARY_URL = f"https://{_LANG}.wikipedia.org/api/rest_v1/page/summary/{{title}}"
WIKI_API_URL     = f"https://{_LANG}.wikipedia.org/w/api.php"
WIKI_ACTION_URL  = WIKI_API_URL + "?action=query&prop=pageprops&titles={title}&format=json"
WIKIDATA_URL     = _WIKIDATA_BASE + "/wiki/Special:EntityData/{qid}.json"

STATIC_PHOTOS_DIR = os.getenv("PHOTOS_DIR", "/app/static/photos")
MAX_IMAGES = int(os.getenv("WIKI_MAX_IMAGES", "5"))

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
ALLOWED_IMAGE_HOSTS = {"upload.wikimedia.org"}

_RU_MONTHS = [
    "", "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]


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
    params = {
        "action": "query",
        "list": "search",
        "srsearch": name,
        "srlimit": 1,
        "srnamespace": 0,
        "format": "json",
    }
    try:
        r = requests.get(WIKI_API_URL, headers=HEADERS, params=params, timeout=10)
        results = r.json().get("query", {}).get("search", [])
        if results:
            title = results[0]["title"]
            logger.info("Wiki search '%s' → '%s'", name, title)
            return title
    except Exception:
        logger.exception("Wiki search failed for '%s'", name)
    return None


def _safe_dir_name(name: str) -> str:
    safe = re.sub(r"[^\w\-\. ]+", "", name, flags=re.UNICODE).strip()
    return safe.replace(" ", "_") or "unknown"


def _get_wikidata_id(name: str) -> Optional[str]:
    url = WIKI_ACTION_URL.format(title=_wiki_title(name))
    r = requests.get(url, headers=HEADERS, timeout=10)
    data = r.json()

    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        props = page.get("pageprops", {})
        qid = props.get("wikibase_item")
        if qid:
            return qid
    return None


def _get_birth_death_from_wikidata(qid: str) -> Dict[str, Optional[str]]:
    url = WIKIDATA_URL.format(qid=qid)
    r = requests.get(url, headers=HEADERS, timeout=10)

    data = r.json()
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
    params = {
        "action": "query",
        "prop": "pageimages",
        "titles": title,
        "piprop": "original",
        "format": "json",
    }

    r = requests.get(WIKI_API_URL, headers=HEADERS, params=params, timeout=10)
    data = r.json()

    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        original = page.get("original")
        if original:
            return original.get("source")

    return None


def fetch_person_from_wikipedia(name: str) -> Optional[Dict]:
    wiki_title = _search_wiki_title(name) or name
    url = WIKI_SUMMARY_URL.format(title=_wiki_title(wiki_title))
    r = requests.get(url, headers=HEADERS, timeout=10)

    try:
        data = r.json()
    except Exception:
        logger.exception("Wikipedia summary parse failed", extra={"name": name})
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
        wiki_title = _search_wiki_title(name) or name
        summary_url = WIKI_SUMMARY_URL.format(title=_wiki_title(wiki_title))
        sr = requests.get(summary_url, headers=HEADERS, timeout=10)
        summary_data = sr.json()

        original = summary_data.get("originalimage", {})
        src = original.get("source", "")

        if src and urlparse(src).hostname in ALLOWED_IMAGE_HOSTS:
            image_infos = [{"url": src, "description": None}]
        else:
            img = _get_pageimage(_wiki_title(wiki_title))
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

        file_path = os.path.join(target_dir, file_name)
        rel_path = f"/static/photos/{folder_name}/{file_name}"

        if not os.path.exists(file_path):
            try:
                r = requests.get(url, headers=IMAGE_HEADERS, timeout=15)
                r.raise_for_status()
                with open(file_path, "wb") as f:
                    f.write(r.content)

                center_face_in_image(file_path)
                file_path = convert_to_webp(file_path)

                # update filename/rel_path after conversion
                file_name = os.path.basename(file_path)
                rel_path = f"/static/photos/{folder_name}/{file_name}"

            except Exception:
                logger.exception("Image download failed", extra={"url": url})
                continue
        else:
            # already cached — ensure webp
            if not file_path.endswith(".webp"):
                file_path = convert_to_webp(file_path)
                file_name = os.path.basename(file_path)
                rel_path = f"/static/photos/{folder_name}/{file_name}"

        description = info.get("description")
        add_photo(name, rel_path, url, description)

        stored.append({
            "file_path": rel_path,
            "source_url": url,
            "description": description,
        })

    return stored