"""LoRA SFT of a small open chat model on arena dataset jsonl (A3-11).

Plain transformers + peft loop (no TRL) so trainer API drift can't bite at 3am. Loss only on the
assistant reply tokens. Runs on any single GPU box: a Verda instance, or inside a Modal function.

    pip install "torch" "transformers>=4.44" "peft>=0.12" accelerate
    python arena/finetune/train_sft.py --base <hf-model-id> --data sft/train-v1.jsonl --out ckpt/sb-lora \
        --epochs 1 --lr 2e-4 --max-len 2048
    # merge for serving:
    python arena/finetune/train_sft.py --merge --base <hf-model-id> --out ckpt/sb-lora --merged ckpt/sb-merged
    # serve OpenAI-compatible, then register in models.yaml as provider verda/modal, tier finetuned:
    vllm serve ckpt/sb-merged --served-model-name arena-ft --max-model-len 4096

Pick --base from the Hugging Face hub at run time (small instruct model with a chat template);
record the exact id in models.yaml `params`/`link`. STATUS: untested on GPU from this machine.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path


def load_examples(path: str, limit: int | None = None) -> list[list[dict]]:
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            out.append(json.loads(line)["messages"])
            if limit and len(out) >= limit:
                break
    return out


def encode(tok, messages: list[dict], max_len: int):
    """input_ids + labels with -100 everywhere except the assistant reply."""
    prompt_ids = tok.apply_chat_template(messages[:-1], add_generation_prompt=True, tokenize=True)
    full_ids = tok.apply_chat_template(messages, tokenize=True)
    if full_ids[: len(prompt_ids)] != prompt_ids:  # template quirk: fall back to suffix match
        reply_ids = tok(messages[-1]["content"], add_special_tokens=False)["input_ids"]
        full_ids = prompt_ids + reply_ids + [tok.eos_token_id]
    labels = [-100] * len(prompt_ids) + full_ids[len(prompt_ids):]
    if len(full_ids) > max_len:  # keep the end: the reply must survive truncation
        full_ids, labels = full_ids[-max_len:], labels[-max_len:]
    return full_ids, labels


def load_model(base: str, **kw):
    """Text-only models load as CausalLM; vision-language ones (e.g. Qwen3.5, `...ForConditionalGeneration`)
    load with the image-text class. We train on text only either way."""
    from transformers import AutoModelForCausalLM
    try:
        return AutoModelForCausalLM.from_pretrained(base, **kw)
    except (ValueError, KeyError):
        from transformers import AutoModelForImageTextToText
        return AutoModelForImageTextToText.from_pretrained(base, **kw)


def lora_targets(model) -> list[str]:
    """Every Linear in the language model; never the vision tower or lm_head."""
    import torch
    skip = ("visual", "vision", "lm_head", "multi_modal_projector", "mm_projector")
    return [n for n, m in model.named_modules()
            if isinstance(m, torch.nn.Linear) and not any(k in n for k in skip)]


def train(a):
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoTokenizer, get_cosine_schedule_with_warmup

    import os
    world = int(os.environ.get("WORLD_SIZE", "1"))  # >1 when launched with torchrun: one process per GPU (DDP)
    rank = int(os.environ.get("RANK", "0"))
    local = int(os.environ.get("LOCAL_RANK", "0"))
    if world > 1:
        import torch.distributed as dist
        dist.init_process_group("nccl")
        torch.cuda.set_device(local)
    main = rank == 0
    log = print if main else (lambda *_, **__: None)

    torch.manual_seed(a.seed)
    random.seed(a.seed)  # same seed everywhere: every rank shuffles identically, then takes its shard
    tok = AutoTokenizer.from_pretrained(a.base)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    model = load_model(a.base, torch_dtype=torch.bfloat16, device_map={"": local} if world > 1 else "auto")
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    model = get_peft_model(model, LoraConfig(r=a.lora_r, lora_alpha=2 * a.lora_r, lora_dropout=0.05,
                                             target_modules=lora_targets(model), task_type="CAUSAL_LM"))
    if main:
        model.print_trainable_parameters()
    core = model  # unwrapped: used for eval and saving
    if world > 1:
        from torch.nn.parallel import DistributedDataParallel as DDP
        model = DDP(model, device_ids=[local], broadcast_buffers=False)

    data = [encode(tok, m, a.max_len) for m in load_examples(a.data, a.limit)]
    random.shuffle(data)
    n_val = max(1, len(data) // 50)
    val, data = data[:n_val], data[n_val:]
    per_step = a.batch * a.grad_accum * world
    data = data[: len(data) // per_step * per_step]  # equal micro-batch count on every rank (DDP would hang)
    steps_per_epoch = len(data) // per_step
    total = steps_per_epoch * a.epochs
    opt = torch.optim.AdamW([p for p in core.parameters() if p.requires_grad], lr=a.lr, weight_decay=0.0)
    sched = get_cosine_schedule_with_warmup(opt, max(1, total // 20), total)
    dev = torch.device("cuda", local) if world > 1 else next(core.parameters()).device

    def batches(rows, bs):
        for i in range(0, len(rows), bs):
            chunk = rows[i:i + bs]
            L = max(len(x) for x, _ in chunk)
            ids = torch.full((len(chunk), L), tok.pad_token_id)
            lab = torch.full((len(chunk), L), -100)
            att = torch.zeros((len(chunk), L), dtype=torch.long)
            for j, (x, y) in enumerate(chunk):
                ids[j, :len(x)] = torch.tensor(x)
                lab[j, :len(y)] = torch.tensor(y)
                att[j, :len(x)] = 1
            yield ids.to(dev), lab.to(dev), att.to(dev)

    @torch.no_grad()
    def evaluate():  # rank 0 only, on the unwrapped model (no collectives)
        core.eval()
        tot, n = 0.0, 0
        for ids, lab, att in batches(val, a.batch):
            tot += core(input_ids=ids, attention_mask=att, labels=lab).loss.item()
            n += 1
        core.train()
        return tot / max(1, n)

    def barrier():
        if world > 1:
            torch.distributed.barrier()

    if main:
        log(f"{len(data)} train / {len(val)} val examples on {world} GPU(s), {total} optimizer steps "
            f"(effective batch {per_step}); val loss {evaluate():.4f}")
    barrier()
    model.train()
    step, t0 = 0, time.time()
    from contextlib import nullcontext
    for ep in range(a.epochs):
        random.shuffle(data)
        shard = data[rank::world]
        for i, (ids, lab, att) in enumerate(batches(shard, a.batch)):
            sync = (i + 1) % a.grad_accum == 0
            ctx = model.no_sync() if (world > 1 and not sync) else nullcontext()
            with ctx:
                loss = model(input_ids=ids, attention_mask=att, labels=lab).loss / a.grad_accum
                loss.backward()
            if sync:
                torch.nn.utils.clip_grad_norm_(core.parameters(), 1.0)
                opt.step(); sched.step(); opt.zero_grad()
                step += 1
                if step % 20 == 0:
                    log(f"ep {ep} step {step}/{total} loss {loss.item() * a.grad_accum:.4f} {time.time() - t0:.0f}s")
        barrier()
        if main:
            log(f"epoch {ep}: val loss {evaluate():.4f}")
            core.save_pretrained(a.out)
            tok.save_pretrained(a.out)
        barrier()
    if not main:
        torch.distributed.destroy_process_group()
        return
    Path(a.out, "train_args.json").write_text(json.dumps({**vars(a), "world_size": world}, indent=1))
    if world > 1:
        torch.distributed.destroy_process_group()


def merge(a):
    import torch
    from peft import PeftModel
    from transformers import AutoTokenizer

    base = load_model(a.base, torch_dtype=torch.bfloat16)
    m = PeftModel.from_pretrained(base, a.out).merge_and_unload()
    m.save_pretrained(a.merged)
    AutoTokenizer.from_pretrained(a.out).save_pretrained(a.merged)
    print(f"merged -> {a.merged}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="HF model id of a small instruct model")
    ap.add_argument("--data")
    ap.add_argument("--out", required=True)
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--merged")
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--grad-accum", type=int, default=4)
    ap.add_argument("--max-len", type=int, default=2048)
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    merge(a) if a.merge else train(a)


if __name__ == "__main__":
    main()
