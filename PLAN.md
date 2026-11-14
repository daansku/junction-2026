# PLAN.md — Junction 2026, phase 3: the last night

**Clock:** written Sat 14.11 21:30 (Helsinki). **Everything final by Sun 15.11 08:00. We submit 09:30** (deadline 10:00). About 10.5 hours left.

**Earlier plans** are archived: `coordination/PLAN-v1.md` (build) and `coordination/PLAN-v2.md` (phase 2). **Still binding:** PLAN-v1 §3 (working rules, ownership, git), §4 (contracts), §5 (game design); PLAN-v2 §3.1 (h2 rules), §4 (ownership table); `bench/PROTOCOL.md` v3 (benchmark list, decoding, claim rule, finalist rule). This file replaces the scope, gates and task lists.

**What changes, in one sentence:** no new features; the night goes to finishing the runs that are in flight, getting one honest post-training answer, and making the site, deck and video match the numbers.

Every agent reads §1–§4, then its own row in §5. Humans read §1, §2 and §6.

---

## 1. Where we stand (Sat 21:30)

| Claim | Status | Evidence so far |
|---|---|---|
| **1. The gap.** Humans finish games with never-seen rules; no model does. | **Holds, thin data** | `eval-v2`, live board 20:29. h1: humans 0.699, 10 of 15 games won; Gemini 4 Argon 0.442, 0 of 6; Gemini Flash 0.020, 0 of 7. h2 (lab-style): humans 0.660, 4 of 4; Kimi K3.1 max 0.398, 0 of 4; Gemini Pro high 0.376, 0 of 3. On easy `eval-v1` d1 games h2 closes the gap (wins in 98–131 moves vs 86–92 optimal): we say so. |
| **2. The reward can't be cheated.** | **Done** | Harbor: reference 1.000, do-nothing 0.000, stop-early 0.167 / 0.500; 9 of 9 container attacks score 0.0; agent egress allowlist closes the answer-key route (A4, 21:13). `coordination/JUDGING.md`. |
| **3. Training on our games improves reasoning elsewhere.** | **Open. First attempt failed.** | No-thinking SFT v2 and GRPO dropped the outside-benchmark headline from 0.758 (base) to 0.44–0.46: the model learned to answer without reasoning. Kept as a documented negative result. **RL v2 (thinking on, from the base model) started ~21:10–21:30.** |

**Running right now (do not disturb):**
- **RL v2**, GRPO on Qwen3.5-9B with thinking on, reward only on the answer after `</think>`:
  `think-games` on a Modal H100 (A3) and on the Verda B200 (A2); `think-ctrl` (generic reasoning-gym puzzles) on a second Modal H100 (A3). Checkpoints every 10 steps, each benchmarked on the dev slice (975 items) and rescored with the v3 rule. First rows expected ~22:45.
- **Sweeps:** h1 main on `eval-v1` (Gemini Flash 30×3 + baselines), `eval-v2` frontier (Kimi K3.1 and Gemini Flash, 30×1), Gemini 4 Argon + Carbon on `eval-v2` (30×1 each), h2 Gemini Pro on the 10-game subset, Sonnet 5.5 on one `eval-v2` game, untuned Qwen on `eval-v1`.
- **Shared server** on the Verda CPU VM (`coordination/API_URL`).

**Done and on `main`:** engine 0.6.0 (21 rules, `eval-v1`, `eval-v2`, `probe-v1` frozen; `train-v1`), training tasks and rewards (`engine/src/engine/tasks/`, incl. `game_turn`), h2 harness, `bench/` pipeline with base numbers, `/challenge` demo live and QA'd, deck v3 (`docs/deck/`), `docs/BUSINESS.md` + `BACKUP IDEAS.md`, video draft scenes (A6), reasoning forensics (A5), forcing generator with `eval-v3` / `eval-v3b` drafts (A7).

**Known gaps:**
- The live boards rebuild only when A2 triggers it (last: 20:29). The Replays filter (aborted runs hidden, on `main` since 20:45) needs a web build on the VM.
- The human number rests on 15 finished `eval-v2` games.
- Every h2 row is a single attempt.
- `bench/PROTOCOL.md` describes the stopped SFT/RL line; the RL v2 comparison is not written into it yet (§6, decision 1).

---

## 2. What we will be able to say at 08:00

