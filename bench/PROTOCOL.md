# Bench protocol (pre-registration)

**Status: DRAFT v1 (A2, Sat 14.11 17:00).** Needs review by A3 (training) and A5 (analysis), then **human approval by 19:00** (PLAN.md §6).
After approval, nobody changes the benchmark list, the generation settings, the comparisons or the checkpoint rule.
Any change after that is a new protocol version, and every row is rerun under it.

This file is written **before any trained model is scored**. SFT v1 (`verda-ft-qwen3-5-9b`) already exists, but its bench numbers do not exist yet.

## 1. Question

Does post-training Qwen3.5-9B on experience from our games improve its reasoning on **outside** benchmarks (logical tier),
beyond what the same amount of non-game fine-tuning gives, without hurting general ability (regression-guard tier)?

## 2. Models compared

| Row | What | Role |
|---|---|---|
| `base` | `Qwen/Qwen3.5-9B` (HF snapshot `c202236…`), no fine-tuning | reference |
| `sft-v1` | A3's SFT v1 (optimal action sequences, h1 format) | free data point, reported, not a candidate |
| `ctrl` | SFT v2, general open reasoning data only, **same token count** as `games`/`mix` | control: "more fine-tuning" |
| `games` | SFT v2, game data only | candidate |
| `mix` | SFT v2, general + game data | candidate |
| `rl-*` | GRPO checkpoints from the best SFT v2 checkpoint | candidates (dev slice), finalist (full list) |

All rows share the base model, LoRA recipe (A3, `posttrain/`) and the generation settings below.

## 3. Benchmarks (frozen list: `bench/configs/benchmarks.yaml`, version 1)

| Tier | Benchmarks | Items |
|---|---|---|
| Near transfer | reasoning-gym `maze`, `sokoban`, `rush_hour`, `shortest_path`, `arc_1d`, `arc_agi` (ARC-AGI-1 in text form); plus our held-out `eval-v1` / `eval-v2` games scored by the arena (A3 `finetune-eval`, h1 and h2) | 100 each (fixed seed) |
| **Logical (target)** | reasoning-gym `zebra_puzzles`, `knights_knaves`; BBH (CoT, zero-shot) `logical_deduction` 5 and 7 objects, `tracking_shuffled_objects` 5 and 7, `navigate`, `web_of_lies`; MuSR (lm-eval `leaderboard_musr`, multiple choice) | 200 / 250 / 756 |
| Regression guard | GSM8K (CoT zero-shot), MATH-500 (`minerva_math500`), MMLU-Pro (first 50 per subject, 700 items), IFEval | full except MMLU-Pro |

Notes, all checked against the installed tools (lm-evaluation-harness 0.4.13, reasoning-gym, Sat 17:10):
- **Dropped:** FOLIO (not in lm-eval 0.4.13). The official ZebraLogic and K&K datasets are replaced by reasoning-gym's procedural `zebra_puzzles` and `knights_knaves`, which generate fresh items from a seed (no contamination). They are labelled as such everywhere.
- MuSR runs as loglikelihood multiple choice (the only form lm-eval ships). This is the Open LLM Leaderboard setup.
- reasoning-gym items: dataset seed `20261114`, item `i` = the i-th item of that seeded dataset, graded by the library's own `score_answer` (partial credit where the library gives it, e.g. near-correct paths).

## 4. Generation settings (frozen: `bench/configs/generation.yaml`, version 1)

- vLLM 0.33.0, bf16, one A100 80 GB, `language_model_only` (text benchmarks).
- Chat template applied, **thinking mode on** (the model's default). Graded text = everything after `</think>`.
- Sampling from the Qwen3.5 model card ("thinking mode, general tasks"): temperature 1.0, top_p 0.95, top_k 20, min_p 0, presence_penalty 1.5, repetition_penalty 1.0.
- `max_gen_toks` 8192 (thinking + answer), context 12288. A reply cut off at the limit is graded as is and counted in `truncated` per benchmark. Same limit for every model, so a model that learns to think shorter is not penalised by us and not helped either.
- Seeds: vLLM / lm-eval 1234. One sample per item.

## 5. Statistics

- Per benchmark: mean of per-item scores, 95% percentile bootstrap CI over items (10,000 resamples, seed 20261114).
- **Paired comparison** (candidate vs reference) per benchmark: bootstrap of the mean per-item difference over the items both runs scored. A delta "excludes zero" when its 95% CI does not contain 0. Items missing on one side are dropped and counted, never imputed.
- Tier score = unweighted mean over the tier's benchmarks (each benchmark counts once, whatever its size). Tier delta = mean of the per-benchmark deltas.
- Effects are reported **per benchmark**, never only as an average. No multiple-comparison correction is applied; with ~9 logical benchmarks, about one in twenty CIs excludes zero by chance, so a single significant benchmark is reported as weak evidence.

## 6. Pre-registered comparisons

1. **Primary:** `games` vs `ctrl` and `mix` vs `ctrl` on the logical tier.
2. Secondary: each candidate vs `base` on every tier; `sft-v1` vs `base`.
3. Regression check: guard-tier delta vs `base` for every candidate.

**Claim rule (honesty, PLAN §3.3):** we say "training on our games improved reasoning" only if a candidate beats `ctrl` on the logical-tier mean **and** on at least two logical benchmarks with CIs excluding zero, with no guard benchmark dropping by more than 2 points with a CI excluding zero. Otherwise the pitch says plainly that no transfer was shown and reports the in-domain (game) gain.

## 7. Checkpoint choice (fixed before results; PLAN §3.3)

- RL checkpoints are scored on the **dev slice** only: `rg_zebra_puzzles`, `rg_knights_knaves`, `bbh_logical_deduction_5`, `bbh_web_of_lies`, `gsm8k`, first 100 items each (`python -m bench run --dev-slice`).
- **Finalist** = the checkpoint with the best mean over the dev slice's four logical benchmarks whose GSM8K drop vs `base` is ≤ 2 points. Ties: the earlier checkpoint.
- The finalist (and `ctrl`, `games`, `mix`) then run the **full list once**. Those are the numbers we report. Dev-slice items are the first 100 of the full sets, so the final numbers on those benchmarks are partly in-sample for the choice; this is stated next to the result.

## 8. How to run

```bash
# on the GPU box (/srv/bench, venv with the gpu extras)
CUDA_VISIBLE_DEVICES=1 python -m bench run --model Qwen/Qwen3.5-9B --out data/derived/bench/base
CUDA_VISIBLE_DEVICES=1 python -m bench run --model Qwen/Qwen3.5-9B --lora <adapter dir> --out data/derived/bench/sft-mix
CUDA_VISIBLE_DEVICES=1 python -m bench run --model <merged dir> --dev-slice --out data/derived/bench/rl-step-200
# anywhere
python -m bench compare --ref data/derived/bench/ctrl --cand data/derived/bench/sft-mix --out data/derived/bench/delta-mix-vs-ctrl.json
```
`compare` warns when two runs used a different config hash (different list or settings): such deltas are not valid.

## Sign-off
- [ ] A3 (training rows, LoRA recipe, token-count matching)
- [ ] A5 (statistics, tier definitions, summary format)
- [ ] Humans (approve the list and the checkpoint rule; after this nothing changes)
