"""Post-training & reasoning-benchmark aggregation (`data/derived/bench_summary.json`, PLAN.md §3.2 & §3.3, A5-20).

Reads per-run outputs written by `bench/` (`<bench_dir>/<run>/{summary.json,items.jsonl}`),
computes paired item-level bootstrap 95% CIs vs `base` and vs `ctrl` (matching `bench/PROTOCOL.md` §5
and `FT_BENCHMARKS.md`), merges in-domain Qwen3.5-9B game evaluation rows (`eval-v1`, `eval-v2`, `probe-v1`),
and evaluates the pre-registered Honesty Claim Rule automatically.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Mapping

from .loader import now_iso

DEFAULT_RESAMPLES = 10_000
DEFAULT_SEED = 20261114

# Canonical row ordering from bench/PROTOCOL.md §2 & FT_BENCHMARKS.md
ROW_ORDER: dict[str, int] = {
    "base": 0,
    "sft-v1": 1,
    "ctrl": 2,
    "sft-ctrl": 2,
    "games": 3,
    "sft-games": 3,
    "mix": 4,
    "sft-mix": 4,
    "finalist": 5,
    "final": 5,
}

FT_BENCHMARKS_SUITE: list[dict[str, Any]] = [
    {"id": "bbh", "label": "BIG-Bench Hard (27 tasks)", "group": "primary", "setting": "3-shot CoT", "items": 6511},
    {"id": "math", "label": "MATH", "group": "primary", "setting": "0-shot CoT", "items": 5000},
    {"id": "gsm8k", "label": "GSM8K", "group": "primary", "setting": "8-shot CoT", "items": 1319},
    {"id": "medqa", "label": "MedQA-USMLE (4-opt)", "group": "primary", "setting": "0-shot", "items": 1273},
    {"id": "mmlu_pro_health", "label": "MMLU-Pro: Health", "group": "primary", "setting": "5-shot CoT", "items": None},
    {"id": "mmlu_pro_law", "label": "MMLU-Pro: Law", "group": "primary", "setting": "5-shot CoT", "items": None},
    {"id": "mmlu_pro_history", "label": "MMLU-Pro: History (Negative Ctrl)", "group": "negative_control", "setting": "5-shot CoT", "items": None},
    {"id": "bbh_tracking_shuffled_objects", "label": "BBH: Tracking Shuffled Objects", "group": "bbh_logic_secondary", "setting": "3-shot CoT", "items": None},
    {"id": "bbh_navigate", "label": "BBH: Navigate", "group": "bbh_logic_secondary", "setting": "3-shot CoT", "items": None},
    {"id": "bbh_logical_deduction", "label": "BBH: Logical Deduction", "group": "bbh_logic_secondary", "setting": "3-shot CoT", "items": None},
    {"id": "bbh_web_of_lies", "label": "BBH: Web of Lies", "group": "bbh_logic_secondary", "setting": "3-shot CoT", "items": None},
    {"id": "bbh_temporal_sequences", "label": "BBH: Temporal Sequences", "group": "bbh_logic_secondary", "setting": "3-shot CoT", "items": None},
]

BBH_SUBSET_NAMES: tuple[str, ...] = (
    "tracking_shuffled_objects",
    "navigate",
    "logical_deduction",
    "web_of_lies",
    "temporal_sequences",
)


def _quantile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return float("nan")
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def paired_delta_ci(
    ref_items: Mapping[str, float],
    cand_items: Mapping[str, float],
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Exact paired item-level bootstrap of mean(cand - ref) matching `bench.stats.paired_delta`."""
    shared = sorted(set(ref_items) & set(cand_items))
    diffs = [float(cand_items[k]) - float(ref_items[k]) for k in shared]
    n = len(diffs)
    meta = {
        "n_shared": n,
        "n_only_ref": len(set(ref_items) - set(cand_items)),
        "n_only_cand": len(set(cand_items) - set(ref_items)),
    }
    if n == 0:
        return {**meta, "delta": None, "ci_low": None, "ci_high": None, "excludes_zero": False, "mean_ref": None, "mean_cand": None}
    rng = random.Random(seed)
    d = sum(diffs) / n
    boots = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(resamples))
    lo = _quantile(boots, alpha / 2)
    hi = _quantile(boots, 1 - alpha / 2)
    return {
        **meta,
        "delta": round(d, 6),
        "ci_low": round(lo, 6),
        "ci_high": round(hi, 6),
        "excludes_zero": bool(lo > 0 or hi < 0),
        "mean_ref": round(sum(float(ref_items[k]) for k in shared) / n, 6),
        "mean_cand": round(sum(float(cand_items[k]) for k in shared) / n, 6),
    }


