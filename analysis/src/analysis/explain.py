"""Failure explanation builder (`data/derived/explanations.json`).

Implements COORDINATION.md §2:
- Packs per-failed-level rules, optimal path, step-aligned hypothesis/reasoning, and truth events.
- Supports cost estimation (`--estimate`), external/A3 judge-LLM execution (`--judge-cmd`, `--judge-arena`),
  and deterministic trace-grounded synthesis (`trace-auditor-v1`) when offline or without API keys.
- Verifies that every `evidence_quote` is an exact verbatim substring of the run's recorded step text.
"""
from __future__ import annotations

import json
import shlex
import subprocess
import sys
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
    "You are an exact benchmark failure auditor for novel 64x64 gridworld games. "
    "You receive ground-truth level mechanics, the BFS optimal path, and a model's step-by-step actions, "
    "engine events, and reasoning/hypotheses. Playing models never saw rule names or truth events. "
    "Identify which mechanic the model misunderstood, at which 1-based step index `i` the failure is clearest, "
    "a concise verdict slug (`never_used_rule`, `wrong_hypothesis`, `ignored_no_effect`, `late_reset`, "
    "`hazard_loss`, or `ran_out_of_budget`), a 1-2 sentence explanation stating what went wrong and what "
    "optimal play required, and an exact verbatim `evidence_quote` copied from the model's text on that level "
    "(or null if no text was recorded). Reply ONLY with valid JSON."
)


def _load_engine_describe(game_id: str, repo_root: Path) -> dict[str, Any] | None:
    """Resolve full level `describe()` (including `optimal_path`) from engine or fake_engine when available."""
    eng_src = repo_root / "engine" / "src"
    if eng_src.exists() and str(eng_src) not in sys.path:
        sys.path.insert(0, str(eng_src))
    try:
        from engine.core.game import spec_from_game_id  # type: ignore
        from engine import make_game  # type: ignore

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


def _verbatim_excerpt(text: str | None, max_chars: int = 180) -> str | None:
    """Return an exact contiguous substring of `text` (never normalized/mutated) for claim verification."""
    if not text:
        return None
    stripped = text.strip()
    if not stripped:
        return None
    if len(stripped) <= max_chars:
        return stripped
    # Cut cleanly on whitespace while remaining an exact contiguous slice of `stripped` (and `text`)
    cut = stripped.rfind(" ", 0, max_chars)
    if cut < max_chars // 2:
        cut = max_chars
    sub = stripped[:cut]
    assert sub in text
    return sub


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
            packets.append({
                "run_id": run_id,
                "game_id": game_id,
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
                "steps": seg["steps"],
            })
    return packets


def build_judge_prompt(packet: dict[str, Any]) -> str:
    """Format a compact step-aligned prompt for the judge LLM (documented in analysis/METRICS.md §6)."""
    trace_lines: list[str] = []
    steps = packet["steps"]
    # Keep prompt compact: first 12, any event/hypothesis-change steps, and last 8 steps on the level
    keep_indices: set[int] = set(range(min(12, len(steps)))) | set(range(max(0, len(steps) - 8), len(steps)))
    prev_hyp = None
    for idx, st in enumerate(steps):
        if st.get("events") or st.get("action") == "RESET" or (st.get("hypothesis") and st.get("hypothesis") != prev_hyp):
            keep_indices.add(idx)
        if st.get("hypothesis"):
            prev_hyp = st.get("hypothesis")

    for idx in sorted(keep_indices):
        st = steps[idx]
        ev = ",".join(st.get("events") or []) or "-"
        hyp = _verbatim_excerpt(st.get("hypothesis"), 140)
        rsn = _verbatim_excerpt(st.get("reasoning"), 140) if not hyp else None
        note = f' hyp="{hyp}"' if hyp else (f' rsn="{rsn}"' if rsn else "")
        ne = " [NO_EFFECT]" if st.get("no_effect") else ""
        trace_lines.append(f"  step {st['i']}: action={st['action']} events=[{ev}]{ne}{note}")

    arrows = _format_arrow_path(packet.get("optimal_path"), max_len=20)
    return (
        f"Run: {packet['run_id']} | Model: {packet['player_id']} | Game: {packet['game_id']} | Level: {packet['level']}\n"
        f"Active rules: {', '.join(packet['active_rules']) or 'walls, goal, move_budget'}\n"
        f"Newly introduced rule on this level: {packet['new_rule'] or 'none'}\n"
        f"Optimal moves: {packet['optimal_moves']} (budget: {packet['move_budget']})"
        f"{f' | Optimal path: {arrows}' if arrows else ''}\n"
        f"Model summary on level: {packet['actions_used']} actions, {packet['resets']} resets, "
        f"{packet['no_effect_actions']} no-effect moves, triggered_new_rule={packet['first_rule_event_step'] is not None}\n"
        "Trace excerpt:\n"
        + "\n".join(trace_lines)
        + "\n\nReturn JSON: {\"step\": <int>, \"rule\": \"<rule>\", \"verdict\": \"<slug>\", "
        "\"explanation\": \"<what failed and what optimal play required>\", \"evidence_quote\": <exact quote or null>}"
    )


