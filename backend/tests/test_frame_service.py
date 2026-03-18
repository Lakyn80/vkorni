"""Tests for services/frame_service.py — memorial frame composition."""
import os
import pytest
from unittest.mock import patch, MagicMock
from PIL import Image


# ── Unit tests — no disk I/O ───────────────────────────────────────────────────

def test_styles_count():
    from app.services.frame_service import STYLES
    assert len(STYLES) == 10


def test_every_style_has_required_keys():
    from app.services.frame_service import STYLES
    required = {"bg", "outer", "inner", "plate_bg", "text_color", "font_file", "bw"}
    for i, style in enumerate(STYLES):
        missing = required - style.keys()
        assert not missing, f"Style {i} missing keys: {missing}"


def test_every_style_color_is_rgb_tuple():
    from app.services.frame_service import STYLES
    for i, s in enumerate(STYLES):
        for key in ("bg", "outer", "inner", "plate_bg", "text_color"):
            val = s[key]
            assert isinstance(val, tuple) and len(val) == 3, \
                f"Style {i} key '{key}' is not an RGB tuple: {val}"
            assert all(0 <= c <= 255 for c in val), \
                f"Style {i} key '{key}' has out-of-range values: {val}"


def test_output_geometry():
    from app.services.frame_service import PHOTO_SIZE, BORDER, PLATE_H, OUTPUT_W, OUTPUT_H
    assert OUTPUT_W == PHOTO_SIZE + BORDER * 2
    assert OUTPUT_H == PHOTO_SIZE + BORDER + PLATE_H


def test_load_font_fallback(tmp_path):
    """_load_font must not crash even if the TTF file doesn't exist."""
    from app.services.frame_service import _load_font
    font = _load_font("nonexistent.ttf", 24)
    assert font is not None


# ── Integration test — actual composition (no external services) ───────────────

def test_compose_portrait_creates_jpg(tmp_path):
    from app.services.frame_service import compose_portrait, OUTPUT_W, OUTPUT_H

    # Create a tiny dummy source image
    src = tmp_path / "photo.jpg"
    img = Image.new("RGB", (100, 100), color=(128, 64, 32))
    img.save(src, "JPEG")

    with patch("app.services.frame_service.settings") as mock_settings:
        mock_settings.frames_dir = str(tmp_path)
        mock_settings.accepted_dir = str(tmp_path / "accepted")
        os.makedirs(mock_settings.accepted_dir, exist_ok=True)

        out = compose_portrait(str(src), birth="1 января 1930", death="1 января 2000", frame_id=0)

    assert os.path.exists(out)
    with Image.open(out) as result:
        assert result.width == OUTPUT_W
        assert result.height == OUTPUT_H


def test_compose_portrait_no_dates(tmp_path):
    """Must not crash when birth/death are None."""
    from app.services.frame_service import compose_portrait

    src = tmp_path / "photo.jpg"
    Image.new("RGB", (200, 200), color=(100, 100, 100)).save(src, "JPEG")

    with patch("app.services.frame_service.settings") as mock_settings:
        mock_settings.frames_dir = str(tmp_path)
        mock_settings.accepted_dir = str(tmp_path / "accepted")
        os.makedirs(mock_settings.accepted_dir, exist_ok=True)

        out = compose_portrait(str(src), birth=None, death=None, frame_id=3)

    assert os.path.exists(out)


def test_compose_portrait_returns_source_on_error(tmp_path):
    """compose_portrait must never raise — returns source_path on failure."""
    from app.services.frame_service import compose_portrait

    fake_path = str(tmp_path / "nonexistent.jpg")

    with patch("app.services.frame_service.settings") as mock_settings:
        mock_settings.frames_dir = str(tmp_path)
        mock_settings.accepted_dir = str(tmp_path / "accepted")

        result = compose_portrait(fake_path, birth="1900", death="2000")

    # Must return the original path, not raise
    assert result == fake_path


def test_all_10_styles_render(tmp_path):
    """Smoke-test every style — none should crash."""
    from app.services.frame_service import compose_portrait, STYLES

    src = tmp_path / "photo.jpg"
    Image.new("RGB", (200, 200), color=(80, 80, 80)).save(src, "JPEG")

    with patch("app.services.frame_service.settings") as mock_settings:
        mock_settings.frames_dir = str(tmp_path)
        mock_settings.accepted_dir = str(tmp_path / "accepted")
        os.makedirs(mock_settings.accepted_dir, exist_ok=True)

        for i in range(len(STYLES)):
            out = compose_portrait(str(src), birth="1 мая 1950", death="1 мая 2010", frame_id=i)
            assert os.path.exists(out), f"Style {i} did not produce output"
