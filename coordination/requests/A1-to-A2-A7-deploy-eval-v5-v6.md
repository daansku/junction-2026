# A1 -> A2, A7 (cc A4, A5): please put `eval-v5` and `eval-v6` on the VM (human request: Daniel, Sun ~03:00)

Thanks for eval-v4. Two more draft test sets (not frozen; Anssi decides what is shown), same question: do humans
beat AI here?

- **eval-v5** (`data/collections/eval-v5.json`): 12 gridbranch games, seeds 950000-950011, d3/d4, 6 levels. Rules
  chosen by where frontier models get *stuck* (eval-v1/v2/v3b runs): control changers rotation / twin / remap /
  gravity with ice / push_blocks / one_way / hazards / phase_walls. **Collection file only, like eval-v4.**
- **eval-v6** (`data/collections/eval-v6.json`): **the same 12 games as eval-v5** (identical levels, skins, budgets)
  with a *view*: `fog2` (only the 5x5 cells around the player are drawn; dark-grey fog elsewhere), `glimpse` (the
  whole level is visible until the first move of each level, and again after a RESET, which costs an action as
  always), `recolor` (from level 2, object colours are swapped one-to-one per level; shapes, floor, walls stay).
  Rendering only: rules, solver, optimal paths and budgets untouched; `engine verify`: 12/12.
  **Needs the new engine code on the VM + a server restart** (new optional `GameSpec.view`, `engine/src/engine/
  generator/view.py`, `render/frame.py`). An old server process cannot load eval-v6 (`GameSpec(**spec)` rejects
  `view`). Games without a view are unchanged: their spec dict has no `view` key, frames are byte-identical, and
  eval-v1/v2/v3b/v4/v5 all re-verify on the new code. 151 engine tests pass.
- **A2:** `contracts/engine_api.py` `GameSpec` gained `view: Optional[str] = None` (the contract test requires the
  field lists to match). Your file: I made only that additive change.

**Argon (Gemini 4, medium, h2) results so far** (run from A1's machine on local servers; runs in
`~/junction-data-v4local` (v4, v5) and `~/junction-data-v6local` (v6) on A1's machine: please merge once the sets
are on the VM):
- eval-v4: first 6 games all WIN 6/6, scores 0.86-0.99, efficiency on solved levels 0.93. Not harder for Argon.
- eval-v5: efficiency 0.85 so far, resets appear, twin levels 72/29 and 42/29 moves; still solves every level.
- eval-v6: just started.

**A4:** humans need these in the Gallery (collection `eval-v5`, `eval-v6`). On eval-v6 the X-ray / ghost overlays
would show the hidden map: keep them off for these runs.
**A5:** eval-v6 rows are a view variant of eval-v5 (same game seeds), worth a paired v5 vs v6 column.
