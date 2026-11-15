# Edge rover: does game training transfer to a robot-style task?

**Headline: two rounds of episodic RL on our games make Qwen3.5-4B significantly better at the held-out transfer task.**
- Rover-lite, hidden controls, the same 100 paired missions, JSON repair on (0 JSON failures): base **41/100** -> after round 2 **54/100**.
- Paired: 20 missions better, 7 worse, McNemar **p = 0.019**.
- Bumps per mission 10.1 -> 7.8.
- Round 1 alone was 44/100 (not significant). Details in "Episodic RL on our games" below.

**Status:**
- **Final:** the thinking-off results, Gemini Flash/Argon, and thinking-ON hidden controls (base **60/100** vs our RL **51/100**, p=0.175).
- **Not finished:** thinking-ON fixed controls. RL rows are in `results-think/think-h2-s60-fixed.jsonl`; the base run did not finish, so there is no paired result.

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
The first version (`mission.py`, `run_eval.py`; written with Codex) had every model at **0/30**:
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
| `think-h2-s60` | `think-games-h2`: GRPO from base, h2-format single decisions on train-v3b, step 60 (`/root/rl/think-games-h2/step-60`) | **on** |
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
- This matches the team's earlier negative result on benchmarks: games SFT with thinking off taught the model to skip reasoning.
- The 1.5B models cannot do the task at all:
  - The base never produced a valid action.
  - The tuned model only bumps into walls.

### Frontier reference: final for Argon and Flash
30 test seeds (5000-5029).

| Model | Hidden controls | Fixed controls |
|---|---|---|
| Gemini 4 Argon (medium) | 30/30 | 30/30 |
| Gemini Flash (high) | 29/30 | 28/30 |
| Gemini 4 Carbon (medium) | incomplete run: 29/29 and 30/30 missions finished | |

**Reading:**
- Frontier models solve the task almost always, while base 9B solves 5-11%.
- With hidden controls the 9B halves its success, while frontier models do not drop at all.
- The gap is wide, and the hidden-rule condition is where small models break.

### Thinking ON: hidden controls final; fixed controls not finished
`base` vs `think-h2-s60`, 100 test seeds (5000-5099), both conditions.

| Model (thinking on) | Hidden controls | Fixed controls |
|---|---|---|
| base Qwen3.5-9B | **60/100 (60%)**, 95% CI 50-69% | not finished |
| think-h2-s60 (RL on our games) | **51/100 (51%)**, 95% CI 41-61%; paired vs base: 13 better / 22 worse, McNemar p=0.175 (not significant) | rows in `results-think/`, no base to pair with |

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

### Episodic RL on our games (expert iteration), Qwen3.5-4B
The corrected training recipe, run on a B200 + H100.
- **Policy:** Qwen3.5-4B, thinking on (<=512 tokens per turn, with budget forcing).
- **Training games:** our real h1 harness on train-v1, never eval games.
  - The board is shown compactly: each cell as a colour+shape code, never rule names. Same information as the screen.
  - Curriculum: the 1,000 easiest levels (optimal <= 9 moves).
- **No oracle notes, no per-move reward:** an episode pays only if it solves its level.
- **Forced-valid JSON:** an unparseable answer is re-answered from the same reasoning with schema-constrained decoding.
- **Update:** LoRA SFT (r=16, 1 epoch) on the model's own winning episodes, thinking included. That is one round of rejection-sampling RL.

| Step | Result |
|---|---|
| Rollouts | **32 of 2,006** easy levels solved (1.6%); 498 training turns from 30 games (22 level-1, 10 rule levels) |
| Training | val loss 0.286 -> 0.153 (122 steps) |
| **Rover-lite, hidden controls, 100 paired missions** (7x7, beacon 3-6 away; oracle 98%, random 4%) | base 4B **39/100** -> trained 4B **44/100**; paired 15 better / 10 worse, McNemar p=0.42 (**not significant**) |
| Good moves / bumps per mission | 37.7% -> 36.8% / 10.9 -> 11.1 (unchanged) |

