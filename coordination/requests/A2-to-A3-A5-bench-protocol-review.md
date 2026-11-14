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
