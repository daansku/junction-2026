# Pitch Narrative — AfterQuery @ Junction 2026 (`docs/PITCH.md`)

> **Duration target:** 10 minutes live (demo + architecture + Harbor rubric proof) followed by 15-minute live judge exploit hunt.
> **Core thesis:** Frontier agents do not fail novel environments because they lack syntax or arithmetic — they fail **2D spatial perception and inductive world-modeling under scarce action budgets**: acting on premature hypotheses across hidden mechanics, burning moves on zero-diff wall collisions, and resetting too late.

---

## 1. The Problem We Chose to Measure (0:00 – 1:30)

AfterQuery asked for an RL environment where a strong reference run beats today's best agents, mistakes are meaningful and debuggable, and rewards cannot be hacked.

Static text and puzzle benchmarks leak in two ways:
1. **Prose gives away the causal graph:** Telling an LLM *"blue tiles are ice and keys unlock doors"* reduces scientific discovery to English reading comprehension.
2. **Fixed layouts & palettes get memorized:** Static colours (`green = goal`, `red = lava`) and seen rule combinations reward recall rather than online experimentation.

Our **Game Factory (`engine 0.5.0`)** generates unlimited, seed-reproducible 64×64 pixel curriculum games:
- **Zero prose instructions:** Agents see only a 16-color indexed frame (`rows 0–1`: shrinking move-budget bar, `rows 3–4`: level & inventory/health pips, `rows 6–63`: playfield) and act with `RESET` / `ACTION1..5`.
- **Per-game `skin_shuffle`:** Object colours and non-directional shapes permute per game seed.
- **15 live mechanics + graduated 6-level curriculum (`rules/CATALOG.md`):** Level 1 teaches basic navigation; Levels 2–5 introduce one new hidden mechanic at a time (`keys_doors`, `plates_gates`, `teleporters`, `hazards`, `push_blocks`, `ice`, `one_way`, `collect_all`, `phase_walls`, `rotation`, `remap`, `twin`, `stamina`, `cracked_floor`, `beacon_goal`); Level 6 is a multi-rule exam — and `eval-v1` holds out unseen rule pairs and disjoint skins.

---

## 2. Why Every Failure Is Fair & Meaningful (`Meaningful Difficulty` — 30 pts) (1:30 – 3:30)

Every generated level passes four mathematical gates before any player sees it:
1. **Exact BFS Solvability:** Produces `optimal_moves` and `optimal_path` (`Optimal` baseline = `1.000`).
2. **Rule-Necessity Ablation:** Disabling any active rule changes `optimal_moves` or breaks solvability — zero decorative clutter.
3. **Bounded Exploration Slack:** `move_budget = ceil(optimal_moves × slack)` gives humans and agents fair room to test a hypothesis once, while punishing blind thrashing.
4. **Random-Walk Rejection:** Any candidate level where random walk wins ≥ 2% of trials is discarded (`random` scores `0.000` across `48` `dev` levels).

---

## 3. Reward Integrity Inside Isolated Harbor Sidecars (`Reward Integrity` — 25 pts) (3:30 – 5:30)

Each level is scored by ARC-AGI-3 action efficiency, averaged across **all** `levels_total` levels of the game:

$$\text{level\_score}(L) = \begin{cases} \min\!\left(1.0,\; \dfrac{\text{optimal\_moves}(L)}{\text{actions\_used}(L)}\right) & \text{if level } L \text{ is solved} \\ 0.0 & \text{if level } L \text{ is not solved} \end{cases}$$

Verified directly on the judges' **Harbor 0.26.0 + Docker** harness (`arena/HARBOR.md`, `coordination/JUDGING.md`):
- **Sidecar isolation:** `game-server` runs in a separate container exposing only `observe()` and `act()` over MCP; `/evidence/score.json` is inaccessible to the agent container and graded in a separate verifier container after agent termination.
- **Do-nothing (`harbor run -a nop`):** **`0.000`** (`0` actions, `0/6` levels).
- **Stop-early (`ORACLE_STOP_AFTER_LEVELS=1` / `=3`):** **`0.167`** (`1/6` levels) and **`0.500`** (`3/6` levels); stopping before solving Level 1 (`arena stop_early`) scores **`0.000`**.
- **Reset farming:** `actions_used(L)` accumulates pre-reset steps plus `RESET` itself — resetting never erases exploration cost.

---

## 4. The Measured Gap Across Harbor & Live Sweeps (`The Gap` — 30 pts) (5:30 – 8:30)

1. **On the Judges' Harbor + OpenCode Harness (`gridworld-s1000-d1-l6-9b1065f8`):**
   - **Reference (`oracle`):** **`1.000`** (`6/6` levels, `92` actions).
   - **OpenCode + Nemotron 3.5 Super VL (`k=3` rubric runs):** `0.020`, `0.094`, `0.087` → **mean `0.067`** (`1/6` levels solved per 30-min run; `0.113` / `2/6` levels in 15-min run).
2. **Across Our 67-Run Multi-Model `dev` Benchmark (`data/derived/leaderboard.json`):**
   - **BFS Optimal:** **`1.000`** (`24/24` levels, `100.0%`).
   - **First-Attempt Humans:** **`0.578`** on `dev` (`40/60` levels, `66.7%`, `40%` full-game wins) and **`0.795`** on `eval-v1`.
   - **Kimi K3.1 Pro (`[image, rle]`):** **`0.374`** (`25/48` levels, `52.1%`, `0%` full-game wins, `RHAE = 0.647` vs human).
   - **Nemotron 3.5 Super VL (`[image, rle]`):** **`0.061`** (`6/48` levels, `12.5%`, `76.8%` no-effect rate).
   - **DeepSeek V3.2 & `gpt-oss-120b` (`[rle]` text-only):** **`0.000`** (`0/96` levels — proving lossless text RLE alone fails without 2D visual spatial grounding).

And our **LENS** diagnostics (`analysis/`) close the loop: `auto-01..03` (`cracked_floor`, `collect_all`, `twin`) were generated from trace failures and shipped into Engine `0.5.0` (where `twin` drove model intro solve rate to `0.0%`), and `auto-04` promotes Tier-3 post-move drift/timing (`conveyors`, `enemies`, `gravity`) into `eval-v2`.

---

## 5. One-Command Reproducibility (`Craft` — 15 pts) (8:30 – 10:00)

From a clean checkout, one command exports Harbor tasks (`python -m arena harbor-export`), runs `oracle`, `nop`, `stop-early`, and `opencode` in isolated Docker containers, and `python -m analysis check-claims` enforces schema and reward-integrity invariants across every chart and insight card.
