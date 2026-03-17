import base64
import logging
import requests
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

REJECT_LABELS: set[str] = {
    "sculpture", "monument", "artifact", "map", "document",
    "building", "sign", "text", "font", "flag", "logo",
}
ACCEPT_LABELS: set[str] = {
    "person", "portrait", "human", "face", "photograph",
    "people", "man", "woman", "child",
}

_VISION_URL = "https://vision.googleapis.com/v1/images:annotate"


def _encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _call_vision_api(image_path: str) -> Optional[dict]:
    if not settings.vision_api_key:
        logger.warning("GOOGLE_VISION_API_KEY not set — skipping Vision validation")
        return None

    payload = {
        "requests": [
            {
                "image": {"content": _encode_image(image_path)},
                "features": [
                    {"type": "LABEL_DETECTION", "maxResults": 20},
                    {"type": "FACE_DETECTION", "maxResults": 5},
                ],
            }
        ]
    }
    try:
        r = requests.post(
            _VISION_URL,
            params={"key": settings.vision_api_key},
            json=payload,
            timeout=15,
        )
        r.raise_for_status()
        return r.json().get("responses", [{}])[0]
    except Exception:
        logger.exception("Google Vision API call failed", extra={"path": image_path})
        return None


def validate_image(image_path: str) -> tuple[bool, str]:
    """
    Validate that an image contains a real person portrait.

    Returns:
        (True, "ok")          — image accepted
        (False, reason_str)   — image rejected with reason
    """
    response = _call_vision_api(image_path)

    if response is None:
        # Vision API unavailable or not configured — accept by default to avoid blocking pipeline
        logger.info("Vision API unavailable, accepting image by default: %s", image_path)
        return True, "vision_api_unavailable_accepted"

    label_annotations = response.get("labelAnnotations") or []
    face_annotations   = response.get("faceAnnotations") or []

    detected_labels = {a["description"].lower() for a in label_annotations}

    rejected = REJECT_LABELS & detected_labels
    if rejected:
        return False, f"rejected labels: {sorted(rejected)}"

    has_face   = len(face_annotations) > 0
    has_person = bool(ACCEPT_LABELS & detected_labels)

    if not has_face and not has_person:
        return False, f"no face or person detected (labels: {sorted(detected_labels)[:8]})"

    return True, "ok"
