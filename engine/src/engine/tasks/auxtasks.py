"""Auxiliary verifiable tasks (single turn, auto-graded by the engine).

  next_frame   predict the next frame after an action (given one earlier transition as context)
  rule_effect  which plain-language effect explains a before/after pair (multiple choice)
  min_moves    minimum number of moves to finish a level shown as a text grid with a legend
  full_plan    write the whole action plan for a level from a text grid; replayed in the engine

Perception tasks use the arena's RLE frame text (pixels only, no rule names). Planning tasks describe
the mechanics in plain words: they train planning, not discovery. Sources: train-v1 only.
"""
from __future__ import annotations

import re

from ..core.actions import Action, parse_action
from ..core.level import Level
from ..core.step import LEVEL_WON, LOST, initial_state, step_level
from .common import (ACTIONS_HELP, MOVES, RLE_HELP, Sample, apply_rle_patch, changed_rows_rle,
                     first_line, pick_game, task_rng, to_rle, visible_roles)

LETTERS = "ABCD"


# ---- state sampling ----------------------------------------------------------------------
def sample_state(rng, min_prefix: int = 1, max_prefix: int = 14, tries: int = 20):
    """A game positioned mid-level after a short, partly random walk along the optimal path.
    Returns (game, prev_frame, prev_action) or None."""
    for _ in range(tries):
        g = pick_game(rng)
        li = rng.randrange(len(g.levels))
        g.goto_level(li + 1)
        path = list(g.level.optimal_path)
        if len(path) < 2:
            continue
        k = rng.randint(min_prefix, min(max_prefix, len(path) - 1))
        prev_frame, prev_action, ok = g.frame(), None, True
        for i in range(k):
            a = rng.choice(MOVES).value if rng.random() < 0.25 else path[i]
            prev_frame, prev_action = g.frame(), a
            g.step(a)
            if g.status != "NOT_FINISHED" or g.idx != li:
                ok = False
                break
        if ok and prev_action is not None:
            return g, prev_frame, prev_action
    return None


def sample_event_state(rng, tries: int = 20):
    """A game positioned right before an optimal-path step that triggers a mechanic (anything
    beyond a plain move or a bump). Returns (game, prev_frame, prev_action, action) or None."""
    for _ in range(tries):
        g = pick_game(rng)
        li = rng.randrange(len(g.levels))
        if not g.levels[li].rules:
            continue
        g.goto_level(li + 1)
        path = list(g.level.optimal_path)
        probe, hits = g.clone(), []
        for i, a in enumerate(path):
            probe.step(a)
            if i >= 1 and effects_of(probe.events)[0] not in ("plain", "bump", "level"):
                hits.append(i)
        if not hits:
            continue
        k = rng.choice(hits)
        prev_frame = prev_action = None
        for a in path[:k]:
            prev_frame, prev_action = g.frame(), a
            g.step(a)
        return g, prev_frame, prev_action, path[k]
    return None


# ---- effects (plain-language, never rule names) ----------------------------------------
EFFECTS = {
    "level": "You reached the goal and a new, different board appeared.",
    "lost": "You lost the level: the floor filled with a red pattern.",
    "decoy": "You reached something that looked like the goal and were sent back to where the level started.",
    "teleport": "You stepped onto a tile and reappeared somewhere else on the board.",
    "rotate": "The whole board turned around.",
    "controls": "You touched a tile that changes which way the arrow actions move you.",
    "collapse": "The tile you had just been standing on turned into a hole.",
    "door": "A barrier in your way vanished and you moved into its place.",
    "pickup": "You stepped onto an item; it disappeared and a marker in the top bar filled in.",
    "plate": "Stepping onto a tile made a barrier elsewhere open or close.",
    "pushed": "You moved and shoved an object one cell ahead of you.",
    "hurt": "You stepped onto a tile and a meter in the top bar went down.",
    "refill": "You stepped onto an item and a meter in the top bar was refilled.",
    "slide": "You kept sliding in the same direction past the cell you stepped to.",
    "phase": "Some walls appeared or disappeared on their own, without you touching them.",
    "bump": "You did not move: something blocked the way. Only the bar at the top changed.",
    "plain": "You moved one cell in the direction you pressed; apart from the bar at the top, nothing else changed.",
}
_EVENT_EFFECT = [("level_complete", "level"), ("level_lost", "lost"), ("decoy", "decoy"),
                 ("teleport", "teleport"), ("rotated", "rotate"), ("controls_changed", "controls"),
                 ("floor_collapsed", "collapse"), ("opened_door", "door"), ("picked_key", "pickup"),
                 ("collected", "pickup"), ("pressed_plate", "plate"), ("pushed", "pushed"),
                 ("hurt", "hurt"), ("refilled", "refill"), ("slid:", "slide"),
                 ("walls_closed", "phase"), ("walls_opened", "phase"), ("bump", "bump")]


