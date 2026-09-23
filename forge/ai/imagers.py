"""AI image generation + procedural fallback, with on-disk caching.

AI images are only ever used for *decorative* surfaces (backdrops, hero art),
never for interactive controls.  If the gateway is unreachable the procedural
generator produces the same asset class, so the ZIP is always complete.
"""
from __future__ import annotations

import hashlib
import io
import math
import random
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from ..spec import DesignSpec, Rect
from ..themes import Palette, mix, rgba, hexs
from .gateway import Gateway

NEG = "no text, no letters, no words, no watermark, no logo, no signature, no ui, no borders"


@dataclass
class ImageRequest:
    key: str
    node: str
    prompt: str
    width: int
    height: int
    seed: int = 1
    kind: str = "backdrop"       # backdrop | art


def build_requests(spec: DesignSpec, pal: Palette, limit: int = 3) -> list[ImageRequest]:
    """Decorative surfaces worth spending an AI call on."""
    reqs: list[ImageRequest] = []
    style_words = {
        "neon": "neon glow, cyan and magenta rim light",
        "cyber": "cyberpunk holographic tech, purple circuits",
        "royal": "luxury gold filigree, dark velvet",
        "ocean": "deep ocean, bioluminescent blue",
        "toxic": "toxic green slime, radioactive haze",
        "lava": "molten lava cracks, ember sparks",
        "candy": "bright cartoon candy world, soft shapes",
        "minimal": "clean minimal abstract shapes, soft pastel",
        "midnight": "midnight city skyline, deep blue fog",
        "military": "tactical dark green, metal plates",
        "sunset": "sunset orange clouds, warm haze",
        "forest": "mystic forest, volumetric green light",
        "mono": "black and white abstract ink texture",
        "ice": "frosted ice crystals, bright white blue",
        "grape": "violet nebula, soft purple glow",
        "rose": "pink silk folds, soft rose light",
    }.get(pal.name, "stylised game art")
    screen_words = {
        "shop": "fantasy shop interior with floating crystals and treasure",
        "inventory": "adventurer backpack contents laid out on dark wood",
        "main_menu": "epic hero landscape with a glowing portal",
        "settings": "abstract control panels, soft depth of field",
        "loading": "wide cinematic landscape, dramatic sky",
        "leaderboard": "champions arena with floating trophies",
        "profile": "character silhouette on a glowing pedestal",
        "hud": "blurred battlefield depth of field",
        "pause": "moody dark arena with light rays",
        "login": "gate of a fantasy castle at night",
        "crate": "glowing treasure chest with light beams",
        "quests": "ancient map with glowing markers",
        "dialog": "soft bokeh background, dark vignette",
        "wheel": "carnival light bokeh, spinning motion blur",
        "chat": "soft dark gradient with subtle particles",
        "store": "floating gem clusters, glossy reflections",
    }.get(spec.brief.kind if spec.brief else "main_menu", "epic game landscape")

    for node in spec.root.walk():
        if node.kind != "backdrop":
            continue
        w, h = int(node.rect.w), int(node.rect.h)
        prompt = (f"{screen_words}, {style_words}, dark moody game background art, "
                  f"dominant colour {hexs(pal.accent)} with {hexs(pal.accent2)} accents, "
                  f"high detail, cinematic lighting, depth of field. {NEG}")
        reqs.append(ImageRequest(key=f"bg_{node.name.lower()}", node=node.name, prompt=prompt,
                                 width=1280, height=720, seed=abs(hash(prompt)) % 99991, kind="backdrop"))
        if len(reqs) >= limit:
            break
    return reqs


def procedural_image(kind: str, pal: Palette, width: int, height: int, seed: int = 3) -> Image.Image:
    """Offline stand-in for an AI image (used by the deterministic path)."""
    from ..painter import part_backdrop
    variant = {"nebula": "nebula", "grid": "grid", "dust": "dust", "rays": "rays"}.get(kind, "nebula")
    return part_backdrop(width, height, pal, {"variant": variant, "seed": seed}, 1)


