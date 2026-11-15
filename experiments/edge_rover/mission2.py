"""Rover mission v2: the edge transfer target for the game bootcamp.

v1 (mission.py) put every model at 0/30: a 1.5B model pressed one key into a wall for the whole battery, so a
training effect could not show. v2 keeps the mission (partially observed 9x9 map, walls, hidden beacon, return to
base, battery) and adds the skill our games train:

  controls="hidden"  the drive mapping is scrambled per mission (a motor-controller fault after landing). ACTION1-4
                     each move one fixed direction, but nobody says which. The rover has to work it out from its
                     own position changes, then explore. This is the same "discover the rules by acting" skill.
  controls="fixed"   v1's spelled-out mapping (navigation only), kept as the second condition.

Observation (both): cumulative map within Manhattan radius 2, explicit position (odometry), energy, the last 12
actions with the position before/after (or BUMP), and the planner's own notes. Deterministic from the seed.
Difficulty knobs (goal distance, slack energy) are set once on dev seeds and frozen before the test seeds run.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import random

SIZE = 9
BASE = (SIZE // 2, SIZE // 2)
ACTIONS = ("ACTION1", "ACTION2", "ACTION3", "ACTION4")
DIRS = {"north": (-1, 0), "south": (1, 0), "west": (0, -1), "east": (0, 1)}
FIXED = {"ACTION1": "north", "ACTION2": "south", "ACTION3": "west", "ACTION4": "east"}
WALL_P = 0.19
GOAL_MIN, GOAL_MAX = 5, 10      # shortest one-way path from base to beacon (frozen after dev calibration)
SLACK = 30                      # energy = 2 * one-way + SLACK


def bfs(walls, start, goal=None, passable=None):
    """Distances from start (optionally only through `passable` cells); returns dict or distance to goal."""
    q, dist = deque([start]), {start: 0}
    while q:
        p = q.popleft()
        if p == goal:
            return dist[p]
        for dr, dc in DIRS.values():
            n = p[0] + dr, p[1] + dc
            if (0 <= n[0] < SIZE and 0 <= n[1] < SIZE and n not in walls and n not in dist
                    and (passable is None or n in passable)):
                dist[n] = dist[p] + 1
                q.append(n)
    return None if goal is not None else dist


@dataclass
class Rover:
    seed: int
    controls: str
    walls: set
    goal: tuple
    path_len: int
    energy_max: int
    mapping: dict
    pos: tuple = BASE
    energy: int = 0
    steps: int = 0
    bumps: int = 0
    found: bool = False
    done: bool = False
    success: bool = False
    known: set = field(default_factory=set)
    history: list = field(default_factory=list)

    @classmethod
    def create(cls, seed: int, controls: str = "hidden") -> "Rover":
        rng = random.Random(seed)
        while True:
            walls = {(r, c) for r in range(SIZE) for c in range(SIZE) if (r, c) != BASE and rng.random() < WALL_P}
            # the base's four neighbours stay clear so every control can be tried from the start
            walls -= {(BASE[0] + dr, BASE[1] + dc) for dr, dc in DIRS.values()}
            d = bfs(walls, BASE)
            goals = [(p, k) for p, k in d.items() if GOAL_MIN <= k <= GOAL_MAX]
            if goals:
                goal, k = rng.choice(sorted(goals))
                break
        dirs = list(DIRS)
        if controls == "hidden":
            rng.shuffle(dirs)
            mapping = dict(zip(ACTIONS, dirs))
        else:
            mapping = dict(FIXED)
        m = cls(seed, controls, walls, goal, k, 2 * k + SLACK, mapping)
        m.energy = m.energy_max
        m.sense()
        return m

    def sense(self, radius: int = 2) -> None:
        r0, c0 = self.pos
        for r in range(SIZE):
            for c in range(SIZE):
                if abs(r - r0) + abs(c - c0) <= radius:
                    self.known.add((r, c))

    def render(self) -> str:
        rows = []
        for r in range(SIZE):
            row = []
            for c in range(SIZE):
                p = (r, c)
                row.append("?" if p not in self.known else "R" if p == self.pos else "G" if p == self.goal
                           else "B" if p == BASE else "#" if p in self.walls else ".")
            rows.append(" ".join(row))
        return "\n".join(rows)

    def act(self, action: str) -> str:
        if self.done:
            return "mission already ended"
        self.steps += 1
        self.energy -= 1
        dr, dc = DIRS[self.mapping[action]]
        before = self.pos
        nxt = before[0] + dr, before[1] + dc
        if not (0 <= nxt[0] < SIZE and 0 <= nxt[1] < SIZE) or nxt in self.walls:
            self.bumps += 1
            res = f"{action}: BUMP, stayed at ({before[0]},{before[1]})"
        else:
            self.pos = nxt
            res = f"{action}: moved ({before[0]},{before[1]}) -> ({nxt[0]},{nxt[1]})"
        self.sense()
        if self.pos == self.goal and not self.found:
            self.found = True
            res += "; BEACON FOUND, now return to base B"
        if self.found and self.pos == BASE:
            self.done = self.success = True
            res += "; MISSION SUCCESS"
        elif self.energy <= 0:
            self.done = True
            res += "; BATTERY EMPTY, mission failed"
        self.history.append(res)
        return res

    def prompt(self, notes: str, last: str) -> str:
        status = "BEACON FOUND: return to B" if self.found else "beacon not found yet"
        if self.controls == "hidden":
            controls = ("Controls: ACTION1, ACTION2, ACTION3, ACTION4. After a motor-controller fault each one drives "
                        "the rover one cell in a fixed compass direction, but nobody knows which action is which "
                        "direction. Work it out from how your position changes.")
        else:
            controls = "Controls: ACTION1 north (row-1), ACTION2 south (row+1), ACTION3 west (col-1), ACTION4 east (col+1)."
        hist = "\n".join("  " + h for h in self.history[-12:]) or "  (none yet)"
        return (
            f"Step {self.steps}. Energy {self.energy}/{self.energy_max}. {status}.\n"
            f"Rover position: row {self.pos[0]}, col {self.pos[1]}. Base B is at row {BASE[0]}, col {BASE[1]}.\n"
            "Map: row 0 is north (top), col 0 is west (left). R=rover, B=base, G=beacon, .=clear, #=wall, "
            "?=not seen yet. The sensor reveals cells within 2 steps (Manhattan distance).\n"
            f"{controls} Each action costs 1 energy, also when the rover bumps into a wall or the map edge.\n"
            "Goal: find the beacon G, then drive back to B before the energy runs out.\n"
            f"Recent actions (oldest first):\n{hist}\n"
            f"Your notes from last step: {notes or '(none)'}\n"
            f"Map (9 rows x 9 columns):\n{self.render()}\n"
            'Reply with only JSON: {"notes": "short memory: what each action does, plan", "action": "ACTION1|ACTION2|ACTION3|ACTION4"}'
        )


# ---- reference policies (sanity: the mission is solvable within the budget; random is near zero) ----

def oracle_action(m: Rover, rng: random.Random | None = None) -> str:
    """Knows the map only as seen; learns the mapping by probing (hidden), then frontier-explores with BFS."""
    import re
    inv = {}
    for h in m.history:  # recover learned mapping from history
        mm = re.match(r"(ACTION\d): moved \((\d),(\d)\) -> \((\d),(\d)\)", h)
        if mm:
            r0, c0, r1, c1 = map(int, mm.groups()[1:])
            inv[mm.group(1)] = (r1 - r0, c1 - c0)
    if m.controls == "fixed":
        inv = {a: DIRS[d] for a, d in FIXED.items()}
    elif len(inv) < 4:  # probe an untried action whose blocked/unknown status is unknown
        for a in ACTIONS:
            if a not in inv and not any(h.startswith(a + ": BUMP") for h in m.history[-1:]):
                return a
    free = {p for p in m.known if p not in m.walls}
    target = m.goal if m.goal in m.known and not m.found else BASE if m.found else None
    d = bfs(m.walls | (set((r, c) for r in range(SIZE) for c in range(SIZE)) - m.known), m.pos)
    if target is None:  # nearest known-free cell that borders the unknown
        front = [p for p in free if p in d and any((p[0] + dr, p[1] + dc) not in m.known and 0 <= p[0] + dr < SIZE
                                                   and 0 <= p[1] + dc < SIZE for dr, dc in DIRS.values())]
        target = min(front, key=lambda p: (d[p], p)) if front else m.pos
    # step along a shortest known path
    back = bfs(m.walls | (set((r, c) for r in range(SIZE) for c in range(SIZE)) - m.known), target)
    best = None
    for a, (dr, dc) in inv.items():
        n = m.pos[0] + dr, m.pos[1] + dc
        if n in back and (best is None or back[n] < back[best[1]]):
            best = (a, n)
    return best[0] if best else (rng or random).choice(ACTIONS)


if __name__ == "__main__":
    import sys
    seeds = range(1000, 1200)
    for controls in ("fixed", "hidden"):
        for name in ("oracle", "random"):
            ok = 0
            for s in seeds:
                m, rng = Rover.create(s, controls), random.Random(s)
                while not m.done:
                    m.act(oracle_action(m, rng) if name == "oracle" else rng.choice(ACTIONS))
                ok += m.success
            print(controls, name, f"{ok}/{len(seeds)}", file=sys.stdout)
