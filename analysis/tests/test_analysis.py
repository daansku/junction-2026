"""Unit and integration tests for the LENS analysis package."""
from __future__ import annotations

import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_SRC = REPO_ROOT / "analysis" / "src"
if str(ANALYSIS_SRC) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_SRC))

from analysis.aggregate import aggregate_runs  # noqa: E402
from analysis.claim_check import check_claims, validate_against_schema  # noqa: E402
from analysis.cli import main as cli_main  # noqa: E402
from analysis.compare import build_comparisons  # noqa: E402
from analysis.explain import build_explanations, build_failure_packets, estimate_judge_cost  # noqa: E402
from analysis.loader import (  # noqa: E402
    extract_level_segments,
    filter_benchmark_runs,
    load_collections,
    load_models,
    load_runs,
)
from analysis.rule_discovery import analyze_rules  # noqa: E402
from analysis.sync import _safe_extract_tar_bytes  # noqa: E402


def _make_step(
    i: int,
    action: str | None,
    *,
    level: int = 1,
    state: str = "PLAYING",
    events: list[str] | None = None,
    optimal_moves: int = 4,
    frame_row6: str = "0" * 64,
    belief: str | None = None,
) -> dict:
    frame = ["0" * 64 for _ in range(64)]
    frame[6] = frame_row6
    return {
        "i": i,
        "t_ms": i * 25,
        "action": action,
        "frame": frame,
        "truth": {
            "level": level,
            "state": state,
            "events": list(events or []),
            "optimal_moves": optimal_moves,
            "move_budget": optimal_moves * 3,
            "active_rules": ["walls", "goal", "move_budget"],
            "new_rule": None if level == 1 else "walls",
        },
        "reasoning": None,
        "hypothesis": None,
        "belief": belief,
        "usage": {"in": 100, "out": 20, "cost_usd": 0.001},
        "latency_ms": 50 if action else None,
    }


def _make_run(run_id: str, player_id: str, kind: str, steps: list[dict], *, effort: str | None = None) -> dict:
    return {
        "meta": {
            "run_id": run_id,
            "game_id": "synthetic-game-0001",
            "collection": "dev",
            "levels_total": 1,
            "levels_completed": 1 if steps and steps[-1]["truth"]["state"] == "WIN" else 0,
            "outcome": "WIN" if steps and steps[-1]["truth"]["state"] == "WIN" else "ABORTED",
            "harness_version": "h1",
            "player": {
                "kind": kind,
                "id": player_id,
                "name": player_id,
                "effort": effort,
            },
        },
        "steps": steps,
    }


