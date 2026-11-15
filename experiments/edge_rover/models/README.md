# Models trained on our games: Qwen3.5-4B + episodic RL (expert iteration)

Three LoRA adapters (r=16, alpha=32, every linear layer of the language model) on top of **`Qwen/Qwen3.5-4B`**.
Each round: the current model plays levels of our train games (train-v1, never eval games) with thinking on, and is
rewarded only for solving a level. A fresh LoRA on the base is then trained on the unique winning episodes so far
(its own reasoning + moves). Full method and numbers: `../README.md`.

| Adapter | Trained on | Rover-lite, hidden controls (100 paired missions) | Held-out MATH (A2's test, 175 items) |
|---|---|---|---|
| (base `Qwen/Qwen3.5-4B`) | - | 41/100 | 0.623 |
| `qwen3.5-4b-ourgames-round1-lora` | 32 wins (30 levels), 498 turns | 50/100 (p=0.14) | - |
| **`qwen3.5-4b-ourgames-round2-lora`** (recommended) | 43 unique levels, 992 turns | **54/100 (p=0.019)** | **0.680** (selection half 0.680, p=0.004) |
| `qwen3.5-4b-ourgames-round3-lora` | 56 unique levels, 1,372 turns | 51/100 (p=0.099) | 0.686 (selection half 0.651) |

- **Checkpoint choice:** round 2 is the reported checkpoint. It is chosen on MATH's selection half (A2's protocol) and is also the best rover checkpoint.
- **p-values:** exact McNemar, paired vs base.
- **JSON repair:** every rover number above uses it (0 JSON failures).

## Rebuild the full model and run it

```bash
python ../merge_stack.py --base Qwen/Qwen3.5-4B --lora qwen3.5-4b-ourgames-round2-lora \
    --out ./merged-round2 --train-sft ../../../arena/finetune/train_sft.py   # ~1 min, ~8 GB
ROVER_LITE=1 python ../run_eval2.py --think --repair --max-tokens 512 --model ./merged-round2 \
    --name round2 --seeds 5000-5099 --controls hidden --outdir results
```

The adapters also load directly with PEFT (`PeftModel.from_pretrained(base, "<adapter dir>")`). They were trained with
transformers 5.20.2 and PEFT 0.21.3.

## Training settings (identical for all rounds)

| Setting | Value |
|---|---|
| Learning rate | 1e-4, AdamW |
| Batch | 1 x grad-accum 4 |
| Epochs | 1 |
| Max length | 4096 |
| Seed | 0 |
| LoRA | r=16, alpha=32, dropout 0.05 |
| Labels | the model's own `<think>` reasoning + JSON answer |

- **Data rules:**
  - Only winning episodes are kept.
  - Each (game, level) contributes at most one win: the best shot, from the first round that won it.
  - Rounds 2-3 keep only wins with reward >= 0.4, and rule levels count 3x.
- **Training data:** `../data/` (`train-rft*.jsonl.gz` + manifests).

Weights are stored with Git LFS (`git lfs pull` after cloning).