The pitch stands on claims 1 and 2 whatever claim 3 shows. For claim 3 there are four outcomes, and each has a line we can defend. The honesty rule (PLAN-v2 §3.3, PROTOCOL §6) decides which one we use; nobody picks after seeing the slide.

| Outcome at the lock | What the deck says |
|---|---|
| **A.** `think-games` beats `think-ctrl` and base under the PROTOCOL claim rule | "RL on our games made a 9B model reason better on outside benchmarks." |
| **B.** `think-games` ≈ `think-ctrl`, both above base | "RL on checkable puzzles helps; ours do as well as hand-picked puzzle sets, and ours are unlimited and never published." |
| **C.** No gain on outside benchmarks; gain on our held-out games | "It learned our games and the skill did not spread. Training on lookalike puzzles does not buy a score on our benchmark." (business idea 1) |
| **D.** No gain anywhere, or a drop | "Two careful negative results, with the cause of the first one found." The pitch leads with the gap and reward integrity. |

For A–C we need the same three things: dev-slice rows per checkpoint, a finalist chosen by the fixed rule, and the full v3 suite with CIs on base, the control finalist and the games finalist. For C we also need an in-domain test on games the model never trained on (§5, A1-24).

---

## 3. Scope for the night

### Must finish
1. **Live site current:** new web bundle, boards on the finished-only rule (WIN / GAME_OVER / BUDGET), automatic rebuild until the lock (A2).
2. **Sweeps in flight finish** and land on the boards (A3, A4). No new paid sweeps beyond those in §1 without a human OK.
3. **RL v2 answer:** dev-slice rows → finalists by the PROTOCOL §7 rule → full v3 suite with paired CIs → `bench_summary.json` (A3 trains, A2 benches, A5 aggregates).
4. **In-domain evidence:** held-out game-turn quiz on `probe-v1` and `eval-v2` states for base and each finalist (A1 builds, A3 runs).
5. **More human games on `eval-v2`**: at least 20 finished games through `/play` under real names (humans).
6. **Presentation matches the locked numbers:** deck, video, `README.md`, `docs/SUBMISSION.md`, `docs/DEMO_SCRIPT.md`, `docs/QA_PREP.md`, claim check.

### Stretch (cut from the bottom up)
1. Finalist plays `eval-v1` / `eval-v2` games under h1 (the 10-game h2 subset) so it appears on the board.
2. Kimi K3.1 repeats on the 4 `eval-v2` h2 games (credits, free) so one h2 row has 3 attempts.
3. One model sweep on `eval-v3` (Kimi, credits) if Anssi freezes it by 00:00.
4. A text-heavier RL mix (planning tasks on symbolic grids) on a GPU that frees up.
5. Finalist through Harbor + OpenCode.

### Not doing any more
New mechanics or rules; web features; rejection sampling (A3-24); `mix` / `ctrl` SFT v2 benches beyond what already ran; Opus on h2 (no key budget); the live-AI demo toggle; generator changes after 03:00.

---

## 4. Gates

| Gate | Time | What must be true |
|---|---|---|
| **N0** | Sat 22:30 | Every agent has read this file. Web bundle rebuilt on the VM, boards rebuilt, rebuild timer running. RL v2 comparison written into `bench/PROTOCOL.md` and approved (§6.1). |
| **N1** | Sun 00:00 | First RL v2 checkpoint rows for all three runs next to base (dev slice, v3). Held-out quiz file on `main`, base model scored on it. A6 draft render. **Human go/no-go on the RL runs and GPU use** (§6.4). |
| **N2** | Sun 03:00 | Sweeps in §1 finished or stopped and labelled. `eval-v3` frozen or parked. **No generator or engine changes after this.** At least 20 finished human `eval-v2` games. |
| **N3** | Sun 04:00 | **Last checkpoint that can be a finalist.** Training stops; finalists picked by PROTOCOL §7 (best dev-slice headline, MMLU-Pro history drop ≤ 2 points, earlier wins ties). |
| **N4** | Sun 05:30 | Full v3 suite done on base, control finalist, games finalist, with paired 95% CIs; quiz scored on the finalists; `bench_summary.json` built. |
| **N5** | Sun 06:30 | **Numbers lock** (moved from 07:00 so the 08:00 target holds). Final board rebuild and `data/published/` snapshot. After this only presentation work. |
| **N6** | Sun 08:00 | Deck, video, README, SUBMISSION, demo script and Q&A match the locked numbers; claim check passes; screenshots retaken; GPU instances deleted. |
| | Sun 09:30 | **Submit.** |

