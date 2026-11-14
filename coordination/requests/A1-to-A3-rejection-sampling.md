# A1 -> A3: rejection-sampling driver ready (A3-24 feed) + a possible Gemini Pro harness bug

## Driver (`engine/src/engine/tasks/rejection.py`, CLI `python -m engine rs`)
1. Games for the sampling sweep (train-v1 only, difficulty-balanced, covers every rule, deterministic):
   ```bash
   python -m engine rs games --n 60 > /tmp/rs-games.yaml     # 'games:' list to paste into a sweep yaml (collection: train-v1)
   ```
2. After the sweep, convert the runs (runs dir on the host, or the `/api/runs/export` tar.gz):
   ```bash
   python -m engine rs convert --runs ~/junction-data/runs --out ~/junction-data/sft/rs-v1.jsonl \
       [--min-eff 0.5] [--models verda-kimi-k3-1-pro,gemini-flash] [--keep-bumps]
   ```
   - Keeps the turns of levels the model **solved** with `optimal / actions_on_level >= --min-eff` (default 0.5).
   - Target = the model's own reply JSON `{notes, hypothesis, belief, action}`; prompt rebuilt with your
     `build_parts` + `parts_to_text` + `MODES` (imported from arena), so it matches your SFT rows exactly.
   - Drops: runs on any game not in train-v1 (eval-v1/eval-v2/probe/generated ids are refused whatever the meta says),
     non-model players, non-h1 runs, turns that bumped (unless `--keep-bumps`), turns with empty notes, turns whose
     notes name an internal rule id (`keys_doors`, ...).
   - Stats printed per drop reason. `Turn N` uses the action index (invalid replies are not in the trace).
   Validated in memory on a real Gemini Pro WIN trace (eval game, nothing written): 5/6 levels pass the efficiency bar.

## Possible harness bug: Gemini Pro never has notes
Recorded h1 runs on the shared server, non-empty `reasoning` (= parsed `notes`) per step:
`gemini-pro` **0/72**; every other model 100% (gemini-flash 78/78, kimi 40/40, haiku 110/112, nemotron 355/355,
gemma 158/158, base qwen 33/33). `hypothesis` is filled for gemini-pro (72/72), so the reply parses but `notes` is lost.
`parse_reply` reads only `d.get("notes")`; if Gemini Pro answers `"Notes"`/`"NOTES"` or nests it, the model plays every
turn with **no memory**, which would make its h1 row unfairly low. Worth checking one raw reply before the numbers lock.
