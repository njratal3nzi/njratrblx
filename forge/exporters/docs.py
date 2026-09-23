"""Documentation + manifest generation for the exported ZIP."""
from __future__ import annotations

import json
import platform
import time

from ..spec import DesignSpec
from ..themes import hexs


def design_system(spec: DesignSpec) -> dict:
    pal = spec.palette
    return {
        "generated_by": "Roblox UI Forge",
        "slug": spec.slug,
        "title": spec.title,
        "screen": spec.brief.kind if spec.brief else "custom",
        "language": spec.lang,
        "canvas": {"width": spec.canvas[0], "height": spec.canvas[1]},
        "style": {
            "id": pal.name, "label_ar": pal.name_ar, "dark": pal.dark,
            "corner_radius": pal.radius, "glow": pal.glow, "glass": pal.glass,
            "grain": pal.grain, "stroke_width": pal.stroke_w,
        },
        "colors": {
            "background": {"deep": hexs(pal.bg_deep), "mid": hexs(pal.bg_mid), "hi": hexs(pal.bg_hi)},
            "panel": {"base": hexs(pal.panel), "hi": hexs(pal.panel_hi), "lo": hexs(pal.panel_lo)},
            "stroke": {"base": hexs(pal.stroke), "hi": hexs(pal.stroke_hi)},
            "accent": {"base": hexs(pal.accent), "hi": hexs(pal.accent_hi), "lo": hexs(pal.accent_lo),
                       "alt": hexs(pal.accent2)},
            "text": {"primary": hexs(pal.text), "dim": hexs(pal.text_dim)},
            "status": {"success": hexs(pal.success), "warn": hexs(pal.warn), "danger": hexs(pal.danger),
                       "info": hexs(pal.info)},
        },
        "color3": {k: list(v) for k, v in pal.to_dict()["color3"].items()},
        "typography": {
            "font_family": "Gotham (Roblox built-in)",
            "weights": {"bold": "Enum.Font.GothamBold", "regular": "Enum.Font.Gotham"},
            "scale_px_at_1080p": {
                "display": spec.root.props.get("title_size", 58),
                "headline": 40, "body": 29, "caption": 23,
            },
        },
        "spacing": {"density": spec.brief.density if spec.brief else "comfortable"},
        "assets": {
            "total": len(spec.assets),
            "by_category": _count_by(spec, "category"),
            "sliceable": sum(1 for a in spec.assets if a.slice),
            "ai_generated": sum(1 for a in spec.assets if a.source != "vector"),
        },
    }


def _count_by(spec: DesignSpec, attr: str) -> dict:
    out: dict[str, int] = {}
    for a in spec.assets:
        k = getattr(a, attr)
        out[k] = out.get(k, 0) + 1
    return out


def manifest(spec: DesignSpec, files: list[str], stats: dict) -> dict:
    return {
        "tool": "Roblox UI Forge",
        "version": "1.0.0",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "platform": platform.platform(),
        "design": design_system(spec),
        "brief": spec.brief.to_dict() if spec.brief else None,
        "planner": spec.planner_source,
        "files": sorted(files),
        "stats": stats,
        "assets": [a.to_dict() for a in spec.assets],
    }


