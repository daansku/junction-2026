# Presentation Deck v2 (`docs/deck/SLIDES.md`)

> Standalone interactive deck: open `docs/deck/index.html` in any browser (`←` / `→` / `Space` / `Home` / `End`).
> Structure follows `PLAN.md` §3.5: **Problem → Environment in 30s → Live Demo (`/challenge`) → The Gap (`h1` then `h2`) → Meaningful Failures (`/replay` + X-Ray) → Reward Integrity (`9/9` Red-Team = `0.000`) → Post-Training & Transfer (`Qwen3.5-9B` + Honesty Rule) → Business Value → Ask**.
> Every number traces to `coordination/JUDGING.md` and `data/derived/{leaderboard,leaderboard_h2,bench_summary,rules,insights,decision_points}.json` (`python -m analysis check-claims`, `0` errors).

---

## Slide 1 — Problem: Static Agent Benchmarks Leak
- **Headline:** Games No Model Has Seen Before.
- **Core problem:** Instruction-heavy benchmarks test reading comprehension and memorized training priors (`green = goal`, `red = lava`), whereas deployed agents fail when APIs, UIs, or physical systems change rules silently without a manual.
- **Headline KPIs:** `64×64×16` pixels-only observation · `18` composable rules · `1.000` BFS optimal ceiling · `0.000` across `9/9` red-team exploit attacks.

## Slide 2 — The Environment in 30 Seconds (`engine 0.5.0`)
- **Visual contact sheet:** `rules/img/all_rules.png` (`18` deterministic mechanics across Tier 0–3).
- **Zero prose, zero score leakage:** Agents see only a `64×64` indexed frame (`rows 0–1` shrinking budget bar, `rows 3–4` level & state pips, `rows 6–63` playfield) with per-seed `skin_shuffle: true` and held-out rule pairs + skins in `eval-v1` and `eval-v2`.
- **4 Mathematical Proofs per Generated Level:** Exact BFS shortest path (`optimal_moves`), single-rule necessity ablation, bounded exploration slack, and `< 2%` random-walk win ceiling (`100` rollouts).

## Slide 3 — Live Demo: Beat the AI (`/challenge`)
- **Public zero-setup kiosk:** Visitors & judges play the exact held-out game in-browser (`gridworld-s900002-d3-l6-f09d6348` default — where our human tester beat every finished model — plus `s900000` quick mode & mobile QR).
- **Zero spoiler bias, instant comparison:** Runs 100% client-side (`engine.ts`, zero paid API calls, isolated from benchmark tables via `loader.py` hygiene filter). Clearing a level reveals `4 moves/s` side-by-side AI ghost replays (`Kimi`, `Gemini`, `Nemotron`) on that exact level.

## Slide 4 — The Gap: `h1` Board, Then `h2` Lab-Standard Board
- **Left — `h1` Stateless Rolling-Notes & Harbor Rubric (`leaderboard.json`):**
  - `Optimal`: **`1.000`** · `Human`: **`0.795`** (`eval-v1`) / **`0.630`** (`eval-v2`, `5` games) / **`0.606`** (`dev`, `23` games)
  - `Harbor 0.26 + OpenCode + Nemotron` (`k=3`): **`0.067`** mean (`0.020`, `0.094`, `0.087`)
  - `Kimi K3.1 Pro` (`dev`, `8` games): **`0.374`** (`52.1%` levels, `0%` game wins)
  - `DeepSeek V3.2` / `gpt-oss-120b` (text-only `[rle]`): **`0.000`** (`0/96` levels despite lossless 64×64 RLE)
- **Right — `h2` Lab-Standard Multi-Turn (`leaderboard_h2.json`, *"Even run the lab way, they lose"*):**
  - Full multi-turn history, preserved thinking blocks, native `act()` tool, `high`/`max` effort, `64k`/`32k` token cap, last-5 frames + caching, 95% bootstrap CIs:
  - `eval-v1` (`d1–d2` partial subsets): `Claude Haiku 5.5 (high)` **`0.827`** (`1/6` games) · `Gemini 3.1 Pro (high)` **`0.803`** (`2/6` games, `95% CI [0.732, 0.874]`).
  - `eval-v1` (full `6/6` `h2` subset incl. `d3`): `Kimi K3.1 Pro (max)` **`0.671`** (`95% CI [0.541, 0.795]`, `50%` wins, `0.436` unseen pairs) vs **`Human 0.795`** (`100%` win).
  - `eval-v2` (`d4`, 8 levels, unseen rules): `Kimi K3.1 Pro (max)` **`0.463`** (`95% CI [0.389, 0.537]`, **`0%` game wins**) vs **`Human 0.637`** (**`100%` game wins**).

