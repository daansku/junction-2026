"""Fine-tune dataset: chat-format SFT examples in exactly the harness h1 prompt format.

Each example = one harness turn: (system, user prompt built by agent_loop.build_parts, assistant JSON).
Trajectories:
  optimal  - follow the shortest path every turn
  gameover - wander on one random level until the budget runs out (context only), then RESET and
             play well: teaches recovery from GAME_OVER
  recover  - with probability p take a random detour move (context only, NOT a training target),
             then the target is the BFS replan from wherever that left us; GAME_OVER -> RESET.
So the model learns to act well from imperfect states, not just to replay perfect runs.

Only train-split games may go in here (train-v1, seeds disjoint from eval). The script refuses
collections whose name contains "eval".

    python -m arena dataset --collection train-v1 --out ~/junction-data/sft/train-v1.jsonl
    python -m arena dataset --seeds 0-199 --out sft.jsonl          # spec-generated games (dev only)
"""
from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

from .agent_loop import HARNESS_VERSION, SYSTEM, build_parts
from .frames import diff_count
from .solver import solve_level

MODES = ["rle"]          # text-only small models; lossless and compact
MAX_STEPS_PER_GAME = 600


def parts_to_text(parts: list[dict]) -> str:
    """Must match OpenAICompatProvider's text-only join, so training == inference."""
    return "\n\n".join(p["text"] for p in parts if p["type"] == "text")


def _compress(path: list[str]) -> str:
    out, i = [], 0
    while i < len(path):
        j = i
        while j + 1 < len(path) and path[j + 1] == path[i]:
            j += 1
        out.append(f"{path[i]}x{j - i + 1}" if j > i else path[i])
        i = j + 1
    return " ".join(out)


def _notes(t: dict, plan: list[str], detour: str | None) -> tuple[str, str]:
    lvl = f"Level {t['level']} of {t['levels_total']}."
    if t["state"] == "GAME_OVER":
        return f"{lvl} Out of moves on this level: the screen shows game over. RESET restarts the level.", \
               "running out of the moves bar ends the level"
    rule = t.get("new_rule")
    hyp = f"this level introduces a new mechanic ({rule}); test it, then use it" if rule else \
        "reach the goal; mechanics as on earlier levels"
    left = t["move_budget"] - t["moves_used"]
    notes = (f"{lvl} About {left} moves left on the bar. "
             + (f"Last move {detour} was a detour, replanning. " if detour else "")
             + f"Plan ({len(plan)} moves): {_compress(plan[:24])}{' ...' if len(plan) > 24 else ''}")
    return notes, hyp


INVERSE = {"ACTION1": "ACTION2", "ACTION2": "ACTION1", "ACTION3": "ACTION4", "ACTION4": "ACTION3"}


def completes_level(game, actions: list[str]) -> bool:
    """True if `actions` from the current state finish the level exactly on the last action."""
    g = game.clone()
    lv = g.truth()["level"]
    for i, a in enumerate(actions):
        g.step(a)
        t = g.truth()
        done = t["state"] == "WIN" or t["level"] > lv
        if done:
            return i == len(actions) - 1
        if t["state"] == "GAME_OVER":
            return False
    return False


def replan(game, before_detour: list[str], detour: str, describe: dict | None) -> list[str]:
    """Cheap candidates first (each verified by simulation), BFS only as a fallback.
    BFS deep-copies the game per node, which is too slow to run every step on thousands of games."""
    t = game.truth()
    if t["moves_used"] == 0 and describe:
        p = describe["levels"][t["level"] - 1].get("optimal_path")
        if p and completes_level(game, p):
            return list(p)
    cands = []
    if before_detour:
        cands.append(before_detour)                                   # detour was a no-op (bump)
        if detour in INVERSE:
            cands.append([INVERSE[detour]] + before_detour)           # step back, continue
    for c in sorted(cands, key=len):
        if completes_level(game, c):
            return c
    return solve_level(game) or []


