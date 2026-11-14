"""Seeded randomness. Never use the global `random` module or builtin `hash()` in the engine.

Every random stream is derived from a tuple of parts (seed, level, attempt, purpose...) via
SHA-256, so the same parts always give the same stream on every machine and Python version.
"""
from __future__ import annotations

import hashlib
import random


def derive_seed(*parts: object) -> int:
    text = "|".join(str(p) for p in parts)
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")


def rng_for(*parts: object) -> random.Random:
    return random.Random(derive_seed(*parts))


def short_hash(text: str, n: int = 8) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:n]