## Slide 5 — Why Failures Are Meaningful (`/replay` + X-Ray Curtain)
- **Pinpointed Epistemic Bottlenecks (`rules.json`, `explanations.json`, `decision_points.json`):**
  - **Zero-change wall/state loops (`46.9%` of decision points):** Agents repeat falsified actions when hidden constraints (`one_way`, `phase_walls`, `twin`) block movement.
  - **Delayed resets (`42.1%` of decision points):** Agents burn `>1.5× optimal_moves` in dead-ends (`cracked_floor`, `push_blocks`) instead of resetting early.
  - **Interactive X-Ray Forensics:** Dragging the `/replay` X-Ray split curtain contrasts raw agent pixels against ground-truth rule sprites, BFS optimal paths, and verbatim false `hypothesis` quotes.

## Slide 6 — Reward Integrity (`Harbor 0.26` + `9/9` Red-Team = `0.000`)
- **Action-efficiency formula:** $\text{level\_score}(L) = \min(1.0,\; \text{optimal\_moves}(L) / \text{actions\_used}(L))$ if solved else $0.0$, averaged over all `levels_total` levels (pre-reset steps + `RESET` included).
- **Verified Harbor Baselines:** `oracle = 1.000` (`6/6`), `STOP_AFTER_LEVELS=3 = 0.500`, `STOP_AFTER_LEVELS=1 = 0.167`, `nop = 0.000`.
- **Inside-Container Red-Team (`9/9 -> 0.000`):** Forging `/evidence/score.json` & `/logs/verifier/reward.txt`, disk/env recon, port scan, unknown MCP tools, malformed actions, session-reset bypass, 32-way race, `2,000× RESET` spam, `3,100×` wall-cycle spam all score **`0.000`**.

## Slide 7 — Post-Training & Reasoning Transfer (`Qwen3.5-9B`)
- **Step 0 Proof (`SFT v1`, `bench_summary.json`):** Pure optimal-action cloning on disjoint `train-v1` achieved `0` JSON parse errors yet solved **`1/36` synced levels (`0.012`, `56.8%` wall-bumps; `4/180` on 30-game sweep)** on `eval-v1` — proving action imitation without causal discovery fails.
- **Controlled Post-Training Ladder (`SFT v2` + `GRPO`):** Token-matched `ctrl` (Tulu-3 reasoning) vs `games` (Narrator `<think>` causal rationales + A1 verifiable world-model tasks: `next_frame`, `rule_induction`, `solvable_in_k`, weighted by `decision_point_targets.json`) vs `mix`, followed by engine-verified GRPO.
- **Pre-Registered Honesty Claim Rule (`FT_BENCHMARKS.md`):** `10,000`-resample paired item-level bootstrap CIs across 6 Primary Far-Transfer tasks (`BBH`, `MATH`, `GSM8K`, `MedQA`, `MMLU-Pro Health & Law`) + `MMLU-Pro: History` negative control. Transfer is claimed **only** if `cand > ctrl` on headline + `≥2` primary benchmarks (`95% CI > 0`) while outpacing `History`.

## Slide 8 — Business & Real-World Value (`docs/BUSINESS.md` Top 3)
1. **Contamination-Proof Frontier Lab Eval & Post-Training Gym:** Fresh private seed splits + Harbor MCP sidecars (`9/9` red-team = `0.000`) + engine-verified RL environments that never saturate across training cutoffs.
2. **Pre-Deployment Sanity Gate for Tool-Using Agents:** Catches zero-effect action loops (`46.9%` of failures) and sunk-cost refusal to reset (`42.1%`) before agents burn enterprise API/cloud budgets.
3. **Procedural Mid-Training Data Engine:** Unlimited BFS-verified state-transition & causal-induction traces (`engine/tasks`) where `SFT v1` (`0.012`) proved raw trajectory cloning fails without explicit state rationales.

## Slide 9 — Ask & 15-Minute Live Exploit Hunt
- **One-Command Harbor Reproduction (`arena/HARBOR.md`):** `harbor run -p harbor/eval-v1/gridworld-s900000-d1-l6-33a57ce4 -a oracle | nop | opencode`.
- **Live Interactive Suite:** `/challenge` (QR live play) · `/leaderboard` (`h1`, `h2` Lab-Standard, `bench` Post-Training) · `/insights` · `/replay` (X-Ray + Take-Over).
- **Automated Audit:** `9/9` analysis unit tests passing + `python -m analysis check-claims` `0` errors across all `7` derived artifacts.
