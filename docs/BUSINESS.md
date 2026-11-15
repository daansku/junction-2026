# Business & Real-World Value

> Six commercial and real-world applications of the procedural game factory: who pays, what pain it solves, why this architecture, what evidence we hold today, and what validation remains.

---

## 1. Candidate Evaluation Matrix (6 Directions Assessed)

### Candidate 1 — Verifiable RL Curricula & Causal-Discovery Training Environments
- **Who pays:** Frontier AI labs, open-weights post-training teams, and RL environment/data vendors (**AfterQuery's core customer base**).
- **Pain solved:** Static reasoning datasets saturate within months and reward memorized solution templates rather than interactive hypothesis testing (`observe → probe → falsify → revise → reset`). Building human-authored interactive environments is slow, unscalable, and riddled with reward-hacking loopholes.
- **Why our factory specifically:**
  1. **Infinite CPU-only curriculum (`~0.5–2 s/game`):** Seeded composition across 18+ orthogonal mechanics with BFS shortest-path proofs, rule-necessity ablation, and `<2%` random-walk rejection.
  2. **Exploit-proof verifiable rewards:** Exact action-efficiency scoring (`min(1, optimal / actions_used)`, `RESET` counted, `9/9` red-team container attacks = `0.000`) plus 4 single-turn verifiable auxiliary tasks (`next_frame`, `rule_effect`, `min_moves`, `full_plan`).
  3. **Targeted failure oversampling:** `decision_points.json` automatically mines frontier traces for premature hypotheses, zero-effect wall loops, and late resets to weight training generation.
- **Evidence we already have:**
  - `h1` & `h2` traces prove a clean capability gradient (Optimal `1.000`, Human `~0.58–0.80`, frontier VLMs `0.37–0.84` on `d1`, open models `<0.10`).
  - Step 0 (`SFT v1`, action-only cloning on `train-v1`) scored `4/180` levels on `eval-v1`, proving naive trajectory cloning fails without explicit discovery rationales (`SFT v2` + `GRPO` + `FT_BENCHMARKS.md` protocol tests whether discovery rationales transfer to outside reasoning).
- **What we still need:** Positive, CI-verified out-of-distribution lift over equal-token `ctrl` on `FT_BENCHMARKS.md` (or multi-family environments beyond 2D grids if transfer stays narrow).

---

### Candidate 2 — Contamination-Proof Private Evals ("Fresh Seed Set Per Contract")
- **Who pays:** Model evaluators, enterprise AI procurement teams, safety institutes (aisi/METR-style), and benchmark operators (ARC Prize / Harbor ecosystems).
- **Pain solved:** Public benchmarks leak into pre-training or prompt tuning almost immediately; even held-out static test sets suffer score inflation as labs hill-climb known visual conventions and task formats.
- **Why our factory specifically:**
  1. **Private one-time seed ranges:** Every evaluation contract draws a fresh seed range (e.g., `s950000+`) with per-seed `skin_shuffle` palette/glyph permutation and held-out rule pairs (`splits.py`), mathematically guaranteeing **zero overlap** with any public corpus while preserving exact difficulty calibration (`d1..d4`) and `1.000` BFS oracle ceilings.
  2. **Drop-in Harbor + MCP sidecar isolation:** Exports directly to `harbor==0.26.0` Docker Compose tasks (`observe`/`act` only, post-termination grading in a separate verifier container).
- **Evidence we already have:**
  - `30` `eval-v1` + `30` `eval-v2` Harbor packages lint-clean and Docker-verified (`oracle = 1.000`, `nop = 0.000`, `stop-early = 1/N`, `9/9` agent-seat red-team exploits = `0.000`).
  - Separates `seen_score`, `unseen_pair_score`, `unseen_skin_score`, and `probe_score` (`probe-v1`), quantifying true compositional generalization vs memorization.
- **What we still need:** Longitudinal stability calibration across seed draws (variance bounds on `N=30` fresh seeds per difficulty band) and multi-domain task skins.

---

### Candidate 3 — Pre-Deployment Agent Readiness & Resource-Bounded Adaptation Audits
- **Who pays:** Enterprise teams deploying computer-use, browser, RPA, and autonomous ops agents where unfamiliar UI states, silent action failures, or API rate/cost budgets cause costly runaway loops.
- **Pain solved:** Standard coding/QA benchmarks test static knowledge, not whether an agent notices *"my last action changed 0 pixels — stop repeating it"* or *"replanning/resetting now is cheaper than burning the remaining budget."*
- **Why our factory specifically:**
  - Directly measures **epistemic hygiene under strict budgets**: `no_effect_rate` (looping on failed actions), `actions_to_first_use`, `belief_accuracy`, and `late_reset` cost — under both stateless (`h1`) and lab-standard multi-turn (`h2`) harnesses.
- **Evidence we already have:**
  - Across `100+` recorded runs, text-only and mid-tier models spend **`55%–77%` of their entire action budget on zero-effect moves** (`no_effect_rate`) and misjudge game state, whereas top vision+thinking agents under `h2` self-correct after a single blocked probe.
- **What we still need:** Correlation study linking a model's gridworld `no_effect_rate` / `late_reset` rate to failure rates on real-world OSWorld / WebArena / enterprise GUI workflows.

---

### Candidate 4 — Small On-Device Planning Models (Robotics, Edge Assistants, Game NPCs) *(Assessed — Conditional)*
- **Who pays:** Edge robotics, warehouse automation, and consumer device teams needing `<10B` models that plan locally under tight latency/memory caps without cloud frontier APIs (`$12–$20/episode` in `h2`).
- **Pain solved:** Frontier multi-turn reasoning (`h2`) costs `$0.50–$20+` and minutes of latency per episode; edge systems need compact models (`4B–9B`) distilled on verifiable state-tracking + short-horizon planning.
- **Why our factory / Caveat:** Our `Qwen3.5-9B` vLLM stack runs at `~1 s/action` vs cloud timeouts, and `engine.tasks` generates unlimited verifiable planning supervision. *Why not top-3 unless `SFT v2`/RL wins:* value hinges directly on our `Qwen3.5-9B` post-training curve beating `ctrl`.

---

### Candidate 5 — Game Industry: Solvability-Proven Procedural Level Generation & Automated QA *(Assessed — Niche)*
- **Who pays:** Puzzle/tactics game studios and UGC platforms.
- **Pain solved:** Procedural puzzle generators frequently ship soft-locks, trivial shortcuts, or decorative mechanics players can ignore.
- **Why our factory / Caveat:** Our 4-gate verifier (BFS shortest path + rule-necessity ablation + slack cap + random-walk rejection) guarantees every generated seed is solvable and non-trivial (`POST /api/games/generate` in `<2 s`). *Why secondary:* puzzle-studio willingness-to-pay is much smaller than AI lab RL/eval budgets.

---

### Candidate 6 — Human Cognitive & Executive-Function Assessment *(Assessed — High Regulatory Burden, Deprioritized)*
- **Who pays:** Behavioural research labs, clinical neuropsychology, or technical hiring platforms.
- **Pain solved:** Culture- and language-independent measurement of inductive flexibility, spatial planning, and perseveration (`no_effect` streaks) with zero text instructions.
- **Ethical & validation caveat (why excluded from commercial pitch):** Any human diagnostic or hiring use requires psychometric norming, IRB/clinical validation, accessibility accommodation (colour-vision, motor speed), and strict anti-bias auditing. Kept strictly as an anonymized research baseline here.
