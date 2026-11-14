# PLAN.md — Junction 2026, phase 3: the last night

**Clock:** written Sat 14.11 21:30 (Helsinki), scope direction added 22:05. **Everything final by Sun 15.11 08:00. We submit 09:30** (deadline 10:00). About 10.5 hours left.

**Earlier plans** are archived: `coordination/PLAN-v1.md` (build) and `coordination/PLAN-v2.md` (phase 2). **Still binding:** PLAN-v1 §3 (working rules, ownership, git), §4 (contracts), §5 (game design); PLAN-v2 §3.1 (h2 rules), §4 (ownership table); `bench/PROTOCOL.md` v3 (benchmark list, decoding, claim rule, finalist rule). This file replaces the scope, gates and task lists.

**What changes, in one sentence:** no new features; the night goes to finishing the runs that are in flight, getting one honest post-training answer, and making the site, deck and video match the numbers.

**Direction from the humans (Daniel, Sat 22:00), binding for scope and story:**
1. **A cleaner website.** Fewer things on screen, one story per page. Cleaning means removing, renaming and aligning, not adding.
2. **The product shows where and why AI goes wrong.** Spotting and analysing model mistakes is the centre of the site and the deck, not a side page.
3. **h2 for several models on `eval-v2`.** The lab-style harness on the never-seen-rule games is the headline comparison.
4. **Business value = a service that trains models to reason better.** Published research already shows that RL on checkable puzzles lifts reasoning benchmarks; our edge is procedural generation: training data is cheap to make, graded automatically, and every game is freshly generated, so no model can have trained on it.

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

**The story, in order:** models make specific, repeatable mistakes when the rules are new (we can show each one, step by step) → our factory generates unlimited games that expose those mistakes, with a reward that can't be cheated → the same factory is training data: a service that trains models to reason better on games nobody has seen → published research says this kind of training transfers; here is how far our own run got in one night.

The pitch stands on claims 1 and 2 whatever claim 3 shows. For claim 3 there are four outcomes, and each has a line we can defend. The honesty rule (PLAN-v2 §3.3, PROTOCOL §6) decides which one we use; nobody picks after seeing the slide.

| Outcome at the lock | What the deck says |
|---|---|
| **A.** `think-games` beats `think-ctrl` and base under the PROTOCOL claim rule | "RL on our games made a 9B model reason better on outside benchmarks. The service works end to end." |
| **B.** `think-games` ≈ `think-ctrl`, both above base | "RL on checkable puzzles helps, as the papers say; ours do as well as hand-picked puzzle sets, and ours are unlimited and freshly generated." |
| **C.** No gain on outside benchmarks; gain on our held-out games | "In one night the model learned our games; the published results that show transfer trained far longer. The pipeline is built and the data is unlimited." Plus: training on lookalike puzzles does not buy a score on our benchmark. |
| **D.** No gain anywhere, or a drop | "Two careful negative results in one night, with the cause of the first one found. The research shows the approach works at longer training budgets; what we built is the data factory and the uncheatable reward." |

**Rule for the business claim:** "research shows this works" may only be said with two or three **primary sources that someone has opened and checked tonight** (title, authors, year, the exact result). Nothing is cited from memory (PLAN-v1 §3.5). Our own result is always shown next to it, whatever it is. "Never seen before" is said precisely: every game *instance* is freshly generated from a random seed, so it cannot be in any training set, and held-out rules and rule combinations test more than memorised instances; we do not claim the *kinds* of puzzle are new to the world.

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
7. **h2 on `eval-v2` for several models** (A3): the frozen 4-game `h2-subset-v2` for every model we can afford, one row per model with effort, attempts and CI; details in §5 A3-35.
8. **Mistakes front and centre** (A5, A1): the overview and `/insights` open on what models get wrong (the failure types, the knowing–doing gap, one replay per type with the divergence step); the deck gives it two slides.
9. **A cleaner site** (A4 shell, A5 pages): the checklist in §5 A4-33 / A5-34. Web changes stop at 03:00 so the screenshots after the lock show the final site.
10. **Business case rewritten around the training service** (A5 doc, A1 slide): `docs/BUSINESS.md` leads with it, with verified sources; contamination-proof evaluation is the second product from the same factory.

### Stretch (cut from the bottom up)
1. Finalist plays `eval-v1` / `eval-v2` games under h1 (the 10-game h2 subset) so it appears on the board.
2. h2 on a second, larger frozen `eval-v2` subset (10 games) for Kimi and one Gemini model, declared in a sweep file before any run.
3. One model sweep on `eval-v3` (Kimi, credits) if Anssi freezes it by 00:00.
4. A text-heavier RL mix (planning tasks on symbolic grids) on a GPU that frees up.
5. Finalist through Harbor + OpenCode.

