"""Schema validation and cross-document claim consistency checks."""
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
    """Validate derived JSON files against contracts/derived.schema.json and reward-integrity invariants."""
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

    exp_path = derived_dir / "explanations.json"
    if exp_path.exists():
        try:
            obj = json.loads(exp_path.read_text(encoding="utf-8"))
            validate_against_schema(obj, schema_path)
            docs["explanations"] = obj
            checked.append("explanations")
        except Exception as exc:
            errors.append(f"explanations.json failed schema validation: {exc}")

    # Cross-check invariants
    if "leaderboard" in docs:
        for row in docs["leaderboard"].get("rows", []):
            pid = row.get("player_id")
            score = row.get("score", 0.0)
            solve_rate = row.get("level_solve_rate", 0.0)
            if not (0.0 <= score <= 1.0):
                errors.append(f"Score out of [0, 1] for {pid}: {score}")
            if not (0.0 <= solve_rate <= 1.0):
                errors.append(f"level_solve_rate out of [0, 1] for {pid}: {solve_rate}")
            if pid in ("noop", "stop_early") and score != 0.0:
                errors.append(f"Reward integrity failure: {pid} has non-zero score {score}")
            if pid == "optimal" and row.get("games", 0) > 0 and score < 0.999:
                errors.append(f"Reference optimal baseline score < 1.0: {score}")

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
