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


def _build_one(args: tuple) -> dict | None:
    seed, levels, d, *rest = args  # optional: family (gridforce), rule pool (eval-v4)
    fam = rest[0] if rest else "gridworld"
    pool = rest[1] if len(rest) > 1 else None
    view = rest[2] if len(rest) > 2 else None
    rules = None
    if pool:  # this game's rules: the pool in a per-seed order (the planner takes new rules in list order)
        from .core.rng import rng_for
        rules = list(pool)
        rng_for("rule-pool", seed, d, ",".join(pool)).shuffle(rules)
    try:
        g = make_game(GameSpec(family=fam, seed=seed, n_levels=levels, difficulty=d, rules=rules, view=view or None))
        if view and "fog" in view and any(r == "hole" for r in g.skin):
            raise ValueError("fog colour is the cracked_floor hole colour: leave cracked_floor out of fog games")
        return g.to_dict()
    except Exception as e:  # noqa: BLE001  a rare unbuildable seed is skipped, not fatal
        print(f"  skip seed {seed} d{d}: {e}", file=sys.stderr)
        return None


def cmd_collection(a) -> int:
    """Build a frozen collection: seeds start..start+n-1, difficulties cycled. Parallel with
    --workers; output order is by seed regardless of worker count (deterministic file)."""
    from concurrent.futures import ProcessPoolExecutor
    diffs = [int(x) for x in a.difficulties.split(",")]
    pool = tuple(r.strip() for r in a.rule_pool.split(",") if r.strip()) if a.rule_pool else None
    jobs = [(a.seed_start + i, a.levels, diffs[i % len(diffs)], a.family, pool, a.view) for i in range(a.n)]
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


def cmd_tasks(a) -> int:
    """Auxiliary verifiable tasks for post-training, as chat JSONL."""
    from .tasks import DEFAULT_ALL, write_jsonl
    names = list(DEFAULT_ALL) if a.task == "all" else a.task.split(",")
    if a.collection:  # build tasks from another train collection (e.g. train-v3b, gridbranch)
        from .tasks import common
        common.SOURCE = a.collection
    t0 = time.time()
    counts = write_jsonl(a.out, names, a.n, a.seed)
    print(f"wrote {a.out}: {counts} ({time.time() - t0:.1f}s)", file=sys.stderr)
    return 0


def cmd_rs(a) -> int:
    """Rejection sampling: pick train-v1 games for the sweep, or convert recorded runs to SFT JSONL."""
    from .tasks import rejection
    if a.rs_cmd == "games":
        ids = rejection.pick_games(a.n, a.seed)
        nl = chr(10)
        print(nl.join(ids) if a.format == "ids" else "games:" + nl + nl.join(f"  - {i}" for i in ids))
        return 0
    st = rejection.convert(a.runs, a.out, a.min_eff, a.models.split(",") if a.models else None,
                           drop_bumps=not a.keep_bumps)
    print(f"wrote {a.out}: {dict(st)}", file=sys.stderr)
    return 0


def cmd_probe(a) -> int:
    """Transfer-probe collection. Fresh seeds (eval range, never trained) whose levels
    use rule combinations that appear in no level of train-v1 or eval-v1. Tiers 1-2 only, so it
    measures near transfer (new combinations of known rules), not unseen rules (that is eval-v2).
    Each game lists its novel levels in `probe_levels` (1-based)."""
    from concurrent.futures import ProcessPoolExecutor
    from .core.game import load_collection
    from . import splits
    seen = {frozenset(lv["rules"]) for c in ("train-v1", "eval-v1")
            for g in load_collection(c)["games"] for lv in g["levels"]}
    jobs = [(a.seed_start + i, a.levels, 2 + i % 2) for i in range(a.candidates)]
    t0 = time.time()
    with ProcessPoolExecutor(a.workers) as ex:
        built = [g for g in ex.map(_build_one, jobs, chunksize=4) if g]
    scored = []
    for g in built:
        nov = [i + 1 for i, lv in enumerate(g["levels"]) if frozenset(lv["rules"]) not in seen]
        if nov:
            g["probe_levels"] = nov
            g["holdout"] = splits.holdout_tag(g)
            scored.append((-len(nov), g["spec"]["seed"], g))
    games = [g for _, _, g in sorted(scored, key=lambda x: x[:2])[:a.n]]
    games.sort(key=lambda g: g["spec"]["seed"])
    out = {"name": a.name, "engine_version": ENGINE_VERSION,
           "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "split": "test", "frozen": True, "holdout": splits.holdout_doc(),
           "probe": {"novel_vs": ["train-v1", "eval-v1"], "seed_start": a.seed_start,
                     "candidates": a.candidates},
           "games": games}
    path = collection_path(a.name)
    path.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    nl = sum(len(g["probe_levels"]) for g in games)
    print(f"wrote {path}: {len(games)} games, {nl} novel levels, from {len(built)} candidates "
          f"({time.time() - t0:.1f}s)", file=sys.stderr)
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


