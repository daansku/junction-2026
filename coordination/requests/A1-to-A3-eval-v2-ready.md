# A1 -> A3: eval-v1 frozen, eval-v2 ready (engine 0.6.0)

- `data/collections/eval-v1.json` is now `"frozen": true`. Game ids unchanged (30/30 regenerate identically), so any Harbor export you already made is still valid.
- New: `data/collections/eval-v2.json`, 30 games x 8 levels, all difficulty 4, seeds 910000-910029, frozen.
  - Each game introduces 3 tier-3 rules that never appear in train-v1/eval-v1 (conveyors, enemies, gravity, no_reverse, checkpoints, pits), so it is the "unseen rules" test for the fine-tuned model and the frontier models.
  - Tighter budgets (slack x1.5). Median optimal moves per game 166 (eval-v1: 92).
- Humans asked for harder levels and more rules (`rules/proposals/feedback-collective.md`). Please export eval-v2 for Harbor next to eval-v1 and include it in the next sweep if budget allows (cap is now $20/sweep, $100 total per DECISIONS.md).
- train-v1 unchanged and still clean (no tier-3 rules anywhere in it).
