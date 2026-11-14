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

v2 (BRANCH_VERSION 2) builds instead of rejecting: loops are opened in the layout until the
target is met, start and goal are a far pair, a goal vault is added whenever a gate rule needs a
chokepoint, and one_way / hazards / push_blocks / ice are placed on a minimum cut across every
start-goal route (the naive shortest route is the trap), so the mechanic is met whichever route
the player takes. Other rules keep A1's placement. Checks run cheapest first.

Changing any constant changes every `gridbranch` game: bump BRANCH_VERSION.
"""
from __future__ import annotations

import random
import time
from collections import Counter, deque

from .. import components as comps
from ..core.level import Level, Pos
from ..core.rng import rng_for
from . import interaction
from .layout import border
from .placement import NBRS, Draft

BRANCH_VERSION = 2
MAX_W, MAX_H = 16, 14          # 4-px cells in the 64x58 play area
STYLES = ("braid", "braid", "rooms", "cave")
RELAX_AFTER = 40              # attempts after which the topology targets drop a step
VAULT_P = 0.5                  # share of candidates that wall the goal into a one-entrance vault


# Diagnostics only (never read by generation): why candidates are rejected and where time goes.
REJECTS: Counter = Counter()   # (stage, rule) -> count; rule = the level's new rule or a placing rule
SECONDS: Counter = Counter()   # stage -> seconds


def _rej(stage: str, rule: str | None, t0: float):
    REJECTS[(stage, rule or "-")] += 1
    SECONDS[stage] += time.perf_counter() - t0
    return None


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


class BranchDraft(Draft):
    """Draft whose reach / path know teleporters: entering one end puts you on the other. A1's
    placement code calls these, so doors, plates and the rest still find the route (and its
    chokepoints) after teleporters have walled the goal side off."""

    def _link(self) -> dict:
        link = {}
        for ax, ay, bx, by in self.data.get("teleporters", {}).get("pairs", []):
            link[(ax, ay)], link[(bx, by)] = (bx, by), (ax, ay)
        return link

    def _nbrs(self, cur, link, blocked):
        for dx, dy in NBRS:
            n = (cur[0] + dx, cur[1] + dy)
            if self.inb(n) and n not in self.walls and n not in blocked:
                yield link.get(n, n)

    def reach(self, src, blocked=frozenset()):
        link = self._link()
        if not link:
            return super().reach(src, blocked)
        dist = {src: 0}
        q = deque([src])
        while q:
            cur = q.popleft()
            for n in self._nbrs(cur, link, blocked):
                if n not in dist:
                    dist[n] = dist[cur] + 1
                    q.append(n)
        return dist

    def path(self, src=None, dst=None, blocked=frozenset()):
        link = self._link()
        if not link:
            return super().path(src, dst, blocked)
        src = src or self.start
        dst = dst or self.goal
        prev = {src: None}
        q = deque([src])
        while q:
            cur = q.popleft()
            if cur == dst:
                out = []
                while cur is not None:
                    out.append(cur)
                    cur = prev[cur]
                return out[::-1]
            for n in self._nbrs(cur, link, blocked):
                if n not in prev:
                    prev[n] = cur
                    q.append(n)
        return None


# ---- v2 construction helpers: build what the checks want instead of rejecting -----------------

GATE_RULES = frozenset({"keys_doors", "plates_gates", "phase_walls", "pits", "teleporters", "rotation"})
DEEP_GATE = frozenset({"teleporters", "rotation"})     # need the cut cell >= 3 steps from the goal


def _dist(w: int, h: int, walls, src: Pos) -> dict[Pos, int]:
    dist = {src: 0}
    q = deque([src])
    while q:
        x, y = q.popleft()
        for dx, dy in NBRS:
            n = (x + dx, y + dy)
            if 0 <= n[0] < w and 0 <= n[1] < h and n not in walls and n not in dist:
                dist[n] = dist[(x, y)] + 1
                q.append(n)
    return dist


def build_loops(rng: random.Random, w: int, h: int, walls: set[Pos], target: int,
                keep: frozenset | set = frozenset(), strict: bool = True) -> bool:
    """Open interior walls that join two corridors far apart in the floor graph, until the layout
    has `target` real loops. Each opening adds one loop around a wall cluster (never a 2x2 square)."""
    for _ in range(3 * target + 6):
        if topology(w, h, walls, [])["real_loops"] >= target:
            return True
        cands = []
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if (x, y) not in walls or (x, y) in keep:
                    continue
                for (ax, ay), (bx, by) in ((((x - 1), y), (x + 1, y)), ((x, y - 1), (x, y + 1))):
                    if (ax, ay) in walls or (bx, by) in walls:
                        continue
                    # the two other sides must stay wall, so no open 2x2 square appears
                    side = ((x, y - 1), (x, y + 1)) if ay == y else ((x - 1, y), (x + 1, y))
                    if not strict or all(s in walls for s in side):
                        cands.append(((x, y), (ax, ay), (bx, by)))
                # 2-thick wall (caves): open two cells in a row
                for dx, dy in ((1, 0), (0, 1)):
                    c2 = (x + dx, y + dy)
                    a, b = (x - dx, y - dy), (x + 2 * dx, y + 2 * dy)
                    if c2 in walls and c2 not in keep and 0 < c2[0] < w - 1 and 0 < c2[1] < h - 1                             and a not in walls and b not in walls and 0 <= b[0] < w and 0 <= b[1] < h:
                        sides = [(x + dy, y + dx), (x - dy, y - dx), (c2[0] + dy, c2[1] + dx), (c2[0] - dy, c2[1] - dx)]
                        if not strict or all(s in walls for s in sides):
                            cands.append(((x, y), a, b, c2))
        if not cands:
            return False
        rng.shuffle(cands)
        best, best_d = None, 0
        for cand in cands[:24]:
            d = _dist(w, h, walls, cand[1]).get(cand[2], 99)
            if d > best_d:
                best, best_d = cand, d
        if best is None or best_d < 4:
            return False
        walls.discard(best[0])
        if len(best) == 4:
            walls.discard(best[3])
    return topology(w, h, walls, [])["real_loops"] >= target


def far_pair(rng: random.Random, w: int, h: int, walls, min_dist: int) -> tuple[Pos, list[Pos]] | None:
    """Start and goal near the ends of the map's longest shortest path (double sweep), at least
    `min_dist` apart in the floor graph. Returns the start and goal candidates, best first."""
    floor = sorted((x, y) for y in range(h) for x in range(w) if (x, y) not in walls)
    if not floor:
        return None
    d0 = _dist(w, h, walls, rng.choice(floor))
    ends = sorted(d0, key=lambda p: (-d0[p], p))[: max(1, len(d0) // 6)]
    start = rng.choice(ends)
    ds = _dist(w, h, walls, start)
    far = sorted((p for p in ds if ds[p] >= min_dist), key=lambda p: (-ds[p], p))
    if not far:
        return None
    top = far[: max(1, len(far) // 3)]
    rng.shuffle(top)
    return start, top


def make_vault(dr: Draft, r: int, corridor: int) -> set[Pos] | None:
    """Clear a (2r+1)^2 room holding the goal (shifted to fit inside the map), wall its ring except
    one entrance, chosen on the side farthest (in the floor graph) from the start. `corridor` cells
    outside the entrance are carved into a walled corridor, so there are 1 + corridor chokepoints in
    a row (one per door / gate / phase wall the level places). Returns the cells to keep as built, or
    None (walls restored)."""
    gx, gy = dr.goal
    bx = min(max(1, gx - r), dr.w - 2 - 2 * r)
    by = min(max(1, gy - r), dr.h - 2 - 2 * r)
    if bx < 1 or by < 1:
        return None
    box = {(x, y) for x in range(bx, bx + 2 * r + 1) for y in range(by, by + 2 * r + 1)}
    ring = {(x, y) for x in range(bx - 1, bx + 2 * r + 2) for y in range(by - 1, by + 2 * r + 2)} - box
    if dr.start in box | ring:
        return None
    cx, cy = bx + r, by + r
    old = set(dr.walls)
    dr.walls -= box
    dr.walls |= ring
    ds = dr.reach(dr.start)
    doors = []
    for dx, dy in NBRS:
        door = (cx + dx * (r + 1), cy + dy * (r + 1))
        out = (door[0] + dx, door[1] + dy)
        if out in ds and ds[out] >= 3 and 0 < door[0] < dr.w - 1 and 0 < door[1] < dr.h - 1:
            doors.append((ds[out], (dx, dy), door, out))
    if not doors:
        dr.walls = old
        return None
    _, (dx, dy), door, out = max(doors)
    dr.walls.discard(door)
    keep = box | ring | {out}
    cur = out
    for _ in range(corridor):
        nxt = (cur[0] + dx, cur[1] + dy)
        sides = [(cur[0] + dy, cur[1] + dx), (cur[0] - dy, cur[1] - dx)]
        if not (0 < nxt[0] < dr.w - 1 and 0 < nxt[1] < dr.h - 1) or dr.start in sides or cur == dr.start:
            break
        for c in sides:
            if 0 < c[0] < dr.w - 1 and 0 < c[1] < dr.h - 1:
                dr.walls.add(c)
                keep.add(c)
        dr.walls.discard(nxt)  # carve on through, so the corridor joins the map
        keep.add(nxt)
        cur = nxt
    if dr.goal not in dr.reach(dr.start):
        dr.walls = old
        return None
    return keep


# ---- placement on every route (one_way, hazards, push_blocks, ice) ----------------------------

ROUTE_RULES = frozenset({"one_way", "hazards", "push_blocks", "ice"})
DIRNAME = {(0, -1): "up", (0, 1): "down", (-1, 0): "left", (1, 0): "right"}


def route_cut(dr: Draft) -> list[Pos] | None:
    """Minimum vertex cut between the start side and the goal side of the map, taken in the middle
    band of the route (max-flow, unit node capacities). Every start-goal route crosses it once."""
    ds, dg = dr.reach(dr.start), dr.reach(dr.goal)
    L = ds.get(dr.goal)
    if not L or L < 8:
        return None
    lo, hi = int(L * 0.3), int(L * 0.7)
    src = {p for p in ds if ds[p] <= lo}
    snk = {p for p in dg if dg[p] <= L - hi}
    if src & snk:
        return None
    blocked = set(dr.occupied) - {dr.start, dr.goal}
    nodes = [p for p in ds if p not in blocked]
    INF = 10 ** 6
    cap: dict = {}
    adj: dict = {}

    def edge(a, b, c):
        cap[(a, b)] = cap.get((a, b), 0) + c
        cap.setdefault((b, a), 0)
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    S, T = ("S",), ("T",)
    for p in nodes:
        inside = p in src or p in snk
        edge((p, 0), (p, 1), INF if inside else 1)
        for dx, dy in NBRS:
            n = (p[0] + dx, p[1] + dy)
            if n in ds and n not in blocked:
                edge((p, 1), (n, 0), INF)
        if p in src:
            edge(S, (p, 0), INF)
        if p in snk:
            edge((p, 1), T, INF)
    flow = 0
    while flow < 6:
        par = {S: None}
        q = deque([S])
        while q and T not in par:
            u = q.popleft()
            for v in adj.get(u, ()):
                if v not in par and cap[(u, v)] > 0:
                    par[v] = u
                    q.append(v)
        if T not in par:
            break
        v = T
        while par[v] is not None:
            u = par[v]
            cap[(u, v)] -= 1
            cap[(v, u)] += 1
            v = u
        flow += 1
    if flow == 0 or flow >= 6:
        return None
    seen = {S}
    q = deque([S])
    while q:
        u = q.popleft()
        for v in adj.get(u, ()):
            if v not in seen and cap[(u, v)] > 0:
                seen.add(v)
                q.append(v)
    cut = sorted(p for p in nodes if (p, 0) in seen and (p, 1) not in seen)
    return cut if len(cut) == flow else None


def _travel(dr: Draft, c: Pos, ds, dg) -> tuple[int, int] | None:
    """Direction a shortest route through c moves when it passes c (start side to goal side)."""
    nb = [(c[0] + dx, c[1] + dy) for dx, dy in NBRS]
    prev = [n for n in nb if n in ds and ds[n] == ds[c] - 1]
    nxt = [n for n in nb if n in dg and dg[n] == dg[c] - 1]
    if nxt:
        n = min(nxt)
        return (n[0] - c[0], n[1] - c[1])
    if prev:
        p = min(prev)
        return (c[0] - p[0], c[1] - p[1])
    return None


def place_on_routes(dr: Draft, rule: str, cut: list[Pos]) -> bool:
    """Write `rule`'s level data (A1's format) so that every route meets the mechanic, with the
    routes differing: the naive shortest one is the trap, another is the way through."""
    ds, dg = dr.reach(dr.start), dr.reach(dr.goal)
    cut = [c for c in cut if c not in dr.occupied]
    if not cut:
        return False
    by_len = sorted(cut, key=lambda c: (ds.get(c, 99) + dg.get(c, 99), c))
    short = by_len[0]
    if rule == "one_way":
        if len(cut) < 2:
            return False
        tiles = []
        for c in by_len:
            d = _travel(dr, c, ds, dg)
            if d is None:
                return False
            if c == short:
                d = (-d[0], -d[1])  # naive shortest route: arrow against travel
            elif dr.rng.random() < 0.3 and len(tiles) < len(cut) - 1:
                d = (d[1], d[0]) if dr.rng.random() < 0.5 else (-d[1], -d[0])  # sideways: also shut
            tiles.append([*dr.claim(c), DIRNAME[d]])
        dr.data["one_way"] = {"tiles": tiles}
        return True
    if rule == "hazards":
        hp = 2 if dr.teaching else 3
        cells = []
        # lethal run along the naive shortest route, starting at its cut cell
        cur, d = short, _travel(dr, short, ds, dg)
        for _ in range(hp):
            if cur in dr.occupied or cur in (dr.start, dr.goal) or cur in dr.walls or not dr.inb(cur):
                return False
            cells.append(cur)
            nxt = [(cur[0] + dx, cur[1] + dy) for dx, dy in NBRS
                   if (cur[0] + dx, cur[1] + dy) in dg and dg[(cur[0] + dx, cur[1] + dy)] == dg.get(cur, 0) - 1]
            if not nxt:
                return False
            cur = min(nxt)
        for c in by_len[1:]:  # other routes: one survivable hazard, or none
            if dr.rng.random() < 0.5:
                cells.append(c)
        if not dr.teaching:
            free = dr.free(set(cells))
            cells += dr.rng.sample(free, min(dr.difficulty, len(free)))
        for c in cells:
            dr.claim(c)
        dr.data["hazards"] = {"cells": [list(c) for c in cells], "max_health": hp}
        return True
    if rule == "push_blocks":
        blocks = [dr.claim(c) for c in cut]
        dr.data["push_blocks"] = {"blocks": [list(b) for b in blocks]}
        return True
    if rule == "ice":
        ice: set[Pos] = set()
        for c in cut:
            d = _travel(dr, c, ds, dg)
            if d is None:
                return False
            run = dr.rng.randint(2, 4)
            for i in range(-1, run):  # a strip along travel through the cut cell, so crossing slides
                p = (c[0] + d[0] * i, c[1] + d[1] * i)
                if dr.inb(p) and p not in dr.walls and p not in dr.occupied:
                    ice.add(p)
            if dr.rng.random() < 0.5:  # widen sideways
                for p in list(ice):
                    q = (p[0] + d[1], p[1] + d[0])
                    if dr.inb(q) and q not in dr.walls and q not in dr.occupied:
                        ice.add(q)
        if len(ice) < 3:
            return False
        for p in ice:
            dr.claim(p)
        dr.data["ice"] = {"cells": [list(p) for p in sorted(ice)]}
        return True
    return False


# ---- level candidate -------------------------------------------------------------------------

def _size(rng, difficulty: int, level_idx: int) -> tuple[int, int]:
    lo_w = min(MAX_W - 2, 9 + level_idx + difficulty // 2)
    lo_h = min(MAX_H - 2, 8 + level_idx + difficulty // 2)
    return rng.randint(lo_w, min(MAX_W, lo_w + 3)), rng.randint(lo_h, min(MAX_H, lo_h + 2))


def _min_optimal(difficulty: int, level_idx: int) -> int:
    return 8 + 3 * difficulty + 2 * level_idx


def try_level(seed: int, family: str, difficulty: int, level_idx: int, rules: tuple[str, ...],
              new_rule: str | None, attempt: int) -> Level | None:
    """Same contract as generator.try_level; called from there for gridbranch families.
    v2: construct loops, a far start/goal pair, a vault when a gate rule needs one and route-wide
    placement for one_way / hazards / push_blocks / ice, then check; cheapest checks first."""
    from ..solver import compute_budget, random_walk_win_rate, solve
    from . import INTRO_ALLOWANCE, RANDOM_WALK_MAX, SLACK, SOLVER_CAP, rule_matters
    teaching = new_rule is not None
    nr = new_rule
    t0 = time.perf_counter()
    rng = rng_for(family, seed, difficulty, "level", level_idx, ",".join(rules), attempt, "branch", BRANCH_VERSION)
    w, h = _size(rng, difficulty, level_idx)
    style = rng.choice(STYLES)
    if style == "braid":  # odd sizes: no solid wall band on the far side
        w, h = w - (w % 2 == 0), h - (h % 2 == 0)
    walls = make_layout(rng, style, w, h, difficulty)
    if len([1 for y in range(h) for x in range(w) if (x, y) not in walls]) < 20:
        return _rej("layout", nr, t0)
    loops_min, bypass_min = targets(difficulty, level_idx)
    if attempt >= RELAX_AFTER:  # hard rule mixes: keep loops, ask for fewer of them
        loops_min, bypass_min = max(1, loops_min - 2), bypass_min - 0.15
    gate = GATE_RULES.intersection(rules)
    vault_r = 2 if DEEP_GATE.intersection(rules) else 1
    # the vault ring costs loops, so build a margin first
    # mechanics add detours, so the bare distance only needs ~60% of the minimum plan length
    pair = far_pair(rng, w, h, walls, int(0.6 * _min_optimal(difficulty, level_idx)))
    if pair is None:
        return _rej("pair", style, t0)
    start, goals = pair
    dense = level_idx >= 3 or difficulty >= 3
    dr = BranchDraft(w, h, walls, start, goals[0], rng, difficulty, teaching and not dense, new_rule)
    vault = bool(gate) or (level_idx > 0 and bool(rules) and rng.random() < VAULT_P / 2)
    keep: set = set()  # vault room, ring and entrance stay as built
    if vault:
        for g in goals[:12]:
            dr.goal = g
            k = make_vault(dr, vault_r, corridor=min(4, len(gate) + int(dense)))
            if k is not None:
                keep = k
                break
        else:
            return _rej("vault", style, t0)
    dr.occupied = {start, dr.goal}
    margin = 1 if "teleporters" in rules else 0  # the teleporter cut walls one loop off
    if not build_loops(rng, w, h, dr.walls, loops_min + margin, keep, strict=style != "cave"):
        return _rej("loops_build", style, t0)
    if dr.goal not in dr.reach(start):
        return _rej("loops_build", style, t0)
    SECONDS["layout"] += time.perf_counter() - t0
    t0 = time.perf_counter()
    cut = None
    for c in sorted((comps.REGISTRY[r] for r in rules), key=lambda c: (c.place_order, c.name)):
        if c.name in ROUTE_RULES:
            if cut is None:
                cut = route_cut(dr) or []
            if place_on_routes(dr, c.name, cut):
                cut = [p for p in cut if p not in dr.occupied] or route_cut(dr) or []
                continue
        if not c.place(dr):  # gates and the rest: A1's placement (vault gives the chokepoint)
            return _rej("place", c.name, t0)
    data = dict(dr.data)
    data["layout"] = f"{style}{'+vault' if vault else ''}"
    lv = Level(w=w, h=h, walls=frozenset(dr.walls), start=start, goal=dr.goal,
               rules=tuple(rules), new_rule=new_rule, data=data)
    SECONDS["place"] += time.perf_counter() - t0
    t0 = time.perf_counter()
    from ..solver import STATS
    n0 = STATS["states"]
    path = solve(lv, max_states=SOLVER_CAP)
    if path is None:
        return _rej("unsolvable_cap" if STATS["states"] - n0 >= SOLVER_CAP else "unsolvable", nr, t0)
    min_opt = _min_optimal(difficulty, level_idx)
    if "teleporters" in rules:  # a teleport is a shortcut by design
        min_opt = int(0.6 * min_opt)
    if len(path) < min_opt:
        return _rej("too_short", nr, t0)
    SECONDS["solve"] += time.perf_counter() - t0
    t0 = time.perf_counter()
    topo = topology(w, h, lv.walls, path_cells(lv, path))
    if topo["real_loops"] < loops_min:
        return _rej("loops", nr, t0)
    if topo["bypass"] < bypass_min:
        return _rej("bypass", nr, t0)
    lv.optimal_moves = len(path)
    lv.optimal_path = [a.value for a in path]
    if not interaction.level_ok(lv, attempt):
        return _rej("forcing", nr, t0)
    SECONDS["forcing"] += time.perf_counter() - t0
    t0 = time.perf_counter()
    for r in rules:
        if not rule_matters(lv, r, len(path)):
            return _rej("matters", r, t0)
    SECONDS["matters"] += time.perf_counter() - t0
    t0 = time.perf_counter()
    lv.move_budget = compute_budget(len(path), SLACK.get(difficulty, 2.5), INTRO_ALLOWANCE if teaching else 0)
    if random_walk_win_rate(lv, tries=200, seed=(seed, level_idx, attempt)) >= RANDOM_WALK_MAX:
        return _rej("random_walk", nr, t0)
    SECONDS["random_walk"] += time.perf_counter() - t0
    REJECTS[("accepted", nr or "-")] += 1
    lv.data["attempt"] = attempt
    lv.data["topology"] = topo
    return lv
