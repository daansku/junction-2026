"""Claude via the Anthropic SDK. No server-side model fallback: a leaderboard row must be one model."""
from __future__ import annotations

import base64
import time

import anthropic

from .base import Reply, with_retries


class AnthropicProvider:
    def __init__(self, model: dict):
        self.model = model
        self.client = anthropic.Anthropic()  # ANTHROPIC_API_KEY or `ant auth login` profile

    def complete(self, system, parts, effort=None, max_tokens=16000) -> Reply:
        content = []
        for p in parts:
            if p["type"] == "text":
                content.append({"type": "text", "text": p["text"]})
            else:
                content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                             "data": base64.b64encode(p["data"]).decode()}})
        kw = {}
        if effort and effort in (self.model.get("efforts") or []):
            kw["output_config"] = {"effort": effort}
        t0 = time.time()
        resp = with_retries(lambda: self.client.messages.create(
            model=self.model["api_model"], max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": content}], **kw))
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        u = resp.usage
        tin = (u.input_tokens or 0) + (getattr(u, "cache_read_input_tokens", 0) or 0) + \
              (getattr(u, "cache_creation_input_tokens", 0) or 0)
        return Reply(text=text, tokens_in=tin, tokens_out=u.output_tokens or 0,
                     latency_ms=int((time.time() - t0) * 1000), refused=resp.stop_reason == "refusal",
                     raw_stop=resp.stop_reason)
