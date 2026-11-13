"""Per-game skins: role -> (colour index, sprite). Skin shuffle permutes object colours by seed
so no player can memorise "red means key". Structural roles keep fixed colours."""
from __future__ import annotations

from .. import components as comps
from ..core.rng import rng_for

FIXED = {"floor", "wall", "budget_bar", "budget_empty"}
from ..render.colors import OBJECT_POOL as POOL


def make_skin(seed: int, family: str, shuffle: bool) -> dict[str, tuple[int, str]]:
    roles = comps.default_roles()
    if not shuffle:
        return roles
    rng = rng_for(family, seed, "skin")
    movable = sorted(r for r in roles if r not in FIXED)
    colours = POOL[:]
    rng.shuffle(colours)
    out = dict(roles)
    for i, r in enumerate(movable):
        out[r] = (colours[i % len(colours)], roles[r][1])
    return out