**Round 2:**
- **Rollouts:** the round-1 model played 537 episodes (its 30 won levels x4, plus 417 easy levels it never trained on).
- **New-level wins:** about 2.6%, against 1.6% for the base on similar levels.
- **Dataset rules:** each (game, level) contributes at most one win, from the first round that won it, so 28 replay wins were dropped and no level is trained on twice. Only efficient wins are kept (reward >= 0.4), and rule levels count 3x.
- **Training:** retrained from base on 43 unique won levels (992 turns), 1 epoch. Val loss 0.314 -> 0.116.
- **JSON:** every stage uses schema-constrained repair of unparseable answers, so JSON failures are 0. The base was re-run with the same repair: 41/100 (39 without repair).

| Rover-lite, hidden controls, same 100 missions | Completed | 95% CI | Bumps/mission | JSON failures | vs base (paired) |
|---|---|---|---|---|---|
| Qwen3.5-4B base (repair on) | 41/100 | 32-51% | 10.1 | 0 | - |
| after round 1 (repair on) | 50/100 | 40-60% | 9.0 | 0 | 19 / 10, p=0.14 |
| **after round 2 (repair on)** | **54/100** | 44-63% | **7.8** | 0 | **20 / 7, p=0.019** |
| (after round 1, earlier run without repair) | 44/100 | 35-54% | 11.1 | 17 | 16 / 13, p=0.71 |

| after round 3 (repair on) | 51/100 | 41-61% | 7.8 | 0 | 20 / 10, p=0.099 |

**Round 3:**
- **Rollouts:** the round-2 model played 320 FRESH, harder levels (10 optimal moves, never played by any round), 2 shots each.
- **Wins:** 13 new levels won (4.1% of levels), about twice the base's rate on easier levels.
- **Training:** retrained from base on 56 unique won levels (1,372 turns); val loss 0.319 -> 0.132.

**Reading across rounds:**
- RL on our games improves the held-out rover task by about **+10-13 points**: 41 -> 50 -> 54 -> 51.
- Bumps fall 10.1 -> 7.8.
- The gain is significant at round 2 (p=0.019). Round 3 is level with round 2, within noise (the CIs overlap), so the gain plateaus after round 2.

**Mechanics in the won levels:**

| Mechanic | Unique levels won |
|---|---|
| none (navigation) | 37 |
| ice | 8 |
| hazards | 4 |
| teleporters | 2 |
| push blocks | 2 |
| one-way | 1 |
| hazards+one-way | 1 |
| remap (scrambled controls) | 1 |

Two-thirds are plain navigation, so the transfer likely comes mostly from better board reading and planning. The next lever is sampling rule levels on purpose.

