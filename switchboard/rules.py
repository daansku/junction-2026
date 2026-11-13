"""Rule grammar for the Switchboard.

A board has N switches (named A, B, C, ...) and M lamps (numbered 0..M-1).
Pressing a switch either FIRES (XOR-toggles a fixed set of 1-3 lamps) or does
nothing. Whether it fires depends on the switch's hidden rule kind:

    toggle   always fires
    counter  fires on every k-th press of this switch since the last reset (k in {2,3})
    gated    fires only if a particular lamp is currently ON (or OFF, by polarity)
    locked   fires only once a particular other switch has been pressed since the last reset

Every piece of hidden state (press counts, which switches were pressed) is a
deterministic function of the agent's own visible action history since the
last reset. Nothing is random after the board is generated.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from itertools import combinations

KIND_ORDER = {"toggle": 0, "counter": 1, "gated": 2, "locked": 3}
COUNTER_KS = (2, 3)
MASK_SIZES = (1, 2, 3)


def switch_name(i: int) -> str:
    return chr(ord("A") + i)


def popcount(x: int) -> int:
    return bin(x).count("1")


@dataclass(frozen=True)
class Rule:
    kind: str
    mask: int
    k: int = 0          # counter period
    gate: int = -1      # lamp index (gated)
    polarity: int = 1   # gated fires when lamp == polarity
    unlock: int = -1    # switch index (locked)

    def fires(self, own_count: int, lamps: int, pressed: int) -> bool:
        """own_count: presses of this switch since reset, BEFORE this press.
        lamps: lamp bitmask before this press.
        pressed: bitmask of switches pressed since reset, before this press."""
        if self.kind == "toggle":
            return True
        if self.kind == "counter":
            return (own_count + 1) % self.k == 0
        if self.kind == "gated":
            return ((lamps >> self.gate) & 1) == self.polarity
        if self.kind == "locked":
            return bool((pressed >> self.unlock) & 1)
        raise ValueError(self.kind)

    def lamps_list(self) -> list[int]:
        return [i for i in range(32) if (self.mask >> i) & 1]

    def describe(self) -> str:
        tgt = f"toggles lamps {self.lamps_list()}"
        if self.kind == "toggle":
            return f"always {tgt}"
        if self.kind == "counter":
            return f"every {self.k}th press {tgt}"
        if self.kind == "gated":
            return f"if lamp {self.gate} is {'ON' if self.polarity else 'OFF'}, {tgt}"
        return f"once {switch_name(self.unlock)} has been pressed, {tgt}"

    def complexity(self) -> tuple:
        return (KIND_ORDER[self.kind], popcount(self.mask), self.k, self.gate, self.polarity, self.unlock, self.mask)


@dataclass(frozen=True)
class Tier:
    name: str
    n_switches: int
    n_lamps: int
    kinds: tuple[str, ...]
    required: tuple[str, ...]
    n_targets: int
    min_dist: int
    budget_factor: float
    budget_extra_per_switch: int


TIERS: dict[str, Tier] = {
    # control tier: pure XOR toggles (linear algebra) - should be "easy" for everyone
    "easy": Tier("easy", 5, 5, ("toggle",), (), 3, 3, 2.0, 2),
    "medium": Tier("medium", 7, 9, ("toggle", "counter", "gated"), ("counter", "gated"), 3, 5, 2.0, 3),
    "hard": Tier("hard", 8, 10, ("toggle", "counter", "gated", "locked"), ("counter", "gated", "locked"), 3, 6, 2.0, 4),
}


@dataclass(frozen=True)
class Wiring:
    rules: tuple[Rule, ...]
    n_lamps: int
    init_lamps: int

    @property
    def n_switches(self) -> int:
        return len(self.rules)

    def relevant_pressed(self) -> int:
        m = 0
        for r in self.rules:
            if r.kind == "locked":
                m |= 1 << r.unlock
        return m


def _random_mask(rng: random.Random, n_lamps: int) -> int:
    size = rng.choice(MASK_SIZES)
    m = 0
    for i in rng.sample(range(n_lamps), size):
        m |= 1 << i
    return m


def all_masks(n_lamps: int) -> list[int]:
    out = []
    for size in MASK_SIZES:
        for combo in combinations(range(n_lamps), size):
            m = 0
            for i in combo:
                m |= 1 << i
            out.append(m)
    return out


def sample_wiring(rng: random.Random, tier: Tier) -> Wiring:
    n, m = tier.n_switches, tier.n_lamps
    kinds = list(tier.required) + [rng.choice(tier.kinds) for _ in range(n - len(tier.required))]
    rng.shuffle(kinds)
    non_locked = [i for i, k in enumerate(kinds) if k != "locked"]
    rules = []
    for i, kind in enumerate(kinds):
        mask = _random_mask(rng, m)
        if kind == "toggle":
            rules.append(Rule("toggle", mask))
        elif kind == "counter":
            rules.append(Rule("counter", mask, k=rng.choice(COUNTER_KS)))
        elif kind == "gated":
            rules.append(Rule("gated", mask, gate=rng.randrange(m), polarity=rng.randrange(2)))
        else:
            rules.append(Rule("locked", mask, unlock=rng.choice([j for j in non_locked if j != i])))
    init = rng.randrange(1 << m)
    return Wiring(tuple(rules), m, init)


def enumerate_candidates(tier: Tier, switch: int) -> list[Rule]:
    """Every rule a switch could have under the disclosed grammar (used by the rules-blind reference)."""
    n, m = tier.n_switches, tier.n_lamps
    out = []
    for mask in all_masks(m):
        if "toggle" in tier.kinds:
            out.append(Rule("toggle", mask))
        if "counter" in tier.kinds:
            out += [Rule("counter", mask, k=k) for k in COUNTER_KS]
        if "gated" in tier.kinds:
            out += [Rule("gated", mask, gate=g, polarity=p) for g in range(m) for p in (0, 1)]
        if "locked" in tier.kinds:
            out += [Rule("locked", mask, unlock=u) for u in range(n) if u != switch]
    return out


def grammar_text(tier: Tier) -> str:
    """The rulebook given to every agent. Same information the rules-blind reference solver uses."""
    lines = [
        f"The board has {tier.n_switches} switches ({', '.join(switch_name(i) for i in range(tier.n_switches))}) "
        f"and {tier.n_lamps} lamps (0..{tier.n_lamps - 1}). Lamp states are shown as a string, lamp 0 first, 1=ON.",
        "Each switch has ONE fixed hidden rule. When a switch 'fires' it flips (ON<->OFF) a fixed set of 1 to 3 lamps.",
        "Possible rule kinds:",
    ]
    desc = {
        "toggle": "  - toggle: fires on every press.",
        "counter": "  - counter: fires only on every k-th press of that switch since the last reset (k is 2 or 3).",
        "gated": "  - gated: fires only if one specific lamp is currently ON (or, for some switches, currently OFF).",
        "locked": "  - locked: does nothing until one specific OTHER switch has been pressed at least once since the last reset; "
                  "after that it fires on every press. The unlocking switch is never itself a locked switch.",
    }
    lines += [desc[k] for k in tier.kinds]
    lines += [
        "The rules never change during an episode. Nothing is random: the same presses from the same state always give the same result.",
        "reset() restores the starting lamps and clears all press counts/unlocks, but costs extra budget.",
    ]
    return "\n".join(lines)