def effects_of(events: list[str]) -> list[str]:
    """All effects present, most salient first; 'plain' if none."""
    out = []
    for key, eff in _EVENT_EFFECT:
        if any(e == key or (key.endswith(":") and e.startswith(key)) for e in events) and eff not in out:
            out.append(eff)
    return out or ["plain"]


# ---- next_frame ------------------------------------------------------------------------
def make_next_frame(seed: int, i: int) -> Sample | None:
    rng = task_rng("next_frame", seed, i)
    forced = None
    if rng.random() < 0.5 and (ev_st := sample_event_state(rng)):
        g, prev_frame, prev_action, forced = ev_st
    elif st := sample_state(rng):
        g, prev_frame, prev_action = st
    else:
        return None
    frame_b = g.frame()
    if forced:
        c = g.clone()
        frame_c = c.step(forced)
        if "level_complete" not in c.events:
            return _next_frame_sample(seed, i, g, prev_frame, prev_action, frame_b, forced, frame_c, c.events)
    cands = {"interesting": [], "plain": [], "bump": []}
    for a in g.available_actions():
        if a == Action.RESET:
            continue
        c = g.clone()
        fc = c.step(a)
        ev = c.events
        if "level_complete" in ev:  # next board is not predictable from this one
            continue
        kind = "bump" if "bump" in ev and len(ev) == 1 else "plain" if not ev else "interesting"
        cands[kind].append((a.value, fc, ev))
    r = rng.random()
    order = (["interesting", "plain", "bump"] if r < 0.5 else ["plain", "interesting", "bump"] if r < 0.9
             else ["bump", "plain", "interesting"])
    pool = next((cands[k] for k in order if cands[k]), None)
    if not pool:
        return None
    a, frame_c, ev = rng.choice(pool)
    return _next_frame_sample(seed, i, g, prev_frame, prev_action, frame_b, a, frame_c, ev)


def _next_frame_sample(seed, i, g, prev_frame, prev_action, frame_b, a, frame_c, ev) -> Sample:
    prompt = (f"{RLE_HELP}\nActions: {ACTIONS_HELP}.\n\n"
              f"Frame A:\n{to_rle(prev_frame)}\n\nThe player pressed {prev_action}, which gave frame B:\n"
              f"{to_rle(frame_b)}\n\nFrom frame B the player now presses {a}. Predict the next frame.\n"
              "After 'ANSWER:' write only the rows that differ from frame B, one run-length line per row "
              "or row range, each on its own line. Rows you leave out stay as in frame B.")
    return Sample("next_frame", f"next_frame-{seed}-{i}", prompt, changed_rows_rle(frame_b, frame_c),
                  {"game_id": g.game_id, "level": g.idx + 1, "action": a, "events": ev,
                   "frame_before": frame_b, "frame_after": frame_c})


_RLE_START = re.compile(r"^\s*r\d+(?:-\d+)?\s*:")


