"""grpo-1 on one Modal H100 (A3-25). Same trainer as the Verda boxes (`posttrain.grpo`), nothing Modal-specific inside.

Volume `junction-grpo` layout:  /sft/<row>/ (adapter)   /tasks/<file>.jsonl   /runs/<run>/step-<k>/ + log.jsonl
HF weights are cached in volume `junction-hf-cache` (first start downloads Qwen3.5-9B once, ~18 GB).

From the A100 box (repo at /root/junction-2026, `. /root/modal-venv/bin/activate`):
    modal volume create junction-grpo                                   # once
    modal volume put junction-grpo /root/ckpt/mix/lora /sft/mix
    modal volume put junction-grpo /root/tasks/rl-s0-mix.jsonl /tasks/rl-s0-mix.jsonl
    modal run --detach posttrain/modal_grpo.py --sft mix --tasks rl-s0-mix.jsonl --run grpo-1 --steps 150
    bash posttrain/tools/modal_pull.sh grpo-1          # loop: copies new step-<k> to /root/ckpt/grpo-1/
`--detach` keeps the run alive if the local client disconnects. Function timeout 4 h (checkpoints every 25 steps
are on the volume before that). Cost: H100 on Modal ~$4/h -> ~$12-16 for a 3-4 h run.
"""
from __future__ import annotations

import os
from pathlib import Path

import modal

REPO = Path(__file__).resolve().parents[1]
GPU = os.environ.get("GRPO_GPU", "H100")  # GRPO_GPU=A100-80GB if the account has no payment method (H100 needs one)
app = modal.App("junction-grpo")
vol = modal.Volume.from_name("junction-grpo", create_if_missing=True)
hf_cache = modal.Volume.from_name("junction-hf-cache", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git")
    # vllm 0.33.0 = bench's pin, inside TRL 1.18's supported range; versions as on the Verda H100 (verified there)
    .uv_pip_install("vllm==0.33.0", "trl==1.18.0", "peft==0.21.3", "accelerate", "datasets", "pyyaml",
                    "hf_transfer")
    .env({"HF_HOME": "/hf", "HF_HUB_ENABLE_HF_TRANSFER": "1", "PYTHONUNBUFFERED": "1",
          "PYTHONPATH": "/repo/engine/src:/repo/posttrain/src"})
    .add_local_dir(REPO / "engine" / "src", "/repo/engine/src", ignore=["**/__pycache__"])
    .add_local_dir(REPO / "posttrain" / "src", "/repo/posttrain/src", ignore=["**/__pycache__"])
    .add_local_dir(REPO / "posttrain" / "configs", "/repo/posttrain/configs")
    .add_local_file(REPO / "data" / "collections" / "train-v1.json", "/repo/data/collections/train-v1.json")
)


