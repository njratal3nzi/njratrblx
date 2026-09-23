"""Vector icon set drawn with PIL (no external assets, infinite resolution).

Every icon is drawn inside a unit box and scaled, so the same code renders a
24 px list icon or a 512 px export sprite.
"""
from __future__ import annotations

from PIL import Image, ImageDraw

IconFn = object


def _s(points, size: float):
    return [(p[0] * size, p[1] * size) for p in points]


def _w(size: float, ratio: float = 0.09) -> int:
    return max(1, int(round(size * ratio)))


# ------------------------------------------------------------------ icons


def i_play(d: ImageDraw, S: float, c, c2):
    d.polygon(_s([(0.24, 0.14), (0.24, 0.86), (0.86, 0.5)], S), fill=c)


def i_gear(d: ImageDraw, S: float, c, c2):
    cx, cy, r = S / 2, S / 2, S * 0.22
    for i in range(8):
        a = i * 3.14159265 / 4
        x, y = cx + (r + S * 0.1) * _cos(a), cy + (r + S * 0.1) * _sin(a)
        d.rectangle([x - S * 0.075, y - S * 0.075, x + S * 0.075, y + S * 0.075], fill=c)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)
    d.ellipse([cx - r * 0.42, cy - r * 0.42, cx + r * 0.42, cy + r * 0.42], fill=c2)


def i_user(d: ImageDraw, S: float, c, c2):
    d.ellipse([S * 0.32, S * 0.12, S * 0.68, S * 0.48], fill=c)
    d.pieslice([S * 0.2, S * 0.45, S * 0.8, S * 1.05], 180, 360, fill=c)


def i_home(d: ImageDraw, S: float, c, c2):
    d.polygon(_s([(0.5, 0.12), (0.1, 0.46), (0.9, 0.46)], S), fill=c)
    d.rectangle([S * 0.24, S * 0.46, S * 0.76, S * 0.88], fill=c)
    d.rectangle([S * 0.42, S * 0.62, S * 0.58, S * 0.88], fill=c2)


def i_cart(d: ImageDraw, S: float, c, c2):
    w = _w(S, 0.1)
    d.line([S * 0.1, S * 0.18, S * 0.24, S * 0.22, S * 0.34, S * 0.62], fill=c, width=w, joint="curve")
    d.polygon(_s([(0.3, 0.3), (0.88, 0.3), (0.8, 0.62), (0.36, 0.62)], S), fill=c)
    d.ellipse([S * 0.36, S * 0.7, S * 0.48, S * 0.82], fill=c)
    d.ellipse([S * 0.68, S * 0.7, S * 0.8, S * 0.82], fill=c)


def i_coin(d: ImageDraw, S: float, c, c2):
    d.ellipse([S * 0.1, S * 0.1, S * 0.9, S * 0.9], fill=c)
    d.ellipse([S * 0.24, S * 0.24, S * 0.76, S * 0.76], fill=c2)
    d.rectangle([S * 0.45, S * 0.3, S * 0.55, S * 0.7], fill=c)


def i_gem(d: ImageDraw, S: float, c, c2):
    d.polygon(_s([(0.5, 0.08), (0.86, 0.34), (0.5, 0.92), (0.14, 0.34)], S), fill=c)
    d.polygon(_s([(0.5, 0.08), (0.86, 0.34), (0.5, 0.34)], S), fill=c2)
    d.polygon(_s([(0.5, 0.08), (0.14, 0.34), (0.5, 0.34)], S), fill=c2)


def i_diamond(d: ImageDraw, S: float, c, c2):
    d.polygon(_s([(0.5, 0.06), (0.94, 0.5), (0.5, 0.94), (0.06, 0.5)], S), fill=c)
    d.polygon(_s([(0.5, 0.06), (0.94, 0.5), (0.5, 0.5)], S), fill=c2)


def i_sword(d: ImageDraw, S: float, c, c2):
    w = _w(S, 0.11)
    d.line([S * 0.78, S * 0.18, S * 0.32, S * 0.64], fill=c, width=w)
    d.polygon(_s([(0.78, 0.1), (0.9, 0.22), (0.82, 0.3), (0.7, 0.18)], S), fill=c)
    d.line([S * 0.24, S * 0.6, S * 0.46, S * 0.82], fill=c2, width=w + 2)
    d.line([S * 0.14, S * 0.78, S * 0.28, S * 0.92], fill=c, width=w + 4)


