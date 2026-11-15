# A2 -> A3: B200 released (Sun 15.11 ~05:00)

The Verda B200 (`95.133.252.154`, root, A2's `junction-verda` key) is yours. A2 runs nothing on it.

- GPU: 0 MiB used, 0% util. No training, vLLM or bench processes. A2's leftover `tail -F` log watchers are killed.
- Backed up to Anssi's laptop (`~/junction-backups/b200-2026-11-15/b200.tgz`, 1.65 GB): `/root/b200bench/out` (MATH held-out results behind the S5 numbers), `/root/data/ckpt` (all LoRA checkpoints, incl. `think-games-h2/step-30`), `/root/h2rl`, `/root/gen_tasks_gb.py`, `/root/*.log`.
- Left in place, free to delete: `/dev/shm/hf` (19 GB, Qwen3.5-9B + caches, reusable), `/dev/shm/ckpt` (17 GB), `/root/data`, `/root/b200bench`, `/root/rl-venv` (torch 2.14 cu130, vLLM 0.33.0, TRL 1.18.0, reusable).
- Disk: `/` 48 GB (15 GB free); `/dev/shm` 84 GB (49 GB free).
- Access: Anssi gives you the private key `a3_b200` (B200 only). `ssh -i a3_b200 root@95.133.252.154`.
- **Held-out MATH test for your model:** `bench/heldout_math/README.md` (exact steps). Short version on the B200:
  `cd /root && git clone https://github.com/daansku/junction-2026.git && cd junction-2026 && bash bench/heldout_math/run.sh <name> --lora <adapter dir>`
  (or `run.sh <name> <merged model dir>`). About 4 min; prints held-out delta vs base, 95% CI and McNemar p.
