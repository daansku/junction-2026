# Live Demo Choreography (`docs/DEMO_SCRIPT.md`)

> **Total demo slot:** 10 minutes + 15-minute live judge exploit hunt & Harbor/OpenCode rerun.
> **Rule:** Never show a static claim where a live `/replay/<run_id>?step=<step>`, `/compare`, or Harbor CLI check shows real ground-truth behavior.

---

## Pre-Demo Verification Checklist (T-15 min)

```bash
# 1. Sync latest runs from shared server, rebuild derived analytics, and verify claims
python -m analysis sync
python -m analysis build --write-proposals
python -m analysis check-claims --derived data/derived
python -m analysis check-claims --derived data/fixtures/derived

# 2. Verify Harbor task export & lint (official judging path)
python -m arena harbor-export --collection eval-v1 --out /tmp/junction-harbor --first 2
harbor lint /tmp/junction-harbor/gridworld-*

# 3. Verify web bundle compiles cleanly
cd web && npm run typecheck && npm run build
```

Keep 5 browser tabs pre-loaded (`110%` zoom on dark display):
1. **Tab 1 — Deck (`docs/deck/index.html`):** Slides 1–2 (framing) and Slide 8 (Harbor + rubric summary).
2. **Tab 2 — Overview & Play (`/` → `/play/<game_id>`):** Live pixels-only human play with keyboard + HUD walk-through.
3. **Tab 3 — Gallery & Compare (`/gallery` → `/compare`):** Rotation-aware optimal path overlay + side-by-side `Optimal` vs `Human` vs `Kimi K3.1 Pro` vs `Nemotron`.
4. **Tab 4 — Leaderboard (`/leaderboard`):** Compute/Cost vs Action-Efficiency Frontier + `VERIFIED ZERO-EXPLOIT` KPI strip.
5. **Tab 5 — Insights & Replay (`/insights` → `/replay/<run_id>?step=<n>`):** Modality gap, rule × player discovery heatmap, and exact failure step replay.

---

## Beat-by-Beat Run of Show (10 Minutes)

| Time | Screen | Presenter Action & Exact Spoken Point |
|---|---|---|
| **0:00 – 1:15** | **Tab 1 (`docs/deck/index.html` Slides 1–2)** | Frame the AfterQuery question: *"Instruction-heavy benchmarks test reading comprehension, not discovery. Our factory generates unlimited, BFS-verified 64×64 pixel games across 18 mechanics (`rules/img/all_rules.png`), shuffles palette colors per seed, and gives zero text hints."* |
| **1:15 – 3:00** | **Tab 2 (`/play`)** | Play Level 1–2 live with arrow keys + `R`. Point out `rows 0–1` (shrinking move budget), `rows 3–4` (level/key/health pips), and network panel showing only pixels + `ACTION1..4` — zero `truth` or score leakage. |
| **3:00 – 5:15** | **Tab 4 (`/leaderboard`)** | Show the real Engine `0.5.0` gap: `Optimal = 1.000`, `Human = 0.578` (`0.795` on `eval-v1`), `Kimi K3.1 Pro [image+rle] = 0.374` (`52.1%` levels), `Nemotron 3.5 Super VL = 0.061` (`12.5%`), and text-only `[rle]` `DeepSeek V3.2` / `gpt-oss-120b = 0.000` (`0/96` levels). Toggle `Tokens / Game` ↔ `USD / Game` and point out `noop = 0.000`, `stop_early = 0.000`. |
| **5:15 – 7:30** | **Tab 5 (`/insights` → click replay chip) & Tab 3 (`/compare`)** | Inspect the **Rule × Player Discovery Matrix** (`twin = 0%`, `no_effect_loop = 2,532` steps) and click an evidence chip straight into `/replay/<run_id>?step=<n>` to inspect the model's `hypothesis`, `belief`, and late `RESET` side by side with `/compare`. |
| **7:30 – 9:00** | **Terminal (`harbor run` + `check-claims`)** | Show the official **Harbor + OpenCode** sidecar task (`arena/HARBOR.md`): `oracle = 1.000`, `nop = 0.000`, `ORACLE_STOP_AFTER_LEVELS=1 = 0.167`, `OpenCode + Nemotron k=3 mean = 0.067`. Run `python -m analysis check-claims --derived data/derived` (`ok: true`, `0` errors). |
| **9:00 – 10:00** | **Tab 1 (Slide 8)** | Close on the 4 rubric pillars (`Gap`, `Meaningful Difficulty`, `Reward Integrity`, `One-Command Harbor Craft`) and hand the keyboard/terminal to judges for the 15-minute exploit hunt. |

---

## Backup Plan if Network / Tunnel Drops Live

- Pre-captured 1080p screenshots of every live route sit in `web/screenshots/01-overview.png .. 08-live.png`.
- `web/` runs offline via `?api=mock` (`data/fixtures/`), or against a local server (`make server PORT=8000`).
- Harbor tasks exported via `python -m arena harbor-export` run self-contained inside local Docker containers with zero external tunnel dependency.