def i_shield(d: ImageDraw, S: float, c, c2):
    d.polygon(_s([(0.5, 0.08), (0.88, 0.22), (0.88, 0.52), (0.5, 0.94), (0.12, 0.52), (0.12, 0.22)], S), fill=c)
    d.polygon(_s([(0.5, 0.24), (0.72, 0.33), (0.72, 0.52), (0.5, 0.76), (0.28, 0.52), (0.28, 0.33)], S), fill=c2)


def i_heart(d: ImageDraw, S: float, c, c2):
    d.pieslice([S * 0.1, S * 0.16, S * 0.54, S * 0.6], 180, 360, fill=c)
    d.pieslice([S * 0.46, S * 0.16, S * 0.9, S * 0.6], 180, 360, fill=c)
    d.polygon(_s([(0.12, 0.42), (0.88, 0.42), (0.5, 0.92)], S), fill=c)


def i_star(d: ImageDraw, S: float, c, c2):
    pts = []
    import math
    for k in range(10):
        ang = -math.pi / 2 + k * math.pi / 5
        r = 0.44 if k % 2 == 0 else 0.19
        pts.append((0.5 + r * math.cos(ang), 0.5 + r * math.sin(ang)))
    d.polygon(_s(pts, S), fill=c)


def i_trophy(d: ImageDraw, S: float, c, c2):
    d.pieslice([S * 0.26, S * 0.12, S * 0.74, S * 0.62], 180, 360, fill=c)
    d.rectangle([S * 0.3, S * 0.36, S * 0.7, S * 0.56], fill=c)
    d.ellipse([S * 0.06, S * 0.2, S * 0.3, S * 0.46], outline=c, width=_w(S, 0.07))
    d.ellipse([S * 0.7, S * 0.2, S * 0.94, S * 0.46], outline=c, width=_w(S, 0.07))
    d.rectangle([S * 0.44, S * 0.56, S * 0.56, S * 0.74], fill=c)
    d.rectangle([S * 0.3, S * 0.74, S * 0.7, S * 0.86], fill=c2)


def i_lock(d: ImageDraw, S: float, c, c2):
    d.ellipse([S * 0.28, S * 0.1, S * 0.72, S * 0.54], outline=c, width=_w(S, 0.11))
    d.rounded_rectangle([S * 0.2, S * 0.42, S * 0.8, S * 0.9], radius=S * 0.1, fill=c)
    d.ellipse([S * 0.44, S * 0.58, S * 0.56, S * 0.7], fill=c2)


def i_search(d: ImageDraw, S: float, c, c2):
    d.ellipse([S * 0.14, S * 0.14, S * 0.68, S * 0.68], outline=c, width=_w(S, 0.11))
    d.line([S * 0.64, S * 0.64, S * 0.9, S * 0.9], fill=c, width=_w(S, 0.13))


def i_close(d: ImageDraw, S: float, c, c2):
    w = _w(S, 0.14)
    d.line([S * 0.26, S * 0.26, S * 0.74, S * 0.74], fill=c, width=w)
    d.line([S * 0.74, S * 0.26, S * 0.26, S * 0.74], fill=c, width=w)


def i_plus(d: ImageDraw, S: float, c, c2):
    w = _w(S, 0.14)
    d.line([S * 0.5, S * 0.2, S * 0.5, S * 0.8], fill=c, width=w)
    d.line([S * 0.2, S * 0.5, S * 0.8, S * 0.5], fill=c, width=w)


def i_minus(d: ImageDraw, S: float, c, c2):
    d.line([S * 0.22, S * 0.5, S * 0.78, S * 0.5], fill=c, width=_w(S, 0.14))


def i_check(d: ImageDraw, S: float, c, c2):
    d.line(_s([(0.2, 0.52), (0.42, 0.74), (0.82, 0.28)], S), fill=c, width=_w(S, 0.14), joint="curve")


def i_arrow_r(d: ImageDraw, S: float, c, c2):
    d.line([S * 0.2, S * 0.5, S * 0.72, S * 0.5], fill=c, width=_w(S, 0.12))
    d.polygon(_s([(0.62, 0.28), (0.62, 0.72), (0.88, 0.5)], S), fill=c)


