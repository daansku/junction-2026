"""Schema validation and cross-document claim consistency checks (PLAN.md §3.5, A5-20/A5-23)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

from .loader import find_repo_root


def validate_against_schema(payload: dict[str, Any], schema_path: Path | None = None) -> None:
    root = find_repo_root()
    spath = schema_path or (root / "contracts" / "derived.schema.json")
    schema = json.loads(spath.read_text(encoding="utf-8"))
    jsonschema.validate(instance=payload, schema=schema)


def check_claims(derived_dir: Path, repo_root: Path | None = None) -> dict[str, Any]:
    """Validate derived JSON files against contracts/derived.schema.json and Phase 2 invariants."""
    root = repo_root or find_repo_root()
    schema_path = root / "contracts" / "derived.schema.json"
    errors: list[str] = []
    checked: list[str] = []

    docs: dict[str, dict[str, Any]] = {}
    for name in ("leaderboard", "rules", "insights"):
        p = derived_dir / f"{name}.json"
        if not p.exists():
            errors.append(f"Missing derived file: {p}")
            continue
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
            validate_against_schema(obj, schema_path)
            docs[name] = obj
            checked.append(name)
        except Exception as exc:
            errors.append(f"{name}.json failed schema validation: {exc}")

    for opt_schema_doc in ("explanations", "leaderboard_h2"):
        p = derived_dir / f"{opt_schema_doc}.json"
        if p.exists():
            try:
                obj = json.loads(p.read_text(encoding="utf-8"))
                validate_against_schema(obj, schema_path)
                docs[opt_schema_doc] = obj
                checked.append(opt_schema_doc)
            except Exception as exc:
                errors.append(f"{opt_schema_doc}.json failed schema validation: {exc}")

    bench_path = derived_dir / "bench_summary.json"
    if bench_path.exists():
        try:
            obj = json.loads(bench_path.read_text(encoding="utf-8"))
            if not isinstance(obj.get("generated_at"), str) or not isinstance(obj.get("claim_evaluation"), dict):
                errors.append("bench_summary.json missing generated_at or claim_evaluation")
            for comp_list_key in ("comparisons_vs_base", "comparisons_vs_ctrl"):
                for comp in obj.get(comp_list_key) or []:
                    for b_id, b_res in (comp.get("benchmarks") or {}).items():
                        d, lo, hi = b_res.get("delta"), b_res.get("ci_low"), b_res.get("ci_high")
                        if d is not None and lo is not None and hi is not None:
                            if not (lo - 1e-6 <= d <= hi + 1e-6):
                                errors.append(f"bench_summary CI out of order on {comp.get('cand')}/{b_id}: {lo}..{hi} vs {d}")
                            expected_excl = bool(lo > 0 or hi < 0)
                            if bool(b_res.get("excludes_zero")) != expected_excl:
                                errors.append(f"bench_summary excludes_zero mismatch on {comp.get('cand')}/{b_id}")
            docs["bench_summary"] = obj
            checked.append("bench_summary")
        except Exception as exc:
            errors.append(f"bench_summary.json validation failed: {exc}")

    dp_path = derived_dir / "decision_points.json"
    if dp_path.exists():
        try:
            obj = json.loads(dp_path.read_text(encoding="utf-8"))
            weights = (obj.get("oversample_weights") or {}).get("by_train_safe_rule") or {}
            forbidden_tier3 = {"conveyors", "enemies", "gravity", "checkpoints", "no_reverse", "pits", "momentum", "boulders", "shadow", "board_flip"}
            leaked = forbidden_tier3 & set(weights)
            if leaked:
                errors.append(f"decision_points.json leaked Tier-3 rules into train-v1 weights: {sorted(leaked)}")
            docs["decision_points"] = obj
            checked.append("decision_points")
        except Exception as exc:
            errors.append(f"decision_points.json validation failed: {exc}")

    # Cross-check invariants on h1 leaderboard
    if "leaderboard" in docs:
        for row in docs["leaderboard"].get("rows", []):
            pid = row.get("player_id")
            score = row.get("score", 0.0)
            solve_rate = row.get("level_solve_rate", 0.0)
            if row.get("harness_version") == "h2":
                errors.append(f"Board separation violation: h2 row {pid} appeared in h1 leaderboard.json")
            if not (0.0 <= score <= 1.0):
                errors.append(f"Score out of [0, 1] for {pid}: {score}")
            if not (0.0 <= solve_rate <= 1.0):
                errors.append(f"level_solve_rate out of [0, 1] for {pid}: {solve_rate}")
            if pid in ("noop", "stop_early") and score != 0.0:
                errors.append(f"Reward integrity failure: {pid} has non-zero score {score}")
            if pid == "optimal" and row.get("games", 0) > 0 and score < 0.999:
                errors.append(f"Reference optimal baseline score < 1.0: {score}")

    # Cross-check invariants on h2 leaderboard
    if "leaderboard_h2" in docs:
        for row in docs["leaderboard_h2"].get("rows", []):
            pid = row.get("player_id")
            kind = row.get("kind")
            score = row.get("score", 0.0)
            if kind == "model" and row.get("harness_version") != "h2":
                errors.append(f"Board separation violation: non-h2 model row {pid} appeared in leaderboard_h2.json")
            if not (0.0 <= score <= 1.0):
                errors.append(f"h2 score out of [0, 1] for {pid}: {score}")
            lo, hi = row.get("score_ci_low"), row.get("score_ci_high")
            if lo is not None and hi is not None and not (lo - 1e-6 <= score <= hi + 1e-6):
                errors.append(f"h2 CI bounds invalid for {pid}: [{lo}, {hi}] vs {score}")

    if "rules" in docs:
        for cell in docs["rules"].get("cells", []):
            sr = cell.get("intro_solve_rate", 0.0)
            if not (0.0 <= sr <= 1.0):
                errors.append(f"intro_solve_rate out of [0, 1] for {cell.get('rule')}/{cell.get('player_id')}: {sr}")

    if "insights" in docs:
        for ins in docs["insights"].get("insights", []):
            if not ins.get("evidence"):
                errors.append(f"Insight {ins.get('id')} has empty evidence array")

    if "explanations" in docs:
        seen_pairs: set[tuple[str, int]] = set()
        for idx, exp in enumerate(docs["explanations"].get("explanations", [])):
            rid = str(exp.get("run_id") or "").strip()
            lv = int(exp.get("level") or 0)
            verdict = str(exp.get("verdict") or "").strip()
            step = exp.get("step")
            if not rid or lv < 1 or not verdict:
                errors.append(f"Explanation #{idx} missing run_id/level/verdict: {exp}")
            pair = (rid, lv)
            if pair in seen_pairs:
                errors.append(f"Duplicate explanation for ({rid}, L{lv})")
            seen_pairs.add(pair)
            if step is not None and (not isinstance(step, int) or step < 0):
                errors.append(f"Invalid step index on ({rid}, L{lv}): {step}")

    return {
        "ok": len(errors) == 0,
        "derived_dir": str(derived_dir),
        "checked": checked,
        "errors": errors,
    }
