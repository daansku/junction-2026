"""Aggregate finished run traces into leaderboard.json (h1) and leaderboard_h2.json (h2) (PLAN.md §3.1)."""
from __future__ import annotations

import random
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

H2_RULES_SUMMARY: list[str] = [
    "Multi-turn conversation: model sees its own full prior turn history (never stateless notes-only).",
    "Reasoning retained across turns: Anthropic thinking blocks preserved; OpenAI-compat assistant message (reasoning_content / Gemini thought signatures) returned verbatim.",
    "Native tool calling: structured act(action, hypothesis, belief) tool; invalid calls cost a turn, not an action.",
    "Leaderboard-standard effort: high / max per model, explicitly labelled per row and never silently mixed.",
    "Generous output cap: 64k tokens (Anthropic streamed) / 32k tokens (OpenAI-compatible) so thinking never truncates.",
    "Provider-default sampling: no artificial temperature overrides on reasoning models.",
    "Fixed context window: full text history + last 5 image frames (older frames cleared) + prompt caching enabled.",
    "Uncertainty reported: 95% bootstrap CI over game scores; single-attempt rows explicitly badged.",
    "Zero truth leakage: pixels + RLE only under prompts/system_h2.md; hidden rules never enter prompts.",
]


def _bootstrap_ci(vals: list[float], resamples: int = 2000, seed: int = 20261114) -> tuple[float | None, float | None]:
    n = len(vals)
    if n == 0:
        return None, None
    if n == 1:
        v = round(vals[0], 6)
        return v, v
    rng = random.Random(seed)
    boots = sorted(sum(vals[rng.randrange(n)] for _ in range(n)) / n for _ in range(resamples))
    lo_idx = int(0.025 * (resamples - 1))
    hi_idx = int(0.975 * (resamples - 1))
    return round(boots[lo_idx], 6), round(boots[hi_idx], 6)


def _run_harness(meta: dict[str, Any]) -> str | None:
    player = meta.get("player") or {}
    h = meta.get("harness_version") or player.get("harness_version")
    return str(h).strip() if h else None


def _group_key(meta: dict[str, Any]) -> tuple[str, str, str | None, str, str | None]:
    player = meta.get("player") or {}
    pid, kind, effort, _ = normalize_player(player)
    collection = str(meta.get("collection") or "dev")
    harness = _run_harness(meta)
    return (pid, kind, effort, collection, harness)


def _is_gemini_underreported(pid: str, provider: str | None, meta: dict[str, Any]) -> bool:
    """Detect Gemini h1 traces recorded before A3's 2026-11-14T15:15Z billed_tokens thinking fix."""
    is_gem = "gemini" in pid.lower() or (provider or "").lower() == "google"
    if not is_gem:
        return False
    if _run_harness(meta) == "h2":
        return False
    started_at = str(meta.get("started_at") or "")
    return not started_at or started_at < "2026-11-14T15:15:00Z"


