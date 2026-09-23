"""PIL rendering engine.

Rule that keeps the export honest: **assets never contain text**.  Every
component is rendered as a transparent (optionally 9-sliceable) background and
the label is drawn by the compositor / emitted as a `TextLabel` in Roblox.  That
way a button exported to Studio is a real, localisable, text-scaled button and
not a flat picture.
"""
from __future__ import annotations

import math
import random
from typing import Callable

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from . import fonts as F
from .spec import Rect
from .themes import Palette, mix, rgba, shade, hsl, hexs
from .icons import render_icon

# ------------------------------------------------------------------ helpers


def _ss(w: float, h: float, rs: int) -> tuple[int, int]:
    return max(1, int(round(w * rs))), max(1, int(round(h * rs)))


def new_canvas(w: float, h: float, rs: int) -> Image.Image:
    return Image.new("RGBA", _ss(w, h, rs), (0, 0, 0, 0))


def _mask(w: int, h: int, radius: float) -> Image.Image:
    radius = max(0, min(radius, min(w, h) / 2))
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    if radius <= 0.5:
        d.rectangle([0, 0, w, h], fill=255)
    else:
        d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    return m


def _ramp_lut(steps: int, top, bottom, mid) -> tuple[list[int], list[int], list[int]]:
    lut_r, lut_g, lut_b = [], [], []
    for i in range(steps):
        t = i / max(1, steps - 1)
        if mid is not None:
            c = mix(top, mid, t * 2) if t < 0.5 else mix(mid, bottom, (t - 0.5) * 2)
        else:
            c = mix(top, bottom, t)
        lut_r.append(int(c[0]))
        lut_g.append(int(c[1]))
        lut_b.append(int(c[2]))
    return lut_r, lut_g, lut_b


def _extend(lut: list[int], steps: int = 256) -> list[int]:
    if steps == len(lut):
        return lut
    out = []
    for i in range(steps):
        t = i / max(1, steps - 1) * (len(lut) - 1)
        lo = int(t)
        hi = min(len(lut) - 1, lo + 1)
        f = t - lo
        out.append(int(round(lut[lo] + (lut[hi] - lut[lo]) * f)))
    return out


def gradient(w: int, h: int, top, bottom: tuple, angle: float = 90.0, mid=None) -> Image.Image:
    """Linear gradient.  angle 90 = top->bottom, 0 = left->right, others = diagonal."""
    w, h = max(1, int(w)), max(1, int(h))
    steps = 256
    rr, gg, bb = _ramp_lut(steps, top, bottom, mid)
    lr, lg, lb = _extend(rr, steps), _extend(gg, steps), _extend(bb, steps)
    if abs(angle - 90) < 1e-6:
        t = Image.linear_gradient("L").resize((w, h), Image.BILINEAR)
    elif abs(angle) < 1e-6 or abs(angle - 180) < 1e-6:
        t = Image.linear_gradient("L").resize((h, w), Image.BILINEAR).transpose(Image.Transpose.ROTATE_90)
        if abs(angle - 180) < 1e-6:
            t = ImageOps.invert(t)
    else:
        # diagonal: build a square t-map then rotate it into the requested direction
        base = Image.linear_gradient("L").resize((steps, steps), Image.BILINEAR)
        rot = base.rotate(90.0 - angle, resample=Image.BILINEAR, expand=False,
                          fillcolor=255 if angle > 90 else 0)
        t = rot.resize((w, h), Image.BILINEAR)
    return Image.merge("RGB", (t.point(lr), t.point(lg), t.point(lb)))


def noise_overlay(w: int, h: int, amount: float, seed: int = 7) -> Image.Image:
    """Cheap film grain: tiny random tile, upscaled + blurred (compresses well too)."""
    if amount <= 0:
        return Image.new("RGBA", (w, h), (0, 0, 0, 0))
    rnd = random.Random(seed)
    tw = th = 48
    tile = Image.new("L", (tw, th))
    tile.putdata([rnd.randint(0, 255) for _ in range(tw * th)])
    img = tile.resize((max(1, w), max(1, h)), Image.BILINEAR).filter(ImageFilter.GaussianBlur(0.7))
    out = Image.new("RGBA", (max(1, w), max(1, h)), (255, 255, 255, 0))
    alpha = img.point(lambda v: int(v * amount * 0.35))
    out.putalpha(alpha)
    return out


def _box(x0: float, y0: float, x1: float, y1: float):
    """Return a valid PIL box or None when the shape would be inverted/degenerate."""
    x0, y0, x1, y1 = float(x0), float(y0), float(x1), float(y1)
    if x1 <= x0 or y1 <= y0:
        return None
    return [x0, y0, x1, y1]


