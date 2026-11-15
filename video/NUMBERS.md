# Numbers on screen

Every number in the video comes from a file below. Until the 07:00 lock these are live values that can still change;
re-fetch with `video/.venv/python.exe video/tools/fetch.py` and re-render before the final.

| Scene | What it shows | Source | Value used (fetched Sat 14.11 ~19:30) | Locked? |
|---|---|---|---|---|
| S0 | failure-mode counts (bar labels, log-scale bar heights) | live `/api/derived/rules.json` → `failure_modes[].count` | no_effect_loop 12,416; late_reset 894; belief_mismatch 860; unsolved_level 116; budget_exhaustion 79; rule_blindness 68 | no |
| S2 | h1 board: games won (bars, completion-first order) and efficiency (second number), models and first-attempt humans on `eval-v1` | live `/api/derived/leaderboard.json` rows `harness_version=h1, collection=eval-v1` (+ `kind=human, collection=eval-v1`) | Gemini 4 Carbon 0.925, Argon 0.900, Hydrogen 0.820, Kimi K3.1 0.712, Gemini 3.8 Flash 0.676, Opus 5.5 0.506, humans 0.365, Qwen3.5 9B SFT v1 0.007, Gemma 4 E4B 0.001, Nemotron 0.000 | no |
| S2 | h2 board | same file, `harness_version=h2` (eval-v1 + eval-v2), humans eval-v2 | Gemini 3.1 Pro 0.803, Kimi K3.1 0.738, Claude Haiku 5.5 0.657, Kimi K3.1 eval-v2 0.463, humans eval-v2 0.438 | no |
| S2 | optimal reference | definition (BFS optimal run scores 1.000 by construction) | 1.000 | yes |
| S1 | seed counter 1001–1036 (montage) | engine in-process, `MONTAGE_SEEDS` in `video/tools/export_engine.py` | 1001–1036 | yes (identifiers, not results) |
| S1 | optimal moves of the shown level | engine in-process, `GameSpec(seed=1000, difficulty=1)` level 2 (`video/tools/export_engine.py`) | 9 | yes (engine output) |
| S4 | Harbor baselines | `coordination/JUDGING.md` Results (dev game, Harbor 0.26.0 + Docker) | nop 0.000 (0 actions, 0/6); stop after L1 0.167 (13 actions, 1/6); oracle 1.000 (92 actions, 6/6) | yes (measured) |
| S5 | held-out MATH (items 26-50/subject, 175, paired): base 0.634, `think-games-h2` step 30 0.674, delta +0.040, 95% CI [-0.029, +0.103], McNemar p = 0.31; spoken "four points", "thirty steps" | A2 message Sun ~04:10, files on the B200 `/root/b200bench/out/` (not in `data/derived` yet); values in `video/s5_training.json`. Strict v5 finalist is step 40 (+0.011), shown as footnote. **Superseded by A2's fresh 1,400-item test (~04:35)** | as listed | no (preliminary, drawn in placeholder colour) |
| S5R | rover missions completed, scrambled controls: Gemini 4 Argon 30/30 (89-100%), Gemini Flash 29/30 (83-99%), Qwen3.5-9B thinking off 8/150 (3-10%), trained on our games thinking on (`think-h2-s60`) 51/100 (41-61%), Qwen3.5-9B thinking on: pending | A3 `experiments/edge_rover/README.md` + `results-*/`, **branch `origin/agent/a3` (d185be0), not on main yet**; all values in `video/rover.json` | as listed | partly (base thinking-on still running) |
| S5R | replayed mission: seed 5000, 16 steps, success | `results-think/think-h2-s60-hidden.jsonl` via `video/tools/fetch_rover.py` (map rebuilt from the seed with A3's `mission2.py`; replay checked against the recorded result) | 16 | yes |
| S6 | business ideas (no numbers) | **PLACEHOLDER** until `docs/BUSINESS.md` | — | no |
| S7 | URL / QR | `coordination/API_URL` + `/challenge` | 65.108.33.107.compute.verda.run/challenge | ask Anssi |
| S0, S3 (spoken) | "walks into the same wall eleven times" | trace `20261114T015741-02f65e44` steps 16–26: 11 consecutive `ACTION4` with event `bump` | 11 | yes (trace) |
