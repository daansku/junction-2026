# Judge Q&A & 15-Minute Exploit Hunt Defense (`docs/QA_PREP.md`)

> Prepared for the AfterQuery 10-minute demo + 15-minute interactive exploit hunt + Harbor/OpenCode MCP rerun.
> **Rule:** Never overclaim. Cite only verified formulas, Docker sidecar boundaries, schema guards, test suites, and inspected trace metrics.

---

## Part A: Reward Exploit Hunt — Anticipated Attacks & Defenses

### Attack 1: *"Inside the Harbor agent container, can OpenCode read `optimal_path`, engine source, or write `1.0` directly to the reward file?"*
- **Why it fails (`arena/HARBOR.md`, `arena/src/arena/harbor.py`):**
  1. **Separate containers:** The agent runs in `main` (node + OpenCode + bash, **no engine code, no game JSON, no `/evidence` volume**). The game runs in a separate `game-server` sidecar container on an internal Compose network.
  2. **Minimal network surface:** `game-server` exposes **only** `/healthz` and `/mcp` with two tools: `observe()` and `act(action)` returning `frame_rle`, `image/png`, `available_actions`, `state`, and `level`. There is no `/truth`, no `/describe`, and no score endpoint on the sidecar.
  3. **Post-termination grading:** `/evidence/score.json` is written inside `game-server`, copied out by Harbor **after** the agent container stops, and graded inside a fresh verifier container (`/logs/verifier/reward.txt`).

### Attack 2: *"Can an agent score high by solving only Level 1 quickly and stopping early before harder levels?"*
- **Why it fails:**
  1. `game_score` ALWAYS averages `level_score(L)` over all `levels_total` levels (`1..levels_total`), never just attempted levels (`analysis/METRICS.md §2`).
  2. Verified directly in Harbor (`coordination/JUDGING.md` on 6-level `gridworld-s1000-d1-l6-9b1065f8`):
     - `harbor run -p "$TASK" -a nop` (`0` actions, `0/6` levels) → **`0.000`**
     - `harbor run -p "$TASK" -a oracle --ae ORACLE_STOP_AFTER_LEVELS=1` (`13` actions, `1/6` levels) → **`0.167`** (`1/6`)
     - `harbor run -p "$TASK" -a oracle --ae ORACLE_STOP_AFTER_LEVELS=3` (`45` actions, `3/6` levels) → **`0.500`** (`3/6`)
     - `harbor run -p "$TASK" -a oracle` (`92` actions, `6/6` levels) → **`1.000`**

### Attack 3: *"What if an agent explores noisily for 40 steps, learns the layout, hits `RESET`, and replays only the optimal path to fake `1.000` efficiency?"*
- **Why it fails:**
  - Both the Harbor sidecar scorer and `analysis/src/analysis/loader.py` count **every** step spent on Level `L` in `actions_used(L)`, including pre-reset exploration and the `RESET` call itself.
  - Verified in `test_reward_integrity_and_reset_penalty`: a clean `4`-step solve scores `1.000`, while `2` exploratory/reset steps + `4` optimal moves consumes `6` actions and scores `4/6 = 0.6667`.

### Attack 4: *"Can an agent farm partial credit by collecting gems/keys, toggling plates, or bumping walls?"*
- **Why it fails:**
  - Zero intermediate shaping reward exists. Sub-goals (`collected`, `picked_key`, `pressed_plate`) are required causal prerequisites to unlock the goal, not point sources; extra actions increase `actions_used(L)` and strictly lower `min(1, optimal_moves / actions_used)`.

### Attack 5: *"Can an agent hardcode RGB colors (`yellow = key`, `green = goal`, `red = hazard`) or memorize training rule pairs?"*
- **Why it fails:**
  - Every generated game enables `skin_shuffle: true`, permuting the 16-color indexed palette and non-directional glyphs per seed (`rules/CATALOG.md`).
  - Furthermore, `eval-v1` holds out **6 unseen rule pairs** (e.g. `(ice, teleporters)`, `(phase_walls, plates_gates)`, `(beacon_goal, twin)`) and **held-out visual skins** disjoint from `dev` and `train-v1` (`engine/src/engine/splits.py`), tracked separately as `seen_score`, `unseen_pair_score`, and `unseen_skin_score` in `leaderboard.json`.

### Attack 6: *"Could `PUBLISHED_MODE` on the public demo URL allow visitors to pollute the leaderboard or trigger `/api/admin/rebuild`?"*
- **Why it fails:**
  - When `PUBLISHED_MODE=1` (`server/src/server/app.py`), model/baseline session creation and `/api/admin/rebuild` return `HTTP 403`, `/api/runs` serves only frozen `data/published/runs`, and visitor `/play` games run isolated in memory without entering benchmark tables.

---

## Part B: Judge Methodology & Design Q&A

### Q1: *"How do judges reproduce our Harbor + OpenCode evaluation in one command?"*
- Run `arena harbor-export` + `harbor run` (`arena/HARBOR.md` — **not** `python -m server mcp`, which is dev/demo-only):
  ```bash
  python -m arena harbor-export --collection eval-v1 --out /tmp/junction-harbor --first 3
  TASK=$(ls -d /tmp/junction-harbor/gridworld-* | head -1)
  harbor run -p "$TASK" -a oracle                                      # -> 1.000
  harbor run -p "$TASK" -a nop                                         # -> 0.000
  harbor run -p "$TASK" -a oracle --ae ORACLE_STOP_AFTER_LEVELS=1      # -> 0.167
  set -a; . ./.env; set +a
  harbor run -p "$TASK" -a opencode -m verda-nemotron/nemotron-3.5-super-vl \
    --ak "opencode_config=$(python3 -c 'import json;print(json.dumps(json.load(open("arena/opencode-nemotron.json"))))')" \
    --ae 'NVIDIA_VERDA_INFERENCE_KEY=${NVIDIA_VERDA_INFERENCE_KEY}' -k 3 -n 1
  ```
- On `dev` task `gridworld-s1000-d1-l6-9b1065f8`, OpenCode + Nemotron `k=3` scored `0.020`, `0.094`, `0.087` (**mean `0.067`**) vs reference `1.000`.

### Q2: *"Why did vision+RLE models (`Kimi K3.1 Pro`: 52.1% levels, `0.374`) beat text-only RLE models (`DeepSeek V3.2`, `gpt-oss-120b`: `0%`) when RLE is lossless?"*
- Every model under `h1` receives the exact lossless 64×64 run-length encoded grid (`rle`), and vision models additionally receive the rendered PNG (`[image, rle]`). While RLE contains 100% of the state information, text-only models fail 2D spatial alignment across 4×4 multi-pixel glyphs (`arrow_up`, `ring`, `checker`), spending `55%–66%` of their move budget on zero-effect wall bumps (`insights.json` finding `modality-gap`).

### Q3: *"How does the closed-loop `eval-v2` rule evolution work?"*
- `python -m analysis build --write-proposals` ranks mechanics with the lowest non-Tier-0 `intro_solve_rate` and highest `wasted_actions` across model traces. Our first round (`auto-01..03`: `cracked_floor`, `collect_all`, `twin`) was implemented directly into Engine `0.4.0/0.5.0` (`twin` currently has `0.0` model intro solve rate!), and `auto-04-eval-v2-tier3-drift-and-timing.md` promotes A1's verified Tier-3 post-move mechanics (`conveyors`, `enemies`, `gravity`) into `eval-v2`.
