# A3 -> A2: GPU split on the A100 box + two benchmark lists (Sat 17:50)

**GPU collision (resolved):** your `bench run --name base-dev` (started ~17:12, CUDA 1) and A3's untuned-Qwen server
for the fine-tune comparison (`vllm serve ... --served-model-name arena-base`, port 8001) both took **GPU 1**; your
vLLM shut down at 17:17 (and A3's first launches failed the same way). From now on:
- **GPU 0: yours** (A3 stopped the fine-tuned model server at 17:50; the fine-tuned eval is finished). Use
  `CUDA_VISIBLE_DEVICES=0` for `bench run`.
- **GPU 1: A3** (port 8001, untuned Qwen3.5-9B for the h1 fine-tune comparison, until ~21:30; then A3 needs it for
  SFT v2 training). Please don't start anything on GPU 1.
- Your `bench run` process (pid 34553, started 17:12) is still alive with no GPU; A3 has not touched it.

**Two benchmark lists:** Daniel (human) added `FT_BENCHMARKS.md` at 17:24 ("for A3"): BBH all 27 (3-shot CoT), MATH
(5,000, 0-shot CoT), GSM8K (8-shot CoT), MedQA-USMLE 4-option, MMLU-Pro health and law (5-shot), headline = mean of
those six; MMLU-Pro history as a negative control; greedy decoding; 1,000-item subsample for intermediate checkpoints.
It differs from `bench/PROTOCOL.md` v1 draft (reasoning-gym + BBH logic subsets + MuSR, sampling per the model card).
A3 has asked the humans which list is final (PROTOCOL sign-off is due 19:00); please hold the base-dev run on the old
list until they answer. A3's compute note: ~16k items per model; with thinking on at 8k tokens that is roughly 2-4 GPU
hours per model on one A100, so greedy + a tighter cap (or thinking off) is needed to bench 4-5 models before 05:00.

**Human decision (Sat 17:55, ignacio in chat with A3): Daniel's `FT_BENCHMARKS.md` is the final benchmark list.**
Please make `bench/configs/benchmarks.yaml` + `PROTOCOL.md` match it (primary six with Daniel's shot counts, MMLU-Pro
history as the negative control, the five pre-declared BBH tasks reported separately, greedy decoding, headline =
unweighted mean over rows 1-6, fixed-seed 1,000-item subsample for intermediate checkpoints) and look up the exact
lm-eval task names. A3's asks for the protocol: (1) keep thinking-mode/length settings identical for every row and
choose a cap that fits ~5 models on one A100 before 05:00 (the fine-tune rows are trained on short h1 replies, so a
cap that truncates long thinking would hit the base model hardest: please report `truncated` per benchmark);
(2) rows: `base`, `sft-v1` (merged weights at `/root/ckpt/merged` on the box), `ctrl`, `games`, `mix`, final.
A3 signs off the training side once the list is in.
