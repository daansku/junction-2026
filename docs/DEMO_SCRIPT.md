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
1. **Tab 1 — Deck v3 (`docs/deck/index.html`):** 11-slide narrative (`←` / `→` / `Space`; press `P` for fullscreen Present mode, `Esc` to exit; matches `docs/deck/SLIDES.md`).
2. **Tab 2 — Beat the AI Kiosk (`/challenge`):** Public zero-setup challenge (`gridworld-s900002-d3-l6-f09d6348` default — where our human tester beat every finished model — plus `s900000` quick mode & QR code for judges' phones).
3. **Tab 3 — Leaderboards (`/leaderboard` → `?view=h1`, `?view=h2`, `?view=bench`):** Stateless `h1` board, Lab-Standard Multi-Turn `h2` board with 95% CIs (finished runs only, cost-capped runs superseded once uncapped replacements land), and Post-Training & Reasoning Transfer (`PROTOCOL v3`, `Qwen3.5-9B`).
4. **Tab 4 — Truth-Diffed Reasoning Forensics + X-Ray Replay (`/insights` & `/replay/<run_id>`):** Cognitive Bottleneck Funnel (`56.9%` Knowing–Doing Gap across `137` audited failures), Rule × Player Discovery Matrix, interactive X-Ray curtain (`50%` split contrasting agent pixel view vs engine truth), `[ ↯ JUMP TO DIVERGENCE ]`, and `[ TAKE OVER FROM STEP N ]`.
5. **Tab 5 — Terminal (`harbor run` + `check-claims`):** Live Harbor Docker sidecar proof (`oracle = 1.000`, `nop = 0.000`, `9/9` red-team = `0.000`).

---

## Beat-by-Beat Run of Show (10 Minutes — Aligned to 11-Slide Deck v3 & `PLAN.md` §3.5)

| Time | Screen | Presenter Action & Exact Spoken Point |
|---|---|---|
| **0:00 – 2:15** | **Tab 1 (Slides 1–3: Game Factory, Problem & Environment)** | *"Static benchmarks that leak into training measure memory, not causal discovery. Our factory generates unlimited, search-verified 64×64×16 pixel games across 21 composable mechanics (`engine 0.6.0`, `2,035` training games, `60` frozen test games), permutes colours per seed, and gives zero words of instruction — every level introduces one rule that you must discover from interaction."* |
| **2:15 – 4:15** | **Tab 1 (Slide 4) → Tab 2 (`/challenge` — Live "Beat the AI" Demo)** | Point to the QR code on Slide 4 / `/challenge` so judges can play on their phones simultaneously (`no login, zero API cost`). Play 1 level of `s900002` (`d3`) or `s900000` (`d1`) live. When the level clears, show the **side-by-side 4 moves/s AI ghost reels** revealing how frontier models fared on that exact level. |
| **4:15 – 6:15** | **Tab 1 (Slides 5–6) & Tab 3 (`/leaderboard` → `h1` then `?view=h2`)** | **Slide 5 (`h1`, `eval-v2`):** `Optimal = 1.000`; unassisted humans (`~0.682–0.693`) beat every finished full-sweep model (`Gemini 4 Argon 0.452–0.494`, `Kimi K3.1 Pro 0.219`, `Gemini Flash 0.071`, text-only `[rle]` = `0.000`), with `Gemini 4 Carbon` as the sole frontier contender currently ahead on its first 3 `eval-v2` games (`0.749`, sweep in flight — check final row after the 07:00 lock). **Slide 6 (`?view=h2` — Lab-Standard Multi-Turn):** *"Did `h1` cripple the models? We built `h2`: full multi-turn history, preserved thinking blocks, native tools, `high`/`max` effort, `64k`/`32k` caps. Easy `d1` games close (`98–131` moves vs `86–92` optimal), yet on `eval-v2` novel rule compositions humans still beat every `h2` model (`Human 0.661`, `4/4` wins vs `Gemini 3.1 Pro high 0.439` and `Kimi K3.1 Pro max 0.398`, `0/4` wins each)."* |
| **6:15 – 7:30** | **Tab 1 (Slide 7) → Tab 4 (`/insights` → `/replay` X-Ray & Divergence)** | Show Slide 7 (`50%` zero-change wall-bumps, `44%` late resets) plus `/insights` **Truth-Diffed Reasoning Forensics**: `h1 → h2` cuts Stage 1 coordinate misreads `61.8% → 0.0%`, exposing a **`>55%` Knowing–Doing Gap** — models explicitly deduce the hidden rule in `<think>` yet fail multi-step spatial rollout. Click into `/replay`, hit **`[ ↯ JUMP TO DIVERGENCE ]`**, and drag the **X-Ray curtain** across the 64×64 canvas to compare verbatim CoT quote vs engine truth. |
| **7:30 – 8:15** | **Tab 1 (Slide 8) & Tab 5 (Reward Integrity + Forcing Audit)** | Show `make judge` / Harbor verification: `oracle = 1.000`, `nop = 0.000`, `STOP_AFTER_LEVELS=1 = 0.125` (`eval-v2` l8) / `0.167` (`eval-v1` l6), `OpenCode + Nemotron = 0.067`, and **9/9 inside-container attacks = `0.000`**. Highlight A7's mechanic-forcing audit (`gridforce` forces the new mechanic on **`100%` of teaching levels** vs `28%` avoider bypass on `eval-v1`, with `gridbranch` adding `4.0` real loops/level and `0%` linear corridors). |
| **8:15 – 9:15** | **Tab 1 (Slide 9) & Tab 3 (`?view=bench` — Post-Training & Honesty Rule)** | Walk through `Qwen3.5-9B` (`PROTOCOL v3`, `ANSWER: X` rescorer with raw lm-eval numbers inline): **Step 0 (`SFT v1`)** solved `4/180` `eval-v1` levels (`0.012`), proving optimal-action cloning without discovery rationales fails. **Line 1 (`SFT v2` answer-only)** exposed a sharp negative result: suppressing `<think>` dropped primary reasoning `~75.8% → ~44.1%`. **Line 2 (`think-gridbranch` / `think-games` vs `think-ctrl`)** runs Thinking-On GRPO directly from base on `gridbranch` multi-loop worlds under our pre-registered 10,000-resample Honesty Claim Rule. |
| **9:15 – 10:00** | **Tab 1 (Slides 10–11: Business Value & "Try to Break It")** | Present the 3 commercial wedges (`docs/BUSINESS.md`: **1. Contamination-Proof Lab Eval & Post-Training Gym**, **2. Pre-Deployment Agent Sanity Gate**, **3. Procedural Verified Training Data & Levels**) and open Slide 11's **15-minute live judge exploit hunt**. |

---

## Network & Live-Demo Fallback Protocol (`PLAN.md` §3.5)

1. **If venue Wi-Fi / Verda tunnel drops:**
   - Run local full stack immediately (`make dev` / `make server PORT=8000` serving synced `data/derived/*.json` and `web/public/challenge/*.json` — `/challenge` plays 100% client-side in TypeScript via `engine.ts` with zero server round-trips!).
   - Or append `?api=mock` to any web route (`data/fixtures/` + bundled static assets).
2. **If projector / live browser session stalls:**
   - Play A4's captured 1080p H.264 screen recordings in `web/screenshots/video/` (`challenge-full-run.mp4` 57 s — note explicitly it is a scripted optimal flow demo, not a human score — `replay-argon.mp4` 31 s, `live-wall.mp4` 23 s) or A6's standalone 2–3 minute rendered **Manim presentation video** (`video/` MP4) alongside local `docs/deck/index.html` (zero external fonts or CDN dependencies).
3. **If external model APIs throttle during the 15-minute judge rerun:**
   - Run local Docker Harbor baselines (`oracle`, `nop`, `redteam`) immediately (`0` network calls), or point Harbor OpenCode at our dedicated Verda GPU vLLM endpoint.
