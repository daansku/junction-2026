"""CLI entry point: python -m analysis <sync|aggregate|rules|insights|explain|build|check-claims>."""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

from .aggregate import aggregate_runs
from .claim_check import check_claims, validate_against_schema
from .explain import build_explanations, build_failure_packets, estimate_judge_cost, make_arena_judge
from .insights import generate_auto_proposals, synthesize_insights
from .loader import default_data_dir, find_repo_root, load_collections, load_models, load_runs
from .rule_discovery import analyze_rules
from .sync import sync_runs


def _synthesize_fixture_baselines(repo_root: Path) -> list[dict[str, Any]]:
    """Compute real deterministic baseline traces (optimal, random, noop, stop_early) over fixture games."""
    games_dir = repo_root / "data" / "fixtures" / "games"
    if not games_dir.exists():
        return []

    # Try importing FakeGame for exact step-by-step random/stop_early traces on the fixture games
    fake_engine = None
    try:
        sys.path.insert(0, str(repo_root / "server" / "src"))
        from server import fake_engine as _fe  # type: ignore

        fake_engine = _fe
    except Exception:
        fake_engine = None

    extra: list[dict[str, Any]] = []
    game_files = sorted(games_dir.glob("*.json"))
    for gf in game_files:
        desc = json.loads(gf.read_text(encoding="utf-8"))
        gid = desc["game_id"]
        levels = desc.get("levels") or []
        n_levels = len(levels)

        # 1) optimal: exact optimal_path replay
        if fake_engine is not None:
            spec = fake_engine.spec_from_game_id(gid)
            for bname in ("optimal", "noop", "stop_early", "random"):
                g = fake_engine.FakeGame(spec)
                steps = [{
                    "i": 0, "t_ms": 0, "action": None, "frame": g.frame(), "truth": g.truth(),
                    "reasoning": None, "hypothesis": None, "belief": None,
                    "usage": {"in": 0, "out": 0, "cost_usd": 0.0}, "latency_ms": None,
                }]
                idx = 0
                if bname == "optimal":
                    for lv in levels:
                        for act in lv.get("optimal_path") or []:
                            idx += 1
                            g.step(act)
                            steps.append({
                                "i": idx, "t_ms": idx * 10, "action": act, "frame": g.frame(), "truth": g.truth(),
                                "reasoning": None, "hypothesis": None, "belief": None,
                                "usage": {"in": 0, "out": 0, "cost_usd": 0.0}, "latency_ms": None,
                            })
                    outcome = "WIN" if g.truth()["state"] == "WIN" else "BUDGET"
                elif bname == "noop":
                    outcome = "ABORTED"
                elif bname == "stop_early":
                    rng = random.Random(0)
                    for _ in range(5):
                        idx += 1
                        act = rng.choice(["ACTION1", "ACTION2", "ACTION3", "ACTION4"])
                        g.step(act)
                        steps.append({
                            "i": idx, "t_ms": idx * 10, "action": act, "frame": g.frame(), "truth": g.truth(),
                            "reasoning": None, "hypothesis": None, "belief": None,
                            "usage": {"in": 0, "out": 0, "cost_usd": 0.0}, "latency_ms": None,
                        })
                    outcome = "ABORTED"
                else:  # random
                    rng = random.Random(42)
                    while g.truth()["state"] != "WIN" and idx < 200:
                        idx += 1
                        act = "RESET" if g.truth()["state"] == "GAME_OVER" else rng.choice(["ACTION1", "ACTION2", "ACTION3", "ACTION4"])
                        g.step(act)
                        steps.append({
                            "i": idx, "t_ms": idx * 10, "action": act, "frame": g.frame(), "truth": g.truth(),
                            "reasoning": None, "hypothesis": None, "belief": None,
                            "usage": {"in": 0, "out": 0, "cost_usd": 0.0}, "latency_ms": None,
                        })
                    outcome = "WIN" if g.truth()["state"] == "WIN" else "BUDGET"

                ft = g.truth()
                done = (ft["level"] - 1) + (1 if ft["state"] == "WIN" else 0)
                extra.append({
                    "meta": {
                        "run_id": f"fixture-baseline-{bname}-{gid[-8:]}",
                        "run_key": f"fixture-{bname}-{gid}",
                        "game_id": gid,
                        "collection": "dev",
                        "split": "dev",
                        "player": {"kind": "baseline", "name": bname, "model_id": f"baseline:{bname}"},
                        "harness_version": "h1",
                        "engine_version": desc.get("engine_version", "fake-0.1"),
                        "started_at": "2026-11-14T04:30:00Z",
                        "ended_at": "2026-11-14T04:30:01Z",
                        "outcome": outcome,
                        "levels_completed": done,
                        "levels_total": n_levels,
                        "actions": idx,
                        "resets": ft["resets"],
                        "tokens_in": 0,
                        "tokens_out": 0,
                        "cost_usd": 0.0,
                        "wall_s": round(idx * 0.01, 3),
                    },
                    "steps": steps,
                })
    return extra


