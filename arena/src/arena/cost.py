"""Token/cost accounting and pre-sweep estimates."""
from __future__ import annotations

from dataclasses import dataclass, field

# Rough per-step token profile for the estimate (refined from real traces after the first sweep).
EST_PROMPT_TOKENS = 900          # system + notes + recent history
EST_TEXT_GRID_TOKENS = 2600      # 64 rows x 64 hex chars
EST_IMAGE_TOKENS = 400           # 512x512 PNG
EST_RLE_TOKENS = 700             # run-length rows (measured on fake-engine frames: see tests)
EST_OUT_TOKENS = {"low": 400, "medium": 1200, "high": 2500, "xhigh": 4000, "max": 6000, None: 800}


def price(model: dict, tokens_in: int, tokens_out: int) -> float | None:
    pi, po = model.get("price_in"), model.get("price_out")
    if pi is None or po is None:
        return None
    return tokens_in / 1e6 * pi + tokens_out / 1e6 * po


def est_tokens_per_step(model: dict, input_modes, effort: str | None) -> tuple[int, int]:
    modes = [input_modes] if isinstance(input_modes, str) else list(input_modes)
    per = {"text": EST_TEXT_GRID_TOKENS, "image": EST_IMAGE_TOKENS, "rle": EST_RLE_TOKENS}
    tin = EST_PROMPT_TOKENS + sum(per.get(m, 0) for m in modes)
    return tin, EST_OUT_TOKENS.get(effort, EST_OUT_TOKENS[None])


@dataclass
class Meter:
    """Running usage for one game; checked against per-game budgets."""
    model: dict
    tokens_in: int = 0
    tokens_out: int = 0
    calls: int = 0
    unknown_price: bool = False
    per_call: list = field(default_factory=list)

    def add(self, tin: int, tout: int) -> dict:
        self.tokens_in += tin
        self.tokens_out += tout
        self.calls += 1
        c = price(self.model, tin, tout)
        if c is None:
            self.unknown_price = True
            c = 0.0
        return {"in": tin, "out": tout, "cost_usd": round(c, 6)}

    @property
    def cost_usd(self) -> float:
        return price(self.model, self.tokens_in, self.tokens_out) or 0.0