def grade_next_frame(s: dict, ans: str) -> float:
    lines = ans.splitlines()
    if ans.strip().upper() in ("NONE", "NO CHANGE"):
        rows = ""
    else:
        k = 0
        while k < len(lines) and (_RLE_START.match(lines[k]) or not lines[k].strip()):
            k += 1
        if any(ln.strip() for ln in lines[k:]) and k == 0:
            return 0.0
        rows = chr(10).join(lines[:k])
    patched = apply_rle_patch(s["meta"]["frame_before"], rows)
    return 1.0 if patched is not None and patched == s["meta"]["frame_after"] else 0.0


# ---- rule_effect -----------------------------------------------------------------------
def make_rule_effect(seed: int, i: int) -> Sample | None:
    rng = task_rng("rule_effect", seed, i)
    forced = None
    if rng.random() < 0.7 and (ev_st := sample_event_state(rng)):
        g, forced = ev_st[0], ev_st[3]
    elif st := sample_state(rng):
        g = st[0]
    else:
        return None
    before = g.frame()
    trans = []
    for a in g.available_actions():
        if a == Action.RESET:
            continue
        c = g.clone()
        after = c.step(a)
        trans.append((a.value, after, effects_of(c.events)))
    special = [t for t in trans if t[2][0] not in ("plain", "bump")]
    hit = [t for t in trans if t[0] == forced]
    a, after, effs = hit[0] if hit else rng.choice(special if special and rng.random() < 0.75 else trans)
    gold = effs[0]
    pool = sorted(k for k in EFFECTS if k not in effs)
    opts = [gold] + rng.sample(pool, 3)
    rng.shuffle(opts)
    letter = LETTERS[opts.index(gold)]
    choices = "\n".join(f"{LETTERS[j]}. {EFFECTS[o]}" for j, o in enumerate(opts))
    prompt = (f"{RLE_HELP}\nActions: {ACTIONS_HELP}.\n\nBefore:\n{to_rle(before)}\n\n"
              f"The player pressed {a}. After:\n{to_rle(after)}\n\n"
              f"Which statement best describes what happened?\n{choices}\n"
              "After 'ANSWER:' write only the letter.")
    return Sample("rule_effect", f"rule_effect-{seed}-{i}", prompt, letter,
                  {"game_id": g.game_id, "level": g.idx + 1, "action": a, "effect": gold,
                   "options": opts})


def grade_letter(s: dict, ans: str) -> float:
    ans = first_line(ans)
    m = re.fullmatch(r"\(?([A-Da-d])[).]?", ans.strip())
    return 1.0 if m and m.group(1).upper() == s["answer"] else 0.0


# ---- planning tasks: text grid + legend --------------------------------------------------
PLAN_RULES = {"keys_doors", "plates_gates", "push_blocks", "one_way", "ice", "collect_all",
              "cracked_floor", "hazards", "teleporters", "beacon_goal"}
_ARROW = {"arrow_up": "^", "arrow_down": "v", "arrow_left": "<", "arrow_right": ">"}
_SYM = {"wall": "#", "player": "@", "goal": "G", "key": "k", "door": "D", "plate": "p", "gate": "=",
        "block": "B", "gem": "*", "hazard": "x", "ice": "~", "cracked": "c", "hole": "o",
        "decoy_a": "F", "decoy_b": "F"}
_LEGEND = {
    "#": "wall",
    "@": "you",
    "G": "the goal: stepping onto it finishes the level",
    "k": "key: step onto it to pick it up (any key opens any door)",
    "D": "locked door: walking into it while holding a key opens it and uses the key up",
    "p": "pressure plate: every time you step onto one, every gate switches between open and closed",
    "=": "closed gate (blocks you while closed)",
    "B": "block: walking into it pushes it one cell if the cell behind it is free (not a wall, block, closed gate/door or the goal)",
    "*": "gem: all gems must be collected (step onto them) before the goal counts",
    "x": "hazard: stepping onto it costs one health",
    "~": "ice: moving onto ice keeps you sliding the same way until something blocks you or you reach a non-ice cell",
    "c": "cracked floor: holds you once; after you step off it, it becomes a hole you can never enter again",
    "F": "fake goal: stepping onto it sends you back to your starting cell",
    "^": "one-way tile: can only be entered moving up",
    "v": "one-way tile: can only be entered moving down",
    "<": "one-way tile: can only be entered moving left",
    ">": "one-way tile: can only be entered moving right",
}


