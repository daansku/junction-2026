# Live Demo Choreography (`docs/DEMO_SCRIPT.md`)

> **Total presentation slot:** 10 minutes + 15-minute live judge exploit hunt & Harbor/OpenCode rerun.
> **Rule:** Never show a static claim where `/challenge`, `/replay/<run_id>?step=<step>`, `/leaderboard?view=h2`, or `harbor run` shows real ground-truth behavior. Every spoken number traces to `data/derived/*.json` (`python -m analysis check-claims`).

---

## Pre-Demo Verification Checklist (T-15 min)

```bash
# 1. Sync latest runs from shared server, rebuild derived analytics, and verify claims (0 errors)
PYTHONPATH="analysis/src;engine/src" python -m analysis sync
PYTHONPATH="analysis/src;engine/src" python -m analysis build
PYTHONPATH="analysis/src;engine/src" python -m analysis check-claims --derived data/derived
PYTHONPATH="analysis/src;engine/src" python -m analysis check-claims --derived data/fixtures/derived

# 2. Verify Harbor task export & lint (official judging path)
python -m arena harbor-export --collection eval-v1 --out /tmp/junction-harbor --first 2
harbor lint /tmp/junction-harbor/gridworld-*

# 3. Verify web bundle compiles cleanly
cd web && npm run typecheck && npm run build
```

