# A1 -> A4 (cc A5): commit one real Harbor + OpenCode run log on the judging set (human request: Daniel, Sun ~03:15)

**Why:** the organisers' "Before you submit" list requires *at least one Harbor run log with its score* in the repo
(see their message: "Include at least one Harbor run log with its score to show a model playing through your
environment"). `main` has result tables but no Harbor output, and the only OpenCode agent result is Nemotron on a
**dev** game. Judges run reference + 3 agent runs + do-nothing + stop-early through Harbor + OpenCode on eval-v2.
Your machine is the one with Docker + `harbor==0.26.0` (A1's has neither).

**Run (one command, the judges' protocol, Gemini credits):**
```bash
git pull
make judge MODEL=gemini/gemini-4-argon K=3 OUT=harbor/run-logs/eval-v2-s910000-argon-k3
```
(default `TASK` = `harbor/eval-v2/gridworld-s910000-d4-l8-f71ee29e`, the README's game 1; 60-min cap per agent run.)
Report whatever Argon scores, high or low: no game picking.

**Before committing, please:**
1. **Scan for secrets.** `judge.sh` passes API keys with `--ae`; Harbor may write resolved env values into job
   configs / logs. `grep -rIE 'AIza|sk-ant|dc_[0-9a-f]{20}|rc_[0-9a-f]{20}|wk-' harbor/run-logs/` must print nothing
   (redact if it does).
2. **Size.** Drop large binaries (images / screenshots) if the folder is over ~20 MB; keep every `result.json`,
   the verifier output (`reward.txt`, `reward.json`, `score_detail.json`), the agent trajectory / OpenCode log and
   each `<tag>.log`.
3. Add `harbor/run-logs/README.md` with the summary table `judge.sh` prints (date, Harbor + Docker versions, command).

**Then:** link it from `README.md` ("Verified Harbor Results": replace or add a row "OpenCode + Gemini 4 Argon,
k=3, eval-v2 game 1") and from `docs/SUBMISSION.md` §1 (A5 owns both; a one-line link is fine, or ask A5).
Optional if time allows: the same with `MODEL=gemini/gemini-3.8-flash` (cheaper, a second model on the judges' harness).

Deadline: numbers lock at 07:00, so ideally committed by ~06:00.
