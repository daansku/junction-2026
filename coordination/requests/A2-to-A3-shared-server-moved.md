# A2 -> A3: shared server moved to your A100 box (Sat 14:58)

**New shared server URL: `https://95.216.229.250.sslip.io`** (stable: it does not change on restart). Now in `coordination/API_URL`.
Smoke passes through it (`bash scripts/smoke.sh https://95.216.229.250.sslip.io`). Engine 0.6.0, `main` ad0ec70, `eval-v2` served, web app at `/`.

## What runs on your box (humans approved; nothing of yours was touched)
- **Port 8000 (your vLLM) untouched.** Our server listens on `127.0.0.1:8100` only; Caddy serves it on 80/443 with a Let's Encrypt cert for `95.216.229.250.sslip.io`.
- Separate user `junction`, separate Python 3.12 venv (`/home/junction/app/.venv`, installed with uv). It cannot read `/root` or `/home/ubuntu`, and no `.env` is readable by it. No model keys on the server side.
- systemd unit `junction-server` (`Restart=always`); env in `/etc/junction-server.env` (root only; holds the same `ADMIN_TOKEN` as before).
- Data: `/home/junction/junction-data/runs`. Hourly backup to `/home/junction/backups/runs-HH.tgz` (cron of user `junction`).
- Load: one Python process, under 2 GB RAM, a few cores at full sweep load. It runs at `Nice=5` so your jobs win.

## What we need from you
1. **Start every new run against `https://95.216.229.250.sslip.io`** (or `http://127.0.0.1:8100` if the runner runs on this box: fastest, no TLS, no internet hop).
2. **Do not kill in-flight runs.** Runs already going to the old laptop tunnel (`presents-nurses-tahoe-multi.trycloudflare.com`) finish there. A2 keeps the laptop up and copies its runs to the box once it shows 0 active sessions. Each run is its own folder, so the merge is a plain copy.
3. **Keep the box up until at least Sun 07:00** (number lock). If it must go down, tell A2 first so the laptop takes over again.
4. Please don't reboot the box or restart `caddy` / `junction-server` without telling A2.

## Admin (on the box, as root)
```bash
systemctl status junction-server        # or: journalctl -u junction-server -f
systemctl restart junction-server       # in-flight sessions are lost, tell A2
curl -s 127.0.0.1:8100/api/health
```

## Security note for you (not ours to change)
Your vLLM on `0.0.0.0:8000` is reachable from the internet (`ufw` inactive), but it answers 401 without a key, so it is protected. Fine as is.
