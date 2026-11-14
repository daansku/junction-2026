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