def _resolve_runs_and_out(args: argparse.Namespace, repo_root: Path) -> tuple[Path, Path, bool]:
    use_fixtures = bool(getattr(args, "fixtures", False))
    runs_arg = getattr(args, "runs", None) or getattr(args, "data_dir", None)
    out_arg = getattr(args, "out", None) or getattr(args, "out_dir", None)

    if use_fixtures:
        runs_dir = Path(runs_arg) if runs_arg else (repo_root / "data" / "fixtures" / "runs")
        out_dir = Path(out_arg) if out_arg else (repo_root / "data" / "fixtures" / "derived")
        return runs_dir, out_dir, True

    if runs_arg:
        runs_dir = Path(runs_arg).expanduser()
        # Allow passing DATA_DIR (parent of runs/) or runs/ directly
        if runs_dir.name != "runs" and (runs_dir / "runs").is_dir():
            runs_dir = runs_dir / "runs"
    else:
        cand = default_data_dir() / "runs"
        if cand.exists() and any(cand.glob("*/meta.json")):
            runs_dir = cand
        else:
            runs_dir = repo_root / "data" / "fixtures" / "runs"

    out_dir = Path(out_arg).expanduser() if out_arg else (repo_root / "data" / "derived")
    return runs_dir, out_dir, False


def build_all(
    runs_dir: Path,
    out_dir: Path,
    repo_root: Path | None = None,
    with_fixture_baselines: bool = False,
    write_proposals: bool = False,
) -> dict[str, Any]:
    root = repo_root or find_repo_root()
    runs = load_runs(runs_dir)
    if with_fixture_baselines:
        existing_ids = {r["meta"].get("run_id") for r in runs}
        for b_run in _synthesize_fixture_baselines(root):
            if b_run["meta"]["run_id"] not in existing_ids:
                runs.append(b_run)

    models = load_models(root)
    games = load_collections(root)

    leaderboard = aggregate_runs(runs, models_registry=models, game_descs=games)
    rules_data = analyze_rules(runs, models_registry=models, game_descs=games)
    insights = synthesize_insights(leaderboard, rules_data, runs=runs)
    explanations = build_explanations(runs, game_descs=games, repo_root=root)

    # Preserve any prior LLM-judge entries on incremental rebuilds so `analysis build` never clobbers A3's judge run
    existing_exp_path = out_dir / "explanations.json"
    if existing_exp_path.exists():
        try:
            prev_exp = json.loads(existing_exp_path.read_text(encoding="utf-8"))
            llm_by_key = {
                (e.get("run_id"), e.get("level")): e
                for e in (prev_exp.get("explanations") or [])
                if e.get("judge_model") and e.get("judge_model") != "trace-auditor-v1"
            }
            if llm_by_key:
                merged = [llm_by_key.get((e["run_id"], e["level"]), e) for e in explanations["explanations"]]
                models_used = sorted({str(e.get("judge_model") or "trace-auditor-v1") for e in merged})
                explanations["explanations"] = merged
                explanations["judge_model"] = ", ".join(models_used)
        except Exception:
            pass

    schema_path = root / "contracts" / "derived.schema.json"
    for payload in (leaderboard, rules_data, insights, explanations):
        validate_against_schema(payload, schema_path)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "leaderboard.json").write_text(json.dumps(leaderboard, indent=2) + "\n", encoding="utf-8")
    (out_dir / "rules.json").write_text(json.dumps(rules_data, indent=2) + "\n", encoding="utf-8")
    (out_dir / "insights.json").write_text(json.dumps(insights, indent=2) + "\n", encoding="utf-8")
    (out_dir / "explanations.json").write_text(json.dumps(explanations, indent=2) + "\n", encoding="utf-8")

    proposals_written: list[str] = []
    if write_proposals:
        paths = generate_auto_proposals(rules_data, leaderboard, root / "rules" / "proposals")
        proposals_written = [str(p) for p in paths]

    return {
        "runs_loaded": len(runs),
        "out_dir": str(out_dir),
        "leaderboard_rows": len(leaderboard["rows"]),
        "rule_cells": len(rules_data["cells"]),
        "insights": len(insights["insights"]),
        "explanations": len(explanations["explanations"]),
        "proposals_written": proposals_written,
    }


