"""Control tasks for think-ctrl: reasoning-gym procedural puzzles in the same JSONL schema as `python -m engine tasks`.

    python -m posttrain.rg_tasks --n 300 --seed 7 --out think-ctrl-s7.jsonl     # 300 per dataset

Datasets: knights_knaves, zebra_puzzles (logic), shortest_path, maze (grid). These are in the bench's SECONDARY
reasoning-gym tier (near transfer), not the primary FT_BENCHMARKS suite. The bench draws them with dataset_seed
20261114; we use seed 7, so no item overlap. Prompt = reasoning-gym's default system prompt (answer inside
<answer></answer>), same as the bench. Reward = the dataset's own `score_answer` on reasoning-gym's `extract_answer`.
A sample's `meta` holds (dataset, seed, size, index) so the reward rebuilds the exact entry deterministically.
"""
from __future__ import annotations

import argparse
import json
from functools import lru_cache

DATASETS = ["knights_knaves", "zebra_puzzles", "shortest_path", "maze"]


@lru_cache(maxsize=32)
def _dataset(name: str, seed: int, size: int):
    import reasoning_gym as rg
    return rg.create_dataset(name, size=size, seed=seed)


def make(n: int, seed: int, datasets=DATASETS) -> list[dict]:
    from reasoning_gym.utils import SYSTEM_PROMPTS
    sysmsg = SYSTEM_PROMPTS["default"]
    out = []
    for name in datasets:
        ds = _dataset(name, seed, n)
        for i, e in enumerate(ds):
            out.append({"task": f"rg:{name}", "id": f"rg:{name}:{seed}:{i}", "prompt": e["question"],
                        "answer": str(e.get("answer")), "meta": {"dataset": name, "seed": seed, "size": n, "index": i},
                        "messages": [{"role": "system", "content": sysmsg}, {"role": "user", "content": e["question"]},
                                     {"role": "assistant", "content": f"<answer>{e.get('answer')}</answer>"}]})
    return out


def score(sample: dict, text: str) -> float:
    from reasoning_gym.utils import extract_answer
    m = sample["meta"]
    ds = _dataset(m["dataset"], int(m["seed"]), int(m["size"]))
    try:
        return float(ds.score_answer(answer=extract_answer(text), entry=ds[int(m["index"])]))
    except Exception:  # noqa: BLE001  malformed answers score 0, never crash training
        return 0.0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300, help="items per dataset")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--datasets", default=",".join(DATASETS))
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    rows = make(a.n, a.seed, a.datasets.split(","))
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"wrote {a.out}: {len(rows)} rows")


if __name__ == "__main__":
    main()
