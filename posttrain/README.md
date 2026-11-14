# posttrain (A3)

PLAN.md phase 2 §3.3. Status and GPU log: `coordination/status/A3.md`.

| Run | Data | Status |
|---|---|---|
| sft-v1 (`arena/finetune/`) | 4k h1 optimal-play turns, 69/31 optimal/recovery | done: val loss 1.60 -> 0.054; eval-v1 h1 result in A3 status |
| sft-ctrl | general reasoning SFT only | waiting for data choice (PROTOCOL.md) |
| sft-games | A1 data v2 + aux tasks | waiting for A1-20/21 |
| sft-mix | general + games | waiting |
| grpo-1 | A1-22 rewards, `grpo.py` + `configs/grpo-1.yaml` | code ready, CPU smoke test passed; waiting for best SFT v2 |

Compute: one Verda 2x A100 80 GB box (`root@95.216.229.250`, ~$4.77/h), the only GPU instance available.

## grpo-1: RL with verifiable rewards (A3-25)

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

CPU smoke test (proves loop, reward plumbing, ref-adapter KL, saving; 2-3 steps, tiny model):
```bash
PYTHONPATH=engine/src python -m engine tasks --task all --n 4 --seed 0 --out /tmp/t.jsonl
cd posttrain/src && PYTHONPATH=../../engine/src python -m posttrain.grpo --base trl-internal-testing/tiny-Qwen3ForCausalLM \
  --tasks /tmp/t.jsonl --out /tmp/g --steps 3 --save-every 2 --per-device-batch 4 --grad-accum 2 \
  --num-generations 4 --max-completion 24 --fake-reward --no-mask-truncated --lr 1e-2
```
