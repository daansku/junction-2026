# Presentation Deck Outline (`docs/deck/SLIDES.md`)

> Standalone interactive deck: open `docs/deck/index.html` in any browser (`←` / `→` / `Space` / `Home` / `End`).
> Every number in this deck traces directly to `coordination/JUDGING.md` and `data/derived/{leaderboard,rules,insights}.json` (verified by `python -m analysis check-claims --derived data/derived`, `0` errors).

---

## Slide 1 — Title: Games No Model Has Seen Before
- **Headline:** Can AI Agents Discover Hidden Game Rules Without Text Instructions?
- **Subtitle:** procedurally seeded 64×64 pixel environments · 18 composable mechanics · Harbor MCP sidecar isolation · action-efficiency scoring
- **KPIs:** `64×64×16` pixels-only observation · `1.000` BFS optimal ceiling · `0.067` OpenCode+Nemotron Harbor mean (`k=3`) · `0.000` `noop` / `stop_early`.

## Slide 2 — Why Static Agent Benchmarks Leak
- **Text priors bypass discovery:** English prompts turn world-modeling into reading comprehension.
- **Static levels & colours get memorized:** Fixed palettes (`green = goal`, `red = lava`) leak across training cutoffs.
- **Our factory (`engine 0.5.0`):** Zero prose instructions. Only a 64×64×16 frame (`rows 0–1`: shrinking budget bar, `rows 3–4`: level & state pips, `rows 6–63`: playfield) with `skin_shuffle: true` per seed and held-out rule pairs + skins in `eval-v1`.

## Slide 3 — Engine `0.5.0` & 18 Composable Mechanics (`Meaningful Difficulty`: 30 pts)
- **Visual contact sheet:** `rules/img/all_rules.png` (18 rules rendered on 6×6 teaching grids).
- **15 Live Curriculum Mechanics:** Tier 0 (`walls`, `goal`, `move_budget`), Tier 1 (`keys_doors`, `plates_gates`, `teleporters`, `hazards`, `push_blocks`, `ice`, `one_way`), Tier 2 (`collect_all`, `phase_walls`, `rotation`, `remap`, `twin`, `stamina`, `cracked_floor`, `beacon_goal`), plus 3 Tier-3 mechanics (`conveyors`, `enemies`, `gravity`) ready for `eval-v2`.
- **4 Mathematical Fairness Proofs per Level:** BFS shortest path (`optimal_moves`), rule-necessity ablation, bounded slack (`ceil(optimal_moves × slack)`), and `< 2%` random-walk win ceiling.

## Slide 4 — Reward Integrity Verified in Harbor (`Reward Integrity`: 25 pts)
- **Scoring formula (`analysis/METRICS.md`):**
  $$\text{level\_score}(L) = \min(1.0,\; \text{optimal\_moves}(L) / \text{actions\_used}(L)) \text{ if solved else } 0.0$$
  averaged across all `levels_total` levels (`1..6`).
- **Harbor Docker Sidecar Isolation (`arena/HARBOR.md`, `gridworld-s1000-d1-l6-9b1065f8`):**
  - `harbor run -p <task> -a oracle` (`92` actions, `6/6` levels) → **`1.000`**
  - `harbor run -p <task> -a oracle --ae ORACLE_STOP_AFTER_LEVELS=3` (`45` actions, `3/6` levels) → **`0.500`**
  - `harbor run -p <task> -a oracle --ae ORACLE_STOP_AFTER_LEVELS=1` (`13` actions, `1/6` levels) → **`0.167`**
  - `harbor run -p <task> -a nop` (`0` actions, `0/6` levels) → **`0.000`**
- **Container & Reset Guards:** `game-server` exposes only `observe` and `act` over MCP; `/evidence/score.json` is graded in a separate verifier container after stopping the agent; `actions_used(L)` accumulates pre-reset actions + `RESET`.

## Slide 5 — The Gap: Harbor Rubric + 67-Run Multi-Model Sweep (`The Gap`: 30 pts)
- **Judges' Harness (`Harbor 0.26.0 + OpenCode + Nemotron 3.5 Super VL`, `k=3` rubric runs):**
  - Attempt A: `0.020` (`155` act, `1/6`) · Attempt B: `0.094` (`135` act, `1/6`) · Attempt C: `0.087` (`227` act, `1/6`) → **mean `0.067`** vs **`oracle 1.000`** (`+ 0.113` / `2/6` in 15-min run).
- **Live Arena `dev` Sweep (`data/derived/leaderboard.json`, Engine `0.5.0`):**
  - `Optimal` (`baseline`): **`1.000`** (`24/24` levels, `100.0%`)
  - `Human` (`image`, `10` dev games): **`0.578`** (`40/60` levels, `66.7%`, `40%` game wins; **`0.795`** on `eval-v1`)
  - `Kimi K3.1 Pro` (`image+rle`, `8` games): **`0.374`** (`25/48` levels, `52.1%`, `0%` game wins, `RHAE = 0.647`)
  - `Nemotron 3.5 Super VL` (`image+rle`, `8` games): **`0.061`** (`6/48` levels, `12.5%`, `76.8%` no-effect rate)
  - `DeepSeek V3.2` (`rle`, `8` games): **`0.000`** (`0/48` levels, `$0.069/game`)
  - `gpt-oss-120b` (`rle`, `8` games): **`0.000`** (`0/48` levels, `$0.193/game`)
  - `Random` / `Stop Early` / `Noop`: **`0.000`** (`0/120` levels)

## Slide 6 — Modality Gap & Step-Level Failure Forensics
- **Vision + RLE vs Text-Only RLE (`modality-gap`):** Under identical `h1` tool semantics, multimodal `[image, rle]` reaches `52.1%` level solve (`Kimi K3.1 Pro`), whereas text-only `[rle]` solves **`0/96` levels** despite receiving lossless 64×64 run-length grids.
- **Pinpointed Failure Modes (`rules.json` & `/insights`):**
  - `no_effect_loop`: `2,532` zero-diff / wall-bump steps (`51.3%` mean model no-effect rate, `@step 16`).
  - `late_reset`: `153` delayed reset episodes burning budget deep into dead-ends (`@step 51`).
  - `twin` bottleneck: `0.0%` model intro solve rate on coupled dual-body movement (`39` budget-exhausted runs).

## Slide 7 — Closed-Loop Curriculum Evolution (`eval-v1` → `eval-v2`)
- **Iteration 1 (Shipped in Engine `0.5.0`):** `analysis` generated `auto-01..03` (`cracked_floor`, `collect_all`, `twin`); A1 implemented all three (`twin` immediately became the `0.0%` intro-solve bottleneck).
- **Iteration 2 (`auto-04-eval-v2-tier3-drift-and-timing.md`):** Promotes A1's verified Tier-3 post-move mechanics (`conveyors`, `enemies`, `gravity`) into `eval-v2` to test two-phase drift and `WAIT` parity while keeping `eval-v1` frozen.

## Slide 8 — One-Command Harbor Reproduction & Live Suite (`Craft`: 15 pts)
- **Official Harbor Judge Commands (`arena/HARBOR.md`):** `python -m arena harbor-export`, `harbor run -p "$TASK" -a oracle | nop | opencode`.
- **Verification Gates:** `7/7` analysis unit tests passing, `check-claims` `0` errors on both `data/derived` and `data/fixtures/derived`, strict TypeScript + Vite web suite (`/play`, `/gallery`, `/compare`, `/live`, `/leaderboard`, `/insights`, `/replay`).