### Not doing any more
New mechanics or rules; new web pages or features (cleaning only); rejection sampling (A3-24); `mix` / `ctrl` SFT v2 benches beyond what already ran; the live-AI demo toggle; generator changes after 03:00. Claude models on h2 only if a human tops up the Anthropic key (§6.12).

---

## 4. Gates

| Gate | Time | What must be true |
|---|---|---|
| **N0** | Sat 22:30 | Every agent has read this file. Web bundle rebuilt on the VM, boards rebuilt, rebuild timer running. RL v2 comparison written into `bench/PROTOCOL.md` and approved (§6.1). |
| **N1** | Sun 00:00 | First RL v2 checkpoint rows for all three runs next to base (dev slice, v3). Held-out quiz file on `main`, base model scored on it. A6 draft render. **Human go/no-go on the RL runs and GPU use** (§6.4). |
| **N2** | Sun 03:00 | Sweeps in §1 finished or stopped and labelled. h2 `eval-v2` runs for the agreed model list finished or in their last hour. **Web changes stop**; site cleanup checklist done. `docs/BUSINESS.md` rewritten with verified sources. `eval-v3` frozen or parked. **No generator or engine changes after this.** At least 20 finished human `eval-v2` games. |
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
| **W1** 21:30–00:00 | held-out quiz (A1-24) | VM rebuild + timer; B200 run; checkpoint benches | Modal runs; sweeps; **launch h2 on `eval-v2`** (A3-35) | Gemini 4 sweep; **site cleanup** (A4-33) | PROTOCOL amendment text; **mistakes-first pages** (A5-34); sources for BUSINESS | draft render | `eval-v3` review material for Anssi |
| **W2** 00:00–03:00 | deck: mistakes slides, business slide, fresh boards; engine on call | checkpoint benches; web rebuilds on request; keep stack up | training; quiz on checkpoints; sweeps and h2 runs finish | cleanup done by 03:00; site QA | **BUSINESS.md rewrite** (A5-35); h1/h2 boards; Q&A prep; SUBMISSION | scenes with real numbers, new story order | freeze or park `eval-v3`; audit numbers to A1/A5 |
| **W3** 03:00–06:30 | slide 9 from `bench_summary` | full v3 suite on finalists; snapshot at lock | finalists by rule; finalist on games (stretch); cost log | on call | aggregation with CIs; claim check | on call | on call |
| **W4** 06:30–08:00 | final deck; publish | final snapshot; published build; GPU cleanup (B200) | GPU cleanup (A100, H100, Modal) | retake screenshots and recordings | README, SUBMISSION, DEMO_SCRIPT, QA final; claim check | final render with locked numbers and voice | on call |

