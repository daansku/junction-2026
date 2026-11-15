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

Still running: fixed controls (~05:15). Use only labelled numbers from the README.

**Libraries:** vLLM 0.33.0, transformers 5.20.2, PEFT 0.21.3, PyTorch 2.14 (CUDA 13.0) on Verda A100 80GB + H100 80GB; Gemini via the openai 3.51 SDK (OpenAI-compatible endpoint). The environment is standard-library Python.
