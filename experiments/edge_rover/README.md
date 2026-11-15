# Edge rover: does game training transfer to a robot-style task?

**Status (Sun 04:20):**
- **Final:** the thinking-off results, Gemini Flash/Argon, and thinking-ON hidden controls (base **60/100** vs our RL **51/100**, p=0.175).
- **Still running:** thinking-ON fixed controls (RL ~04:30, base ~05:15). This file will be updated.

## The question
Our games ask a model to discover unseen rules by acting. Does training on them make a model better at a separate task that
needs the same skill? The transfer target is a small rover mission an edge-sized model could run on board.

## The task (rover v2, `mission2.py`)
- **Mission:**
  - 9x9 grid with walls (19% density) and a hidden beacon.
  - The rover starts at base B in the centre.
  - It must find the beacon G, then drive back to B, before the battery runs out.
- **Observation, as text each step:**
  - The map seen so far; the sensor reveals cells within Manhattan distance 2.
  - Its own position (odometry), the energy left, the last 12 actions with position before/after (or BUMP), and the planner's own notes from the previous step.
- **Energy:**
  - The shortest one-way path from base to beacon is 5-10 steps.
  - The battery holds 2 x one-way + 30.
  - Every action costs 1, including bumps.
- **Two conditions:**
  - **hidden controls (the headline):** a "motor-controller fault" scrambles which of ACTION1-4 drives north/south/west/east, differently per mission. The rover must work the mapping out from its own position changes, then explore. This is the skill our games train: find the rules by acting.
  - **fixed controls:** the mapping is spelled out (navigation only).
- **Deterministic:** every mission is generated from its seed (`Rover.create(seed, controls)`).
  - Dev seeds 1000-1029 were used once to set the difficulty knobs (goal distance, energy slack, reply length).
  - Test seeds 5000-5149 never touched calibration.
- **Reference policies (200 dev seeds):**

  | Policy | Fixed controls | Hidden controls |
  |---|---|---|
  | Scripted frontier-explorer oracle | 88% | 82% |
  | Random | 0% | 0.5% |

  The oracle probes the controls, then explores with BFS. So the task is solvable within the budget, and luck does not solve it.
- **Reply format:** the model must reply with JSON `{"notes": "...", "action": "ACTION1|..|ACTION4"}`. An unparseable reply is an invalid turn: no move, no energy spent, but it counts toward a turn cap of battery + 10.

### Why v1 was replaced
The first version (`mission.py`, `run_eval.py`; Codex, Sat night) had every model at **0/30**:
- The 1.5B base pressed ACTION1 (north) into a wall for the whole battery.
- The tuned 1.5B model did the same with ACTION2.

A task at the floor cannot show a training effect, and its fixed controls did not test rule discovery.

## Models compared
All are Qwen3.5-9B variants, so every difference comes from training only.

| Name | What it is | Thinking during training |
|---|---|---|
| `base` | Qwen/Qwen3.5-9B, untouched | - |
| `grpo1` | games SFT v2 LoRA, then GRPO 25 steps on game turns + aux tasks (`/root/ckpt/grpo-1/step-25`) | **off** |
| `grpo2` | games SFT v2 LoRA, then GRPO 20 steps on game turns only (`/root/ckpt/grpo-2/step-20`) | **off** |
| `think-h2-s60` | A2's `think-games-h2`: GRPO from base, h2-format single decisions on train-v3b, step 60 (`/root/rl/think-games-h2/step-60`) | **on** |
| Gemini 4 Argon / Flash / Carbon | frontier reference via the Gemini API (`reasoning_effort` medium/high) | - |
| `q15base` / `q15boot` | Codex's v1 pair: Qwen2.5-1.5B-Instruct and its game-bootcamp LoRA | off |

LoRA stacks are merged into plain checkpoints with `merge_stack.py`, in training order: base, then SFT, then RL.

## Results

### Thinking OFF: final
150 test seeds, greedy decoding, paired on identical missions. The p-values are exact McNemar tests vs base.

| Model | Hidden controls | Fixed controls |
|---|---|---|
| base Qwen3.5-9B | **8/150 (5%)**, 95% CI 3-10% | **17/150 (11%)**, 95% CI 7-17% |
| grpo1 (thinking-off RL) | 0/150, p=0.008 | 2/150, p=0.0007 |
| grpo2 (thinking-off RL) | 0/150, p=0.008 | 3/150, p=0.003 |
| Qwen2.5-1.5B base / bootcamp LoRA | 0/150 / 0/150 | 0/150 / 0/150 |

