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

from pathlib import Path

import modal

REPO = Path(__file__).resolve().parents[1]
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


@app.function(image=image, gpu="H100", timeout=4 * 3600, volumes={"/vol": vol, "/hf": hf_cache})
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


@app.local_entrypoint()
def main(sft: str = "mix", tasks: str = "rl-s0-mix.jsonl", run: str = "grpo-1", steps: int = 150,
         save_every: int = 25, config: str = "grpo-1-h100.yaml", extra: str = ""):
    train.remote(sft, tasks, run, steps, save_every, config, extra)