def text_grid(level: Level, skin) -> tuple[str, str] | None:
    """(grid, legend) for the level's start, or None if something can't be shown in text."""
    st = initial_state(level)
    cells = visible_roles(level, st, skin)
    tel = {}
    for n, (ax, ay, bx, by) in enumerate(level.data.get("teleporters", {}).get("pairs", []), 1):
        tel[(ax, ay)] = tel[(bx, by)] = str(n)
    used, rows = set(), []
    for y in range(level.h):
        row = []
        for x in range(level.w):
            p = (x, y)
            if p == st.pos:
                ch = "@"
            elif p == level.goal:
                ch = "G"
            elif p in tel:
                ch = tel[p]
            elif p in cells:
                role, sprite = cells[p]
                ch = _ARROW.get(sprite) if role == "one_way" else _SYM.get(role)
                if ch is None:
                    return None
            else:
                ch = "."
            used.add(ch)
            row.append(ch)
        rows.append("".join(row))
    leg = ["'.' = floor"] + [f"'{c}' = {_LEGEND[c]}" for c in "#@G" if c in used]
    leg += [f"'{c}' = {d}" for c, d in _LEGEND.items() if c in used and c not in "#@G"]
    if tel:
        leg.append("'1', '2', ... = teleporter pair: stepping onto one end moves you to the other end with the same digit (if it is free)")
    if "hazards" in level.rules:
        leg.append(f"You start with {level.data['hazards']['max_health']} health; at 0 health you lose the level.")
    return "\n".join(rows), "\n".join(leg)


def _plan_level(rng, tries: int = 40):
    for _ in range(tries):
        g = pick_game(rng)
        li = rng.randrange(len(g.levels))
        lv = g.levels[li]
        if not set(lv.rules) <= PLAN_RULES or lv.optimal_moves < 3:
            continue
        if not lv.rules and rng.random() < 0.75:
            continue
        tg = text_grid(lv, g.skin)
        if tg:
            return g, li, lv, tg
    return None


def _plan_prompt(lv: Level, grid: str, legend: str) -> str:
    return (f"A grid puzzle. Row 1 is the top row. Legend:\n{legend}\n\nGrid ({lv.w} wide, {lv.h} tall):\n{grid}\n\n"
            f"Each action moves you one cell: {ACTIONS_HELP.replace(', ACTION5 = interact', '')}. "
            f"Moving into a wall or the edge does nothing but still counts as a move. You have at most "
            f"{lv.move_budget} moves.")


def make_min_moves(seed: int, i: int) -> Sample | None:
    rng = task_rng("min_moves", seed, i)
    got = _plan_level(rng)
    if not got:
        return None
    g, li, lv, (grid, legend) = got
    prompt = (_plan_prompt(lv, grid, legend) + "\n\nWhat is the smallest number of moves that finishes the "
              "level? After 'ANSWER:' write only the number.")
    return Sample("min_moves", f"min_moves-{seed}-{i}", prompt, str(lv.optimal_moves),
                  {"game_id": g.game_id, "level": li + 1, "rules": list(lv.rules)})


def grade_min_moves(s: dict, ans: str) -> float:
    ans = first_line(ans)
    m = re.fullmatch(r"\s*(\d{1,4})\s*\.?\s*", ans)
    return 1.0 if m and int(m.group(1)) == int(s["answer"]) else 0.0


