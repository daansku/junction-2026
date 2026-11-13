"""Claude backend: manual tool loop on the Anthropic SDK.

Manual loop (not the beta tool runner) because the episode can end mid-turn and we
stop as soon as the environment says done. No server-side model fallbacks: a benchmark
run must not silently switch models.
"""
from __future__ import annotations

import json
import os

import anthropic

from .llm_agent import SYSTEM, TOOLS, first_prompt, run_tool

EFFORT = os.environ.get("SWITCHBOARD_EFFORT", "high")


def _tools():
    return [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in TOOLS]


def run_episode(provider, model, view, tr, max_turns=400):
    client = anthropic.Anthropic()
    tools = _tools()
    messages = [{"role": "user", "content": first_prompt(view)}]
    for turn in range(max_turns):
        if view.observe()["done"]:
            return
        resp = client.messages.create(
            model=model,
            max_tokens=16000,
            system=SYSTEM,
            tools=tools,
            messages=messages,
            output_config={"effort": EFFORT},
            cache_control={"type": "ephemeral"},
        )
        tr.usage["input_tokens"] += resp.usage.input_tokens
        tr.usage["output_tokens"] += resp.usage.output_tokens
        messages.append({"role": "assistant", "content": resp.content})
        text = "".join(b.text for b in resp.content if b.type == "text")
        calls = [b for b in resp.content if b.type == "tool_use"]
        tr.add(turn=turn, stop_reason=resp.stop_reason, text=text,
               calls=[{"name": c.name, "input": c.input} for c in calls])
        if resp.stop_reason == "refusal":
            raise RuntimeError("model refused")
        if not calls:
            # model stopped talking to the tools; nudge once per turn, the budget/turn cap bounds this
            messages.append({"role": "user", "content": "The episode is not over. Continue using the tools. State: "
                             + json.dumps(view.observe())})
            continue
        results = []
        for c in calls:
            out = run_tool(view, c.name, c.input if isinstance(c.input, dict) else {})
            results.append({"type": "tool_result", "tool_use_id": c.id, "content": json.dumps(out),
                            "is_error": "error" in out})
        messages.append({"role": "user", "content": results})