def i_arrow_l(d: ImageDraw, S: float, c, c2):
    d.line([S * 0.28, S * 0.5, S * 0.8, S * 0.5], fill=c, width=_w(S, 0.12))
    d.polygon(_s([(0.38, 0.28), (0.38, 0.72), (0.12, 0.5)], S), fill=c)


def i_back(d: ImageDraw, S: float, c, c2):
    d.line([S * 0.3, S * 0.5, S * 0.86, S * 0.5], fill=c, width=_w(S, 0.1))
    d.line(_s([(0.44, 0.28), (0.24, 0.5), (0.44, 0.72)], S), fill=c, width=_w(S, 0.1), joint="curve")


def i_chat(d: ImageDraw, S: float, c, c2):
    d.rounded_rectangle([S * 0.1, S * 0.16, S * 0.9, S * 0.68], radius=S * 0.14, fill=c)
    d.polygon(_s([(0.26, 0.64), (0.44, 0.64), (0.24, 0.9)], S), fill=c)
    for i, x in enumerate((0.3, 0.5, 0.7)):
        d.ellipse([S * x - S * 0.04, S * 0.38, S * x + S * 0.04, S * 0.46], fill=c2)


def i_bell(d: ImageDraw, S: float, c, c2):
    d.pieslice([S * 0.22, S * 0.14, S * 0.78, S * 0.7], 180, 360, fill=c)
    d.rectangle([S * 0.22, S * 0.42, S * 0.78, S * 0.68], fill=c)
    d.rounded_rectangle([S * 0.16, S * 0.66, S * 0.84, S * 0.76], radius=S * 0.04, fill=c)
    d.ellipse([S * 0.42, S * 0.76, S * 0.58, S * 0.92], fill=c)
    d.ellipse([S * 0.46, S * 0.06, S * 0.54, S * 0.16], fill=c)


def i_crown(d: ImageDraw, S: float, c, c2):
    d.polygon(_s([(0.1, 0.34), (0.3, 0.54), (0.5, 0.24), (0.7, 0.54), (0.9, 0.34), (0.86, 0.74), (0.14, 0.74)], S), fill=c)
    d.rectangle([S * 0.14, S * 0.74, S * 0.86, S * 0.86], fill=c2)


def i_bolt(d: ImageDraw, S: float, c, c2):
    d.polygon(_s([(0.58, 0.06), (0.24, 0.54), (0.46, 0.54), (0.4, 0.94), (0.78, 0.42), (0.54, 0.42)], S), fill=c)


def i_gift(d: ImageDraw, S: float, c, c2):
    d.rectangle([S * 0.14, S * 0.34, S * 0.86, S * 0.88], fill=c)
    d.rectangle([S * 0.44, S * 0.34, S * 0.56, S * 0.88], fill=c2)
    d.rectangle([S * 0.1, S * 0.26, S * 0.9, S * 0.4], fill=c2)
    d.ellipse([S * 0.28, S * 0.1, S * 0.52, S * 0.3], outline=c2, width=_w(S, 0.08))
    d.ellipse([S * 0.48, S * 0.1, S * 0.72, S * 0.3], outline=c2, width=_w(S, 0.08))


def i_bag(d: ImageDraw, S: float, c, c2):
    d.rounded_rectangle([S * 0.16, S * 0.34, S * 0.84, S * 0.9], radius=S * 0.08, fill=c)
    d.arc([S * 0.32, S * 0.12, S * 0.68, S * 0.56], 180, 360, fill=c2, width=_w(S, 0.09))


def i_medal(d: ImageDraw, S: float, c, c2):
    d.polygon(_s([(0.3, 0.06), (0.46, 0.06), (0.56, 0.42), (0.4, 0.42)], S), fill=c2)
    d.ellipse([S * 0.26, S * 0.36, S * 0.74, S * 0.84], fill=c)
    d.ellipse([S * 0.4, S * 0.5, S * 0.6, S * 0.7], fill=c2)


def i_fire(d: ImageDraw, S: float, c, c2):
    d.polygon(_s([(0.5, 0.04), (0.78, 0.42), (0.86, 0.72), (0.5, 0.96), (0.14, 0.72), (0.26, 0.4)], S), fill=c)
    d.polygon(_s([(0.5, 0.36), (0.66, 0.62), (0.5, 0.86), (0.34, 0.62)], S), fill=c2)


