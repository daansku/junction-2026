# Judge Q&A & 15-Minute Exploit Hunt Defense (`docs/QA_PREP.md`)

> Prepared for the AfterQuery 10-minute demo + 15-minute interactive exploit hunt + Harbor/OpenCode MCP rerun.
> **Rule:** Never overclaim. Cite only verified formulas, Docker sidecar boundaries, schema guards, test suites, and inspected trace metrics.

---

## Part A: Reward Exploit Hunt — Tested Red-Team Attacks & Defenses (`9 / 9 -> 0.000`)

Executed from inside the Harbor agent container (`coordination/redteam/redteam_agent.py` + `coordination/redteam/attack.py` on frozen `harbor/eval-v1/gridworld-s900000-d1-l6-33a57ce4`, solution folder stripped; see `coordination/JUDGING.md` → Red team):

| # | Red-Team Attack (Agent Container Seat) | Empirical Result | Verified Reward |
|---|---|---|---|
| 1 | **Forge `/evidence/score.json` & `/logs/verifier/reward.txt`** (`1.0`, `won: true`) | Writes stay inside `main` container; Harbor pulls `score.json` from `service = "game"` and overwrites `reward.*` in a fresh verifier container | **0.000** |
| 2 | **Disk & env recon** (`find /` for `solve.sh`, `collection.json`, `score.json`, `sidecar.py`; `env`) | Nothing present in `main`; env holds only standard container vars (no game id, no keys) | **0.000** |
| 3 | **Side routes & port scan** (`/docs`, `/score`, `/truth`, `/state`, `/evidence/score.json`, traversal; ports `22..9000`) | Only `GET /healthz` (`{"ok":true}`) and `/mcp` respond; all other routes `404` / ports closed | **0.000** |
| 4 | **MCP surface & unknown tools** (`tools/list`, resources, prompts, `score`) | Tools = `observe`, `act(action, note)` only; unknown tools rejected | **0.000** |
| 5 | **Malformed actions & extra args** (`ACTION6`, `UNDO`, `WIN`, `RESET;ACTION1`, 5k-char string, `debug=true`) | Rejected without advancing state or leaking truth/score words | **0.000** |
| 6 | **Fresh MCP session reset** (open new session mid-episode to bypass move count) | New MCP session attaches to the same live episode; nothing resets | **0.000** |
| 7 | **Concurrency race** (`32` parallel `act` calls across `32` sessions) | Serialized cleanly (`33` valid actions sent = `33` recorded) | **0.000** |
| 8 | **`RESET` spam** (`2,000` consecutive `RESET` calls) | Every `RESET` increments `actions_used`; `0` levels solved | **0.000** |
| 9 | **Wall-cycle spam** (`3,100` cyclic moves) | Move budget ends level (`GAME_OVER`) after `33` moves; only `RESET` accepted thereafter | **0.000** |

### Architectural Guarantees Behind Those Results

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