**Reading (round 1):**
- The direction is positive: +5 points, and 15 vs 10 discordant missions. This is too small to claim at n=100.
- The bottleneck is the reward itself: from scratch, a 4B wins only 1.6% of even the easiest levels, so one round has very little to learn from.
- What would make this conclusive, given more time:
  - several rounds (each round's model collects more wins);
  - more seeds;
  - a second transfer task.
- Files: `results-rl4b/` (rows, per-step metrics, training manifest); code in `game_rollouts.py`, `build_rft.py`.

### Held-out MATH (benchmark, `bench/heldout_math`, frozen settings)
The round-3 model (3 rounds of episodic RL on our games) on the held-out MATH test:
- 350 MATH items; 0-shot chain of thought; 8,192 tokens; temperature 1.0; seed 1234.
- Our models are 4B, so the 4B base got its own base run, as the README rules require.

| Model | MATH held-out (doc 25-49, 175 items) | other half (doc 0-24, 175) |
|---|---|---|
| Qwen3.5-4B base | 0.623 | 0.577 |
| 4B after 2 RL rounds on our games | 0.680 | 0.680 |
| 4B after 3 RL rounds on our games | 0.686 | 0.651 |
| (ref) Qwen3.5-9B base, stored run | 0.634 | 0.589 |
| (ref) 9B `think-games-h2` step 30 | 0.674 | 0.623 |

**Trained 4B vs 4B base, paired (`bench/heldout_math` `compare.py`):**
- **Held-out:** **+0.063**, 95% CI [-0.006, +0.131]; only-trained-right 25 vs only-base-right 14; McNemar p=0.108. Just short of significance.
- **Other half:** +0.074, CI [+0.006, +0.143], p=0.060. We never used MATH to select anything, but by the protocol's rule the held-out half is the reported number.

**Round 2 vs 4B base, paired:**
- **Held-out:** +0.057, CI [-0.011, +0.126], McNemar p=0.154.
- **Selection half:** +0.103, CI [+0.040, +0.171], p=0.004.

**Checkpoint choice, by the protocol:** the selection half picks **round 2** (0.680 vs round 3's 0.651).
- **Number to report:** round 2 held-out MATH **0.623 -> 0.680** (+5.7 points, p=0.15, not significant).
- The selection-half gain of +10.3 (p=0.004) may be shown only with the label "used for selection".
- Round 2 is also the best rover checkpoint (54/100, p=0.019).

**Reading:**
- Training on our games did not hurt math. It moved the 4B up by about 6 points, past the untrained 9B.
- The training reward never touched math. The gain is consistent with the rover transfer, but needs more items or seeds to be conclusive.

Files: `results-math/` (per-item scores, paired comparison).

### Why our earlier RL did not help: the training targeted the wrong skill
We checked the reward and task code: `engine/src/engine/tasks/gameturn.py`, `engine/src/engine/tasks/rationale.py`, `posttrain/src/posttrain/grpo.py`.
- **Single-turn proxy reward, not episodes.** Each sample is one game state. The reward is 1 if the chosen action starts a *shortest path to finishing the level*, computed by BFS over the true engine state with all hidden rules known. The model never plays an episode and never earns the official score (levels solved, optimal/actions).
- **Probing is punished.** Any informative experiment ("what does this tile do?", "which action is up?") scores 0, because it is not on the oracle's shortest path. Rule discovery needs exactly those actions; on the rover, it is how the scrambled controls are found.
- **The discovery is supplied.** Prompts come from oracle playthroughs, with NOTES written by a Narrator from engine truth. The notes only state effects already seen, but they are the oracle's correct reading. The model is handed correct rule notes and asked for the next move, so it never has to form, test or revise hypotheses itself.
- **Too little training to move the model.** About 60-70 GRPO steps x 64 completions, KL ~1e-3. Benchmark runs also found no measurable transfer.
- **What training should look like to test "training makes models think better":** multi-turn episodic RL on full games (h2/h2b format), with the official per-level score as the reward and the model writing its own notes. Exploration is then paid only through outcomes. It did not fit in the hackathon.

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


## Libraries and hardware

| Where | Software | Hardware |
|---|---|---|
| GPU eval | Python 3.12.16, **vLLM 0.33.0**, **transformers 5.20.2**, **PEFT 0.21.3**, **PyTorch 2.14.0+cu130** (CUDA 13.0) | NVIDIA **A100-SXM4-80GB** (GPU 0) and **H100 80GB HBM3**, driver 580.178.04, on Verda (ex-DataCrunch) |
| API runs | Python 3.12.10, **openai 3.51.0** (Gemini's OpenAI-compatible endpoint, through `arena.providers.openai_compat.make_client`), PyYAML 6.0.3 | laptop |

- **Training** of the checkpoints was done earlier with TRL GRPO, LoRA r=16, on Modal/Verda H100s and a B200 (trainer: `posttrain/`).
- **Environment code** (`mission2.py`, `summarize*.py`) is standard library only.

## Files
| File | What it does |
|---|---|
| `mission2.py` | rover v2 environment + oracle/random reference policies |
| `run_eval2.py` | batched vLLM evaluator (thinking off / `--think`), per-step metrics |
| `run_api.py` | same missions, same prompt and parser, for API models |
| `merge_stack.py` | merges LoRA stacks into a vLLM-servable checkpoint |
| `summarize2.py` | results table with CIs and paired tests |
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
