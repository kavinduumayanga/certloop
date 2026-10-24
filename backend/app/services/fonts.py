from pathlib import Path

import reportlab
from PIL import ImageFont


DEFAULT_FONT_NAME = "Bitstream Vera Sans"


def default_font_path() -> Path:
    """Return ReportLab's redistributable, installation-local Vera Sans font."""
    path = Path(reportlab.__file__).resolve().parent / "fonts" / "Vera.ttf"
    if not path.is_file():
        raise RuntimeError("The default Bitstream Vera Sans font is unavailable")
    return path


def resolve_font_path(custom_font_path: str | None) -> Path:
    return Path(custom_font_path) if custom_font_path else default_font_path()


def font_display_name(custom_font_path: str | None) -> str:
    if not custom_font_path:
        return DEFAULT_FONT_NAME
    try:
        family, style = ImageFont.truetype(custom_font_path, 32).getname()
        return family if style.casefold() == "regular" else f"{family} {style}"
    except OSError:
        return "Custom font"
