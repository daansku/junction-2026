"""python -m engine {gen, collection, play, render, verify}"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .core.actions import Action, parse_action
from .core.game import Game, GameSpec, collection_path, load_collection, make_game
from .core.version import ENGINE_VERSION
from .render.png import contact_sheet, frame_png, write_png


def _spec(a) -> GameSpec:
    return GameSpec(family=a.family, seed=a.seed, n_levels=a.levels, difficulty=a.difficulty,
                    skin_shuffle=not a.no_shuffle)


def _game_args(p):
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--levels", type=int, default=6)
    p.add_argument("--difficulty", type=int, default=2)
    p.add_argument("--family", default="gridworld")
    p.add_argument("--no-shuffle", action="store_true")


def cmd_gen(a) -> int:
    g = make_game(_spec(a))
    print(json.dumps(g.describe(), indent=2))
    return 0


def _build_one(args: tuple[int, int, int]) -> dict | None:
    seed, levels, d = args
    try:
        return make_game(GameSpec(seed=seed, n_levels=levels, difficulty=d)).to_dict()
    except Exception as e:  # noqa: BLE001  a rare unbuildable seed is skipped, not fatal
        print(f"  skip seed {seed} d{d}: {e}", file=sys.stderr)
        return None


def cmd_collection(a) -> int:
    """Build a frozen collection: seeds start..start+n-1, difficulties cycled. Parallel with
    --workers; output order is by seed regardless of worker count (deterministic file)."""
    from concurrent.futures import ProcessPoolExecutor
    diffs = [int(x) for x in a.difficulties.split(",")]
    jobs = [(a.seed_start + i, a.levels, diffs[i % len(diffs)]) for i in range(a.n)]
    t0 = time.time()
    if a.workers > 1:
        with ProcessPoolExecutor(a.workers) as ex:
            built = list(ex.map(_build_one, jobs, chunksize=4))
    else:
        built = [_build_one(j) for j in jobs]
    games = [g for g in built if g is not None]
    from . import splits
    for g in games:
        g["holdout"] = splits.holdout_tag(g)
    if a.split == "train":
        n0 = len(games)
        games = [g for g in games if splits.is_train_ok(g)]
        print(f"  train hold-out filter: kept {len(games)}/{n0}", file=sys.stderr)
    if a.limit:
        games = games[:a.limit]
    for g in games[:10]:
        print(f"  {g['game_id']}", file=sys.stderr)
    out = {"name": a.name, "engine_version": ENGINE_VERSION,
           "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "split": a.split, "frozen": a.frozen, "holdout": splits.holdout_doc(),
           "games": games}
    path = Path(a.out) if a.out else collection_path(a.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {path} ({len(games)}/{len(jobs)} games, {time.time() - t0:.1f}s)", file=sys.stderr)
    return 0


def _print_frame(frame: list[str]) -> None:
    for row in frame:
        print(row.replace("0", "."))


def cmd_play(a) -> int:
    g = make_game(_spec(a))
    keys = {"w": Action.ACTION1, "s": Action.ACTION2, "a": Action.ACTION3, "d": Action.ACTION4,
            "r": Action.RESET, " ": Action.ACTION5, "e": Action.ACTION5}
    frame = g.reset()
    while True:
        _print_frame(frame)
        print(json.dumps(g.truth()))
        try:
            line = input("wasd/r/e, q quit > ")
        except EOFError:
            return 0
        for ch in line.lower() or " ":
            if ch == "q":
                return 0
            if ch in keys:
                frame = g.step(keys[ch])


def cmd_render(a) -> int:
    """Contact sheet: start frame of every level, then the final WIN frame."""
    g = make_game(_spec(a))
    frames = []
    for lv_path in [lv.optimal_path for lv in g.levels]:
        frames.append(g.frame())
        for act in lv_path:
            g.step(act)
    frames.append(g.frame())
    write_png(a.out, contact_sheet(frames, cols=a.cols))
    if a.frame_out:
        write_png(a.frame_out, frame_png(frames[0]))
    print(f"wrote {a.out} ({g.game_id})")
    return 0


def verify_game(gd: dict) -> list[str]:
    errs = []
    g = Game.from_dict(gd)
    if g.game_id != g._make_id():
        errs.append("game_id does not match content hash")
    if gd["engine_version"] == ENGINE_VERSION:
        regen = make_game(GameSpec(**gd["spec"]))
        if regen.game_id != g.game_id:
            errs.append("not reproducible from spec with this engine version")
    g.reset()
    for i, lv in enumerate(g.levels):
        if not lv.optimal_path:
            errs.append(f"level {i + 1}: no optimal path")
            continue
        if len(lv.optimal_path) > lv.move_budget:
            errs.append(f"level {i + 1}: optimal path exceeds budget")
        for act in lv.optimal_path:
            g.step(act)
        if g.idx != i + 1:
            errs.append(f"level {i + 1}: optimal path does not win")
            break
    if not errs and g.status != "WIN":
        errs.append("game not won after all optimal paths")
    return errs


def cmd_verify(a) -> int:
    col = load_collection(a.collection)
    bad = 0
    for gd in col["games"]:
        errs = verify_game(gd)
        if errs:
            bad += 1
            print(f"FAIL {gd['game_id']}: {'; '.join(errs)}")
    n = len(col["games"])
    print(f"{n - bad}/{n} games ok ({col.get('name')}, engine {col.get('engine_version')})")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m engine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("gen", help="generate one game, print describe() JSON"); _game_args(p)
    p.set_defaults(fn=cmd_gen)
    p = sub.add_parser("collection", help="build a frozen collection file")
    p.add_argument("name"); p.add_argument("--n", type=int, default=10)
    p.add_argument("--seed-start", type=int, default=1000)
    p.add_argument("--levels", type=int, default=6)
    p.add_argument("--difficulties", default="1,2,3")
    p.add_argument("--split", default="dev"); p.add_argument("--out")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--limit", type=int, default=0, help="keep at most N games after filtering")
    p.add_argument("--frozen", action="store_true", help="mark the collection frozen")
    p.set_defaults(fn=cmd_collection)
    p = sub.add_parser("play", help="play in the terminal"); _game_args(p); p.set_defaults(fn=cmd_play)
    p = sub.add_parser("render", help="PNG contact sheet of a game"); _game_args(p)
    p.add_argument("--out", default="sheet.png"); p.add_argument("--frame-out")
    p.add_argument("--cols", type=int, default=4)
    p.set_defaults(fn=cmd_render)
    p = sub.add_parser("verify", help="verify a collection"); p.add_argument("collection")
    p.set_defaults(fn=cmd_verify)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
