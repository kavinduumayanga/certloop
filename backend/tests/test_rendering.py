from io import BytesIO
from pathlib import Path

from PIL import Image, ImageChops

import app.services.rendering as rendering
from app.services.rendering import is_render_current, render_certificate, render_preview_png


def test_participant_name_is_solid_black_without_color_channels(tmp_path: Path, font_path: Path):
    template = tmp_path / "template.png"
    Image.new("RGB", (800, 500), "white").save(template)
    png, _, _ = render_preview_png(template, font_path, "Ada Lovelace", {"x":.2,"y":.35,"w":.6,"h":.2,"font_size":100,"min_font_size":18,"auto_fit":True,"vertical_offset":0})
    rendered = Image.open(BytesIO(png)).convert("RGB")
    pixels = [rendered.getpixel((x, y)) for y in range(rendered.height) for x in range(rendered.width)]
    changed = [pixel for pixel in pixels if pixel != (255, 255, 255)]
    assert changed
    assert all(red == green == blue for red, green, blue in changed)
    assert (0, 0, 0) in changed


def test_renderer_loads_the_exact_supplied_font_path(tmp_path: Path, font_path: Path, monkeypatch):
    template = tmp_path / "template.png"
    Image.new("RGB", (600, 400), "white").save(template)
    calls = []
    original = rendering.ImageFont.truetype
    def recording_truetype(path, size, *args, **kwargs):
        calls.append(Path(path))
        return original(path, size, *args, **kwargs)
    monkeypatch.setattr(rendering.ImageFont, "truetype", recording_truetype)
    render_preview_png(template, font_path, "Ada", {"x":.2,"y":.35,"w":.6,"h":.2,"font_size":80,"min_font_size":18,"auto_fit":True,"vertical_offset":0})
    assert calls and all(path == font_path for path in calls)


def test_long_name_auto_fits_and_pdf_is_valid(tmp_path: Path, font_path: Path):
    template = tmp_path / "template.png"
    Image.new("RGB", (1200, 800), "white").save(template)
    result = render_certificate(template, font_path, tmp_path / "out", "abc12345", "Alexandria Catherine Montgomery-Smythe", {"x":.2,"y":.4,"w":.6,"h":.14,"font_size":120,"min_font_size":18,"auto_fit":True,"vertical_offset":0})
    assert result.font_size < 120
    assert result.pdf_path.read_bytes().startswith(b"%PDF")
    assert Image.open(result.preview_path).size == (1200, 800)
    assert is_render_current(result.pdf_path)


def test_impossible_name_is_flagged(tmp_path: Path, font_path: Path):
    template = tmp_path / "t.png"; Image.new("RGB", (300, 200), "white").save(template)
    result = render_certificate(template, font_path, tmp_path, "id", "W" * 80, {"x":.4,"y":.4,"w":.1,"h":.05,"font_size":60,"min_font_size":24,"auto_fit":True,"vertical_offset":0})
    assert result.warning


def test_live_preview_and_generated_preview_use_identical_pixels(tmp_path: Path, font_path: Path):
    template = tmp_path / "template.png"
    Image.new("RGB", (900, 600), "white").save(template)
    region = {"x": .15, "y": .38, "w": .7, "h": .18, "font_size": 96, "min_font_size": 20, "auto_fit": True, "vertical_offset": 7}
    live_png, live_size, live_warning = render_preview_png(template, font_path, "Ada Lovelace", region)
    generated = render_certificate(template, font_path, tmp_path / "out", "participant", "Ada Lovelace", region)
    live = Image.open(BytesIO(live_png)).convert("RGB")
    saved = Image.open(generated.preview_path).convert("RGB")
    assert ImageChops.difference(live, saved).getbbox() is None
    assert live_size == generated.font_size
    assert live_warning == generated.warning


def test_name_pixels_are_clipped_to_configured_region(tmp_path: Path, font_path: Path):
    template = tmp_path / "template.png"
    original = Image.new("RGB", (500, 300), "white")
    original.save(template)
    region = {"x": .3, "y": .4, "w": .4, "h": .12, "font_size": 120, "min_font_size": 24, "auto_fit": False, "vertical_offset": 0}
    live_png, _, warning = render_preview_png(template, font_path, "W" * 30, region)
    difference = ImageChops.difference(original, Image.open(BytesIO(live_png)).convert("RGB"))
    changed = difference.getbbox()
    assert warning
    assert changed is not None
    left, top, right, bottom = changed
    assert left >= 150 and top >= 120 and right <= 350 and bottom <= 156


def test_jpeg_template_is_embedded_without_full_page_png_inflation(tmp_path: Path, font_path: Path):
    template = tmp_path / "template.jpg"
    Image.effect_noise((1600, 1000), 80).convert("RGB").save(template, "JPEG", quality=90)
    result = render_certificate(template, font_path, tmp_path / "out", "participant", "Ada Lovelace", {"x":.2,"y":.4,"w":.6,"h":.15,"font_size":100,"min_font_size":20,"auto_fit":True,"vertical_offset":0})
    assert result.pdf_path.stat().st_size < result.preview_path.stat().st_size
    assert result.pdf_path.stat().st_size < template.stat().st_size * 2

