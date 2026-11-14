"""Rule-discovery, cross-level learning, and failure-mode analysis -> rules.json."""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from .loader import (
    extract_level_segments,
    find_repo_root,
    load_collections,
    load_models,
    load_runs,
    normalize_player,
    now_iso,
)


def analyze_rules(
    runs: list[dict[str, Any]],
    models_registry: dict[str, dict[str, Any]] | None = None,
    game_descs: dict[str, dict[str, Any]] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Compute rules.json structure strictly from run traces."""
    models_registry = models_registry if models_registry is not None else load_models()
    game_descs = game_descs if game_descs is not None else load_collections()

    # Cell accumulators keyed by (rule, player_id, effort)
    cell_acc: dict[tuple[str, str, str | None], dict[str, Any]] = defaultdict(
        lambda: {
            "intro_levels": 0,
            "intro_solved": 0,
            "first_use_steps": [],
            "wasted_list": [],
            "no_effect_list": [],
            "hyp_total": 0,
            "hyp_matches": 0,
            "belief_total": 0,
            "belief_correct": 0,
            "intro_scores": [],
            "recombined_total": 0,
            "recombined_solved": 0,
        }
    )

    # Cross-level learning curve accumulators: (level_num, player_id, tier)
    curve_acc: dict[tuple[int, str, str], dict[str, Any]] = defaultdict(
        lambda: {"attempts": 0, "solved": 0, "scores": [], "actions": [], "optimal": []}
    )

    # Failure taxonomy accumulators
    failure_examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    failure_counts: dict[str, int] = defaultdict(int)
    rules_seen: set[str] = set()
    players_seen: set[str] = set()

    for run in runs:
        meta = run["meta"]
        gid = str(meta.get("game_id") or "")
        run_id = str(meta.get("run_id") or "")
        player = meta.get("player") or {}
        pid, kind, effort, _ = normalize_player(player)
        players_seen.add(pid)

        reg = models_registry.get(pid)
        tier = reg["card"]["tier"] if reg else kind

        seg_info = extract_level_segments(run, game_descs.get(gid))
        for lv_num, seg in seg_info["segments"].items():
            # Cross-level learning curve: only count levels actually attempted or level 1..levels_total
            # Include all levels in the game so skipping/failing early levels shows true drop-off
            ckey = (lv_num, pid, tier)
            curve_acc[ckey]["attempts"] += 1
            if seg["solved"]:
                curve_acc[ckey]["solved"] += 1
            curve_acc[ckey]["scores"].append(seg["level_score"])
            if seg["actions_used"] > 0:
                curve_acc[ckey]["actions"].append(seg["actions_used"])
            if seg["optimal_moves"] > 0:
                curve_acc[ckey]["optimal"].append(seg["optimal_moves"])

            if seg["actions_used"] == 0 and not seg["solved"]:
                # Never reached this level in this run
                continue

            intro_rule = seg["new_rule"]
            if not intro_rule and lv_num == 1:
                # Level 1 teaches basic navigation/goal when engine omits new_rule
                intro_rule = "walls" if "walls" in seg["active_rules"] else "goal"

            if intro_rule:
                rules_seen.add(intro_rule)
                acc = cell_acc[(intro_rule, pid, effort)]
                acc["intro_levels"] += 1
                if seg["solved"]:
                    acc["intro_solved"] += 1
                acc["intro_scores"].append(seg["level_score"])
                if seg["first_rule_event_step"] is not None:
                    acc["first_use_steps"].append(seg["first_rule_event_step"])
                opt = seg["optimal_moves"]
                used = seg["actions_used"]
                wasted = max(0, used - opt) if seg["solved"] else used
                acc["wasted_list"].append(wasted)
                acc["no_effect_list"].append(seg["no_effect_actions"])
                if kind == "model":
                    acc["hyp_total"] += 1
                    if seg["hypothesis_matched"]:
                        acc["hyp_matches"] += 1
                acc["belief_total"] += seg["belief_total"]
                acc["belief_correct"] += seg["belief_correct"]

            # Track recombined usage on later levels
            for r in seg["active_rules"]:
                rules_seen.add(r)
                if r != intro_rule:
                    racc = cell_acc[(r, pid, effort)]
                    racc["recombined_total"] += 1
                    if seg["solved"]:
                        racc["recombined_solved"] += 1

            # Collect failure modes for model/human runs (exclude noop/stop_early/optimal)
            if kind in ("model", "human"):
                if seg["no_effect_actions"] >= 1:
                    failure_counts["no_effect_loop"] += seg["no_effect_actions"]
                    bump_step = next((st["i"] for st in seg["steps"] if st["no_effect"]), None)
                    if bump_step is not None and len(failure_examples["no_effect_loop"]) < 8:
                        failure_examples["no_effect_loop"].append({
                            "run_id": run_id,
                            "step": bump_step,
                            "player_id": pid,
                            "level": lv_num,
                            "rule": intro_rule,
                            "count": seg["no_effect_actions"],
                        })
                if seg["resets"] > 0 and seg["actions_used"] > max(4, seg["optimal_moves"]):
                    failure_counts["late_reset"] += seg["resets"]
                    rst_step = next((st["i"] for st in seg["steps"] if st["action"] == "RESET"), None)
                    if rst_step is not None and len(failure_examples["late_reset"]) < 8:
                        failure_examples["late_reset"].append({
                            "run_id": run_id,
                            "step": rst_step,
                            "player_id": pid,
                            "level": lv_num,
                            "rule": intro_rule,
                        })
                if not seg["solved"]:
                    failure_counts["unsolved_level"] += 1
                    last_step = seg["steps"][-1]["i"] if seg["steps"] else 0
                    if len(failure_examples["unsolved_level"]) < 8:
                        failure_examples["unsolved_level"].append({
                            "run_id": run_id,
                            "step": last_step,
                            "player_id": pid,
                            "level": lv_num,
                            "rule": intro_rule,
                        })
                mismatches = [st["i"] for st in seg["steps"] if st["belief"] in ("playing", "won", "lost") and st["belief"] != st["expected_belief"]]
                if mismatches:
                    failure_counts["belief_mismatch"] += len(mismatches)
                    if len(failure_examples["belief_mismatch"]) < 8:
                        failure_examples["belief_mismatch"].append({
                            "run_id": run_id,
                            "step": mismatches[0],
                            "player_id": pid,
                            "level": lv_num,
                            "rule": intro_rule,
                        })
                if intro_rule and kind == "model" and not seg["solved"] and not seg["hypothesis_matched"]:
                    failure_counts["rule_blindness"] += 1
                    if len(failure_examples["rule_blindness"]) < 8:
                        last_step = seg["steps"][-1]["i"] if seg["steps"] else 0
                        failure_examples["rule_blindness"].append({
                            "run_id": run_id,
                            "step": last_step,
                            "player_id": pid,
                            "level": lv_num,
                            "rule": intro_rule,
                        })

        if meta.get("outcome") == "BUDGET":
            failure_counts["budget_exhaustion"] += 1
            last_i = int(run["steps"][-1]["i"]) if run["steps"] else 0
            if len(failure_examples["budget_exhaustion"]) < 8:
                failure_examples["budget_exhaustion"].append({
                    "run_id": run_id,
                    "step": last_i,
                    "player_id": pid,
                    "actions": meta.get("actions"),
                })

    cells: list[dict[str, Any]] = []
    for (rule, pid, effort), acc in sorted(cell_acc.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2] or "")):
        if acc["intro_levels"] == 0 and acc["recombined_total"] == 0:
            continue
        intro_n = acc["intro_levels"]
        cells.append({
            "rule": rule,
            "player_id": pid,
            "effort": effort,
            "intro_levels": intro_n,
            "intro_solve_rate": round(acc["intro_solved"] / intro_n, 4) if intro_n > 0 else 0.0,
            "actions_to_first_use": round(statistics.median(acc["first_use_steps"]), 2) if acc["first_use_steps"] else None,
            "wasted_actions": round(statistics.fmean(acc["wasted_list"]), 2) if acc["wasted_list"] else None,
            "hypothesis_match_rate": round(acc["hyp_matches"] / acc["hyp_total"], 4) if acc["hyp_total"] > 0 else None,
            # Extended fields for Insights UI
            "repeated_no_effect_actions": round(statistics.fmean(acc["no_effect_list"]), 2) if acc["no_effect_list"] else None,
            "belief_accuracy": round(acc["belief_correct"] / acc["belief_total"], 4) if acc["belief_total"] > 0 else None,
            "intro_score": round(statistics.fmean(acc["intro_scores"]), 4) if acc["intro_scores"] else None,
            "recombined_levels": acc["recombined_total"],
            "recombined_solve_rate": round(acc["recombined_solved"] / acc["recombined_total"], 4)
            if acc["recombined_total"] > 0
            else None,
        })

    level_curve: list[dict[str, Any]] = []
    for (lv_num, pid, tier), acc in sorted(curve_acc.items()):
        n = acc["attempts"]
        level_curve.append({
            "level": lv_num,
            "player_id": pid,
            "tier": tier,
            "attempts": n,
            "solve_rate": round(acc["solved"] / n, 4) if n > 0 else 0.0,
            "mean_score": round(statistics.fmean(acc["scores"]), 4) if acc["scores"] else 0.0,
            "mean_actions": round(statistics.fmean(acc["actions"]), 2) if acc["actions"] else None,
            "mean_optimal": round(statistics.fmean(acc["optimal"]), 2) if acc["optimal"] else None,
        })

    failure_modes = [
        {
            "mode": mode,
            "count": count,
            "examples": failure_examples.get(mode, []),
        }
        for mode, count in sorted(failure_counts.items(), key=lambda kv: -kv[1])
    ]

    return {
        "generated_at": generated_at or now_iso(),
        "rules": sorted(rules_seen),
        "players": sorted(players_seen),
        "cells": cells,
        "level_curve": level_curve,
        "failure_modes": failure_modes,
    }


def build_rules(
    runs_dir: Path,
    out_path: Path | None = None,
    repo_root: Path | None = None,
    extra_runs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    root = repo_root or find_repo_root()
    runs = load_runs(runs_dir)
    if extra_runs:
        runs = runs + extra_runs
    models = load_models(root)
    games = load_collections(root)
    data = analyze_rules(runs, models_registry=models, game_descs=games)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data
