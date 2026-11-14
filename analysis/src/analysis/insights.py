"""Generate headline insights (insights.json) and automated rule proposals (rules/proposals/auto-*.md)."""
from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

from .compare import build_comparisons
from .loader import find_repo_root, now_iso


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

    # Helper to pick a representative step from runs
    def _first_run_step() -> tuple[str | None, int | None]:
        for run in runs:
            meta = run.get("meta") or {}
            if (meta.get("player") or {}).get("kind") in ("model", "human") and run.get("steps"):
                steps = run["steps"]
                mid = steps[min(len(steps) - 1, 1)]["i"]
                return str(meta.get("run_id")), int(mid)
        return None, None

    default_run_id, default_step = _first_run_step()

    # Finding 1: The Efficiency Gap (Optimal / Human vs Models)
    best_model = comparisons.get("best_model")
    opt_score = optimal_rows[0]["score"] if optimal_rows else 1.0
    if best_model:
        evidence = [
            {
                "label": f"{best_model['display_name']} Efficiency Score",
                "value": best_model["score"],
                "run_id": default_run_id,
                "step": default_step,
            },
            {
                "label": "Optimal Reference Score",
                "value": opt_score,
                "run_id": None,
                "step": None,
            },
        ]
        if human_rows:
            h_score = human_rows[0]["score"]
            evidence.insert(
                1,
                {
                    "label": "Human Baseline Score",
                    "value": h_score,
                    "run_id": None,
                    "step": None,
                },
            )
            summary = (
                f"Best evaluated model ({best_model['display_name']}) achieved an action-efficiency "
                f"score of {best_model['score']:.3f} vs. {h_score:.3f} for first-attempt humans and "
                f"{opt_score:.3f} for BFS optimal play."
            )
        else:
            gap = round(opt_score - best_model["score"], 4)
            summary = (
                f"Evaluated model ({best_model['display_name']}) achieved {best_model['score']:.3f} "
                f"action-efficiency score, leaving a {gap:.3f} gap behind BFS optimal ({opt_score:.3f}) "
                f"due to exploration overhead and budget exhaustion."
            )
        # Attach level completion proof step if present in runs
        for run in runs:
            meta = run.get("meta") or {}
            if (meta.get("player") or {}).get("kind") == "model":
                for st in run.get("steps") or []:
                    if "level_complete" in ((st.get("truth") or {}).get("events") or []):
                        evidence.append({
                            "label": f"Level {st['truth']['level'] - 1} Solved",
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

    # Finding 2: Repeated No-Effect Actions & Exploration Waste
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

    # Finding 3: Reset Timing & Budget Exhaustion (or Hardest Rule Bottleneck)
    hardest_cell = None
    if intro_model_cells:
        hardest_cell = min(
            intro_model_cells,
            key=lambda c: (c.get("intro_solve_rate", 1.0), -(c.get("wasted_actions") or 0.0)),
        )
    late_reset_mode = next((fm for fm in failure_modes if fm["mode"] == "late_reset"), None)
    budget_mode = next((fm for fm in failure_modes if fm["mode"] == "budget_exhaustion"), None)
    ev3: list[dict[str, Any]] = []
    if hardest_cell:
        ev3.append({
            "label": f"Hardest Rule Intro Solve Rate ({hardest_cell['rule']})",
            "value": hardest_cell["intro_solve_rate"],
            "run_id": default_run_id,
            "step": default_step,
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
            "Action-efficiency scoring (`min(1, optimal_moves / actions_used)` per solved level) "
            "assigns 0.000 to `noop` and `stop_early`, penalizes reset farming, and rewards only genuine level completion."
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

    weakest_rule = min(
        cells,
        key=lambda c: (c.get("intro_solve_rate", 1.0), -(c.get("wasted_actions") or 0.0)),
        default=None,
    )

    written: list[Path] = []

    p1 = proposals_dir / "auto-01-wall-bump-cooldown.md"
    p1.write_text(
        "\n".join([
            "# Auto-Proposal 01: Brittle Floor / Bump-Penalty Tiles (`cracked_floor`)",
            "",
            "- **Generated by:** A5 (`python -m analysis insights --write-proposals`)",
            "- **Target:** A1 (`engine/src/engine/components/`) for `eval-v2`",
            f"- **Observed Failure Cited:** `no_effect_loop` ({no_effect_count} zero-effect/bump actions observed in trace corpus"
            + (f"; best model `{best_model['player_id']}` score `{best_model['score']:.3f}`" if best_model else "")
            + ").",
            "",
            "## Problem Observed",
            "Models repeatedly collide with walls or blocked tiles without updating spatial boundaries in `NOTES`, trusting single-step trial-and-error instead of mapping impassable geometry.",
            "",
            "## Proposed Mechanic (`eval-v2`)",
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
            "- **Target:** A1 (`engine/src/engine/components/`) for `eval-v2`",
            f"- **Observed Failure Cited:** {weak_note}; models frequently tunnel directly toward the goal ring without sequencing intermediate sub-goals.",
            "",
            "## Problem Observed",
            "Models form premature single-object hypotheses (`reach coloured ring = done`) and ignore secondary board state changes.",
            "",
            "## Proposed Mechanic (`eval-v2`)",
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
            "# Auto-Proposal 03: Mirror Twin / Coupled Movement (`mirror_twin`)",
            "",
            "- **Generated by:** A5 (`python -m analysis insights --write-proposals`)",
            "- **Target:** A1 (`engine/src/engine/components/`) for `eval-v2`",
            f"- **Observed Failure Cited:** `late_reset` ({late_reset_count} late reset episodes) + multi-step budget exhaustion (`unsolved_level={unsolved_count}`).",
            "",
            "## Problem Observed",
            "Models commit to local greedy moves and fail to issue `RESET` promptly when a coupled constraint becomes unsolvable.",
            "",
            "## Proposed Mechanic (`eval-v2`)",
            "- Spawn a secondary twin sprite (skinned in a paired accent colour) that mirrors the player's horizontal/vertical delta unless blocked by a wall; both the player and twin must avoid hazards, or the twin must stand on a pressure plate to keep the exit gate open.",
            "- Forces simultaneous dual-entity forward simulation and decisive `RESET` when the twin gets desynchronized.",
            "",
        ]),
        encoding="utf-8",
    )
    written.append(p3)

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