def grade_image(img: Image.Image, pal: Palette, strength: float = 0.35,
                radius: float = 0.0, vignette: float = 0.45) -> Image.Image:
    """Theme-grade a raw AI image so it belongs to the palette."""
    img = img.convert("RGBA")
    tint = Image.new("RGBA", img.size, rgba(pal.accent, 1.0))
    from PIL import ImageChops
    graded = Image.blend(img.convert("RGB"), ImageChops.multiply(img.convert("RGB"),
                                                                 Image.new("RGB", img.size, mix(pal.accent, (255, 255, 255), 0.45))),
                         strength)
    graded = ImageEnhance.Contrast(graded).enhance(1.08)
    graded = ImageEnhance.Color(graded).enhance(1.05)
    out = graded.convert("RGBA")
    if vignette > 0:
        v = Image.new("L", img.size, 0)
        d = ImageDraw.Draw(v)
        d.ellipse([-img.width * 0.2, -img.height * 0.25, img.width * 1.2, img.height * 1.25], fill=255)
        v = v.filter(ImageFilter.GaussianBlur(max(8, img.width // 40)))
        dark = Image.new("RGBA", img.size, rgba(mix(pal.bg_deep, (0, 0, 0), 0.5), 1.0))
        out.alpha_composite(Image.composite(dark, Image.new("RGBA", img.size, (0, 0, 0, 0)),
                                           ImageOps.invert(v).point(lambda p: int(p * vignette))))
    if radius > 0:
        m = Image.new("L", img.size, 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=radius, fill=255)
        out.putalpha(m)
    return out


def fit_cover(img: Image.Image, w: int, h: int) -> Image.Image:
    """Resize + centre crop to exactly w x h (CSS object-fit: cover)."""
    w, h = max(1, int(w)), max(1, int(h))
    src = img.convert("RGBA")
    scale = max(w / src.width, h / src.height)
    nw, nh = max(1, int(src.width * scale)), max(1, int(src.height * scale))
    src = src.resize((nw, nh), Image.LANCZOS)
    x, y = (nw - w) // 2, (nh - h) // 2
    return src.crop((x, y, x + w, y + h))


@dataclass
class AIImager:
    gateway: Gateway
    cache_dir: Path | None = None
    results: dict = field(default_factory=dict)   # node -> {"image": PIL, "source": str, "prompt": str}

    def _cache_path(self, req: ImageRequest) -> Path | None:
        if self.cache_dir is None:
            return None
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha1(f"{req.prompt}|{req.width}x{req.height}|{req.seed}".encode()).hexdigest()[:24]
        return self.cache_dir / f"{req.key}_{key}.png"

    def fetch(self, req: ImageRequest) -> tuple[Image.Image | None, str]:
        cached = self._cache_path(req)
        if cached is not None and cached.exists():
            try:
                return Image.open(cached).convert("RGBA"), "cache"
            except Exception:
                pass
        data, provider = self.gateway.image(req.prompt, req.width, req.height, req.seed)
        if not data:
            return None, "local"
        try:
            img = Image.open(io.BytesIO(data)).convert("RGBA")
        except Exception:
            return None, "local"
        if cached is not None:
            try:
                img.save(cached, "PNG")
            except Exception:
                pass
        return img, provider

    def run(self, spec: DesignSpec, pal: Palette, log=print, limit: int = 2) -> dict:
        reqs = build_requests(spec, pal, limit=limit)
        for req in reqs:
            img, source = self.fetch(req)
            if img is None:
                log(f"  · AI image skipped for {req.node} (offline) -> procedural")
                continue
            node = _find(spec, req.node)
            if node is None:
                continue
            sized = fit_cover(img, int(node.rect.w), int(node.rect.h))
            sized = grade_image(sized, pal, strength=0.3, vignette=0.5)
            self.results[req.node] = {"image": sized, "source": source, "prompt": req.prompt}
            log(f"  · AI image for {req.node} via {source} ({sized.width}x{sized.height})")
        return self.results

    def prompts(self) -> str:
        return "\n\n".join(f"[{k}]\n{v['prompt']}" for k, v in self.results.items())


def _find(spec: DesignSpec, name: str):
    for n in spec.root.walk():
        if n.name == name:
            return n
    return None
