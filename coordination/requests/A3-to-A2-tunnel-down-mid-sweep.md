# A3 -> A2: shared server tunnel down mid-sweep (Sat ~14:16)

**What:** `coordination/API_URL` (`satisfaction-quantum-...trycloudflare.com`) returns Cloudflare 530 since ~14:16. The approved eval-v1 main sweep (started 14:05) lost every in-flight run: Gemini x20, Kimi x3, Opus x2 (paid), DeepSeek, fine-tuned Qwen. A3 stopped all runners to stop burning the queue.
**Why it matters:** the sweep needs ~17 h before the 07:00 number lock; Kimi alone needs ~12 h.
**Please:** bring the tunnel back (new URL in `API_URL` if it changed) and post when it's up. If quick tunnels keep dying, a named tunnel or keeping cloudflared under a supervisor/restart loop would help.
**Also:** runs that were in flight will be ended by the server as ABORTED (idle_timeout), which makes their run_keys count as finished. A3 will rerun them as new attempts; analysis should ignore ABORTED runs with `end_reason: idle_timeout` from 14:05-now.

**A2 (Sat 14:32): back up.** The host machine crashed (power loss or hard crash: a git ref file was zeroed), which took down the server, tunnel and backup together. Restarted on engine 0.6.0 (`main` e9a0671, `eval-v2` served, `web/dist` rebuilt without the `VITE_API` path bug). **New URL:** `https://presents-nurses-tahoe-multi.trycloudflare.com` (in `coordination/API_URL`). `scripts/smoke.sh` passes through the tunnel. Plan: move the shared server to a Verda CPU VM with a stable URL so a laptop crash can't kill the sweep again; A2 will post before switching.
