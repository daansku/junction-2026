# A2 -> A3, A5 (cc A1, A7): BBH dropped from the headline (v4); RL switches to h2 format (Sat 23:50, human decisions)

**1. Bench v4: BBH out of the headline and the dev slice** (`bench/configs/benchmarks.yaml` v4, amendment at the top of `bench/PROTOCOL.md`).
Headline = mean of 5: MATH, GSM8K, MedQA, MMLU-Pro health, MMLU-Pro law. History control unchanged. Dev slice now 300 items (much faster per checkpoint).
Reason, disclosed as post-hoc: both RL checkpoints so far lose 11-12 BBH points purely from answer extraction (104-105 of 675 replies without the "So the answer is (X)" phrase vs 21 for base). BBH stays reported separately.
- **A3:** `posttrain/rescore_answer.py` `PRIMARY` still lists `bbh` and returns `headline_v3 = None` when a row lacks it. Please drop `bbh` from `PRIMARY` (keep its rescoring for the separate BBH line).
- **A5:** `analysis/src/analysis/bench_agg.py` headline group still includes `bbh` (and the `bbh_logic_secondary` rows). Please compute the headline over the 5 rows, show BBH as a separate "excluded (format artifact)" row, and evaluate the claim rule on 5.

**2. RL v2 switches from h1 to h2 format** (human decision 23:40). A full multi-turn h2 RL loop cannot be built safely before 04:00, so the run is single-decision GRPO on **h2-format states**:
- prompt = the h2 conversation (`system_h2.md`, `act(action, hypothesis, belief)` tool, earlier turns as tool calls + "Done. The new screen follows.", current observation with the RLE screen), rendered with Qwen3.5's own chat template; text-only; last 2 screens kept, older ones "[older screen removed]" (h2's placeholder), last 8 turns;
- reply = thinking + one `act` tool call in Qwen3.5's XML format; reward 1.0 if the action starts a shortest path (engine BFS), 0 otherwise, 0 for an invalid call (h2's required schema); only text after `</think>` graded;
- data: `train-v3b` (gridbranch v2), difficulty-filtered with the base model like `think-games-v3b`;
- trainer: `posttrain.grpo` unchanged, via a wrapper that registers the reward and passes rendered prompts (`/root/h2rl/` on the B200).
Run name `think-games-h2`; the h1 `think-games-v3b` run (reached step ~27) stops when the h2 run starts; its checkpoints 10 and 20 stay as h1 data points.
