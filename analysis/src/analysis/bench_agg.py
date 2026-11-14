"""Post-training & reasoning-benchmark aggregation (`data/derived/bench_summary.json`, PLAN.md §3.2 & §3.3, A5-20).

Implements `bench/PROTOCOL.md` v3 + `FT_BENCHMARKS.md` + `DECISIONS.md` (Sat 20:50 & 21:15):
- Reads `<bench_dir>/<run>/{summary.json,items.jsonl}` and automatically prefers canonical PROTOCOL v3
  rescored files (`items_v3.jsonl`, `summary_v3.json` from `python -m posttrain.rescore_answer`, which
  accepts `"ANSWER: X"` on `[invalid]` lm-eval extractions while changing 0 items on `base`), keeping
  official lm-eval means alongside v3 means (`official_mean`, `rescored_count`) for full transparency.
- Supports both Line 1 (no-thinking SFT v2 `ctrl`/`games`/`mix` + `rl-grpo-*`, documented negative result
  showing CoT suppression drops Qwen3.5-9B from ~0.76 to ~0.44) and Line 2 (`DECISIONS.md` Sat 21:15
  Thinking-On GRPO from base: `think-games` vs `think-ctrl` on shared dev-slice items).
- Computes paired item-level bootstrap 95% CIs (`10,000` resamples, seed `20261114`) over exact shared item IDs,
  merges in-domain Qwen3.5-9B game evaluation rows, and evaluates the pre-registered Honesty Claim Rule.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Mapping

from .loader import now_iso

DEFAULT_RESAMPLES = 10_000
DEFAULT_SEED = 20261114

# Canonical row ordering across PROTOCOL v3 + Thinking-On RL re-plan
ROW_ORDER: dict[str, int] = {
    "base": 0,
    "think-ctrl": 1,
    "think-games": 2,
    "finalist": 3,
    "final": 3,
    "ctrl": 4,
    "sft-ctrl": 4,
    "games": 5,
    "sft-games": 5,
    "mix": 6,
    "sft-mix": 6,
    "rl-nothink": 7,
    "sft-v1": 8,
    "games-dev": 9,
}

RL_FAMILY_PREFIXES: tuple[tuple[str, str], ...] = (
    ("think-games", "rl-think-games-"),
    ("think-ctrl", "rl-think-ctrl-"),
    ("rl-nothink", "rl-grpo-"),
)

FT_BENCHMARKS_SUITE: list[dict[str, Any]] = [
    {"id": "bbh", "label": "BIG-Bench Hard (27 tasks)", "group": "primary", "setting": "3-shot CoT", "items": 1350},
    {"id": "math", "label": "MATH", "group": "primary", "setting": "0-shot CoT", "items": 350},
    {"id": "gsm8k", "label": "GSM8K", "group": "primary", "setting": "8-shot CoT", "items": 250},
    {"id": "medqa", "label": "MedQA-USMLE (4-opt)", "group": "primary", "setting": "0-shot", "items": 1273},
    {"id": "mmlu_pro_health", "label": "MMLU-Pro: Health", "group": "primary", "setting": "5-shot CoT", "items": 100},
    {"id": "mmlu_pro_law", "label": "MMLU-Pro: Law", "group": "primary", "setting": "5-shot CoT", "items": 100},
    {"id": "mmlu_pro_history", "label": "MMLU-Pro: History (Negative Ctrl)", "group": "negative_control", "setting": "5-shot CoT", "items": 100},
    {"id": "bbh_tracking_shuffled_objects", "label": "BBH: Tracking Shuffled Objects", "group": "bbh_logic_secondary", "setting": "3-shot CoT", "items": 50},
    {"id": "bbh_navigate", "label": "BBH: Navigate", "group": "bbh_logic_secondary", "setting": "3-shot CoT", "items": 50},
    {"id": "bbh_logical_deduction", "label": "BBH: Logical Deduction", "group": "bbh_logic_secondary", "setting": "3-shot CoT", "items": 50},
    {"id": "bbh_web_of_lies", "label": "BBH: Web of Lies", "group": "bbh_logic_secondary", "items": 50, "setting": "3-shot CoT"},
    {"id": "bbh_temporal_sequences", "label": "BBH: Temporal Sequences", "group": "bbh_logic_secondary", "setting": "3-shot CoT", "items": 50},
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


def mean_bootstrap_ci(
    values: list[float],
    resamples: int = 2_000,
    seed: int = DEFAULT_SEED,
    alpha: float = 0.05,
) -> tuple[float | None, float | None, float | None]:
    """Deterministic item-level bootstrap mean and 95% CI."""
    n = len(values)
    if n == 0:
        return None, None, None
    mean_v = sum(values) / n
    if n == 1 or resamples <= 0:
        return round(mean_v, 6), round(mean_v, 6), round(mean_v, 6)
    rng = random.Random(seed)
    boots = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(resamples))
    return (
        round(mean_v, 6),
        round(_quantile(boots, alpha / 2), 6),
        round(_quantile(boots, 1 - alpha / 2), 6),
    )


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
    """Normalize benchmark tier across FT_BENCHMARKS.md and bench/PROTOCOL.md v1-v3."""
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
        "sft-games-dev-merged": "games-dev",
        "sft-mix": "mix",
        "sft_mix": "mix",
        "sft_v1": "sft-v1",
        "sftv1": "sft-v1",
        "think_games": "think-games",
        "think_ctrl": "think-ctrl",
        "base-dev": "base-dev",
    }
    return aliases.get(n, n)


def _parse_items_jsonl(path: Path) -> dict[str, dict[str, float]]:
    items_by_bench: dict[str, dict[str, float]] = {}
    if not path.exists():
        return items_by_bench
    for line in path.read_text(encoding="utf-8").splitlines():
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
    return items_by_bench


def _compute_tier_means(benches: Mapping[str, Mapping[str, Any]], field: str = "mean") -> dict[str, dict[str, Any]]:
    tiers_map: dict[str, list[float]] = {}
    for b_info in benches.values():
        val = b_info.get(field)
        if val is not None:
            tiers_map.setdefault(str(b_info["tier"]), []).append(float(val))
    return {
        t: {"benchmarks": len(vals), "mean": round(sum(vals) / len(vals), 6)}
        for t, vals in sorted(tiers_map.items())
        if vals
    }


def _load_bench_run_dir(run_dir: Path, ci_resamples: int = 2_000) -> dict[str, Any] | None:
    summary_path = run_dir / "summary.json"
    summary_v3_path = run_dir / "summary_v3.json"
    if not summary_path.exists() and not summary_v3_path.exists():
        return None

    summary: dict[str, Any] = {}
    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            if not summary_v3_path.exists():
                return None

    summary_v3: dict[str, Any] | None = None
    if summary_v3_path.exists():
        try:
            summary_v3 = json.loads(summary_v3_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            summary_v3 = None

    items_v3_path = run_dir / "items_v3.jsonl"
    items_orig_path = run_dir / "items.jsonl"
    use_v3 = items_v3_path.exists() or summary_v3 is not None
    scoring_mode = "v3" if use_v3 else "official"

    items_by_bench = _parse_items_jsonl(items_v3_path if items_v3_path.exists() else items_orig_path)
    orig_items_by_bench = _parse_items_jsonl(items_orig_path) if (use_v3 and items_orig_path.exists()) else items_by_bench
    changed_items = (summary_v3 or {}).get("changed_items") or {}

    raw_name = str(summary.get("name") or (summary_v3 or {}).get("run") or run_dir.name)
    row_id = _normalize_row_id(raw_name)

    orig_benches_raw = summary.get("benchmarks") or {}
    v3_benches_raw = (summary_v3 or {}).get("benchmarks") or {}
    all_raw_keys = sorted(set(orig_benches_raw) | set(v3_benches_raw) | set(items_by_bench))

    benches_out: dict[str, dict[str, Any]] = {}
    for raw_b_id in all_raw_keys:
        b_id = "medqa" if raw_b_id == "medqa_4options" else raw_b_id
        orig_info = orig_benches_raw.get(raw_b_id) or orig_benches_raw.get(b_id) or {}
        v3_info = v3_benches_raw.get(raw_b_id) or v3_benches_raw.get(b_id) or {}
        if not isinstance(orig_info, dict):
            orig_info = {}
        if not isinstance(v3_info, dict):
            v3_info = {}

        tier = _classify_benchmark_tier(b_id, orig_info.get("tier"))
        official_mean: float | None = None
        if orig_info.get("mean") is not None:
            official_mean = round(float(orig_info["mean"]), 6)
        elif b_id in orig_items_by_bench and orig_items_by_bench[b_id]:
            vals_orig = list(orig_items_by_bench[b_id].values())
            official_mean = round(sum(vals_orig) / len(vals_orig), 6)

        if use_v3 and b_id in items_by_bench and items_by_bench[b_id]:
            vals_v3 = list(items_by_bench[b_id].values())
            mean_v, lo_v, hi_v = mean_bootstrap_ci(vals_v3, resamples=ci_resamples)
            n_items = len(vals_v3)
        elif use_v3 and v3_info.get("mean") is not None:
            mean_v = round(float(v3_info["mean"]), 6)
            lo_v = round(float(v3_info["ci_low"]), 6) if v3_info.get("ci_low") is not None else None
            hi_v = round(float(v3_info["ci_high"]), 6) if v3_info.get("ci_high") is not None else None
            n_items = int(v3_info.get("n") or orig_info.get("n") or 0)
        elif orig_info:
            mean_v = official_mean
            lo_v = round(float(orig_info["ci_low"]), 6) if orig_info.get("ci_low") is not None else None
            hi_v = round(float(orig_info["ci_high"]), 6) if orig_info.get("ci_high") is not None else None
            n_items = int(orig_info.get("n") or 0)
        elif b_id in items_by_bench and items_by_bench[b_id]:
            vals = list(items_by_bench[b_id].values())
            mean_v, lo_v, hi_v = mean_bootstrap_ci(vals, resamples=ci_resamples)
            n_items = len(vals)
            official_mean = mean_v
        else:
            continue

        benches_out[b_id] = {
            "tier": tier,
            "n": n_items,
            "mean": mean_v,
            "official_mean": official_mean,
            "rescored_count": int(changed_items.get(b_id) or changed_items.get(raw_b_id) or 0),
            "ci_low": lo_v,
            "ci_high": hi_v,
            "truncated": int(orig_info.get("truncated") or 0),
        }

    # Include pre-declared BBH subsets from summary["subsets"]["bbh_subset"] if not already sliced from items
    bbh_subsets = (summary.get("subsets") or {}).get("bbh_subset") or {}
    for sub_name, sub_info in bbh_subsets.items():
        if not isinstance(sub_info, dict):
            continue
        sub_id = sub_name if sub_name.startswith("bbh_") else f"bbh_{sub_name}"
        off_sub_mean = round(float(sub_info["mean"]), 6) if sub_info.get("mean") is not None else None
        if sub_id in benches_out:
            if benches_out[sub_id].get("official_mean") is None:
                benches_out[sub_id]["official_mean"] = off_sub_mean
            continue
        benches_out[sub_id] = {
            "tier": "bbh_logic_secondary",
            "n": int(sub_info.get("n") or 0),
            "mean": off_sub_mean,
            "official_mean": off_sub_mean,
            "rescored_count": 0,
            "ci_low": round(float(sub_info["ci_low"]), 6) if sub_info.get("ci_low") is not None else None,
            "ci_high": round(float(sub_info["ci_high"]), 6) if sub_info.get("ci_high") is not None else None,
            "truncated": 0,
        }

    tier_means = _compute_tier_means(benches_out, field="mean")
    official_tier_means = _compute_tier_means(benches_out, field="official_mean")

    # Detect dev_slice either from summary flag, directory naming, or BBH item count (dev slice = 25*27 = 675 vs full 1350)
    bbh_n = (benches_out.get("bbh") or {}).get("n", 0)
    inferred_dev_slice = bool(
        summary.get("dev_slice", False)
        or "dev" in raw_name.lower()
        or raw_name.lower().startswith("rl-")
        or (0 < bbh_n <= 700 and sum(x.get("n", 0) for x in benches_out.values() if x["tier"] == "primary") <= 1100)
    )

    return {
        "row_id": row_id,
        "raw_name": raw_name,
        "model": summary.get("model") or "Qwen/Qwen3.5-9B",
        "lora": summary.get("lora"),
        "dev_slice": inferred_dev_slice,
        "is_checkpoint": False,
        "scoring_mode": scoring_mode,
        "rescored_total": int(sum(int(v) for v in changed_items.values())) if changed_items else 0,
        "config_hash": summary.get("config_hash"),
        "created_at": summary.get("started_at") or summary.get("created_at") or summary.get("finished_at"),
        "benchmarks": benches_out,
        "tier_means": tier_means,
        "official_tier_means": official_tier_means,
        "_items": items_by_bench,
    }


def _primary_headline(run: Mapping[str, Any]) -> float:
    p = (run.get("tier_means") or {}).get("primary") or {}
    if p.get("mean") is not None:
        return float(p["mean"])
    l = (run.get("tier_means") or {}).get("logical") or {}
    if l.get("mean") is not None:
        return float(l["mean"])
    return -1.0


def _promote_canonical_families(loaded_runs: list[dict[str, Any]]) -> None:
    """Promote best checkpoint per RL family (`think-games`, `think-ctrl`, `rl-nothink`) and resolve `games-dev`."""
    existing_ids = {r["row_id"] for r in loaded_runs}

    # If `sft-games-dev-merged` (`games-dev`) is present and full `games` is NOT yet present, promote it to `games`
    if "games" not in existing_ids:
        for r in loaded_runs:
            if r["row_id"] == "games-dev":
                r["row_id"] = "games"
                existing_ids.add("games")
                break
    else:
        for r in loaded_runs:
            if r["row_id"] == "games-dev":
                r["is_checkpoint"] = True

    # For each RL family prefix, promote the highest-headline checkpoint to the family's canonical `row_id`
    for canonical_id, prefix in RL_FAMILY_PREFIXES:
        family_runs = [r for r in loaded_runs if r["raw_name"].lower().startswith(prefix)]
        if not family_runs:
            continue
        if canonical_id in existing_ids:
            for r in family_runs:
                if r["row_id"] != canonical_id:
                    r["is_checkpoint"] = True
            continue
        best = max(family_runs, key=lambda r: (_primary_headline(r), r["raw_name"]))
        for r in family_runs:
            if r is best:
                r["row_id"] = canonical_id
                r["is_checkpoint"] = False
            else:
                r["is_checkpoint"] = True
        existing_ids.add(canonical_id)


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
        elif r_meta.get("mean") is not None and c_meta.get("mean") is not None and r_meta.get("n") == c_meta.get("n"):
            # Summary-only fallback ONLY when both runs evaluated the same item count
            diff = round(float(c_meta["mean"]) - float(r_meta["mean"]), 6)
            d = {
                "n_shared": int(c_meta.get("n") or 0),
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
                "n_only_ref": int(r_meta.get("n") or 0),
                "n_only_cand": int(c_meta.get("n") or 0),
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
        "config_hash_match": bool(
            ref_run.get("config_hash") is not None
            and ref_run.get("config_hash") == cand_run.get("config_hash")
        ),
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
    """Evaluate PLAN.md §3.3 + bench/PROTOCOL.md §6 + FT_BENCHMARKS.md + DECISIONS.md Sat 21:15 honesty rule."""
    non_control_ctrl_comps = [
        c for c in comparisons_vs_ctrl
        if c["cand"] not in ("base", "sft-v1", "ctrl", "think-ctrl")
        and not (runs_by_id.get(c["cand"]) or {}).get("is_checkpoint", False)
    ]

    if not runs_by_id or len(non_control_ctrl_comps) == 0:
        sft_v1_eval = next(
            (r for r in in_domain_rows if r["role"] == "sft-v1" and r["collection"] == "eval-v1"),
            None,
        )
        base_h = _primary_headline(runs_by_id["base"]) if "base" in runs_by_id else -1.0
        games_h = _primary_headline(runs_by_id["games"]) if "games" in runs_by_id else -1.0

        notes: list[str] = []
        if sft_v1_eval:
            notes.append(
                f"Step 0 (`{sft_v1_eval['player_id']}`, action-only SFT) solved {sft_v1_eval['levels_solved']}/"
                f"{sft_v1_eval['levels_attempted']} levels on eval-v1 ({sft_v1_eval['score']:.3f})."
            )
        if base_h > 0 and games_h > 0 and (games_h - base_h) < -0.15:
            notes.append(
                f"Line 1 negative result (PROTOCOL v3): answer-only SFT suppressed `<think>` and dropped Qwen3.5-9B "
                f"primary headline from {base_h:.3f} to {games_h:.3f}. Line 2 (`think-games` vs `think-ctrl`, GRPO with `<think>` ON from base) is running."
            )
        elif base_h > 0:
            notes.append(
                f"Qwen3.5-9B `base` primary headline = {base_h:.3f}; awaiting matched control (`think-ctrl` / `ctrl`) benches."
            )
        else:
            notes.append(
                "Pre-registered PROTOCOL v3 (`ANSWER: X` rescorer + paired item-level bootstrap) locked; awaiting GPU bench outputs."
            )

        return {
            "status": "pending_bench_runs",
            "transfer_shown": False,
            "winning_candidate": None,
            "headline": "Pre-registered PROTOCOL v3 active; Thinking-On GRPO (`think-games` vs `think-ctrl`) & control benches in flight.",
            "detail": " ".join(notes),
        }

    vs_base_by_cand = {c["cand"]: c for c in comparisons_vs_base}
    best_winner: dict[str, Any] | None = None

    for comp in non_control_ctrl_comps:
        cand = comp["cand"]
        ctrl_ref = comp["ref"]
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
                    "ctrl_ref": ctrl_ref,
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
                f"Transfer supported: `{best_winner['cand']}` beats matched `{best_winner['ctrl_ref']}` by "
                f"{best_winner['mean_delta']:+.3f} across `{best_winner['target_tier']}` "
                f"({best_winner['sig_positive']} benchmarks with 95% CI > 0; negative control & guard passed)."
            ),
            "detail": "Satisfies the pre-registered PLAN.md §3.3 / bench/PROTOCOL.md v3 §6 claim rule.",
        }

    return {
        "status": "null_transfer_in_domain_only",
        "transfer_shown": False,
        "winning_candidate": None,
        "headline": "Honesty rule: outside-benchmark gain over matched control did not clear the 95% CI threshold.",
        "detail": (
            "Per PLAN.md §3.3 & bench/PROTOCOL.md v3, no trained candidate beat its matched control (`think-ctrl` / `ctrl`) "
            "on >=2 primary reasoning benchmarks with 95% CIs excluding zero. Reporting exact PROTOCOL v3 & official deltas plainly."
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
                parsed = _load_bench_run_dir(child, ci_resamples=min(2_000, resamples))
                if parsed is not None:
                    loaded_runs.append(parsed)

    _promote_canonical_families(loaded_runs)
    loaded_runs.sort(key=lambda r: (1 if r["is_checkpoint"] else 0, ROW_ORDER.get(r["row_id"], 50), r["row_id"]))

    # Map row_id -> run (if duplicate row_id ever exists, prefer non-dev_slice then later run)
    runs_by_id: dict[str, dict[str, Any]] = {}
    for r in loaded_runs:
        prev = runs_by_id.get(r["row_id"])
        if prev is None or (prev["dev_slice"] and not r["dev_slice"]):
            runs_by_id[r["row_id"]] = r

    comparisons_vs_base: list[dict[str, Any]] = []
    comparisons_vs_ctrl: list[dict[str, Any]] = []

    base_run = runs_by_id.get("base") or runs_by_id.get("base-dev")
    sft_ctrl_run = runs_by_id.get("ctrl")
    think_ctrl_run = runs_by_id.get("think-ctrl")

    for r in loaded_runs:
        rid = r["row_id"]
        if base_run is not None and r is not base_run and rid != "base":
            comparisons_vs_base.append(_compute_comparison(base_run, r, resamples=resamples))

        if rid in ("base", "base-dev", "ctrl", "think-ctrl"):
            continue
        is_think_rl = rid == "think-games" or r["raw_name"].lower().startswith("rl-think-games-")
        matched_ctrl = (think_ctrl_run or sft_ctrl_run) if is_think_rl else sft_ctrl_run
        if matched_ctrl is not None and r is not matched_ctrl:
            comparisons_vs_ctrl.append(_compute_comparison(matched_ctrl, r, resamples=resamples))

    in_domain_rows = _extract_in_domain_game_rows(lb_h1, lb_h2)
    claim_eval = _evaluate_honesty_rule(runs_by_id, comparisons_vs_ctrl, comparisons_vs_base, in_domain_rows)

    public_runs = [
        {k: v for k, v in r.items() if k != "_items"}
        for r in loaded_runs
    ]

    return {
        "generated_at": generated_at or now_iso(),
        "protocol_version": "ft-benchmarks-v3",
        "bootstrap_resamples": resamples,
        "bootstrap_seed": DEFAULT_SEED,
        "suite_definition": FT_BENCHMARKS_SUITE,
        "claim_evaluation": claim_eval,
        "in_domain_games": in_domain_rows,
        "runs": public_runs,
        "comparisons_vs_base": comparisons_vs_base,
        "comparisons_vs_ctrl": comparisons_vs_ctrl,
    }
