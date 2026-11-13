"""OpenAI-compatible backend (OpenAI, OpenRouter, HF router, self-hosted vLLM on Verda, ...)."""
from __future__ import annotations

import json
import os

from openai import OpenAI

from .llm_agent import SYSTEM, TOOLS, first_prompt, run_tool

PROVIDERS = {
    "openai": (os.environ.get("OPENAI_BASE_URL"), "OPENAI_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "hf": ("https://router.huggingface.co/v1", "HF_TOKEN"),
    "vllm": (os.environ.get("VLLM_BASE_URL", "http://localhost:8000/v1"), "VLLM_API_KEY"),
}


def run_episode(provider, model, view, tr, max_turns=400):
    base_url, key_env = PROVIDERS[provider]
    client = OpenAI(base_url=base_url, api_key=os.environ.get(key_env, "EMPTY"))
    tools = [{"type": "function", "function": t} for t in TOOLS]
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": first_prompt(view)}]
    for turn in range(max_turns):
        if view.observe()["done"]:
            return
        resp = client.chat.completions.create(model=model, messages=messages, tools=tools)
        if resp.usage:
            tr.usage["input_tokens"] += resp.usage.prompt_tokens or 0
            tr.usage["output_tokens"] += resp.usage.completion_tokens or 0
        msg = resp.choices[0].message
        calls = msg.tool_calls or []
        messages.append({
            "role": "assistant", "content": msg.content or "",
            **({"tool_calls": [c.model_dump() for c in calls]} if calls else {}),
        })
        tr.add(turn=turn, text=msg.content or "",
               calls=[{"name": c.function.name, "input": c.function.arguments} for c in calls])
        if not calls:
            messages.append({"role": "user", "content": "The episode is not over. Continue using the tools. State: "
                             + json.dumps(view.observe())})
            continue
        for c in calls:
            try:
                args = json.loads(c.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            out = run_tool(view, c.function.name, args if isinstance(args, dict) else {})
            messages.append({"role": "tool", "tool_call_id": c.id, "content": json.dumps(out)})
