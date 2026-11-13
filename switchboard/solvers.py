"""Reference policies and baselines.

- oracle        knows the true wiring (upper bound; not a fair agent)
- rules_blind   the REFERENCE RUN: sees only observations + the rulebook every agent gets,
                does hypothesis elimination over the disclosed grammar and plans with the
                simplest consistent model. Proves the task is solvable from available info.
- noop          does nothing (judged baseline)
- stop_early    presses every switch once, then quits (judged baseline)
- random        presses uniformly random switches until the budget runs out
"""
from __future__ import annotations

import random
from collections import Counter

from .env import RESET, PublicView, State, SwitchboardEnv, parse_lamps, shortest_path, step
from .rules import Rule, Wiring, enumerate_candidates, switch_name


def oracle(env: SwitchboardEnv, **_) -> None:
    while not env.done:
        path = shortest_path(env.w, env.state, env.current_target, max_cost=env.ep.budget - env.used)
        if not path:
            break
        for a in path:
            r = env.reset() if a == RESET else env.press(switch_name(a))
            if r.get("reached_target") or env.done:
                break


def noop(env: SwitchboardEnv, **_) -> None:
    PublicView(env).finish()


def stop_early(env: SwitchboardEnv, **_) -> None:
    v = PublicView(env)
    for s in v.observe()["switches"]:
        v.press(s)
    v.finish()


def random_policy(env: SwitchboardEnv, rng_seed: int = 0, **_) -> None:
    v = PublicView(env)
    rng = random.Random(rng_seed)
    sw = v.observe()["switches"]
    while not v.observe()["done"]:
        v.press(rng.choice(sw))


def greedy(env: SwitchboardEnv, rng_seed: int = 0, **_) -> None:
    """Shallow heuristic / exploit probe: assume every switch is a plain toggle with the effect it
    showed last time, and greedily press whatever minimises Hamming distance to the target.
    No hypothesis tracking, no planning. Roughly what a careless agent does."""
    v = PublicView(env)
    rng = random.Random(rng_seed)
    obs = v.observe()
    sw = obs["switches"]
    last_effect: dict[str, int] = {}
    while not obs["done"]:
        lamps, target = parse_lamps(obs["lamps"]), parse_lamps(obs["target"])
        untried = [s for s in sw if s not in last_effect]
        if untried:
            s = untried[0]
        else:
            dist = {s: bin((lamps ^ last_effect[s]) ^ target).count("1") for s in sw}
            best = min(dist.values())
            s = rng.choice([k for k, d in dist.items() if d == best]) if best < bin(lamps ^ target).count("1") \
                else rng.choice(sw)
        new = v.press(s)
        if "error" in new:
            break
        last_effect[s] = lamps ^ parse_lamps(new["lamps"])
        obs = new


class RulesBlind:
    def __init__(self, view: PublicView):
        self.v = view
        t = view.tier
        self.n, self.m = t.n_switches, t.n_lamps
        self.cands: list[list[Rule]] = [enumerate_candidates(t, s) for s in range(self.n)]
        obs = view.observe()
        self.init = self.lamps = parse_lamps(obs["lamps"])
        self.counts = [0] * self.n
        self.pressed = 0
        self.ever = 0
        self.obs = obs

    # ---- acting while tracking history-derived hidden state
    def act(self, a: int) -> dict:
        if a == RESET:
            obs = self.v.reset()
            if "error" not in obs:
                self.counts = [0] * self.n
                self.pressed = 0
                self.lamps = parse_lamps(obs["lamps"])
            self.obs = obs
            return obs
        before, c, p = self.lamps, self.counts[a], self.pressed
        obs = self.v.press(switch_name(a))
        self.obs = obs
        if "error" in obs:
            return obs
        after = parse_lamps(obs["lamps"])
        self.cands[a] = [r for r in self.cands[a] if (before ^ (r.mask if r.fires(c, before, p) else 0)) == after]
        if not self.cands[a]:
            raise RuntimeError(f"no consistent rule left for switch {switch_name(a)}")
        self.counts[a] += 1
        self.pressed |= 1 << a
        self.ever |= 1 << a
        self.lamps = after
        return obs

    # ---- model
    def hypothesis(self) -> Wiring:
        return Wiring(tuple(min(c, key=Rule.complexity) for c in self.cands), self.m, self.init)

    def hyp_state(self, w: Wiring) -> State:
        counts = tuple(self.counts[i] % r.k if r.kind == "counter" else 0 for i, r in enumerate(w.rules))
        return State(self.lamps, counts, self.pressed & w.relevant_pressed())

    def informativeness(self, a: int) -> int:
        outcomes = Counter(
            self.lamps ^ (r.mask if r.fires(self.counts[a], self.lamps, self.pressed) else 0) for r in self.cands[a]
        )
        return len(outcomes)

    def choose(self) -> int:
        for s in range(self.n):  # touch every switch once first
            if not (self.ever >> s) & 1:
                return s
        target = parse_lamps(self.obs["target"])
        w = self.hypothesis()
        path = shortest_path(w, self.hyp_state(w), target, max_cost=self.obs["budget_left"])
        if path:
            return path[0]
        # model says unreachable within budget -> the model must be wrong; probe the most ambiguous switch
        best = max(range(self.n), key=self.informativeness)
        if self.informativeness(best) > 1:
            return best
        return RESET if self.obs["budget_left"] >= 2 else 0

    def run(self) -> None:
        while not self.obs["done"]:
            obs = self.act(self.choose())
            if "error" in obs:
                break


def rules_blind(env: SwitchboardEnv, **_) -> None:
    RulesBlind(PublicView(env)).run()


POLICIES = {
    "oracle": oracle,
    "rules_blind": rules_blind,
    "noop": noop,
    "stop_early": stop_early,
    "random": random_policy,
    "greedy": greedy,
}
