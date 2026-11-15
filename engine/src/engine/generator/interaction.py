"""Forced interaction: opt-in stricter level checks and curriculum for the `gridforce` family.

Only games whose family ends in "force" (e.g. `gridforce`) use anything here; `gridworld` games
(dev, train-v1, eval-v1, eval-v2, probe-v1) are untouched and regenerate byte-identically.

Rule kinds:
  use       the player must use it. Forced = no plan that never triggers it wins in fewer than
            K x optimal moves (or avoiding it makes the level unsolvable). "Triggers" = the rule's
            truth events, or entering one of its cells (one_way, phase_walls).
  avoid     the skill is staying away (hazards, beacon decoy, cracked floor, enemies). Forced = the
            rule-ignorant optimal plan is strictly shorter than the real optimum, so every ignorant
            shortest plan fails on the real level and the player must notice the rule and detour.
  builtin   cannot win without it (collect_all, checkpoints, twin): always counts as forced.
  constraint  no_reverse: not an object you touch; skipped.

Human decisions ("Forced-interaction generator"): the newest rule is a hard
requirement; older rules are soft (required on early attempts, relaxed on later ones); levels
combine more seen mechanics, kept tidy (MAX_RULES, at most one view-scrambling rule per level).

Changing any constant below changes every `gridforce` game: bump FORCE_VERSION and say so.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import replace
from itertools import combinations

from .. import components as comps
from ..core.actions import MOVE_ACTIONS, Action
from ..core.level import Level
from ..core.rng import rng_for
from ..core.step import LEVEL_WON, LOST, initial_state, step_level, uses_interact

FORCE_VERSION = 1
K = 2.0                 # v1: an avoider needs >= K x optimal moves, so scores <= 1/K on the level
AVOID_CAP = 80_000      # avoid-solver state cap; hitting it counts as "not shown forced" (reject)
SOFT_ALL_UNTIL = 20     # attempts [0, 20): every older rule on the level must be forced
SOFT_HALF_UNTIL = 40    # attempts [20, 40): at least half; later attempts: only the new rule
MAX_RULES = {1: 2, 2: 3, 3: 3, 4: 3}   # active rules per level (tidy levels)
SCRAMBLERS = frozenset({"remap", "rotation", "gravity", "twin"})  # change what a key press does

USE_EVENTS: dict[str, tuple[str, ...]] = {
    "keys_doors": ("picked_key", "opened_door"), "plates_gates": ("pressed_plate",),
    "teleporters": ("teleport",), "push_blocks": ("pushed",), "ice": ("slid",),
    "rotation": ("rotated",), "remap": ("controls_changed",), "stamina": ("refilled",),
    "conveyors": ("drifted",), "gravity": ("gravity_on",), "pits": ("pit_filled",),
}
USE_CELLS: dict[str, str] = {"one_way": "tiles", "phase_walls": "cells"}
AVOID = frozenset({"hazards", "beacon_goal", "cracked_floor", "enemies"})
BUILTIN = frozenset({"collect_all", "checkpoints", "twin"})


def forcing(family: str) -> bool:
    return family.endswith("force")


def kind(rule: str) -> str:
    if rule in USE_EVENTS or rule in USE_CELLS:
        return "use"
    if rule in AVOID:
        return "avoid"
    if rule in BUILTIN:
        return "builtin"
    return "constraint"


def triggers(level: Level, rule: str, pos: tuple[int, int], events: list[str]) -> bool:
    """Did this transition use `rule`? (events, or entering one of its cells)"""
    if rule in USE_EVENTS:
        pre = USE_EVENTS[rule]
        return any(e.split(":", 1)[0] in pre for e in events)
    if rule in USE_CELLS:
        cells = level.__dict__.setdefault("_a7_cells", {})
        if rule not in cells:
            cells[rule] = frozenset(tuple(t[:2]) for t in level.data.get(rule, {}).get(USE_CELLS[rule], []))
        return pos in cells[rule]
    return False


def avoid_optimal(level: Level, rule: str, limit: int | None = None,
                  cap: int = AVOID_CAP) -> int | float | None:
    """Shortest win that never triggers `rule` (budget ignored). Returns its length; math.inf if
    there is none (or none of length <= limit); None if the state cap was hit first."""
    lv = replace(level, move_budget=0)
    acts = list(MOVE_ACTIONS) + ([Action.ACTION5] if uses_interact(lv) else [])
    s0 = initial_state(lv)
    depth = {s0.key(): 0}
    q = deque([s0])
    while q:
        s = q.popleft()
        d = depth[s.key()]
        if limit is not None and d + 1 > limit:
            return math.inf
        for a in acts:
            ns, ev, out = step_level(lv, s, a)
            if out == LOST or triggers(lv, rule, ns.pos, ev):
                continue
            if out == LEVEL_WON:
                return d + 1
            k = ns.key()
            if k not in depth:
                depth[k] = d + 1
                if len(depth) > cap:
                    return None
                q.append(ns)
    return math.inf


def ignorant_optimal(level: Level, rule: str) -> int | float | None:
    """Optimal length for a player who does not know `rule` exists (rule removed)."""
    from ..solver import solve
    p = solve(replace(level, rules=tuple(r for r in level.rules if r != rule)))
    return math.inf if p is None else len(p)


def avoid_limit(optimal: int) -> int:
    """Longest avoiding win that still counts as 'too close': < K x optimal."""
    return math.ceil(K * optimal) - 1


def rule_forced(level: Level, rule: str, optimal: int | None = None) -> bool:
    optimal = optimal or level.optimal_moves
    k = kind(rule)
    if k == "builtin":
        return True
    if k == "constraint":
        return False
    if k == "avoid":
        ig = ignorant_optimal(level, rule)
        return ig is math.inf or ig < optimal
    a = avoid_optimal(level, rule, limit=avoid_limit(optimal))
    return a is not None and a >= K * optimal


def scored(rule: str) -> bool:
    """Rules the forcing check is about (builtin ones are forced anyway, constraints n/a)."""
    return kind(rule) in ("use", "avoid")


def level_ok(level: Level, attempt: int) -> bool:
    """The flag-gated generator hook, called after every existing check in try_level.
    New rule: hard. Older rules: soft, relaxed with the attempt index. A level without a new
    rule (recombination / exam) needs at least one forced rule."""
    opt = level.optimal_moves
    new = level.new_rule
    if new is not None and scored(new) and not rule_forced(level, new, opt):
        return False
    olds = [r for r in level.rules if r != new and scored(r)]
    if not olds:
        return True
    if attempt < SOFT_ALL_UNTIL:
        need = len(olds)
    elif attempt < SOFT_HALF_UNTIL:
        need = (len(olds) + 1) // 2
    else:
        need = 0
    if new is None or not scored(new):
        need = max(need, 1)
    if need == 0:
        return True
    have, left = 0, len(olds)
    for r in olds:
        if rule_forced(level, r, opt):
            have += 1
        left -= 1
        if have >= need:
            return True
        if have + left < need:
            return False
    return have >= need


def level_report(level: Level) -> dict[str, dict]:
    """Per rule: kind, avoid/ignorant optimal, avoider score bound, forced? (audit tool)."""
    opt = level.optimal_moves
    out = {}
    for r in level.rules:
        k = kind(r)
        row: dict = {"kind": k, "new": r == level.new_rule}
        if k == "use":
            a = avoid_optimal(level, r)
            row["avoid_optimal"] = None if a is None else (None if a is math.inf else a)
            row["avoider_score"] = None if a is None else (0.0 if a is math.inf else round(opt / a, 3))
            row["forced"] = a is not None and a >= K * opt
        elif k == "avoid":
            ig = ignorant_optimal(level, r)
            row["ignorant_optimal"] = None if ig is math.inf else ig
            row["forced"] = ig is math.inf or ig < opt
        else:
            row["forced"] = k == "builtin"
        out[r] = row
    return out


# ---- curriculum variant (combines more seen rules, kept tidy) -----------------------------

def _tidy(rules) -> bool:
    return len(SCRAMBLERS.intersection(rules)) <= 1


def _pick_olds(rng, seen: list[str], uses: dict[str, int], new: str, k: int) -> list[str]:
    """k seen rules, least reused first (ties broken by the seed), at most one scrambler."""
    order = sorted(seen, key=lambda r: (uses[r], rng.random()))
    out: list[str] = []
    for r in order:
        if len(out) >= k:
            break
        if _tidy([new, *out, r]):
            out.append(r)
    return out


def _old_count(rng, difficulty: int, n_seen: int, level_idx: int) -> int:
    cap = min(n_seen, MAX_RULES.get(difficulty, 3) - 1)
    if cap <= 0:
        return 0
    if level_idx <= 2:  # second taught rule: alone or with the first, about evenly
        return 1 if rng.random() < 0.6 else 0
    if cap == 1:
        return 1
    return 2 if rng.random() < 0.7 else 1


def plan(seed: int, family: str, difficulty: int, n_levels: int,
         rules: list[str] | None = None) -> list[tuple[tuple[str, ...], str | None, list[tuple[str, ...]]]]:
    """Same contract as curriculum.plan: per level (rule set, new rule or None, fallbacks).
    Level 1 plain; one new rule per level; last level of >= 5 is an exam on seen rules."""
    from . import curriculum
    rng = rng_for(family, seed, difficulty, "curriculum", "force", FORCE_VERSION)
    if rules is not None:
        order = list(rules)
    else:
        order = curriculum.rule_pool(curriculum.max_tier_for(difficulty))
        if difficulty >= curriculum.HARD_DIFFICULTY:
            order = curriculum._hard_order(rng, order)
        else:
            rng.shuffle(order)
    max_rules = MAX_RULES.get(difficulty, 3)
    out: list = [((), None, [])]
    used: set[frozenset] = {frozenset()}
    seen: list[str] = []
    uses: dict[str, int] = {}
    exam = n_levels >= 5
    for i in range(1, n_levels):
        ready = [r for r in order if not comps.REGISTRY[r].requires
                 or any(q in seen for q in comps.REGISTRY[r].requires)]
        if ready and not (exam and i == n_levels - 1):
            new = ready[0]
            order.remove(new)
            olds = _pick_olds(rng, seen, uses, new, _old_count(rng, difficulty, len(seen), i))
            req = comps.REGISTRY[new].requires
            if req and not any(q in olds for q in req):
                partner = rng.choice(sorted(q for q in req if q in seen))
                olds = olds[: max_rules - 2] + [partner]
                if not _tidy([new, *olds]):
                    olds = [o for o in olds if o == partner or o not in SCRAMBLERS]
            primary = tuple(sorted({new, *olds}))
            fallbacks = [tuple(sorted({new, *c})) for c in combinations(sorted(seen), 2)
                         if len(olds) >= 2] + [tuple(sorted({new, o})) for o in sorted(seen, key=lambda r: uses[r])]
            fallbacks.append((new,))
            if req:
                fallbacks = [f for f in fallbacks if any(q in f for q in req)] + \
                            [tuple(sorted({new, q})) for q in req if q in seen]
            fallbacks = [f for f in dict.fromkeys(fallbacks)
                         if f != primary and frozenset(f) not in used and _tidy(f) and len(f) <= max_rules]
            if frozenset(primary) in used:
                primary, fallbacks = (fallbacks[0], fallbacks[1:]) if fallbacks else ((new,), [])
            seen.append(new)
            uses[new] = 0
            for r in primary:
                if r != new:
                    uses[r] += 1
            out.append((primary, new, fallbacks[:12]))
            used.add(frozenset(primary))
        else:  # recombination / exam: as many seen rules as allowed, least reused first
            size = min(max_rules, len(seen))
            combos = [tuple(sorted(c)) for n in range(size, 1, -1) for c in combinations(sorted(seen), n)
                      if frozenset(c) not in used and _tidy(c)]
            if not combos:
                combos = [(s,) for s in sorted(seen) if frozenset((s,)) not in used]
            if not combos:
                break
            rng.shuffle(combos)
            combos.sort(key=lambda c: (-len(c), sum(uses[r] for r in c)))
            singles = [(s,) for s in sorted(seen)]
            out.append((combos[0], None, combos[1:12] + singles))
            for r in combos[0]:
                uses[r] += 1
            used.add(frozenset(combos[0]))
    return out
