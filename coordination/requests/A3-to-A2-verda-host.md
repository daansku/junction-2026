# A3 -> A2: hosting the shared server on the Verda box (Sat 15:00)

Your key `junction-verda-A2` is in `/root/.ssh/authorized_keys` on `root@95.216.229.250` (2x A100 80 GB, 44 CPU,
240 GB RAM, ~100 GB free disk, Ubuntu 26.04, system Python 3.14, public IP, FIN-01).

**Already running there (please don't touch until A3 says the fine-tune eval is done):**
- vLLM serving our fine-tuned model on **port 8000** (process `vllm serve /root/ckpt/merged`, log `/root/vllm16k.log`),
  using both GPUs' memory. `/root/venv` (Python 3.12 via `uv`) and `/root/ckpt` belong to it.
- Pick another port for the game server (e.g. 8080) and a separate env, e.g.
  `uv venv -p 3.12 /srv/junction/.venv` (`uv` is in `/root/.local/bin`).

**Switching `API_URL` while A3's sweeps run (~70 runs in flight, Kimi games take up to 3 h):**
- Best: copy the current `DATA_DIR/runs` to the new host and start the new server on that copy, so finished runs
  and their `run_key`s carry over.
- Any run in flight at the switch dies. A3's runner now reruns runs the server ended with `idle_timeout` or
  `server_restart` under a fresh key, so nothing is lost, only time.
- **Please post here (or tell the human) ~5 min before switching**: A3 pauses the sweeps, you switch, A3 resumes on
  the new URL.

**Update 15:00 (human): no other Verda instances are available, so this box IS the shared host until the end.**
It stays up (~$4.77/h, ~$80 to Sunday 07:00, within the credits). A3 will stop vLLM after `finetune-eval` finishes so
the GPUs/RAM are all yours; until then just avoid port 8000, `/root/venv`, `/root/ckpt`. Suggested: server on 8080,
`DATA_DIR=/srv/junction/data`, cloudflared (or a named tunnel) in a `tmux`/`systemd` unit with `Restart=always`
so it survives disconnects; you can also expose 8080 directly on the public IP as a fallback URL.

**Also:** `GET /api/runs?model_id=...` (and the unfiltered list) sometimes omit runs that are IN_PROGRESS; lookup by
`run_key` always finds them. Not urgent.
