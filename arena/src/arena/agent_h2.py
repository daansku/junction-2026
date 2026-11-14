"""Agent loop h2: models run the way labs benchmark them (PLAN.md phase 2, section 3.1).

Differences from h1 (h1 stays as is; h2 is a separate board, never mixed):
  1. One continuous multi-turn conversation: the model sees its own previous turns.
  2. Reasoning retained across turns: Anthropic thinking blocks go back unchanged (append-only history, so
     preserved thinking stays valid); OpenAI-compatible providers get their assistant message back exactly as
     returned (Kimi's `reasoning_content`, Gemini's thought-signature fields, whatever the provider sent).
  3. Native tool calling: one tool, act(action, hypothesis, belief). A reply without a valid call is an invalid
     turn (counted in the trace, costs a turn, not an action), as in h1.
  4. Effort: the sweep entry's effort, else the model's `h2_effort`, else "high". Recorded in the trace.
  5. Generous output: the model's `h2_max_tokens`, else 64000 (Anthropic, streamed) / 32768 (OpenAI-compatible).
  6. Provider-default sampling (no temperature etc. sent).
  7. Context: full text history (OpenAI-compatible: reasoning text kept for the last THINKING_TURNS turns, as
     Anthropic's server-side thinking clearing); the frame (image + RLE grid) is attached to every observation, and only the last
     IMAGE_TURNS observations keep their frame (Anthropic: server-side context editing, which does not invalidate
     thinking; OpenAI-compatible: older frames replaced by a placeholder client-side). Anthropic thinking older
     than THINKING_TURNS assistant turns is cleared server-side. Same N for every model. Prompt caching on.
  8. Repeats are a sweep setting (attempts).
  9. System prompt `prompts/system_h2.md`: same idea as h1, no rule names, no hints. Pixels only: the truth
     channel never reaches a prompt.
"""
from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path

from .agent_loop import END_STATES, Budgets, GameResult, _outcome
from .client import GameClient
from .cost import price
from .frames import diff_count, to_png, to_rle

HARNESS_VERSION = "h2"
SYSTEM = (Path(__file__).parent / "prompts" / "system_h2.md").read_text(encoding="utf-8")
IMAGE_TURNS = 5          # observations that keep their frame
THINKING_TURNS = 10      # Anthropic: assistant turns that keep their thinking blocks

# h2b (Sat 22:40 human decision: same sweeps, much less wall time). Identical to h2 except:
#   - act takes a list of 1..MAX_MOVES actions run in order (each one counted and scored exactly as in h2); the
#     list stops early on a level change, game end, or an action that changes no cell; fewer model calls per run.
#   - smaller context: last H2B_IMAGE_TURNS frames, last H2B_THINKING_TURNS reasoning blocks.
# Separate board from h2 (different run keys); never mixed with h2 rows.
SYSTEM_H2B = (Path(__file__).parent / "prompts" / "system_h2b.md").read_text(encoding="utf-8")
MAX_MOVES = 5
H2B_IMAGE_TURNS = 2
H2B_THINKING_TURNS = 3
ACTIONS = ["ACTION1", "ACTION2", "ACTION3", "ACTION4", "ACTION5", "RESET"]

ACT_DESCRIPTION = ("Take exactly one action in the game. Call this once per turn. You get the new screen back.")


ACT_DESCRIPTION_H2B = (f"Take 1 to {MAX_MOVES} actions in order. Call this once per turn. The list stops early when "
                      "a level ends, the game ends, or an action changes nothing. You get the new screen back.")


def act_schema(multi: bool = False) -> dict:
    first = ({"actions": {"type": "array", "items": {"type": "string", "enum": ACTIONS},
                          "description": f"1 to {MAX_MOVES} actions, carried out in order."}} if multi else
             {"action": {"type": "string", "enum": ACTIONS, "description": "The action to take."}})
    return {
        "type": "object",
        "properties": {
            **first,
            "hypothesis": {"type": "string", "description": "Your current best guess about the rule that matters now."},
            "belief": {"type": "string", "enum": ["playing", "won", "lost"],
                       "description": "Whether you think the game is still being played, won or lost."},
        },
        "required": [next(iter(first)), "hypothesis", "belief"],
        "additionalProperties": False,
    }


