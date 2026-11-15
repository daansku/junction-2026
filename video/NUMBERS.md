# Numbers on screen

Every number in the video comes from a file below. Until the 07:00 lock these are live values that can still change;
re-fetch with `video/.venv/python.exe video/tools/fetch.py` and re-render before the final.

| Scene | What it shows | Source | Value used (fetched Sat 14.11 ~19:30) | Locked? |
|---|---|---|---|---|
| S0 | failure-mode counts (bar labels, log-scale bar heights) | live `/api/derived/rules.json` → `failure_modes[].count` | no_effect_loop 12,416; late_reset 894; belief_mismatch 860; unsolved_level 116; budget_exhaustion 79; rule_blindness 68 | no |
| S2 | h1 board, `eval-v2` only (Anssi, Sun): games won (bars) + efficiency; rows with >= 3 finished games | live `/api/derived/leaderboard.json` built 01:30 UTC, `harness_version=h1`, `collection=eval-v2` | humans 79% won (eff 0.67, 28 games), Gemini 4 Carbon 42% (0.68), Gemini 4 Argon 10% (0.47), Kimi K3.1 0% (0.22), Gemini 3.8 Flash 0% (0.10) | no (re-fetch at lock) |
| S2 | h2 board, `eval-v2` only, effort in the label | live `/api/derived/leaderboard_h2.json` built 01:30 UTC | Gemini 4 Argon medium 100% won (eff 0.89, 5 games), humans 94% (0.65), Gemini 4 Carbon medium 86% (0.85), Gemini 3.8 Flash high 44% (0.66), DeepSeek 4.1 Flash high 6% (0.47), Gemini 3.1 Pro high 0% (0.44), Kimi K3.1 max 0% (0.40), Gemini 3.1 Pro medium 0% (0.11). Spoken: "the best model finishes every game, but still needs more moves than the optimal run. Most models finish none." | no (re-fetch at lock) |
| S2 | optimal reference | definition (BFS optimal run scores 1.000 by construction) | 1.000 | yes |
| S1 | seed counter 1001–1036 (montage) | engine in-process, `MONTAGE_SEEDS` in `video/tools/export_engine.py` | 1001–1036 | yes (identifiers, not results) |
| S1 | optimal moves of the shown level | engine in-process, `GameSpec(seed=1000, difficulty=1)` level 2 (`video/tools/export_engine.py`) | 9 | yes (engine output) |
| S4 | Harbor baselines | `coordination/JUDGING.md` Results (dev game, Harbor 0.26.0 + Docker) | nop 0.000 (0 actions, 0/6); stop after L1 0.167 (13 actions, 1/6); oracle 1.000 (92 actions, 6/6) | yes (measured) |
| S5 | MATH dev slice, the items used to pick the checkpoint (items 1-25/subject, 175), chosen by Anssi: base 0.589 (103/175), `think-games-h2` step 30 0.640 (112/175); no CI whiskers on screen (Anssi); spoken "five points", "thirty steps". Held-out items 26-50 (not shown): base 0.634, step 30 0.674, paired delta 95% CI [-0.029, +0.103], p = 0.31 | A2 message Sun ~04:10, B200 `/root/b200bench/out/`; values in `video/s5_training.json`; strict v5 finalist step 40 shown as footnote | as listed | yes (Anssi) |
| S5R | rover-lite missions completed, scrambled controls, 100 paired missions: scripted explorer 98%, random 4%, Qwen3.5-4B 39/100, Qwen3.5-4B trained on our games (one round of expert iteration) 44/100; spoken "thirty-nine", "forty-four". Not shown: paired 15 better / 10 worse, McNemar p = 0.42 (not significant) | A3 `experiments/edge_rover/README.md` "Episodic RL on our games ... final 06:21", `results-rl4b/`, **branch `origin/agent/a3` (6d25e47), not on main**; values in `video/rover.json`. Best rover result we have (Anssi) | as listed | yes (Anssi) |
| S5R | replayed mission: rover-lite seed 5019, trained 4B, 12 steps, success | `results-rl4b/rft4b-lite-hidden.jsonl` via `video/tools/fetch_rover.py` (map rebuilt with A3's `mission2.py`, `ROVER_LITE=1`; replay checked against the recorded result) | 12 | yes |
| S6 | business ideas (no numbers) | **PLACEHOLDER** until `docs/BUSINESS.md` | — | no |
| S7 | URL / QR | `coordination/API_URL` + `/challenge` | 65.108.33.107.compute.verda.run/challenge | ask Anssi |
| S0, S3 (spoken) | "walks into the same wall eleven times" | trace `20261114T015741-02f65e44` steps 16–26: 11 consecutive `ACTION4` with event `bump` | 11 | yes (trace) |