class AnalysisPipelineTests(unittest.TestCase):
    def test_fixture_run_0001_exact_attribution(self) -> None:
        runs = load_runs(REPO_ROOT / "data" / "fixtures" / "runs")
        self.assertEqual(len(runs), 1)
        run = runs[0]
        self.assertEqual(run["meta"]["run_id"], "fixture-run-0001")

        games = load_collections(REPO_ROOT)
        seg_info = extract_level_segments(run, games.get(run["meta"]["game_id"]))
        self.assertEqual(seg_info["levels_total"], 6)
        self.assertEqual(seg_info["levels_solved"], 2)

        segs = seg_info["segments"]
        self.assertTrue(segs[1]["solved"])
        self.assertAlmostEqual(segs[1]["level_score"], 5 / 7, places=6)
        self.assertTrue(segs[2]["solved"])
        self.assertEqual(segs[2]["resets"], 1)
        self.assertEqual(segs[2]["no_effect_actions"], 1)
        self.assertAlmostEqual(segs[2]["level_score"], 16 / 20, places=6)
        for lv in (3, 4, 5, 6):
            self.assertFalse(segs[lv]["solved"])
            self.assertEqual(segs[lv]["level_score"], 0.0)

        self.assertAlmostEqual(seg_info["game_score"], (5 / 7 + 16 / 20) / 6, places=6)

        lb = aggregate_runs(runs, models_registry=load_models(REPO_ROOT), game_descs=games)
        self.assertEqual(len(lb["rows"]), 1)
        row = lb["rows"][0]
        self.assertAlmostEqual(row["score"], 0.252381, places=6)
        self.assertEqual(row["belief_accuracy"], 1.0)
        self.assertAlmostEqual(row["no_effect_rate"], round(1 / 30, 4), places=4)

    def test_fixture_derived_matches_schema(self) -> None:
        derived_dir = REPO_ROOT / "data" / "fixtures" / "derived"
        schema_path = REPO_ROOT / "contracts" / "derived.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        for name in ("leaderboard", "rules", "insights"):
            payload = json.loads((derived_dir / f"{name}.json").read_text(encoding="utf-8"))
            validate_against_schema(payload, schema_path)
            sub_schema = {
                "$schema": schema["$schema"],
                "$defs": schema["$defs"],
                **schema["$defs"][name],
            }
            jsonschema.validate(instance=payload, schema=sub_schema)

        res = check_claims(derived_dir, repo_root=REPO_ROOT)
        self.assertTrue(res["ok"], msg=f"check_claims failed: {res['errors']}")
        self.assertEqual(res["errors"], [])

    def test_reward_integrity_and_reset_penalty(self) -> None:
        noop_run = _make_run(
            "syn-noop",
            "baseline:noop",
            "baseline",
            [_make_step(0, None)],
        )
        stop_early_run = _make_run(
            "syn-stop",
            "baseline:stop_early",
            "baseline",
            [
                _make_step(0, None),
                _make_step(1, "ACTION1", frame_row6="1" + "0" * 63),
                _make_step(2, "ACTION2", frame_row6="2" + "0" * 63),
            ],
        )
        optimal_steps = [_make_step(0, None)]
        for i in range(1, 5):
            is_last = i == 4
            optimal_steps.append(
                _make_step(
                    i,
                    "ACTION4",
                    state="WIN" if is_last else "PLAYING",
                    events=["game_won"] if is_last else [],
                    frame_row6=f"{i}" + "0" * 63,
                )
            )
        optimal_run = _make_run("syn-opt", "baseline:optimal", "baseline", optimal_steps)

        reset_steps = [
            _make_step(0, None),
            _make_step(1, "ACTION1", frame_row6="1" + "0" * 63),
            _make_step(2, "RESET", events=["reset"], frame_row6="0" * 64),
        ]
        for i in range(3, 7):
            is_last = i == 6
            reset_steps.append(
                _make_step(
                    i,
                    "ACTION4",
                    state="WIN" if is_last else "PLAYING",
                    events=["game_won"] if is_last else [],
                    frame_row6=f"{i}" + "0" * 63,
                )
            )
        reset_model = _make_run("syn-model-reset", "m-reset", "model", reset_steps, effort="low")
        clean_model = _make_run("syn-model-clean", "m-reset", "model", optimal_steps, effort="high")

        lb = aggregate_runs(
            [noop_run, stop_early_run, optimal_run, reset_model, clean_model],
            models_registry={},
            game_descs={},
        )
        by_key = {(r["player_id"], r["effort"]): r for r in lb["rows"]}
        self.assertEqual(by_key[("noop", None)]["score"], 0.0)
        self.assertEqual(by_key[("stop_early", None)]["score"], 0.0)
        self.assertEqual(by_key[("optimal", None)]["score"], 1.0)

        reset_score = by_key[("m-reset", "low")]["score"]
        clean_score = by_key[("m-reset", "high")]["score"]
        self.assertAlmostEqual(reset_score, 4 / 6, places=6)
        self.assertEqual(clean_score, 1.0)
        self.assertLess(reset_score, clean_score)

        comp = build_comparisons(lb)
        self.assertTrue(comp["reward_integrity"]["passed"])
        self.assertEqual(len(comp["effort_ablations"]), 1)
        self.assertEqual([p["effort"] for p in comp["effort_ablations"][0]["points"]], ["low", "high"])

    def test_sync_tar_extraction_and_traversal_guard(self) -> None:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            payload = b'{"run_id": "run-1"}\n'
            info = tarfile.TarInfo("run-1/meta.json")
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
        with tempfile.TemporaryDirectory() as td:
            count = _safe_extract_tar_bytes(buf.getvalue(), Path(td))
            self.assertEqual(count, 1)
            self.assertTrue((Path(td) / "run-1" / "meta.json").exists())

        bad_buf = io.BytesIO()
        with tarfile.open(fileobj=bad_buf, mode="w:gz") as tar:
            info = tarfile.TarInfo("../escape.txt")
            info.size = 4
            tar.addfile(info, io.BytesIO(b"nope"))
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                _safe_extract_tar_bytes(bad_buf.getvalue(), Path(td))

    def test_cli_build_and_check_claims_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td) / "derived"
            rc = cli_main(
                [
                    "build",
                    "--runs",
                    str(REPO_ROOT / "data" / "fixtures" / "runs"),
                    "--out",
                    str(out_dir),
                    "--with-fixture-baselines",
                ]
            )
            self.assertEqual(rc, 0)
            self.assertEqual(cli_main(["check-claims", "--derived", str(out_dir)]), 0)

            # Corrupt noop score to verify check-claims catches reward integrity tampering
            lb_path = out_dir / "leaderboard.json"
            lb_data = json.loads(lb_path.read_text(encoding="utf-8"))
            for row in lb_data["rows"]:
                if row["player_id"] == "noop":
                    row["score"] = 0.25
            lb_path.write_text(json.dumps(lb_data, indent=2), encoding="utf-8")
            self.assertEqual(cli_main(["check-claims", "--derived", str(out_dir)]), 1)

    def test_run_hygiene_filtering(self) -> None:
        dev_games = json.loads((REPO_ROOT / "data" / "collections" / "dev.json").read_text(encoding="utf-8"))["games"]
        valid_gid = dev_games[0]["game_id"]

        def _custom_run(run_id: str, pid: str, kind: str, gid: str, outcome: str, end_reason: str | None = None) -> dict:
            r = _make_run(run_id, pid, kind, [_make_step(0, None)])
            r["meta"]["game_id"] = gid
            r["meta"]["outcome"] = outcome
            if end_reason:
                r["meta"]["end_reason"] = end_reason
            return r

        corpus = [
            _custom_run("r-anon", "anonymous", "human", valid_gid, "BUDGET"),
            _custom_run("r-smoke", "smoke-optimal", "baseline", valid_gid, "WIN"),
            _custom_run("r-idle", "nemotron-3-5-super-vl", "model", valid_gid, "ABORTED", "idle_timeout"),
            _custom_run("r-abort", "verda-kimi-k3-1-pro", "model", valid_gid, "ABORTED"),
            _custom_run("r-stale", "optimal", "baseline", "gridworld-s1000-d1-l6-stale020", "WIN"),
            _custom_run("r-noop", "baseline:noop", "baseline", valid_gid, "ABORTED"),
            _custom_run("r-stop", "baseline:stop_early", "baseline", valid_gid, "ABORTED"),
            _custom_run("r-valid-model", "verda-kimi-k3-1-pro", "model", valid_gid, "BUDGET"),
            _custom_run("r-valid-human", "judge-1", "human", valid_gid, "WIN"),
        ]
        cleaned = filter_benchmark_runs(corpus, REPO_ROOT)
        kept_ids = [r["meta"]["run_id"] for r in cleaned]
        self.assertEqual(kept_ids, ["r-noop", "r-stop", "r-valid-model", "r-valid-human"])

    def test_tier2_tier3_events_and_holdout_splits(self) -> None:
        steps = [_make_step(0, None, optimal_moves=2)]
        steps[0]["truth"]["active_rules"] = ["walls", "goal", "collect_all", "conveyors"]
        steps[0]["truth"]["new_rule"] = "collect_all"
        s1 = _make_step(1, "ACTION4", events=["collected", "conveyor:right"], optimal_moves=2, frame_row6="1" + "0" * 63)
        s1["truth"]["active_rules"] = ["walls", "goal", "collect_all", "conveyors"]
        s1["truth"]["new_rule"] = "collect_all"
        s2 = _make_step(2, "ACTION4", state="WIN", events=["level_complete", "game_won"], optimal_moves=2, frame_row6="2" + "0" * 63)
        s2["truth"]["active_rules"] = ["walls", "goal", "collect_all", "conveyors"]
        s2["truth"]["new_rule"] = "collect_all"
        steps.extend([s1, s2])

        run_seen = _make_run("r-seen", "verda-kimi-k3-1-pro", "model", steps)
        run_seen["meta"]["collection"] = "eval-v1"
        run_seen["meta"]["game_id"] = "eval-seen"

        run_unseen = _make_run("r-unseen", "verda-kimi-k3-1-pro", "model", [_make_step(0, None, optimal_moves=2)])
        run_unseen["meta"]["collection"] = "eval-v1"
        run_unseen["meta"]["game_id"] = "eval-unseen"
        run_unseen["meta"]["outcome"] = "BUDGET"

        game_descs = {
            "eval-seen": {"game_id": "eval-seen", "levels": [{"optimal_moves": 2}], "holdout": {"levels": [], "skin": False}},
            "eval-unseen": {"game_id": "eval-unseen", "levels": [{"optimal_moves": 2}], "holdout": {"levels": [1], "skin": True}},
        }
        lb = aggregate_runs([run_seen, run_unseen], models_registry=load_models(REPO_ROOT), game_descs=game_descs)
        row = lb["rows"][0]
        self.assertEqual(row["input_modes"], ["image", "rle"])
        self.assertEqual(row["seen_score"], 1.0)
        self.assertEqual(row["unseen_pair_score"], 0.0)
        self.assertEqual(row["unseen_skin_score"], 0.0)

        rules_doc = analyze_rules([run_seen], models_registry=load_models(REPO_ROOT), game_descs=game_descs)
        collect_cell = next(c for c in rules_doc["cells"] if c["rule"] == "collect_all")
        self.assertEqual(collect_cell["actions_to_first_use"], 1.0)
        self.assertEqual(collect_cell["intro_solve_rate"], 1.0)

    def test_takeover_filter_and_failure_explanations(self) -> None:
        # 1) Take-over runs (`start_level` or `takeover_of`) are excluded from baselines
        r_takeover = _make_run("r-takeover", "alice", "human", [_make_step(0, None), _make_step(1, "ACTION1", state="WIN")])
        r_takeover["meta"]["start_level"] = 3
        r_takeover["meta"]["takeover_of"] = {"run_id": "model-run-1", "step": 23}
        self.assertEqual(filter_benchmark_runs([r_takeover], REPO_ROOT), [])

        # 2) Failure explanations + verbatim quote enforcement + cost estimate
        s0 = _make_step(0, None, optimal_moves=4)
        s0["truth"]["active_rules"] = ["walls", "goal", "checkpoints"]
        s0["truth"]["new_rule"] = "checkpoints"
        s1 = _make_step(1, "ACTION4", events=["bump"], optimal_moves=4)
        s1["truth"]["active_rules"] = ["walls", "goal", "checkpoints"]
        s1["truth"]["new_rule"] = "checkpoints"
        s1["hypothesis"] = "Blue hollow ring looks like the immediate exit."
        s2 = _make_step(2, "ACTION2", events=["checkpoints_reset"], optimal_moves=4, frame_row6="3" + "0" * 63)
        s2["truth"]["active_rules"] = ["walls", "goal", "checkpoints"]
        s2["truth"]["new_rule"] = "checkpoints"
        s2["reasoning"] = "Stepped on the second ring and HUD pips cleared."

        failed_run = _make_run("r-fail-cp", "verda-kimi-k3-1-pro", "model", [s0, s1, s2])
        failed_run["meta"]["outcome"] = "BUDGET"
        failed_run["meta"]["levels_completed"] = 0

        pkts = build_failure_packets([failed_run], repo_root=REPO_ROOT)
        self.assertEqual(len(pkts), 1)
        est = estimate_judge_cost(pkts)
        self.assertEqual(est["failed_levels"], 1)
        self.assertTrue(est["within_decisions_sweep_cap"])

        # Deterministic auditor
        exp_doc = build_explanations([failed_run], repo_root=REPO_ROOT)
        validate_against_schema(exp_doc, REPO_ROOT / "contracts" / "derived.schema.json")
        self.assertEqual(len(exp_doc["explanations"]), 1)
        item = exp_doc["explanations"][0]
        self.assertEqual(item["rule"], "checkpoints")
        self.assertEqual(item["verdict"], "hazard_loss")
        self.assertEqual(item["step"], 2)
        self.assertEqual(item["evidence_quote"], "Stepped on the second ring and HUD pips cleared.")

        # External judge returning a non-verbatim hallucinated quote falls back to verified verbatim quote
        fake_llm = lambda _pkt: {
            "step": 2,
            "rule": "checkpoints",
            "verdict": "wrong_hypothesis",
            "explanation": "Touched later checkpoint out of order.",
            "evidence_quote": "THIS QUOTE DOES NOT EXIST IN STEPS",
            "judge_model": "mock-judge-v1",
        }
        exp_llm = build_explanations([failed_run], repo_root=REPO_ROOT, judge_fn=fake_llm)
        validate_against_schema(exp_llm, REPO_ROOT / "contracts" / "derived.schema.json")
        self.assertEqual(exp_llm["explanations"][0]["judge_model"], "mock-judge-v1")
        self.assertEqual(exp_llm["explanations"][0]["evidence_quote"], "Stepped on the second ring and HUD pips cleared.")

        # A3 arena.judge.complete wrapper (`make_arena_judge`) parses fenced JSON replies cleanly
        from analysis.explain import make_arena_judge

        def _fake_arena_complete(prompt: str, system: str = "", max_tokens: int = 350) -> dict:
            self.assertIsInstance(prompt, str)
            self.assertIn("checkpoints", prompt)
            return {
                "reply": '```json\n{"step": 1, "rule": "checkpoints", "verdict": "wrong_hypothesis", "explanation": "Mistook checkpoint 2 ring for goal.", "evidence_quote": "Blue hollow ring looks like the immediate exit."}\n```',
                "model": "gemini-pro",
                "cost_usd": 0.004,
            }

        exp_arena = build_explanations([failed_run], repo_root=REPO_ROOT, judge_fn=make_arena_judge(_fake_arena_complete))
        validate_against_schema(exp_arena, REPO_ROOT / "contracts" / "derived.schema.json")
        self.assertEqual(exp_arena["judge_model"], "gemini-pro")
        self.assertEqual(exp_arena["explanations"][0]["step"], 1)
        self.assertEqual(exp_arena["explanations"][0]["evidence_quote"], "Blue hollow ring looks like the immediate exit.")

    def test_phase2_h2_bench_and_sampling_export(self) -> None:
        from analysis.aggregate import aggregate_h2_runs
        from analysis.bench_agg import build_bench_summary
        from analysis.sampling_export import build_decision_points_export

        dev_games = json.loads((REPO_ROOT / "data" / "collections" / "dev.json").read_text(encoding="utf-8"))["games"]
        valid_gid = dev_games[0]["game_id"]

        # 1) /challenge visitor runs + early h2 budget_tokens bug runs are dropped
        r_chal = _make_run("r-chal", "visitor", "human", [_make_step(0, None), _make_step(1, "ACTION1", state="WIN")])
        r_chal["meta"]["game_id"] = valid_gid
        r_chal["meta"]["player"]["mode"] = "challenge"
        r_chal["meta"]["player"]["purpose"] = "challenge"

        r_h2_bug = _make_run("r-h2-bug", "claude-haiku-5-5", "model", [_make_step(0, None), _make_step(1, "ACTION1")])
        r_h2_bug["meta"]["game_id"] = valid_gid
        r_h2_bug["meta"]["harness_version"] = None
        r_h2_bug["meta"]["player"]["harness_version"] = "h2"
        r_h2_bug["meta"]["end_reason"] = "budget_tokens"
        r_h2_bug["meta"]["started_at"] = "2026-11-14T14:50:19Z"

        r_h2_ok = _make_run(
            "r-h2-ok",
            "verda-kimi-k3-1-pro",
            "model",
            [_make_step(0, None, optimal_moves=1), _make_step(1, "ACTION1", state="WIN", events=["level_complete", "game_won"], optimal_moves=1, frame_row6="1" + "0" * 63)],
        )
        r_h2_ok["meta"]["game_id"] = valid_gid
        r_h2_ok["meta"]["harness_version"] = None
        r_h2_ok["meta"]["player"]["harness_version"] = "h2"
        r_h2_ok["meta"]["player"]["effort"] = "max"
        r_h2_ok["meta"]["player"]["reasoning_mode"] = "assistant-message-returned-verbatim"
        r_h2_ok["meta"]["started_at"] = "2026-11-14T15:57:22Z"

        r_gem_h1 = _make_run("r-gem-h1", "gemini-flash", "model", [_make_step(0, None, optimal_moves=2), _make_step(1, "ACTION1", events=["bump"], optimal_moves=2), _make_step(2, "ACTION1", events=["bump"], optimal_moves=2)])
        r_gem_h1["meta"]["game_id"] = valid_gid
        r_gem_h1["meta"]["outcome"] = "BUDGET"
        r_gem_h1["meta"]["cost_usd"] = 0.05
        r_gem_h1["meta"]["started_at"] = "2026-11-14T13:00:00Z"

        cleaned = filter_benchmark_runs([r_chal, r_h2_bug, r_h2_ok, r_gem_h1], REPO_ROOT)
        self.assertEqual([r["meta"]["run_id"] for r in cleaned], ["r-h2-ok", "r-gem-h1"])
        self.assertEqual(r_h2_ok["meta"]["harness_version"], "h2")

        # 2) Strict h1 vs h2 board separation + Gemini pre-17:15 cost underreport flag
        models_reg = load_models(REPO_ROOT)
        lb_h1 = aggregate_runs(cleaned, models_registry=models_reg, game_descs={})
        lb_h2 = aggregate_h2_runs(cleaned, models_registry=models_reg, game_descs={})
        validate_against_schema(lb_h1, REPO_ROOT / "contracts" / "derived.schema.json")
        validate_against_schema(lb_h2, REPO_ROOT / "contracts" / "derived.schema.json")
        self.assertEqual([r["player_id"] for r in lb_h1["rows"]], ["gemini-flash"])
        self.assertTrue(lb_h1["rows"][0]["cost_underreported"])
        self.assertEqual([r["player_id"] for r in lb_h2["rows"]], ["verda-kimi-k3-1-pro"])
        self.assertEqual(lb_h2["rows"][0]["reasoning_mode"], "assistant-message-returned-verbatim")
        self.assertTrue(lb_h2["rows"][0]["single_attempt"])

        # 3) Bench paired bootstrap CIs + Honesty Rule
        with tempfile.TemporaryDirectory() as td:
            bdir = Path(td) / "bench"
            for name, bbh_sc, gsm_sc, hist_sc in (("base", 0.40, 0.50, 0.50), ("ctrl", 0.42, 0.51, 0.50), ("sft-mix", 0.68, 0.72, 0.51)):
                rdir = bdir / name
                rdir.mkdir(parents=True)
                items_lines = []
                for idx in range(40):
                    items_lines.append(json.dumps({"bench": "bbh", "item": f"q{idx}", "score": 1.0 if idx < int(40 * bbh_sc) else 0.0}))
                    items_lines.append(json.dumps({"bench": "gsm8k", "item": f"m{idx}", "score": 1.0 if idx < int(40 * gsm_sc) else 0.0}))
                    items_lines.append(json.dumps({"bench": "mmlu_pro_history", "item": f"h{idx}", "score": 1.0 if idx < int(40 * hist_sc) else 0.0}))
                (rdir / "items.jsonl").write_text("\n".join(items_lines) + "\n", encoding="utf-8")
                (rdir / "summary.json").write_text(json.dumps({
                    "name": name,
                    "model": "Qwen/Qwen3.5-9B",
                    "config_hash": "hash1",
                    "benchmarks": {
                        "bbh": {"tier": "primary", "n": 40, "mean": bbh_sc, "ci_low": bbh_sc - 0.1, "ci_high": bbh_sc + 0.1, "truncated": 0},
                        "gsm8k": {"tier": "primary", "n": 40, "mean": gsm_sc, "ci_low": gsm_sc - 0.1, "ci_high": gsm_sc + 0.1, "truncated": 0},
                        "mmlu_pro_history": {"tier": "negative_control", "n": 40, "mean": hist_sc, "ci_low": hist_sc - 0.1, "ci_high": hist_sc + 0.1, "truncated": 0},
                    },
                }), encoding="utf-8")
            bs = build_bench_summary(bdir, lb_h1=lb_h1, lb_h2=lb_h2, resamples=500)
            self.assertEqual(bs["claim_evaluation"]["status"], "transfer_supported")
            self.assertEqual(bs["claim_evaluation"]["winning_candidate"], "mix")

        # 4) Decision-point export excludes Tier-3 rules from train-v1 weights
        dp = build_decision_points_export(cleaned, repo_root=REPO_ROOT)
        self.assertGreaterEqual(len(dp["decision_points"]), 1)
        self.assertNotIn("conveyors", dp["oversample_weights"]["by_train_safe_rule"])
        self.assertNotIn("checkpoints", dp["oversample_weights"]["by_train_safe_rule"])


if __name__ == "__main__":
    unittest.main()
