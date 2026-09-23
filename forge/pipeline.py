"""End-to-end pipeline: prompt -> design tree -> rendered assets -> ZIP."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFilter

from . import layouts, painter
from .ai.gateway import Gateway
from .ai.imagers import AIImager, fit_cover
from .ai.planner import Planner, apply_plan
from .brief import Brief, parse as parse_brief
from .config import SETTINGS, Settings
from .exporters import zipper
from .spec import Asset, DesignSpec, Rect
from .themes import Palette, build_palette, hexs, mix, rgba, shade
from . import fonts as F

Log = Callable[[str], None]

CATEGORY = {
    "button": "buttons",
    "panel": "panels", "row": "panels", "toast": "panels", "field": "panels",
    "tab": "panels", "badge": "panels", "slot": "panels",
    "track": "controls", "fill": "controls", "knob": "controls", "toggle": "controls",
    "divider": "controls",
    "icon": "icons", "avatar": "icons",
    "backdrop": "backgrounds", "scrim": "backgrounds",
    "wheel": "misc", "minimap": "misc",
}

BUTTON_STATES = ("idle", "hover", "pressed", "disabled")


@dataclass
class Result:
    spec: DesignSpec
    images: dict = field(default_factory=dict)
    previews: dict = field(default_factory=dict)
    thumbs: dict = field(default_factory=dict)
    zip_path: Path | None = None
    stats: dict = field(default_factory=dict)
    log_lines: list = field(default_factory=list)
    gateway: dict = field(default_factory=dict)
    ai_prompts: str = ""

    def to_public(self) -> dict:
        return {
            "slug": self.spec.slug, "title": self.spec.title, "subtitle": self.spec.subtitle,
            "stats": self.stats, "gateway": self.gateway, "log": self.log_lines,
            "notes": self.spec.notes,
            "zip": self.zip_path.name if self.zip_path else None,
            "previews": sorted(self.previews), "thumbs": sorted(self.thumbs),
            "assets": [{"key": a.key, "category": a.category, "filename": a.filename,
                        "w": a.width, "h": a.height, "source": a.source,
                        "slice": a.slice} for a in self.spec.assets],
            "palette": self.spec.palette.swatch() if self.spec.palette else {},
            "fonts": F.font_report(),
        }


# ------------------------------------------------------------------ assets


def _unique(keys: set, base: str) -> str:
    key = base
    i = 2
    while key in keys:
        key = f"{base}_{i}"
        i += 1
    keys.add(key)
    return key


def build_assets(spec: DesignSpec, pal: Palette, rs: int, states: bool = True) -> None:
    keys: set[str] = set()
    for node in spec.root.walk():
        if node.kind not in painter.RENDERERS:
            continue
        r = node.rect
        if r.w <= 0 or r.h <= 0:
            continue
        category = CATEGORY.get(node.kind, "misc")
        base = _unique(keys, "".join(ch if ch.isalnum() else "_" for ch in node.name).strip("_").lower() or node.kind)
        props = dict(node.props)
        rs_a = painter.asset_scale(node.kind, r.w, r.h, rs)
        asset = Asset(key=base, category=category, filename=f"{base}.png", rect=Rect(*r.tup()),
                      slice=painter.slice_center(node.kind, r.w, r.h, props, pal, rs_a),
                      renderer=node.kind, props=props, node=node.name, rs=rs_a)
        spec.add_asset(asset)
        if node.kind == "button" and states:
            for st in BUTTON_STATES[1:]:
                sp = dict(props)
                sp["state"] = st
                k = _unique(keys, f"{base}_{st}")
                spec.add_asset(Asset(key=k, category=category, filename=f"{k}.png", rect=Rect(*r.tup()),
                                     slice=painter.slice_center(node.kind, r.w, r.h, sp, pal, rs_a),
                                     renderer=node.kind, props=sp, node=node.name, source="vector", rs=rs_a))
    # keep the node -> primary asset mapping stable (first asset for that node)
    seen: set[str] = set()
    for a in list(spec.assets):
        if a.node in seen:
            continue
        seen.add(a.node)


# ------------------------------------------------------------------ rendering


def render_assets(spec: DesignSpec, pal: Palette, rs: int, log: Log = print) -> dict:
    images: dict[str, Image.Image] = {}
    for asset in spec.assets:
        try:
            img = painter.render(asset.renderer, asset.rect.w, asset.rect.h, pal, asset.props, asset.rs)
        except Exception as exc:  # never let one component kill the run
            log(f"  ! {asset.key}: {type(exc).__name__}: {exc}")
            img = painter.new_canvas(asset.rect.w, asset.rect.h, rs)
        asset.width, asset.height = img.size
        images[asset.key] = img
    return images


def compose(spec: DesignSpec, images: dict, pal: Palette, ai_images: dict | None = None,
            scale: float = 1.0, shadows: bool = True) -> Image.Image:
    cw, ch = spec.canvas
    W, H = int(cw * scale), int(ch * scale)
    canvas = Image.new("RGBA", (W, H), rgba(pal.bg_deep, 1.0))
    ai_images = ai_images or {}

    for node in spec.root.walk():
        if node.kind == "root" or not node.visible:
            continue
        r = node.rect
        dw, dh = max(1, int(r.w * scale)), max(1, int(r.h * scale))
        pos = (int(r.x * scale), int(r.y * scale))

        if node.name in ai_images:
            img = ai_images.get(node.name)
            if img is not None:
                canvas.alpha_composite(fit_cover(img, dw, dh).convert("RGBA"), pos)
                continue

        asset = spec.asset_for(node.name)
        src = images.get(asset.key) if asset else None
        if src is not None:
            if shadows and node.props.get("shadow"):
                sh = painter.shadow_layer(Rect(pos[0], pos[1], dw, dh), pal, scale=1,
                                          strength=0.55, radius=node.props.get("radius", pal.radius) * scale)
                pad = int(min(dw, dh) * 0.12) + 6
                canvas.alpha_composite(sh, (pos[0] - pad // 2, pos[1] - pad // 4 + pad))
            piece = src if (src.width, src.height) == (dw, dh) else src.resize((dw, dh), Image.LANCZOS)
            canvas.alpha_composite(piece, pos)
            if node.kind == "button" and node.props.get("variant") == "primary" and pal.glow > 0.45:
                gl = Image.new("RGBA", (dw, dh), (0, 0, 0, 0))
                ImageDraw.Draw(gl).rounded_rectangle([dw * 0.06, dh * 0.25, dw * 0.94, dh * 0.95],
                                                     radius=min(dw, dh) * 0.4,
                                                     fill=rgba(mix(pal.accent, pal.accent_hi, 0.5), 0.5))
                gl = gl.filter(ImageFilter.GaussianBlur(max(2, int(min(dw, dh) * 0.16))))
                tmp = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
                tmp.alpha_composite(gl, pos)
                canvas.alpha_composite(tmp)

        if node.props.get("label"):
            painter.draw_label(canvas, _scaled(node, scale), pal, scale=scale)
    return canvas


def _scaled(node, scale: float):
    """Lightweight view of a node with its rect/text scaled for the compositor."""
    from .spec import Node
    r = node.rect
    p = dict(node.props)
    for k in ("font_size", "pad_x"):
        if k in p:
            p[k] = float(p[k]) * scale
    if "stroke_width" in p:
        p["stroke_width"] = float(p["stroke_width"]) * scale
    return Node(kind=node.kind, name=node.name, rect=Rect(r.x * scale, r.y * scale, r.w * scale, r.h * scale),
                props=p)


def compose_showcase(preview: Image.Image, spec: DesignSpec, stats: dict,
                     width: int = 1920, height: int = 1080) -> Image.Image:
    pal = spec.palette
    out = Image.new("RGBA", (width, height), rgba(pal.bg_deep, 1.0))
    out.alpha_composite(painter.gradient(width, height, pal.bg_deep, mix(pal.bg_mid, pal.accent, 0.12),
                                         angle=115).convert("RGBA"))
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(glow)
    d.ellipse([width * 0.55, -height * 0.4, width * 1.3, height * 0.8], fill=rgba(pal.accent, 0.28))
    d.ellipse([-width * 0.2, height * 0.5, width * 0.35, height * 1.4], fill=rgba(pal.accent2, 0.22))
    out.alpha_composite(glow.filter(ImageFilter.GaussianBlur(120)))

    d = ImageDraw.Draw(out)
    # header
    F.draw_centered(d, 60, 62, "ROBLOX UI FORGE", 34, rgba(pal.accent_hi, 1.0), anchor="lm")
    d.line([(60, 104), (width - 60, 104)], fill=rgba(mix(pal.stroke, pal.accent, 0.4), 0.6), width=2)
    d.text((60, 132), F.shape(spec.title), font=F.load(72), fill=rgba(pal.text, 1.0), anchor="lm")
    d.text((60, 216), F.shape(f"{spec.subtitle}   |   {pal.name} ({pal.name_ar})   |   "
                              f"{spec.canvas[0]}x{spec.canvas[1]}"),
           font=F.load(28), fill=rgba(pal.text_dim, 1.0), anchor="lm")

    # preview panel (left)
    pw, ph = int(width * 0.60), int(height * 0.60)
    shot = preview.copy()
    shot.thumbnail((pw - 40, ph - 40), Image.LANCZOS)
    px, py = 60, 300
    d.rounded_rectangle([px, py, px + pw, py + ph], radius=24, fill=rgba(pal.panel_lo, 1.0),
                        outline=rgba(mix(pal.stroke, pal.accent, 0.5), 1.0), width=2)
    out.alpha_composite(shot, (px + (pw - shot.width) // 2, py + (ph - shot.height) // 2))

    # swatches (right)
    sx = px + pw + 60
    d.text((sx, py + 4), "PALETTE", font=F.load(30), fill=rgba(pal.accent_hi, 1.0), anchor="lm")
    sw = pal.swatch()
    i = 0
    for k, v in sw.items():
        col, row = i % 4, i // 4
        x, y = sx + col * 118, py + 50 + row * 118
        d.rounded_rectangle([x, y, x + 100, y + 100], radius=16, fill=v + "FF" if isinstance(v, str) else v,
                            outline=rgba(pal.stroke, 1.0), width=2)
        d.text((x + 50, y + 112), v, font=F.load(17), fill=rgba(pal.text_dim, 1.0), anchor="mm")
        d.text((x + 50, y + 132), k.replace("_", " "), font=F.load(14), fill=rgba(mix(pal.text_dim, pal.bg_deep, 0.4), 1.0),
               anchor="mm")
        i += 1

    # stats block
    by = py + 50 + ((len(sw) + 3) // 4) * 118 + 40
    d.text((sx, by), "PACKAGE", font=F.load(30), fill=rgba(pal.accent_hi, 1.0), anchor="lm")
    lines = [
        f"components   {stats.get('nodes', 0)}",
        f"png assets   {stats.get('assets', 0)}",
        f"button states {stats.get('button_states', 0)}",
        f"text labels  {stats.get('texts', 0)}",
        f"ai images    {stats.get('ai_images', 0)}",
        f"9-slice sets {stats.get('sliceable', 0)}",
    ]
    for j, line in enumerate(lines):
        d.text((sx, by + 48 + j * 34), line, font=F.load(22), fill=rgba(pal.text, 1.0), anchor="lm")

    d.text((60, height - 46), "Generated by Roblox UI Forge — assets/ + luau/ + studio/ inside the ZIP",
           font=F.load(20), fill=rgba(pal.text_dim, 1.0), anchor="lm")
    return out


def make_thumbs(spec: DesignSpec, full: Image.Image, limit: int = 8, scale: float = 1.0) -> dict:
    out: dict[str, Image.Image] = {}
    wanted = ("button", "slot", "panel", "toast", "row", "tab", "avatar", "wheel", "minimap", "field")
    seen: set[str] = set()
    for node in spec.root.walk():
        if node.kind not in wanted or node.kind in seen:
            continue
        seen.add(node.kind)
        r = node.rect
        pad = 26
        box = (max(0, int((r.x - pad) * scale)), max(0, int((r.y - pad) * scale)),
               min(full.width, int((r.right + pad) * scale)), min(full.height, int((r.bottom + pad) * scale)))
        if box[2] - box[0] < 24 or box[3] - box[1] < 24:
            continue
        crop = full.crop(box)
        crop.thumbnail((520, 520), Image.LANCZOS)
        out[f"thumb_{node.kind}_{len(out)}"] = crop
        if len(out) >= limit:
            break
    return out


# ------------------------------------------------------------------ pipeline


def run(prompt: str, *, kind: str | None = None, style: str | None = None, hue: float | None = None,
        dark: bool | None = None, lang: str | None = None, radius: int | None = None,
        density: str | None = None, use_llm: bool | None = None, use_ai_images: bool | None = None,
        export_states: bool = True, settings: Settings = SETTINGS, log: Log = print,
        progress: Callable[[float, str], None] | None = None,
        work_dir: Path | None = None) -> Result:
    t0 = time.time()
    lines: list[str] = []

    def _log(msg: str) -> None:
        lines.append(msg)
        try:
            log(msg)
        except Exception:
            pass

    def _prog(p: float, stage: str) -> None:
        if progress:
            try:
                progress(round(p, 3), stage)
            except Exception:
                pass

    settings.ensure_dirs()
    gw = Gateway(settings=settings)
    if use_llm is not None:
        settings.use_llm_planner = use_llm
    if use_ai_images is not None:
        settings.use_ai_images = use_ai_images

    _prog(0.02, "parsing")
    brief = parse_brief(prompt, kind=kind, style=style, hue=hue, dark=dark, lang=lang)
    if radius is not None:
        brief.radius = int(radius)
    if density:
        brief.density = density
    _log(f"• screen = {brief.kind} | style = {brief.style} | lang = {brief.lang} | density = {brief.density}")

    _prog(0.08, "palette")
    pal = build_palette(brief.style, hue=brief.hue, sat=brief.sat, dark=brief.dark, radius=brief.radius)

    _prog(0.14, "layout")
    spec = layouts.build(brief, pal, (settings.canvas_w, settings.canvas_h))
    n_nodes = sum(1 for _ in spec.root.walk()) - 1
    _log(f"• layout built: {n_nodes} nodes")

    _prog(0.22, "planner")
    plan_source = "builtin"
    if settings.use_llm_planner:
        planner = Planner(gateway=gw)
        plan = planner.plan(spec, brief)
        plan_source = plan.source
        if plan.raw:
            notes = apply_plan(spec, plan, log=_log)
            for n in notes:
                _log(f"• {n}")
            pal = spec.palette
            _log(f"• planner = {plan.source}")
        else:
            _log(f"• planner skipped ({plan.error}) -> deterministic design kept")
    spec.planner_source = plan_source

    _prog(0.32, "assets")
    build_assets(spec, pal, settings.rscale, states=export_states)
    _log(f"• {len(spec.assets)} assets planned ({sum(1 for a in spec.assets if a.slice)} sliceable)")

    _prog(0.40, "ai-images")
    ai_images: dict[str, Image.Image] = {}
    ai_prompts = ""
    if settings.use_ai_images:
        imager = AIImager(gateway=gw, cache_dir=settings.cache_dir)
        ai_raw = imager.run(spec, pal, log=_log, limit=2)
        for node_name, data in ai_raw.items():
            ai_images[node_name] = data["image"]
        ai_prompts = imager.prompts()
    else:
        _log("• AI images disabled -> procedural textures")

    _prog(0.55, "render")
    images = render_assets(spec, pal, settings.rscale, log=_log)
    _log(f"• rendered {len(images)} PNGs")

    _prog(0.78, "compose")
    full = compose(spec, images, pal, ai_images=ai_images, scale=1.0)
    preview = full.resize((int(full.width * settings.preview_scale),
                           int(full.height * settings.preview_scale)), Image.LANCZOS)
    showcase = compose_showcase(preview, spec, {
        "nodes": n_nodes, "assets": len(spec.assets),
        "button_states": sum(1 for a in spec.assets if a.key.endswith(("_hover", "_pressed", "_disabled"))) +
                         sum(1 for a in spec.assets if a.category == "buttons" and a.renderer == "button"
                             and not a.key.endswith(("_hover", "_pressed", "_disabled"))),
        "texts": sum(1 for n in spec.root.walk() if n.kind == "text"),
        "ai_images": len(ai_images),
        "sliceable": sum(1 for a in spec.assets if a.slice),
    })
    thumbs = make_thumbs(spec, full, limit=8)

    _prog(0.9, "zip")
    stats = {
        "nodes": n_nodes, "assets": len(spec.assets),
        "buttons": sum(1 for n in spec.root.walk() if n.kind == "button"),
        "texts": sum(1 for n in spec.root.walk() if n.kind == "text"),
        "panels": sum(1 for n in spec.root.walk() if n.kind == "panel"),
        "ai_images": len(ai_images),
        "sliceable": sum(1 for a in spec.assets if a.slice),
        "button_states": sum(1 for a in spec.assets if a.key.endswith(("_hover", "_pressed", "_disabled"))),
        "elapsed": round(time.time() - t0, 2),
    }
    previews = {"preview_full": full, "preview": preview, "preview_showcase": showcase, **thumbs}
    out_dir = work_dir or (settings.out_dir / f"{spec.slug}_{int(t0)}")
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"RobloxUIForge_{spec.slug}.zip"
    zipper.build_zip(spec, images, previews, zip_path, gw.active_summary(), stats, ai_prompts)
    stats["elapsed"] = round(time.time() - t0, 2)
    stats["zip_bytes"] = zip_path.stat().st_size
    _log(f"• ZIP ready: {zip_path.name} ({stats['zip_bytes'] / 1024:.0f} KB) in {stats['elapsed']}s")
    _prog(1.0, "done")

    return Result(spec=spec, images=images, previews=previews, thumbs=thumbs, zip_path=zip_path,
                  stats=stats, log_lines=lines, gateway=gw.active_summary(), ai_prompts=ai_prompts)