def _classify_benchmark_tier(bench_id: str, raw_tier: str | None) -> str:
    """Normalize benchmark tier across FT_BENCHMARKS.md and bench/PROTOCOL.md v1/v2."""
    bid = bench_id.lower()
    if "history" in bid or raw_tier == "negative_control":
        return "negative_control"
    if raw_tier in ("primary", "logical", "near_transfer", "guard", "bbh_logic_secondary", "secondary_reasoning_gym"):
        return raw_tier
    if any(k in bid for k in ("tracking_shuffled", "navigate", "logical_deduction", "web_of_lies", "temporal_sequences")):
        if bid.startswith("bbh_"):
            return "bbh_logic_secondary"
    if bid.startswith("rg_"):
        return "secondary_reasoning_gym"
    if any(k in bid for k in ("bbh", "math", "gsm8k", "medqa", "mmlu_pro_health", "mmlu_pro_law")):
        return "primary"
    return raw_tier or "primary"


def _normalize_row_id(name: str) -> str:
    n = name.strip().lower()
    aliases = {
        "sft-ctrl": "ctrl",
        "sft_ctrl": "ctrl",
        "control": "ctrl",
        "sft-games": "games",
        "sft_games": "games",
        "sft-mix": "mix",
        "sft_mix": "mix",
        "sft_v1": "sft-v1",
        "sftv1": "sft-v1",
        "base-dev": "base-dev",
    }
    return aliases.get(n, n)


def _load_bench_run_dir(run_dir: Path) -> dict[str, Any] | None:
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        return None
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    items_by_bench: dict[str, dict[str, float]] = {}
    items_path = run_dir / "items.jsonl"
    if items_path.exists():
        for line in items_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                it = json.loads(line)
                b = "medqa" if str(it["bench"]) == "medqa_4options" else str(it["bench"])
                item_id = str(it["item"])
                sc = float(it["score"])
                items_by_bench.setdefault(b, {})[item_id] = sc
                if b == "bbh":
                    subtask = str(it.get("subtask") or item_id)
                    for sub_name in BBH_SUBSET_NAMES:
                        if sub_name in subtask:
                            items_by_bench.setdefault(f"bbh_{sub_name}", {})[item_id] = sc
            except (KeyError, ValueError, json.JSONDecodeError):
                continue

    raw_name = str(summary.get("name") or run_dir.name)
    row_id = _normalize_row_id(raw_name)
    benches_out: dict[str, dict[str, Any]] = {}
    for raw_b_id, b_info in (summary.get("benchmarks") or {}).items():
        if not isinstance(b_info, dict):
            continue
        b_id = "medqa" if raw_b_id == "medqa_4options" else raw_b_id
        tier = _classify_benchmark_tier(b_id, b_info.get("tier"))
        benches_out[b_id] = {
            "tier": tier,
            "n": int(b_info.get("n") or 0),
            "mean": round(float(b_info["mean"]), 6) if b_info.get("mean") is not None else None,
            "ci_low": round(float(b_info["ci_low"]), 6) if b_info.get("ci_low") is not None else None,
            "ci_high": round(float(b_info["ci_high"]), 6) if b_info.get("ci_high") is not None else None,
            "truncated": int(b_info.get("truncated") or 0),
        }

    # Include pre-declared BBH subsets written by bench/run.py under summary["subsets"]["bbh_subset"]
    bbh_subsets = (summary.get("subsets") or {}).get("bbh_subset") or {}
    for sub_name, sub_info in bbh_subsets.items():
        if not isinstance(sub_info, dict):
            continue
        sub_id = sub_name if sub_name.startswith("bbh_") else f"bbh_{sub_name}"
        if sub_id not in benches_out:
            benches_out[sub_id] = {
                "tier": "bbh_logic_secondary",
                "n": int(sub_info.get("n") or 0),
                "mean": round(float(sub_info["mean"]), 6) if sub_info.get("mean") is not None else None,
                "ci_low": round(float(sub_info["ci_low"]), 6) if sub_info.get("ci_low") is not None else None,
                "ci_high": round(float(sub_info["ci_high"]), 6) if sub_info.get("ci_high") is not None else None,
                "truncated": 0,
            }

    # Unweighted tier means
    tiers_map: dict[str, list[float]] = {}
    for b_info in benches_out.values():
        if b_info["mean"] is not None:
            tiers_map.setdefault(b_info["tier"], []).append(float(b_info["mean"]))
    tier_means = {
        t: {"benchmarks": len(vals), "mean": round(sum(vals) / len(vals), 6)}
        for t, vals in sorted(tiers_map.items())
        if vals
    }

    return {
        "row_id": row_id,
        "raw_name": raw_name,
        "model": summary.get("model"),
        "lora": summary.get("lora"),
        "dev_slice": bool(summary.get("dev_slice", False)),
        "config_hash": summary.get("config_hash"),
        "created_at": summary.get("started_at") or summary.get("created_at") or summary.get("finished_at"),
        "benchmarks": benches_out,
        "tier_means": tier_means,
        "_items": items_by_bench,
    }


