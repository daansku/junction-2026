"""GRPO on the engine-verified tasks, from a LoRA SFT checkpoint.

Built on TRL's GRPOTrainer (checked against trl 1.18.0): passing a `PeftModel` whose adapter is already
trained makes TRL copy it to a frozen "ref" adapter, so the KL term (`beta`) is to the SFT policy, not the
base model. Generation runs in vLLM (colocate mode: one vLLM engine per training GPU, LoRA merged and pushed
into it every step) or, with `--no-vllm`, in HF generate (slow; for CPU smoke tests / plan B).

    python -m engine tasks --task all --n 2000 --seed 0 --out /root/tasks/rl-s0.jsonl
    accelerate launch --num_processes 2 -m posttrain.grpo --config posttrain/configs/grpo-1.yaml \
        --base Qwen/Qwen3.5-9B --sft-lora /root/ckpt/sft-games --tasks /root/tasks/rl-s0.jsonl \
        --out /root/ckpt/grpo-1 --steps 300 --save-every 25

Every `--save-every` optimizer steps the policy adapter (only "default", never "ref") is written to
`<out>/step-<k>/` for `python -m bench run --lora <out>/step-<k> --dev-slice`. Metrics go to
`<out>/log.jsonl` (reward overall and per task, KL, completion length, clip ratio, ...).

Reward = `engine.tasks.reward(sample, reply)` in [0, 1]; grades the text after the last "ANSWER:", exact
match except full_plan efficiency. `--fake-reward` swaps it for a length/format toy reward (smoke tests only).
"""
from __future__ import annotations

import argparse
import json
import os
import random
import time
from pathlib import Path

# ----------------------------------------------------------------------------------------------- data


def load_tasks(path: str, only: list[str] | None = None, limit: int | None = None, seed: int = 0) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = json.loads(line)
            if only and s["task"] not in only:
                continue
            rows.append(s)
    random.Random(seed).shuffle(rows)  # tasks are written grouped by type; mix them
    return rows[:limit] if limit else rows


def to_dataset(rows: list[dict]):
    """Conversational prompt (system + user, no gold reply) + the columns the reward needs. `meta` differs per
    task, so it travels as a JSON string (Arrow wants one schema per column)."""
    from datasets import Dataset
    return Dataset.from_list([{
        "prompt": [m for m in s["messages"] if m["role"] != "assistant"],
        "task": s["task"], "sample_id": s["id"], "answer": s["answer"],
        "meta_json": json.dumps(s.get("meta", {})),
    } for s in rows])


def prompt_tokens(tok, s: dict, thinking: bool) -> int:
    msgs = [m for m in s["messages"] if m["role"] != "assistant"]
    text = tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False, enable_thinking=bool(thinking))
    return len(tok(text, add_special_tokens=False)["input_ids"])


# --------------------------------------------------------------------------------------------- reward


def _text(completion) -> str:
    if isinstance(completion, str):
        return completion
    return "".join(m.get("content") or "" for m in completion if m.get("role") == "assistant")  # conversational


THINK_END = "</think>"


def make_reward(fake: bool = False, thinking: bool = False, tok=None):
    """Reward = verifier on the reply. With `thinking`: ONLY the text after the last `</think>` is graded, and a reply
    without `</think>` (never closed / truncated) scores 0, so the policy is paid for conclusions reached after
    thinking. The raw `completion_ids` are decoded here (not TRL's parsed message, which may move the thinking into a
    separate field and hide whether it was closed). Tasks named `rg:<dataset>` are graded by reasoning-gym."""
    if fake:
        def score(sample: dict, reply: str) -> float:  # toy: answer line present + shorter is better
            return (0.5 if "ANSWER:" in reply else 0.0) + 0.5 / (1 + len(reply) / 50)
    else:
        from engine.tasks import reward as score  # exploit-tested; do not wrap with partial credit

    def grade(sample: dict, reply: str) -> float:
        if sample["task"].startswith("rg:"):
            from posttrain.rg_tasks import score as rg_score
            return rg_score(sample, reply)
        return score(sample, reply)

    def engine_reward(prompts, completions, task, sample_id, answer, meta_json, **kw):
        ids = kw.get("completion_ids")
        if tok is not None and ids is not None:
            texts = tok.batch_decode(ids, skip_special_tokens=True)  # think tags are not special: they stay
        else:
            texts = [_text(c) for c in completions]
        out, closed = [], []
        for x, t, i, a, m in zip(texts, task, sample_id, answer, meta_json):
            if thinking:
                ok = THINK_END in x
                closed.append(ok)
                if not ok:
                    out.append(0.0)
                    continue
                x = x.rsplit(THINK_END, 1)[1]
            out.append(float(grade({"task": t, "id": i, "answer": a, "meta": json.loads(m)}, x)))
        log_metric = kw.get("log_metric")
        if log_metric:  # per-task mean reward in the trainer's logs
            for t in sorted(set(task)):
                vals = [r for r, tt in zip(out, task) if tt == t]
                log_metric(f"reward_task/{t}", sum(vals) / len(vals))
            log_metric("answer_rate", sum("ANSWER:" in x for x in texts) / len(texts))
            if thinking:
                log_metric("think_closed_rate", sum(closed) / len(closed))
        return out

    return engine_reward