def _add_common_io_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--runs", help="Path to runs directory (e.g. ~/junction-data/runs)")
    p.add_argument("--data-dir", help="Alias for DATA_DIR containing runs/")
    p.add_argument("--out", help="Output directory for derived JSONs (default: data/derived)")
    p.add_argument("--out-dir", help="Alias for --out")
    p.add_argument("--fixtures", action="store_true", help="Build from data/fixtures/runs -> data/fixtures/derived")
    p.add_argument("--with-fixture-baselines", action="store_true", help="Include deterministic baselines on fixture games")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m analysis", description="LENS analysis & derived build CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sync = sub.add_parser("sync", help="Mirror finished runs from shared server /api/runs/export")
    p_sync.add_argument("--api", help="Shared server base URL (defaults to API_URL or coordination/API_URL)")
    p_sync.add_argument("--data-dir", help="Local data directory (default: DATA_DIR or ~/junction-data)")
    p_sync.add_argument("--since", help="ISO-8601 timestamp to fetch incrementally")

    p_agg = sub.add_parser("aggregate", help="Build leaderboard.json")
    _add_common_io_args(p_agg)

    p_rules = sub.add_parser("rules", help="Build rules.json")
    _add_common_io_args(p_rules)

    p_ins = sub.add_parser("insights", help="Build insights.json")
    _add_common_io_args(p_ins)
    p_ins.add_argument("--write-proposals", action="store_true", help="Write rules/proposals/auto-*.md")

    p_exp = sub.add_parser("explain", help="Build explanations.json (or estimate judge-LLM cost)")
    _add_common_io_args(p_exp)
    p_exp.add_argument("--estimate", action="store_true", help="Print judge token & USD cost estimate and exit")
    p_exp.add_argument("--judge-cmd", help="Shell command accepting JSON {system, prompt, max_tokens} on stdin")
    p_exp.add_argument("--judge-arena", action="store_true", help="Use arena.judge.complete if available")

    p_build = sub.add_parser("build", help="Build leaderboard.json, rules.json, insights.json, and explanations.json")
    _add_common_io_args(p_build)
    p_build.add_argument("--write-proposals", action="store_true", help="Write rules/proposals/auto-*.md")

    p_check = sub.add_parser("check-claims", help="Validate derived JSON files against contracts/derived.schema.json")
    p_check.add_argument("--derived", help="Derived directory to verify (default: data/derived or data/fixtures/derived)")

    args = parser.parse_args(argv)
    root = find_repo_root()

    if args.cmd == "sync":
        dd = Path(args.data_dir).expanduser() if args.data_dir else None
        res = sync_runs(api_url=args.api, data_dir=dd, since=args.since)
        print(json.dumps(res, indent=2))
        return 0

    if args.cmd == "check-claims":
        target = Path(args.derived) if args.derived else (
            root / "data" / "derived" if (root / "data" / "derived" / "leaderboard.json").exists()
            else root / "data" / "fixtures" / "derived"
        )
        res = check_claims(target, repo_root=root)
        print(json.dumps(res, indent=2))
        return 0 if res["ok"] else 1

    runs_dir, out_dir, is_fixtures = _resolve_runs_and_out(args, root)
    with_baselines = bool(args.with_fixture_baselines or (is_fixtures and not args.runs))

    if args.cmd == "build":
        res = build_all(
            runs_dir,
            out_dir,
            repo_root=root,
            with_fixture_baselines=with_baselines,
            write_proposals=bool(args.write_proposals),
        )
        print(json.dumps(res, indent=2))
        return 0

    runs = load_runs(runs_dir)
    if with_baselines:
        runs.extend(_synthesize_fixture_baselines(root))
    models = load_models(root)
    games = load_collections(root)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.cmd == "aggregate":
        lb = aggregate_runs(runs, models_registry=models, game_descs=games)
        validate_against_schema(lb, root / "contracts" / "derived.schema.json")
        (out_dir / "leaderboard.json").write_text(json.dumps(lb, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"rows": len(lb["rows"]), "out": str(out_dir / "leaderboard.json")}, indent=2))
        return 0

    if args.cmd == "rules":
        rd = analyze_rules(runs, models_registry=models, game_descs=games)
        validate_against_schema(rd, root / "contracts" / "derived.schema.json")
        (out_dir / "rules.json").write_text(json.dumps(rd, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"cells": len(rd["cells"]), "out": str(out_dir / "rules.json")}, indent=2))
        return 0

    if args.cmd == "insights":
        lb = aggregate_runs(runs, models_registry=models, game_descs=games)
        rd = analyze_rules(runs, models_registry=models, game_descs=games)
        ins = synthesize_insights(lb, rd, runs=runs)
        validate_against_schema(ins, root / "contracts" / "derived.schema.json")
        (out_dir / "insights.json").write_text(json.dumps(ins, indent=2) + "\n", encoding="utf-8")
        written: list[str] = []
        if args.write_proposals:
            written = [str(p) for p in generate_auto_proposals(rd, lb, root / "rules" / "proposals")]
        print(json.dumps({"insights": len(ins["insights"]), "proposals": written, "out": str(out_dir / "insights.json")}, indent=2))
        return 0

    if args.cmd == "explain":
        packets = build_failure_packets(runs, game_descs=games, repo_root=root)
        est = estimate_judge_cost(packets)
        if args.estimate:
            print(json.dumps(est, indent=2))
            return 0
        judge_fn = None
        if args.judge_arena:
            arena_src = root / "arena" / "src"
            if arena_src.exists() and str(arena_src) not in sys.path:
                sys.path.insert(0, str(arena_src))
            from arena import judge as _arena_judge  # type: ignore

            judge_fn = make_arena_judge(_arena_judge.complete)
        exp = build_explanations(
            runs,
            game_descs=games,
            repo_root=root,
            judge_fn=judge_fn,
            judge_cmd=args.judge_cmd,
        )
        validate_against_schema(exp, root / "contracts" / "derived.schema.json")
        (out_dir / "explanations.json").write_text(json.dumps(exp, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({**est, "written": len(exp["explanations"]), "judge_model": exp["judge_model"], "out": str(out_dir / "explanations.json")}, indent=2))
        return 0

    return 1
