"""Run deterministic base or LoRA rover missions with the same Qwen checkpoint."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import time

from mission import RoverMission

SYSTEM = """You are the onboard planner for a small exploration rover. Use its accumulated map and notes to explore safely, find the hidden beacon, and return to base before battery runs out. Plan one move at a time. Keep notes concise and update the map/frontier or route when useful. Output only the requested JSON."""


def action_from(text: str) -> tuple[str | None, str]:
    match = re.search(r"\{.*?\}", text, re.S)
    if not match:
        return None, ""
    try:
        obj = json.loads(match.group())
    except json.JSONDecodeError:
        return None, ""
    action = str(obj.get("action", "")).strip().upper()
    if action not in ("ACTION1", "ACTION2", "ACTION3", "ACTION4"):
        return None, str(obj.get("notes", ""))[:1000]
    return action, str(obj.get("notes", ""))[:1000]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="HF id or local model directory")
    ap.add_argument("--adapter", help="optional PEFT adapter directory")
    ap.add_argument("--seeds", default="1000-1019")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-new-tokens", type=int, default=110)
    a = ap.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    seeds = [int(x) for x in a.seeds.split(",")] if "," in a.seeds else list(
        range(int(a.seeds.partition("-")[0]), int(a.seeds.partition("-")[2]) + 1)
    )
    tok = AutoTokenizer.from_pretrained(a.model)
    model = AutoModelForCausalLM.from_pretrained(
        a.model, dtype=torch.bfloat16, device_map="auto"
    )
    if a.adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, a.adapter)
    model.eval()
    device = model.get_input_embeddings().weight.device
    rows = []
    start_all = time.time()
    for seed in seeds:
        env = RoverMission.create(seed)
        notes, result = "", ""
        invalid = 0
        turns = 0
        action_trace = []
        while not env.done and turns < env.energy_max + 5:
            prompt = env.prompt(notes, result)
            messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
            ids = tok.apply_chat_template(messages, add_generation_prompt=True,
                                          tokenize=True, return_tensors="pt")["input_ids"].to(device)
            with torch.inference_mode():
                out = model.generate(ids, max_new_tokens=a.max_new_tokens, do_sample=False,
                                     pad_token_id=tok.eos_token_id)
            reply = tok.decode(out[0, ids.shape[1]:], skip_special_tokens=True)
            action, new_notes = action_from(reply)
            turns += 1
            if action is None:
                invalid += 1
                result = "INVALID REPLY: choose one allowed action in the JSON schema"
                notes = new_notes or notes
                continue
            notes = new_notes
            action_trace.append(action)
            result = env.act(action)
        row = {"seed": seed, "success": env.success, "found_beacon": env.found,
               "steps": env.steps, "turns": turns, "bumps": env.bumps,
               "energy_left": env.energy, "shortest_one_way": env.path_len,
               "energy_budget": env.energy_max, "invalid_replies": invalid,
               "final_pos": list(env.pos), "action_trace": action_trace}
        rows.append(row)
        print(json.dumps(row), flush=True)
    out_path = Path(a.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    print(json.dumps({"episodes": len(rows), "successes": sum(r["success"] for r in rows),
                      "success_rate": sum(r["success"] for r in rows) / max(len(rows), 1),
                      "wall_seconds": round(time.time() - start_all, 1), "out": str(out_path)}))


if __name__ == "__main__":
    main()
