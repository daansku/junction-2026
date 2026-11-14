"""Component registry. Add a component: new file here, decorate the class with @register,
import the module at the bottom of this file."""
from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.level import Level
    from .base import Component

REGISTRY: dict[str, "Component"] = {}


def register(cls):
    inst = cls()
    if not inst.name:
        raise ValueError(f"{cls.__name__} has no name")
    if inst.name in REGISTRY:
        raise ValueError(f"duplicate component {inst.name}")
    REGISTRY[inst.name] = inst
    return cls


def always_on() -> list[str]:
    return sorted(n for n, c in REGISTRY.items() if c.always_on)


def active(level: "Level") -> tuple["Component", ...]:
    return _active(tuple(level.rules))


@lru_cache(maxsize=None)
def _active(rules: tuple[str, ...]) -> tuple["Component", ...]:
    names = set(always_on()) | set(rules)
    missing = names - REGISTRY.keys()
    if missing:
        raise KeyError(f"unknown components: {sorted(missing)}")
    return tuple(sorted((REGISTRY[n] for n in names), key=lambda c: (c.layer, c.name)))


def raw_roles() -> dict[str, tuple[int | str, str]]:
    """Role -> (colour or "@other_role", sprite). "@x" = same colour as role x."""
    from ..render import colors as C
    roles: dict = {"player": (C.BLUE, "full"), "floor": (C.FLOOR, "full")}
    for name in sorted(REGISTRY):
        roles.update(REGISTRY[name].roles)
    return roles


def resolve_links(roles: dict) -> dict[str, tuple[int, str]]:
    out = {}
    for r, (col, spr) in roles.items():
        seen = 0
        while isinstance(col, str):
            col = roles[col.lstrip("@")][0]
            seen += 1
            if seen > 8:
                raise ValueError(f"role link cycle at {r}")
        out[r] = (int(col), spr)
    return out


def default_roles() -> dict[str, tuple[int, str]]:
    return resolve_links(raw_roles())


def tiers() -> dict[str, int]:
    return {n: c.tier for n, c in REGISTRY.items() if not c.always_on}


# registration side effects; one module per component
from . import walls, goal, budget  # noqa: E402,F401  tier 0
from . import keys_doors, plates_gates, teleporters, hazards, push_blocks, one_way, ice  # noqa: E402,F401  tier 1
