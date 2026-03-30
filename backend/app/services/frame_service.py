"""
frame_service.py
----------------
Standalone module — applies decorative memorial frames to portrait images.

10 fully programmatic styles (pure Pillow — no external PNG templates needed).
Fonts downloaded into /app/frames/fonts/ by Dockerfile at build time.

Geometry (px):
    PHOTO_SIZE  512 × 512   (same as center_face_in_image output)
    BORDER       50          left / right / top padding
    PLATE_H      90          date plate at the bottom
    ──────────────────
    OUTPUT       612 × 652   total canvas

Usage:
    from app.services.frame_service import compose_portrait
    out = compose_portrait("/app/static/photos/name/photo.webp",
                           birth="25 апреля 1946", death="6 апреля 2022")
"""

import logging
import os
import random
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from app.config import settings

logger = logging.getLogger(__name__)

# ─── Geometry ─────────────────────────────────────────────────────────────────
PHOTO_SIZE = 512
BORDER     = 50
OUTPUT_W   = PHOTO_SIZE + BORDER * 2   # 612
OUTPUT_H   = PHOTO_SIZE + BORDER * 2   # 612

FONTS_DIR = os.path.join(settings.frames_dir, "fonts")

# ─── Fallback system fonts ────────────────────────────────────────────────────
_FALLBACK_FONTS = [
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
]

# ─── 10 frame styles ──────────────────────────────────────────────────────────
# bg           canvas background (RGB)
# outer        outer border stroke color
# inner        inner border stroke color (thinner, tight around photo)
# plate_bg     date plate fill
# text_color   date text color
# font_file    TTF filename in FONTS_DIR
# bw           outer border stroke width (px)
# deco         True → add Art Deco extra hairline + side ticks

STYLES: list[dict] = [
    # 0 — Black marble + gold
    {"bg": (18, 18, 18), "outer": (165, 132, 58), "inner": (80, 64, 28),
     "plate_bg": (25, 25, 25), "text_color": (205, 168, 78),
     "font_file": "Cinzel-Regular.ttf", "bw": 6},

    # 1 — Dark wood + cream
    {"bg": (58, 34, 14), "outer": (212, 188, 142), "inner": (118, 88, 48),
     "plate_bg": (48, 26, 9), "text_color": (222, 196, 148),
     "font_file": "LibreBaskerville-Regular.ttf", "bw": 8},

    # 2 — Silver museum
    {"bg": (228, 228, 230), "outer": (158, 158, 165), "inner": (200, 200, 205),
     "plate_bg": (215, 215, 218), "text_color": (55, 55, 68),
     "font_file": "EBGaramond-Regular.ttf", "bw": 5},

    # 3 — Gold ornate
    {"bg": (28, 18, 6), "outer": (212, 172, 68), "inner": (148, 118, 42),
     "plate_bg": (20, 13, 4), "text_color": (222, 185, 88),
     "font_file": "PlayfairDisplay-Regular.ttf", "bw": 10},

    # 4 — Sepia vintage
    {"bg": (92, 72, 48), "outer": (182, 155, 108), "inner": (128, 102, 68),
     "plate_bg": (78, 58, 36), "text_color": (232, 206, 158),
     "font_file": "Cormorant-Regular.ttf", "bw": 7},

    # 5 — Stone monument
    {"bg": (88, 88, 90), "outer": (202, 202, 202), "inner": (138, 138, 140),
     "plate_bg": (72, 72, 74), "text_color": (232, 228, 224),
     "font_file": "CrimsonText-Regular.ttf", "bw": 6},

    # 6 — Art Deco
    {"bg": (14, 11, 7), "outer": (196, 158, 64), "inner": (98, 78, 28),
     "plate_bg": (11, 8, 4), "text_color": (196, 158, 64),
     "font_file": "JosefinSlab-Regular.ttf", "bw": 4, "deco": True},

    # 7 — Victorian
    {"bg": (44, 14, 14), "outer": (178, 138, 88), "inner": (28, 8, 8),
     "plate_bg": (36, 8, 8), "text_color": (202, 165, 98),
     "font_file": "Spectral-Regular.ttf", "bw": 9},

    # 8 — Orthodox / Byzantine
    {"bg": (14, 24, 58), "outer": (196, 158, 64), "inner": (98, 78, 28),
     "plate_bg": (9, 16, 48), "text_color": (212, 175, 78),
     "font_file": "Cardo-Regular.ttf", "bw": 7},

    # 9 — White gallery
    {"bg": (248, 246, 242), "outer": (178, 152, 88), "inner": (212, 196, 158),
     "plate_bg": (240, 238, 234), "text_color": (78, 58, 28),
     "font_file": "IMFellEnglish-Regular.ttf", "bw": 3},
]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _load_font(font_file: str, size: int) -> ImageFont.FreeTypeFont:
    path = os.path.join(FONTS_DIR, font_file)
    if os.path.exists(path):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            logger.warning("Cannot load font %s", path)
    for fb in _FALLBACK_FONTS:
        if os.path.exists(fb):
            try:
                return ImageFont.truetype(fb, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _diamond(draw: ImageDraw.Draw, cx: int, cy: int, r: int, color: tuple) -> None:
    """Small diamond ornament — used as corner decoration."""
    draw.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill=color)


# ─── Public API ───────────────────────────────────────────────────────────────

def compose_portrait(
    source_path: str,
    birth: Optional[str],
    death: Optional[str],
    frame_id: Optional[int] = None,
    profession: Optional[str] = None,   # kept for API compatibility, unused
    person_name: Optional[str] = None,  # kept for API compatibility, unused
) -> str:
    """
    Apply a memorial frame overlay to source_path.

    Always returns a path — on any error returns source_path unchanged so
    callers never crash.

    Args:
        source_path : Local path to the photo (any Pillow-supported format).
        birth       : Birth date string, e.g. "25 апреля 1946".
        death       : Death date string, e.g. "6 апреля 2022".
        frame_id    : 0–9 to pin a style; None = random each call.

    Returns:
        Absolute path to the composed JPEG in accepted_images/.
    """
    try:
        return _compose(source_path, birth, death, frame_id)
    except Exception:
        logger.exception("frame_service: composition failed for %s — returning original", source_path)
        return source_path


def _compose(
    source_path: str,
    birth: Optional[str],
    death: Optional[str],
    frame_id: Optional[int],
) -> str:
    if frame_id is None:
        frame_id = random.randint(0, len(STYLES) - 1)

    s  = STYLES[frame_id % len(STYLES)]
    bw = s["bw"]

    # ── 1. Load & resize source ───────────────────────────────────────────────
    with Image.open(source_path) as src:
        src = src.convert("RGB")
        src = src.resize((PHOTO_SIZE, PHOTO_SIZE), Image.LANCZOS)

    # ── 2. Canvas ─────────────────────────────────────────────────────────────
    canvas = Image.new("RGB", (OUTPUT_W, OUTPUT_H), s["bg"])
    draw   = ImageDraw.Draw(canvas)

    px, py = BORDER, BORDER          # photo top-left corner
    canvas.paste(src, (px, py))

    # ── 3. Save ───────────────────────────────────────────────────────────────
    os.makedirs(settings.accepted_dir, exist_ok=True)
    stem     = Path(source_path).stem
    out_path = os.path.join(settings.accepted_dir, f"{stem}_frame{frame_id}.jpg")
    canvas.save(out_path, "JPEG", quality=88, optimize=True)
    logger.info("Frame #%d applied → %s", frame_id, out_path)
    return out_path
