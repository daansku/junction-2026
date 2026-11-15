# posttrain (A3)

Post-training on our games: SFT and GRPO on Qwen3.5-9B, scored on `bench/` (protocol: `bench/PROTOCOL.md`).

| Run | Data | Status |
|---|---|---|
| sft-v1 (`arena/finetune/`) | 4k h1 optimal-play turns, 69/31 optimal/recovery | done: val loss 1.60 -> 0.054 |
| sft-ctrl | general reasoning SFT only | waiting for data choice (PROTOCOL.md) |
| sft-games | A1 data v2 + aux tasks | waiting for A1-20/21 |
| sft-mix | general + games | waiting |
| grpo-1 | 70% A1 `game_turn` (h1 map turns) + 30% aux (blocked_moves, full_plan, rule_effect), 4,290 prompts; start = SFT v2 `games` | running on a Modal H100 (`modal_grpo.py`, volume `junction-grpo`), 150 steps, step-<k> every 25 |

Compute: one Verda 2x A100 80 GB box (~$4.77/h), the only GPU instance available.

## grpo-1: RL with verifiable rewards (A3-25)

**Start checkpoint = SFT v2 `games`, an A3 decision taken Sat 19:35 before any bench result, to save ~3 h** (the
`games` and `mix` val losses are on different data and not comparable; `games` is trained on the h1 map-turn
distribution that `game_turn` RL optimises). Recorded in the run's `grpo_args.json` (`note`).

`src/posttrain/grpo.py` + `configs/grpo-1.yaml`. TRL 1.18 `GRPOTrainer` (pinned in the `gpu` extra): the SFT v2
LoRA is loaded as a trainable `PeftModel`; TRL copies it to a frozen `ref` adapter, so `beta` is the KL to the
SFT policy. G=8 completions per prompt, clipped ratio (0.2 / 0.28 clip-higher), DAPO token loss, truncated replies
masked. Reward = `engine.tasks.reward` (A1-22, exact match / plan efficiency, no partial credit to farm).
Generation: vLLM colocate (one engine per GPU, LoRA merged and pushed every step), Qwen chat template,
`enable_thinking: false` (SFT v2 format), max 1024 new tokens.

```bash
# on the GPU box, repo at /root/junction-2026
uv pip install -e engine -e "posttrain[gpu]"
python -m engine tasks --task all --n 1500 --seed 0 --out /root/tasks/rl-s0.jsonl   # seed 1 = bench dev slice
accelerate launch --num_processes 2 -m posttrain.grpo --config posttrain/configs/grpo-1.yaml \
    --sft-lora /root/ckpt/<best-sft-v2> --tasks /root/tasks/rl-s0.jsonl --out /root/ckpt/grpo-1
# each save: python -m bench run --model Qwen/Qwen3.5-9B --lora /root/ckpt/grpo-1/step-<k> --dev-slice ...
```

Outputs in `--out`: `step-<k>/` (policy adapter only + tokenizer + `grpo_meta.json`), `log.jsonl` (per step:
`reward`, `reward_task/<task>`, `answer_rate`, `kl`, `completions/mean_length`, `completions/clipped_ratio`,
`frac_reward_zero_std`), `grpo_args.json`. Watch: `frac_reward_zero_std` near 1 = no signal (all 8 replies
score the same; drop or rebalance that task with `--task-filter`); `kl` > 0.1 = drifting, lower `lr`.
If OOM: `--per-device-batch 4 --grad-accum 8` (same batch) or `vllm_sleep: true`. Plan B if vLLM + Qwen3.5
weight sync breaks: `--no-vllm` (HF generate, several times slower).

**One GPU (H100, or any free 80 GB card): self-serve, no hand-offs.**
```bash
SFT_LORA=/root/ckpt/games/lora GPU=0 bash posttrain/run_grpo.sh          # configs/grpo-1-h100.yaml, own /root/rl-venv
GPU=1 RUN=/root/ckpt/grpo-1 EVERY=50 BASE_RUN=<base dev-slice run dir>   nohup bash posttrain/tools/bench_watch.sh > /root/bench-watch.log 2>&1 &   # benches step-50/100/150 + final itself
```
`run_grpo.sh` refuses a GPU with < 70 GB free (stop the vLLM server on it first). `bench_watch.sh` needs a whole
GPU (bench's vLLM takes 88%) and a python with `bench[gpu]` (`BENCH_PY`); newest unbenched checkpoint first.
Prompts over `max_prompt_tokens` (3072) are dropped: `rule_effect` has 12k-token outliers (~3% of all prompts).

## RL v2: thinking ON (think-games, think-ctrl), human-approved Sat 20:20

grpo-1/grpo-2 (thinking off, from the no-think SFT) were stopped at 20:52: they teach answering without reasoning.
v2 starts from **base Qwen3.5-9B + a fresh LoRA** (r16, alpha 32, language-model linears; no SFT adapter) with
`enable_thinking: true` and up to 3,072 completion tokens (`configs/grpo-think.yaml`). **Reward = verifier on the text
after the last `</think>` only; a reply that never closes `</think>` (or is truncated) scores 0** (`grpo.make_reward`
decodes the raw completion ids, so TRL's message parsing cannot hide an unclosed thinking block). Logged per step:
reward, per-task reward, `think_closed_rate`, `completions/mean_length`, `completions/clipped_ratio`, KL.

| Run | Data (1,200 prompts) | Reward |
|---|---|---|
| `think-games` | 70% A1 `game_turn` (seed 3, h1 JSON after the thinking block) + 30% aux (blocked_moves, full_plan, rule_effect; seed 3) | `engine.tasks.reward` |
| `think-ctrl` | reasoning-gym knights_knaves, zebra_puzzles, shortest_path, maze, 300 each, seed 7 (`posttrain.rg_tasks`) | reasoning-gym `score_answer` |

**think-ctrl touches the bench's SECONDARY reasoning-gym tier (near transfer: those datasets are in the bench, drawn
there with seed 20261114, here with seed 7, so no item overlap), not the primary FT_BENCHMARKS suite.** It is the
"generic puzzles instead of our games" control for the primary-suite comparison.

Modal: `GRPO_TIMEOUT_H=6.5 modal run --detach posttrain/modal_grpo.py --sft none --config grpo-think.yaml ...`, one H100
each, checkpoint every 15 steps, each benched (merged, thinking-on bench settings) and rescored with
`posttrain.rescore_answer`.

CPU smoke test (proves loop, reward plumbing, ref-adapter KL, saving; 2-3 steps, tiny model):
```bash
PYTHONPATH=engine/src python -m engine tasks --task all --n 4 --seed 0 --out /tmp/t.jsonl
cd posttrain/src && PYTHONPATH=../../engine/src python -m posttrain.grpo --base trl-internal-testing/tiny-Qwen3ForCausalLM \
  --tasks /tmp/t.jsonl --out /tmp/g --steps 3 --save-every 2 --per-device-batch 4 --grad-accum 2 \
  --num-generations 4 --max-completion 24 --fake-reward --no-mask-truncated --lr 1e-2
```