def aggregate_runs(
    runs: list[dict[str, Any]],
    models_registry: dict[str, dict[str, Any]] | None = None,
    game_descs: dict[str, dict[str, Any]] | None = None,
    generated_at: str | None = None,
    harness_filter: str | None = "h1",
) -> dict[str, Any]:
    """Compute leaderboard.json structure strictly from run traces.

    By default (`harness_filter='h1'`), excludes `h2` runs so h1 and h2 boards are never mixed (PLAN.md §1.1 & §3.1).
    """
    models_registry = models_registry if models_registry is not None else load_models()
    game_descs = game_descs if game_descs is not None else load_collections()

    filtered_runs: list[dict[str, Any]] = []
    for run in runs:
        rh = _run_harness(run["meta"])
        # h1 board = h1 runs only (or runs with no harness tag: humans, baselines, older traces). Every other
        # harness (h2, and variants such as h2b) has its own board and is never mixed into h1.
        if harness_filter == "h1" and rh not in (None, "h1"):
            continue
        # Lab-style boards (h2, h2b, ...): model runs of exactly that harness; human / baseline references pass.
        if harness_filter not in (None, "h1") and rh != harness_filter and (run["meta"].get("player") or {}).get("kind") == "model":
            continue
        filtered_runs.append(run)

    grouped: dict[tuple[str, str, str | None, str, str | None], list[dict[str, Any]]] = defaultdict(list)
    max_games_per_collection: dict[str, set[str]] = defaultdict(set)

    for run in filtered_runs:
        meta = run["meta"]
        col = str(meta.get("collection") or "dev")
        if meta.get("game_id"):
            max_games_per_collection[col].add(str(meta["game_id"]))
        grouped[_group_key(meta)].append(run)

    pre_rows: list[dict[str, Any]] = []
    human_score_by_collection: dict[str, float] = {}

    for (pid, kind, effort, collection, harness), group_runs in grouped.items():
        level_scores: list[float] = []
        per_run_game_scores: list[float] = []
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
        attempts_by_game: dict[str, int] = defaultdict(int)
        display_name = pid
        provider: str | None = None
        reasoning_modes: set[str] = set()
        image_turns_val: int | None = None
        max_tokens_val: int | None = None
        any_gemini_underreported = False
        best_run_id: str | None = None
        best_run_tuple: tuple[int, float, int] = (-1, -1.0, 10**9)

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
        probe_scores: list[float] = []
        observed_input_modes: list[str] | None = (
            list(model_card["input_modes"]) if model_card and model_card.get("input_modes") else None
        )

        for run in group_runs:
            meta = run["meta"]
            gid = str(meta.get("game_id") or "")
            if gid:
                game_ids.add(gid)
                attempts_by_game[gid] += 1
            player = meta.get("player") or {}
            if not model_card and kind == "model":
                display_name = str(player.get("name") or pid)
                provider = player.get("provider")
            if observed_input_modes is None and isinstance(player.get("input_modes"), list):
                observed_input_modes = [str(m) for m in player["input_modes"]]
            rm = player.get("reasoning_mode") or meta.get("reasoning_mode")
            if rm:
                reasoning_modes.add(str(rm))
            if player.get("image_turns") is not None:
                image_turns_val = int(player["image_turns"])
            if player.get("max_tokens") is not None:
                max_tokens_val = int(player["max_tokens"])
            if kind == "model" and _is_gemini_underreported(pid, provider, meta):
                any_gemini_underreported = True

            gdesc = game_descs.get(gid)
            holdout = (gdesc or {}).get("holdout")
            holdout_levels = set(int(x) for x in (holdout or {}).get("levels", [])) if isinstance(holdout, dict) else set()
            is_holdout_skin = bool((holdout or {}).get("skin")) if isinstance(holdout, dict) else False
            probe_levels = set(int(x) for x in (gdesc or {}).get("probe_levels", [])) if isinstance(gdesc, dict) else set()

            seg_info = extract_level_segments(run, gdesc)
            levels_attempted += seg_info["levels_total"]
            levels_solved += seg_info["levels_solved"]
            run_lscores: list[float] = []
            for lv_num, seg in seg_info["segments"].items():
                lscore = seg["level_score"]
                level_scores.append(lscore)
                run_lscores.append(lscore)
                if lv_num in probe_levels:
                    probe_scores.append(lscore)
                if isinstance(holdout, dict):
                    if lv_num in holdout_levels:
                        unseen_pair_scores.append(lscore)
                    elif not is_holdout_skin:
                        seen_scores.append(lscore)
                    if is_holdout_skin:
                        unseen_skin_scores.append(lscore)

            run_gscore = statistics.fmean(run_lscores) if run_lscores else 0.0
            per_run_game_scores.append(run_gscore)

            acts = int(meta.get("actions") if meta.get("actions") is not None else len(run["steps"]))
            cand_tuple = (int(seg_info["levels_solved"]), run_gscore, -acts)
            if meta.get("run_id") and cand_tuple > best_run_tuple:
                best_run_tuple = cand_tuple
                best_run_id = str(meta["run_id"])

            if meta.get("outcome") == "WIN" or (
                seg_info["levels_total"] > 0 and seg_info["levels_solved"] >= seg_info["levels_total"]
            ):
                wins += 1

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
        unique_games = len(game_ids) if game_ids else n_games
        attempts_per_game = round(n_games / unique_games, 2) if unique_games > 0 else 1.0
        single_attempt = kind == "model" and max(attempts_by_game.values(), default=1) <= 1

        score = round(statistics.fmean(level_scores), 6) if level_scores else 0.0
        ci_lo, ci_hi = _bootstrap_ci(per_run_game_scores) if per_run_game_scores else (None, None)
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
        notes: list[str] = []
        if kind == "model" and col_total_games > 1 and len(game_ids) < col_total_games:
            notes.append(f"Evaluated on {len(game_ids)}/{col_total_games} games in {collection}")
        if harness not in (None, "h1") and single_attempt:
            notes.append("single-attempt (k=1)")
        cost_note: str | None = None
        if any_gemini_underreported:
            cost_note = "Cost ~3.6x underreported (thinking tokens excluded in Gemini compat pre-17:15)"
            notes.append("cost underreported (~3.6x: thinking tokens excluded pre-17:15)")

        subset_note = " · ".join(notes) if notes else None

        row = {
            "player_id": pid,
            "kind": kind,
            "effort": effort,
            "collection": collection,
            "harness_version": harness,
            "games": n_games,
            "unique_games": unique_games,
            "attempts_per_game": attempts_per_game,
            "single_attempt": single_attempt,
            "levels_attempted": levels_attempted,
            "levels_solved": levels_solved,
            "level_solve_rate": level_solve_rate,
            "game_win_rate": game_win_rate,
            "score": score,
            "score_ci_low": ci_lo,
            "score_ci_high": ci_hi,
            "median_actions": median_actions,
            "tokens_in": tokens_in_total if kind == "model" else None,
            "tokens_out": tokens_out_total if kind == "model" else None,
            "cost_per_game": cost_per_game,
            "cost_per_solved_level": cost_per_solved_level,
            "cost_underreported": any_gemini_underreported,
            "cost_note": cost_note,
            "latency_ms_median": round(statistics.median(latencies_all), 1) if latencies_all else None,
            "subset_note": subset_note,
            "model": model_card,
            # Display & h2 / diagnostic fields (open properties on leaderboard_row)
            "display_name": display_name,
            "provider": provider,
            "tier": model_card["tier"] if model_card else kind,
            "input_modes": observed_input_modes if kind == "model" else (["image"] if kind == "human" else None),
            "reasoning_mode": ", ".join(sorted(reasoning_modes)) if reasoning_modes else None,
            "image_turns": image_turns_val,
            "max_tokens": max_tokens_val,
            "best_run_id": best_run_id,
            "model_order": model_order,
            "resets_total": resets_total,
            "belief_accuracy": round(belief_correct / belief_total, 4) if belief_total > 0 else None,
            "no_effect_rate": round(no_effect_total / total_actions, 4) if total_actions > 0 else None,
            "seen_score": round(statistics.fmean(seen_scores), 6) if seen_scores else None,
            "unseen_pair_score": round(statistics.fmean(unseen_pair_scores), 6) if unseen_pair_scores else None,
            "unseen_skin_score": round(statistics.fmean(unseen_skin_scores), 6) if unseen_skin_scores else None,
            "probe_score": round(statistics.fmean(probe_scores), 6) if probe_scores else None,
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

    # Completion first (human decision Sat ~23:45, DECISIONS.md): games won, levels solved, then efficiency (score).
    pre_rows.sort(
        key=lambda r: (
            -(r.get("game_win_rate") or 0),
            -r["level_solve_rate"],
            -r["score"],
            r["cost_per_game"] if r["cost_per_game"] is not None else float("inf"),
            r["player_id"],
        )
    )

    return {
        "generated_at": generated_at or now_iso(),
        "harness_filter": harness_filter,
        "rows": pre_rows,
    }


def aggregate_h2_runs(
    runs: list[dict[str, Any]],
    models_registry: dict[str, dict[str, Any]] | None = None,
    game_descs: dict[str, dict[str, Any]] | None = None,
    generated_at: str | None = None,
    harness: str = "h2",
) -> dict[str, Any]:
    """Build a dedicated lab-style leaderboard for one harness (`h2` -> leaderboard_h2.json, `h2b` ->
    leaderboard_h2b.json). Originally: the dedicated h2 Lab-Standard Leaderboard (`leaderboard_h2.json`, PLAN.md §3.1).

    Never mixes h1 model runs into h2. Includes Optimal and Human reference rows matched to the
    exact game subset evaluated under h2 per collection (falling back to collection-wide Human/Optimal
    with an explicit subset_note if no exact-game baseline trace exists yet).
    """
    models_registry = models_registry if models_registry is not None else load_models()
    game_descs = game_descs if game_descs is not None else load_collections()

    h2_model_runs = [r for r in runs if _run_harness(r["meta"]) == harness and (r["meta"].get("player") or {}).get("kind") == "model"]
    h2_games_by_col: dict[str, set[str]] = defaultdict(set)
    for r in h2_model_runs:
        col = str(r["meta"].get("collection") or "dev")
        gid = str(r["meta"].get("game_id") or "")
        if gid:
            h2_games_by_col[col].add(gid)

    ref_runs: list[dict[str, Any]] = []
    for col, target_gids in h2_games_by_col.items():
        for ref_kind in ("human", "baseline"):
            exact = [
                r for r in runs
                if str(r["meta"].get("collection") or "dev") == col
                and (r["meta"].get("player") or {}).get("kind") == ref_kind
                and str(r["meta"].get("game_id") or "") in target_gids
            ]
            if exact:
                ref_runs.extend(exact)
            else:
                # Fallback to collection-level reference so Optimal / Human ceiling is always visible
                col_refs = [
                    r for r in runs
                    if str(r["meta"].get("collection") or "dev") == col
                    and (r["meta"].get("player") or {}).get("kind") == ref_kind
                ]
                ref_runs.extend(col_refs)

    board = aggregate_runs(
        h2_model_runs + ref_runs,
        models_registry=models_registry,
        game_descs=game_descs,
        generated_at=generated_at,
        harness_filter=harness,
    )

    # Guarantee an exact BFS Optimal (1.000) ceiling row per h2 collection from collection specs if not recorded as a session
    existing_opt_cols = {r["collection"] for r in board["rows"] if r["player_id"] == "optimal"}
    for col, target_gids in sorted(h2_games_by_col.items()):
        if col in existing_opt_cols:
            continue
        opt_actions: list[int] = []
        tot_lv = 0
        for gid in sorted(target_gids):
            gd = game_descs.get(gid) or {}
            lvs = gd.get("levels") or []
            if lvs:
                tot_lv += len(lvs)
                opt_actions.append(sum(int(lv.get("optimal_moves") or 0) for lv in lvs))
        if opt_actions and tot_lv > 0:
            h_row = next((r for r in board["rows"] if r["collection"] == col and r["kind"] == "human"), None)
            board["rows"].insert(0, {
                "player_id": "optimal",
                "kind": "baseline",
                "effort": None,
                "collection": col,
                "harness_version": None,
                "games": len(opt_actions),
                "unique_games": len(opt_actions),
                "attempts_per_game": 1.0,
                "single_attempt": False,
                "levels_attempted": tot_lv,
                "levels_solved": tot_lv,
                "level_solve_rate": 1.0,
                "game_win_rate": 1.0,
                "score": 1.0,
                "score_ci_low": 1.0,
                "score_ci_high": 1.0,
                "median_actions": round(statistics.median(opt_actions), 2),
                "tokens_in": None,
                "tokens_out": None,
                "cost_per_game": None,
                "cost_per_solved_level": None,
                "cost_underreported": False,
                "cost_note": None,
                "latency_ms_median": None,
                "subset_note": f"Exact BFS shortest-path ceiling on the {len(opt_actions)} h2 {col} game(s)",
                "model": None,
                "display_name": "Optimal",
                "provider": "baseline",
                "tier": "baseline",
                "input_modes": None,
                "reasoning_mode": None,
                "image_turns": None,
                "max_tokens": None,
                "best_run_id": None,
                "model_order": 999,
                "resets_total": 0,
                "belief_accuracy": None,
                "no_effect_rate": 0.0,
                "seen_score": 1.0,
                "unseen_pair_score": None,
                "unseen_skin_score": None,
                "probe_score": None,
                "rhae_vs_human": round(1.0 / h_row["score"], 4) if h_row and h_row["score"] > 0 else None,
            })

    for r in board["rows"]:
        if r["kind"] in ("baseline", "human"):
            r["harness_version"] = None

    opt_cols_total = len(h2_games_by_col)
    if opt_cols_total > 1:
        for r in board["rows"]:
            if r["player_id"] == "optimal" and "[" not in str(r.get("display_name") or ""):
                r["display_name"] = f"Optimal [{r['collection']}]"

    board["harness_version"] = "h2"
    board["h2_rules"] = H2_RULES_SUMMARY
    board["h2_games_by_collection"] = {c: sorted(gs) for c, gs in sorted(h2_games_by_col.items())}
    return board


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
    data = aggregate_runs(runs, models_registry=models, game_descs=games, harness_filter="h1")
    if out_path is not None:
        import json

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data
