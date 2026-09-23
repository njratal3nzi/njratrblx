"""Font discovery, Arabic shaping and text measuring helpers.

Arabic preview text needs (1) a font that carries Arabic glyphs and (2) shaping
+ bidi reordering, because PIL rasterises code points as-is.  Both are optional
dependencies: when they are missing we fall back to the latin label so a design
can always be rendered.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

from .config import FONT_DIR

try:  # optional, installed via requirements.txt
    import arabic_reshaper
    from bidi.algorithm import get_display

    _HAS_SHAPER = True
except Exception:  # pragma: no cover - exercised only without the deps
    arabic_reshaper = None
    get_display = None
    _HAS_SHAPER = False

ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")

# Candidate fonts, best first.  The bundled Amiri font guarantees Arabic support
# anywhere (laptop, CI, Colab) without touching the system.
ARABIC_CANDIDATES = [
    FONT_DIR / "Amiri-Regular.ttf",
    Path("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf"),
    Path("/usr/share/fonts/truetype/kacst/KacstOne.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/amiri/Amiri-Regular.ttf"),
    Path("/System/Library/Fonts/GeezaPro.ttc"),
    Path("C:/Windows/Fonts/arial.ttf"),
]

LATIN_CANDIDATES = [
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"),
    FONT_DIR / "Amiri-Regular.ttf",
    Path("/System/Library/Fonts/Helvetica.ttc"),
    Path("C:/Windows/Fonts/arialbd.ttf"),
]


def _first_existing(candidates: list[Path]) -> Path | None:
    for c in candidates:
        try:
            if c.exists():
                return c
        except OSError:
            continue
    return None


def _find_font() -> Path | None:
    env = Path(__file__).resolve().parent.parent
    override = env / "forge" / "assets" / "fonts"
    extra = list(override.glob("*.ttf")) + list(override.glob("*.otf"))
    return _first_existing(extra + LATIN_CANDIDATES)


FONT_PATH: Path | None = _find_font()
ARABIC_FONT_PATH: Path | None = _first_existing(ARABIC_CANDIDATES)


def has_arabic(text: str) -> bool:
    return bool(ARABIC_RE.search(text or ""))


def arabic_available() -> bool:
    """True when Arabic can be drawn (font with Arabic glyphs present)."""
    return ARABIC_FONT_PATH is not None


@lru_cache(maxsize=512)
def load(size: int, arabic: bool = False, index: int = 0) -> ImageFont.FreeTypeFont:
    size = max(6, int(size))
    path = ARABIC_FONT_PATH if arabic else FONT_PATH
    if path is None:
        return ImageFont.load_default()
    try:
        return ImageFont.truetype(str(path), size=size, index=index)
    except Exception:
        try:
            return ImageFont.truetype(str(FONT_PATH), size=size)
        except Exception:
            return ImageFont.load_default()


def shape(text: str) -> str:
    """Shape Arabic for rasterisation; also normalises presentation forms."""
    if not text:
        return ""
    if not has_arabic(text):
        return text
    if not _HAS_SHAPER:
        return text
    try:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except Exception:
        return text


def auto_font(text: str, size: int) -> ImageFont.FreeTypeFont:
    return load(size, arabic=has_arabic(text))


def measure(draw, text: str, size: int, font: ImageFont.FreeTypeFont | None = None) -> tuple[int, int]:
    font = font or auto_font(text, size)
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def fit_text(draw, text: str, size: int, max_width: int, min_size: int = 9) -> tuple[str, ImageFont.FreeTypeFont]:
    """Shrink, then ellipsise, so `text` fits inside `max_width`."""
    if max_width <= 4:
        return "", load(min_size)
    size = int(size)
    while size > min_size:
        font = auto_font(text, size)
        if measure(draw, text, size, font)[0] <= max_width:
            return text, font
        size -= 1
    font = auto_font(text, min_size)
    w, _ = measure(draw, text, min_size, font)
    if w <= max_width:
        return text, font
    while text and measure(draw, text + "…", min_size, font)[0] > max_width:
        text = text[:-1]
    return (text + "…"), font


def draw_centered(draw, cx: float, cy: float, text: str, size: int, fill, anchor: str = "mm", **kw):
    font = kw.pop("font", None) or auto_font(text, size)
    draw.text((cx, cy), shape(text), font=font, fill=fill, anchor=anchor, **kw)


def strip_arabic(text: str) -> str:
    """Remove Arabic runs (used only when no Arabic font exists)."""
    return ARABIC_RE.sub("", text).strip()


def font_report() -> dict:
    return {
        "latin_font": str(FONT_PATH) if FONT_PATH else None,
        "arabic_font": str(ARABIC_FONT_PATH) if ARABIC_FONT_PATH else None,
        "arabic_renderable": arabic_available(),
        "shaper_installed": _HAS_SHAPER,
    }


def display(text: str, fallback: str = "") -> str:
    """Text to rasterise: Arabic when possible, otherwise the latin fallback."""
    if has_arabic(text):
        if arabic_available():
            return text
        if fallback:
            return fallback
        return strip_arabic(text) or text
    return text


__all__ = [
    "ARABIC_FONT_PATH",
    "FONT_PATH",
    "arabic_available",
    "auto_font",
    "display",
    "draw_centered",
    "fit_text",
    "font_report",
    "has_arabic",
    "load",
    "measure",
    "shape",
    "strip_arabic",
]
