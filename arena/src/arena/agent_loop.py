"""Agent loop h1: identical for every model.

Each turn is a fresh single-message request (no growing chat history): the model gets the
system prompt, its own rolling NOTES, the last few actions with how many cells changed, and
the current frame (image and/or text grid per input_modes). It answers
{notes, hypothesis, belief, action}. Bounded context = comparable cost across models and
no advantage for long-context models. The truth channel is never put in a prompt.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from .client import GameClient
from .cost import Meter
from .frames import diff_count, to_png, to_rle, to_text
from .providers import Provider, Reply

HARNESS_VERSION = "h1"
SYSTEM = (Path(__file__).parent / "prompts" / "system_h1.md").read_text(encoding="utf-8")
HISTORY_K = 12
END_STATES = ("WIN",)


@dataclass
class Budgets:
    max_actions: int = 400          # total actions per game, incl. resets
    max_turns: int = 500            # model calls (invalid replies cost a turn, not an action)
    max_cost_usd: float = 2.0
    max_wall_s: float = 3600
    max_tokens_total: int = 3_000_000


@dataclass
class GameResult:
    run_id: str
    game_id: str
    outcome: str
    levels_completed: int
    levels_total: int
    actions: int
    turns: int
    invalid_replies: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    cost_known: bool
    wall_s: float
    reason: str
    extra: dict = field(default_factory=dict)


_JSON = re.compile(r"\{.*\}", re.S)


def parse_reply(text: str, allowed: list[str]) -> tuple[dict | None, str | None]:
    """Returns (parsed, error). Accepts fenced or bare JSON; action matched case-insensitively."""
    m = _JSON.search(text or "")
    if not m:
        return None, "no JSON object found"
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        return None, f"invalid JSON: {e.msg}"
    if not isinstance(d, dict):
        return None, "reply is not an object"
    act = str(d.get("action", "")).strip().upper()
    if act not in allowed:
        return None, f"action {d.get('action')!r} not in {allowed}"
    d["action"] = act
    d["belief"] = d.get("belief") if d.get("belief") in ("playing", "won", "lost") else "playing"
    d["notes"] = str(d.get("notes", ""))[:2000]
    d["hypothesis"] = str(d.get("hypothesis", ""))[:500]
    return d, None


def build_parts(frame, notes, history, allowed, input_modes, step) -> list[dict]:
    lines = [f"Turn {step}. Available actions: {', '.join(allowed)}.",
             f"Your NOTES from last turn:\n{notes or '(none yet)'}"]
    if history:
        lines.append("Recent actions (oldest first) and how many of the 4096 cells changed after each:")
        lines += [f"  {a} -> {c} cells changed" for a, c in history[-HISTORY_K:]]
    parts = [{"type": "text", "text": "\n".join(lines)}]
    if "image" in input_modes:
        parts.append({"type": "image_png", "data": to_png(frame)})
    if "text" in input_modes:
        parts.append({"type": "text", "text": "Current screen (64 rows of 64 hex colour indices, row 0 at top):\n"
                                              + to_text(frame)})
    if "rle" in input_modes:
        parts.append({"type": "text", "text": "Current screen, run-length encoded (64x64, colour indices 0-f; "
                                              "each row lists colourxcount runs left to right; rN-M = identical rows):\n"
                                              + to_rle(frame)})
    parts.append({"type": "text", "text": "Reply with the JSON object only."})
    return parts


def play_model(client: GameClient, game_id: str, provider: Provider, model: dict, *, effort: str | None,
               run_key: str | None, budgets: Budgets, input_modes: list[str] | None = None,
               log=print) -> GameResult:
    modes = input_modes or model.get("input_modes", ["text"])
    player = {"kind": "model", "name": model["display_name"], "model_id": model["id"],
              "provider": model["provider"], "effort": effort, "harness_version": HARNESS_VERSION,
              "input_modes": modes}
    session, start = client.start(game_id, player, run_key=run_key)
    frame, allowed = start["frame"], start.get("available_actions") or ["RESET", "ACTION1", "ACTION2", "ACTION3", "ACTION4"]
    meter = Meter(model)
    notes, history, prev = "", [], None
    actions = turns = invalid = 0
    t0 = time.time()
    reason = "budget_actions"
    truth = session.truth()
    while True:
        if truth.get("state") in END_STATES:
            reason = "win"
            break
        if actions >= budgets.max_actions:
            reason = "budget_actions"; break
        if turns >= budgets.max_turns:
            reason = "budget_turns"; break
        if meter.cost_usd >= budgets.max_cost_usd:
            reason = "budget_cost"; break
        if time.time() - t0 >= budgets.max_wall_s:
            reason = "budget_wall"; break
        if meter.tokens_in + meter.tokens_out >= budgets.max_tokens_total:
            reason = "budget_tokens"; break

        parts = build_parts(frame, notes, history, allowed, modes, turns + 1)
        turns += 1
        reply: Reply = provider.complete(SYSTEM, parts, effort=effort)
        usage = meter.add(reply.tokens_in, reply.tokens_out)
        if reply.refused:
            reason = "refusal"; break
        parsed, err = parse_reply(reply.text, allowed)
        if parsed is None:
            invalid += 1
            history.append((f"(invalid reply: {err})", 0))
            continue
        out = session.act(parsed["action"], reasoning=parsed["notes"], hypothesis=parsed["hypothesis"],
                          belief=parsed["belief"], usage=usage, latency_ms=reply.latency_ms)
        actions += 1
        prev, frame = frame, out["frame"]
        allowed = out.get("available_actions") or allowed
        history.append((parsed["action"], diff_count(prev, frame)))
        notes = parsed["notes"]
        truth = session.truth()

    t = truth
    outcome = _outcome(t, reason)
    session.end(reason, outcome=outcome, usage_total={"in": meter.tokens_in, "out": meter.tokens_out,
                                                       "cost_usd": round(meter.cost_usd, 6)})
    done = (t.get("level", 1) - 1) + (1 if t.get("state") == "WIN" else 0)
    return GameResult(run_id=session.run_id, game_id=game_id, outcome=outcome,
                      levels_completed=done, levels_total=t.get("levels_total", 0), actions=actions,
                      turns=turns, invalid_replies=invalid, tokens_in=meter.tokens_in,
                      tokens_out=meter.tokens_out, cost_usd=round(meter.cost_usd, 6),
                      cost_known=not meter.unknown_price, wall_s=round(time.time() - t0, 1), reason=reason)


def _outcome(truth: dict, reason: str) -> str:
    """WIN / GAME_OVER from the game; harness-side stops are BUDGET; refusals and deliberate
    early stops (noop, stop_early baselines) are ABORTED."""
    if truth.get("state") == "WIN":
        return "WIN"
    if reason in ("refusal", "noop", "stop_early", "optimal_path_failed"):
        return "ABORTED"
    if truth.get("state") == "GAME_OVER":
        return "GAME_OVER"
    return "BUDGET"
