# Video storyboard: draft v1 (A6, Sat 14.11)

**Status:** structure approved by Anssi (Sat 14.11). VO lines still draft; scenes being built.

## Decisions (Anssi, Sat 14.11)

| Topic | Decision |
|---|---|
| Use | Submission / backup video only |
| Length | 2–3 min (target 3:00) |
| Audio | TTS narration: free local voice for drafts, ElevenLabs for the final take |
| Tool | Manim Community Edition, own env in `video/.venv` (Python 3.12 + ffmpeg from conda-forge) |
| Look | Our palette and shapes (`web/DESIGN.md`, `contracts/palette.json`), with 3Blue1Brown-style smooth transitions (morphs, eased camera moves) |
| Cut order if time runs short | business value, then reward integrity, then post-training detail |
| Delivery | YouTube unlisted (Anssi uploads) + final MP4 and `.srt` in `video/` (under ~100 MB) |
| Opening | Anssi's idea: break one agent, then many; the pieces become a failure-mode chart, then a game frame |

## Visual language

- Background `#0e0e0f` (DESIGN `--bg`). Text in IBM Plex Sans / Plex Mono, `--text-1` / `--text-2`. Single accent `#ffdc00`.
- Game frames drawn cell by cell from real 64×64 frames with the 16-colour palette. Crisp squares, no rounding, thin `--line` border.
- **The agent sprite:** a small block made of palette cells (the player cell from a real frame, scaled up). When it fails, it splits into square shards in the colour of its failure mode.
- **Failure-mode colours** (fixed for the whole video, from the game palette):

| Failure mode (`rules.json`) | On-screen label | Colour |
|---|---|---|
| `no_effect_loop` | bumps walls, nothing changes | red `#E5383B` |
| `late_reset` | resets too late | orange `#F2832B` |
| `belief_mismatch` | acts on a wrong belief | magenta `#D63AAF` |
| `rule_blindness` | misses the new rule | azure `#6FD3F2` |
| `budget_exhaustion` | runs out of moves | yellow `#F5C518` |
| `unsolved_level` | never solves the level | grey `#8A8F98` |

- Transitions: shapes morph into the next scene's shapes (`Transform` / `ReplacementTransform`), camera moves are eased. No hard cuts except the cold open.
- Charts: flat bars, numbers in mono, baselines (optimal, human) as labelled reference lines, as on the web board.

## Scene list

Timings assume about 150 words per minute of narration. VO lines are drafts and will be tightened once Anssi approves the structure. `[N]` marks a number that must come from data (see `NUMBERS.md`).

### S0 Hook: break one, break many (0:00–0:22, 22 s)

| Time | On screen | Voice-over |
|---|---|---|
| 0:00 | Black. One agent sprite inside a small game frame. It moves, bumps a wall, and splits in half into red shards. | "Break one AI agent, and you learn one thing: it broke." |
| 0:06 | The camera pulls back fast. Dozens, then hundreds of small frames scroll past, each with an agent breaking into one of the six colours. No count is shown. | "Break thousands of them, on games none of them has ever seen…" |
| 0:12 | The shards fly together and sort by colour into six bars: the failure-mode chart. Labels fade in. | "…and the pieces stop being noise. They line up." |
| 0:17 | The bars collapse into cells and rebuild into a single 64×64 game frame. | "Every failure points at something an agent can't do yet. We built a factory that finds those things." |

Notes: the chart uses the real counts `[N1]`. `no_effect_loop` (2,706) dwarfs `rule_blindness` (22), so the bars use a log scale, or show only the ranking with the counts as labels. The count is not spoken.

### S1 The environment in 30 seconds (0:22–0:52, 30 s)

| Time | On screen | Voice-over |
|---|---|---|
| 0:22 | The frame from S0 zooms in. Three bands light up in turn: the move-budget bar (rows 0–1), the level and inventory pips (rows 3–4), the playfield. | "The agent sees only this: 64 by 64 pixels, 16 colours. No text, no score, no rule names." |
| 0:30 | Six action keys appear under the frame: `RESET`, `ACTION1`–`ACTION5`. The player takes a few real steps (optimal path replay). | "It can press six buttons. That's all." |
| 0:36 | The same level morphs through three colour skins (real `skin_shuffle` of one seed). | "Colours are reshuffled for every game, so nothing can be memorised." |
| 0:41 | Level strip: level 1, then levels 2–5, each showing one new mechanic icon (keys and doors, ice, teleporters…). | "Each new level hides one new rule. The agent has to discover it by experimenting." |
| 0:47 | The optimal path draws itself across the playfield in accent yellow. | "And every level is proven solvable by search, so we always know the best possible run." |

### S2 The gap (0:52–1:25, 33 s)

