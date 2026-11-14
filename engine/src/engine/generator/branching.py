"""Branching levels (A7): the `gridbranch` family. More alternative routes, more complex levels.

Opt-in like `gridforce` (generator/interaction.py), which stays as it is so the two can be compared:
only families named "gridbranch*" use this file. Per level, on top of gridforce (new rule forced,
older rules soft, tidy multi-rule curriculum):

  * loopy layouts: braided mazes, rooms joined by several doorways, caves; optionally a walled goal
    vault with one entrance, so gate mechanics (doors, plates, phase walls, pits) still find a
    chokepoint while the rest of the map offers several routes;
  * a topology check that rejects corridor levels:
      - real_loops: independent cycles around wall clusters (planar faces of the floor graph that
        are not open 2x2 squares), so open floor does not count as "alternatives";
      - bypass share: fraction of the optimal path's cells that are NOT cut points of the floor
        graph, i.e. where a different route exists;
    both thresholds ramp with the level index and the difficulty;
  * larger grids and longer optimal plans as the game goes on, and "dense" placement (the
    components' non-teaching object counts) from level 3 on.

Changing any constant changes every `gridbranch` game: bump BRANCH_VERSION.
"""
from __future__ import annotations

import random
from collections import deque

from .. import components as comps
from ..core.level import Level, Pos
from ..core.rng import rng_for
from . import interaction
from .layout import border
from .placement import NBRS, Draft

BRANCH_VERSION = 1
MAX_W, MAX_H = 16, 14          # 4-px cells in the 64x58 play area
STYLES = ("braid", "braid", "rooms", "cave")
RELAX_AFTER = 40              # attempts after which the topology targets drop a step
VAULT_P = 0.5                  # share of candidates that wall the goal into a one-entrance vault


def enabled(family: str) -> bool:
    return family.startswith("gridbranch")


# ---- layouts ---------------------------------------------------------------------------------