---

## 5. Agent tasks

Task ids continue. Blocked for more than 10 minutes → write it in your status file and take the next task.

| Window | A1 FORGE | A2 GATEWAY | A3 ARENA | A4 STUDIO | A5 LENS | A6 REEL | A7 WARDEN |
|---|---|---|---|---|---|---|---|
| **W1** 21:30–00:00 | held-out quiz (A1-24) | VM rebuild + timer; B200 run; checkpoint benches | Modal runs; sweeps; dev-slice table | Gemini 4 sweep; Harbor docs | PROTOCOL amendment text; `bench_summary` for RL v2 | draft render | `eval-v3` review material for Anssi |
| **W2** 00:00–03:00 | deck updates from fresh boards; engine on call | checkpoint benches; keep stack up | training; quiz on checkpoints; sweeps finish | site QA on fresh boards | h1/h2 boards; Q&A prep; SUBMISSION | scenes with real numbers | freeze or park `eval-v3`; audit numbers to A1/A5 |
| **W3** 03:00–06:30 | slide 9 from `bench_summary` | full v3 suite on finalists; snapshot at lock | finalists by rule; finalist on games (stretch); cost log | on call | aggregation with CIs; claim check | on call | on call |
| **W4** 06:30–08:00 | final deck; publish | final snapshot; published build; GPU cleanup (B200) | GPU cleanup (A100, H100, Modal) | retake screenshots and recordings | README, SUBMISSION, DEMO_SCRIPT, QA final; claim check | final render with locked numbers and voice | on call |

