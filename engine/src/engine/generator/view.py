"""View constraints (A1, eval-v6): change what the player SEES, never what the game does.

Opt-in per game through `GameSpec.view`, a comma list:
  * `fog<r>`   only cells within Chebyshev distance r of the player are drawn; every other grid cell
               shows the fog colour. Tests whether a player builds and remembers a map.
  * `glimpse`  with fog: the whole level is visible until the first move of the level (also after
               a RESET, which costs an action as always). One look, then play from memory.
  * `recolor`  from level 2 on, each level swaps the object colours by a fixed one-to-one map of the
               object palette (shapes, floor, walls and HUD bars stay). Objects that share a colour
               (a key and its door) still share it; distinct objects stay distinct. Tests whether a
               player re-identifies objects by shape and behaviour instead of carrying over
               "colour X means Y" from the previous level.

Levels, rules, solver, optimal paths and budgets are untouched: generation never reads the view,
so a viewed game has exactly the levels of the same spec without a view (and stays provably
solvable). The settings live in `level.data["view"]` (part of the game id hash) and only
`render.frame.render` reads them.
"""
from __future__ import annotations

from typing import Any

from ..core.level import Level
from ..core.rng import rng_for
from ..render.colors import DARK_GREY, OBJECT_POOL

FOG = DARK_GREY   # used only by HUD bars and cracked_floor's "hole" (the builder refuses games with holes)


def parse(view: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for tok in (t.strip() for t in view.split(",")):
        if not tok:
            continue
        if tok.startswith("fog"):
            out["radius"] = int(tok[3:] or 2)
        elif tok == "glimpse":
            out["glimpse"] = True
        elif tok == "recolor":
            out["recolor"] = True
        else:
            raise ValueError(f"unknown view option {tok!r} (fog<r>, glimpse, recolor)")
    if out.get("glimpse") and "radius" not in out:
        raise ValueError("glimpse needs fog<r>")
    return out


def recolor_map(family: str, seed: int, level_idx: int) -> list[int]:
    """Palette index -> index; a non-identity permutation of OBJECT_POOL, identity elsewhere."""
    pool = list(OBJECT_POOL)
    perm = pool[:]
    rng = rng_for("view-recolor", family, seed, level_idx)
    while perm == pool:
        rng.shuffle(perm)
    m = list(range(16))
    for a, b in zip(pool, perm):
        m[a] = b
    return m


def apply(levels: list[Level], family: str, seed: int, view: str) -> None:
    opts = parse(view)
    for i, lv in enumerate(levels):
        d: dict[str, Any] = {}
        if "radius" in opts:
            d["radius"] = opts["radius"]
            d["fog"] = FOG
            if opts.get("glimpse"):
                d["glimpse"] = True
        if opts.get("recolor") and i > 0:
            d["recolor"] = recolor_map(family, seed, i)
        lv.data["view"] = d