def asset_scale(kind: str, w: float, h: float, rs: float) -> float:
    """Render scale per asset: crisp for small controls, capped for big surfaces."""
    if kind in ("backdrop", "scrim"):
        return 1.0
    cap = {"icon": 256, "avatar": 320, "divider": 96, "knob": 128, "badge": 360,
           "wheel": 620, "minimap": 460, "toggle": 220}.get(kind, 640)
    longest = max(w, h)
    if longest <= 0:
        return 1.0
    if longest * rs <= cap:
        return float(rs)
    return max(1.0, cap / longest)


def glow(img: Image.Image, color, radius: int, strength: float = 1.0) -> Image.Image:
    """Outer glow around the alpha shape."""
    if strength <= 0 or radius <= 0:
        return img
    pad = radius
    base = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    shape = img.split()[3].filter(ImageFilter.GaussianBlur(radius))
    layer = Image.new("RGBA", base.size, rgba(color, min(1.0, strength)))
    layer.putalpha(shape.point(lambda v: int(v * min(1.0, strength))))
    base.alpha_composite(layer)
    base.alpha_composite(img, (pad, pad))
    return base


def inner_highlight(img: Image.Image, color=(255, 255, 255), alpha: float = 0.18, thickness: int = 2) -> Image.Image:
    """Soft top-edge light, gives buttons their 'plastic' read."""
    if alpha <= 0:
        return img
    w, h = img.size
    hi = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(hi)
    t = max(1, min(int(thickness), (w - 1) // 2, (h - 1) // 2))
    if t < 1:
        return img
    for i in range(t):
        a = int(255 * alpha * (1 - i / max(1, t)))
        d.line([(t, i + 1), (w - t, i + 1)], fill=(*color, a))
    hi = hi.filter(ImageFilter.GaussianBlur(max(0.6, t * 0.7)))
    mask = img.split()[3]
    img.alpha_composite(Image.composite(hi, Image.new("RGBA", (w, h), (0, 0, 0, 0)), mask))
    return img


def inner_shadow(img: Image.Image, color=(0, 0, 0), alpha: float = 0.35, thickness: int = 3) -> Image.Image:
    w, h = img.size
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(sh)
    t = max(1, min(int(thickness), (w - 1) // 2, (h - 1) // 2))
    for i in range(t):
        a = int(255 * alpha * (1 - i / max(1, t)))
        d.rectangle([i, i, w - 1 - i, h - 1 - i], outline=(*color, a))
    sh = sh.filter(ImageFilter.GaussianBlur(max(0.6, t * 0.8)))
    mask = img.split()[3]
    img.alpha_composite(Image.composite(sh, Image.new("RGBA", (w, h), (0, 0, 0, 0)), mask))
    return img


def apply_mask(img: Image.Image, mask: Image.Image) -> Image.Image:
    a = img.split()[3]
    from PIL import ImageChops
    img.putalpha(ImageChops.multiply(a, mask))
    return img


def rounded_panel(w: float, h: float, rs: int, radius: float, top, bottom,
                  stroke=None, stroke_w: float = 2.0, mid=None, angle: float = 90.0,
                  grain: float = 0.0) -> Image.Image:
    W, H = _ss(w, h, rs)
    R = radius * rs
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    grad = gradient(W, H, top, bottom, angle=angle, mid=mid).convert("RGBA")
    m = _mask(W, H, R)
    img.paste(grad, (0, 0), m)
    if grain > 0:
        n = noise_overlay(W, H, grain)
        img.alpha_composite(Image.composite(n, Image.new("RGBA", (W, H), (0, 0, 0, 0)), m))
    if stroke is not None and stroke_w > 0:
        d = ImageDraw.Draw(img)
        sw = max(1, min(int(round(stroke_w * rs)), max(1, min(W, H) // 2)))
        inset = sw / 2
        box = _box(inset, inset, W - 1 - inset, H - 1 - inset)
        if box:
            d.rounded_rectangle(box, radius=max(0, R - inset), outline=rgba(stroke, 1.0), width=sw)
    return img


# ------------------------------------------------------------------ parts
# Each renderer: (w, h, pal, props, rs) -> PIL RGBA image (logical size w x h)


def _radius(props, pal: Palette, w: float, h: float) -> float:
    r = props.get("radius", pal.radius)
    if isinstance(r, str) and r.endswith("%"):
        return min(w, h) * float(r[:-1]) / 100.0
    return float(r)


def part_panel(w, h, pal: Palette, props: dict, rs: int) -> Image.Image:
    r = _radius(props, pal, w, h)
    top = props.get("top") or pal.panel_hi
    bottom = props.get("bottom") or pal.panel_lo
    stroke = props.get("stroke", pal.stroke)
    sw = props.get("stroke_w", pal.stroke_w)
    img = rounded_panel(w, h, rs, r, top, bottom, stroke=stroke, stroke_w=sw, grain=pal.grain * 0.6)
    img = inner_highlight(img, alpha=0.10, thickness=max(2, int(2 * rs)))
    if props.get("inset"):
        img = inner_shadow(img, alpha=0.28, thickness=max(2, int(3 * rs)))
    if props.get("header_h"):
        hh = int(props["header_h"] * rs)
        W, H = img.size
        head = Image.new("RGBA", (W, hh), (0, 0, 0, 0))
        g = gradient(W, hh, mix(top, pal.accent, 0.22), top).convert("RGBA")
        hm = _mask(W, hh, r)
        hm2 = Image.new("L", (W, hh), 255)
        from PIL import ImageChops
        head.paste(g, (0, 0), ImageChops.multiply(hm, hm2))
        img.alpha_composite(head, (0, 0))
        d = ImageDraw.Draw(img)
        d.line([(0, hh), (W, hh)], fill=rgba(mix(pal.stroke, pal.accent, 0.5), 0.55), width=max(1, rs))
    return img


def part_button(w, h, pal: Palette, props: dict, rs: int) -> Image.Image:
    variant = props.get("variant", "primary")
    state = props.get("state", "idle")
    r = _radius(props, pal, w, h)
    if variant == "primary":
        top, bottom = pal.accent_hi, pal.accent_lo
        stroke = mix(pal.accent_hi, (255, 255, 255), 0.35)
    elif variant == "secondary":
        top, bottom = pal.panel_hi, pal.panel_lo
        stroke = pal.stroke
    elif variant == "ghost":
        top = bottom = mix(pal.panel, (0, 0, 0), 0.2)
        stroke = mix(pal.stroke, pal.text, 0.15)
    elif variant == "danger":
        top, bottom = shade(pal.danger, 0.12), shade(pal.danger, -0.16)
        stroke = mix(pal.danger, (255, 255, 255), 0.3)
    elif variant == "success":
        top, bottom = shade(pal.success, 0.12), shade(pal.success, -0.16)
        stroke = mix(pal.success, (255, 255, 255), 0.3)
    else:  # flat
        top = bottom = pal.panel
        stroke = pal.stroke

    if state == "hover":
        top = mix(top, (255, 255, 255), 0.14)
        bottom = mix(bottom, (255, 255, 255), 0.06)
    elif state == "pressed":
        top = mix(top, (0, 0, 0), 0.22)
        bottom = mix(bottom, (0, 0, 0), 0.16)
    elif state == "disabled":
        top = mix(top, pal.panel, 0.7)
        bottom = mix(bottom, pal.panel, 0.7)
        stroke = mix(stroke, pal.panel, 0.7)

    sw = props.get("stroke_w", pal.stroke_w)
    img = rounded_panel(w, h, rs, r, top, bottom, stroke=stroke, stroke_w=sw,
                        mid=mix(top, bottom, 0.55), grain=pal.grain * 0.35)
    if variant == "ghost":
        img.putalpha(img.split()[3].point(lambda v: int(v * 0.55)))
        d = ImageDraw.Draw(img)
        box = _box(rs, rs, img.width - rs, img.height - rs)
        if box:
            d.rounded_rectangle(box, radius=max(0, r * rs - rs),
                                outline=rgba(stroke, 0.9), width=max(1, int(sw * rs)))
    img = inner_highlight(img, alpha=0.26 if state != "pressed" else 0.08, thickness=max(2, int(2.5 * rs)))
    if state == "pressed":
        img = inner_shadow(img, alpha=0.4, thickness=max(2, int(4 * rs)))
    if state == "disabled":
        img.putalpha(img.split()[3].point(lambda v: int(v * 0.6)))
    if variant in ("primary", "danger", "success") and state == "idle" and pal.glow > 0.3:
        # accent sheen across the lower half
        W, H = img.size
        sheen = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sheen)
        sd.ellipse([-W * 0.2, H * 0.55, W * 1.2, H * 1.9], fill=rgba(mix(bottom, (255, 255, 255), 0.25), 0.35))
        sheen = sheen.filter(ImageFilter.GaussianBlur(H * 0.12))
        img.alpha_composite(Image.composite(sheen, Image.new("RGBA", (W, H), (0, 0, 0, 0)), img.split()[3]))
    return img


def part_field(w, h, pal: Palette, props: dict, rs: int) -> Image.Image:
    r = _radius(props, pal, w, h)
    img = rounded_panel(w, h, rs, r, mix(pal.panel_lo, (0, 0, 0), 0.25), mix(pal.panel_lo, (0, 0, 0), 0.1),
                        stroke=props.get("stroke", mix(pal.stroke, pal.panel_lo, 0.4)),
                        stroke_w=props.get("stroke_w", max(1, pal.stroke_w - 1)), grain=pal.grain * 0.3)
    img = inner_shadow(img, alpha=0.45, thickness=max(2, int(4 * rs)))
    if props.get("focus"):
        d = ImageDraw.Draw(img)
        box = _box(rs, rs, img.width - rs, img.height - rs)
        if box:
            d.rounded_rectangle(box, radius=max(0, r * rs - rs),
                                outline=rgba(pal.accent, 0.95), width=max(1, int(2 * rs)))
    return img


def part_track(w, h, pal: Palette, props: dict, rs: int) -> Image.Image:
    r = min(h / 2, _radius(props, pal, w, h))
    img = rounded_panel(w, h, rs, r, mix(pal.panel_lo, (0, 0, 0), 0.35), mix(pal.panel_lo, (0, 0, 0), 0.15),
                        stroke=mix(pal.stroke, pal.panel_lo, 0.5), stroke_w=max(1, pal.stroke_w - 1))
    return inner_shadow(img, alpha=0.5, thickness=max(2, int(3 * rs)))


def part_fill(w, h, pal: Palette, props: dict, rs: int) -> Image.Image:
    r = min(h / 2, _radius(props, pal, w, h))
    c = props.get("color", pal.accent)
    img = rounded_panel(w, h, rs, r, mix(c, (255, 255, 255), 0.28), shade(c, -0.18),
                        stroke=mix(c, (255, 255, 255), 0.35), stroke_w=max(1, pal.stroke_w - 1))
    img = inner_highlight(img, alpha=0.35, thickness=max(2, int(2 * rs)))
    if props.get("stripes"):
        W, H = img.size
        st = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(st)
        step = max(6, int(H * 0.9))
        for x in range(-H, W + H, step):
            sd.line([(x, H), (x + H, 0)], fill=rgba((255, 255, 255), 0.14), width=max(2, step // 3))
        img.alpha_composite(Image.composite(st, Image.new("RGBA", (W, H), (0, 0, 0, 0)), img.split()[3]))
    return img


def part_knob(w, h, pal: Palette, props: dict, rs: int) -> Image.Image:
    W, H = _ss(w, h, rs)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    c = props.get("color", pal.panel_hi)
    d = ImageDraw.Draw(img)
    d.ellipse([rs, rs, W - rs, H - rs], fill=rgba(mix(c, (255, 255, 255), 0.5), 1.0))
    d.ellipse([rs, rs, W - rs, H - rs], outline=rgba(mix(c, pal.stroke, 0.5), 1.0), width=max(1, int(2 * rs)))
    d.ellipse([W * 0.28, H * 0.28, W * 0.72, H * 0.72], fill=rgba(props.get("dot", pal.accent), 1.0))
    return img


def part_toggle(w, h, pal: Palette, props: dict, rs: int) -> Image.Image:
    on = bool(props.get("on", True))
    W, H = _ss(w, h, rs)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = H / 2
    track = mix(pal.accent, pal.accent_lo, 0.25) if on else mix(pal.panel_lo, (0, 0, 0), 0.3)
    d.rounded_rectangle([0, 0, W - 1, H - 1], radius=r, fill=rgba(track, 1.0))
    d.rounded_rectangle([0, 0, W - 1, H - 1], radius=r,
                        outline=rgba(pal.accent if on else pal.stroke, 0.9), width=max(1, int(pal.stroke_w * rs)))
    kd = int(H * 0.36)
    kx = W - kd - int(H * 0.14) if on else int(H * 0.14)
    d.ellipse([kx, int(H * 0.14), kx + kd, int(H * 0.14) + kd], fill=rgba((250, 250, 252), 1.0))
    d.ellipse([kx, int(H * 0.14), kx + kd, int(H * 0.14) + kd], outline=rgba(mix(pal.stroke, (0, 0, 0), 0.3), 0.6),
              width=max(1, rs))
    return img


def part_slot(w, h, pal: Palette, props: dict, rs: int) -> Image.Image:
    rarity = props.get("rarity", 0)
    rc = props.get("rarity_color") or pal.rarity(rarity)
    r = _radius(props, pal, w, h)
    img = rounded_panel(w, h, rs, r, mix(pal.panel_hi, (0, 0, 0), 0.05), mix(pal.panel_lo, (0, 0, 0), 0.15),
                        stroke=mix(pal.stroke, rc, 0.55), stroke_w=props.get("stroke_w", pal.stroke_w + 1))
    img = inner_shadow(img, alpha=0.4, thickness=max(2, int(4 * rs)))
    W, H = img.size
    # rarity corner shine + top tint
    tint = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    td = ImageDraw.Draw(tint)
    td.polygon([(0, 0), (W, 0), (W, H * 0.35), (0, H * 0.7)], fill=rgba(rc, 0.16))
    td.ellipse([-W * 0.3, -H * 0.6, W * 0.7, H * 0.25], fill=rgba(mix(rc, (255, 255, 255), 0.4), 0.2))
    img.alpha_composite(Image.composite(tint, Image.new("RGBA", (W, H), (0, 0, 0, 0)), img.split()[3]))
    if props.get("selected"):
        d = ImageDraw.Draw(img)
        box = _box(rs * 2, rs * 2, W - rs * 2, H - rs * 2)
        if box:
            d.rounded_rectangle(box, radius=max(0, r * rs - rs * 2),
                                outline=rgba(pal.accent_hi, 1.0), width=max(2, int(2.5 * rs)))
    return img


def part_badge(w, h, pal: Palette, props: dict, rs: int) -> Image.Image:
    r = min(h / 2, _radius(props, pal, w, h))
    c = props.get("color", pal.accent)
    img = rounded_panel(w, h, rs, r, mix(c, (255, 255, 255), 0.3), shade(c, -0.14),
                        stroke=mix(c, (255, 255, 255), 0.45), stroke_w=max(1, pal.stroke_w))
    return inner_highlight(img, alpha=0.3, thickness=max(1, int(2 * rs)))


def part_avatar(w, h, pal: Palette, props: dict, rs: int) -> Image.Image:
    W, H = _ss(w, h, rs)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ring = props.get("ring", pal.accent)
    rw = max(1, min(int(W * props.get("ring_w", 0.055)), max(1, min(W, H) // 2 - 2)))
    d.ellipse([0, 0, W - 1, H - 1], fill=rgba(ring, 1.0))
    d.ellipse([rw, rw, W - 1 - rw, H - 1 - rw], fill=rgba(mix(pal.panel_hi, pal.accent, 0.25), 1.0))
    inner = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    idr = ImageDraw.Draw(inner)
    g = gradient(W, H, mix(pal.accent, (255, 255, 255), 0.2), mix(pal.panel_lo, (0, 0, 0), 0.1)).convert("RGBA")
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).ellipse([rw + rs * 2, rw + rs * 2, W - rw - rs * 2, H - rw - rs * 2], fill=255)
    inner.paste(g, (0, 0), m)
    # simple silhouette so an empty avatar does not look broken
    idr2 = ImageDraw.Draw(inner)
    cx, cy = W / 2, H / 2
    idr2.ellipse([cx - W * 0.16, cy - H * 0.22, cx + W * 0.16, cy + H * 0.06], fill=rgba(mix(pal.text, pal.accent, 0.5), 0.85))
    idr2.pieslice([cx - W * 0.3, cy - H * 0.02, cx + W * 0.3, cy + H * 0.5], 180, 360,
                  fill=rgba(mix(pal.text, pal.accent, 0.5), 0.85))
    img.alpha_composite(Image.composite(inner, Image.new("RGBA", (W, H), (0, 0, 0, 0)), m))
    if props.get("crown"):
        cr = render_icon("crown", int(W * 0.42), mix(pal.warn, (255, 255, 255), 0.15), mix(pal.warn, (0, 0, 0), 0.25))
        img.alpha_composite(cr, (int(W / 2 - cr.width / 2), -int(cr.height * 0.45)))
    return img


def part_divider(w, h, pal: Palette, props: dict, rs: int) -> Image.Image:
    W, H = _ss(w, h, rs)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = Image.new("L", (W, 1), 0)
    gd = ImageDraw.Draw(g)
    for x in range(W):
        t = abs(x / max(1, W - 1) * 2 - 1)
        gd.point((x, 0), fill=int(255 * (1 - t) ** 1.4))
    line = Image.new("RGBA", (W, max(1, H)), rgba(props.get("color", mix(pal.stroke, pal.accent, 0.4)), 1.0))
    line.putalpha(g.resize((W, max(1, H)), Image.BILINEAR))
    img.alpha_composite(line)
    return img


def part_tab(w, h, pal: Palette, props: dict, rs: int) -> Image.Image:
    active = bool(props.get("active"))
    r = _radius(props, pal, w, h)
    if active:
        img = rounded_panel(w, h, rs, r, mix(pal.accent, (255, 255, 255), 0.22), mix(pal.accent_lo, (0, 0, 0), 0.05),
                            stroke=mix(pal.accent_hi, (255, 255, 255), 0.4), stroke_w=pal.stroke_w)
        img = inner_highlight(img, alpha=0.3, thickness=max(2, int(2 * rs)))
    else:
        img = rounded_panel(w, h, rs, r, mix(pal.panel, (255, 255, 255), 0.04), mix(pal.panel, (0, 0, 0), 0.12),
                            stroke=mix(pal.stroke, pal.panel, 0.5), stroke_w=max(1, pal.stroke_w - 1),
                            grain=pal.grain * 0.3)
        img.putalpha(img.split()[3].point(lambda v: int(v * 0.85)))
    return img


def part_toast(w, h, pal: Palette, props: dict, rs: int) -> Image.Image:
    r = _radius(props, pal, w, h)
    accent = props.get("color", pal.success)
    img = rounded_panel(w, h, rs, r, mix(pal.panel_hi, (255, 255, 255), 0.06), pal.panel_lo,
                        stroke=mix(pal.stroke, accent, 0.4), stroke_w=pal.stroke_w, grain=pal.grain * 0.5)
    W, H = img.size
    bar = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bar)
    bw = max(4, int(W * 0.012))
    if props.get("side", "left") == "left":
        bd.rectangle([0, 0, bw, H], fill=rgba(accent, 1.0))
    else:
        bd.rectangle([W - bw, 0, W, H], fill=rgba(accent, 1.0))
    img.alpha_composite(Image.composite(bar, Image.new("RGBA", (W, H), (0, 0, 0, 0)), img.split()[3]))
    return img


def part_row(w, h, pal: Palette, props: dict, rs: int) -> Image.Image:
    r = _radius(props, pal, w, h)
    idx = int(props.get("index", 0))
    top = props.get("top") or (mix(pal.panel_hi, (255, 255, 255), 0.05) if idx % 2 == 0 else pal.panel)
    bottom = props.get("bottom") or (mix(pal.panel_lo, (0, 0, 0), 0.05) if idx % 2 == 0 else mix(pal.panel_lo, (0, 0, 0), 0.12))
    img = rounded_panel(w, h, rs, r, top, bottom, stroke=mix(pal.stroke, pal.panel, 0.4),
                        stroke_w=max(1, pal.stroke_w - 1))
    if props.get("highlight"):
        W, H = img.size
        hl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        hd = ImageDraw.Draw(hl)
        hd.rectangle([0, 0, max(2, int(W * 0.006)), H], fill=rgba(pal.accent, 1.0))
        hd.rectangle([0, 0, W, H], fill=rgba(pal.accent, 0.10))
        img.alpha_composite(Image.composite(hl, Image.new("RGBA", (W, H), (0, 0, 0, 0)), img.split()[3]))
    return img


def part_icon(w, h, pal: Palette, props: dict, rs: int) -> Image.Image:
    name = props.get("icon", "star")
    size = int(min(w, h))
    color = props.get("color", pal.text)
    secondary = props.get("secondary", mix(color, pal.panel_lo, 0.5))
    img = render_icon(name, int(size * rs), color, secondary, pad_ratio=props.get("pad", 0.06), supersample=1)
    if props.get("plate"):
        plate = rounded_panel(w, h, rs, _radius(props, pal, w, h), pal.panel_hi, pal.panel_lo,
                              stroke=pal.stroke, stroke_w=pal.stroke_w)
        plate.alpha_composite(img.resize((int(size * rs * 0.62),) * 2, Image.LANCZOS),
                              (int((plate.width - size * rs * 0.62) / 2), int((plate.height - size * rs * 0.62) / 2)))
        return plate
    return img


def part_wheel(w, h, pal: Palette, props: dict, rs: int) -> Image.Image:
    W, H = _ss(w, h, rs)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    n = int(props.get("segments", 8))
    cx, cy, R = W / 2, H / 2, min(W, H) / 2 - 2 * rs
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=rgba(mix(pal.panel_lo, (0, 0, 0), 0.3), 1.0))
    for i in range(n):
        a0 = -90 + i * 360 / n
        a1 = a0 + 360 / n
        c = pal.rarity(i) if i % 3 else mix(pal.accent, (255, 255, 255), 0.15)
        d.pieslice([cx - R, cy - R, cx + R, cy + R], a0, a1, fill=rgba(mix(c, pal.panel_lo, 0.25), 1.0),
                   outline=rgba(mix(pal.stroke, (255, 255, 255), 0.2), 0.9), width=max(1, int(1.5 * rs)))
    hub = R * 0.22
    d.ellipse([cx - hub, cy - hub, cx + hub, cy + hub], fill=rgba(pal.panel_hi, 1.0),
              outline=rgba(pal.accent_hi, 1.0), width=max(2, int(2.5 * rs)))
    d.polygon([(cx - R * 0.06, cy - R * 0.98), (cx + R * 0.06, cy - R * 0.98), (cx, cy - R * 0.8)],
              fill=rgba(mix(pal.warn, (255, 255, 255), 0.2), 1.0))
    return img


def part_minimap(w, h, pal: Palette, props: dict, rs: int) -> Image.Image:
    r = _radius(props, pal, w, h)
    img = rounded_panel(w, h, rs, r, mix(pal.panel_lo, (0, 0, 0), 0.4), mix(pal.panel_lo, (0, 0, 0), 0.1),
                        stroke=mix(pal.stroke, pal.accent, 0.3), stroke_w=pal.stroke_w, grain=pal.grain)
    W, H = img.size
    g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(g)
    step = max(8, int(min(W, H) / 8))
    for x in range(0, W, step):
        gd.line([(x, 0), (x, H)], fill=rgba(mix(pal.stroke, pal.accent, 0.4), 0.35), width=1)
    for y in range(0, H, step):
        gd.line([(0, y), (W, y)], fill=rgba(mix(pal.stroke, pal.accent, 0.4), 0.35), width=1)
    rnd = random.Random(11)
    for _ in range(14):
        x, y = rnd.uniform(0.05, 0.95) * W, rnd.uniform(0.05, 0.95) * H
        rr = rnd.uniform(0.008, 0.03) * min(W, H)
        gd.ellipse([x - rr, y - rr, x + rr, y + rr], fill=rgba(mix(pal.accent2, (255, 255, 255), 0.2), 0.7))
    pr = min(W, H) * 0.035
    gd.polygon([(W / 2 - pr, H / 2 + pr), (W / 2 + pr, H / 2 + pr), (W / 2, H / 2 - pr * 1.6)],
               fill=rgba(pal.warn, 1.0))
    img.alpha_composite(Image.composite(g, Image.new("RGBA", (W, H), (0, 0, 0, 0)), img.split()[3]))
    return img


def part_backdrop(w, h, pal: Palette, props: dict, rs: int) -> Image.Image:
    """Full-screen background: layered gradients, glow orbs, grid, vignette."""
    W, H = _ss(w, h, rs)
    variant = props.get("variant", "nebula")
    seed = int(props.get("seed", 3))
    rnd = random.Random(seed)
    img = gradient(W, H, pal.bg_deep, mix(pal.bg_mid, pal.bg_deep, 0.3), angle=115).convert("RGBA")
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    if variant in ("nebula", "aurora", "glow"):
        n = 6 if variant == "nebula" else 4
        for i in range(n):
            cx = rnd.uniform(-0.1, 1.1) * W
            cy = rnd.uniform(-0.1, 1.1) * H
            rad = rnd.uniform(0.15, 0.45) * max(W, H)
            c = [pal.accent, pal.accent2, mix(pal.accent, (255, 255, 255), 0.3), pal.info][i % 4]
            d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=rgba(c, 0.22))
        layer = layer.filter(ImageFilter.GaussianBlur(max(20, W // 28)))
        img.alpha_composite(layer)
    if variant in ("grid", "tech", "cyber"):
        g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(g)
        step = max(24, W // 26)
        for x in range(0, W + step, step):
            gd.line([(x, 0), (x, H)], fill=rgba(mix(pal.stroke, pal.accent, 0.5), 0.3), width=max(1, rs))
        for y in range(0, H + step, step):
            gd.line([(0, y), (W, y)], fill=rgba(mix(pal.stroke, pal.accent, 0.5), 0.3), width=max(1, rs))
        g = g.filter(ImageFilter.GaussianBlur(0.4))
        img.alpha_composite(g)
        # perspective floor lines
        fl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        fd = ImageDraw.Draw(fl)
        hy = int(H * 0.62)
        for i in range(-8, 9):
            fd.line([(W / 2 + i * W * 0.05, hy), (W / 2 + i * W * 0.42, H)],
                    fill=rgba(pal.accent, 0.25), width=max(1, rs))
        for k in range(1, 9):
            y = hy + (H - hy) * (k / 9) ** 2
            fd.line([(0, y), (W, y)], fill=rgba(pal.accent, 0.18), width=max(1, rs))
        img.alpha_composite(fl.filter(ImageFilter.GaussianBlur(0.8)))
    if variant in ("rays", "burst"):
        rays = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        rd = ImageDraw.Draw(rays)
        cx, cy = W / 2, H * 0.42
        for i in range(24):
            a = math.radians(i * 15 + 7)
            ln = max(W, H)
            rd.polygon([(cx, cy), (cx + math.cos(a) * ln, cy + math.sin(a) * ln),
                        (cx + math.cos(a + 0.06) * ln, cy + math.sin(a + 0.06) * ln)],
                       fill=rgba(mix(pal.accent, (255, 255, 255), 0.4), 0.14))
        img.alpha_composite(rays.filter(ImageFilter.GaussianBlur(6)))
    if variant in ("dust", "particles", "stars"):
        p = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        pd = ImageDraw.Draw(p)
        for _ in range(int(W * H / 9000)):
            x, y = rnd.uniform(0, W), rnd.uniform(0, H)
            rr = rnd.uniform(0.6, 2.6) * rs
            pd.ellipse([x - rr, y - rr, x + rr, y + rr], fill=rgba((255, 255, 255), rnd.uniform(0.15, 0.6)))
        img.alpha_composite(p.filter(ImageFilter.GaussianBlur(0.5)))

    # grain + vignette
    if pal.grain > 0:
        img.alpha_composite(noise_overlay(W, H, pal.grain))
    vig = Image.new("L", (W, H), 0)
    vd = ImageDraw.Draw(vig)
    vd.ellipse([-W * 0.25, -H * 0.35, W * 1.25, H * 1.35], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(max(30, W // 12)))
    dark = Image.new("RGBA", (W, H), rgba(mix(pal.bg_deep, (0, 0, 0), 0.4), 1.0))
    from PIL import ImageChops
    img.alpha_composite(Image.composite(dark, Image.new("RGBA", (W, H), (0, 0, 0, 0)), ImageChops.invert(vig)))
    return img


def part_scrim(w, h, pal: Palette, props: dict, rs: int) -> Image.Image:
    """Dark readability layer behind text-heavy areas."""
    W, H = _ss(w, h, rs)
    g = gradient(W, H, (0, 0, 0), (0, 0, 0), angle=90).convert("RGBA")
    g.putalpha(Image.new("L", (W, H), int(255 * float(props.get("alpha", 0.45)))))
    return g


RENDERERS: dict[str, Callable] = {
    "panel": part_panel,
    "button": part_button,
    "field": part_field,
    "track": part_track,
    "fill": part_fill,
    "knob": part_knob,
    "toggle": part_toggle,
    "slot": part_slot,
    "badge": part_badge,
    "avatar": part_avatar,
    "divider": part_divider,
    "tab": part_tab,
    "toast": part_toast,
    "row": part_row,
    "icon": part_icon,
    "wheel": part_wheel,
    "minimap": part_minimap,
    "backdrop": part_backdrop,
    "scrim": part_scrim,
}

SLICEABLE = {"panel", "button", "field", "track", "fill", "badge", "tab", "toast", "row", "slot"}


def render(renderer: str, w: float, h: float, pal: Palette, props: dict, rs: int) -> Image.Image:
    fn = RENDERERS.get(renderer)
    if fn is None:
        return new_canvas(w, h, rs)
    return fn(max(1.0, w), max(1.0, h), pal, props or {}, max(0.5, float(rs)))


def slice_center(renderer: str, w: float, h: float, props: dict, pal: Palette, rs: int):
    """Roblox SliceCenter in *source* pixels, or None when slicing makes no sense."""
    if renderer not in SLICEABLE:
        return None
    W, H = _ss(w, h, rs)
    r = _radius(props, pal, w, h) * rs
    if renderer in ("track", "fill", "badge"):
        r = min(H / 2, r)
    r = max(1.0, min(r, min(W, H) / 2 - 1))
    return (round(r, 2), round(r, 2), round(W - r, 2), round(H - r, 2))


# ------------------------------------------------------------------ text layout

def text_color(props: dict, pal: Palette):
    c = props.get("color")
    if c:
        return c
    return pal.text


def draw_label(img: Image.Image, node, pal: Palette, scale: float = 1.0) -> None:
    """Draw a node's label onto an already-composited image (preview only)."""
    props = node.props
    label = props.get("label")
    if not label:
        return
    rtl = bool(props.get("rtl", False))
    size = int(max(8, props.get("font_size", 28) * scale))
    color = text_color(props, pal)
    align = props.get("align", "center")
    if align not in ("left", "right", "center"):
        align = "center"
    if rtl and align == "left":
        side = "right"
    elif rtl and align == "right":
        side = "left"
    else:
        side = align
    d = ImageDraw.Draw(img)
    r = node.rect
    pad_x = float(props.get("pad_x", 18))
    px = {"left": r.x + pad_x, "right": r.right - pad_x, "center": r.cx}[side]
    anchor = {"left": "lm", "right": "rm", "center": "mm"}[side]
    maxw = max(4.0, r.w - 2 * pad_x)
    if props.get("icon"):
        maxw -= size * 1.4
    txt = F.display(str(label), props.get("label_en", ""))
    txt, font = F.fit_text(d, txt, size, maxw, min_size=max(8, int(size * 0.45)))
    kw = {}
    if props.get("stroke"):
        kw["stroke_width"] = max(1, int(size * 0.06))
        kw["stroke_fill"] = rgba(props["stroke"], 0.85)
    d.text((px, r.cy), F.shape(txt), font=font, fill=rgba(color, props.get("alpha", 1.0)), anchor=anchor, **kw)
    if props.get("icon"):
        ic = render_icon(props["icon"], int(size * 1.15), props.get("icon_color", color))
        ix = (r.right - pad_x - ic.width) if side == "right" else (r.x + pad_x)
        img.alpha_composite(ic, (int(ix), int(r.cy - ic.height / 2)))


def shadow_layer(rect: Rect, pal: Palette, scale: float = 1.0, strength: float = 0.5,
                 radius: float | None = None) -> Image.Image:
    """Soft drop shadow the size of the full composite (placed under an asset)."""
    w = max(4, int(rect.w * scale))
    h = max(4, int(rect.h * scale))
    r = (radius if radius is not None else pal.radius) * scale
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    m = _mask(w, h, r)
    sh = Image.new("RGBA", (w, h), rgba(mix((0, 0, 0), pal.bg_deep, 0.35), 1.0))
    sh.putalpha(m.point(lambda v: int(v * min(1.0, strength))))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(max(2, int(min(w, h) * 0.09)))))
    return img
