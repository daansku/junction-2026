"""Aggregate finished run traces into leaderboard.json (PLAN.md §4.6, contracts/derived.schema.json)."""
from __future__ import annotations

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


def _group_key(meta: dict[str, Any]) -> tuple[str, str, str | None, str, str | None]:
    player = meta.get("player") or {}
    pid, kind, effort, _ = normalize_player(player)
    collection = str(meta.get("collection") or "dev")
    harness = meta.get("harness_version")
    return (pid, kind, effort, collection, str(harness) if harness else None)


def aggregate_runs(
    runs: list[dict[str, Any]],
    models_registry: dict[str, dict[str, Any]] | None = None,
    game_descs: dict[str, dict[str, Any]] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Compute leaderboard.json structure strictly from run traces."""
    models_registry = models_registry if models_registry is not None else load_models()
    game_descs = game_descs if game_descs is not None else load_collections()

    grouped: dict[tuple[str, str, str | None, str, str | None], list[dict[str, Any]]] = defaultdict(list)
    max_games_per_collection: dict[str, set[str]] = defaultdict(set)

    for run in runs:
        meta = run["meta"]
        col = str(meta.get("collection") or "dev")
        if meta.get("game_id"):
            max_games_per_collection[col].add(str(meta["game_id"]))
        grouped[_group_key(meta)].append(run)

    # First pass to compute raw stats per group so we can compute rhae_vs_human per collection
    pre_rows: list[dict[str, Any]] = []
    human_score_by_collection: dict[str, float] = {}

    for (pid, kind, effort, collection, harness), group_runs in grouped.items():
        level_scores: list[float] = []
        levels_attempted = 0
        levels_solved = 0
        wins = 0
        actions_list: list[int] = []
        tokens_in_total = 0
        tokens_out_total = 0
        cost_total = 0.0
        has_any_cost = False
        latencies_all: list[int] = []
        belief_total = 0
        belief_correct = 0
        no_effect_total = 0
        resets_total = 0
        game_ids: set[str] = set()
        display_name = pid
        provider: str | None = None

        reg_entry = models_registry.get(pid)
        model_card = dict(reg_entry["card"]) if reg_entry else None
        model_order = reg_entry["order"] if reg_entry else 999

        if model_card:
            display_name = model_card["display_name"]
            provider = model_card["provider"]
        elif kind == "human":
            display_name = "Human"
            provider = "human"
        elif kind == "baseline":
            display_name = pid.replace("_", " ").title()
            provider = "baseline"

        seen_scores: list[float] = []
        unseen_pair_scores: list[float] = []
        unseen_skin_scores: list[float] = []
        observed_input_modes: list[str] | None = (
            list(model_card["input_modes"]) if model_card and model_card.get("input_modes") else None
        )

        for run in group_runs:
            meta = run["meta"]
            gid = str(meta.get("game_id") or "")
            if gid:
                game_ids.add(gid)
            player = meta.get("player") or {}
            if not model_card and kind == "model":
                display_name = str(player.get("name") or pid)
                provider = player.get("provider")
            if observed_input_modes is None and isinstance(player.get("input_modes"), list):
                observed_input_modes = [str(m) for m in player["input_modes"]]

            gdesc = game_descs.get(gid)
            holdout = (gdesc or {}).get("holdout")
            holdout_levels = set(int(x) for x in (holdout or {}).get("levels", [])) if isinstance(holdout, dict) else set()
            is_holdout_skin = bool((holdout or {}).get("skin")) if isinstance(holdout, dict) else False

            seg_info = extract_level_segments(run, gdesc)
            levels_attempted += seg_info["levels_total"]
            levels_solved += seg_info["levels_solved"]
            for lv_num, seg in seg_info["segments"].items():
                lscore = seg["level_score"]
                level_scores.append(lscore)
                if isinstance(holdout, dict):
                    if lv_num in holdout_levels:
                        unseen_pair_scores.append(lscore)
                    elif not is_holdout_skin:
                        seen_scores.append(lscore)
                    if is_holdout_skin:
                        unseen_skin_scores.append(lscore)

            if meta.get("outcome") == "WIN" or (
                seg_info["levels_total"] > 0 and seg_info["levels_solved"] >= seg_info["levels_total"]
            ):
                wins += 1

            acts = int(meta.get("actions") if meta.get("actions") is not None else len(run["steps"]))
            actions_list.append(acts)
            resets_total += int(meta.get("resets") or 0)
            tokens_in_total += int(meta.get("tokens_in") or 0)
            tokens_out_total += int(meta.get("tokens_out") or 0)

            rcost = meta.get("cost_usd")
            if isinstance(rcost, (int, float)) and rcost > 0:
                cost_total += float(rcost)
                has_any_cost = True

            latencies_all.extend(seg_info["latencies"])
            belief_total += seg_info["belief_total"]
            belief_correct += seg_info["belief_correct"]
            no_effect_total += seg_info["no_effect_total"]

        n_games = len(group_runs)
        score = round(statistics.fmean(level_scores), 6) if level_scores else 0.0
        level_solve_rate = round(levels_solved / levels_attempted, 6) if levels_attempted > 0 else 0.0
        game_win_rate = round(wins / n_games, 6) if n_games > 0 else 0.0
        median_actions = round(statistics.median(actions_list), 2) if actions_list else None

        price_known = (
            model_card is not None
            and model_card.get("price_in") is not None
            and model_card.get("price_out") is not None
        ) or has_any_cost

        if kind == "model" and price_known:
            cost_per_game: float | None = round(cost_total / n_games, 6) if n_games > 0 else 0.0
            cost_per_solved_level: float | None = (
                round(cost_total / levels_solved, 6) if levels_solved > 0 else None
            )
        else:
            cost_per_game = None
            cost_per_solved_level = None

        total_actions = sum(actions_list)
        col_total_games = len(max_games_per_collection.get(collection, set()))
        subset_note = None
        if kind == "model" and col_total_games > 1 and len(game_ids) < col_total_games:
            subset_note = f"Evaluated on {len(game_ids)}/{col_total_games} games in {collection}"

        row = {
            "player_id": pid,
            "kind": kind,
            "effort": effort,
            "collection": collection,
            "harness_version": harness,
            "games": n_games,
            "levels_attempted": levels_attempted,
            "levels_solved": levels_solved,
            "level_solve_rate": level_solve_rate,
            "game_win_rate": game_win_rate,
            "score": score,
            "median_actions": median_actions,
            "tokens_in": tokens_in_total if kind == "model" else None,
            "tokens_out": tokens_out_total if kind == "model" else None,
            "cost_per_game": cost_per_game,
            "cost_per_solved_level": cost_per_solved_level,
            "latency_ms_median": round(statistics.median(latencies_all), 1) if latencies_all else None,
            "subset_note": subset_note,
            "model": model_card,
            # Useful extra display/diagnostic properties (allowed by derived.schema.json)
            "display_name": display_name,
            "provider": provider,
            "tier": model_card["tier"] if model_card else kind,
            "input_modes": observed_input_modes if kind == "model" else (["image"] if kind == "human" else None),
            "model_order": model_order,
            "resets_total": resets_total,
            "belief_accuracy": round(belief_correct / belief_total, 4) if belief_total > 0 else None,
            "no_effect_rate": round(no_effect_total / total_actions, 4) if total_actions > 0 else None,
            "seen_score": round(statistics.fmean(seen_scores), 6) if seen_scores else None,
            "unseen_pair_score": round(statistics.fmean(unseen_pair_scores), 6) if unseen_pair_scores else None,
            "unseen_skin_score": round(statistics.fmean(unseen_skin_scores), 6) if unseen_skin_scores else None,
            "rhae_vs_human": None,
        }
        pre_rows.append(row)
        if kind == "human" and score > 0:
            human_score_by_collection[collection] = score

    cols_per_player: dict[tuple[str, str | None], set[str]] = defaultdict(set)
    for row in pre_rows:
        cols_per_player[(row["player_id"], row["effort"])].add(row["collection"])

    for row in pre_rows:
        h_score = human_score_by_collection.get(row["collection"])
        if h_score and h_score > 0:
            row["rhae_vs_human"] = round(row["score"] / h_score, 4)
        if len(cols_per_player[(row["player_id"], row["effort"])]) > 1:
            row["display_name"] = f"{row['display_name']} [{row['collection']}]"

    pre_rows.sort(
        key=lambda r: (
            -r["score"],
            -r["level_solve_rate"],
            r["cost_per_game"] if r["cost_per_game"] is not None else float("inf"),
            r["player_id"],
        )
    )

    return {
        "generated_at": generated_at or now_iso(),
        "rows": pre_rows,
    }


def build_leaderboard(
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
    data = aggregate_runs(runs, models_registry=models, game_descs=games)
    if out_path is not None:
        import json

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data
