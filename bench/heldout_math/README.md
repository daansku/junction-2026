# Held-out MATH test (PROTOCOL amendment v5)

The test behind the S5 result: base Qwen3.5-9B **0.634** vs `think-games-h2` step 30 **0.674** on 175 held-out MATH
items, delta **+0.040**, paired-bootstrap 95% CI **[-0.029, +0.103]**, McNemar **p = 0.311**: not significant.

## What it measures

- MATH (`minerva_math`, lm-eval 0.4.13), 0-shot chain of thought, first 50 problems of each of the 7 subjects = 350 items,
  graded with `math_verify`.
- Frozen generation settings (`bench/configs/generation.yaml`): Qwen3.5 thinking sampling (temperature 1.0, top_p 0.95,
  top_k 20, presence_penalty 1.5), 8,192 new tokens, seed 1234, chat template.
- **Held-out half** = problems 26-50 of each subject (doc 25-49, 175 items). Nobody used these to pick a checkpoint.
  Report this number.
- **Selection half** = problems 1-25 (doc 0-24). The dev slice used to pick checkpoints. Report it only with the label
  "used for selection".
- Paired per item against base (`base_math_items.jsonl`, same items, same settings): bootstrap 95% CI of the
  difference, exact McNemar p and a permutation p.

## Files

| File | What |
|---|---|
| `run.sh` | merge (if LoRA) -> bench 350 MATH items -> rescore -> compare with base |
| `compare.py` | paired comparison of any run with base; works without a GPU |
| `base_math_items.jsonl` | base Qwen3.5-9B scores per item (the reference) |
| `step30_math_items.jsonl` | `think-games-h2` step 30 scores per item (the S5 result) |

## Run it on the B200 (exact steps)

The B200 (`95.133.252.154`) already has the Python env (`/root/rl-venv`: vLLM 0.33.0, lm-eval 0.4.13, torch 2.14)
and Qwen3.5-9B in `/dev/shm/hf`.

```bash
ssh -i a3_b200 root@95.133.252.154

# 1. the repo is already on the box (a copy of main, commit e6e7493; the GitHub repo is private,
#    so the box cannot clone it without your GitHub login)
cd /root/junction-2026

# 2. copy your model to the box (from your machine), e.g. a LoRA adapter dir:
#    scp -i a3_b200 -r ./my-adapter root@95.133.252.154:/root/models/my-adapter

# 3a. LoRA adapter on top of Qwen3.5-9B (merged first, the way step 30 was tested):
bash bench/heldout_math/run.sh my-model --lora /root/models/my-adapter

# 3b. or a full / already-merged model dir (or an HF id):
bash bench/heldout_math/run.sh my-model /root/models/my-merged-model

# 4. check the base reference reproduces (optional, ~4 min): rerun base and compare it with the stored base
bash bench/heldout_math/run.sh base-check Qwen/Qwen3.5-9B
```

Each run takes about 4 minutes on the B200 (plus about 20 s to merge a LoRA adapter). Results land in `out/heldout/<name>/`.
The last lines print, for example:

```
HELD-OUT (doc 25-49, report this): n=175 base=0.634 cand=0.674 delta=+0.040 95% CI [-0.029, +0.103] | only cand right 21, only base right 14 | McNemar p=0.311 | permutation p=0.309
selection half (doc 0-24): n=175 base=0.589 cand=0.623 delta=+0.034 95% CI [-0.040, +0.109] | ...
```

Rerun only the comparison (no GPU): `python bench/heldout_math/compare.py out/heldout/my-model`.

## Rules (so the number stays comparable)

- The model must be a Qwen3.5-9B derivative that uses the same chat template and `<think>` tags. Another base model
  needs its own base run: run `run.sh` on that base and pass it with `--base out/heldout/<base run>`.
- Change nothing in `bench/configs/` and pass no extra flags. `GPU_MEM` only changes vLLM's memory share, never the scores.
- Sampling is random (temperature 1.0, fixed seed), and 175 items is a small sample. A difference counts only when
  the 95% CI excludes 0.
- If you test several checkpoints and pick the best on the held-out half, that half is no longer held out. Pick on the
  selection half, then report the held-out half for that one model only.

## Off the B200

Any GPU with about 40 GB free works. Install `bench` (`pip install -e bench[gpu]` or the versions above), then set
`PY=<that python>` and `HF_HOME=<HF cache>` before calling `run.sh`.