def i_key(d: ImageDraw, S: float, c, c2):
    d.ellipse([S * 0.12, S * 0.12, S * 0.48, S * 0.48], outline=c, width=_w(S, 0.11))
    d.line([S * 0.44, S * 0.44, S * 0.88, S * 0.88], fill=c, width=_w(S, 0.11))
    d.line([S * 0.7, S * 0.62, S * 0.8, S * 0.72], fill=c, width=_w(S, 0.1))


def i_logout(d: ImageDraw, S: float, c, c2):
    d.arc([S * 0.14, S * 0.14, S * 0.7, S * 0.86], 100, 260, fill=c, width=_w(S, 0.11))
    d.line([S * 0.46, S * 0.5, S * 0.92, S * 0.5], fill=c, width=_w(S, 0.11))
    d.polygon(_s([(0.78, 0.34), (0.78, 0.66), (0.96, 0.5)], S), fill=c)


def i_refresh(d: ImageDraw, S: float, c, c2):
    d.arc([S * 0.16, S * 0.16, S * 0.84, S * 0.84], 300, 200, fill=c, width=_w(S, 0.11))
    d.polygon(_s([(0.6, 0.1), (0.84, 0.2), (0.62, 0.36)], S), fill=c)


def i_eye(d: ImageDraw, S: float, c, c2):
    d.polygon(_s([(0.06, 0.5), (0.5, 0.2), (0.94, 0.5), (0.5, 0.8)], S), fill=c)
    d.ellipse([S * 0.38, S * 0.38, S * 0.62, S * 0.62], fill=c2)


def i_volume(d: ImageDraw, S: float, c, c2):
    d.polygon(_s([(0.14, 0.36), (0.34, 0.36), (0.54, 0.18), (0.54, 0.82), (0.34, 0.64), (0.14, 0.64)], S), fill=c)
    d.arc([S * 0.5, S * 0.3, S * 0.76, S * 0.7], -60, 60, fill=c, width=_w(S, 0.08))
    d.arc([S * 0.6, S * 0.18, S * 0.94, S * 0.82], -60, 60, fill=c, width=_w(S, 0.08))


def i_music(d: ImageDraw, S: float, c, c2):
    d.line([S * 0.38, S * 0.72, S * 0.38, S * 0.2], fill=c, width=_w(S, 0.09))
    d.line([S * 0.74, S * 0.66, S * 0.74, S * 0.14], fill=c, width=_w(S, 0.09))
    d.line([S * 0.36, S * 0.2, S * 0.76, S * 0.14], fill=c, width=_w(S, 0.09))
    d.ellipse([S * 0.22, S * 0.66, S * 0.46, S * 0.84], fill=c)
    d.ellipse([S * 0.58, S * 0.6, S * 0.82, S * 0.78], fill=c)


def i_rank(d: ImageDraw, S: float, c, c2):
    d.rounded_rectangle([S * 0.14, S * 0.52, S * 0.34, S * 0.88], radius=S * 0.04, fill=c)
    d.rounded_rectangle([S * 0.4, S * 0.3, S * 0.6, S * 0.88], radius=S * 0.04, fill=c)
    d.rounded_rectangle([S * 0.66, S * 0.12, S * 0.86, S * 0.88], radius=S * 0.04, fill=c2)


def i_robux(d: ImageDraw, S: float, c, c2):
    d.rounded_rectangle([S * 0.2, S * 0.2, S * 0.8, S * 0.8], radius=S * 0.12, outline=c, width=_w(S, 0.12))
    d.rounded_rectangle([S * 0.36, S * 0.36, S * 0.64, S * 0.64], radius=S * 0.06, fill=c)


def i_discord(d: ImageDraw, S: float, c, c2):
    d.rounded_rectangle([S * 0.12, S * 0.24, S * 0.88, S * 0.78], radius=S * 0.26, fill=c)
    d.ellipse([S * 0.3, S * 0.42, S * 0.44, S * 0.6], fill=c2)
    d.ellipse([S * 0.56, S * 0.42, S * 0.7, S * 0.6], fill=c2)


def i_target(d: ImageDraw, S: float, c, c2):
    d.ellipse([S * 0.1, S * 0.1, S * 0.9, S * 0.9], outline=c, width=_w(S, 0.08))
    d.ellipse([S * 0.3, S * 0.3, S * 0.7, S * 0.7], outline=c, width=_w(S, 0.08))
    d.ellipse([S * 0.44, S * 0.44, S * 0.56, S * 0.56], fill=c)