def verify_game(gd: dict, regen: bool = True) -> list[str]:
    errs = []
    g = Game.from_dict(gd)
    if g.game_id != g._make_id():
        errs.append("game_id does not match content hash")
    if regen and gd["engine_version"] == ENGINE_VERSION:
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
        errs = verify_game(gd, regen=not a.quick)
        if errs:
            bad += 1
            print(f"FAIL {gd['game_id']}: {'; '.join(errs)}")
    n = len(col["games"])
    print(f"{n - bad}/{n} games ok ({col.get('name')}, engine {col.get('engine_version')})")
    return 1 if bad else 0


def _fuzz_one(args: tuple[int, int]) -> str | None:
    """None if ok, else an error string."""
    from .core.rng import rng_for
    seed, d = args
    try:
        g = make_game(GameSpec(seed=seed, difficulty=d))
        errs = verify_game(g.to_dict())
        if errs:
            return f"seed {seed} d{d}: {'; '.join(errs)}"
        rng = rng_for("fuzz-player", seed)
        acts = [a.value for a in Action] + ["up", 3, 0]
        g.reset()
        for _ in range(400):
            f = g.step(rng.choice(acts))
            if len(f) != 64 or any(len(r) != 64 for r in f):
                return f"seed {seed} d{d}: bad frame"
        return None
    except Exception as e:  # noqa: BLE001
        return f"seed {seed} d{d}: {type(e).__name__}: {e}"


def cmd_fuzz(a) -> int:
    from concurrent.futures import ProcessPoolExecutor
    jobs = [(a.seed_start + i, 1 + i % 4) for i in range(a.n)]
    t0 = time.time()
    with ProcessPoolExecutor(a.workers) as ex:
        res = list(ex.map(_fuzz_one, jobs, chunksize=8))
    bad = [r for r in res if r]
    for r in bad[:50]:
        print("FAIL", r)
    print(f"fuzz: {len(jobs) - len(bad)}/{len(jobs)} ok in {time.time() - t0:.0f}s")
    return 1 if bad else 0


