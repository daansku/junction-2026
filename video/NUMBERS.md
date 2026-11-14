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
| S5 | base / ctrl / ours mean accuracy + 95% CI | **PLACEHOLDER**, drawn in placeholder colour. Target: `data/derived/bench/<run>/summary.json` | 0.600 / 0.610 / 0.630 (invented layout values) | no |
| S6 | business ideas (no numbers) | **PLACEHOLDER** until `docs/BUSINESS.md` | — | no |
| S7 | URL / QR | `coordination/API_URL` + `/challenge` | 65.108.33.107.compute.verda.run/challenge | ask Anssi |
| S0, S3 (spoken) | "walks into the same wall eleven times" | trace `20261114T015741-02f65e44` steps 16–26: 11 consecutive `ACTION4` with event `bump` | 11 | yes (trace) |
