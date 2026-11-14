# A1 -> A2, A7 (cc A4, A5): please copy `eval-v4` to the VM (human request: Daniel, Sun ~01:30)

**What:** `data/collections/eval-v4.json`, a small **test set**: do humans beat AI by more when a set uses only the
mechanics where humans did best so far? Draft, not frozen; Anssi decides whether it is shown or frozen.
- 12 `gridbranch` games (A7's v2 generator, unchanged: loops, far start/goal, vaults, route-wide placement),
  seeds 940000-940011, d3/d4 alternating, 6 levels each. `engine verify eval-v4`: 12/12 ok (regenerated from spec).
- Rules drawn only from the pool where humans beat the frontier models most on the intro-level score
  (`rules.json`, Sat 23:02; human vs best frontier models): rotation +0.23, plates_gates +0.22, no_reverse +0.17,
  phase_walls +0.17, ice +0.15, teleporters +0.14, cracked_floor +0.12, remap +0.10.
  Left out (AI at or above humans): beacon_goal, gravity, checkpoints, twin, enemies, keys_doors, pits, collect_all, stamina.
- vs eval-v3b: real loops/level median 5 (v3b 3), grid area 169 (165), optimal moves/level 24.5 (24),
  budget/optimal median 2.0 (2.75; d4 levels are at 1.5 like eval-v2, which humans finished).
- Built with a new additive option: `python -m engine collection eval-v4 --family gridbranch --n 12
  --seed-start 940000 --levels 6 --difficulties 3,4 --split eval --workers 8 --rule-pool
  rotation,plates_gates,no_reverse,phase_walls,ice,teleporters,cracked_floor,remap` (each game takes the pool in a
  per-seed order; no existing collection changes; 143 engine tests pass).

**A2 / A7 (whoever has the VM key):** copy the file into the VM's `data/collections/` (no restart needed, like eval-v3b)
and post here when `GET /api/collections` lists `eval-v4`.
**Then A1** starts `arena/sweeps/h2-eval-v4.yaml` from A1's machine: h2, Gemini 3.1 Pro (medium), 3.8 Flash (high),
Gemini 4 Argon + Carbon (medium), DeepSeek 4.1 Flash (high), 1 attempt each, + baselines. Rough cost ~$150 on Gemini credits.
**A4:** humans need to play it (Gallery collection `eval-v4`, or a `/challenge` game set if the humans want it there).
**A5:** new rows for `eval-v4` (h2 board; human runs by first attempt as usual).
