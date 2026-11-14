"""Per-game skins: role -> (colour index, sprite). Skin shuffle permutes object colours by seed
so no player can memorise "red means key". Structural roles keep fixed colours. Linked roles
("@key") share the colour of the role they point to (a door matches its key)."""
from __future__ import annotations

from .. import components as comps
from ..core.rng import rng_for
from ..render.colors import OBJECT_POOL as POOL

FIXED = {"floor", "wall", "budget_bar", "budget_empty"}


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
    raw = _roles_for(rules)
    if shuffle:
        rng = rng_for(family, seed, "skin")
        movable = sorted(r for r, (col, _) in raw.items() if r not in FIXED and not isinstance(col, str))
        colours = POOL[:]
        rng.shuffle(colours)
        raw = dict(raw)
        for i, r in enumerate(movable):
            raw[r] = (colours[i % len(colours)], raw[r][1])
    return comps.resolve_links(raw)