# ---------------------------------------------------------------------------------------------- model


def load_model(base: str, **kw):
    """Same as arena/finetune/train_sft.py: CausalLM, else the image-text class (Qwen3.5 is a VLM)."""
    from transformers import AutoModelForCausalLM
    try:
        return AutoModelForCausalLM.from_pretrained(base, **kw)
    except (ValueError, KeyError):
        from transformers import AutoModelForImageTextToText
        return AutoModelForImageTextToText.from_pretrained(base, **kw)


def lora_targets(model) -> list[str]:
    """Every Linear in the language model; never the vision tower or lm_head (as train_sft.py)."""
    import torch
    skip = ("visual", "vision", "lm_head", "multi_modal_projector", "mm_projector")
    return [n for n, m in model.named_modules()
            if isinstance(m, torch.nn.Linear) and not any(k in n for k in skip)]


def build_policy(a):
    """Base + SFT adapter (trainable). Without --sft-lora: base + a fresh LoRA (KL then is to the base)."""
    import torch
    from peft import LoraConfig, PeftModel, get_peft_model
    cuda = torch.cuda.is_available()
    dtype = torch.bfloat16 if cuda else torch.float32
    local = int(os.environ.get("LOCAL_RANK", "0"))
    model = load_model(a.base, dtype=dtype, device_map={"": local} if cuda else None)
    if a.sft_lora:
        model = PeftModel.from_pretrained(model, a.sft_lora, is_trainable=True)
    else:
        model = get_peft_model(model, LoraConfig(r=a.lora_r, lora_alpha=2 * a.lora_r, lora_dropout=0.0,
                                                 target_modules=lora_targets(model), task_type="CAUSAL_LM"))
    return model


def vl_param_name(name: str) -> str:
    """HF text-only Qwen3.5 (`Qwen3_5ForCausalLM`, what load_model returns) names its weights `model.layers.N...`;
    vLLM builds the checkpoint's VL class (`Qwen3_5ForConditionalGeneration`), whose loader maps only the
    checkpoint's own names `model.language_model.*`. Without this, TRL's per-step weight push fails."""
    if name.startswith("model.") and not name.startswith(("model.language_model.", "model.visual.")):
        return "model.language_model." + name[len("model."):]
    return name


def patch_vllm_names_for_vl(base: str, policy) -> bool:
    """Rename pushed weights when the checkpoint is a VL model but the policy was loaded text-only."""
    from transformers import AutoConfig
    archs = AutoConfig.from_pretrained(base).architectures or []
    if not any("ForConditionalGeneration" in x for x in archs):
        return False
    if any(".language_model." in n for n, _ in policy.named_parameters()):
        return False  # loaded as the VL class: names already match
    from trl.generation import vllm_generation as vg
    orig = vg.VLLMGeneration._fix_param_name_to_vllm
    if getattr(orig, "_vl_patched", False):
        return True

    def fixed(self, name, extra_prefixes=None):
        return vl_param_name(orig(self, name, extra_prefixes))
    fixed._vl_patched = True
    vg.VLLMGeneration._fix_param_name_to_vllm = fixed
    return True


# ------------------------------------------------------------------------------------------ callbacks


