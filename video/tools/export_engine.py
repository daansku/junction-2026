"""Render engine frames for S1 (environment) into video/cache/engine.json.

Run with the repo venv (the engine lives there, not in video/.venv):
  .venv/Scripts/python.exe video/tools/export_engine.py
"""
from __future__ import annotations

import json
import pathlib

from engine import GameSpec, make_game
from engine.core.game import Game
from engine.generator.skin import make_skin

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "video" / "cache" / "engine.json"
SEED, DIFF = 1000, 1          # the Harbor task game (gridworld-s1000-d1-l6-...)
SKIN_LEVEL = 5                # level with the most objects, so the reshuffle is visible
MONTAGE_SEEDS = list(range(1001, 1037))
LADDER_SEED = 2000           # S1 difficulty dial: the same seed at difficulty 1-4   # other generated games for the S1 opening montage


def as_strings(frame) -> list[str]:
    if isinstance(frame, list) and frame and isinstance(frame[0], str):
        return frame
    if hasattr(frame, "to_hex"):
        return frame.to_hex()
    return ["".join(f"{int(v):x}" for v in row) for row in frame]


def main() -> None:
    spec = GameSpec(seed=SEED, difficulty=DIFF, n_levels=6)
    game = make_game(spec)
    desc = game.describe()
    levels = []
    for i, lv in enumerate(game.levels):
        game.goto_level(i + 1)
        frames = [as_strings(game.frame())]
        for a in lv.optimal_path:
            frames.append(as_strings(game.step(a)))
            if game.idx != i:          # level won: the last frame already shows the next level
                frames.pop()
                break
        levels.append({"level": i + 1, "new_rule": lv.new_rule, "rules": list(lv.rules),
                       "optimal_moves": lv.optimal_moves, "move_budget": lv.move_budget,
                       "optimal_path": list(lv.optimal_path), "frames": frames,
                       "optimal_pixels": desc["levels"][i]["optimal_pixels"],
                       "start_pixel": desc["levels"][i]["start_pixel"]})
    # same layout, other skins (the skins two other seeds would get)
    used = sorted({r for lv in game.levels for r in lv.rules})
    skins = []
    for other in (SEED, 4242, 7777):
        g = Game(spec, game.levels, make_skin(other, spec.family, True, used))
        g.goto_level(SKIN_LEVEL)
        skins.append(as_strings(g.frame()))
    # generator montage: one frame from each of many other generated games
    montage = []
    for k, other in enumerate(MONTAGE_SEEDS):
        g = make_game(GameSpec(seed=other, difficulty=1 + k % 3, n_levels=6))
        g.goto_level(1 + k % len(g.levels))
        montage.append({"seed": other, "game_id": g.game_id, "frame": as_strings(g.frame())})
    # difficulty ladder: one generated game per difficulty level, shown at its last level
    ladder = []
    for d in (1, 2, 3, 4):
        g = make_game(GameSpec(seed=LADDER_SEED, difficulty=d, n_levels=6))
        best = None
        for li, lv in enumerate(g.levels, start=1):   # the busiest level (most object cells) shows the difficulty best
            g.goto_level(li)
            fr = as_strings(g.frame())
            play = "".join(fr[6:])
            counts = sorted(((play.count(ch), ch) for ch in set(play)), reverse=True)
            busy = sum(n for n, _ in counts[2:])      # everything except the two commonest colours (floor, wall)
            if best is None or busy > best[0]:
                best = (busy, lv, fr)
        _, lv, fr = best
        ladder.append({"difficulty": d, "game_id": g.game_id, "rules": list(lv.rules),
                       "optimal_moves": lv.optimal_moves, "frame": fr})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"game_id": game.game_id, "levels": levels, "skins": skins, "skin_level": SKIN_LEVEL,
                               "montage": montage, "ladder": ladder}), encoding="utf-8")
    print(game.game_id, [len(l["frames"]) for l in levels])


if __name__ == "__main__":
    main()
