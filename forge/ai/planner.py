"""LLM refinement layer.

Order of operations matters: the deterministic engine builds the *whole* layout
first, then the model is asked to improve copy, naming and styling.  A model
reply that is missing, malformed or out-of-schema is simply ignored, so the
tool never depends on the network to produce a complete design.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from ..brief import Brief
from ..spec import DesignSpec
from ..themes import STYLE_PRESETS
from .gateway import Gateway, extract_json

SYSTEM = """You are the art director of "Roblox UI Forge", a tool that turns one
sentence into a complete, production-ready Roblox (Luau) UI kit.

You refine an ALREADY BUILT layout. You never invent structure. Reply with ONE
JSON object and nothing else. Schema:

{
  "title": "short UI title in the user's language",
  "title_en": "same title in English",
  "subtitle": "one short line, same language",
  "subtitle_en": "same line in English",
  "style": "one of: neon, cyber, royal, ocean, toxic, lava, candy, minimal, midnight, military, sunset, forest, mono, ice, grape, rose",
  "hue": integer 0-359 or null,
  "dark": true | false | null,
  "density": "compact" | "comfortable" | "spacious",
  "labels": { "<NodeName>": {"ar": "...", "en": "..."}, ... }
}

Rules:
- labels keys MUST be node names from the provided list, values must be short
  (1-3 words for buttons, max 12 words for descriptions).
- Keep the same language as the user's request for "ar"/main fields, English for
  the *_en fields.
- Never mention that you are an AI. Never add markdown, code fences or prose."""


@dataclass
class PlanResult:
    source: str = "builtin"
    applied: list[str] = field(default_factory=list)
    overrides: dict = field(default_factory=dict)
    raw: dict | None = None
    error: str = ""

    def to_dict(self) -> dict:
        return {"source": self.source, "applied": self.applied, "overrides": self.overrides,
                "raw": self.raw, "error": self.error}


@dataclass
class Planner:
    gateway: Gateway

    def plan(self, spec: DesignSpec, brief: Brief) -> PlanResult:
        if not self.gateway.settings.use_llm_planner:
            return PlanResult(source="builtin", error="LLM planner disabled")
        nodes = _collect_text_nodes(spec)
        if not nodes:
            return PlanResult(source="builtin", error="no text nodes")
        payload = {
            "request": brief.raw or brief.title,
            "language": brief.lang,
            "screen": brief.screen.get("en"),
            "current_style": brief.style,
            "current_density": brief.density,
            "nodes": nodes,
        }
        text, provider = self.gateway.text(SYSTEM, json.dumps(payload, ensure_ascii=False)[:12000],
                                           json_mode=True, temperature=0.55)
        data = extract_json(text)
        if not data:
            return PlanResult(source="builtin", error=f"no valid JSON from {provider}")
        return PlanResult(source=provider, raw=data)


def _collect_text_nodes(spec: DesignSpec, limit: int = 90) -> list[dict]:
    out = []
    for n in spec.root.walk():
        if n.kind != "text":
            continue
        out.append({"name": n.name, "ar": n.props.get("label", ""), "en": n.props.get("label_en", ""),
                    "size": int(n.props.get("font_size", 24))})
        if len(out) >= limit:
            break
    return out


def apply_plan(spec: DesignSpec, plan: PlanResult, log=None) -> list[str]:
    """Apply a validated plan to the spec.  Returns human readable notes."""
    notes: list[str] = []
    if not plan.raw:
        return notes
    data = plan.raw
    ar = spec.lang == "ar"

    title = _clean(data.get("title"), 60)
    if title:
        spec.title = title
        spec.root.props["title"] = title
        plan.applied.append("title")
    subtitle = _clean(data.get("subtitle") or data.get("subtitle_en"), 90)
    if subtitle:
        spec.subtitle = subtitle
        plan.applied.append("subtitle")

    style = data.get("style")
    if isinstance(style, str) and style in STYLE_PRESETS and spec.palette is not None:
        from ..themes import build_palette
        hue = data.get("hue") if isinstance(data.get("hue"), (int, float)) else None
        dark = data.get("dark") if isinstance(data.get("dark"), bool) else None
        spec.palette = build_palette(style, hue=hue, dark=dark, radius=spec.palette.radius)
        notes.append(("تم تغيير النمط إلى %s" % STYLE_PRESETS[style]["ar"]) if ar else f"style -> {style}")

    labels = data.get("labels")
    if isinstance(labels, dict) and labels:
        by_name = {n.name: n for n in spec.root.walk() if n.kind == "text"}
        count = 0
        for name, val in labels.items():
            node = by_name.get(name)
            if node is None or not isinstance(val, dict):
                continue
            la = _clean(val.get("ar"), 80)
            le = _clean(val.get("en"), 80)
            if la:
                node.props["label"] = la
                count += 1
            if le:
                node.props["label_en"] = le
        if count:
            plan.applied.append(f"labels x{count}")
            notes.append(("حسّن النموذج %d نصاً" % count) if ar else f"LLM rewrote {count} labels")
    return notes


def _clean(v, maxlen: int = 60) -> str:
    if not isinstance(v, str):
        return ""
    v = " ".join(v.split()).strip()
    if len(v) > maxlen:
        v = v[:maxlen - 1].rstrip() + "…"
    return v
