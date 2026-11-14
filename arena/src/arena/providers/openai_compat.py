"""One adapter for every OpenAI-compatible endpoint: Google Gemini (compat layer), NVIDIA, featherless,
Verda deployments, Modal-served fine-tunes. Base URLs checked against provider docs on 2026-11-14:
  google      https://generativelanguage.googleapis.com/v1beta/openai/  (ai.google.dev/gemini-api/docs/openai)
  nvidia      https://integrate.api.nvidia.com/v1                       (build.nvidia.com)
  featherless https://api.featherless.ai/v1                             (featherless.ai/docs/getting-started)
  verda       per-deployment URL, OpenAI-compatible (vLLM/SGLang)       -> VERDA_BASE_URL
  modal       our own vLLM endpoint                                     -> MODAL_BASE_URL
"""
from __future__ import annotations

import base64
import os
import time

from openai import OpenAI

from .base import Reply, with_retries

ENDPOINTS = {
    "google": (lambda: "https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY"),
    "nvidia": (lambda: "https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY"),
    "featherless": (lambda: "https://api.featherless.ai/v1", "FEATHERLESS_API_KEY"),
    "verda": (lambda: os.environ.get("VERDA_BASE_URL", ""), "VERDA_INFERENCE_KEY"),
    "modal": (lambda: os.environ.get("MODAL_BASE_URL", ""), "MODAL_API_KEY"),
    "openai": (lambda: os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"), "OPENAI_API_KEY"),
}


def make_client(provider: str, base_url: str | None = None, api_key_env: str | None = None) -> OpenAI:
    """`base_url` / `api_key_env` come from a model's registry entry and override the provider
    defaults, so one provider (e.g. verda) can serve several deployments with different keys."""
    url_fn, key_env = ENDPOINTS[provider]
    key_env = api_key_env or key_env
    url = base_url or url_fn()
    if not url:
        raise RuntimeError(f"no base URL for provider {provider}; set it in .env")
    return OpenAI(base_url=url, api_key=os.environ.get(key_env) or "EMPTY")


class OpenAICompatProvider:
    def __init__(self, model: dict):
        self.model = model
        self.client = make_client(model["provider"], model.get("base_url"), model.get("api_key_env"))

    def complete(self, system, parts, effort=None, max_tokens=16000) -> Reply:
        if all(p["type"] == "text" for p in parts):
            # one string, joined exactly like arena.dataset.parts_to_text (fine-tune train == inference)
            content = "\n\n".join(p["text"] for p in parts)
        else:
            content = []
            for p in parts:
                if p["type"] == "text":
                    content.append({"type": "text", "text": p["text"]})
                else:
                    url = "data:image/png;base64," + base64.b64encode(p["data"]).decode()
                    content.append({"type": "image_url", "image_url": {"url": url}})
        kw = {"max_tokens": max_tokens}
        if effort and effort in (self.model.get("efforts") or []):
            kw["reasoning_effort"] = effort
        t0 = time.time()
        resp = with_retries(lambda: self.client.chat.completions.create(
            model=self.model["api_model"],
            messages=[{"role": "system", "content": system}, {"role": "user", "content": content}], **kw))
        ch = resp.choices[0]
        u = resp.usage
        return Reply(text=ch.message.content or "", tokens_in=getattr(u, "prompt_tokens", 0) or 0,
                     tokens_out=getattr(u, "completion_tokens", 0) or 0,
                     latency_ms=int((time.time() - t0) * 1000),
                     refused=ch.finish_reason == "content_filter", raw_stop=ch.finish_reason)


def list_remote_models(provider: str) -> list[str]:
    """Live model ids from the provider's /models endpoint (used by `arena models --check`)."""
    return [m.id for m in make_client(provider).models.list()]
