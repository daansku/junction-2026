"""Provider adapters. Every adapter takes the same (system, parts) input and returns a Reply.

parts: list of {"type": "text", "text": str} | {"type": "image_png", "data": bytes}
"""
from __future__ import annotations

from .base import Provider, Reply


def get_provider(model: dict) -> Provider:
    p = model["provider"]
    if p == "anthropic":
        from .anthropic_provider import AnthropicProvider
        return AnthropicProvider(model)
    if p == "mock":
        from .mock_provider import MockProvider
        return MockProvider(model)
    from .openai_compat import OpenAICompatProvider
    return OpenAICompatProvider(model)


__all__ = ["Provider", "Reply", "get_provider"]
