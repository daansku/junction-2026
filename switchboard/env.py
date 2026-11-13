"""Switchboard simulator, planner and episode/scoring logic."""
from __future__ import annotations

import heapq
import math
import random
from dataclasses import dataclass, field

from .rules import TIERS, Tier, Wiring, grammar_text, sample_wiring, switch_name

RESET = -1
RESET_COST = 2


# ---------------------------------------------------------------- simulation
@dataclass(frozen=True)
class State:
    lamps: int
    counts: tuple[int, ...]   # presses since reset, reduced mod k for counters (0 for others)
    pressed: int              # switches pressed since reset, restricted to bits that matter


def initial_state(w: Wiring) -> State:
    return State(w.init_lamps, (0,) * w.n_switches, 0)


def step(w: Wiring, s: State, a: int) -> tuple[State, bool]:
    """Apply press of switch `a`. Returns (next_state, fired)."""
    if a == RESET:
        return initial_state(w), False
    r = w.rules[a]
    fired = r.fires(s.counts[a], s.lamps, s.pressed)
    lamps = s.lamps ^ r.mask if fired else s.lamps
    counts = s.counts
    if r.kind == "counter":
        counts = counts[:a] + ((counts[a] + 1) % r.k,) + counts[a + 1:]
    pressed = s.pressed | ((1 << a) & w.relevant_pressed())
    return State(lamps, counts, pressed), fired


def shortest_path(w: Wiring, start: State, target_lamps: int, reset_cost: int = RESET_COST,
                  max_cost: int | None = None) -> list[int] | None:
    """Cheapest action sequence (presses cost 1, reset costs reset_cost) to reach target lamps."""
    if start.lamps == target_lamps:
        return []
    dist = {start: 0}
    prev: dict[State, tuple[State, int]] = {}
    pq = [(0, 0, start)]
    tie = 0
    actions = list(range(w.n_switches)) + [RESET]
    while pq:
        d, _, s = heapq.heappop(pq)
        if d > dist[s]:
            continue
        if s.lamps == target_lamps:
            path = []
            while s != start:
                s, a = prev[s]
                path.append(a)
            return path[::-1]
        if max_cost is not None and d >= max_cost:
            continue
        for a in actions:
            ns, _ = step(w, s, a)
            nd = d + (reset_cost if a == RESET else 1)
            if nd < dist.get(ns, math.inf):
                dist[ns] = nd
                prev[ns] = (s, a)
                tie += 1
                heapq.heappush(pq, (nd, tie, ns))
    return None


def reachable_distances(w: Wiring) -> dict[int, int]:
    """Min presses from the initial state to every reachable lamp pattern (no resets needed from init)."""
    start = initial_state(w)
    best: dict[int, int] = {start.lamps: 0}
    seen = {start}
    frontier = [start]
    d = 0
    while frontier:
        d += 1
        nxt = []
        for s in frontier:
            for a in range(w.n_switches):
                ns, _ = step(w, s, a)
                if ns not in seen:
                    seen.add(ns)
                    nxt.append(ns)
                    best.setdefault(ns.lamps, d)
        frontier = nxt
    return best


def plan_cost(path: list[int], reset_cost: int = RESET_COST) -> int:
    return sum(reset_cost if a == RESET else 1 for a in path)


# ---------------------------------------------------------------- episodes
@dataclass(frozen=True)
class Episode:
    seed: int
    tier: Tier
    wiring: Wiring
    targets: tuple[int, ...]
    oracle_cost: int
    budget: int


def make_episode(seed: int, tier_name: str) -> Episode:
    tier = TIERS[tier_name]
    rng = random.Random(f"switchboard:{tier_name}:{seed}")
    for _ in range(1000):
        w = sample_wiring(rng, tier)
        dists = reachable_distances(w)
        pool = sorted(l for l, d in dists.items() if d >= tier.min_dist and l != w.init_lamps)
        if len(pool) < tier.n_targets:
            continue
        targets = tuple(rng.sample(pool, tier.n_targets))
        # oracle cost: plan target by target from the true state
        s = initial_state(w)
        total = 0
        for t in targets:
            p = shortest_path(w, s, t)
            assert p is not None
            for a in p:
                s, _ = step(w, s, a)
            total += plan_cost(p)
        budget = math.ceil(total * tier.budget_factor) + tier.budget_extra_per_switch * tier.n_switches
        return Episode(seed, tier, w, targets, total, budget)
    raise RuntimeError("could not generate episode")


def lamps_str(lamps: int, n: int) -> str:
    return "".join("1" if (lamps >> i) & 1 else "0" for i in range(n))


def parse_lamps(s: str) -> int:
    return sum(1 << i for i, c in enumerate(s) if c == "1")


