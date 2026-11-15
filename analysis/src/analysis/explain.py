"""Truth-Diffed Reasoning Forensics & Failure Explanation Builder (`data/derived/explanations.json`).

Implements Truth-Diffed Reasoning Forensics:
- Slices ±2-step inflection windows per failed level (initial path divergence, first rule event,
  `no_effect` streak onset, hypothesis shifts, adverse truth events, and RESET/terminal steps),
  pairing BOTH `step.reasoning` (`<think>` CoT / scratchpad notes) AND `step.hypothesis` with engine `truth`.
- Tags `reasoning_source` (`cot` | `notes` | `hypothesis_only` | `none`) so `h2` Chain-of-Thought,
  `h1` rolling notes, and API-encrypted thinking models (`gemini-pro` on `h2`) are never conflated.
- Classifies each failed level across a 5-stage Cognitive Bottleneck Funnel (`perception`,
  `rule_induction`, `belief_updating`, `spatial_planning`, `budget_management`), 7 root causes,
  and `deduced_rule_in_cot` (isolating the **Knowing–Doing Gap**: models that explicitly articulate
  the hidden mechanic in CoT/notes yet fail multi-step spatial execution).
- Supports cost estimation (`--estimate`), JSONL prompt/reply batch hooks for `arena judge`
  (`--export-prompts`, `--import-replies`), direct `arena.judge.complete` (`--judge-arena`),
  and deterministic truth-diffed reasoning analysis (`reasoning-auditor-v2`) offline.
- Strictly verifies that every `evidence_quote` is an exact verbatim substring of recorded step text.
"""
from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from .loader import (
    TIER_0_RULES,
    extract_level_segments,
    find_repo_root,
    normalize_player,
    now_iso,
)

ACTION_ARROWS: dict[str, str] = {
    "ACTION1": "↑",
    "ACTION2": "↓",
    "ACTION3": "←",
    "ACTION4": "→",
    "ACTION5": "␣",
    "RESET": "R",
}

COGNITIVE_STAGES: tuple[str, ...] = (
    "perception",
    "rule_induction",
    "belief_updating",
    "spatial_planning",
    "budget_management",
)

COGNITIVE_STAGE_LABELS: dict[str, str] = {
    "perception": "1 · Perception",
    "rule_induction": "2 · Rule Induction",
    "belief_updating": "3 · Belief Updating",
    "spatial_planning": "4 · Spatial Planning",
    "budget_management": "5 · Budget Management",
}

ROOT_CAUSES: tuple[str, ...] = (
    "coordinate_misread",
    "unprobed_new_rule",
    "false_rule_hypothesis",
    "ignored_falsifying_feedback",
    "knew_rule_failed_rollout",
    "hazard_collision",
    "sunk_cost_late_reset",
)

ADVERSE_EVENTS: frozenset[str] = frozenset({
    "hurt",
    "enemy_hit",
    "caught",
    "floor_collapsed",
    "checkpoints_reset",
    "decoy",
    "crushed",
    "shadow_hit",
})

# High-precision word-boundary regexes for non-Tier-0 mechanics (avoids generic false positives like "x " or "in order to")
STRICT_RULE_DEDUCTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "keys_doors": re.compile(r"\b(keys?|locked\s+doors?|unlock\w*|doors?)\b", re.IGNORECASE),
    "plates_gates": re.compile(r"\b(pressure\s+plates?|plates?|switch(?:es)?|gates?|toggl\w+)\b", re.IGNORECASE),
    "teleporters": re.compile(r"\b(teleport\w*|portals?|warp\w*|paired\s+pads?)\b", re.IGNORECASE),
    "hazards": re.compile(r"\b(hazards?|damag\w+|hurts?|lose\s+health|health\s+bar|\bhp\b|spikes?|red\s+cross\w*|traps?)\b", re.IGNORECASE),
    "push_blocks": re.compile(r"\b(push(?:able|ing|ed)?\s*(?:blocks?|boxes|crates?|tiles?)?|movable\s+blocks?|crates?|sokoban|shov\w+)\b", re.IGNORECASE),
    "ice": re.compile(r"\b(ice|icy|slid(?:e|es|ing)|slippery|glid\w+|until\s+(?:hitting|blocked|wall))\b", re.IGNORECASE),
    "one_way": re.compile(r"\b(one[- ]way|directional\s+tiles?|arrow\s+tiles?|permitted\s+direction|cannot\s+go\s+back)\b", re.IGNORECASE),
    "collect_all": re.compile(r"\b(collect\s+all|all\s+(?:gems?|shards?|tokens?|diamonds?|items?)|gems?|shards?|diamonds?)\b", re.IGNORECASE),
    "phase_walls": re.compile(r"\b(phas(?:e|ing)\s*walls?|alternating\s+walls?|every\s+other\s+(?:step|move|turn)|periodic\w*|parity|open\s+and\s+close)\b", re.IGNORECASE),
    "rotation": re.compile(r"\b(rotat(?:e|ed|es|ing|ion)|90[- ]degree\w*|clockwise|counter[- ]clockwise|orientation\s+shift\w*)\b", re.IGNORECASE),
    "remap": re.compile(r"\b(remap\w*|inverted\s+controls?|swapped\s+controls?|controls?\s+changed|action\d\s+maps?\s+to|reversed\s+controls?)\b", re.IGNORECASE),
    "twin": re.compile(r"\b(twins?|two\s+(?:avatars?|players?|sprites?|characters?|agents?)|both\s+(?:avatars?|players?|sprites?|units?)|coupled|synchronized|mirror(?:ed)?\s+move\w*)\b", re.IGNORECASE),
    "stamina": re.compile(r"\b(stamina|energy\s+(?:bar|meter|pads?)|refill\w*|recharg\w+|deplet\w+)\b", re.IGNORECASE),
    "cracked_floor": re.compile(r"\b(cracked|collaps(?:e|es|ed|ing)|crumbl\w+|brittle|step\s+once|disappear\w*\s+after)\b", re.IGNORECASE),
    "beacon_goal": re.compile(r"\b(beacons?|decoys?|fake\s+goals?|real\s+goal|true\s+goal|matching\s+(?:color|colour)|hud\s+(?:color|colour|beacon|indicator))\b", re.IGNORECASE),
    "conveyors": re.compile(r"\b(conveyors?|belts?|drift(?:s|ed|ing)?|carried|pushed\s+after)\b", re.IGNORECASE),
    "enemies": re.compile(r"\b(enem(?:y|ies)|patrol\w*|moving\s+(?:hazard|obstacle|guard)|guards?|chasers?)\b", re.IGNORECASE),
    "gravity": re.compile(r"\b(gravity|falls?\s+down\w*|falling|drop(?:s|ped)?\s+down)\b", re.IGNORECASE),
    "checkpoints": re.compile(r"\b(checkpoints?|in\s+sequence|strict\s+order|numbered\s+rings?|pips?\s+(?:reset|cleared)|out\s+of\s+(?:order|turn))\b", re.IGNORECASE),
    "no_reverse": re.compile(r"\b(no[- ]reverse|cannot\s+reverse|u[- ]turns?|backtrack\w*|trail\s+tiles?|violet\s+trail)\b", re.IGNORECASE),
    "pits": re.compile(r"\b(pits?|fill\s+the\s+(?:pit|hole|gap)|bridge\s+the|push\s+\w+\s+into|chasms?)\b", re.IGNORECASE),
    "momentum": re.compile(r"\b(momentum|coasting|keep\s+moving)\b", re.IGNORECASE),
    "boulders": re.compile(r"\b(boulders?|falling\s+rocks?|crush\w+)\b", re.IGNORECASE),
    "shadow": re.compile(r"\b(shadows?|delayed\s+clone|follower)\b", re.IGNORECASE),
    "board_flip": re.compile(r"\b(board\s+flip\w*|flipped\s+board|upside\s+down)\b", re.IGNORECASE),
}

