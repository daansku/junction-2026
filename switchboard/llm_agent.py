"""Provider-agnostic pieces of the LLM agent: tool specs, tool execution, transcripts, dispatch.

Spec format for --llm:  <provider>:<model>
    anthropic:claude-opus-5-5          (ANTHROPIC_API_KEY)            -> llm_anthropic.py
    openai:<model>                     (OPENAI_API_KEY, OPENAI_BASE_URL optional)
    openrouter:<vendor/model>          (OPENROUTER_API_KEY)
    vllm:<model>                       (VLLM_BASE_URL, e.g. a Verda box running vLLM)
    hf:<model>                         (HF_TOKEN, HuggingFace router)

The judged harness (Harbor + OpenCode over MCP) does not use this file; it talks to
mcp_server.py. This runner exists so we can benchmark many models cheaply and collect
trajectories for training.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .env import PublicView, SwitchboardEnv

SYSTEM = (
    "You are an agent operating a device through tools. Work carefully: every action costs budget. "
    "Keep acting with the tools until the episode is done. Do not stop to ask questions; nobody will answer."
)

TOOLS = [
    {
        "name": "press",
        "description": "Press one switch. Costs 1 budget. Returns the new lamp state and whether the current target was reached.",
        "parameters": {
            "type": "object",
            "properties": {"switch": {"type": "string", "description": "Switch letter, e.g. 'A'"}},
            "required": ["switch"],
            "additionalProperties": False,
        },
    },
    {
        "name": "reset",
        "description": "Restore the starting lamps and clear all hidden press counts/unlocks. Costs the reset cost. Completed targets stay completed.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_state",
        "description": "Free. Returns current lamps, current target, budget and progress.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "finish",
        "description": "End the episode now. Only do this if you cannot make further progress.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]


def run_tool(view: PublicView, name: str, args: dict) -> dict:
    if name == "press":
        return view.press(str(args.get("switch", "")))
    if name == "reset":
        return view.reset()
    if name == "get_state":
        return view.observe()
    if name == "finish":
        return view.finish()
    return {"error": f"unknown tool {name}"}


def first_prompt(view: PublicView) -> str:
    return view.instructions + "\n\nCurrent state:\n" + json.dumps(view.observe())


class Transcript:
    def __init__(self, log_dir: Path | None, spec: str, env: SwitchboardEnv, run_idx: int):
        self.path = None
        if log_dir:
            log_dir.mkdir(parents=True, exist_ok=True)
            safe = spec.replace(":", "_").replace("/", "_")
            self.path = log_dir / f"{safe}__{env.tier.name}__seed{env.ep.seed}__run{run_idx}__{int(time.time())}.json"
        self.spec, self.env, self.run_idx = spec, env, run_idx
        self.steps: list[dict] = []
        self.usage = {"input_tokens": 0, "output_tokens": 0}

    def add(self, **kw):
        self.steps.append(kw)

    def save(self, error: str | None = None):
        if not self.path:
            return
        self.path.write_text(json.dumps({
            "spec": self.spec, "run": self.run_idx, "summary": self.env.summary(),
            "error": error, "usage": self.usage, "steps": self.steps,
            "env_history": self.env.history,
        }, indent=1))


def make_llm_policy(spec: str, log_dir: Path | None = None, max_turns: int = 400):
    provider, _, model = spec.partition(":")
    if provider == "anthropic":
        from .llm_anthropic import run_episode
    else:
        from .llm_openai import run_episode

    def policy(env: SwitchboardEnv, rng_seed: int = 0, **_):
        run_idx = rng_seed % 1000
        tr = Transcript(log_dir, spec, env, run_idx)
        err = None
        try:
            run_episode(provider, model, PublicView(env), tr, max_turns=max_turns)
        except Exception as e:  # keep the eval going; the episode just scores what it reached
            err = f"{type(e).__name__}: {e}"
            print(f"  [{spec} seed {env.ep.seed}] error: {err}")
        tr.save(err)

    return policy