class SwitchboardEnv:
    """One episode. All score-relevant state lives here; agents only see observations."""

    def __init__(self, seed: int, tier: str = "hard"):
        self.ep = make_episode(seed, tier)
        self.tier = self.ep.tier
        self.w = self.ep.wiring
        self.state = initial_state(self.w)
        self.used = 0
        self.targets_done = 0
        self.history: list[dict] = []
        self.finished_by_agent = False

    # ---- derived
    @property
    def n(self) -> int:
        return self.w.n_lamps

    @property
    def done(self) -> bool:
        return self.targets_done >= len(self.ep.targets) or self.used >= self.ep.budget or self.finished_by_agent

    @property
    def current_target(self) -> int | None:
        if self.targets_done >= len(self.ep.targets):
            return None
        return self.ep.targets[self.targets_done]

    def observe(self) -> dict:
        t = self.current_target
        return {
            "lamps": lamps_str(self.state.lamps, self.n),
            "target": None if t is None else lamps_str(t, self.n),
            "targets_completed": self.targets_done,
            "targets_total": len(self.ep.targets),
            "budget_used": self.used,
            "budget_total": self.ep.budget,
            "budget_left": self.ep.budget - self.used,
            "reset_cost": RESET_COST,
            "switches": [switch_name(i) for i in range(self.w.n_switches)],
            "done": self.done,
            "score": self.score(),
        }

    def _check_target(self) -> bool:
        t = self.current_target
        if t is not None and self.state.lamps == t:
            self.targets_done += 1
            return True
        return False

    def _act(self, a: int) -> dict:
        if self.done:
            return {"error": "episode is over", **self.observe()}
        cost = RESET_COST if a == RESET else 1
        if self.used + cost > self.ep.budget:
            return {"error": f"not enough budget (need {cost}, have {self.ep.budget - self.used})", **self.observe()}
        before = self.state.lamps
        self.state, _ = step(self.w, self.state, a)
        self.used += cost
        hit = self._check_target()
        self.history.append({
            "action": "reset" if a == RESET else switch_name(a),
            "lamps_before": lamps_str(before, self.n),
            "lamps_after": lamps_str(self.state.lamps, self.n),
            "reached_target": hit,
        })
        return {"reached_target": hit, **self.observe()}

    def press(self, switch: str) -> dict:
        if not isinstance(switch, str) or len(switch.strip()) != 1:
            return {"error": f"unknown switch {switch!r}", **self.observe()}
        i = ord(switch.strip().upper()) - ord("A")
        if not 0 <= i < self.w.n_switches:
            return {"error": f"unknown switch {switch!r}", **self.observe()}
        return self._act(i)

    def reset(self) -> dict:
        return self._act(RESET)

    def finish(self) -> dict:
        """Agent declares it is done. Score is unaffected except that no further actions are possible."""
        self.finished_by_agent = True
        return self.observe()

    def score(self) -> float:
        """0.8 * fraction of targets reached + 0.2 * efficiency bonus (only if ALL targets reached).

        Efficiency = oracle_cost / budget_used, capped at 1. No credit for actions, claims,
        or exploration; only lamp patterns actually reached in the simulator count."""
        k = len(self.ep.targets)
        s = 0.8 * self.targets_done / k
        if self.targets_done == k and self.used > 0:
            s += 0.2 * min(1.0, self.ep.oracle_cost / self.used)
        return round(s, 4)

    def summary(self) -> dict:
        return {
            "seed": self.ep.seed,
            "tier": self.tier.name,
            "score": self.score(),
            "targets_completed": self.targets_done,
            "targets_total": len(self.ep.targets),
            "budget_used": self.used,
            "budget_total": self.ep.budget,
            "oracle_cost": self.ep.oracle_cost,
            "n_actions": len(self.history),
        }

    def instructions(self) -> str:
        return (
            "You control a switchboard with hidden wiring. Your goal: make the lamps show each target pattern in turn "
            f"({len(self.ep.targets)} targets). When the lamps exactly match the current target, it is completed automatically "
            "and the next target is revealed (the lamps stay as they are).\n"
            f"You have a budget of {self.ep.budget} units: each press costs 1, reset costs {RESET_COST}. "
            "The episode ends when all targets are done or the budget is spent.\n"
            "Scoring: 80% for the fraction of targets reached, plus up to 20% for efficiency if you reach ALL targets.\n\n"
            + grammar_text(self.tier)
        )


class PublicView:
    """What a rules-blind agent may touch: actions and observations only."""

    def __init__(self, env: SwitchboardEnv):
        self._env = env
        self.tier = env.tier
        self.instructions = env.instructions()

    def observe(self) -> dict:
        return self._env.observe()

    def press(self, switch: str) -> dict:
        return self._env.press(switch)

    def reset(self) -> dict:
        return self._env.reset()

    def finish(self) -> dict:
        return self._env.finish()