MOTION_HALLUCINATION_RE = re.compile(
    r"\b(moved\s+(?:up|down|left|right|to)|now\s+at\s*\(|stepped\s+onto|reached\s+the|successfully\s+moved)\b",
    re.IGNORECASE,
)
BLOCK_ACKNOWLEDGED_RE = re.compile(
    r"\b(blocked|wall|bump\w*|didn'?t\s+move|did\s+not\s+move|unchanged|same\s+position|no\s+effect|stuck|cannot\s+move|can'?t\s+move)\b",
    re.IGNORECASE,
)
CAUSAL_SIGNAL_RE = re.compile(
    r"\b(because|since|therefore|means|wait|realize|notice|blocked|wall|goal|key|door|ice|slide|twin|portal|teleport|plate|gate|checkpoint|hazard|crack|decoy|beacon|conveyor|enemy|reset|budget)\b",
    re.IGNORECASE,
)

RULE_HINTS: dict[str, str] = {
    "keys_doors": "pick up the matching key before stepping onto the locked door",
    "plates_gates": "step onto the pressure plate to toggle the linked gate open",
    "teleporters": "enter a teleporter portal to warp across the wall gap to its paired exit",
    "hazards": "route around hazard cross tiles or budget HP before reaching the goal",
    "push_blocks": "push movable crates out of chokepoints without corner-locking them",
    "ice": "launch onto ice along a line that stops against a wall or solid block aligned with the route",
    "one_way": "traverse directional arrow tiles only in their permitted travel direction",
    "collect_all": "collect every required shard/gem before entering the goal ring",
    "phase_walls": "time movements with alternating open/closed phase-wall parity",
    "rotation": "account for 90-degree orientation shifts when mapping actions to board directions",
    "remap": "probe action-to-direction remapping early instead of assuming default arrow bindings",
    "twin": "coordinate both coupled twin avatars around obstacles simultaneously",
    "stamina": "visit stamina refill pads before exhausting movement energy",
    "cracked_floor": "cross brittle cracked-floor bridges at most once without backtracking over collapsed tiles",
    "beacon_goal": "match the HUD beacon colour/glyph and avoid decoy goals",
    "conveyors": "compensate for post-step conveyor belt drift",
    "enemies": "time corridor crossings around deterministic patrolling enemies",
    "gravity": "account for post-move downward gravity fall",
    "checkpoints": "visit all azure checkpoints in strict solid-first sequence without stepping on later rings early",
    "no_reverse": "use loops/detours instead of immediate 180-degree U-turns onto the violet trail tile",
    "pits": "shove a push-block into the white checker pit to permanently bridge the chokepoint",
    "move_budget": "reset early once exploratory moves exceed optimal slack so enough budget remains for execution",
    "walls": "navigate around solid wall cells instead of repeating blocked moves",
}

JUDGE_SYSTEM_PROMPT = (
    "You are an exact cognitive failure auditor for novel 64x64 gridworld games. "
    "You receive ground-truth level mechanics, the BFS optimal path, and a model's step-by-step actions, "
    "engine truth events, Chain-of-Thought/notes (`rsn`), and structured `hyp` across key inflection windows. "
    "Playing models never saw rule names or truth events. Contrast what the model claimed in `rsn`/`hyp` against "
    "what engine `events`/`[NO_EFFECT]` actually recorded. Identify: "
    "(1) 1-based `step` where the failure/divergence is clearest, "
    "(2) `rule` misunderstood or mis-executed, "
    "(3) `verdict` (`never_used_rule` | `wrong_hypothesis` | `ignored_no_effect` | `late_reset` | `hazard_loss` | `ran_out_of_budget`), "
    "(4) `cognitive_stage` (`perception` | `rule_induction` | `belief_updating` | `spatial_planning` | `budget_management`), "
    "(5) `root_cause` (`coordinate_misread` | `unprobed_new_rule` | `false_rule_hypothesis` | `ignored_falsifying_feedback` | `knew_rule_failed_rollout` | `hazard_collision` | `sunk_cost_late_reset`), "
    "(6) `deduced_rule_in_cot` (boolean: true ONLY if the model explicitly articulated the non-trivial mechanic before failing execution), "
    "(7) `truth_contrast` (1 sentence contrasting model belief/reasoning vs engine truth), "
    "(8) `explanation` (1-2 sentences: what went wrong and what optimal play required), and "
    "(9) exact verbatim `evidence_quote` copied from `rsn` or `hyp` on that level (or null if none). "
    "Reply ONLY with valid JSON."
)


def _load_engine_describe(game_id: str, repo_root: Path) -> dict[str, Any] | None:
    """Resolve full level `describe()` (including `optimal_path`) from engine or fake_engine when available."""
    eng_src = repo_root / "engine" / "src"
    if eng_src.exists() and str(eng_src) not in sys.path:
        sys.path.insert(0, str(eng_src))
    try:
        from engine import make_game  # type: ignore
        from engine.core.game import spec_from_game_id  # type: ignore

        if game_id.startswith("gridworld-"):
            spec = spec_from_game_id(game_id)
            return make_game(spec).describe()
    except Exception:
        pass

    srv_src = repo_root / "server" / "src"
    if srv_src.exists() and str(srv_src) not in sys.path:
        sys.path.insert(0, str(srv_src))
    try:
        from server import fake_engine  # type: ignore

        spec = fake_engine.spec_from_game_id(game_id)
        return fake_engine.FakeGame(spec).describe()
    except Exception:
        return None


def _format_arrow_path(optimal_path: list[str] | None, max_len: int = 12) -> str:
    if not optimal_path:
        return ""
    arrows = [ACTION_ARROWS.get(a, a) for a in optimal_path[:max_len]]
    suffix = " …" if len(optimal_path) > max_len else ""
    return "".join(arrows) + suffix