@app.function(image=image, gpu=GPU, timeout=4 * 3600, volumes={"/vol": vol, "/hf": hf_cache})
def train(sft: str, tasks: str, run: str, steps: int, save_every: int, config: str, extra: str):
    import shlex
    import subprocess
    import threading
    import time

    out = Path("/vol/runs") / run
    out.mkdir(parents=True, exist_ok=True)
    stop = threading.Event()

    def committer():  # make step-<k> and log.jsonl visible to `modal volume get` while training runs
        while not stop.wait(120):
            try:
                vol.commit()
            except Exception as e:  # noqa: BLE001
                print(f"[modal] commit failed: {e}", flush=True)

    threading.Thread(target=committer, daemon=True).start()
    cmd = ["accelerate", "launch", "--num_processes", "1", "--mixed_precision", "bf16", "-m", "posttrain.grpo",
           "--config", f"/repo/posttrain/configs/{config}", "--sft-lora", f"/vol/sft/{sft}",
           "--tasks", f"/vol/tasks/{tasks}", "--out", str(out), "--steps", str(steps),
           "--save-every", str(save_every), *shlex.split(extra)]
    print("[modal] " + " ".join(cmd), flush=True)
    t0 = time.time()
    with open(out / "train.log", "a") as log:
        p = subprocess.Popen(cmd, cwd="/repo", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in p.stdout:  # tee: Modal logs + train.log on the volume
            print(line, end="", flush=True)
            log.write(line)
            log.flush()
        rc = p.wait()
    stop.set()
    hf_cache.commit()
    vol.commit()
    print(f"[modal] exit {rc} after {(time.time() - t0) / 60:.0f} min", flush=True)
    if rc:
        raise RuntimeError(f"posttrain.grpo exited {rc}")


@app.function(image=image, gpu="L40S", timeout=3600, volumes={"/vol": vol, "/hf": hf_cache})
def evaluate(adapters: str, tasks: str = "heldout-gameturn-s2.jsonl", out: str = "eval/heldout.json",
             samples: int = 4, no_base: bool = False):
    """In-domain check: `modal run posttrain/modal_grpo.py::evaluate --adapters sft/games,runs/grpo-2/step-20`
    (paths relative to the volume). L40S (~$2/h): 9B bf16 fits, ~5-10 min for 200 prompts x 5 replies x adapters."""
    import subprocess

    paths = [f"/vol/{p.strip().strip('/')}" for p in adapters.split(",") if p.strip()]
    Path(f"/vol/{out}").parent.mkdir(parents=True, exist_ok=True)
    cmd = ["python", "-m", "posttrain.eval_tasks", "--tasks", f"/vol/tasks/{tasks}", "--out", f"/vol/{out}",
           "--samples", str(samples), "--adapters", *paths] + (["--no-base"] if no_base else [])
    print("[modal] " + " ".join(cmd), flush=True)
    rc = subprocess.run(cmd, cwd="/repo").returncode
    hf_cache.commit()
    vol.commit()
    if rc:
        raise RuntimeError(f"eval_tasks exited {rc}")


bench_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git")
    # same versions as A2's bench venv on the A100 box (/srv/bench/.venv), so Modal rows match its rows
    .uv_pip_install("vllm==0.33.0", "transformers==5.20.2", "lm-eval[api,ifeval,math]==0.4.13",
                    "reasoning-gym==0.1.25", "datasets==5.2.0", "huggingface_hub", "pyyaml", "math-verify==0.9.0",
                    "antlr4-python3-runtime==4.11.0", "peft==0.21.3", "accelerate")
    .env({"HF_HOME": "/hf", "PYTHONUNBUFFERED": "1", "PYTHONPATH": "/repo/bench/src"})
    .add_local_dir(REPO / "bench" / "src", "/repo/bench/src", ignore=["**/__pycache__"])
    .add_local_dir(REPO / "bench" / "configs", "/repo/bench/configs")
)


MERGE_SCRIPT = """
import sys, torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
ad, dst = sys.argv[1], sys.argv[2]
base = AutoModelForCausalLM.from_pretrained("Qwen/Qwen3.5-9B", dtype=torch.bfloat16, device_map={"": 0})
m = PeftModel.from_pretrained(base, ad).merge_and_unload()
m.save_pretrained(dst, safe_serialization=True)
AutoTokenizer.from_pretrained(ad).save_pretrained(dst)
print("[merge] done", type(m).__name__, flush=True)
"""


@app.function(image=bench_image, gpu="H100", timeout=3 * 3600, volumes={"/vol": vol, "/hf": hf_cache})
def bench_dev(adapter: str, name: str):
    """Dev-slice bench of one adapter on its own H100, A2's generation.yaml unchanged (vLLM at 0.88). The adapter is
    MERGED into the base first: vLLM 0.33's LoRA path asserts on loglikelihood requests (MedQA), see A3 status.
    `modal run posttrain/modal_grpo.py::bench_dev --adapter runs/grpo-1/step-25 --name rl-grpo-1-step-25`
    -> /vol/bench/<name>/ (pull with `modal volume get junction-grpo /bench/<name> /srv/bench/out/`)."""
    import subprocess
    import threading

    stop = threading.Event()

    def committer():
        while not stop.wait(300):
            try:
                vol.commit()
            except Exception:  # noqa: BLE001
                pass

    threading.Thread(target=committer, daemon=True).start()
    out = f"/vol/bench/{name}"
    merged = "/tmp/merged"
    merge = MERGE_SCRIPT
    rc = subprocess.run(["python", "-c", merge, f"/vol/{adapter.strip('/')}", merged]).returncode
    if rc:
        raise RuntimeError(f"merge exited {rc}")
    cmd = ["python", "-m", "bench", "run", "--model", merged, "--name", name, "--dev-slice", "--out", out, "--resume"]
    print("[modal] " + " ".join(cmd), flush=True)
    rc = subprocess.run(cmd, cwd="/repo").returncode
    stop.set()
    hf_cache.commit()
    vol.commit()
    if rc:
        raise RuntimeError(f"bench exited {rc}")


@app.local_entrypoint()
def main(sft: str = "mix", tasks: str = "rl-s0-mix.jsonl", run: str = "grpo-1", steps: int = 150,
         save_every: int = 25, config: str = "grpo-1-h100.yaml", extra: str = ""):
    print(f"GPU {GPU}")
    train.remote(sft, tasks, run, steps, save_every, config, extra)
