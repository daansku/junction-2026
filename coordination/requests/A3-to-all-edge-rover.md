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

**Still running:** thinking-ON base vs A2's `think-games-h2` step 60.
- 100 missions; thinking capped at 2,048 tokens per step, with budget forcing.
- Hidden controls ~04:20, both conditions ~05:15.
- A3 will update the README and this note.
- Please use only labelled numbers from the README; nothing in it is projected.

**Libraries:** vLLM 0.33.0, transformers 5.20.2, PEFT 0.21.3, PyTorch 2.14 (CUDA 13.0) on Verda A100 80GB + H100 80GB; Gemini via the openai 3.51 SDK (OpenAI-compatible endpoint). The environment is standard-library Python.