def make_callbacks(a, tok):
    from transformers import TrainerCallback

    out = Path(a.out)

    class SaveAdapter(TrainerCallback):
        """`<out>/step-<k>/`: the policy LoRA only (TRL's ref copy lives in the same PeftModel as "ref")."""

        def _save(self, state, model):
            if not state.is_world_process_zero:
                return
            d = out / f"step-{state.global_step}"
            m = getattr(model, "module", model)
            m.save_pretrained(d, selected_adapters=["default"])
            tok.save_pretrained(d)
            (d / "grpo_meta.json").write_text(json.dumps({
                "step": state.global_step, "base": a.base, "sft_lora": a.sft_lora, "tasks": a.tasks,
                "recent_reward": next((h.get("reward") for h in reversed(state.log_history) if "reward" in h), None),
            }, indent=1))
            print(f"[grpo] saved {d}", flush=True)

        def on_step_end(self, args, state, control, model=None, **kw):
            if state.global_step % a.save_every == 0:
                self._save(state, model)

        def on_train_end(self, args, state, control, model=None, **kw):
            if state.global_step % a.save_every != 0:
                self._save(state, model)

    class JsonlLog(TrainerCallback):
        def __init__(self):
            self.t0 = time.time()

        def on_log(self, args, state, control, logs=None, **kw):
            if state.is_world_process_zero and logs:
                with open(out / "log.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps({"step": state.global_step, "elapsed_s": round(time.time() - self.t0),
                                        **logs}) + "\n")

    return [SaveAdapter(), JsonlLog()]


# ------------------------------------------------------------------------------------------------ main

DEFAULTS = dict(  # overridden by --config yaml, then by explicit CLI flags
    base="Qwen/Qwen3.5-9B", sft_lora=None, tasks=None, out=None, steps=300, save_every=25,
    task_filter=None, limit=None, seed=0, lora_r=16, max_prompt_tokens=3072, note="",
    lr=1e-5, warmup_ratio=0.03, per_device_batch=8, grad_accum=4, num_generations=8,
    max_completion=1024, temperature=1.0, top_p=1.0, beta=0.04, epsilon=0.2, epsilon_high=0.28,
    loss_type="dapo", scale_rewards="group", num_iterations=1, mask_truncated=True,
    enable_thinking=False, use_vllm=True, vllm_mode="colocate", vllm_gpu_mem=0.35, vllm_max_len=6144,
    vllm_sleep=False, fake_reward=False, logging_steps=1,
)


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", help="yaml with any of the keys below (underscores); CLI flags win")
    ap.add_argument("--base")
    ap.add_argument("--sft-lora", help="LoRA adapter dir from SFT v2 (the policy init and the KL reference)")
    ap.add_argument("--tasks", help="jsonl from `python -m engine tasks`")
    ap.add_argument("--out", help="checkpoints go to <out>/step-<k>")
    ap.add_argument("--steps", type=int)
    ap.add_argument("--save-every", type=int)
    ap.add_argument("--task-filter", help="comma list, e.g. rule_effect,min_moves")
    ap.add_argument("--limit", type=int, help="use only the first N (shuffled) samples")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--lr", type=float)
    ap.add_argument("--per-device-batch", type=int, help="completions per GPU per micro-step")
    ap.add_argument("--grad-accum", type=int)
    ap.add_argument("--num-generations", type=int, help="group size G")
    ap.add_argument("--max-completion", type=int)
    ap.add_argument("--beta", type=float, help="KL coefficient to the SFT policy")
    ap.add_argument("--vllm-gpu-mem", type=float)
    ap.add_argument("--note", help="free text stored in grpo_args.json (decisions, provenance)")
    ap.add_argument("--max-prompt-tokens", type=int, help="drop longer prompts (rule_effect has 12k-token outliers)")
    ap.add_argument("--vllm-max-len", type=int, help="vLLM context: >= longest prompt + max completion")
    ap.add_argument("--no-vllm",dest="use_vllm", action="store_false", default=None)
    ap.add_argument("--thinking", dest="enable_thinking", action="store_true", default=None,
                    help="Qwen thinking mode on (default off: SFT v2 data answers without <think>)")
    ap.add_argument("--no-mask-truncated", dest="mask_truncated", action="store_false", default=None,
                    help="learn from cut-off replies too (smoke tests: a random tiny model never stops)")
    ap.add_argument("--fake-reward", action="store_true", default=None)
    raw = ap.parse_args(argv)
    cfg = dict(DEFAULTS)
    if raw.config:
        import yaml
        cfg.update({k.replace("-", "_"): v for k, v in (yaml.safe_load(open(raw.config)) or {}).items()})
    cfg.update({k: v for k, v in vars(raw).items() if v is not None and k != "config"})
    unknown = set(cfg) - set(DEFAULTS)
    if unknown:
        raise SystemExit(f"unknown config keys: {sorted(unknown)}")
    a = argparse.Namespace(**cfg)
    for k in ("tasks", "out"):
        if not getattr(a, k):
            raise SystemExit(f"--{k} is required")
    if isinstance(a.task_filter, str):
        a.task_filter = [t for t in a.task_filter.split(",") if t]
    return a


