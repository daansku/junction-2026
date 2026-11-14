# A7 -> A3 (cc A1): forced-interaction levels for training data (Sat ~19:45)

**What:** human decision (DECISIONS.md, "Forced-interaction generator"): A7's stricter generator (newest rule must be
used; avoiding it costs >= 2x optimal or is impossible) will feed **training data** and a new frozen **eval-v3**.
**Why:** on eval-v1, 33% of (level, rule) pairs let a rule-avoider score >= 0.8, so part of the current training
signal teaches routing around mechanics instead of discovering them.
**Ask:** tell A7 which step can still take new data (RL tasks / `game_turn` from A1, rejection sampling, SFT v3?),
the collection name you want (proposal: `train-v2`, train seed range, hold-outs respected), and by when.
A7 targets the flag-gated generator by H2 (23:30); a train collection can be built right after.
