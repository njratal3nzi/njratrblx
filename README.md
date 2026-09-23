# Roblox UI Forge ⚡

> **اكتب جملة واحدة — واستلم واجهة روبلوكس كاملة.**
> *Write one sentence — receive a complete Roblox UI kit.*

Roblox UI Forge is a text-to-UI generator. Describe the screen you want (in Arabic or
English) and it builds a **full design system + component tree**, renders every asset as a
transparent 9-sliceable PNG, and packages everything into a ready-to-use ZIP containing:

- `assets/` — buttons (4 states), panels, icons, controls, backgrounds
- `luau/` — a dependency-free runtime library + a generated builder for your exact screen
- `studio/` — a zero-upload Command-Bar preview + an `.rbxmx` model file
- `preview_full.png` / `preview_showcase.png` — renders of the finished design
- `design-system.json` / `manifest.json` — machine readable tokens & 9-slice maps

It ships with a polished **web UI** that runs anywhere: laptop, CI, or **Google Colab**.

---

## ✨ What makes it special

- **One sentence in, full kit out.** A rule-based brief parser (Arabic + English) detects the
  screen type, style, palette, density and features, then a deterministic layout engine builds
  16 different screen archetypes (shop, inventory, HUD, leaderboard, loading, wheel, chat, …).
- **Real AI layer, optional.** Uses the free, key-less **Pollinations** gateway for LLM copy
  refinement and AI backdrops. Add OpenRouter / Groq / OpenAI keys for better models. **If the
  network is down, the deterministic engine + procedural textures still produce a complete ZIP** —
  the tool never hard-fails.
- **Assets are honest.** Text is *never* baked into images: every label is a real `TextLabel`,
  and every scalable asset is exported with a Roblox `SliceCenter` so it stretches cleanly.
- **Full RTL.** Arabic briefs produce mirrored, right-to-left layouts with shaped Arabic text.

---

## 🚀 Run it

### Local
```bash
./run.sh                 # installs deps if needed, serves http://0.0.0.0:8000
```
or
```bash
pip install -r requirements.txt
python app.py            # --host 0.0.0.0 --port 8000
```

### Google Colab (one cell)
```python
!pip install -q pillow fastapi "uvicorn[standard]" requests arabic-reshaper python-bidi
!git clone -q https://github.com/YOUR_USER/njratrblx forge  # or upload this repo as a zip
%cd forge
!python app.py --port 8000 &   # then run colab/tunnel.py below to get a public URL
```
See `colab/RobloxUI_Forge_Colab.ipynb` for a ready notebook that also opens a public tunnel.

### Library only
```python
from forge import pipeline
r = pipeline.run("متجر نيون احترافي مع تبويبات وزر شراء")
print(r.zip_path)
```

---

## 🧩 Importing into Roblox

1. Upload the PNGs in `assets/` → **Creator Dashboard → Development Items → Images**.
2. Paste the `rbxassetid://` values into the `ASSETS` table in `luau/Design_<slug>.lua`.
3. Put `luau/UiForge.lua` in `ReplicatedStorage` as a ModuleScript named `UiForge`.
4. Run the design script (StarterPlayerScripts) — done.

**Instant preview, no uploads:** paste `studio/Studio_QuickBuild.lua` into Studio's Command
Bar (View → Command Bar) and it builds the layout with solid colours immediately.

---

## ⚙️ Environment variables

| var | default | purpose |
|---|---|---|
| `FORGE_PORT` | `8000` | web port |
| `FORGE_PROVIDERS` | `pollinations,openrouter,local` | AI provider chain |
| `OPENROUTER_API_KEY` / `GROQ_API_KEY` / `OPENAI_API_KEY` | — | optional better models |
| `FORGE_USE_LLM` / `FORGE_AI_IMAGES` | `1` | enable/disable AI |
| `FORGE_RSCALE` | `2` | export supersampling |

## 🧪 Tests
```bash
pytest -q
```