def make_full_plan(seed: int, i: int) -> Sample | None:
    rng = task_rng("full_plan", seed, i)
    got = _plan_level(rng)
    if not got:
        return None
    g, li, lv, (grid, legend) = got
    prompt = (_plan_prompt(lv, grid, legend) + "\n\nWrite a sequence of actions that finishes the level in as "
              "few moves as you can. After 'ANSWER:' write the actions separated by spaces, e.g. "
              "'ACTION4 ACTION4 ACTION2'. You may write 'ACTION4x3' for three ACTION4 in a row.")
    return Sample("full_plan", f"full_plan-{seed}-{i}", prompt, compress(list(lv.optimal_path)),
                  {"game_id": g.game_id, "level": li + 1, "rules": list(lv.rules),
                   "optimal_moves": lv.optimal_moves, "level_data": lv.to_dict()})


def compress(path: list[str]) -> str:
    out, i = [], 0
    while i < len(path):
        j = i
        while j + 1 < len(path) and path[j + 1] == path[i]:
            j += 1
        out.append(f"{path[i]}x{j - i + 1}" if j > i else path[i])
        i = j + 1
    return " ".join(out)


MAX_PLAN = 400


def parse_plan(ans: str) -> list[Action] | None:
    """'ACTION4x3 ACTION2' -> actions. None if any token is invalid or the plan is absurdly long."""
    out: list[Action] = []
    for tok in ans.replace(",", " ").split():
        m = re.fullmatch(r"(ACTION[1-5])(?:[xX\*](\d{1,3}))?", tok.strip().upper())
        if not m:
            return None
        out += [parse_action(m.group(1))] * int(m.group(2) or 1)
        if len(out) > MAX_PLAN:
            return None
    return out


def score_plan(lv: Level, actions: list[Action]) -> float:
    """Efficiency on one level: min(1, optimal / actions used) if the plan finishes the level
    within the move budget, else 0. Actions after the winning move are counted (no padding)."""
    if not actions or len(actions) > lv.move_budget:
        return 0.0
    s = initial_state(lv)
    for n, a in enumerate(actions, 1):
        s, _, out = step_level(lv, s, a)
        if out == LEVEL_WON:
            return min(1.0, lv.optimal_moves / len(actions)) if n == len(actions) else \
                min(1.0, lv.optimal_moves / len(actions))
        if out == LOST:
            return 0.0
    return 0.0


def grade_full_plan(s: dict, ans: str) -> float:
    ans = first_line(ans)
    acts = parse_plan(ans)
    if acts is None:
        return 0.0
    return score_plan(Level.from_dict(s["meta"]["level_data"]), acts)


# ---- perception grounding (SFT v1 bumps walls ~65% of moves, misreads the level) ----------
def _context(rng):
    """Mid-level state plus the transition that led to it (so 'you' = what moved)."""
    st = sample_state(rng, min_prefix=1, max_prefix=20)
    if st is None:
        return None
    g, prev_frame, prev_action = st
    if prev_frame == g.frame():
        return None
    return g, (f"{RLE_HELP}\nActions: {ACTIONS_HELP}. The player controls one object.\n\n"
               f"Frame A:\n{to_rle(prev_frame)}\n\nThe player pressed {prev_action}, which gave frame B:\n"
               f"{to_rle(g.frame())}\n\n")


def make_blocked_moves(seed: int, i: int) -> Sample | None:
    rng = task_rng("blocked_moves", seed, i)
    ctx = _context(rng)
    if ctx is None:
        return None
    g, head = ctx
    blocked = []
    for a in MOVES:
        c = g.clone()
        c.step(a)
        if c.events == ["bump"]:
            blocked.append(a.value)
    # flatten the answer distribution so a constant answer can't farm reward
    keep = {0: 0.5, 1: 0.45, 2: 1.0, 3: 1.0}.get(len(blocked), 1.0)
    if rng.random() > keep:
        return None
    ans = " ".join(blocked) if blocked else "NONE"
    prompt = (head + "In frame B, which of ACTION1, ACTION2, ACTION3, ACTION4 would leave the player where it is "
              "(blocked by something)? After 'ANSWER:' list them separated by spaces in any order, or write NONE.")
    return Sample("blocked_moves", f"blocked_moves-{seed}-{i}", prompt, ans,
                  {"game_id": g.game_id, "level": g.idx + 1, "blocked": blocked})


