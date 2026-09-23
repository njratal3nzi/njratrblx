"""Colour system: HSL driven palettes + named style presets.

A palette is fully deterministic: (hue, saturation, style) -> colours.  The same
palette feeds the PIL renderer, the Luau theme module and the .rbxmx export, so
what you preview is exactly what Roblox builds.
"""
from __future__ import annotations

import colorsys
import random
from dataclasses import dataclass, field, asdict

# ---------------------------------------------------------------- colour utils


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def hsl(h: float, s: float, l: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hls_to_rgb((h % 360.0) / 360.0, _clamp(l), _clamp(s))
    return int(round(r * 255)), int(round(g * 255)), int(round(b * 255))


def to_hsl(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    h, l, s = colorsys.rgb_to_hls(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)
    return h * 360.0, s, l


def shade(rgb, amount: float) -> tuple[int, int, int]:
    """amount < 0 darkens, > 0 lightens (amount in lightness units)."""
    h, s, l = to_hsl(rgb)
    return hsl(h, s, l + amount)


def mix(a, b, t: float = 0.5) -> tuple[int, int, int]:
    t = _clamp(t)
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def hexs(rgb) -> str:
    return "#%02X%02X%02X" % (int(rgb[0]), int(rgb[1]), int(rgb[2]))


def rgba(rgb, a: float = 1.0):
    return (int(rgb[0]), int(rgb[1]), int(rgb[2]), int(round(_clamp(a) * 255)))


def color3(rgb) -> tuple[float, float, float]:
    """Roblox Color3 channel values (0..1)."""
    return (round(rgb[0] / 255, 5), round(rgb[1] / 255, 5), round(rgb[2] / 255, 5))


def contrast(rgb) -> tuple[int, int, int]:
    """Readable text colour for a background."""
    return (255, 255, 255) if luminance(rgb) < 0.55 else (16, 18, 24)


def luminance(rgb) -> float:
    r, g, b = (v / 255 for v in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


# ---------------------------------------------------------------- palette


@dataclass
class Palette:
    name: str
    name_ar: str
    hue: float
    sat: float
    style: str
    dark: bool = True
    radius: int = 18
    glow: float = 0.55
    grain: float = 0.10
    stroke_w: int = 2
    glass: float = 0.0

    bg_deep: tuple = (0, 0, 0)
    bg_mid: tuple = (0, 0, 0)
    bg_hi: tuple = (0, 0, 0)
    panel: tuple = (0, 0, 0)
    panel_hi: tuple = (0, 0, 0)
    panel_lo: tuple = (0, 0, 0)
    stroke: tuple = (0, 0, 0)
    stroke_hi: tuple = (0, 0, 0)
    accent: tuple = (0, 0, 0)
    accent_hi: tuple = (0, 0, 0)
    accent_lo: tuple = (0, 0, 0)
    accent2: tuple = (0, 0, 0)
    text: tuple = (0, 0, 0)
    text_dim: tuple = (0, 0, 0)
    success: tuple = (0, 0, 0)
    warn: tuple = (0, 0, 0)
    danger: tuple = (0, 0, 0)
    info: tuple = (0, 0, 0)

    def swatch(self) -> dict:
        keys = (
            "bg_deep", "bg_mid", "bg_hi", "panel", "panel_hi", "panel_lo", "stroke",
            "accent", "accent_hi", "accent2", "text", "text_dim", "success", "warn", "danger",
        )
        return {k: hexs(getattr(self, k)) for k in keys}

    def to_dict(self) -> dict:
        d = asdict(self)
        for k, v in d.items():
            if isinstance(v, tuple):
                d[k] = hexs(v)
        d["color3"] = {k: color3(getattr(self, k)) for k in asdict(self) if isinstance(getattr(self, k), tuple)}
        return d

    def rarity(self, index: int = 0):
        order = [self.info, self.success, self.accent2, self.warn, self.danger, self.accent]
        return order[index % len(order)]


# ---------------------------------------------------------------- styles

STYLE_PRESETS: dict[str, dict] = {
    "neon":     {"ar": "نيون",        "hue": 190, "sat": 0.95, "dark": True,  "radius": 20, "glow": 1.0,  "glass": 0.35, "grain": 0.16},
    "cyber":    {"ar": "سايبر",       "hue": 285, "sat": 0.9,  "dark": True,  "radius": 8,  "glow": 0.9,  "glass": 0.2,  "grain": 0.22},
    "royal":    {"ar": "ملكي ذهبي",   "hue": 45,  "sat": 0.85, "dark": True,  "radius": 14, "glow": 0.7,  "glass": 0.3,  "grain": 0.10},
    "ocean":    {"ar": "محيط",        "hue": 205, "sat": 0.8,  "dark": True,  "radius": 22, "glow": 0.6,  "glass": 0.4,  "grain": 0.08},
    "toxic":    {"ar": "سام",         "hue": 95,  "sat": 0.9,  "dark": True,  "radius": 16, "glow": 0.85, "glass": 0.2,  "grain": 0.2},
    "lava":     {"ar": "حمم",         "hue": 12,  "sat": 0.9,  "dark": True,  "radius": 18, "glow": 0.85, "glass": 0.25, "grain": 0.16},
    "candy":    {"ar": "كرتوني",      "hue": 320, "sat": 0.75, "dark": False, "radius": 28, "glow": 0.45, "glass": 0.15, "grain": 0.04},
    "minimal":  {"ar": "بسيط",        "hue": 220, "sat": 0.12, "dark": False, "radius": 12, "glow": 0.15, "glass": 0.0,  "grain": 0.02},
    "midnight": {"ar": "منتصف الليل", "hue": 232, "sat": 0.55, "dark": True,  "radius": 16, "glow": 0.5,  "glass": 0.3,  "grain": 0.1},
    "military": {"ar": "عسكري",       "hue": 78,  "sat": 0.35, "dark": True,  "radius": 4,  "glow": 0.3,  "glass": 0.1,  "grain": 0.3},
    "sunset":   {"ar": "غروب",        "hue": 20,  "sat": 0.85, "dark": True,  "radius": 24, "glow": 0.75, "glass": 0.3,  "grain": 0.08},
    "forest":   {"ar": "غابة",        "hue": 145, "sat": 0.6,  "dark": True,  "radius": 18, "glow": 0.5,  "glass": 0.2,  "grain": 0.1},
    "mono":     {"ar": "أبيض وأسود",  "hue": 0,   "sat": 0.0,  "dark": True,  "radius": 10, "glow": 0.25, "glass": 0.0,  "grain": 0.06},
    "ice":      {"ar": "جليد",        "hue": 195, "sat": 0.5,  "dark": False, "radius": 22, "glow": 0.5,  "glass": 0.5,  "grain": 0.03},
    "grape":    {"ar": "بنفسجي",      "hue": 268, "sat": 0.7,  "dark": True,  "radius": 20, "glow": 0.7,  "glass": 0.35, "grain": 0.1},
    "rose":     {"ar": "وردي",        "hue": 340, "sat": 0.7,  "dark": False, "radius": 26, "glow": 0.4,  "glass": 0.3,  "grain": 0.04},
}

DEFAULT_STYLE = "neon"


def build_palette(style: str = DEFAULT_STYLE, hue: float | None = None, sat: float | None = None,
                  dark: bool | None = None, radius: int | None = None) -> Palette:
    p = STYLE_PRESETS.get(style, STYLE_PRESETS[DEFAULT_STYLE])
    h = float(p["hue"] if hue is None else hue) % 360.0
    s = float(p["sat"] if sat is None else sat)
    is_dark = p["dark"] if dark is None else bool(dark)
    radius = int(p["radius"] if radius is None else radius)
    glow, glass, grain = float(p["glow"]), float(p["glass"]), float(p["grain"])

    if is_dark:
        bg_deep = hsl(h, s * 0.55, 0.05)
        bg_mid = hsl(h, s * 0.5, 0.085)
        bg_hi = hsl(h, s * 0.45, 0.13)
        panel = hsl(h, s * 0.35, 0.11)
        panel_hi = hsl(h, s * 0.3, 0.18)
        panel_lo = hsl(h, s * 0.4, 0.06)
        stroke = hsl(h, s * 0.5, 0.26)
        stroke_hi = hsl(h, s * 0.85, 0.62)
        accent = hsl(h, s, 0.55)
        accent_hi = hsl(h, s, 0.72)
        accent_lo = hsl(h, s * 0.9, 0.34)
        text = hsl(h, 0.25, 0.97)
        text_dim = hsl(h, 0.2, 0.68)
    else:
        bg_deep = hsl(h, s * 0.35, 0.965)
        bg_mid = hsl(h, s * 0.3, 0.93)
        bg_hi = hsl(h, s * 0.25, 1.0)
        panel = hsl(h, s * 0.2, 0.99)
        panel_hi = hsl(h, s * 0.15, 1.0)
        panel_lo = hsl(h, s * 0.25, 0.9)
        stroke = hsl(h, s * 0.35, 0.82)
        stroke_hi = hsl(h, s * 0.8, 0.55)
        accent = hsl(h, s, 0.5)
        accent_hi = hsl(h, s, 0.62)
        accent_lo = hsl(h, s * 0.95, 0.4)
        text = hsl(h, 0.35, 0.14)
        text_dim = hsl(h, 0.2, 0.42)

    accent2 = hsl((h + 42) % 360, s * 0.9, 0.55 if is_dark else 0.48)
    pal = Palette(
        name=style, name_ar=p["ar"], hue=h, sat=s, style=style, dark=is_dark,
        radius=radius, glow=glow, grain=grain, glass=glass,
        stroke_w=2 if style not in ("military", "mono") else 1,
        bg_deep=bg_deep, bg_mid=bg_mid, bg_hi=bg_hi, panel=panel, panel_hi=panel_hi,
        panel_lo=panel_lo, stroke=stroke, stroke_hi=stroke_hi, accent=accent,
        accent_hi=accent_hi, accent_lo=accent_lo, accent2=accent2, text=text,
        text_dim=text_dim,
        success=hsl(145, 0.65, 0.45 if is_dark else 0.38),
        warn=hsl(38, 0.9, 0.52 if is_dark else 0.45),
        danger=hsl(2, 0.78, 0.55 if is_dark else 0.48),
        info=hsl(200, 0.8, 0.55 if is_dark else 0.45),
    )
    return pal


def palette_from_seed(seed_text: str) -> Palette:
    """Deterministic-but-varied palette when the user gives no colour hint."""
    rnd = random.Random(seed_text or "forge")
    style = rnd.choice(list(STYLE_PRESETS))
    p = STYLE_PRESETS[style]
    return build_palette(style, hue=(p["hue"] + rnd.randint(-14, 14)) % 360)


def style_names() -> list[dict]:
    return [{"id": k, "label_en": k.replace("_", " ").title(), "label_ar": v["ar"],
             "swatch": hexs(hsl(v["hue"], v["sat"], 0.5))} for k, v in STYLE_PRESETS.items()]
