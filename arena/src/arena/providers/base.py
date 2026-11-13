from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Reply:
    text: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    refused: bool = False
    raw_stop: str | None = None
    extra: dict = field(default_factory=dict)


class Provider(Protocol):
    def complete(self, system: str, parts: list[dict], effort: str | None = None,
                 max_tokens: int = 16000) -> Reply: ...


def with_retries(fn, tries: int = 4, base: float = 2.0):
    """Retry transient failures (rate limits, 5xx, network). Last error propagates."""
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # provider SDKs raise different classes; classify by name
            name = type(e).__name__
            status = getattr(e, "status_code", None)
            transient = status in (408, 409, 429) or (status or 0) >= 500 or \
                any(k in name for k in ("RateLimit", "Timeout", "Connection", "Overloaded", "InternalServer"))
            if not transient or i == tries - 1:
                raise
            time.sleep(base * 2 ** i)
