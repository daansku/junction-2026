"""Offline fake model for harness tests: answers in the required JSON shape, moves randomly."""
from __future__ import annotations

import json
import random

from .base import Reply


class MockProvider:
    def __init__(self, model: dict):
        self.model = model
        self.rng = random.Random(model.get("seed", 0))
        self.calls = 0

    def complete(self, system, parts, effort=None, max_tokens=16000) -> Reply:
        self.calls += 1
        if self.model.get("garbage_every") and self.calls % self.model["garbage_every"] == 0:
            return Reply(text="I think I'll go left!", tokens_in=100, tokens_out=10)
        a = self.rng.choice(["ACTION1", "ACTION2", "ACTION3", "ACTION4"])
        out = {"notes": f"call {self.calls}", "hypothesis": "the yellow bar is my budget",
               "belief": "playing", "action": a}
        return Reply(text="```json\n" + json.dumps(out) + "\n```", tokens_in=1200, tokens_out=60, latency_ms=1)