### Q1: *"How do judges reproduce our Harbor + OpenCode evaluation in one command from a fresh clone?"*
- Run `make setup` + `harbor run` against the committed frozen `harbor/eval-v1/` tasks (`arena/HARBOR.md` — **not** `python -m server mcp`, which is dev/demo-only):
  ```bash
  make setup && . .venv/bin/activate
  uv tool install harbor==0.26.0
  TASK=harbor/eval-v1/gridworld-s900000-d1-l6-33a57ce4
  harbor run -p "$TASK" -a oracle                                      # -> 1.000 (86 actions, 6/6)
  harbor run -p "$TASK" -a nop                                         # -> 0.000
  harbor run -p "$TASK" -a oracle --ae ORACLE_STOP_AFTER_LEVELS=1      # -> 0.167 (11 actions, 1/6)
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


### Q4: *"Did you cripple the models in `h1` with a stateless notes-only prompt, small output cap, or missing chat history?"*
- **No — we built a dedicated Lab-Standard Multi-Turn Harness (`h2`, `PLAN.md` §3.1) and published it as a separate leaderboard (`leaderboard_h2.json`, `/leaderboard?view=h2`):**
  1. **Every lab-standard advantage enabled in `h2`:** Full multi-turn conversation history, preserved reasoning across turns (Anthropic thinking blocks kept verbatim; OpenAI-compatible `reasoning_content` / Gemini thought signatures returned verbatim), native `act(action, hypothesis, belief)` tool calling (invalid calls cost a turn, not an action), leaderboard-standard `high`/`max` effort, generous `64k` / `32k` output token caps, provider-default sampling, and last-5 image frames + prompt caching — with zero hidden-rule leakage.
  2. **Empirical result (`data/derived/leaderboard_h2.json`):** Giving models `h2` substantially improves `d1–d2` performance (`Claude Haiku 5.5` `high` reaches **`0.827`** on `s900000`; `Gemini 3.1 Pro` `high` averages **`0.803`** across its first 2 `eval-v1` games), **yet frontier models still lose to first-attempt unassisted humans across the full multi-rule sets:**
     - On the full 6-game `eval-v1` `h2` subset (`d1–d3`), `Kimi K3.1 Pro` (`effort=max`, `76.4M` input tokens) scores **`0.671`** (`95% CI [0.541, 0.795]`, `33/36` levels, `50%` game wins, `0.436` on unseen rule pairs) vs **`Human 0.795`** (`100%` game win) and **`Optimal 1.000`**.
     - On 8-level `eval-v2` (`d4`, unseen rules), `Kimi K3.1 Pro` (`effort=max`, `h2`) drops to **`0.463`** (`95% CI [0.389, 0.537]`, `12/16` levels, **`0%` game wins**) vs **`Human 0.637`** (**`100%` game wins**, `16/16` levels).
  3. **Takeaway:** Stateless memory was *part* of the `d1` gap, which `h2` cleanly separates and quantifies — but causal hypothesis testing under novel rule composition (`d3–d4`) remains a genuine capability gap even under lab-standard multi-turn evaluation.

### Q5: *"Is your post-training reasoning transfer real, or just answer-format alignment / data contamination?"*
- **Our experimental design (`bench/PROTOCOL.md` v3, `FT_BENCHMARKS.md`, & `DECISIONS.md` Sat 20:50 / 21:15) pre-registers five controls specifically to separate genuine reasoning transfer from formatting or contamination:**
  1. **Step 0 Diagnostic Proof (`SFT v1`):** Fine-tuning `Qwen3.5-9B` on pure optimal action trajectories (`train-v1`, disjoint seeds from all eval sets) eliminated JSON parse errors (`0` invalid actions) yet scored **`0.012`** on held-out `eval-v1` (`1/36` synced levels; `4/180` across the 30-game sweep, `56.8%` wall-bump loops). Cloning optimal actions without causal discovery rationales fails completely.
  2. **Canonical `PROTOCOL v3` Rescorer (`posttrain.rescore_answer`):** Answer-trained models frequently emit `"ANSWER: X"` instead of lm-eval's `"the answer is (X)"`, causing regex `[invalid]` extractions. Our `PROTOCOL v3` rescorer accepts `"ANSWER: X"` only when the official regex returned `[invalid]` — changing **`0` items on `base`** while reporting both `v3` and raw official lm-eval numbers side-by-side (`official_mean` in `bench_summary.json` and `/leaderboard?view=bench`).
  3. **Documented Negative Result on CoT Suppression (Line 1) → Thinking-On GRPO Re-Plan (Line 2):** Even after `PROTOCOL v3` rescoring, Line 1 (`SFT v2` answer-only targets without `<think>`) dropped `Qwen3.5-9B` primary reasoning from **`~75.8%` (`base`) to `~44.1%` (`games`)** because SFT taught the model to emit `"ANSWER: X"` in ~10 tokens with zero Chain-of-Thought, and RL from that SFT checkpoint could not revive `<think>` (`0` exploration variance). Rather than hiding this, we report it plainly as a diagnostic finding and run **Line 2 (`think-games` vs `think-ctrl`)**: GRPO directly from `Qwen/Qwen3.5-9B` base with `<think>` ON (`enable_thinking=True`) against an equal-compute general-math/logic GRPO control (`think-ctrl`).
  4. **Negative Control (`MMLU-Pro: History`):** Alongside the 6-task Primary Far-Transfer Headline (`BBH 27-task`, `MATH`, `GSM8K`, `MedQA-USMLE`, `MMLU-Pro: Health`, `MMLU-Pro: Law`), we run `MMLU-Pro: History` (pure factual recall). If `History` rises as much as the primary suite, `bench_summary.json` flags the delta as formatting rather than reasoning.
  5. **Pre-Registered Honesty Claim Rule (`10,000` paired item-level bootstrap resamples, seed `20261114`):** We claim outside reasoning transfer **only** if a candidate (`think-games` / `mix` / `games`) beats its matched control (`think-ctrl` / `ctrl`) on the primary headline **and** on $\ge 2$ primary benchmarks with paired 95% CIs excluding zero while outpacing `MMLU-Pro: History`. Otherwise we report `HONEST NULL / IN-DOMAIN` and exact CIs without spin.

### Q6: *"Can an agent score high on a level by routing around the newly introduced mechanic instead of discovering and using it?"*
- **We audited every frozen level with an exact rule-avoider solver (`coordination/A7_AUDIT.md`, `engine/tools/interaction_audit.py`) and built dedicated mechanic-forcing and multi-loop generators (`gridforce` & `gridbranch`):**
  1. **Exact Audit of Frozen `gridworld` Collections:** Defining *avoider score* = `optimal_moves / shortest_win_without_triggering_rule` (`0` if impossible; *forced* = avoider score $\le 0.5$, i.e., avoiding costs $\ge 2\times$ optimal moves or is unsolvable), on `eval-v1` `28%` of use-rule pairs allowed a rule-ignoring path to score $\ge 0.8$ (concentrated in `one_way 91%`, `push_blocks 71%`, `remap 60%`, while `keys_doors`, `plates_gates`, `teleporters`, `phase_walls`, and `stamina` were already `0%` avoider $\ge 0.8$).
  2. **Forcing Generator (`gridforce`, `FORCE_VERSION 1`):** Enforces hard mechanic-forcing on every newly introduced rule (`K = 2.0`) while keeping existing frozen collections byte-identical (`135` engine tests pass):
     - Across `d1`, `d2`, `d3`, and `d4` (`140` generated games, `0` failures, median `0.7s–2.7s`/game), the **newly introduced mechanic is forced on `100%` of teaching levels (`112/112` on `eval-v3`)**, cutting overall use-rule avoider $\ge 0.8$ from `28%` (`eval-v1`) down to **`4%`** (and **`0%` on teaching levels**).
  3. **Multi-Path Branching Topology (`gridbranch`, `BRANCH_VERSION 1`):** Eliminates narrow single-corridor memorization by requiring planar wall-cluster cycles and non-cutpoint bypasses: increases **real loops/level from `1.1` → `4.0`**, cuts **linear levels from `10%` → `0%`**, raises optimal path depth `15.5` → `29.1` moves, and keeps **`106/106` (`100%`)** of new rules forced.

### Q7: *"Why do frontier models still fail on `d3–d4` even when `h2` gives them full multi-turn memory, native tools, and Chain-of-Thought?"*
- **We built a Truth-Diffed Reasoning Forensics auditor (`analysis/src/analysis/explain.py`, `explanations.json`, `/insights` + `/replay`) that diffs every `<think>` and scratchpad trace against hidden engine `truth` across `137` failed model runs:**
  1. **Why we diff CoT against engine truth:** Models routinely emit confident post-hoc rationalizations while hitting walls (`[NO_EFFECT]`) or miscounting coordinates. Pure LLM text-only grading gets fooled; diffing CoT claims against engine `events`, `active_rules`, and BFS `optimal_path` pinpoints the exact first divergence step (`first_divergence_step`) with a programmatically verified verbatim quote (`quote in step[quote_source]`).
  2. **Empirical `h1 → h2` shift & the `56.9%` Knowing–Doing Gap:**
     - Moving from stateless `h1` (`n=102`) to multi-turn `h2` (`n=35`) **eliminates Stage 1 coordinate/perception misreads (`61.8% → 0.0%`)**, proving `h2` fixed the stateless spatial-orientation bottleneck.
     - Yet across all `137` audited failures, **`56.9%` (`78/137`) explicitly articulate the active hidden mechanic in CoT/notes (`deduced_rule_in_cot = true`) at an earlier step (`deduced_rule_step < terminal_step`) and still fail** — shifting `h2` failures into **Stage 4 Spatial Rollout (`42.9%` `knew_rule_failed_rollout`)** and **Stage 3 Belief Updating (`34.3%` `ignored_falsifying_feedback`)**. Models can *name* a rule like `ice`, `conveyors`, or `twin` in prose far earlier than they can simulate its 2D state transitions forward over 15–30 steps.
