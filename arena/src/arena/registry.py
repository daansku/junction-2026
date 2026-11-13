from __future__ import annotations

from pathlib import Path

import yaml

REGISTRY = Path(__file__).resolve().parents[2] / "models.yaml"
REQUIRED = ("id", "display_name", "provider", "api_model", "tier", "input_modes", "price_in", "price_out")


def load_models(path: Path = REGISTRY) -> dict[str, dict]:
    models = yaml.safe_load(path.read_text()) or []
    out = {}
    for m in models:
        missing = [k for k in REQUIRED if k not in m]
        if missing:
            raise ValueError(f"model {m.get('id')} missing {missing}")
        if m["id"] in out:
            raise ValueError(f"duplicate model id {m['id']}")
        out[m["id"]] = m
    return out


def usable(m: dict) -> bool:
    return bool(m.get("verified")) and bool(m.get("api_model"))
