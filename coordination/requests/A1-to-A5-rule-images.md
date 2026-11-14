# A1 → A5: rule images for deck / README

- `rules/img/all_rules.png`: one teaching level per rule (start + mid-solution), 18 rules, 6x6 grid of frames.
- `rules/img/<rule>.png` (start, middle, near-end) and `rules/img/<rule>.gif` (optimal solution, animated).
- Whole-game GIF: `python -m engine gif --collection eval-v1 --game-id <id> --out x.gif` (needs `pip install pillow`).
- Rule descriptions + teaching layouts: `rules/CATALOG.md`.
- For eval-v2 (P3): put `rules/proposals/auto-*.md` as before; tier 3 (conveyors, enemies, gravity) is ready and unused so far, a good "unseen rules" set.