def estimate_judge_cost(packets: list[dict[str, Any]]) -> dict[str, Any]:
    """Estimate token usage and USD spend before calling any external judge model."""
    prompts = [build_judge_prompt(p) for p in packets]
    chars_in = sum(len(p) + len(JUDGE_SYSTEM_PROMPT) for p in prompts)
    est_tokens_in = max(0, (chars_in + 3) // 4)
    est_tokens_out = len(packets) * 140
    # Reference rates ($/1M tokens): fast judge (Haiku / Flash) vs frontier judge (Sonnet)
    cost_fast_usd = round((est_tokens_in * 0.80 + est_tokens_out * 4.00) / 1_000_000, 4)
    cost_sonnet_usd = round((est_tokens_in * 3.00 + est_tokens_out * 15.00) / 1_000_000, 4)
    return {
        "failed_levels": len(packets),
        "est_tokens_in": est_tokens_in,
        "est_tokens_out": est_tokens_out,
        "est_cost_fast_judge_usd": cost_fast_usd,
        "est_cost_sonnet_judge_usd": cost_sonnet_usd,
        "within_decisions_sweep_cap": cost_sonnet_usd <= 20.0,
    }


def _find_best_quote_near_step(steps: list[dict[str, Any]], target_i: int) -> str | None:
    """Pick a verbatim quote from hypothesis/reasoning closest to `target_i`."""
    candidates: list[tuple[int, str]] = []
    for st in steps:
        for field in ("hypothesis", "reasoning"):
            raw = st.get(field)
            if isinstance(raw, str) and raw.strip():
                excerpt = _verbatim_excerpt(raw, 180)
                if excerpt:
                    candidates.append((abs(int(st["i"]) - target_i), excerpt))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _verify_quote_in_steps(quote: str | None, steps: list[dict[str, Any]]) -> str | None:
    """Ensure any LLM-returned quote is an exact substring of recorded step text; otherwise fallback."""
    if not quote:
        return None
    q = quote.strip()
    if not q:
        return None
    for st in steps:
        for field in ("hypothesis", "reasoning"):
            raw = st.get(field)
            if isinstance(raw, str) and q in raw:
                return q
    return None


def synthesize_deterministic_explanation(packet: dict[str, Any]) -> dict[str, Any]:
    """Produce an exact trace-verified explanation (`trace-auditor-v1`) from events, hypotheses, and BFS truth."""
    steps = packet["steps"]
    new_rule = packet.get("new_rule")
    active_rules = [r for r in packet.get("active_rules", []) if r not in TIER_0_RULES]
    primary_rule = new_rule or (active_rules[-1] if active_rules else "walls")

    # Detect specific failure events on the level
    hazard_step = next(
        (
            st
            for st in steps
            if any(
                ev in ("hurt", "enemy_hit", "caught", "floor_collapsed", "checkpoints_reset", "decoy", "crushed", "shadow_hit")
                for ev in (st.get("events") or [])
            )
        ),
        None,
    )
    consec_no_effect_step: dict[str, Any] | None = None
    streak = 0
    for st in steps:
        if st.get("no_effect"):
            streak += 1
            if streak >= 2 and consec_no_effect_step is None:
                consec_no_effect_step = st
        else:
            streak = 0

    reset_step = next((st for st in steps if st.get("action") == "RESET"), None)
    last_step = steps[-1]
    opt_moves = packet["optimal_moves"]
    arrows = _format_arrow_path(packet.get("optimal_path"), max_len=10)
    arrow_clause = f" ({arrows})" if arrows else ""

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
        verdict = "ran_out_of_budget" if not packet["hypothesis_matched"] and new_rule else "ran_out_of_budget"
        if new_rule and not packet["hypothesis_matched"]:
            verdict = "wrong_hypothesis"
        hint = RULE_HINTS.get(rule, "follow the shortest valid trajectory")
        explanation = (
            f"Run ended at step {step_i} on Level {packet['level']} after {packet['actions_used']} moves "
            f"(budget {packet['move_budget']}, outcome `{packet.get('outcome') or 'BUDGET'}`) while navigating `{rule}`. "
            f"Optimal play finishes in {opt_moves} moves{arrow_clause}: {hint}."
        )

    quote = _find_best_quote_near_step(steps, step_i)
    return {
        "run_id": packet["run_id"],
        "game_id": packet["game_id"],
        "player_id": packet["player_id"],
        "level": packet["level"],
        "step": step_i,
        "rule": rule,
        "verdict": verdict,
        "explanation": explanation,
        "evidence_quote": quote,
        "judge_model": "trace-auditor-v1",
    }


def _make_cmd_judge(cmd_str: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    argv = shlex.split(cmd_str)

    def _call(packet: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "system": JUDGE_SYSTEM_PROMPT,
            "prompt": build_judge_prompt(packet),
            "max_tokens": 350,
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
        if isinstance(parsed, dict) and isinstance(parsed.get("reply"), str):
            reply_text = parsed["reply"].strip()
            if reply_text.startswith("```"):
                reply_text = reply_text.strip("`").removeprefix("json").strip()
            inner = json.loads(reply_text)
            inner.setdefault("judge_model", parsed.get("model") or cmd_str)
            return inner
        return parsed

    return _call


def build_explanations(
    runs: list[dict[str, Any]],
    game_descs: dict[str, dict[str, Any]] | None = None,
    repo_root: Path | None = None,
    judge_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    judge_cmd: str | None = None,
) -> dict[str, Any]:
    """Generate schema-valid `explanations.json` payload across all failed model levels."""
    root = repo_root or find_repo_root()
    packets = build_failure_packets(runs, game_descs=game_descs, repo_root=root)
    runner = judge_fn or (_make_cmd_judge(judge_cmd) if judge_cmd else None)

    items: list[dict[str, Any]] = []
    used_models: set[str] = set()

    for pkt in packets:
        det = synthesize_deterministic_explanation(pkt)
        if runner is not None:
            try:
                raw = runner(pkt)
                verified_quote = _verify_quote_in_steps(raw.get("evidence_quote"), pkt["steps"])
                step_val = raw.get("step")
                valid_step_ids = {int(s["i"]) for s in pkt["steps"]}
                step_i = int(step_val) if isinstance(step_val, int) and step_val in valid_step_ids else det["step"]
                jm = str(raw.get("judge_model") or "llm-judge")
                item = {
                    "run_id": pkt["run_id"],
                    "game_id": pkt["game_id"],
                    "player_id": pkt["player_id"],
                    "level": pkt["level"],
                    "step": step_i,
                    "rule": str(raw.get("rule") or det["rule"]),
                    "verdict": str(raw.get("verdict") or det["verdict"]),
                    "explanation": str(raw.get("explanation") or det["explanation"]),
                    "evidence_quote": verified_quote if verified_quote is not None else det["evidence_quote"],
                    "judge_model": jm,
                }
                used_models.add(jm)
                items.append(item)
                continue
            except Exception:
                pass

        used_models.add(det["judge_model"])
        items.append(det)

    top_model = sorted(used_models)[0] if len(used_models) == 1 else (", ".join(sorted(used_models)) if used_models else "trace-auditor-v1")
    return {
        "generated_at": now_iso(),
        "judge_model": top_model,
        "explanations": items,
    }