def main(argv=None):
    a = parse_args(argv)
    import torch
    from transformers import AutoTokenizer
    from trl import GRPOConfig, GRPOTrainer

    Path(a.out).mkdir(parents=True, exist_ok=True)
    cuda = torch.cuda.is_available()
    tok = AutoTokenizer.from_pretrained(a.sft_lora or a.base)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    tok.padding_side = "left"

    rows = load_tasks(a.tasks, a.task_filter, None, a.seed)
    n_all = len(rows)
    rows = [r for r in rows if prompt_tokens(tok, r, a.enable_thinking) <= a.max_prompt_tokens][: a.limit or None]
    if a.vllm_max_len < a.max_prompt_tokens + a.max_completion:
        raise SystemExit(f"vllm_max_len {a.vllm_max_len} < max_prompt_tokens + max_completion")
    ds = to_dataset(rows)
    counts = {"dropped_long_prompts": n_all - len(rows)} if not a.limit else {}
    for r in rows:
        counts[r["task"]] = counts.get(r["task"], 0) + 1

    cfg = GRPOConfig(
        output_dir=a.out, max_steps=a.steps, learning_rate=a.lr, lr_scheduler_type="constant_with_warmup",
        warmup_steps=max(1, int(a.warmup_ratio * a.steps)),  # transformers 5 dropped warmup_ratio
        per_device_train_batch_size=a.per_device_batch,
        gradient_accumulation_steps=a.grad_accum, num_generations=a.num_generations,
        max_completion_length=a.max_completion, temperature=a.temperature, top_p=a.top_p,
        chat_template_kwargs={"enable_thinking": bool(a.enable_thinking)},
        beta=a.beta, epsilon=a.epsilon, epsilon_high=a.epsilon_high, loss_type=a.loss_type,
        scale_rewards=a.scale_rewards, num_iterations=a.num_iterations,
        mask_truncated_completions=a.mask_truncated,
        use_vllm=bool(a.use_vllm and cuda), vllm_mode=a.vllm_mode, vllm_gpu_memory_utilization=a.vllm_gpu_mem,
        vllm_max_model_length=a.vllm_max_len, vllm_enable_sleep_mode=a.vllm_sleep,
        bf16=cuda, gradient_checkpointing=cuda, gradient_checkpointing_kwargs={"use_reentrant": False},
        save_strategy="no",  # our callback writes adapter-only checkpoints; no 100 GB optimizer states
        logging_steps=a.logging_steps, report_to="none", seed=a.seed, remove_unused_columns=False,
        log_completions=False, use_cpu=not cuda,
    )
    policy = build_policy(a)
    if cfg.use_vllm and patch_vllm_names_for_vl(a.base, policy):
        print("[grpo] VL checkpoint loaded text-only: weight names pushed to vLLM get the model.language_model. prefix",
              flush=True)
    trainer = GRPOTrainer(model=policy, reward_funcs=make_reward(a.fake_reward, bool(a.enable_thinking), tok), args=cfg,
                          train_dataset=ds, processing_class=tok, callbacks=make_callbacks(a, tok))
    if trainer.is_world_process_zero():
        prompts_per_step = a.per_device_batch * a.grad_accum * trainer.accelerator.num_processes // a.num_generations
        info = {**vars(a), "task_counts": counts, "world_size": trainer.accelerator.num_processes,
                "prompts_per_step": prompts_per_step, "completions_per_step": prompts_per_step * a.num_generations}
        Path(a.out, "grpo_args.json").write_text(json.dumps(info, indent=1))
        print(f"[grpo] {len(rows)} prompts {counts}; {prompts_per_step} prompts x {a.num_generations} per step, "
              f"{a.steps} steps, vllm={cfg.use_vllm}", flush=True)
    trainer.train()


if __name__ == "__main__":
    main()