def braid_layout(rng: random.Random, w: int, h: int, braid: float) -> set[Pos]:
    """Perfect maze on odd cells, then open a wall at a share `braid` of dead ends (loops)."""
    walls = {(x, y) for y in range(h) for x in range(w)}
    cells = [(x, y) for y in range(1, h - 1, 2) for x in range(1, w - 1, 2)]
    start = rng.choice(cells)
    walls.discard(start)
    stack = [start]
    while stack:
        x, y = stack[-1]
        nb = [(x + dx, y + dy, x + dx // 2, y + dy // 2) for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2))
              if 0 < x + dx < w - 1 and 0 < y + dy < h - 1 and (x + dx, y + dy) in walls]
        if not nb:
            stack.pop()
            continue
        nx, ny, mx, my = rng.choice(nb)
        walls -= {(nx, ny), (mx, my)}
        stack.append((nx, ny))
    for c in cells:
        if c in walls:
            continue
        opens = [(c[0] + dx, c[1] + dy) for dx, dy in NBRS if (c[0] + dx, c[1] + dy) not in walls]
        if len(opens) == 1 and rng.random() < braid:
            cand = [(c[0] + dx, c[1] + dy) for dx, dy in NBRS
                    if (c[0] + dx, c[1] + dy) in walls and 0 < c[0] + 2 * dx < w - 1 and 0 < c[1] + 2 * dy < h - 1]
            if cand:
                walls.discard(rng.choice(cand))
    # even-sized grids leave a solid last row/column: open a few cells into it
    for p in sorted(walls):
        if 0 < p[0] < w - 1 and 0 < p[1] < h - 1 and rng.random() < 0.06:
            walls.discard(p)
    return walls


def rooms_layout(rng: random.Random, w: int, h: int, extra: float) -> set[Pos]:
    """A 2-3 x 2-3 grid of rooms; every room-room wall gets one doorway (spanning tree first,
    then extra doorways with probability `extra`), plus a few pillars."""
    walls = border(w, h)
    nx = 2 if w < 12 else rng.choice((2, 3))
    ny = 2 if h < 11 else rng.choice((2, 3))
    xs = sorted(rng.sample(range(3, w - 3), nx - 1)) if nx > 1 else []
    ys = sorted(rng.sample(range(3, h - 3), ny - 1)) if ny > 1 else []
    if any(b - a < 3 for a, b in zip(xs, xs[1:])) or any(b - a < 3 for a, b in zip(ys, ys[1:])):
        xs, ys = xs[:1], ys[:1]
    for x in xs:
        walls |= {(x, y) for y in range(1, h - 1)}
    for y in ys:
        walls |= {(x, y) for x in range(1, w - 1)}
    bx, by = [0, *xs, w - 1], [0, *ys, h - 1]
    rooms = [(i, j) for i in range(len(bx) - 1) for j in range(len(by) - 1)]
    edges = []
    for i, j in rooms:
        if i + 1 < len(bx) - 1:
            edges.append(((i, j), (i + 1, j), [(bx[i + 1], y) for y in range(by[j] + 1, by[j + 1])]))
        if j + 1 < len(by) - 1:
            edges.append(((i, j), (i, j + 1), [(x, by[j + 1]) for x in range(bx[i] + 1, bx[i + 1])]))
    rng.shuffle(edges)
    parent = {r: r for r in rooms}

    def find(r):
        while parent[r] != r:
            parent[r] = parent[parent[r]]
            r = parent[r]
        return r
    for a, b, seg in edges:
        tree = find(a) != find(b)
        if tree:
            parent[find(a)] = find(b)
        if (tree or rng.random() < extra) and seg:
            walls.discard(rng.choice(seg))
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if (x, y) not in walls and x not in xs and y not in ys and rng.random() < 0.08:
                walls.add((x, y))
    return walls


def cave_layout(rng: random.Random, w: int, h: int, fill: float) -> set[Pos]:
    """Cellular-automaton cave, largest open component kept."""
    wall = {(x, y) for y in range(h) for x in range(w)
            if x in (0, w - 1) or y in (0, h - 1) or rng.random() < fill}
    for _ in range(3):
        nxt = set(border(w, h))
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                n = sum((x + dx, y + dy) in wall for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy)
                if n >= 5 or (n == 4 and (x, y) in wall):
                    nxt.add((x, y))
        wall = nxt
    floor = [(x, y) for y in range(h) for x in range(w) if (x, y) not in wall]
    if not floor:
        return wall
    best: set[Pos] = set()
    seen: set[Pos] = set()
    for f in floor:
        if f in seen:
            continue
        comp, q = {f}, deque([f])
        while q:
            cx, cy = q.popleft()
            for dx, dy in NBRS:
                n = (cx + dx, cy + dy)
                if n not in wall and n not in comp:
                    comp.add(n)
                    q.append(n)
        seen |= comp
        if len(comp) > len(best):
            best = comp
    return {(x, y) for y in range(h) for x in range(w) if (x, y) not in best}


def make_layout(rng: random.Random, style: str, w: int, h: int, difficulty: int) -> set[Pos]:
    if style == "braid":
        return braid_layout(rng, w, h, braid=0.35 + 0.1 * difficulty)
    if style == "rooms":
        return rooms_layout(rng, w, h, extra=0.35 + 0.1 * difficulty)
    return cave_layout(rng, w, h, fill=0.42)


def add_vault(dr: Draft) -> bool:
    """Wall the goal into a small room with one entrance (a chokepoint for gate mechanics)."""
    gx, gy = dr.goal
    r = 1 if dr.rng.random() < 0.6 else 2
    box = {(x, y) for x in range(gx - r, gx + r + 1) for y in range(gy - r, gy + r + 1)}
    ring = {(x, y) for x in range(gx - r - 1, gx + r + 2) for y in range(gy - r - 1, gy + r + 2)} - box
    ring = {p for p in ring if dr.inb(p) and 0 < p[0] < dr.w - 1 and 0 < p[1] < dr.h - 1}
    if dr.start in box | ring:
        return False
    doors = [p for p in ring if p[0] in range(gx - r, gx + r + 1) or p[1] in range(gy - r, gy + r + 1)]
    doors = [p for p in doors if p not in dr.walls]
    if not doors:
        return False
    door = dr.rng.choice(sorted(doors))
    dr.walls |= ring - {door}
    return dr.goal in dr.reach(dr.start)


# ---- topology metrics ------------------------------------------------------------------------

def topology(w: int, h: int, walls, path_cells: list[Pos]) -> dict:
    """real_loops and the bypass share of the path (cells that are not cut points)."""
    floor = {(x, y) for y in range(h) for x in range(w) if (x, y) not in walls}
    v = len(floor)
    e = sum(((x + 1, y) in floor) + ((x, y + 1) in floor) for x, y in floor)
    squares = sum(1 for x, y in floor if {(x + 1, y), (x, y + 1), (x + 1, y + 1)} <= floor)
    real_loops = max(0, e - v + 1 - squares)
    cut = _articulation(floor)
    inner = path_cells[1:-1]
    bypass = sum(c not in cut for c in inner) / len(inner) if inner else 0.0
    return {"real_loops": real_loops, "bypass": round(bypass, 3)}


def _articulation(floor: set[Pos]) -> set[Pos]:
    """Cut vertices of the floor graph (iterative Tarjan)."""
    disc: dict[Pos, int] = {}
    low: dict[Pos, int] = {}
    cut: set[Pos] = set()
    t = 0
    for root in sorted(floor):
        if root in disc:
            continue
        disc[root] = low[root] = t
        t += 1
        kids = 0
        stack = [(root, None, iter([(root[0] + dx, root[1] + dy) for dx, dy in NBRS]))]
        while stack:
            u, par, it = stack[-1]
            for n in it:
                if n not in floor or n == par:
                    continue
                if n in disc:
                    low[u] = min(low[u], disc[n])
                else:
                    disc[n] = low[n] = t
                    t += 1
                    if u == root:
                        kids += 1
                    stack.append((n, u, iter([(n[0] + dx, n[1] + dy) for dx, dy in NBRS])))
                    break
            else:
                stack.pop()
                if par is not None:
                    low[par] = min(low[par], low[u])
                    if par != root and low[u] >= disc[par]:
                        cut.add(par)
        if kids > 1:
            cut.add(root)
    return cut


def targets(difficulty: int, level_idx: int) -> tuple[int, float]:
    """(min real loops, min bypass share) for a level; ramps with level and difficulty."""
    loops = min(6, 1 + level_idx // 2 + (difficulty - 1))
    bypass = min(0.75, 0.30 + 0.05 * level_idx + 0.05 * (difficulty - 1))
    return loops, bypass


def path_cells(lv: Level, actions) -> list[Pos]:
    from ..core.actions import parse_action
    from ..core.step import initial_state, step_level
    s = initial_state(lv)
    out = [s.pos]
    for a in actions:
        s, _, _ = step_level(lv, s, parse_action(a))
        if s.pos != out[-1]:
            out.append(s.pos)
    return out


# ---- level candidate -------------------------------------------------------------------------

def _size(rng, difficulty: int, level_idx: int) -> tuple[int, int]:
    lo_w = min(MAX_W - 2, 9 + level_idx + difficulty // 2)
    lo_h = min(MAX_H - 2, 8 + level_idx + difficulty // 2)
    return rng.randint(lo_w, min(MAX_W, lo_w + 3)), rng.randint(lo_h, min(MAX_H, lo_h + 2))


def _min_optimal(difficulty: int, level_idx: int) -> int:
    return 8 + 3 * difficulty + 2 * level_idx


def try_level(seed: int, family: str, difficulty: int, level_idx: int, rules: tuple[str, ...],
              new_rule: str | None, attempt: int) -> Level | None:
    """Same contract as generator.try_level; called from there for gridbranch families."""
    from ..solver import compute_budget, random_walk_win_rate, solve
    from . import INTRO_ALLOWANCE, RANDOM_WALK_MAX, SLACK, SOLVER_CAP, rule_matters
    teaching = new_rule is not None
    rng = rng_for(family, seed, difficulty, "level", level_idx, ",".join(rules), attempt, "branch", BRANCH_VERSION)
    w, h = _size(rng, difficulty, level_idx)
    style = rng.choice(STYLES)
    if style == "braid":  # odd sizes: no solid wall band on the far side
        w, h = w - (w % 2 == 0), h - (h % 2 == 0)
    walls = make_layout(rng, style, w, h, difficulty)
    floor = [(x, y) for y in range(h) for x in range(w) if (x, y) not in walls]
    if len(floor) < 20:
        return None
    start = rng.choice(floor)
    dense = level_idx >= 3 or difficulty >= 3
    dr = Draft(w, h, walls, start, start, rng, difficulty, teaching and not dense, new_rule)
    dist = dr.reach(start)
    far = sorted((d, p) for p, d in dist.items() if d > 0)
    if not far:
        return None
    dr.goal = rng.choice(far[int(len(far) * 0.75):])[1]
    vault = level_idx > 0 and rules and rng.random() < VAULT_P
    if vault and not add_vault(dr):
        return None
    dr.occupied = {start, dr.goal}
    loops_min, bypass_min = targets(difficulty, level_idx)
    if attempt >= RELAX_AFTER:  # hard rule mixes: keep loops, ask for fewer of them
        loops_min, bypass_min = max(1, loops_min - 2), bypass_min - 0.15
    # cheap pre-check on the bare layout: enough loops before placing anything
    pre = topology(w, h, dr.walls, dr.path() or [])
    if pre["real_loops"] < loops_min:
        return None
    for c in sorted((comps.REGISTRY[r] for r in rules), key=lambda c: (c.place_order, c.name)):
        if not c.place(dr):
            return None
    data = dict(dr.data)
    data["layout"] = f"{style}{'+vault' if vault else ''}"
    lv = Level(w=w, h=h, walls=frozenset(dr.walls), start=start, goal=dr.goal,
               rules=tuple(rules), new_rule=new_rule, data=data)
    path = solve(lv, max_states=SOLVER_CAP)
    if path is None or len(path) < _min_optimal(difficulty, level_idx):
        return None
    topo = topology(w, h, lv.walls, path_cells(lv, path))
    if topo["real_loops"] < loops_min or topo["bypass"] < bypass_min:
        return None
    for r in rules:
        if not rule_matters(lv, r, len(path)):
            return None
    lv.optimal_moves = len(path)
    lv.optimal_path = [a.value for a in path]
    lv.move_budget = compute_budget(len(path), SLACK.get(difficulty, 2.5), INTRO_ALLOWANCE if teaching else 0)
    if random_walk_win_rate(lv, tries=200, seed=(seed, level_idx, attempt)) >= RANDOM_WALK_MAX:
        return None
    if not interaction.level_ok(lv, attempt):
        return None
    lv.data["attempt"] = attempt
    lv.data["topology"] = topo
    return lv