def game_examples(game, rng: random.Random, kind: str, p_detour: float = 0.15, game_id: str = "") -> list[dict]:
    frame = game.frame() if hasattr(game, "frame") else game.reset()
    allowed = [getattr(a, "value", a) for a in game.available_actions()]
    moves = [a for a in allowed if a.startswith("ACTION") and a not in ("ACTION6", "ACTION7")]
    try:
        desc = game.describe()
    except Exception:
        desc = None
    notes, history, out = "", [], []
    nar = None
    if hasattr(game, "skin"):  # real engine game (MockGame has no skin/rules): discovery rationales
        from engine.tasks.rationale import Narrator  # visible colour/shape, effects only after seen, no rule names
        nar = Narrator(game)
    plan: list[str] = []
    detour, before = None, []
    blow_level = rng.randint(1, game.truth()["levels_total"]) if kind == "gameover" else None
    for step in range(1, MAX_STEPS_PER_GAME + 1):
        t = game.truth()
        if t["state"] == "WIN":
            break
        if blow_level is not None and t["state"] == "GAME_OVER":
            blow_level, detour = None, None  # blown once; from here on: RESET, then play well
        if blow_level is not None and t["level"] == blow_level and t["state"] != "GAME_OVER":
            a = rng.choice(moves)  # wander (context only) until the budget runs out
            plan = []
            prev = frame
            frame = game.step(a)
            if nar:
                nar.after(a, game)
            history.append((a, diff_count(prev, frame)))
            continue
        take_detour = kind == "recover" and t["state"] != "GAME_OVER" and detour is None and rng.random() < p_detour
        example = None
        if take_detour:
            a = rng.choice([m for m in moves if not plan or m != plan[0]] or moves)
            detour, before, plan = a, plan, []
        else:
            if t["state"] == "GAME_OVER":
                a, plan = "RESET", []
                new_notes, hyp = nar.before([], None) if nar else _notes(t, [], None)
            else:
                if not plan:
                    plan = replan(game, before, detour, desc)
                    if not plan:
                        break  # unsolvable from here (should not happen with RESET allowed)
                a = plan[0]
                new_notes, hyp = nar.before(plan, detour) if nar else _notes(t, plan, detour)
            allowed_now = [getattr(x, "value", x) for x in game.available_actions()] or allowed
            prompt = parts_to_text(build_parts(frame, notes, history, allowed_now, MODES, step))
            example = (prompt, new_notes, hyp, a, t["level"])
            notes, detour, before = new_notes, None, []
            plan = plan[1:] if plan and plan[0] == a else []
        prev = frame
        frame = game.step(a)
        if nar:
            nar.after(a, game)
        history.append((a, diff_count(prev, frame)))
        if example:
            prompt, new_notes, hyp, a, lvl = example
            belief = "won" if game.truth()["state"] == "WIN" else "playing"
            reply = json.dumps({"notes": new_notes, "hypothesis": hyp, "belief": belief, "action": a})
            out.append({"messages": [{"role": "system", "content": SYSTEM},
                                     {"role": "user", "content": prompt},
                                     {"role": "assistant", "content": reply}],
                        "meta": {"game_id": game_id, "kind": kind, "level": lvl, "step": step,
                                 "harness_version": HARNESS_VERSION, "modes": MODES}})
    return out


def _count(rng: random.Random, n: float) -> int:
    """Fractional per-game count: 0.3 = one trajectory in 30% of games (lets you hit a target mix)."""
    whole = int(n)
    return whole + (1 if rng.random() < n - whole else 0)


def build(games, out_path: Path, n_recover: float = 2, n_gameover: float = 1, seed: int = 0, log=print) -> Counter:
    """games: iterable of (game_id, factory) where factory() returns a fresh Game."""
    rng = random.Random(seed)
    stats = Counter()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for gid, factory in games:
            kinds = ["optimal"] + ["recover"] * _count(rng, n_recover) + ["gameover"] * _count(rng, n_gameover)
            for kind in kinds:
                exs = game_examples(factory(), rng, kind, game_id=gid)
                for e in exs:
                    f.write(json.dumps(e) + "\n")
                stats[kind] += len(exs)
            stats["games"] += 1
    log(f"wrote {out_path}: {dict(stats)}")
    return stats


def games_from(eng, collection: str | None, seeds: list[int] | None, n_levels: int = 6):
    if collection:
        if "eval" in collection:
            raise SystemExit("refusing to build training data from an eval collection")
        for meta in eng.list_games(collection):
            gid = meta["game_id"]
            yield gid, (lambda gid=gid: eng.load_game(collection, gid))
    else:
        for s in seeds or []:
            spec = eng.GameSpec(seed=s, n_levels=n_levels)
            yield f"spec-s{s}", (lambda spec=spec: eng.make_game(spec))
