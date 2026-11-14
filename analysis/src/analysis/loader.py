"""Shared trace, model-card, and collection loading utilities."""
from __future__ import annotations

import json
import os
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# Canonical rule events emitted by engine 0.2.0 and fake_engine
RULE_EVENTS: dict[str, tuple[str, ...]] = {
    "walls": ("bump", "level_complete"),
    "goal": ("level_complete", "game_won"),
    "move_budget": ("reset", "out_of_moves", "level_lost", "level_complete"),
    "keys_doors": ("picked_key", "opened_door"),
    "plates_gates": ("pressed_plate",),
    "teleporters": ("teleport",),
    "hazards": ("hurt",),
    "push_blocks": ("pushed",),
    "ice": ("slid:",),
    "one_way": ("bump", "level_complete"),
}

RULE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "walls": ("wall", "block", "grey", "obstacle", "corridor", "bump"),
    "goal": ("goal", "green", "target", "ring", "finish", "exit", "complete"),
    "move_budget": ("budget", "bar", "move", "timer", "limit", "reset", "yellow"),
    "keys_doors": ("key", "door", "unlock", "open", "pick", "collect"),
    "plates_gates": ("plate", "switch", "gate", "toggle", "button", "checker"),
    "teleporters": ("teleport", "portal", "warp", "pair", "jump", "x "),
    "hazards": ("hazard", "hurt", "damage", "health", "hp", "life", "avoid", "cross", "plus"),
    "push_blocks": ("push", "block", "box", "crate", "shove", "move block", "sokoban"),
    "ice": ("ice", "slid", "slip", "glide", "momentum"),
    "one_way": ("one-way", "one way", "arrow", "direction"),
}

TIER_ORDER = ("optimal", "human", "finetuned", "frontier", "open", "baseline")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def find_repo_root(start: Path | None = None) -> Path:
    cur = (start or Path(__file__)).resolve()
    if cur.is_file():
        cur = cur.parent
    for candidate in [cur, *cur.parents]:
        if (candidate / "contracts" / "derived.schema.json").exists() or (candidate / "PLAN.md").exists():
            return candidate
    return Path.cwd()


def default_data_dir() -> Path:
    env = os.environ.get("DATA_DIR")
    if env:
        return Path(env).expanduser()
    return Path.home() / "junction-data"


def load_models(repo_root: Path | None = None) -> dict[str, dict[str, Any]]:
    root = repo_root or find_repo_root()
    p = root / "arena" / "models.yaml"
    if not p.exists():
        return {}
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    out: dict[str, dict[str, Any]] = {}
    for idx, entry in enumerate(raw):
        if not isinstance(entry, dict) or not entry.get("id"):
            continue
        card = {
            "id": str(entry["id"]),
            "display_name": str(entry.get("display_name") or entry["id"]),
            "provider": str(entry.get("provider") or "unknown"),
            "api_model": str(entry.get("api_model") or entry["id"]),
            "tier": str(entry.get("tier") or "open"),
            "input_modes": list(entry.get("input_modes") or ["text"]),
            "efforts": list(entry.get("efforts") or []),
            "price_in": entry.get("price_in"),
            "price_out": entry.get("price_out"),
            "params": entry.get("params"),
            "link": entry.get("link"),
        }
        # Keep non-schema internal order index out of model_card; attach alongside
        out[card["id"]] = {"card": card, "order": idx}
    return out


