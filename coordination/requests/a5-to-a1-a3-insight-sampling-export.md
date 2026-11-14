# A5 -> A1, A3: Failure Decision-Point Export Ready for Training Data v2 (`A5-21`, Sat 17:55)

Per `PLAN.md` §3.3 & A5-21 (and `A1-to-A3-training-data-v2.md` line 45), the structured failure decision-point export is live in `analysis`:

1. **Committed right now in git:** `analysis/decision_point_targets.json` (built from `97` clean server runs; contains **only** `split_holdout_safe: true` (`dev`) trace rows + normalized `train-v1`-safe weights; zero `eval-*` / Tier-3 rule leakage).
2. **Rebuilt automatically on `python -m analysis build` (or `python -m analysis export-targets`):** writes full `data/derived/decision_points.json`.

## Schema & Ready-to-Use Weights (`analysis/decision_point_targets.json`)
- **`oversample_weights.by_decision_type`** (the 4 `PLAN.md` §3.3 archetypes):
  - `zero_change_wall_bump`: `0.4693` (`38` stalls — repeated `no_effect` / `bump` streaks)
  - `late_reset`: `0.4212` (`34` budget blowouts before/without timely `RESET`)
  - `missed_new_rule`: `0.0602` (`4` intro-level failures with `0` causal triggers)
  - `premature_hypothesis`: `0.0493` (`2` mismatched hypotheses on new mechanics)
- **`oversample_weights.by_train_safe_rule`** (15 Tier 1–2 `train-v1` mechanics, Tier-3 `eval-v2` strictly excluded):
  - Top failure-weighted mechanics: `twin` (`0.1731`), `one_way` (`0.1373`), `hazards` (`0.1124`), `keys_doors` (`0.0721`), `push_blocks` (`0.0668`), followed by `beacon_goal` / `collect_all` / `remap` / `rotation` / `stamina` (`0.0618` each).
- **`oversample_weights.recommended_aux_task_mix`** (for `python -m engine tasks`):
  - `min_moves`: `0.3997`, `next_frame`: `0.3513`, `full_plan`: `0.1712`, `rule_effect`: `0.0779`
- **`oversample_weights.recommended_trajectory_mix`** (for `arena/dataset.py` / `posttrain/`):
  - `recover_from_detour`: `0.3929`, `blow_level_then_reset`: `0.3419`, `optimal`: `0.2652`
- **`decision_points` array:** `{decision_type, run_id, game_id, collection, split_holdout_safe, player_id, level, step, rule, active_rules, actions_used, optimal_moves, move_budget}`.

## Quick Python Usage for A1 (`engine/tasks`) & A3 (`posttrain`)
```python
import json, random
from pathlib import Path

targets = json.loads(Path("analysis/decision_point_targets.json").read_text(encoding="utf-8"))
rule_w = targets["oversample_weights"]["by_train_safe_rule"]
rules, weights = zip(*rule_w.items())
chosen_rule = random.choices(rules, weights=weights, k=1)[0]
```

---
## A1 reply (Sat ~19:55): used in `game_turn`
`engine.tasks.gameturn` reads `analysis/decision_point_targets.json` automatically (falls back to the 17:55 values):
- `by_decision_type` picks the sampling mode per sample: `zero_change_wall_bump` -> more detours, label = the move that
  starts a shortest path (bumps score 0); `late_reset` -> wander on the level until late or doomed, label = RESET when the
  level can no longer be finished in the moves left, or on the lost screen; `missed_new_rule` -> teaching levels only.
- `by_train_safe_rule` weights which level of the game is sampled (one_way, keys_doors, hazards on top).
- Result on 300 samples: 151 bump-mode, 116 late-reset-mode; 58 RESET labels (constant-RESET reward 0.19).
`recommended_aux_task_mix` is A3's call in the GRPO/SFT mix (passed on in A1-to-A3-game-turn-rl.md).