def _verbatim_excerpt(
    text: str | None,
    max_chars: int = 180,
    focus_pattern: re.Pattern[str] | None = None,
) -> str | None:
    """Return an exact contiguous substring of `text` (never normalized/mutated) for claim verification."""
    if not text:
        return None
    stripped = text.strip()
    if not stripped:
        return None
    if len(stripped) <= max_chars:
        assert stripped in text
        return stripped

    # When a focus pattern (e.g. rule deduction or causal phrase) hits deep inside a long CoT block,
    # center a clean word-bounded window around that match while preserving exact substring identity.
    pattern = focus_pattern or CAUSAL_SIGNAL_RE
    m = pattern.search(stripped)
    if m and m.start() > max_chars // 2:
        half = max_chars // 2
        raw_start = max(0, m.start() - half)
        if raw_start > 0:
            ws = stripped.find(" ", raw_start)
            if 0 <= ws < m.start():
                raw_start = ws + 1
        raw_end = min(len(stripped), raw_start + max_chars)
        if raw_end < len(stripped):
            ws_end = stripped.rfind(" ", raw_start + max_chars // 2, raw_end)
            if ws_end > raw_start:
                raw_end = ws_end
        window = stripped[raw_start:raw_end].strip()
        if window and window in text:
            return window

    # Default: cut cleanly on whitespace from start of `stripped`
    cut = stripped.rfind(" ", 0, max_chars)
    if cut < max_chars // 2:
        cut = max_chars
    sub = stripped[:cut].strip()
    assert sub in text
    return sub


def _classify_reasoning_source(steps: list[dict[str, Any]], harness_version: str) -> str:
    rsn_count = sum(1 for st in steps if isinstance(st.get("reasoning"), str) and st["reasoning"].strip())
    hyp_count = sum(1 for st in steps if isinstance(st.get("hypothesis"), str) and st["hypothesis"].strip())
    if rsn_count > 0:
        return "cot" if harness_version == "h2" else "notes"
    if hyp_count > 0:
        return "hypothesis_only"
    return "none"


def _detect_rule_deduction(
    steps: list[dict[str, Any]],
    target_rule: str | None,
) -> tuple[bool, int | None, str | None]:
    """Check if and when the model explicitly articulated `target_rule` (non-Tier-0) in reasoning/hypothesis."""
    if not target_rule or target_rule in TIER_0_RULES:
        return False, None, None
    pat = STRICT_RULE_DEDUCTION_PATTERNS.get(target_rule)
    if pat is None:
        pat = re.compile(rf"\b{re.escape(target_rule.replace('_', ' '))}\b", re.IGNORECASE)

    first_match_i: int | None = None
    first_match_field: str | None = None
    for st in steps:
        for field in ("reasoning", "hypothesis"):
            raw = st.get(field)
            if isinstance(raw, str) and pat.search(raw):
                first_match_i = int(st["i"])
                first_match_field = field
                break
        if first_match_i is not None:
            break

    if first_match_i is None:
        return False, None, None

    # Pre-terminal requirement: articulating a mechanic on an earlier step (with >=1 subsequent action
    # on the level) proves genuine Knowing-Doing divergence rather than a terminal impact observation.
    last_i = int(steps[-1]["i"]) if steps else first_match_i
    deduced_before_end = first_match_i < last_i
    return deduced_before_end, first_match_i, first_match_field


def build_failure_packets(
    runs: list[dict[str, Any]],
    game_descs: dict[str, dict[str, Any]] | None = None,
    repo_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Build structured diagnostic packets for every attempted failed level across model runs."""
    root = repo_root or find_repo_root()
    descs = dict(game_descs or {})
    full_desc_cache: dict[str, dict[str, Any] | None] = {}
    packets: list[dict[str, Any]] = []

    for run in runs:
        meta = run.get("meta") or {}
        player = meta.get("player") or {}
        player_id, kind, effort, _ = normalize_player(player)
        if kind != "model":
            continue

        run_id = str(meta.get("run_id") or "")
        game_id = str(meta.get("game_id") or "")
        if not run_id or not game_id:
            continue

        harness_version = str(meta.get("harness_version") or player.get("harness_version") or "h1").strip() or "h1"
        collection = str(meta.get("collection") or "dev")

        base_desc = descs.get(game_id) or {}
        if game_id not in full_desc_cache:
            if any("optimal_path" in lv for lv in (base_desc.get("levels") or [])):
                full_desc_cache[game_id] = base_desc
            else:
                full_desc_cache[game_id] = _load_engine_describe(game_id, root) or base_desc
        desc = full_desc_cache[game_id] or base_desc
        desc_levels = {int(lv["level"]): lv for lv in (desc.get("levels") or []) if "level" in lv}

        seg_info = extract_level_segments(run, desc)
        for lv_num in sorted(seg_info["segments"]):
            seg = seg_info["segments"][lv_num]
            if seg["solved"] or seg["actions_used"] <= 0:
                continue
            dlv = desc_levels.get(lv_num, {})
            optimal_path = list(dlv.get("optimal_path") or [])
            lv_steps = seg["steps"]
            packets.append({
                "run_id": run_id,
                "game_id": game_id,
                "collection": collection,
                "harness_version": harness_version,
                "reasoning_source": _classify_reasoning_source(lv_steps, harness_version),
                "player_id": f"{player_id}:{effort}" if effort else player_id,
                "raw_player_id": player_id,
                "effort": effort,
                "outcome": meta.get("outcome"),
                "level": lv_num,
                "active_rules": list(seg["active_rules"] or dlv.get("rules") or []),
                "new_rule": seg["new_rule"] or dlv.get("new_rule"),
                "optimal_moves": int(seg["optimal_moves"] or dlv.get("optimal_moves") or 0),
                "move_budget": int(seg["move_budget"] or dlv.get("move_budget") or 0),
                "optimal_path": optimal_path,
                "actions_used": int(seg["actions_used"]),
                "resets": int(seg["resets"]),
                "no_effect_actions": int(seg["no_effect_actions"]),
                "first_rule_event_step": seg["first_rule_event_step"],
                "hypothesis_matched": bool(seg["hypothesis_matched"]),
                "steps": lv_steps,
            })
    return packets


def slice_inflection_windows(
    packet: dict[str, Any],
    radius: int = 2,
    max_steps: int = 24,
) -> list[int]:
    """Select sorted 0-based indices into `packet['steps']` covering ±radius windows around key inflections."""
    steps = packet["steps"]
    n = len(steps)
    if n <= max_steps:
        return list(range(n))

    anchors: list[int] = [0, min(1, n - 1), n - 1]
    non_tier0 = [r for r in packet.get("active_rules", []) if r not in TIER_0_RULES]
    target_rule = packet.get("new_rule") or (non_tier0[-1] if non_tier0 else None)
    _, deduced_step_i, _ = _detect_rule_deduction(steps, target_rule)

    streak = 0
    added_streak_anchor = False
    prev_hyp: str | None = None
    hyp_shifts = 0

    for idx, st in enumerate(steps):
        evs = st.get("events") or []
        if deduced_step_i is not None and int(st["i"]) == deduced_step_i:
            anchors.append(idx)
        if any(ev in ADVERSE_EVENTS for ev in evs) or st.get("action") == "RESET":
            anchors.append(idx)
        elif evs and any(ev != "bump" for ev in evs):
            anchors.append(idx)

        if st.get("no_effect"):
            streak += 1
            if streak == 2 and not added_streak_anchor:
                anchors.append(idx)
                added_streak_anchor = True
        else:
            streak = 0

        bel = st.get("belief")
        if bel in ("playing", "won", "lost") and bel != st.get("expected_belief"):
            anchors.append(idx)

        hyp = st.get("hypothesis")
        if isinstance(hyp, str) and hyp.strip() and hyp != prev_hyp:
            if hyp_shifts < 4:
                anchors.append(idx)
            hyp_shifts += 1
            prev_hyp = hyp

    chosen: set[int] = set()
    # Add exact anchors first, then ±1, then ±radius until max_steps
    for d in range(0, radius + 1):
        for a in anchors:
            for cand in (a - d, a + d):
                if 0 <= cand < n:
                    chosen.add(cand)
                    if len(chosen) >= max_steps:
                        return sorted(chosen)
    return sorted(chosen)


def build_judge_prompt(packet: dict[str, Any]) -> str:
    """Format a step-aligned inflection-window prompt pairing BOTH `reasoning` and `hypothesis` with `truth`."""
    trace_lines: list[str] = []
    steps = packet["steps"]
    keep_indices = slice_inflection_windows(packet, radius=2, max_steps=24)
    non_tier0 = [r for r in packet.get("active_rules", []) if r not in TIER_0_RULES]
    target_rule = packet.get("new_rule") or (non_tier0[-1] if non_tier0 else None)
    focus_pat = STRICT_RULE_DEDUCTION_PATTERNS.get(target_rule) if target_rule else None

    prev_idx = -1
    for idx in keep_indices:
        if prev_idx >= 0 and idx > prev_idx + 1:
            trace_lines.append(f"  ... ({idx - prev_idx - 1} intermediate step(s) omitted) ...")
        prev_idx = idx
        st = steps[idx]
        ev = ",".join(st.get("events") or []) or "-"
        rsn = _verbatim_excerpt(st.get("reasoning"), 220, focus_pattern=focus_pat)
        hyp = _verbatim_excerpt(st.get("hypothesis"), 130)
        parts = [f"  step {st['i']}: action={st['action']} events=[{ev}]"]
        if st.get("no_effect"):
            parts.append("[NO_EFFECT]")
        if st.get("belief") and st.get("belief") != st.get("expected_belief"):
            parts.append(f"[BELIEF={st['belief']}!=TRUTH={st.get('expected_belief')}]")
        if rsn:
            parts.append(f'rsn="{rsn}"')
        if hyp and hyp != rsn:
            parts.append(f'hyp="{hyp}"')
        trace_lines.append(" ".join(parts))

    arrows = _format_arrow_path(packet.get("optimal_path"), max_len=20)
    return (
        f"Run: {packet['run_id']} | Model: {packet['player_id']} | Harness: {packet.get('harness_version', 'h1')} "
        f"(reasoning_source={packet.get('reasoning_source', 'notes')}) | Game: {packet['game_id']} | Level: {packet['level']}\n"
        f"Active rules: {', '.join(packet['active_rules']) or 'walls, goal, move_budget'}\n"
        f"Newly introduced rule on this level: {packet['new_rule'] or 'none'}\n"
        f"Optimal moves: {packet['optimal_moves']} (budget: {packet['move_budget']})"
        f"{f' | Optimal path: {arrows}' if arrows else ''}\n"
        f"Model summary on level: {packet['actions_used']} actions, {packet['resets']} resets, "
        f"{packet['no_effect_actions']} no-effect moves, triggered_new_rule={packet['first_rule_event_step'] is not None}\n"
        "Inflection-window trace (truth events paired with model reasoning & hypothesis):\n"
        + "\n".join(trace_lines)
        + "\n\nReturn JSON: {\"step\": <int>, \"rule\": \"<rule>\", \"verdict\": \"<slug>\", "
        "\"cognitive_stage\": \"<perception|rule_induction|belief_updating|spatial_planning|budget_management>\", "
        "\"root_cause\": \"<slug>\", \"deduced_rule_in_cot\": <bool>, "
        "\"truth_contrast\": \"<1-sentence model claim vs engine truth>\", "
        "\"explanation\": \"<what failed and what optimal play required>\", \"evidence_quote\": <exact quote or null>}"
    )


def estimate_judge_cost(packets: list[dict[str, Any]]) -> dict[str, Any]:
    """Estimate token usage and USD spend before calling any external judge model."""
    prompts = [build_judge_prompt(p) for p in packets]
    chars_in = sum(len(p) + len(JUDGE_SYSTEM_PROMPT) for p in prompts)
    est_tokens_in = max(0, (chars_in + 3) // 4)
    est_tokens_out = len(packets) * 180
    # Gemini 3.x counts hidden thinking against output tokens (~1200 avg tokens/call)
    est_tokens_out_gemini = len(packets) * 1200
    # Reference rates ($/1M tokens): Gemini Flash ($0.50/$3, unlimited credits), Gemini Pro ($2/$12), Sonnet ($3/$15)
    cost_fast_usd = round((est_tokens_in * 0.50 + est_tokens_out_gemini * 3.00) / 1_000_000, 4)
    cost_gemini_pro_usd = round((est_tokens_in * 2.00 + est_tokens_out_gemini * 12.00) / 1_000_000, 4)
    cost_sonnet_usd = round((est_tokens_in * 3.00 + est_tokens_out * 15.00) / 1_000_000, 4)
    return {
        "failed_levels": len(packets),
        "est_tokens_in": est_tokens_in,
        "est_tokens_out": est_tokens_out,
        "est_cost_fast_judge_usd": cost_fast_usd,
        "est_cost_gemini_pro_usd": cost_gemini_pro_usd,
        "est_cost_sonnet_judge_usd": cost_sonnet_usd,
        "within_decisions_sweep_cap": max(cost_gemini_pro_usd, cost_sonnet_usd) <= 20.0,
    }


def _select_forensic_quote(
    steps: list[dict[str, Any]],
    target_i: int,
    target_rule: str | None = None,
    prefer_deduced_step: int | None = None,
) -> tuple[str | None, str | None]:
    """Select the highest-signal verbatim `(evidence_quote, quote_source)` near `target_i`."""
    focus_pat = STRICT_RULE_DEDUCTION_PATTERNS.get(target_rule) if target_rule else None
    scored: list[tuple[float, str, str]] = []

    for st in steps:
        st_i = int(st["i"])
        dist = abs(st_i - target_i)
        deduced_bonus = -1.5 if (prefer_deduced_step is not None and st_i == prefer_deduced_step) else 0.0
        for field in ("reasoning", "hypothesis"):
            raw = st.get(field)
            if not isinstance(raw, str) or not raw.strip():
                continue
            excerpt = _verbatim_excerpt(raw, 180, focus_pattern=focus_pat)
            if not excerpt:
                continue
            # Lower score is better: prioritize exact `target_i` first, then rich causal `reasoning` over generic `hypothesis`
            score = float(dist) * 3.0 + deduced_bonus
            if field == "reasoning" and len(excerpt) >= 24:
                score -= 0.6
            if focus_pat and focus_pat.search(excerpt):
                score -= 0.8
            elif CAUSAL_SIGNAL_RE.search(excerpt):
                score -= 0.3
            scored.append((score, excerpt, field))

    if not scored:
        return None, None
    scored.sort(key=lambda item: item[0])
    best_quote, best_source = scored[0][1], scored[0][2]
    return best_quote, best_source


def _verify_quote_in_steps(
    quote: str | None,
    steps: list[dict[str, Any]],
) -> tuple[str | None, str | None]:
    """Ensure any LLM-returned quote is an exact substring of recorded step text; return `(quote, source)`."""
    if not quote:
        return None, None
    q = quote.strip()
    if not q:
        return None, None
    for st in steps:
        for field in ("reasoning", "hypothesis"):
            raw = st.get(field)
            if isinstance(raw, str) and q in raw:
                return q, field
    return None, None


def synthesize_deterministic_explanation(packet: dict[str, Any]) -> dict[str, Any]:
    """Produce a truth-diffed forensic diagnosis (`reasoning-auditor-v2`) from reasoning, hypothesis, and engine truth."""
    steps = packet["steps"]
    new_rule = packet.get("new_rule")
    non_tier0_rules = [r for r in packet.get("active_rules", []) if r not in TIER_0_RULES]
    primary_rule = new_rule or (non_tier0_rules[-1] if non_tier0_rules else "walls")
    is_pure_tier0 = len(non_tier0_rules) == 0 and (not new_rule or new_rule in TIER_0_RULES)
    harness_version = str(packet.get("harness_version") or "h1")
    reasoning_source = str(packet.get("reasoning_source") or _classify_reasoning_source(steps, harness_version))
    source_label = {
        "cot": "h2 CoT",
        "notes": "h1 notes",
        "hypothesis_only": "hypothesis trace (CoT encrypted)",
        "none": "step trace",
    }.get(reasoning_source, "reasoning")

    # 1) Rule deduction check in CoT / notes / hypothesis
    deduced_rule_in_cot, deduced_rule_step, _ = _detect_rule_deduction(
        steps, None if is_pure_tier0 else primary_rule
    )

    # 2) Adverse truth events, no-effect streaks, belief mismatches, and motion hallucinations
    hazard_step = next(
        (st for st in steps if any(ev in ADVERSE_EVENTS for ev in (st.get("events") or []))),
        None,
    )

    consec_no_effect_step: dict[str, Any] | None = None
    consec_no_effect_max = 0
    unchanged_hyp_during_block = 0
    cur_unchanged_block = 0
    streak = 0
    prev_hyp: str | None = None
    hallucinated_motion_step: dict[str, Any] | None = None
    belief_mismatch_step: dict[str, Any] | None = None

    for idx, st in enumerate(steps):
        bel = st.get("belief")
        if belief_mismatch_step is None and bel in ("playing", "won", "lost") and bel != st.get("expected_belief"):
            belief_mismatch_step = st

        hyp = st.get("hypothesis")
        rsn = st.get("reasoning")
        combined_txt = " ".join(x for x in (rsn, hyp) if isinstance(x, str))

        if st.get("no_effect"):
            streak += 1
            if streak > consec_no_effect_max:
                consec_no_effect_max = streak
            if streak >= 2 and consec_no_effect_step is None:
                consec_no_effect_step = st
            if hyp and hyp == prev_hyp:
                cur_unchanged_block += 1
                unchanged_hyp_during_block = max(unchanged_hyp_during_block, cur_unchanged_block)
            else:
                cur_unchanged_block = 1
            if (
                hallucinated_motion_step is None
                and idx > 0
                and steps[idx - 1].get("no_effect")
                and combined_txt
                and MOTION_HALLUCINATION_RE.search(combined_txt)
                and not BLOCK_ACKNOWLEDGED_RE.search(combined_txt)
            ):
                hallucinated_motion_step = st
        else:
            streak = 0
            cur_unchanged_block = 0

        if isinstance(hyp, str) and hyp.strip():
            prev_hyp = hyp

    reset_step = next((st for st in steps if st.get("action") == "RESET"), None)
    last_step = steps[-1]
    opt_moves = packet["optimal_moves"]
    move_budget = packet["move_budget"]
    arrows = _format_arrow_path(packet.get("optimal_path"), max_len=10)
    arrow_clause = f" ({arrows})" if arrows else ""

    # 3) Legacy schema-compatible `rule`, `step`, `verdict`, and `explanation`
    if hazard_step is not None:
        evs = hazard_step.get("events") or []
        if "checkpoints_reset" in evs:
            rule = "checkpoints"
        elif "decoy" in evs:
            rule = "beacon_goal"
        elif "floor_collapsed" in evs:
            rule = "cracked_floor"
        elif "enemy_hit" in evs or "caught" in evs:
            rule = "enemies"
        else:
            rule = "hazards" if "hazards" in packet.get("active_rules", []) else primary_rule
        step_i = int(hazard_step["i"])
        verdict = "hazard_loss"
        hint = RULE_HINTS.get(rule, f"satisfy `{rule}` constraints")
        if deduced_rule_in_cot and deduced_rule_step is not None and deduced_rule_step < step_i:
            explanation = (
                f"Model identified `{primary_rule}` in {source_label} at step {deduced_rule_step}, "
                f"but triggered `{evs[0]}` under `{rule}` at step {step_i} during spatial rollout ({packet['actions_used']} moves). "
                f"Optimal play solves Level {packet['level']} in {opt_moves} moves{arrow_clause}: {hint}."
            )
        else:
            explanation = (
                f"At step {step_i}, the model triggered `{evs[0]}` under `{rule}` and spent {packet['actions_used']} moves "
                f"without recovering. Optimal play solves Level {packet['level']} in {opt_moves} moves{arrow_clause}: {hint}."
            )
    elif new_rule and packet["first_rule_event_step"] is None:
        rule = new_rule
        pivot = consec_no_effect_step or reset_step or last_step
        step_i = int(pivot["i"])
        verdict = "never_used_rule" if packet["hypothesis_matched"] else "wrong_hypothesis"
        hint = RULE_HINTS.get(rule, f"engage `{rule}` directly")
        explanation = (
            f"Across {packet['actions_used']} actions on Level {packet['level']} ({packet['no_effect_actions']} no-effect moves), "
            f"the model never triggered newly introduced mechanic `{rule}` (clearest stall at step {step_i}). "
            f"Optimal solution requires {opt_moves} moves{arrow_clause}: {hint}."
        )
    elif packet["no_effect_actions"] >= 3 and consec_no_effect_step is not None:
        rule = primary_rule
        step_i = int(consec_no_effect_step["i"])
        verdict = "ignored_no_effect"
        hint = RULE_HINTS.get(rule, "change route after a blocked move")
        explanation = (
            f"Starting at step {step_i}, the model repeated blocked/no-effect actions ({packet['no_effect_actions']} total on Level {packet['level']}) "
            f"instead of updating its plan for `{rule}`. "
            f"Optimal play completes the level in {opt_moves} moves{arrow_clause}: {hint}."
        )
    elif packet["resets"] > 0 and reset_step is not None and packet["actions_used"] > opt_moves:
        rule = new_rule or "move_budget"
        step_i = int(reset_step["i"])
        verdict = "late_reset"
        hint = RULE_HINTS.get(rule, RULE_HINTS["move_budget"])
        explanation = (
            f"The model reset at step {step_i} ({packet['resets']} reset(s), {packet['actions_used']} total moves on Level {packet['level']}) "
            f"without converging on the {opt_moves}-move path{arrow_clause}. Needed strategy: {hint}."
        )
    else:
        rule = primary_rule
        step_i = int(last_step["i"])
        verdict = "wrong_hypothesis" if (new_rule and not packet["hypothesis_matched"]) else "ran_out_of_budget"
        hint = RULE_HINTS.get(rule, "follow the shortest valid trajectory")
        if deduced_rule_in_cot and deduced_rule_step is not None:
            explanation = (
                f"Model deduced `{primary_rule}` in {source_label} by step {deduced_rule_step}, "
                f"but failed multi-step spatial execution across {packet['actions_used']} moves (budget {move_budget}). "
                f"Optimal play finishes Level {packet['level']} in {opt_moves} moves{arrow_clause}: {hint}."
            )
        else:
            explanation = (
                f"Run ended at step {step_i} on Level {packet['level']} after {packet['actions_used']} moves "
                f"(budget {move_budget}, outcome `{packet.get('outcome') or 'BUDGET'}`) while navigating `{rule}`. "
                f"Optimal play finishes in {opt_moves} moves{arrow_clause}: {hint}."
            )

    # 4) 5-Stage Cognitive Funnel (`cognitive_stage`) + 7 Root Causes (`root_cause`) + `truth_contrast`
    if is_pure_tier0:
        if packet["no_effect_actions"] >= 2 or belief_mismatch_step is not None or hallucinated_motion_step is not None:
            cognitive_stage = "perception"
            root_cause = "coordinate_misread"
            piv = hallucinated_motion_step or belief_mismatch_step or consec_no_effect_step or last_step
            truth_contrast = (
                f"Model misread 64x64 wall/goal coordinates around step {piv['i']} on a pure Tier-0 maze, "
                f"while engine truth recorded {packet['no_effect_actions']} blocked moves (`bump`, 0 playfield pixels changed; optimal: {opt_moves} moves)."
            )
        elif packet["resets"] > 0 and reset_step is not None:
            cognitive_stage = "budget_management"
            root_cause = "sunk_cost_late_reset"
            truth_contrast = (
                f"Model spent {packet['actions_used']} moves with {packet['resets']} reset(s) (first RESET at step {reset_step['i']}), "
                f"leaving insufficient budget for the {opt_moves}-move Tier-0 path."
            )
        else:
            cognitive_stage = "spatial_planning"
            root_cause = "knew_rule_failed_rollout"
            truth_contrast = (
                f"Model recognized basic walls/goal but wandered for {packet['actions_used']} moves without dead-end pruning "
                f"(engine optimal path: {opt_moves} moves{arrow_clause})."
            )
    elif deduced_rule_in_cot:
        # Model explicitly articulated the non-Tier-0 mechanic prior to terminal step -> Knowing-Doing regime
        if consec_no_effect_max >= 4 and unchanged_hyp_during_block >= 3:
            cognitive_stage = "belief_updating"
            root_cause = "ignored_falsifying_feedback"
            truth_contrast = (
                f"Despite mentioning `{primary_rule}` at step {deduced_rule_step}, model repeated {consec_no_effect_max} consecutive "
                f"zero-effect actions without revising its blocked route (engine truth: `bump` / unchanged playfield)."
            )
        elif (
            verdict == "late_reset"
            and reset_step is not None
            and move_budget > 0
            and packet["actions_used"] >= max(opt_moves * 2, int(move_budget * 0.75))
        ):
            cognitive_stage = "budget_management"
            root_cause = "sunk_cost_late_reset"
            truth_contrast = (
                f"Model deduced `{primary_rule}` by step {deduced_rule_step} but delayed RESET until step {reset_step['i']}, "
                f"exhausting {packet['actions_used']}/{move_budget} moves against a {opt_moves}-move solution."
            )
        elif hazard_step is not None:
            evs = hazard_step.get("events") or ["hazard"]
            cognitive_stage = "spatial_planning"
            root_cause = "hazard_collision"
            hz_i = int(hazard_step["i"])
            if deduced_rule_step is not None and deduced_rule_step <= hz_i:
                truth_contrast = (
                    f"Model articulated `{primary_rule}` in {source_label} at step {deduced_rule_step}, "
                    f"yet its trajectory collided with `{evs[0]}` at step {hz_i} (optimal: {opt_moves} moves)."
                )
            else:
                truth_contrast = (
                    f"After triggering `{evs[0]}` at step {hz_i}, model deduced `{primary_rule}` in {source_label} "
                    f"at step {deduced_rule_step} yet failed spatial recovery across {packet['actions_used']} moves (optimal: {opt_moves} moves)."
                )
        else:
            cognitive_stage = "spatial_planning"
            root_cause = "knew_rule_failed_rollout"
            truth_contrast = (
                f"Knowing-Doing Gap: {source_label} correctly identified `{primary_rule}` at step {deduced_rule_step}, "
                f"but multi-step rollout failed across {packet['actions_used']} actions (engine optimal: {opt_moves} moves{arrow_clause})."
            )
    else:
        # Model never articulated the non-Tier-0 mechanic before terminal step
        if belief_mismatch_step is not None and belief_mismatch_step.get("belief") == "won":
            cognitive_stage = "perception"
            root_cause = "coordinate_misread"
            truth_contrast = (
                f"Model reported `belief=won` at step {belief_mismatch_step['i']} while engine truth was "
                f"`{belief_mismatch_step.get('expected_belief')}` (`{primary_rule}` remained unsatisfied)."
            )
        elif hallucinated_motion_step is not None and consec_no_effect_max >= 3:
            cognitive_stage = "perception"
            root_cause = "coordinate_misread"
            truth_contrast = (
                f"Model claimed forward movement at step {hallucinated_motion_step['i']} while engine truth recorded "
                f"`[NO_EFFECT]` (`bump` / 0 pixels changed across {consec_no_effect_max} consecutive steps)."
            )
        elif new_rule and packet["first_rule_event_step"] is None and consec_no_effect_max < 4:
            cognitive_stage = "rule_induction"
            root_cause = "unprobed_new_rule"
            truth_contrast = (
                f"Model's {source_label} never identified `{new_rule}`, and engine truth confirms 0 `{new_rule}` "
                f"events across all {packet['actions_used']} actions."
            )
        elif consec_no_effect_max >= 3 and packet["no_effect_actions"] >= 4:
            cognitive_stage = "belief_updating"
            root_cause = "ignored_falsifying_feedback"
            truth_contrast = (
                f"Model executed {packet['no_effect_actions']} no-effect actions (streak of {consec_no_effect_max} starting near step {step_i}) "
                f"without inducing `{primary_rule}` or abandonar-rerouting around engine `bump` feedback."
            ).replace("abandonar-rerouting", "rerouting")
        elif verdict == "late_reset" and packet["resets"] >= 2 and reset_step is not None:
            cognitive_stage = "budget_management"
            root_cause = "sunk_cost_late_reset"
            truth_contrast = (
                f"Model spent {packet['actions_used']} moves across {packet['resets']} late resets (first at step {reset_step['i']}) "
                f"without inducing `{primary_rule}` in time for the {opt_moves}-move path."
            )
        else:
            cognitive_stage = "rule_induction"
            root_cause = "false_rule_hypothesis"
            ev_tag = (hazard_step.get("events") or ["stall"])[0] if hazard_step else "budget exhaustion"
            truth_contrast = (
                f"Model acted under an unverified hypothesis without deducing `{primary_rule}` in {source_label}; "
                f"engine truth recorded `{ev_tag}` at step {step_i} (optimal: {opt_moves} moves)."
            )

    prefer_step = deduced_rule_step if root_cause == "knew_rule_failed_rollout" else None
    quote, quote_source = _select_forensic_quote(
        steps,
        step_i,
        target_rule=None if is_pure_tier0 else primary_rule,
        prefer_deduced_step=prefer_step,
    )

    return {
        "run_id": packet["run_id"],
        "game_id": packet["game_id"],
        "collection": packet.get("collection", "dev"),
        "harness_version": harness_version,
        "player_id": packet["player_id"],
        "level": packet["level"],
        "step": step_i,
        "rule": rule,
        "verdict": verdict,
        "cognitive_stage": cognitive_stage,
        "root_cause": root_cause,
        "reasoning_source": reasoning_source,
        "deduced_rule_in_cot": deduced_rule_in_cot,
        "deduced_rule_step": deduced_rule_step,
        "truth_contrast": truth_contrast,
        "explanation": explanation,
        "evidence_quote": quote,
        "quote_source": quote_source,
        "judge_model": "reasoning-auditor-v2",
    }


def summarize_explanations(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute top-level Cognitive Bottleneck Funnel & Knowing-Doing Gap rollups across all diagnoses."""
    total = len(items)
    non_tier0_items = [e for e in items if e.get("rule") not in TIER_0_RULES]
    kd_count = sum(1 for e in non_tier0_items if bool(e.get("deduced_rule_in_cot")))
    kd_rate = round(kd_count / len(non_tier0_items), 4) if non_tier0_items else 0.0

    h1_items = [e for e in items if (e.get("harness_version") or "h1") != "h2"]
    h2_items = [e for e in items if e.get("harness_version") == "h2"]

    by_stage: list[dict[str, Any]] = []
    for stg in COGNITIVE_STAGES:
        stg_items = [e for e in items if e.get("cognitive_stage") == stg]
        stg_h1 = [e for e in h1_items if e.get("cognitive_stage") == stg]
        stg_h2 = [e for e in h2_items if e.get("cognitive_stage") == stg]
        rc_counts = Counter(str(e.get("root_cause") or "") for e in stg_items if e.get("root_cause"))
        top_rc = rc_counts.most_common(1)[0][0] if rc_counts else None
        by_stage.append({
            "stage": stg,
            "label": COGNITIVE_STAGE_LABELS.get(stg, stg),
            "count": len(stg_items),
            "share": round(len(stg_items) / total, 4) if total else 0.0,
            "h1_count": len(stg_h1),
            "h1_share": round(len(stg_h1) / len(h1_items), 4) if h1_items else 0.0,
            "h2_count": len(stg_h2),
            "h2_share": round(len(stg_h2) / len(h2_items), 4) if h2_items else 0.0,
            "top_root_cause": top_rc,
        })

    by_source = dict(Counter(str(e.get("reasoning_source") or "none") for e in items))

    def _harness_summary(sub: list[dict[str, Any]]) -> dict[str, Any]:
        sub_non_t0 = [e for e in sub if e.get("rule") not in TIER_0_RULES]
        sub_kd = sum(1 for e in sub_non_t0 if bool(e.get("deduced_rule_in_cot")))
        return {
            "total": len(sub),
            "non_tier0_total": len(sub_non_t0),
            "knowing_doing_gap_count": sub_kd,
            "knowing_doing_gap_rate": round(sub_kd / len(sub_non_t0), 4) if sub_non_t0 else 0.0,
            "stages": {stg: sum(1 for e in sub if e.get("cognitive_stage") == stg) for stg in COGNITIVE_STAGES},
        }

    model_groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for e in items:
        pid = str(e.get("player_id") or "unknown")
        hv = str(e.get("harness_version") or "h1")
        model_groups.setdefault((pid, hv), []).append(e)

    by_model: list[dict[str, Any]] = []
    for (pid, hv), grp in sorted(model_groups.items(), key=lambda kv: (-len(kv[1]), kv[0][0], kv[0][1])):
        grp_non_t0 = [e for e in grp if e.get("rule") not in TIER_0_RULES]
        grp_kd = sum(1 for e in grp_non_t0 if bool(e.get("deduced_rule_in_cot")))
        stg_map = {stg: sum(1 for e in grp if e.get("cognitive_stage") == stg) for stg in COGNITIVE_STAGES}
        primary_bottleneck = max(COGNITIVE_STAGES, key=lambda s: stg_map[s]) if grp else "rule_induction"
        src_counts = Counter(str(e.get("reasoning_source") or "none") for e in grp)
        by_model.append({
            "player_id": pid,
            "harness_version": hv,
            "reasoning_source": src_counts.most_common(1)[0][0] if src_counts else "none",
            "total": len(grp),
            "knowing_doing_gap_count": grp_kd,
            "knowing_doing_gap_rate": round(grp_kd / len(grp_non_t0), 4) if grp_non_t0 else 0.0,
            "primary_bottleneck": primary_bottleneck,
            "stages": stg_map,
        })

    return {
        "total_failed_levels": total,
        "non_tier0_failed_levels": len(non_tier0_items),
        "knowing_doing_gap_count": kd_count,
        "knowing_doing_gap_rate": kd_rate,
        "by_cognitive_stage": by_stage,
        "by_reasoning_source": by_source,
        "by_harness": {
            "h1": _harness_summary(h1_items),
            "h2": _harness_summary(h2_items),
        },
        "by_model": by_model,
    }


def export_judge_prompts_jsonl(packets: list[dict[str, Any]], out_path: Path, max_tokens: int = 4000) -> int:
    """Write prompts JSONL compatible with `python -m arena judge --in prompts.jsonl --out replies.jsonl`."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for pkt in packets:
            row = {
                "id": f"{pkt['run_id']}:{pkt['level']}",
                "system": JUDGE_SYSTEM_PROMPT,
                "prompt": build_judge_prompt(pkt),
                "max_tokens": max_tokens,
            }
            fh.write(json.dumps(row) + "\n")
    return len(packets)


def load_judge_replies_jsonl(replies_path: Path) -> dict[tuple[str, int], dict[str, Any]]:
    """Parse JSONL replies emitted by `python -m arena judge` keyed by `(run_id, level)`."""
    out: dict[tuple[str, int], dict[str, Any]] = {}
    if not replies_path.exists():
        return out
    for line in replies_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("error") or not row.get("text"):
            continue
        rid_lv = str(row.get("id") or "")
        if ":" not in rid_lv:
            continue
        rid, lv_str = rid_lv.rsplit(":", 1)
        try:
            lv = int(lv_str)
            parsed = _parse_judge_reply_dict({"reply": row["text"], "model": row.get("model")}, str(row.get("model") or "llm-judge"))
            out[(rid, lv)] = parsed
        except Exception:
            continue
    return out


def _parse_judge_reply_dict(parsed: dict[str, Any], fallback_model: str) -> dict[str, Any]:
    if isinstance(parsed.get("reply"), str):
        reply_text = parsed["reply"].strip()
        if reply_text.startswith("```"):
            lines = reply_text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            reply_text = "\n".join(lines).strip()
        inner = json.loads(reply_text)
        inner.setdefault("judge_model", parsed.get("model") or fallback_model)
        return inner
    return parsed


def make_arena_judge(
    complete_fn: Callable[..., dict[str, Any]],
    model_id: str | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Wrap `arena.judge.complete(prompt, system=..., max_tokens=...)` into a packet -> dict callable."""

    def _call(packet: dict[str, Any]) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "system": JUDGE_SYSTEM_PROMPT,
            "max_tokens": 500,
        }
        if model_id:
            kwargs["model_id"] = model_id
        try:
            res = complete_fn(build_judge_prompt(packet), **kwargs)
        except TypeError:
            kwargs.pop("model_id", None)
            res = complete_fn(build_judge_prompt(packet), **kwargs)
        return _parse_judge_reply_dict(res, model_id or "gemini-pro")

    return _call


def _make_cmd_judge(cmd_str: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    argv = shlex.split(cmd_str)

    def _call(packet: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "system": JUDGE_SYSTEM_PROMPT,
            "prompt": build_judge_prompt(packet),
            "max_tokens": 500,
            "packet": {k: v for k, v in packet.items() if k != "steps"},
        }
        proc = subprocess.run(
            argv,
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=90,
            check=True,
        )
        out = proc.stdout.strip()
        parsed = json.loads(out)
        return _parse_judge_reply_dict(parsed, cmd_str)

    return _call


def _merge_raw_judge_with_deterministic(
    raw: dict[str, Any],
    det: dict[str, Any],
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    """Merge an external LLM judge response onto deterministic truth-diffed fields with strict verification."""
    verified_quote, verified_src = _verify_quote_in_steps(raw.get("evidence_quote"), steps)
    step_val = raw.get("step")
    valid_step_ids = {int(s["i"]) for s in steps}
    step_i = int(step_val) if isinstance(step_val, int) and step_val in valid_step_ids else det["step"]
    jm = str(raw.get("judge_model") or "llm-judge")

    raw_stage = str(raw.get("cognitive_stage") or "").strip()
    stage = raw_stage if raw_stage in COGNITIVE_STAGES else det["cognitive_stage"]

    raw_rc = str(raw.get("root_cause") or "").strip()
    root_cause = raw_rc if raw_rc in ROOT_CAUSES else det["root_cause"]

    deduced = raw.get("deduced_rule_in_cot")
    deduced_bool = bool(deduced) if isinstance(deduced, bool) else det["deduced_rule_in_cot"]
    if det.get("rule") in TIER_0_RULES:
        deduced_bool = False

    merged = dict(det)
    merged.update({
        "step": step_i,
        "rule": str(raw.get("rule") or det["rule"]),
        "verdict": str(raw.get("verdict") or det["verdict"]),
        "cognitive_stage": stage,
        "root_cause": root_cause,
        "deduced_rule_in_cot": deduced_bool,
        "truth_contrast": str(raw.get("truth_contrast") or det["truth_contrast"]),
        "explanation": str(raw.get("explanation") or det["explanation"]),
        "evidence_quote": verified_quote if verified_quote is not None else det["evidence_quote"],
        "quote_source": verified_src if verified_quote is not None else det["quote_source"],
        "judge_model": jm,
    })
    return merged


def build_explanations(
    runs: list[dict[str, Any]],
    game_descs: dict[str, dict[str, Any]] | None = None,
    repo_root: Path | None = None,
    judge_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    judge_cmd: str | None = None,
    preloaded_replies: dict[tuple[str, int], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Generate schema-valid `explanations.json` payload with Cognitive Bottleneck Funnel summary."""
    root = repo_root or find_repo_root()
    packets = build_failure_packets(runs, game_descs=game_descs, repo_root=root)
    runner = judge_fn or (_make_cmd_judge(judge_cmd) if judge_cmd else None)
    replies_map = preloaded_replies or {}

    items: list[dict[str, Any]] = []
    used_models: set[str] = set()

    for pkt in packets:
        det = synthesize_deterministic_explanation(pkt)
        key = (pkt["run_id"], int(pkt["level"]))

        if key in replies_map:
            item = _merge_raw_judge_with_deterministic(replies_map[key], det, pkt["steps"])
            used_models.add(item["judge_model"])
            items.append(item)
            continue

        if runner is not None:
            try:
                raw = runner(pkt)
                item = _merge_raw_judge_with_deterministic(raw, det, pkt["steps"])
                used_models.add(item["judge_model"])
                items.append(item)
                continue
            except Exception:
                pass

        used_models.add(det["judge_model"])
        items.append(det)

    top_model = (
        sorted(used_models)[0]
        if len(used_models) == 1
        else (", ".join(sorted(used_models)) if used_models else "reasoning-auditor-v2")
    )
    return {
        "generated_at": now_iso(),
        "judge_model": top_model,
        "summary": summarize_explanations(items),
        "explanations": items,
    }
