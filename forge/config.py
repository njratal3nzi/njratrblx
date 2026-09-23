"""Global configuration for Roblox UI Forge.

Everything can be overridden with environment variables, which makes the same
code base work on a laptop, in this sandbox, and on Google Colab.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "forge" / "assets" / "fonts"


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "y"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    # --- web server ---
    host: str = field(default_factory=lambda: _env("FORGE_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: _env_int("FORGE_PORT", 8000))

    # --- output ---
    out_dir: Path = field(default_factory=lambda: Path(_env("FORGE_OUT", str(ROOT / "out"))))
    cache_dir: Path = field(default_factory=lambda: Path(_env("FORGE_CACHE", str(ROOT / "work" / "cache"))))

    # --- AI gateway ---
    # provider chain is tried in order until one answers.
    providers: list[str] = field(
        default_factory=lambda: [
            p.strip()
            for p in _env("FORGE_PROVIDERS", "pollinations,openrouter,local").split(",")
            if p.strip()
        ]
    )
    pollinations_base: str = field(
        default_factory=lambda: _env("FORGE_POLLINATIONS_BASE", "https://image.pollinations.ai")
    )
    pollinations_text_base: str = field(
        default_factory=lambda: _env("FORGE_POLLINATIONS_TEXT", "https://text.pollinations.ai")
    )
    image_model: str = field(default_factory=lambda: _env("FORGE_IMAGE_MODEL", "flux"))
    text_model: str = field(default_factory=lambda: _env("FORGE_TEXT_MODEL", "openai"))
    openrouter_base: str = field(default_factory=lambda: _env("FORGE_OPENROUTER_BASE", "https://openrouter.ai/api/v1"))
    openrouter_key: str = field(default_factory=lambda: _env("OPENROUTER_API_KEY", ""))
    openrouter_model: str = field(default_factory=lambda: _env("FORGE_OPENROUTER_MODEL", "openai/gpt-4o-mini"))
    groq_key: str = field(default_factory=lambda: _env("GROQ_API_KEY", ""))
    groq_model: str = field(default_factory=lambda: _env("FORGE_GROQ_MODEL", "llama-3.3-70b-versatile"))
    openai_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY", ""))
    openai_base: str = field(default_factory=lambda: _env("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    openai_model: str = field(default_factory=lambda: _env("FORGE_OPENAI_MODEL", "gpt-4o-mini"))

    request_timeout: float = field(default_factory=lambda: float(_env("FORGE_TIMEOUT", "45")))
    probe_timeout: float = field(default_factory=lambda: float(_env("FORGE_PROBE_TIMEOUT", "6")))
    max_retries: int = field(default_factory=lambda: _env_int("FORGE_RETRIES", "2"))
    concurrency: int = field(default_factory=lambda: _env_int("FORGE_CONCURRENCY", "6"))

    use_llm_planner: bool = field(default_factory=lambda: _env_bool("FORGE_USE_LLM", True))
    use_ai_images: bool = field(default_factory=lambda: _env_bool("FORGE_AI_IMAGES", True))

    # --- render quality ---
    rscale: int = field(default_factory=lambda: _env_int("FORGE_RSCALE", 2))  # export supersampling
    preview_scale: float = field(default_factory=lambda: float(_env("FORGE_PREVIEW_SCALE", "0.5")))
    canvas_w: int = field(default_factory=lambda: _env_int("FORGE_CANVAS_W", 1920))
    canvas_h: int = field(default_factory=lambda: _env_int("FORGE_CANVAS_H", 1080))

    def __post_init__(self) -> None:
        self.out_dir = Path(self.out_dir)
        self.cache_dir = Path(self.cache_dir)

    def ensure_dirs(self) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        FONT_DIR.mkdir(parents=True, exist_ok=True)

    def to_public_dict(self) -> dict:
        d = asdict(self)
        d["out_dir"] = str(d["out_dir"])
        d["cache_dir"] = str(d["cache_dir"])
        for k in ("openrouter_key", "groq_key", "openai_key"):
            d[k] = "***" if d.get(k) else ""
        return d


SETTINGS = Settings()
SETTINGS.ensure_dirs()