def _compute_comparison(ref_run: dict[str, Any], cand_run: dict[str, Any], resamples: int) -> dict[str, Any]:
    ref_items: dict[str, dict[str, float]] = ref_run["_items"]
    cand_items: dict[str, dict[str, float]] = cand_run["_items"]
    all_benches = sorted(set(ref_run["benchmarks"]) | set(cand_run["benchmarks"]))
    per_bench: dict[str, dict[str, Any]] = {}

    for b in all_benches:
        r_meta = ref_run["benchmarks"].get(b, {})
        c_meta = cand_run["benchmarks"].get(b, {})
        tier = c_meta.get("tier") or r_meta.get("tier") or _classify_benchmark_tier(b, None)
        if b in ref_items and b in cand_items and ref_items[b] and cand_items[b]:
            d = paired_delta_ci(ref_items[b], cand_items[b], resamples=resamples)
        elif r_meta.get("mean") is not None and c_meta.get("mean") is not None:
            # Summary-only fallback when items.jsonl was not copied
            diff = round(float(c_meta["mean"]) - float(r_meta["mean"]), 6)
            d = {
                "n_shared": min(int(r_meta.get("n") or 0), int(c_meta.get("n") or 0)),
                "n_only_ref": 0,
                "n_only_cand": 0,
                "delta": diff,
                "ci_low": None,
                "ci_high": None,
                "excludes_zero": False,
                "mean_ref": r_meta["mean"],
                "mean_cand": c_meta["mean"],
            }
        else:
            d = {
                "n_shared": 0,
                "n_only_ref": 0,
                "n_only_cand": 0,
                "delta": None,
                "ci_low": None,
                "ci_high": None,
                "excludes_zero": False,
                "mean_ref": r_meta.get("mean"),
                "mean_cand": c_meta.get("mean"),
            }
        per_bench[b] = {
            "tier": tier,
            "truncated_ref": r_meta.get("truncated", 0),
            "truncated_cand": c_meta.get("truncated", 0),
            **d,
        }

    tier_deltas: dict[str, dict[str, Any]] = {}
    tiers_present = sorted({info["tier"] for info in per_bench.values() if info.get("tier")})
    for t in tiers_present:
        ds = [info["delta"] for info in per_bench.values() if info["tier"] == t and info["delta"] is not None]
        sig_pos = sum(
            1 for info in per_bench.values()
            if info["tier"] == t and info["delta"] is not None and info["delta"] > 0 and info["excludes_zero"]
        )
        sig_neg = sum(
            1 for info in per_bench.values()
            if info["tier"] == t and info["delta"] is not None and info["delta"] < 0 and info["excludes_zero"]
        )
        tier_deltas[t] = {
            "benchmarks": len(ds),
            "mean_delta": round(sum(ds) / len(ds), 6) if ds else None,
            "sig_positive": sig_pos,
            "sig_negative": sig_neg,
        }

    return {
        "ref": ref_run["row_id"],
        "cand": cand_run["row_id"],
        "config_hash_match": ref_run.get("config_hash") == cand_run.get("config_hash"),
        "benchmarks": per_bench,
        "tiers": tier_deltas,
    }


