# Data behind the episodic RL rounds (gzipped JSON lines)

| File | What |
|---|---|
| `rollouts-b200-try1.jsonl.gz` | Round 1, base 4B, B200 games 0-1017, levels with optimal <= 9 (300-token answer budget: many invalid JSON replies) |
| `rollouts-b200-try2.jsonl.gz` | Round 1, same levels, 900-token answer budget |
| `rollouts-h100.jsonl.gz` | Round 1, H100 games 1018-2034, levels with optimal <= 9 |
| `rollouts-b200-v3.jsonl.gz` | Round 1, B200 games 0-1017, forced-valid JSON (schema repair) |
| `rollouts-r2.jsonl.gz` | Round 2, round-1 model: the 30 won levels x4 + 417 easy levels (`r2_episodes.jsonl`) |
| `rollouts-r3.jsonl.gz` | Round 3, round-2 model: 320 fresh levels with 10 optimal moves, 2 shots each (`r3_episodes.jsonl`) |
| `train-rft.jsonl.gz` / `-rft2` / `-rft3` | Training sets for the round 1 / 2 / 3 adapters (+ `.manifest.json` with counts) |

**Rollout rows:** one per episode, with these fields:
- `game_id`, `level`, `attempt`
- `solved`, `reward` (min(1, optimal/actions) if solved, else 0)
- `optimal`, `actions`, `repaired`
- `system` prompt
- `turns`: one entry per turn, with the prompt (`user`), the full model `reply` including `<think>`, `valid`, `forced`

**Training rows:** `{"messages": [system, user, assistant], "meta": {...}}`.
