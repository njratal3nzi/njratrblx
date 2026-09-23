"""Assembles the final ZIP deliverable."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from ..spec import DesignSpec
from . import docs, luau, rbxmx


def _png_bytes(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def build_zip(spec: DesignSpec, images: dict, previews: dict, out_path: Path,
              gateway_summary: dict, stats: dict, prompts: str = "") -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    files: list[str] = []
    slices: dict[str, list] = {}

    design_lua, library_lua = luau.design_script(spec)

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        def put(name: str, data: bytes | str) -> None:
            if isinstance(data, str):
                data = data.encode("utf-8")
            z.writestr(name, data)
            files.append(name)

        # --- assets
        for asset in spec.assets:
            img = images.get(asset.key)
            if img is None:
                continue
            path = f"assets/{asset.category}/{asset.filename}"
            put(path, _png_bytes(img))
            if asset.slice:
                slices[asset.key] = [round(v, 2) for v in asset.slice]

        # --- previews (thumbnails are grouped under preview/)
        for name, img in previews.items():
            path = f"preview/{name}.png" if name.startswith("thumb") else f"{name}.png"
            put(path, _png_bytes(img))
            files.append(path)

        # --- luau
        put("luau/UiForge.lua", library_lua)
        put(f"luau/Design_{spec.slug}.lua", design_lua)
        put("luau/Bind_Assets.lua", luau.bind_assets_script(spec))
        put("luau/AutoScale.lua", luau.auto_scale_script())

        # --- studio
        put("studio/Studio_QuickBuild.lua", luau.quick_build_script(spec))
        put(f"studio/{spec.slug}.rbxmx", rbxmx.build_rbxmx(spec))

        # --- data
        put("slices.json", json.dumps(slices, indent=2))
        put("design-system.json", json.dumps(docs.design_system(spec), indent=2, ensure_ascii=False))
        put("prompts.txt", prompts or "-- no AI prompts were used (procedural textures only)")
        put("tree.json", spec.to_json())
        put("README.md", docs.readme(spec, stats, gateway_summary))
        put("manifest.json", json.dumps(docs.manifest(spec, files, stats), indent=2, ensure_ascii=False))

    return out_path