def i_ammo(d: ImageDraw, S: float, c, c2):
    for i, x in enumerate((0.24, 0.42, 0.6, 0.78)):
        d.rounded_rectangle([S * (x - 0.05), S * 0.34, S * (x + 0.05), S * 0.86], radius=S * 0.03, fill=c)
        d.polygon(_s([(x - 0.05, 0.34), (x + 0.05, 0.34), (x, 0.18)], S), fill=c2)


def i_map(d: ImageDraw, S: float, c, c2):
    d.polygon(_s([(0.1, 0.28), (0.38, 0.16), (0.62, 0.28), (0.9, 0.16), (0.9, 0.76), (0.62, 0.88), (0.38, 0.76), (0.1, 0.88)], S), fill=c)
    d.line([S * 0.38, S * 0.16, S * 0.38, S * 0.76], fill=c2, width=_w(S, 0.06))
    d.line([S * 0.62, S * 0.28, S * 0.62, S * 0.88], fill=c2, width=_w(S, 0.06))


def i_xp(d: ImageDraw, S: float, c, c2):
    d.ellipse([S * 0.1, S * 0.1, S * 0.9, S * 0.9], outline=c, width=_w(S, 0.1))
    d.pieslice([S * 0.1, S * 0.1, S * 0.9, S * 0.9], -90, 60, fill=c)
    d.ellipse([S * 0.3, S * 0.3, S * 0.7, S * 0.7], fill=c2)


def i_flag(d: ImageDraw, S: float, c, c2):
    d.rectangle([S * 0.2, S * 0.12, S * 0.28, S * 0.9], fill=c)
    d.polygon(_s([(0.28, 0.16), (0.86, 0.28), (0.28, 0.5)], S), fill=c2)


def _cos(a):
    import math
    return math.cos(a)


def _sin(a):
    import math
    return math.sin(a)


ICONS: dict[str, IconFn] = {
    "play": i_play, "settings": i_gear, "user": i_user, "home": i_home, "cart": i_cart,
    "coin": i_coin, "gem": i_gem, "diamond": i_diamond, "sword": i_sword, "shield": i_shield,
    "heart": i_heart, "star": i_star, "trophy": i_trophy, "lock": i_lock, "search": i_search,
    "close": i_close, "plus": i_plus, "minus": i_minus, "check": i_check, "arrow_right": i_arrow_r,
    "arrow_left": i_arrow_l, "back": i_back, "chat": i_chat, "bell": i_bell, "crown": i_crown,
    "bolt": i_bolt, "gift": i_gift, "bag": i_bag, "medal": i_medal, "fire": i_fire,
    "key": i_key, "logout": i_logout, "refresh": i_refresh, "eye": i_eye, "volume": i_volume,
    "music": i_music, "rank": i_rank, "robux": i_robux, "discord": i_discord, "target": i_target,
    "ammo": i_ammo, "map": i_map, "xp": i_xp, "flag": i_flag,
}

ICON_NAMES = sorted(ICONS)


def icon_names() -> list[str]:
    return ICON_NAMES


def render_icon(name: str, size: int, color=(255, 255, 255), secondary=None,
                pad_ratio: float = 0.0, supersample: int = 3) -> Image.Image:
    """Render one icon as an RGBA image with transparent background."""
    fn = ICONS.get(name, i_star)
    secondary = secondary or color
    px = max(8, int(size))
    S = px * max(1, supersample)
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    inner = S * (1 - 2 * pad_ratio)
    off = S * pad_ratio
    d2 = ImageDraw.Draw(img)
    # draw into a translated context by rendering on a sub-image
    sub = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sub)
    fn(sd, inner, color, secondary)
    img.alpha_composite(sub, (int(off), int(off)))
    if S != px:
        img = img.resize((px, px), Image.LANCZOS)
    _ = d, d2
    return img


def render_icon_sheet(names: list[str], size: int = 128, color=(255, 255, 255),
                      secondary=None, columns: int = 8) -> Image.Image:
    """Contact sheet, handy as a single uploadable sprite."""
    names = [n for n in names if n in ICONS] or ICON_NAMES
    rows = max(1, -(-len(names) // columns))
    sheet = Image.new("RGBA", (size * columns, size * rows), (0, 0, 0, 0))
    for i, n in enumerate(names):
        sheet.alpha_composite(render_icon(n, size, color, secondary), ((i % columns) * size, (i // columns) * size))
    return sheet
