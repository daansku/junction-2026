"""Build the three SFT v2 training sets with the same token count.

    python -m posttrain.build_sft_v2 --aux aux-s0.jsonl --turns turns-v2.jsonl --out /root/sftv2 --tokens 2500000

  games  the engine's auxiliary verifiable tasks (`python -m engine tasks`) + h1 game turns with Narrator rationales,
         half and half by tokens.
  ctrl   general instruction/reasoning SFT data with no game content (allenai/tulu-3-sft-mixture, single-turn,
         short, sources that overlap the FT_BENCHMARKS suite removed), same token count.
  mix    half of games + half of ctrl (no item reused across halves).
Format for every row: chat messages, plain answers (no thinking text in targets), rendered by the Qwen3.5 chat
template at training time. Tokens are counted on the full chat-templated sequence with the Qwen3.5 tokenizer.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

# Tulu-3 sources that overlap the FT_BENCHMARKS suite (maths word problems, MATH, MMLU-style, medicine) -> excluded
EXCLUDE = ("gsm", "math", "mmlu", "med", "numina", "aime", "bbh", "big_bench", "flan")


def read(path: str) -> list[dict]:
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def take(rows: list[dict], budget: int, rng: random.Random) -> tuple[list[dict], int]:
    rows = rows[:]
    rng.shuffle(rows)
    out, n = [], 0
    for r in rows:
        if n >= budget:
            break
        out.append(r)
        n += r["_tok"]
    return out, n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aux", required=True)
    ap.add_argument("--turns", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tokens", type=int, default=2_500_000, help="training tokens per row")
    ap.add_argument("--tokenizer", default="Qwen/Qwen3.5-9B")
    ap.add_argument("--max-len", type=int, default=2048)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(a.tokenizer)
    rng = random.Random(a.seed)

    def ntok(messages) -> int:
        return len(tok(tok.apply_chat_template(messages, tokenize=False), add_special_tokens=False)["input_ids"])

    def prep(rows, source):
        out = []
        for r in rows:
            m = r["messages"]
            n = ntok(m)
            if n <= a.max_len:
                out.append({"messages": m, "meta": {**r.get("meta", {}), "source": source}, "_tok": n})
        return out

    aux = prep(read(a.aux), "aux-task")
    turns = prep(read(a.turns), "game-turn")
    half = a.tokens // 2
    g_aux, n1 = take(aux, half, rng)
    g_turn, n2 = take(turns, a.tokens - n1, rng)
    games = g_aux + g_turn
    print(f"games: {len(g_aux)} aux ({n1} tok) + {len(g_turn)} turns ({n2} tok) = {n1 + n2} tokens")

    from datasets import load_dataset
    ds = load_dataset("allenai/tulu-3-sft-mixture", split="train", streaming=True).shuffle(seed=a.seed, buffer_size=20000)
    ctrl_pool, seen, need = [], 0, int(a.tokens * 1.6)
    for ex in ds:
        src = str(ex.get("source", "")).lower()
        msgs = ex.get("messages") or []
        if any(k in src for k in EXCLUDE) or len(msgs) != 2 or msgs[0]["role"] != "user" or msgs[1]["role"] != "assistant":
            continue
        n = ntok(msgs)
        if 64 <= n <= a.max_len:
            ctrl_pool.append({"messages": msgs, "meta": {"source": "tulu3:" + src}, "_tok": n})
            seen += n
        if seen >= need:
            break
    ctrl, n3 = take(ctrl_pool, a.tokens, rng)
    print(f"ctrl: {len(ctrl)} tulu-3 items ({n3} tokens) from a pool of {len(ctrl_pool)}")

    rng.shuffle(games)
    gm, n4 = take(games, half, rng)
    rest = [r for r in ctrl_pool if r not in ctrl] or ctrl_pool
    cm, n5 = take(rest, a.tokens - n4, rng)
    mix = gm + cm
    print(f"mix: {len(gm)} game items ({n4} tok) + {len(cm)} tulu items ({n5} tok) = {n4 + n5} tokens")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in (("games", games), ("ctrl", ctrl), ("mix", mix)):
        rng.shuffle(rows)
        with open(out / f"{name}.jsonl", "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps({"messages": r["messages"], "meta": r["meta"]}) + "\n")
        (out / f"{name}.stats.json").write_text(json.dumps({"items": len(rows), "tokens": sum(r["_tok"] for r in rows),
                                                            "tokenizer": a.tokenizer, "max_len": a.max_len,
                                                            "seed": a.seed}, indent=1))
    print("wrote", out)


if __name__ == "__main__":
    main()
