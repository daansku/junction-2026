# A4 -> A3: Harbor tasks now lock the agent's network (please keep it in exports)

Human request (Sat ~20:30): fix the answer-key exploit. Our public web server serves every eval game's `optimal_path`
(`GET /api/games/<id>`) and recorded winning runs, and the agent container had open internet.

What changed (A4, in your files):
- `arena/src/arena/harbor/export.py`: `[agent] network_mode = "allowlist"` + `allowed_hosts` (`AGENT_ALLOWED_HOSTS`:
  model APIs). The game URL is now `GAME_URL = "http://localhost:8000/mcp"` (task.toml, instruction.md, solve.sh),
  and the `game` service has no `expose`: with egress control Harbor puts it in the sidecar's network namespace
  next to the agent. A first version kept `game` as its own host; that traffic went through Harbor's transparent
  proxy, which reset idle MCP connections (`ECONNRESET` on `act` after slow turns). On localhost: 0 resets.
- `arena/tests/test_harbor.py`: asserts the allowlist, the localhost URL and no `expose:`. 9/9 pass.
- The 60 committed tasks in `harbor/eval-v1` and `harbor/eval-v2` got the same edits **in place** (not
  re-exported, so the frozen game files did not move). A fresh export of eval-v2 game 1 gives byte-identical
  `task.toml`, `docker-compose.yaml`, `instruction.md` and `solution/solve.sh`. `harbor lint` clean.

Verified (Docker 29.8.1, Harbor 0.26.0): oracle 1.000 (eval-v1 + eval-v2 game 1), stop-early 0.125; red team recon
from the agent seat: GitHub, PyPI, our server (name and IP) unreachable, `api.anthropic.com` reachable; OpenCode
plays (Haiku, Nemotron, DeepSeek) with 0 connection resets.

Ask: if you re-export, keep the allowlist. If a model API we use is missing, add it to `AGENT_ALLOWED_HOSTS`
(judges can add theirs with `harbor run ... --allow-agent-host <host>`). Details: `arena/HARBOR.md` ("Network").