### A1 — FORGE
- **A1-24** Held-out quiz: `game_turn` states from `probe-v1` and `eval-v2` (never trained on), labelled by the solver; an evaluation-only path that refuses to write training messages; `python -m engine quiz` to build the file and to score a JSONL of replies. Report accuracy split by collection. Due N1.
- **A1-25** Deck (`docs/deck/`, taken over from A5 at the humans' request), reordered to the story in §2: (a) **mistakes get two slides**: the failure types with shares, and one replay with the divergence step and A5's knowing–doing finding (58.7% of failed hidden-rule levels where the model had already stated the rule), if the claim check supports it; (b) the gap slide leads with **h2 on `eval-v2`, one bar per model**; (c) **business slide = the training service** (who pays, published evidence with sources from A5-35, our edge: generated, auto-graded, never-seen data), evaluation as the second product; (d) slide 9 from `bench_summary.json` at N4. Refresh numbers when boards change; final at N6; republish.
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
- **A3-34** Stretch 1 and 2 (§3). Cost and GPU-hour log in the status file; delete the A100 box, H100 and Modal apps at N6.
- **A3-35** **h2 on `eval-v2` for several models** (must, launch by 23:30). Games: the frozen 4-game `arena/sweeps/h2-subset-v2.yaml`; no other games are added after a result is seen. Models, each at the highest effort it supports, h2 rules unchanged (PLAN-v2 §3.1): Kimi K3.1 (Verda credits; 3 attempts), Gemini Pro, Gemini Flash, Gemini 4 Argon and Carbon (Gemini credits; caps high enough that no run is cut by cost), one open model if an endpoint is fast enough to finish, Claude Haiku / Sonnet / Opus only after a key top-up (§6.12), and the RL finalist at N4 (stretch). `--dry-run` estimate first; wall cap so every run ends by 04:00; capped or single-attempt rows are labelled. Report per model: score with CI, games won, effort, attempts.

### A4 — STUDIO
- **A4-30** Gemini 4 Argon + Carbon on `eval-v2` to the finish.
- **A4-31** After A2's rebuild: QA `/leaderboard` (h1, h2, bench), `/replay`, `/challenge` on projector and phone; report anything wrong to the owner.
- **A4-33** **Site cleanup** (shell, nav, `/challenge`, gallery, compare, live), done by 03:00, nothing new added:
  top navigation cut to the pages a visitor needs (Overview, Beat the AI, Leaderboard, Mistakes, Replays, Play), the rest reachable from those pages; debug controls (data-source picker, truth overlay) behind one switch that is off by default; one name per thing across pages (game, level, run, attempt; "Mistakes" for `/insights`); internal ids and agent jargon (h1, h2, RHAE, tier names) explained once or replaced with plain labels ("standard harness", "lab-style harness"); empty and loading states that say what will appear; no fixture or placeholder data visible on the public URL. Ask A2 for a VM web build after each batch.
- **A4-32** After N5: retake screenshots and recordings (`web/scripts/deck_capture.py`), including `/leaderboard?view=h2` and `?view=bench`; copy the two deck images to `docs/deck/assets/` or tell A1.

### A5 — LENS
- **A5-30** `bench_agg` for RL v2: base / `think-ctrl` / `think-games`, paired CIs, the claim rule evaluated automatically, the quiz numbers as an in-domain row.
- **A5-31** Boards and insights stay correct on every rebuild; fix the `%` in the CLI help string (Python 3.14).
- **A5-32** `docs/SUBMISSION.md`, `README.md`, `docs/DEMO_SCRIPT.md` (deck v3 slide numbers), `docs/QA_PREP.md` (add: "your first fine-tune made the model worse, why?" and "isn't your control closer to the benchmarks than your games?").
- **A5-33** Claim check over deck, README, submission and video numbers at N6.
- **A5-34** **Mistakes first** (pages A5 owns: overview, `/insights`, `/replay`, leaderboard), done by 03:00: the overview opens on the gap in one line and the top failure types with a link to a replay of each; `/insights` leads with the failure funnel and the knowing–doing gap, analysis detail below; every failure type links to one replay that opens at the divergence step; the leaderboard defaults to `eval-v2` with the lab-style (h2) view one click away; long explanatory text cut to one line per panel. Same cleanup rules as A4-33.
- **A5-35** **`docs/BUSINESS.md` rewritten** (≤ 2 pages) with the training service first: who pays (labs, teams fine-tuning open models, agent builders), what they get (fresh verified games and rewards, a training run, a before/after report on outside benchmarks and on a private never-seen test set), why us (procedural generation: about 0.5–2 s of CPU per verified game, automatic grading, every instance new, difficulty and rules controllable, failure-targeted sampling), pricing sketch, risks. **Evidence section:** two or three primary sources found and opened tonight that report reasoning-benchmark gains from RL or fine-tuning on procedurally generated or automatically checked puzzles, each with title, authors, year, link and the exact number quoted; then our own result in one honest line. Second product: contamination-proof evaluation from the same factory. Hand the sources to A1 (slide) and A6 (video).

### A6 — REEL
- **A6-10** Draft render by N1 with placeholders marked. Scene order follows the story in §2 (mistakes → factory → training service → evidence). Scene lines for claim 3 written for all four outcomes.
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
| 12 | **by 23:00** | h2 on `eval-v2`: confirm the model list in A3-35; top up the Anthropic key if Claude rows are wanted (Opus on 4 games was estimated at about $27 per game). | money |
| 13 | **by 02:30** | Look at the cleaned site once on a laptop and a phone; say what still feels cluttered. | taste |

One keeper per machine stays reachable through the night; an agent that stops costs more than an hour of sleep.

---

## 7. If we fall behind

- Cut in this order: the open-model h2 row → h2 repeats beyond one attempt → cosmetic site cleanup (keep: nav, jargon, no placeholder data) → Harbor run of the finalist → `eval-v3` sweep → Kimi h2 repeats → finalist on games → the B200 run (Modal `think-games` is enough) → the full v3 suite on a second games finalist.
- Never cut: at least Kimi and one Gemini model on h2 `eval-v2`, the mistakes story on the overview and in the deck, verified sources for any "research shows" sentence, the `think-ctrl` control and CIs, the finalist rule, separate h1 / h2 boards, the finished-only rule, the claim check, the recorded video.
- No RL v2 rows by 00:30 → A2 and A3 look at one run together; if thinking never closes (`think_closed_rate` near 0), shorten `max_completion` or lower the task difficulty mix and restart once. No second restart after 01:30.
- Full suite not finished by 05:30 → report the dev slice for the finalists, label it as the dev slice, and say the full suite was not run.
- Rebuild on the VM fails → A5 builds the boards locally from `/api/runs/export` and A2 copies the files to the VM.
- GPU gone for more than 30 minutes → move the run to the other provider (Verda ↔ Modal), log it, keep going.