**Reading:**
- RL with thinking off made the model *significantly worse* than base at the transfer task.
- Its notes collapse into a copy of the template ("short memory: what each action does, plan"). It stops planning and drives in small loops.
- This matches the team's earlier negative result on benchmarks: games SFT with thinking off taught the model to skip reasoning (`coordination/requests/A3-to-all-RESULTS.md`).
- The 1.5B models cannot do the task at all:
  - The base never produced a valid action.
  - The tuned model only bumps into walls.

### Frontier reference: final for Argon and Flash
30 test seeds (5000-5029).

| Model | Hidden controls | Fixed controls |
|---|---|---|
| Gemini 4 Argon (medium) | 30/30 | 30/30 |
| Gemini Flash (high) | 29/30 | 28/30 |
| Gemini 4 Carbon (medium) | (last mission still running; 29/29 and 30/30 so far) | |

**Reading:**
- Frontier models solve the task almost always, while base 9B solves 5-11%.
- With hidden controls the 9B halves its success, while frontier models do not drop at all.
- The gap is wide, and the hidden-rule condition is where small models break.

### Thinking ON: RL hidden controls final; base still running
`base` vs `think-h2-s60`, 100 test seeds (5000-5099), both conditions.

| Model (thinking on) | Hidden controls | Fixed controls |
|---|---|---|
| base Qwen3.5-9B | **60/100 (60%)**, 95% CI 50-69% | running (~05:15) |
| think-h2-s60 (RL on our games) | **51/100 (51%)**, 95% CI 41-61%; paired vs base: 13 better / 22 worse, McNemar p=0.175 (not significant) | running (~04:30) |

**Like-for-like check:** both models hit the 2,048-token thinking cap on **99.5%** of turns (base 3,472/3,488, RL 3,522/3,541; ~2,045 tokens per turn). Both had 1.4 bumps per mission and ~1.4 invalid turns per mission.

**The RL model's hidden-controls run, in numbers:**
- **Beacons:** found on 59 of 100 missions; 51 completed the return to base.
- **Successful missions:** 24.9 actions on average, 17 energy left.
- **Bumps:** 1.4 per mission, against 30 for thinking-off base.
- **The thinking cap:** 3,522 of its 3,541 turns hit the 2,048-token cap, so almost every action was a budget-forced answer. 148 turns were still invalid.

**Reading (hidden controls final):**
- **Thinking is the whole effect.** The same base model goes from 5% (thinking off) to **60%** (thinking on) on hidden controls, with no training.
- **Our thinking RL did not improve transfer.** It scored 51% against the base's 60%. That is not a significant difference (p=0.175), so read it as "no gain", not "harm".
- **Thinking-off RL made transfer significantly worse** (see above).
- **The difficulty ladder is clear:**

  | Policy | Hidden controls |
  |---|---|
  | Random | 0% |
  | 9B, thinking off | 5% |
  | 9B, thinking on | 60% |
  | Gemini | 97-100% |

  The hidden-rule condition is where thinking matters.

