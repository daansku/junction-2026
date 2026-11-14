# Fine-tune benchmarks (for A3)

Evaluate the base model, the format-only control and the fine-tuned model on every item below, with the same server, prompts and greedy decoding. Run all of them with `lm-evaluation-harness`, and look up the exact task names in the installed version.

## Primary suite

| # | Benchmark | Field | Setting | Items |
|---|---|---|---|---|
| 1 | Big-Bench Hard (all 27 tasks) | logic, state tracking, spatial, language | 3-shot, chain of thought | ~6.5k |
| 2 | MATH | maths | 0-shot, chain of thought | 5,000 |
| 3 | GSM8K | maths | 8-shot, chain of thought | 1,319 |
| 4 | MedQA-USMLE, 4 options | medicine | 0-shot | 1,273 |
| 5 | MMLU-Pro: health | medicine | 5-shot | full subject |
| 6 | MMLU-Pro: law | law | 5-shot | full subject |

**Headline metric:** the unweighted mean accuracy over rows 1–6 (the "far-transfer score").

## Negative control

| Benchmark | Field | Setting |
|---|---|---|
| MMLU-Pro: history | knowledge recall | 5-shot |

This must not move. If it rises as much as the suite, the gain comes from answer formatting, not reasoning.

## Secondary: pre-declared BBH subset

These tasks are reported separately, as the place a gain is most plausible:
- tracking shuffled objects
- navigate
- logical deduction
- web of lies
- temporal sequences

## Notes

- Commit this list, the shot counts and the subsample seed before training starts.
- If time is short, run the full suite on base, control and the final model, and a fixed 1,000-item random subsample on the intermediate checkpoints.
- The base model's scores should be close to its published numbers before the fine-tuned model's scores mean anything.
