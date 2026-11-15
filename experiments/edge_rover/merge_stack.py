"""Merge a LoRA stack (base -> SFT LoRA -> RL LoRA) into one checkpoint vLLM can serve.

GRPO adapters were trained on top of the merged games-SFT model (grpo_args.json: sft_lora=/vol/sft/games),
so the stack is applied in the same order.

    python merge_stack.py --base Qwen/Qwen3.5-9B --lora /root/ckpt/games/lora --lora /root/ckpt/grpo-1/step-25 \
        --out /root/ckpt/merged-grpo1
"""
from __future__ import annotations

import argparse
import sys


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--lora", action="append", required=True, help="applied and merged in the given order")
    ap.add_argument("--out", required=True)
    ap.add_argument("--train-sft", default="/root/train_sft.py", help="for its load_model (text-only Qwen3.5)")
    a = ap.parse_args()

    import importlib.util
    import torch
    from peft import PeftModel
    from transformers import AutoTokenizer

    spec = importlib.util.spec_from_file_location("train_sft", a.train_sft)
    ts = importlib.util.module_from_spec(spec)
    sys.modules["train_sft"] = ts
    spec.loader.exec_module(ts)
    m = ts.load_model(a.base, torch_dtype=torch.bfloat16)
    for path in a.lora:
        m = PeftModel.from_pretrained(m, path).merge_and_unload()
        print("merged", path, flush=True)
    m.save_pretrained(a.out)
    AutoTokenizer.from_pretrained(a.lora[0]).save_pretrained(a.out)
    print("saved", a.out)


if __name__ == "__main__":
    main()
