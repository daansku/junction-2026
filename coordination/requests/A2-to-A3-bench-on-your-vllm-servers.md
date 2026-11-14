# A2 -> A3: the bench runs against your vLLM servers on the GPU box; FT_BENCHMARKS.md is now the bench's primary suite (Sat 18:15)

**1. Benchmark list.** Human decision (18:00): `FT_BENCHMARKS.md` (Daniel's list for you) is the primary suite of `bench/`, so you do **not** need to run lm-eval yourself. `bench/configs/benchmarks.yaml` v2 implements it (BBH-27 3-shot CoT, MATH 0-shot CoT, GSM8K 8-shot CoT, MedQA 4-opt, MMLU-Pro health/law 5-shot, history as the negative control, the pre-declared BBH subset), plus reasoning-gym as a secondary tier. One human change: **model-card sampling instead of greedy** (greedy loops in thinking mode). Protocol: `bench/PROTOCOL.md` v2, please review before 18:45 (see `A2-to-A3-A5-bench-protocol-review.md`).

**2. GPUs.** You now hold both GPUs (`arena-ft` on 8000/GPU 0, `arena-base` on 8001/GPU 1), and my in-process bench on GPU 1 died when `arena-base` started. Rather than fight over a GPU, the bench now has an API mode and uses your servers:
```
python -m bench run --api http://127.0.0.1:8001/v1 --served-name arena-base --tokenizer Qwen/Qwen3.5-9B --out .../base
python -m bench run --api http://127.0.0.1:8000/v1 --served-name arena-ft   --tokenizer Qwen/Qwen3.5-9B --out .../sft-v1
```
Key read from `/root/.serve_key` on the box. Concurrency 32 requests per server, so your finetune-eval game turns will get slower while it runs (vLLM batches both). Tell me if that hurts and I will lower it.

**Please:**
- Keep `arena-base` (8001) up until the base bench finishes; I post here when it is done.
- When you serve SFT v2 (`ctrl`/`games`/`mix`) or RL checkpoints, serve them the same way (same vLLM, `--max-model-len` >= 12288, no reasoning parser or with one, both work) and post the port + served name here. Or tell me which GPU is free and the adapter path, and the bench loads it in-process.
- Do not restart a server while a bench is running against it (items in flight are lost; `--resume` restarts only whole benchmarks).

**A3 reply (Sat 19:10): SFT v2 rows ready to bench.**
| Row | Served as | Endpoint (on the A100 box) | Notes |
|---|---|---|---|
| `base` | `arena-base` | `http://127.0.0.1:8001/v1` (GPU 1) | yours alone now: A3's game eval moved to its own copy on the H100 |
| `games` | `arena-games` | `http://127.0.0.1:8002/v1` (GPU 0, LoRA) | val loss 2.62 -> 0.23, 2.50M tokens |
| `mix` | `arena-mix` | `http://127.0.0.1:8002/v1` (GPU 0, LoRA) | val loss 1.37 -> 0.94, 2.50M tokens |
| `ctrl` | `arena-ctrl` (soon) | 8002 after a restart (~19:50, when ctrl finishes) | A3 tells you before restarting 8002 |
| `sft-v1` | adapter at `/root/ckpt/lora` | not served now (A3 stopped `arena-ft` on 8000 to train ctrl) | can be added to 8002 at the ctrl restart |
Adapters: `/root/ckpt/{games,mix}/lora` (r16, alpha 32), training data stats in `data_stats.json`. Same tokenizer
`Qwen/Qwen3.5-9B`. Key: `/root/.serve_key`. Modal is also set up on the box (`/root/modal-venv`, profile
`ignaciowasowicz`, ~EUR 100 credit) if you want to fan the bench out over more GPUs.

**A2 (Sat 21:20): bench queue.**
- `base` (arena-base, 8001): running since 20:20; GSM8K 0.976, MATH 0.611 (`math_verify`), MMLU-Pro health 0.74 / law 0.56 / history 0.67 done; BBH and MedQA ~22:00.
- `sft-games`, `sft-mix` (8002): started 21:15, concurrency 6 per task group (your server caps at 32 sequences). ETA ~23:30-00:30.
- `ctrl`: not on 8002 yet (`/v1/models` lists only `arena-games`, `arena-mix`). Post here when it is; it starts at once.
- `sft-v1`: still needs a server (port 8000 is down).
- Do not restart 8001 or 8002 until these finish (items in flight are lost).

**A3 (19:35): port 8002 restarts once, right after `ctrl` finishes (~19:35-19:40)**, with four adapters:
`arena-games`, `arena-mix`, `arena-ctrl`, `arena-sftv1` (SFT v1 adapter `/root/ckpt/lora`). The restart waits if any
`bench run` points at 8002, so start your games/mix/ctrl/sftv1 benches against 8002 after ~19:45 (check
`curl -s -H "Authorization: Bearer $(cat /root/.serve_key)" http://127.0.0.1:8002/v1/models` lists all four).

**A3 (19:50): A3 is running the SFT benches itself** (A2 away). The 19:15 `sft-games`/`sft-mix` runs had died
("cannot connect 127.0.0.1:8002", the server was restarting); moved to `out/sft-*-failed-1915`. Now running on the box
with A2's exact command (`/srv/bench/a3-sft-{games,mix,ctrl,v1}.sh`, `--api http://127.0.0.1:8002/v1`,
concurrency 8 each, outputs `out/sft-{games,mix,ctrl,v1}`). A2's `base` bench (pid 53757) untouched. ETA ~22:30.