def observation_text(step: int, allowed: list[str], last: tuple[str, int] | None, frame) -> str:
    head = f"Turn {step}. Available actions: {', '.join(allowed)}."
    if last:
        head += f" Your last action {last[0]} changed {last[1]} of the 4096 cells."
    return (head + "\nCurrent screen, run-length encoded (64x64, colour indices 0-f; each row lists colourxcount "
            "runs left to right; rN-M = identical rows):\n" + to_rle(frame))


class Turn:
    """What one model call produced."""

    def __init__(self, action=None, hypothesis="", belief="playing", reasoning="", invalid=None, refused=False,
                 tokens_in=0, tokens_out=0, cost=0.0, latency_ms=0, stop=None, actions=None):
        self.actions = actions or ([action] if action else [])
        self.action, self.hypothesis, self.belief, self.reasoning = action, hypothesis, belief, reasoning
        self.invalid, self.refused, self.stop = invalid, refused, stop
        self.tokens_in, self.tokens_out, self.cost, self.latency_ms = tokens_in, tokens_out, cost, latency_ms


def _parse_args(args, allowed: list[str]) -> tuple[dict | None, str | None]:
    if isinstance(args, str):
        try:
            args = json.loads(args or "{}")
        except json.JSONDecodeError as e:
            return None, f"invalid tool arguments: {e.msg}"
    if not isinstance(args, dict):
        return None, "tool arguments are not an object"
    if "actions" in args:  # h2b: the first must be available now; later ones are checked when they run
        raw = args.get("actions")
        if isinstance(raw, str):
            raw = [raw]
        if not isinstance(raw, list) or not raw:
            return None, "actions must be a non-empty list"
        acts = [str(a).strip().upper() for a in raw][:MAX_MOVES]
        if acts[0] not in allowed or any(a not in ACTIONS for a in acts):
            return None, f"actions {raw!r}: each must be one of {allowed}"
    else:
        acts = [str(args.get("action", "")).strip().upper()]
        if acts[0] not in allowed:
            return None, f"action {args.get('action')!r} not in {allowed}"
    act = acts[0]
    belief = args.get("belief") if args.get("belief") in ("playing", "won", "lost") else "playing"
    return {"action": act, "actions": acts, "hypothesis": str(args.get("hypothesis", ""))[:500], "belief": belief}, None


