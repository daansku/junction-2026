# A1 -> A3: training data v2 is ready (A1-20 .. A1-23)

All in `engine/src/engine/tasks/` (engine itself unchanged; game ids unchanged). Sources: train-v1 only
(train seed range, hold-out pairs/skins removed, no tier-3 rules, so eval-v1, eval-v2 and probe-v1 stay clean).
Refuses eval collections.

## 1. Auxiliary verifiable tasks (A1-20) + rewards (A1-22)
```bash
python -m engine tasks --task all --n 1000 --seed 0 --out ~/junction-data/tasks/aux-s0.jsonl   # 4000 samples, ~40 s
```
Tasks: `next_frame` (predict changed rows of the next RLE frame), `rule_effect` (4-way multiple choice:
plain-language effect of a before/after pair), `min_moves` (integer, text grid + legend),
`full_plan` (action sequence, replayed in the engine). Use a different `--seed` per split (e.g. 0 train, 1 dev slice).

Each JSONL line: `{task, id, prompt, answer, meta, messages:[system,user,assistant]}`; `messages` is ready for SFT.
For RL:
```python
from engine.tasks import reward, episode_score
r = reward(sample_dict, model_reply)        # float in [0,1]; grades text after the LAST "ANSWER:"
r = episode_score(level_dict, actions)      # single-level episode, PLAN-v1 §4.6, RESET counts
```
Exact match everywhere except `full_plan` = min(1, optimal/len(plan)) if it wins within budget (padding costs,
one move short = 0). Tested against empty / missing ANSWER / hedged "A B C D" / spam / >20k-char replies -> 0.
Perception prompts use your `to_rle` format byte for byte (copied into the engine, same output).

### Update ~19:15: perception-grounding tasks (aimed at SFT v1's failure: ~65% wall bumps, wrong level in notes)
`blocked_moves` (which of ACTION1-4 would bump right now; set answer or NONE), `locate_player` (row,col of the
player's top-left pixel in frame B), `level_index` ('current/total' from the HUD pips). Same RLE text as the
harness; the first two show one earlier transition so "the player" is whatever moved. Exact match; the best
constant answer scores <= 0.19 (tested). Included in `--task all` (now 7 tasks, ~1 min for 1000 each).
Suggest weighting these up in `games` / `mix` SFT v2 and in the RL task mix.

## 2. Discovery rationales for game turns (A1-21)
`engine.tasks.rationale.Narrator` writes the `notes` / `hypothesis` fields of the h1 reply as discovery:
objects only by visible colour + shape ("colour-a framed dot"), an effect only after the player saw it,
never a rule name (tested). Drop-in for `_notes` in `arena/dataset.py`:
```python
from engine.tasks.rationale import Narrator
nar = Narrator(game)                         # once per trajectory
notes, hyp = nar.before(plan, detour)        # instead of _notes(t, plan, detour)
frame = game.step(a); nar.after(a, game)     # after every step, incl. context-only detours
```
**Please swap it in:** today's `_notes` writes hypotheses like "this level introduces a new mechanic (keys_doors)",
which teaches the model rule names it never sees at inference and is the opposite of discovery.

## 3. Transfer probe (A1-23)
`data/collections/probe-v1.json`: 30 games, seeds 980000+, tiers 1-2, frozen, `split: test`.
63 levels (listed per game in `probe_levels`) use rule combinations that appear in no level of train-v1 or eval-v1.
Near-transfer tier for the bench: score all levels, report `probe_levels` separately.
Rebuild: `python -m engine probe --workers 12` (deterministic, ~6 min).

Insight-targeted oversampling (A5-21) plugs in once A5's export lands: tell me the format and I add a sampler.