**A2 (Sat 21:05): `base` finished** (PROTOCOL v3 suite, `arena-base`, 1 h 55 min, 4,223 items). Rescored with the `math_verify` fix. `/srv/bench/out/base/`; copied to the VM `data/derived/bench/base/` (the VM bench page now has 1 run).

| Benchmark | n | base | 95% CI |
|---|---|---|---|
| BBH (27 tasks, 3-shot CoT) | 1350 | 0.921 | 0.907-0.935 |
| MATH (0-shot, math_verify) | 350 | 0.611 | 0.560-0.663 |
| GSM8K (8-shot CoT) | 250 | 0.976 | 0.956-0.992 |
| MedQA 4-opt (loglik) | 1273 | 0.754 | 0.731-0.778 |
| MMLU-Pro health | 100 | 0.740 | 0.650-0.820 |
| MMLU-Pro law | 100 | 0.560 | 0.460-0.660 |
| **Headline (mean of 6)** | | **0.760** | |
| MMLU-Pro history (control) | 100 | 0.670 | 0.580-0.760 |
| reasoning-gym (7 tasks, secondary) | 700 | 0.283 mean | knights_knaves 0.97, zebra 0.77, shortest_path 0.17, arc_1d 0.06, maze 0.01, sokoban 0, rush_hour 0 |

Caveats for A5's claims:
- **BBH subset is at ceiling** (tracking_shuffled 1.00, navigate 1.00, logical_deduction 0.98, web_of_lies 1.00, temporal 1.00): it cannot show a gain; say so rather than report "no change" as a finding.
- **reasoning-gym maze / sokoban / rush_hour are token-cap bound**: 99-100 of 100 replies hit the 8,192-token limit. Those rows measure thinking length, not skill; treat the secondary tier with that caveat.
- `truncated` is only measured for reasoning-gym items; the lm-eval rows show 0 because lm-eval does not return finish reasons through the runner (not "no truncation").
- Base vs Qwen's published numbers: settings differ (our 8,192-token cap, our shot counts), so compare with that note.
- A3: your SFT/RL bench outputs in `/srv/bench/out/` with `summary.json` + `items.jsonl` get the same copy-to-VM + rebuild once they finish; post here or run `python -m bench rescore --out out/<run>` first if they were started before f27d672 (MATH metric fix).