### Why our RL did not help: the training targeted the wrong skill
We checked the reward and task code: `engine/src/engine/tasks/gameturn.py`, `engine/src/engine/tasks/rationale.py`, `posttrain/src/posttrain/grpo.py`.
- **Single-turn proxy reward, not episodes.** Each sample is one game state. The reward is 1 if the chosen action starts a *shortest path to finishing the level*, computed by BFS over the true engine state with all hidden rules known. The model never plays an episode and never earns the official score (levels solved, optimal/actions).
- **Probing is punished.** Any informative experiment ("what does this tile do?", "which action is up?") scores 0, because it is not on the oracle's shortest path. Rule discovery needs exactly those actions; on the rover, it is how the scrambled controls are found.
- **The discovery is supplied.** Prompts come from oracle playthroughs, with NOTES written by a Narrator from engine truth. The notes only state effects already seen, but they are the oracle's correct reading. The model is handed correct rule notes and asked for the next move, so it never has to form, test or revise hypotheses itself.
- **Too little training to move the model.** About 60-70 GRPO steps x 64 completions, KL ~1e-3 (A2's log). A2's benchmark runs also found no measurable transfer.
- **What training should look like to test "training makes models think better":** multi-turn episodic RL on full games (h2/h2b format), with the official per-level score as the reward and the model writing its own notes. Exploration is then paid only through outcomes. It did not fit before the 06:30 lock.

- **Decoding settings:**
  - Qwen3.5 model-card sampling: T=0.6, top_p=0.95, top_k=20, seeded per mission and turn.
  - Thinking is capped at 2,048 tokens per step for both models.
  - **Budget forcing:** a reply cut off inside `<think>` gets "Time is up. I must answer now. `</think>`" appended, and the model then gives its JSON answer greedily. A cut-off costs no extra turn, and the count of forced answers is recorded per mission.
- **Live direction metric**, logged per step in `think/<name>-<controls>.metrics.jsonl`:
  - **good-move %:** the share of moves that got the rover closer, on the true map, to its current target (the beacon, then base).
  - **Random play:** ~40%.
  - **Also logged:** bump %, mean distance to target, beacons found and successes so far.
- **RL over its hidden-controls run:** 57% good moves overall.
  - Per step, it peaks at ~75% around step 18.
  - After that the per-step average falls, because the missions that finish leave the pool and the stuck rovers remain (survivorship). Completed missions only ever go up.

## How to run
**GPU eval, one model, all missions batched; each step is one vLLM generate call:**
```bash
CUDA_VISIBLE_DEVICES=0 python run_eval2.py --model Qwen/Qwen3.5-9B --name base --seeds 5000-5149 --outdir results
CUDA_VISIBLE_DEVICES=0 python run_eval2.py --think --model /root/ckpt/merged-think-h2-s60 --name think-h2-s60 \
    --seeds 5000-5099 --outdir think
```

**Merge a LoRA stack (e.g. SFT, then RL):**
```bash
python merge_stack.py --base Qwen/Qwen3.5-9B --lora /root/ckpt/games/lora --lora /root/ckpt/grpo-1/step-25 \
    --out /root/ckpt/merged-grpo1
```

**API models** (arena model registry `arena/models.yaml`, keys from the repo `.env`, never printed):
```bash
python run_api.py --model gemini-4-argon --effort medium --seeds 5000-5029 --outdir test-api --workers 60
```

**Tables** (Wilson 95% CI, paired McNemar vs a reference model):
```bash
python summarize2.py results-nothink/*.jsonl --ref base
```

**Sanity-check reference policies** (oracle vs random):
```bash
python mission2.py
```

**Live progress bars + direction metrics** (ssh to both GPU boxes):
```bash
python progress.py
```

## Libraries and hardware

| Where | Software | Hardware |
|---|---|---|
| GPU eval | Python 3.12.16, **vLLM 0.33.0**, **transformers 5.20.2**, **PEFT 0.21.3**, **PyTorch 2.14.0+cu130** (CUDA 13.0) | NVIDIA **A100-SXM4-80GB** (GPU 0) and **H100 80GB HBM3**, driver 580.178.04, on Verda (ex-DataCrunch) |
| API runs | Python 3.12.10, **openai 3.51.0** (Gemini's OpenAI-compatible endpoint, through `arena.providers.openai_compat.make_client`), PyYAML 6.0.3 | laptop |

- **Training** of the checkpoints was done earlier with TRL GRPO, LoRA r=16, on Modal/Verda H100s and A2's B200 (see `coordination/`).
- **Environment code** (`mission2.py`, `summarize*.py`) is standard library only.

## Files
| File | What it does |
|---|---|
| `mission2.py` | rover v2 environment + oracle/random reference policies |
| `run_eval2.py` | batched vLLM evaluator (thinking off / `--think`), per-step metrics |
| `run_api.py` | same missions, same prompt and parser, for API models |
| `merge_stack.py` | merges LoRA stacks into a vLLM-servable checkpoint |
| `summarize2.py` | results table with CIs and paired tests |
| `progress.py` | live CLI progress for the GPU runs |
| `results-nothink/` | final thinking-off rows (one JSON line per mission, with full action history) |
| `results-think/` | thinking-on rows + per-step direction metrics (`*.metrics.jsonl`) |
| `test-api/` | Gemini rows |
| `mission.py`, `run_eval.py`, `build_bootcamp.py`, `combine_bootcamp.py`, `summarize.py` | v1 (Codex), kept for the record |

## Caveats
- **This is a simulator transfer test**, not robot hardware: no power, latency or safety claims.
- **Small samples:**
  - Gemini rows are 30 missions each.
  - The thinking-on comparison is 100 paired missions.
  - At base rates of 5-11%, only large effects are significant.
- **Not fully clean A/B pairs:**
  - The thinking-off RL checkpoints started from a games SFT, so they differ from base in two training stages.
  - `think-h2-s60` is a clean base -> RL pair.
- **Effort levels:** Gemini models ran at the effort levels used elsewhere in the project (Argon/Carbon medium, Flash high). Their reasoning text is not returned by the endpoint.