### A1 — FORGE
- **A1-24** Held-out quiz: `game_turn` states from `probe-v1` and `eval-v2` (never trained on), labelled by the solver; an evaluation-only path that refuses to write training messages; `python -m engine quiz` to build the file and to score a JSONL of replies. Report accuracy split by collection. Due N1.
- **A1-25** Deck (`docs/deck/`, taken over from A5 at the humans' request): refresh slides 5–7 when boards change; add A5's knowing–doing finding (58.7% of failed levels where the model had stated the rule) if the claim check supports it; fill slide 9 from `bench_summary.json` at N4; final at N6; republish.
- **A1-26** Engine on call. A7's hooks are on `main` (143 engine tests pass, frozen collections byte-identical); no engine changes after N2.
- Stretch: a text-heavier RL data mix, only if a human asks and a GPU is free.

### A2 — GATEWAY
- **A2-30** Now: on the VM `git pull`, `cd web && npm install && npm run build`, `POST /api/admin/rebuild`; confirm the board build includes the finished-only rule (`analysis/src/analysis/loader.py::is_finished`); add a timer that rebuilds every 10–15 minutes until N5 (`coordination/requests/A1-to-A2-A5-finished-runs-only.md`).
- **A2-31** `think-games` on the B200; checkpoint bench chain on the A100 box; rows into A3's timeline table.
- **A2-32** N3–N4: full v3 suite on the finalists (base is done). One model per GPU; merged weights, not `--lora` (vLLM 0.33 bug on loglikelihood requests).
- **A2-33** `bench/PROTOCOL.md`: v3 rescoring rule and the RL v2 comparison as an amendment, after the human OK (§6.1).
- **A2-34** `data/published/` snapshot and final rebuild at N5; published-mode build; delete the B200 at N6.

### A3 — ARENA
- **A3-30** `think-games` and `think-ctrl` on Modal within the EUR 100 cap; watch reward, `think_closed_rate`, completion length and KL; stop a run that collapses and say so.
- **A3-31** Finalists at N3 by PROTOCOL §7, one per run family (`think-games`: best of Modal and B200; `think-ctrl`). Register in `arena/models.yaml` (`tier: finetuned`).
- **A3-32** Run A1's quiz on base and on each benchmarked checkpoint (replaces the seed-2 in-domain check, which uses training games).
- **A3-33** Sweeps in §1 to the finish; label capped or single-attempt rows; check the Gemini Pro h1 notes problem A1 flagged (0 of 72 turns have notes) before the lock.
- **A3-34** Stretch 1 and 2. Cost and GPU-hour log in the status file; delete the A100 box, H100 and Modal apps at N6.

### A4 — STUDIO
- **A4-30** Gemini 4 Argon + Carbon on `eval-v2` to the finish.
- **A4-31** After A2's rebuild: QA `/leaderboard` (h1, h2, bench), `/replay`, `/challenge` on projector and phone; report anything wrong to the owner.
- **A4-32** After N5: retake screenshots and recordings (`web/scripts/deck_capture.py`), including `/leaderboard?view=h2` and `?view=bench`; copy the two deck images to `docs/deck/assets/` or tell A1.

### A5 — LENS
- **A5-30** `bench_agg` for RL v2: base / `think-ctrl` / `think-games`, paired CIs, the claim rule evaluated automatically, the quiz numbers as an in-domain row.
- **A5-31** Boards and insights stay correct on every rebuild; fix the `%` in the CLI help string (Python 3.14).
- **A5-32** `docs/SUBMISSION.md`, `README.md`, `docs/DEMO_SCRIPT.md` (deck v3 slide numbers), `docs/QA_PREP.md` (add: "your first fine-tune made the model worse, why?" and "isn't your control closer to the benchmarks than your games?").
- **A5-33** Claim check over deck, README, submission and video numbers at N6.

### A6 — REEL
- **A6-10** Draft render by N1 with placeholders marked. Scene lines for claim 3 written for all four outcomes in §2.
- **A6-11** Final numbers after N5; final 1080p MP4 with captions by N6. Needs the ElevenLabs key (§6.7) or ships with the local voice.

### A7 — WARDEN
- **A7-10** `eval-v3` / `eval-v3b`: review material to Anssi now; freeze the chosen one or park both by N2. No model runs without his OK.
- **A7-11** Before/after audit numbers (share of teaching levels an avoider can nearly solve) to A1 and A5 for one deck line.
- **A7-12** No generator changes after N2; frozen collections stay byte-identical.

---

## 6. Humans — decisions and tasks

| # | When | Task | Why an agent can't |
|---|---|---|---|
| 1 | **now** | Approve the RL v2 comparison for `bench/PROTOCOL.md`: candidate `think-games`, control `think-ctrl`, reference base; same claim rule and finalist rule. Must be fixed before the first RL v2 rows are read (~22:45). | keeps the result honest |
| 2 | **now** | Confirm the numbers lock at **06:30** (was 07:00). | schedule call |
| 3 | **now** | Is the repo public at submission? If yes, decide what happens to `harbor/eval-*/solution/` (optimal paths). The agent seat is closed by A4's allowlist; a public repo still shows them to anyone. | risk call |
| 4 | **00:00** | RL go/no-go: read the first checkpoint rows; keep, stop or re-point each GPU (B200, two Modal H100s, A100 box, H100). | money, judgment |
| 5 | **before sleep** | Play `eval-v2` games through `/play` under your real name, first attempt only; target 20 finished games in total. `/challenge` plays do not count. | only humans can |
| 6 | **by 00:00** | Anssi: choose `eval-v3`, `eval-v3b` or neither; say whether Kimi may run on it. | taste, money |
| 7 | **by 05:00** | ElevenLabs key in `video/.env` if the video gets the final voice. | account |
| 8 | **tonight** | Decide who presents which slide; rewrite the speaker notes in `docs/deck/SLIDES.md` in your own words. | your voice |
| 9 | **06:30** | Numbers lock. | |
| 10 | **08:00–09:30** | Final check of site, deck, video, README one-command eval. **Submit 09:30.** | platform login |
| 11 | **after** | Rehearse the pitch twice, timed; run the booth demo. | in person |

One keeper per machine stays reachable through the night; an agent that stops costs more than an hour of sleep.

---

## 7. If we fall behind

- Cut in this order: Harbor run of the finalist → `eval-v3` sweep → Kimi h2 repeats → finalist on games → the B200 run (Modal `think-games` is enough) → the full v3 suite on a second games finalist.
- Never cut: the `think-ctrl` control and CIs, the finalist rule, separate h1 / h2 boards, the finished-only rule, the claim check, the recorded video.
- No RL v2 rows by 00:30 → A2 and A3 look at one run together; if thinking never closes (`think_closed_rate` near 0), shorten `max_completion` or lower the task difficulty mix and restart once. No second restart after 01:30.
- Full suite not finished by 05:30 → report the dev slice for the finalists, label it as the dev slice, and say the full suite was not run.
- Rebuild on the VM fails → A5 builds the boards locally from `/api/runs/export` and A2 copies the files to the VM.
- GPU gone for more than 30 minutes → move the run to the other provider (Verda ↔ Modal), log it, keep going.
