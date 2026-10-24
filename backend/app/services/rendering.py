import io
import zipfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .files import safe_filename


NAME_COLOR = (0, 0, 0, 255)
RENDER_STYLE_VERSION = "solid-black-overlay-pdf-v2"


@dataclass
class RenderResult:
    filename: str
    pdf_path: Path
    preview_path: Path
    font_size: int
    warning: str | None


@dataclass
class RenderedImage:
    image: Image.Image
    name_layer: Image.Image
    name_position: tuple[int, int]
    font_size: int
    warning: str | None


def render_version_path(pdf_path: Path | str) -> Path:
    return Path(f"{pdf_path}.render-version")


def is_render_current(pdf_path: Path | str | None) -> bool:
    if not pdf_path:
        return False
    try:
        return render_version_path(pdf_path).read_text(encoding="utf-8").strip() == RENDER_STYLE_VERSION
    except OSError:
        return False


def _font_fits(font: ImageFont.FreeTypeFont, text: str, max_width: int, max_height: int, vertical_offset: int) -> bool:
    box = font.getbbox(text, stroke_width=0)
    text_w, text_h = box[2] - box[0], box[3] - box[1]
    local_y = (max_height - text_h) // 2 + vertical_offset
    return text_w <= max_width and local_y >= 0 and local_y + text_h <= max_height


def fit_font(text: str, font_path: Path, max_size: int, min_size: int, max_width: int, max_height: int, vertical_offset: int = 0) -> tuple[ImageFont.FreeTypeFont, int, bool]:
    for size in range(max_size, min_size - 1, -1):
        font = ImageFont.truetype(str(font_path), size)
        if _font_fits(font, text, max_width, max_height, vertical_offset):
            return font, size, True
    font = ImageFont.truetype(str(font_path), min_size)
    return font, min_size, False


def render_certificate_image(template_path: Path, font_path: Path, name: str, region: dict) -> RenderedImage:
    base = Image.open(template_path).convert("RGB")
    width, height = base.size
    x = round(region["x"] * width)
    y = round(region["y"] * height)
    box_w = min(max(1, round(region["w"] * width)), width - x)
    box_h = min(max(1, round(region["h"] * height)), height - y)
    vertical_offset = region.get("vertical_offset", 0)
    if region.get("auto_fit", True):
        font, actual_size, fits = fit_font(name, font_path, region["font_size"], region["min_font_size"], box_w, box_h, vertical_offset)
    else:
        actual_size = region["font_size"]
        font = ImageFont.truetype(str(font_path), actual_size)
        fits = _font_fits(font, name, box_w, box_h, vertical_offset)
    bbox = font.getbbox(name)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    mask = Image.new("L", (max(text_w, 1), max(text_h, 1)), 0)
    draw = ImageDraw.Draw(mask)
    draw.text((-bbox[0], -bbox[1]), name, font=font, fill=255)
    solid_name = Image.new("RGBA", (max(text_w, 1), max(text_h, 1)), NAME_COLOR)
    local_x = (box_w - text_w) // 2
    local_y = (box_h - text_h) // 2 + vertical_offset
    layer = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    source_left, source_top = max(0, -local_x), max(0, -local_y)
    source_right, source_bottom = min(text_w, box_w - local_x), min(text_h, box_h - local_y)
    if source_right > source_left and source_bottom > source_top:
        source_box = (source_left, source_top, source_right, source_bottom)
        layer.paste(
            solid_name.crop(source_box),
            (max(local_x, 0), max(local_y, 0)),
            mask.crop(source_box),
        )
    rgba = base.convert("RGBA")
    rgba.alpha_composite(layer, (x, y))
    warning = None if fits else f"Name cannot fit inside the configured area at the minimum font size of {region['min_font_size']}px"
    return RenderedImage(rgba.convert("RGB"), layer, (x, y), actual_size, warning)


def render_preview_png(template_path: Path, font_path: Path, name: str, region: dict) -> tuple[bytes, int, str | None]:
    rendered = render_certificate_image(template_path, font_path, name, region)
    buffer = io.BytesIO()
    rendered.image.save(buffer, "PNG")
    return buffer.getvalue(), rendered.font_size, rendered.warning


def render_certificate(template_path: Path, font_path: Path, output_dir: Path, participant_id: str, name: str, region: dict) -> RenderResult:
    rendered = render_certificate_image(template_path, font_path, name, region)

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{safe_filename(name)}-{participant_id[:8]}"
    preview_path = output_dir / f"{stem}.png"
    pdf_path = output_dir / f"{stem}.pdf"
    rendered.image.save(preview_path, "PNG", optimize=True)
    page_w, page_h = rendered.image.size
    pdf = canvas.Canvas(str(pdf_path), pagesize=(page_w, page_h), pageCompression=1)
    # Keep the uploaded background in its original encoding. Embedding a 1.4 MB
    # JPEG after converting the whole certificate to PNG produced ~9.4 MB PDFs
    # and needlessly prolonged SMTP DATA uploads.
    pdf.drawImage(ImageReader(str(template_path)), 0, 0, width=page_w, height=page_h, preserveAspectRatio=True, mask="auto")
    overlay = io.BytesIO()
    rendered.name_layer.save(overlay, "PNG", optimize=True)
    overlay.seek(0)
    overlay_x, overlay_y_from_top = rendered.name_position
    overlay_w, overlay_h = rendered.name_layer.size
    pdf.drawImage(
        ImageReader(overlay), overlay_x, page_h - overlay_y_from_top - overlay_h,
        width=overlay_w, height=overlay_h, preserveAspectRatio=True, mask="auto",
    )
    pdf.showPage()
    pdf.save()
    render_version_path(pdf_path).write_text(RENDER_STYLE_VERSION, encoding="utf-8")
    return RenderResult(pdf_path.name, pdf_path, preview_path, rendered.font_size, rendered.warning)


def make_zip(files: list[tuple[Path, str]], output: Path) -> Path:
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, name in files:
            archive.write(path, arcname=name)
    return output