def readme(spec: DesignSpec, stats: dict, gateway_summary: dict) -> str:
    pal = spec.palette
    ar = spec.lang == "ar"
    ds = design_system(spec)
    n = len(spec.assets)
    lines = []
    A = lines.append
    A(f"# {spec.title} — Roblox UI Forge")
    A("")
    A(f"**Screen:** {spec.brief.screen['en'] if spec.brief else 'custom'}  •  "
      f"**Style:** {pal.name} ({pal.name_ar})  •  **Canvas:** {spec.canvas[0]}×{spec.canvas[1]}  •  "
      f"**Assets:** {n}")
    A("")
    A("> " + ("تم توليد هذا المجلد بالكامل آلياً من وصف نصي واحد."
              if ar else "This whole folder was generated automatically from a single text prompt."))
    A("")
    A("---")
    A("")
    A("## " + ("١) التشغيل السريع (3 خطوات)" if ar else "1) Quick start (3 steps)"))
    A("")
    A(("1. ارفع صور مجلد `assets/` إلى Roblox: **Creator Dashboard → Development Items → Images**."
       if ar else "1. Upload the PNGs in `assets/` to Roblox: **Creator Dashboard → Development Items → Images**."))
    A(("2. انسخ معرّفات `rbxassetid://` والصقها في جدول `ASSETS` داخل `luau/Design_%s.lua`." % spec.slug
       if ar else "2. Copy the `rbxassetid://` ids into the `ASSETS` table in `luau/Design_%s.lua`." % spec.slug))
    A(("3. ضع `luau/UiForge.lua` كـ ModuleScript باسم **UiForge** في `ReplicatedStorage`، ثم شغّل سكربت التصميم."
       if ar else "3. Put `luau/UiForge.lua` in `ReplicatedStorage` as a ModuleScript named **UiForge**, then run the design script."))
    A("")
    A("### " + ("معاينة فورية بدون رفع أي صورة" if ar else "Instant preview without uploading anything"))
    A("")
    A(("الصق محتوى `studio/Studio_QuickBuild.lua` في **Command Bar** داخل Roblox Studio "
       "(View → Command Bar) وسيبني الواجهة كاملة بألوان صريحة لتقيّم التخطيط فوراً."
       if ar else "Paste `studio/Studio_QuickBuild.lua` into Roblox Studio's **Command Bar** "
                  "(View → Command Bar) and it builds the full layout with solid colours so you can judge it instantly."))
    A("")
    A("---")
    A("")
    A("## " + ("٢) محتويات الملف" if ar else "2) What is inside"))
    A("")
    A("| " + ("المسار" if ar else "Path") + " | " + ("الوصف" if ar else "Description") + " |")
    A("|---|---|")
    A(("| `assets/` | صور PNG بخلفية شفافة (أزرار بحالاتها، لوحات، أيقونات، خلفيات) |"
       if ar else "| `assets/` | Transparent PNGs: buttons (with states), panels, icons, backgrounds |"))
    A(("| `luau/UiForge.lua` | مكتبة التشغيل: ثيم + دوال بناء الأزرار واللوحات |"
       if ar else "| `luau/UiForge.lua` | Runtime library: theme + button/panel/progress builders |"))
    A(("| `luau/Design_%s.lua` | يبني هذه الشاشة بالضبط من شجرة المكونات |" % spec.slug
       if ar else "| `luau/Design_%s.lua` | Builds this exact screen from the component tree |" % spec.slug))
    A(("| `luau/Bind_Assets.lua` | جدول ربط الصور بالمعرّفات |"
       if ar else "| `luau/Bind_Assets.lua` | Asset-name → id binding table |"))
    A(("| `luau/AutoScale.lua` | يضبط حجم الواجهة لكل الشاشات |"
       if ar else "| `luau/AutoScale.lua` | Scales the UI to any viewport |"))
    A(("| `studio/Studio_QuickBuild.lua` | معاينة فورية في Command Bar |"
       if ar else "| `studio/Studio_QuickBuild.lua` | Instant Command-Bar preview |"))
    A(("| `studio/%s.rbxmx` | ملف نموذج جاهز للسحب إلى Studio (ثانوي) |" % spec.slug
       if ar else "| `studio/%s.rbxmx` | Draggable model file (secondary path) |" % spec.slug))
    A(("| `design-system.json` | الألوان والحواف والخطوط بصيغة قابلة للقراءة آلياً |"
       if ar else "| `design-system.json` | Colours, radii and type tokens, machine readable |"))
    A(("| `manifest.json` | قائمة كل أصل مع أبعاده ومناطق القص (SliceCenter) |"
       if ar else "| `manifest.json` | Every asset with size and 9-slice insets |"))
    A(("| `preview_full.png` | لقطة الواجهة كاملة |" if ar else "| `preview_full.png` | Full screen render |"))
    A(("| `preview_showcase.png` | ملصق العرض مع الثيم |" if ar else "| `preview_showcase.png` | Theme showcase poster |"))
    A(("| `prompts.txt` | الأوامر النصية المستخدمة لتوليد صور الذكاء الاصطناعي |"
       if ar else "| `prompts.txt` | The AI prompts used for the generated artwork |"))
    A("")
    A("---")
    A("")
    A("## " + ("٣) الثيم" if ar else "3) Design tokens"))
    A("")
    A("```json")
    A(json.dumps({"colors": ds["colors"]["accent"] | {"panel": ds["colors"]["panel"]["base"],
                                                      "text": ds["colors"]["text"]["primary"],
                                                      "background": ds["colors"]["background"]["deep"]},
                  "corner_radius": ds["style"]["corner_radius"],
                  "dark": ds["style"]["dark"]}, indent=2))
    A("```")
    A("")
    A("## " + ("٤) ملاحظات مهمة" if ar else "4) Good to know"))
    A("")
    for note in spec.notes:
        A(f"- {note}")
    A("")
    A(("### لماذا النصوص ليست داخل الصور؟" if ar else "### Why is text not baked into the images?"))
    A("")
    A(("لأن كل نص يُصدَّر كـ `TextLabel` حقيقي: تقدر تغيّره، تترجمه، وتستخدم `TextScaled` "
       "بدون إعادة توليد أي صورة."
       if ar else "Every label is exported as a real `TextLabel`, so you can edit it, translate it "
                  "and use `TextScaled` without regenerating a single image."))
    A("")
    A(("### القص 9-Slice" if ar else "### 9-slice"))
    A("")
    A(("كل أصل قابل للتوسع يحمل `SliceCenter` في `manifest.json`، ومكتبة `UiForge` تطبّقه تلقائياً "
       "عند رفع الصورة، فالأزرار تتمدد لأي عرض دون تشوّه."
       if ar else "Every scalable asset carries a `SliceCenter` in `manifest.json`; `UiForge` applies it "
                  "automatically once you bind the id, so buttons stretch to any width without distortion."))
    A("")
    A("---")
    A("")
    A("## " + ("٥) كيف تم التوليد" if ar else "5) Generation report"))
    A("")
    A(f"- Prompt: `{(spec.brief.raw[:180] if spec.brief and spec.brief.raw else spec.title)}`")
    A(f"- Planner: `{spec.planner_source}`")
    A(f"- Components: {stats.get('nodes', 0)}  |  Assets: {n}  |  Buttons: {stats.get('buttons', 0)}  |  "
      f"Text labels: {stats.get('texts', 0)}")
    A(f"- AI images: {stats.get('ai_images', 0)} via `{gateway_summary.get('image_provider', 'local')}`  |  "
      f"Text model: `{gateway_summary.get('text_provider', 'local')}`")
    A(f"- Render time: {stats.get('elapsed', 0):.1f}s")
    A("")
    A("---")
    A("")
    A("_Generated by **Roblox UI Forge** — " + ("أداة توليد واجهات روبلوكس من وصف نصي." if ar else
                                               "text-to-UI generator for Roblox._"))
    return "\n".join(lines)
