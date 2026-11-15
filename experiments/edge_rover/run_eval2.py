"""Batched rover v2 eval with vLLM: all missions advance one step per generate call (greedy, thinking off).

    CUDA_VISIBLE_DEVICES=0 python run_eval2.py --model /root/ckpt/games/merged --name games \
        --seeds 5000-5149 --controls hidden,fixed --outdir results
Writes results/<name>-<controls>.jsonl (one row per mission) and prints a summary line per condition.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import time

from mission2 import ACTIONS, BASE, Rover, bfs

SYSTEM = ("You are the onboard planner of a small exploration rover. Use the map, your position history and your "
          "notes to explore efficiently, find the hidden beacon and return to base before the battery runs out. "
          "Output only the requested JSON.")


def parse(text: str) -> tuple[str | None, str]:
    for m in re.finditer(r"\{.*?\}", text, re.S):
        try:
            obj = json.loads(m.group())
        except json.JSONDecodeError:
            continue
        a = str(obj.get("action", "")).strip().upper()
        return (a if a in ACTIONS else None), str(obj.get("notes", ""))[:600]
    m = re.search(r"ACTION[1-4]", text)
    return (m.group() if m else None), ""


def seeds_of(s: str) -> list[int]:
    if "-" in s and "," not in s:
        a, b = s.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in s.split(",")]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--seeds", default="1000-1029")
    ap.add_argument("--controls", default="hidden,fixed")
    ap.add_argument("--outdir", default="results")
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--gpu-mem", type=float, default=0.85)
    ap.add_argument("--think", action="store_true",
                    help="thinking ON, Qwen3.5 model-card sampling (T=0.6, top_p=0.95, top_k=20), seeded per mission/turn")
    a = ap.parse_args()

    from vllm import LLM, SamplingParams
    if a.think and a.max_tokens == 400:
        a.max_tokens = 2048
    llm = LLM(a.model, dtype="bfloat16", max_model_len=12288 if a.think else 4096, gpu_memory_utilization=a.gpu_mem,
              enable_prefix_caching=True, seed=0, limit_mm_per_prompt={"image": 0})
    sp = SamplingParams(temperature=0.0, max_tokens=a.max_tokens)
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    seeds = seeds_of(a.seeds)
    for controls in a.controls.split(","):
        t0 = time.time()
        envs = {s: Rover.create(s, controls) for s in seeds}
        st = {s: {"notes": "", "last": "", "invalid": 0, "turns": 0, "replies": []} for s in seeds}
        # live direction metric: true shortest-path distance to the current target (beacon, then base)
        dist = {s: (bfs(envs[s].walls, envs[s].goal), bfs(envs[s].walls, BASE)) for s in seeds}
        tdist = lambda s: dist[s][1 if envs[s].found else 0].get(envs[s].pos, 99)
        mlog = out / f"{a.name}-{controls}.metrics.jsonl"
        mlog.write_text("")
        cum = {"good": 0, "moves": 0, "bumps": 0}
        while True:
            live = [s for s in seeds if not envs[s].done and st[s]["turns"] < envs[s].energy_max + 10]
            if not live:
                break
            msgs = [[{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": envs[s].prompt(st[s]["notes"], st[s]["last"])}] for s in live]
            if a.think:
                sps = [SamplingParams(temperature=0.6, top_p=0.95, top_k=20, max_tokens=a.max_tokens,
                                      seed=s * 1000 + st[s]["turns"]) for s in live]
            res = llm.chat(msgs, sps if a.think else sp, use_tqdm=False,
                           chat_template_kwargs={"enable_thinking": a.think})
            texts = [r.outputs[0].text for r in res]
            if a.think:  # budget forcing: a reply cut off inside its thinking is closed and asked for the answer
                cut = [i for i, t in enumerate(texts) if "</think>" not in t]
                if cut:
                    tok = llm.get_tokenizer()
                    prompts = [tok.apply_chat_template(msgs[i], tokenize=False, add_generation_prompt=True,
                                                       enable_thinking=True) + texts[i] +
                               "\n\nTime is up. I must answer now.\n</think>\n\n" for i in cut]
                    fin = llm.generate(prompts, SamplingParams(temperature=0.0, max_tokens=300), use_tqdm=False)
                    for i, f in zip(cut, fin):
                        texts[i] = texts[i] + "\n</think>\n\n" + f.outputs[0].text
                        st[live[i]]["forced"] = st[live[i]].get("forced", 0) + 1
            good = moves = bumps = 0
            for s, r, text in zip(live, res, texts):
                if a.think:
                    st[s]["think_tokens"] = st[s].get("think_tokens", 0) + len(r.outputs[0].token_ids)
                    text = text.split("</think>")[-1]
                act, notes = parse(text)
                x = st[s]
                x["turns"] += 1
                if len(x["replies"]) < 3:
                    x["replies"].append(text[:400])
                if act is None:
                    x["invalid"] += 1
                    x["last"] = "INVALID REPLY: answer with the JSON and one of ACTION1-ACTION4"
                    x["notes"] = notes or x["notes"]
                    continue
                x["notes"] = notes
                d0, f0, b0 = tdist(s), envs[s].found, envs[s].bumps
                x["last"] = envs[s].act(act)
                moves += 1
                bumps += envs[s].bumps - b0
                good += (envs[s].found and not f0) or tdist(s) < d0
            cum["good"] += good
            cum["moves"] += moves
            cum["bumps"] += bumps
            row = {"step": max(st[s]["turns"] for s in seeds), "t": round(time.time() - t0), "live": len(live),
                   "n": len(seeds), "found": sum(e.found for e in envs.values()),
                   "success": sum(e.success for e in envs.values()),
                   "good_pct": round(100 * good / max(moves, 1), 1), "bump_pct": round(100 * bumps / max(moves, 1), 1),
                   "good_pct_cum": round(100 * cum["good"] / max(cum["moves"], 1), 1),
                   "mean_dist": round(sum(tdist(s) for s in live) / len(live), 2)}
            with open(mlog, "a") as f:
                f.write(json.dumps(row) + "\n")
        rows = []
        for s in seeds:
            e, x = envs[s], st[s]
            rows.append({"model": a.name, "controls": controls, "seed": s, "success": e.success, "found": e.found,
                         "steps": e.steps, "bumps": e.bumps, "energy_left": e.energy, "energy_max": e.energy_max,
                         "one_way": e.path_len, "invalid": x["invalid"], "turns": x["turns"],
                         "think_tokens": x.get("think_tokens", 0), "forced_answers": x.get("forced", 0), "mapping": e.mapping, "history": e.history, "first_replies": x["replies"]})
        p = out / f"{a.name}-{controls}.jsonl"
        p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        n = len(rows)
        print(json.dumps({"model": a.name, "controls": controls, "n": n,
                          "success": sum(r["success"] for r in rows), "found": sum(r["found"] for r in rows),
                          "bumps_mean": round(sum(r["bumps"] for r in rows) / n, 2),
                          "invalid": sum(r["invalid"] for r in rows), "wall_s": round(time.time() - t0)}), flush=True)


if __name__ == "__main__":
    main()
