# Bench protocol (pre-registration)

**Status: amendments v5 (MATH finalist + held-out) and v4 (BBH removed) below. Base text: v3; v3 only cuts item counts from v2.** Approved before any trained model was scored.
After approval, nobody changes the benchmark list, the generation settings, the comparisons or the checkpoint rule.
Any change after that is a new protocol version, and every row is rerun under it.

**v3 change:** every model runs a **fixed subsample** of the suite (~2,250 generative items + full MedQA), the same items for every model, because the full ~17k-item suite takes ~13 h per model on the shared vLLM server. Item counts are in §3.

**v2 changes:** the primary suite is the list in `FT_BENCHMARKS.md` (replacing the v1 list);
decoding is the Qwen3.5 model-card sampling, not greedy (greedy makes thinking models loop; see §4).

This file is written **before any trained model is scored**.

## Amendment v5

**Finalist rule (replaces §7's "best dev-slice headline"):** the RL checkpoint with the **best dev-slice MATH score** (175 items: the first 25 per MATH subject) whose MMLU-Pro history control is not more than 2 points below base. Ties: the earlier checkpoint. Reason: the training targets logical/mathematical reasoning, and MATH is the only dev-slice row large enough to show a trend (the other rows have 25 items).

**Held-out evaluation (guards against the winner's curse):** choosing the maximum of noisy dev-slice scores overstates the gain, so the finalist's reported MATH number comes from items **not used for the choice**: MATH items 26-50 per subject (175 items), scored for the finalist and for base (base already has them from its full v3 run), paired bootstrap 95% CI. The dev-slice MATH values (items 1-25) are reported next to it, labelled "used for selection".

**Disclosure:** like v4, this was decided after observing checkpoint results (dev-slice MATH so far: base 0.589, h2 steps 10-50: 0.606, 0.617, 0.640, 0.611, 0.606). It is reported as a post-hoc change. Training continued past the original cutoff; every checkpoint is benched the same way, and the rule is applied to all of them.

## Amendment v4

**BBH is removed from the headline and from the dev slice.** Headline = unweighted mean of 5 rows: MATH, GSM8K, MedQA, MMLU-Pro health, MMLU-Pro law. Negative control unchanged (MMLU-Pro history).

**Why:** the first two RL v2 checkpoints (`think-gridbranch` s10, `think-games-v3b` s10) lost 11-12 points on BBH while every other row moved by 0-8 points. All of the extra misses are replies where lm-eval's `get-answer` filter finds no answer (104-105 of 675 vs 21 for base): short direct answers without the 3-shot "So the answer is (X)" phrase. That is an answer-format artifact of training on our games' reply style, not a measured reasoning change.

**Disclosure:** this change was made after observing results, so it is a post-hoc protocol change. BBH numbers stay in every run directory and are reported separately next to the headline, with the format artifact explained. The alternative (a lenient extraction rule applied to all rows) was considered and not chosen.

## 1. Question

Does post-training Qwen3.5-9B on experience from our games improve its reasoning on **outside** benchmarks
(the far-transfer suite), beyond what the same amount of non-game fine-tuning gives, while knowledge recall
(the negative control) stays flat?

## 2. Models compared

| Row | What | Role |
|---|---|---|
| `base` | `Qwen/Qwen3.5-9B` (HF snapshot `c202236…`), no fine-tuning | reference |
| `sft-v1` | SFT v1 (optimal action sequences, h1 format) | free data point, reported, not a candidate |
| `ctrl` | SFT v2, general open reasoning data only (or the "format-only control" of FT_BENCHMARKS.md), **same token count** as `games`/`mix` | control |
| `games` | SFT v2, game data only | candidate |
| `mix` | SFT v2, general + game data | candidate |
| `rl-*` | GRPO checkpoints from the best SFT v2 checkpoint | candidates (dev slice), finalist (full suite) |

All rows share the base model, LoRA recipe (`posttrain/`), serving stack (vLLM 0.33.0) and the generation settings below.

## 3. Benchmarks (frozen list: `bench/configs/benchmarks.yaml`, version 2)

**Primary: far-transfer suite** (FT_BENCHMARKS.md). **Headline = unweighted mean accuracy over these six rows.**

| # | Benchmark | lm-eval task (0.4.13) | Setting | Items |
|---|---|---|---|---|
| 1 | Big-Bench Hard, all 27 tasks | `bbh_cot_fewshot` | 3-shot CoT | first 50 per task = 1,350 |
| 2 | MATH | `minerva_math` with `--num_fewshot 0` | 0-shot CoT | first 50 per subject = 350 |
| 3 | GSM8K | `gsm8k_cot` | 8-shot CoT | first 250 |
| 4 | MedQA-USMLE, 4 options | `medqa_4options` | 0-shot, loglikelihood multiple choice (the only form lm-eval ships) | full 1,273 |
| 5 | MMLU-Pro: health | `mmlu_pro_health` | 5-shot CoT | first 100 |
| 6 | MMLU-Pro: law | `mmlu_pro_law` | 5-shot CoT | first 100 |

**Negative control:** MMLU-Pro history (`mmlu_pro_history`, 5-shot CoT, first 100). Must not move. If it rises as much as the suite, the gain is answer formatting, not reasoning.

**Pre-declared BBH subset** (reported separately, computed from row 1's items): tracking shuffled objects, navigate, logical deduction, web of lies, temporal sequences.

**Secondary (never in the headline):** reasoning-gym `maze`, `sokoban`, `rush_hour`, `shortest_path`, `arc_1d`, `zebra_puzzles`, `knights_knaves`, 100 items each from dataset seed `20261114`, graded by the library's own `score_answer`. Our held-out `eval-v1`/`eval-v2` games are scored by the arena (`finetune-eval` sweeps, h1/h2), not here.

Metrics: the task's own primary metric, preferring the `flexible-extract` / `custom-extract` filter where a task has several (the model is not told the "The answer is" format in 0-shot settings). MedQA: `acc_norm`.

## 4. Generation settings (frozen: `bench/configs/generation.yaml`, version 1)

- vLLM 0.33.0, bf16, one A100 80 GB. Either in-process (`--model`) or the same vLLM serving the model over its OpenAI API (`--api`); our GPU servers served `arena-base` (base) and `arena-ft` (SFT v1) this way.
- Generative tasks: chat template applied, few-shot examples as earlier turns (`--fewshot_as_multiturn`), **thinking mode on** (the model's default). Graded text = everything after `</think>`.
- Sampling, Qwen3.5 model card "thinking mode, general tasks": temperature 1.0, top_p 0.95, top_k 20, min_p 0, presence_penalty 1.5, repetition_penalty 1.0. FT_BENCHMARKS.md asked for greedy; we chose model-card sampling instead because greedy decoding makes thinking models repeat until the token limit. Seeds fixed; sampling noise is covered by the CIs.
- `max_gen_toks` 8192 (thinking + answer). A reply cut off at the limit is graded as is and counted in `truncated`. Same limit for every model.
- Multiple choice (MedQA): loglikelihood of each option, no chat template, no sampling.

## 5. Statistics

- Per benchmark: mean of per-item scores, 95% percentile bootstrap CI over items (10,000 resamples, seed 20261114).
- **Paired comparison** (candidate vs reference) per benchmark: bootstrap of the mean per-item difference over the items both runs scored. A delta "excludes zero" when its 95% CI does not contain 0. Items missing on one side are dropped and counted, never imputed.
- Headline = unweighted mean over the six primary rows; headline delta = mean of the six per-benchmark deltas.
- Effects are reported **per benchmark**, never only as the headline. No multiple-comparison correction; a single significant benchmark is reported as weak evidence.
- Sanity check (FT_BENCHMARKS.md): the base model's scores should be close to its published numbers before any delta means anything. Where our settings differ from Qwen's (shots, token limit), we say so next to the base row.

## 6. Pre-registered comparisons

1. **Primary:** `games` vs `ctrl` and `mix` vs `ctrl` on the headline.
2. Secondary: each candidate vs `base` on every row; BBH subset; `sft-v1` vs `base`; reasoning-gym tier.
3. Negative control: MMLU-Pro history delta for every candidate.

**Claim rule (honesty):** we say "training on our games improved reasoning" only if a candidate beats `ctrl` on the headline **and** on at least two primary benchmarks with CIs excluding zero, **and** its MMLU-Pro history delta vs `ctrl` is not as large as its headline delta (otherwise: formatting, not reasoning). Otherwise the pitch says plainly that no transfer was shown and reports the in-domain (game) gain.

## 7. Intermediate checkpoints and the finalist (fixed before results)

- RL / intermediate checkpoints run the **dev slice**: the first 25 items of every (sub)task of the primary suite and the negative control (~975 items; `python -m bench run --dev-slice`). Same items for every checkpoint. FT_BENCHMARKS.md asked for a random 1,000-item subsample; lm-eval's `--limit` takes the first N, which is fixed and identical across models.
- **Finalist** = the checkpoint with the best dev-slice headline whose MMLU-Pro history drop vs `base` is ≤ 2 points. Ties: the earlier checkpoint.
- `base`, `ctrl` and the finalist run the **v3 suite** (the fixed subsample in §3) once (FT_BENCHMARKS.md: "if time is short, run the full suite on base, control and the final model"). `games`/`mix` run it too if GPU time allows. Dev-slice items are a subset of the full sets, so final numbers are partly in-sample for the choice; this is stated next to the result.

## 8. How to run

```bash
# on the GPU box (/srv/bench, venv with the gpu extras)
python -m bench run --api http://127.0.0.1:8001/v1 --served-name arena-base --tokenizer Qwen/Qwen3.5-9B --out data/derived/bench/base
python -m bench run --api http://127.0.0.1:8000/v1 --served-name arena-ft --tokenizer Qwen/Qwen3.5-9B --out data/derived/bench/sft-v1
CUDA_VISIBLE_DEVICES=1 python -m bench run --model Qwen/Qwen3.5-9B --lora <adapter dir> --out data/derived/bench/sft-mix
CUDA_VISIBLE_DEVICES=1 python -m bench run --model <merged dir> --dev-slice --out data/derived/bench/rl-step-200
# anywhere
python -m bench compare --ref data/derived/bench/ctrl --cand data/derived/bench/sft-mix --out data/derived/bench/delta-mix-vs-ctrl.json
```
`compare` warns when two runs used a different config hash (different list, settings or slice): such deltas are not valid.
