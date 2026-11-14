"""Export structured failure decision points & oversampling weights for A1/A3 training data v2 (PLAN.md §3.3, A5-21).

Produces `decision_points.json` containing:
1. Per-failure decision-point records (`decision_type`, `game_id`, `collection`, `level`, `step`, `rule`, `active_rules`)
   across the four PLAN.md §3.3 archetypes:
   - `premature_hypothesis`
   - `zero_change_wall_bump`
   - `late_reset`
   - `missed_new_rule`
2. `oversample_weights`: normalized `train-v1`-safe sampling weights over `by_decision_type`, `by_train_safe_rule`,
   and A1's `engine.tasks` / A3's `posttrain` trajectory types (strictly excluding Tier-3 eval-only mechanics).
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .loader import (
    TIER_0_RULES,
    extract_level_segments,
    find_repo_root,
    normalize_player,
    now_iso,
)

# Tier 1-2 mechanics eligible in train-v1 (Tier-3 eval-v2 mechanics are strictly excluded from train weights)
TRAIN_V1_SAFE_RULES: tuple[str, ...] = (
    "keys_doors",
    "plates_gates",
    "teleporters",
    "hazards",
    "push_blocks",
    "ice",
    "one_way",
    "collect_all",
    "phase_walls",
    "rotation",
    "remap",
    "twin",
    "stamina",
    "cracked_floor",
    "beacon_goal",
)

DECISION_TYPES: tuple[str, ...] = (
    "premature_hypothesis",
    "zero_change_wall_bump",
    "late_reset",
    "missed_new_rule",
)


def _normalize_weights(counts: dict[str, float], floor: float = 0.02) -> dict[str, float]:
    if not counts:
        return {}
    total = sum(max(0.0, v) for v in counts.values())
    if total <= 0:
        u = round(1.0 / len(counts), 4)
        return {k: u for k in sorted(counts)}
    raw = {k: max(floor, v / total) for k, v in counts.items()}
    s = sum(raw.values())
    return {k: round(v / s, 4) for k, v in sorted(raw.items(), key=lambda item: (-item[1], item[0]))}


def build_decision_points_export(
    runs: list[dict[str, Any]],
    game_descs: dict[str, dict[str, Any]] | None = None,
    repo_root: Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Extract structured failure decision points and `train-v1`-safe oversampling weights."""
    _ = repo_root or find_repo_root()
    descs = game_descs or {}

    points: list[dict[str, Any]] = []
    type_counts: Counter[str] = Counter()
    rule_fail_counts: Counter[str] = Counter()
    rule_attempt_counts: Counter[str] = Counter()

    for run in runs:
        meta = run.get("meta") or {}
        player = meta.get("player") or {}
        pid, kind, effort, _ = normalize_player(player)
        if kind != "model":
            continue

        run_id = str(meta.get("run_id") or "")
        gid = str(meta.get("game_id") or "")
        col = str(meta.get("collection") or "dev")
        if not run_id or not gid:
            continue

        seg_info = extract_level_segments(run, descs.get(gid))
        for lv_num in sorted(seg_info["segments"]):
            seg = seg_info["segments"][lv_num]
            if seg["actions_used"] <= 0:
                continue

            active_rules = [r for r in (seg["active_rules"] or []) if r not in TIER_0_RULES]
            new_rule = seg["new_rule"]
            primary_rule = new_rule or (active_rules[-1] if active_rules else "walls")
            for r in active_rules:
                if r in TRAIN_V1_SAFE_RULES:
                    rule_attempt_counts[r] += 1

            if seg["solved"]:
                continue

            for r in active_rules:
                if r in TRAIN_V1_SAFE_RULES:
                    rule_fail_counts[r] += 1

            steps = seg["steps"]
            opt_moves = int(seg["optimal_moves"] or 0)
            budget = int(seg["move_budget"] or 0)
            slack = max(2, budget - opt_moves) if budget > opt_moves else max(4, opt_moves // 2)

            # 1) Missed newly introduced rule (0 causal rule triggers on intro level)
            if new_rule and seg["first_rule_event_step"] is None:
                pivot_step = int(steps[min(len(steps) - 1, max(0, opt_moves // 2))]["i"])
                points.append({
                    "decision_type": "missed_new_rule",
                    "run_id": run_id,
                    "game_id": gid,
                    "collection": col,
                    "split_holdout_safe": col == "dev",
                    "player_id": f"{pid}:{effort}" if effort else pid,
                    "level": lv_num,
                    "step": pivot_step,
                    "rule": new_rule,
                    "active_rules": list(seg["active_rules"] or []),
                    "actions_used": int(seg["actions_used"]),
                    "optimal_moves": opt_moves,
                    "move_budget": budget,
                })
                type_counts["missed_new_rule"] += 1

            # 2) Zero-change wall bump / repeated no-effect streak (>= 2 consecutive no-effect steps)
            streak = 0
            bump_step: int | None = None
            for st in steps:
                if st.get("no_effect") or "bump" in (st.get("events") or []):
                    streak += 1
                    if streak == 2 and bump_step is None:
                        bump_step = int(st["i"])
                else:
                    streak = 0
            if bump_step is not None:
                points.append({
                    "decision_type": "zero_change_wall_bump",
                    "run_id": run_id,
                    "game_id": gid,
                    "collection": col,
                    "split_holdout_safe": col == "dev",
                    "player_id": f"{pid}:{effort}" if effort else pid,
                    "level": lv_num,
                    "step": bump_step,
                    "rule": primary_rule,
                    "active_rules": list(seg["active_rules"] or []),
                    "actions_used": int(seg["actions_used"]),
                    "optimal_moves": opt_moves,
                    "move_budget": budget,
                })
                type_counts["zero_change_wall_bump"] += 1

            # 3) Resetting too late (blew past slack without resetting, or first RESET happened after slack exhausted)
            reset_indices = [idx for idx, st in enumerate(steps) if st.get("action") == "RESET"]
            late_reset_step: int | None = None
            if reset_indices and reset_indices[0] > slack:
                late_reset_step = int(steps[reset_indices[0]]["i"])
            elif not reset_indices and opt_moves > 0 and len(steps) > opt_moves + slack:
                late_reset_step = int(steps[min(len(steps) - 1, slack)]["i"])
            if late_reset_step is not None:
                points.append({
                    "decision_type": "late_reset",
                    "run_id": run_id,
                    "game_id": gid,
                    "collection": col,
                    "split_holdout_safe": col == "dev",
                    "player_id": f"{pid}:{effort}" if effort else pid,
                    "level": lv_num,
                    "step": late_reset_step,
                    "rule": primary_rule,
                    "active_rules": list(seg["active_rules"] or []),
                    "actions_used": int(seg["actions_used"]),
                    "optimal_moves": opt_moves,
                    "move_budget": budget,
                })
                type_counts["late_reset"] += 1

            # 4) Acting on premature / mismatched hypothesis
            if new_rule and not seg["hypothesis_matched"]:
                hyp_step_obj = next((st for st in steps if st.get("hypothesis")), steps[0])
                points.append({
                    "decision_type": "premature_hypothesis",
                    "run_id": run_id,
                    "game_id": gid,
                    "collection": col,
                    "split_holdout_safe": col == "dev",
                    "player_id": f"{pid}:{effort}" if effort else pid,
                    "level": lv_num,
                    "step": int(hyp_step_obj["i"]),
                    "rule": new_rule,
                    "active_rules": list(seg["active_rules"] or []),
                    "actions_used": int(seg["actions_used"]),
                    "optimal_moves": opt_moves,
                    "move_budget": budget,
                })
                type_counts["premature_hypothesis"] += 1

    # Compute train-v1-safe oversampling weights (empirical failure rate + volume Laplace smoothing)
    raw_type_scores = {dt: float(type_counts.get(dt, 0) + 1) for dt in DECISION_TYPES}
    by_type = _normalize_weights(raw_type_scores, floor=0.05)

    raw_rule_scores: dict[str, float] = {}
    for r in TRAIN_V1_SAFE_RULES:
        fails = rule_fail_counts.get(r, 0)
        att = rule_attempt_counts.get(r, 0)
        fail_rate = (fails + 1.0) / (att + 2.0)
        raw_rule_scores[r] = fail_rate * (1.0 + 0.25 * fails)
    by_rule = _normalize_weights(raw_rule_scores, floor=0.025)

    # Map decision-point weights directly onto A1's 4 auxiliary tasks and A3's 3 trajectory modes
    aux_task_weights = _normalize_weights({
        "next_frame": by_type["zero_change_wall_bump"] + 0.5 * by_type["premature_hypothesis"],
        "rule_effect": by_type["missed_new_rule"] + by_type["premature_hypothesis"],
        "min_moves": by_type["late_reset"] + 0.3 * by_type["zero_change_wall_bump"],
        "full_plan": 0.5 * by_type["missed_new_rule"] + 0.5 * by_type["late_reset"],
    })
    trajectory_mode_weights = _normalize_weights({
        "optimal": 0.35,
        "recover_from_detour": by_type["zero_change_wall_bump"] + by_type["premature_hypothesis"],
        "blow_level_then_reset": by_type["late_reset"] + 0.5 * by_type["missed_new_rule"],
    })

    return {
        "generated_at": generated_at or now_iso(),
        "holdout_notice": (
            "NEVER train on eval-v1, eval-v2, or probe-v1 traces. Use `oversample_weights` to bias procedural "
            "`train-v1` seed/mechanic generation in `engine.tasks` and `arena/dataset.py`."
        ),
        "counts_by_decision_type": {dt: int(type_counts.get(dt, 0)) for dt in DECISION_TYPES},
        "oversample_weights": {
            "by_decision_type": by_type,
            "by_train_safe_rule": by_rule,
            "recommended_aux_task_mix": aux_task_weights,
            "recommended_trajectory_mix": trajectory_mode_weights,
        },
        "decision_points": points,
    }