def grade_blocked_moves(s: dict, ans: str) -> float:
    ans = first_line(ans)
    toks = ans.replace(",", " ").upper().split()
    if toks == ["NONE"]:
        got: set | None = set()
    elif toks and all(re.fullmatch(r"ACTION[1-4]", t) for t in toks) and len(set(toks)) == len(toks):
        got = set(toks)
    else:
        got = None
    return 1.0 if got is not None and got == set(s["meta"]["blocked"]) else 0.0


def _player_pixel(g) -> tuple[int, int] | None:
    """Top-left pixel (row, col) of the player's square in the play area (rows 6-63)."""
    col = "%x" % g.skin["player"][0]
    f = g.frame()
    pts = [(y, x) for y in range(6, 64) for x in range(64) if f[y][x] == col]
    if not pts:
        return None
    return min(y for y, _ in pts), min(x for _, x in pts)


def make_locate_player(seed: int, i: int) -> Sample | None:
    rng = task_rng("locate_player", seed, i)
    ctx = _context(rng)
    if ctx is None:
        return None
    g, head = ctx
    px = _player_pixel(g)
    if px is None:
        return None
    prompt = (head + "In frame B, where is the player? After 'ANSWER:' write the row and column (0-based, row 0 = top "
              "line, column 0 = left) of the top-left cell of the player's square, as 'row,col'.")
    return Sample("locate_player", f"locate_player-{seed}-{i}", prompt, f"{px[0]},{px[1]}",
                  {"game_id": g.game_id, "level": g.idx + 1})


def grade_pair(s: dict, ans: str) -> float:
    ans = first_line(ans)
    m = re.fullmatch(r"\s*\(?\s*(\d{1,2})\s*[,/ ]\s*(\d{1,2})\s*\)?\s*", ans)
    return 1.0 if m and f"{int(m.group(1))},{int(m.group(2))}" == s["answer"] else 0.0


def make_level_index(seed: int, i: int) -> Sample | None:
    rng = task_rng("level_index", seed, i)
    g = pick_game(rng)
    li = rng.randrange(len(g.levels))
    g.goto_level(li + 1)
    path = list(g.level.optimal_path)
    for _ in range(rng.randint(0, max(0, min(10, len(path) - 1)))):
        g.step(rng.choice(MOVES))
        if g.status != "NOT_FINISHED" or g.idx != li:
            return None
    prompt = (f"{RLE_HELP}\n\nScreen:\n{to_rle(g.frame())}\n\nThe game has several levels; the row of small "
              "squares near the top shows progress through them. Which level is being played, and how many levels "
              "are there? After 'ANSWER:' write 'current/total', e.g. '2/6'.")
    return Sample("level_index", f"level_index-{seed}-{i}", prompt, f"{li + 1}/{len(g.levels)}",
                  {"game_id": g.game_id, "level": li + 1})


def grade_fraction(s: dict, ans: str) -> float:
    ans = first_line(ans)
    m = re.fullmatch(r"\s*(\d{1,2})\s*(?:/|of)\s*(\d{1,2})\s*", ans, re.I)
    return 1.0 if m and f"{int(m.group(1))}/{int(m.group(2))}" == s["answer"] else 0.0


TASKS = {
    "next_frame": (make_next_frame, grade_next_frame),
    "rule_effect": (make_rule_effect, grade_letter),
    "min_moves": (make_min_moves, grade_min_moves),
    "full_plan": (make_full_plan, grade_full_plan),
    "blocked_moves": (make_blocked_moves, grade_blocked_moves),
    "locate_player": (make_locate_player, grade_pair),
    "level_index": (make_level_index, grade_fraction),
}
