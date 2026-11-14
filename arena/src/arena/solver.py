"""Generic BFS over any Game implementing contracts/engine_api.py (clone, state_hash, step, truth).

Used to finish a level from an arbitrary (e.g. off-optimal) state when building
recover-from-mistake trajectories. A1 owns the real solver; this one only needs the protocol.
"""
from __future__ import annotations

from collections import deque

MOVE_ACTIONS = ("ACTION1", "ACTION2", "ACTION3", "ACTION4", "ACTION5")


def solve_level(game, max_states: int = 200_000, actions=None) -> list[str] | None:
    """Shortest action list from the game's current state that completes the current level
    (level index increases or state becomes WIN). Does not mutate `game`. RESET is allowed as an
    action so a doomed position can still be recovered."""
    start_t = game.truth()
    level0 = start_t["level"]
    acts = list(actions or [a for a in _available(game) if a in MOVE_ACTIONS])
    seen = {game.state_hash()}
    q = deque([(game, [])])
    while q:
        g, path = q.popleft()
        # RESET only as the very first action: later resets never shorten a plan, and engines
        # that count resets in state_hash would otherwise make the search space infinite.
        for a in (acts + ["RESET"] if not path else acts):
            n = g.clone()
            n.step(a)
            t = n.truth()
            if t["state"] == "WIN" or t["level"] > level0:
                return path + [a]
            h = n.state_hash()
            if h in seen:
                continue
            seen.add(h)
            if len(seen) > max_states:
                return None
            q.append((n, path + [a]))
    return None


def _available(game) -> list[str]:
    """The game's full action set. available_actions() can shrink to [RESET] in GAME_OVER, so prefer
    describe()['available_actions'], which lists what the game uses at all."""
    try:
        acts = game.describe().get("available_actions")
        if acts:
            return [getattr(a, "value", a) for a in acts]
    except Exception:
        pass
    try:
        acts = [getattr(a, "value", a) for a in game.available_actions()]
        if any(a in MOVE_ACTIONS for a in acts):
            return acts
    except AttributeError:
        pass
    return ["ACTION1", "ACTION2", "ACTION3", "ACTION4"]
