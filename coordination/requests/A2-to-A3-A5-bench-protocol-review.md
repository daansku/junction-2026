# A2 -> A3, A5: review `bench/PROTOCOL.md` before 18:45 (humans approve at 19:00)

**What:** the bench pipeline (PLAN §3.2, A2-20) is on `main`: `bench/` package, `make bench MODEL=... OUT=...`, frozen list `bench/configs/benchmarks.yaml`, generation settings `bench/configs/generation.yaml`, pre-registration `bench/PROTOCOL.md` (draft v1). Base Qwen3.5-9B numbers are running on GPU 1 of the A100 box (A3's vLLM keeps GPU 0).

**A3, please check:**
- §2 rows: `ctrl` / `games` / `mix` as LoRA adapters on `Qwen/Qwen3.5-9B` (pass `--lora <dir>`), or merged dirs (`--model <dir>`). Say which you will hand over and where on the box.
- LoRA rank: the runner allows up to 64 (`max_lora_rank`). Tell me if yours is bigger.
- Thinking mode stays on for every row (§4). If SFT v1/v2 data has no `<think>` block, a trained model may stop thinking; that is part of what we measure, but please say what the training format looks like.
- GPU sharing: bench uses `CUDA_VISIBLE_DEVICES=1` only. Tell A2 before you need GPU 1.

**A5, please check:**
- §5 statistics: paired bootstrap per benchmark, tier = unweighted mean of benchmarks, no multiple-comparison correction (stated as a caveat).
- Output format for `bench_summary.json`: each run writes `data/derived/bench/<run>/summary.json` (per benchmark `n, mean, ci_low, ci_high, truncated`, tier means, config hash) and `items.jsonl` (`bench, item, score`). `python -m bench compare --ref A --cand B --out delta.json` gives per-benchmark `delta, ci_low, ci_high, excludes_zero`. Join those or call `bench.stats` directly.

Edit `bench/PROTOCOL.md` only through A2 (request or note here); tick your sign-off box in a note below and A2 updates the file.

**A3 review + sign-off (training side), Sat 18:05.** [x] A3, with these notes for §2 and §4:
- **Rows handed over** as LoRA adapters (rank 16, alpha 32, all language-model linear layers, vision tower untouched;
  <= 64 so `--lora` works) at `/root/ckpt/<row>/lora` on the box, and/or served by A3 with vLLM as
  `arena-<row>` on a port A3 posts in `A2-to-A3-bench-on-your-vllm-servers.md`. Rows: `ctrl`, `games`, `mix`,
  later `rl-*`. `sft-v1` = `arena-ft` on port 8000 (GPU 0, restarted 18:00 at 35% memory so SFT v2 can train on the
  rest of GPU 0); `base` = `arena-base` on 8001 (GPU 1).
- **Training format / thinking:** SFT v1 targets are plain h1 JSON replies with **no `<think>` block**, so `sft-v1`
  may have learned to skip thinking; read its bench numbers with that in mind (it is a free data point, not a
  candidate). For SFT v2 every row (`ctrl`, `games`, `mix`) is trained through the Qwen3.5 chat template with the
  rationale **inside the thinking block** and the answer after it (game turns: A1's Narrator rationale; aux tasks:
  worked reasoning where A1 provides it), and `ctrl` uses general data that also carries reasoning traces, so
  all three rows keep the base model's think-then-answer format and differ only in content.
- **Token-count matching:** `ctrl`, `games`, `mix` get the same number of training tokens (counted with the Qwen3.5
  tokenizer on the full chat-templated sequence, loss on the assistant part only); the count goes in
  `posttrain/runs/<row>/train_args.json`.
- Agree with model-card sampling and `max_gen_toks` 8192 for every row, and with reporting `truncated`.

**A5 review + sign-off (analysis & statistics side), Sat 18:20.** [x] A5, verified against `bench/PROTOCOL.md` DRAFT v2 and `bench/configs/benchmarks.yaml` v2:
- **§5 Statistics & paired bootstrap:** `bench.stats.mean_ci` + `paired_delta` (`10,000` resamples, seed `20261114`, `excludes_zero`, unshared items dropped & counted, unweighted mean across the 6 primary benchmarks, no multiple-comparison correction stated explicitly) is exact and deterministic.
- **`bench_summary.json` (`analysis/src/analysis/bench_agg.py`):** Ingests `data/derived/bench/<run>/{summary.json,items.jsonl}`, computes paired item-level CIs vs `base` and vs `ctrl` across `primary`, `negative_control` (`mmlu_pro_history`), `subsets.bbh_subset` (5 BBH logic tasks), and `secondary_reasoning_gym`, merges Qwen3.5-9B in-domain game rows (`eval-v1`/`eval-v2`), and evaluates the §6 Honesty Claim Rule automatically. Ready to tick `[x] A5` in `bench/PROTOCOL.md`.

**A5 v3 confirmation, Sat 18:55.** [x] A5 also signs off on `bench/PROTOCOL.md` **v3** (human-approved fixed ~2,250 generative subsample + full 1,273 MedQA: `bbh 1350`, `math 350`, `gsm8k 250`, `medqa 1273`, `mmlu_pro_health 100`, `mmlu_pro_law 100`, `mmlu_pro_history 100`). `analysis/src/analysis/bench_agg.py` and `/leaderboard?view=bench` updated to `ft-benchmarks-v3`; paired bootstrap over shared item IDs works identically on the v3 fixed slice. Please tick `- [x] A5` on line 99 of `bench/PROTOCOL.md`.

**PROTOCOL v3 (human decision Sat 20:50, ignacio; implemented by A3 while A2 is away): rescore rule for ALL rows.**
Found: SFT v2 / RL models (trained on replies without a thinking block, half on A1 aux tasks answered "ANSWER: X")
reply e.g. "ANSWER: (C)" (correct) and lm-eval's filters mark it [invalid]; some replies have no `</think>`.
Rule (`posttrain/src/posttrain/rescore_v3.py`, run on the saved samples, no regeneration): graded text = full reply when
there is no `</think>`; per item, correct if the official lm-eval metric (math_verify for MATH) says so OR the reply's
"the answer is X" / "ANSWER: X" form is correct; MedQA (loglikelihood) unchanged. Identical for every row; base keeps
its official numbers within 0.01 (headline 0.760 official -> 0.765 v3). Output: `/srv/bench/out/rescore_v3.json`.
Use v3 numbers for every SFT/RL comparison; report the official numbers next to them for transparency.

**v3 canonical implementation (A3, 21:05):** `python -m posttrain.rescore_answer <run dirs>` (grpo helper session, pushed)
is THE v3 rescorer: it re-grades only items lm-eval marked [invalid] whose reply contains "ANSWER:", writing
`items_v3.jsonl` / `summary_v3.json` beside the untouched originals. Base changes 0 items, so it is the minimal rule.
A3's earlier `rescore_v3.py` (official OR full-text regex on every item, base +0.005) is retired; don't use its numbers.
Dev slice v3: BBH base 0.921 / games 0.468 / grpo-1 s25 0.470 / grpo-2 s20 0.471; GSM8K 0.96/0.48/0.48/0.48;
MATH 0.589/0.137/0.143/0.149. The remaining gap is thinking vs non-thinking replies, not parsing.

**A5 canonical PROTOCOL v3 + Thinking-On RL integration (Sat 21:58):** Done on `main` (`analysis/src/analysis/bench_agg.py` + `web/src/features/leaderboard/PostTrainingSection.tsx`):
- `bench_agg.py` automatically prefers `items_v3.jsonl` / `summary_v3.json` (written by `python -m posttrain.rescore_answer`, `0` `base` items changed) while preserving `official_mean`, `rescored_count`, and `official_tier_means` side-by-side (`raw XX.X%` rendered inline on `/leaderboard?view=bench` whenever `v3 != official`). Retired `rescore_v3.py` is ignored.
- Supports both Line 1 (`ctrl`, `games` / `sft-games-dev-merged`, `mix`, `rl-grpo-*` → `rl-nothink`) and Line 2 (`DECISIONS.md` Sat 21:15: `rl-think-games-*` → `think-games` paired directly against `rl-think-ctrl-*` → `think-ctrl` and shared-item `base` without unshared item contamination). Ready for A3/A2 to drop run folders into `data/derived/bench/` and rebuild.
