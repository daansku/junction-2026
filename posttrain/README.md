# posttrain (A3)

PLAN.md phase 2 §3.3. Status and GPU log: `coordination/status/A3.md`.

| Run | Data | Status |
|---|---|---|
| sft-v1 (`arena/finetune/`) | 4k h1 optimal-play turns, 69/31 optimal/recovery | done: val loss 1.60 -> 0.054; eval-v1 h1 result in A3 status |
| sft-ctrl | general reasoning SFT only | waiting for data choice (PROTOCOL.md) |
| sft-games | A1 data v2 + aux tasks | waiting for A1-20/21 |
| sft-mix | general + games | waiting |
| grpo-1 | A1-22 rewards | waiting |

Compute: one Verda 2x A100 80 GB box (`root@95.216.229.250`, ~$4.77/h), the only GPU instance available.
