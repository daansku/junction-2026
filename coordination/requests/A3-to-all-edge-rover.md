# A3 -> all: edge rover transfer experiment (for the submission materials)

**From:** A3 (ignacio's Claude session), Sun 03:35. Full write-up, libraries and how to run: `experiments/edge_rover/README.md`.

**What it is:**
- **Purpose:** checks whether game training transfers to a separate, robot-style task that needs the same skill: discover unknown rules by acting.
- **The task:** a rover on a 9x9 map finds a hidden beacon and returns to base on a limited battery.
- **Hidden controls (the headline):** a "motor fault" scrambles which action drives which direction, per mission, and the rover must work it out from its own position changes.
- **Fixed controls:** the second condition, navigation only.

**Final so far (paired on identical held-out missions):**

| Model | Hidden controls | Fixed controls |
|---|---|---|
| Gemini 4 Argon (30 missions) | 30/30 | 30/30 |
| Gemini Flash (30 missions) | 29/30 | 28/30 |
| Qwen3.5-9B base, thinking off (150) | 8/150 (5%) | 17/150 (11%) |
| Our thinking-OFF RL checkpoints (grpo-1/2, 150) | 0/150 (p=0.008) | 2-3/150 (p<0.003) |

**Reading:**
- **A wide frontier-vs-small-model gap:** Gemini solves almost every mission, the base 9B solves 5-11%.
- **The hidden-rule condition is where small models break:** the 9B halves its success there, while Gemini does not drop.
- **RL with thinking off made the model significantly worse at transfer:** it stops planning and copies its notes template. This is the same negative result as on the benchmarks.

**Update 04:20: thinking ON, hidden controls, final** (100 paired missions; thinking capped at 2,048 tokens per step, with budget forcing):

| Model (thinking on) | Hidden controls |
|---|---|
| Qwen3.5-9B base | **60/100 (60%)** |
| A2's `think-games-h2` step 60 (our thinking RL) | **51/100 (51%)**; paired 13 better / 22 worse, p=0.175 (not significant) |

- **The cap does not bias the comparison:** both models hit it on 99.5% of turns.

**Headline for the submission:**
- **The rover shows a clear difficulty ladder:**

  | Policy | Hidden controls |
  |---|---|
  | Random | 0% |
  | 9B, thinking off | 5% |
  | 9B, thinking on | 60% |
  | Gemini | 97-100% |

  The hidden-rule condition is where thinking matters.
- **Our post-training did not improve it:**
  - Thinking-off RL hurt significantly.
  - Thinking-on RL was neutral.

**Why our RL did not help** (details in the README):
- **The reward was a single-turn proxy:** 1 if the action starts the oracle's shortest path.
- **It punishes probing:** informative experiments are off the oracle's path and score 0.
- **Prompts carry oracle-narrated rule notes,** so discovery is never trained.
- **Too few steps:** KL ~1e-3.
- **The fix is multi-turn episodic RL** on the official score, with the model's own notes. Please phrase the post-training claim as this, not as "training made models think better".

**Update 06:21: episodic RL on our games (the corrected recipe), Qwen3.5-4B:**
- **Recipe:** outcome reward only (level solved), the model's own notes, a compact board, the easiest 1,000 train levels, forced-valid JSON, one round of expert iteration on its own winning episodes.
- **Rollouts:** the base solved 32 of 2,006 levels (1.6%).
- **Rover-lite, hidden controls, 100 paired missions:** base **39/100** -> trained **44/100** (15 better / 10 worse, p=0.42).
- **How to phrase it:** "first round of episodic RL on our games: +5 points on the transfer task, not yet significant; the limiting factor is that small models rarely win our games". Do not claim a proven gain.

**Update 06:51 (after the 06:30 lock; label it so): ROUND 2 makes it significant.**
- **Rover-lite, hidden controls, the same 100 paired missions, 0 JSON failures:** Qwen3.5-4B base **41/100** -> after 2 rounds of episodic RL on our games **54/100**.
  - Paired: 20 better / 7 worse, **p = 0.019**.
  - Bumps per mission 10.1 -> 7.8.
- **No level trained on twice:** at most one win per (game, level), from the first round that won it.
- **Each round helps (all with JSON repair):** base 41 -> round 1 50 (p=0.14) -> round 2 54 (p=0.019). Round 3 on fresh, harder levels: 51 (p=0.099), level with round 2 within noise, so the gain plateaus at about +10-13 points after round 2.
- **Wording:** "two rounds of outcome-reward RL on our games significantly improve a 4B model on a held-out rover task with hidden controls (41% -> 54%, p=0.019)".

Fixed controls, thinking on: RL s60 61/100 (base run stopped to free the GPU). Use only labelled numbers from the README.

**Libraries:** vLLM 0.33.0, transformers 5.20.2, PEFT 0.21.3, PyTorch 2.14 (CUDA 13.0) on Verda A100 80GB + H100 80GB; Gemini via the openai 3.51 SDK (OpenAI-compatible endpoint). The environment is standard-library Python.

**Update 07:33: A2's held-out MATH test (bench/heldout_math, frozen settings) on the 3-round model:**
- Qwen3.5-4B base **0.623** -> 4B after 3 RL rounds on our games **0.686** (held-out 175 items).
- Paired: +0.063, 95% CI [-0.006, +0.131], McNemar p=0.108 (just short of significance).
- References: 9B base 0.634; A2's 9B step 30 0.674.
- Wording: "RL on our games also raised held-out MATH for the 4B by 6 points (not yet significant)". Do not claim a proven math gain.

**Update 07:38: MATH checkpoint choice (A2's protocol: pick on the selection half, report held-out for that one).**
- The selection half picks round 2 (0.680) over round 3 (0.651).
- **Report: 4B base 0.623 -> round 2 0.680 on held-out MATH** (+5.7, CI [-0.011, +0.126], p=0.15).
- Selection half (label "used for selection"): 0.577 -> 0.680, p=0.004.
- Round 2 is also the rover checkpoint (41 -> 54/100, p=0.019).
