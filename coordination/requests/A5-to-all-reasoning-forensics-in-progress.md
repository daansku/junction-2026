# A5 -> all: Truth-Diffed Reasoning Forensics Tool (`A5-24`, Human Request Sat 19:25)

**Owner:** A5 (LENS)
**Status:** **COMPLETED & PUSHED** (finished Sat 19:52 Helsinki — file lock released; VM redeploy requested in `A5-to-A2-deploy-reasoning-forensics.md`)

Per human request, A5 is building and deploying a **Truth-Diffed Reasoning Forensics** pipeline to diagnose *why* models fail using their per-step reasoning messages (`step.reasoning` + `step.hypothesis`) contrasted against engine `truth`.

## Files A5 Is Actively Editing (All Inside A5's Existing Scope)
- `analysis/src/analysis/explain.py`
- `analysis/src/analysis/claim_check.py`
- `analysis/src/analysis/cli.py`
- `analysis/tests/test_analysis.py`
- `analysis/METRICS.md`
- `data/fixtures/derived/explanations.json`
- `web/src/features/play/epistemicApi.ts`
- `web/src/features/insights/InsightsPage.tsx` & `web/src/features/insights/insights.css`
- `web/src/features/replay/ReplayPage.tsx` & `web/src/features/replay/replay.css`

*(No files in `engine/`, `server/`, `arena/`, `bench/`, `posttrain/`, `video/`, `web/src/features/challenge/`, or `web/src/lib/{api,mock,types}.ts` will be touched.)*

## Contract Compatibility Guarantee (Zero Breaking Changes)
`data/derived/explanations.json` keeps its existing array structure (`generated_at`, `judge_model`, `explanations[]` with `run_id, game_id, player_id, level, step, rule, verdict, explanation, evidence_quote, judge_model`) and adds **strictly additive** forensic fields + top-level summary rollups:
- Per-explanation additive fields:
  - `harness_version`: `"h1" | "h2"`
  - `collection`: `"dev" | "eval-v1" | "eval-v2" | ...`
  - `reasoning_source`: `"cot" | "notes" | "hypothesis_only" | "none"` (handles `h2` CoT vs `h1` rolling notes vs Gemini Pro encrypted thoughts)
  - `cognitive_stage`: `"perception" | "rule_induction" | "belief_updating" | "spatial_planning" | "budget_management"`
  - `root_cause`: fine-grained reason slug (`coordinate_misread`, `unprobed_new_rule`, `false_rule_hypothesis`, `ignored_falsifying_feedback`, `knew_rule_failed_rollout`, `sunk_cost_late_reset`, `hazard_collision`)
  - `deduced_rule_in_cot`: `bool` (separates *"never induced the rule"* from the **Knowing–Doing Gap**: *"stated the rule in `<think>`/notes, then failed spatial execution"*)
  - `truth_contrast`: 1-sentence deterministic contrast between what the model claimed vs what engine `truth` recorded at `step`
  - `quote_source`: `"reasoning" | "hypothesis" | null` (`evidence_quote` verified as an exact substring of either `step.reasoning` or `step.hypothesis`)
- Top-level additive summary (`summary`):
  - `by_cognitive_stage`, `by_model`, `by_harness`, and `knowing_doing_gap_rate` for `/insights`, `deck`, and `A6`/`A7` consumption.
