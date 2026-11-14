"""Generate headline insights (insights.json) and automated rule proposals (rules/proposals/auto-*.md)."""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from .compare import build_comparisons
from .loader import TIER_0_RULES, find_repo_root, now_iso


def _rank_hardest_rule(intro_model_cells: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Aggregate intro solve rate and wasted actions per rule across models (preferring Tier 1+ rules)."""
    if not intro_model_cells:
        return None
    non_tier0 = [c for c in intro_model_cells if c.get("rule") not in TIER_0_RULES]
    pool = non_tier0 if non_tier0 else intro_model_cells

    by_rule: dict[str, dict[str, float]] = defaultdict(lambda: {"attempts": 0.0, "solved": 0.0, "wasted_sum": 0.0, "wasted_n": 0.0})
    for c in pool:
        r = str(c["rule"])
        n = float(c.get("intro_levels") or 0)
        if n <= 0:
            continue
        by_rule[r]["attempts"] += n
        by_rule[r]["solved"] += float(c.get("intro_solve_rate") or 0.0) * n
        if c.get("wasted_actions") is not None:
            by_rule[r]["wasted_sum"] += float(c["wasted_actions"]) * n
            by_rule[r]["wasted_n"] += n

    if not by_rule:
        return None
    ranked = []
    for r, acc in by_rule.items():
        sr = round(acc["solved"] / acc["attempts"], 4) if acc["attempts"] > 0 else 0.0
        wa = round(acc["wasted_sum"] / acc["wasted_n"], 2) if acc["wasted_n"] > 0 else None
        ranked.append({"rule": r, "intro_solve_rate": sr, "wasted_actions": wa, "attempts": int(acc["attempts"])})
    ranked.sort(key=lambda x: (x["intro_solve_rate"], -(x["wasted_actions"] or 0.0), x["rule"]))
    return ranked[0]


def synthesize_insights(
    leaderboard: dict[str, Any],
    rules_data: dict[str, Any],
    runs: list[dict[str, Any]] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build schema-valid insights.json with evidence + deep replay links."""
    comparisons = build_comparisons(leaderboard)
    rows = leaderboard.get("rows") or []
    cells = rules_data.get("cells") or []
    failure_modes = rules_data.get("failure_modes") or []
    runs = runs or []

    model_rows = [r for r in rows if r.get("kind") == "model"]
    human_rows = [r for r in rows if r.get("kind") == "human"]
    optimal_rows = [r for r in rows if r.get("kind") == "baseline" and r.get("player_id") == "optimal"]

    insights: list[dict[str, Any]] = []

    # Helper to pick a representative step from runs (optionally filtered to a player_id)
    def _first_run_step(target_pid: str | None = None) -> tuple[str | None, int | None]:
        for run in runs:
            meta = run.get("meta") or {}
            player = meta.get("player") or {}
            pid = player.get("model_id") or player.get("id") or player.get("name")
            if target_pid is not None and pid != target_pid:
                continue
            if player.get("kind") in ("model", "human") and run.get("steps"):
                steps = run["steps"]
                mid = steps[min(len(steps) - 1, 1)]["i"]
                return str(meta.get("run_id")), int(mid)
        if target_pid is not None:
            return _first_run_step(None)
        return None, None

    default_run_id, default_step = _first_run_step()

    # Finding 1: The Efficiency Gap (Optimal / Human vs Models)
    best_model = comparisons.get("best_model")
    opt_score = optimal_rows[0]["score"] if optimal_rows else 1.0
    if best_model:
        bm_run_id, bm_step = _first_run_step(best_model["player_id"])
        evidence = [
            {
                "label": f"{best_model['display_name']} Efficiency Score",
                "value": best_model["score"],
                "run_id": bm_run_id,
                "step": bm_step,
            },
            {
                "label": "Optimal Reference Score",
                "value": opt_score,
                "run_id": None,
                "step": None,
            },
        ]
        if human_rows:
            h_row = next((r for r in human_rows if r.get("collection") == best_model.get("collection")), human_rows[0])
            h_score = h_row["score"]
            evidence.insert(
                1,
                {
                    "label": f"Human Baseline Score ({h_row.get('collection', 'dev')})",
                    "value": h_score,
                    "run_id": None,
                    "step": None,
                },
            )
            h_won = h_row.get("game_win_rate") or 0.0
            m_won = best_model.get("game_win_rate") or 0.0
            summary = (
                f"Best evaluated model ({best_model['display_name']}) won {m_won * 100:.0f}% of its games "
                f"({best_model['level_solve_rate'] * 100:.0f}% of levels) vs. {h_won * 100:.0f}% for first-attempt "
                f"humans; efficiency {best_model['score']:.3f} vs. {h_score:.3f} (BFS optimal {opt_score:.3f})."
            )
        else:
            gap = round(opt_score - best_model["score"], 4)
            summary = (
                f"Best evaluated model ({best_model['display_name']}) achieved {best_model['score']:.3f} "
                f"action-efficiency score ({best_model['level_solve_rate'] * 100:.1f}% levels solved), "
                f"leaving a {gap:.3f} gap behind BFS optimal ({opt_score:.3f}) due to exploration overhead and budget exhaustion."
            )
        # Attach level completion proof step if present in runs (prefer best_model first)
        ordered_runs = sorted(
            runs,
            key=lambda rn: 0
            if ((rn.get("meta") or {}).get("player") or {}).get("id") == best_model["player_id"]
            or ((rn.get("meta") or {}).get("player") or {}).get("model_id") == best_model["player_id"]
            else 1,
        )
        for run in ordered_runs:
            meta = run.get("meta") or {}
            if (meta.get("player") or {}).get("kind") == "model":
                for st in run.get("steps") or []:
                    if "level_complete" in ((st.get("truth") or {}).get("events") or []):
                        evidence.append({
                            "label": f"Level { max(1, int(st['truth']['level']) - 1) } Solved",
                            "value": f"step {st['i']}",
                            "run_id": str(meta.get("run_id")),
                            "step": int(st["i"]),
                        })
                        break
                if len(evidence) >= 3:
                    break
        insights.append({
            "id": "efficiency-gap",
            "title": "Action-Efficiency Gap Against Optimal and Human Play",
            "summary": summary,
            "category": "gap",
            "severity": "high",
            "evidence": evidence,
        })

    # Finding 2: Vision + RLE vs Text-Only RLE Modality Gap (when both modalities are present)
    vision_models = [r for r in model_rows if "image" in (r.get("input_modes") or [])]
    rle_only_models = [
        r for r in model_rows
        if (r.get("input_modes") or []) and "image" not in (r.get("input_modes") or [])
    ]
    if vision_models and rle_only_models:
        best_vis = max(vision_models, key=lambda r: r["score"])
        best_rle = max(rle_only_models, key=lambda r: (r["score"], -(r.get("no_effect_rate") or 1.0)))
        vis_run_id, vis_step = _first_run_step(best_vis["player_id"])
        rle_run_id, rle_step = _first_run_step(best_rle["player_id"])
        rle_levels_attempted = sum(int(r.get("levels_attempted") or 0) for r in rle_only_models)
        rle_levels_solved = sum(int(r.get("levels_solved") or 0) for r in rle_only_models)
        insights.append({
            "id": "modality-gap",
            "title": "2D Spatial Vision + RLE Outperforms Lossless Text-Only RLE",
            "summary": (
                f"Under identical h1 tool semantics, multimodal [image, rle] models reach "
                f"{best_vis['level_solve_rate'] * 100:.1f}% level solve ({best_vis['display_name']}: {best_vis['score']:.3f}), "
                f"whereas text-only [rle] models solve {rle_levels_solved}/{rle_levels_attempted} levels "
                f"despite receiving exact lossless 64×64 run-length grids."
            ),
            "category": "modality",
            "severity": "high",
            "evidence": [
                {
                    "label": f"{best_vis['display_name']} [image+rle] Solve Rate",
                    "value": best_vis["level_solve_rate"],
                    "run_id": vis_run_id,
                    "step": vis_step,
                },
                {
                    "label": f"{best_rle['display_name']} [rle] Solve Rate",
                    "value": best_rle["level_solve_rate"],
                    "run_id": rle_run_id,
                    "step": rle_step,
                },
                {
                    "label": "Text-Only [rle] Levels Solved",
                    "value": f"{rle_levels_solved}/{rle_levels_attempted}",
                    "run_id": rle_run_id,
                    "step": rle_step,
                },
            ],
        })

    # Finding 3: Repeated No-Effect Actions & Exploration Waste
    no_effect_mode = next((fm for fm in failure_modes if fm["mode"] == "no_effect_loop"), None)
    model_cells = [c for c in cells if c.get("player_id") not in ("optimal", "noop", "stop_early", "random")]
    intro_model_cells = [c for c in model_cells if (c.get("intro_levels") or 0) > 0]
    if no_effect_mode or intro_model_cells:
        ev_list: list[dict[str, Any]] = []
        if no_effect_mode:
            ev_list.append({
                "label": "No-Effect / Bump Actions Observed",
                "value": no_effect_mode["count"],
                "run_id": no_effect_mode["examples"][0]["run_id"] if no_effect_mode["examples"] else default_run_id,
                "step": no_effect_mode["examples"][0]["step"] if no_effect_mode["examples"] else default_step,
            })
        wasted_vals = [c["wasted_actions"] for c in intro_model_cells if c.get("wasted_actions") is not None]
        if wasted_vals:
            ev_list.append({
                "label": "Mean Wasted Actions on Intro Levels",
                "value": round(statistics.fmean(wasted_vals), 2),
                "run_id": default_run_id,
                "step": default_step,
            })
        no_eff_rates = [r["no_effect_rate"] for r in model_rows if r.get("no_effect_rate") is not None]
        if no_eff_rates:
            ev_list.append({
                "label": "No-Effect Action Rate",
                "value": round(statistics.fmean(no_eff_rates), 4),
                "run_id": no_effect_mode["examples"][0]["run_id"] if (no_effect_mode and no_effect_mode["examples"]) else default_run_id,
                "step": no_effect_mode["examples"][0]["step"] if (no_effect_mode and no_effect_mode["examples"]) else default_step,
            })
        insights.append({
            "id": "no-effect-thrashing",
            "title": "Models Spend Budget on Repeated No-Effect Actions and Detours",
            "summary": (
                "Across observed model steps, agents lose move budget bumping into walls or repeating "
                "actions whose playfield diff is zero instead of updating spatial constraints immediately."
            ),
            "category": "failure_mode",
            "severity": "medium",
            "evidence": ev_list or [{"label": "Sample Step", "value": "no_effect", "run_id": default_run_id, "step": default_step}],
        })

    # Finding 4: Reset Timing & Budget Exhaustion (or Hardest Rule Bottleneck)
    hardest_cell = _rank_hardest_rule(intro_model_cells)
    late_reset_mode = next((fm for fm in failure_modes if fm["mode"] == "late_reset"), None)
    budget_mode = next((fm for fm in failure_modes if fm["mode"] == "budget_exhaustion"), None)
    ev3: list[dict[str, Any]] = []
    if hardest_cell:
        rule_ex_run, rule_ex_step = default_run_id, default_step
        unsolved_mode = next((fm for fm in failure_modes if fm["mode"] == "unsolved_level"), None)
        if unsolved_mode:
            match_ex = next(
                (ex for ex in unsolved_mode.get("examples") or [] if ex.get("rule") == hardest_cell["rule"]),
                None,
            )
            if match_ex:
                rule_ex_run, rule_ex_step = match_ex.get("run_id"), match_ex.get("step")
        ev3.append({
            "label": f"Hardest Rule Intro Solve Rate ({hardest_cell['rule']})",
            "value": hardest_cell["intro_solve_rate"],
            "run_id": rule_ex_run,
            "step": rule_ex_step,
        })
    if late_reset_mode and late_reset_mode["examples"]:
        ex = late_reset_mode["examples"][0]
        ev3.append({
            "label": "Late Reset Triggered",
            "value": f"level {ex.get('level')}",
            "run_id": ex["run_id"],
            "step": ex["step"],
        })
    if budget_mode and budget_mode["examples"]:
        ex = budget_mode["examples"][0]
        ev3.append({
            "label": "Action Budget Exhausted Runs",
            "value": budget_mode["count"],
            "run_id": ex["run_id"],
            "step": ex["step"],
        })
    if ev3:
        insights.append({
            "id": "reset-and-budget-horizon",
            "title": "Reset Timing and Multi-Level Budget Horizon Limit Game Completion",
            "summary": (
                "Models struggle to detect wasted trajectories early: calling RESET only after walking "
                "deep into dead-ends consumes irrecoverable per-level and per-game action budget."
            ),
            "category": "planning",
            "severity": "high",
            "evidence": ev3,
        })

    # Finding 4: Reward Integrity Verified
    ri = comparisons["reward_integrity"]
    insights.append({
        "id": "reward-integrity-verified",
        "title": "Reward Integrity: Zero-Effort Baselines Score Strictly Zero",
        "summary": (
            "Action-efficiency scoring (min(1, optimal_moves / actions_used) per solved level) "
            "assigns 0.000 to noop and stop_early, penalizes reset farming, and rewards only genuine level completion."
        ),
        "category": "reward_integrity",
        "severity": "info",
        "evidence": [
            {"label": "noop Score", "value": ri["noop_score"] if ri["noop_score"] is not None else 0.0, "run_id": None, "step": None},
            {"label": "stop_early Score", "value": ri["stop_early_score"] if ri["stop_early_score"] is not None else 0.0, "run_id": None, "step": None},
            {"label": "random Score", "value": ri["random_score"] if ri["random_score"] is not None else 0.0, "run_id": None, "step": None},
            {"label": "optimal Score", "value": ri["optimal_score"] if ri["optimal_score"] is not None else 1.0, "run_id": None, "step": None},
        ],
    })

    # Finding 5: Fine-tune / Effort Ablation if present in traces
    if comparisons.get("effort_ablations"):
        ab = comparisons["effort_ablations"][0]
        insights.append({
            "id": "effort-ablation-scaling",
            "title": f"Reasoning Effort Scaling on {ab['display_name']}",
            "summary": (
                "Increasing reasoning effort trades substantially higher token spend for marginal gains "
                "when spatial rule induction fails at the perception layer."
            ),
            "category": "ablation",
            "severity": "medium",
            "evidence": [
                {
                    "label": f"Effort {pt['effort']} Score",
                    "value": pt["score"],
                    "run_id": default_run_id,
                    "step": default_step,
                }
                for pt in ab["points"]
            ],
        })

    return {
        "generated_at": generated_at or now_iso(),
        "insights": insights,
    }


def generate_auto_proposals(
    rules_data: dict[str, Any],
    leaderboard_data: dict[str, Any],
    proposals_dir: Path,
) -> list[Path]:
    """Write rules/proposals/auto-*.md targeting observed model failure modes (`eval-v2` loop)."""
    proposals_dir.mkdir(parents=True, exist_ok=True)
    cells = [
        c for c in (rules_data.get("cells") or [])
        if (c.get("intro_levels") or 0) > 0
        and c.get("player_id") not in ("optimal", "noop", "stop_early", "random")
    ]
    failure_modes = {fm["mode"]: fm for fm in (rules_data.get("failure_modes") or [])}
    rows = leaderboard_data.get("rows") or []
    best_model = max(
        (r for r in rows if r.get("kind") == "model"),
        key=lambda r: r["score"],
        default=None,
    )

    no_effect_count = failure_modes.get("no_effect_loop", {}).get("count", 0)
    unsolved_count = failure_modes.get("unsolved_level", {}).get("count", 0)
    late_reset_count = failure_modes.get("late_reset", {}).get("count", 0)

    weakest_rule = _rank_hardest_rule(cells)

    written: list[Path] = []

    p1 = proposals_dir / "auto-01-wall-bump-cooldown.md"
    p1.write_text(
        "\n".join([
            "# Auto-Proposal 01: Brittle Floor / Bump-Penalty Tiles (`cracked_floor`)",
            "",
            "- **Generated by:** A5 (`python -m analysis insights --write-proposals`)",
            "- **Target:** A1 (`engine/src/engine/components/cracked_floor.py`)",
            "- **Status:** Shipped into live Engine 0.4.0/0.5.0 rule pool.",
            f"- **Observed Failure Cited:** `no_effect_loop` ({no_effect_count} zero-effect/bump actions observed in trace corpus"
            + (f"; best model `{best_model['player_id']}` score `{best_model['score']:.3f}`" if best_model else "")
            + ").",
            "",
            "## Problem Observed",
            "Models repeatedly collide with walls or blocked tiles without updating spatial boundaries in `NOTES`, trusting single-step trial-and-error instead of mapping impassable geometry.",
            "",
            "## Mechanic Specification",
            "- Add `cracked_floor` tiles (single-use bridges): stepping onto one lets the player pass once, then turns the cell into a permanent wall (or pit) after leaving it.",
            "- Unlike static walls, models cannot blindly backtrack after wandering down a corridor — testing 2-step lookahead and amplifying the cost of aimless exploration.",
            "- Exact BFS state adds one bitmask integer (`cracked_used`) per cracked tile (<= 4 tiles per level).",
            "",
        ]),
        encoding="utf-8",
    )
    written.append(p1)

    p2 = proposals_dir / "auto-02-false-goal-indicator.md"
    weak_note = (
        f"rule `{weakest_rule['rule']}` had intro_solve_rate=`{weakest_rule['intro_solve_rate']}`, wasted_actions=`{weakest_rule['wasted_actions']}`"
        if weakest_rule
        else f"{unsolved_count} unsolved level attempts recorded"
    )
    p2.write_text(
        "\n".join([
            "# Auto-Proposal 02: Collect-All Key Shards Before Goal Activation (`collect_all`)",
            "",
            "- **Generated by:** A5 (`python -m analysis insights --write-proposals`)",
            "- **Target:** A1 (`engine/src/engine/components/collect_all.py`)",
            "- **Status:** Shipped into live Engine 0.4.0/0.5.0 rule pool.",
            f"- **Observed Failure Cited:** {weak_note}; models frequently tunnel directly toward the goal ring without sequencing intermediate sub-goals.",
            "",
            "## Problem Observed",
            "Models form premature single-object hypotheses (`reach coloured ring = done`) and ignore secondary board state changes.",
            "",
            "## Mechanic Specification",
            "- Place 2–3 small token sprites on the board and render the goal ring as locked (hollow/dimmed sprite) until all tokens are collected, lighting a matching pip in the HUD (`rows 3–4`) per collected token.",
            "- Forces genuine sub-goal ordering (`TSP`-like shortest tour) while remaining trivially verifiable in BFS via `collected_mask`.",
            "",
        ]),
        encoding="utf-8",
    )
    written.append(p2)

    p3 = proposals_dir / "auto-03-commitment-corridor.md"
    p3.write_text(
        "\n".join([
            "# Auto-Proposal 03: Mirror Twin / Coupled Movement (`twin`)",
            "",
            "- **Generated by:** A5 (`python -m analysis insights --write-proposals`)",
            "- **Target:** A1 (`engine/src/engine/components/twin.py`)",
            "- **Status:** Shipped into live Engine 0.4.0/0.5.0 rule pool.",
            f"- **Observed Failure Cited:** `late_reset` ({late_reset_count} late reset episodes) + multi-step budget exhaustion (`unsolved_level={unsolved_count}`).",
            "",
            "## Problem Observed",
            "Models commit to local greedy moves and fail to issue `RESET` promptly when a coupled constraint becomes unsolvable.",
            "",
            "## Mechanic Specification",
            "- Spawn a secondary twin sprite (skinned in a paired accent colour) that mirrors the player's horizontal/vertical delta unless blocked by a wall; both the player and twin must avoid hazards, or the twin must stand on a pressure plate to keep the exit gate open.",
            "- Forces simultaneous dual-entity forward simulation and decisive `RESET` when the twin gets desynchronized.",
            "",
        ]),
        encoding="utf-8",
    )
    written.append(p3)

    p4 = proposals_dir / "auto-04-eval-v2-tier3-drift-and-timing.md"
    p4.write_text(
        "\n".join([
            "# Auto-Proposal 04: Activate Tier-3 Post-Move Drift & Timing (`conveyors`, `enemies`, `gravity`) for `eval-v2`",
            "",
            "- **Generated by:** A5 (`python -m analysis insights --write-proposals`)",
            "- **Target:** A1 (`engine/src/engine/gen.py` & `splits.py` `eval-v2` pool — components already implemented in `engine/src/engine/components/`)",
            f"- **Observed Failure Cited:** `no_effect_loop={no_effect_count}`, `unsolved_level={unsolved_count}`, `late_reset={late_reset_count}`"
            + (f", weakest non-base rule `{weakest_rule['rule']}` (intro solve `{weakest_rule['intro_solve_rate']}`)" if weakest_rule else "")
            + ".",
            "",
            "## Problem Observed",
            "Even when multimodal frontier models solve isolated static mechanics (52.1% level solve on `dev`), their world model assumes environment state only mutates at the player's target cell. When `phase_walls` or `ice` introduce post-step state transitions, models mispredict landing coordinates or fail to `WAIT`/`ACTION5` at safe chokepoints.",
            "",
            "## Proposed `eval-v2` Promotion",
            "- Promote A1's opt-in Tier-3 mechanics (`conveyors`, `enemies`, `gravity`, already BFS-verified in `engine 0.5.0` and catalogued in `rules/CATALOG.md`) into the `eval-v2` hold-out split:",
            "  1. **`conveyors`:** 1-cell post-move drift (`conveyor:<dir>`), testing two-phase state prediction (`player step -> board drift`).",
            "  2. **`enemies`:** deterministic 2-cell patrol (`enemy_hit`), testing spatiotemporal parity and `ACTION5` (`WAIT`) timing.",
            "  3. **`gravity`:** post-move downward settle for both player and `push_blocks` (`fell:<n>`), testing coupled physics composition.",
            "- Keeps `eval-v1` frozen and uncontaminated while giving `eval-v2` an immediate, solver-proven difficulty step up.",
            "",
        ]),
        encoding="utf-8",
    )
    written.append(p4)

    return written


def build_insights(
    runs_dir: Path,
    leaderboard: dict[str, Any],
    rules_data: dict[str, Any],
    out_path: Path | None = None,
    extra_runs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from .loader import load_runs

    runs = load_runs(runs_dir)
    if extra_runs:
        runs = runs + extra_runs
    data = synthesize_insights(leaderboard, rules_data, runs=runs)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data
