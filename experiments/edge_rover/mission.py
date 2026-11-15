"""Deterministic, partially observed rover missions for the bootcamp transfer study."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import random

SIZE = 9
DELTAS = {
    "ACTION1": (-1, 0),  # north
    "ACTION2": (1, 0),   # south
    "ACTION3": (0, -1),  # west
    "ACTION4": (0, 1),   # east
}


def _path_length(walls: set[tuple[int, int]], start: tuple[int, int], goal: tuple[int, int]) -> int | None:
    q = deque([(start, 0)])
    seen = {start}
    while q:
        p, d = q.popleft()
        if p == goal:
            return d
        for dr, dc in DELTAS.values():
            n = p[0] + dr, p[1] + dc
            if 0 <= n[0] < SIZE and 0 <= n[1] < SIZE and n not in walls and n not in seen:
                seen.add(n)
                q.append((n, d + 1))
    return None


@dataclass
class RoverMission:
    seed: int
    walls: set[tuple[int, int]]
    goal: tuple[int, int]
    path_len: int
    energy_max: int
    pos: tuple[int, int]
    energy: int
    steps: int = 0
    bumps: int = 0
    found: bool = False
    done: bool = False
    success: bool = False
    known: set[tuple[int, int]] | None = None
    history: list[tuple[str, int]] | None = None

    @classmethod
    def create(cls, seed: int) -> "RoverMission":
        rng = random.Random(seed)
        start = (SIZE // 2, SIZE // 2)
        # Rejection sampling gives every mission a reachable, nontrivial beacon and
        # leaves the center clear so the same opening is safe across all seeds.
        while True:
            walls = {(r, c) for r in range(SIZE) for c in range(SIZE)
                     if (r, c) != start and rng.random() < 0.19}
            options = [(r, c, _path_length(walls, start, (r, c)))
                       for r in range(SIZE) for c in range(SIZE)]
            goals = [(r, c, d) for r, c, d in options if d is not None and 9 <= d <= 15]
            if goals:
                gr, gc, dist = rng.choice(goals)
                break
        energy = 2 * dist + 18
        mission = cls(seed, walls, (gr, gc), dist, energy, start, energy,
                      known=set(), history=[])
        mission.observe()
        return mission

    def observe(self, radius: int = 2) -> str:
        r0, c0 = self.pos
        rows = []
        for r in range(SIZE):
            row = []
            for c in range(SIZE):
                p = (r, c)
                visible = abs(r - r0) + abs(c - c0) <= radius
                if visible:
                    self.known.add(p)
                if p not in self.known:
                    row.append("?")
                elif p == self.pos:
                    row.append("R")
                elif p == self.goal:
                    row.append("G")
                elif p == (SIZE // 2, SIZE // 2):
                    row.append("B")
                elif p in self.walls:
                    row.append("#")
                else:
                    row.append(".")
            rows.append("".join(row))
        return "\n".join(rows)

    def act(self, action: str) -> str:
        if self.done:
            return "mission already ended"
        self.steps += 1
        self.energy -= 1
        dr, dc = DELTAS[action]
        nxt = self.pos[0] + dr, self.pos[1] + dc
        if not (0 <= nxt[0] < SIZE and 0 <= nxt[1] < SIZE) or nxt in self.walls:
            self.bumps += 1
            result = "BUMP: rover stayed in place; energy -1"
            self.history.append((action, 0))
        else:
            self.pos = nxt
            result = f"MOVED to row {nxt[0]}, col {nxt[1]}; energy -1"
            self.history.append((action, 1))
        if self.pos == self.goal:
            self.found = True
            result += "; BEACON FOUND: return to base B"
        if self.found and self.pos == (SIZE // 2, SIZE // 2):
            self.done, self.success = True, True
            result += "; MISSION SUCCESS: rover returned to base"
        elif self.energy <= 0:
            self.done = True
            result += "; BATTERY EMPTY: mission failed"
        return result

    def prompt(self, notes: str, last_result: str) -> str:
        status = "BEACON FOUND; return to B" if self.found else "beacon not yet found"
        recent = self.history[-12:]
        action_history = "\n".join(f"  {action} -> {moved} cells moved" for action, moved in recent)
        return (
            f"Step {self.steps}; energy {self.energy}/{self.energy_max}; {status}.\n"
            "Map coordinates: row 0 is north, col 0 is west. R=rover, B=base, G=beacon, "
            ".=seen clear ground, #=wall, ?=unseen. Sensor reveals Manhattan radius 2.\n"
            "Controls are fixed: ACTION1 north, ACTION2 south, ACTION3 west, ACTION4 east. "
            "Each action costs one energy; bumping a wall still costs energy. Find G, then return to B.\n"
            f"Previous action result: {last_result or '(mission start)'}\n"
            + (f"Recent actions (oldest first), and cells moved (0 means bump):\n{action_history}\n" if recent else "")
            +
            f"Your notes: {notes or '(none)'}\n"
            "Current local map (9 rows x 9 columns):\n"
            f"{self.observe()}\n"
            "Choose one action. Reply only with JSON: "
            '{"notes":"short map/plan memory","action":"ACTION1|ACTION2|ACTION3|ACTION4"}'
        )
