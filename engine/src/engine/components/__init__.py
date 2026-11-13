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


def default_roles() -> dict[str, tuple[int, str]]:
    from ..render import colors as C
    roles: dict[str, tuple[int, str]] = {"player": (C.BLUE, "full"), "floor": (C.FLOOR, "full")}
    for name in sorted(REGISTRY):
        roles.update(REGISTRY[name].roles)
    return roles


from . import walls, goal, budget  # noqa: E402,F401  (registration side effects)
