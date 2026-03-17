import logging
import os
import random
import uuid
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Profession → frame template mapping
# Frames 1–3: decorative   (artists)
# Frames 4–6: classic      (politicians)
# Frames 7–8: minimal      (scientists)
# Frames 9–10: modern      (athletes)
# ---------------------------------------------------------------------------
PROFESSION_FRAME_MAP: dict[str, list[int]] = {
    "artist":     [1, 2, 3],
    "painter":    [1, 2, 3],
    "musician":   [1, 2, 3],
    "writer":     [1, 2, 3],
    "actor":      [1, 2, 3],
    "politician": [4, 5, 6],
    "statesman":  [4, 5, 6],
    "president":  [4, 5, 6],
    "scientist":  [7, 8],
    "physicist":  [7, 8],
    "chemist":    [7, 8],
    "biologist":  [7, 8],
    "mathematician": [7, 8],
    "athlete":    [9, 10],
    "footballer": [9, 10],
    "boxer":      [9, 10],
    "swimmer":    [9, 10],
}

# Canvas dimensions
CANVAS_W = 800
CANVAS_H = 1000
PLATE_H  = 120        # bottom date plate height
FRAME_BORDER = 30     # inner portrait padding from frame edge


def _pick_frame(profession: Optional[str]) -> int:
    if profession:
        key = profession.lower().strip()
        candidates = PROFESSION_FRAME_MAP.get(key)
        if candidates:
            return random.choice(candidates)
    return random.randint(1, 10)


def _frame_template_path(frame_id: int) -> str:
    return os.path.join(settings.frames_dir, "templates", f"{frame_id}.png")


def _font_path(font_id: int) -> str:
    return os.path.join(settings.frames_dir, "fonts", f"{font_id}.ttf")


def _load_font(font_id: int, size: int) -> ImageFont.FreeTypeFont:
    path = _font_path(font_id)
    if os.path.exists(path):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            logger.warning("Failed to load font %s, falling back to default", path)
    return ImageFont.load_default()


def _draw_shadow_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    position: tuple[int, int],
    font: ImageFont.FreeTypeFont,
    text_color: tuple[int, int, int] = (255, 255, 255),
    shadow_color: tuple[int, int, int] = (0, 0, 0),
    shadow_offset: int = 2,
) -> None:
    x, y = position
    draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=shadow_color)
    draw.text((x, y), text, font=font, fill=text_color)


def compose_portrait(
    source_path: str,
    birth: Optional[str],
    death: Optional[str],
    profession: Optional[str] = None,
    person_name: Optional[str] = None,
) -> str:
    """
    Compose a framed portrait image.

    Steps:
      1. Open source image, resize to fit portrait area
      2. Paste frame overlay (RGBA) if available
      3. Draw bottom plate with birth–death dates
      4. Apply text shadow effect
      5. Save to accepted_dir and return the file path

    Returns:
        Absolute path to the composed output image.
    """
    frame_id = _pick_frame(profession)
    font_id  = random.randint(1, 10)

    os.makedirs(settings.accepted_dir, exist_ok=True)

    # --- 1. Open and resize source portrait ---
    source = Image.open(source_path).convert("RGBA")
    portrait_h = CANVAS_H - PLATE_H
    portrait_area = (CANVAS_W - FRAME_BORDER * 2, portrait_h - FRAME_BORDER * 2)
    source.thumbnail(portrait_area, Image.LANCZOS)

    # Create canvas
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (20, 20, 20, 255))

    # Center portrait on canvas (above plate)
    px = (CANVAS_W - source.width) // 2
    py = FRAME_BORDER + (portrait_h - FRAME_BORDER * 2 - source.height) // 2
    canvas.paste(source, (px, py), source)

    # --- 2. Overlay frame template if it exists ---
    frame_path = _frame_template_path(frame_id)
    if os.path.exists(frame_path):
        try:
            frame_img = Image.open(frame_path).convert("RGBA").resize(
                (CANVAS_W, CANVAS_H), Image.LANCZOS
            )
            canvas.alpha_composite(frame_img)
        except Exception:
            logger.warning("Could not apply frame template %s", frame_path)

    # --- 3. Draw bottom plate ---
    plate_top = CANVAS_H - PLATE_H
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([(0, plate_top), (CANVAS_W, CANVAS_H)], fill=(10, 10, 10, 220))

    # Separator line
    draw.line([(20, plate_top + 4), (CANVAS_W - 20, plate_top + 4)], fill=(180, 150, 100, 255), width=2)

    # --- 4. Render dates ---
    font_large  = _load_font(font_id, 42)
    font_small  = _load_font(font_id, 22)

    date_str = ""
    if birth and death:
        date_str = f"{birth} – {death}"
    elif birth:
        date_str = f"{birth} – ?"
    elif death:
        date_str = f"? – {death}"

    if date_str:
        bbox = draw.textbbox((0, 0), date_str, font=font_large)
        text_w = bbox[2] - bbox[0]
        text_x = (CANVAS_W - text_w) // 2
        text_y = plate_top + 20
        _draw_shadow_text(draw, date_str, (text_x, text_y), font_large,
                          text_color=(220, 195, 140), shadow_color=(0, 0, 0))

    if person_name:
        bbox = draw.textbbox((0, 0), person_name, font=font_small)
        name_w = bbox[2] - bbox[0]
        name_x = (CANVAS_W - name_w) // 2
        name_y = plate_top + 72
        _draw_shadow_text(draw, person_name, (name_x, name_y), font_small,
                          text_color=(180, 180, 180), shadow_color=(0, 0, 0))

    # --- 5. Apply subtle emboss glow on frame border ---
    embossed = canvas.filter(ImageFilter.SMOOTH_MORE)
    canvas = Image.blend(canvas, embossed, alpha=0.15)

    # --- 6. Save output ---
    out_name = f"{uuid.uuid4().hex}.jpg"
    out_path = os.path.join(settings.accepted_dir, out_name)
    canvas.convert("RGB").save(out_path, "JPEG", quality=90)
    logger.info("Composed portrait saved: %s (frame=%d, font=%d)", out_path, frame_id, font_id)
    return out_path
