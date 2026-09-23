"""Design tree: geometry helpers + Node / Asset / DesignSpec data classes."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Iterator

# ------------------------------------------------------------------ geometry


@dataclass
class Rect:
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    def inset(self, dx: float, dy: float | None = None) -> "Rect":
        dy = dx if dy is None else dy
        return Rect(self.x + dx, self.y + dy, max(0.0, self.w - 2 * dx), max(0.0, self.h - 2 * dy))

    def offset(self, dx: float, dy: float) -> "Rect":
        return Rect(self.x + dx, self.y + dy, self.w, self.h)

    def resized(self, w: float, h: float, cx: bool = True, cy: bool = True) -> "Rect":
        return Rect(self.cx - w / 2 if cx else self.x, self.cy - h / 2 if cy else self.y, w, h)

    def tup(self) -> tuple[float, float, float, float]:
        return (round(self.x, 3), round(self.y, 3), round(self.w, 3), round(self.h, 3))

    def to_dict(self) -> dict:
        return {"x": round(self.x, 3), "y": round(self.y, 3), "w": round(self.w, 3), "h": round(self.h, 3)}


def split_h(r: Rect, parts: list[float], gap: float = 0.0) -> list[Rect]:
    """Split horizontally.  part > 1 -> pixels, 0 < part <= 1 -> share of what is left."""
    return _split(r, parts, gap, horizontal=True)


def split_v(r: Rect, parts: list[float], gap: float = 0.0) -> list[Rect]:
    """Split vertically with the same rule as :func:`split_h`."""
    return _split(r, parts, gap, horizontal=False)


def _split(r: Rect, parts: list[float], gap: float, horizontal: bool) -> list[Rect]:
    if not parts:
        return []
    total = (r.w if horizontal else r.h)
    px_used = sum(p for p in parts if p > 1)
    gaps = gap * (len(parts) - 1)
    free = max(0.0, total - px_used - gaps)
    weight = sum(p for p in parts if 0 < p <= 1)
    out: list[Rect] = []
    cur = r.x if horizontal else r.y
    for p in parts:
        if p > 1:
            size = float(p)
        elif p > 0:
            size = free * (p / weight) if weight > 0 else 0.0
        else:
            size = 0.0
        out.append(Rect(cur, r.y, size, r.h) if horizontal else Rect(r.x, cur, r.w, size))
        cur += size + gap
    return out


def grid(r: Rect, cols: int, rows: int, gap: float = 12.0,
         cell_ratio: float | None = None, align: str = "top") -> list[Rect]:
    """Uniform grid; `cell_ratio` (w/h) locks cell shape and re-centres the grid."""
    cols = max(1, cols)
    rows = max(1, rows)
    cw = (r.w - gap * (cols - 1)) / cols
    ch = (r.h - gap * (rows - 1)) / rows
    if cell_ratio:
        target_h = cw / cell_ratio
        if target_h <= ch:
            ch = target_h
        else:
            cw = ch * cell_ratio
    total_w = cw * cols + gap * (cols - 1)
    total_h = ch * rows + gap * (rows - 1)
    ox = r.x + (r.w - total_w) / 2
    oy = r.y
    if align == "center":
        oy = r.y + (r.h - total_h) / 2
    elif align == "bottom":
        oy = r.bottom - total_h
    cells = []
    for row in range(rows):
        for col in range(cols):
            cells.append(Rect(ox + col * (cw + gap), oy + row * (ch + gap), cw, ch))
    return cells


def center_in(r: Rect, w: float, h: float) -> Rect:
    return Rect(r.cx - w / 2, r.cy - h / 2, w, h)


# ------------------------------------------------------------------ tree


@dataclass
class Node:
    kind: str                     # component kind -> forge.painter.RENDERERS
    name: str
    rect: Rect = field(default_factory=Rect)
    props: dict[str, Any] = field(default_factory=dict)
    children: list["Node"] = field(default_factory=list)
    visible: bool = True

    def add(self, child: "Node") -> "Node":
        self.children.append(child)
        return child

    def walk(self) -> Iterator["Node"]:
        yield self
        for c in self.children:
            yield from c.walk()

    def to_dict(self) -> dict:
        return {
            "kind": self.kind, "name": self.name, "rect": self.rect.to_dict(),
            "props": self.props, "visible": self.visible,
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class Asset:
    key: str                      # unique, snake_case
    category: str                 # buttons / panels / icons / backgrounds / misc
    filename: str
    rect: Rect = field(default_factory=Rect)
    slice: tuple[float, float, float, float] | None = None   # Roblox SliceCenter, source px
    renderer: str = ""            # painter renderer name
    props: dict[str, Any] = field(default_factory=dict)
    source: str = "vector"        # vector | ai | hybrid
    ai_prompt: str = ""
    node: str = ""                # owning node name
    width: int = 0
    height: int = 0
    rs: float = 2.0               # render scale actually used for this asset

    def to_dict(self) -> dict:
        d = asdict(self)
        d["rect"] = self.rect.to_dict()
        return d


def slugify(text: str, fallback: str = "design") -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", text or "").strip("-").lower()
    return s or fallback


@dataclass
class DesignSpec:
    slug: str = "design"
    title: str = "Design"
    subtitle: str = ""
    lang: str = "ar"
    canvas: tuple[int, int] = (1920, 1080)
    palette: Any = None
    brief: Any = None
    root: Node = field(default_factory=lambda: Node("root", "ScreenGui"))
    assets: list[Asset] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    planner_source: str = "builtin"

    # --- assets --------------------------------------------------------
    def add_asset(self, asset: Asset) -> Asset:
        self.assets.append(asset)
        return asset

    def asset_by_key(self, key: str) -> Asset | None:
        for a in self.assets:
            if a.key == key:
                return a
        return None

    def asset_for(self, node_name: str) -> Asset | None:
        for a in self.assets:
            if a.node == node_name:
                return a
        return None

    # --- serialisation -------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "slug": self.slug, "title": self.title, "subtitle": self.subtitle,
            "lang": self.lang, "canvas": list(self.canvas),
            "planner_source": self.planner_source,
            "palette": self.palette.to_dict() if self.palette is not None else None,
            "brief": self.brief.to_dict() if self.brief is not None else None,
            "tree": self.root.to_dict(),
            "assets": [a.to_dict() for a in self.assets],
            "notes": self.notes,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