def load_collections(repo_root: Path | None = None) -> dict[str, dict[str, Any]]:
    root = repo_root or find_repo_root()
    games: dict[str, dict[str, Any]] = {}
    col_dir = root / "data" / "collections"
    if col_dir.exists():
        for path in sorted(col_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            for g in data.get("games", []):
                if isinstance(g, dict) and g.get("game_id"):
                    games[g["game_id"]] = g
    fx_games = root / "data" / "fixtures" / "games"
    if fx_games.exists():
        for path in sorted(fx_games.glob("*.json")):
            try:
                g = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(g, dict) and g.get("game_id") and g["game_id"] not in games:
                games[g["game_id"]] = g
    return games


def normalize_player(player: dict[str, Any]) -> tuple[str, str, str | None, str]:
    """Return (player_id, kind, effort, display_name)."""
    kind = str(player.get("kind") or "baseline")
    raw_id = str(player.get("model_id") or player.get("name") or "unknown")
    name = str(player.get("name") or raw_id)
    effort = player.get("effort")
    if kind == "baseline":
        pid = raw_id.removeprefix("baseline:")
        return pid, "baseline", None, pid
    if kind == "human":
        return "human", "human", None, "Human"
    return raw_id, "model", str(effort) if effort else None, name


def load_runs(runs_dir: Path, include_in_progress: bool = False) -> list[dict[str, Any]]:
    if not runs_dir.exists():
        return []
    runs: list[dict[str, Any]] = []
    for meta_path in sorted(runs_dir.glob("*/meta.json")):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        outcome = meta.get("outcome")
        if not include_in_progress and (outcome in (None, "IN_PROGRESS")):
            continue
        steps_path = meta_path.parent / "steps.jsonl"
        steps: list[dict[str, Any]] = []
        if steps_path.exists():
            for line in steps_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    steps.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        steps.sort(key=lambda s: int(s.get("i", 0)))
        runs.append({"meta": meta, "steps": steps})
    return runs


def _playfield_unchanged(prev_frame: list[str] | None, curr_frame: list[str] | None) -> bool:
    if not prev_frame or not curr_frame or len(prev_frame) < 64 or len(curr_frame) < 64:
        return False
    # Rows 0..5 contain HUD (budget bar, pips, inventory); rows 6..63 are pure playfield
    return prev_frame[6:] == curr_frame[6:]


def _expected_belief(state: str | None) -> str:
    if state == "WIN":
        return "won"
    if state == "GAME_OVER":
        return "lost"
    return "playing"


def matches_rule_hypothesis(rule: str, text: str | None) -> bool:
    if not text:
        return False
    low = f" {text.lower()} "
    if rule.lower() in low or rule.replace("_", " ").lower() in low:
        return True
    kws = RULE_KEYWORDS.get(rule, ())
    return any(kw in low for kw in kws)


def triggers_rule_event(rule: str, events: list[str]) -> bool:
    prefixes = RULE_EVENTS.get(rule, ())
    for ev in events:
        for pref in prefixes:
            if pref.endswith(":"):
                if ev.startswith(pref):
                    return True
            elif ev == pref:
                return True
    return False


def extract_level_segments(run: dict[str, Any], game_desc: dict[str, Any] | None = None) -> dict[str, Any]:
    """Segment a run into level 1..levels_total metrics and step-level diagnostics."""
    meta = run["meta"]
    steps = run["steps"]
    levels_total = int(meta.get("levels_total") or (game_desc or {}).get("levels_total") or 1)
    desc_levels = {int(lv["level"]): lv for lv in (game_desc or {}).get("levels", []) if "level" in lv}

    segments: dict[int, dict[str, Any]] = {}
    for lv_num in range(1, levels_total + 1):
        dlv = desc_levels.get(lv_num, {})
        segments[lv_num] = {
            "level": lv_num,
            "optimal_moves": int(dlv.get("optimal_moves") or 0),
            "move_budget": int(dlv.get("move_budget") or 0),
            "active_rules": list(dlv.get("rules") or []),
            "new_rule": dlv.get("new_rule"),
            "actions_used": 0,
            "resets": 0,
            "solved": False,
            "level_score": 0.0,
            "no_effect_actions": 0,
            "first_rule_event_step": None,
            "hypothesis_matched": False,
            "belief_total": 0,
            "belief_correct": 0,
            "latencies": [],
            "steps": [],
        }

    prev_step: dict[str, Any] | None = None
    belief_total = 0
    belief_correct = 0
    no_effect_total = 0
    latencies: list[int] = []

    for step in steps:
        action = step.get("action")
        if action is None and int(step.get("i", 0)) == 0:
            prev_step = step
            continue

        pre_truth = (prev_step or step).get("truth") or {}
        post_truth = step.get("truth") or {}
        lv_num = int(pre_truth.get("level") or post_truth.get("level") or 1)
        if lv_num not in segments:
            segments[lv_num] = {
                "level": lv_num,
                "optimal_moves": int(pre_truth.get("optimal_moves") or 0),
                "move_budget": int(pre_truth.get("move_budget") or 0),
                "active_rules": list(pre_truth.get("active_rules") or []),
                "new_rule": pre_truth.get("new_rule"),
                "actions_used": 0,
                "resets": 0,
                "solved": False,
                "level_score": 0.0,
                "no_effect_actions": 0,
                "first_rule_event_step": None,
                "hypothesis_matched": False,
                "belief_total": 0,
                "belief_correct": 0,
                "latencies": [],
                "steps": [],
            }

        seg = segments[lv_num]
        if not seg["optimal_moves"] and pre_truth.get("optimal_moves"):
            seg["optimal_moves"] = int(pre_truth["optimal_moves"])
        if not seg["move_budget"] and pre_truth.get("move_budget"):
            seg["move_budget"] = int(pre_truth["move_budget"])
        if not seg["active_rules"] and pre_truth.get("active_rules"):
            seg["active_rules"] = list(pre_truth["active_rules"])
        if seg["new_rule"] is None and pre_truth.get("new_rule") is not None:
            seg["new_rule"] = pre_truth.get("new_rule")

        seg["actions_used"] += 1
        step_in_level = seg["actions_used"]
        if action == "RESET":
            seg["resets"] += 1

        events = list(post_truth.get("events") or [])
        prev_frame = prev_step.get("frame") if prev_step else None
        curr_frame = step.get("frame")
        is_no_effect = (action != "RESET") and (
            "bump" in events or _playfield_unchanged(prev_frame, curr_frame)
        )
        if is_no_effect:
            seg["no_effect_actions"] += 1
            no_effect_total += 1

        # Track rule discovery signals on introducing levels
        intro_rule = seg["new_rule"]
        if intro_rule:
            if seg["first_rule_event_step"] is None and triggers_rule_event(intro_rule, events):
                seg["first_rule_event_step"] = step_in_level
            hyp_text = " ".join(
                str(x) for x in (step.get("hypothesis"), step.get("reasoning")) if x
            )
            if not seg["hypothesis_matched"] and matches_rule_hypothesis(intro_rule, hyp_text):
                seg["hypothesis_matched"] = True

        # Belief calibration
        belief = step.get("belief")
        if belief in ("playing", "won", "lost"):
            expected = _expected_belief(post_truth.get("state"))
            seg["belief_total"] += 1
            belief_total += 1
            if belief == expected:
                seg["belief_correct"] += 1
                belief_correct += 1

        lat = step.get("latency_ms")
        if isinstance(lat, (int, float)) and lat >= 0:
            seg["latencies"].append(int(lat))
            latencies.append(int(lat))

        post_level = int(post_truth.get("level") or lv_num)
        solved_now = (
            "level_complete" in events
            or "game_won" in events
            or post_truth.get("state") == "WIN"
            or post_level > lv_num
        )
        if solved_now:
            seg["solved"] = True

        seg["steps"].append({
            "i": int(step.get("i", step_in_level)),
            "action": action,
            "events": events,
            "no_effect": is_no_effect,
            "belief": belief,
            "expected_belief": _expected_belief(post_truth.get("state")),
        })
        prev_step = step

    # Fallback if trace had zero steps for completed levels (e.g., synthetic summary)
    levels_completed_meta = int(meta.get("levels_completed") or 0)
    level_scores: list[float] = []
    for lv_num in sorted(segments):
        seg = segments[lv_num]
        if lv_num <= levels_completed_meta and not seg["solved"] and seg["actions_used"] > 0:
            seg["solved"] = True
        if seg["solved"]:
            opt = seg["optimal_moves"]
            used = seg["actions_used"]
            if opt <= 0:
                seg["level_score"] = 1.0 if used >= 0 else 0.0
            elif used <= 0:
                seg["level_score"] = 0.0
            else:
                seg["level_score"] = min(1.0, opt / used)
        else:
            seg["level_score"] = 0.0
        if seg["solved"] and seg["first_rule_event_step"] is None and seg["new_rule"]:
            # E.g. one_way traversed purely along arrows without bumping
            seg["first_rule_event_step"] = seg["actions_used"]
        level_scores.append(seg["level_score"])

    game_score = statistics.fmean(level_scores) if level_scores else 0.0
    return {
        "levels_total": levels_total,
        "levels_solved": sum(1 for s in segments.values() if s["solved"]),
        "game_score": game_score,
        "segments": segments,
        "no_effect_total": no_effect_total,
        "belief_total": belief_total,
        "belief_correct": belief_correct,
        "latencies": latencies,
    }
