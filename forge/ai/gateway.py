"""Pluggable AI gateway.

Priority chain (default): pollinations -> openrouter -> local.

* ``pollinations`` is a free, key-less, effectively unlimited gateway.  It is the
  default so the tool works the moment you run it, including on Google Colab.
* ``openrouter`` / ``groq`` / ``openai`` are used when a key is supplied
  (OpenRouter exposes free models too).
* ``local`` never touches the network: the deterministic design engine and the
  procedural texture generator take over, so a full ZIP is still produced.

Every network call is time-boxed and failure-tolerant: a provider that is down
is skipped, never fatal.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
from dataclasses import dataclass, field

import requests

from ..config import Settings, SETTINGS


@dataclass
class ProviderStatus:
    name: str
    kind: str                      # text | image | both | none
    available: bool
    latency_ms: int = 0
    detail: str = ""
    needs_key: bool = False


@dataclass
class Gateway:
    settings: Settings = field(default_factory=lambda: SETTINGS)
    _probe_cache: dict = field(default_factory=dict)
    last_text_provider: str = "local"
    last_image_provider: str = "local"
    calls: int = 0
    failures: int = 0

    # ------------------------------------------------------------------ keys
    def key_for(self, provider: str) -> str:
        return {
            "openrouter": self.settings.openrouter_key,
            "groq": self.settings.groq_key,
            "openai": self.settings.openai_key,
        }.get(provider, "")

    def enabled(self) -> list[str]:
        return [p for p in self.settings.providers if p in ("pollinations", "openrouter", "groq", "openai", "local")]

    # ------------------------------------------------------------------ low level
    def _request(self, method: str, url: str, timeout: float | None = None, **kw) -> requests.Response | None:
        timeout = timeout or self.settings.request_timeout
        for attempt in range(max(1, self.settings.max_retries + 1)):
            try:
                self.calls += 1
                r = requests.request(method, url, timeout=timeout, **kw)
                if r.status_code == 200:
                    return r
                if r.status_code in (429, 500, 502, 503, 504) and attempt < self.settings.max_retries:
                    time.sleep(0.8 * (attempt + 1))
                    continue
                self.failures += 1
                return None
            except Exception:
                self.failures += 1
                if attempt >= self.settings.max_retries:
                    return None
                time.sleep(0.4 * (attempt + 1))
        return None

    # ------------------------------------------------------------------ text
    def text(self, system: str, user: str, json_mode: bool = False,
             max_tokens: int = 1600, temperature: float = 0.6) -> tuple[str, str]:
        """Returns (text, provider).  ('' , 'local') when nothing answered."""
        if not self.settings.use_llm_planner:
            return "", "local"
        for provider in self.enabled():
            if provider == "local":
                continue
            if provider in ("openrouter", "groq", "openai") and not self.key_for(provider):
                continue
            out = self._text_with(provider, system, user, json_mode, max_tokens, temperature)
            if out:
                self.last_text_provider = provider
                return out, provider
        return "", "local"

    def _text_with(self, provider: str, system: str, user: str, json_mode: bool,
                   max_tokens: int, temperature: float) -> str:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        if provider == "pollinations":
            body = {"model": self.settings.text_model, "messages": messages, "temperature": temperature}
            if json_mode:
                body["response_format"] = {"type": "json_object"}
            r = self._request("POST", f"{self.settings.pollinations_text_base}/openai",
                              timeout=min(35.0, self.settings.request_timeout),
                              json=body, headers={"Accept": "application/json"})
            if r is None:  # fallback: plain GET endpoint
                q = urllib.parse.quote(f"{system}\n\n{user}")[:1800]
                r = self._request("GET", f"{self.settings.pollinations_text_base}/{q}")
                return r.text.strip() if r is not None else ""
            return _extract_message(r)
        if provider in ("openrouter", "openai"):
            base = self.settings.openrouter_base if provider == "openrouter" else self.settings.openai_base
            model = self.settings.openrouter_model if provider == "openrouter" else self.settings.openai_model
            headers = {"Authorization": f"Bearer {self.key_for(provider)}", "Content-Type": "application/json"}
            if provider == "openrouter":
                headers["HTTP-Referer"] = "https://github.com/roblox-ui-forge"
                headers["X-Title"] = "Roblox UI Forge"
            body = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
            if json_mode:
                body["response_format"] = {"type": "json_object"}
            r = self._request("POST", f"{base.rstrip('/')}/chat/completions", json=body, headers=headers)
            return _extract_message(r) if r is not None else ""
        if provider == "groq":
            r = self._request(
                "POST", "https://api.groq.com/openai/v1/chat/completions",
                json={"model": self.settings.groq_model, "messages": messages,
                      "temperature": temperature, "max_tokens": max_tokens},
                headers={"Authorization": f"Bearer {self.key_for(provider)}", "Content-Type": "application/json"})
            return _extract_message(r) if r is not None else ""
        return ""

    # ------------------------------------------------------------------ images
    def image(self, prompt: str, width: int = 1024, height: int = 1024,
              seed: int | None = None) -> tuple[bytes | None, str]:
        if not self.settings.use_ai_images:
            return None, "local"
        for provider in self.enabled():
            if provider == "local":
                continue
            data = self._image_with(provider, prompt, width, height, seed)
            if data:
                self.last_image_provider = provider
                return data, provider
        return None, "local"

    def _image_with(self, provider: str, prompt: str, width: int, height: int, seed: int | None) -> bytes | None:
        seed = int(seed if seed is not None else (abs(hash(prompt)) % 99999))
        if provider == "pollinations":
            url = (f"{self.settings.pollinations_base}/prompt/{urllib.parse.quote(prompt[:900])}"
                   f"?width={int(width)}&height={int(height)}&seed={seed}&nologo=true&model={self.settings.image_model}")
            r = self._request("GET", url, headers={"Accept": "image/*"})
            if r is not None and len(r.content) > 800:
                return r.content
        if provider in ("openai", "openrouter"):
            base = self.settings.openai_base if provider == "openai" else self.settings.openrouter_base
            r = self._request("POST", f"{base.rstrip('/')}/images/generations",
                              json={"model": "gpt-image-1", "prompt": prompt[:900], "size": "1024x1024", "n": 1},
                              headers={"Authorization": f"Bearer {self.key_for(provider)}"})
            if r is not None:
                try:
                    item = r.json()["data"][0]
                    if item.get("url"):
                        rr = self._request("GET", item["url"])
                        return rr.content if rr is not None else None
                except Exception:
                    return None
        return None

    # ------------------------------------------------------------------ probing
    def probe(self, force: bool = False) -> dict[str, dict]:
        if self._probe_cache and not force:
            return self._probe_cache
        out: dict[str, dict] = {}
        for p in self.enabled():
            st = self._probe_one(p)
            out[p] = {"name": st.name, "kind": st.kind, "available": st.available,
                      "latency_ms": st.latency_ms, "detail": st.detail, "needs_key": st.needs_key}
        self._probe_cache = out
        return out

    def _probe_one(self, name: str) -> ProviderStatus:
        t = time.time()
        if name == "local":
            return ProviderStatus("local", "both", True, 0, "deterministic engine, no network", needs_key=False)
        if name == "pollinations":
            ok_txt = ok_img = False
            try:
                resp = requests.get(f"{self.settings.pollinations_text_base}/", timeout=self.settings.probe_timeout)
                ok_txt = resp.status_code < 500
            except Exception:
                pass
            try:
                resp = requests.get(f"{self.settings.pollinations_base}/", timeout=self.settings.probe_timeout)
                ok_img = resp.status_code < 500
            except Exception:
                pass
            ok = ok_txt or ok_img
            ms = int((time.time() - t) * 1000)
            detail = ("free & key-less (text %s / image %s)" % ("ok" if ok_txt else "down", "ok" if ok_img else "down")
                      if ok else "unreachable from this network")
            return ProviderStatus("pollinations", "both", ok, ms, detail)
        key = self.key_for(name)
        if not key:
            return ProviderStatus(name, "text", False, 0, "no API key set", needs_key=True)
        base = {"openrouter": f"{self.settings.openrouter_base.rstrip('/')}/models",
                "groq": "https://api.groq.com/openai/v1/models",
                "openai": f"{self.settings.openai_base.rstrip('/')}/models"}.get(name, "")
        try:
            resp = requests.get(base, timeout=self.settings.probe_timeout,
                                headers={"Authorization": f"Bearer {key}"})
            ok = resp.status_code == 200
            detail = "key accepted" if ok else f"HTTP {resp.status_code}"
        except Exception as exc:
            ok, detail = False, f"{type(exc).__name__}"
        return ProviderStatus(name, "text", ok, int((time.time() - t) * 1000), detail, needs_key=True)

    def active_summary(self) -> dict:
        return {"providers": self.enabled(), "text_provider": self.last_text_provider,
                "image_provider": self.last_image_provider, "calls": self.calls, "failures": self.failures}


def _extract_message(resp: requests.Response | None) -> str:
    if resp is None:
        return ""
    try:
        data = resp.json()
    except Exception:
        return (resp.text or "").strip()
    if isinstance(data, dict):
        ch = data.get("choices")
        if ch:
            msg = ch[0].get("message") or {}
            return (msg.get("content") or "").strip()
        if "output_text" in data:
            return str(data["output_text"]).strip()
    return json.dumps(data)[:4000]


def extract_json(text: str) -> dict | None:
    """Pull the first JSON object out of an LLM reply (tolerates prose + fences)."""
    if not text:
        return None
    text = re.sub(r"```(?:json)?", " ", text)
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[start:i + 1])
                    return obj if isinstance(obj, dict) else None
                except Exception:
                    break
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None
