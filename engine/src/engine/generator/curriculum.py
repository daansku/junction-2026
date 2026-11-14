"""Curriculum: which rules each level uses (PLAN.md §5).

Level 1 is movement + goal only. Each later level introduces exactly one new rule, alone or
with up to two already-seen rules. When the rule pool runs out, levels recombine seen rules
with no new rule. No two levels in a game share a rule set. Order is decided by the seed.
"""
from __future__ import annotations

from itertools import combinations

from .. import components as comps
from ..core.rng import rng_for

MAX_TIER = 2  # raise as tiers land


def max_tier_for(difficulty: int) -> int:
    return 1 if difficulty <= 1 else MAX_TIER


def rule_pool(max_tier: int = MAX_TIER) -> list[str]:
    return sorted(n for n, t in comps.tiers().items() if t <= max_tier)


def _old_count(rng, difficulty: int, n_seen: int, level_idx: int) -> int:
    if n_seen == 0:
        return 0
    if level_idx <= 2:  # early levels teach alone
        return 0 if rng.random() < 0.7 else 1
    if difficulty >= 2 and rng.random() < 0.6:
        return min(n_seen, rng.randint(1, 2))
    cap = min(n_seen, 1 if difficulty <= 1 else 2)
    return rng.randint(0, cap)


def plan(seed: int, family: str, difficulty: int, n_levels: int,
         rules: list[str] | None = None) -> list[tuple[tuple[str, ...], str | None, list[tuple[str, ...]]]]:
    """Per level: (rule set, new rule or None, fallback rule sets to try if generation fails)."""
    rng = rng_for(family, seed, difficulty, "curriculum")
    if rules is not None:
        order = list(rules)
    else:
        order = rule_pool(max_tier_for(difficulty))
        rng.shuffle(order)
    out: list = [((), None, [])]
    used: set[frozenset] = {frozenset()}
    seen: list[str] = []
    exam = n_levels >= 5  # last level recombines seen rules, no new rule
    for i in range(1, n_levels):
        if order and not (exam and i == n_levels - 1):
            new = order.pop(0)
            k = _old_count(rng, difficulty, len(seen), i)
            olds = rng.sample(seen, k)
            primary = tuple(sorted({new, *olds}))
            fallbacks = [tuple(sorted({new, o})) for o in seen if o not in olds] + [(new,)]
            fallbacks = [f for f in dict.fromkeys(fallbacks) if f != primary and frozenset(f) not in used]
            if frozenset(primary) in used:
                primary, fallbacks = (fallbacks[0], fallbacks[1:]) if fallbacks else ((new,), [])
            seen.append(new)
            out.append((primary, new, fallbacks))
            used.add(frozenset(primary))
        else:  # recombination level
            combos = [tuple(sorted(c)) for r in (2, 3) for c in combinations(sorted(seen), r)
                      if frozenset(c) not in used]
            if not combos:
                combos = [(s,) for s in sorted(seen) if frozenset((s,)) not in used]
            if not combos:
                break
            rng.shuffle(combos)
            singles = [(s,) for s in sorted(seen)]
            out.append((combos[0], None, combos[1:12] + singles))
            used.add(frozenset(combos[0]))
    return out
