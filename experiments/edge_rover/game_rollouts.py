"""Expert-iteration RL, step 1: the policy plays whole levels of our train games (multi-turn, thinking ON, its own
notes), and each episode gets the outcome reward only (level solved -> min(1, optimal/actions), else 0).

Uses the real h1 harness: arena SYSTEM prompt, build_parts (screen as RLE), parse_reply. No oracle notes, no
per-move shaping, so probing is never punished: only solving the level pays.

    CUDA_VISIBLE_DEVICES=0 python game_rollouts.py --model Qwen/Qwen3.5-9B --games 0-63 --levels 2,3,4 --k 2 \
        --out rollouts/a.jsonl
Writes one line per episode: {game_id, level, attempt, solved, reward, actions, optimal, turns: [{user, reply}]}.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
import zlib

ROOT = Path(__file__).resolve().parent / "repo"
sys.path[:0] = [str(ROOT / "arena" / "src"), str(ROOT / "engine" / "src")]

from arena.agent_loop import SYSTEM, build_parts, parse_reply  # noqa: E402
from arena.dataset import parts_to_text  # noqa: E402
from engine import list_games, load_game  # noqa: E402
from engine.tasks.common import visible_roles  # noqa: E402

SHAPE = {"full": "S", "ring": "O", "dot": "o", "cross": "+", "x": "X", "corners": "C", "hbar": "-", "vbar": "|",
         "checker": "K", "frame_dot": "D", "bars": "B", "diag": "/", "diamond": "V", "half": "H", "tri": "T",
         "arrow_up": "^", "arrow_down": "v", "arrow_left": "<", "arrow_right": ">"}
SHAPE_WORD = {"S": "solid square", "O": "ring", "o": "small dot", "+": "plus sign", "X": "X mark", "C": "corner tile",
              "-": "horizontal bar", "|": "vertical bar", "K": "checkered tile", "D": "framed dot", "B": "barred tile",
              "/": "striped tile", "V": "diamond", "H": "half tile", "T": "triangle", "^": "arrow up", "v": "arrow down",
              "<": "arrow left", ">": "arrow right"}
SYSTEM_COMPACT_NOTE = ("\n\nIn this version you see the game board directly: a small grid where each cell is a 2-character "
                       "code, colour index (0-f) + shape letter, explained in a legend. '..' is empty floor. Which code "
                       "is you, which is the goal, and what each one does is NOT given: find out by acting.")


def compact(g) -> str:
    """The logical board as colour+shape codes only (what the pixels show), never role names."""
    lv, st = g.level, g.state
    cells = visible_roles(lv, st, g.skin)
    used = {}
    rows = []
    for y in range(lv.h):
        row = []
        for x in range(lv.w):
            r = cells.get((x, y))
            if r is None or r[0] == "floor":
                row.append("..")
                continue
            col, spr = g.skin.get(r[0], (0, "full"))
            code = f"{col:x}{SHAPE.get(spr, '?')}"
            used[code] = f"colour {col:x} {SHAPE_WORD.get(SHAPE.get(spr, '?'), 'tile')}"
            row.append(code)
        rows.append(" ".join(row))
    t = g.truth()
    legend = "; ".join(f"{k} = {v}" for k, v in sorted(used.items()))
    return (f"Board ({lv.w} columns x {lv.h} rows, row 0 at the top):\n" + "\n".join(rows)
            + f"\nLegend: {legend}\nMoves used on this level: {t['moves_used']} of {t['move_budget']}.")

COLL = ROOT / "data" / "collections" / "train-v1.json"
HISTORY = 12
BRIEF = ("\n\nThinking budget: you have about 400 tokens of private reasoning per turn, then you must answer. "
         "Be efficient: do not redescribe the whole screen or repeat your notes. Think in short bullet points: "
         "what changed after the last action, what that tells you about the rules, and which action to take next "
         "and why. Then output the JSON. Keep the JSON notes under 40 words: no board descriptions in them.")


def changed(a, b) -> int:
    return sum(x != y for ra, rb in zip(a, b) for x, y in zip(ra, rb))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--games", default="0-63", help="index range into train-v1")
    ap.add_argument("--levels", default="2,3,4")
    ap.add_argument("--k", type=int, default=2, help="attempts per level (different sampling seeds)")
    ap.add_argument("--max-tokens", type=int, default=2048)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-opt", type=int, help="curriculum: every level of every train game with optimal <= this")
    ap.add_argument("--cap-extra", type=int, default=8, help="episode move cap = 2 x optimal + this")
    ap.add_argument("--obs", default="rle", choices=["rle", "compact"])
    ap.add_argument("--brief", action="store_true", help="append the thinking-budget instruction to the system prompt")
    ap.add_argument("--max-wall", type=int, default=2100, help="seconds; unfinished episodes count as unsolved")
    a = ap.parse_args()

    from vllm import LLM, SamplingParams
    system = SYSTEM + (SYSTEM_COMPACT_NOTE if a.obs == "compact" else "") + (BRIEF if a.brief else "")
    lo, hi = map(int, a.games.split("-"))
    metas = list_games(str(COLL))[lo:hi + 1]
    eps = []
    if a.max_opt:  # curriculum over all train games, sliced by --games so two GPUs can split the work
        metas = list_games(str(COLL))[lo:hi + 1]
    for m in metas:
        lvls = ([i + 1 for i, o in enumerate(m["optimal_moves"]) if o <= a.max_opt] if a.max_opt
                else list(map(int, a.levels.split(","))))
        for lv in lvls:
            for k in range(a.k):
                g = load_game(str(COLL), m["game_id"])
                g.goto_level(lv)
                opt = g.truth()["optimal_moves"]
                eps.append({"g": g, "game_id": m["game_id"], "level": lv, "attempt": k, "optimal": opt,
                            "cap": 2 * opt + a.cap_extra, "notes": "", "hist": [], "turns": [], "actions": 0,
                            "solved": False, "done": False, "frame": g.frame(), "seed": zlib.crc32(f"{m['game_id']}|{lv}|{k}".encode()) % 10**6})
    print(f"{len(eps)} episodes", flush=True)
    llm = LLM(a.model, dtype="bfloat16", max_model_len=12288, gpu_memory_utilization=0.88,
              enable_prefix_caching=True, seed=0, limit_mm_per_prompt={"image": 0})
    tok = llm.get_tokenizer()
    t0, step = time.time(), 0
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    while True:
        live = [e for e in eps if not e["done"]]
        if not live or time.time() - t0 > a.max_wall:
            break
        step += 1
        users = []
        for e in live:
            allowed = [x.value for x in e["g"].available_actions()]
            e["allowed"] = allowed
            if a.obs == "compact":
                parts = build_parts(e["frame"], e["notes"], e["hist"], allowed, [], e["actions"] + 1)
                parts.insert(1, {"type": "text", "text": compact(e["g"])})
            else:
                parts = build_parts(e["frame"], e["notes"], e["hist"], allowed, ["rle"], e["actions"] + 1)
            users.append(parts_to_text(parts))
        msgs = [[{"role": "system", "content": system}, {"role": "user", "content": u}] for u in users]
        sps = [SamplingParams(temperature=0.6, top_p=0.95, top_k=20, max_tokens=a.max_tokens,
                              seed=e["seed"] * 100 + e["actions"]) for e in live]
        res = llm.chat(msgs, sps, use_tqdm=False, chat_template_kwargs={"enable_thinking": True})
        texts = [r.outputs[0].text for r in res]
        cut = [i for i, t in enumerate(texts) if "</think>" not in t]
        if cut:  # same budget forcing as the rover eval
            prompts = [tok.apply_chat_template(msgs[i], tokenize=False, add_generation_prompt=True, enable_thinking=True)
                       + texts[i] + "\n\nTime is up. I must answer now.\n</think>\n\n" for i in cut]
            fin = llm.generate(prompts, SamplingParams(temperature=0.0, max_tokens=900), use_tqdm=False)
            for i, f in zip(cut, fin):
                texts[i] = texts[i] + "\n\nTime is up. I must answer now.\n</think>\n\n" + f.outputs[0].text
        # Forced-valid answers: any reply whose JSON does not parse is re-answered from the SAME thinking with
        # schema-constrained decoding (action limited to the available actions, notes capped), so a formatting slip
        # never ends an episode. The repaired reply (thinking + constrained JSON) is what gets recorded and trained on.
        from vllm.sampling_params import StructuredOutputsParams
        bad = [i for i, (e, t) in enumerate(zip(live, texts)) if parse_reply(t.split("</think>")[-1], e["allowed"])[0] is None]
        if bad:
            heads = [texts[i].split("</think>")[0].replace("\n\nTime is up. I must answer now.", "") for i in bad]
            prompts = [tok.apply_chat_template(msgs[i], tokenize=False, add_generation_prompt=True, enable_thinking=True)
                       + h + "\n</think>\n\n" for i, h in zip(bad, heads)]
            schemas = [{"type": "object", "properties": {
                "notes": {"type": "string", "maxLength": 300}, "hypothesis": {"type": "string", "maxLength": 200},
                "belief": {"type": "string", "enum": ["playing", "won", "lost"]},
                "action": {"type": "string", "enum": live[i]["allowed"]}},
                "required": ["notes", "hypothesis", "belief", "action"], "additionalProperties": False} for i in bad]
            fixed = llm.generate(prompts, [SamplingParams(temperature=0.0, max_tokens=400,
                                                          structured_outputs=StructuredOutputsParams(json=sc))
                                           for sc in schemas], use_tqdm=False)
            for i, h, f in zip(bad, heads, fixed):
                texts[i] = h + "\n</think>\n\n" + f.outputs[0].text
                live[i]["repaired"] = live[i].get("repaired", 0) + 1
        for e, u, text in zip(live, users, texts):
            answer = text.split("</think>")[-1]
            d, err = parse_reply(answer, e["allowed"])
            e["turns"].append({"user": u, "reply": text, "valid": d is not None, "forced": "Time is up." in text})
            if d is None:
                e["invalid"] = e.get("invalid", 0) + 1
                if e["invalid"] > 10:
                    e["done"] = True
                continue
            g, lv0 = e["g"], e["g"].truth()["level"]
            prev = e["frame"]
            e["frame"] = g.step(d["action"])
            e["actions"] += 1
            e["hist"].append((d["action"], changed(prev, e["frame"])))
            e["notes"] = d.get("notes", "")
            t = g.truth()
            if t["state"] == "WIN" or t["level"] > lv0:
                e["solved"], e["done"] = True, True
            elif e["actions"] >= e["cap"] or t["state"] == "GAME_OVER":
                e["done"] = True
        n_s = sum(e["solved"] for e in eps)
        print(json.dumps({"step": step, "t": round(time.time() - t0), "live": len(live), "solved": n_s,
                          "episodes": len(eps)}), flush=True)
    with out.open("w", encoding="utf-8") as f:
        for e in eps:
            f.write(json.dumps({"game_id": e["game_id"], "level": e["level"], "attempt": e["attempt"],
                                "solved": e["solved"], "optimal": e["optimal"], "actions": e["actions"], "repaired": e.get("repaired", 0),
                                "reward": min(1.0, e["optimal"] / e["actions"]) if e["solved"] else 0.0,
                                "system": system, "turns": e["turns"]}) + "\n")
    print("wrote", out, sum(e["solved"] for e in eps), "solved of", len(eps))


if __name__ == "__main__":
    main()
