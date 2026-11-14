# Numbers on screen

Every number in the video comes from a file below. Until the 07:00 lock these are live values that can still change;
re-fetch with `video/.venv/python.exe video/tools/fetch.py` and re-render before the final.

| Scene | What it shows | Source | Value used (fetched Sat 14.11 ~19:30) | Locked? |
|---|---|---|---|---|
| S0 | failure-mode counts (bar labels, log-scale bar heights) | live `/api/derived/rules.json` → `failure_modes[].count` | no_effect_loop 12,416; late_reset 894; belief_mismatch 860; unsolved_level 116; budget_exhaustion 79; rule_blindness 68 | no |