def cmd_rulesheet(a) -> int:
    """One teaching level per rule (start frame + frame after the rule first fires)."""
    from . import components as comps
    from .generator import generate_level
    from .generator.skin import make_skin
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    frames, names = [], []
    for r in sorted(n for n, c in comps.REGISTRY.items() if not c.always_on):
        req = comps.REGISTRY[r].requires
        rules = tuple(sorted({r, req[0]})) if req else (r,)
        lv = generate_level(a.seed, "gridworld", 2, 1, rules, r)
        g = Game(GameSpec(seed=a.seed), [lv], make_skin(a.seed, "gridworld", False, list(rules)))
        seq = [g.frame()]
        for act in lv.optimal_path:
            seq.append(g.step(act))
        frames += [seq[0], seq[len(seq) // 2]]
        names.append(r)
        write_png(out / f"{r}.png", contact_sheet([seq[0], seq[len(seq) // 2], seq[-2]], cols=3))
        if a.gif:
            _gif(seq, out / f"{r}.gif")
    write_png(out / "all_rules.png", contact_sheet(frames, cols=6, scale=3))
    print(f"wrote {len(names)} rule sheets to {out}: {', '.join(names)}")
    return 0


def _gif(frames: list[list[str]], path: Path, scale: int = 6, ms: int = 180) -> None:
    try:
        from PIL import Image
    except ImportError:
        print("  (pip install pillow for GIFs)", file=sys.stderr)
        return
    from .render.palette import load_palette
    from .render.png import frame_pixels
    pal = [c for rgb in load_palette() for c in rgb]
    imgs = []
    for f in frames:
        im = Image.new("P", (64, 64))
        im.putpalette(pal)
        im.putdata([v for row in frame_pixels(f) for v in row])
        imgs.append(im.resize((64 * scale, 64 * scale), Image.NEAREST))
    imgs[0].save(path, save_all=True, append_images=imgs[1:], duration=ms, loop=0)


def cmd_gif(a) -> int:
    """Animated GIF of the optimal play-through of one game (all levels)."""
    from .core.game import load_game
    g = load_game(a.collection, a.game_id) if a.game_id else make_game(_spec(a))
    seq = [g.reset()]
    for lv in g.levels:
        for act in lv.optimal_path:
            seq.append(g.step(act))
    _gif(seq, Path(a.out))
    print(f"wrote {a.out} ({len(seq)} frames, {g.game_id})")
    return 0


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
    p.add_argument("--family", default="gridworld", help="gridforce = forced-interaction generator")
    p.add_argument("--rule-pool", default="", help="comma list: each game draws its rules from this pool, "
                   "in a per-seed order (eval-v4); default = the curriculum's pool")
    p.add_argument("--view", default="", help="what the player sees, rules untouched (eval-v6): "
                   "comma list of fog<r>, glimpse, recolor (generator/view.py)")
    p.set_defaults(fn=cmd_collection)
    p = sub.add_parser("play", help="play in the terminal"); _game_args(p); p.set_defaults(fn=cmd_play)
    p = sub.add_parser("render", help="PNG contact sheet of a game"); _game_args(p)
    p.add_argument("--out", default="sheet.png"); p.add_argument("--frame-out")
    p.add_argument("--cols", type=int, default=4)
    p.set_defaults(fn=cmd_render)
    p = sub.add_parser("verify", help="verify a collection"); p.add_argument("collection")
    p.add_argument("--quick", action="store_true", help="skip regenerate-from-spec check")
    p.set_defaults(fn=cmd_verify)
    p = sub.add_parser("rulesheet", help="PNG (+GIF) of a teaching level per rule")
    p.add_argument("--out-dir", default="rules/img"); p.add_argument("--seed", type=int, default=7)
    p.add_argument("--gif", action="store_true")
    p.set_defaults(fn=cmd_rulesheet)
    p = sub.add_parser("gif", help="GIF of the optimal play-through"); _game_args(p)
    p.add_argument("--collection", default="dev"); p.add_argument("--game-id")
    p.add_argument("--out", default="game.gif")
    p.set_defaults(fn=cmd_gif)
    p = sub.add_parser("fuzz", help="generate+verify+random-play many seeds")
    p.add_argument("--n", type=int, default=1000); p.add_argument("--seed-start", type=int, default=500000)
    p.add_argument("--workers", type=int, default=8)
    p.set_defaults(fn=cmd_fuzz)
    p = sub.add_parser("tasks", help="auxiliary verifiable tasks (JSONL) for post-training")
    p.add_argument("--task", default="all", help="all or comma list: next_frame,rule_effect,min_moves,full_plan")
    p.add_argument("--n", type=int, default=1000, help="samples per task")
    p.add_argument("--seed", type=int, default=0); p.add_argument("--out", required=True)
    p.add_argument("--collection", help="train collection to draw games from (default train-v1)")
    p.set_defaults(fn=cmd_tasks)
    p = sub.add_parser("rs", help="rejection sampling: pick train games / convert runs to SFT data")
    rs = p.add_subparsers(dest="rs_cmd", required=True)
    q = rs.add_parser("games", help="train-v1 game ids for the sampling sweep")
    q.add_argument("--n", type=int, default=60); q.add_argument("--seed", type=int, default=0)
    q.add_argument("--format", choices=["ids", "yaml"], default="yaml")
    q = rs.add_parser("convert", help="runs dir or /api/runs/export tar.gz -> h1 SFT JSONL")
    q.add_argument("--runs", required=True); q.add_argument("--out", required=True)
    q.add_argument("--min-eff", type=float, default=0.5, help="keep solved levels with optimal/actions >= this")
    q.add_argument("--models", help="comma list of model_ids to keep (default: all models)")
    q.add_argument("--keep-bumps", action="store_true", help="keep turns whose move bumped (default: drop)")
    p.set_defaults(fn=cmd_rs)
    p = sub.add_parser("probe", help="transfer-probe collection (novel rule combinations)")
    p.add_argument("--name", default="probe-v1"); p.add_argument("--n", type=int, default=30)
    p.add_argument("--seed-start", type=int, default=980000)
    p.add_argument("--candidates", type=int, default=600)
    p.add_argument("--levels", type=int, default=6); p.add_argument("--workers", type=int, default=12)
    p.set_defaults(fn=cmd_probe)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
