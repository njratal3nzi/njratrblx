"""Roblox UI Forge — web server.

Run directly (works locally, in this sandbox, and on Google Colab)::

    python app.py            # serves http://0.0.0.0:8000
    python app.py --port 7860

The server is intentionally tolerant: the AI layer degrades to the deterministic
engine, so the "Generate" button always yields a ZIP.
"""
from __future__ import annotations

import argparse
import json
import threading
import time
import traceback
import uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from forge import pipeline
from forge.brief import PRESETS, SCREEN_KINDS
from forge.config import SETTINGS
from forge.themes import style_names

WEB = Path(__file__).resolve().parent / "web"

app = FastAPI(title="Roblox UI Forge", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])

_lock = threading.Lock()
JOBS: dict[str, dict] = {}
GATEWAY = None          # lazily created Gateway for probing / settings


def _gateway():
    global GATEWAY
    if GATEWAY is None:
        from forge.ai.gateway import Gateway
        GATEWAY = Gateway(settings=SETTINGS)
    return GATEWAY


class GenerateRequest(BaseModel):
    prompt: str = ""
    kind: str | None = None
    style: str | None = None
    density: str | None = None
    dark: bool | None = None
    radius: int | None = None
    lang: str | None = None
    use_llm: bool = True
    use_ai_images: bool = True
    export_states: bool = True


class GatewaySettings(BaseModel):
    providers: list[str] | None = None
    openrouter_key: str | None = None
    groq_key: str | None = None
    openai_key: str | None = None
    use_llm: bool | None = None
    use_ai_images: bool | None = None


def _run_job(job_id: str, req: GenerateRequest) -> None:
    job = JOBS[job_id]

    def push(line: str) -> None:
        with _lock:
            job["log"].append(line)

    try:
        job["status"] = "running"
        result = pipeline.run(
            req.prompt or req.kind or "main menu", kind=req.kind, style=req.style,
            density=req.density, dark=req.dark, radius=req.radius, lang=req.lang,
            use_llm=req.use_llm, use_ai_images=req.use_ai_images,
            export_states=req.export_states, settings=SETTINGS, log=push,
        )
        # persist previews so they can be served from disk
        web_dir = result.zip_path.parent / "web"
        web_dir.mkdir(parents=True, exist_ok=True)
        for name, img in result.previews.items():
            img.save(web_dir / f"{name}.png", "PNG")
        with _lock:
            job.update({
                "status": "done",
                "result": result.to_public(),
                "web_dir": str(web_dir),
                "zip_path": str(result.zip_path),
                "finished_at": time.time(),
            })
    except Exception as exc:
        with _lock:
            job.update({"status": "error", "error": f"{type(exc).__name__}: {exc}",
                        "trace": traceback.format_exc()})
        logs.put(f"! error: {exc}")
    finally:
        with _lock:
            job.setdefault("log", [])


def _spawn(req: GenerateRequest) -> str:
    job_id = uuid.uuid4().hex[:10]
    with _lock:
        JOBS[job_id] = {"id": job_id, "status": "queued", "log": [], "result": None,
                        "created_at": time.time()}
    t = threading.Thread(target=_run_job, args=(job_id, req), daemon=True)
    t.start()
    return job_id


# ------------------------------------------------------------------ routes

@app.get("/", response_class=HTMLResponse)
def index() -> Response:
    return HTMLResponse((WEB / "index.html").read_text(encoding="utf-8"))


@app.get("/api/health")
def health():
    return {"ok": True, "version": "1.0.0", "time": time.time()}


@app.get("/api/meta")
def meta():
    return {"styles": style_names(), "kinds": [{"id": k, "ar": v["ar"], "en": v["en"]}
                                               for k, v in SCREEN_KINDS.items()],
            "presets": PRESETS, "fonts": __import__("forge").fonts.font_report(),
            "settings": SETTINGS.to_public_dict()}


@app.get("/api/gateway")
def gateway_status():
    return _gateway().probe()


@app.post("/api/gateway")
def gateway_update(body: GatewaySettings):
    if body.providers is not None:
        SETTINGS.providers = body.providers
    if body.openrouter_key is not None:
        SETTINGS.openrouter_key = body.openrouter_key
    if body.groq_key is not None:
        SETTINGS.groq_key = body.groq_key
    if body.openai_key is not None:
        SETTINGS.openai_key = body.openai_key
    if body.use_llm is not None:
        SETTINGS.use_llm_planner = body.use_llm
    if body.use_ai_images is not None:
        SETTINGS.use_ai_images = body.use_ai_images
    _gateway()._probe_cache = {}
    return {"ok": True, "summary": _gateway().active_summary(), "probe": _gateway().probe(force=True)}


@app.post("/api/generate")
def generate(req: GenerateRequest):
    if not req.prompt and not req.kind:
        raise HTTPException(400, "Provide a prompt or a screen kind")
    return {"job_id": _spawn(req)}


@app.get("/api/jobs")
def jobs():
    with _lock:
        return [{"id": j["id"], "status": j["status"], "created_at": j["created_at"]}
                for j in sorted(JOBS.values(), key=lambda j: -j["created_at"])[:20]]


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    with _lock:
        job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return job


@app.get("/api/jobs/{job_id}/zip")
def job_zip(job_id: str):
    with _lock:
        job = JOBS.get(job_id)
    if not job or not job.get("zip_path"):
        raise HTTPException(404, "zip not ready")
    path = Path(job["zip_path"])
    return FileResponse(path, media_type="application/zip", filename=path.name)


@app.get("/api/jobs/{job_id}/img/{name}")
def job_img(job_id: str, name: str):
    with _lock:
        job = JOBS.get(job_id)
    if not job or not job.get("web_dir"):
        raise HTTPException(404, "previews not ready")
    safe = "".join(c for c in name if c.isalnum() or c in "-_.")
    path = Path(job["web_dir"]) / f"{safe}.png"
    if not path.exists():
        raise HTTPException(404, "image not found")
    return FileResponse(path, media_type="image/png")


@app.get("/api/jobs/{job_id}/file/{path:path}")
def job_file(job_id: str, path: str):
    with _lock:
        job = JOBS.get(job_id)
    if not job or not job.get("zip_path"):
        raise HTTPException(404, "not ready")
    base = Path(job["zip_path"]).parent
    target = (base / path).resolve()
    if not str(target).startswith(str(base.resolve())):
        raise HTTPException(400, "bad path")
    if not target.exists():
        raise HTTPException(404, "file not found")
    return FileResponse(target)


def main() -> None:
    parser = argparse.ArgumentParser(description="Roblox UI Forge")
    parser.add_argument("--host", default=SETTINGS.host)
    parser.add_argument("--port", type=int, default=SETTINGS.port)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    print(f"[Roblox UI Forge] serving on http://{args.host}:{args.port}")
    uvicorn.run("app:app", host=args.host, port=args.port, reload=args.reload, log_level="info")


if __name__ == "__main__":
    main()
