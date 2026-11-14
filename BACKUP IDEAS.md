# Backup business ideas

What we pitch if post-training on our puzzles does **not** improve reasoning on outside benchmarks
(PLAN.md §3.3 honesty rule). Main plan: `docs/BUSINESS.md` (A5).

**Core reframe:** if fine-tuning on our games doesn't transfer, then nobody can game our benchmark by
training on lookalike puzzles. A negative transfer result becomes evidence that the evaluation is robust,
so the evaluation business carries the pitch without needing transfer.

---

## 1. Contamination-proof evaluations and agent testing (lead backup)

**Who pays:**
- AI labs, for internal and pre-release evaluation
- companies choosing which model to buy
- agent startups, as regression tests for each release
- government AI safety institutes

**Pain:** public benchmarks leak into training data, so scores rise without capability. A number on a
published test is hard to trust.

**Why us:**
- a fresh, never-published game set per evaluation, generated on demand and proven solvable
- pixels-only interface: no hints, no rule names
- exploit-tested reward: do-nothing scores 0, stop-early earns only the levels solved, the reference solution scores 1.0
- human baselines
- difficulty bands d1–d4, including never-trained rules (`eval-v2`)

**Evidence we already have:**
- the gap on the judges' own harness: frontier agents average 0.067 against 1.0 for the reference (`coordination/JUDGING.md`)
- 1,000/1,000 fuzzed games solvable and deterministic
- `probe-v1`: levels whose rule combinations appear in no training or `eval-v1` level

**What makes it convincing:** report plainly that fine-tuning on 28.7k examples of our games did not lift
scores on unseen rules. That shows the benchmark resists training to the test.

**Pricing:**
- per private evaluation run (fresh hidden set plus a failure report)
- a subscription for continuous testing on every release

**Agent framing:** "Can your agent adapt to software it has never seen?" That is the core question for
computer-use agents. Our failure analysis supplies the examples: acting on premature hypotheses, repeating
moves that change nothing, missing the newly introduced rule.

---

## 2. Guaranteed-solvable level generation for game studios (non-AI hedge)

**Who pays:** puzzle and mobile game studios that hand-design thousands of levels and pay for playtesting.

**Why us:** every level comes with
- a proof it is solvable and its par (minimum moves), from the search solver
- a difficulty signal: random-walk win rate (under 2% required) and the d1–d4 bands
- a guarantee that every mechanic in the level actually matters
- seed reproducibility: same seed, same level

**Evidence:** more than 2,000 verified games in `train-v1`; the human playtest found the levels fair, with a
good mix of easy and hard.

**Weakness:** the engine is grid-only. Studios would plug in their own mechanics, so the product is a
level-generation engine (SDK or per-title licence), not ready-made levels.

---

## 3. Daily "beat the AI" puzzle and human reasoning data (flywheel)

**Product:** a free daily puzzle in the style of Wordle, built on `/challenge`: "You solved it in 14 moves;
Opus needed 61."

**Revenue:**
- light consumer revenue, plus brand marketing for ideas 1 and 2
- the real asset: a large dataset of humans discovering hidden rules move by move, with their hypotheses.
  Labs cannot easily buy that, and it fits imitation learning and reward modelling.

**Evidence:** human playtest traces, the visitor board and the kiosk demo already exist.

**Risks:** consumer growth is uncertain; collecting data needs consent and privacy terms.

---

## Recommendation for the pitch

- **Lead with idea 1.** It reuses all the reward-integrity work, and a failed transfer result strengthens it.
- **Idea 2 in one line**, as the hedge that does not depend on AI.
- **Idea 3 as the growth story.**
- **Drop** education and cognitive assessment: validating such a test and the ethics involved take longer
  than a startup can wait.

## Numbers to secure before the 07:00 lock

1. **Resistance claim:** SFT v1 and v2 scores on `eval-v2` (unseen rules) and `probe-v1` against the base
   model. SFT v1 so far: 3/144 levels on `eval-v1` (A3 status).
2. **Cost per private evaluation:** our compute plus model-call cost per game.
3. **Generation throughput:** 0.5–2 s per verified game on one CPU core (already measured).
