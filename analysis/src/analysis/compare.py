"""Head-to-head comparisons: baselines, reward integrity, human vs models, effort ablation."""
from __future__ import annotations

from collections import defaultdict
from typing import Any


def build_comparisons(leaderboard: dict[str, Any]) -> dict[str, Any]:
    """Summarize reward integrity checks, RHAE gaps, and effort ablations from leaderboard rows."""
    rows = leaderboard.get("rows") or []
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_id[str(r["player_id"])].append(r)

    def _mean_score(pid: str) -> float | None:
        rs = by_id.get(pid, [])
        if not rs:
            return None
        return round(sum(x["score"] for x in rs) / len(rs), 6)

    noop_score = _mean_score("noop")
    stop_early_score = _mean_score("stop_early")
    random_score = _mean_score("random")
    optimal_score = _mean_score("optimal")
    human_score = _mean_score("human")

    model_rows = [r for r in rows if r.get("kind") == "model"]
    # Completion first: games won, levels solved, then efficiency.
    best_model = (max(model_rows, key=lambda r: (r.get("game_win_rate") or 0, r["level_solve_rate"], r["score"]))
                  if model_rows else None)
    finetuned_rows = [r for r in model_rows if r.get("tier") == "finetuned"]
    frontier_rows = [r for r in model_rows if r.get("tier") == "frontier"]

    # Effort ablation: models that appear with >= 2 distinct effort values
    by_model_col: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in model_rows:
        if r.get("effort"):
            by_model_col[(str(r["player_id"]), str(r["collection"]))].append(r)

    effort_order = {"low": 0, "medium": 1, "high": 2, "xhigh": 3, "max": 4}
    effort_ablations: list[dict[str, Any]] = []
    for (pid, col), entries in sorted(by_model_col.items()):
        if len(entries) < 2:
            continue
        entries_sorted = sorted(entries, key=lambda e: effort_order.get(str(e.get("effort")), 99))
        effort_ablations.append({
            "player_id": pid,
            "display_name": entries_sorted[0].get("display_name", pid),
            "collection": col,
            "points": [
                {
                    "effort": e.get("effort"),
                    "score": e["score"],
                    "level_solve_rate": e["level_solve_rate"],
                    "cost_per_game": e.get("cost_per_game"),
                    "tokens_total": (e.get("tokens_in") or 0) + (e.get("tokens_out") or 0),
                }
                for e in entries_sorted
            ],
        })

    reward_integrity = {
        "noop_score": noop_score,
        "stop_early_score": stop_early_score,
        "random_score": random_score,
        "optimal_score": optimal_score,
        "passed": (
            (noop_score is None or noop_score == 0.0)
            and (stop_early_score is None or stop_early_score == 0.0)
            and (optimal_score is None or optimal_score >= 0.999)
            and (random_score is None or random_score < 0.05)
        ),
    }

    return {
        "reward_integrity": reward_integrity,
        "human_score": human_score,
        "best_model": {
            "player_id": best_model["player_id"],
            "display_name": best_model.get("display_name", best_model["player_id"]),
            "collection": best_model.get("collection"),
            "score": best_model["score"],
            "level_solve_rate": best_model["level_solve_rate"],
            "game_win_rate": best_model.get("game_win_rate"),
            "effort": best_model.get("effort"),
        }
        if best_model
        else None,
        "best_frontier_score": max((r["score"] for r in frontier_rows), default=None),
        "best_finetuned_score": max((r["score"] for r in finetuned_rows), default=None),
        "human_vs_best_model_gap": (
            round(human_score - best_model["score"], 6)
            if human_score is not None and best_model is not None
            else None
        ),
        "effort_ablations": effort_ablations,
    }
