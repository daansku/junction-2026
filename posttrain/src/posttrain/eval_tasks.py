"""In-domain check for RL checkpoints: mean engine reward on held-out task prompts (e.g. 200 game_turn, seed 2).

    python -m posttrain.eval_tasks --base Qwen/Qwen3.5-9B --tasks heldout-gameturn-s2.jsonl \
        --adapters /root/ckpt/games/lora /root/ckpt/grpo-2/step-20 ... --out eval.json

One vLLM engine, every adapter as a LoRARequest (the base model is scored too, `--no-base` skips it). Same chat
template and thinking setting as training (`enable_thinking` off), `--samples` replies per prompt at the training
temperature (default 4 at T=1.0) plus one greedy reply. Reward = `engine.tasks.reward` (unchanged).
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="Qwen/Qwen3.5-9B")
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--adapters", nargs="*", default=[])
    ap.add_argument("--no-base", action="store_true")
    ap.add_argument("--samples", type=int, default=4)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--gpu-mem", type=float, default=0.85)
    ap.add_argument("--thinking", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    from engine.tasks import reward
    from vllm import LLM, SamplingParams
    from vllm.lora.request import LoRARequest

    rows = [json.loads(l) for l in open(a.tasks, encoding="utf-8")]
    convs = [[m for m in s["messages"] if m["role"] != "assistant"] for s in rows]
    llm = LLM(model=a.base, enable_lora=True, max_lora_rank=64, max_loras=1, gpu_memory_utilization=a.gpu_mem,
              max_model_len=6144, language_model_only=True, seed=0)
    kw = dict(chat_template_kwargs={"enable_thinking": bool(a.thinking)}, use_tqdm=False)
    targets = ([] if a.no_base else [("base", None)]) + [(d, d) for d in a.adapters]
    results = {}
    for i, (name, path) in enumerate(targets):
        t0 = time.time()
        req = LoRARequest(f"a{i}", i + 1, path) if path else None
        greedy = llm.chat(convs, SamplingParams(temperature=0, max_tokens=a.max_tokens), lora_request=req, **kw)
        samp = llm.chat(convs, SamplingParams(temperature=a.temperature, max_tokens=a.max_tokens, n=a.samples, seed=0),
                        lora_request=req, **kw)
        g = [reward(s, o.outputs[0].text) for s, o in zip(rows, greedy)]
        r = [reward(s, c.text) for s, o in zip(rows, samp) for c in o.outputs]
        by_task = {}
        for s, x in zip(rows, g):
            by_task.setdefault(s["task"], []).append(x)
        results[name] = {"greedy_mean": sum(g) / len(g), f"sampled_mean_T{a.temperature}": sum(r) / len(r),
                         "greedy_by_task": {k: sum(v) / len(v) for k, v in by_task.items()},
                         "n_prompts": len(rows), "seconds": round(time.time() - t0)}
        print(f"[eval] {name}: greedy {results[name]['greedy_mean']:.3f} "
              f"sampled {results[name][f'sampled_mean_T{a.temperature}']:.3f}", flush=True)
        Path(a.out).write_text(json.dumps({"tasks": a.tasks, "base": a.base, "results": results}, indent=1))


if __name__ == "__main__":
    main()