| Time | On screen | Voice-over |
|---|---|---|
| 0:52 | Board 1 (h1): bars grow for optimal `[N2]`, first-attempt humans `[N3]`, then the frontier models `[N4…]`. | "On games nobody has seen before, people beat the best AI models." |
| 1:05 | Board 1 slides left. Board 2 (h2) builds next to it: "run the way labs benchmark them": full conversation, maximum reasoning effort. | *(depends on the h2 result, see below)* |
| 1:18 | The gap between the reference line and the best model is highlighted with a bracket. | "The gap is there, it's reproducible, and it comes from decisions, not from tricks." |

**Open: the h2 line depends on data.** A3's first h2 results (17:30) show h2 closes most of the gap on the easy (d1) `eval-v1` games; d2/d3 and `eval-v2` are pending. Two versions, picked at the 07:00 lock:
- **Gap holds on harder games:** "Even run the way labs benchmark them, they lose on the levels with new rules."
- **Gap closes:** "Run the lab way, they close the gap on easy games. On new rules, [result]." The deck (A5) must use the same wording.

### S3 Why failures are meaningful: several replays (1:25–1:50, 25 s)

Anssi: show 2–4 failure modes. Start with one replay, scroll to the next, then pan out to many agents failing (mirrors the hook).

| Time | On screen | Voice-over |
|---|---|---|
| 1:25 | Replay 1, cell by cell `[N5]`: Nemotron on a `hazards` level, `no_effect_loop` from step 16 (`run 20261114T015741-02f65e44`). The model's stated hypothesis, word for word from the trace, sits next to the frame. Each bump flashes red; the budget bar shrinks. | "Here is one failure up close. The model thinks it is walking to the goal, but the screen doesn't change. It tries again. And again." |
| 1:35 | Scroll right to replay 2: Kimi K3.1, `late_reset` on a `one_way` level (step 123), orange tag. | "The strongest model walks into a dead end and resets far too late." |
| 1:40 | Scroll to replays 3–4 (one `belief_mismatch`, one `rule_blindness`; runs picked from `rules.json` examples), magenta and azure tags. | "Another acts on a belief the screen already disproved. Another never notices the new rule." |
| 1:44 | Camera pans out: the replays shrink into a wall of many failing agents, each tagged by colour. | "Everything they needed was on screen. Each mistake is a decision we can point to and measure." |

### S4 Reward integrity (1:50–2:10, 20 s)

| Time | On screen | Voice-over |
|---|---|---|
| 1:50 | The scoring rule builds as a picture: a solved level scores optimal moves divided by moves used; an unsolved level scores zero. | "The score rewards solving levels efficiently. Nothing else." |
| 1:57 | Three agents try shortcuts, each with its real score `[N6]`: do nothing (0.000), stop after one level (0.167), reset to wipe history (the moves still count). | "Doing nothing scores zero. Stopping early scores only the levels it solved. Resetting never erases the moves already spent." |
| 2:05 | The grader appears in its own sealed box, outside the agent's box. | "And the score is computed in a separate container the agent can't reach." |

### S5 Post-training (2:10–2:35, 25 s)

| Time | On screen | Voice-over |
|---|---|---|
| 2:10 | The failure-mode colours from S0 flow into one small agent: Qwen3.5-9B. | "Then we asked: can a small model learn from this experience?" |
| 2:16 | Three bars with 95% confidence intervals on the outside-benchmark suite: base, control (same amount of non-game training), ours `[N7]`. | *(depends on the result, see below)* |
| 2:28 | The control bar is marked as the honest comparison. | "We compare against a control trained on the same amount of non-game data, so the gain is from our games, not just from more training." |

**Open: the result line depends on the 07:00 lock.**
- **Gain with a CI that excludes zero:** "Trained on our games, it reasons better on outside benchmarks than the control."
- **No gain:** "On outside reasoning it did not beat the control. In our own games it improved by [N]. That is the honest result." (PLAN §3.3 honesty rule.)

### S6 Business value (2:35–2:48, 13 s)

| Time | On screen | Voice-over |
|---|---|---|
| 2:35 | Two or three short lines, each with a small pixel icon, from `docs/BUSINESS.md` (not written yet). Candidates: fresh contamination-proof evals for every evaluation; RL training environments for labs. | "A factory of fresh, verified games is useful beyond this hackathon: private evals that can't leak, and training environments for labs." |

### S7 Close (2:48–3:00, 12 s)

| Time | On screen | Voice-over |
|---|---|---|
| 2:48 | Callback to S0: the grid of agents again; this time a few of them reach the goal and light up in green. | "Every broken agent shows where AI still has to learn." |
| 2:54 | Pixel wordmark **Game Factory**, the public URL, and a QR code to `/challenge`. | "Try to beat the AI yourself." |

## Answered (Sat 14.11)

- Name on the end card: **Game Factory**.
- S3: several failure modes (2–4), scroll between them, then pan out.
- Ending: "Try to beat the AI yourself" + QR code to `/challenge`.
- Structure and timings approved.

## Dependencies

- h2 board result (A3), post-training result (A3/A2 `bench`), `docs/BUSINESS.md` (A5): placeholders until the 07:00 lock.
- Real frames: from the engine in-process or `/api/runs/{id}/steps`; no screen recordings needed.
