"""Per-game skins: role -> (colour index, sprite).

Skin shuffle permutes object colours AND object shapes by seed, so no player — human,
frontier model or fine-tuned model — can memorise "orange dot means key". Kept fixed:
structural roles (floor, wall, budget bar), the player (solid square), goal-like rings (the
ring means "a goal" in every game; which ring is real is part of the puzzle), and directional
arrows. Linked roles ("@key") share the colour of the role they point to.
"""
from __future__ import annotations

from .. import components as comps
from ..core.rng import rng_for
from ..render.colors import OBJECT_POOL as POOL

FIXED = {"floor", "wall", "budget_bar", "budget_empty", "hole"}
FIXED_SHAPE = {"player", "goal", "twin_goal", "decoy_a", "decoy_b", "one_way", "phase_wall",
               "health", "stamina"}
SHAPE_POOL = ["dot", "cross", "x", "corners", "checker", "frame_dot", "bars", "diag", "diamond",
              "half", "tri", "hbar", "vbar"]


def _roles_for(rules: list[str] | None) -> dict:
    raw = comps.raw_roles()
    if rules is None:
        return raw
    keep = {"player", "floor"}
    for n in set(comps.always_on()) | set(rules):
        keep |= set(comps.REGISTRY[n].roles)
    return {r: v for r, v in raw.items() if r in keep}


def make_skin(seed: int, family: str, shuffle: bool,
              rules: list[str] | None = None) -> dict[str, tuple[int, str]]:
    """rules: every rule used anywhere in the game (None = all registered roles)."""
    raw = dict(_roles_for(rules))
    if shuffle:
        rng = rng_for(family, seed, "skin")
        movable = sorted(r for r, (col, _) in raw.items() if r not in FIXED and not isinstance(col, str))
        colours = POOL[:]
        rng.shuffle(colours)
        for i, r in enumerate(movable):
            raw[r] = (colours[i % len(colours)], raw[r][1])
        shaped = sorted(r for r in raw if r not in FIXED and r not in FIXED_SHAPE)
        shapes = SHAPE_POOL[:]
        rng.shuffle(shapes)
        for i, r in enumerate(shaped):
            raw[r] = (raw[r][0], shapes[i % len(shapes)])
    return comps.resolve_links(raw)