def _extract_in_domain_game_rows(
    lb_h1: dict[str, Any],
    lb_h2: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Extract Qwen3.5-9B base vs fine-tuned game-benchmark rows across h1 and h2."""
    rows_out: list[dict[str, Any]] = []
    for harness_label, board in (("h1", lb_h1), ("h2", lb_h2 or {"rows": []})):
        for r in board.get("rows") or []:
            pid = str(r.get("player_id") or "")
            tier = str(r.get("tier") or "")
            is_qwen_or_ft = (
                "qwen" in pid.lower()
                or "-ft-" in pid.lower()
                or tier == "finetuned"
            )
            if not is_qwen_or_ft:
                continue
            role = "sft-v1" if ("ft" in pid.lower() or tier == "finetuned") else "base"
            rows_out.append({
                "role": role,
                "player_id": pid,
                "display_name": r.get("display_name") or pid,
                "collection": r.get("collection"),
                "harness_version": r.get("harness_version") or harness_label,
                "games": r.get("games", 0),
                "levels_solved": r.get("levels_solved", 0),
                "levels_attempted": r.get("levels_attempted", 0),
                "level_solve_rate": r.get("level_solve_rate", 0.0),
                "score": r.get("score", 0.0),
                "score_ci_low": r.get("score_ci_low"),
                "score_ci_high": r.get("score_ci_high"),
                "probe_score": r.get("probe_score"),
                "no_effect_rate": r.get("no_effect_rate"),
            })
    return rows_out


def _evaluate_honesty_rule(
    runs_by_id: dict[str, dict[str, Any]],
    comparisons_vs_ctrl: list[dict[str, Any]],
    comparisons_vs_base: list[dict[str, Any]],
    in_domain_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Evaluate PLAN.md §3.3 + bench/PROTOCOL.md §6 + FT_BENCHMARKS.md honesty claim rule."""
    if not runs_by_id or ("ctrl" not in runs_by_id and len(comparisons_vs_base) == 0):
        sft_v1_eval = next(
            (r for r in in_domain_rows if r["role"] == "sft-v1" and r["collection"] == "eval-v1"),
            None,
        )
        in_dom_note = (
            f"SFT v1 (`{sft_v1_eval['player_id']}`, pure optimal-action cloning on train-v1) solved "
            f"{sft_v1_eval['levels_solved']}/{sft_v1_eval['levels_attempted']} levels on held-out eval-v1 "
            f"(score {sft_v1_eval['score']:.3f}), confirming PLAN §3.3 Step 0: action-only SFT learns output syntax, not causal discovery."
            if sft_v1_eval
            else "SFT v1 action-cloning baseline evaluated; awaiting SFT v2 (`ctrl` / `games` / `mix`) + `FT_BENCHMARKS.md` runs."
        )
        return {
            "status": "pending_bench_runs",
            "transfer_shown": False,
            "winning_candidate": None,
            "headline": "Pre-registered benchmark protocol locked; outside-benchmark GPU runs in flight.",
            "detail": in_dom_note,
        }

    # Check candidates (`games`, `mix`, `finalist`, `rl-*`) against `ctrl`
    vs_base_by_cand = {c["cand"]: c for c in comparisons_vs_base}
    best_winner: dict[str, Any] | None = None

    for comp in comparisons_vs_ctrl:
        cand = comp["cand"]
        if cand in ("base", "sft-v1", "ctrl"):
            continue
        # Target tier: `primary` (FT_BENCHMARKS.md) if present, else `logical` (PROTOCOL.md v1)
        target_tier = "primary" if "primary" in comp["tiers"] else ("logical" if "logical" in comp["tiers"] else None)
        if not target_tier:
            continue
        t_info = comp["tiers"][target_tier]
        mean_d = t_info.get("mean_delta")
        sig_pos = int(t_info.get("sig_positive") or 0)

        # Negative control (`mmlu_pro_history` must not rise as much as primary suite)
        neg_ctrl_d = (comp["tiers"].get("negative_control") or {}).get("mean_delta")
        neg_ctrl_ok = True
        if neg_ctrl_d is not None and mean_d is not None and mean_d > 0 and neg_ctrl_d >= mean_d:
            neg_ctrl_ok = False

        # Guard tier vs base: no guard benchmark drops > 2 points (-0.02) with CI excluding zero
        guard_ok = True
        base_comp = vs_base_by_cand.get(cand)
        if base_comp:
            for b_info in base_comp["benchmarks"].values():
                if b_info["tier"] == "guard" and b_info["delta"] is not None:
                    if b_info["delta"] < -0.02 and b_info["excludes_zero"]:
                        guard_ok = False
                        break

        if mean_d is not None and mean_d > 0 and sig_pos >= 2 and neg_ctrl_ok and guard_ok:
            if best_winner is None or mean_d > best_winner["mean_delta"]:
                best_winner = {
                    "cand": cand,
                    "target_tier": target_tier,
                    "mean_delta": mean_d,
                    "sig_positive": sig_pos,
                    "neg_ctrl_delta": neg_ctrl_d,
                }

    if best_winner is not None:
        return {
            "status": "transfer_supported",
            "transfer_shown": True,
            "winning_candidate": best_winner["cand"],
            "headline": (
                f"Transfer supported: `{best_winner['cand']}` beats equal-token `ctrl` by "
                f"{best_winner['mean_delta']:+.3f} across `{best_winner['target_tier']}` "
                f"({best_winner['sig_positive']} benchmarks with 95% CI > 0; negative control & guard passed)."
            ),
            "detail": "Satisfies the pre-registered PLAN.md §3.3 / bench/PROTOCOL.md §6 claim rule.",
        }

    return {
        "status": "null_transfer_in_domain_only",
        "transfer_shown": False,
        "winning_candidate": None,
        "headline": "Honesty rule: outside-benchmark gain over equal-token `ctrl` did not clear the 95% CI threshold.",
        "detail": (
            "Per PLAN.md §3.3, no trained candidate beat `ctrl` on >=2 target reasoning benchmarks with 95% CIs "
            "excluding zero without formatting/guard regressions. Reporting exact deltas and in-domain game results plainly."
        ),
    }


def build_bench_summary(
    bench_dir: Path | None,
    lb_h1: dict[str, Any],
    lb_h2: dict[str, Any] | None = None,
    resamples: int = DEFAULT_RESAMPLES,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Aggregate all bench runs + in-domain Qwen3.5-9B game results into `bench_summary.json`."""
    loaded_runs: list[dict[str, Any]] = []
    if bench_dir is not None and bench_dir.exists():
        for child in sorted(bench_dir.iterdir()):
            if child.is_dir():
                parsed = _load_bench_run_dir(child)
                if parsed is not None:
                    loaded_runs.append(parsed)

    loaded_runs.sort(key=lambda r: (ROW_ORDER.get(r["row_id"], 50), r["row_id"]))
    runs_by_id = {r["row_id"]: r for r in loaded_runs if not r["dev_slice"]}

    comparisons_vs_base: list[dict[str, Any]] = []
    comparisons_vs_ctrl: list[dict[str, Any]] = []

    base_run = runs_by_id.get("base")
    ctrl_run = runs_by_id.get("ctrl")

    for r in loaded_runs:
        if r["dev_slice"]:
            continue
        if base_run is not None and r["row_id"] != "base":
            comparisons_vs_base.append(_compute_comparison(base_run, r, resamples=resamples))
        if ctrl_run is not None and r["row_id"] not in ("base", "ctrl"):
            comparisons_vs_ctrl.append(_compute_comparison(ctrl_run, r, resamples=resamples))

    in_domain_rows = _extract_in_domain_game_rows(lb_h1, lb_h2)
    claim_eval = _evaluate_honesty_rule(runs_by_id, comparisons_vs_ctrl, comparisons_vs_base, in_domain_rows)

    public_runs = [
        {k: v for k, v in r.items() if k != "_items"}
        for r in loaded_runs
    ]

    return {
        "generated_at": generated_at or now_iso(),
        "protocol_version": "ft-benchmarks-v1",
        "bootstrap_resamples": resamples,
        "bootstrap_seed": DEFAULT_SEED,
        "suite_definition": FT_BENCHMARKS_SUITE,
        "claim_evaluation": claim_eval,
        "in_domain_games": in_domain_rows,
        "runs": public_runs,
        "comparisons_vs_base": comparisons_vs_base,
        "comparisons_vs_ctrl": comparisons_vs_ctrl,
    }