# ---------------------------------------------------------------- Anthropic (official SDK)
class AnthropicH2:
    reasoning_mode = "anthropic-thinking-blocks-preserved"

    def __init__(self, model: dict, effort: str, multi: bool = False):
        import anthropic
        self.model, self.effort, self.multi = model, effort, multi
        self.system = SYSTEM_H2B if multi else SYSTEM
        self.image_turns = H2B_IMAGE_TURNS if multi else IMAGE_TURNS
        self.thinking_turns = H2B_THINKING_TURNS if multi else THINKING_TURNS
        self.client = anthropic.Anthropic(timeout=float(os.environ.get("ARENA_H2_TIMEOUT_S", "900")), max_retries=3)
        self.max_tokens = int(model.get("h2_max_tokens") or 64000)
        self.messages: list[dict] = []
        self.pending_tool_id: str | None = None
        self.tools = [{"name": "act", "description": ACT_DESCRIPTION_H2B if multi else ACT_DESCRIPTION,
                       "input_schema": act_schema(multi), "strict": True}]

    def observe(self, text: str, png: bytes, note: str | None = None):
        content = [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                "data": base64.standard_b64encode(png).decode()}},
                   {"type": "text", "text": text}]
        if self.pending_tool_id:  # the frame arrives as the result of the act call that produced it
            block = {"type": "tool_result", "tool_use_id": self.pending_tool_id, "content": content}
            self.messages.append({"role": "user", "content": [block] + ([{"type": "text", "text": note}] if note else [])})
            self.pending_tool_id = None
        else:
            self.messages.append({"role": "user", "content": content + ([{"type": "text", "text": note}] if note else [])})

    def ask(self, allowed: list[str]) -> Turn:
        t0 = time.time()
        with self.client.beta.messages.stream(
            model=self.model["api_model"],
            max_tokens=self.max_tokens,
            system=[{"type": "text", "text": self.system}],
            tools=self.tools,
            messages=self.messages,
            thinking={"type": "adaptive", "display": "summarized"},
            output_config={"effort": self.effort},
            cache_control={"type": "ephemeral"},
            betas=["context-management-2025-06-27"],
            context_management={"edits": [
                {"type": "clear_thinking_20251015", "keep": {"type": "thinking_turns", "value": self.thinking_turns}},
                {"type": "clear_tool_uses_20250919", "trigger": {"type": "tool_uses", "value": self.image_turns + 1},
                 "keep": {"type": "tool_uses", "value": self.image_turns}},
            ]},
        ) as stream:
            msg = stream.get_final_message()
        lat = int((time.time() - t0) * 1000)
        u = msg.usage
        tin = (u.input_tokens or 0) + (getattr(u, "cache_read_input_tokens", 0) or 0) + \
            (getattr(u, "cache_creation_input_tokens", 0) or 0)
        cost = anthropic_cost(self.model, u)
        # append-only: the full assistant content (thinking blocks included) goes back unchanged
        self.messages.append({"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in msg.content]})
        reasoning = "\n".join(filter(None, [getattr(b, "thinking", None) if b.type == "thinking" else
                                            (b.text if b.type == "text" else None) for b in msg.content]))[:4000]
        base = dict(reasoning=reasoning, tokens_in=tin, tokens_out=u.output_tokens or 0, cost=cost, latency_ms=lat,
                    stop=msg.stop_reason)
        if msg.stop_reason == "refusal":
            return Turn(refused=True, **base)
        calls = [b for b in msg.content if b.type == "tool_use"]
        if not calls:
            return Turn(invalid=f"no act call (stop_reason {msg.stop_reason})", **base)
        first, extra = calls[0], calls[1:]
        parsed, err = _parse_args(first.input, allowed)
        if extra:  # every tool_use needs a tool_result; only the first one runs
            self._extra = [{"type": "tool_result", "tool_use_id": b.id, "is_error": True,
                            "content": "Ignored: only one action per turn."} for b in extra]
        else:
            self._extra = []
        if parsed is None:
            self.messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": first.id, "is_error": True, "content": err}] + self._extra})
            return Turn(invalid=err, **base)
        self.pending_tool_id = first.id
        return Turn(action=parsed["action"], actions=parsed["actions"], hypothesis=parsed["hypothesis"],
                    belief=parsed["belief"], **base)

    def observe_after_act(self, text: str, png: bytes):
        extra, self._extra = getattr(self, "_extra", []), []
        self.observe(text, png)
        if extra:
            self.messages[-1]["content"] = self.messages[-1]["content"][:1] + extra + self.messages[-1]["content"][1:]

    def nudge(self, text: str):
        """After an invalid turn: append-only reminder (never edits earlier turns)."""
        last = self.messages[-1]
        if last["role"] == "user":
            last["content"].append({"type": "text", "text": text})
        else:
            self.messages.append({"role": "user", "content": [{"type": "text", "text": text}]})


def anthropic_cost(model: dict, u) -> float:
    pin, pout = model.get("price_in") or 0.0, model.get("price_out") or 0.0
    read = model.get("price_cache_read", pin * 0.1)
    write = model.get("price_cache_write", pin * 1.25)
    return ((u.input_tokens or 0) * pin + (getattr(u, "cache_read_input_tokens", 0) or 0) * read +
            (getattr(u, "cache_creation_input_tokens", 0) or 0) * write + (u.output_tokens or 0) * pout) / 1e6


# ---------------------------------------------------------------- OpenAI-compatible (Kimi, Gemini compat, vLLM, ...)
class OpenAICompatH2:
    reasoning_mode = "assistant-message-returned-verbatim"

    def __init__(self, model: dict, effort: str, multi: bool = False):
        from openai import OpenAI
        from .providers.openai_compat import make_client
        base = make_client(model["provider"], model.get("base_url"), model.get("api_key_env"))
        self.client: OpenAI = base.with_options(timeout=float(os.environ.get("ARENA_H2_TIMEOUT_S", "900")),
                                                max_retries=2)
        self.model, self.effort, self.multi = model, effort, multi
        self.image_turns = H2B_IMAGE_TURNS if multi else IMAGE_TURNS
        self.thinking_turns = H2B_THINKING_TURNS if multi else THINKING_TURNS
        self.max_tokens = int(model.get("h2_max_tokens") or 32768)
        self.images = "image" in (model.get("input_modes") or [])
        self.messages: list[dict] = [{"role": "system", "content": SYSTEM_H2B if multi else SYSTEM}]
        self.pending_call_ids: list[str] = []
        self.tools = [{"type": "function", "function": {
            "name": "act", "description": ACT_DESCRIPTION_H2B if multi else ACT_DESCRIPTION,
            "parameters": act_schema(multi)}}]

    def _drop_old_reasoning(self):
        """Same window as Anthropic's server-side thinking clearing: only the last THINKING_TURNS assistant turns
        keep their reasoning text (tool calls, signatures and visible text stay)."""
        seen = 0
        for m in reversed(self.messages):
            if m.get("role") != "assistant":
                continue
            seen += 1
            if seen > self.thinking_turns:
                for k in ("reasoning_content", "reasoning"):
                    m.pop(k, None)

    def _drop_old_frames(self):
        seen = 0
        for m in reversed(self.messages):
            if m["role"] != "user" or not isinstance(m["content"], list):
                continue
            if any(p.get("type") == "image_url" for p in m["content"]):
                seen += 1
                if seen > self.image_turns:
                    m["content"] = [p for p in m["content"] if p.get("type") != "image_url"]
                    for p in m["content"]:
                        if p.get("type") == "text" and "Current screen" in p.get("text", ""):
                            p["text"] = p["text"].split("\nCurrent screen")[0] + "\n[older screen removed]"

    def observe(self, text: str, png: bytes, note: str | None = None):
        for i, cid in enumerate(self.pending_call_ids):  # every tool call gets a tool message
            self.messages.append({"role": "tool", "tool_call_id": cid,
                                  "content": "Done. The new screen follows." if i == 0 else
                                  "Ignored: only one action per turn."})
        self.pending_call_ids = []
        parts = []
        if self.images:
            parts.append({"type": "image_url", "image_url": {
                "url": "data:image/png;base64," + base64.b64encode(png).decode()}})
        parts.append({"type": "text", "text": text + (f"\n{note}" if note else "")})
        self.messages.append({"role": "user", "content": parts})
        self._drop_old_frames()
        self._drop_old_reasoning()

    def ask(self, allowed: list[str]) -> Turn:
        kw = {"max_tokens": self.max_tokens}
        if self.effort and self.effort in (self.model.get("efforts") or []):
            kw["reasoning_effort"] = self.effort
        t0 = time.time()
        resp = self.client.chat.completions.create(model=self.model["api_model"], messages=self.messages,
                                                   tools=self.tools, tool_choice="auto", **kw)
        lat = int((time.time() - t0) * 1000)
        ch = resp.choices[0]
        msg = ch.message
        # reasoning retained: the assistant message goes back exactly as returned (all provider fields kept)
        self.messages.append(msg.model_dump(exclude_none=True))
        u = resp.usage
        from .providers.openai_compat import billed_tokens
        tin, tout = billed_tokens(u)
        cost = price(self.model, tin, tout) or 0.0
        reasoning = (getattr(msg, "reasoning_content", None) or "") + ("\n" if msg.content else "") + (msg.content or "")
        base = dict(reasoning=reasoning[:4000], tokens_in=tin, tokens_out=tout, cost=cost, latency_ms=lat,
                    stop=ch.finish_reason)
        if ch.finish_reason == "content_filter":
            return Turn(refused=True, **base)
        calls = msg.tool_calls or []
        if not calls:
            return Turn(invalid=f"no act call (finish_reason {ch.finish_reason})", **base)
        self.pending_call_ids = [c.id for c in calls]
        parsed, err = _parse_args(calls[0].function.arguments, allowed)
        if parsed is None:
            for i, cid in enumerate(self.pending_call_ids):
                self.messages.append({"role": "tool", "tool_call_id": cid,
                                      "content": f"Error: {err}" if i == 0 else "Ignored: only one action per turn."})
            self.pending_call_ids = []
            return Turn(invalid=err, **base)
        return Turn(action=parsed["action"], actions=parsed["actions"], hypothesis=parsed["hypothesis"],
                    belief=parsed["belief"], **base)

    def observe_after_act(self, text: str, png: bytes):
        self.observe(text, png)

    def nudge(self, text: str):
        self.messages.append({"role": "user", "content": text})


def make_adapter(model: dict, effort: str, multi: bool = False):
    cls = AnthropicH2 if model["provider"] == "anthropic" else OpenAICompatH2
    return cls(model, effort, multi)


# ---------------------------------------------------------------- game loop (identical for every model)
def play_model_h2(client: GameClient, game_id: str, model: dict, *, effort: str | None, run_key: str | None,
                  budgets: Budgets, log=print, harness: str = HARNESS_VERSION) -> GameResult:
    eff = effort or model.get("h2_effort") or "high"
    multi = harness == "h2b"
    ad = make_adapter(model, eff, multi)
    player = {"kind": "model", "name": model["display_name"], "model_id": model["id"], "provider": model["provider"],
              "effort": eff, "harness_version": harness, "input_modes": model.get("input_modes"),
              "reasoning_mode": ad.reasoning_mode, "image_turns": ad.image_turns, "max_tokens": ad.max_tokens,
              **({"max_moves_per_turn": MAX_MOVES} if multi else {})}
    session, start = client.start(game_id, player, run_key=run_key)
    frame = start["frame"]
    allowed = start.get("available_actions") or ["RESET", "ACTION1", "ACTION2", "ACTION3", "ACTION4"]
    actions = turns = invalid = 0
    tin = tout = 0
    cost = 0.0
    t0 = time.time()
    reason = "budget_actions"
    truth = session.truth()
    ad.observe(observation_text(1, allowed, None, frame), to_png(frame))
    while True:
        if truth.get("state") in END_STATES:
            reason = "win"; break
        if actions >= budgets.max_actions:
            reason = "budget_actions"; break
        if turns >= budgets.max_turns:
            reason = "budget_turns"; break
        if cost >= budgets.max_cost_usd:
            reason = "budget_cost"; break
        if time.time() - t0 >= budgets.max_wall_s:
            reason = "budget_wall"; break
        if tin + tout >= budgets.max_tokens_total:
            reason = "budget_tokens"; break
        turns += 1
        tr = ad.ask(allowed)
        tin += tr.tokens_in; tout += tr.tokens_out; cost += tr.cost
        if tr.refused:
            reason = "refusal"; break
        if tr.action is None:
            invalid += 1
            ad.nudge(f"(Invalid turn: {tr.invalid}. Call the act tool with exactly one of: {', '.join(allowed)}.)")
            continue
        usage = {"in": tr.tokens_in, "out": tr.tokens_out, "cost_usd": round(tr.cost, 6)}
        start_frame, ran, stopped = frame, [], None
        lvl0 = truth.get("level")
        for i, a in enumerate(tr.actions):
            if actions >= budgets.max_actions:
                stopped = "the action budget was reached"; break
            if a not in allowed:
                stopped = f"{a} was not available"; break
            first = i == 0  # model usage / reasoning are attached to the first action of the call only
            out = session.act(a, reasoning=tr.reasoning if first else "", hypothesis=tr.hypothesis,
                              belief=tr.belief, usage=usage if first else {"in": 0, "out": 0, "cost_usd": 0.0},
                              latency_ms=tr.latency_ms if first else 0)
            actions += 1
            prev, frame = frame, out["frame"]
            allowed = out.get("available_actions") or allowed
            truth = session.truth()
            ran.append((a, diff_count(prev, frame)))
            if truth.get("state") in END_STATES or truth.get("state") == "GAME_OVER":
                stopped = "the game ended"; break
            if truth.get("level") != lvl0:
                stopped = "the level changed"; break
            if ran[-1][1] == 0:
                stopped = "the action changed nothing"; break
        if not multi:
            ad.observe_after_act(observation_text(turns + 1, allowed, ran[0], frame), to_png(frame))
            continue
        text = observation_text(turns + 1, allowed, None, frame)
        steps = ", ".join(f"{a} ({n} cells changed)" for a, n in ran)
        head, rest = text.split("\n", 1)
        note = f" You asked for {len(tr.actions)} action(s); {len(ran)} ran: {steps or 'none'}."
        if stopped and len(ran) < len(tr.actions):
            note += f" Stopped because {stopped}."
        ad.observe_after_act(head + note + "\n" + rest, to_png(frame))

    t = truth
    outcome = _outcome(t, reason)
    session.end(reason, outcome=outcome, usage_total={"in": tin, "out": tout, "cost_usd": round(cost, 6)})
    done = (t.get("level", 1) - 1) + (1 if t.get("state") == "WIN" else 0)
    return GameResult(run_id=session.run_id, game_id=game_id, outcome=outcome, levels_completed=done,
                      levels_total=t.get("levels_total", 0), actions=actions, turns=turns, invalid_replies=invalid,
                      tokens_in=tin, tokens_out=tout, cost_usd=round(cost, 6),
                      cost_known=bool(model.get("price_in") is not None), wall_s=round(time.time() - t0, 1),
                      reason=reason, extra={"harness_version": harness, "effort": eff,
                                            "reasoning_mode": ad.reasoning_mode})