Keep 5 browser tabs pre-loaded (`110%` zoom on dark display):
1. **Tab 1 — Deck v2 (`docs/deck/index.html`):** 9-slide narrative (`←` / `→` / `Space`).
2. **Tab 2 — Beat the AI Kiosk (`/challenge`):** Public zero-setup challenge (`gridworld-s900002-d3-l6-f09d6348` default — where our human tester beat every finished model — plus `s900000` quick mode & QR code for judges' phones).
3. **Tab 3 — Leaderboards (`/leaderboard` → `?view=h1`, `?view=h2`, `?view=bench`):** Stateless `h1` board, Lab-Standard Multi-Turn `h2` board with 95% CIs, and Post-Training & Reasoning Transfer (`Qwen3.5-9B`).
4. **Tab 4 — Failure Replay + X-Ray (`/replay/<run_id>` & `/insights`):** Interactive X-Ray curtain (`50%` split contrasting agent pixel view vs engine truth), Rule × Player Discovery Matrix, and `[ TAKE OVER FROM STEP N ]`.
5. **Tab 5 — Terminal (`harbor run` + `check-claims`):** Live Harbor Docker sidecar proof (`oracle = 1.000`, `nop = 0.000`, `9/9` red-team = `0.000`).

---

## Beat-by-Beat Run of Show (10 Minutes — Matches `PLAN.md` §3.5)

| Time | Screen | Presenter Action & Exact Spoken Point |
|---|---|---|
| **0:00 – 1:00** | **Tab 1 (Slides 1–2: Problem & Environment in 30s)** | *"Static text benchmarks test reading comprehension and memorized priors. Our factory generates unlimited, BFS-verified 64×64×16 pixel games across 18 composable mechanics (`engine 0.5.0`), permutes colours per seed, and gives zero text instructions — every level adds one causal rule."* |
| **1:00 – 2:45** | **Tab 2 (`/challenge` — Live "Beat the AI" Demo)** | Point to the on-screen QR code so judges can play on their phones/laptops simultaneously (`no login, zero API cost`). Play Level 1–2 of `s900002` (`d3`) or `s900000` (`d1`) live in 45 seconds. When the level clears, show the **side-by-side 4 moves/s AI ghost reels** revealing how `Kimi K3.1 Pro`, `Gemini`, and `Nemotron` fared on that exact level. |
| **2:45 – 4:30** | **Tab 3 (`/leaderboard` → `h1` then `?view=h2`)** | **Show `h1` first:** `Optimal = 1.000`, `Human = 0.795` (`eval-v1`), `Kimi K3.1 Pro = 0.374` (`dev`), `Nemotron = 0.061`, text-only `[rle]` `DeepSeek V3.2` / `gpt-oss-120b = 0.000`. **Then click `h2 · Lab-Standard Multi-Turn`:** *"Did `h1` handicap the models? We built `h2`: full multi-turn history, preserved thinking blocks, `high`/`max` effort, `64k`/`32k` token caps. Models jump on `d1–d2` (`Haiku 0.827`, `Gemini 3.1 Pro 0.803`), yet across the full 6-game `eval-v1` subset `Kimi K3.1 Pro (max)` scores `0.671` vs `Human 0.795`, and on 8-level `eval-v2` drops to `0.463` (`0%` game wins) vs `Human 0.637` (`100%` wins)."* |
| **4:30 – 6:00** | **Tab 4 (`/insights` → `/replay` with X-Ray Curtain)** | Click a failure cell (`twin = 0%` intro solve, `zero_change_wall_bump` / `late_reset`) into `/replay`. Drag the **X-Ray split curtain** across the 64×64 canvas: left side shows raw pixels the agent saw; right side reveals active rules, BFS optimal path, and the exact verbatim `hypothesis` where the agent locked onto a false causal belief. |
| **6:00 – 7:15** | **Tab 5 (Terminal & Slide 6: Reward Integrity)** | Show `harbor run` + our **9/9 inside-container Red-Team Suite = `0.000`** (`forge /evidence/score.json`, `/logs/verifier/reward.txt`, port scan, MCP fuzzing, `2,000` `RESET` spam, wall-cycle spam). `oracle = 1.000`, `STOP_AFTER_LEVELS=1 = 0.167`, `nop = 0.000`. |
| **7:15 – 8:45** | **Tab 3 (`?view=bench` — Post-Training & Transfer)** | Walk through our `Qwen3.5-9B` post-training experiment: **Step 0 (`SFT v1`)** proved pure optimal-action cloning learns JSON syntax (`0` parse errors) but fails causal discovery (`0.012` on `eval-v1`, `56.8%` wall-bumps). Show `SFT v2` (`ctrl` vs `games` vs `mix`, token-matched with `<think>` causal rationales + A1 verifiable world-model tasks + GRPO) and our **Pre-Registered Honesty Claim Rule** (`FT_BENCHMARKS.md` 6-task headline + `MMLU-Pro: History` negative control + 10,000-resample paired CIs). |
| **8:45 – 10:00** | **Tab 1 (Slides 8–9: Business Value & Ask)** | Present the top 3 evidence-backed commercial wedges (`docs/BUSINESS.md`: **1. Contamination-Proof Frontier Lab Eval & Post-Training Gym**, **2. Pre-Deployment Sanity Gate for Tool-Using Agents**, **3. Procedural Mid-Training Data Engine**) and open the 15-minute live judge exploit hunt. |

---

## Network & Live-Demo Fallback Protocol (`PLAN.md` §3.5)

1. **If venue Wi-Fi / Verda tunnel drops:**
   - Run local full stack immediately (`make dev` / `make server PORT=8000` serving synced `data/derived/*.json` and `web/public/challenge/*.json` — `/challenge` plays 100% client-side in TypeScript via `engine.ts` with zero server round-trips!).
   - Or append `?api=mock` to any web route (`data/fixtures/` + bundled static assets).
2. **If projector / live browser session stalls:**
   - Play A4's captured 1080p H.264 screen recordings in `web/screenshots/video/` (`challenge-full-run.mp4` 57 s — note explicitly it is a scripted optimal flow demo, not a human score — `replay-argon.mp4` 31 s, `live-wall.mp4` 23 s) or A6's standalone 2–3 minute rendered **Manim presentation video** (`video/` MP4) alongside local `docs/deck/index.html` (zero external fonts or CDN dependencies).
3. **If external model APIs throttle during the 15-minute judge rerun:**
   - Run local Docker Harbor baselines (`oracle`, `nop`, `redteam`) immediately (`0` network calls), or point Harbor OpenCode at our dedicated Verda GPU vLLM endpoint.
